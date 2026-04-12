"""MiniMax music generation client for instrumental background music."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

API_BASE_URL = "https://api.minimaxi.com"
MUSIC_GENERATION_PATH = "/v1/music_generation"
DEFAULT_MODEL = "music-2.6"
DEFAULT_FORMAT = "mp3"
DEFAULT_SAMPLE_RATE = 44100
DEFAULT_BITRATE = 256000
DEFAULT_TIMEOUT = 300

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MusicResult:
    audio_path: str
    prompt: str
    model: str
    duration_ms: int | None = None


def _check_api_key() -> str:
    api_key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "MINIMAX_API_KEY (MiniMax API Key) is required but not set or empty. "
            "Please set it before running: export MINIMAX_API_KEY='your-key'"
        )
    return api_key


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


def _extract_download_url(data: dict[str, Any]) -> str:
    candidates: list[str] = []

    def _collect(value: Any) -> None:
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            candidates.append(value)
        elif isinstance(value, dict):
            for nested in value.values():
                _collect(nested)
        elif isinstance(value, list):
            for nested in value:
                _collect(nested)

    _collect(data.get("data"))
    _collect(data)
    for url in candidates:
        lowered = url.lower()
        if lowered.endswith((".mp3", ".wav", ".flac", ".m4a")):
            return url
    if candidates:
        return candidates[0]
    raise RuntimeError("Music generation response did not contain a downloadable audio URL")


def _coerce_duration_ms(data: dict[str, Any]) -> int | None:
    candidates = [
        data.get("duration_ms"),
        data.get("audio_length"),
        data.get("duration"),
        (data.get("data") or {}).get("duration_ms") if isinstance(data.get("data"), dict) else None,
    ]
    for value in candidates:
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value if value >= 0 else None
        if isinstance(value, float):
            return int(value) if value >= 0 else None
        if isinstance(value, str):
            try:
                parsed = int(float(value))
            except ValueError:
                continue
            return parsed if parsed >= 0 else None
    return None


def _build_payload(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    output_format: str = "url",
) -> dict[str, Any]:
    normalized_prompt = prompt.strip()
    if not normalized_prompt:
        raise ValueError("prompt must be a non-empty string")

    return {
        "model": model,
        "prompt": normalized_prompt,
        "is_instrumental": True,
        "audio_setting": {
            "sample_rate": DEFAULT_SAMPLE_RATE,
            "bitrate": DEFAULT_BITRATE,
            "format": DEFAULT_FORMAT,
        },
        "output_format": output_format,
    }


async def _download_file(download_url: str, output_path: Path) -> str:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        response = await client.get(download_url)
        response.raise_for_status()
    output_path.write_bytes(response.content)
    return str(output_path)


async def generate_instrumental(
    prompt: str,
    *,
    output_dir: str = "./output",
    model: str = DEFAULT_MODEL,
) -> MusicResult:
    api_key = _check_api_key()
    payload = _build_payload(prompt, model=model)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        response = await client.post(
            f"{_get_base_url()}{MUSIC_GENERATION_PATH}",
            json=payload,
            headers=headers,
        )

    data = _safe_parse_json_response(response, "Music generation")
    download_url = _extract_download_url(data)
    target_path = Path(output_dir) / "bgm.mp3"
    audio_path = await _download_file(download_url, target_path)

    return MusicResult(
        audio_path=audio_path,
        prompt=prompt.strip(),
        model=model,
        duration_ms=_coerce_duration_ms(data),
    )
