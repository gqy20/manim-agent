"use client";

import type { PipelineOutputData, Task, TaskStatus } from "@/types";

const TERMINAL_STATUSES: ReadonlySet<TaskStatus> = new Set(["completed", "failed"]);

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
    source_code: mergeNullableValue(prev.source_code, next.source_code),
    audio_path: mergeNullableValue(prev.audio_path, next.audio_path),
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
    target_duration_seconds: mergeNullableValue(
      prev.target_duration_seconds,
      next.target_duration_seconds,
    ),
    plan_text: mergeNullableValue(prev.plan_text, next.plan_text),
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
