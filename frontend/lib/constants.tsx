import { Clock, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import type { TaskStatus } from "@/types";

export interface StatusConfig {
  color: string;
  icon: React.ReactNode;
  label: string;
}

export const STATUS_CONFIG: Record<TaskStatus, StatusConfig> = {
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
