"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Bug,
  CircleAlert,
  ExternalLink,
  Filter,
  Inbox,
  Loader2,
  RefreshCw,
  Search,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { listAllDebugIssues } from "@/lib/api";
import type { DebugIssue } from "@/types";

const STATUS_OPTIONS = ["open", "fixed", "ignored"];
const SEVERITY_OPTIONS = ["low", "medium", "high", "blocker"];

const ISSUE_TYPE_LABELS: Record<string, string> = {
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

const SEVERITY_LABELS: Record<string, string> = {
  low: "低",
  medium: "中",
  high: "高",
  blocker: "阻塞",
};

interface FilterState {
  status: string;
  severity: string;
  issueType: string;
  taskId: string;
  search: string;
}

const EMPTY_FILTERS: FilterState = {
  status: "",
  severity: "",
  issueType: "",
  taskId: "",
  search: "",
};

function issueTypeLabel(type: string) {
  return ISSUE_TYPE_LABELS[type] ?? type;
}

function severityLabel(severity: string) {
  return SEVERITY_LABELS[severity] ?? severity;
}

function compactDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default function GlobalDebugIssuesPage() {
  const [issues, setIssues] = useState<DebugIssue[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [severity, setSeverity] = useState("");
  const [issueType, setIssueType] = useState("");
  const [taskId, setTaskId] = useState("");
  const [search, setSearch] = useState("");
  const [appliedFilters, setAppliedFilters] = useState<FilterState>(EMPTY_FILTERS);

  const issueTypes = useMemo(() => {
    const values = new Set(Object.keys(ISSUE_TYPE_LABELS));
    issues.forEach((issue) => values.add(issue.issue_type));
    return Array.from(values);
  }, [issues]);

  const loadIssues = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await listAllDebugIssues({
        limit: 200,
        status: appliedFilters.status,
        severity: appliedFilters.severity,
        issue_type: appliedFilters.issueType,
        task_id: appliedFilters.taskId,
        search: appliedFilters.search,
      });
      setIssues(result.issues);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load debug issues.");
    } finally {
      setLoading(false);
    }
  }, [appliedFilters]);

  useEffect(() => {
    void loadIssues();
  }, [loadIssues]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAppliedFilters({ status, severity, issueType, taskId, search });
  }

  function clearFilters() {
    setStatus("");
    setSeverity("");
    setIssueType("");
    setTaskId("");
    setSearch("");
    setAppliedFilters(EMPTY_FILTERS);
  }

  const openCount = issues.filter((issue) => issue.status === "open").length;
  const blockerCount = issues.filter((issue) => issue.severity === "blocker").length;

  return (
    <main className="h-[var(--app-content-height)] overflow-y-auto overscroll-contain">
      <div className="mx-auto flex min-h-full w-full max-w-[1500px] flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-3">
            <Link
              href="/history"
              className="inline-flex h-7 w-fit items-center gap-1 rounded-md px-2.5 text-[0.8rem] font-medium text-muted-foreground transition hover:bg-muted hover:text-foreground"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              返回历史
            </Link>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-primary/15 bg-primary/[0.08] text-primary">
                <Bug className="h-5 w-5" />
              </div>
              <div>
                <h1 className="text-2xl font-semibold tracking-tight">全局调试问题</h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  跨任务查看已记录的问题，定位重复出现的 pipeline、prompt 和渲染风险。
                </p>
              </div>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center sm:min-w-72">
            <div className="rounded-lg border border-border/70 bg-background/45 px-3 py-2">
              <div className="font-mono text-lg text-foreground">{issues.length}</div>
              <div className="mt-0.5 text-[10px] uppercase tracking-widest text-muted-foreground">
                total
              </div>
            </div>
            <div className="rounded-lg border border-border/70 bg-background/45 px-3 py-2">
              <div className="font-mono text-lg text-foreground">{openCount}</div>
              <div className="mt-0.5 text-[10px] uppercase tracking-widest text-muted-foreground">
                open
              </div>
            </div>
            <div className="rounded-lg border border-border/70 bg-background/45 px-3 py-2">
              <div className="font-mono text-lg text-foreground">{blockerCount}</div>
              <div className="mt-0.5 text-[10px] uppercase tracking-widest text-muted-foreground">
                blocker
              </div>
            </div>
          </div>
        </header>

        <form
          onSubmit={handleSubmit}
          className="grid gap-3 rounded-lg border border-border/70 bg-background/45 p-3 md:grid-cols-[minmax(180px,1fr)_140px_140px_170px_140px_auto_auto]"
        >
          <label className="relative block">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="搜索标题或描述"
              className="h-9 w-full rounded-md border border-border bg-background/60 pl-9 pr-3 text-sm outline-none transition focus:border-primary/45 focus:ring-3 focus:ring-primary/15"
            />
          </label>
          <input
            value={taskId}
            onChange={(event) => setTaskId(event.target.value)}
            placeholder="task id"
            className="h-9 rounded-md border border-border bg-background/60 px-3 font-mono text-sm outline-none transition focus:border-primary/45 focus:ring-3 focus:ring-primary/15"
          />
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            className="h-9 rounded-md border border-border bg-background/60 px-3 text-sm outline-none transition focus:border-primary/45 focus:ring-3 focus:ring-primary/15"
          >
            <option value="">全部状态</option>
            {STATUS_OPTIONS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
          <select
            value={severity}
            onChange={(event) => setSeverity(event.target.value)}
            className="h-9 rounded-md border border-border bg-background/60 px-3 text-sm outline-none transition focus:border-primary/45 focus:ring-3 focus:ring-primary/15"
          >
            <option value="">全部级别</option>
            {SEVERITY_OPTIONS.map((value) => (
              <option key={value} value={value}>
                {severityLabel(value)}
              </option>
            ))}
          </select>
          <select
            value={issueType}
            onChange={(event) => setIssueType(event.target.value)}
            className="h-9 rounded-md border border-border bg-background/60 px-3 text-sm outline-none transition focus:border-primary/45 focus:ring-3 focus:ring-primary/15"
          >
            <option value="">全部分类</option>
            {issueTypes.map((value) => (
              <option key={value} value={value}>
                {issueTypeLabel(value)}
              </option>
            ))}
          </select>
          <Button type="submit" disabled={loading} className="h-9">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Filter className="h-4 w-4" />}
            筛选
          </Button>
          <Button type="button" variant="outline" onClick={clearFilters} className="h-9">
            <RefreshCw className="h-4 w-4" />
            清空
          </Button>
        </form>

        {error && (
          <div className="flex items-center gap-2 rounded-lg border border-destructive/25 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            <CircleAlert className="h-4 w-4" />
            {error}
          </div>
        )}

        {loading && (
          <div className="grid gap-3">
            {Array.from({ length: 5 }).map((_, index) => (
              <div
                key={index}
                className="h-28 animate-pulse rounded-lg border border-border/70 bg-muted/20"
              />
            ))}
          </div>
        )}

        {!loading && issues.length === 0 && (
          <div className="flex min-h-80 items-center justify-center rounded-lg border border-dashed border-border bg-background/35 text-center">
            <div className="space-y-3 text-muted-foreground">
              <Inbox className="mx-auto h-8 w-8 opacity-45" />
              <div>
                <p className="text-sm font-medium text-foreground/75">暂无匹配的问题</p>
                <p className="mt-1 text-xs">调整筛选条件，或在单个 task 的 debug 页面记录新问题。</p>
              </div>
            </div>
          </div>
        )}

        {!loading && issues.length > 0 && (
          <section className="grid gap-3 pb-8">
            {issues.map((issue) => (
              <article
                key={issue.id}
                className="rounded-lg border border-border/70 bg-background/45 p-4 transition hover:border-primary/25 hover:bg-background/70"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-base font-medium text-foreground">{issue.title}</h2>
                      <Badge variant={issue.severity === "blocker" ? "destructive" : "outline"}>
                        {severityLabel(issue.severity)}
                      </Badge>
                      <Badge variant={issue.status === "open" ? "secondary" : "outline"}>
                        {issue.status}
                      </Badge>
                    </div>
                    <p className="line-clamp-2 text-sm leading-relaxed text-muted-foreground">
                      {issue.description}
                    </p>
                  </div>
                  <Link
                    href={`/tasks/${issue.task_id}/debug`}
                    className="inline-flex h-7 w-fit shrink-0 items-center justify-center gap-1 rounded-md border border-border bg-background px-2.5 text-[0.8rem] font-medium transition hover:bg-muted hover:text-foreground"
                  >
                    打开任务
                    <ExternalLink className="h-3.5 w-3.5" />
                  </Link>
                </div>
                <div className="mt-4 grid gap-2 font-mono text-[11px] text-muted-foreground sm:grid-cols-2 lg:grid-cols-5">
                  <div className="break-all">task: {issue.task_id}</div>
                  <div>phase: {issue.phase_id ?? "none"}</div>
                  <div>type: {issueTypeLabel(issue.issue_type)}</div>
                  <div>source: {issue.source}</div>
                  <div>created: {compactDate(issue.created_at)}</div>
                </div>
              </article>
            ))}
          </section>
        )}
      </div>
    </main>
  );
}
