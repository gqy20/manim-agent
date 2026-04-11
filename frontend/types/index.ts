export type TaskStatus = "pending" | "running" | "completed" | "failed";

export interface TaskCreatePayload {
  user_text: string;
  voice_id: string;
  model: string;
  quality: "high" | "medium" | "low";
  preset: "default" | "educational" | "presentation" | "proof" | "concept";
  no_tts: boolean;
}

/** Pipeline 结构化输出数据（完成任务时可用）。 */
export interface PipelineOutputData {
  video_output: string | null;
  scene_file: string | null;
  scene_class: string | null;
  duration_seconds: number | null;
  narration: string | null;
  source_code: string | null;
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
  pipeline_output: PipelineOutputData | null;
}

// ── 结构化事件载荷 ────────────────────────────────────────

/** 工具调用开始时的上下文。 */
export interface ToolStartPayload {
  tool_use_id: string;
  name: string;
  input_summary: Record<string, unknown>;
}

/** 工具调用结果。 */
export interface ToolResultPayload {
  tool_use_id: string;
  name: string;
  is_error: boolean;
  content: string | null;
  duration_ms: number | null;
}

/** Claude 思考/推理块。 */
export interface ThinkingPayload {
  thinking: string;
  preview: string | null;
  signature: string;
}

/** 执行进度快照。 */
export interface ProgressPayload {
  turn: number;
  total_tokens: number;
  tool_uses: number;
  elapsed_ms: number;
  last_tool_name: string | null;
}

export interface StatusPayload {
  task_status: TaskStatus;
  phase: "init" | "scene" | "render" | "tts" | "mux" | "done" | null;
  message: string | null;
}

// ── SSE 事件类型 ──────────────────────────────────────────

/** 所有可能的 SSE 事件类型名称。 */
export type SSEEventType =
  | "log"
  | "status"
  | "error"
  | "tool_start"
  | "tool_result"
  | "thinking"
  | "progress";

/** 所有结构化载荷类型的联合。 */
export type StructuredPayload =
  | ToolStartPayload
  | ToolResultPayload
  | ThinkingPayload
  | ProgressPayload
  | StatusPayload;

/**
 * SSE 事件（向后兼容 + 结构化扩展）。
 *
 * - log/status/error 事件：data 为纯文本字符串
 * - tool_start/tool_result/thinking/progress：data 为对应载荷对象
 */
export interface SSEEvent {
  type: SSEEventType;
  data: string | StructuredPayload;
  timestamp: string;
}

// ── 类型守卫 ──────────────────────────────────────────────

/** 判断事件是否为工具调用开始。 */
export function isToolStart(
  evt: SSEEvent,
): evt is SSEEvent & { data: ToolStartPayload } {
  return evt.type === "tool_start" && typeof evt.data === "object";
}

/** 判断事件是否为工具调用结果。 */
export function isToolResult(
  evt: SSEEvent,
): evt is SSEEvent & { data: ToolResultPayload } {
  return evt.type === "tool_result" && typeof evt.data === "object";
}

/** 判断事件是否为思考块。 */
export function isThinking(
  evt: SSEEvent,
): evt is SSEEvent & { data: ThinkingPayload } {
  return evt.type === "thinking" && typeof evt.data === "object";
}

/** 判断事件是否为进度事件。 */
export function isProgress(
  evt: SSEEvent,
): evt is SSEEvent & { data: ProgressPayload } {
  return evt.type === "progress" && typeof evt.data === "object";
}

export function isStatusPayload(
  evt: SSEEvent,
): evt is SSEEvent & { data: StatusPayload } {
  return (
    evt.type === "status" &&
    typeof evt.data === "object" &&
    evt.data !== null &&
    "task_status" in evt.data
  );
}
