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

vi.mock("gsap", () => ({
  __esModule: true,
  default: {
    to: vi.fn().mockImplementation((_target, config?: { onComplete?: () => void }) => {
      config?.onComplete?.();
    }),
  },
}));

describe("TaskForm", () => {
  beforeEach(() => {
    pushMock.mockReset();
    createTaskMock.mockReset();
    clarifyContentMock.mockReset();
  });

  it("creates the task directly from the generation action", async () => {
    createTaskMock.mockResolvedValue({ id: "task-create" });
    const user = userEvent.setup();

    render(<TaskForm />);

    const prompt = screen.getByRole("textbox", { name: /讲解主题/i });
    await user.type(prompt, "用动画解释勾股定理");
    await user.click(screen.getByRole("button", { name: /生成动画/i }));

    await waitFor(() => expect(createTaskMock).toHaveBeenCalledTimes(1));
    expect(clarifyContentMock).not.toHaveBeenCalled();
    expect(createTaskMock).toHaveBeenCalledWith(
      expect.objectContaining({
        user_text: "用动画解释勾股定理",
      }),
    );
    expect(pushMock).toHaveBeenCalledWith("/tasks/task-create");
  });

  it("clarifies the prompt and keeps generation as the next action", async () => {
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
    const user = userEvent.setup();

    render(<TaskForm />);

    const prompt = screen.getByRole("textbox", { name: /讲解主题/i });
    await user.type(prompt, "高斯定理");
    await user.click(screen.getByRole("button", { name: /理解内容/i }));

    await waitFor(() => expect(clarifyContentMock).toHaveBeenCalledTimes(1));
    expect(createTaskMock).not.toHaveBeenCalled();
    expect(await screen.findByText("已理解内容")).toBeInTheDocument();
    expect(prompt).toHaveValue("请用教学动画讲解散度定理。");
  });
});
