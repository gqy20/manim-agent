import type {
  ClarifyContentPayload,
  ClarifyContentResponse,
  DebugIssue,
  DebugIssueCreatePayload,
  DebugPromptArtifact,
  DebugPromptIndexResponse,
  Task,
  TaskCreatePayload,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function readApiError(res: Response, fallback: string): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: unknown };
    if (typeof data.detail === "string" && data.detail.trim()) {
      return data.detail.trim();
    }
  } catch {
    // Fall back to the supplied message when the body is not JSON.
  }
  return fallback;
}

export async function createTask(payload: TaskCreatePayload): Promise<Task> {
  const res = await fetch(`${API_BASE}/api/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`Failed to create task: ${res.statusText}`);
  }
  return res.json();
}

export async function clarifyContent(
  payload: ClarifyContentPayload,
): Promise<ClarifyContentResponse> {
  const res = await fetch(`${API_BASE}/api/clarify-content`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const detail = await readApiError(res, res.statusText);
    throw new Error(detail || "Failed to clarify content");
  }
  return res.json();
}

export async function getTask(id: string): Promise<Task> {
  const res = await fetch(`${API_BASE}/api/tasks/${id}`);
  if (!res.ok) throw new Error("Task not found");
  return res.json();
}

export async function terminateTask(id: string): Promise<Task> {
  const res = await fetch(`${API_BASE}/api/tasks/${id}/terminate`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(`Failed to terminate task: ${res.statusText}`);
  }
  return res.json();
}

export async function deleteTask(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/tasks/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error(`Failed to delete task: ${res.statusText}`);
  }
}

export async function listTasks(limit = 50): Promise<{ tasks: Task[]; total: number }> {
  const res = await fetch(`${API_BASE}/api/tasks?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch tasks");
  return res.json();
}

export function getVideoUrl(
  taskId: string,
  videoPath?: string | null,
): string {
  // If task already has a public R2 URL, use it directly (skip 302 redirect)
  if (videoPath && /^https?:\/\//.test(videoPath)) {
    return videoPath;
  }
  return `${API_BASE}/api/tasks/${taskId}/video`;
}

export async function getDebugPromptIndex(taskId: string): Promise<DebugPromptIndexResponse> {
  const res = await fetch(`${API_BASE}/api/tasks/${taskId}/debug/prompts`);
  if (!res.ok) {
    throw new Error(await readApiError(res, "Failed to fetch debug prompt index"));
  }
  return res.json();
}

export async function getDebugPromptArtifact(
  taskId: string,
  phaseId: string,
): Promise<DebugPromptArtifact> {
  const res = await fetch(`${API_BASE}/api/tasks/${taskId}/debug/prompts/${phaseId}`);
  if (!res.ok) {
    throw new Error(await readApiError(res, "Failed to fetch debug prompt artifact"));
  }
  return res.json();
}

export async function listDebugIssues(taskId: string): Promise<DebugIssue[]> {
  const res = await fetch(`${API_BASE}/api/tasks/${taskId}/debug/issues`);
  if (!res.ok) {
    throw new Error(await readApiError(res, "Failed to fetch debug issues"));
  }
  const data = (await res.json()) as { issues: DebugIssue[] };
  return data.issues;
}

export async function createDebugIssue(
  taskId: string,
  payload: DebugIssueCreatePayload,
): Promise<DebugIssue> {
  const res = await fetch(`${API_BASE}/api/tasks/${taskId}/debug/issues`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(await readApiError(res, "Failed to create debug issue"));
  }
  return res.json();
}
