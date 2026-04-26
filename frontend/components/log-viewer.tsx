"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type {
  ProgressPayload,
  SSEEvent,
  ThinkingPayload,
  ToolResultPayload,
  ToolStartPayload,
} from "@/types";
import {
  isProgress,
  isStatusPayload,
  isThinking,
  isToolResult,
  isToolStart,
} from "@/types";
import { getLatestStructuredStatus, normalizeVisualPhase } from "@/lib/pipeline-phase";

import { PipelineProgress } from "./pipeline-progress";

interface LogViewerProps {
  events: SSEEvent[];
  isRunning: boolean;
  taskStatus: string;
}

interface PhaseMarker {
  id: string;
  label: string;
  icon: string;
  className: string;
}

const TIMESTAMP_COL_CLASS =
  "w-[5.25rem] shrink-0 pt-[2px] text-[10px] font-mono text-white/20 tabular-nums whitespace-nowrap";

function formatEventTime(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return "--:--:--";
  }
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function formatToolValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function getToolDisplayName(name: string): string {
  if (name === "StructuredOutput") return "Output";
  return name;
}

function getToolSummaryKeys(payload: ToolStartPayload): string[] {
  if (payload.name === "Read" || payload.name === "Edit") return [];

  return Object.keys(payload.input_summary)
    .filter((key) => key !== "file_path" && key !== "replace_all")
    .slice(0, 3);
}

function formatCny(value: number): string {
  if (value < 0.01) return `CNY ${value.toFixed(4)}`;
  if (value < 1) return `CNY ${value.toFixed(3)}`;
  return `CNY ${value.toFixed(2)}`;
}

function StatsBar({ events }: { events: SSEEvent[] }) {
  const stats = useMemo(() => {
    let logs = 0;
    let thinking = 0;
    let toolStarts = 0;
    let toolResults = 0;
    let progressEvents = 0;
    let errors = 0;
    let lastProgress: ProgressPayload | null = null;

    for (const event of events) {
      switch (event.type) {
        case "log":
          logs += 1;
          break;
        case "thinking":
          thinking += 1;
          break;
        case "tool_start":
          toolStarts += 1;
          break;
        case "tool_result":
          toolResults += 1;
          break;
        case "progress":
          progressEvents += 1;
          if (typeof event.data === "object" && event.data !== null) {
            lastProgress = event.data as ProgressPayload;
          }
          break;
        default:
          break;
      }

      if (event.type === "log" && typeof event.data === "string") {
        const lower = event.data.toLowerCase();
        if (lower.includes("[err]") || lower.includes("[trace]") || lower.includes("failed")) {
          errors += 1;
        }
      }
    }

    return { errors, lastProgress, logs, progressEvents, thinking, toolResults, toolStarts };
  }, [events]);

  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-border/20 bg-surface/40 px-3 py-1.5 text-[10px] font-mono text-muted-foreground/60">
      <span title="Text logs">LOG {stats.logs}</span>
      {stats.thinking > 0 && <span title="Reasoning blocks">THINK {stats.thinking}</span>}
      {stats.toolStarts > 0 && (
        <span title="Tool activity">TOOLS {stats.toolStarts}</span>
      )}
      {stats.toolResults > 0 && <span title="Completed tool results">RESULTS {stats.toolResults}</span>}
      {stats.progressEvents > 0 && <span title="Structured progress">PROG {stats.progressEvents}</span>}
      {stats.lastProgress && (
        <>
          <span title="Current turn">TURN {stats.lastProgress.turn}</span>
          <span title="Token usage">{stats.lastProgress.total_tokens.toLocaleString()} TOKENS</span>
          {stats.lastProgress.estimated_cost_cny != null && (
            <span title={`Estimated local token cost (${stats.lastProgress.pricing_model ?? "unknown pricing"})`}>
              {formatCny(stats.lastProgress.estimated_cost_cny)}
            </span>
          )}
          <span title="Elapsed">{(stats.lastProgress.elapsed_ms / 1000).toFixed(1)}S</span>
        </>
      )}
      {stats.errors > 0 && (
        <span className="ml-auto text-red-400/70" title="Error lines">
          ERR {stats.errors}
        </span>
      )}
    </div>
  );
}

function detectPhase(
  event: SSEEvent,
  index: number,
  hasStructuredPhaseStatus: boolean,
): PhaseMarker | null {
  if (isStatusPayload(event)) {
    const phase = normalizeVisualPhase(event.data.phase);
    if (!phase) return null;

    const structuredMap: Record<string, PhaseMarker> = {
      init: { id: `phase-${index}`, label: "INIT", icon: "INIT", className: "phase-init" },
      scene: { id: `phase-${index}`, label: "SCENE", icon: "SCEN", className: "phase-scene" },
      render: { id: `phase-${index}`, label: "RENDER", icon: "RNDR", className: "phase-render" },
      tts: { id: `phase-${index}`, label: "VOICE", icon: "VOIC", className: "phase-tts" },
      mux: { id: `phase-${index}`, label: "FINAL", icon: "COMP", className: "phase-mux" },
    };

    return structuredMap[phase] ?? null;
  }

  if (hasStructuredPhaseStatus) {
    return null;
  }

  if (event.type !== "log" || typeof event.data !== "string") return null;
  const line = event.data;
  const lower = line.toLowerCase();

  if (line.includes("[PROGRESS]") || line.includes("Phase 1")) {
    return { id: `phase-${index}`, label: "INIT", icon: "INIT", className: "phase-init" };
  }
  if (line.includes("Phase 2") || lower.includes("scene")) {
    return { id: `phase-${index}`, label: "Build Scene", icon: "SCN", className: "phase-scene" };
  }
  if (line.includes("Phase 3") || lower.includes("render")) {
    return { id: `phase-${index}`, label: "Render Video", icon: "RND", className: "phase-render" };
  }
  if (line.includes("Phase 4") || line.includes("[TTS]") || lower.includes("voice")) {
    return { id: `phase-${index}`, label: "Generate Voice", icon: "TTS", className: "phase-tts" };
  }
  if (lower.includes("[mux]") || lower.includes("ffmpeg")) {
    return { id: `phase-${index}`, label: "Mux Final", icon: "MUX", className: "phase-mux" };
  }
  if (line.includes("[SUMMARY]") || lower.includes("completed")) {
    return { id: `phase-${index}`, label: "Complete", icon: "DONE", className: "phase-summary" };
  }

  return null;
}

function PhaseDivider({ marker }: { marker: PhaseMarker }) {
  const colorMap: Record<string, { line: string; text: string; bg: string; border: string }> = {
    "phase-init": { line: "via-cyan-500/30", text: "text-cyan-400", bg: "bg-cyan-500/[0.04]", border: "border-cyan-500/20" },
    "phase-scene": { line: "via-violet-500/30", text: "text-violet-400", bg: "bg-violet-500/[0.04]", border: "border-violet-500/20" },
    "phase-render": { line: "via-green-500/30", text: "text-green-400", bg: "bg-green-500/[0.04]", border: "border-green-500/20" },
    "phase-tts": { line: "via-orange-500/30", text: "text-orange-400", bg: "bg-orange-500/[0.04]", border: "border-orange-500/20" },
    "phase-mux": { line: "via-sky-500/30", text: "text-sky-400", bg: "bg-sky-500/[0.04]", border: "border-sky-500/20" },
    "phase-done": { line: "via-emerald-500/30", text: "text-emerald-400", bg: "bg-emerald-500/[0.04]", border: "border-emerald-500/20" },
  };

  const style = colorMap[marker.className] || colorMap["phase-init"];

  return (
    <div className={`my-4 flex items-center justify-center gap-4`}>
      <div className={`h-[1px] flex-1 bg-gradient-to-r from-transparent ${style.line} to-transparent`}></div>
      <div className={`rounded-full border ${style.border} ${style.bg} px-3 py-0.5 text-[10px] font-mono tracking-[0.2em] font-bold ${style.text}`}>
        {marker.label}
      </div>
      <div className={`h-[1px] flex-1 bg-gradient-to-r from-transparent ${style.line} to-transparent`}></div>
    </div>
  );
}

function classifyLog(line: string): string {
  const lower = line.toLowerCase();
  if (lower.includes("[err]") || lower.includes("error") || lower.includes("failed") || lower.includes("traceback")) {
    return "log-error";
  }
  if (lower.includes("warning") || lower.includes("warn")) {
    return "log-warning";
  }
  if (lower.includes("[ok]") || lower.includes("done") || lower.includes("complete") || lower.includes("success")) {
    return "log-success";
  }
  if (lower.includes("phase") || lower.includes("[progress]") || lower.includes("[summary]")) {
    return "log-step";
  }
  if (!line.trim()) {
    return "log-dim";
  }
  return "log-info";
}

function LogLine({ text, timestamp }: { text: string; timestamp: string }) {
  return (
    <div className="my-0.5 flex flex-col">
      <span className={`${TIMESTAMP_COL_CLASS}`}>{formatEventTime(timestamp)}</span>
      <pre className={`${classifyLog(text)} min-w-0 whitespace-pre-wrap break-all text-left font-mono mt-[2px]`}>
        {text}
      </pre>
    </div>
  );
}

function ToolStartView({ payload, timestamp }: { payload: ToolStartPayload; timestamp: string }) {
  const [expanded, setExpanded] = useState(false);
  const entries = Object.entries(payload.input_summary).slice(0, 4);
  const summaryKeys = getToolSummaryKeys(payload);
  const displayName = getToolDisplayName(payload.name);

  return (
    <div className="my-0.5 flex min-w-0 flex-col border-l-2 border-blue-500/18 py-1 pl-3">
      <span className={`${TIMESTAMP_COL_CLASS} select-none`}>{formatEventTime(timestamp)}</span>
      <button
        type="button"
        onClick={() => setExpanded((current) => !current)}
        className="mt-[2px] flex min-w-0 items-center gap-2 text-left text-[11px] text-blue-200/70 hover:text-blue-200"
      >
        <span
          className="inline-block text-[10px] text-blue-300/70 transition-transform"
          style={{ transform: expanded ? "rotate(90deg)" : "none" }}
        >
          &gt;
        </span>
        <span className="shrink-0 font-semibold" title={payload.name}>
          {displayName}
        </span>
        {summaryKeys.length > 0 && (
          <>
            <span className="shrink-0 text-white/18">/</span>
            <span className="min-w-0 truncate text-white/30">
              {summaryKeys.join(", ")}
            </span>
          </>
        )}
        <span className="shrink-0 text-white/18">/</span>
        <span className="ml-auto shrink-0 font-mono text-[10px] text-blue-500/35">
          {payload.tool_use_id.slice(-8)}
        </span>
      </button>
      <AnimatePresence>
        {expanded && entries.length > 0 && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="mt-2 overflow-hidden"
          >
            <div className="space-y-1.5 rounded-md border border-blue-400/10 bg-blue-500/[0.025] p-2 text-[10px] font-mono">
              {entries.map(([key, value]) => (
                <div key={key} className="min-w-0">
                  <div className="mb-1 text-[9px] uppercase tracking-[0.16em] text-blue-300/45">
                    {key}
                  </div>
                  <pre className="max-h-32 overflow-auto whitespace-pre-wrap break-words rounded bg-black/22 px-2 py-1.5 leading-relaxed text-blue-100/58 custom-scrollbar">
                    {formatToolValue(value)}
                  </pre>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function ToolResultView({ payload, timestamp }: { payload: ToolResultPayload; timestamp: string }) {
  const tone = payload.is_error
    ? "border-red-500/10 bg-red-500/[0.04] text-red-300"
    : "border-green-500/10 bg-green-500/[0.04] text-green-300";

  return (
    <div className={`my-0.5 flex flex-col gap-1 rounded-md border px-3 py-1.5 ${tone}`}>
      <span className={`${TIMESTAMP_COL_CLASS} select-none`}>{formatEventTime(timestamp)}</span>
      <div className="flex items-center gap-2">
        <span className={`rounded-sm px-1.5 py-0.5 font-mono text-[9px] font-bold tracking-wider ${payload.is_error ? "bg-red-500/10 text-red-400" : "bg-green-500/10 text-green-400"}`}>
          {payload.is_error ? "ERR" : "OK"}
        </span>
        {payload.content && (
          <span className="max-w-[280px] truncate text-[11px] text-current/75">
            {payload.content.length > 120 ? `${payload.content.slice(0, 120)}...` : payload.content}
          </span>
        )}
        {payload.duration_ms != null && (
          <span className="ml-auto shrink-0 text-[10px] font-mono text-muted-foreground/40 opacity-70">{payload.duration_ms}ms</span>
        )}
      </div>
    </div>
  );
}

function ThinkingView({ payload, timestamp }: { payload: ThinkingPayload; timestamp: string }) {
  const [expanded, setExpanded] = useState(false);
  const preview = payload.preview ?? `${payload.thinking.slice(0, 97)}...`;

  return (
    <div className="my-0.5 flex flex-col border-l-2 border-purple-500/25 py-1 pl-3">
      <span className={TIMESTAMP_COL_CLASS}>{formatEventTime(timestamp)}</span>
      <div className="min-w-0 flex-1 mt-[2px]">
        <button
          type="button"
          onClick={() => setExpanded((current) => !current)}
          className="flex w-full items-center gap-2 text-left text-[11px] text-purple-300/80 hover:text-purple-300"
        >
          <span className="inline-block transition-transform text-[10px]" style={{ transform: expanded ? "rotate(90deg)" : "none" }}>
            ▶
          </span>
          <span className="rounded-sm bg-purple-500/10 px-1.5 py-0.5 font-mono text-[9px] font-bold tracking-wider text-purple-400">
            THINK
          </span>
          <span className="flex-1 truncate opacity-75">{preview}</span>
        </button>
        <AnimatePresence>
          {expanded && (
            <motion.pre
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="mt-2 overflow-hidden whitespace-pre-wrap break-words text-[11px] leading-relaxed text-purple-200/60 font-sans"
            >
              {payload.thinking}
            </motion.pre>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

function ProgressView({ payload, timestamp }: { payload: ProgressPayload; timestamp: string }) {
  return (
    <div className="my-1 flex w-full max-w-full flex-col gap-1.5 rounded-md border border-white/5 bg-white/[0.02] px-3 py-2 text-[11px] text-muted-foreground/60">
      <span className={`${TIMESTAMP_COL_CLASS} select-none`}>{formatEventTime(timestamp)}</span>
      <div className="flex flex-wrap items-center gap-2 sm:gap-3">
        <span className="rounded-sm bg-white/5 px-1.5 py-0.5 font-mono text-[9px] font-bold tracking-wider text-white/40">
          STEP
        </span>
        <span className="font-medium text-white/50">Turn {payload.turn}</span>
        <span className="flex items-center gap-1">
          <span className="font-mono font-medium text-cyan-400/80">{payload.total_tokens.toLocaleString()}</span>
          <span className="text-[10px] text-white/30">tokens</span>
        </span>
        {payload.estimated_cost_cny != null && (
          <span className="flex items-center gap-1">
            <span className="font-mono font-medium text-emerald-300/75">
              {formatCny(payload.estimated_cost_cny)}
            </span>
            <span className="text-[10px] text-white/30">est.</span>
          </span>
        )}
        <span className="flex items-center gap-1">
          <span className="font-mono font-medium text-blue-400/80">{payload.tool_uses}</span>
          <span className="text-[10px] text-white/30">tools</span>
        </span>
        <span className="ml-auto text-[10px] font-mono text-white/40 opacity-70">{(payload.elapsed_ms / 1000).toFixed(1)}s</span>
      </div>
    </div>
  );
}

function StatusView({
  payload,
  timestamp,
}: {
  payload: { message: string | null; phase: string | null; task_status: string };
  timestamp: string;
}) {
  const isDone = payload.task_status === "completed";
  const isError = payload.task_status === "failed";
  const tone = isDone
    ? "border-emerald-500/20 bg-emerald-500/[0.05] text-emerald-300"
    : isError
      ? "border-red-500/20 bg-red-500/[0.05] text-red-300"
      : "border-cyan-500/20 bg-cyan-500/[0.05] text-cyan-300";

  return (
    <div className={`my-1 flex flex-col rounded-md border px-3 py-2 ${tone}`}>
      <span className={`${TIMESTAMP_COL_CLASS} select-none text-current/40`}>{formatEventTime(timestamp)}</span>
      <div className="flex items-center gap-2.5 text-[11px] font-medium mt-[2px]">
        <span className="flex items-center justify-center w-[18px] h-[18px] rounded-sm bg-current/10 text-[10px] tracking-tighter">
          {isDone ? "✓" : isError ? "✕" : "⟳"}
        </span>
        <span className="uppercase tracking-widest text-[10px] font-bold opacity-80">{payload.task_status}</span>
        {payload.phase && (
          <span className="rounded-full border border-current/15 px-2 py-0.5 text-[9px] font-mono uppercase tracking-widest text-current/80">
            {payload.phase}
          </span>
        )}
      </div>
      {payload.message && <p className="mt-2 text-[11px] leading-relaxed text-current/75 break-words">{payload.message}</p>}
    </div>
  );
}

function EventRenderer({ event }: { event: SSEEvent }) {
  if (isToolStart(event)) {
    return <ToolStartView payload={event.data} timestamp={event.timestamp} />;
  }
  if (isToolResult(event)) {
    return <ToolResultView payload={event.data} timestamp={event.timestamp} />;
  }
  if (isThinking(event)) {
    return <ThinkingView payload={event.data} timestamp={event.timestamp} />;
  }
  if (isProgress(event)) {
    return <ProgressView payload={event.data} timestamp={event.timestamp} />;
  }
  if (isStatusPayload(event)) {
    return <StatusView payload={event.data} timestamp={event.timestamp} />;
  }
  if (typeof event.data === "string") {
    return <LogLine text={event.data} timestamp={event.timestamp} />;
  }
  return <LogLine text={JSON.stringify(event.data)} timestamp={event.timestamp} />;
}

export function LogViewer({ events, isRunning, taskStatus }: LogViewerProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (bottomRef.current) {
      const container = bottomRef.current.parentElement;
      if (container && isRunning) {
        container.scrollTop = container.scrollHeight;
      }
    }
  }, [events, isRunning]);

  const phaseMarkers = useMemo(() => {
    const hasStructuredPhaseStatus = !!getLatestStructuredStatus(events)?.phase;
    const markers: { index: number; marker: PhaseMarker }[] = [];
    events.forEach((event, index) => {
      const marker = detectPhase(event, index, hasStructuredPhaseStatus);
      if (marker) {
        markers.push({ index, marker });
      }
    });
    return markers;
  }, [events]);

  const phaseIndexSet = useMemo(() => new Set(phaseMarkers.map((item) => item.index)), [phaseMarkers]);
  const phaseMap = useMemo(() => new Map(phaseMarkers.map((item) => [item.index, item.marker])), [phaseMarkers]);

  return (
    <div className="relative overflow-hidden rounded-xl border border-white/10 bg-black/40 shadow-2xl ring-1 ring-white/5 backdrop-blur-xl transition-all duration-300 flex-1 flex flex-col h-full min-h-0">
      <div className="pointer-events-none absolute inset-0 bg-[url('data:image/svg+xml,%3Csvg viewBox=%220 0 200 200%22 xmlns=%22http://www.w3.org/2000/svg%22%3E%3Cfilter id=%22noiseFilter%22%3E%3CfeTurbulence type=%22fractalNoise%22 baseFrequency=%220.85%22 numOctaves=%223%22 stitchTiles=%22stitch%22/%3E%3C/filter%3E%3Crect width=%22100%25%22 height=%22100%25%22 filter=%22url(%23noiseFilter)%22/%3E%3C/svg%3E')] opacity-[0.04] mix-blend-screen" />

      <div className="relative z-10 shrink-0 border-b border-white/[0.05] bg-white/[0.02] px-4 pb-3 pt-3">
        <div className="min-w-0 overflow-hidden opacity-90">
          <PipelineProgress events={events} taskStatus={taskStatus} />
        </div>
      </div>

      {events.length > 0 && <span className="shrink-0"><StatsBar events={events} /></span>}

      <div
        data-log-scroll-container
        className="custom-scrollbar relative z-10 min-h-0 flex-1 overflow-y-auto overscroll-contain bg-transparent p-4 font-mono text-xs leading-5"
      >
        <div className="space-y-0">
          {events.length === 0 && (
            <div className="flex flex-col gap-2 px-1 pt-2 font-mono text-[11px] uppercase tracking-widest text-white/30">
              <span className="log-dim">Awaiting system boot...</span>
              <div className="flex items-center gap-2.5">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-400 opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-cyan-500" />
                </span>
                <span className="animate-pulse text-cyan-500/70">Initializing Claude Agent SDK</span>
              </div>
            </div>
          )}
          {events.map((event, index) => {
            const nodes: ReactNode[] = [];
            if (phaseIndexSet.has(index)) {
              nodes.push(
                <motion.div
                  key={`phase-${index}`}
                  initial={{ opacity: 0, y: 10, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                >
                  <PhaseDivider marker={phaseMap.get(index)!} />
                </motion.div>
              );
            }
            nodes.push(
              <motion.div
                key={`event-${index}`}
                initial={{ opacity: 0, x: -10, filter: "blur(4px)" }}
                animate={{ opacity: 1, x: 0, filter: "blur(0px)" }}
                transition={{ duration: 0.3, ease: "easeOut" }}
                className="will-change-transform"
              >
                <EventRenderer event={event} />
              </motion.div>
            );
            return nodes;
          })}
          {isRunning && <pre className="inline-block animate-pulse text-green-400">_</pre>}
          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  );
}
