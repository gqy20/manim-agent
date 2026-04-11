import type { SSEEvent, SSEEventType } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

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

/** Default reconnection config for SSE streams. */
const DEFAULT_RECONNECT = {
  /** Maximum number of reconnection attempts (0 = no reconnect). */
  maxAttempts: 5,
  /** Base delay in ms — actual delay = baseDelay * 2^attempt. */
  baseDelayMs: 1000,
  /** Jitter factor (0–1) to avoid thundering herd. */
  jitterFactor: 0.2,
  /** Cap on the maximum delay between retries. */
  maxDelayMs: 30_000,
} as const;

interface ReconnectState {
  attempt: number;
  timerId: ReturnType<typeof setTimeout> | null;
  aborted: boolean;
}

/**
 * Connect to a task's SSE event stream with automatic reconnection.
 *
 * - Reconnects on unexpected close (non-terminal status) using exponential
 *   backoff with jitter.
 * - Stops reconnecting after `options.maxAttempts` or when the task reaches
 *   a terminal status (completed / failed).
 * - Returns a cleanup function that closes the connection and cancels any
 *   pending reconnection timer.
 */
export function connectTaskEvents(
  taskId: string,
  onEvent: (event: SSEEvent) => void,
  onError?: (error: Event) => void,
  onComplete?: () => void,
  options?: Partial<typeof DEFAULT_RECONNECT>,
): () => void {
  const cfg = { ...DEFAULT_RECONNECT, ...options };
  const state: ReconnectState = { attempt: 0, timerId: null, aborted: false };

  let es: EventSource | null = null;
  let registered = false; // track whether event listeners are attached

  function openConnection() {
    if (state.aborted) return;

    const url = `${API_BASE}/api/tasks/${taskId}/events`;
    es = new EventSource(url);

    registered = false;

    const handleEvent = (e: MessageEvent<string>) => {
      // Reset attempt counter on successful event delivery
      state.attempt = 0;

      // 跳过空数据或非 JSON 数据（旧日志兼容 + 边界容错）
      if (!e.data || e.data === "undefined" || e.data === "null") {
        return;
      }
      try {
        const parsed: SSEEvent = JSON.parse(e.data);
        onEvent(parsed);
        if (parsed.type === "status" && typeof parsed.data === "string") {
          // 仅在终态（completed / failed）时关闭连接
          const terminal = ["completed", "failed"];
          if (terminal.includes(parsed.data as string)) {
            es?.close();
            onComplete?.();
          }
        }
      } catch (err) {
        console.warn("[SSE] failed to parse event:", err, "| raw:", e.data.slice(0, 120));
      }
    };

    // Register listeners on first open
    for (const evtType of ALL_EVENT_TYPES) {
      es!.addEventListener(evtType, handleEvent);
    }
    registered = true;

    es.onerror = (e) => {
      // EventSource sets readyState to CLOSED on error.
      // If the task is terminal, the server already sent the status event
      // and we closed above — don't reconnect.
      if (!es || es.readyState === EventSource.CLOSED && state.attempt === 0) {
        // Clean close (likely terminal)
        return;
      }

      onError?.(e);

      // Attempt reconnection
      if (state.attempt < cfg.maxAttempts && !state.aborted) {
        state.attempt++;
        const delay = Math.min(
          cfg.baseDelayMs * Math.pow(2, state.attempt - 1),
          cfg.maxDelayMs,
        );
        // Add jitter ±jitterFactor
        const jitter = delay * cfg.jitterFactor * (Math.random() * 2 - 1);
        const finalDelay = Math.round(delay + jitter);

        console.warn(
          `[SSE] Connection lost (attempt ${state.attempt}/${cfg.maxAttempts}), reconnecting in ${finalDelay}ms...`,
        );

        state.timerId = setTimeout(() => {
          state.timerId = null;
          // Clean up old ES before reopening
          if (es) {
            es.close();
            es = null;
          }
          openConnection();
        }, finalDelay);
      } else if (state.attempt >= cfg.maxAttempts) {
        console.error(`[SSE] Max reconnection attempts (${cfg.maxAttempts}) reached.`);
        // Push a synthetic error event so UI can show disconnected state
        onEvent({
          type: "error",
          data: `SSE 连接断开，已重试 ${cfg.maxAttempts} 次`,
          timestamp: new Date().toISOString(),
        });
      }
    };
  }

  // Start the first connection
  openConnection();

  // Return cleanup function
  return () => {
    state.aborted = true;
    if (state.timerId !== null) {
      clearTimeout(state.timerId);
      state.timerId = null;
    }
    if (es) {
      if (registered) {
        es.close();
      }
      es = null;
    }
  };
}
