"use client";

import type { ElementType, ReactNode } from "react";
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Clapperboard,
  FileCode2,
  Film,
  ListChecks,
  ListVideo,
  Mic,
  Music2,
  Route,
  Sparkles,
  Target,
  Users,
  Volume2,
} from "lucide-react";

import type { FrameAnalysisOutput, PipelineOutputData } from "@/types";

interface PipelinePhaseCardsProps {
  pipelineOutput: PipelineOutputData | null;
}

function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "--";
  if (seconds < 60) return `${Math.round(seconds * 10) / 10}s`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return rest > 0 ? `${minutes}m${rest}s` : `${minutes}m`;
}

function formatMs(ms: number | null | undefined): string {
  if (ms == null) return "--";
  if (ms < 1000) return `${ms}ms`;
  return formatDuration(ms / 1000);
}

function hasText(value: string | null | undefined): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function valueCount(values: Array<unknown[] | string | number | boolean | null | undefined>): number {
  return values.filter((value) => {
    if (Array.isArray(value)) return value.length > 0;
    if (typeof value === "string") return value.trim().length > 0;
    return value !== null && value !== undefined;
  }).length;
}

function PhaseShell({
  icon: Icon,
  title,
  meta,
  tone,
  children,
}: {
  icon: ElementType;
  title: string;
  meta?: ReactNode;
  tone: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-white/[0.06] bg-white/[0.025] overflow-hidden">
      <div className={`h-px bg-gradient-to-r ${tone}`} />
      <div className="flex items-center justify-between gap-3 border-b border-white/[0.04] px-3 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <Icon className="h-3.5 w-3.5 shrink-0 text-white/38" />
          <h3 className="truncate text-[10px] font-mono uppercase tracking-widest text-white/55">
            {title}
          </h3>
        </div>
        {meta && <div className="shrink-0 text-[9px] font-mono text-white/28">{meta}</div>}
      </div>
      <div className="space-y-2 px-3 py-2.5">{children}</div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="min-w-0 rounded-md border border-white/[0.04] bg-black/20 px-2.5 py-2">
      <div className="text-[9px] font-mono uppercase tracking-widest text-white/24">{label}</div>
      <div className="mt-1 truncate text-[11px] text-white/62">{value}</div>
    </div>
  );
}

function TextBlock({ icon: Icon, children }: { icon?: ElementType; children: ReactNode }) {
  return (
    <div className="flex min-w-0 gap-2 rounded-md border border-white/[0.04] bg-black/18 px-2.5 py-2">
      {Icon && <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-white/28" />}
      <div className="min-w-0 text-[11px] leading-relaxed text-white/54">{children}</div>
    </div>
  );
}

function PillList({ items, tone = "bg-white/[0.04] text-white/45" }: { items: string[]; tone?: string }) {
  if (items.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.slice(0, 8).map((item, index) => (
        <span key={`${item}-${index}`} className={`rounded-md px-2 py-1 text-[10px] ${tone}`}>
          {item}
        </span>
      ))}
      {items.length > 8 && (
        <span className="rounded-md bg-white/[0.03] px-2 py-1 text-[10px] text-white/25">
          +{items.length - 8}
        </span>
      )}
    </div>
  );
}

function PlanningSection({ d }: { d: PipelineOutputData }) {
  const spec = d.phase1_planning?.build_spec;
  const beats = spec?.beats ?? d.beats ?? [];
  const beatTotal = beats.reduce((sum, beat) => sum + (beat.target_duration_seconds ?? 0), 0);

  if (!spec && !hasText(d.plan_text) && beats.length === 0) return null;

  return (
    <PhaseShell
      icon={BookOpen}
      title="Planning"
      tone="from-cyan-400/35 via-cyan-400/12 to-transparent"
      meta={beats.length ? `${beats.length} beats` : undefined}
    >
      <div className="grid gap-2 sm:grid-cols-3">
        {spec?.mode && <Metric label="Mode" value={spec.mode} />}
        {spec?.target_duration_seconds != null && (
          <Metric label="Target" value={formatDuration(spec.target_duration_seconds)} />
        )}
        {beatTotal > 0 && <Metric label="Beat Sum" value={formatDuration(beatTotal)} />}
      </div>

      {spec?.learning_goal && (
        <TextBlock icon={Target}>{spec.learning_goal}</TextBlock>
      )}
      {spec?.audience && (
        <TextBlock icon={Users}>{spec.audience}</TextBlock>
      )}
      {d.plan_text && (
        <TextBlock icon={Route}>
          <p className="line-clamp-3">{d.plan_text}</p>
        </TextBlock>
      )}

      {beats.length > 0 && (
        <div className="space-y-1.5">
          {beats.slice(0, 6).map((beat, index) => {
            const required = "required_elements" in beat ? beat.required_elements ?? [] : [];
            return (
              <div key={beat.id ?? index} className="rounded-md border border-white/[0.04] bg-black/16 px-2.5 py-2">
                <div className="flex items-start gap-2">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-cyan-500/10 text-[9px] font-mono text-cyan-300/75">
                    {index + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-[11px] font-medium text-white/70">{beat.title ?? beat.id}</span>
                      {beat.target_duration_seconds != null && (
                        <span className="shrink-0 text-[9px] font-mono text-white/28">
                          {formatDuration(beat.target_duration_seconds)}
                        </span>
                      )}
                    </div>
                    {beat.visual_goal && <p className="mt-1 line-clamp-2 text-[10px] text-white/42">{beat.visual_goal}</p>}
                    {beat.narration_intent && <p className="mt-1 line-clamp-2 text-[10px] text-amber-200/42">{beat.narration_intent}</p>}
                    <PillList items={required} />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </PhaseShell>
  );
}

function ImplementationSection({ d }: { d: PipelineOutputData }) {
  const phase = d.phase2_implementation;
  const implemented = phase?.implemented_beats ?? d.implemented_beats ?? [];
  const deviations = phase?.deviations_from_plan ?? d.deviations_from_plan ?? [];
  const sceneClass = phase?.scene_class ?? d.scene_class;
  const sceneFile = phase?.scene_file ?? d.scene_file;
  const renderMode = phase?.render_mode ?? d.render_mode;
  const segmentPaths = phase?.segment_video_paths ?? d.segment_video_paths ?? [];
  const summary = phase?.build_summary ?? d.build_summary;

  if (valueCount([implemented, deviations, sceneClass, sceneFile, renderMode, segmentPaths, summary]) === 0) {
    return null;
  }

  return (
    <PhaseShell
      icon={FileCode2}
      title="Implementation"
      tone="from-violet-400/35 via-violet-400/10 to-transparent"
      meta={renderMode ?? undefined}
    >
      <div className="grid gap-2 sm:grid-cols-3">
        {sceneClass && <Metric label="Scene" value={<code className="text-violet-200/75">{sceneClass}</code>} />}
        {sceneFile && <Metric label="File" value={sceneFile} />}
        {segmentPaths.length > 0 && <Metric label="Segments" value={segmentPaths.length} />}
      </div>

      {summary && <TextBlock icon={Sparkles}>{summary}</TextBlock>}
      <PillList items={implemented} tone="bg-violet-500/[0.08] text-violet-100/58" />

      {deviations.length > 0 && (
        <div className="space-y-1">
          {deviations.map((item, index) => (
            <TextBlock key={`${item}-${index}`} icon={AlertTriangle}>
              <span className="text-amber-200/58">{item}</span>
            </TextBlock>
          ))}
        </div>
      )}
    </PhaseShell>
  );
}

function ReviewSection({ d }: { d: PipelineOutputData }) {
  const review = d.phase3_render_review;
  const approved = review?.approved ?? d.review_approved;
  const summary = review?.summary ?? d.review_summary;
  const blocking = review?.blocking_issues ?? d.review_blocking_issues ?? [];
  const edits = review?.suggested_edits ?? d.review_suggested_edits ?? [];
  const frames = review?.frame_analyses ?? d.review_frame_analyses ?? [];

  if (approved == null && !summary && blocking.length === 0 && edits.length === 0 && frames.length === 0) {
    return null;
  }

  return (
    <PhaseShell
      icon={approved === false ? AlertTriangle : CheckCircle2}
      title="Render Review"
      tone={approved === false ? "from-red-400/35 via-red-400/10 to-transparent" : "from-emerald-400/35 via-emerald-400/10 to-transparent"}
      meta={approved == null ? "unchecked" : approved ? "approved" : "blocked"}
    >
      {summary && <TextBlock icon={Film}>{summary}</TextBlock>}
      <PillList items={blocking} tone="bg-red-500/[0.08] text-red-100/58" />
      <PillList items={edits} tone="bg-amber-500/[0.08] text-amber-100/58" />
      {frames.length > 0 && (
        <div className="space-y-1.5">
          {frames.slice(0, 4).map((frame: FrameAnalysisOutput, index) => (
            <div key={`${frame.frame_path}-${index}`} className="rounded-md border border-white/[0.04] bg-black/16 px-2.5 py-2">
              <div className="flex items-center gap-2 text-[10px] font-mono text-white/30">
                <span>{frame.timestamp_label || `frame ${index + 1}`}</span>
                <span className="truncate">{frame.frame_path}</span>
              </div>
              {frame.visual_assessment && (
                <p className="mt-1 line-clamp-2 text-[10px] text-white/45">{frame.visual_assessment}</p>
              )}
              <PillList items={frame.issues_found ?? []} tone="bg-red-500/[0.08] text-red-100/55" />
            </div>
          ))}
        </div>
      )}
    </PhaseShell>
  );
}

function NarrationSection({ d }: { d: PipelineOutputData }) {
  const map = d.beat_to_narration_map ?? [];
  if (!d.narration && map.length === 0 && d.narration_coverage_complete == null) return null;

  return (
    <PhaseShell
      icon={Mic}
      title="Narration"
      tone="from-orange-400/35 via-orange-400/10 to-transparent"
      meta={d.narration_coverage_complete == null ? undefined : d.narration_coverage_complete ? "covered" : "partial"}
    >
      {d.narration && (
        <TextBlock icon={Mic}>
          <p className="line-clamp-5 whitespace-pre-wrap">{d.narration}</p>
        </TextBlock>
      )}
      {map.length > 0 && (
        <div className="space-y-1.5">
          {map.slice(0, 6).map((item, index) => (
            <div key={`${item}-${index}`} className="flex gap-2 rounded-md border border-white/[0.04] bg-black/16 px-2.5 py-2">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-orange-500/10 text-[9px] font-mono text-orange-300/75">
                {index + 1}
              </span>
              <span className="line-clamp-2 text-[10px] text-white/46">{item}</span>
            </div>
          ))}
        </div>
      )}
      {d.estimated_narration_duration_seconds != null && (
        <Metric label="Estimated Duration" value={formatDuration(d.estimated_narration_duration_seconds)} />
      )}
    </PhaseShell>
  );
}

function AudioSection({ d }: { d: PipelineOutputData }) {
  const phase = d.phase4_tts;
  const audioPath = phase?.audio_path ?? d.audio_path;
  const ttsMode = phase?.tts_mode ?? d.tts_mode;
  const ttsDuration = phase?.tts_duration_ms ?? d.tts_duration_ms;
  const usage = phase?.tts_usage_characters ?? d.tts_usage_characters;
  const audioSegments = d.audio_segments ?? [];

  if (valueCount([audioPath, ttsMode, ttsDuration, usage, audioSegments, d.timeline_path, d.bgm_path]) === 0) {
    return null;
  }

  return (
    <PhaseShell
      icon={Volume2}
      title="Audio"
      tone="from-sky-400/35 via-sky-400/10 to-transparent"
      meta={audioSegments.length ? `${audioSegments.length} segments` : undefined}
    >
      <div className="grid gap-2 sm:grid-cols-3">
        {ttsMode && <Metric label="TTS Mode" value={ttsMode} />}
        {ttsDuration != null && <Metric label="Voice Length" value={formatMs(ttsDuration)} />}
        {usage != null && <Metric label="Usage" value={`${usage} chars`} />}
      </div>
      {audioPath && <TextBlock icon={Volume2}><code className="text-sky-100/65">{audioPath}</code></TextBlock>}
      {d.timeline_total_duration_seconds != null && (
        <Metric label="Timeline" value={formatDuration(d.timeline_total_duration_seconds)} />
      )}
      {d.bgm_path && (
        <TextBlock icon={Music2}>
          <span className="line-clamp-2">{d.bgm_prompt || d.bgm_path}</span>
        </TextBlock>
      )}
      {audioSegments.length > 0 && (
        <PillList
          items={audioSegments.slice(0, 8).map((segment) => `${segment.beat_id} ${formatDuration(segment.duration_seconds)}`)}
          tone="bg-sky-500/[0.08] text-sky-100/58"
        />
      )}
    </PhaseShell>
  );
}

function MuxSection({ d }: { d: PipelineOutputData }) {
  const phase = d.phase5_mux;
  const finalVideo = phase?.final_video_output ?? d.final_video_output;
  const duration = phase?.duration_seconds ?? d.duration_seconds;
  const mixMode = phase?.audio_mix_mode ?? d.audio_mix_mode;
  const subtitle = phase?.subtitle_path ?? d.subtitle_path;
  const bgmPath = phase?.bgm_path ?? d.bgm_path;

  if (valueCount([finalVideo, duration, mixMode, subtitle, bgmPath, d.intro_video_path, d.outro_video_path]) === 0) {
    return null;
  }

  return (
    <PhaseShell
      icon={Clapperboard}
      title="Final Mux"
      tone="from-cyan-400/35 via-cyan-400/10 to-transparent"
      meta={mixMode ?? undefined}
    >
      <div className="grid gap-2 sm:grid-cols-3">
        {duration != null && <Metric label="Final Duration" value={formatDuration(duration)} />}
        {d.bgm_volume != null && <Metric label="BGM Volume" value={d.bgm_volume.toFixed(2)} />}
        {d.intro_outro_backend && <Metric label="Intro/Outro" value={d.intro_outro_backend} />}
      </div>
      {finalVideo && <TextBlock icon={Clapperboard}><code className="text-cyan-100/65">{finalVideo}</code></TextBlock>}
      {subtitle && <TextBlock icon={ListChecks}><code>{subtitle}</code></TextBlock>}
      {bgmPath && <TextBlock icon={Music2}><code>{bgmPath}</code></TextBlock>}
      <PillList items={[d.intro_video_path, d.outro_video_path].filter(hasText)} />
    </PhaseShell>
  );
}

export function PipelinePhaseCards({ pipelineOutput }: PipelinePhaseCardsProps) {
  if (!pipelineOutput) return null;

  const sections = [
    <PlanningSection key="planning" d={pipelineOutput} />,
    <ImplementationSection key="implementation" d={pipelineOutput} />,
    <ReviewSection key="review" d={pipelineOutput} />,
    <NarrationSection key="narration" d={pipelineOutput} />,
    <AudioSection key="audio" d={pipelineOutput} />,
    <MuxSection key="mux" d={pipelineOutput} />,
  ].filter(Boolean);

  if (sections.length === 0) return null;

  return (
    <div className="gsap-plan-card relative flex aspect-video w-full flex-col overflow-hidden rounded-xl border border-cyan-500/10 bg-black/50 shadow-2xl ring-1 ring-cyan-500/8 backdrop-blur-xl xl:aspect-auto xl:min-h-0 xl:flex-1">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-400/30 to-transparent" />
      <div className="flex shrink-0 items-center justify-between border-b border-white/[0.05] px-4 py-2.5">
        <div className="flex items-center gap-2 text-cyan-400/65">
          <ListVideo className="h-4 w-4" />
          <h2 className="text-[11px] font-mono uppercase tracking-widest">Structured Output</h2>
        </div>
        <span className="text-[9px] font-mono text-white/28">{sections.length} phases</span>
      </div>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto custom-scrollbar p-3">
        {sections}
      </div>
    </div>
  );
}
