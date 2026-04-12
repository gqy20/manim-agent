"""MiniMax TTS client.

Prefers synchronous HTTP synthesis for lower latency, and falls back to the
async long-text workflow when sync is unavailable or the input is too long.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

API_BASE_URL = "https://api.minimaxi.com"
API_BASE_URL_BJ = "https://api-bj.minimaxi.com"

SYNC_TTS_PATH = "/v1/t2a_v2"
CREATE_TASK_PATH = "/v1/t2a_async_v2"
QUERY_TASK_PATHS = (
    "/v1/query/t2a_async_query_v2",
    "/v1/t2a_async/query",
)
FILE_INFO_PATH = "/v1/files/query"
FILE_RETRIEVE_PATH = "/v1/files/retrieve"

POLL_INTERVAL = 1
POLL_TIMEOUT = 300
DOWNLOAD_MAX_RETRIES = 3
SYNC_TEXT_LIMIT = 10_000

DEFAULT_MODEL = "speech-2.8-hd"
DEFAULT_VOICE_ID = "female-tianmei"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TTSResult:
    audio_path: str
    subtitle_path: str
    extra_info_path: str
    duration_ms: int
    word_count: int
    usage_characters: int
    mode: str = "async"


def _check_api_key() -> str:
    api_key = os.environ.get("MINIMAX_API_KEY", "")
    if not api_key.strip():
        raise RuntimeError(
            "MINIMAX_API_KEY (MiniMax API Key) is required but not set or empty. "
            "Please set it before running: export MINIMAX_API_KEY='your-key'"
        )
    return api_key.strip()


def _get_base_url() -> str:
    return os.environ.get("MINIMAX_API_BASE_URL", API_BASE_URL)


def _safe_parse_json_response(resp: httpx.Response, context: str) -> dict[str, Any]:
    if resp.status_code >= 400:
        raise RuntimeError(f"{context} failed with HTTP {resp.status_code}: {resp.text[:512]}")

    content_type = resp.headers.get("content-type", "").lower()
    if "application/json" not in content_type:
        raise RuntimeError(
            f"{context} returned non-JSON content-type '{content_type}': {resp.text[:128]}"
        )

    try:
        data = resp.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{context} returned invalid JSON: {resp.text[:256]}") from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"{context} returned non-object payload: {data!r}")
    return data


def _extract_task_payload(raw: dict[str, Any]) -> dict[str, Any]:
    data = raw.get("data")
    if isinstance(data, dict):
        return data
    return raw


def _coerce_status(payload: dict[str, Any]) -> str:
    status = payload.get("task_status") or payload.get("status")
    if isinstance(status, str):
        return status
    return ""


def _coerce_error(payload: dict[str, Any], base_resp: dict[str, Any]) -> str:
    for field in ("error_message", "error", "msg"):
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            return value

    status_msg = base_resp.get("status_msg")
    if isinstance(status_msg, str) and status_msg.strip():
        return status_msg
    return "Unknown failure"


def _coerce_identifier(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _coerce_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _build_sync_payload(
    text: str,
    *,
    voice_id: str = DEFAULT_VOICE_ID,
    model: str = DEFAULT_MODEL,
    speed: float = 1.0,
    emotion: str | None = None,
) -> dict[str, Any]:
    if not text or not text.strip():
        raise ValueError("text must be a non-empty string")

    return {
        "model": model,
        "text": text.strip(),
        "stream": False,
        "language_boost": "auto",
        "voice_setting": {
            "voice_id": voice_id,
            "speed": speed,
            "vol": 1.0,
            "pitch": 0,
            "emotion": emotion,
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
            "channel": 1,
        },
        "subtitle_enable": False,
    }


def _build_async_payload(
    text: str,
    *,
    voice_id: str = DEFAULT_VOICE_ID,
    model: str = DEFAULT_MODEL,
    speed: float = 1.0,
    emotion: str | None = None,
) -> dict[str, Any]:
    payload = _build_sync_payload(
        text,
        voice_id=voice_id,
        model=model,
        speed=speed,
        emotion=emotion,
    )
    payload["audio_setting"] = {
        "audio_sample_rate": 32000,
        "bitrate": 128000,
        "format": "mp3",
        "channel": 1,
    }
    payload.pop("stream", None)
    payload.pop("subtitle_enable", None)
    return payload


def _build_payload(
    text: str,
    *,
    voice_id: str = DEFAULT_VOICE_ID,
    model: str = DEFAULT_MODEL,
    speed: float = 1.0,
    emotion: str | None = None,
) -> dict[str, Any]:
    """Backward-compatible alias for the async payload format."""
    return _build_async_payload(
        text,
        voice_id=voice_id,
        model=model,
        speed=speed,
        emotion=emotion,
    )


def _write_sync_audio_file(audio_hex: str, output_path: Path) -> str:
    if not audio_hex:
        raise RuntimeError("TTS sync response missing audio payload")

    try:
        audio_bytes = bytes.fromhex(audio_hex)
    except ValueError as exc:
        raise RuntimeError("TTS sync response returned invalid hex audio") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(audio_bytes)
    return str(output_path)


async def _synthesize_sync(
    text: str,
    *,
    voice_id: str,
    model: str,
    output_dir: str,
    speed: float,
    emotion: str | None,
) -> TTSResult:
    api_key = _check_api_key()
    base_url = _get_base_url()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = _build_sync_payload(
        text,
        voice_id=voice_id,
        model=model,
        speed=speed,
        emotion=emotion,
    )

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{base_url}{SYNC_TTS_PATH}",
            json=payload,
            headers=headers,
        )

    data = _safe_parse_json_response(resp, "TTS sync synthesis")
    base_resp = data.get("base_resp", {})
    if not isinstance(base_resp, dict):
        base_resp = {}
    if base_resp.get("status_code", -1) != 0:
        raise RuntimeError(
            f"TTS sync synthesis failed: [{base_resp.get('status_code')}] "
            f"{base_resp.get('status_msg', 'Unknown error')}"
        )

    payload_data = _extract_task_payload(data)
    audio_path = _write_sync_audio_file(
        str(payload_data.get("audio", "")).strip(),
        Path(output_dir) / "audio.mp3",
    )

    extra_info = data.get("extra_info")
    if not isinstance(extra_info, dict):
        extra_info = {}

    extra_info_path = Path(output_dir) / "extra_info.json"
    extra_info_path.parent.mkdir(parents=True, exist_ok=True)
    extra_info_path.write_text(
        json.dumps(extra_info, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return TTSResult(
        audio_path=audio_path,
        subtitle_path="",
        extra_info_path=str(extra_info_path),
        duration_ms=_coerce_int(extra_info.get("audio_length")),
        word_count=_coerce_int(extra_info.get("word_count")),
        usage_characters=_coerce_int(extra_info.get("usage_characters")),
        mode="sync",
    )


async def _create_task(_text: str, payload: dict[str, Any]) -> dict[str, str]:
    api_key = _check_api_key()
    base_url = _get_base_url()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{base_url}{CREATE_TASK_PATH}",
            json=payload,
            headers=headers,
        )

    data = _safe_parse_json_response(resp, "TTS task creation")
    base_resp = data.get("base_resp", {})
    if not isinstance(base_resp, dict):
        base_resp = {}
    status_code = base_resp.get("status_code", -1)

    if status_code != 0:
        status_msg = base_resp.get("status_msg", "Unknown error")
        raise RuntimeError(f"TTS task creation failed: [{status_code}] {status_msg}")

    task_data = _extract_task_payload(data)
    return {
        "task_id": _coerce_identifier(task_data.get("task_id")),
        "file_id": _coerce_identifier(task_data.get("file_id")),
        "file_id_subtitle": _coerce_identifier(task_data.get("file_id_subtitle")),
        "file_id_extra": _coerce_identifier(task_data.get("file_id_extra")),
    }


async def _poll_task(task_id: Any) -> dict[str, Any]:
    task_id = _coerce_identifier(task_id)
    if not task_id:
        raise RuntimeError("TTS polling failed: task_id is empty")

    api_key = _check_api_key()
    base_url = _get_base_url()
    headers = {"Authorization": f"Bearer {api_key}"}
    deadline = asyncio.get_event_loop().time() + POLL_TIMEOUT

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            last_error: str | None = None
            last_data: dict[str, Any] | None = None
            last_status = ""

            for path in QUERY_TASK_PATHS:
                try:
                    resp = await client.get(
                        f"{base_url}{path}",
                        params={"task_id": task_id},
                        headers=headers,
                    )
                except httpx.HTTPError as exc:
                    last_error = str(exc)
                    continue

                try:
                    data = _safe_parse_json_response(resp, "TTS task query")
                except RuntimeError as exc:
                    if resp.status_code == 404 and path == QUERY_TASK_PATHS[0]:
                        last_error = str(exc)
                        continue
                    raise

                base_resp = data.get("base_resp", {})
                if not isinstance(base_resp, dict):
                    base_resp = {}

                if base_resp.get("status_code", 0) != 0:
                    task_data = _extract_task_payload(data)
                    raise RuntimeError(
                        f"TTS task query failed: {base_resp.get('status_code')}: "
                        f"{_coerce_error(task_data, base_resp)}"
                    )

                task_data = _extract_task_payload(data)
                status = _coerce_status(task_data)
                last_status = status
                last_data = task_data

                if status.lower() == "success":
                    return task_data
                if status.lower() == "failed":
                    raise RuntimeError(f"TTS task failed: {_coerce_error(task_data, base_resp)}")
                break

            if last_data is None:
                if last_error:
                    raise RuntimeError(f"TTS polling failed: {last_error}")
                raise RuntimeError("TTS polling failed: no valid query response")

            if asyncio.get_event_loop().time() > deadline:
                raise TimeoutError(
                    f"TTS polling timeout after {POLL_TIMEOUT}s "
                    f"(task_id={task_id}, last_status={last_status})"
                )

            await asyncio.sleep(POLL_INTERVAL)


async def _download_file(
    file_id: str,
    output_path: Path,
    api_key: str,
    base_url: str,
) -> None:
    headers = {"Authorization": f"Bearer {api_key}"}

    for attempt in range(1, DOWNLOAD_MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                download_url = ""

                file_resp = await client.get(
                    f"{base_url}{FILE_RETRIEVE_PATH}",
                    params={"file_id": file_id},
                    headers=headers,
                )
                if file_resp.status_code == 404:
                    legacy_resp = await client.post(
                        f"{base_url}{FILE_INFO_PATH}",
                        json={"file_id": file_id},
                        headers=headers,
                    )
                    legacy_data = _safe_parse_json_response(legacy_resp, "TTS file query")
                    legacy_payload = _extract_task_payload(legacy_data)
                    if isinstance(legacy_payload, dict):
                        download_url = str(legacy_payload.get("file_url", "")).strip()
                else:
                    file_data = _safe_parse_json_response(file_resp, "TTS file retrieve")
                    file_info = file_data.get("file")
                    if isinstance(file_info, dict):
                        download_url = str(file_info.get("download_url", "")).strip()

                if not download_url:
                    raise RuntimeError(f"No download URL for file_id={file_id}")

                dl_resp = await client.get(download_url)
                dl_resp.raise_for_status()

                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(dl_resp.content)
                return

        except Exception as exc:
            if attempt == DOWNLOAD_MAX_RETRIES:
                raise RuntimeError(
                    f"Failed to download file_id={file_id} after "
                    f"{DOWNLOAD_MAX_RETRIES} attempts: {exc}"
                ) from exc
            await asyncio.sleep(2**attempt)


async def _download_files(
    file_ids: dict[str, str],
    output_dir: str,
) -> dict[str, str]:
    api_key = _check_api_key()
    base_url = _get_base_url()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    paths: dict[str, str] = {}
    key_to_filename = {
        "audio": "audio.mp3",
        "subtitle": "subtitle.srt",
        "extra": "extra_info.json",
    }

    for key, filename in key_to_filename.items():
        fid = file_ids.get(key, "")
        if not fid:
            continue
        target = out / filename
        await _download_file(fid, target, api_key, base_url)
        paths[key] = str(target)

    return paths


async def synthesize(
    text: str,
    voice_id: str = DEFAULT_VOICE_ID,
    model: str = DEFAULT_MODEL,
    output_dir: str = "./output",
    speed: float = 1.0,
    emotion: str | None = None,
) -> TTSResult:
    _check_api_key()
    normalized_text = text.strip()

    if len(normalized_text) <= SYNC_TEXT_LIMIT:
        try:
            return await _synthesize_sync(
                normalized_text,
                voice_id=voice_id,
                model=model,
                output_dir=output_dir,
                speed=speed,
                emotion=emotion,
            )
        except Exception as exc:
            logger.warning("Sync TTS failed, falling back to async mode: %s", exc)

    payload = _build_async_payload(
        normalized_text,
        voice_id=voice_id,
        model=model,
        speed=speed,
        emotion=emotion,
    )
    task_info = await _create_task(normalized_text, payload)
    result_data = await _poll_task(task_info["task_id"])

    file_ids = {
        "audio": task_info["file_id"],
        "subtitle": task_info["file_id_subtitle"],
        "extra": task_info["file_id_extra"],
    }
    paths = await _download_files(file_ids, output_dir)

    return TTSResult(
        audio_path=paths.get("audio", ""),
        subtitle_path=paths.get("subtitle", ""),
        extra_info_path=paths.get("extra", ""),
        duration_ms=_coerce_int(result_data.get("audio_length")),
        word_count=_coerce_int(result_data.get("word_count")),
        usage_characters=_coerce_int(result_data.get("usage_characters")),
        mode="async",
    )
