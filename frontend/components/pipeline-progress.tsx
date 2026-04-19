"use client";

import { useMemo } from "react";
import type { ReactNode } from "react";
import type { SSEEvent } from "@/types";
import {
  AlertTriangle,
  CheckCircle2,
  Clapperboard,
  Combine,
  Film,
  Loader2,
  Mic,
  Sparkles,
} from "lucide-react";
import {
  getLatestVisualPhase,
  getVisualPhaseIndex,
  type VisualPipelinePhase,
} from "@/lib/pipeline-phase";

export interface PipelinePhase {
  id: string;
  label: string;
  icon: ReactNode;
}

const PIPELINE_PHASES: PipelinePhase[] = [
  {
    id: "init",
    label: "INIT",
    icon: <Sparkles className="h-3.5 w-3.5" />,
  },
  {
    id: "scene",
    label: "SCENE",
    icon: <Film className="h-3.5 w-3.5" />,
  },
  {
    id: "render",
    label: "RENDER",
    icon: <Clapperboard className="h-3.5 w-3.5" />,
  },
  {
    id: "tts",
    label: "VOICE",
    icon: <Mic className="h-3.5 w-3.5" />,
  },
  {
    id: "mux",
    label: "FINAL",
    icon: <Combine className="h-3.5 w-3.5" />,
  },
];

type PhaseStatus = "pending" | "active" | "done" | "error";

interface PhaseState {
  phase: PipelinePhase;
  status: PhaseStatus;
}

interface PipelineProgressProps {
  events: SSEEvent[];
  taskStatus: string;
}

function detectCurrentPhases(events: SSEEvent[], taskStatus: string): PhaseState[] {
  const visualPhase = getLatestVisualPhase(events);
  const activePhase: VisualPipelinePhase | null =
    visualPhase ?? (events.length > 0 ? "init" : null);
  const activeIndex = getVisualPhaseIndex(activePhase);
  const hasError = taskStatus === "failed";
  const states: PhaseState[] = PIPELINE_PHASES.map((phase) => ({
    phase,
    status: "pending",
  }));

  for (let index = 0; index < states.length; index += 1) {
    if (index < activeIndex) {
      states[index].status = "done";
    } else if (index === activeIndex) {
      states[index].status = hasError ? "error" : "active";
    }
  }

  if (taskStatus === "completed" && visualPhase === "mux") {
    states.forEach((state) => {
      state.status = "done";
    });
  }

  if (taskStatus === "failed") {
    const failedIndex = activeIndex >= 0 ? activeIndex : 0;
    if (states[failedIndex]) {
      states[failedIndex].status = "error";
    }
  }

  return states;
}

function StepDot({ state }: { state: PhaseState }) {
  const baseClasses =
    "relative z-10 flex h-5.5 w-5.5 items-center justify-center rounded-full border transition-all duration-500 bg-background/50 backdrop-blur-sm";

  if (state.status === "done") {
    return (
        <div className={`${baseClasses} border-emerald-500/40 text-emerald-400 drop-shadow-[0_0_6px_rgba(52,211,153,0.3)]`}>
        <CheckCircle2 className="h-3 w-3" />
      </div>
    );
  }

  if (state.status === "active") {
    return (
        <div
        className={`${baseClasses} border-cyan-500/60 text-cyan-400 drop-shadow-[0_0_12px_rgba(6,182,212,0.8)] outline outline-1 outline-cyan-500/30 outline-offset-2`}
      >
        <Loader2 className="h-2.5 w-2.5 animate-spin" />
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className={`${baseClasses} border-red-500/50 text-red-500 drop-shadow-[0_0_8px_rgba(239,68,68,0.5)]`}>
        <AlertTriangle className="h-2.5 w-2.5" />
      </div>
    );
  }

  return (
    <div className={`${baseClasses} border-white/10 text-muted-foreground/30`}>
      <span className="scale-[0.85]">{state.phase.icon}</span>
    </div>
  );
}

function ConnectorLine({
  index,
  activeUntil,
}: {
  index: number;
  activeUntil: number;
}) {
  const isActive = index < activeUntil;
  return (
    <div className="relative mx-1.5 h-[2px] w-full flex-1 overflow-hidden rounded-full sm:mx-3">
      <div className="absolute inset-0 bg-white/[0.06]" />
      <div
        className={`absolute inset-y-0 left-0 transition-all duration-700 ease-out ${
          isActive ? "w-full bg-gradient-to-r from-cyan-500/50 to-cyan-400/80" : "w-0"
        }`}
      />
      {isActive && <div className="absolute inset-0 animate-pulse bg-cyan-400/20" />}
    </div>
  );
}

export function PipelineProgress({ events, taskStatus }: PipelineProgressProps) {
  const phases = useMemo(() => detectCurrentPhases(events, taskStatus), [events, taskStatus]);

  const activeIndex = phases.findIndex((phase) => phase.status === "active");
  const doneCount = phases.filter((phase) => phase.status === "done").length;
  const activeUntil = activeIndex >= 0 ? activeIndex : doneCount;

  return (
    <div className="relative w-full overflow-hidden pb-3">
      <div className="flex min-w-0 items-center justify-between gap-2">
      {phases.map((state, index) => {
        const isLast = index === phases.length - 1;
        return (
          <div key={state.phase.id} className={`min-w-0 flex items-center ${isLast ? "flex-none" : "flex-1"}`}>
            <div className="flex flex-col items-center relative shrink-0 group">
              <StepDot state={state} />
              <span
                className={`absolute top-[22px] whitespace-nowrap text-[7px] uppercase tracking-[0.14em] font-mono transition-all duration-300 max-[420px]:hidden sm:text-[7px] sm:tracking-[0.12em] ${
                  index === 0
                    ? "left-0 text-left"
                    : isLast
                      ? "right-0 text-right"
                      : "left-1/2 -translate-x-1/2 text-center"
                } ${
                  state.status === "active"
                    ? "font-semibold text-cyan-300 drop-shadow-[0_0_12px_rgba(34,211,238,0.95)]"
                    : state.status === "done"
                      ? "text-emerald-400/75"
                      : state.status === "error"
                        ? "font-medium text-red-400/90 drop-shadow-[0_0_10px_rgba(248,113,113,0.8)]"
                        : "text-muted-foreground/25"
                }`}
              >
                {state.phase.label}
              </span>
            </div>
            {!isLast && <ConnectorLine index={index} activeUntil={activeUntil} />}
          </div>
        );
      })}
      </div>
    </div>
  );
}
