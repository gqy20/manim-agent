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

  if (loading) {
    return (
      <main className="flex-1 container py-8 max-w-6xl">
        <div className="flex items-center gap-3 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span>加载中...</span>
        </div>
      </main>
    );
  }

  if (!task) {
    return (
      <main className="flex-1 container py-8 max-w-6xl">
        <div className="glass-card rounded-xl p-8 text-center space-y-3">
          <XCircle className="h-10 w-10 text-muted-foreground/40 mx-auto" />
          <h1 className="text-lg font-semibold">任务不存在</h1>
          <p className="text-sm text-muted-foreground">
            任务 &quot;{taskId}&quot; 未找到或已被删除。
          </p>
          <Link href="/" className="inline-flex items-center gap-1.5 text-sm text-primary hover:text-primary/80 transition-colors mt-2">
            <ArrowLeft className="h-3.5 w-3.5" />
            返回首页
          </Link>
        </div>
      </main>
    );
  }

  const isRunning = task.status === "running" || task.status === "pending";
  const showVideo = task.status === "completed" && task.video_path;
  const config = STATUS_CONFIG[task.status] ?? STATUS_CONFIG.pending;

  return (
    <main className="flex-1 container py-8 max-w-6xl space-y-6 animate-fade-in-up">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div className="space-y-1">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors mb-2"
          >
            <ArrowLeft className="h-3 w-3" />
            返回
          </Link>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary/10 text-primary">
              <Film className="h-4 w-4" />
            </div>
            <div>
              <h1 className="text-lg font-semibold font-mono">{taskId}</h1>
              <p className="text-sm text-muted-foreground line-clamp-1 mt-0.5">
                {task.user_text}
              </p>
            </div>
          </div>
        </div>
        <Badge variant="outline" className={`font-medium ${config.color}`}>
          <span className="mr-1.5">{config.icon}</span>
          {config.label}
        </Badge>
      </div>

      {/* Error display */}
      {task.error && (
        <div className="rounded-xl border border-destructive/20 bg-destructive/8 p-4 text-sm text-red-400 glass-card">
          <strong>错误：</strong>{task.error}
        </div>
      )}

      {/* Main content grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left: Log viewer */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">流水线日志</h2>
            {logs.length > 0 && (
              <span className="text-[11px] text-muted-foreground/60 font-mono">{logs.length} 行</span>
            )}
          </div>
          <LogViewer logs={logs} isRunning={isRunning} />
        </div>

        {/* Right: Video player or placeholder */}
        <div className="space-y-2">
          <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">输出</h2>
          {showVideo ? (
            <VideoPlayer src={getVideoUrl(taskId)} />
          ) : (
            <div className="flex flex-col items-center justify-center border border-border/50 rounded-xl h-[480px] text-muted-foreground bg-surface/50 glow-border transition-all duration-300">
              {isRunning ? (
                <div className="flex flex-col items-center gap-3">
                  <div className="relative">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    <div className="absolute inset-0 h-8 w-8 animate-ping opacity-20">
                      <Loader2 className="h-full w-full" />
                    </div>
                  </div>
                  <span className="text-sm">正在生成动画...</span>
                  <span className="text-xs text-muted-foreground/60">请耐心等待，通常需要几分钟</span>
                </div>
              ) : task.status === "failed" ? (
                <div className="flex flex-col items-center gap-2">
                  <XCircle className="h-8 w-8 text-red-400/60" />
                  <span className="text-sm">生成失败</span>
                  <span className="text-xs text-muted-foreground/60">请查看上方日志了解详情</span>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2">
                  <Film className="h-8 w-8 text-muted-foreground/30" />
                  <span className="text-sm">暂无视频</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
