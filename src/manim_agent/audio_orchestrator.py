"""Beat-level narration, TTS, and BGM orchestration helpers."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from . import music_client, tts_client, video_builder
from .audio_normalizer import normalize_audio_to_duration
from .beat_schema import AudioOrchestrationResult, BeatSpec
from .subtitle_builder import write_timeline_srt
from .timeline_builder import finalize_timeline, write_timeline_file

logger = logging.getLogger(__name__)


def _build_default_bgm_prompt(user_text: str, preset: str, narration_text: str) -> str:
    preset_style = {
        "educational": "calm educational underscore, soft piano and light strings",
        "presentation": "clean modern underscore, light piano and gentle ambient textures",
        "proof": "subtle thoughtful underscore, restrained piano and low strings",
        "concept": "clear contemporary underscore, piano and marimba with light ambient texture",
        "default": "calm instrumental underscore, soft piano and light strings",
    }.get(preset, "calm instrumental underscore, soft piano and light strings")
    topic_hint = user_text.strip() or narration_text.strip() or "a narrated math explainer"
    return (
        f"{preset_style}, background music for a narrated explainer video about {topic_hint}, "
        "instrumental only, no vocals, non-distracting, low intensity, supportive, "
        "steady pacing, suitable under spoken narration"
    )


def _parse_narration_hint(entry: str) -> str:
    if "->" in entry:
        return entry.split("->", 1)[1].strip()
    return entry.strip()


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _coerce_duration_seconds(value: Any) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value) / 1000.0
    return 0.0


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _resolve_tts_artifact_path(
    *,
    raw_path: str | None,
    output_root: Path,
    beat_id: str,
    artifact_name: str,
    required: bool = False,
    non_empty: bool = False,
) -> str | None:
    path_text = _optional_str(raw_path)
    if path_text is None:
        if required:
            raise RuntimeError(f"TTS did not return {artifact_name} for {beat_id}.")
        return None

    path = Path(path_text)
    if not path.is_absolute():
        path = output_root / path
    path = path.resolve()

    if not _is_relative_to(path, output_root):
        raise RuntimeError(
            f"TTS returned {artifact_name} outside task output directory for {beat_id}: {path}"
        )
    if not path.exists():
        raise RuntimeError(f"TTS {artifact_name} file for {beat_id} does not exist: {path}")
    if not path.is_file():
        raise RuntimeError(f"TTS {artifact_name} path for {beat_id} is not a file: {path}")
    if non_empty and path.stat().st_size <= 0:
        raise RuntimeError(f"TTS {artifact_name} file for {beat_id} is empty: {path}")
    return str(path)


def _write_audio_manifest(beats: list[BeatSpec], output_path: str) -> str:
    payload = {
        "beats": [
            {
                "id": beat.id,
                "title": beat.title,
                "audio_path": beat.audio_path,
                "normalized_audio_path": beat.normalized_audio_path,
                "audio_exists": Path(beat.audio_path).exists() if beat.audio_path else False,
                "audio_size_bytes": (
                    Path(beat.audio_path).stat().st_size
                    if beat.audio_path and Path(beat.audio_path).exists()
                    else None
                ),
                "subtitle_path": beat.subtitle_path,
                "extra_info_path": beat.extra_info_path,
                "tts_mode": beat.tts_mode,
                "duration_seconds": beat.actual_audio_duration_seconds,
                "target_duration_seconds": beat.target_duration_seconds,
                "normalization_strategy": beat.normalization_strategy,
            }
            for beat in beats
        ]
    }
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def build_beats_from_pipeline_output(
    *,
    implemented_beats: list[str],
    beat_to_narration_map: list[str],
    fallback_narration: str | None = None,
    po: Any | None = None,
) -> list[BeatSpec]:
    """Construct stable beat records from existing pipeline output fields."""
    beats: list[BeatSpec] = []

    structured_beats = list(getattr(po, "beats", []) or []) if po is not None else []
    if structured_beats:
        for index, raw in enumerate(structured_beats, start=1):
            if not isinstance(raw, dict):
                raw = raw.model_dump() if hasattr(raw, "model_dump") else {}
            beat_id = str(raw.get("id") or raw.get("beat_id") or f"beat_{index:03d}")
            title = str(raw.get("title") or beat_id)
            beats.append(
                BeatSpec(
                    id=beat_id,
                    title=title,
                    narration_hint=_optional_str(raw.get("narration_hint")),
                    narration_text=_optional_str(raw.get("narration_text")),
                    target_duration_seconds=raw.get("target_duration_seconds"),
                )
            )
        _apply_rendered_segment_durations(beats, po)
        return beats

    hints = [_parse_narration_hint(entry) for entry in beat_to_narration_map if entry.strip()]

    if implemented_beats:
        for index, title in enumerate(implemented_beats, start=1):
            hint = hints[index - 1] if index - 1 < len(hints) else None
            beats.append(
                BeatSpec(
                    id=f"beat_{index:03d}",
                    title=title.strip() or f"Beat {index}",
                    narration_hint=hint,
                )
            )
        _apply_rendered_segment_durations(beats, po)
        return beats

    raise RuntimeError(
        "Beat structure is required for audio orchestration. "
        "Pipeline output did not provide implemented_beats."
    )


def _apply_rendered_segment_durations(beats: list[BeatSpec], po: Any | None) -> None:
    if po is None:
        return
    segments = list(getattr(po, "rendered_segments", []) or [])
    by_id: dict[str, Any] = {}
    for segment in segments:
        data = segment.model_dump() if hasattr(segment, "model_dump") else segment
        if isinstance(data, dict) and data.get("beat_id"):
            by_id[str(data["beat_id"])] = data
    for beat in beats:
        data = by_id.get(beat.id)
        if not data:
            continue
        duration = data.get("duration_seconds")
        if isinstance(duration, (int, float)) and duration > 0:
            beat.target_duration_seconds = float(duration)


def _apply_phase35_beat_narrations(beats: list[BeatSpec], po: Any) -> None:
    narration_output = getattr(po, "phase3_5_narration", None)
    beat_narrations = list(getattr(narration_output, "beat_narrations", []) or [])
    by_id: dict[str, Any] = {}
    for item in beat_narrations:
        data = item.model_dump() if hasattr(item, "model_dump") else item
        if isinstance(data, dict) and data.get("beat_id"):
            by_id[str(data["beat_id"])] = data
    for beat in beats:
        data = by_id.get(beat.id)
        if not data:
            continue
        text = _optional_str(data.get("text"))
        if text:
            beat.narration_text = text
        duration = data.get("target_duration_seconds")
        if isinstance(duration, (int, float)) and duration > 0 and not beat.target_duration_seconds:
            beat.target_duration_seconds = float(duration)


async def generate_beat_narrations(
    *,
    beats: list[BeatSpec],
    user_text: str,
    plan_text: str,
    build_summary: str | None,
    target_duration_seconds: int,
    fallback_full_narration: str | None = None,
) -> list[BeatSpec]:
    """Populate beat narration text with simple deterministic fallbacks."""
    del user_text, plan_text, build_summary, target_duration_seconds

    if len(beats) == 1 and not beats[0].narration_text and fallback_full_narration:
        beats[0].narration_text = fallback_full_narration.strip()
        return beats

    for beat in beats:
        if beat.narration_text and beat.narration_text.strip():
            beat.narration_text = beat.narration_text.strip()
            continue
        if beat.narration_hint:
            beat.narration_text = beat.narration_hint
        else:
            beat.narration_text = beat.title
    return beats


async def synthesize_beat_tts(
    *,
    beats: list[BeatSpec],
    voice_id: str,
    model: str,
    output_dir: str,
    concurrency: int = 2,
) -> list[BeatSpec]:
    """Synthesize TTS for each beat with bounded concurrency."""
    semaphore = asyncio.Semaphore(max(1, concurrency))
    root = Path(output_dir).resolve()

    async def _run(beat: BeatSpec) -> BeatSpec:
        async with semaphore:
            beat_dir = root / "audio" / beat.id
            result = await tts_client.synthesize(
                text=beat.narration_text or beat.title,
                voice_id=voice_id,
                model=model,
                output_dir=str(beat_dir),
            )
            beat.audio_path = _resolve_tts_artifact_path(
                raw_path=getattr(result, "audio_path", None),
                output_root=root,
                beat_id=beat.id,
                artifact_name="audio",
                required=True,
                non_empty=True,
            )
            beat.subtitle_path = _resolve_tts_artifact_path(
                raw_path=getattr(result, "subtitle_path", None),
                output_root=root,
                beat_id=beat.id,
                artifact_name="subtitle",
            )
            beat.extra_info_path = _resolve_tts_artifact_path(
                raw_path=getattr(result, "extra_info_path", None),
                output_root=root,
                beat_id=beat.id,
                artifact_name="extra info",
            )
            beat.tts_mode = _optional_str(getattr(result, "mode", None))
            beat.actual_audio_duration_seconds = _coerce_duration_seconds(
                getattr(result, "duration_ms", 0)
            )
            return beat

    return list(await asyncio.gather(*(_run(beat) for beat in beats)))


async def normalize_beat_audios(
    *,
    beats: list[BeatSpec],
    output_dir: str,
    concurrency: int = 2,
) -> list[BeatSpec]:
    """Fit each synthesized beat audio file into its visual beat duration."""
    semaphore = asyncio.Semaphore(max(1, concurrency))
    root = Path(output_dir).resolve()

    async def _run(beat: BeatSpec) -> BeatSpec:
        if not beat.audio_path:
            return beat
        async with semaphore:
            if not Path(beat.audio_path).exists():
                logger.warning(
                    "Skipping beat audio normalization because the source file is missing: %s",
                    beat.audio_path,
                )
                return beat
            target_duration = (
                beat.target_duration_seconds or beat.actual_audio_duration_seconds or 0.0
            )
            output_path = root / "normalized_audio" / f"{beat.id}.mp3"
            result = await normalize_audio_to_duration(
                audio_path=beat.audio_path,
                output_path=str(output_path),
                target_duration_seconds=target_duration,
                actual_duration_seconds=beat.actual_audio_duration_seconds,
            )
            beat.normalized_audio_path = result.output_path
            beat.normalized_audio_duration_seconds = result.duration_seconds
            beat.normalization_strategy = result.strategy
            return beat

    return list(await asyncio.gather(*(_run(beat) for beat in beats)))


async def maybe_generate_bgm(
    *,
    enabled: bool,
    prompt: str | None,
    user_text: str,
    narration_text: str,
    output_dir: str,
    preset: str,
) -> tuple[str | None, int | None, str | None]:
    """Generate BGM when enabled; otherwise return empty metadata."""
    if not enabled:
        return None, None, None

    resolved_prompt = prompt.strip() if prompt and prompt.strip() else _build_default_bgm_prompt(
        user_text, preset, narration_text
    )
    try:
        result = await music_client.generate_instrumental(
            prompt=resolved_prompt,
            output_dir=output_dir,
            model="music-2.6",
        )
    except Exception as exc:
        logger.warning(
            "Background music generation failed. Falling back to narration-only audio: %s",
            exc,
        )
        return None, None, resolved_prompt
    return result.audio_path, result.duration_ms, resolved_prompt


async def orchestrate_audio_assets(
    *,
    po: Any,
    user_text: str,
    plan_text: str,
    target_duration_seconds: int,
    voice_id: str,
    model: str,
    output_dir: str,
    bgm_enabled: bool,
    bgm_prompt: str | None,
    preset: str,
) -> AudioOrchestrationResult:
    """Build beats, synthesize beat audio, run optional BGM, and resolve a timeline."""
    beats = build_beats_from_pipeline_output(
        implemented_beats=list(getattr(po, "implemented_beats", []) or []),
        beat_to_narration_map=list(getattr(po, "beat_to_narration_map", []) or []),
        fallback_narration=getattr(po, "narration", None),
        po=po,
    )
    _apply_phase35_beat_narrations(beats, po)
    beats = await generate_beat_narrations(
        beats=beats,
        user_text=user_text,
        plan_text=plan_text,
        build_summary=getattr(po, "build_summary", None),
        target_duration_seconds=target_duration_seconds,
        fallback_full_narration=getattr(po, "narration", None),
    )

    narration_text = " ".join(filter(None, (beat.narration_text for beat in beats)))
    beats_result, bgm_result = await asyncio.gather(
        synthesize_beat_tts(
            beats=beats,
            voice_id=voice_id,
            model=model,
            output_dir=output_dir,
        ),
        maybe_generate_bgm(
            enabled=bgm_enabled,
            prompt=bgm_prompt,
            user_text=user_text,
            narration_text=narration_text,
            output_dir=output_dir,
            preset=preset,
        ),
    )

    beats_result = await normalize_beat_audios(
        beats=beats_result,
        output_dir=output_dir,
    )

    timeline = finalize_timeline(beats_result)
    timeline_path = write_timeline_file(timeline, str(Path(output_dir) / "timeline.json"))
    timeline_subtitle_path = write_timeline_srt(
        timeline,
        str(Path(output_dir) / "timeline_subtitles.srt"),
    )
    _write_audio_manifest(beats_result, str(Path(output_dir) / "audio_manifest.json"))

    audio_paths = [
        beat.normalized_audio_path or beat.audio_path
        for beat in beats_result
        if beat.normalized_audio_path or beat.audio_path
    ]
    concatenated_audio_path = None
    concatenated_subtitle_path = timeline_subtitle_path
    if len(audio_paths) == 1:
        concatenated_audio_path = audio_paths[0]
    elif audio_paths:
        concatenated_audio_path = await video_builder.concat_audios(
            audio_paths=audio_paths,
            output_path=str(Path(output_dir) / "audio_track.mp3"),
        )

    result = AudioOrchestrationResult(
        beats=timeline.beats,
        timeline=timeline,
        timeline_path=timeline_path,
        concatenated_audio_path=concatenated_audio_path,
        concatenated_subtitle_path=concatenated_subtitle_path,
        bgm_path=bgm_result[0],
        bgm_duration_ms=bgm_result[1],
        bgm_prompt=bgm_result[2],
    )
    return result
