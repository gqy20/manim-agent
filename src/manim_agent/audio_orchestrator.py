"""Beat-level narration, TTS, and BGM orchestration helpers."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from . import music_client, tts_client, video_builder
from .beat_schema import AudioOrchestrationResult, BeatSpec
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


def build_beats_from_pipeline_output(
    *,
    implemented_beats: list[str],
    beat_to_narration_map: list[str],
    fallback_narration: str | None = None,
) -> list[BeatSpec]:
    """Construct stable beat records from existing pipeline output fields."""
    beats: list[BeatSpec] = []
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
        return beats

    title = "Main narration"
    return [
        BeatSpec(
            id="beat_001",
            title=title,
            narration_hint=hints[0] if hints else None,
            narration_text=(fallback_narration or "").strip() or None,
        )
    ]


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
    root = Path(output_dir)

    async def _run(beat: BeatSpec) -> BeatSpec:
        async with semaphore:
            beat_dir = root / "audio" / beat.id
            result = await tts_client.synthesize(
                text=beat.narration_text or beat.title,
                voice_id=voice_id,
                model=model,
                output_dir=str(beat_dir),
            )
            beat.audio_path = _optional_str(getattr(result, "audio_path", None))
            beat.subtitle_path = _optional_str(getattr(result, "subtitle_path", None))
            beat.extra_info_path = _optional_str(getattr(result, "extra_info_path", None))
            beat.tts_mode = _optional_str(getattr(result, "mode", None))
            beat.actual_audio_duration_seconds = _coerce_duration_seconds(
                getattr(result, "duration_ms", 0)
            )
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
    )
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

    timeline = finalize_timeline(beats_result)
    timeline_path = write_timeline_file(timeline, str(Path(output_dir) / "timeline.json"))

    audio_paths = [beat.audio_path for beat in beats_result if beat.audio_path]
    subtitle_paths = [beat.subtitle_path for beat in beats_result if beat.subtitle_path]
    concatenated_audio_path = None
    concatenated_subtitle_path = None
    if len(audio_paths) == 1:
        concatenated_audio_path = audio_paths[0]
    elif audio_paths:
        concatenated_audio_path = await video_builder.concat_audios(
            audio_paths=audio_paths,
            output_path=str(Path(output_dir) / "audio_track.mp3"),
        )

    if len(subtitle_paths) == 1:
        concatenated_subtitle_path = subtitle_paths[0]

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
