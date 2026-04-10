"use client";

import { useEffect, useState } from "react";
import { TaskCard } from "@/components/task-card";
import { listTasks } from "@/lib/api";
import type { Task } from "@/types";
import { Loader2 } from "lucide-react";

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
    <main className="flex-1 container py-8 space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">History</h1>

      {loading && (
        <div className="flex items-center justify-center py-12 text-muted-foreground">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Loading tasks...
        </div>
      )}

      {!loading && tasks.length === 0 && (
        <p className="text-muted-foreground text-center py-12">
          No tasks yet. Create your first animation!
        </p>
      )}

      {!loading && tasks.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {tasks.map((task) => (
            <TaskCard key={task.id} task={task} />
          ))}
        </div>
      )}
    </main>
  );
}
