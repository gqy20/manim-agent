"use client";

import { Download } from "lucide-react";

interface VideoPlayerProps {
  src: string;
}

export function VideoPlayer({ src }: VideoPlayerProps) {
  return (
    <div className="flex flex-col gap-3">
      <div className="relative group rounded-xl overflow-hidden border border-border/50 glow-border transition-all duration-300">
        <video
          src={src}
          controls
          className="w-full bg-black max-h-[480px] block"
          preload="metadata"
        />
        <div className="absolute inset-0 pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-300 ring-1 ring-inset ring-white/5 rounded-xl" />
      </div>

      {/* Action bar */}
      <div className="flex items-center justify-between px-1">
        <a
          href={src}
          download
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-primary transition-colors"
        >
          <Download className="h-3.5 w-3.5" />
          下载视频
        </a>
        <span className="text-xs text-muted-foreground/60">
          支持全屏播放
        </span>
      </div>
    </div>
  );
}
