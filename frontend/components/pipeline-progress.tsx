"use client";

import { useMemo } from "react";
import type { SSEEvent, StatusPayload } from "@/types";
import { isStatusPayload } from "@/types";
import {
  Loader2,
  Sparkles,
  Film,
  Clapperboard,
  Mic,
  CheckCircle2,
} from "lucide-react";

// ── Pipeline Phase Definition ──────────────────────────────

export interface PipelinePhase {
  id: string;
  label: string;
  icon: React.ReactNode;
  /** Legacy-only fallback keywords for older log-only backends */
  keywords: string[];
}

/** Ordered pipeline phases — index = step order. */
const PIPELINE_PHASES: PipelinePhase[] = [
  {
    id: "init",
    label: "初始化",
    icon: <Sparkles className="h-3.5 w-3.5" />,
    keywords: ["[PROGRESS]", "Phase 1", "Connecting", "Initializing"],
  },
  {
    id: "scene",
    label: "场景生成",
    icon: <Film className="h-3.5 w-3.5" />,
    keywords: [
      "Phase 2",
      "scene",
      "generat",
      "Write",
      "Edit",
      "manim",
      ".py",
    ],
  },
  {
    id: "render",
    label: "视频渲染",
    icon: <Clapperboard className="h-3.5 w-3.5" />,
    keywords: ["Phase 3", "render", "Rendering", "-qh", "-qm", "-ql"],
  },
  {
    id: "tts",
    label: "语音合成",
    icon: <Mic className="h-3.5 w-3.5" />,
    keywords: ["Phase 4", "TTS", "narration", "voice", "speech"],
  },
  {
    id: "done",
    label: "完成",
    icon: <CheckCircle2 className="h-3.5 w-3.5" />,
    keywords: ["[SUMMARY]", "Session Summary", "completed", "final.mp4"],
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

const PHASE_ORDER = ["init", "scene", "render", "tts", "done"] as const;

function getActivePhaseIndexFromStatus(
  phase: StatusPayload["phase"] | undefined,
): number {
  if (!phase) return -1;
  if (phase === "mux" || phase === "done") {
    return PHASE_ORDER.indexOf("done");
  }
  return PHASE_ORDER.indexOf(phase as (typeof PHASE_ORDER)[number]);
}

function detectLegacyPhaseFromLogs(events: SSEEvent[]): number {
  const logText = events
    .filter((e) => e.type === "log" && typeof e.data === "string")
    .map((e) => (e.data as string).toLowerCase())
    .join(" ");

  let maxActiveIndex = -1;
  for (let i = 0; i < PIPELINE_PHASES.length; i++) {
    const phase = PIPELINE_PHASES[i];
    const matched = phase.keywords.some((kw) => logText.includes(kw.toLowerCase()));
    if (matched) {
      maxActiveIndex = i;
    }
  }

  if (maxActiveIndex === -1 && events.length > 0) {
    return 0;
  }

  return maxActiveIndex;
}

// ── Phase Detection ────────────────────────────────────────

/**
 * Scan all events to determine which pipeline phase we're in.
 * Returns an array of PhaseState matching PIPELINE_PHASES order.
 */
function detectCurrentPhases(
  events: SSEEvent[],
  taskStatus: string,
): PhaseState[] {
  const latestStatusPayload = [...events]
    .reverse()
    .find((event): event is SSEEvent & { data: StatusPayload } => isStatusPayload(event))
    ?.data;

  // If task is terminal, mark everything up to current as done
  const isTerminal = ["completed", "failed"].includes(taskStatus);
  const hasError = taskStatus === "failed";

  // Also check structured event types
  const hasToolEvents = events.some((e) =>
    e.type === "tool_start" || e.type === "tool_result",
  );
  const hasProgressEvents = events.some((e) => e.type === "progress");
  const hasThinkingEvents = events.some((e) => e.type === "thinking");

  const states: PhaseState[] = PIPELINE_PHASES.map((phase) => ({
    phase,
    status: "pending" as PhaseStatus,
  }));

  let maxActiveIndex = getActivePhaseIndexFromStatus(latestStatusPayload?.phase);

  // Prefer structured events over log text when status phase is not available yet.
  if (maxActiveIndex === -1 && (hasToolEvents || hasThinkingEvents || hasProgressEvents)) {
    maxActiveIndex = PHASE_ORDER.indexOf("scene");
  }

  // Legacy fallback for older servers that only emitted free-form logs.
  if (maxActiveIndex === -1) {
    maxActiveIndex = detectLegacyPhaseFromLogs(events);
  }

  if (maxActiveIndex < 0 && isTerminal) {
    maxActiveIndex = PHASE_ORDER.indexOf("done");
  }

  // Assign statuses
  for (let i = 0; i < states.length; i++) {
    if (i < maxActiveIndex) {
      states[i].status = "done";
    } else if (i === maxActiveIndex) {
      states[i].status = isTerminal
        ? hasError
          ? "error"
          : "done"
        : "active";
    } else {
      states[i].status = isTerminal ? (hasError ? "error" : "pending") : "pending";
    }
  }

  // Special case: completed task → all done
  if (taskStatus === "completed") {
    states.forEach((s) => {
      if (s.status !== "error") s.status = "done";
    });
  }

  return states;
}

// ── Sub-components ─────────────────────────────────────────

function StepDot({ state }: { state: PhaseState }) {
  const { status, phase } = state;

  const baseClasses =
    "relative z-10 flex items-center justify-center w-8 h-8 rounded-full border transition-all duration-500";

  switch (status) {
    case "done":
      return (
        <div
          className={`${baseClasses} bg-emerald-500/15 border-emerald-500/30 text-emerald-400`}
        >
          <CheckCircle2 className="h-4 w-4" />
        </div>
      );
    case "active":
      return (
        <div
          className={`${baseClasses} bg-cyan-500/15 border-cyan-500/40 text-cyan-400 shadow-[0_0_12px_rgba(6,182,212,0.25)]`}
        >
          <Loader2 className="h-4 w-4 animate-spin" />
        </div>
      );
    case "error":
      return (
        <div
          className={`${baseClasses} bg-red-500/15 border-red-500/30 text-red-400`}
        >
          {phase.icon}
        </div>
      );
    default:
      return (
        <div
          className={`${baseClasses} bg-white/[0.03] border-white/10 text-muted-foreground/30`}
        >
          {phase.icon}
        </div>
      );
  }
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
  const isLast = index >= total - 1;

  if (isLast) return null;

  return (
    <div className="flex-1 h-[2px] mx-1 relative overflow-hidden rounded-full">
      {/* Background track */}
      <div className="absolute inset-0 bg-white/[0.06]" />
      {/* Progress fill */}
      <div
        className={`absolute inset-y-0 left-0 transition-all duration-700 ease-out ${
          isActive
            ? "bg-gradient-to-r from-cyan-500/50 to-cyan-400/30"
            : "w-0"
        }`}
      />
      {/* Animated shimmer when active */}
      {isActive && (
        <div className="absolute inset-0 animate-pulse bg-cyan-400/10" />
      )}
    </div>
  );
}

// ── Main Component ──────────────────────────────────────────

export function PipelineProgress({ events, taskStatus }: PipelineProgressProps) {
  const phases = useMemo(
    () => detectCurrentPhases(events, taskStatus),
    [events, taskStatus],
  );

  // Find the active phase index for connector lines
  const activeIndex = phases.findIndex((p) => p.status === "active");
  const doneCount = phases.filter((p) => p.status === "done").length;
  const activeUntil = activeIndex >= 0 ? activeIndex : doneCount;

  const isIdle = taskStatus === "pending" && events.length === 0;

  return (
    <div className="space-y-2.5">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Loader2 className={`h-3.5 w-3.5 ${isIdle ? "text-muted-foreground/30" : "text-primary/60"}`} />
        <h2 className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground/60">
          Pipeline
        </h2>
        {!isIdle && (
          <span className="text-[10px] font-mono text-primary/40">
            {phases.find((p) => p.status === "active")?.phase.label ?? "Idle"}
          </span>
        )}
      </div>

      {/* Progress Stepper */}
      <div className="glass-card rounded-xl p-4 sm:p-5">
        <div className="flex items-center gap-1">
          {phases.map((state, i) => (
            <div key={state.phase.id} className="flex items-center gap-1">
              {/* Step dot + label */}
              <div className="flex flex-col items-center gap-1.5">
                <StepDot state={state} />
                <span
                  className={`text-[9px] font-mono whitespace-nowrap transition-colors duration-300 ${
                    state.status === "active"
                      ? "text-cyan-400 font-medium"
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

              {/* Connector line to next step */}
              <ConnectorLine
                index={i}
                total={phases.length}
                activeUntil={activeUntil}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
