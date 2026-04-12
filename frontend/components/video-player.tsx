"use client";

import { useCallback, useState } from "react";
import type { SyntheticEvent } from "react";
import { AlertTriangle, Download, RefreshCw } from "lucide-react";

interface VideoPlayerProps {
  src: string;
}

type PlayerState = "loading" | "playing" | "error";

export function VideoPlayer({ src }: VideoPlayerProps) {
  const [state, setState] = useState<PlayerState>("loading");
  const [errorMsg, setErrorMsg] = useState("");

  const handleError = useCallback((event: SyntheticEvent<HTMLVideoElement>) => {
    const video = event.currentTarget;
    let msg = "Video failed to load.";

    switch (video.error?.code) {
      case MediaError.MEDIA_ERR_ABORTED:
        msg = "Video loading was interrupted.";
        break;
      case MediaError.MEDIA_ERR_NETWORK:
        msg = "A network error prevented the video from loading.";
        break;
      case MediaError.MEDIA_ERR_DECODE:
        msg = "The video file could not be decoded.";
        break;
      case MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED:
        msg = "This video source is unavailable or unsupported.";
        break;
      default:
        msg = video.error?.message || msg;
        break;
    }

    setErrorMsg(msg);
    setState("error");
  }, []);

  const handleRetry = useCallback(() => {
    setState("loading");
    setErrorMsg("");
  }, []);

  return (
    <div className="group relative flex flex-col gap-3">
      <div className="relative overflow-hidden rounded-xl border border-white/10 bg-black/40 shadow-2xl ring-1 ring-white/5 transition-all duration-300 backdrop-blur-xl">
        <div className="pointer-events-none absolute inset-0 bg-blue-500/5 blur-[100px]" />
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-500/50 to-transparent opacity-0 transition-opacity duration-500 group-hover:opacity-100" />

        {state === "error" && (
          <div className="relative z-10 flex h-[480px] flex-col items-center justify-center gap-3 bg-black/60">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-red-500/20 bg-red-500/10">
              <AlertTriangle className="h-6 w-6 text-red-400/80" />
            </div>
            <div className="space-y-1 text-center">
              <p className="text-sm font-medium text-red-400/90">Playback failed</p>
              <p className="max-w-xs text-[11px] text-muted-foreground/60">{errorMsg}</p>
            </div>
            <button
              type="button"
              onClick={handleRetry}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border/40 px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:border-border/80 hover:text-foreground"
            >
              <RefreshCw className="h-3 w-3" />
              Retry
            </button>
          </div>
        )}

        {(state === "loading" || state === "playing") && (
          <video
            key={state === "loading" ? src : undefined}
            src={src}
            controls
            className="relative z-10 block max-h-[480px] w-full bg-black"
            preload="metadata"
            onLoadedData={() => setState("playing")}
            onError={handleError}
          />
        )}

        <div className="pointer-events-none absolute inset-0 z-20 rounded-xl opacity-0 ring-1 ring-inset ring-cyan-500/20 transition-opacity duration-300 group-hover:opacity-100" />
      </div>

      <div className="flex items-center justify-between px-2">
        <a
          href={src}
          download
          className="group/btn relative inline-flex items-center gap-2 font-mono text-[11px] uppercase tracking-wide text-cyan-500/70 transition-colors hover:text-cyan-400"
        >
          <div className="absolute -inset-1 scale-90 rounded-md bg-cyan-500/10 opacity-0 transition-all group-hover/btn:scale-100 group-hover/btn:opacity-100" />
          <Download className="relative z-10 h-3.5 w-3.5" />
          <span className="relative z-10">Download</span>
        </a>
        <span className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-white/30">
          <span className="h-1 w-1 animate-pulse rounded-full bg-white/20" />
          Fullscreen Supported
        </span>
      </div>
    </div>
  );
}
