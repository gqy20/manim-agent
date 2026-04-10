import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { Task } from "@/types";
import { Clock, CheckCircle2, XCircle, Loader2, Film, ArrowUpRight } from "lucide-react";

const STATUS_CONFIG: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
  pending: {
    color: "bg-yellow-500/15 text-yellow-400 border-yellow-500/20",
    icon: <Clock className="h-3 w-3" />,
    label: "等待中",
  },
  running: {
    color: "bg-blue-500/15 text-blue-400 border-blue-500/20",
    icon: <Loader2 className="h-3 w-3 animate-spin" />,
    label: "生成中",
  },
  completed: {
    color: "bg-green-500/15 text-green-400 border-green-500/20",
    icon: <CheckCircle2 className="h-3 w-3" />,
    label: "已完成",
  },
  failed: {
    color: "bg-red-500/15 text-red-400 border-red-500/20",
    icon: <XCircle className="h-3 w-3" />,
    label: "失败",
  },
};

interface TaskCardProps {
  task: Task;
}

export function TaskCard({ task }: TaskCardProps) {
  const config = STATUS_CONFIG[task.status] ?? STATUS_CONFIG.pending;

  return (
    <Link href={`/tasks/${task.id}`} className="group block">
      <Card
        className="glass-card rounded-xl p-4 cursor-pointer transition-all duration-300 ease-out
          hover:border-primary/25
          hover:shadow-xl hover:shadow-primary/[0.04]
          hover:-translate-y-1
          active:scale-[0.98]
          relative overflow-hidden"
        style={{ transformStyle: "preserve-3d", perspective: "1000px" }}
      >
        {/* Subtle top accent line */}
        <div className="absolute top-0 left-4 right-4 h-[1px] bg-gradient-to-r from-transparent via-primary/0 to-transparent group-hover:via-primary/30 transition-all duration-500"/>

        <CardContent className="p-0 space-y-3">
          {/* Header row */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 min-w-0">
              <div className="p-1.5 rounded-md bg-surface/80 flex-shrink-0 group-hover:bg-primary/10 transition-colors duration-300">
                <Film className="h-3 w-3 text-muted-foreground/50 group-hover:text-primary/60 transition-colors"/>
              </div>
              <span className="font-mono text-xs text-muted-foreground group-hover:text-foreground/70 transition-colors truncate">
                {task.id}
              </span>
            </div>
            <Badge variant="outline" className={`text-[10px] font-medium px-2 py-0.5 ${config.color}`}>
              <span className="mr-1">{config.icon}</span>
              {config.label}
            </Badge>
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
  );
}
