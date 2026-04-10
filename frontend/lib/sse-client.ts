import type { SSEEvent, SSEEventType } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8471";

/** 所有需要注册的 SSE 事件名称。 */
const ALL_EVENT_TYPES: SSEEventType[] = [
  "log",
  "status",
  "error",
  "tool_start",
  "tool_result",
  "thinking",
  "progress",
];

/**
 * Connect to a task's SSE event stream.
 * Returns a cleanup function that closes the connection.
 */
export function connectTaskEvents(
  taskId: string,
  onEvent: (event: SSEEvent) => void,
  onError?: (error: Event) => void,
  onComplete?: () => void,
): () => void {
  const url = `${API_BASE}/api/tasks/${taskId}/events`;
  const es = new EventSource(url);

  const handleEvent = (e: MessageEvent<string>) => {
    try {
      const parsed: SSEEvent = JSON.parse(e.data);
      onEvent(parsed);
      if (parsed.type === "status") {
        es.close();
        onComplete?.();
      }
    } catch (err) {
      console.warn("[SSE] failed to parse event:", err);
    }
  };

  // 注册所有事件类型的监听器
  for (const evtType of ALL_EVENT_TYPES) {
    es.addEventListener(evtType, handleEvent);
  }

  es.onerror = (e) => {
    onError?.(e);
  };

  // Return cleanup function
  return () => {
    for (const evtType of ALL_EVENT_TYPES) {
      es.removeEventListener(evtType, handleEvent);
    }
    es.close();
  };
}
