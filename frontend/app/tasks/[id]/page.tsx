"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import Link from "next/link";
import { ArrowLeft, Film, Loader2, Play, Terminal, XCircle } from "lucide-react";

import { LogViewer } from "@/components/log-viewer";
import { PipelineProgress } from "@/components/pipeline-progress";
import { VideoPlayer } from "@/components/video-player";
import { StatusBadge } from "@/components/ui/status-badge";
import { getTask, getVideoUrl } from "@/lib/api";
import { logger } from "@/lib/logger";
import { connectTaskEvents } from "@/lib/sse-client";
import type { SSEEvent, Task, TaskStatus } from "@/types";
import { isStatusPayload } from "@/types";

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

export default function TaskDetailPage() {
  const params = useParams();
  const taskId = params.id as string;
  const [task, setTask] = useState<Task | null>(null);
  const [logs, setLogs] = useState<SSEEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [eventsError, setEventsError] = useState<string | null>(null);
  const containerRef = useRef<HTMLElement>(null);
  const refreshInFlightRef = useRef(false);

  async function refreshTaskSnapshot(currentTaskId: string) {
    if (refreshInFlightRef.current) return;
    refreshInFlightRef.current = true;
    try {
      const latest = await getTask(currentTaskId);
      setTask((prev) => {
        if (!prev || prev.id !== currentTaskId) return latest;
        return {
          ...prev,
          ...latest,
          pipeline_output: latest.pipeline_output ?? prev.pipeline_output,
        };
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
    if (!task?.id) return;

    const cleanup = connectTaskEvents(
      task.id,
      (event: SSEEvent) => {
        setEventsError(null);
        setLogs((prev) => [...prev, event]);

        if (event.type === "status" && typeof event.data === "string") {
          setTask((prev) =>
            prev && prev.status !== event.data ? { ...prev, status: event.data as TaskStatus } : prev,
          );
          if (event.data === "completed" || event.data === "failed") {
            void refreshTaskSnapshot(task.id);
          }
          return;
        }

        if (isStatusPayload(event)) {
          setTask((prev) => {
            if (!prev) return prev;
            return {
              ...prev,
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
            };
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

    const timer = window.setInterval(() => {
      void refreshTaskSnapshot(taskId);
    }, 4000);

    return () => window.clearInterval(timer);
  }, [task?.status, taskId]);

  useGSAP(() => {
    if (!task || loading || !containerRef.current) return;

    gsap.killTweensOf(".gsap-video-placeholder");
    const timeline = gsap.timeline({ defaults: { ease: "power3.out" } });

    timeline
      .fromTo(
        ".gsap-header",
        { y: -20, opacity: 0, filter: "blur(5px)" },
        { y: 0, opacity: 1, filter: "blur(0px)", duration: 0.6, stagger: 0.1 },
      )
      .fromTo(
        ".gsap-panel",
        { y: 40, opacity: 0, scale: 0.98 },
        {
          y: 0,
          opacity: 1,
          scale: 1,
          duration: 0.8,
          stagger: 0.15,
          ease: "power4.out",
        },
        "-=0.3",
      );

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

    return () => timeline.kill();
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
      <main className="container max-w-6xl flex-1 py-8">
        <DetailSkeleton />
      </main>
    );
  }

  if (!task) {
    return (
      <main className="container max-w-6xl flex-1 py-8">
        <div className="glass-card mx-auto max-w-md animate-fade-in-up space-y-4 rounded-2xl p-12 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-destructive/[0.06]">
            <XCircle className="h-8 w-8 text-destructive/40" />
          </div>
          <div className="space-y-1">
            <h1 className="text-lg font-semibold">Task not found</h1>
            <p className="text-sm text-muted-foreground">
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
  const showVideo = task.status === "completed" && !!task.video_path;
  const currentPhaseLabel =
    task.status === "completed"
      ? showVideo
        ? "Final video ready"
        : "Syncing final video"
      : task.status === "failed"
        ? "Pipeline failed"
      : latestStatusPayload?.phase === "mux"
      ? "Final mux in progress"
      : latestStatusPayload?.phase
        ? `${latestStatusPayload.phase} in progress`
        : isRunning
          ? "Waiting for first backend event"
          : "Pipeline idle";
  const currentPhaseMessage =
    latestStatusPayload?.message ??
    (task.status === "completed"
      ? "The backend has completed the task. The page is syncing the final video metadata."
      : task.status === "failed"
        ? "The pipeline failed before the final artifact was ready."
        : "The log stream is connected and waiting for the next update.");
  const liveBadge = isRunning ? "Live" : task.status === "completed" ? "Synced" : "Stopped";

  return (
    <main ref={containerRef} className="mx-auto flex-1 w-full max-w-[1400px] space-y-6 px-6 py-8 md:px-10">
      <div className="gsap-header flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1.5">
          <Link
            href="/"
            className="gsap-header group mb-2 inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-all duration-200 hover:text-foreground"
          >
            <ArrowLeft className="h-3 w-3 transition-transform group-hover:-translate-x-0.5" />
            Back to Home
          </Link>
          <div className="gsap-header flex items-center gap-3">
            <div className="rounded-xl border border-primary/10 bg-primary/[0.08] p-2.5 text-primary">
              <Film className="h-4.5 w-4.5" />
            </div>
            <div>
              <h1 className="font-mono text-lg font-semibold tracking-tight">{task.id}</h1>
              <p className="mt-0.5 line-clamp-1 max-w-md text-sm text-muted-foreground">{task.user_text}</p>
            </div>
          </div>
        </div>
        <StatusBadge status={task.status} size="md" className="gsap-header" />
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

      <PipelineProgress events={logs} taskStatus={task.status} />

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="gsap-panel gsap-log space-y-2.5 opacity-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-cyan-500/70">
              <Terminal className="h-3.5 w-3.5" />
              <h2 className="text-[10px] font-mono uppercase tracking-widest">Logs</h2>
            </div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] uppercase tracking-widest text-white/35">{liveBadge}</span>
              {logs.length > 0 && (
                <span className="rounded border border-cyan-500/10 bg-cyan-950/20 px-2 py-0.5 font-mono text-[10px] text-cyan-400/50 shadow-inner">
                  {logs.length} EVTS
                </span>
              )}
            </div>
          </div>
          <div className="rounded-xl border border-white/8 bg-white/[0.03] px-4 py-3">
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1">
                <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-cyan-400/60">Current Stage</p>
                <p className="text-sm text-white/85">{currentPhaseLabel}</p>
                <p className="text-[11px] leading-relaxed text-muted-foreground/65">{currentPhaseMessage}</p>
              </div>
              <div
                className={`mt-1 h-2.5 w-2.5 rounded-full ${
                  isRunning ? "animate-pulse bg-cyan-400" : task.status === "completed" ? "bg-emerald-400" : "bg-red-400/80"
                }`}
              />
            </div>
          </div>
          <LogViewer events={logs} isRunning={isRunning} />
        </div>

        <div className="gsap-panel gsap-video space-y-2.5 opacity-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-cyan-500/70">
              <Play className="h-3.5 w-3.5" />
              <h2 className="text-[10px] font-mono uppercase tracking-widest">Output Video</h2>
            </div>
          </div>
          {showVideo ? (
            <VideoPlayer src={getVideoUrl(task.id, task.video_path)} />
          ) : (
            <div className="gsap-video-placeholder group relative flex h-[480px] flex-col items-center justify-center overflow-hidden rounded-xl border border-white/5 bg-black/40 shadow-2xl ring-1 ring-white/5 backdrop-blur-xl transition-all duration-300">
              <div className="absolute inset-0 bg-blue-500/5 blur-[100px] transition-colors duration-1000 group-hover:bg-cyan-500/10" />
              <svg className="absolute inset-0 h-full w-full opacity-[0.03]" xmlns="http://www.w3.org/2000/svg">
                <defs>
                  <pattern id="detail-grid" width="28" height="28" patternUnits="userSpaceOnUse">
                    <path d="M 28 0 L 0 0 0 28" fill="none" stroke="currentColor" strokeWidth="0.5" />
                  </pattern>
                </defs>
                <rect width="100%" height="100%" fill="url(#detail-grid)" />
              </svg>
              <div className="relative z-10 flex flex-col items-center gap-4">
                {isRunning ? (
                  <>
                    <div className="relative">
                      <div className="absolute -inset-4 rounded-full bg-cyan-500/10 animate-ping" style={{ animationDuration: "3s" }} />
                      <div className="absolute -inset-2 rounded-full bg-blue-500/20 animate-pulse" />
                      <Loader2 className="relative z-10 h-10 w-10 animate-spin text-cyan-400" />
                    </div>
                    <div className="flex flex-col items-center space-y-1 text-center">
                      <span className="text-[11px] font-mono uppercase tracking-widest text-cyan-400/80">
                        {currentPhaseLabel}
                      </span>
                      <span className="max-w-[22rem] text-[10px] font-mono text-white/30">{currentPhaseMessage}</span>
                    </div>
                  </>
                ) : task.status === "failed" ? (
                  <>
                    <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-red-500/20 bg-gradient-to-br from-red-500/10 to-red-950/30 shadow-[0_0_15px_rgba(239,68,68,0.1)]">
                      <XCircle className="h-6 w-6 text-red-400/80" />
                    </div>
                    <div className="flex flex-col items-center space-y-1 text-center">
                      <span className="text-[11px] font-mono uppercase tracking-widest text-red-400/80">Render Failed</span>
                      <span className="text-[10px] font-mono text-white/30">CHECK LOGS FOR TRACEBACK</span>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/5 bg-white/5">
                      <Film className="h-6 w-6 text-white/20" />
                    </div>
                    <div className="flex flex-col items-center space-y-1 text-center">
                      <span className="text-[11px] font-mono uppercase tracking-widest text-white/30">RESULT SYNCING</span>
                      <span className="max-w-[22rem] text-[10px] font-mono text-white/20">
                        {currentPhaseMessage}
                      </span>
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
