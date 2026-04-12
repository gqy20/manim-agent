"use client";

import type { PipelineOutputData, Task, TaskStatus } from "@/types";

const TERMINAL_STATUSES: ReadonlySet<TaskStatus> = new Set(["completed", "failed"]);

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
    video_output: next.video_output ?? prev.video_output,
    scene_file: next.scene_file ?? prev.scene_file,
    scene_class: next.scene_class ?? prev.scene_class,
    duration_seconds: next.duration_seconds ?? prev.duration_seconds,
    narration: next.narration ?? prev.narration,
    source_code: next.source_code ?? prev.source_code,
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
