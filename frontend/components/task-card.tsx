import Link from "next/link";
import type { CSSProperties } from "react";
import { useRef } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import type { Task } from "@/types";
import { Film, ArrowUpRight, Loader2, Trash2 } from "lucide-react";
import { formatTaskTimestamp } from "@/lib/utils";

interface TaskCardProps {
  task: Task;
  deleting?: boolean;
  onDelete?: (task: Task) => void;
}

const TERMINAL_TASK_STATUSES = new Set(["completed", "failed", "stopped"]);

export function TaskCard({ task, deleting = false, onDelete }: TaskCardProps) {
  const divRef = useRef<HTMLDivElement>(null);
  const canDelete = TERMINAL_TASK_STATUSES.has(task.status) && !!onDelete;

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    e.currentTarget.style.setProperty("--spotlight-x", `${e.clientX - rect.left}px`);
    e.currentTarget.style.setProperty("--spotlight-y", `${e.clientY - rect.top}px`);
  };

  return (
    <div
      ref={divRef}
      onMouseMove={handleMouseMove}
      className="group relative h-full [--spotlight-x:50%] [--spotlight-y:50%]"
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
          className="absolute right-3 top-3 z-20 inline-flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-black/45 text-white/35 opacity-0 transition-[opacity,border-color,background-color,color] duration-200 hover:border-red-400/25 hover:bg-red-500/[0.12] hover:text-red-200 focus-visible:opacity-100 group-hover:opacity-100 disabled:cursor-not-allowed disabled:opacity-100"
          aria-label={`Delete task ${task.id}`}
        >
          {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
        </button>
      )}
      <Link href={`/tasks/${task.id}`} className="block h-full">
        <Card
          className="glass-card relative h-full cursor-pointer overflow-hidden rounded-lg p-4 transition-[border-color,box-shadow,transform] duration-300 ease-out
            hover:border-primary/25
            hover:shadow-lg hover:shadow-primary/[0.03]
            hover:-translate-y-0.5
            active:scale-[0.98]
            "
          style={{ transformStyle: "preserve-3d", perspective: "1000px" }}
        >
          {/* Spotlight overlay effect */}
          <div
            className="pointer-events-none absolute -inset-px transition-opacity duration-300 z-0 opacity-0 group-hover:opacity-100"
            style={{
              background:
                "radial-gradient(520px circle at var(--spotlight-x) var(--spotlight-y), rgba(255,255,255,0.045), transparent 42%)",
            } as CSSProperties}
          />

          {/* Subtle top accent line */}
          <div className="absolute top-0 left-4 right-4 h-px bg-gradient-to-r from-transparent via-primary/0 to-transparent transition-colors duration-500 group-hover:via-primary/30" />

          <CardContent className="space-y-3 p-0">
            {/* Header row */}
            <div className="flex items-center justify-between gap-3 pr-9">
              <div className="flex min-w-0 items-center gap-2">
                <div className="flex-shrink-0 rounded-md bg-surface/80 p-1.5 transition-colors duration-300 group-hover:bg-primary/10">
                  <Film className="h-3 w-3 text-muted-foreground/50 transition-colors group-hover:text-primary/60" />
                </div>
                <span className="truncate font-mono text-xs text-muted-foreground transition-colors group-hover:text-foreground/70">
                  {task.id}
                </span>
              </div>
              <StatusBadge status={task.status} />
            </div>

            {/* Description */}
            <p className="line-clamp-2 text-sm leading-relaxed text-foreground/75 transition-colors group-hover:text-foreground/90">
              {task.user_text}
            </p>

            {/* Footer */}
            <div className="flex items-center justify-between pt-1">
              <span className="font-mono text-[11px] text-muted-foreground/50">
                {formatTaskTimestamp(task.created_at)}
              </span>
              <span className="flex -translate-x-2 items-center gap-1 text-[10px] text-primary/45 opacity-0 transition-[opacity,transform] duration-300 group-hover:translate-x-0 group-hover:opacity-100">
                查看
                <ArrowUpRight className="h-2.5 w-2.5" />
              </span>
            </div>
          </CardContent>
        </Card>
      </Link>
    </div>
  );
}
