import { describe, expect, it } from "vitest";

import type { Task } from "@/types";

import { mergeTaskState } from "./task-state";

function buildTask(overrides: Partial<Task> = {}): Task {
  return {
    id: "task-1",
    user_text: "demo",
    status: "running",
    created_at: "2026-04-12T00:00:00.000Z",
    completed_at: null,
    video_path: null,
    error: null,
    options: {
      user_text: "demo",
      voice_id: "female-tianmei",
      model: "speech-2.8-hd",
      quality: "high",
      preset: "default",
      no_tts: false,
    },
    pipeline_output: null,
    ...overrides,
  };
}

describe("mergeTaskState", () => {
  it("preserves terminal status when a stale running snapshot arrives", () => {
    const prev = buildTask({
      status: "completed",
      video_path: "https://example.com/final.mp4",
    });

    const merged = mergeTaskState(prev, {
      status: "running",
      video_path: null,
    });

    expect(merged.status).toBe("completed");
    expect(merged.video_path).toBe("https://example.com/final.mp4");
  });

  it("merges pipeline output without dropping known fields", () => {
    const prev = buildTask({
      pipeline_output: {
        video_output: "/tmp/out.mp4",
        scene_file: "scene.py",
        scene_class: "GeneratedScene",
        duration_seconds: 8,
        narration: "旧旁白",
        source_code: "print('hi')",
      },
    });

    const merged = mergeTaskState(prev, {
      pipeline_output: {
        video_output: null,
        scene_file: null,
        scene_class: null,
        duration_seconds: null,
        narration: "新旁白",
        source_code: null,
      },
    });

    expect(merged.pipeline_output).toEqual({
      video_output: "/tmp/out.mp4",
      scene_file: "scene.py",
      scene_class: "GeneratedScene",
      duration_seconds: 8,
      narration: "新旁白",
      source_code: "print('hi')",
    });
  });
});
