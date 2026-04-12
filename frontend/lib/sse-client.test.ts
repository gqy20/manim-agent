import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SSEEvent } from "@/types";
import { connectTaskEvents } from "./sse-client";

type ErrorHandler = (error: Event) => void;
type MessageHandler = (event: MessageEvent<string>) => void;

class MockEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;

  static openCount = 0;
  static instances: MockEventSource[] = [];
  static reset(): void {
    MockEventSource.openCount = 0;
    MockEventSource.instances = [];
  }

  url: string;
  readyState = MockEventSource.OPEN;
  onerror: ErrorHandler | null = null;
  onmessage: MessageHandler | null = null;
  private handlers = new Map<string, Set<(event: MessageEvent<string>) => void>>();
  private closed = false;

  constructor(url: string) {
    this.url = url;
    MockEventSource.openCount += 1;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, handler: (event: MessageEvent<string>) => void): void {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set());
    }
    this.handlers.get(type)!.add(handler);
  }

  removeEventListener(type: string, handler: (event: MessageEvent<string>) => void): void {
    this.handlers.get(type)?.delete(handler);
  }

  close(): void {
    this.closed = true;
    this.readyState = MockEventSource.CLOSED;
  }

  isClosed(): boolean {
    return this.closed;
  }

  triggerEvent(type: string, data: string): void {
    const ev = new MessageEvent(type, { data });
    for (const handler of this.handlers.get(type) ?? []) {
      handler(ev);
    }
  }

  triggerError(): void {
    if (!this.onerror) {
      return;
    }
    this.onerror(new Event("error"));
  }

  triggerMessage(data: string): void {
    if (!this.onmessage) {
      return;
    }
    this.onmessage(new MessageEvent("message", { data }));
  }
}

declare global {
  interface Window {
    EventSource: typeof MockEventSource;
  }
}

function lastEventSource(): MockEventSource | undefined {
  return MockEventSource.instances[MockEventSource.instances.length - 1];
}

describe("connectTaskEvents", () => {
  beforeEach(() => {
    MockEventSource.reset();
    globalThis.EventSource = MockEventSource as never;
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("parses SSE events, updates stream, and completes on terminal status", () => {
    const events: SSEEvent[] = [];
    const onComplete = vi.fn();
    const cleanup = connectTaskEvents(
      "task-1",
      (evt) => events.push(evt),
      () => {},
      onComplete,
      { maxAttempts: 1, baseDelayMs: 1 },
    );

    const es = lastEventSource();
    expect(es).toBeDefined();
    expect(MockEventSource.openCount).toBe(1);
    expect(es!.url).toMatch(/\/api\/tasks\/task-1\/events$/);

    es?.triggerEvent(
      "status",
      JSON.stringify({
        type: "status",
        data: {
          task_status: "completed",
          phase: "done",
          message: "done",
        },
        timestamp: "2026-04-12T00:00:00.000Z",
      }),
    );

    expect(events).toHaveLength(1);
    expect(events[0]?.type).toBe("status");
    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(es?.isClosed()).toBe(true);

    cleanup();
  });

  it("retries when SSE connection errors and schedules reconnect", async () => {
    vi.useFakeTimers();
    const onError = vi.fn();
    const cleanup = connectTaskEvents(
      "task-2",
      () => {},
      onError,
      undefined,
      { maxAttempts: 2, baseDelayMs: 10 },
    );

    const first = lastEventSource();
    expect(first).toBeDefined();
    expect(MockEventSource.openCount).toBe(1);

    const rand = vi.spyOn(Math, "random").mockReturnValue(0);
    first!.readyState = MockEventSource.OPEN;
    first!.triggerError();

    expect(onError).toHaveBeenCalledOnce();
    expect(MockEventSource.openCount).toBe(1);

    await vi.advanceTimersByTimeAsync(10);
    expect(MockEventSource.openCount).toBe(2);

    cleanup();
    rand.mockRestore();
  });

  it("unwraps backend-wrapped default message events", () => {
    const events: SSEEvent[] = [];
    const cleanup = connectTaskEvents("task-3", (evt) => events.push(evt));

    const es = lastEventSource();
    expect(es).toBeDefined();

    es?.triggerMessage(
      JSON.stringify({
        event: "thinking",
        data: JSON.stringify({
          type: "thinking",
          data: {
            thinking: "Let me think...",
            preview: "Let me think...",
            signature: "",
          },
          timestamp: "2026-04-12T00:00:00.000Z",
        }),
      }),
    );

    expect(events).toHaveLength(1);
    expect(events[0]?.type).toBe("thinking");

    cleanup();
  });
});
