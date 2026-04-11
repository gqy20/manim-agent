/**
 * 前端日志持久化模块
 *
 * 将前端 warn/error 级别日志缓冲后批量 POST 到后端，
 * 由后端写入 backend/logs/frontend-{sessionId}.log (NDJSON 格式)。
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

/** 生成当前页面的会话 ID（时间戳 + 4位随机字符） */
function generateSessionId(): string {
  const ts = Date.now().toString(36);
  const rnd = Math.random().toString(36).slice(2, 6);
  return `${ts}-${rnd}`;
}

export interface LogEntry {
  timestamp: string;
  level: "debug" | "info" | "warn" | "error";
  module: string;
  message: string;
  context?: Record<string, unknown>;
  userAgent: string;
  url: string;
  /** 会话标识，用于后端按会话分文件 */
  sessionId: string;
}

interface LoggerConfig {
  /** 最小记录级别，默认 warn */
  minLevel?: LogEntry["level"];
  /** 缓冲区最大容量，默认 200 */
  bufferSize?: number;
  /** 批量刷写阈值，默认 50 */
  flushThreshold?: number;
  /** 刷写间隔(ms)，默认 5000 */
  flushIntervalMs?: number;
  /** 后端接收端点 */
  endpoint?: string;
}

/** 日志级别优先级（数值越大越重要） */
const LEVEL_PRIORITY: Record<LogEntry["level"], number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

export class FrontendLogger {
  private buffer: LogEntry[] = [];
  private timerId: ReturnType<typeof setInterval> | null = null;
  private config: Required<LoggerConfig>;
  private flushing = false;
  /** 当前会话 ID，页面加载时生成，贯穿整个生命周期 */
  readonly sessionId: string;

  constructor(config?: LoggerConfig) {
    this.sessionId = generateSessionId();
    this.config = {
      minLevel: config?.minLevel ?? "warn",
      bufferSize: config?.bufferSize ?? 200,
      flushThreshold: config?.flushThreshold ?? 50,
      flushIntervalMs: config?.flushIntervalMs ?? 5000,
      endpoint: config?.endpoint ?? `${API_BASE}/api/tasks/frontend-logs`,
    };

    // 定时刷写
    if (typeof window !== "undefined") {
      this.timerId = setInterval(() => this.flush(), this.config.flushIntervalMs);

      // 页面卸载时兜底发送
      document.addEventListener(
        "visibilitychange",
        () => {
          if (document.visibilityState === "hidden") {
            this.flushViaBeacon();
          }
        },
        { once: false },
      );
    }
  }

  /** 核心记录方法 */
  private log(
    level: LogEntry["level"],
    module: string,
    message: string,
    context?: Record<string, unknown>,
  ): void {
    // 级别过滤
    if (LEVEL_PRIORITY[level] < LEVEL_PRIORITY[this.config.minLevel]) {
      return;
    }

    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      module,
      message,
      context,
      userAgent: typeof navigator !== "undefined" ? navigator.userAgent : "",
      url: typeof window !== "undefined" ? window.location.pathname : "",
      sessionId: this.sessionId,
    };

    // 环形缓冲：超出容量时丢弃最旧的
    this.buffer.push(entry);
    if (this.buffer.length > this.config.bufferSize) {
      this.buffer.shift();
    }

    // 达到阈值时触发刷写
    if (this.buffer.length >= this.config.flushThreshold) {
      this.flush();
    }
  }

  debug(module: string, message: string, context?: Record<string, unknown>): void {
    this.log("debug", module, message, context);
  }

  info(module: string, message: string, context?: Record<string, unknown>): void {
    this.log("info", module, message, context);
  }

  warn(module: string, message: string, context?: Record<string, unknown>): void {
    this.log("warn", module, message, context);
  }

  error(module: string, message: string, context?: Record<string, unknown>): void {
    this.log("error", module, message, context);
  }

  /** 手动触发刷写（异步，静默处理错误） */
  async flush(): Promise<void> {
    if (this.flushing || this.buffer.length === 0) return;

    this.flushing = true;
    const batch = this.buffer.splice(0);

    try {
      await fetch(this.config.endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(batch),
        keepalive: true,
      });
    } catch {
      // 失败时放回缓冲区头部（下次重试）
      this.buffer.unshift(...batch);
    } finally {
      this.flushing = false;
    }
  }

  /** 使用 sendBeacon 兜底发送（页面卸载时调用） */
  private flushViaBeacon(): void {
    if (this.buffer.length === 0) return;

    const batch = this.buffer.splice(0);
    try {
      const payload = JSON.stringify(batch);
      navigator.sendBeacon(this.config.endpoint, payload);
    } catch {
      // sendBeacon 失败时静默忽略（页面即将卸载）
    }
  }

  /** 销毁实例（清除定时器） */
  destroy(): void {
    if (this.timerId !== null) {
      clearInterval(this.timerId);
      this.timerId = null;
    }
    // 最后一次尝试发送剩余日志
    this.flushViaBeacon();
  }
}

/** 全局单例 */
export const logger = new FrontendLogger();
