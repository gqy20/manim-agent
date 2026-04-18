import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TaskForm } from "./task-form";

const pushMock = vi.fn();
const createTaskMock = vi.fn();
const clarifyContentMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock("@/lib/api", () => ({
  createTask: (...args: unknown[]) => createTaskMock(...args),
  clarifyContent: (...args: unknown[]) => clarifyContentMock(...args),
}));

vi.mock("@/lib/logger", () => ({
  logger: {
    error: vi.fn(),
  },
}));

vi.mock("@gsap/react", () => ({
  useGSAP: vi.fn(),
}));

vi.mock("gsap", () => {
  const timeline = (config?: { onComplete?: () => void }) => {
    const api = {
      to: vi.fn().mockImplementation(() => {
        config?.onComplete?.();
        return api;
      }),
      play: vi.fn().mockImplementation(() => {
        config?.onComplete?.();
      }),
    };
    return api;
  };
  return {
    default: {
      timeline,
      to: vi.fn(),
      fromTo: vi.fn(),
    },
  };
});

describe("TaskForm", () => {
  beforeEach(() => {
    pushMock.mockReset();
    createTaskMock.mockReset();
    clarifyContentMock.mockReset();
  });

  it("skips clarification and creates the task directly", async () => {
    createTaskMock.mockResolvedValue({ id: "task-skip" });
    const user = userEvent.setup();

    render(<TaskForm />);

    const prompt = screen.getByRole("textbox");
    await user.type(prompt, "用动画解释勾股定理");
    await user.click(screen.getByRole("button", { name: /跳过理解，直接生成/i }));

    await waitFor(() => expect(createTaskMock).toHaveBeenCalledTimes(1));
    expect(clarifyContentMock).not.toHaveBeenCalled();
    expect(createTaskMock).toHaveBeenCalledWith(
      expect.objectContaining({
        user_text: "用动画解释勾股定理",
      }),
    );
    expect(pushMock).toHaveBeenCalledWith("/tasks/task-skip");
  });

  it("clarifies then immediately creates the task with recommended text", async () => {
    clarifyContentMock.mockResolvedValue({
      original_user_text: "高斯定理",
      clarification: {
        topic_interpretation: "默认理解为散度定理。",
        core_question: "为什么体内源汇总量等于边界总通量。",
        prerequisite_concepts: [],
        explanation_path: [],
        scope_boundaries: [],
        optional_branches: [],
        animation_focus: [],
        ambiguity_notes: [],
        clarified_brief_cn: "解释散度定理。",
        recommended_request_cn: "请用教学动画讲解散度定理。",
      },
    });
    createTaskMock.mockResolvedValue({ id: "task-auto-run" });
    const user = userEvent.setup();

    render(<TaskForm />);

    const prompt = screen.getByRole("textbox");
    await user.type(prompt, "高斯定理");
    await user.click(screen.getByRole("button", { name: /理解并直接生成/i }));

    await waitFor(() => expect(clarifyContentMock).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(createTaskMock).toHaveBeenCalledTimes(1));
    expect(createTaskMock).toHaveBeenCalledWith(
      expect.objectContaining({
        user_text: "请用教学动画讲解散度定理。",
      }),
    );
    expect(pushMock).toHaveBeenCalledWith("/tasks/task-auto-run");
  });
});
