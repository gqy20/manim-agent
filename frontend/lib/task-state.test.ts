import { describe, expect, it } from "vitest";

import type { PipelineOutputData, Task } from "@/types";

import { mergeTaskState } from "./task-state";

function buildPipelineOutput(
  overrides: Partial<PipelineOutputData> = {},
): PipelineOutputData {
  return {
    video_output: null,
    final_video_output: null,
    scene_file: null,
    scene_class: null,
    duration_seconds: null,
    narration: null,
    implemented_beats: [],
    build_summary: null,
    deviations_from_plan: [],
    beat_to_narration_map: [],
    narration_coverage_complete: null,
    estimated_narration_duration_seconds: null,
    source_code: null,
    audio_path: null,
    bgm_path: null,
    bgm_prompt: null,
    bgm_duration_ms: null,
    bgm_volume: null,
    audio_mix_mode: null,
    subtitle_path: null,
    extra_info_path: null,
    tts_mode: null,
    tts_duration_ms: null,
    tts_word_count: null,
    tts_usage_characters: null,
    run_turns: null,
    run_tool_use_count: null,
    run_tool_stats: {},
    run_duration_ms: null,
    run_cost_usd: null,
    target_duration_seconds: null,
    plan_text: null,
    review_summary: null,
    review_approved: null,
    review_blocking_issues: [],
    review_suggested_edits: [],
    review_frame_paths: [],
    ...overrides,
  };
}

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
      bgm_enabled: false,
      bgm_prompt: null,
      bgm_volume: 0.12,
      target_duration_seconds: 60,
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
      pipeline_output: buildPipelineOutput({
        video_output: "/tmp/out.mp4",
        final_video_output: "/tmp/final.mp4",
        scene_file: "scene.py",
        scene_class: "GeneratedScene",
        duration_seconds: 8,
        narration: "旧旁白",
        implemented_beats: ["Intro", "Proof"],
        build_summary: "Built the proof walkthrough",
        deviations_from_plan: ["Shortened ending"],
        beat_to_narration_map: ["Intro -> 介绍直角三角形"],
        narration_coverage_complete: true,
        estimated_narration_duration_seconds: 7.5,
        source_code: "print('hi')",
        audio_path: "/tmp/audio.mp3",
        bgm_path: "/tmp/bgm.mp3",
        bgm_prompt: "calm instrumental",
        bgm_duration_ms: 8100,
        bgm_volume: 0.12,
        audio_mix_mode: "voice_with_bgm",
        subtitle_path: "/tmp/subtitle.srt",
        extra_info_path: "/tmp/extra.json",
        tts_mode: "sync",
        tts_duration_ms: 7500,
        tts_word_count: 20,
        tts_usage_characters: 40,
        run_turns: 12,
        run_tool_use_count: 9,
        run_tool_stats: { Bash: 3, Edit: 6 },
        run_duration_ms: 123000,
        run_cost_usd: 0.42,
        target_duration_seconds: 60,
        plan_text: "Mode\nLearning Goal",
        review_summary: "Looks good",
        review_approved: true,
        review_blocking_issues: [],
        review_suggested_edits: ["Tighten ending"],
        review_frame_paths: ["/tmp/frame-1.png"],
      }),
    });

    const merged = mergeTaskState(prev, {
      pipeline_output: buildPipelineOutput({
        narration: "新旁白",
        build_summary: "Updated build summary",
        run_turns: 14,
        run_tool_stats: { Bash: 4, Edit: 7, Read: 3 },
        review_summary: "Updated review",
      }),
    });

    expect(merged.pipeline_output).toEqual(
      buildPipelineOutput({
        video_output: "/tmp/out.mp4",
        final_video_output: "/tmp/final.mp4",
        scene_file: "scene.py",
        scene_class: "GeneratedScene",
        duration_seconds: 8,
        narration: "新旁白",
        implemented_beats: ["Intro", "Proof"],
        build_summary: "Updated build summary",
        deviations_from_plan: ["Shortened ending"],
        beat_to_narration_map: ["Intro -> 介绍直角三角形"],
        narration_coverage_complete: true,
        estimated_narration_duration_seconds: 7.5,
        source_code: "print('hi')",
        audio_path: "/tmp/audio.mp3",
        bgm_path: "/tmp/bgm.mp3",
        bgm_prompt: "calm instrumental",
        bgm_duration_ms: 8100,
        bgm_volume: 0.12,
        audio_mix_mode: "voice_with_bgm",
        subtitle_path: "/tmp/subtitle.srt",
        extra_info_path: "/tmp/extra.json",
        tts_mode: "sync",
        tts_duration_ms: 7500,
        tts_word_count: 20,
        tts_usage_characters: 40,
        run_turns: 14,
        run_tool_use_count: 9,
        run_tool_stats: { Bash: 4, Edit: 7, Read: 3 },
        run_duration_ms: 123000,
        run_cost_usd: 0.42,
        target_duration_seconds: 60,
        plan_text: "Mode\nLearning Goal",
        review_summary: "Updated review",
        review_approved: true,
        review_blocking_issues: [],
        review_suggested_edits: ["Tighten ending"],
        review_frame_paths: ["/tmp/frame-1.png"],
      }),
    );
  });
});
