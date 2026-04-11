import type { SSEEvent, SSEEventType } from "@/types";
import { isStatusPayload } from "@/types";
import { logger } from "@/lib/logger";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

const ALL_EVENT_TYPES: SSEEventType[] = [
  "log",
  "status",
  "error",
  "tool_start",
  "tool_result",
  "thinking",
  "progress",
];

const DEFAULT_RECONNECT = {
  maxAttempts: 5,
  baseDelayMs: 1000,
  jitterFactor: 0.2,
  maxDelayMs: 30_000,
} as const;

interface ReconnectState {
  attempt: number;
  timerId: ReturnType<typeof setTimeout> | null;
  aborted: boolean;
}

export function connectTaskEvents(
  taskId: string,
  onEvent: (event: SSEEvent) => void,
  onError?: (error: Event) => void,
  onComplete?: () => void,
  options?: Partial<typeof DEFAULT_RECONNECT>,
): () => void {
  const cfg = { ...DEFAULT_RECONNECT, ...options };
  const state: ReconnectState = { attempt: 0, timerId: null, aborted: false };
  const eventsUrl = `${API_BASE}/api/tasks/${taskId}/events`;
  console.debug(`[SSE] connectTaskEvents called taskId=${taskId} url=${eventsUrl}`);

  let es: EventSource | null = null;
  let registered = false;

  function isTerminalStatus(event: SSEEvent): boolean {
    if (event.type !== "status") return false;
    if (typeof event.data === "string") {
      return ["completed", "failed"].includes(event.data);
    }
    if (isStatusPayload(event)) {
      return ["completed", "failed"].includes(event.data.task_status);
    }
    return false;
  }

  function openConnection() {
    if (state.aborted) return;

    es = new EventSource(eventsUrl);
    console.debug(`[SSE] opening ${eventsUrl} attempt=${state.attempt}`);
    registered = false;
    let eventCount = 0;

    const handleEvent = (e: MessageEvent<string>) => {
      state.attempt = 0;
      if (!e.data || e.data === "undefined" || e.data === "null") {
        return;
      }

      try {
        const parsed: SSEEvent = JSON.parse(e.data);
        eventCount += 1;
        console.debug(`[SSE] received #${eventCount} task=${taskId} type=${parsed.type}`);
        onEvent(parsed);

        if (isTerminalStatus(parsed)) {
          es?.close();
          onComplete?.();
        }
      } catch (err) {
        logger.warn("sse-client", "Failed to parse SSE event", { raw: e.data.slice(0, 120) });
      }
    };

    for (const evtType of ALL_EVENT_TYPES) {
      es.addEventListener(evtType, handleEvent);
    }
    registered = true;

    es.onerror = (e) => {
      logger.warn("sse-client", "SSE onerror event", { taskId, readyState: es?.readyState });
      if ((!es || es.readyState === EventSource.CLOSED) && state.attempt === 0) {
        return;
      }

      onError?.(e);

      if (state.attempt < cfg.maxAttempts && !state.aborted) {
        state.attempt++;
        const delay = Math.min(
          cfg.baseDelayMs * Math.pow(2, state.attempt - 1),
          cfg.maxDelayMs,
        );
        const jitter = delay * cfg.jitterFactor * (Math.random() * 2 - 1);
        const finalDelay = Math.round(delay + jitter);

        logger.warn(
          "sse-client",
          `Connection lost (attempt ${state.attempt}/${cfg.maxAttempts}), reconnecting in ${finalDelay}ms`,
          { taskId },
        );

        state.timerId = setTimeout(() => {
          state.timerId = null;
          es?.close();
          es = null;
          openConnection();
        }, finalDelay);
      } else if (state.attempt >= cfg.maxAttempts) {
        logger.error("sse-client", `Max reconnection attempts (${cfg.maxAttempts}) reached`, { taskId });
        onEvent({
          type: "error",
          data: `SSE disconnected after ${cfg.maxAttempts} retries`,
          timestamp: new Date().toISOString(),
        });
      }
    };
  }

  openConnection();

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
