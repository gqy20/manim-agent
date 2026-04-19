"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, History, Inbox, Sparkles } from "lucide-react";

import { TaskCard } from "@/components/task-card";
import { deleteTask, listTasks } from "@/lib/api";
import { logger } from "@/lib/logger";
import type { Task } from "@/types";

function TaskCardSkeleton() {
  return (
    <div className="glass-card group relative overflow-hidden rounded-xl p-4">
      <div className="absolute inset-0 opacity-[0.03]" style={{
        backgroundImage: `radial-gradient(circle at 50% 50%, oklch(0.72 0.11 250) 1px, transparent 1px)`,
        backgroundSize: "16px 16px",
      }} />
      <div className="relative flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="skeleton h-7 w-7 rounded-md" />
          <div className="skeleton h-3.5 w-20 rounded" />
        </div>
        <div className="skeleton h-5 w-14 rounded-full" />
      </div>
      <div className="relative mt-3 space-y-1.5">
        <div className="skeleton h-4 w-full rounded" />
        <div className="skeleton h-4 w-3/4 rounded" />
      </div>
      <div className="relative mt-3 flex items-center justify-between">
        <div className="skeleton h-3 w-24 rounded" />
        <div className="skeleton h-3 w-10 rounded" />
      </div>
    </div>
  );
}

export default function HistoryPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingTaskId, setDeletingTaskId] = useState<string | null>(null);

  useEffect(() => {
    listTasks()
      .then((res) => setTasks(res.tasks))
      .catch((err: unknown) =>
        logger.error("history", "Failed to load task list", {
          message: err instanceof Error ? err.message : String(err),
        }),
      )
      .finally(() => setLoading(false));
  }, []);

  async function handleDeleteTask(task: Task) {
    if (deletingTaskId) return;
    const confirmed = window.confirm(`Delete task ${task.id}? This removes its saved output and logs.`);
    if (!confirmed) return;

    setDeletingTaskId(task.id);
    try {
      await deleteTask(task.id);
      setTasks((prev) => prev.filter((item) => item.id !== task.id));
    } catch (err) {
      logger.error("history", "Failed to delete task", {
        taskId: task.id,
        message: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setDeletingTaskId(null);
    }
  }

  return (
    <main className="h-[var(--app-content-height)] overflow-y-auto overscroll-contain">
      <div className="container mx-auto min-h-full max-w-[1400px] space-y-8 px-6 py-10 sm:py-14">
        <div className="">
          <div className="mb-2 flex items-center gap-3">
            <div className="rounded-xl border border-primary/10 bg-primary/[0.08] p-2.5 text-primary">
              <History className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">历史任务</h1>
              <p className="mt-0.5 text-sm text-muted-foreground">查看过去创建的动画任务。</p>
            </div>
          </div>
        </div>

        {loading && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <TaskCardSkeleton key={index} />
            ))}
          </div>
        )}

        {!loading && tasks.length === 0 && (
          <div className="glass-card mx-auto max-w-md space-y-5 rounded-2xl p-16 text-center">
            <div className="relative mx-auto h-20 w-20">
              <div className="absolute inset-0 animate-pulse rounded-2xl bg-primary/[0.04]" />
              <div className="relative flex h-full w-full items-center justify-center">
                <Inbox className="h-10 w-10 text-muted-foreground/25" />
              </div>
            </div>
            <div className="space-y-1.5">
              <p className="text-[15px] font-medium text-foreground/80">暂无任务记录</p>
              <p className="text-sm text-muted-foreground/60">去创建你的第一个数学动画吧。</p>
            </div>
            <Link
              href="/create"
              className="group inline-flex items-center gap-2 rounded-xl border border-primary/15 bg-primary/[0.08] px-5 py-2.5 text-sm text-primary transition-all duration-200 hover:border-primary/25 hover:bg-primary/12"
            >
              <Sparkles className="h-3.5 w-3.5" />
              去创建动画
              <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
            </Link>
          </div>
        )}

        {!loading && tasks.length > 0 && (
          <div className="grid gap-4 pb-8 sm:grid-cols-2 lg:grid-cols-3">
            {tasks.map((task, index) => (
            <div
              key={task.id}
              style={{ animationDelay: `${Math.min(index * 0.06, 0.5)}s` }}
            >
                <TaskCard
                  task={task}
                  deleting={deletingTaskId === task.id}
                  onDelete={handleDeleteTask}
                />
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
