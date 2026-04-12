"use client";

import { useMemo } from "react";
import type { ReactNode } from "react";
import type { SSEEvent, StatusPayload } from "@/types";
import { isStatusPayload } from "@/types";
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

export interface PipelinePhase {
  id: string;
  label: string;
  icon: ReactNode;
  keywords: string[];
}

const PHASE_ORDER = ["init", "scene", "render", "tts", "mux", "done"] as const;

const PIPELINE_PHASES: PipelinePhase[] = [
  {
    id: "init",
    label: "INIT",
    icon: <Sparkles className="h-3.5 w-3.5" />,
    keywords: ["[progress]", "phase 1", "connect", "init"],
  },
  {
    id: "scene",
    label: "SCENE",
    icon: <Film className="h-3.5 w-3.5" />,
    keywords: ["scene", "write", "edit", ".py", "generatedscene"],
  },
  {
    id: "render",
    label: "RENDER",
    icon: <Clapperboard className="h-3.5 w-3.5" />,
    keywords: ["phase 2", "render", "manim", "-qh", "-qm", "-ql"],
  },
  {
    id: "tts",
    label: "VOICE",
    icon: <Mic className="h-3.5 w-3.5" />,
    keywords: ["phase 3", "[tts]", "voice", "speech", "narration"],
  },
  {
    id: "mux",
    label: "FINAL",
    icon: <Combine className="h-3.5 w-3.5" />,
    keywords: ["phase 4", "[mux]", "ffmpeg", "final video"],
  },
  {
    id: "done",
    label: "DONE",
    icon: <CheckCircle2 className="h-3.5 w-3.5" />,
    keywords: ["[summary]", "completed", "final.mp4"],
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

function getActivePhaseIndexFromStatus(
  phase: StatusPayload["phase"] | undefined,
): number {
  if (!phase) return -1;
  return PHASE_ORDER.indexOf(phase as (typeof PHASE_ORDER)[number]);
}

function detectLegacyPhaseFromLogs(events: SSEEvent[]): number {
  const logText = events
    .flatMap((event) =>
      event.type === "log" && typeof event.data === "string" ? [event.data.toLowerCase()] : [],
    )
    .join(" ");

  let maxActiveIndex = -1;
  for (let index = 0; index < PIPELINE_PHASES.length; index += 1) {
    const phase = PIPELINE_PHASES[index];
    if (phase.keywords.some((keyword) => logText.includes(keyword))) {
      maxActiveIndex = index;
    }
  }

  if (maxActiveIndex === -1 && events.length > 0) {
    return 0;
  }

  return maxActiveIndex;
}

function detectCurrentPhases(events: SSEEvent[], taskStatus: string): PhaseState[] {
  const latestStatusPayload = [...events]
    .reverse()
    .find((event): event is SSEEvent & { data: StatusPayload } => isStatusPayload(event))
    ?.data;

  const isTerminal = ["completed", "failed"].includes(taskStatus);
  const hasError = taskStatus === "failed";
  const hasSceneSignals = events.some(
    (event) =>
      event.type === "tool_start" ||
      event.type === "tool_result" ||
      event.type === "thinking" ||
      event.type === "progress",
  );

  const states: PhaseState[] = PIPELINE_PHASES.map((phase) => ({
    phase,
    status: "pending",
  }));

  let maxActiveIndex = getActivePhaseIndexFromStatus(latestStatusPayload?.phase);

  if (maxActiveIndex === -1 && hasSceneSignals) {
    maxActiveIndex = PHASE_ORDER.indexOf("scene");
  }

  if (maxActiveIndex === -1) {
    maxActiveIndex = detectLegacyPhaseFromLogs(events);
  }

  if (maxActiveIndex < 0 && isTerminal) {
    maxActiveIndex = PHASE_ORDER.indexOf("done");
  }

  for (let index = 0; index < states.length; index += 1) {
    if (index < maxActiveIndex) {
      states[index].status = "done";
    } else if (index === maxActiveIndex) {
      states[index].status = isTerminal ? (hasError ? "error" : "done") : "active";
    }
  }

  if (taskStatus === "completed") {
    states.forEach((state) => {
      state.status = "done";
    });
  }

  if (taskStatus === "failed") {
    const activeState = states.find((state) => state.status === "active");
    if (activeState) {
      activeState.status = "error";
    }
  }

  return states;
}

function StepDot({ state }: { state: PhaseState }) {
  const baseClasses =
    "relative z-10 flex h-7 w-7 items-center justify-center rounded-full border transition-all duration-500 bg-background/50 backdrop-blur-sm";

  if (state.status === "done") {
    return (
      <div className={`${baseClasses} border-emerald-500/40 text-emerald-400 drop-shadow-[0_0_6px_rgba(52,211,153,0.3)]`}>
        <CheckCircle2 className="h-4 w-4" />
      </div>
    );
  }

  if (state.status === "active") {
    return (
      <div
        className={`${baseClasses} border-cyan-500/60 text-cyan-400 drop-shadow-[0_0_12px_rgba(6,182,212,0.8)] outline outline-1 outline-cyan-500/30 outline-offset-2`}
      >
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className={`${baseClasses} border-red-500/50 text-red-500 drop-shadow-[0_0_8px_rgba(239,68,68,0.5)]`}>
        <AlertTriangle className="h-3 w-3" />
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
  total,
  activeUntil,
}: {
  index: number;
  total: number;
  activeUntil: number;
}) {
  const isActive = index < activeUntil;
  return (
    <div className="relative mx-3 h-[2px] w-full flex-1 overflow-hidden rounded-full">
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
  const latestStatusPayload = useMemo(
    () =>
      [...events]
        .reverse()
        .find((event): event is SSEEvent & { data: StatusPayload } => isStatusPayload(event))
        ?.data,
    [events],
  );

  const activeIndex = phases.findIndex((phase) => phase.status === "active");
  const doneCount = phases.filter((phase) => phase.status === "done").length;
  const activeUntil = activeIndex >= 0 ? activeIndex : doneCount;

  return (
    <div className="w-full relative flex items-center justify-between pb-1 gap-1">
      {phases.map((state, index) => {
        const isLast = index === phases.length - 1;
        return (
          <div key={state.phase.id} className={`flex items-center ${isLast ? "flex-none" : "flex-1"}`}>
            <div className="flex flex-col items-center relative shrink-0 group">
              <StepDot state={state} />
              <span
                className={`absolute top-[26px] whitespace-nowrap text-[9px] uppercase tracking-widest font-mono transition-all duration-300 ${
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
            {!isLast && <ConnectorLine index={index} total={phases.length} activeUntil={activeUntil} />}
          </div>
        );
      })}
    </div>
  );
}
