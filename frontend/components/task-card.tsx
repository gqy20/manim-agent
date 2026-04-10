import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { Task } from "@/types";
import { Clock, CheckCircle2, XCircle, Loader2 } from "lucide-react";

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
    <Link href={`/tasks/${task.id}`}>
      <Card className="group glass-card rounded-xl p-4 cursor-pointer transition-all duration-300 hover:border-primary/20 hover:shadow-lg hover:shadow-primary/5 hover:-translate-y-0.5">
        <CardContent className="p-0 space-y-3">
          {/* Header row */}
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs text-muted-foreground group-hover:text-foreground/80 transition-colors">
              {task.id}
            </span>
            <Badge variant="outline" className={`text-[10px] font-medium px-2 py-0.5 ${config.color}`}>
              <span className="mr-1">{config.icon}</span>
              {config.label}
            </Badge>
          </div>

          {/* Description */}
          <p className="text-sm text-foreground/80 line-clamp-2 leading-relaxed">
            {task.user_text}
          </p>

          {/* Footer */}
          <div className="flex items-center justify-between pt-1">
            <span className="text-[11px] text-muted-foreground/60">
              {new Date(task.created_at).toLocaleDateString("zh-CN", {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
            <span className="text-[10px] text-primary/60 opacity-0 group-hover:opacity-100 transition-opacity">
              查看详情 →
            </span>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
