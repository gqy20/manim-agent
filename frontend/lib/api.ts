import type { Task, TaskCreatePayload } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

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

export async function getTask(id: string): Promise<Task> {
  const res = await fetch(`${API_BASE}/api/tasks/${id}`);
  if (!res.ok) throw new Error("Task not found");
  return res.json();
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
