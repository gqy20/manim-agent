"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import Link from "next/link";
import { ArrowLeft, Film, Loader2, Play, Terminal, XCircle } from "lucide-react";

import { LogViewer } from "@/components/log-viewer";
import { VideoPlayer } from "@/components/video-player";
import { PipelineProgress } from "@/components/pipeline-progress";
import { StatusBadge } from "@/components/ui/status-badge";
import { getTask, getVideoUrl } from "@/lib/api";
import { connectTaskEvents } from "@/lib/sse-client";
import type { SSEEvent, Task, TaskStatus } from "@/types";
import { isStatusPayload } from "@/types";

function DetailSkeleton() {
  return (
    <div className="space-y-6 animate-fade-in-up">
      <div className="flex items-center gap-4">
        <div className="w-20 h-4 skeleton rounded" />
        <div className="w-32 h-8 skeleton rounded-lg" />
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="glass-card rounded-xl p-6 space-y-3">
          <div className="w-24 h-3.5 skeleton rounded" />
          <div className="w-full h-[400px] skeleton rounded-lg" />
        </div>
        <div className="glass-card rounded-xl p-6 space-y-3">
          <div className="w-16 h-3.5 skeleton rounded" />
          <div className="w-full h-[400px] skeleton rounded-lg flex items-center justify-center">
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

  useEffect(() => {
    setTask(null);
    setLogs([]);
    setEventsError(null);

    if (!taskId) {
      setEventsError("Missing taskId in route params.");
      setLoading(false);
      return;
    }

    console.debug("[TaskDetail] loading task", taskId);
    getTask(taskId)
      .then((data) => {
        console.debug("[TaskDetail] task loaded", data.id, data.status);
        setTask(data);
      })
      .catch((err) => {
        console.error("[TaskDetail] failed to load task", taskId, err);
        setEventsError("Failed to load task details.");
        setTask(null);
      })
      .finally(() => setLoading(false));
  }, [taskId]);

  useEffect(() => {
    if (!task || !task.id) return;

    console.debug("[TaskDetail] connectTaskEvents", task.id);
    const cleanup = connectTaskEvents(
      task.id,
      (event: SSEEvent) => {
        console.debug("[TaskDetail] SSE event", event.type);
        setLogs((prev) => [...prev, event]);
        if (event.type === "status" && typeof event.data === "string") {
          setTask((prev) =>
            prev ? { ...prev, status: event.data as TaskStatus } : prev,
          );
        } else if (isStatusPayload(event)) {
          setTask((prev) =>
            prev ? { ...prev, status: event.data.task_status } : prev,
          );
        }
      },
      (error) => {
        console.error("[TaskDetail] SSE error", task.id, error);
        setEventsError("SSE disconnected. Front-end is retrying; check backend SSE logs.");
      },
      () => {
        console.debug("[TaskDetail] SSE complete", task.id);
      },
    );

    return cleanup;
  }, [task]);

  // GSAP Entry Animation Orchestration
  useGSAP(() => {
    if (!task || loading || !containerRef.current) return;
    gsap.killTweensOf(".gsap-video-placeholder");
    const tl = gsap.timeline({ defaults: { ease: "power3.out" } });

    tl.fromTo(
      ".gsap-header",
      { y: -20, opacity: 0, filter: "blur(5px)" },
      { y: 0, opacity: 1, filter: "blur(0px)", duration: 0.6, stagger: 0.1 },
    ).fromTo(
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
        boxShadow: "0 0 30px rgba(6, 182, 212, 0.15)",
        borderColor: "rgba(6, 182, 212, 0.3)",
        repeat: -1,
        yoyo: true,
        duration: 2,
        ease: "sine.inOut",
      });
    }

    return () => tl.kill();
  }, [task, loading]);

  if (loading) {
    return (
      <main className="flex-1 container py-8 max-w-6xl">
        <DetailSkeleton />
      </main>
    );
  }

  if (!task) {
    return (
      <main className="flex-1 container py-8 max-w-6xl">
        <div className="glass-card rounded-2xl p-12 text-center space-y-4 max-w-md mx-auto animate-fade-in-up">
          <div className="w-16 h-16 mx-auto rounded-2xl bg-destructive/[0.06] flex items-center justify-center">
            <XCircle className="h-8 w-8 text-destructive/40" />
          </div>
          <div className="space-y-1">
            <h1 className="text-lg font-semibold">Task not found</h1>
            <p className="text-sm text-muted-foreground">
              Task &quot;{taskId}&quot; does not exist or has been removed.
            </p>
          </div>
          <Link href="/" className="inline-flex items-center gap-1.5 text-sm text-primary hover:text-primary/80 transition-colors mt-3 group">
            <ArrowLeft className="h-3.5 w-3.5 group-hover:-translate-x-0.5 transition-transform" />
            Back to Home
          </Link>
        </div>
      </main>
    );
  }

  const isRunning = task.status === "running" || task.status === "pending";
  const showVideo = task.status === "completed" && !!task.video_path;

  return (
    <main ref={containerRef} className="flex-1 w-full px-6 md:px-10 py-8 max-w-[1400px] mx-auto space-y-6">
      <div className="gsap-header flex items-start justify-between flex-wrap gap-4">
        <div className="space-y-1.5">
          <Link
            href="/"
            className="gsap-header inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-all duration-200 mb-2 group"
          >
            <ArrowLeft className="h-3 w-3 group-hover:-translate-x-0.5 transition-transform" />
            Back to Home
          </Link>
          <div className="gsap-header flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-primary/[0.08] border border-primary/10 text-primary">
              <Film className="h-4.5 w-4.5" />
            </div>
            <div>
              <h1 className="text-lg font-semibold font-mono tracking-tight">{task.id}</h1>
              <p className="text-sm text-muted-foreground line-clamp-1 mt-0.5 max-w-md">
                {task.user_text}
              </p>
            </div>
          </div>
        </div>
        <StatusBadge status={task.status} size="md" className="gsap-header" />
      </div>

      {eventsError && (
        <div className="gsap-header rounded-xl border border-destructive/20 bg-destructive/[0.04] p-4 text-sm text-red-400 glass-card backdrop-blur-sm">
          <strong className="font-semibold">Error:</strong> {eventsError}
        </div>
      )}
      {task.error && (
        <div className="gsap-header rounded-xl border border-destructive/20 bg-destructive/[0.04] p-4 text-sm text-red-400 glass-card backdrop-blur-sm">
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
            {logs.length > 0 && (
              <span className="text-[10px] text-cyan-400/50 font-mono bg-cyan-950/20 border border-cyan-500/10 px-2 py-0.5 rounded shadow-inner">
                {logs.length} EVTS
              </span>
            )}
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
            <div className="gsap-video-placeholder group flex flex-col items-center justify-center border border-white/5 rounded-xl h-[480px] bg-black/40 backdrop-blur-xl shadow-2xl transition-all duration-300 overflow-hidden relative ring-1 ring-white/5">
              <div className="absolute inset-0 bg-blue-500/5 blur-[100px] pointer-events-none group-hover:bg-cyan-500/10 transition-colors duration-1000" />
              <svg className="absolute inset-0 w-full h-full opacity-[0.03]" xmlns="http://www.w3.org/2000/svg">
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
                      <Loader2 className="h-10 w-10 animate-spin text-cyan-400 relative z-10" />
                    </div>
                    <div className="flex flex-col items-center text-center space-y-1">
                      <span className="text-[11px] font-mono uppercase tracking-widest text-cyan-400/80">Rendering Animation</span>
                      <span className="text-[10px] font-mono text-white/30">AWAITING OUTPUT FROM ENGINE</span>
                    </div>
                  </>
                ) : task.status === "failed" ? (
                  <>
                    <div className="relative w-14 h-14 rounded-2xl bg-gradient-to-br from-red-500/10 to-red-950/30 flex items-center justify-center border border-red-500/20 shadow-[0_0_15px_rgba(239,68,68,0.1)]">
                      <XCircle className="h-6 w-6 text-red-400/80" />
                    </div>
                    <div className="flex flex-col items-center text-center space-y-1">
                      <span className="text-[11px] font-mono uppercase tracking-widest text-red-400/80">Render Failed</span>
                      <span className="text-[10px] font-mono text-white/30">CHECK LOGS FOR TRACEBACK</span>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="w-14 h-14 rounded-2xl bg-white/5 border border-white/5 flex items-center justify-center">
                      <Film className="h-6 w-6 text-white/20" />
                    </div>
                    <span className="text-[11px] font-mono uppercase tracking-widest text-white/20">NO MEDIA AVAILABLE</span>
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

