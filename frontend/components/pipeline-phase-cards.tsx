"use client";

import { useMemo } from "react";
import {
  FileCode2, Film, Mic, Volume2, Clapperboard, CheckCircle2,
  AlertTriangle, Clock, Target, BookOpen, ListVideo,
} from "lucide-react";
import type { PipelineOutputData } from "@/types";

interface PipelinePhaseCardsProps {
  pipelineOutput: PipelineOutputData | null;
}

function formatDurationSec(sec: number | null): string {
  if (sec == null) return "--";
  if (sec < 60) return `${sec.toFixed(1)}s`;
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return s > 0 ? `${m}m${s}s` : `${m}m`;
}

function formatMs(ms: number | null): string {
  if (ms == null) return "--";
  if (ms < 1000) return `${ms}ms`;
  return formatDurationSec(ms / 1000);
}

/* ── Shared shell ── */
function CardShell({
  icon: Icon,
  label,
  accent,
  children,
}: {
  icon: React.ElementType;
  label: string;
  accent: string;
  children: React.ReactNode;
}) {
  return (
    <div className="group relative flex aspect-video w-full flex-col overflow-hidden rounded-xl border border-white/8 bg-black/50 shadow-2xl ring-1 ring-white/5 backdrop-blur-xl">
      <div className={`absolute inset-x-0 top-0 h-px bg-gradient-to-r ${accent}`} />
      <div className="flex shrink-0 items-center gap-2.5 border-b border-white/5 px-5 py-2.5">
        <Icon className="h-4 w-4 shrink-0 text-white/40" />
        <span className="text-[11px] font-mono uppercase tracking-widest text-white/45">
          {label}
        </span>
      </div>
      <div className="flex flex-1 flex-col overflow-y-auto custom-scrollbar px-5 py-3 gap-2">
        {children}
      </div>
      <div className={`absolute inset-x-0 bottom-0 h-px bg-gradient-to-r ${accent}`} />
    </div>
  );
}

/* ── Row helper ── */
function InfoRow({
  icon: Icon,
  label,
  value,
  dim = false,
}: {
  icon?: React.ElementType;
  label: string;
  value: React.ReactNode;
  dim?: boolean;
}) {
  return (
    <div className="flex items-start gap-2">
      {Icon && <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-white/25" />}
      <span className="shrink-0 text-[10px] text-white/30">{label}</span>
      <span className={`min-w-0 truncate text-[11px] ${dim ? "text-white/35" : "text-white/60"}`}>
        {value}
      </span>
    </div>
  );
}

/* ══════════════════════════════════════
   Phase 2A — Script Draft
   ══════════════════════════════════════ */
function ScriptDraftView({ d }: { d: PipelineOutputData }) {
  const beats = d.implemented_beats ?? [];
  const timing = d.beat_timing_seconds ?? {};

  return (
    <CardShell icon={FileCode2} label="Script Draft" accent="from-violet-400/30 to-transparent">
      {d.scene_class && (
        <InfoRow icon={FileCode2} label="Scene" value={<code className="text-violet-300/70">{d.scene_class}</code>} />
      )}
      {d.scene_file && (
        <InfoRow label="File" value={d.scene_file} dim />
      )}
      {d.build_summary && (
        <InfoRow icon={Target} label="Summary" value={d.build_summary} />
      )}

      {beats.length > 0 && (
        <>
          <div className="text-[9px] font-mono uppercase tracking-widest text-white/22 mt-1">
            Implemented Beats ({beats.length})
          </div>
          <div className="flex flex-col gap-1">
            {beats.map((beat, i) => (
              <div
                key={beat}
                className="flex items-center gap-2 rounded-lg border border-white/[0.03] bg-white/[0.015] px-2.5 py-1.5"
              >
                <span className="flex h-4.5 w-4.5 shrink-0 items-center justify-center rounded bg-violet-500/10 text-[8px] font-mono text-violet-400/70">
                  {i + 1}
                </span>
                <span className="truncate text-[10.5px] text-white/55">{beat}</span>
                {timing[beat] != null && (
                  <span className="shrink-0 text-[9px] font-mono text-white/22">
                    {formatDurationSec(timing[beat])}
                  </span>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {d.estimated_duration_seconds != null && d.estimated_duration_seconds > 0 && (
        <InfoRow icon={Clock} label="Est. duration" value={formatDurationSec(d.estimated_duration_seconds)} dim />
      )}
    </CardShell>
  );
}

/* ══════════════════════════════════════
   Phase 2B / 3 — Render Result
   ══════════════════════════════════════ */
function RenderResultView({ d }: { d: PipelineOutputData }) {
  const deviations = d.deviations_from_plan ?? [];
  const beats = d.implemented_beats ?? [];

  return (
    <CardShell icon={Film} label="Render Output" accent="from-emerald-400/25 to-transparent">
      {d.video_output && (
        <InfoRow
          icon={Film}
          label="Video"
          value={<span className="font-mono text-emerald-300/65">{d.video_output}</span>}
        />
      )}
      {d.duration_seconds != null && d.duration_seconds > 0 && (
        <InfoRow icon={Clock} label="Duration" value={formatDurationSec(d.duration_seconds)} />
      )}
      {d.build_summary && (
        <InfoRow icon={Target} label="Build summary" value={d.build_summary} />
      )}

      {d.review_approved === true && (
        <div className="flex items-center gap-1.5 rounded-lg border border-emerald-500/15 bg-emerald-500/[0.04] px-2.5 py-1.5">
          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400/70" />
          <span className="text-[10px] text-emerald-300/60">Render review passed</span>
          {d.review_summary && (
            <span className="truncate text-[10px] text-white/30">{d.review_summary}</span>
          )}
        </div>
      )}
      {d.review_approved === false && (
        <div className="flex items-center gap-1.5 rounded-lg border border-red-500/15 bg-red-500/[0.04] px-2.5 py-1.5">
          <AlertTriangle className="h-3.5 w-3.5 text-red-400/70" />
          <span className="text-[10px] text-red-300/60">Render review blocked</span>
        </div>
      )}

      {deviations.length > 0 && (
        <>
          <div className="text-[9px] font-mono uppercase tracking-widest text-white/20 mt-1">
            Deviations ({deviations.length})
          </div>
          <div className="flex flex-col gap-1">
            {deviations.map((dev, i) => (
              <div key={i} className="rounded-lg border border-amber-500/8 bg-amber-500/[0.02] px-2.5 py-1.5 text-[10px] text-amber-300/50">
                {dev}
              </div>
            ))}
          </div>
        </>
      )}

      {beats.length > 0 && !d.build_summary && (
        <InfoRow icon={ListVideo} label="Beats" value={`${beats.length} implemented`} dim />
      )}
    </CardShell>
  );
}

/* ══════════════════════════════════════
   Phase 3.5 — Narration
   ══════════════════════════════════════ */
function NarrationView({ d }: { d: PipelineOutputData }) {
  const beatMap = d.beat_to_narration_map ?? [];

  return (
    <CardShell icon={Mic} label="Narration" accent="from-orange-400/25 to-transparent">
      {d.narration && (
        <div className="rounded-lg border border-white/[0.04] bg-white/[0.02] p-3">
          <p className="line-clamp-6 whitespace-pre-wrap text-[11px] leading-relaxed text-white/55">
            {d.narration}
          </p>
        </div>
      )}

      {beatMap.length > 0 && (
        <>
          <div className="text-[9px] font-mono uppercase tracking-widest text-white/22 mt-1">
            Beat Narration Map ({beatMap.length})
          </div>
          <div className="flex flex-col gap-1 max-h-[40%] overflow-y-auto custom-scrollbar">
            {beatMap.map((text, i) => (
              <div key={i} className="flex gap-2 rounded-lg border border-white/[0.03] px-2.5 py-1.5">
                <span className="flex h-4.5 w-4.5 shrink-0 items-center justify-center rounded bg-orange-500/10 text-[8px] font-mono text-orange-400/70">
                  {i + 1}
                </span>
                <span className="line-clamp-2 text-[10.5px] text-white/45">{text}</span>
              </div>
            ))}
          </div>
        </>
      )}

      <div className="flex items-center gap-3 mt-1 text-[9px] font-mono text-white/25">
        {d.narration_coverage_complete != null && (
          <span className={d.narration_coverage_complete ? "text-emerald-400/40" : "text-amber-400/40"}>
            {d.narration_coverage_complete ? "Coverage: complete" : "Coverage: partial"}
          </span>
        )}
        {d.estimated_narration_duration_seconds != null && d.estimated_narration_duration_seconds > 0 && (
          <span>Est. {formatDurationSec(d.estimated_narration_duration_seconds)}</span>
        )}
      </div>
    </CardShell>
  );
}

/* ══════════════════════════════════════
   Phase 4 — TTS
   ══════════════════════════════════════ */
function TTSView({ d }: { d: PipelineOutputData }) {
  return (
    <CardShell icon={Volume2} label="Voice Synthesis" accent="from-sky-400/25 to-transparent">
      {d.audio_path && (
        <InfoRow
          icon={Volume2}
          label="Audio"
          value={<span className="font-mono text-sky-300/65">{d.audio_path}</span>}
        />
      )}
      {d.tts_mode && (
        <InfoRow label="Mode" value={d.tts_mode} />
      )}
      {d.tts_duration_ms != null && d.tts_duration_ms > 0 && (
        <InfoRow icon={Clock} label="Audio length" value={formatMs(d.tts_duration_ms)} />
      )}
      {d.tts_word_count != null && d.tts_word_count > 0 && (
        <InfoRow label="Words" value={`${d.tts_word_count}`} dim />
      )}
      {d.narration && (
        <div className="mt-1 rounded-lg border border-white/[0.03] bg-white/[0.015] p-2.5">
          <p className="line-clamp-3 text-[10px] leading-relaxed text-white/35">{d.narration}</p>
        </div>
      )}
    </CardShell>
  );
}

/* ══════════════════════════════════════
   Phase 5 — Final Mux
   ══════════════════════════════════════ */
function FinalMuxView({ d }: { d: PipelineOutputData }) {
  return (
    <CardShell icon={Clapperboard} label="Final Output" accent="from-cyan-400/25 to-transparent">
      {d.final_video_output && (
        <InfoRow
          icon={Clapperboard}
          label="Final video"
          value={<span className="font-mono text-cyan-300/65">{d.final_video_output}</span>}
        />
      )}
      {d.video_output && !d.final_video_output && (
        <InfoRow
          icon={Film}
          label="Video output"
          value={<span className="font-mono text-cyan-300/65">{d.video_output}</span>}
        />
      )}
      {d.duration_seconds != null && d.duration_seconds > 0 && (
        <InfoRow icon={Clock} label="Duration" value={formatDurationSec(d.duration_seconds)} />
      )}
      {d.audio_path && (
        <InfoRow icon={Volume2} label="Audio track" value={d.audio_path} dim />
      )}
      {d.subtitle_path && (
        <InfoRow label="Subtitles" value={d.subtitle_path} dim />
      )}
      {d.bgm_path && (
        <InfoRow label="BGM" value={d.bgm_prompt || d.bgm_path} dim />
      )}
    </CardShell>
  );
}

/* ══════════════════════════════════════
   Public API — auto-detect which view to show
   ══════════════════════════════════════ */

/** Priority order: later phases override earlier ones. */
export function PipelinePhaseCards({ pipelineOutput }: PipelinePhaseCardsProps) {
  const view = useMemo((): "narration" | "tts" | "mux" | "render" | "script" | null => {
    if (!pipelineOutput) return null;

    // Phase 5: has final_video_output or mux-phase data
    if (pipelineOutput.final_video_output) return "mux";

    // Phase 4: has audio_path + tts_mode
    if (pipelineOutput.audio_path && pipelineOutput.tts_mode) return "tts";

    // Phase 3.5: has narration with beat map
    if (pipelineOutput.narration && pipelineOutput.beat_to_narration_map?.length) return "narration";

    // Phase 3/2B: has video_output + build_summary (render result)
    if (pipelineOutput.video_output && pipelineOutput.build_summary) return "render";

    // Phase 2A: has scene_class or implemented_beats without render data
    if (pipelineOutput.scene_class || (pipelineOutput.implemented_beats?.length && !pipelineOutput.video_output)) return "script";

    // Fallback: if we have any narration but no beat map
    if (pipelineOutput.narration) return "narration";

    // Fallback: if we have video_output
    if (pipelineOutput.video_output) return "render";

    return null;
  }, [pipelineOutput]);

  if (!view || !pipelineOutput) return null;

  switch (view) {
    case "script": return <ScriptDraftView d={pipelineOutput} />;
    case "render": return <RenderResultView d={pipelineOutput} />;
    case "narration": return <NarrationView d={pipelineOutput} />;
    case "tts": return <TTSView d={pipelineOutput} />;
    case "mux": return <FinalMuxView d={pipelineOutput} />;
    default: return null;
  }
}
