"use client";

import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { LogViewer } from "@/components/log-viewer";
import { VideoPlayer } from "@/components/video-player";
import { PipelineProgress } from "@/components/pipeline-progress";
import { StatusBadge } from "@/components/ui/status-badge";
import { getTask, getVideoUrl } from "@/lib/api";
import { connectTaskEvents } from "@/lib/sse-client";
import type { Task, SSEEvent, TaskStatus } from "@/types";
import {
  ArrowLeft,
  Film,
  Loader2,
  Terminal,
  Play,
  XCircle,
} from "lucide-react";
import Link from "next/link";

/* ── Skeleton for detail ─────────────────────────── */

function DetailSkeleton() {
  return (
    <div className="space-y-6 animate-fade-in-up">
      <div className="flex items-center gap-4">
        <div className="w-20 h-4 skeleton rounded"/>
        <div className="w-32 h-8 skeleton rounded-lg"/>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="glass-card rounded-xl p-6 space-y-3">
          <div className="w-24 h-3.5 skeleton rounded"/>
          <div className="w-full h-[400px] skeleton rounded-lg"/>
        </div>
        <div className="glass-card rounded-xl p-6 space-y-3">
          <div className="w-16 h-3.5 skeleton rounded"/>
          <div className="w-full h-[400px] skeleton rounded-lg flex items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground/20"/>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Page ───────────────────────────────────────── */

export default function TaskDetailPage() {
  const params = useParams();
  const taskId = params.id as string;
  const [task, setTask] = useState<Task | null>(null);
  const [logs, setLogs] = useState<SSEEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const containerRef = useRef<HTMLElement>(null);

  useEffect(() => {
    getTask(taskId)
      .then(setTask)
      .catch(() => setTask(null))
      .finally(() => setLoading(false));
  }, [taskId]);

  // Connect to SSE stream
  useEffect(() => {
    if (!task) return;

    const cleanup = connectTaskEvents(
      taskId,
      (event: SSEEvent) => {
        // 存储所有事件（结构化 + 纯文本）
        setLogs((prev) => [...prev, event]);
        if (event.type === "status" && typeof event.data === "string") {
          setTask((prev) =>
            prev ? { ...prev, status: event.data as TaskStatus } : prev,
          );
        }
      },
      () => {},
    );

    return cleanup;
  }, [task, taskId]);

  // GSAP Entry Animation Orchestration
  useGSAP(() => {
    if (!task || loading || !containerRef.current) return;

    // Kill any previous breathing animation to prevent leaks
    gsap.killTweensOf(".gsap-video-placeholder");

    // We compose a timeline to present the page elements beautifully
    const tl = gsap.timeline({ defaults: { ease: "power3.out" } });

    tl.fromTo(".gsap-header",
      { y: -20, opacity: 0, filter: "blur(5px)" },
      { y: 0, opacity: 1, filter: "blur(0px)", duration: 0.6, stagger: 0.1 }
    )
    .fromTo(".gsap-panel",
      { y: 40, opacity: 0, scale: 0.98 },
      { y: 0, opacity: 1, scale: 1, duration: 0.8, stagger: 0.15, ease: "power4.out" },
      "-=0.3"
    );

    // If the task is running, make the placeholder border breathe/pulse slightly
    if (task.status === "running" || task.status === "pending") {
      gsap.to(".gsap-video-placeholder", {
        boxShadow: "0 0 30px rgba(6, 182, 212, 0.15)",
        borderColor: "rgba(6, 182, 212, 0.3)",
        repeat: -1,
        yoyo: true,
        duration: 2,
        ease: "sine.inOut",
        id: "detail-breathing",  // named for targeted kill
      });
    }

    return () => { tl.kill(); };
  }, [task, loading]);

  if (loading) return (
    <main className="flex-1 container py-8 max-w-6xl">
      <DetailSkeleton />
    </main>
  );

  if (!task) return (
    <main className="flex-1 container py-8 max-w-6xl">
      <div className="glass-card rounded-2xl p-12 text-center space-y-4 max-w-md mx-auto animate-fade-in-up">
        <div className="w-16 h-16 mx-auto rounded-2xl bg-destructive/[0.06] flex items-center justify-center">
          <XCircle className="h-8 w-8 text-destructive/40" />
        </div>
        <div className="space-y-1">
          <h1 className="text-lg font-semibold">任务不存在</h1>
          <p className="text-sm text-muted-foreground">
            任务 &quot;{taskId}&quot; 未找到或已被删除。
          </p>
        </div>
        <Link href="/" className="inline-flex items-center gap-1.5 text-sm text-primary hover:text-primary/80 transition-colors mt-3 group">
          <ArrowLeft className="h-3.5 w-3.5 group-hover:-translate-x-0.5 transition-transform" />
          返回首页
        </Link>
      </div>
    </main>
  );

  const isRunning = task.status === "running" || task.status === "pending";
  const showVideo = task.status === "completed" && task.video_path;

  return (
    <main ref={containerRef} className="flex-1 w-full px-6 md:px-10 py-8 max-w-[1400px] mx-auto space-y-6">
      {/* Header */}
      <div className="gsap-header flex items-start justify-between flex-wrap gap-4">
        <div className="space-y-1.5">
          <Link
            href="/"
            className="gsap-header inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-all duration-200 mb-2 group"
          >
            <ArrowLeft className="h-3 w-3 group-hover:-translate-x-0.5 transition-transform" />
            返回首页
          </Link>
          <div className="gsap-header flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-primary/[0.08] border border-primary/10 text-primary">
              <Film className="h-4.5 w-4.5" />
            </div>
            <div>
              <h1 className="text-lg font-semibold font-mono tracking-tight">{taskId}</h1>
              <p className="text-sm text-muted-foreground line-clamp-1 mt-0.5 max-w-md">
                {task.user_text}
              </p>
            </div>
          </div>
        </div>
        <StatusBadge status={task.status} size="md" className="gsap-header" />
      </div>

      {/* Error display */}
      {task.error && (
        <div className="gsap-header rounded-xl border border-destructive/20 bg-destructive/[0.04] p-4 text-sm text-red-400 glass-card backdrop-blur-sm">
          <strong>错误：</strong>{task.error}
        </div>
      )}

      {/* Pipeline Progress Bar */}
      <PipelineProgress events={logs} taskStatus={task.status} />

      {/* Main content grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left: Log viewer */}
        <div className="gsap-panel gsap-log space-y-2.5 opacity-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-cyan-500/70">
              <Terminal className="h-3.5 w-3.5" />
              <h2 className="text-[10px] font-mono uppercase tracking-widest">Logs</h2>
            </div>
            {logs.length > 0 && (
              <span className="text-[10px] text-cyan-400/50 font-mono bg-cyan-950/20 border border-cyan-500/10 px-2 py-0.5 rounded shadow-inner">{logs.length} EVTS</span>
            )}
          </div>
          <LogViewer events={logs} isRunning={isRunning} />
        </div>

        {/* Right: Video player or placeholder */}
        <div className="gsap-panel gsap-video space-y-2.5 opacity-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-cyan-500/70">
              <Play className="h-3.5 w-3.5" />
              <h2 className="text-[10px] font-mono uppercase tracking-widest">Output Video</h2>
            </div>
          </div>
          {showVideo ? (
            <VideoPlayer src={getVideoUrl(taskId, task.video_path)} />
          ) : (
            <div className="gsap-video-placeholder group flex flex-col items-center justify-center border border-white/5 rounded-xl h-[480px] bg-black/40 backdrop-blur-xl shadow-2xl transition-all duration-300 overflow-hidden relative ring-1 ring-white/5">
              {/* Animated subtle glow */}
              <div className="absolute inset-0 bg-blue-500/5 blur-[100px] pointer-events-none group-hover:bg-cyan-500/10 transition-colors duration-1000" />
              
              {/* Subtle grid background */}
              <svg className="absolute inset-0 w-full h-full opacity-[0.03]" xmlns="http://www.w3.org/2000/svg">
                <defs>
                  <pattern id="detail-grid" width="28" height="28" patternUnits="userSpaceOnUse">
                    <path d="M 28 0 L 0 0 0 28" fill="none" stroke="currentColor" strokeWidth="0.5"/>
                  </pattern>
                </defs>
                <rect width="100%" height="100%" fill="url(#detail-grid)"/>
              </svg>

              <div className="relative z-10 flex flex-col items-center gap-4">
                {isRunning ? (
                  <>
                    <div className="relative">
                      {/* Outer pulse ring */}
                      <div className="absolute -inset-4 rounded-full bg-cyan-500/10 animate-ping" style={{ animationDuration: '3s' }} />
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

      {/* Pipeline Output Summary (completed tasks only) */}
      {task.pipeline_output && (
        <div className="space-y-2.5">
          <div className="flex items-center gap-2">
            <Terminal className="h-3.5 w-3.5 text-muted-foreground/50" />
            <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Pipeline 输出
            </h2>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {task.pipeline_output.duration_seconds != null && (
              <div className="glass-card rounded-lg p-3 text-center space-y-1">
                <span className="text-[10px] text-muted-foreground/50 uppercase tracking-wider">时长</span>
                <span className="text-sm font-mono font-medium tabular-nums">
                  {task.pipeline_output.duration_seconds.toFixed(1)}s
                </span>
              </div>
            )}
            {task.pipeline_output.scene_class && (
              <div className="glass-card rounded-lg p-3 text-center space-y-1">
                <span className="text-[10px] text-muted-foreground/50 uppercase tracking-wider">场景类</span>
                <span className="text-sm font-mono truncate">
                  {task.pipeline_output.scene_class}
                </span>
              </div>
            )}
            {task.pipeline_output.scene_file && (
              <div className="glass-card rounded-lg p-3 text-center space-y-1">
                <span className="text-[10px] text-muted-foreground/50 uppercase tracking-wider">文件</span>
                <span className="text-xs font-mono truncate">
                  {task.pipeline_output.scene_file.split("/").pop()}
                </span>
              </div>
            )}
            {task.pipeline_output.narration && (
              <div className="glass-card rounded-lg p-3 col-span-2 sm:col-span-4 space-y-1">
                <span className="text-[10px] text-muted-foreground/50 uppercase tracking-wider">解说词</span>
                <p className="text-xs text-muted-foreground/70 line-clamp-2 italic">
                  &ldquo;{task.pipeline_output.narration}&rdquo;
                </p>
              </div>
            )}
          </div>
          {task.pipeline_output.source_code && (
            <details className="glass-card rounded-lg overflow-hidden group cursor-pointer">
              <summary className="flex items-center justify-between px-4 py-3 text-xs text-muted-foreground hover:text-foreground transition-colors">
                <span className="font-mono uppercase tracking-wider">Manim 源码</span>
                <span className="opacity-40 group-hover:opacity-100 transition-opacity">&#9660;</span>
              </summary>
              <pre className="max-h-[240px] overflow-auto bg-zinc-950/80 px-4 py-3 text-[11px] leading-relaxed font-mono whitespace-pre-wrap break-all text-zinc-400/80">
                {task.pipeline_output.source_code}
              </pre>
            </details>
          )}
        </div>
      )}
    </main>
  );
}
