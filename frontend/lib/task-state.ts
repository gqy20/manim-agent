"use client";

import type { PipelineOutputData, Task, TaskStatus } from "@/types";

const TERMINAL_STATUSES: ReadonlySet<TaskStatus> = new Set(["completed", "failed", "stopped"]);

function mergeNullableValue<T>(prev: T | null, next: T | null | undefined): T | null {
  if (next === undefined || next === null) {
    return prev;
  }
  return next;
}

function mergeList(prev: string[], next: string[] | undefined): string[] {
  if (!next || next.length === 0) {
    return prev;
  }
  return next;
}

function mergeArray<T>(prev: T[] | undefined, next: T[] | undefined): T[] | undefined {
  if (!next || next.length === 0) {
    return prev;
  }
  return next;
}

function mergeNumberMap(
  prev: Record<string, number>,
  next: Record<string, number> | undefined,
): Record<string, number> {
  if (!next || Object.keys(next).length === 0) {
    return prev;
  }
  return next;
}

function mergePipelineOutput(
  prev: PipelineOutputData | null,
  next: PipelineOutputData | null | undefined,
): PipelineOutputData | null {
  if (next === undefined) {
    return prev;
  }

  if (!prev) {
    return next ?? null;
  }

  if (!next) {
    return prev;
  }

  return {
    video_output: mergeNullableValue(prev.video_output, next.video_output),
    final_video_output: mergeNullableValue(prev.final_video_output, next.final_video_output),
    scene_file: mergeNullableValue(prev.scene_file, next.scene_file),
    scene_class: mergeNullableValue(prev.scene_class, next.scene_class),
    duration_seconds: mergeNullableValue(prev.duration_seconds, next.duration_seconds),
    narration: mergeNullableValue(prev.narration, next.narration),
    implemented_beats: mergeList(prev.implemented_beats, next.implemented_beats),
    build_summary: mergeNullableValue(prev.build_summary, next.build_summary),
    deviations_from_plan: mergeList(prev.deviations_from_plan, next.deviations_from_plan),
    beat_to_narration_map: mergeList(prev.beat_to_narration_map, next.beat_to_narration_map),
    narration_coverage_complete: mergeNullableValue(
      prev.narration_coverage_complete,
      next.narration_coverage_complete,
    ),
    estimated_narration_duration_seconds: mergeNullableValue(
      prev.estimated_narration_duration_seconds,
      next.estimated_narration_duration_seconds,
    ),
    render_mode: mergeNullableValue(prev.render_mode ?? null, next.render_mode),
    segment_render_complete: mergeNullableValue(
      prev.segment_render_complete ?? null,
      next.segment_render_complete,
    ),
    timeline_path: mergeNullableValue(prev.timeline_path ?? null, next.timeline_path),
    timeline_total_duration_seconds: mergeNullableValue(
      prev.timeline_total_duration_seconds ?? null,
      next.timeline_total_duration_seconds,
    ),
    segment_render_plan_path: mergeNullableValue(
      prev.segment_render_plan_path ?? null,
      next.segment_render_plan_path,
    ),
    segment_video_paths: mergeArray(prev.segment_video_paths, next.segment_video_paths),
    rendered_segments: mergeArray(prev.rendered_segments, next.rendered_segments),
    audio_concat_path: mergeNullableValue(prev.audio_concat_path ?? null, next.audio_concat_path),
    source_code: mergeNullableValue(prev.source_code, next.source_code),
    audio_path: mergeNullableValue(prev.audio_path, next.audio_path),
    bgm_path: mergeNullableValue(prev.bgm_path, next.bgm_path),
    bgm_prompt: mergeNullableValue(prev.bgm_prompt, next.bgm_prompt),
    bgm_duration_ms: mergeNullableValue(prev.bgm_duration_ms, next.bgm_duration_ms),
    bgm_volume: mergeNullableValue(prev.bgm_volume, next.bgm_volume),
    audio_mix_mode: mergeNullableValue(prev.audio_mix_mode, next.audio_mix_mode),
    subtitle_path: mergeNullableValue(prev.subtitle_path, next.subtitle_path),
    extra_info_path: mergeNullableValue(prev.extra_info_path, next.extra_info_path),
    tts_mode: mergeNullableValue(prev.tts_mode, next.tts_mode),
    tts_duration_ms: mergeNullableValue(prev.tts_duration_ms, next.tts_duration_ms),
    tts_word_count: mergeNullableValue(prev.tts_word_count, next.tts_word_count),
    tts_usage_characters: mergeNullableValue(
      prev.tts_usage_characters,
      next.tts_usage_characters,
    ),
    run_turns: mergeNullableValue(prev.run_turns, next.run_turns),
    run_tool_use_count: mergeNullableValue(prev.run_tool_use_count, next.run_tool_use_count),
    run_tool_stats: mergeNumberMap(prev.run_tool_stats, next.run_tool_stats),
    run_duration_ms: mergeNullableValue(prev.run_duration_ms, next.run_duration_ms),
    run_cost_usd: mergeNullableValue(prev.run_cost_usd, next.run_cost_usd),
    run_cost_cny: mergeNullableValue(prev.run_cost_cny, next.run_cost_cny),
    run_model_name: mergeNullableValue(prev.run_model_name, next.run_model_name),
    run_pricing_model: mergeNullableValue(prev.run_pricing_model, next.run_pricing_model),
    target_duration_seconds: mergeNullableValue(
      prev.target_duration_seconds,
      next.target_duration_seconds,
    ),
    plan_text: mergeNullableValue(prev.plan_text, next.plan_text),
    mode: mergeNullableValue(prev.mode, next.mode),
    learning_goal: mergeNullableValue(prev.learning_goal, next.learning_goal),
    audience: mergeNullableValue(prev.audience, next.audience),
    phase1_planning: mergeNullableValue(prev.phase1_planning ?? null, next.phase1_planning),
    phase2_implementation: mergeNullableValue(
      prev.phase2_implementation ?? null,
      next.phase2_implementation,
    ),
    phase3_render_review: mergeNullableValue(
      prev.phase3_render_review ?? null,
      next.phase3_render_review,
    ),
    phase3_5_narration: mergeNullableValue(
      prev.phase3_5_narration ?? null,
      next.phase3_5_narration,
    ),
    phase4_tts: mergeNullableValue(prev.phase4_tts ?? null, next.phase4_tts),
    phase5_mux: mergeNullableValue(prev.phase5_mux ?? null, next.phase5_mux),
    beats: next.beats ?? prev.beats,
    audio_segments: mergeArray(prev.audio_segments, next.audio_segments),
    review_summary: mergeNullableValue(prev.review_summary, next.review_summary),
    review_approved: mergeNullableValue(prev.review_approved, next.review_approved),
    review_blocking_issues: mergeList(
      prev.review_blocking_issues,
      next.review_blocking_issues,
    ),
    review_suggested_edits: mergeList(
      prev.review_suggested_edits,
      next.review_suggested_edits,
    ),
    review_frame_paths: mergeList(prev.review_frame_paths, next.review_frame_paths),
    review_frame_analyses: mergeArray(prev.review_frame_analyses, next.review_frame_analyses),
    review_vision_analysis_used: mergeNullableValue(
      prev.review_vision_analysis_used ?? null,
      next.review_vision_analysis_used,
    ),
    intro_requested: mergeNullableValue(prev.intro_requested ?? null, next.intro_requested),
    outro_requested: mergeNullableValue(prev.outro_requested ?? null, next.outro_requested),
    intro_spec: mergeNullableValue(prev.intro_spec ?? null, next.intro_spec),
    outro_spec: mergeNullableValue(prev.outro_spec ?? null, next.outro_spec),
    intro_video_path: mergeNullableValue(prev.intro_video_path ?? null, next.intro_video_path),
    outro_video_path: mergeNullableValue(prev.outro_video_path ?? null, next.outro_video_path),
    intro_outro_backend: mergeNullableValue(
      prev.intro_outro_backend ?? null,
      next.intro_outro_backend,
    ),
  };
}

function mergeStatus(prev: TaskStatus, next: TaskStatus): TaskStatus {
  if (TERMINAL_STATUSES.has(prev) && !TERMINAL_STATUSES.has(next)) {
    return prev;
  }

  return next;
}

export function mergeTaskState(prev: Task, next: Partial<Task>): Task {
  const mergedStatus = next.status ? mergeStatus(prev.status, next.status) : prev.status;
  const mergedVideoPath =
    next.video_path !== undefined ? next.video_path ?? prev.video_path : prev.video_path;

  return {
    ...prev,
    ...next,
    status: mergedStatus,
    video_path: mergedVideoPath,
    error: next.error !== undefined ? next.error ?? prev.error : prev.error,
    pipeline_output: mergePipelineOutput(prev.pipeline_output, next.pipeline_output),
  };
}
