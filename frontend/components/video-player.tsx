"use client";

import { Download } from "lucide-react";

interface VideoPlayerProps {
  src: string;
}

export function VideoPlayer({ src }: VideoPlayerProps) {
  return (
    <div className="flex flex-col gap-3 group relative">
      <div className="relative rounded-xl overflow-hidden border border-white/10 bg-black/40 backdrop-blur-xl shadow-2xl transition-all duration-300 ring-1 ring-white/5">
        {/* 背景光晕 */}
        <div className="absolute inset-0 bg-blue-500/5 blur-[100px] pointer-events-none" />
        
        {/* 顶部指示条 */}
        <div className="absolute top-0 inset-x-0 h-[1px] bg-gradient-to-r from-transparent via-cyan-500/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
        
        <video
          src={src}
          controls
          className="w-full bg-black max-h-[480px] block relative z-10"
          preload="metadata"
        />
        <div className="absolute inset-0 pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-300 ring-inset ring-1 ring-cyan-500/20 rounded-xl z-20" />
      </div>

      {/* Action bar */}
      <div className="flex items-center justify-between px-2">
        <a
          href={src}
          download
          className="inline-flex items-center gap-2 text-[11px] font-mono tracking-wide text-cyan-500/70 hover:text-cyan-400 transition-colors uppercase group/btn relative"
        >
          <div className="absolute -inset-1 bg-cyan-500/10 scale-90 opacity-0 group-hover/btn:scale-100 group-hover/btn:opacity-100 transition-all rounded-md" />
          <Download className="h-3.5 w-3.5 relative z-10" />
          <span className="relative z-10">Download</span>
        </a>
        <span className="flex items-center gap-2 text-[10px] uppercase font-mono tracking-widest text-white/30">
          <span className="w-1 h-1 rounded-full bg-white/20 animate-pulse" />
          Fullscreen Supported
        </span>
      </div>
    </div>
  );
}
