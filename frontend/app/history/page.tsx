"use client";

import { useEffect, useState } from "react";
import { TaskCard } from "@/components/task-card";
import { listTasks } from "@/lib/api";
import type { Task } from "@/types";
import { Loader2, History, Inbox, Sparkles, ArrowRight } from "lucide-react";
import Link from "next/link";

/* ── Skeleton ────────────────────────────────────── */

function TaskCardSkeleton() {
  return (
    <div className="glass-card rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md skeleton"/>
          <div className="w-20 h-3.5 skeleton rounded"/>
        </div>
        <div className="w-14 h-5 skeleton rounded-full"/>
      </div>
      <div className="space-y-1.5">
        <div className="w-full h-4 skeleton rounded"/>
        <div className="w-3/4 h-4 skeleton rounded"/>
      </div>
      <div className="flex items-center justify-between pt-1">
        <div className="w-24 h-3 skeleton rounded"/>
        <div className="w-10 h-3 skeleton rounded"/>
      </div>
    </div>
  );
}

/* ── Page ───────────────────────────────────────── */

export default function HistoryPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listTasks()
      .then((res) => setTasks(res.tasks))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="flex-1 container py-10 sm:py-14 max-w-6xl space-y-8">
      {/* Page header */}
      <div className="animate-fade-in-up">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2.5 rounded-xl bg-primary/[0.08] border border-primary/10 text-primary">
            <History className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">历史记录</h1>
            <p className="text-sm text-muted-foreground mt-0.5">过去的动画生成任务</p>
          </div>
        </div>
      </div>

      {/* Loading — skeleton grid */}
      {loading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 animate-fade-in-up animate-delay-100">
          {Array.from({ length: 6 }).map((_, i) => (
            <TaskCardSkeleton key={i} />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && tasks.length === 0 && (
        <div className="glass-card rounded-2xl p-16 text-center space-y-5 animate-fade-in-up animate-delay-200 max-w-md mx-auto">
          <div className="relative w-20 h-20 mx-auto">
            <div className="absolute inset-0 rounded-2xl bg-primary/[0.04] animate-pulse"/>
            <div className="relative flex items-center justify-center w-full h-full">
              <Inbox className="h-10 w-10 text-muted-foreground/25" />
            </div>
          </div>
          <div className="space-y-1.5">
            <p className="text-foreground/80 font-medium text-[15px]">暂无任务记录</p>
            <p className="text-sm text-muted-foreground/60">创建你的第一个数学动画吧</p>
          </div>
          <Link
            href="/"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary/[0.08] border border-primary/15 text-sm text-primary hover:bg-primary/12 hover:border-primary/25 transition-all duration-200 group"
          >
            <Sparkles className="h-3.5 w-3.5" />
            去创建动画
            <ArrowRight className="h-3.5 w-3.5 group-hover:translate-x-0.5 transition-transform"/>
          </Link>
        </div>
      )}

      {/* Task grid */}
      {!loading && tasks.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {tasks.map((task, i) => (
            <div
              key={task.id}
              className="animate-fade-in-up"
              style={{ animationDelay: `${Math.min(i * 0.06, 0.5)}s` }}
            >
              <TaskCard task={task} />
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
