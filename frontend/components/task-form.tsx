"use client";

import type React from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import {
  BrainCircuit,
  Check,
  Clock3,
  FileVideo,
  Loader2,
  Mic2,
  Music4,
  Play,
  Save,
  SlidersHorizontal,
  Sparkles,
  Volume2,
  Wand2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { clarifyContent, createTask } from "@/lib/api";
import { gsap } from "@/lib/gsap";
import { logger } from "@/lib/logger";
import { usePrefersReducedMotion } from "@/lib/motion";
import type { ContentClarifyData, TaskDurationSeconds } from "@/types";

const VOICES = [
  { id: "female-tianmei", label: "甜美女声" },
  { id: "male-qn-qingse", label: "清新男声" },
  { id: "presenter_male", label: "专业播音" },
  { id: "audiobook_male_1", label: "故事旁白" },
  { id: "female-shaonv", label: "活力女声" },
];

const QUALITIES = [
  { value: "high", label: "高清 1080p60", summary: "1080p60" },
  { value: "medium", label: "标准 480p", summary: "480p" },
  { value: "low", label: "流畅 360p", summary: "360p" },
];

const PRESETS = [
  { value: "default", label: "默认" },
  { value: "educational", label: "教学讲解" },
  { value: "presentation", label: "演示汇报" },
  { value: "proof", label: "证明推导" },
  { value: "concept", label: "概念可视化" },
];

const DURATIONS: { value: TaskDurationSeconds; label: string }[] = [
  { value: 30, label: "30 秒" },
  { value: 60, label: "1 分钟" },
  { value: 180, label: "3 分钟" },
  { value: 300, label: "5 分钟" },
];

const TEMPLATES = ["傅里叶变换", "抛物线与二次函数", "勾股定理", "二叉树遍历"];

const BGM_STYLES = [
  { label: "极简", prompt: "冷静、极简、轻微存在感的钢琴与弦乐" },
  { label: "温和", prompt: "温和、清澈、适合教学讲解的环境音乐" },
  { label: "电影感", prompt: "克制的电影感铺底，带轻微推进感" },
];

const DRAFT_STORAGE_KEY = "manim-agent:create-draft";

function getLabel<T extends { id?: string | number; value?: string | number; label: string }>(
  list: T[],
  key: string,
): string {
  return list.find((item) => String(item.id ?? item.value) === key)?.label ?? key;
}

function getQualitySummary(quality: string) {
  return QUALITIES.find((item) => item.value === quality)?.summary ?? quality;
}

function SettingField({
  icon: Icon,
  label,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.18em] text-foreground/52">
        <Icon className="h-3.5 w-3.5 text-primary/55" />
        <span>{label}</span>
      </div>
      {children}
    </div>
  );
}

function Switch({
  checked,
  onChange,
  disabled,
  ariaLabel,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
  ariaLabel: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative h-5 w-9 shrink-0 rounded-full border transition-[background-color,border-color,box-shadow] duration-300 disabled:pointer-events-none disabled:opacity-45 ${
        checked
          ? "border-primary/45 bg-primary/20 shadow-[0_0_18px_-8px_oklch(0.72_0.11_250/0.85)]"
          : "border-white/12 bg-black/22"
      }`}
    >
      <span
        className={`absolute top-1/2 h-3.5 w-3.5 -translate-y-1/2 rounded-full transition-[left,background-color,box-shadow] duration-300 ${
          checked
            ? "left-[1.15rem] bg-primary shadow-[0_0_12px_oklch(0.72_0.11_250/0.65)]"
            : "left-0.5 bg-foreground/38"
        }`}
      />
    </button>
  );
}

export function TaskForm({ initialPrompt = "" }: { initialPrompt?: string }) {
  const router = useRouter();
  const formRef = useRef<HTMLFormElement>(null);
  const reduceMotion = usePrefersReducedMotion();

  const [text, setText] = useState(initialPrompt);
  const [voiceId, setVoiceId] = useState("female-tianmei");
  const [quality, setQuality] = useState<"high" | "medium" | "low">("high");
  const [preset, setPreset] = useState<
    "default" | "educational" | "presentation" | "proof" | "concept"
  >("default");
  const [targetDurationSeconds, setTargetDurationSeconds] = useState<TaskDurationSeconds>(60);
  const [noTts, setNoTts] = useState(false);
  const [bgmEnabled, setBgmEnabled] = useState(false);
  const [bgmPrompt, setBgmPrompt] = useState(BGM_STYLES[0].prompt);
  const [bgmVolume, setBgmVolume] = useState(0.12);
  const [bgmTuningOpen, setBgmTuningOpen] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [clarifying, setClarifying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [clarification, setClarification] = useState<ContentClarifyData | null>(null);
  const [draftSaved, setDraftSaved] = useState(false);

  const canAct = !!text.trim() && !submitting && !clarifying;
  const summary = `${getQualitySummary(quality)} · 约 ${getLabel(DURATIONS, String(targetDurationSeconds))} · MP4`;
  const activeBgmStyle =
    BGM_STYLES.find((style) => style.prompt === bgmPrompt)?.label ?? "自定义";

  useEffect(() => {
    if (initialPrompt) return;

    try {
      const rawDraft = window.localStorage.getItem(DRAFT_STORAGE_KEY);
      if (!rawDraft) return;

      const draft = JSON.parse(rawDraft) as Partial<{
        text: string;
        voiceId: string;
        quality: "high" | "medium" | "low";
        preset: "default" | "educational" | "presentation" | "proof" | "concept";
        targetDurationSeconds: TaskDurationSeconds;
        noTts: boolean;
        bgmEnabled: boolean;
        bgmPrompt: string;
        bgmVolume: number;
      }>;

      if (typeof draft.text === "string") setText(draft.text);
      if (typeof draft.voiceId === "string") setVoiceId(draft.voiceId);
      if (draft.quality) setQuality(draft.quality);
      if (draft.preset) setPreset(draft.preset);
      if (typeof draft.targetDurationSeconds === "number") {
        setTargetDurationSeconds(draft.targetDurationSeconds);
      }
      if (typeof draft.noTts === "boolean") setNoTts(draft.noTts);
      if (typeof draft.bgmEnabled === "boolean") setBgmEnabled(draft.bgmEnabled);
      if (typeof draft.bgmPrompt === "string") setBgmPrompt(draft.bgmPrompt);
      if (typeof draft.bgmVolume === "number") setBgmVolume(draft.bgmVolume);
      if (draft.text) setDraftSaved(true);
    } catch {
      window.localStorage.removeItem(DRAFT_STORAGE_KEY);
    }
  }, [initialPrompt]);

  const handleTemplate = useCallback((template: string) => {
    setText(`用动画讲解${template}，突出直觉、关键步骤和图像变化。`);
    setClarification(null);
    setError(null);
    setDraftSaved(false);
  }, []);

  const runTaskCreation = useCallback(
    async (finalUserText: string) => {
      setSubmitting(true);
      setError(null);

      const formEl = formRef.current;
      const submit = () => {
        createTask({
          user_text: finalUserText,
          voice_id: voiceId,
          model: "speech-2.8-hd",
          quality,
          preset,
          no_tts: noTts,
          bgm_enabled: bgmEnabled && !noTts,
          bgm_prompt: bgmEnabled && bgmPrompt.trim() ? bgmPrompt.trim() : null,
          bgm_volume: bgmVolume,
          target_duration_seconds: targetDurationSeconds,
        })
          .then((task) => {
            if (!task?.id) {
              logger.error("task-form", "createTask returned empty task id", { task });
              throw new Error("创建任务失败：服务返回了空任务 ID");
            }
            router.push(`/tasks/${task.id}`);
          })
          .catch((err) => {
            setError(err instanceof Error ? err.message : "创建任务失败");
            setSubmitting(false);
            if (formEl) {
              gsap.to(formEl, {
                y: 0,
                opacity: 1,
                filter: "blur(0px)",
                scale: 1,
                duration: 0.35,
              });
            }
          });
      };

      if (!formEl || reduceMotion || process.env.NODE_ENV === "test") {
        submit();
        return;
      }

      gsap.to(formEl, {
        y: -22,
        opacity: 0,
        scale: 0.985,
        filter: "blur(7px)",
        duration: 0.42,
        ease: "power3.in",
        onComplete: submit,
      });
    },
    [
      bgmEnabled,
      bgmPrompt,
      bgmVolume,
      noTts,
      preset,
      quality,
      router,
      targetDurationSeconds,
      voiceId,
      reduceMotion,
    ],
  );

  const handleClarify = useCallback(async () => {
    const normalized = text.trim();
    if (!normalized || submitting || clarifying) return;

    setClarifying(true);
    setError(null);
    try {
      const result = await clarifyContent({ user_text: normalized });
      setClarification(result.clarification);
      setText(result.clarification.recommended_request_cn);
    } catch (err) {
      setError(err instanceof Error ? err.message : "理解内容失败");
    } finally {
      setClarifying(false);
    }
  }, [clarifying, submitting, text]);

  const handleCreate = useCallback(async () => {
    const normalized = text.trim();
    if (!normalized || submitting || clarifying) return;
    await runTaskCreation(normalized);
  }, [clarifying, runTaskCreation, submitting, text]);

  const handleSaveDraft = useCallback(() => {
    if (!text.trim()) return;

    window.localStorage.setItem(
      DRAFT_STORAGE_KEY,
      JSON.stringify({
        text,
        voiceId,
        quality,
        preset,
        targetDurationSeconds,
        noTts,
        bgmEnabled,
        bgmPrompt,
        bgmVolume,
      }),
    );
    setDraftSaved(true);
  }, [
    bgmEnabled,
    bgmPrompt,
    bgmVolume,
    noTts,
    preset,
    quality,
    targetDurationSeconds,
    text,
    voiceId,
  ]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (clarification) {
      await handleCreate();
    } else {
      await handleClarify();
    }
  }

  return (
    <form
      ref={formRef}
      onSubmit={handleSubmit}
      className="grid min-h-[calc(var(--app-content-height)-10.5rem)] gap-6 lg:grid-cols-[minmax(0,1fr)_390px]"
    >
      <section className="relative flex min-h-[600px] overflow-hidden rounded-lg border border-white/12 bg-[linear-gradient(145deg,oklch(0.19_0.01_245/0.88),oklch(0.128_0.008_250/0.97))] p-4 shadow-[0_36px_110px_-78px_oklch(0.72_0.11_250/0.72),0_0_0_1px_oklch(1_0_0/0.015),inset_0_1px_0_oklch(1_0_0/0.075)] transition-[border-color,box-shadow,transform] duration-500 hover:border-white/16 hover:shadow-[0_40px_120px_-78px_oklch(0.72_0.11_250/0.84),0_0_0_1px_oklch(1_0_0/0.025),inset_0_1px_0_oklch(1_0_0/0.085)] sm:p-5 lg:p-6">
        <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(90deg,oklch(1_0_0/0.04)_1px,transparent_1px),linear-gradient(180deg,oklch(1_0_0/0.028)_1px,transparent_1px)] bg-[size:64px_64px] opacity-[0.1]" />
        <div className="pointer-events-none absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-primary/28 to-transparent" />
        <div className="relative flex min-h-0 w-full flex-col space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-foreground/56">描述概念、受众和你希望动画突出的直觉。</p>
            <span className="font-mono text-[11px] text-foreground/48">{text.trim().length} chars</span>
          </div>

          <Textarea
            id="prompt"
            name="prompt"
            aria-label="讲解主题"
            autoComplete="off"
            spellCheck={false}
            placeholder="例如：用频域直觉解释傅里叶变换，并展示信号如何分解为不同频率"
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setClarification(null);
              setDraftSaved(false);
            }}
            rows={10}
            disabled={submitting}
            className="min-h-[340px] flex-1 resize-none rounded-lg border-white/12 bg-[oklch(0.095_0.006_250/0.34)] px-5 py-4 text-[15px] leading-7 text-foreground/90 shadow-[inset_0_1px_0_oklch(1_0_0/0.05),inset_0_0_0_1px_oklch(1_0_0/0.01)] placeholder:text-muted-foreground/58 transition-[border-color,box-shadow,background-color] duration-300 focus-visible:border-primary/46 focus-visible:bg-[oklch(0.105_0.008_250/0.42)] focus-visible:ring-primary/16 sm:min-h-[390px] lg:min-h-0"
          />

          <div className="flex flex-wrap gap-2">
            {TEMPLATES.map((template) => (
              <button
                key={template}
                type="button"
                onClick={() => handleTemplate(template)}
                disabled={submitting || clarifying}
                className="rounded-lg border border-white/10 bg-white/[0.026] px-3 py-2 text-xs text-foreground/68 transition-[border-color,background-color,color,transform] duration-200 hover:-translate-y-0.5 hover:border-primary/26 hover:bg-primary/[0.055] hover:text-foreground/88 disabled:pointer-events-none disabled:opacity-50"
              >
                {template}
              </button>
            ))}
          </div>

          <AnimatePresence>
            {clarification && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 10 }}
                transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
                className="rounded-lg border border-primary/18 bg-primary/[0.045] p-4"
                aria-live="polite"
              >
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-primary/24 bg-primary/10 text-primary">
                    <Check className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-foreground/86">已理解内容</p>
                    <p className="mt-1 line-clamp-2 text-sm leading-6 text-foreground/58">
                      {clarification.clarified_brief_cn || clarification.topic_interpretation}
                    </p>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <AnimatePresence>
            {error && (
              <motion.p
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                className="rounded-lg border border-destructive/25 bg-destructive/10 px-3 py-2.5 text-sm text-destructive"
                role="alert"
                aria-live="polite"
              >
                {error}
              </motion.p>
            )}
          </AnimatePresence>

          <div className="mt-auto flex flex-col gap-3 border-t border-white/12 pt-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2 text-xs text-foreground/58">
              <Sparkles className="h-3.5 w-3.5 text-primary/58" />
              <span>推荐先理解内容，再生成动画。</span>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row">
              <Button
                type="button"
                variant="outline"
                disabled={!canAct}
                onClick={handleClarify}
                className="h-10 rounded-lg border-primary/20 bg-primary/[0.055] px-4 text-foreground/82 hover:bg-primary/[0.09]"
              >
                {clarifying ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    理解中
                  </>
                ) : (
                  <>
                    <BrainCircuit className="mr-2 h-4 w-4" />
                    理解内容
                  </>
                )}
              </Button>
              <Button
                type="button"
                disabled={!canAct}
                onClick={handleCreate}
                className="btn-glow h-10 rounded-lg px-5"
              >
                {submitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    创建中
                  </>
                ) : (
                  <>
                    <Play className="mr-2 h-4 w-4" />
                    生成动画
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      </section>

      <aside className="flex min-h-[600px] flex-col gap-4">
        <section className="flex flex-1 flex-col rounded-lg border border-white/12 bg-[linear-gradient(180deg,oklch(0.178_0.01_245/0.82),oklch(0.132_0.008_250/0.965))] p-4 shadow-[0_34px_90px_-78px_oklch(0.7_0.1_250/0.58),inset_0_1px_0_oklch(1_0_0/0.07)] transition-[border-color,box-shadow] duration-500 hover:border-white/16 hover:shadow-[0_38px_100px_-78px_oklch(0.7_0.1_250/0.68),inset_0_1px_0_oklch(1_0_0/0.08)]">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground/84">
              <SlidersHorizontal className="h-4 w-4 text-primary/70" />
              输出设置
            </h2>
            <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-foreground/50">
              {summary}
            </span>
          </div>

          <div className="space-y-4">
            <SettingField icon={Mic2} label="音色">
              <Select
                value={voiceId}
                onValueChange={(v) => {
                  if (!v) return;
                  setVoiceId(v);
                  setDraftSaved(false);
                }}
                disabled={submitting}
              >
                <SelectTrigger className="h-10 w-full rounded-lg border-white/10 bg-black/18 text-[13px] transition-[border-color,background-color,box-shadow] duration-200 hover:border-white/16 hover:bg-white/[0.035] focus:border-primary/35 focus:ring-primary/12">
                  <SelectValue>{getLabel(VOICES, voiceId)}</SelectValue>
                </SelectTrigger>
                <SelectContent className="border-white/10 bg-popover">
                  {VOICES.map((voice) => (
                    <SelectItem key={voice.id} value={voice.id}>
                      {voice.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </SettingField>

            <div className="grid grid-cols-2 gap-3">
              <SettingField icon={FileVideo} label="画质">
                <Select
                  value={quality}
                  onValueChange={(v) => {
                    if (!v) return;
                    setQuality(v as "high" | "medium" | "low");
                    setDraftSaved(false);
                  }}
                  disabled={submitting}
                >
                  <SelectTrigger className="h-10 w-full rounded-lg border-white/10 bg-black/18 text-[13px] transition-[border-color,background-color,box-shadow] duration-200 hover:border-white/16 hover:bg-white/[0.035] focus:border-primary/35 focus:ring-primary/12">
                    <SelectValue>{getLabel(QUALITIES, quality)}</SelectValue>
                  </SelectTrigger>
                  <SelectContent className="border-white/10 bg-popover">
                    {QUALITIES.map((item) => (
                      <SelectItem key={item.value} value={item.value}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </SettingField>

              <SettingField icon={Clock3} label="时长">
                <Select
                  value={String(targetDurationSeconds)}
                  onValueChange={(v) => {
                    if (!v) return;
                    setTargetDurationSeconds(Number(v) as TaskDurationSeconds);
                    setDraftSaved(false);
                  }}
                  disabled={submitting}
                >
                  <SelectTrigger className="h-10 w-full rounded-lg border-white/10 bg-black/18 text-[13px] transition-[border-color,background-color,box-shadow] duration-200 hover:border-white/16 hover:bg-white/[0.035] focus:border-primary/35 focus:ring-primary/12">
                    <SelectValue>{getLabel(DURATIONS, String(targetDurationSeconds))}</SelectValue>
                  </SelectTrigger>
                  <SelectContent className="border-white/10 bg-popover">
                    {DURATIONS.map((item) => (
                      <SelectItem key={item.value} value={String(item.value)}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </SettingField>
            </div>

            <SettingField icon={Wand2} label="模式">
              <Select
                value={preset}
                onValueChange={(v) =>
                  {
                    if (!v) return;
                    setPreset(v as "default" | "educational" | "presentation" | "proof" | "concept");
                    setDraftSaved(false);
                  }
                }
                disabled={submitting}
              >
                <SelectTrigger className="h-10 w-full rounded-lg border-white/10 bg-black/18 text-[13px] transition-[border-color,background-color,box-shadow] duration-200 hover:border-white/16 hover:bg-white/[0.035] focus:border-primary/35 focus:ring-primary/12">
                  <SelectValue>{getLabel(PRESETS, preset)}</SelectValue>
                </SelectTrigger>
                <SelectContent className="border-white/10 bg-popover">
                  {PRESETS.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </SettingField>
          </div>

          <div className="mt-5 border-t border-white/12 pt-4">
            <div className="mb-3 flex items-center justify-between">
              <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-foreground/52">
                Audio
              </p>
              <span className="text-xs text-foreground/52">
                {noTts ? "静音视频" : bgmEnabled ? "配音 + BGM" : "仅配音"}
              </span>
            </div>

            <div>
              <div className="grid grid-cols-[1fr_auto] items-center gap-3 py-2">
                <div className="flex items-center gap-3">
                  <Mic2 className="h-4 w-4 text-primary/62" />
                  <div>
                    <p className="text-sm font-medium text-foreground/80">配音</p>
                    <p className="mt-0.5 text-xs text-foreground/58">{getLabel(VOICES, voiceId)}</p>
                  </div>
                </div>
                <Switch
                  checked={!noTts}
                  ariaLabel="启用配音"
                  onChange={(checked) => {
                    setNoTts(!checked);
                    setDraftSaved(false);
                  }}
                  disabled={submitting}
                />
              </div>

              <div className="my-3 h-px bg-white/12" />

              <div className="grid grid-cols-[1fr_auto] items-center gap-3 py-2">
                <div className="flex items-center gap-3">
                  <Music4
                    className={`h-4 w-4 transition ${
                      bgmEnabled && !noTts ? "text-primary/72" : "text-foreground/42"
                    }`}
                  />
                  <div>
                    <p className="text-sm font-medium text-foreground/80">背景音乐</p>
                    <p className="mt-0.5 text-xs text-foreground/56">
                      {bgmEnabled && !noTts ? "风格与音量已启用" : "关闭"}
                    </p>
                  </div>
                </div>
                <Switch
                  checked={bgmEnabled && !noTts}
                  ariaLabel="启用背景音乐"
                  onChange={(checked) => {
                    setBgmEnabled(checked);
                    if (!checked) setBgmTuningOpen(false);
                    setDraftSaved(false);
                  }}
                  disabled={submitting || noTts}
                />
              </div>

              <div className="relative mt-3">
                <div
                  className={`flex h-9 items-center justify-between gap-2 border-t px-0 pt-3 transition ${
                    bgmEnabled && !noTts
                      ? "border-primary/14"
                      : "border-white/10"
                  }`}
                >
                  <div className="flex min-w-0 items-center gap-2">
                    <span
                      className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                        bgmEnabled && !noTts ? "bg-primary/80" : "bg-foreground/24"
                      }`}
                    />
                    <span className="truncate text-xs text-foreground/72">{activeBgmStyle}</span>
                    <span className="text-foreground/24">·</span>
                    <span className="font-mono text-[11px] text-foreground/58">
                      {bgmVolume.toFixed(2)}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setBgmTuningOpen((value) => !value)}
                    disabled={submitting}
                  className="rounded-md px-2 py-1 text-xs text-primary/82 transition-[background-color,color,transform] duration-200 hover:-translate-y-px hover:bg-primary/[0.08] hover:text-primary disabled:pointer-events-none disabled:opacity-45"
                  >
                    调校
                  </button>
                </div>

                <AnimatePresence>
                  {bgmTuningOpen && (
                    <motion.div
                      initial={{ opacity: 0, y: 6, scale: 0.98 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: 6, scale: 0.98 }}
                      transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
                      className="absolute right-0 top-12 z-20 w-[min(292px,calc(100vw-3rem))] rounded-lg border border-white/12 bg-[oklch(0.145_0.008_250/0.98)] p-3 shadow-[0_22px_60px_-30px_oklch(0_0_0/0.9),inset_0_1px_0_oklch(1_0_0/0.06)] backdrop-blur-2xl"
                    >
                      <div className="mb-3 flex items-center justify-between">
                        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-foreground/38">
                          BGM Tuning
                        </p>
                        <button
                          type="button"
                          onClick={() => setBgmTuningOpen(false)}
                          className="text-xs text-foreground/34 transition hover:text-foreground/68"
                        >
                          完成
                        </button>
                      </div>

                      <div className="grid grid-cols-3 gap-1.5">
                        {BGM_STYLES.map((style) => (
                          <button
                            key={style.label}
                            type="button"
                            onClick={() => {
                              setBgmPrompt(style.prompt);
                              setDraftSaved(false);
                            }}
                            className={`h-8 rounded-md border px-2 text-xs transition ${
                              bgmPrompt === style.prompt
                                ? "border-primary/30 bg-primary/14 text-primary"
                                : "border-white/8 bg-black/16 text-foreground/46 hover:text-foreground/70"
                            }`}
                          >
                            {style.label}
                          </button>
                        ))}
                      </div>

                      <label className="mt-3 flex items-center gap-3">
                        <Volume2 className="h-4 w-4 shrink-0 text-primary/60" />
                        <input
                          type="range"
                          name="bgmVolume"
                          aria-label="背景音乐音量"
                          min="0.05"
                          max="0.3"
                          step="0.01"
                          value={bgmVolume}
                          onChange={(e) => {
                            setBgmVolume(Number(e.target.value));
                            setDraftSaved(false);
                          }}
                          disabled={submitting}
                          className="min-w-0 flex-1 accent-primary"
                        />
                        <span className="w-9 text-right font-mono text-[11px] text-foreground/44">
                          {bgmVolume.toFixed(2)}
                        </span>
                      </label>

                      <input
                        name="bgmPrompt"
                        aria-label="自定义音乐描述"
                        autoComplete="off"
                        value={bgmPrompt}
                        onChange={(e) => {
                          setBgmPrompt(e.target.value);
                          setDraftSaved(false);
                        }}
                        disabled={submitting}
                        placeholder="自定义音乐描述"
                        className="mt-3 h-9 w-full rounded-lg border border-white/8 bg-black/20 px-3 text-sm text-foreground/78 outline-none transition placeholder:text-muted-foreground/34 focus:border-primary/30 focus:ring-2 focus:ring-primary/12"
                      />
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>
          </div>

          <button
            type="button"
            disabled={!text.trim() || submitting}
            onClick={handleSaveDraft}
            className="mt-auto flex items-center justify-center gap-2 rounded-md px-3 py-2.5 text-sm text-foreground/52 transition-[background-color,color,transform] duration-200 hover:-translate-y-px hover:bg-white/[0.035] hover:text-foreground/76 disabled:pointer-events-none disabled:opacity-35"
          >
            {draftSaved ? <Check className="h-4 w-4 text-primary/70" /> : <Save className="h-4 w-4" />}
            {draftSaved ? "已保存草稿" : "保存草稿"}
          </button>
        </section>
      </aside>
    </form>
  );
}
