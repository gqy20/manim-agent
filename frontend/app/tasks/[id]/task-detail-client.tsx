"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import Link from "next/link";
import { ArrowLeft, Check, Copy, FileCode2, Film, Loader2, Play, Terminal, XCircle } from "lucide-react";

import { LogViewer } from "@/components/log-viewer";
import { VideoPlayer } from "@/components/video-player";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import { getTask, getVideoUrl } from "@/lib/api";
import { logger } from "@/lib/logger";
import { connectTaskEvents } from "@/lib/sse-client";
import { mergeTaskState } from "@/lib/task-state";
import type { SSEEvent, Task, TaskStatus } from "@/types";
import { isStatusPayload } from "@/types";

type VideoPlaceholderPhase = "init" | "scene" | "render" | "tts" | "mux" | "done";
type TtsTransportMode = "sync" | "async" | null;

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

function getElapsedRuntime(createdAt: string, completedAt: string | null, now: number): number {
  const startedAt = new Date(createdAt).getTime();
  if (Number.isNaN(startedAt)) return 0;

  const endedAt = completedAt ? new Date(completedAt).getTime() : now;
  if (Number.isNaN(endedAt)) {
    return Math.max(0, now - startedAt);
  }

  return Math.max(0, endedAt - startedAt);
}

function detectVideoPlaceholderPhase(events: SSEEvent[]): VideoPlaceholderPhase {
  const latestStatus = [...events]
    .reverse()
    .find((event) => isStatusPayload(event))
    ?.data;

  if (latestStatus?.phase) {
    return latestStatus.phase;
  }

  const logText = events
    .flatMap((event) =>
      event.type === "log" && typeof event.data === "string" ? [event.data.toLowerCase()] : [],
    )
    .join(" ");

  if (!logText) return "init";
  if (logText.includes("[tts]") || logText.includes("voice") || logText.includes("speech")) return "tts";
  if (logText.includes("[mux]") || logText.includes("ffmpeg") || logText.includes("final video")) return "mux";
  if (logText.includes("render") || logText.includes("manim") || logText.includes("phase 2")) return "render";
  if (logText.includes("scene") || logText.includes("generatedscene") || logText.includes("tool")) return "scene";
  return "init";
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
}: {
  isRunning: boolean;
  taskStatus: TaskStatus;
  events: SSEEvent[];
  createdAt: string;
  completedAt: string | null;
}) {
  const phase = useMemo(() => detectVideoPlaceholderPhase(events), [events]);
  const ttsTransportMode = useMemo(() => detectTtsTransportMode(events), [events]);
  const [runtimeNow, setRuntimeNow] = useState(() => Date.now());

  useEffect(() => {
    setRuntimeNow(Date.now());

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

  const phaseMeta: Record<VideoPlaceholderPhase, { label: string; detail: string; accent: string }> = {
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

  const currentPhase = useMemo(() => {
    if (phase !== "tts") return phaseMeta[phase];

    return {
      ...phaseMeta.tts,
      detail:
        ttsTransportMode === "sync"
          ? "Streaming back a direct HTTP voice render"
          : ttsTransportMode === "async"
            ? "Falling back to the long-text voice pipeline"
            : phaseMeta.tts.detail,
    };
  }, [phase, phaseMeta, ttsTransportMode]);

  if (taskStatus === "failed") {
    return (
      <div className="gsap-video-placeholder group relative flex aspect-video w-full flex-col items-center justify-center overflow-hidden rounded-xl border border-white/5 bg-black/40 shadow-2xl ring-1 ring-white/5 backdrop-blur-xl transition-all duration-300">
        <div className="absolute inset-0 bg-gradient-to-br from-red-500/10 via-transparent to-transparent" />
        <div className="relative z-10 flex flex-col items-center gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-red-500/20 bg-gradient-to-br from-red-500/10 to-red-950/30 shadow-[0_0_15px_rgba(239,68,68,0.1)]">
            <XCircle className="h-6 w-6 text-red-400/80" />
          </div>
          <div className="flex flex-col items-center space-y-1 text-center">
            <span className="text-[11px] font-mono uppercase tracking-widest text-red-400/80">Render Failed</span>
            <span className="text-[10px] font-mono text-white/30">CHECK LOGS FOR TRACEBACK</span>
          </div>
        </div>
      </div>
    );
  }

  if (!isRunning) {
    return (
      <div className="gsap-video-placeholder group relative flex aspect-video w-full flex-col items-center justify-center overflow-hidden rounded-xl border border-white/5 bg-black/40 shadow-2xl ring-1 ring-white/5 backdrop-blur-xl transition-all duration-300">
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

  return (
    <div className="gsap-video-placeholder group relative flex aspect-video w-full flex-col items-center justify-center overflow-hidden rounded-xl border border-cyan-500/10 bg-black/40 shadow-2xl ring-1 ring-cyan-500/10 backdrop-blur-xl transition-all duration-300">
      <div className={`absolute inset-0 bg-gradient-to-br ${currentPhase.accent}`} />
      <div className="video-grid-sweep absolute inset-0" />
      <svg className="absolute inset-0 h-full w-full opacity-[0.05]" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern id="detail-grid-active" width="28" height="28" patternUnits="userSpaceOnUse">
            <path d="M 28 0 L 0 0 0 28" fill="none" stroke="currentColor" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#detail-grid-active)" />
      </svg>
      <div className="video-grid-radar absolute left-1/2 top-1/2 h-[38vmin] w-[38vmin] -translate-x-1/2 -translate-y-1/2 rounded-full" />
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
          <div className="rounded-full border border-cyan-400/15 bg-cyan-500/5 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.22em] text-cyan-200/80 shadow-[0_0_18px_rgba(34,211,238,0.08)]">
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
    <div className="animate-fade-in-up space-y-6">
      <div className="flex items-center gap-4">
        <div className="skeleton h-4 w-20 rounded" />
        <div className="skeleton h-8 w-32 rounded-lg" />
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="glass-card space-y-3 rounded-xl p-6">
          <div className="skeleton h-3.5 w-24 rounded" />
          <div className="skeleton h-[400px] w-full rounded-lg" />
        </div>
        <div className="glass-card space-y-3 rounded-xl p-6">
          <div className="skeleton h-3.5 w-16 rounded" />
          <div className="skeleton flex h-[400px] w-full items-center justify-center rounded-lg">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground/20" />
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
}: {
  sceneFile: string | null;
  sceneClass: string | null;
  sourceCode: string | null;
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

  if (!hasScript && !hasMeta) {
    return null;
  }

  return (
    <div className="rounded-xl border border-white/5 bg-white/[0.02] overflow-hidden flex flex-col h-full max-h-[500px]">
      <div className="flex items-center justify-between p-3 border-b border-white/5 bg-black/20 shrink-0">
        <div className="flex items-center gap-2 text-cyan-500/70">
          <FileCode2 className="h-3.5 w-3.5" />
          <h3 className="text-[10px] font-mono uppercase tracking-widest text-cyan-400">manim script</h3>
        </div>
        {hasScript && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleCopy}
            className="border-white/10 bg-white/[0.02] text-white/75 hover:bg-white/[0.05] hover:text-white h-7 px-3 text-xs"
          >
            {copied ? <Check className="h-3 w-3 mr-1" /> : <Copy className="h-3 w-3 mr-1" />}
            {copied ? "Copied" : "Copy"}
          </Button>
        )}
      </div>

      <div className="flex-1 overflow-auto bg-black/30 shadow-inner">
        {hasScript ? (
          <pre className="p-4 font-mono text-[12px] leading-6 text-white/80">
            <code>{sourceCode}</code>
          </pre>
        ) : (
          <div className="flex items-center justify-center h-full p-4">
            <span className="text-[11px] font-mono text-white/30 tracking-widest uppercase">No source code available</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default function TaskDetailClient() {
  const params = useParams();
  const taskId = params.id as string;
  const [task, setTask] = useState<Task | null>(null);
  const [logs, setLogs] = useState<SSEEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [eventsError, setEventsError] = useState<string | null>(null);
  const [stableVideoSrc, setStableVideoSrc] = useState<string | null>(null);
  const containerRef = useRef<HTMLElement>(null);
  const refreshInFlightRef = useRef(false);

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
          if (event.data === "completed" || event.data === "failed") {
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
          if (event.data.task_status === "completed" || event.data.task_status === "failed") {
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

    gsap.killTweensOf(".gsap-video-placeholder");

    if (task.status === "running" || task.status === "pending") {
      gsap.to(".gsap-video-placeholder", {
        borderColor: "rgba(6, 182, 212, 0.3)",
        boxShadow: "0 0 30px rgba(6, 182, 212, 0.15)",
        duration: 2,
        ease: "sine.inOut",
        repeat: -1,
        yoyo: true,
      });
    }
  }, [task, loading]);

  const latestStatusPayload = useMemo(
    () =>
      [...logs]
        .reverse()
        .find((event) => isStatusPayload(event))
        ?.data ?? null,
    [logs],
  );

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
        <div className="glass-card mx-auto max-w-md animate-fade-in-up space-y-4 rounded-2xl p-12 text-center">
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

  const liveBadge = isRunning ? "Live" : task.status === "completed" ? "Synced" : "Stopped";

  return (
    <main ref={containerRef} className="container mx-auto flex-1 w-full max-w-[1800px] flex flex-col space-y-4 px-6 md:px-10">
      <div className="gsap-header flex flex-wrap items-center justify-between gap-4 pt-4 md:pt-6">
        <div className="gsap-header flex items-center gap-3">
          <div className="flex-shrink-0 rounded-xl border border-primary/10 bg-primary/[0.08] p-2.5 text-primary shadow-[0_0_15px_rgba(6,182,212,0.15)]">
            <Film className="h-4.5 w-4.5" />
          </div>
          <div>
            <h1 className="font-mono text-lg font-semibold tracking-tight">{task.id}</h1>
            <p className="mt-0.5 line-clamp-1 max-w-md text-sm text-muted-foreground">{task.user_text}</p>
          </div>
        </div>
        <StatusBadge status={task.status} size="md" className="gsap-header flex-shrink-0" />
      </div>

      {eventsError && (
        <div className="gsap-header glass-card rounded-xl border border-destructive/20 bg-destructive/[0.04] p-4 text-sm text-red-400 backdrop-blur-sm">
          <strong className="font-semibold">Error:</strong> {eventsError}
        </div>
      )}
      {task.error && (
        <div className="gsap-header glass-card rounded-xl border border-destructive/20 bg-destructive/[0.04] p-4 text-sm text-red-400 backdrop-blur-sm">
          <strong>Task Error:</strong> {task.error}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-12 mt-4 relative">
        <div className="flex flex-col space-y-4 lg:col-span-4 z-10 glass-card p-4 rounded-xl lg:sticky lg:top-8 h-[calc(100vh-10rem)]">
          <div className="flex items-center justify-between pb-2 border-b border-white/5 shrink-0">
            <div className="flex bg-black/40 p-1 rounded-lg">
              <button 
                onClick={() => setActiveTab("logs")}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-[10px] font-mono uppercase tracking-widest transition-all ${
                  activeTab === "logs" ? "bg-cyan-500/15 text-cyan-400 shadow-sm" : "text-white/40 hover:text-white/60 hover:bg-white/5"
                }`}
              >
                <Terminal className="h-3.5 w-3.5" />
                Logs
              </button>
              <button 
                onClick={() => setActiveTab("script")}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-[10px] font-mono uppercase tracking-widest transition-all ${
                  activeTab === "script" ? "bg-cyan-500/15 text-cyan-400 shadow-sm" : "text-white/40 hover:text-white/60 hover:bg-white/5"
                }`}
              >
                <FileCode2 className="h-3.5 w-3.5" />
                Source Code
              </button>
            </div>
            {activeTab === "logs" && (
              <div className="flex items-center gap-2 pr-2">
                <span className="font-mono text-[9px] uppercase tracking-widest text-white/35 flex items-center gap-1.5">
                   <div className={`h-1.5 w-1.5 rounded-full ${isRunning ? 'bg-cyan-500 animate-pulse drop-shadow-[0_0_6px_rgba(6,182,212,0.8)]' : task.status === 'completed' ? 'bg-emerald-500 drop-shadow-[0_0_6px_rgba(16,185,129,0.8)]' : 'bg-red-500'}`} />
                   {liveBadge}
                </span>
                {logs.length > 0 && (
                  <span className="rounded bg-cyan-950/30 px-2 py-[2px] font-mono text-[9px] text-cyan-400/50">
                    {logs.length} EVTS
                  </span>
                )}
              </div>
            )}
          </div>
          
          <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
            {activeTab === "logs" ? (
              <div className="flex flex-col space-y-4 h-full mt-4 flex-1 min-h-0">
                <LogViewer events={logs} isRunning={isRunning} taskStatus={task.status} />
              </div>
            ) : (
              <div className="animate-fade-in-up mt-2 flex-1 min-h-0 h-full">
                <ManimScriptPanel
                  sceneFile={task.pipeline_output?.scene_file ?? null}
                  sceneClass={task.pipeline_output?.scene_class ?? null}
                  sourceCode={task.pipeline_output?.source_code ?? null}
                />
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-col space-y-4 lg:col-span-8 lg:sticky lg:top-8 self-start w-full h-[calc(100vh-10rem)]">
          <div className="flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2 text-cyan-500/70">
              <Play className="h-4 w-4" />
              <h2 className="text-[11px] font-mono uppercase tracking-widest">Output Video</h2>
            </div>
          </div>
          {showVideo && stableVideoSrc ? (
            <VideoPlayer src={stableVideoSrc} />
          ) : (
            <VideoPipelinePlaceholder
              isRunning={isRunning}
              taskStatus={task.status}
              events={logs}
              createdAt={task.created_at}
              completedAt={task.completed_at}
            />
          )}

        </div>
      </div>
    </main>
  );
}
