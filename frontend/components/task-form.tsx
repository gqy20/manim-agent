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
      className="flex h-full min-h-0 flex-col gap-4"
    >
      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[minmax(0,1.5fr)_minmax(320px,1fr)] lg:items-stretch lg:content-start">
        {/* Left — Input */}
        <div className="flex min-h-0 flex-col gap-4">
          <div className="flex min-h-0 flex-1 flex-col gap-4 rounded-2xl border border-border bg-card p-5">
            <p className="text-sm text-foreground/50">
              用一句完整描述定义这次动画任务。
            </p>

            <Textarea
              id="prompt"
              placeholder='例如："用动画演示勾股定理的证明过程"'
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={8}
              disabled={submitting}
              className="min-h-[160px] flex-1 resize-none rounded-xl border-border bg-background px-4 py-3 text-[15px] leading-relaxed placeholder:text-muted-foreground/40 focus:border-primary/30 focus:ring-primary/15"
            />

            <div className="flex gap-2">
              {TEMPLATES.map((template) => (
                <button
                  key={template.text}
                  type="button"
                  onClick={() => handleTemplate(template.text)}
                  disabled={submitting || clarifying}
                  className="flex items-center gap-2 rounded-xl border border-border bg-background px-3 py-2 text-left transition hover:border-foreground/15 hover:bg-foreground/[0.03]"
                >
                  <span className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border bg-foreground/[0.04] text-[10px] font-mono text-foreground/50">
                    {template.icon}
                  </span>
                  <span className="line-clamp-1 text-xs text-foreground/50">{template.text}</span>
                </button>
              ))}
            </div>

            {clarification && clarificationSourceText === text.trim() && (
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
            )}
          </div>

          {/* BGM Panel */}
          {bgmPanelVisible && (
            <div className="rounded-2xl border border-border bg-card p-5">
              <div className="mb-4">
                <h3 className="text-sm font-medium text-foreground/85">背景音乐层</h3>
                <p className="mt-1 text-sm text-foreground/44">为讲解铺一层低干扰背景音乐。</p>
              </div>

              <div className="gap-4 xl:grid xl:grid-cols-[minmax(0,1fr)_200px]">
                <div>
                  <FieldLabel label="配乐描述" />
                  <Textarea
                    id="bgm-prompt"
                    value={bgmPrompt}
                    onChange={(e) => setBgmPrompt(e.target.value)}
                    rows={3}
                    disabled={submitting}
                    placeholder="例如：冷静、极简、轻微存在感的钢琴与弦乐，不要人声"
                    className="mt-2 min-h-[100px] resize-none rounded-xl border-border bg-background px-4 py-3 text-[13px] leading-6 placeholder:text-muted-foreground/40 focus:border-primary/30"
                  />
                </div>

                <div>
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
                    className="mt-3 w-full accent-primary"
                  />
                  <div className="mt-2 flex justify-between text-[10px] uppercase tracking-wider text-foreground/26">
                    <span>轻微</span>
                    <span className="font-mono text-foreground/55">{bgmVolume.toFixed(2)}</span>
                    <span>明显</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right — Params + Actions */}
        <aside className="flex min-h-0 flex-col gap-4">
          <div className="rounded-2xl border border-border bg-card p-4 space-y-4">
            <div>
              <h3 className="text-sm font-medium text-foreground/82">交付参数</h3>
              <p className="mt-0.5 text-xs text-foreground/38">决定交付风格与制作规格。</p>
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
          <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4">
            <div className="space-y-2.5">
              <label className="flex cursor-pointer items-center gap-2.5 rounded-xl border border-border px-3 py-2 select-none transition-colors hover:bg-foreground/[0.02]">
                <div
                  className={`relative h-4 w-4 rounded border transition-colors ${
                    noTts ? "border-primary bg-primary" : "border-border"
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
                    <svg className="pointer-events-none absolute inset-0 m-auto h-3 w-3 text-primary-foreground" viewBox="0 0 12 12" fill="none">
                      <path d="M2 6l3 3l5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </div>
                <span className="text-[13px] text-foreground/65">跳过语音合成，仅生成静音视频</span>
              </label>

              <button
                type="button"
                onClick={() => { if (submitting || noTts) return; setBgmEnabled((v) => !v); }}
                disabled={submitting || noTts}
                className="flex items-center gap-3 rounded-xl border border-border px-3 py-2 text-left transition-colors hover:bg-foreground/[0.02] disabled:opacity-50"
              >
                <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border transition-colors ${bgmPanelVisible ? "border-primary/30 bg-primary/10 text-primary" : "border-border bg-foreground/[0.03] text-foreground/36"}`}>
                  <Music4 className="h-3.5 w-3.5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-foreground/80">背景音乐</span>
                    <span className={`rounded-full px-1.5 py-px text-[10px] ${bgmPanelVisible ? "bg-primary/10 text-primary" : "bg-foreground/[0.05] text-foreground/32"}`}>
                      {bgmPanelVisible ? "On" : "Off"}
                    </span>
                  </div>
                  <p className="mt-0.5 text-[12px] text-foreground/40">
                    {bgmPanelVisible ? "左侧已展开编辑面板。" : "点击展开背景音乐配置。"}
                  </p>
                </div>
                <span className="text-[11px] font-mono text-foreground/36">{bgmVolume.toFixed(2)}</span>
              </button>

              {error && (
                <p className="rounded-lg border border-destructive/20 bg-destructive/8 px-3 py-2.5 text-sm text-destructive animate-fade-in-up">
                  {error}
                </p>
              )}
            </div>

            <div className="mt-auto space-y-2 pt-1">
              <motion.div whileHover={canSubmit ? { scale: 1.005 } : {}} whileTap={canSubmit ? { scale: 0.98 } : {}}>
                <Button
                  type="submit"
                  disabled={!canSubmit}
                  size="lg"
                  className="w-full h-10.5 text-[14px] font-medium btn-glow"
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
                    className="h-9 border-border bg-transparent text-foreground/70 hover:bg-foreground/[0.04] hover:text-foreground/85"
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
                    className="h-9 border border-border bg-foreground/[0.06] text-foreground/80 hover:bg-foreground/[0.1]"
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
    </form>
  );
}
