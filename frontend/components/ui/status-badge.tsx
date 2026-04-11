import { Badge } from "@/components/ui/badge";
import { STATUS_CONFIG, type StatusConfig } from "@/lib/constants";
import type { TaskStatus } from "@/types";

interface StatusBadgeProps {
  status: TaskStatus;
  /** Override default icon size (default: h-3 w-3) */
  size?: "sm" | "md";
  /** Additional CSS classes */
  className?: string;
}

const SIZE_CLASS: Record<string, string> = {
  sm: "text-[10px] font-medium px-2 py-0.5",
  md: "font-medium flex items-center gap-1.5 px-3 py-1",
};

export function StatusBadge({ status, size = "sm", className }: StatusBadgeProps) {
  const config: StatusConfig = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending;
  return (
    <Badge variant="outline" className={`${SIZE_CLASS[size]} ${config.color} ${className ?? ""}`}>
      {config.icon}
      {config.label}
    </Badge>
  );
}
