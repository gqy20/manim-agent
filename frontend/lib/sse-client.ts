import type { SSEEvent } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8471";

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

  es.onmessage = (e) => {
    try {
      const parsed: SSEEvent = JSON.parse(e.data);
      onEvent(parsed);
      if (parsed.type === "status") {
        es.close();
        onComplete?.();
      }
    } catch {
      // ignore parse errors
    }
  };

  es.onerror = (e) => {
    onError?.(e);
  };

  // Return cleanup function
  return () => es.close();
}
