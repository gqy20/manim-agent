"use client";

import type { SSEEvent, StatusPayload, TaskStatus } from "@/types";
import { isStatusPayload } from "@/types";

export type VisualPipelinePhase = "init" | "scene" | "render" | "tts" | "mux";

const VISUAL_PHASE_ORDER: VisualPipelinePhase[] = ["init", "scene", "render", "tts", "mux"];

export function getLatestStructuredStatus(events: SSEEvent[]): StatusPayload | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (isStatusPayload(event)) {
      return event.data;
    }
  }
  return null;
}

export function normalizeVisualPhase(
  phase: StatusPayload["phase"] | null | undefined,
): VisualPipelinePhase | null {
  if (!phase) return null;
  if (phase === "done") return "mux";
  if (VISUAL_PHASE_ORDER.includes(phase as VisualPipelinePhase)) {
    return phase as VisualPipelinePhase;
  }
  return null;
}

export function getLatestVisualPhase(events: SSEEvent[]): VisualPipelinePhase | null {
  return normalizeVisualPhase(getLatestStructuredStatus(events)?.phase);
}

export function getVisualPhaseIndex(
  phase: VisualPipelinePhase | null | undefined,
): number {
  if (!phase) return -1;
  return VISUAL_PHASE_ORDER.indexOf(phase);
}

export function getDisplayPhaseForTask(
  events: SSEEvent[],
  taskStatus: TaskStatus | string,
): VisualPipelinePhase {
  const visualPhase = getLatestVisualPhase(events);
  if (visualPhase) return visualPhase;
  if (taskStatus === "completed") return "mux";
  if (events.length > 0) return "init";
  return "init";
}

