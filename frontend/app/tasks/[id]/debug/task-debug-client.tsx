"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Bug,
  ClipboardList,
  Database,
  FileText,
  Loader2,
  MessageSquarePlus,
  RefreshCw,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  createDebugIssue,
  getDebugPromptArtifact,
  getDebugPromptIndex,
  getTask,
  listDebugIssues,
} from "@/lib/api";
import type { DebugIssue, DebugPromptArtifact, DebugPromptPhaseSummary, Task } from "@/types";

type PromptTab = "system" | "user" | "inputs" | "options" | "output";

const ISSUE_TYPES = [
  "prompt",
  "schema",
  "script_structure",
  "render",
  "visual_quality",
  "narration",
  "tts",
  "audio_mux",
  "infra",
  "frontend",
  "product",
  "other",
];

const SEVERITIES = ["low", "medium", "high", "blocker"];

function formatJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

function metricLabel(phase: DebugPromptPhaseSummary | null) {
  const metrics = phase?.metrics ?? {};
  const tokens = typeof metrics.approx_tokens === "number" ? metrics.approx_tokens : 0;
  const chars =
    (typeof metrics.system_prompt_chars === "number" ? metrics.system_prompt_chars : 0) +
    (typeof metrics.user_prompt_chars === "number" ? metrics.user_prompt_chars : 0);
  return `${chars.toLocaleString()} chars / ~${tokens.toLocaleString()} tokens`;
}

function PromptBlock({ value }: { value: string }) {
  return (
    <pre className="h-full min-h-[28rem] overflow-auto whitespace-pre-wrap rounded-lg border border-white/8 bg-black/35 p-4 font-mono text-[11px] leading-relaxed text-white/72 custom-scrollbar">
      {value || "No content captured."}
    </pre>
  );
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
  const [savingIssue, setSavingIssue] = useState(false);
  const [issueTitle, setIssueTitle] = useState("");
  const [issueType, setIssueType] = useState("prompt");
  const [severity, setSeverity] = useState("medium");
  const [description, setDescription] = useState("");

  const selectedPhase = useMemo(
    () => phases.find((phase) => phase.phase_id === selectedPhaseId) ?? null,
    [phases, selectedPhaseId],
  );

  const loadDebug = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [taskData, promptIndex, issueData] = await Promise.all([
        getTask(taskId),
        getDebugPromptIndex(taskId),
        listDebugIssues(taskId),
      ]);
      setTask(taskData);
      setPhases(promptIndex.phases);
      setIssues(issueData);
      setSelectedPhaseId((current) => current ?? promptIndex.phases[0]?.phase_id ?? null);
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
    setArtifactLoading(true);
    getDebugPromptArtifact(taskId, selectedPhaseId)
      .then((data) => setArtifact(data))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load artifact."))
      .finally(() => setArtifactLoading(false));
  }, [selectedPhaseId, taskId]);

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
        },
      });
      setIssues((prev) => [created, ...prev]);
      setIssueTitle("");
      setDescription("");
    } finally {
      setSavingIssue(false);
    }
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
            : formatJson(artifact?.output_snapshot);

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
            </div>
          </div>
          <div className="flex items-center gap-3">
            {task && (
              <span className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 font-mono text-[10px] uppercase tracking-wider text-white/52">
                {task.status}
              </span>
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
                {phases.map((phase) => (
                  <button
                    key={phase.phase_id}
                    type="button"
                    onClick={() => setSelectedPhaseId(phase.phase_id)}
                    className={`mb-2 w-full rounded-lg border px-3 py-3 text-left transition ${
                      selectedPhaseId === phase.phase_id
                        ? "border-cyan-400/25 bg-cyan-500/[0.08]"
                        : "border-white/6 bg-black/15 hover:border-white/12 hover:bg-white/[0.04]"
                    }`}
                  >
                    <div className="font-mono text-[11px] uppercase tracking-wider text-white/75">
                      {phase.phase_name}
                    </div>
                    <div className="mt-1 font-mono text-[9px] text-white/32">
                      {phase.phase_id} / {metricLabel(phase)}
                    </div>
                  </button>
                ))}
              </div>
            </aside>

            <section className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-white/8 bg-white/[0.025]">
              <div className="flex shrink-0 items-center justify-between border-b border-white/8 px-4 py-3">
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-widest text-cyan-300/70">
                    {selectedPhase?.phase_name ?? "No Phase"}
                  </div>
                  <div className="mt-1 font-mono text-[10px] text-white/32">
                    {selectedPhase ? metricLabel(selectedPhase) : "No prompt artifact captured"}
                  </div>
                </div>
                {artifactLoading && <Loader2 className="h-4 w-4 animate-spin text-cyan-300/60" />}
              </div>
              <div className="flex shrink-0 gap-2 border-b border-white/8 px-4 py-2">
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
              <div className="min-h-0 flex-1 p-4">
                <PromptBlock value={tabValue} />
              </div>
            </section>

            <aside className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-white/8 bg-white/[0.025]">
              <div className="shrink-0 border-b border-white/8 px-4 py-3">
                <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-white/45">
                  <MessageSquarePlus className="h-3.5 w-3.5" />
                  Issues
                </div>
              </div>
              <div className="shrink-0 space-y-3 border-b border-white/8 p-4">
                <input
                  value={issueTitle}
                  onChange={(event) => setIssueTitle(event.target.value)}
                  placeholder="Issue title"
                  className="h-9 w-full rounded-lg border border-white/10 bg-black/30 px-3 text-sm text-white/80 outline-none focus:border-cyan-400/35"
                />
                <div className="grid grid-cols-2 gap-2">
                  <select
                    value={issueType}
                    onChange={(event) => setIssueType(event.target.value)}
                    className="h-9 rounded-lg border border-white/10 bg-black/30 px-2 text-xs text-white/75 outline-none"
                  >
                    {ISSUE_TYPES.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                  <select
                    value={severity}
                    onChange={(event) => setSeverity(event.target.value)}
                    className="h-9 rounded-lg border border-white/10 bg-black/30 px-2 text-xs text-white/75 outline-none"
                  >
                    {SEVERITIES.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </div>
                <textarea
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  placeholder="What happened, why it matters, and a possible fix."
                  className="min-h-28 w-full resize-none rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white/75 outline-none focus:border-cyan-400/35"
                />
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
                  Save Issue
                </Button>
              </div>
              <div className="min-h-0 flex-1 overflow-auto p-3 custom-scrollbar">
                {issues.map((issue) => (
                  <div key={issue.id} className="mb-3 rounded-lg border border-white/8 bg-black/18 p-3">
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="text-sm font-medium text-white/82">{issue.title}</h3>
                      <span className="rounded border border-white/8 px-1.5 py-0.5 font-mono text-[9px] uppercase text-white/42">
                        {issue.severity}
                      </span>
                    </div>
                    <p className="mt-2 line-clamp-3 text-xs leading-relaxed text-white/48">
                      {issue.description}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-1.5 font-mono text-[9px] uppercase tracking-wider text-white/34">
                      <span>{issue.issue_type}</span>
                      <span>/</span>
                      <span>{issue.status}</span>
                      {issue.phase_id && (
                        <>
                          <span>/</span>
                          <span>{issue.phase_id}</span>
                        </>
                      )}
                    </div>
                  </div>
                ))}
                {issues.length === 0 && (
                  <div className="flex h-full items-center justify-center text-center">
                    <div className="space-y-2 text-white/32">
                      <FileText className="mx-auto h-5 w-5" />
                      <p className="font-mono text-[10px] uppercase tracking-widest">No issues yet</p>
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
