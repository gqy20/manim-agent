"use client";

import { useEffect, useRef, useState } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import type {
  SSEEvent,
  ToolStartPayload,
  ToolResultPayload,
  ThinkingPayload,
  ProgressPayload,
} from "@/types";
import {
  isToolStart,
  isToolResult,
  isThinking,
  isProgress,
} from "@/types";

interface LogViewerProps {
  events: SSEEvent[];
  isRunning: boolean;
}

// ── 图标组件 ──────────────────────────────────────────────

function ToolIcon({ name }: { name: string }) {
  const iconMap: Record<string, string> = {
    Write: "\u270f\ufe0f",
    Edit: "\u270f\ufe0f",
    Bash: "\U0001f528",
    Read: "\U0001f4cf",
    Glob: "\U0001f50d",
  };
  return <span>{iconMap[name] || "\u25b6"}</span>;
}

// ── 子组件：各类事件渲染器 ────────────────────────────────

function LogLine({ text }: { text: string }) {
  const cls = classifyLog(text);
  return (
    <pre className={`${cls} whitespace-pre-wrap break-all`}>{text}</pre>
  );
}

function ToolStartView({ payload }: { payload: ToolStartPayload }) {
  return (
    <div className="flex items-start gap-2 py-1 px-2 rounded-md bg-blue-500/[0.04] border border-blue-500/10 my-0.5">
      <span className="text-blue-400 shrink-0 mt-0.5">
        <ToolIcon name={payload.name} />
      </span>
      <div className="min-w-0 flex-1">
        <span className="text-blue-300 font-medium text-[11px]">
          {payload.name}
        </span>
        {Object.keys(payload.input_summary).length > 0 && (
          <span className="text-blue-200/60 text-[11px] ml-2 truncate block">
            {formatInputSummary(payload.input_summary)}
          </span>
        )}
      </div>
    </div>
  );
}

function ToolResultView({ payload }: { payload: ToolResultPayload }) {
  const isError = payload.is_error;
  const bg = isError ? "bg-red-500/[0.04]" : "bg-green-500/[0.04]";
  const border = isError
    ? "border-red-500/10"
    : "border-green-500/10";
  const textColor = isError ? "text-red-300" : "text-green-300";
  const icon = isError ? "\u274c" : "\u2705";

  return (
    <div
      className={`flex items-center gap-2 py-1 px-2 rounded-md ${bg} border ${border} my-0.5 ml-6`}
    >
      <span className={textColor}>{icon}</span>
      {payload.content && (
        <span className={`${textColor}/70 text-[11px] truncate`}>
          {payload.content.length > 120
            ? payload.content.slice(0, 120) + "..."
            : payload.content}
        </span>
      )}
      {payload.duration_ms != null && (
        <span className="text-muted-foreground/40 text-[10px] ml-auto shrink-0">
          {payload.duration_ms}ms
        </span>
      )}
    </div>
  );
}

function ThinkingView({ payload }: { payload: ThinkingPayload }) {
  const [expanded, setExpanded] = useState(false);
  const preview = payload.preview ?? payload.thinking.slice(0, 97) + "...";

  return (
    <div className="my-0.5 border-l-2 border-purple-500/30 pl-3 py-1">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 text-purple-300/80 hover:text-purple-300 text-[11px] w-full text-left"
      >
        <span className="transition-transform inline-block"
          style={{ transform: expanded ? "rotate(90deg)" : "none" }}
        >&#9654;</span>
        <span>\U0001f4ad</span>
        <span className="truncate">{preview}</span>
      </button>
      {expanded && (
        <pre className="text-purple-200/50 text-[11px] mt-1 whitespace-pre-wrap break-words leading-relaxed">
          {payload.thinking}
        </pre>
      )}
    </div>
  );
}

function ProgressView({ payload }: { payload: ProgressPayload }) {
  return (
    <div className="flex items-center gap-3 py-1 px-2 text-[11px] text-muted-foreground/60 my-0.5">
      <span>\u2699\ufe0f</span>
      <span>Turn {payload.turn}</span>
      <span className="text-cyan-400/70 font-mono">
        {payload.total_tokens.toLocaleString()} tokens
      </span>
      <span>{payload.tool_uses} tools</span>
      <span className="ml-auto text-[10px]">
        {(payload.elapsed_ms / 1000).toFixed(1)}s
      </span>
    </div>
  );
}

// ── 分类函数（向后兼容） ──────────────────────────────────

function classifyLog(line: string): string {
  const lower = line.toLowerCase();
  if (lower.includes("error") || lower.includes("failed")
      || lower.includes("exception") || lower.includes("traceback")) {
    return "log-error";
  }
  if (lower.includes("warning") || lower.includes("warn")) {
    return "log-warning";
  }
  if (lower.includes("\u2713") || lower.includes("done")
      || lower.includes("complete") || lower.includes("success")) {
    return "log-success";
  }
  if (/^(==|\u2192|\u25b8|\u25cf|\u25a0|\[.*?\])/.test(line)
      || lower.includes("step") || lower.includes("stage")
      || lower.includes("phase")) {
    return "log-step";
  }
  if (line.trim().length === 0) return "log-dim";
  return "log-info";
}

function formatInputSummary(
  summary: Record<string, unknown>,
): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(summary)) {
    const vs = String(v);
    parts.push(
      vs.length > 50 ? `${k}=${vs.slice(0, 47)}...` : `${k}=${vs}`,
    );
  }
  return parts.join(" ");
}

// ── 主组件 ────────────────────────────────────────────────

export function LogViewer({ events, isRunning }: LogViewerProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  return (
    <div className="relative rounded-xl overflow-hidden border border-border/50 glow-border transition-all duration-300">
      {/* Terminal header bar */}
      <div className="flex items-center gap-2 px-4 py-2.5 bg-surface-elevated/80 border-b border-border/30">
        <div className="flex gap-1.5">
          <span className="w-3 h-3 rounded-full bg-red-500/70" />
          <span className="w-3 h-3 rounded-full bg-yellow-500/70" />
          <span className="w-3 h-3 rounded-full bg-green-500/70" />
        </div>
        <span className="text-xs text-muted-foreground font-mono ml-1">
          流水线日志
        </span>
        {isRunning && (
          <span className="ml-auto flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            <span className="text-xs text-green-400 font-mono">运行中</span>
          </span>
        )}
      </div>

      {/* Event content */}
      <ScrollArea className="h-[480px] w-full bg-zinc-950/90 p-4 font-mono text-xs leading-5">
        <div className="space-y-0">
          {events.length === 0 && (
            <span className="log-dim">等待流水线启动...</span>
          )}
          {events.map((evt, i) => (
            <EventRenderer key={i} event={evt} />
          ))}
          {isRunning && (
            <pre className="text-green-400 animate-pulse inline-block">
              &#9608;
            </pre>
          )}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>
    </div>
  );
}

// ── 事件分发渲染器 ────────────────────────────────────────

function EventRenderer({ event }: { event: SSEEvent }) {
  // 结构化事件
  if (isToolStart(event)) {
    return <ToolStartView payload={event.data} />;
  }
  if (isToolResult(event)) {
    return <ToolResultView payload={event.data} />;
  }
  if (isThinking(event)) {
    return <ThinkingView payload={event.data} />;
  }
  if (isProgress(event)) {
    return <ProgressView payload={event.data} />;
  }

  // 向后兼容：纯文本日志 / status / error
  if (typeof event.data === "string") {
    return <LogLine text={event.data} />;
  }

  // 兜底：未知结构化数据转为 JSON 字符串
  return <LogLine text={JSON.stringify(event.data)} />;
}
