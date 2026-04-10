export type TaskStatus = "pending" | "running" | "completed" | "failed";

export interface TaskCreatePayload {
  user_text: string;
  voice_id: string;
  model: string;
  quality: "high" | "medium" | "low";
  preset: "default" | "educational" | "presentation" | "proof" | "concept";
  no_tts: boolean;
}

export interface Task {
  id: string;
  user_text: string;
  status: TaskStatus;
  created_at: string;
  completed_at: string | null;
  video_path: string | null;
  error: string | null;
  options: TaskCreatePayload;
}

export interface SSEEvent {
  type: "log" | "status" | "error";
  data: string;
  timestamp: string;
}
