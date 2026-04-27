"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Bug,
  CheckCircle2,
  ClipboardList,
  Copy,
  Database,
  FileText,
  Loader2,
  MessageSquarePlus,
  RefreshCw,
  Search,
  Trash2,
  XCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  createDebugIssue,
  deleteDebugIssue,
  getDebugPromptArtifact,
  getDebugPromptIndex,
  getTask,
  getVideoUrl,
  listDebugIssues,
} from "@/lib/api";
import type { DebugIssue, DebugPromptArtifact, DebugPromptPhaseSummary, Task } from "@/types";

type PromptTab = "system" | "user" | "inputs" | "options" | "output";
type OutputView = "readable" | "json";

const ISSUE_TYPES = [
  { value: "提示词", label: "提示词" },
  { value: "结构化输出", label: "结构化输出" },
  { value: "脚本结构", label: "脚本结构" },
  { value: "渲染执行", label: "渲染执行" },
  { value: "视觉质量", label: "视觉质量" },
  { value: "解说文案", label: "解说文案" },
  { value: "语音合成", label: "语音合成" },
  { value: "音视频合成", label: "音视频合成" },
  { value: "基础设施", label: "基础设施" },
  { value: "前端界面", label: "前端界面" },
  { value: "产品体验", label: "产品体验" },
  { value: "其他", label: "其他" },
];

const LEGACY_ISSUE_TYPE_LABELS: Record<string, string> = {
  prompt: "提示词",
  schema: "结构化输出",
  script_structure: "脚本结构",
  render: "渲染执行",
  visual_quality: "视觉质量",
  narration: "解说文案",
  tts: "语音合成",
  audio_mux: "音视频合成",
  infra: "基础设施",
  frontend: "前端界面",
  product: "产品体验",
  other: "其他",
};

const SEVERITIES = [
  { value: "low", label: "低" },
  { value: "medium", label: "中" },
  { value: "high", label: "高" },
  { value: "blocker", label: "阻塞" },
];

const SEVERITY_LABELS: Record<string, string> = {
  low: "低",
  medium: "中",
  high: "高",
  blocker: "阻塞",
};
const PHASE_ORDER: Record<string, number> = {
  phase1: 10,
  phase2a: 20,
  phase2b: 21,
  phase3: 30,
  phase3_5: 35,
  phase4: 40,
  phase5: 50,
};

function formatJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

function isEmptyRecord(value: unknown) {
  return (
    value == null ||
    (typeof value === "object" && !Array.isArray(value) && Object.keys(value).length === 0)
  );
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asString(value: unknown) {
  return typeof value === "string" ? value : "";
}

function firstRecord(...values: unknown[]) {
  for (const value of values) {
    const record = asRecord(value);
    if (Object.keys(record).length > 0) return record;
  }
  return {};
}

function metricLabel(phase: DebugPromptPhaseSummary | null) {
  const metrics = phase?.metrics ?? {};
  const tokens = typeof metrics.approx_tokens === "number" ? metrics.approx_tokens : 0;
  const chars =
    (typeof metrics.system_prompt_chars === "number" ? metrics.system_prompt_chars : 0) +
    (typeof metrics.user_prompt_chars === "number" ? metrics.user_prompt_chars : 0);
  return `${chars.toLocaleString()} chars / ~${tokens.toLocaleString()} tokens`;
}

function phaseNumberLabel(phaseId: string) {
  const normalized = phaseId.replace(/^phase/i, "").replace("_", ".");
  return normalized ? normalized.toUpperCase() : phaseId.toUpperCase();
}

function phaseStatus(phase: DebugPromptPhaseSummary) {
  if (phase.error || phase.status === "failed") return "failed";
  if (phase.status === "completed") return "completed";
  return "started";
}

function phaseStatusLabel(status: string) {
  if (status === "completed") return "completed";
  if (status === "failed") return "failed";
  return "waiting";
}

function issueTypeLabel(type: string) {
  return LEGACY_ISSUE_TYPE_LABELS[type] ?? type;
}

function severityLabel(value: string) {
  return SEVERITY_LABELS[value] ?? value;
}

function highlightText(value: string, query: string) {
  if (!query.trim()) return value;
  const escaped = query.trim().replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const parts = value.split(new RegExp(`(${escaped})`, "gi"));
  return parts.map((part, index) =>
    part.toLowerCase() === query.trim().toLowerCase() ? (
      <mark key={`${part}-${index}`} className="rounded bg-cyan-400/20 px-0.5 text-cyan-100">
        {part}
      </mark>
    ) : (
      part
    ),
  );
}

function PromptBlock({
  value,
  searchQuery,
  emptyMessage,
  onSelectText,
}: {
  value: string;
  searchQuery: string;
  emptyMessage: string;
  onSelectText: (value: string) => void;
}) {
  function handleMouseUp() {
    const selected = window.getSelection()?.toString().trim() ?? "";
    onSelectText(selected.slice(0, 1200));
  }

  return (
    <pre
      onMouseUp={handleMouseUp}
      className="h-full min-h-[28rem] overflow-auto whitespace-pre-wrap rounded-lg border border-white/8 bg-black/35 p-4 font-mono text-[11px] leading-relaxed text-white/72 custom-scrollbar"
    >
      {value ? highlightText(value, searchQuery) : emptyMessage}
    </pre>
  );
}

function InfoPill({ label, value }: { label: string; value: unknown }) {
  if (value == null || value === "") return null;
  return (
    <span className="font-mono text-[10px] text-white/38">
      {label}: <span className="text-white/68">{String(value)}</span>
    </span>
  );
}

function TextList({ items }: { items: unknown[] }) {
  if (items.length === 0) return null;
  return (
    <ul className="space-y-1.5">
      {items.map((item, index) => (
        <li key={index} className="flex gap-2 text-sm leading-relaxed text-white/62">
          <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-cyan-300/55" />
          <span>{String(item)}</span>
        </li>
      ))}
    </ul>
  );
}

function SummarySection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border-t border-white/8 py-4 first:border-t-0 first:pt-0">
      <h3 className="font-mono text-[10px] uppercase tracking-widest text-cyan-300/70">
        {title}
      </h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function Phase1Readable({ snapshot }: { snapshot: Record<string, unknown> }) {
  const buildSpec = firstRecord(asRecord(snapshot.phase1_planning).build_spec, snapshot.build_spec);
  const beats = asArray(buildSpec.beats);
  return (
    <div className="h-full overflow-auto rounded-lg border border-white/8 bg-black/20 px-5 py-4 custom-scrollbar">
      <div className="flex flex-wrap gap-x-5 gap-y-2 border-b border-white/8 pb-3">
        <InfoPill label="Mode" value={buildSpec.mode} />
        <InfoPill label="Audience" value={buildSpec.audience} />
        <InfoPill label="Target" value={`${buildSpec.target_duration_seconds ?? "?"}s`} />
      </div>
      <div className="mt-4">
        <SummarySection title="Learning Goal">
          <p className="text-sm leading-relaxed text-white/68">
            {asString(buildSpec.learning_goal) || "No learning goal captured."}
          </p>
        </SummarySection>
        <SummarySection title={`Beat Plan (${beats.length})`}>
          <div className="divide-y divide-white/8">
            {beats.map((rawBeat, index) => {
              const beat = asRecord(rawBeat);
              return (
                <div key={`${beat.id ?? index}`} className="py-4 first:pt-0 last:pb-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-[10px] text-cyan-300/70">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <h4 className="text-sm font-semibold text-white/82">
                      {asString(beat.title) || asString(beat.id) || "Untitled beat"}
                    </h4>
                    {beat.target_duration_seconds != null && (
                      <span className="ml-auto font-mono text-[10px] text-white/35">
                        {String(beat.target_duration_seconds)}s
                      </span>
                    )}
                  </div>
                  <p className="mt-3 text-sm leading-relaxed text-white/62">
                    {asString(beat.visual_goal)}
                  </p>
                  <p className="mt-2 text-xs leading-relaxed text-white/44">
                    {asString(beat.narration_intent)}
                  </p>
                  <div className="mt-2 text-xs leading-relaxed text-white/34">
                    {asArray(beat.required_elements).join(" / ")}
                  </div>
                </div>
              );
            })}
          </div>
        </SummarySection>
      </div>
    </div>
  );
}

function Phase2Readable({ snapshot }: { snapshot: Record<string, unknown> }) {
  const output = firstRecord(snapshot.draft_output, snapshot.pipeline_output);
  const analysis = firstRecord(snapshot.draft_analysis, snapshot.phase2_analysis);
  return (
    <div className="h-full overflow-auto rounded-lg border border-white/8 bg-black/20 px-5 py-4 custom-scrollbar">
      <div className="flex flex-wrap gap-x-5 gap-y-2 border-b border-white/8 pb-3">
        <InfoPill label="Scene File" value={output.scene_file} />
        <InfoPill label="Scene Class" value={output.scene_class} />
        <InfoPill label="Estimated" value={output.estimated_duration_seconds ? `${output.estimated_duration_seconds}s` : null} />
      </div>
      <div className="mt-4">
        <SummarySection title="Build Summary">
          <p className="text-sm leading-relaxed text-white/68">
            {asString(output.build_summary) || "No build summary captured yet."}
          </p>
        </SummarySection>
        <SummarySection title="Implemented Beats">
          <TextList items={asArray(output.implemented_beats)} />
        </SummarySection>
        <SummarySection title="Analysis">
          <div className="flex flex-wrap gap-x-5 gap-y-2">
            <InfoPill label="Accepted" value={analysis.accepted == null ? null : String(analysis.accepted)} />
            <InfoPill label="Analysis Path" value={snapshot.analysis_path} />
          </div>
          <div className="mt-3">
            <TextList items={asArray(analysis.issues)} />
          </div>
        </SummarySection>
      </div>
    </div>
  );
}

function Phase3Readable({ snapshot }: { snapshot: Record<string, unknown> }) {
  const review = firstRecord(snapshot.review_output);
  return (
    <div className="h-full overflow-auto rounded-lg border border-white/8 bg-black/20 px-5 py-4 custom-scrollbar">
      <div className="flex flex-wrap gap-x-5 gap-y-2 border-b border-white/8 pb-3">
        <InfoPill label="Approved" value={review.approved == null ? null : String(review.approved)} />
        <InfoPill label="Frames" value={asArray(review.frame_analyses).length || null} />
      </div>
      <div className="mt-4">
        <SummarySection title="Review Summary">
          <p className="text-sm leading-relaxed text-white/68">
            {asString(review.summary) || "No review summary captured yet."}
          </p>
        </SummarySection>
        <SummarySection title="Blocking Issues">
          <TextList items={asArray(review.blocking_issues)} />
        </SummarySection>
        <SummarySection title="Suggested Edits">
          <TextList items={asArray(review.suggested_edits)} />
        </SummarySection>
      </div>
    </div>
  );
}

function NarrationReadable({ snapshot }: { snapshot: Record<string, unknown> }) {
  const narration = firstRecord(snapshot.narration_output);
  return (
    <div className="h-full overflow-auto rounded-lg border border-white/8 bg-black/20 px-5 py-4 custom-scrollbar">
      <div className="flex flex-wrap gap-x-5 gap-y-2 border-b border-white/8 pb-3">
        <InfoPill label="Method" value={narration.generation_method} />
        <InfoPill label="Chars" value={narration.char_count} />
      </div>
      <div className="mt-4">
        <SummarySection title="Narration">
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-white/68">
            {asString(snapshot.narration_text) || asString(narration.narration)}
          </p>
        </SummarySection>
        <SummarySection title="Beat Coverage">
          <TextList items={asArray(narration.beat_coverage)} />
        </SummarySection>
      </div>
    </div>
  );
}

function AudioReadable({ snapshot }: { snapshot: Record<string, unknown> }) {
  return (
    <div className="h-full overflow-auto rounded-lg border border-white/8 bg-black/20 px-5 py-4 custom-scrollbar">
      <div className="flex flex-wrap gap-x-5 gap-y-2 border-b border-white/8 pb-3">
        <InfoPill label="Segments" value={asArray(snapshot.beats).length || null} />
        <InfoPill label="Timeline" value={snapshot.timeline_total_duration_seconds ? `${snapshot.timeline_total_duration_seconds}s` : null} />
        <InfoPill label="Mix" value={snapshot.audio_mix_mode} />
      </div>
      <div className="mt-4">
        <SummarySection title="Generated Assets">
          <TextList
            items={[
              snapshot.audio_concat_path && `audio: ${snapshot.audio_concat_path}`,
              snapshot.subtitle_path && `subtitle: ${snapshot.subtitle_path}`,
              snapshot.bgm_path && `bgm: ${snapshot.bgm_path}`,
            ].filter(Boolean)}
          />
        </SummarySection>
      </div>
    </div>
  );
}

function MuxReadable({ snapshot }: { snapshot: Record<string, unknown> }) {
  return (
    <div className="h-full overflow-auto rounded-lg border border-white/8 bg-black/20 px-5 py-4 custom-scrollbar">
      <div className="flex flex-wrap gap-x-5 gap-y-2 border-b border-white/8 pb-3">
        <InfoPill label="Segment Visuals" value={snapshot.used_segment_visuals == null ? null : String(snapshot.used_segment_visuals)} />
        <InfoPill label="Segments" value={asArray(snapshot.segment_video_paths).length || null} />
      </div>
      <div className="mt-4">
        <SummarySection title="Final Video">
          <p className="break-all font-mono text-xs leading-relaxed text-white/62">
            {asString(snapshot.final_video_output) || "No final video captured yet."}
          </p>
        </SummarySection>
      </div>
    </div>
  );
}

function GenericReadable({ snapshot }: { snapshot: Record<string, unknown> }) {
  return (
    <div className="h-full overflow-auto rounded-lg border border-white/8 bg-black/20 px-5 py-4 custom-scrollbar">
      <div className="divide-y divide-white/8">
        {Object.entries(snapshot).map(([key, value]) => (
          <div key={key} className="py-3 first:pt-0 last:pb-0">
            <div className="font-mono text-[9px] uppercase tracking-widest text-white/32">
              {key}
            </div>
            <pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-white/62 custom-scrollbar">
              {typeof value === "string" ? value : formatJson(value)}
            </pre>
          </div>
        ))}
      </div>
    </div>
  );
}

function ReadableOutput({
  artifact,
  emptyMessage,
}: {
  artifact: DebugPromptArtifact | null;
  emptyMessage: string;
}) {
  const snapshot = asRecord(artifact?.output_snapshot);
  if (isEmptyRecord(snapshot)) {
    return (
      <div className="flex h-full min-h-[28rem] items-center justify-center rounded-lg border border-white/8 bg-black/25 p-6 text-center text-sm leading-relaxed text-white/45">
        {emptyMessage}
      </div>
    );
  }
  if (artifact?.phase_id === "phase1") {
    return <Phase1Readable snapshot={snapshot} />;
  }
  if (artifact?.phase_id === "phase2a" || artifact?.phase_id === "phase2b") {
    return <Phase2Readable snapshot={snapshot} />;
  }
  if (artifact?.phase_id === "phase3") {
    return <Phase3Readable snapshot={snapshot} />;
  }
  if (artifact?.phase_id === "phase3_5") {
    return <NarrationReadable snapshot={snapshot} />;
  }
  if (artifact?.phase_id === "phase4") {
    return <AudioReadable snapshot={snapshot} />;
  }
  if (artifact?.phase_id === "phase5") {
    return <MuxReadable snapshot={snapshot} />;
  }
  return <GenericReadable snapshot={snapshot} />;
}

function buildTaskResultPhase(task: Task): DebugPromptPhaseSummary {
  return {
    phase_id: "pipeline_output",
    phase_name: "Task Result Snapshot",
    created_at: task.completed_at ?? task.created_at,
    artifact_path: "task.pipeline_output",
    metrics: {
      system_prompt_chars: 0,
      user_prompt_chars: 0,
      approx_tokens: 0,
    },
    error: task.error,
    status: task.error ? "failed" : "completed",
  };
}

function buildTaskResultArtifact(task: Task): DebugPromptArtifact {
  return {
    task_id: task.id,
    phase_id: "pipeline_output",
    phase_name: "Task Result Snapshot",
    created_at: task.completed_at ?? task.created_at,
    inputs: {
      user_text: task.user_text,
      options: task.options,
    },
    system_prompt: "",
    user_prompt: "",
    options: asRecord(task.options),
    referenced_artifacts: {},
    output_snapshot: asRecord(task.pipeline_output),
    error: task.error,
    status: task.error ? "failed" : "completed",
    metrics: {
      system_prompt_chars: 0,
      user_prompt_chars: 0,
      approx_tokens: 0,
    },
  };
}

export default function TaskDebugClient() {
  const params = useParams();
  const taskId = params.id as string;
  const [task, setTask] = useState<Task | null>(null);
  const [phases, setPhases] = useState<DebugPromptPhaseSummary[]>([]);
  const [selectedPhaseId, setSelectedPhaseId] = useState<string | null>(null);
  const [artifact, setArtifact] = useState<DebugPromptArtifact | null>(null);
  const [issues, setIssues] = useState<DebugIssue[]>([]);
  const [tab, setTab] = useState<PromptTab>("user");
  const [loading, setLoading] = useState(true);
  const [artifactLoading, setArtifactLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [debugNotice, setDebugNotice] = useState<string | null>(null);
  const [savingIssue, setSavingIssue] = useState(false);
  const [issueTitle, setIssueTitle] = useState("");
  const [issueType, setIssueType] = useState("提示词");
  const [severity, setSeverity] = useState("medium");
  const [description, setDescription] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedText, setSelectedText] = useState("");
  const [copied, setCopied] = useState(false);
  const [outputView, setOutputView] = useState<OutputView>("readable");
  const [openIssueId, setOpenIssueId] = useState<string | null>(null);
  const [deletingIssueId, setDeletingIssueId] = useState<string | null>(null);

  const sortedPhases = useMemo(
    () =>
      [...phases].sort(
        (a, b) =>
          (PHASE_ORDER[a.phase_id] ?? 999) - (PHASE_ORDER[b.phase_id] ?? 999) ||
          a.phase_id.localeCompare(b.phase_id),
      ),
    [phases],
  );

  const selectedPhase = useMemo(
    () => sortedPhases.find((phase) => phase.phase_id === selectedPhaseId) ?? null,
    [selectedPhaseId, sortedPhases],
  );

  const loadDebug = useCallback(async () => {
    setLoading(true);
    setError(null);
    setDebugNotice(null);
    try {
      const [taskData, issueData] = await Promise.all([
        getTask(taskId),
        listDebugIssues(taskId),
      ]);
      let promptPhases: DebugPromptPhaseSummary[] = [];
      try {
        const promptIndex = await getDebugPromptIndex(taskId);
        promptPhases = promptIndex.phases;
      } catch (promptErr) {
        if (!taskData.pipeline_output) {
          throw promptErr;
        }
        promptPhases = [buildTaskResultPhase(taskData)];
        setDebugNotice(
          "Prompt artifacts are missing for this task. Showing the persisted task result snapshot instead.",
        );
      }
      setTask(taskData);
      setPhases(promptPhases);
      setIssues(issueData);
      setSelectedPhaseId((current) =>
        promptPhases.some((phase) => phase.phase_id === current)
          ? current
          : (promptPhases[0]?.phase_id ?? null),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load debug data.");
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    if (!taskId) return;
    void loadDebug();
  }, [loadDebug, taskId]);

  useEffect(() => {
    if (!taskId || !selectedPhaseId) {
      setArtifact(null);
      return;
    }
    if (selectedPhaseId === "pipeline_output" && task?.pipeline_output) {
      setArtifactLoading(false);
      setArtifact(buildTaskResultArtifact(task));
      return;
    }
    setArtifactLoading(true);
    getDebugPromptArtifact(taskId, selectedPhaseId)
      .then((data) => setArtifact(data))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load artifact."))
      .finally(() => setArtifactLoading(false));
  }, [selectedPhaseId, task, taskId]);

  useEffect(() => {
    setSearchQuery("");
    setSelectedText("");
    setCopied(false);
  }, [selectedPhaseId, tab]);

  async function handleCreateIssue() {
    if (!issueTitle.trim() || !description.trim()) return;
    setSavingIssue(true);
    try {
      const created = await createDebugIssue(taskId, {
        phase_id: selectedPhaseId,
        title: issueTitle.trim(),
        description: description.trim(),
        issue_type: issueType,
        severity,
        status: "open",
        source: "manual",
        prompt_artifact_path: selectedPhase?.artifact_path ?? null,
        metadata: {
          active_tab: tab,
          phase_name: selectedPhase?.phase_name ?? null,
          selected_text: selectedText || null,
          task_status: task?.status ?? null,
        },
      });
      setIssues((prev) => [created, ...prev]);
      setOpenIssueId(created.id);
      setIssueTitle("");
      setDescription("");
    } finally {
      setSavingIssue(false);
    }
  }

  async function handleDeleteIssue(issueId: string) {
    const confirmed = window.confirm("Delete this issue?");
    if (!confirmed) return;
    setDeletingIssueId(issueId);
    setError(null);
    try {
      await deleteDebugIssue(issueId);
      setIssues((prev) => prev.filter((issue) => issue.id !== issueId));
      setOpenIssueId((current) => (current === issueId ? null : current));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete debug issue.");
    } finally {
      setDeletingIssueId(null);
    }
  }

  async function handleCopyTab() {
    if (!tabValue) return;
    await navigator.clipboard.writeText(tabValue);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  const tabValue =
    tab === "system"
      ? artifact?.system_prompt ?? ""
      : tab === "user"
        ? artifact?.user_prompt ?? ""
        : tab === "inputs"
          ? formatJson(artifact?.inputs)
          : tab === "options"
            ? formatJson(artifact?.options)
            : isEmptyRecord(artifact?.output_snapshot)
              ? ""
              : formatJson(artifact?.output_snapshot);

  const outputEmptyMessage =
    artifact?.status === "started"
      ? "Waiting for this phase to finish. Output will appear after the pipeline writes the completion snapshot."
      : artifact?.status === "failed"
        ? artifact.error || "This phase failed before producing an output snapshot."
        : "No output snapshot was captured for this phase.";

  return (
    <main className="h-[var(--app-content-height)] overflow-hidden">
      <div className="mx-auto flex h-full max-w-[1800px] flex-col gap-4 px-4 py-4 md:px-8">
        <header className="flex shrink-0 items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <Link
              href={`/tasks/${taskId}`}
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 bg-white/[0.03] text-white/60 hover:bg-white/[0.08] hover:text-white"
            >
              <ArrowLeft className="h-4 w-4" />
            </Link>
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.22em] text-cyan-400/70">
                <Bug className="h-3.5 w-3.5" />
                Task Debug
              </div>
              <h1 className="mt-1 truncate font-mono text-lg text-white/85">{taskId}</h1>
              {task && (
                <div className="mt-1 truncate font-mono text-[10px] text-white/34">
                  created {new Date(task.created_at).toLocaleString()} / target{" "}
                  {task.options.target_duration_seconds}s
                  {task.error ? ` / ${task.error}` : ""}
                </div>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3">
            {task && (
              <span className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 font-mono text-[10px] uppercase tracking-wider text-white/52">
                {task.status}
              </span>
            )}
            {task?.pipeline_output?.final_video_output && (
              <Link
                href={getVideoUrl(task.id, task.video_path ?? task.pipeline_output.final_video_output)}
                target="_blank"
                className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 font-mono text-[10px] uppercase tracking-wider text-cyan-300/70 hover:bg-white/[0.08]"
              >
                Final Video
              </Link>
            )}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void loadDebug()}
              className="border-white/10 bg-white/[0.03] text-white/65 hover:bg-white/[0.08]"
            >
              <RefreshCw className="mr-2 h-3.5 w-3.5" />
              Refresh
            </Button>
          </div>
        </header>

        {error && (
          <div className="shrink-0 rounded-xl border border-red-500/20 bg-red-500/[0.05] px-4 py-3 text-sm text-red-200/80">
            {error}
          </div>
        )}
        {debugNotice && (
          <div className="shrink-0 rounded-xl border border-amber-400/18 bg-amber-400/[0.045] px-4 py-3 text-sm text-amber-100/72">
            {debugNotice}
          </div>
        )}

        {loading ? (
          <div className="flex flex-1 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-cyan-300/70" />
          </div>
        ) : (
          <div className="grid min-h-0 flex-1 grid-cols-[280px_minmax(0,1fr)_360px] gap-4">
            <aside className="min-h-0 overflow-hidden rounded-xl border border-white/8 bg-white/[0.025]">
              <div className="border-b border-white/8 px-4 py-3">
                <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-white/45">
                  <ClipboardList className="h-3.5 w-3.5" />
                  Phases
                </div>
              </div>
              <div className="h-full overflow-auto p-2 custom-scrollbar">
                {sortedPhases.map((phase) => {
                  const status = phaseStatus(phase);
                  return (
                  <button
                    key={phase.phase_id}
                    type="button"
                    onClick={() => setSelectedPhaseId(phase.phase_id)}
                    className={`mb-2 flex w-full items-start gap-3 rounded-lg border px-3 py-3 text-left transition ${
                      selectedPhaseId === phase.phase_id
                        ? "border-cyan-400/25 bg-cyan-500/[0.08]"
                        : "border-white/6 bg-black/15 hover:border-white/12 hover:bg-white/[0.04]"
                    }`}
                  >
                    <span
                      className={`mt-0.5 flex h-6 w-7 shrink-0 items-center justify-center rounded-md border font-mono text-[10px] ${
                        selectedPhaseId === phase.phase_id
                          ? "border-cyan-400/25 bg-cyan-500/10 text-cyan-300/80"
                          : "border-white/8 bg-white/[0.03] text-white/38"
                      }`}
                    >
                      {phaseNumberLabel(phase.phase_id)}
                    </span>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span
                          className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                            status === "completed"
                              ? "bg-emerald-400/80"
                              : status === "failed"
                                ? "bg-red-400/85"
                                : "bg-white/25"
                          }`}
                        />
                        <div className="truncate font-mono text-[11px] uppercase tracking-wider text-white/75">
                          {phase.phase_name}
                        </div>
                      </div>
                      <div className="mt-1 font-mono text-[9px] text-white/32">
                        {phase.phase_id} / {phaseStatusLabel(status)} / {metricLabel(phase)}
                      </div>
                    </div>
                  </button>
                );
                })}
              </div>
            </aside>

            <section className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-white/8 bg-white/[0.025]">
              <div className="flex shrink-0 items-center justify-between border-b border-white/8 px-4 py-3">
                <div>
                  <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-cyan-300/70">
                    {artifact?.status === "completed" ? (
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-300/75" />
                    ) : artifact?.status === "failed" ? (
                      <XCircle className="h-3.5 w-3.5 text-red-300/75" />
                    ) : null}
                    {selectedPhase?.phase_name ?? "No Phase"}
                  </div>
                  <div className="mt-1 font-mono text-[10px] text-white/32">
                    {selectedPhase
                      ? `${phaseNumberLabel(selectedPhase.phase_id)} / ${artifact?.status ?? selectedPhase.status} / ${metricLabel(selectedPhase)}`
                      : "No prompt artifact captured"}
                  </div>
                </div>
                {artifactLoading && <Loader2 className="h-4 w-4 animate-spin text-cyan-300/60" />}
              </div>
              <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-white/8 px-4 py-2">
                <div className="flex gap-2">
                  {(["user", "system", "inputs", "options", "output"] as PromptTab[]).map((item) => (
                    <button
                      key={item}
                      type="button"
                      onClick={() => setTab(item)}
                      className={`rounded-md px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest ${
                        tab === item
                          ? "bg-cyan-500/12 text-cyan-300"
                          : "text-white/38 hover:bg-white/[0.05] hover:text-white/65"
                      }`}
                    >
                      {item}
                    </button>
                  ))}
                </div>
                <div className="ml-auto flex min-w-[16rem] items-center gap-2">
                  {tab === "output" && (
                    <div className="flex h-8 rounded-md border border-white/8 bg-black/25 p-0.5">
                      {(["readable", "json"] as OutputView[]).map((item) => (
                        <button
                          key={item}
                          type="button"
                          onClick={() => setOutputView(item)}
                          className={`rounded px-2 font-mono text-[9px] uppercase tracking-widest ${
                            outputView === item
                              ? "bg-cyan-500/12 text-cyan-300"
                              : "text-white/35 hover:text-white/65"
                          }`}
                        >
                          {item}
                        </button>
                      ))}
                    </div>
                  )}
                  <div className="flex h-8 flex-1 items-center gap-2 rounded-md border border-white/8 bg-black/25 px-2">
                    <Search className="h-3.5 w-3.5 text-white/28" />
                    <input
                      value={searchQuery}
                      onChange={(event) => setSearchQuery(event.target.value)}
                      placeholder="Search current tab"
                      className="min-w-0 flex-1 bg-transparent font-mono text-[10px] text-white/70 outline-none placeholder:text-white/25"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => void handleCopyTab()}
                    disabled={!tabValue}
                    className="flex h-8 w-8 items-center justify-center rounded-md border border-white/8 bg-white/[0.03] text-white/45 hover:bg-white/[0.08] hover:text-white/75 disabled:opacity-35"
                    title="Copy current tab"
                  >
                    {copied ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                  </button>
                </div>
              </div>
              <div className="min-h-0 flex-1 p-4">
                {tab === "output" && outputView === "readable" ? (
                  <ReadableOutput artifact={artifact} emptyMessage={outputEmptyMessage} />
                ) : (
                  <PromptBlock
                    value={tabValue}
                    searchQuery={searchQuery}
                    emptyMessage={tab === "output" ? outputEmptyMessage : "No content captured."}
                    onSelectText={setSelectedText}
                  />
                )}
              </div>
            </section>

            <aside className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-white/8 bg-white/[0.025]">
              <div className="shrink-0 border-b border-white/8 px-4 py-3">
                <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-white/45">
                  <MessageSquarePlus className="h-3.5 w-3.5" />
                  问题池
                </div>
              </div>
              <div className="shrink-0 space-y-3 border-b border-white/8 p-4">
                <input
                  value={issueTitle}
                  onChange={(event) => setIssueTitle(event.target.value)}
                  placeholder="问题标题"
                  className="h-9 w-full rounded-lg border border-white/10 bg-black/30 px-3 text-sm text-white/80 outline-none focus:border-cyan-400/35"
                />
                <div className="grid grid-cols-2 gap-2">
                  <select
                    value={issueType}
                    onChange={(event) => setIssueType(event.target.value)}
                    className="h-9 rounded-lg border border-white/10 bg-black/30 px-2 text-xs text-white/75 outline-none"
                  >
                    {ISSUE_TYPES.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                  <select
                    value={severity}
                    onChange={(event) => setSeverity(event.target.value)}
                    className="h-9 rounded-lg border border-white/10 bg-black/30 px-2 text-xs text-white/75 outline-none"
                  >
                    {SEVERITIES.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </div>
                <textarea
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  placeholder="描述现象、影响范围、可能原因，以及建议的修复方向。"
                  className="min-h-28 w-full resize-none rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white/75 outline-none focus:border-cyan-400/35"
                />
                {selectedText && (
                  <div className="rounded-lg border border-cyan-400/15 bg-cyan-500/[0.04] px-3 py-2">
                    <div className="font-mono text-[9px] uppercase tracking-widest text-cyan-300/55">
                      已选中 {tab}
                    </div>
                    <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-white/45">
                      {selectedText}
                    </p>
                  </div>
                )}
                <Button
                  type="button"
                  onClick={() => void handleCreateIssue()}
                  disabled={savingIssue || !issueTitle.trim() || !description.trim()}
                  className="w-full"
                >
                  {savingIssue ? (
                    <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Database className="mr-2 h-3.5 w-3.5" />
                  )}
                  保存问题
                </Button>
              </div>
              <div className="min-h-0 flex-1 overflow-auto p-3 custom-scrollbar">
                {issues.map((issue) => {
                  const isOpen = openIssueId === issue.id;
                  return (
                    <div
                      key={issue.id}
                      className={`mb-3 rounded-lg border p-3 transition ${
                        isOpen
                          ? "border-cyan-400/20 bg-cyan-500/[0.045]"
                          : "border-white/8 bg-black/18 hover:border-white/14 hover:bg-white/[0.035]"
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => setOpenIssueId(isOpen ? null : issue.id)}
                        className="w-full text-left"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <h3 className="text-sm font-medium text-white/82">{issue.title}</h3>
                          <span className="rounded border border-white/8 px-1.5 py-0.5 font-mono text-[9px] uppercase text-white/42">
                            {severityLabel(issue.severity)}
                          </span>
                        </div>
                        <p className="mt-2 line-clamp-3 text-xs leading-relaxed text-white/48">
                          {issue.description}
                        </p>
                        <div className="mt-3 flex flex-wrap gap-1.5 font-mono text-[9px] uppercase tracking-wider text-white/34">
                          <span>{issueTypeLabel(issue.issue_type)}</span>
                          <span>/</span>
                          <span>{issue.status}</span>
                          {issue.phase_id && (
                            <>
                              <span>/</span>
                              <span>{issue.phase_id}</span>
                            </>
                          )}
                        </div>
                      </button>
                      {isOpen && (
                        <div className="mt-4 space-y-3 border-t border-white/8 pt-3">
                          <p className="whitespace-pre-wrap text-xs leading-relaxed text-white/62">
                            {issue.description}
                          </p>
                          <div className="grid gap-x-3 gap-y-2 font-mono text-[10px] text-white/42 sm:grid-cols-2">
                            <div>任务: {issue.task_id}</div>
                            <div>阶段: {issue.phase_id ?? "无"}</div>
                            <div>分类: {issueTypeLabel(issue.issue_type)}</div>
                            <div>状态: {issue.status}</div>
                            <div>来源: {issue.source}</div>
                            <div>创建: {new Date(issue.created_at).toLocaleString()}</div>
                            <div className="break-all sm:col-span-2">id: {issue.id}</div>
                            <div className="break-all sm:col-span-2">
                              提示词: {issue.prompt_artifact_path ?? "未关联"}
                            </div>
                            {issue.related_artifact_path && (
                              <div className="break-all sm:col-span-2">
                                相关产物: {issue.related_artifact_path}
                              </div>
                            )}
                          </div>
                          <div>
                            <div className="mb-1 font-mono text-[9px] uppercase tracking-widest text-white/30">
                              元数据
                            </div>
                            {Object.keys(issue.metadata ?? {}).length > 0 && (
                              <pre className="max-h-36 overflow-auto whitespace-pre-wrap rounded border border-white/8 bg-black/25 p-2 text-[10px] leading-relaxed text-white/45 custom-scrollbar">
                                {formatJson(issue.metadata)}
                              </pre>
                            )}
                            {Object.keys(issue.metadata ?? {}).length === 0 && (
                              <div className="rounded border border-white/8 bg-black/20 p-2 text-xs text-white/35">
                                没有记录元数据。
                              </div>
                            )}
                          </div>
                          <button
                            type="button"
                            onClick={() => void handleDeleteIssue(issue.id)}
                            disabled={deletingIssueId === issue.id}
                            className="inline-flex h-8 items-center gap-2 rounded-md border border-red-400/15 bg-red-500/[0.035] px-3 font-mono text-[10px] uppercase tracking-widest text-red-200/65 hover:border-red-300/25 hover:bg-red-500/[0.08] disabled:cursor-not-allowed disabled:opacity-55"
                          >
                            {deletingIssueId === issue.id ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <Trash2 className="h-3.5 w-3.5" />
                            )}
                            删除
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
                {issues.length === 0 && (
                  <div className="flex h-full items-center justify-center text-center">
                    <div className="space-y-2 text-white/32">
                      <FileText className="mx-auto h-5 w-5" />
                      <p className="font-mono text-[10px] uppercase tracking-widest">暂无问题</p>
                    </div>
                  </div>
                )}
              </div>
            </aside>
          </div>
        )}
      </div>
    </main>
  );
}
