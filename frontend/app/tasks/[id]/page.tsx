"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { LogViewer } from "@/components/log-viewer";
import { VideoPlayer } from "@/components/video-player";
import { Badge } from "@/components/ui/badge";
import { getTask, getVideoUrl } from "@/lib/api";
import { connectTaskEvents } from "@/lib/sse-client";
import type { Task, SSEEvent, TaskStatus } from "@/types";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  running: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
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

    // Replay existing logs if task has them (from store)
    // The SSE endpoint will also replay them

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
      () => {
        // On error, silently handle - logs may still be available via polling fallback
      },
    );

    return cleanup;
  }, [task, taskId]);

  if (loading) {
    return (
      <main className="flex-1 container py-8">
        <p className="text-muted-foreground">Loading task...</p>
      </main>
    );
  }

  if (!task) {
    return (
      <main className="flex-1 container py-8">
        <h1 className="text-xl font-semibold">Task not found</h1>
        <p className="text-muted-foreground mt-2">
          Task ID &quot;{taskId}&quot; does not exist.
        </p>
      </main>
    );
  }

  const isRunning = task.status === "running" || task.status === "pending";
  const showVideo = task.status === "completed" && task.video_path;

  return (
    <main className="flex-1 container py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-semibold">Task: {taskId}</h1>
          <p className="text-sm text-muted-foreground mt-1 line-clamp-1">
            {task.user_text}
          </p>
        </div>
        <Badge variant="secondary" className={STATUS_STYLES[task.status]}>
          {task.status.toUpperCase()}
        </Badge>
      </div>

      {/* Error display */}
      {task.error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <strong>Error:</strong> {task.error}
        </div>
      )}

      {/* Main content grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left: Log viewer */}
        <div className="space-y-2">
          <h2 className="text-sm font-medium text-muted-foreground">Pipeline Logs</h2>
          <LogViewer logs={logs} isRunning={isRunning} />
        </div>

        {/* Right: Video player or placeholder */}
        <div className="space-y-2">
          <h2 className="text-sm font-medium text-muted-foreground">Output</h2>
          {showVideo ? (
            <VideoPlayer src={getVideoUrl(taskId)} />
          ) : (
            <div className="flex items-center justify-center border rounded-lg h-[500px] text-muted-foreground bg-muted/30">
              {isRunning ? (
                <span>Generating video...</span>
              ) : task.status === "failed" ? (
                <span>Generation failed</span>
              ) : (
                <span>No video available yet</span>
              )}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
