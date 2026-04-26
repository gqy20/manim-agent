"use client";

import { useMemo } from "react";
import { BookOpen, Target, Users, Clock } from "lucide-react";
import type { PipelineOutputData } from "@/types";

interface PlanBeat {
  id: string;
  title: string;
  visual_goal: string;
  narration_intent: string;
  target_duration_seconds: number | null;
}

interface PlanCardProps {
  pipelineOutput: Pick<
    PipelineOutputData,
    "plan_text" | "mode" | "learning_goal" | "audience" | "beats" | "target_duration_seconds"
  > | null;
}

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "--";
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s > 0 ? `${m}m${s}s` : `${m}m`;
}

export function PlanCard({ pipelineOutput }: PlanCardProps) {
  const beats = useMemo(
    () => (pipelineOutput?.beats?.length ? pipelineOutput.beats : []),
    [pipelineOutput?.beats],
  );

  const totalBeatDuration = useMemo(
    () =>
      beats.reduce((sum, b) => sum + (b.target_duration_seconds ?? 0), 0),
    [beats],
  );

  if (!pipelineOutput || (!pipelineOutput.plan_text && beats.length === 0)) {
    return null;
  }

  return (
    <div className="gsap-plan-card group relative flex aspect-video w-full flex-col overflow-hidden rounded-xl border border-cyan-500/10 bg-black/50 shadow-2xl ring-1 ring-cyan-500/8 backdrop-blur-xl">
      {/* Header gradient */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-400/30 to-transparent" />

      {/* Scrollable content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Meta bar */}
        <div className="flex shrink-0 items-center gap-4 border-b border-white/5 px-5 py-3">
          {pipelineOutput.mode && (
            <span className="rounded-full border border-violet-400/20 bg-violet-500/8 px-2.5 py-0.5 text-[9px] font-mono uppercase tracking-wider text-violet-300/80">
              {pipelineOutput.mode}
            </span>
          )}
          {pipelineOutput.target_duration_seconds != null && (
            <span className="flex items-center gap-1 text-[9px] font-mono text-white/35">
              <Clock className="h-3 w-3" />
              Target {formatDuration(pipelineOutput.target_duration_seconds)}
            </span>
          )}
          {totalBeatDuration > 0 && (
            <span className="text-[9px] font-mono text-white/25">
              Beats sum {formatDuration(totalBeatDuration)}
            </span>
          )}
        </div>

        {/* Goal & Audience row */}
        {(pipelineOutput.learning_goal || pipelineOutput.audience) && (
          <div className="flex shrink-0 gap-4 border-b border-white/4 px-5 py-2.5">
            {pipelineOutput.learning_goal && (
              <div className="flex items-start gap-1.5 min-w-0 flex-1">
                <Target className="mt-0.5 h-3.5 w-3.3 shrink-0 text-emerald-400/60" />
                <span className="truncate text-[10px] leading-relaxed text-white/50">
                  {pipelineOutput.learning_goal}
                </span>
              </div>
            )}
            {pipelineOutput.audience && (
              <div className="flex items-start gap-1.5 min-w-0 flex-1">
                <Users className="mt-0.5 h-3.5 w-3.5 shrink-0 text-sky-400/60" />
                <span className="truncate text-[10px] leading-relaxed text-white/45">
                  {pipelineOutput.audience}
                </span>
              </div>
            )}
          </div>
        )}

        {/* Plan text snippet */}
        {pipelineOutput.plan_text && (
          <div className="shrink-0 border-b border-white/4 px-5 py-2">
            <div className="flex items-start gap-1.5">
              <BookOpen className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400/50" />
              <p className="line-clamp-2 text-[10px] leading-relaxed text-white/40">
                {pipelineOutput.plan_text}
              </p>
            </div>
          </div>
        )}

        {/* Beat timeline */}
        {beats.length > 0 && (
          <div className="flex-1 overflow-y-auto custom-scrollbar px-5 py-3">
            <div className="text-[9px] font-mono uppercase tracking-widest text-white/22 mb-2.5">
              Animation Beats ({beats.length})
            </div>
            <div className="flex flex-col gap-1.5">
              {beats.map((beat, idx) => (
                <div
                  key={beat.id ?? idx}
                  className="group/beat flex items-start gap-2.5 rounded-lg border border-white/[0.04] bg-white/[0.02] px-3 py-2 transition-colors hover:border-cyan-500/12 hover:bg-cyan-500/[0.03]"
                >
                  {/* Beat number badge */}
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-cyan-500/10 text-[9px] font-mono font-medium text-cyan-400/70">
                    {idx + 1}
                  </span>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-[11px] font-medium text-white/75">
                        {beat.title}
                      </span>
                      {beat.target_duration_seconds != null && (
                        <span className="shrink-0 text-[9px] font-mono text-white/25">
                          {formatDuration(beat.target_duration_seconds)}
                        </span>
                      )}
                    </div>
                    {beat.visual_goal && (
                      <p className="mt-0.5 line-clamp-1 text-[10px] text-white/35">
                        {beat.visual_goal}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Bottom accent line */}
      <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-cyan-400/15 to-transparent" />
    </div>
  );
}
