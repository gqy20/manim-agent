"""MiniMax 异步 TTS 客户端。

封装 MiniMax speech-2.8-hd 模型的异步语音合成全流程：
创建任务 → 轮询状态 → 下载音频/字幕/元信息文件。
"""

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

# ── 常量 ──────────────────────────────────────────────────────

API_BASE_URL = "https://api.minimaxi.com"
API_BASE_URL_BJ = "https://api-bj.minimaxi.com"

CREATE_TASK_PATH = "/v1/t2a_async_v2"
QUERY_TASK_PATHS = (
    "/v1/query/t2a_async_query_v2",
    "/v1/t2a_async/query",
)
FILE_INFO_PATH = "/v1/files/query"

POLL_INTERVAL = 3  # 秒
POLL_TIMEOUT = 300  # 秒
DOWNLOAD_MAX_RETRIES = 3

DEFAULT_MODEL = "speech-2.8-hd"
DEFAULT_VOICE_ID = "female-tianmei"

# ── 数据类 ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class TTSResult:
    """TTS 合成结果。"""

    audio_path: str
    subtitle_path: str
    extra_info_path: str
    duration_ms: int
    word_count: int
    usage_characters: int


# ── 内部函数 ──────────────────────────────────────────────────


def _check_api_key() -> str:
    """检查 API Key 是否存在且非空。

    Returns:
        API Key 字符串。

    Raises:
        RuntimeError: 环境变量缺失或为空。
    """
    api_key = os.environ.get("MINIMAX_API_KEY", "")
    if not api_key.strip():
        raise RuntimeError(
            "MINIMAX_API_KEY (MiniMax API Key) is required but not set or empty. "
            "Please set it before running: export MINIMAX_API_KEY='your-key'"
        )
    return api_key.strip()


def _get_base_url() -> str:
    """获取 API 基础 URL，支持备用地址。"""
    return os.environ.get("MINIMAX_API_BASE_URL", API_BASE_URL)


def _safe_parse_json_response(resp: httpx.Response, context: str) -> dict[str, Any]:
    """Parse JSON response and provide useful error context."""
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


def _build_payload(
    text: str,
    *,
    voice_id: str = DEFAULT_VOICE_ID,
    model: str = DEFAULT_MODEL,
    speed: float = 1.0,
    emotion: str | None = None,
) -> dict:
    """构建 TTS 请求体。

    Args:
        text: 待合成文本。
        voice_id: 音色 ID。
        model: 模型名称。
        speed: 语速（0.5-2.0）。
        emotion: 语气情感。

    Returns:
        请求字典。

    Raises:
        ValueError: 文本为空或纯空白。
    """
    if not text or not text.strip():
        raise ValueError("text must be a non-empty string")

    return {
        "model": model,
        "text": text.strip(),
        "language_boost": "auto",
        "voice_setting": {
            "voice_id": voice_id,
            "speed": speed,
            "vol": 1.0,
            "pitch": 0,
            "emotion": emotion,
        },
        "audio_setting": {
            "audio_sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
            "channel": 1,
        },
    }


async def _create_task(
    text: str,
    payload: dict,
) -> dict:
    """创建异步 TTS 任务。

    Args:
        text: 原始文本（用于日志）。
        payload: 请求体。

    Returns:
        包含 task_id, file_id 等的字典。

    Raises:
        RuntimeError: API 返回错误。
    """
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
        raise RuntimeError(
            f"TTS task creation failed: [{status_code}] {status_msg}"
        )

    task_data = _extract_task_payload(data)
    return {
        "task_id": task_data.get("task_id", ""),
        "file_id": task_data.get("file_id", ""),
        "file_id_subtitle": task_data.get("file_id_subtitle", ""),
        "file_id_extra": task_data.get("file_id_extra", ""),
    }


async def _poll_task(task_id: str) -> dict:
    """轮询任务状态直到完成或超时。

    Args:
        task_id: 任务 ID。

    Returns:
        成功时的 data 字典。

    Raises:
        TimeoutError: 轮询超时。
        RuntimeError: 任务失败。
    """
    if not task_id.strip():
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
                    error_msg = _coerce_error(task_data, base_resp)
                    raise RuntimeError(f"TTS task failed: {error_msg}")
                break

            if last_data is None:
                if last_error:
                    raise RuntimeError(f"TTS polling failed: {last_error}")
                raise RuntimeError("TTS polling failed: no valid query response")

            # 检查超时
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
    """下载单个文件（含重试）。"""
    headers = {"Authorization": f"Bearer {api_key}"}

    for attempt in range(1, DOWNLOAD_MAX_RETRIES + 1):
        try:
            # 先查询文件下载 URL
            async with httpx.AsyncClient(timeout=30) as client:
                file_resp = await client.post(
                    f"{base_url}{FILE_INFO_PATH}",
                    json={"file_id": file_id},
                    headers=headers,
                )
                file_data = file_resp.json().get("data", {})
                download_url = file_data.get("file_url", "")

                if not download_url:
                    raise RuntimeError(
                        f"No download URL for file_id={file_id}"
                    )

                # 下载文件内容
                dl_resp = await client.get(download_url)
                dl_resp.raise_for_status()

                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(dl_resp.content)
                return

        except Exception as e:
            if attempt == DOWNLOAD_MAX_RETRIES:
                raise RuntimeError(
                    f"Failed to download file_id={file_id} after "
                    f"{DOWNLOAD_MAX_RETRIES} attempts: {e}"
                ) from e
            await asyncio.sleep(2**attempt)


async def _download_files(
    file_ids: dict[str, str],
    output_dir: str,
) -> dict[str, str]:
    """下载所有产物文件。

    Args:
        file_ids: {"audio": id, "subtitle": id, "extra": id}。
        output_dir: 输出目录。

    Returns:
        文件路径映射。
    """
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


# ── 公共接口 ──────────────────────────────────────────────────


async def synthesize(
    text: str,
    voice_id: str = DEFAULT_VOICE_ID,
    model: str = DEFAULT_MODEL,
    output_dir: str = "./output",
    speed: float = 1.0,
    emotion: str | None = None,
) -> TTSResult:
    """异步合成语音。

    流程：
    1. 校验 API Key 和输入参数
    2. POST 创建异步任务 → 获得 task_id + file_ids
    3. GET 轮询任务状态（间隔 POLL_INTERVAL，超时 POLL_TIMEOUT）
    4. status=Success 时下载 3 个文件到 output_dir
    5. 返回 TTSResult

    Args:
        text: 待合成的脚本文本。
        voice_id: MiniMax 音色 ID。
        model: TTS 模型名称。
        output_dir: 输出目录。
        speed: 语速（0.5-2.0）。
        emotion: 语气情感（speech-2.8-hd 支持）。

    Returns:
        TTSResult 数据类，包含所有产物的本地路径和统计信息。
    """
    _check_api_key()
    payload = _build_payload(
        text,
        voice_id=voice_id,
        model=model,
        speed=speed,
        emotion=emotion,
    )

    task_info = await _create_task(text, payload)
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
        duration_ms=result_data.get("audio_length", 0),
        word_count=result_data.get("word_count", 0),
        usage_characters=result_data.get("usage_characters", 0),
    )
