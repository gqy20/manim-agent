"use client";

import { useState, useCallback } from "react";
import { Download, AlertTriangle, RefreshCw } from "lucide-react";

interface VideoPlayerProps {
  src: string;
}

type PlayerState = "loading" | "playing" | "error" | "empty";

export function VideoPlayer({ src }: VideoPlayerProps) {
  const [state, setState] = useState<PlayerState>("loading");
  const [errorMsg, setErrorMsg] = useState<string>("");

  const handleError = useCallback((e: React.SyntheticEvent<HTMLVideoElement>) => {
    const video = e.currentTarget;
    let msg = "视频加载失败";
    switch (video.error?.code) {
      case MediaError.MEDIA_ERR_ABORTED:
        msg = "视频加载被中断"; break;
      case MediaError.MEDIA_ERR_NETWORK:
        msg = "网络错误，视频无法下载"; break;
      case MediaError.MEDIA_ERR_DECODE:
        msg = "视频格式不支持或文件损坏"; break;
      case MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED:
        msg = "视频源不可用或格式不受支持"; break;
      default:
        msg = video.error?.message || msg;
    }
    setErrorMsg(msg);
    setState("error");
  }, []);

  const handleRetry = useCallback(() => {
    setState("loading");
    setErrorMsg("");
  }, []);

  return (
    <div className="flex flex-col gap-3 group relative">
      <div className="relative rounded-xl overflow-hidden border border-white/10 bg-black/40 backdrop-blur-xl shadow-2xl transition-all duration-300 ring-1 ring-white/5">
        {/* 背景光晕 */}
        <div className="absolute inset-0 bg-blue-500/5 blur-[100px] pointer-events-none" />

        {/* 顶部指示条 */}
        <div className="absolute top-0 inset-x-0 h-[1px] bg-gradient-to-r from-transparent via-cyan-500/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

        {/* Error State */}
        {state === "error" && (
          <div className="relative z-10 flex flex-col items-center justify-center gap-3 h-[480px] bg-black/60">
            <div className="w-14 h-14 rounded-2xl bg-red-500/10 flex items-center justify-center border border-red-500/20">
              <AlertTriangle className="h-6 w-6 text-red-400/80" />
            </div>
            <div className="text-center space-y-1">
              <p className="text-sm font-medium text-red-400/90">播放失败</p>
              <p className="text-[11px] text-muted-foreground/60 max-w-xs">{errorMsg}</p>
            </div>
            <button
              onClick={handleRetry}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-border/40 text-muted-foreground hover:text-foreground hover:border-border/80 transition-colors"
            >
              <RefreshCw className="h-3 w-3" />
              重试
            </button>
          </div>
        )}

        {/* Loading / Playing State */}
        {(state === "loading" || state === "playing") && (
          <video
            key={state === "loading" ? src : undefined}
            src={src}
            controls
            className="w-full bg-black max-h-[480px] block relative z-10"
            preload="metadata"
            onLoadedData={() => setState("playing")}
            onError={handleError}
            // Hide on error state (our custom UI is shown instead)
            style={state !== "loading" && state !== "playing" ? { display: "none" } : undefined}
          />
        )}

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
