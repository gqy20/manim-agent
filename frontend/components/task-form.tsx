"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { Loader2, Sparkles, Wand2 } from "lucide-react";

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
  { id: "female-shaonv", label: "活泼女声" },
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
  { text: "演示圆周率 pi 的几何意义和计算方法", icon: "C" },
  { text: "用动画解释傅里叶级数如何分解波形", icon: "D" },
];

function getLabel<T extends { id?: string | number; value?: string | number; label: string }>(
  list: T[],
  key: string,
): string {
  return list.find((item) => String(item.id ?? item.value) === key)?.label ?? key;
}

function ClarificationList({
  title,
  items,
}: {
  title: string;
  items: string[];
}) {
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

export function TaskForm() {
  const router = useRouter();
  const formRef = useRef<HTMLFormElement>(null);

  const [text, setText] = useState("");
  const [voiceId, setVoiceId] = useState("female-tianmei");
  const [quality, setQuality] = useState<"high" | "medium" | "low">("high");
  const [preset, setPreset] = useState<
    "default" | "educational" | "presentation" | "proof" | "concept"
  >("default");
  const [targetDurationSeconds, setTargetDurationSeconds] =
    useState<TaskDurationSeconds>(60);
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
    }, 30);
  }, []);

  const handlePromptChange = useCallback(
    (value: string) => {
      setText(value);
      if (clarification && value.trim() !== clarificationSourceText) {
        setClarification(null);
        setClarificationSourceText("");
      }
    },
    [clarification, clarificationSourceText],
  );

  const runTaskCreation = useCallback(
    async (finalUserText: string) => {
      setSubmitting(true);
      setError(null);

      const formEl = document.querySelector(".glass-card");
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
              gsap.to(formEl, {
                y: 0,
                opacity: 1,
                filter: "blur(0px)",
                scale: 1,
                duration: 0.4,
              });
            });
        },
      });

      if (formEl) {
        tl.to(formEl, {
          y: -40,
          opacity: 0,
          scale: 0.95,
          filter: "blur(10px)",
          duration: 0.6,
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

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const normalized = text.trim();
    if (!normalized) return;

    if (clarification && clarificationSourceText === normalized) {
      await runTaskCreation(clarification.recommended_request_cn);
      return;
    }

    setClarifying(true);
    setError(null);
    try {
      const result = await clarifyContent({ user_text: normalized });
      setClarification(result.clarification);
      setClarificationSourceText(normalized);
    } catch (err) {
      setError(err instanceof Error ? err.message : "内容理解失败");
    } finally {
      setClarifying(false);
    }
  }

  const hasCurrentClarification =
    !!clarification && clarificationSourceText === text.trim();
  const canSubmit = !submitting && !clarifying && !!text.trim();

  useGSAP(() => {
    if (!formRef.current) return;
    gsap.fromTo(
      formRef.current,
      { y: 30, opacity: 0, scale: 0.98 },
      { y: 0, opacity: 1, scale: 1, duration: 0.8, ease: "power3.out", delay: 0.2 },
    );
  }, { scope: formRef });

  return (
    <form
      ref={formRef}
      onSubmit={handleSubmit}
      className="glass-card rounded-2xl p-6 sm:p-8 glow-border transition-all duration-300"
    >
      <div className="space-y-2.5 relative group">
        <div className="absolute -inset-0.5 bg-gradient-to-r from-primary/30 to-indigo-500/30 rounded-lg blur opacity-0 group-focus-within:opacity-100 transition duration-1000 group-hover:duration-200 pointer-events-none" />
        <label
          htmlFor="prompt"
          className="relative text-sm font-medium text-foreground/80 flex items-center gap-1.5"
        >
          <Sparkles className="h-3.5 w-3.5 text-primary/70" />
          描述你想生成的动画
        </label>
        <Textarea
          id="prompt"
          placeholder='例如："用动画演示勾股定理的证明过程"'
          value={text}
          onChange={(e) => handlePromptChange(e.target.value)}
          rows={8}
          disabled={submitting}
          className="relative resize-none min-h-[160px] max-h-[300px] overflow-y-auto bg-background/60 border-white/5 text-foreground placeholder:text-muted-foreground/40 focus:border-primary/30 focus:ring-primary/20 transition-all duration-300 text-[15px] leading-relaxed shadow-inner"
        />
        <div className="flex flex-wrap gap-2 mt-3">
          {TEMPLATES.slice(0, 2).map((template) => (
            <button
              key={template.text}
              type="button"
              onClick={() => handleTemplate(template.text)}
              disabled={submitting || clarifying}
              className="text-[11px] flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-white/10 bg-white/5 text-white/50 hover:text-white/80 hover:bg-white/10 hover:border-white/20 transition-all cursor-pointer"
            >
              <span>{template.icon}</span>
              <span className="truncate max-w-[180px]">{template.text}</span>
            </button>
          ))}
        </div>
      </div>

      {clarification && clarificationSourceText === text.trim() && (
        <div className="mt-5 rounded-2xl border border-cyan-400/20 bg-cyan-400/[0.06] p-4 sm:p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-cyan-300/70">
                内容理解确认
              </p>
              <p className="mt-1 text-sm text-foreground/85">
                我会按下面这份理解来生成动画。你可以直接继续，也可以修改原始输入后重新理解。
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setClarification(null);
                setClarificationSourceText("");
              }}
              disabled={submitting || clarifying}
              className="border-white/15 bg-transparent text-white/70 hover:bg-white/10 hover:text-white"
            >
              重新编辑
            </Button>
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-2">
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
              <section>
                <p className="text-xs font-medium text-white/45">内容摘要</p>
                <p className="mt-1 text-sm leading-6 text-white/85">
                  {clarification.clarified_brief_cn}
                </p>
              </section>
            </div>

            <div className="space-y-3">
              <section>
                <p className="text-xs font-medium text-white/45">关键前置概念</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {clarification.prerequisite_concepts.map((item) => (
                    <span
                      key={item}
                      className="rounded-full border border-white/10 bg-white/[0.06] px-2.5 py-1 text-[11px] text-white/75"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </section>
              <ClarificationList title="推荐讲解主线" items={clarification.explanation_path} />
            </div>
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <ClarificationList title="默认边界" items={clarification.scope_boundaries} />
            <ClarificationList title="可选分支" items={clarification.optional_branches} />
            <ClarificationList title="动画表达重点" items={clarification.animation_focus} />
          </div>

          {clarification.ambiguity_notes.length > 0 && (
            <section className="mt-4 rounded-xl border border-amber-300/20 bg-amber-300/[0.06] p-3">
              <p className="text-xs font-medium text-amber-200/80">待确认歧义</p>
              <ul className="mt-2 space-y-1.5 text-sm text-amber-50/85">
                {clarification.ambiguity_notes.map((item) => (
                  <li key={item}>- {item}</li>
                ))}
              </ul>
            </section>
          )}

          <section className="mt-4 rounded-xl border border-white/10 bg-black/15 p-3">
            <p className="text-xs font-medium text-white/45">推荐提交文本</p>
            <p className="mt-2 text-sm leading-6 text-white/88">
              {clarification.recommended_request_cn}
            </p>
          </section>
        </div>
      )}

      <div className="pt-4">
        <div className="grid grid-cols-1 gap-4 pb-2 md:grid-cols-2 xl:grid-cols-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
            <label className="text-[11px] font-medium text-white/30 uppercase tracking-wider shrink-0 w-6">
              音色
            </label>
            <Select value={voiceId} onValueChange={(v) => v && setVoiceId(v)} disabled={submitting}>
              <SelectTrigger className="min-h-10 w-full bg-transparent border-white/10 text-[12px] font-medium text-white/80 shadow-none transition-colors hover:border-white/20 focus:border-primary/40 focus:ring-primary/20 sm:min-h-8 sm:text-[11px]">
                <SelectValue>{getLabel(VOICES, voiceId)}</SelectValue>
              </SelectTrigger>
              <SelectContent className="bg-black/80 backdrop-blur-xl border border-white/10">
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

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
            <label className="text-[11px] font-medium text-white/30 uppercase tracking-wider shrink-0 w-6">
              画质
            </label>
            <Select
              value={quality}
              onValueChange={(v) => v && setQuality(v as "high" | "medium" | "low")}
              disabled={submitting}
            >
              <SelectTrigger className="min-h-10 w-full bg-transparent border-white/10 text-[12px] font-medium text-white/80 shadow-none transition-colors hover:border-white/20 focus:border-primary/40 focus:ring-primary/20 sm:min-h-8 sm:text-[11px]">
                <SelectValue>{getLabel(QUALITIES, quality)}</SelectValue>
              </SelectTrigger>
              <SelectContent className="bg-black/80 backdrop-blur-xl border border-white/10">
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

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
            <label className="text-[11px] font-medium text-white/30 uppercase tracking-wider shrink-0 w-6">
              模式
            </label>
            <Select
              value={preset}
              onValueChange={(v) =>
                v && setPreset(v as "default" | "educational" | "presentation" | "proof" | "concept")
              }
              disabled={submitting}
            >
              <SelectTrigger className="min-h-10 w-full bg-transparent border-white/10 text-[12px] font-medium text-white/80 shadow-none transition-colors hover:border-white/20 focus:border-primary/40 focus:ring-primary/20 sm:min-h-8 sm:text-[11px]">
                <SelectValue>{getLabel(PRESETS, preset)}</SelectValue>
              </SelectTrigger>
              <SelectContent className="bg-black/80 backdrop-blur-xl border border-white/10">
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

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
            <label className="text-[11px] font-medium text-white/30 uppercase tracking-wider shrink-0 w-6">
              时长
            </label>
            <Select
              value={String(targetDurationSeconds)}
              onValueChange={(v) =>
                v && setTargetDurationSeconds(Number(v) as TaskDurationSeconds)
              }
              disabled={submitting}
            >
              <SelectTrigger className="min-h-10 w-full bg-transparent border-white/10 text-[12px] font-medium text-white/80 shadow-none transition-colors hover:border-white/20 focus:border-primary/40 focus:ring-primary/20 sm:min-h-8 sm:text-[11px]">
                <SelectValue>{getLabel(DURATIONS, String(targetDurationSeconds))}</SelectValue>
              </SelectTrigger>
              <SelectContent className="bg-black/80 backdrop-blur-xl border border-white/10">
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
      </div>

      <label className="flex items-center gap-2.5 text-sm cursor-pointer group select-none mt-4 mb-4">
        <div
          className={`relative w-4 h-4 rounded border transition-colors duration-200 ${
            noTts
              ? "bg-primary border-primary"
              : "border-border/60 group-hover:border-foreground/30 bg-background/30"
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
              className="absolute inset-0 m-auto w-3 h-3 text-primary-foreground pointer-events-none"
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
        <span className="text-muted-foreground/80 group-hover:text-foreground/70 transition-colors text-[13px]">
          跳过语音合成，仅生成静音视频
        </span>
      </label>

      <div className="mb-4 rounded-xl border border-white/8 bg-white/[0.03] p-4">
        <label className="flex items-start gap-3 cursor-pointer group select-none">
          <div
            className={`relative mt-0.5 h-4 w-4 rounded border transition-colors duration-200 ${
              bgmEnabled && !noTts
                ? "bg-primary border-primary"
                : "border-border/60 group-hover:border-foreground/30 bg-background/30"
            }`}
          >
            <input
              type="checkbox"
              checked={bgmEnabled}
              onChange={(e) => setBgmEnabled(e.target.checked)}
              disabled={submitting || noTts}
              className="sr-only"
            />
            {bgmEnabled && !noTts && (
              <svg
                className="absolute inset-0 m-auto h-3 w-3 text-primary-foreground pointer-events-none"
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
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-[13px] font-medium text-foreground/85">添加纯音乐背景</span>
              <span className="rounded-full border border-cyan-400/15 bg-cyan-400/8 px-2 py-0.5 text-[10px] uppercase tracking-wider text-cyan-300/70">
                music-2.6
              </span>
            </div>
            <p className="text-[12px] leading-relaxed text-muted-foreground/70">
              在解说下方加一层低干扰背景音乐。留空 prompt 时，系统会根据动画模式自动生成适合的配乐描述。
            </p>
            {noTts && (
              <p className="text-[11px] text-amber-300/80">
                当前已开启静音视频，背景音乐会一起禁用。
              </p>
            )}
          </div>
        </label>

        {bgmEnabled && !noTts && (
          <div className="mt-4 grid gap-4 md:grid-cols-[1.6fr_0.8fr]">
            <div className="space-y-2">
              <label
                htmlFor="bgm-prompt"
                className="text-[11px] font-medium uppercase tracking-wider text-white/45"
              >
                BGM Prompt
              </label>
              <Textarea
                id="bgm-prompt"
                value={bgmPrompt}
                onChange={(e) => setBgmPrompt(e.target.value)}
                rows={4}
                disabled={submitting}
                placeholder="例如：calm instrumental underscore, soft piano and light strings, no vocals"
                className="min-h-[96px] resize-none bg-background/40 border-white/10 text-[13px] text-foreground/85 placeholder:text-muted-foreground/40"
              />
              <p className="text-[11px] text-muted-foreground/65">
                可以不填。默认会生成适合教学解说视频的背景音乐，不会加入人声。
              </p>
            </div>

            <div className="space-y-3 rounded-lg border border-white/8 bg-black/15 p-3">
              <div className="space-y-1">
                <label
                  htmlFor="bgm-volume"
                  className="text-[11px] font-medium uppercase tracking-wider text-white/45"
                >
                  Volume
                </label>
                <div className="flex items-baseline justify-between">
                  <span className="text-[12px] text-muted-foreground/70">混流音量</span>
                  <span className="font-mono text-sm text-cyan-300">{bgmVolume.toFixed(2)}</span>
                </div>
              </div>
              <input
                id="bgm-volume"
                type="range"
                min="0.05"
                max="0.30"
                step="0.01"
                value={bgmVolume}
                onChange={(e) => setBgmVolume(Number(e.target.value))}
                disabled={submitting}
                className="w-full accent-cyan-400"
              />
              <div className="flex justify-between text-[10px] uppercase tracking-wider text-white/30">
                <span>Subtle</span>
                <span>Present</span>
              </div>
              <p className="text-[11px] leading-relaxed text-muted-foreground/65">
                建议保持在 0.10 到 0.16，这样能托底但不会压过解说。
              </p>
            </div>
          </div>
        )}
      </div>

      {error && (
        <p className="text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2.5 animate-fade-in-up mb-4">
          {error}
        </p>
      )}

      <motion.div
        className="relative"
        whileHover={canSubmit ? { scale: 1.01 } : {}}
        whileTap={canSubmit ? { scale: 0.98 } : {}}
      >
        <Button
          type="submit"
          disabled={!canSubmit}
          size="lg"
          className="w-full btn-glow font-medium h-12 text-[15px] relative overflow-hidden"
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
              <div className="absolute inset-0 bg-white/20 blur opacity-0 hover:opacity-100 transition-opacity duration-300" />
            </>
          )}
        </Button>
      </motion.div>
    </form>
  );
}
