"use client";

import { useEffect, useRef, useState, useMemo } from "react";
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
  isStatusPayload,
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

// ── 统计栏 ────────────────────────────────────────────────

function StatsBar({ events }: { events: SSEEvent[] }) {
  const stats = useMemo(() => {
    let logs = 0, thinking = 0, toolStarts = 0, toolResults = 0,
        progressEvents = 0, errors = 0;
    let lastProgress: ProgressPayload | null = null;

    for (const evt of events) {
      switch (evt.type) {
        case "log": logs++; break;
        case "thinking": thinking++; break;
        case "tool_start": toolStarts++; break;
        case "tool_result": toolResults++; break;
        case "progress":
          progressEvents++;
          if (typeof evt.data === "object" && evt.data !== null) {
            lastProgress = evt.data as ProgressPayload;
          }
          break;
        case "status": break;
        default: break;
      }
      // 检测错误日志
      if (evt.type === "log" && typeof evt.data === "string") {
        const d = evt.data.toLowerCase();
        if (d.includes("[err]") || d.includes("[trace]")) errors++;
      }
    }

    return { logs, thinking, toolStarts, toolResults, progressEvents, errors, lastProgress };
  }, [events]);

  const p = stats.lastProgress;
  return (
    <div className="flex items-center gap-3 px-3 py-1.5 text-[10px] font-mono border-b border-border/20 bg-surface/40 text-muted-foreground/60 flex-wrap">
      <span title="文本日志">
        \ud83d\udcdd {stats.logs}
      </span>
      {stats.thinking > 0 && (
        <span title="思考块">
          \ud83e\udde0 {stats.thinking}
        </span>
      )}
      {stats.toolStarts > 0 && (
        <span title="工具调用">
          \U0001f527 {stats.toolStarts}/{stats.toolResults}
        </span>
      )}
      {p && (
        <>
          <span title="当前轮次">
            \ud83d\udd02 Turn {p.turn}
          </span>
          <span title="Token 消耗">
            \ud83d\udcca {p.total_tokens.toLocaleString()}
          </span>
          <span title="已用时间">
            \u23f1 {(p.elapsed_ms / 1000).toFixed(1)}s
          </span>
        </>
      )}
      {stats.errors > 0 && (
        <span className="text-red-400/70 ml-auto" title="错误数量">
          \u274c {stats.errors}
        </span>
      )}
    </div>
  );
}

// ── 阶段标记 ──────────────────────────────────────────────

interface PhaseMarker {
  id: string;
  label: string;
  icon: string;
  className: string;
}

/** 从事件内容中检测 pipeline 阶段。 */
function detectPhase(evt: SSEEvent, index: number, allEvents: SSEEvent[]): PhaseMarker | null {
  if (evt.type !== "log" || typeof evt.data !== "string") return null;
  const d = evt.data;

  // 匹配已知阶段模式
  if (d.includes("[PROGRESS]") || d.includes("Phase 1")) {
    return { id: `phase-${index}`, label: "初始化", icon: "\U0001f504", className: "phase-init" };
  }
  if (d.includes("Phase 2") || d.toLowerCase().includes("scene") && d.toLowerCase().includes("generat")) {
    return { id: `phase-${index}`, label: "场景生成", icon: "\U0001f3a8", className: "phase-scene" };
  }
  if (d.includes("Phase 3") || d.toLowerCase().includes("render")) {
    return { id: `phase-${index}`, label: "视频渲染", icon: "\U0001f39e", className: "phase-render" };
  }
  if (d.includes("Phase 4") || d.includes("TTS") || d.toLowerCase().includes("narration") || d.toLowerCase().includes("voice")) {
    return { id: `phase-${index}`, label: "语音合成", icon: "\U0001f3a4", className: "phase-tts" };
  }
  if (d.includes("[SUMMARY]") || d.includes("Session Summary")) {
    return { id: `phase-${index}`, label: "完成摘要", icon: "\U0001f4cb", className: "phase-summary" };
  }

  // 检测工具调用密集区域 → 标记为执行阶段
  if (isToolStart(evt)) {
    // 检查前面几个事件是否也是 tool_start（连续工具调用）
    const recentTools = allEvents.slice(Math.max(0, index - 3), index)
      .filter(e => isToolStart(e));
    if (recentTools.length === 0 || index < 3) {
      // 第一个 tool_start 或间隔后的第一个
      return { id: `phase-${index}`, label: "工具执行", icon: "\U0001f527", className: "phase-tools" };
    }
  }

  return null;
}

function PhaseDivider({ marker }: { marker: PhaseMarker }) {
  const colorMap: Record<string, string> = {
    "phase-init": "border-cyan-500/30 text-cyan-400 bg-cyan-500/[0.04]",
    "phase-scene": "border-purple-500/30 text-purple-400 bg-purple-500/[0.04]",
    "phase-render": "border-green-500/30 text-green-400 bg-green-500/[0.04]",
    "phase-tts": "border-orange-500/30 text-orange-400 bg-orange-500/[0.04]",
    "phase-summary": "border-blue-500/30 text-blue-400 bg-blue-500/[0.04]",
    "phase-tools": "border-blue-500/30 text-blue-400 bg-blue-500/[0.04]",
  };
  const cls = colorMap[marker.className] || colorMap["phase-tools"];

  return (
    <div key={marker.id} className={`flex items-center gap-2 py-1 px-3 my-2 rounded-md border ${cls}`}>
      <span>{marker.icon}</span>
      <span className="text-[11px] font-medium">{marker.label}</span>
    </div>
  );
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
    <div className="flex items-start gap-2 py-1.5 px-2 rounded-md bg-blue-500/[0.05] border border-blue-500/10 my-0.5">
      <span className="text-blue-400 shrink-0 mt-0.5">
        <ToolIcon name={payload.name} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-blue-300 font-medium text-[11px]">
            {payload.name}
          </span>
          <span className="text-blue-500/40 text-[10px] font-mono">
            {payload.tool_use_id.slice(-8)}
          </span>
        </div>
        {Object.keys(payload.input_summary).length > 0 && (
          <div className="mt-0.5 flex flex-wrap gap-x-2 gap-y-0.5">
            {Object.entries(payload.input_summary).slice(0, 4).map(([k, v]) => (
              <span key={k} className="text-blue-200/50 text-[10px] font-mono truncate max-w-[180px]">
                {k}={typeof v === "string" ? v.slice(0, 40) + (v.length > 40 ? "..." : "") : JSON.stringify(v).slice(0, 30)}
              </span>
            ))}
            {Object.keys(payload.input_summary).length > 4 && (
              <span className="text-blue-300/40 text-[10px]">
                +{Object.keys(payload.input_summary).length - 4} more
              </span>
            )}
          </div>
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
        <span className={`${textColor}/70 text-[11px] truncate max-w-[280px]`}>
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
    <div className="my-0.5 border-l-2 border-purple-500/25 pl-3 py-1">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 text-purple-300/80 hover:text-purple-300 text-[11px] w-full text-left"
      >
        <span className="transition-transform inline-block"
          style={{ transform: expanded ? "rotate(90deg)" : "none" }}
        >&#9654;</span>
        <span>\U0001f4ad</span>
        <span className="truncate flex-1">{preview}</span>
        {payload.signature && (
          <span className="text-purple-400/30 text-[10px] font-mono shrink-0">
            {payload.signature.slice(0, 12)}
          </span>
        )}
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
    <div className="flex items-center gap-3 py-1 px-2 text-[11px] text-muted-foreground/60 my-0.5 bg-surface/30 rounded-sm">
      <span>\u2699\ufe0f</span>
      <span>Turn {payload.turn}</span>
      <span className="text-cyan-400/70 font-mono font-medium">
        {payload.total_tokens.toLocaleString()} tokens
      </span>
      <span>{payload.tool_uses} tools</span>
      {payload.last_tool_name && (
        <span className="text-blue-400/50">{payload.last_tool_name}</span>
      )}
      <span className="ml-auto text-[10px]">
        {(payload.elapsed_ms / 1000).toFixed(1)}s
      </span>
    </div>
  );
}

// ── 分类函数（向后兼容） ──────────────────────────────────

function classifyLog(line: string): string {
  const lower = line.toLowerCase();
  if (lower.includes("[err]") || lower.includes("error") || lower.includes("failed")
      || lower.includes("exception") || lower.includes("traceback")) {
    return "log-error";
  }
  if (lower.includes("warning") || lower.includes("warn")) {
    return "log-warning";
  }
  if (lower.includes("\u2713") || lower.includes("done")
      || lower.includes("complete") || lower.includes("success")
      || lower.includes("[ok]")) {
    return "log-success";
  }
  if (/^(==|\u2192|\u25b8|\u25cf|\u25a0|\[.*?\])/.test(line)
      || lower.includes("step") || lower.includes("stage")
      || lower.includes("phase") || lower.includes("[progress]")
      || lower.includes("[summary]")) {
    return "log-step";
  }
  if (line.trim().length === 0) return "log-dim";
  return "log-info";
}

// ── 主组件 ────────────────────────────────────────────────

export function LogViewer({ events, isRunning }: LogViewerProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  // Pre-compute phase marker indices once per events change (O(n) instead of O(n²))
  const phaseMarkers = useMemo(() => {
    const markers: { index: number; marker: PhaseMarker }[] = [];
    events.forEach((evt, i) => {
      const phase = detectPhase(evt, i, events);
      if (phase) markers.push({ index: i, marker: phase });
    });
    return markers;
  }, [events]);

  const phaseIndexSet = useMemo(
    () => new Set(phaseMarkers.map((m) => m.index)),
    [phaseMarkers],
  );
  const phaseMap = useMemo(
    () => new Map(phaseMarkers.map((m) => [m.index, m.marker])),
    [phaseMarkers],
  );

  return (
    <div className="relative rounded-xl overflow-hidden border border-white/10 bg-black/40 backdrop-blur-xl shadow-2xl transition-all duration-300 ring-1 ring-white/5">
      {/* 噪点纹理层 */}
      <div className="absolute inset-0 pointer-events-none opacity-[0.04] mix-blend-screen bg-[url('data:image/svg+xml,%3Csvg viewBox=%220 0 200 200%22 xmlns=%22http://www.w3.org/2000/svg%22%3E%3Cfilter id=%22noiseFilter%22%3E%3CfeTurbulence type=%22fractalNoise%22 baseFrequency=%220.85%22 numOctaves=%223%22 stitchTiles=%22stitch%22/%3E%3C/filter%3E%3Crect width=%22100%25%22 height=%22100%25%22 filter=%22url(%23noiseFilter)%22/%3E%3C/svg%3E')]" />

      {/* Terminal header bar */}
      <div className="relative z-10 flex items-center gap-2 px-4 py-3 bg-white/[0.02] border-b border-white/[0.05]">
        <div className="flex gap-1 items-center">
          <span className="w-1.5 h-3.5 bg-cyan-500/80 shrink-0 rounded-[1px]" />
          <span className="w-1.5 h-3.5 bg-blue-500/40 shrink-0 rounded-[1px] animate-pulse" />
        </div>
        <span className="text-[10px] text-cyan-400/80 font-mono tracking-widest uppercase ml-1 mt-0.5">
          SYS.LOGS
        </span>
        {isRunning && (
          <span className="ml-auto flex items-center gap-2">
            <span className="w-1 h-3 bg-green-500 animate-pulse shadow-[0_0_8px_rgba(34,197,94,0.8)]" />
            <span className="text-[10px] text-green-400 font-mono uppercase tracking-wider">Active</span>
          </span>
        )}
      </div>

      {/* Statistics bar */}
      {events.length > 0 && <StatsBar events={events} />}

      {/* Event content */}
      <ScrollArea className={`h-[480px] w-full bg-transparent p-4 font-mono text-xs leading-5 relative z-10`}>
        <div className="space-y-0">
          {events.length === 0 && (
            <div className="flex flex-col gap-2 pt-2 px-1 text-white/30 font-mono text-[11px] uppercase tracking-widest">
              <span className="log-dim">Awaiting system boot...</span>
              <div className="flex items-center gap-2.5">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500" />
                </span>
                <span className="animate-pulse text-cyan-500/70">Initializing Claude Agent SDK</span>
              </div>
            </div>
          )}
          {events.map((evt, i) => {
            const elements: React.ReactNode[] = [];

            // O(1) lookup from pre-computed phase map
            if (phaseIndexSet.has(i)) {
              elements.push(<PhaseDivider key={`phase-${i}`} marker={phaseMap.get(i)!} />);
            }

            elements.push(
              <EventRenderer key={`evt-${i}`} event={evt} index={i} />
            );

            return elements;
          })}
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

function EventRenderer({ event, index }: { event: SSEEvent; index?: number }) {
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
  if (isStatusPayload(event)) {
    const statusMap: Record<string, { icon: string }> = {
      pending: { icon: "⏳" },
      running: { icon: "▶" },
      completed: { icon: "✅" },
      failed: { icon: "❌" },
    };
    const s = statusMap[event.data.task_status] ?? { icon: "•" };
    const phaseSuffix = event.data.phase ? ` (${event.data.phase})` : "";
    const messageSuffix = event.data.message ? ` - ${event.data.message}` : "";
    return (
      <LogLine
        text={`${s.icon} Status: ${event.data.task_status}${phaseSuffix}${messageSuffix}`}
      />
    );
  }

  // Backward compatibility: plain-text log / status / error events
  if (typeof event.data === "string") {
    // status 事件也渲染为可见日志
    if (event.type === "status") {
      const statusMap: Record<string, { icon: string; cls: string }> = {
        pending: { icon: "\u23F3", cls: "log-step" },
        running: { icon: "\u25B6", cls: "log-success" },
        completed: { icon: "\u2705", cls: "log-success" },
        failed: { icon: "\u274C", cls: "log-error" },
      };
      const s = statusMap[event.data as string]
        ?? { icon: "\u2022", cls: "log-info" };
      return <LogLine text={`${s.icon} Status: ${event.data}`} />;
    }
    return <LogLine text={event.data} />;
  }

  // 兜底：未知结构化数据转为 JSON 字符串
  return <LogLine text={JSON.stringify(event.data)} />;
}
