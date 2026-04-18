import { CheckCircle2, Clock, Hand, Loader2, XCircle } from "lucide-react";

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
    label: "Pending",
  },
  running: {
    color: "bg-blue-500/15 text-blue-400 border-blue-500/20",
    icon: <Loader2 className="h-3 w-3 animate-spin" />,
    label: "Running",
  },
  completed: {
    color: "bg-green-500/15 text-green-400 border-green-500/20",
    icon: <CheckCircle2 className="h-3 w-3" />,
    label: "Completed",
  },
  failed: {
    color: "bg-red-500/15 text-red-400 border-red-500/20",
    icon: <XCircle className="h-3 w-3" />,
    label: "Failed",
  },
  stopped: {
    color: "bg-zinc-500/15 text-zinc-300 border-zinc-500/20",
    icon: <Hand className="h-3 w-3" />,
    label: "Stopped",
  },
};
