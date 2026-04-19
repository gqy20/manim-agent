"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import gsap from "gsap";
import { Loader2, Music4, Play, SkipForward, Sparkles, Wand2, X } from "lucide-react";

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
      <p className="text-xs font-medium text-foreground/40">{title}</p>
      <ul className="mt-2 space-y-1.5 text-sm text-foreground/75">
        {items.map((item) => (
          <li key={item}>- {item}</li>
        ))}
      </ul>
    </section>
  );
}

function FieldLabel({ label }: { label: string }) {
  return (
    <label className="text-[11px] font-medium uppercase tracking-[0.16em] text-foreground/34">
      {label}
    </label>
  );
}

function AnimatedCheckbox({ checked, onChange, disabled }: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      onClick={() => !disabled && onChange(!checked)}
      disabled={disabled}
      className="relative h-4 w-4 shrink-0 rounded border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/32"
      style={{
        borderColor: checked ? undefined : undefined,
        backgroundColor: checked ? undefined : undefined,
      }}
    >
      <motion.div
        className="absolute inset-0 flex items-center justify-center"
        initial={false}
        animate={checked ? { scale: 1, opacity: 1 } : { scale: 0.3, opacity: 0 }}
        transition={{ type: "spring", stiffness: 500, damping: 28, delay: checked ? 0.05 : 0 }}
      >
        <svg className="h-3 w-3 text-primary-foreground" viewBox="0 0 12 12" fill="none">
          <motion.path
            d="M2 6l3 3l5-5"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: checked ? 1 : 0 }}
            transition={{ duration: 0.2, ease: "easeOut", delay: checked ? 0.08 : 0 }}
          />
        </svg>
      </motion.div>
    </button>
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

  return (
    <form
      ref={formRef}
      onSubmit={handleSubmit}
      className="flex h-full min-h-0 flex-col gap-4"
    >
      <div className="grid min-h-0 flex-1 gap-4 xl:grid-cols-[minmax(0,1fr)_420px] xl:items-start">
        {/* Left — Input */}
        <div className="flex min-h-0 flex-col gap-4">
          <div className="flex min-h-[calc(var(--app-content-height)-12.5rem)] flex-1 flex-col gap-4 rounded-2xl border border-border bg-card p-5">
            <p className="text-sm text-foreground/40">
              描述你想讲解的数学概念。
            </p>

            <Textarea
              id="prompt"
              placeholder='例如：用动画演示勾股定理的证明过程'
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={8}
              disabled={submitting}
              className="min-h-[360px] flex-1 resize-none rounded-xl border-border bg-background px-4 py-3 text-[15px] leading-relaxed placeholder:text-muted-foreground/40 focus:border-primary/30 focus:ring-primary/15"
            />

            <div className="flex gap-2">
              {TEMPLATES.map((template) => (
                <motion.button
                  key={template.text}
                  type="button"
                  onClick={() => handleTemplate(template.text)}
                  disabled={submitting || clarifying}
                  whileHover={{ y: -1, borderColor: "rgba(255,255,255,0.15)" }}
                  whileTap={{ scale: 0.97 }}
                  className="flex items-center gap-2 rounded-xl border border-border bg-background px-3 py-2 text-left transition-colors hover:bg-foreground/[0.03]"
                >
                  <span className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border bg-foreground/[0.04] text-[10px] font-mono text-foreground/50">
                    {template.icon}
                  </span>
                  <span className="line-clamp-1 text-xs text-foreground/50">{template.text}</span>
                </motion.button>
              ))}
            </div>

            <AnimatePresence mode="wait">
              {clarification && clarificationSourceText === text.trim() && (
                <motion.div
                  key="clarification"
                  initial={{ opacity: 0, height: 0, y: -8 }}
                  animate={{ opacity: 1, height: "auto", y: 0 }}
                  exit={{ opacity: 0, height: 0, y: -8 }}
                  transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                  className="overflow-hidden"
                >
                  <div className="rounded-xl border border-primary/20 bg-primary/[0.04] p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-[11px] uppercase tracking-[0.16em] text-primary/60">
                          内容理解确认
                        </p>
                        <p className="mt-1 text-sm text-foreground/80">
                          系统已整理出推荐表达。可直接生成，或退回重新编辑。
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
                        className="border-border bg-transparent text-foreground/60 hover:bg-foreground/[0.05] hover:text-foreground/80"
                      >
                        重新编辑
                      </Button>
                    </div>

                    <div className="mt-3 grid gap-3 md:grid-cols-2">
                      <div className="space-y-3">
                        <section>
                          <p className="text-xs font-medium text-foreground/40">主题理解</p>
                          <p className="mt-1 text-sm leading-6 text-foreground/80">{clarification.topic_interpretation}</p>
                        </section>
                        <section>
                          <p className="text-xs font-medium text-foreground/40">核心问题</p>
                          <p className="mt-1 text-sm leading-6 text-foreground/80">{clarification.core_question}</p>
                        </section>
                      </div>

                      <div className="space-y-3">
                        <section>
                          <p className="text-xs font-medium text-foreground/40">内容摘要</p>
                          <p className="mt-1 text-sm leading-6 text-foreground/80">{clarification.clarified_brief_cn}</p>
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
                </motion.div>
              )}
            </AnimatePresence>
          </div>

        </div>

        {/* Right — Params + Actions */}
        <aside className="flex min-h-0 flex-col gap-4">
          <div className="rounded-2xl border border-border bg-card p-4 space-y-4">
            <div>
              <h3 className="text-sm font-medium text-foreground/82">输出设置</h3>
            </div>

            <div className="space-y-3">
              <div className="space-y-1.5">
                <FieldLabel label="音色" />
                <Select value={voiceId} onValueChange={(v) => v && setVoiceId(v)} disabled={submitting}>
                  <SelectTrigger className="h-9 w-full border-border bg-background text-[12px] focus:border-primary/35">
                    <SelectValue>{getLabel(VOICES, voiceId)}</SelectValue>
                  </SelectTrigger>
                  <SelectContent className="border-border bg-popover">
                    {VOICES.map((voice) => (
                      <SelectItem key={voice.id} value={voice.id} className="text-[11px]">
                        {voice.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <FieldLabel label="画质" />
                  <Select value={quality} onValueChange={(v) => v && setQuality(v as "high" | "medium" | "low")} disabled={submitting}>
                    <SelectTrigger className="h-9 w-full border-border bg-background text-[12px] focus:border-primary/35">
                      <SelectValue>{getLabel(QUALITIES, quality)}</SelectValue>
                    </SelectTrigger>
                    <SelectContent className="border-border bg-popover">
                      {QUALITIES.map((item) => (
                        <SelectItem key={item.value} value={item.value} className="text-[11px]">
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <FieldLabel label="时长" />
                  <Select value={String(targetDurationSeconds)} onValueChange={(v) => v && setTargetDurationSeconds(Number(v) as TaskDurationSeconds)} disabled={submitting}>
                    <SelectTrigger className="h-9 w-full border-border bg-background text-[12px] focus:border-primary/35">
                      <SelectValue>{getLabel(DURATIONS, String(targetDurationSeconds))}</SelectValue>
                    </SelectTrigger>
                    <SelectContent className="border-border bg-popover">
                      {DURATIONS.map((item) => (
                        <SelectItem key={item.value} value={String(item.value)} className="text-[11px]">
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-1.5">
                <FieldLabel label="模式" />
                <Select value={preset} onValueChange={(v) => v && setPreset(v as "default" | "educational" | "presentation" | "proof" | "concept")} disabled={submitting}>
                  <SelectTrigger className="h-9 w-full border-border bg-background text-[12px] focus:border-primary/35">
                    <SelectValue>{getLabel(PRESETS, preset)}</SelectValue>
                  </SelectTrigger>
                  <SelectContent className="border-border bg-popover">
                    {PRESETS.map((item) => (
                      <SelectItem key={item.value} value={item.value} className="text-[11px]">
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          {/* Options & Actions */}
          <div className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-5">
            <div className="space-y-3">
              <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-border bg-background/35 px-3.5 py-3 select-none transition-colors hover:bg-foreground/[0.02]">
                <AnimatedCheckbox
                  checked={noTts}
                  onChange={setNoTts}
                  disabled={submitting}
                />
                <span className="text-[13px] text-foreground/70">跳过语音合成，仅生成静音视频</span>
              </label>

              <motion.button
                type="button"
                onClick={() => { if (submitting || noTts) return; setBgmEnabled((v) => !v); }}
                disabled={submitting || noTts}
                whileHover={!submitting && !noTts ? { backgroundColor: "rgba(255,255,255,0.02)" } : {}}
                whileTap={!submitting && !noTts ? { scale: 0.99 } : {}}
                className="flex w-full items-center justify-between gap-3 rounded-2xl border border-border bg-background/35 px-4 py-3 text-left transition-colors disabled:opacity-50"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <motion.div
                    className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border transition-colors ${bgmPanelVisible ? "border-primary/30 bg-primary/10 text-primary" : "border-border bg-foreground/[0.03] text-foreground/36"}`}
                    animate={bgmPanelVisible ? { rotate: [0, -10, 10, 0] } : {}}
                    transition={{ duration: 0.35 }}
                  >
                    <Music4 className="h-4 w-4" />
                  </motion.div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-foreground/82">背景音乐</span>
                      <motion.span
                        className={`rounded-full px-2 py-0.5 text-[10px] ${bgmPanelVisible ? "bg-primary/10 text-primary" : "bg-foreground/[0.05] text-foreground/32"}`}
                        layout
                        transition={{ type: "spring", stiffness: 400, damping: 25 }}
                      >
                        {bgmPanelVisible ? "On" : "Off"}
                      </motion.span>
                    </div>
                    <p className="mt-0.5 text-[12px] text-foreground/42">
                      {bgmPanelVisible ? "左侧保持展开的音乐配置面板。" : "点击展开背景音乐配置。"}
                    </p>
                  </div>
                </div>
                <div className="shrink-0 text-right">
                  <div className="text-[10px] uppercase tracking-[0.16em] text-foreground/26">Volume</div>
                  <div className="mt-1 font-mono text-[12px] text-foreground/46">{bgmVolume.toFixed(2)}</div>
                </div>
              </motion.button>

              <AnimatePresence>
                {error && (
                  <motion.p
                    key="error"
                    initial={{ opacity: 0, y: -6, height: 0 }}
                    animate={{ opacity: 1, y: 0, height: "auto" }}
                    exit={{ opacity: 0, y: -6, height: 0 }}
                    className="rounded-lg border border-destructive/20 bg-destructive/8 px-3 py-2.5 text-sm text-destructive overflow-hidden"
                  >
                    {error}
                  </motion.p>
                )}
              </AnimatePresence>
            </div>

            <div className="mt-auto space-y-2.5 pt-1">
              <motion.div whileHover={canSubmit ? { scale: 1.005 } : {}} whileTap={canSubmit ? { scale: 0.98 } : {}}>
                <Button
                  type="submit"
                  disabled={!canSubmit}
                  size="lg"
                  className="h-11 w-full text-[14px] font-medium btn-glow"
                >
                  {submitting ? (
                    <><Loader2 className="mr-2 h-4 w-4 animate-spin" />正在创建...</>
                  ) : clarifying ? (
                    <><Loader2 className="mr-2 h-4 w-4 animate-spin" />正在理解内容...</>
                  ) : hasCurrentClarification ? (
                    <><Wand2 className="mr-2 h-4 w-4" />按此理解继续生成</>
                  ) : (
                    <><Sparkles className="mr-2 h-4 w-4" />先理解内容</>
                  )}
                </Button>
              </motion.div>

              {!hasCurrentClarification && (
                <div className="grid grid-cols-2 gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    disabled={!canSubmit}
                    onClick={handleCreateWithoutClarification}
                    className="h-10 border-border bg-transparent text-foreground/70 hover:bg-foreground/[0.04] hover:text-foreground/85"
                  >
                    {submitting ? (
                      <><Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />提交中...</>
                    ) : (
                      <><SkipForward className="mr-2 h-3.5 w-3.5" />跳过理解直接生成</>
                    )}
                  </Button>

                  <Button
                    type="button"
                    variant="secondary"
                    disabled={!canSubmit}
                    onClick={handleClarifyAndRun}
                    className="h-10 border border-border bg-foreground/[0.06] text-foreground/80 hover:bg-foreground/[0.1]"
                  >
                    {clarifying ? (
                      <><Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />处理中...</>
                    ) : (
                      <><Play className="mr-2 h-3.5 w-3.5" />理解并直接生成</>
                    )}
                  </Button>
                </div>
              )}
            </div>
          </div>
        </aside>
      </div>

      <AnimatePresence>
        {bgmPanelVisible && (
          <motion.div
            key="bgm-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 px-4 py-8 backdrop-blur-sm"
            onClick={() => setBgmEnabled(false)}
          >
            <motion.div
              initial={{ opacity: 0, y: 18, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 12, scale: 0.98 }}
              transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
              className="w-full max-w-3xl rounded-3xl border border-border bg-card/96 p-6 shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.18em] text-primary/55">Background Music</p>
                  <h3 className="mt-2 text-xl font-medium text-foreground/90">背景音乐配置</h3>
                  <p className="mt-1 text-sm text-foreground/46">这层配置覆盖在主页面之上，不再挤压主编辑区布局。</p>
                </div>
                <button
                  type="button"
                  onClick={() => setBgmEnabled(false)}
                  className="flex h-9 w-9 items-center justify-center rounded-full border border-border bg-background/50 text-foreground/55 transition-colors hover:bg-background hover:text-foreground/85"
                  aria-label="关闭背景音乐配置"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="mt-6 grid gap-5 lg:grid-cols-[minmax(0,1fr)_240px] lg:items-start">
                <div>
                  <FieldLabel label="配乐描述" />
                  <Textarea
                    id="bgm-prompt"
                    value={bgmPrompt}
                    onChange={(e) => setBgmPrompt(e.target.value)}
                    rows={6}
                    disabled={submitting}
                    placeholder="例如：冷静、极简、轻微存在感的钢琴与弦乐，不要人声"
                    className="mt-2 min-h-[180px] resize-none rounded-2xl border-border bg-background px-4 py-3 text-[14px] leading-6 placeholder:text-muted-foreground/40 focus:border-primary/30"
                  />
                </div>

                <div className="rounded-2xl border border-border bg-background/50 p-4">
                  <FieldLabel label="音量" />
                  <input
                    id="bgm-volume"
                    type="range"
                    min="0.05"
                    max="0.3"
                    step="0.01"
                    value={bgmVolume}
                    onChange={(e) => setBgmVolume(Number(e.target.value))}
                    disabled={submitting}
                    className="mt-4 w-full accent-primary"
                  />
                  <div className="mt-3 flex justify-between text-[10px] uppercase tracking-wider text-foreground/26">
                    <span>轻微</span>
                    <span className="font-mono text-foreground/55">{bgmVolume.toFixed(2)}</span>
                    <span>明显</span>
                  </div>
                </div>
              </div>

              <div className="mt-6 flex justify-end">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setBgmEnabled(false)}
                  className="border-border bg-background/50 text-foreground/75 hover:bg-background hover:text-foreground"
                >
                  关闭
                </Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </form>
  );
}
