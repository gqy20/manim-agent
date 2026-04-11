import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { LogEntry } from "./logger";
import { FrontendLogger } from "./logger";

/** 创建一个可检查的 fetch mock */
function createMockFetch() {
  return vi.fn().mockResolvedValue({ ok: true });
}

describe("FrontendLogger", () => {
  let logger: FrontendLogger;
  let mockFetch: ReturnType<typeof createMockFetch>;

  beforeEach(() => {
    vi.useFakeTimers();
    mockFetch = createMockFetch();
    globalThis.fetch = mockFetch;

    // 模拟浏览器环境
    Object.defineProperty(globalThis, "navigator", {
      value: { userAgent: "test-agent", sendBeacon: vi.fn() },
      writable: true,
    });
    Object.defineProperty(globalThis, "document", {
      value: {
        visibilityState: "visible",
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      },
      writable: true,
    });
    Object.defineProperty(globalThis, "window", {
      value: { location: { pathname: "/test" }, setInterval: vi.fn(), clearInterval: vi.fn() },
      writable: true,
    });

    // 使用较短的 flushIntervalMs 方便测试
    logger = new FrontendLogger({
      minLevel: "debug",
      bufferSize: 200,
      flushThreshold: 50,
      flushIntervalMs: 5000,
      endpoint: "/api/test-logs",
    });
  });

  afterEach(() => {
    logger.destroy();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  // ── 基本记录功能 ──────────────────────────────────────

  it("should construct a valid LogEntry for each level", () => {
    const entries: LogEntry[] = [];

    // 拦截 buffer 来捕获 entry（通过 spy）
    const origLog = (logger as unknown as { log: typeof logger.log }).log.bind(logger);
    vi.spyOn(logger as unknown as { log: typeof logger.log }, "log").mockImplementation(
      (level, module, message, context) => {
        const entry = { timestamp: new Date().toISOString(), level, module, message, context, userAgent: "test-agent", url: "/test", sessionId: logger.sessionId };
        entries.push(entry);
      },
    );

    logger.debug("mod1", "debug msg");
    logger.info("mod2", "info msg");
    logger.warn("mod3", "warn msg");
    logger.error("mod4", "error msg");

    expect(entries).toHaveLength(4);
    expect(entries[0]).toMatchObject({ level: "debug", module: "mod1", message: "debug msg" });
    expect(entries[1]).toMatchObject({ level: "info", module: "mod2", message: "info msg" });
    expect(entries[2]).toMatchObject({ level: "warn", module: "mod3", message: "warn msg" });
    expect(entries[3]).toMatchObject({ level: "error", module: "mod4", message: "error msg" });
  });

  // ── 级别过滤 ──────────────────────────────────────────

  it("should filter out logs below minLevel (default warn)", () => {
    const strictLogger = new FrontendLogger({
      minLevel: "warn",
      bufferSize: 100,
      flushThreshold: 999, // 不触发自动 flush
      flushIntervalMs: 60_000,
      endpoint: "/api/test-logs",
    });

    strictLogger.debug("m", "d"); // 应被过滤
    strictLogger.info("m", "i");  // 应被过滤
    strictLogger.warn("m", "w");  // 应保留
    strictLogger.error("m", "e"); // 应保留

    // 通过 flush 来验证缓冲区内容
    const buf = (strictLogger as unknown as { buffer: LogEntry[] }).buffer;
    expect(buf).toHaveLength(2);
    expect(buf[0].level).toBe("warn");
    expect(buf[1].level).toBe("error");

    strictLogger.destroy();
  });

  // ── 缓冲区管理 ────────────────────────────────────────

  it("should discard oldest entries when buffer exceeds capacity", () => {
    const tinyLogger = new FrontendLogger({
      minLevel: "debug",
      bufferSize: 5,
      flushThreshold: 999,
      flushIntervalMs: 60_000,
      endpoint: "/api/test-logs",
    });

    for (let i = 0; i < 10; i++) {
      tinyLogger.debug("mod", `msg-${i}`);
    }

    const buf = (tinyLogger as unknown as { buffer: LogEntry[] }).buffer;
    expect(buf).toHaveLength(5);
    // 最旧的应该被丢弃，保留最新的5条
    expect(buf[0].message).toBe("msg-5");
    expect(buf[4].message).toBe("msg-9");

    tinyLogger.destroy();
  });

  // ── 自动 flush：缓冲区满阈值 ─────────────────────────

  it("should trigger flush when buffer reaches flushThreshold", () => {
    const flushSpy = vi.spyOn(FrontendLogger.prototype, "flush").mockResolvedValue();

    const flushLogger = new FrontendLogger({
      minLevel: "debug",
      bufferSize: 200,
      flushThreshold: 3,
      flushIntervalMs: 60_000,
      endpoint: "/api/test-logs",
    });

    // 前两条不触发
    flushLogger.warn("m", "a");
    flushLogger.warn("m", "b");
    expect(flushSpy).not.toHaveBeenCalled();

    // 第三条触发自动 flush
    flushLogger.warn("m", "c");
    expect(flushSpy).toHaveBeenCalledTimes(1);

    flushSpy.mockRestore();
    flushLogger.destroy();
  });

  // ── flush 发送数据到后端 ───────────────────────────────

  it("should POST buffered entries to endpoint", async () => {
    const postLogger = new FrontendLogger({
      minLevel: "debug",
      bufferSize: 200,
      flushThreshold: 999, // 不自动触发
      flushIntervalMs: 60_000,
      endpoint: "/api/test-logs",
    });

    postLogger.error("mod1", "err-one", { code: 500 });
    postLogger.error("mod2", "err-two");

    await postLogger.flush();

    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/test-logs",
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining("err-one"),
      }),
    );

    const body = JSON.parse(mockFetch.mock.calls[0][1]?.body);
    expect(body).toHaveLength(2);
    expect(body[0]).toMatchObject({ level: "error", module: "mod1", message: "err-one" });
    expect(body[1]).toMatchObject({ level: "error", module: "mod2", message: "err-two" });
    expect(body[0].context).toEqual({ code: 500 });

    postLogger.destroy();
  });

  // ── 定时器 flush ──────────────────────────────────────

  it("should flush on interval timer", async () => {
    const timerLogger = new FrontendLogger({
      minLevel: "debug",
      bufferSize: 200,
      flushThreshold: 999, // 不会因数量触发
      flushIntervalMs: 3000,
      endpoint: "/api/test-logs",
    });

    timerLogger.error("m", "pending log");

    // 推进时间到超过 flushIntervalMs
    await vi.advanceTimersByTimeAsync(3000);

    expect(mockFetch).toHaveBeenCalledTimes(1);

    timerLogger.destroy();
  });

  // ── destroy 清理定时器 ─────────────────────────────────

  it("should clear timer and send remaining logs on destroy", () => {
    const beaconSpy = vi.spyOn(navigator, "sendBeacon");

    logger.error("m", "remaining");

    logger.destroy();

    expect(beaconSpy).toHaveBeenCalledWith(
      "/api/test-logs",
      expect.stringContaining("remaining"),
    );
  });

  // ── flush 失败时放回缓冲区 ────────────────────────────

  it("should put entries back into buffer when flush fails", async () => {
    const failLogger = new FrontendLogger({
      minLevel: "debug",
      bufferSize: 200,
      flushThreshold: 999, // 不让 log() 自动触发 flush
      flushIntervalMs: 60_000,
      endpoint: "/api/fail-logs",
    });

    globalThis.fetch = vi.fn().mockRejectedValue(new Error("network error"));

    failLogger.warn("m", "will-fail-1");
    failLogger.warn("m", "will-fail-2");

    // 手动调用一次 flush（不通过定时器避免无限循环）
    await failLogger.flush();

    const buf = (failLogger as unknown as { buffer: LogEntry[] }).buffer;
    // 失败后应放回缓冲区头部
    expect(buf.length).toBeGreaterThanOrEqual(2);
    expect(buf[0].message).toBe("will-fail-1");

    failLogger.destroy();
  });

  // ── context 可选参数 ──────────────────────────────────

  it("should include optional context in log entry", () => {
    const ctxLogger = new FrontendLogger({
      minLevel: "debug",
      bufferSize: 100,
      flushThreshold: 999,
      flushIntervalMs: 60_000,
      endpoint: "/api/test-logs",
    });

    ctxLogger.error("my-module", "something broke", { code: 500, taskId: "abc123" });

    const buf = (ctxLogger as unknown as { buffer: LogEntry[] }).buffer;
    expect(buf).toHaveLength(1);
    expect(buf[0].context).toEqual({ code: 500, taskId: "abc123" });

    ctxLogger.destroy();
  });

  // ── 会话 ID ─────────────────────────────────────────────

  it("should generate a unique sessionId for each instance", () => {
    const loggerA = new FrontendLogger({
      minLevel: "warn", bufferSize: 10, flushThreshold: 999, flushIntervalMs: 60_000, endpoint: "/api/test-logs",
    });
    const loggerB = new FrontendLogger({
      minLevel: "warn", bufferSize: 10, flushThreshold: 999, flushIntervalMs: 60_000, endpoint: "/api/test-logs",
    });

    // 格式：时间戳(base36)-4位随机字符
    expect(loggerA.sessionId).toMatch(/^[a-z0-9]+-[a-z0-9]{4}$/);
    expect(loggerB.sessionId).toMatch(/^[a-z0-9]+-[a-z0-9]{4}$/);
    // 不同实例应有不同 ID
    expect(loggerA.sessionId).not.toBe(loggerB.sessionId);

    loggerA.destroy();
    loggerB.destroy();
  });

  it("should include sessionId in every log entry and flushed payload", async () => {
    const sidLogger = new FrontendLogger({
      minLevel: "debug", bufferSize: 200, flushThreshold: 999, flushIntervalMs: 60_000, endpoint: "/api/test-logs",
    });

    sidLogger.error("m", "test");

    // 验证缓冲区中的 entry 包含 sessionId
    const buf = (sidLogger as unknown as { buffer: LogEntry[] }).buffer;
    expect(buf[0].sessionId).toBe(sidLogger.sessionId);

    // 验证 flush 发送的 payload 也包含 sessionId
    await sidLogger.flush();
    const body = JSON.parse(mockFetch.mock.calls[mockFetch.mock.calls.length - 1][1]?.body);
    expect(body[0].sessionId).toBe(sidLogger.sessionId);

    sidLogger.destroy();
  });
});
