"use client";

import { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";

interface LogViewerProps {
  logs: string[];
  isRunning: boolean;
}

function classifyLog(line: string): string {
  const lower = line.toLowerCase();
  if (lower.includes("error") || lower.includes("failed") || lower.includes("exception") || lower.includes("traceback")) return "log-error";
  if (lower.includes("warning") || lower.includes("warn")) return "log-warning";
  if (lower.includes("✓") || lower.includes("done") || lower.includes("complete") || lower.includes("success")) return "log-success";
  if (/^(==|→|▸|●|■|\[.*?\])/.test(line) || lower.includes("step") || lower.includes("stage") || lower.includes("phase")) return "log-step";
  if (line.trim().length === 0) return "log-dim";
  return "log-info";
}

export function LogViewer({ logs, isRunning }: LogViewerProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className="relative rounded-xl overflow-hidden border border-border/50 glow-border transition-all duration-300">
      {/* Terminal header bar */}
      <div className="flex items-center gap-2 px-4 py-2.5 bg-surface-elevated/80 border-b border-border/30">
        <div className="flex gap-1.5">
          <span className="w-3 h-3 rounded-full bg-red-500/70" />
          <span className="w-3 h-3 rounded-full bg-yellow-500/70" />
          <span className="w-3 h-3 rounded-full bg-green-500/70" />
        </div>
        <span className="text-xs text-muted-foreground font-mono ml-1">流水线日志</span>
        {isRunning && (
          <span className="ml-auto flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            <span className="text-xs text-green-400 font-mono">运行中</span>
          </span>
        )}
      </div>

      {/* Log content */}
      <ScrollArea className="h-[480px] w-full bg-zinc-950/90 p-4 font-mono text-xs leading-5">
        <div className="space-y-0.5">
          {logs.length === 0 && (
            <span className="log-dim">等待流水线启动...</span>
          )}
          {logs.map((line, i) => (
            <pre key={i} className={`${classifyLog(line)} whitespace-pre-wrap break-all`}>
              {line}
            </pre>
          ))}
          {isRunning && (
            <pre className="text-green-400 animate-pulse inline-block">&#9608;</pre>
          )}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>
    </div>
  );
}
