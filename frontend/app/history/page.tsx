"use client";

import { useEffect, useState } from "react";
import { TaskCard } from "@/components/task-card";
import { listTasks } from "@/lib/api";
import type { Task } from "@/types";
import { Loader2, History, Inbox } from "lucide-react";

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
    <main className="flex-1 container py-10 max-w-6xl space-y-8">
      {/* Page header */}
      <div className="animate-fade-in-up">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 rounded-lg bg-primary/10 text-primary">
            <History className="h-5 w-5" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight">历史记录</h1>
        </div>
        <p className="text-sm text-muted-foreground ml-11">
          过去的动画生成任务
        </p>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="flex items-center justify-center py-16 text-muted-foreground animate-fade-in-up animate-delay-100">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          加载中...
        </div>
      )}

      {/* Empty state */}
      {!loading && tasks.length === 0 && (
        <div className="glass-card rounded-xl p-12 text-center space-y-3 animate-fade-in-up animate-delay-200">
          <Inbox className="h-12 w-12 text-muted-foreground/30 mx-auto" />
          <p className="text-muted-foreground">暂无任务记录</p>
          <a
            href="/"
            className="inline-flex items-center gap-1.5 text-sm text-primary hover:text-primary/80 transition-colors"
          >
            去创建第一个动画 →
          </a>
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
