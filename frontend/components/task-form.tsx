"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { Loader2, Music4, Play, SkipForward, Sparkles, Volume2, Wand2 } from "lucide-react";

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
import { logger } from "@/lib/logger";
import type { ContentClarifyData, TaskDurationSeconds } from "@/types";

const VOICES = [
  { id: "female-tianmei", label: "甜美女声" },
  { id: "male-qn-qingse", label: "清新男声" },
  { id: "presenter_male", label: "专业播音" },
  { id: "audiobook_male_1", label: "故事旁白" },
  { id: "female-shaonv", label: "活力女声" },
];

const QUALITIES = [
  { value: "high", label: "高清 1080p60" },
  { value: "medium", label: "标清 480p" },
  { value: "low", label: "流畅 360p" },
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

const TEMPLATES = [
  { text: "用动画演示勾股定理的证明过程", icon: "A" },
  { text: "可视化二次函数 y=ax^2+bx+c 的图像变化", icon: "B" },
];

function getLabel<T extends { id?: string | number; value?: string | number; label: string }>(
  list: T[],
  key: string,
): string {
  return list.find((item) => String(item.id ?? item.value) === key)?.label ?? key;
}

function ClarificationList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <section>
      <p className="text-xs font-medium text-white/45">{title}</p>
      <ul className="mt-2 space-y-1.5 text-sm text-white/78">
        {items.map((item) => (
          <li key={item}>- {item}</li>
        ))}
      </ul>
    </section>
  );
}

function FieldLabel({ label }: { label: string }) {
  return (
    <label className="text-[11px] font-medium uppercase tracking-[0.2em] text-white/34">
      {label}
    </label>
  );
}

export function TaskForm({ initialPrompt = "" }: { initialPrompt?: string }) {
  const router = useRouter();
  const formRef = useRef<HTMLFormElement>(null);

  const [text, setText] = useState(initialPrompt);
  const [voiceId, setVoiceId] = useState("female-tianmei");
  const [quality, setQuality] = useState<"high" | "medium" | "low">("high");
  const [preset, setPreset] = useState<
    "default" | "educational" | "presentation" | "proof" | "concept"
  >("default");
  const [targetDurationSeconds, setTargetDurationSeconds] = useState<TaskDurationSeconds>(60);
  const [noTts, setNoTts] = useState(false);
  const [bgmEnabled, setBgmEnabled] = useState(false);
  const [bgmPrompt, setBgmPrompt] = useState("");
  const [bgmVolume, setBgmVolume] = useState(0.12);

  const [submitting, setSubmitting] = useState(false);
  const [clarifying, setClarifying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [clarification, setClarification] = useState<ContentClarifyData | null>(null);
  const [clarificationSourceText, setClarificationSourceText] = useState("");

  const handleTemplate = useCallback((templateText: string) => {
    setText("");
    setClarification(null);
    setClarificationSourceText("");
    let i = 0;
    const interval = setInterval(() => {
      setText(templateText.slice(0, i + 1));
      i += 1;
      if (i >= templateText.length) clearInterval(interval);
    }, 24);
  }, []);

  const runTaskCreation = useCallback(
    async (finalUserText: string) => {
      setSubmitting(true);
      setError(null);

      const formEl = formRef.current;
      const tl = gsap.timeline({
        onComplete: () => {
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
        },
      });

      if (formEl) {
        tl.to(formEl, {
          y: -28,
          opacity: 0,
          scale: 0.97,
          filter: "blur(8px)",
          duration: 0.45,
          ease: "power3.in",
        });
      } else {
        tl.play();
      }
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
    ],
  );

  const handleCreateWithoutClarification = useCallback(async () => {
    const normalized = text.trim();
    if (!normalized || submitting || clarifying) return;
    await runTaskCreation(normalized);
  }, [clarifying, runTaskCreation, submitting, text]);

  const handleClarifyAndRun = useCallback(async () => {
    const normalized = text.trim();
    if (!normalized || submitting || clarifying) return;

    setClarifying(true);
    setError(null);
    try {
      const result = await clarifyContent({ user_text: normalized });
      setClarification(result.clarification);
      setClarificationSourceText(normalized);
      setText(result.clarification.recommended_request_cn);
      await runTaskCreation(result.clarification.recommended_request_cn);
    } catch (err) {
      setError(err instanceof Error ? err.message : "理解内容失败");
    } finally {
      setClarifying(false);
    }
  }, [clarifying, runTaskCreation, submitting, text]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const normalized = text.trim();
    if (!normalized) return;

    if (clarification && clarificationSourceText && normalized !== clarificationSourceText) {
      await runTaskCreation(normalized);
      return;
    }

    setClarifying(true);
    setError(null);
    try {
      const result = await clarifyContent({ user_text: normalized });
      setClarification(result.clarification);
      setClarificationSourceText(normalized);
      setText(result.clarification.recommended_request_cn);
    } catch (err) {
      setError(err instanceof Error ? err.message : "内容理解失败");
    } finally {
      setClarifying(false);
    }
  }

  const hasCurrentClarification =
    !!clarification && !!clarificationSourceText && text.trim() !== clarificationSourceText;
  const canSubmit = !submitting && !clarifying && !!text.trim();
  const bgmPanelVisible = bgmEnabled && !noTts;

  useGSAP(
    () => {
      if (!formRef.current) return;
      gsap.fromTo(
        formRef.current,
        { y: 24, opacity: 0, scale: 0.985 },
        { y: 0, opacity: 1, scale: 1, duration: 0.7, ease: "power3.out", delay: 0.18 },
      );
    },
    { scope: formRef },
  );

  return (
    <form
      ref={formRef}
      onSubmit={handleSubmit}
      className="flex h-full min-h-0 flex-col rounded-[30px] border border-white/7 bg-[linear-gradient(180deg,rgba(5,10,16,0.84),rgba(8,13,22,0.74))] p-2.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.04),0_16px_60px_rgba(2,6,23,0.2)] transition-all duration-300 sm:p-3"
    >
      <div className="grid min-h-0 flex-1 gap-2.5 lg:grid-cols-[minmax(0,1.5fr)_minmax(340px,1fr)] lg:items-stretch">
        <section
          className={`min-h-0 gap-2.5 ${
            bgmPanelVisible ? "grid grid-rows-[minmax(0,0.95fr)_minmax(0,1fr)]" : "flex flex-col"
          }`}
        >
          <div
            className={`flex min-h-0 flex-col rounded-[24px] border border-white/7 bg-black/20 p-5 ${
              bgmPanelVisible ? "h-full overflow-hidden" : "flex-1"
            }`}
          >
            <div className="mb-3.5">
              <p className="text-sm text-white/58">用一句完整描述定义这次动画任务。</p>
            </div>

            <Textarea
              id="prompt"
              placeholder='例如："用动画演示勾股定理的证明过程"'
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={8}
              disabled={submitting}
              className="min-h-[144px] flex-1 resize-none rounded-[22px] border-white/6 bg-black/24 px-4 py-3 text-[15px] leading-relaxed text-foreground placeholder:text-muted-foreground/35 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] transition-all duration-300 focus:border-primary/30 focus:ring-primary/20"
            />

            <div className="mt-3 shrink-0 grid gap-2 sm:grid-cols-2">
              {TEMPLATES.map((template) => (
                <button
                  key={template.text}
                  type="button"
                  onClick={() => handleTemplate(template.text)}
                  disabled={submitting || clarifying}
                  className="flex items-center gap-2 rounded-[18px] border border-white/8 bg-white/[0.03] px-3 py-1.5 text-left transition hover:border-white/16 hover:bg-white/[0.05]"
                >
                  <span className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/[0.04] text-[10px] text-white/62">
                    {template.icon}
                  </span>
                  <span className="line-clamp-1 text-xs text-white/62">{template.text}</span>
                </button>
              ))}
            </div>

            {clarification && clarificationSourceText === text.trim() && (
              <div className="mt-3 rounded-[24px] border border-cyan-400/20 bg-cyan-400/[0.06] p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.18em] text-cyan-300/70">
                      内容理解确认
                    </p>
                    <p className="mt-1 text-sm text-foreground/85">
                      系统已经整理出推荐表达。你可以直接生成，也可以退回原始输入重新编辑。
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setText(clarificationSourceText);
                      setClarification(null);
                      setClarificationSourceText("");
                    }}
                    disabled={submitting || clarifying}
                    className="border-white/15 bg-transparent text-white/70 hover:bg-white/10 hover:text-white"
                  >
                    重新编辑
                  </Button>
                </div>

                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  <div className="space-y-3">
                    <section>
                      <p className="text-xs font-medium text-white/45">主题理解</p>
                      <p className="mt-1 text-sm leading-6 text-white/85">
                        {clarification.topic_interpretation}
                      </p>
                    </section>
                    <section>
                      <p className="text-xs font-medium text-white/45">核心问题</p>
                      <p className="mt-1 text-sm leading-6 text-white/85">
                        {clarification.core_question}
                      </p>
                    </section>
                  </div>

                  <div className="space-y-3">
                    <section>
                      <p className="text-xs font-medium text-white/45">内容摘要</p>
                      <p className="mt-1 text-sm leading-6 text-white/85">
                        {clarification.clarified_brief_cn}
                      </p>
                    </section>
                    <ClarificationList title="推荐讲解主线" items={clarification.explanation_path} />
                  </div>
                </div>

                <div className="mt-3 grid gap-3 md:grid-cols-3">
                  <ClarificationList title="默认边界" items={clarification.scope_boundaries} />
                  <ClarificationList title="可选分支" items={clarification.optional_branches} />
                  <ClarificationList title="动画重点" items={clarification.animation_focus} />
                </div>
              </div>
            )}
          </div>

          {bgmPanelVisible && (
            <div className="rounded-[24px] border border-white/8 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.08),transparent_28%),linear-gradient(180deg,rgba(255,255,255,0.035),rgba(255,255,255,0.018))] p-5 shadow-[0_18px_50px_rgba(2,6,23,0.2)]">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-lg font-medium text-white/88">背景音乐层</h3>
                  <p className="mt-2 max-w-[34rem] text-sm leading-7 text-white/50">
                    为讲解铺一层低干扰背景音乐。这里集中完成编辑，右侧只保留状态和启动控制。
                  </p>
                </div>
                <div className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-[10px] uppercase tracking-[0.16em] text-cyan-300/80">
                  Music-2.6
                </div>
              </div>

              <div className="mt-5 grid min-h-0 items-stretch gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
                <div className="flex min-h-0 flex-col rounded-[20px] border border-white/8 bg-black/16 p-4">
                  <FieldLabel label="配乐描述" />
                  <Textarea
                    id="bgm-prompt"
                    value={bgmPrompt}
                    onChange={(e) => setBgmPrompt(e.target.value)}
                    rows={3}
                    disabled={submitting}
                    placeholder="例如：冷静、极简、轻微存在感的钢琴与弦乐，不要人声"
                    className="mt-3 min-h-[132px] flex-1 resize-none rounded-2xl border-white/10 bg-black/20 px-4 py-3 text-[13px] leading-6 text-foreground/90 placeholder:text-muted-foreground/35 focus:border-cyan-400/35 focus:ring-cyan-400/20"
                  />
                </div>

                <div className="flex min-h-0 flex-col rounded-[20px] border border-white/8 bg-black/16 px-4 py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <FieldLabel label="音量" />
                      <p className="mt-1 text-[12px] leading-6 text-white/45">
                        建议保持轻微存在感，不压过解说。
                      </p>
                    </div>
                    <span className="font-mono text-lg text-cyan-300">{bgmVolume.toFixed(2)}</span>
                  </div>
                  <input
                    id="bgm-volume"
                    type="range"
                    min="0.05"
                    max="0.3"
                    step="0.01"
                    value={bgmVolume}
                    onChange={(e) => setBgmVolume(Number(e.target.value))}
                    disabled={submitting}
                    className="mt-5 w-full accent-cyan-400"
                  />
                  <div className="mt-2 flex justify-between text-[10px] uppercase tracking-[0.16em] text-white/28">
                    <span>Subtle</span>
                    <span>Present</span>
                  </div>
                  <div className="mt-auto pt-4">
                    <div className="rounded-xl border border-cyan-400/10 bg-cyan-400/[0.05] px-3 py-2.5">
                      <p className="text-[11px] leading-5 text-white/60">
                        推荐区间 <span className="font-mono text-cyan-300">0.10 - 0.16</span>
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </section>

        <aside className="grid min-h-0 gap-2.5 lg:grid-rows-[minmax(0,0.95fr)_minmax(0,1fr)]">
          <div className="rounded-[24px] border border-white/7 bg-black/16 p-4">
            <div className="mb-3">
              <h3 className="text-sm font-medium text-white/84">交付参数</h3>
              <p className="mt-1 text-sm text-white/46">决定交付风格与制作规格。</p>
            </div>

            <div className="space-y-2.5">
              <div className="space-y-1.5">
                <FieldLabel label="音色" />
                <Select value={voiceId} onValueChange={(v) => v && setVoiceId(v)} disabled={submitting}>
                  <SelectTrigger className="min-h-10 w-full border-white/10 bg-transparent text-[12px] font-medium text-white/80 shadow-none transition-colors hover:border-white/20 focus:border-primary/40 focus:ring-primary/20">
                    <SelectValue>{getLabel(VOICES, voiceId)}</SelectValue>
                  </SelectTrigger>
                  <SelectContent className="border border-white/10 bg-black/80 backdrop-blur-xl">
                    {VOICES.map((voice) => (
                      <SelectItem
                        key={voice.id}
                        value={voice.id}
                        className="text-[11px] text-white/70 focus:bg-white/10 focus:text-white"
                      >
                        {voice.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
                <div className="space-y-1.5">
                  <FieldLabel label="画质" />
                  <Select
                    value={quality}
                    onValueChange={(v) => v && setQuality(v as "high" | "medium" | "low")}
                    disabled={submitting}
                  >
                    <SelectTrigger className="min-h-10 w-full border-white/10 bg-transparent text-[12px] font-medium text-white/80 shadow-none transition-colors hover:border-white/20 focus:border-primary/40 focus:ring-primary/20">
                      <SelectValue>{getLabel(QUALITIES, quality)}</SelectValue>
                    </SelectTrigger>
                    <SelectContent className="border border-white/10 bg-black/80 backdrop-blur-xl">
                      {QUALITIES.map((item) => (
                        <SelectItem
                          key={item.value}
                          value={item.value}
                          className="text-[11px] text-white/70 focus:bg-white/10 focus:text-white"
                        >
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <FieldLabel label="时长" />
                  <Select
                    value={String(targetDurationSeconds)}
                    onValueChange={(v) => v && setTargetDurationSeconds(Number(v) as TaskDurationSeconds)}
                    disabled={submitting}
                  >
                    <SelectTrigger className="min-h-10 w-full border-white/10 bg-transparent text-[12px] font-medium text-white/80 shadow-none transition-colors hover:border-white/20 focus:border-primary/40 focus:ring-primary/20">
                      <SelectValue>{getLabel(DURATIONS, String(targetDurationSeconds))}</SelectValue>
                    </SelectTrigger>
                    <SelectContent className="border border-white/10 bg-black/80 backdrop-blur-xl">
                      {DURATIONS.map((item) => (
                        <SelectItem
                          key={item.value}
                          value={String(item.value)}
                          className="text-[11px] text-white/70 focus:bg-white/10 focus:text-white"
                        >
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-1.5">
                <FieldLabel label="模式" />
                <Select
                  value={preset}
                  onValueChange={(v) =>
                    v && setPreset(v as "default" | "educational" | "presentation" | "proof" | "concept")
                  }
                  disabled={submitting}
                >
                  <SelectTrigger className="min-h-10 w-full border-white/10 bg-transparent text-[12px] font-medium text-white/80 shadow-none transition-colors hover:border-white/20 focus:border-primary/40 focus:ring-primary/20">
                    <SelectValue>{getLabel(PRESETS, preset)}</SelectValue>
                  </SelectTrigger>
                  <SelectContent className="border border-white/10 bg-black/80 backdrop-blur-xl">
                    {PRESETS.map((item) => (
                      <SelectItem
                        key={item.value}
                        value={item.value}
                        className="text-[11px] text-white/70 focus:bg-white/10 focus:text-white"
                      >
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          <div className="flex min-h-0 flex-col rounded-[24px] border border-white/7 bg-black/18 p-3.5">
            <div className="space-y-2.5">
              <label className="flex cursor-pointer items-center gap-2.5 rounded-[20px] border border-white/7 bg-black/18 px-4 py-2 text-sm group select-none">
                <div
                  className={`relative h-4 w-4 rounded border transition-colors duration-200 ${
                    noTts
                      ? "border-primary bg-primary"
                      : "border-border/60 bg-background/30 group-hover:border-foreground/30"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={noTts}
                    onChange={(e) => setNoTts(e.target.checked)}
                    disabled={submitting}
                    className="sr-only"
                  />
                  {noTts && (
                    <svg
                      className="pointer-events-none absolute inset-0 m-auto h-3 w-3 text-primary-foreground"
                      viewBox="0 0 12 12"
                      fill="none"
                    >
                      <path
                        d="M2 6l3 3l5-5"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  )}
                </div>
                <span className="text-[13px] text-muted-foreground/80 transition-colors group-hover:text-foreground/70">
                  跳过语音合成，仅生成静音视频
                </span>
              </label>

              <button
                type="button"
                onClick={() => {
                  if (submitting || noTts) return;
                  setBgmEnabled((value) => !value);
                }}
                disabled={submitting || noTts}
                className="relative isolate overflow-hidden rounded-[24px] border border-white/8 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.08),transparent_28%),linear-gradient(180deg,rgba(255,255,255,0.035),rgba(255,255,255,0.018))] p-3.5 text-left shadow-[0_18px_50px_rgba(2,6,23,0.2)] transition hover:border-white/14 disabled:cursor-not-allowed disabled:opacity-55"
              >
                <div className="pointer-events-none absolute -left-8 top-0 h-20 w-20 rounded-full bg-cyan-400/10 blur-3xl" />
                <div className="relative z-10 flex items-start gap-3">
                  <div
                    className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border transition-colors ${
                      bgmPanelVisible
                        ? "border-cyan-400/40 bg-cyan-400/14 text-cyan-300"
                        : "border-white/12 bg-black/20 text-white/38"
                    }`}
                  >
                    <Music4 className="h-3.5 w-3.5" />
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium text-white/90">背景音乐层</span>
                      <span className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] text-cyan-300/80">
                        Music-2.6
                      </span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] uppercase tracking-[0.14em] ${
                          bgmPanelVisible ? "bg-emerald-400/12 text-emerald-300" : "bg-white/6 text-white/35"
                        }`}
                      >
                        {bgmPanelVisible ? "On" : "Off"}
                      </span>
                    </div>
                    <p className="mt-2 text-[12px] leading-6 text-white/48">
                      {bgmPanelVisible ? "左侧已展开完整编辑面板。" : "点击展开完整背景音乐配置。"}
                    </p>
                  </div>

                  <div className="mt-1 flex shrink-0 items-center gap-1 text-[11px] text-cyan-300/75">
                    <Volume2 className="h-3.5 w-3.5" />
                    {bgmVolume.toFixed(2)}
                  </div>
                </div>
              </button>

              {error && (
                <p className="rounded-lg border border-destructive/20 bg-destructive/10 px-3 py-2.5 text-sm text-destructive animate-fade-in-up">
                  {error}
                </p>
              )}
            </div>

            <div className="mt-auto pt-2.5">
              <div className="rounded-[24px] border border-white/7 bg-black/18 p-1.5">
              <motion.div
                className="relative"
                whileHover={canSubmit ? { scale: 1.01 } : {}}
                whileTap={canSubmit ? { scale: 0.98 } : {}}
              >
                <Button
                  type="submit"
                  disabled={!canSubmit}
                  size="lg"
                  className="relative h-10.5 w-full overflow-hidden text-[15px] font-medium btn-glow"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      正在创建任务...
                    </>
                  ) : clarifying ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      正在理解内容...
                    </>
                  ) : hasCurrentClarification ? (
                    <>
                      <Wand2 className="mr-2 h-4 w-4" />
                      按此理解继续生成
                    </>
                  ) : (
                    <>
                      <Sparkles className="mr-2 h-4 w-4" />
                      先理解内容
                    </>
                  )}
                </Button>
              </motion.div>

              {!hasCurrentClarification && (
                <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
                  <Button
                    type="button"
                    variant="outline"
                    disabled={!canSubmit}
                    onClick={handleCreateWithoutClarification}
                    className="h-9.5 border-white/10 bg-transparent text-white/75 hover:bg-white/10 hover:text-white"
                  >
                    {submitting ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        提交中...
                      </>
                    ) : (
                      <>
                        <SkipForward className="mr-2 h-4 w-4" />
                        跳过理解，直接生成
                      </>
                    )}
                  </Button>

                  <Button
                    type="button"
                    variant="secondary"
                    disabled={!canSubmit}
                    onClick={handleClarifyAndRun}
                    className="h-9.5 border border-white/10 bg-white/[0.06] text-white hover:bg-white/[0.12]"
                  >
                    {clarifying ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        理解并生成中...
                      </>
                    ) : (
                      <>
                        <Play className="mr-2 h-4 w-4" />
                        理解并直接生成
                      </>
                    )}
                  </Button>
                </div>
              )}
              </div>
            </div>
          </div>
        </aside>
      </div>
    </form>
  );
}
