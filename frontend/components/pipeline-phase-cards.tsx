"use client";

import { Fragment, useRef, type ElementType, type ReactNode } from "react";
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
import { gsap, useGSAP } from "@/lib/gsap";
import { usePrefersReducedMotion } from "@/lib/motion";

interface PipelinePhaseCardsProps {
  pipelineOutput: PipelineOutputData | null;
  variant?: "panel" | "embedded";
}

type PhaseSurface = "panel" | "embedded";

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
  surface = "embedded",
}: {
  icon: ElementType;
  title: string;
  meta?: ReactNode;
  tone: string;
  children: ReactNode;
  surface?: PhaseSurface;
}) {
  if (surface === "panel") {
    return (
      <section data-pipeline-phase className="border-t border-white/[0.055] py-3 first:border-t-0 first:pt-0 last:pb-0">
        <div className="mb-2 flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2">
            <Icon className="h-3.5 w-3.5 shrink-0 text-cyan-400/42" />
            <h3 className="truncate text-[10px] font-mono uppercase tracking-widest text-white/50">
              {title}
            </h3>
          </div>
          {meta && <div className="shrink-0 text-[9px] font-mono text-white/28">{meta}</div>}
        </div>
        <div className="space-y-2">{children}</div>
      </section>
    );
  }

  return (
    <section data-pipeline-phase className="rounded-lg border border-white/[0.06] bg-white/[0.025] overflow-hidden">
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

function Metric({
  label,
  value,
  surface = "embedded",
}: {
  label: string;
  value: ReactNode;
  surface?: PhaseSurface;
}) {
  if (surface === "panel") {
    return (
      <div className="min-w-0">
        <div className="text-[9px] font-mono uppercase tracking-widest text-white/24">{label}</div>
        <div className="mt-0.5 truncate text-[11px] text-white/58">{value}</div>
      </div>
    );
  }

  return (
    <div className="min-w-0 rounded-md border border-white/[0.04] bg-black/20 px-2.5 py-2">
      <div className="text-[9px] font-mono uppercase tracking-widest text-white/24">{label}</div>
      <div className="mt-1 truncate text-[11px] text-white/62">{value}</div>
    </div>
  );
}

function TextBlock({
  icon: Icon,
  children,
  surface = "embedded",
}: {
  icon?: ElementType;
  children: ReactNode;
  surface?: PhaseSurface;
}) {
  if (surface === "panel") {
    return (
      <div className="flex min-w-0 gap-2">
        {Icon && <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-white/24" />}
        <div className="min-w-0 text-[11px] leading-relaxed text-white/50">{children}</div>
      </div>
    );
  }

  return (
    <div className="flex min-w-0 gap-2 rounded-md border border-white/[0.04] bg-black/18 px-2.5 py-2">
      {Icon && <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-white/28" />}
      <div className="min-w-0 text-[11px] leading-relaxed text-white/54">{children}</div>
    </div>
  );
}

function PillList({
  items,
  tone = "bg-white/[0.04] text-white/45",
  limit = 8,
}: {
  items: string[];
  tone?: string;
  limit?: number;
}) {
  if (items.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.slice(0, limit).map((item, index) => (
        <span key={`${item}-${index}`} className={`rounded-md px-2 py-1 text-[10px] ${tone}`}>
          {item}
        </span>
      ))}
      {items.length > limit && (
        <span className="rounded-md bg-white/[0.03] px-2 py-1 text-[10px] text-white/25">
          +{items.length - limit}
        </span>
      )}
    </div>
  );
}

function PlanningSection({ d, surface = "embedded" }: { d: PipelineOutputData; surface?: PhaseSurface }) {
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
      surface={surface}
    >
      <div className="grid gap-2 sm:grid-cols-3">
        {spec?.mode && <Metric label="Mode" value={spec.mode} surface={surface} />}
        {spec?.target_duration_seconds != null && (
          <Metric label="Target" value={formatDuration(spec.target_duration_seconds)} surface={surface} />
        )}
        {beatTotal > 0 && <Metric label="Beat Sum" value={formatDuration(beatTotal)} surface={surface} />}
      </div>

      {spec?.learning_goal && (
        <TextBlock icon={Target} surface={surface}>{spec.learning_goal}</TextBlock>
      )}
      {spec?.audience && (
        <TextBlock icon={Users} surface={surface}>{spec.audience}</TextBlock>
      )}
      {surface === "embedded" && d.plan_text && (
        <TextBlock icon={Route} surface={surface}>
          <p className="line-clamp-3">{d.plan_text}</p>
        </TextBlock>
      )}

      {beats.length > 0 && (
        <div className="space-y-1.5">
          {beats.slice(0, surface === "panel" ? 5 : 6).map((beat, index) => {
            const required = "required_elements" in beat ? beat.required_elements ?? [] : [];
            return (
              <div key={beat.id ?? index} className={surface === "panel" ? "px-0 py-1.5" : "rounded-md border border-white/[0.04] bg-black/16 px-2.5 py-2"}>
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
                    <PillList items={required} limit={surface === "panel" ? 3 : 8} />
                  </div>
                </div>
              </div>
            );
          })}
          {surface === "panel" && beats.length > 5 && (
            <div className="pl-7 text-[10px] font-mono text-white/25">
              +{beats.length - 5} beats in Report
            </div>
          )}
        </div>
      )}
    </PhaseShell>
  );
}

function ImplementationSection({ d, surface = "embedded" }: { d: PipelineOutputData; surface?: PhaseSurface }) {
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
      surface={surface}
    >
      <div className="grid gap-2 sm:grid-cols-3">
        {sceneClass && <Metric label="Scene" value={<code className="text-violet-200/75">{sceneClass}</code>} surface={surface} />}
        {sceneFile && <Metric label="File" value={sceneFile} surface={surface} />}
        {segmentPaths.length > 0 && <Metric label="Segments" value={segmentPaths.length} surface={surface} />}
      </div>

      {summary && <TextBlock icon={Sparkles} surface={surface}>{summary}</TextBlock>}
      <PillList items={implemented} tone="bg-violet-500/[0.08] text-violet-100/58" />

      {deviations.length > 0 && (
        <div className="space-y-1">
          {deviations.map((item, index) => (
            <TextBlock key={`${item}-${index}`} icon={AlertTriangle} surface={surface}>
              <span className="text-amber-200/58">{item}</span>
            </TextBlock>
          ))}
        </div>
      )}
    </PhaseShell>
  );
}

function ReviewSection({ d, surface = "embedded" }: { d: PipelineOutputData; surface?: PhaseSurface }) {
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
      surface={surface}
    >
      {summary && <TextBlock icon={Film} surface={surface}>{summary}</TextBlock>}
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

function NarrationSection({ d, surface = "embedded" }: { d: PipelineOutputData; surface?: PhaseSurface }) {
  const map = d.beat_to_narration_map ?? [];
  if (!d.narration && map.length === 0 && d.narration_coverage_complete == null) return null;

  return (
    <PhaseShell
      icon={Mic}
      title="Narration"
      tone="from-orange-400/35 via-orange-400/10 to-transparent"
      meta={d.narration_coverage_complete == null ? undefined : d.narration_coverage_complete ? "covered" : "partial"}
      surface={surface}
    >
      {d.narration && (
        <TextBlock icon={Mic} surface={surface}>
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
        <Metric label="Estimated Duration" value={formatDuration(d.estimated_narration_duration_seconds)} surface={surface} />
      )}
    </PhaseShell>
  );
}

function AudioSection({ d, surface = "embedded" }: { d: PipelineOutputData; surface?: PhaseSurface }) {
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
      surface={surface}
    >
      <div className="grid gap-2 sm:grid-cols-3">
        {ttsMode && <Metric label="TTS Mode" value={ttsMode} surface={surface} />}
        {ttsDuration != null && <Metric label="Voice Length" value={formatMs(ttsDuration)} surface={surface} />}
        {usage != null && <Metric label="Usage" value={`${usage} chars`} surface={surface} />}
      </div>
      {audioPath && <TextBlock icon={Volume2} surface={surface}><code className="text-sky-100/65">{audioPath}</code></TextBlock>}
      {d.timeline_total_duration_seconds != null && (
        <Metric label="Timeline" value={formatDuration(d.timeline_total_duration_seconds)} surface={surface} />
      )}
      {d.bgm_path && (
        <TextBlock icon={Music2} surface={surface}>
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

function MuxSection({ d, surface = "embedded" }: { d: PipelineOutputData; surface?: PhaseSurface }) {
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
      surface={surface}
    >
      <div className="grid gap-2 sm:grid-cols-3">
        {duration != null && <Metric label="Final Duration" value={formatDuration(duration)} surface={surface} />}
        {d.bgm_volume != null && <Metric label="BGM Volume" value={d.bgm_volume.toFixed(2)} surface={surface} />}
        {d.intro_outro_backend && <Metric label="Intro/Outro" value={d.intro_outro_backend} surface={surface} />}
      </div>
      {finalVideo && <TextBlock icon={Clapperboard} surface={surface}><code className="text-cyan-100/65">{finalVideo}</code></TextBlock>}
      {subtitle && <TextBlock icon={ListChecks} surface={surface}><code>{subtitle}</code></TextBlock>}
      {bgmPath && <TextBlock icon={Music2} surface={surface}><code>{bgmPath}</code></TextBlock>}
      <PillList items={[d.intro_video_path, d.outro_video_path].filter(hasText)} />
    </PhaseShell>
  );
}

export function PipelinePhaseCards({ pipelineOutput, variant = "panel" }: PipelinePhaseCardsProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const reduceMotion = usePrefersReducedMotion();

  useGSAP(() => {
    if (!rootRef.current) return;

    const phases = rootRef.current.querySelectorAll<HTMLElement>("[data-pipeline-phase]");
    if (reduceMotion) {
      gsap.set(phases, { opacity: 1, y: 0, filter: "none" });
      return;
    }

    gsap.fromTo(
      phases,
      { opacity: 0, y: 12, filter: "blur(6px)" },
      {
        opacity: 1,
        y: 0,
        filter: "blur(0px)",
        duration: 0.46,
        ease: "power3.out",
        stagger: 0.07,
      },
    );
  }, { scope: rootRef, dependencies: [pipelineOutput, variant, reduceMotion] });

  if (!pipelineOutput) return null;

  const sections = [
    PlanningSection({ d: pipelineOutput, surface: variant }),
    ImplementationSection({ d: pipelineOutput, surface: variant }),
    ReviewSection({ d: pipelineOutput, surface: variant }),
    NarrationSection({ d: pipelineOutput, surface: variant }),
    AudioSection({ d: pipelineOutput, surface: variant }),
    MuxSection({ d: pipelineOutput, surface: variant }),
  ].filter(Boolean);

  if (sections.length === 0) return null;

  const renderedSections = sections.map((section, index) => (
    <Fragment key={index}>{section}</Fragment>
  ));

  if (variant === "embedded") {
    return (
      <div ref={rootRef} className="space-y-3">
        {renderedSections}
      </div>
    );
  }

  return (
    <div ref={rootRef} className="gsap-plan-card flex aspect-video w-full flex-col overflow-hidden rounded-lg bg-black/18 xl:aspect-auto xl:min-h-0 xl:flex-1">
      <div className="flex shrink-0 items-center justify-between border-b border-white/[0.045] px-1 pb-2">
        <div className="flex items-center gap-2 text-cyan-400/58">
          <ListVideo className="h-4 w-4" />
          <h2 className="text-[11px] font-mono uppercase tracking-widest">Pipeline Progress</h2>
        </div>
        <span className="text-[9px] font-mono text-white/25">{sections.length} phases</span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto custom-scrollbar px-1 py-3">{renderedSections}</div>
    </div>
  );
}
