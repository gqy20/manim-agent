"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Bug, Check, Copy, Expand, FileCode2, Film, Loader2, Play, Terminal, Trash2, X, XCircle } from "lucide-react";

import { LogViewer } from "@/components/log-viewer";
import { PipelinePhaseCards } from "@/components/pipeline-phase-cards";
import { VideoPlayer } from "@/components/video-player";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import { deleteTask, getTask, getVideoUrl, terminateTask } from "@/lib/api";
import { gsap, useGSAP } from "@/lib/gsap";
import { logger } from "@/lib/logger";
import { usePrefersReducedMotion } from "@/lib/motion";
import { getDisplayPhaseForTask } from "@/lib/pipeline-phase";
import { connectTaskEvents } from "@/lib/sse-client";
import { mergeTaskState } from "@/lib/task-state";
import type { PipelineOutputData, SSEEvent, Task, TaskStatus } from "@/types";
import { isStatusPayload } from "@/types";

type VideoPlaceholderPhase = "init" | "scene" | "render" | "tts" | "mux" | "done";
type TtsTransportMode = "sync" | "async" | null;

const VOICE_LABELS: Record<string, string> = {
  "female-tianmei": "Sweet Female",
  "male-qn-qingse": "Warm Male",
  "female-yujie": "Elegant Female",
};
const PROMPT_DEBUG_ENABLED = process.env.NEXT_PUBLIC_ENABLE_PROMPT_DEBUG !== "0";

const VIDEO_PHASE_META: Record<
  VideoPlaceholderPhase,
  { label: string; detail: string; accent: string }
> = {
  init: {
    label: "SYSTEM LINK",
    detail: "Bootstrapping the agent runtime",
    accent: "from-cyan-500/25 via-sky-500/10 to-transparent",
  },
  scene: {
    label: "SCENE DRAFT",
    detail: "Sketching animation structure and beats",
    accent: "from-violet-500/25 via-cyan-500/10 to-transparent",
  },
  render: {
    label: "FRAME RENDER",
    detail: "Compiling frames into motion",
    accent: "from-emerald-500/20 via-cyan-500/10 to-transparent",
  },
  tts: {
    label: "VOICE SYNTH",
    detail: "Generating narration and timing cues",
    accent: "from-orange-500/20 via-cyan-500/10 to-transparent",
  },
  mux: {
    label: "FINAL PASS",
    detail: "Merging assets into the delivery file",
    accent: "from-sky-500/25 via-cyan-500/10 to-transparent",
  },
  done: {
    label: "DELIVERY READY",
    detail: "Final output has been assembled",
    accent: "from-emerald-500/25 via-cyan-500/10 to-transparent",
  },
};

function formatElapsedRuntime(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return [hours, minutes, seconds].map((value) => String(value).padStart(2, "0")).join(":");
  }

  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function formatCnyCost(value: number): string {
  if (value < 0.01) return `CNY ${value.toFixed(4)}`;
  if (value < 1) return `CNY ${value.toFixed(3)}`;
  return `CNY ${value.toFixed(2)}`;
}

function getElapsedRuntime(createdAt: string, completedAt: string | null, now: number): number {
  const startedAt = new Date(createdAt).getTime();
  if (Number.isNaN(startedAt)) return 0;

  const endedAt = completedAt ? new Date(completedAt).getTime() : now;
  if (Number.isNaN(endedAt)) {
    return Math.max(0, now - startedAt);
  }

  return Math.max(0, endedAt - startedAt);
}

function detectVideoPlaceholderPhase(
  events: SSEEvent[],
  taskStatus: TaskStatus,
): VideoPlaceholderPhase {
  return getDisplayPhaseForTask(events, taskStatus);
}

function detectTtsTransportMode(events: SSEEvent[]): TtsTransportMode {
  for (const event of [...events].reverse()) {
    if (event.type !== "log" || typeof event.data !== "string") continue;
    const line = event.data.toLowerCase();
    if (line.includes("[tts] transport: sync http")) return "sync";
    if (line.includes("[tts] transport: async long-text")) return "async";
  }
  return null;
}

function VideoPipelinePlaceholder({
  isRunning,
  taskStatus,
  events,
  createdAt,
  completedAt,
  errorMessage,
  pipelineOutput,
}: {
  isRunning: boolean;
  taskStatus: TaskStatus;
  events: SSEEvent[];
  createdAt: string;
  completedAt: string | null;
  errorMessage?: string | null;
  pipelineOutput?: PipelineOutputData | null;
}) {
  const phase = useMemo(
    () => detectVideoPlaceholderPhase(events, taskStatus),
    [events, taskStatus],
  );
  const ttsTransportMode = useMemo(() => detectTtsTransportMode(events), [events]);
  const [runtimeNow, setRuntimeNow] = useState(() => Date.now());
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!isRunning) return;

    const timer = window.setInterval(() => {
      setRuntimeNow(Date.now());
    }, 1000);

    return () => window.clearInterval(timer);
  }, [isRunning]);

  const elapsedLabel = useMemo(
    () => formatElapsedRuntime(getElapsedRuntime(createdAt, completedAt, runtimeNow)),
    [completedAt, createdAt, runtimeNow],
  );

  const currentPhase = useMemo(() => {
    if (phase !== "tts") return VIDEO_PHASE_META[phase];

    return {
      ...VIDEO_PHASE_META.tts,
      detail:
        ttsTransportMode === "sync"
          ? "Streaming back a direct HTTP voice render"
          : ttsTransportMode === "async"
            ? "Falling back to the long-text voice pipeline"
            : VIDEO_PHASE_META.tts.detail,
    };
  }, [phase, ttsTransportMode]);

  const hasPipelineOutput = pipelineOutput != null;

  if (taskStatus === "failed") {
    const handleCopy = () => {
      navigator.clipboard.writeText(errorMessage ?? "");
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    };

    if (hasPipelineOutput) {
      return (
        <div className="flex min-h-0 flex-1 flex-col gap-3">
          <div className="shrink-0 rounded-xl border border-red-500/15 bg-red-500/[0.04] p-3">
            <div className="flex items-center justify-between gap-3">
              <div className="flex min-w-0 items-center gap-2.5">
                <XCircle className="h-4 w-4 shrink-0 text-red-400/80" />
                <div className="min-w-0">
                  <div className="text-[10px] font-mono uppercase tracking-widest text-red-300/80">
                    Render Failed
                  </div>
                  {errorMessage && (
                    <p className="mt-1 line-clamp-2 text-[10px] text-red-100/42">
                      {errorMessage}
                    </p>
                  )}
                </div>
              </div>
              {errorMessage && (
                <button
                  onClick={handleCopy}
                  className="flex shrink-0 items-center gap-1.5 rounded-lg border border-white/8 bg-white/[0.04] px-2.5 py-1.5 text-[10px] font-mono text-white/40 transition-all hover:border-cyan-500/25 hover:text-cyan-400 hover:bg-cyan-500/5"
                >
                  {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                  {copied ? "Copied" : "Copy"}
                </button>
              )}
            </div>
          </div>
          <PipelinePhaseCards pipelineOutput={pipelineOutput} />
        </div>
      );
    }

    return (
      <div className="gsap-video-placeholder group relative flex aspect-video w-full flex-col items-center overflow-hidden rounded-xl border border-red-500/15 bg-black/40 shadow-2xl ring-1 ring-red-500/10 backdrop-blur-xl transition-all duration-300 xl:aspect-auto xl:min-h-0 xl:flex-1">
        <div className="absolute inset-0 bg-gradient-to-br from-red-500/10 via-transparent to-transparent" />
        <div className="relative z-10 flex h-full min-h-0 w-full flex-col gap-3 overflow-hidden p-4">
          <div className="flex items-center justify-between shrink-0">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-red-500/20 bg-gradient-to-br from-red-500/10 to-red-950/30 shadow-[0_0_15px_rgba(239,68,68,0.1)]">
                <XCircle className="h-5 w-5 text-red-400/80" />
              </div>
              <div className="flex flex-col">
                <span className="text-[11px] font-mono uppercase tracking-widest text-red-400/90">Render Failed</span>
                <span className="text-[10px] font-mono text-white/30">Pipeline execution error</span>
              </div>
            </div>
            {errorMessage && (
              <button
                onClick={handleCopy}
                className="flex shrink-0 items-center gap-1.5 rounded-lg border border-white/8 bg-white/[0.04] px-2.5 py-1.5 text-[10px] font-mono text-white/40 transition-all hover:border-cyan-500/25 hover:text-cyan-400 hover:bg-cyan-500/5"
              >
                {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                {copied ? "Copied" : "Copy"}
              </button>
            )}
          </div>
          {errorMessage && (
            <pre className="min-h-0 flex-1 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-red-500/10 bg-red-500/[0.03] p-3 font-mono text-[11px] leading-relaxed text-red-300/70 custom-scrollbar">
              {errorMessage}
            </pre>
          )}
        </div>
      </div>
    );
  }

  if (!isRunning) {
    return (
      <div className="gsap-video-placeholder group relative flex aspect-video w-full flex-col items-center justify-center overflow-hidden rounded-xl border border-white/5 bg-black/40 shadow-2xl ring-1 ring-white/5 backdrop-blur-xl transition-all duration-300 xl:aspect-auto xl:min-h-0 xl:flex-1">
        <div className="absolute inset-0 bg-blue-500/5 blur-[100px] transition-colors duration-1000 group-hover:bg-cyan-500/10" />
        <svg className="absolute inset-0 h-full w-full opacity-[0.03]" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="detail-grid-idle" width="28" height="28" patternUnits="userSpaceOnUse">
              <path d="M 28 0 L 0 0 0 28" fill="none" stroke="currentColor" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#detail-grid-idle)" />
        </svg>
        <div className="relative z-10 flex flex-col items-center gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/5 bg-white/5">
            <Film className="h-6 w-6 text-white/20" />
          </div>
          <div className="flex flex-col items-center space-y-1 text-center">
            <span className="text-[11px] font-mono uppercase tracking-widest text-white/30">RESULT SYNCING</span>
            <span className="max-w-[22rem] text-[10px] font-mono text-white/20">
              Waiting for final artifacts to be retrieved.
            </span>
          </div>
        </div>
      </div>
    );
  }

  if (hasPipelineOutput) {
    return <PipelinePhaseCards pipelineOutput={pipelineOutput} />;
  }

  return (
    <div
      data-video-phase={phase}
      className="gsap-video-placeholder group relative flex aspect-video w-full flex-col items-center justify-center overflow-hidden rounded-xl border border-cyan-500/10 bg-black/40 shadow-2xl ring-1 ring-cyan-500/10 backdrop-blur-xl transition-all duration-300 xl:aspect-auto xl:min-h-0 xl:flex-1"
    >
      <div className={`absolute inset-0 bg-gradient-to-br ${currentPhase.accent}`} />
      <div className="video-grid-sweep absolute inset-0" />
      <div className="phase-scanline pointer-events-none absolute inset-y-0 left-0 w-1/3 bg-gradient-to-r from-transparent via-cyan-300/[0.09] to-transparent opacity-0 blur-sm" />
      <svg className="absolute inset-0 h-full w-full opacity-[0.05]" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern id="detail-grid-active" width="28" height="28" patternUnits="userSpaceOnUse">
            <path d="M 28 0 L 0 0 0 28" fill="none" stroke="currentColor" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#detail-grid-active)" />
      </svg>
      <svg
        className="pointer-events-none absolute inset-0 h-full w-full text-cyan-200/70"
        viewBox="0 0 400 260"
        fill="none"
        aria-hidden="true"
      >
        <path className="phase-draft-path" d="M74 168 C118 88 172 88 216 168 S302 198 336 100" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" opacity="0" />
        <path className="phase-draft-path" d="M92 192 L338 192" stroke="currentColor" strokeWidth="0.8" strokeLinecap="round" opacity="0" />
        <path className="phase-draft-path" d="M112 206 L112 58" stroke="currentColor" strokeWidth="0.8" strokeLinecap="round" opacity="0" />
      </svg>
      <div className="video-grid-radar absolute left-1/2 top-1/2 h-[38vmin] w-[38vmin] -translate-x-1/2 -translate-y-1/2 rounded-full" />
      <div className="pointer-events-none absolute left-1/2 top-1/2 flex h-24 w-36 -translate-x-1/2 -translate-y-1/2 items-end justify-center gap-1.5">
        {[0, 1, 2, 3, 4, 5, 6].map((bar) => (
          <span
            key={bar}
            className="phase-wave-bar h-10 w-1 rounded-full bg-orange-300/60 opacity-0 shadow-[0_0_10px_rgba(251,146,60,0.22)]"
            style={{ height: `${18 + (bar % 4) * 7}px` }}
          />
        ))}
      </div>
      <div className="pointer-events-none absolute left-1/2 top-1/2 grid h-28 w-28 -translate-x-1/2 -translate-y-1/2 grid-cols-3 place-items-center">
        {[0, 1, 2, 3, 4, 5, 6, 7, 8].map((node) => (
          <span
            key={node}
            className="phase-assembly-node h-2 w-2 rounded-full border border-sky-200/35 bg-sky-300/25 opacity-0 shadow-[0_0_10px_rgba(125,211,252,0.2)]"
          />
        ))}
      </div>
      <div className="pointer-events-none absolute inset-x-8 top-8 flex justify-between opacity-50">
        <span className="h-3 w-8 rounded-full border border-cyan-500/20" />
        <span className="h-3 w-14 rounded-full border border-cyan-500/15" />
      </div>
      <div className="pointer-events-none absolute inset-x-8 bottom-8 flex justify-between opacity-40">
        <span className="h-3 w-14 rounded-full border border-cyan-500/15" />
        <span className="h-3 w-8 rounded-full border border-cyan-500/20" />
      </div>
      <div className="relative z-10 flex flex-col items-center gap-5">
        <div className={`video-orb video-orb-${phase}`}>
          <div className="video-orb-core" />
          <div className="video-orb-ring video-orb-ring-primary" />
          <div className="video-orb-ring video-orb-ring-secondary" />
          <div className="video-orb-ring video-orb-ring-orbit" />
          <div className="video-orb-pulse" />
        </div>
        <div className="flex flex-col items-center space-y-2 text-center">
          <div className="phase-glyph rounded-full border border-cyan-400/15 bg-cyan-500/5 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.22em] text-cyan-200/80 shadow-[0_0_18px_rgba(34,211,238,0.08)]">
            Run Time {elapsedLabel}
          </div>
          {phase === "tts" && ttsTransportMode && (
            <div className="rounded-full border border-white/8 bg-white/[0.03] px-3 py-1 font-mono text-[9px] uppercase tracking-[0.24em] text-white/55">
              {ttsTransportMode === "sync" ? "Sync TTS" : "Async Fallback"}
            </div>
          )}
          <span className="text-[11px] font-mono uppercase tracking-[0.26em] text-cyan-300 drop-shadow-[0_0_10px_rgba(34,211,238,0.45)]">
            {currentPhase.label}
          </span>
          <span className="max-w-[22rem] text-[10px] font-mono text-white/28">
            {currentPhase.detail}
          </span>
        </div>
      </div>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <div className="skeleton h-4 w-20 rounded" />
        <div className="skeleton h-8 w-32 rounded-lg" />
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="glass-card overflow-hidden rounded-xl p-6">
          <div className="skeleton mb-4 h-3.5 w-24 rounded" />
          <div className="relative flex aspect-video w-full items-center justify-center overflow-hidden rounded-lg border border-white/5 bg-black/30">
            <svg className="absolute inset-0 h-full w-full opacity-[0.04]" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <pattern id="skel-grid" width="24" height="24" patternUnits="userSpaceOnUse">
                  <path d="M 24 0 L 0 0 0 24" fill="none" stroke="currentColor" strokeWidth="0.5" />
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill="url(#skel-grid)" />
            </svg>
            <div className="video-orb video-orb-init" style={{ transform: "scale(0.6)" }}>
              <div className="video-orb-core" style={{ inset: "18px" }} />
              <div className="video-orb-ring video-orb-ring-primary" style={{ inset: "4px" }} />
              <div className="video-orb-ring video-orb-ring-secondary" style={{ inset: "-8px" }} />
              <div className="video-orb-pulse" style={{ inset: "-24px" }} />
            </div>
          </div>
        </div>
        <div className="glass-card overflow-hidden rounded-xl p-6">
          <div className="skeleton mb-4 h-3.5 w-16 rounded" />
          <div className="relative flex aspect-video w-full items-center justify-center overflow-hidden rounded-lg border border-white/5 bg-black/30">
            <svg className="absolute inset-0 h-full w-full opacity-[0.04]" xmlns="http://www.w3.org/2000/svg">
              <rect width="100%" height="100%" fill="url(#skel-grid)" />
            </svg>
            <div className="flex flex-col items-center gap-3">
              <span className="font-mono text-[10px] uppercase tracking-[0.26em] text-cyan-300/40">Loading</span>
              <div className="h-px w-16 bg-gradient-to-r from-transparent via-primary/20 to-transparent" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ManimScriptPanel({
  sceneFile,
  sceneClass,
  sourceCode,
  onExpand,
}: {
  sceneFile: string | null;
  sceneClass: string | null;
  sourceCode: string | null;
  onExpand: () => void;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!sourceCode) return;
    try {
      await navigator.clipboard.writeText(sourceCode);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  };

  const hasScript = !!sourceCode;
  const hasMeta = !!sceneFile || !!sceneClass;
  const lines = useMemo(() => (sourceCode ? sourceCode.split(/\r?\n/) : []), [sourceCode]);
  const previewLines = lines.slice(0, 140);
  const fileName = sceneFile?.split(/[\\/]/).pop() ?? "scene.py";

  if (!hasScript && !hasMeta) {
    return null;
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-white/5 bg-white/[0.02]">
      <div className="shrink-0 border-b border-white/5 bg-black/20 p-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2 text-cyan-500/70">
            <FileCode2 className="h-3.5 w-3.5 shrink-0" />
            <div className="min-w-0">
              <h3 className="truncate text-[10px] font-mono uppercase tracking-widest text-cyan-400">manim script</h3>
              <div className="mt-1 flex min-w-0 items-center gap-2 text-[9px] font-mono text-white/28">
                {sceneFile && <span className="truncate">{fileName}</span>}
                {sceneClass && <span className="truncate text-white/36">{sceneClass}</span>}
                {hasScript && <span className="shrink-0">{lines.length} lines</span>}
              </div>
            </div>
          </div>
          {hasScript && (
            <div className="flex shrink-0 items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleCopy}
                className="h-7 border-white/10 bg-white/[0.02] px-2.5 text-[10px] text-white/65 hover:bg-white/[0.05] hover:text-white"
              >
                {copied ? <Check className="mr-1.5 h-3 w-3" /> : <Copy className="mr-1.5 h-3 w-3" />}
                {copied ? "Copied" : "Copy"}
              </Button>
              <Button
                type="button"
                variant="outline"
                size="icon-sm"
                onClick={onExpand}
                className="border-white/10 bg-white/[0.02] text-white/60 hover:bg-cyan-500/[0.08] hover:text-cyan-300"
                aria-label="Open full source"
              >
                <Expand className="h-3.5 w-3.5" />
              </Button>
            </div>
          )}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto bg-black/30 shadow-inner custom-scrollbar">
        {hasScript ? (
          <div className="w-max min-w-full py-3 font-mono text-[11px] leading-[18px] text-left">
            {previewLines.map((line, index) => (
              <div key={index} className="grid grid-cols-[3rem_minmax(0,1fr)] hover:bg-white/[0.025]">
                <span className="sticky left-0 z-10 select-none border-r border-white/[0.04] bg-black/70 pr-2 text-right text-white/18">
                  {index + 1}
                </span>
                <code className="whitespace-pre px-3 text-white/72">{line || " "}</code>
              </div>
            ))}
            {lines.length > previewLines.length && (
              <button
                type="button"
                onClick={onExpand}
                className="ml-12 mt-3 rounded-md border border-cyan-500/15 bg-cyan-500/[0.05] px-3 py-1.5 text-[10px] font-mono uppercase tracking-widest text-cyan-300/70 hover:bg-cyan-500/[0.1]"
              >
                Open full source ({lines.length - previewLines.length} more lines)
              </button>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full p-4">
            <span className="text-[11px] font-mono text-white/30 tracking-widest uppercase">No source code available</span>
          </div>
        )}
      </div>
    </div>
  );
}

function SourceCodeDrawer({
  sceneFile,
  sceneClass,
  sourceCode,
  open,
  onClose,
}: {
  sceneFile: string | null;
  sceneClass: string | null;
  sourceCode: string | null;
  open: boolean;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const lines = useMemo(() => (sourceCode ? sourceCode.split(/\r?\n/) : []), [sourceCode]);
  const fileName = sceneFile?.split(/[\\/]/).pop() ?? "scene.py";

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose, open]);

  const handleCopy = async () => {
    if (!sourceCode) return;
    try {
      await navigator.clipboard.writeText(sourceCode);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[85] flex items-center justify-center bg-black/62 p-3 backdrop-blur-sm sm:p-6">
      <button
        type="button"
        aria-label="Close source code"
        className="absolute inset-0 cursor-default"
        onClick={onClose}
      />
      <section className="relative z-10 flex h-[min(88dvh,920px)] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-white/10 bg-background/96 shadow-2xl ring-1 ring-cyan-500/10">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-400/35 to-transparent" />
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-white/8 bg-white/[0.025] px-5 py-4">
          <div className="min-w-0">
            <div className="text-[10px] font-mono uppercase tracking-[0.22em] text-cyan-400/70">
              Source Code
            </div>
            <div className="mt-1 flex min-w-0 flex-wrap items-center gap-2 font-mono text-sm text-white/70">
              <span className="truncate">{fileName}</span>
              {sceneClass && <span className="text-white/35">{sceneClass}</span>}
              <span className="text-white/28">{lines.length} lines</span>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {sourceCode && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleCopy}
                className="h-7 border-white/10 bg-white/[0.03] px-2.5 text-[10px] text-white/60 hover:bg-white/[0.08] hover:text-white"
              >
                {copied ? <Check className="mr-1.5 h-3 w-3" /> : <Copy className="mr-1.5 h-3 w-3" />}
                {copied ? "Copied" : "Copy"}
              </Button>
            )}
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              onClick={onClose}
              className="border-white/10 bg-white/[0.03] text-white/60 hover:bg-white/[0.08] hover:text-white"
              aria-label="Close source code"
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-auto bg-black/45 custom-scrollbar">
          {sourceCode ? (
            <div className="w-max min-w-full py-4 font-mono text-[12px] leading-5 text-left">
              {lines.map((line, index) => (
                <div key={index} className="grid grid-cols-[4rem_minmax(0,1fr)] hover:bg-white/[0.025]">
                  <span className="sticky left-0 z-10 select-none border-r border-white/[0.04] bg-black/80 pr-3 text-right text-white/20">
                    {index + 1}
                  </span>
                  <code className="whitespace-pre px-4 text-white/78">{line || " "}</code>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex h-full items-center justify-center p-6">
              <span className="text-[11px] font-mono uppercase tracking-widest text-white/30">
                No source code available
              </span>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function PipelineReportModal({
  pipelineOutput,
  taskId,
  open,
  onClose,
}: {
  pipelineOutput: PipelineOutputData | null;
  taskId: string;
  open: boolean;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose, open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[80] flex items-stretch justify-end bg-black/55 backdrop-blur-sm">
      <button
        type="button"
        aria-label="Close report"
        className="absolute inset-0 cursor-default"
        onClick={onClose}
      />
      <aside className="relative z-10 flex h-full w-full max-w-3xl flex-col border-l border-white/10 bg-background/96 shadow-2xl">
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-white/8 px-5 py-4">
          <div className="min-w-0">
            <div className="text-[10px] font-mono uppercase tracking-[0.22em] text-cyan-400/70">
              Pipeline Report
            </div>
            <div className="mt-1 truncate font-mono text-sm text-white/70">{taskId}</div>
          </div>
          <Button
            type="button"
            variant="outline"
            size="icon-sm"
            onClick={onClose}
            className="border-white/10 bg-white/[0.03] text-white/60 hover:bg-white/[0.08] hover:text-white"
            aria-label="Close report"
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto custom-scrollbar p-4">
          <PipelinePhaseCards pipelineOutput={pipelineOutput} variant="embedded" />
        </div>
      </aside>
    </div>
  );
}

export default function TaskDetailClient() {
  const router = useRouter();
  const params = useParams();
  const taskId = params.id as string;
  const [task, setTask] = useState<Task | null>(null);
  const [logs, setLogs] = useState<SSEEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [eventsError, setEventsError] = useState<string | null>(null);
  const [stableVideoSrc, setStableVideoSrc] = useState<string | null>(null);
  const [terminating, setTerminating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);
  const [sourceOpen, setSourceOpen] = useState(false);
  const containerRef = useRef<HTMLElement>(null);
  const refreshInFlightRef = useRef(false);
  const reduceMotion = usePrefersReducedMotion();
  const activePlaceholderPhase = useMemo<VideoPlaceholderPhase>(
    () => (task ? detectVideoPlaceholderPhase(logs, task.status) : "init"),
    [logs, task],
  );

  const [activeTab, setActiveTab] = useState<"logs" | "script">("logs");

  async function refreshTaskSnapshot(currentTaskId: string) {
    if (refreshInFlightRef.current) return;
    refreshInFlightRef.current = true;
    try {
      const latest = await getTask(currentTaskId);
      setTask((prev) => {
        if (!prev || prev.id !== currentTaskId) return latest;
        return mergeTaskState(prev, latest);
      });
      setEventsError(null);
    } catch {
      logger.error("task-detail", "Failed to refresh task snapshot", { taskId: currentTaskId });
    } finally {
      refreshInFlightRef.current = false;
    }
  }

  async function handleTerminateTask() {
    if (!task || terminating) return;
    setTerminating(true);
    try {
      const latest = await terminateTask(task.id);
      setTask((prev) => (prev ? mergeTaskState(prev, latest) : latest));
      setEventsError(null);
    } catch {
      logger.error("task-detail", "Failed to terminate task", { taskId: task.id });
      setEventsError("Failed to terminate task.");
    } finally {
      setTerminating(false);
    }
  }

  async function handleDeleteTask() {
    if (!task || deleting || isRunning) return;
    const confirmed = window.confirm(`Delete task ${task.id}? This removes its saved output and logs.`);
    if (!confirmed) return;

    setDeleting(true);
    try {
      await deleteTask(task.id);
      router.push("/history");
    } catch {
      logger.error("task-detail", "Failed to delete task", { taskId: task.id });
      setEventsError("Failed to delete task.");
      setDeleting(false);
    }
  }

  useEffect(() => {
    setTask(null);
    setLogs([]);
    setEventsError(null);
    setStableVideoSrc(null);

    if (!taskId) {
      setEventsError("Missing taskId in route params.");
      setLoading(false);
      return;
    }

    getTask(taskId)
      .then((data) => setTask(data))
      .catch(() => {
        logger.error("task-detail", "Failed to load task", { taskId });
        setEventsError("Failed to load task details.");
        setTask(null);
      })
      .finally(() => setLoading(false));
  }, [taskId]);

  useEffect(() => {
    if (!task?.video_path) return;

    const nextVideoSrc = getVideoUrl(task.id, task.video_path);
    setStableVideoSrc((prev) => (prev === nextVideoSrc ? prev : nextVideoSrc));
  }, [task?.id, task?.video_path]);

  useEffect(() => {
    if (!task?.id) return;

    const cleanup = connectTaskEvents(
      task.id,
      (event: SSEEvent) => {
        setEventsError(null);
        setLogs((prev) => [...prev, event]);

        if (event.type === "status" && typeof event.data === "string") {
          setTask((prev) =>
            prev && prev.status !== event.data
              ? mergeTaskState(prev, { status: event.data as TaskStatus })
              : prev,
          );
          if (event.data === "completed" || event.data === "failed" || event.data === "stopped") {
            void refreshTaskSnapshot(task.id);
          }
          return;
        }

        if (isStatusPayload(event)) {
          setTask((prev) => {
            if (!prev) return prev;
            return mergeTaskState(prev, {
              status: event.data.task_status,
              error:
                event.data.task_status === "failed"
                  ? event.data.message ?? prev.error
                  : prev.error,
              video_path:
                event.data.video_path !== undefined
                  ? event.data.video_path
                  : prev.video_path,
              pipeline_output:
                event.data.pipeline_output !== undefined
                  ? event.data.pipeline_output
                  : prev.pipeline_output,
            });
          });
          if (
            event.data.task_status === "completed" ||
            event.data.task_status === "failed" ||
            event.data.task_status === "stopped"
          ) {
            void refreshTaskSnapshot(task.id);
          }
        }
      },
      () => {
        logger.error("task-detail", "SSE connection error", { taskId: task.id });
        setEventsError("SSE disconnected. Front-end is retrying; check backend SSE logs.");
      },
      () => {
        void refreshTaskSnapshot(task.id);
      },
    );

    return cleanup;
  }, [task?.id]);

  useEffect(() => {
    const taskStatus = task?.status;
    if (!taskId || !taskStatus) return;
    if (taskStatus !== "running" && taskStatus !== "pending") return;
    if (!eventsError) return;

    const timer = window.setInterval(() => {
      if (typeof document !== "undefined" && document.fullscreenElement) {
        return;
      }
      void refreshTaskSnapshot(taskId);
    }, 4000);

    return () => window.clearInterval(timer);
  }, [eventsError, task?.status, taskId]);

  useGSAP(() => {
    if (!task || loading || !containerRef.current) return;

    const videoPlaceholder = containerRef.current.querySelector(".gsap-video-placeholder");
    if (!videoPlaceholder) return;

    gsap.killTweensOf(videoPlaceholder);
    const orbParts = videoPlaceholder.querySelectorAll(".video-orb-core, .video-orb-ring, .video-orb-pulse");
    const scanline = videoPlaceholder.querySelector(".phase-scanline");
    const draftPaths = videoPlaceholder.querySelectorAll<SVGPathElement>(".phase-draft-path");
    const waveBars = videoPlaceholder.querySelectorAll(".phase-wave-bar");
    const assemblyNodes = videoPlaceholder.querySelectorAll(".phase-assembly-node");
    const phaseGlyph = videoPlaceholder.querySelector(".phase-glyph");
    gsap.killTweensOf(orbParts);
    gsap.killTweensOf([scanline, phaseGlyph, ...draftPaths, ...waveBars, ...assemblyNodes]);

    if (reduceMotion) {
      gsap.set(videoPlaceholder, { clearProps: "borderColor,boxShadow,scale" });
      gsap.set(orbParts, { clearProps: "filter,opacity,scale" });
      gsap.set([scanline, phaseGlyph, ...draftPaths, ...waveBars, ...assemblyNodes], {
        clearProps: "all",
      });
      return;
    }

    if (task.status === "running" || task.status === "pending") {
      const tl = gsap.timeline({ repeat: -1, yoyo: true });
      tl
        .to(videoPlaceholder, {
          borderColor: "rgba(6, 182, 212, 0.3)",
          boxShadow: "0 0 30px rgba(6, 182, 212, 0.15)",
          scale: 1.002,
          duration: 2,
          ease: "sine.inOut",
        }, 0)
        .to(orbParts, {
          filter: "brightness(1.18)",
          opacity: 0.92,
          scale: 1.015,
          duration: 2,
          ease: "sine.inOut",
          stagger: 0.04,
        }, 0);

      if (phaseGlyph) {
        tl.fromTo(
          phaseGlyph,
          { opacity: 0.45, scale: 0.98 },
          { opacity: 0.9, scale: 1.02, duration: 1.2, ease: "sine.inOut" },
          0,
        );
      }

      if (activePlaceholderPhase === "scene" && draftPaths.length > 0) {
        draftPaths.forEach((path) => {
          const length = typeof path.getTotalLength === "function" ? path.getTotalLength() + 8 : 180;
          gsap.set(path, { strokeDasharray: length, strokeDashoffset: length, opacity: 0.2 });
        });
        tl.to(draftPaths, {
          strokeDashoffset: 0,
          opacity: 0.48,
          duration: 1.4,
          ease: "power2.inOut",
          stagger: 0.14,
        }, 0.12);
      }

      if (activePlaceholderPhase === "render" && scanline) {
        gsap.set(scanline, { xPercent: -110, opacity: 0 });
        tl.to(scanline, {
          xPercent: 110,
          opacity: 0.55,
          duration: 1.05,
          ease: "none",
        }, 0);
      }

      if (activePlaceholderPhase === "tts" && waveBars.length > 0) {
        gsap.set(waveBars, { transformOrigin: "50% 100%" });
        tl.fromTo(
          waveBars,
          { scaleY: 0.28, opacity: 0.35 },
          {
            scaleY: 1.35,
            opacity: 0.85,
            duration: 0.48,
            ease: "sine.inOut",
            stagger: { each: 0.06, from: "center" },
          },
          0,
        );
      }

      if ((activePlaceholderPhase === "mux" || activePlaceholderPhase === "done") && assemblyNodes.length > 0) {
        tl.fromTo(
          assemblyNodes,
          { opacity: 0.2, scale: 0.78 },
          {
            opacity: 0.85,
            scale: 1.08,
            duration: 0.8,
            ease: "power2.inOut",
            stagger: { each: 0.08, from: "edges" },
          },
          0,
        );
      }
    } else {
      gsap.to(videoPlaceholder, {
        borderColor: "rgba(255, 255, 255, 0.08)",
        boxShadow: "0 0 0 rgba(6, 182, 212, 0)",
        scale: 1,
        duration: 0.35,
        ease: "power2.out",
      });
    }
  }, { scope: containerRef, dependencies: [task?.status, loading, activePlaceholderPhase, stableVideoSrc, reduceMotion] });

  if (loading) {
    return (
      <main className="container mx-auto max-w-6xl flex-1 px-6 py-8">
        <DetailSkeleton />
      </main>
    );
  }

  if (!task) {
    return (
      <main className="container mx-auto max-w-6xl flex-1 px-6 py-8">
        <div className="glass-card mx-auto max-w-md space-y-4 rounded-2xl p-12 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-destructive/[0.06]">
            <XCircle className="h-8 w-8 text-destructive/40" />
          </div>
          <div className="space-y-1">
            <h1 className="text-lg font-semibold">Task not found</h1>
            <p className="sm text-muted-foreground">
              Task &quot;{taskId}&quot; does not exist or has been removed.
            </p>
          </div>
          <Link
            href="/"
            className="group mt-3 inline-flex items-center gap-1.5 text-sm text-primary transition-colors hover:text-primary/80"
          >
            <ArrowLeft className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5" />
            Back to Home
          </Link>
        </div>
      </main>
    );
  }

  const isRunning = task.status === "running" || task.status === "pending";
  const showVideo = !!stableVideoSrc;
  const hasPipelineReport = task.pipeline_output != null;

  const voiceSummary = task.options.no_tts
    ? "No narration"
    : `${VOICE_LABELS[task.options.voice_id] ?? task.options.voice_id} / ${task.options.model}`;
  const musicSummary = task.options.bgm_enabled ? "BGM on" : "No BGM";
  const pipelineProfile = `${voiceSummary} / ${musicSummary} / Target ${task.options.target_duration_seconds}s`;
  const finalAgentCostCny = task.pipeline_output?.run_cost_cny ?? null;
  const finalAgentTurns = task.pipeline_output?.run_turns ?? null;
  const finalAgentModel =
    task.pipeline_output?.run_pricing_model ?? task.pipeline_output?.run_model_name ?? null;

  return (
    <main
      ref={containerRef}
      className="container mx-auto flex w-full max-w-[1800px] flex-1 flex-col space-y-3 px-4 pb-4 sm:px-6 md:px-10 md:pb-6 xl:h-[var(--app-content-height)] xl:overflow-hidden"
    >
      <div className="gsap-header flex flex-col gap-3 pt-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 flex-1 items-start gap-3">
          <div className="flex-shrink-0 rounded-xl border border-primary/10 bg-primary/[0.07] p-2.5 text-primary shadow-[0_0_10px_rgba(6,182,212,0.1)]">
            <Film className="h-4.5 w-4.5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline gap-3">
              <h1 className="truncate font-mono text-lg font-semibold tracking-tight">{task.id}</h1>
              <span className="shrink-0 font-mono text-[11px] tracking-[0.14em] text-cyan-300/58">
                {pipelineProfile}
              </span>
            </div>
            <p className="mt-1 line-clamp-2 max-w-5xl text-sm leading-relaxed text-muted-foreground/80">
              {task.user_text}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3 lg:justify-end">
          <div className="flex items-center gap-3">
            {isRunning && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => void handleTerminateTask()}
                disabled={terminating}
                className="border-red-500/20 bg-red-500/[0.06] text-red-300 hover:bg-red-500/[0.12] hover:text-red-200"
              >
                {terminating ? (
                  <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <XCircle className="mr-2 h-3.5 w-3.5" />
                )}
                Terminate
              </Button>
            )}
            {!isRunning && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => void handleDeleteTask()}
                disabled={deleting}
                className="border-white/12 bg-white/[0.04] text-white/75 hover:bg-white/[0.08] hover:text-white"
              >
                {deleting ? (
                  <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Trash2 className="mr-2 h-3.5 w-3.5" />
                )}
                Delete
              </Button>
            )}
            {finalAgentCostCny != null && (
              <span
                title="Final estimated Claude Agent SDK cost across all SDK phases"
                className="inline-flex h-7 items-center rounded-full border border-emerald-500/20 bg-emerald-500/[0.07] px-3 font-mono text-[10px] font-semibold uppercase tracking-wider text-emerald-300/90"
              >
                {formatCnyCost(finalAgentCostCny)}
              </span>
            )}
            {finalAgentTurns != null && (
              <span
                title="Final Claude Agent SDK turn count across all SDK phases"
                className="inline-flex h-7 items-center rounded-full border border-cyan-500/18 bg-cyan-500/[0.06] px-3 font-mono text-[10px] font-semibold uppercase tracking-wider text-cyan-300/85"
              >
                Turns {finalAgentTurns.toLocaleString()}
              </span>
            )}
            {finalAgentModel && (
              <span
                title="Claude Agent SDK model used for final token-cost accounting"
                className="inline-flex h-7 max-w-[13rem] items-center rounded-full border border-violet-500/18 bg-violet-500/[0.055] px-3 font-mono text-[10px] font-semibold uppercase tracking-wider text-violet-200/80"
              >
                <span className="truncate">Model {finalAgentModel}</span>
              </span>
            )}
            {PROMPT_DEBUG_ENABLED && (
              <Link href={`/tasks/${task.id}/debug`}>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="border-white/12 bg-white/[0.04] text-white/75 hover:bg-white/[0.08] hover:text-white"
                >
                  <Bug className="mr-2 h-3.5 w-3.5" />
                  Debug
                </Button>
              </Link>
            )}
            <StatusBadge status={task.status} size="md" className="gsap-header flex-shrink-0" />
          </div>
        </div>
      </div>

      {eventsError && (
        <div className="gsap-header glass-card rounded-xl border border-destructive/20 bg-destructive/[0.04] p-4 text-sm text-red-400 backdrop-blur-sm">
          <strong className="font-semibold">Error:</strong> {eventsError}
        </div>
      )}
      <div className="relative mt-2 grid min-h-0 gap-4 xl:flex-1 xl:grid-cols-[300px_minmax(0,1fr)] xl:items-stretch">
        <section
          className="glass-card order-2 z-10 flex min-h-0 flex-col overflow-hidden rounded-xl p-3 xl:order-1"
        >
          <div className="flex shrink-0 flex-col gap-3 border-b border-white/5 pb-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex w-full overflow-x-auto rounded-lg bg-black/40 p-1 sm:w-auto">
              <button 
                onClick={() => setActiveTab("logs")}
                className={`flex min-h-10 flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-[10px] font-mono uppercase tracking-widest transition-all sm:min-h-0 sm:flex-none sm:justify-start sm:py-1.5 ${
                  activeTab === "logs" ? "bg-cyan-500/15 text-cyan-400 shadow-sm" : "text-white/40 hover:text-white/60 hover:bg-white/5"
                }`}
              >
                <Terminal className="h-3.5 w-3.5" />
                Logs
              </button>
              <button 
                onClick={() => setActiveTab("script")}
                className={`flex min-h-10 flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-[10px] font-mono uppercase tracking-widest transition-all sm:min-h-0 sm:flex-none sm:justify-start sm:py-1.5 ${
                  activeTab === "script" ? "bg-cyan-500/15 text-cyan-400 shadow-sm" : "text-white/40 hover:text-white/60 hover:bg-white/5"
                }`}
              >
                <FileCode2 className="h-3.5 w-3.5" />
                Code
              </button>
            </div>
            {activeTab === "logs" && (
              <div className="flex items-center sm:justify-end sm:pr-1">
                {logs.length > 0 && (
                  <span className="whitespace-nowrap rounded border border-cyan-500/10 bg-cyan-500/[0.04] px-2 py-1 font-mono text-[9px] uppercase tracking-wider text-cyan-400/45">
                    {logs.length} events
                  </span>
                )}
              </div>
            )}
          </div>
          
          <div className="mt-3 flex min-h-0 flex-1 flex-col overflow-hidden">
            {activeTab === "logs" ? (
              <div className="flex h-full min-h-0 flex-1 flex-col">
                <LogViewer events={logs} isRunning={isRunning} taskStatus={task.status} />
              </div>
            ) : (
              <div className="h-full min-h-0 flex-1 animate-fade-in-up">
                <ManimScriptPanel
                  sceneFile={task.pipeline_output?.scene_file ?? null}
                  sceneClass={task.pipeline_output?.scene_class ?? null}
                  sourceCode={task.pipeline_output?.source_code ?? null}
                  onExpand={() => setSourceOpen(true)}
                />
              </div>
            )}
          </div>
        </section>

        <section
          className="glass-card order-1 flex min-h-0 w-full flex-col overflow-hidden rounded-xl p-3 xl:order-2"
        >
          <div className="flex shrink-0 items-center justify-between border-b border-white/5 pb-2">
            <div className="flex items-center gap-2 text-cyan-500/58">
              <Play className="h-4 w-4" />
              <h2 className="text-[11px] font-mono uppercase tracking-widest">Output Video</h2>
            </div>
            {hasPipelineReport && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setReportOpen(true)}
                className="h-7 border-white/10 bg-white/[0.03] px-2.5 text-[10px] font-mono uppercase tracking-widest text-white/50 hover:bg-cyan-500/[0.08] hover:text-cyan-300"
              >
                <FileCode2 className="mr-1.5 h-3.5 w-3.5" />
                Report
              </Button>
            )}
          </div>
          <div className="mt-3 flex min-h-0 flex-1 flex-col">
            {showVideo && stableVideoSrc ? (
              <VideoPlayer src={stableVideoSrc} />
            ) : (
              <VideoPipelinePlaceholder
                isRunning={isRunning}
                taskStatus={task.status}
                events={logs}
                createdAt={task.created_at}
                completedAt={task.completed_at}
                errorMessage={task.error}
                pipelineOutput={task.pipeline_output}
              />
            )}
          </div>
        </section>
      </div>
      <PipelineReportModal
        pipelineOutput={task.pipeline_output}
        taskId={task.id}
        open={reportOpen}
        onClose={() => setReportOpen(false)}
      />
      <SourceCodeDrawer
        sceneFile={task.pipeline_output?.scene_file ?? null}
        sceneClass={task.pipeline_output?.scene_class ?? null}
        sourceCode={task.pipeline_output?.source_code ?? null}
        open={sourceOpen}
        onClose={() => setSourceOpen(false)}
      />
    </main>
  );
}
