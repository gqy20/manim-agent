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
    label: "Initialize",
    icon: <Sparkles className="h-3.5 w-3.5" />,
    keywords: ["[progress]", "phase 1", "connect", "init"],
  },
  {
    id: "scene",
    label: "Build Scene",
    icon: <Film className="h-3.5 w-3.5" />,
    keywords: ["scene", "write", "edit", ".py", "generatedscene"],
  },
  {
    id: "render",
    label: "Render Video",
    icon: <Clapperboard className="h-3.5 w-3.5" />,
    keywords: ["phase 2", "render", "manim", "-qh", "-qm", "-ql"],
  },
  {
    id: "tts",
    label: "Generate Voice",
    icon: <Mic className="h-3.5 w-3.5" />,
    keywords: ["phase 3", "[tts]", "voice", "speech", "narration"],
  },
  {
    id: "mux",
    label: "Mux Final",
    icon: <Combine className="h-3.5 w-3.5" />,
    keywords: ["phase 4", "[mux]", "ffmpeg", "final video"],
  },
  {
    id: "done",
    label: "Complete",
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
    "relative z-10 flex h-8 w-8 items-center justify-center rounded-full border transition-all duration-500";

  if (state.status === "done") {
    return (
      <div className={`${baseClasses} border-emerald-500/30 bg-emerald-500/15 text-emerald-400`}>
        <CheckCircle2 className="h-4 w-4" />
      </div>
    );
  }

  if (state.status === "active") {
    return (
      <div
        className={`${baseClasses} border-cyan-500/40 bg-cyan-500/15 text-cyan-400 shadow-[0_0_12px_rgba(6,182,212,0.25)]`}
      >
        <Loader2 className="h-4 w-4 animate-spin" />
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className={`${baseClasses} border-red-500/30 bg-red-500/15 text-red-400`}>
        <AlertTriangle className="h-4 w-4" />
      </div>
    );
  }

  return (
    <div className={`${baseClasses} border-white/10 bg-white/[0.03] text-muted-foreground/30`}>
      {state.phase.icon}
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
  if (index >= total - 1) return null;

  const isActive = index < activeUntil;
  return (
    <div className="relative mx-1 h-[2px] flex-1 overflow-hidden rounded-full">
      <div className="absolute inset-0 bg-white/[0.06]" />
      <div
        className={`absolute inset-y-0 left-0 transition-all duration-700 ease-out ${
          isActive ? "w-full bg-gradient-to-r from-cyan-500/50 to-cyan-400/30" : "w-0"
        }`}
      />
      {isActive && <div className="absolute inset-0 animate-pulse bg-cyan-400/10" />}
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

  const isIdle = taskStatus === "pending" && events.length === 0;
  const isCompleted = taskStatus === "completed";
  const isFailed = taskStatus === "failed";
  const activePhase = phases.find((phase) => phase.status === "active");
  const headerLabel = isCompleted
    ? "Completed"
    : isFailed
      ? "Needs Attention"
      : activePhase?.phase.label ?? latestStatusPayload?.phase ?? (isIdle ? "Idle" : "Running");
  const headerTone = isCompleted
    ? "text-emerald-400"
    : isFailed
      ? "text-red-400"
      : isIdle
        ? "text-muted-foreground/30"
        : "text-cyan-400";
  const phaseMessage = latestStatusPayload?.message ?? null;

  return (
    <div className="space-y-2.5">
      <div className="flex items-center gap-2">
        <Loader2
          className={`h-3.5 w-3.5 ${isIdle ? "text-muted-foreground/30" : "text-primary/60"}`}
        />
        <h2 className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground/60">
          Pipeline
        </h2>
        <span className={`text-[10px] font-mono ${headerTone}`}>{headerLabel}</span>
      </div>

      <div className="glass-card space-y-4 rounded-xl p-4 sm:p-5">
        <div className="flex items-center gap-1 overflow-x-auto pb-1">
          {phases.map((state, index) => (
            <div key={state.phase.id} className="flex items-center gap-1">
              <div className="flex flex-col items-center gap-1.5">
                <StepDot state={state} />
                <span
                  className={`whitespace-nowrap text-[9px] font-mono transition-colors duration-300 ${
                    state.status === "active"
                      ? "font-medium text-cyan-400"
                      : state.status === "done"
                        ? "text-emerald-400/70"
                        : state.status === "error"
                          ? "text-red-400/70"
                          : "text-muted-foreground/30"
                  }`}
                >
                  {state.phase.label}
                </span>
              </div>
              <ConnectorLine index={index} total={phases.length} activeUntil={activeUntil} />
            </div>
          ))}
        </div>

        <div className="rounded-xl border border-white/8 bg-white/[0.02] px-3.5 py-3">
          <div className="flex items-start gap-3">
            <div
              className={`mt-0.5 flex h-8 w-8 items-center justify-center rounded-full border ${
                isCompleted
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                  : isFailed
                    ? "border-red-500/30 bg-red-500/10 text-red-400"
                    : "border-cyan-500/30 bg-cyan-500/10 text-cyan-400"
              }`}
            >
              {isCompleted ? (
                <CheckCircle2 className="h-4 w-4" />
              ) : isFailed ? (
                <AlertTriangle className="h-4 w-4" />
              ) : (
                <Loader2 className="h-4 w-4 animate-spin" />
              )}
            </div>
            <div className="min-w-0 space-y-1">
              <p className="text-[11px] font-mono uppercase tracking-[0.24em] text-white/45">
                {isCompleted
                  ? "Pipeline Complete"
                  : isFailed
                    ? "Pipeline Interrupted"
                    : "Current Phase"}
              </p>
              <p className="text-sm text-white/85">
                {phaseMessage ??
                  (isCompleted
                    ? "The backend has finished the task and the UI is syncing the final artifact."
                    : isFailed
                      ? "The pipeline reported a failure. Review the log stream to find the last successful step."
                      : activePhase?.phase.label
                        ? `${activePhase.phase.label} is currently in progress.`
                        : "The pipeline is connected and waiting for the next backend update.")}
              </p>
              <p className="text-[11px] text-muted-foreground/60">{events.length} events received</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
