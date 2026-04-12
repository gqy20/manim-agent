import { afterEach, describe, expect, it, vi } from "vitest";
import {
  clarifyContent,
  createTask,
  getTask,
  getVideoUrl,
  listTasks,
} from "./api";
import type {
  ClarifyContentResponse,
  Task,
  TaskCreatePayload,
} from "@/types";

describe("api client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("posts createTask payload and returns created task", async () => {
    const task: Task = {
      id: "task-1",
      user_text: "hello",
      status: "pending",
      created_at: "2026-04-12T00:00:00.000Z",
      completed_at: null,
      video_path: null,
      error: null,
      options: {
        user_text: "hello",
        voice_id: "v",
        model: "m",
        quality: "high",
        preset: "default",
        no_tts: false,
        bgm_enabled: false,
        bgm_prompt: null,
        bgm_volume: 0.12,
        target_duration_seconds: 60,
      },
      pipeline_output: null,
    };
    const payload: TaskCreatePayload = {
      user_text: "hello",
      voice_id: "v",
      model: "m",
      quality: "high",
      preset: "default",
      no_tts: false,
      bgm_enabled: false,
      bgm_prompt: null,
      bgm_volume: 0.12,
      target_duration_seconds: 60,
    };

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(task),
      }),
    );

    const result = await createTask(payload);
    expect(result).toEqual(task);
    expect(fetch).toHaveBeenCalledWith("/api/tasks", expect.objectContaining({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }));
  });

  it("reads task details", async () => {
    const task = {
      id: "task-2",
      user_text: "abc",
      status: "running",
      created_at: "2026-04-12T00:00:00.000Z",
      completed_at: null,
      video_path: null,
      error: null,
      options: {
        user_text: "abc",
        voice_id: "v",
        model: "m",
        quality: "medium",
        preset: "proof",
        no_tts: false,
        bgm_enabled: false,
        bgm_prompt: null,
        bgm_volume: 0.12,
        target_duration_seconds: 180,
      },
      pipeline_output: null,
    };

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(task),
      }),
    );

    const result = await getTask("task-2");
    expect(result.id).toBe("task-2");
    expect(fetch).toHaveBeenCalledWith("/api/tasks/task-2");
  });

  it("returns all task list", async () => {
    const response = {
      tasks: [],
      total: 0,
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(response),
      }),
    );

    const result = await listTasks(10);
    expect(result).toEqual(response);
    expect(fetch).toHaveBeenCalledWith("/api/tasks?limit=10");
  });

  it("builds video URL from path type", () => {
    expect(getVideoUrl("task-1", "http://cdn.example/video.mp4")).toBe(
      "http://cdn.example/video.mp4",
    );
    expect(getVideoUrl("task-1", "/tmp/final.mp4")).toBe("/api/tasks/task-1/video");
    expect(getVideoUrl("task-1")).toBe("/api/tasks/task-1/video");
  });

  it("posts clarifyContent payload and returns clarification", async () => {
    const response: ClarifyContentResponse = {
      original_user_text: "高斯定理",
      clarification: {
        topic_interpretation: "默认理解为向量分析中的高斯散度定理。",
        core_question: "为什么体内源汇总量可以等价地转成边界总通量。",
        prerequisite_concepts: ["向量场", "通量"],
        explanation_path: ["直觉现象", "公式表达", "简单例子"],
        scope_boundaries: ["默认不展开严格证明"],
        optional_branches: ["物理中的高斯定律"],
        animation_focus: ["箭头流场", "封闭曲面"],
        ambiguity_notes: ["可能与其他高斯相关结论混用"],
        clarified_brief_cn: "默认按散度定理来理解，重点讲通量与散度的对应关系。",
        recommended_request_cn:
          "请用教学动画讲解向量分析中的高斯散度定理，重点说明体内散度总量与边界曲面总通量之间的对应关系，先讲直观含义，再给公式和一个简单例子。",
      },
    };

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(response),
      }),
    );

    const result = await clarifyContent({ user_text: "高斯定理" });
    expect(result).toEqual(response);
    expect(fetch).toHaveBeenCalledWith(
      "/api/clarify-content",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_text: "高斯定理" }),
      }),
    );
  });
});
