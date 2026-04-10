"use client";

import { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";

interface LogViewerProps {
  logs: string[];
  isRunning: boolean;
}

export function LogViewer({ logs, isRunning }: LogViewerProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <ScrollArea className="h-[500px] w-full rounded-md border bg-zinc-950 p-4 font-mono text-sm">
      <div className="space-y-1">
        {logs.length === 0 && (
          <span className="text-zinc-500">Waiting for pipeline to start...</span>
        )}
        {logs.map((line, i) => (
          <pre key={i} className="text-zinc-300 whitespace-pre-wrap break-all text-xs leading-5">
            {line}
          </pre>
        ))}
        {isRunning && (
          <pre className="text-green-400 animate-pulse inline-block">&#9608;</pre>
        )}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}
