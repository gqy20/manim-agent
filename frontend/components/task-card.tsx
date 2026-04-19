import Link from "next/link";
import { useRef, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import type { Task } from "@/types";
import { Film, ArrowUpRight, Loader2, Trash2 } from "lucide-react";

interface TaskCardProps {
  task: Task;
  deleting?: boolean;
  onDelete?: (task: Task) => void;
}

const TERMINAL_TASK_STATUSES = new Set(["completed", "failed", "stopped"]);

export function TaskCard({ task, deleting = false, onDelete }: TaskCardProps) {
  const divRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [opacity, setOpacity] = useState(0);
  const canDelete = TERMINAL_TASK_STATUSES.has(task.status) && !!onDelete;

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!divRef.current) return;
    const rect = divRef.current.getBoundingClientRect();
    setPosition({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  return (
    <div
      ref={divRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setOpacity(1)}
      onMouseLeave={() => setOpacity(0)}
      className="group relative h-full"
    >
      {canDelete && (
        <button
          type="button"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onDelete(task);
          }}
          disabled={deleting}
          className="absolute right-3 top-3 z-20 inline-flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-black/45 text-white/35 opacity-0 transition-all duration-200 hover:border-red-400/25 hover:bg-red-500/[0.12] hover:text-red-200 group-hover:opacity-100 disabled:cursor-not-allowed disabled:opacity-100"
          aria-label={`Delete task ${task.id}`}
        >
          {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
        </button>
      )}
      <Link href={`/tasks/${task.id}`} className="block h-full">
        <Card
          className="glass-card rounded-xl p-4 cursor-pointer transition-all duration-300 ease-out
            hover:border-primary/25
            hover:shadow-xl hover:shadow-primary/[0.04]
            hover:-translate-y-1
            active:scale-[0.98]
            relative overflow-hidden h-full"
          style={{ transformStyle: "preserve-3d", perspective: "1000px" }}
        >
          {/* Spotlight overlay effect */}
          <div
            className="pointer-events-none absolute -inset-px transition-opacity duration-300 z-0"
            style={{
              opacity,
              background: `radial-gradient(600px circle at ${position.x}px ${position.y}px, rgba(255,255,255,0.06), transparent 40%)`,
            }}
          />

          {/* Subtle top accent line */}
        <div className="absolute top-0 left-4 right-4 h-[1px] bg-gradient-to-r from-transparent via-primary/0 to-transparent group-hover:via-primary/30 transition-all duration-500"/>

        <CardContent className="p-0 space-y-3">
          {/* Header row */}
          <div className="flex items-center justify-between gap-3 pr-9">
            <div className="flex items-center gap-2 min-w-0">
              <div className="p-1.5 rounded-md bg-surface/80 flex-shrink-0 group-hover:bg-primary/10 transition-colors duration-300">
                <Film className="h-3 w-3 text-muted-foreground/50 group-hover:text-primary/60 transition-colors"/>
              </div>
              <span className="font-mono text-xs text-muted-foreground group-hover:text-foreground/70 transition-colors truncate">
                {task.id}
              </span>
            </div>
            <StatusBadge status={task.status} />
          </div>

          {/* Description */}
          <p className="text-sm text-foreground/75 line-clamp-2 leading-relaxed group-hover:text-foreground/90 transition-colors">
            {task.user_text}
          </p>

          {/* Footer */}
          <div className="flex items-center justify-between pt-1">
            <span className="text-[11px] text-muted-foreground/50 font-mono">
              {new Date(task.created_at).toLocaleDateString("zh-CN", {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
            <span className="flex items-center gap-1 text-[10px] text-primary/40 opacity-0 -translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300">
              查看
              <ArrowUpRight className="h-2.5 w-2.5"/>
            </span>
          </div>
        </CardContent>
      </Card>
      </Link>
    </div>
  );
}
