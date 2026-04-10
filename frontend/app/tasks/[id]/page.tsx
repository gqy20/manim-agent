"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { LogViewer } from "@/components/log-viewer";
import { VideoPlayer } from "@/components/video-player";
import { Badge } from "@/components/ui/badge";
import { getTask, getVideoUrl } from "@/lib/api";
import { connectTaskEvents } from "@/lib/sse-client";
import type { Task, SSEEvent, TaskStatus } from "@/types";
import {
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  ArrowLeft,
  Film,
  Terminal,
  Play,
} from "lucide-react";
import Link from "next/link";

const STATUS_CONFIG: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
  pending: {
    color: "bg-yellow-500/15 text-yellow-400 border-yellow-500/20",
    icon: <Clock className="h-3.5 w-3.5" />,
    label: "等待中",
  },
  running: {
    color: "bg-blue-500/15 text-blue-400 border-blue-500/20",
    icon: <Loader2 className="h-3.5 w-3.5 animate-spin" />,
    label: "生成中",
  },
  completed: {
    color: "bg-green-500/15 text-green-400 border-green-500/20",
    icon: <CheckCircle2 className="h-3.5 w-3.5" />,
    label: "已完成",
  },
  failed: {
    color: "bg-red-500/15 text-red-400 border-red-500/20",
    icon: <XCircle className="h-3.5 w-3.5" />,
    label: "失败",
  },
};

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
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

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
        if (event.type === "log") {
          setLogs((prev) => [...prev, event.data]);
        } else if (event.type === "status") {
          setTask((prev) =>
            prev ? { ...prev, status: event.data as TaskStatus } : prev,
          );
        }
      },
      () => {},
    );

    return cleanup;
  }, [task, taskId]);

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
  const config = STATUS_CONFIG[task.status] ?? STATUS_CONFIG.pending;

  return (
    <main className="flex-1 container py-8 max-w-6xl space-y-6 animate-fade-in-up">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div className="space-y-1.5">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-all duration-200 mb-2 group"
          >
            <ArrowLeft className="h-3 w-3 group-hover:-translate-x-0.5 transition-transform" />
            返回首页
          </Link>
          <div className="flex items-center gap-3">
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
        <Badge variant="outline" className={`font-medium ${config.color} px-3 py-1`}>
          <span className="mr-1.5">{config.icon}</span>
          {config.label}
        </Badge>
      </div>

      {/* Error display */}
      {task.error && (
        <div className="rounded-xl border border-destructive/20 bg-destructive/[0.04] p-4 text-sm text-red-400 glass-card backdrop-blur-sm animate-fade-in-up">
          <strong>错误：</strong>{task.error}
        </div>
      )}

      {/* Main content grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left: Log viewer */}
        <div className="space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Terminal className="h-3.5 w-3.5 text-muted-foreground/50" />
              <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">流水线日志</h2>
            </div>
            {logs.length > 0 && (
              <span className="text-[11px] text-muted-foreground/50 font-mono bg-surface/60 px-2 py-0.5 rounded">{logs.length} 行</span>
            )}
          </div>
          <LogViewer logs={logs} isRunning={isRunning} />
        </div>

        {/* Right: Video player or placeholder */}
        <div className="space-y-2.5">
          <div className="flex items-center gap-2">
            <Play className="h-3.5 w-3.5 text-muted-foreground/50" />
            <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">输出视频</h2>
          </div>
          {showVideo ? (
            <VideoPlayer src={getVideoUrl(taskId)} />
          ) : (
            <div className="flex flex-col items-center justify-center border border-border/40 rounded-xl h-[480px] text-muted-foreground bg-surface/30 glow-border transition-all duration-300 overflow-hidden relative">
              {/* Subtle grid background */}
              <svg className="absolute inset-0 w-full h-full opacity-[0.02]" xmlns="http://www.w3.org/2000/svg">
                <defs>
                  <pattern id="detail-grid" width="28" height="28" patternUnits="userSpaceOnUse">
                    <path d="M 28 0 L 0 0 0 28" fill="none" stroke="currentColor" strokeWidth="0.5"/>
                  </pattern>
                </defs>
                <rect width="100%" height="100%" fill="url(#detail-grid)"/>
              </svg>

              <div className="relative z-10 flex flex-col items-center gap-3">
                {isRunning ? (
                  <>
                    <div className="relative">
                      <Loader2 className="h-10 w-10 animate-spin text-primary/60" />
                      <div className="absolute inset-0 h-10 w-10 animate-ping opacity-10">
                        <Loader2 className="h-full w-full text-primary" />
                      </div>
                    </div>
                    <span className="text-sm font-medium text-foreground/70">正在生成动画...</span>
                    <span className="text-xs text-muted-foreground/50">请耐心等待，通常需要几分钟</span>
                  </>
                ) : task.status === "failed" ? (
                  <>
                    <div className="w-14 h-14 rounded-2xl bg-destructive/[0.06] flex items-center justify-center">
                      <XCircle className="h-7 w-7 text-destructive/40" />
                    </div>
                    <span className="text-sm font-medium text-foreground/70">生成失败</span>
                    <span className="text-xs text-muted-foreground/50">请查看上方日志了解详情</span>
                  </>
                ) : (
                  <>
                    <div className="w-14 h-14 rounded-2xl bg-surface flex items-center justify-center">
                      <Film className="h-7 w-7 text-muted-foreground/20" />
                    </div>
                    <span className="text-sm text-muted-foreground/60">暂无视频</span>
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
