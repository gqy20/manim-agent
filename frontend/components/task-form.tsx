"use client";

import { useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { createTask } from "@/lib/api";
import { logger } from "@/lib/logger";
import type { TaskDurationSeconds } from "@/types";
import { Loader2, Wand2, ChevronDown, Sparkles } from "lucide-react";

/* ── Data ────────────────────────────────────────── */

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
  { value: 30, label: "30秒" },
  { value: 60, label: "1分钟" },
  { value: 180, label: "3分钟" },
  { value: 300, label: "5分钟" },
];

const TEMPLATES = [
  { text: "用动画演示勾股定理的证明过程", icon: "📐" },
  { text: "可视化二次函数 y=ax²+bx+c 的图像变换", icon: "📈" },
  { text: "演示圆周率 π 的几何意义和计算方法", icon: "🔄" },
  { text: "用动画解释傅里叶级数如何分解波形", icon: "🌊" },
  { text: "展示欧拉公式 e^(iπ) + 1 = 0 的直观理解", icon: "∞" },
  { text: "动画呈现微积分中极限的 ε-δ 定义", icon: "ε" },
];

/* ── Helpers ─────────────────────────────────────── */

function getLabel<T extends { id?: string | number; value?: string | number; label: string }>(
  list: T[],
  key: string,
): string {
  return (
    list.find((item) => String(item.id ?? item.value) === key)?.label ?? key
  );
}

/* ── Component ───────────────────────────────────── */

export function TaskForm() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [voiceId, setVoiceId] = useState("female-tianmei");
  const [quality, setQuality] = useState<"high" | "medium" | "low">("high");
  const [preset, setPreset] = useState<"default" | "educational" | "presentation" | "proof" | "concept">("default");
  const [targetDurationSeconds, setTargetDurationSeconds] = useState<TaskDurationSeconds>(60);
  const [noTts, setNoTts] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showAllTemplates, setShowAllTemplates] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  const handleTemplate = useCallback((templateText: string) => {
    setText("");
    let i = 0;
    const interval = setInterval(() => {
      setText(templateText.slice(0, i + 1));
      i++;
      if (i >= templateText.length) clearInterval(interval);
    }, 30);
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setSubmitting(true);
    setError(null);

    // Get the button element and form container to animate out
    const formEl = document.querySelector(".glass-card");
    
    // Play an exit timeline animation before actually redirecting
    const tl = gsap.timeline({
      onComplete: () => {
        createTask({
          user_text: text.trim(),
          voice_id: voiceId,
          model: "speech-2.8-hd",
          quality,
          preset,
          no_tts: noTts,
          target_duration_seconds: targetDurationSeconds,
        })
          .then((task) => {
            if (!task?.id) {
              logger.error("task-form", "createTask returned empty task id", { task });
              throw new Error("创建任务失败：服务返回空任务ID");
            }
            console.debug("[TaskForm] createTask success", task.id);
            router.push(`/tasks/${task.id}`);
          })
          .catch((err) => {
            setError(err instanceof Error ? err.message : "创建任务失败");
            setSubmitting(false);
            // Restore form if error
            gsap.to(formEl, { y: 0, opacity: 1, filter: "blur(0px)", scale: 1, duration: 0.4 });
          });
      }
    });

    if (formEl) {
      tl.to(formEl, {
        y: -40,
        opacity: 0,
        scale: 0.95,
        filter: "blur(10px)",
        duration: 0.6,
        ease: "power3.in"
      });
    } else {
      tl.play();
    }
  }

  const canSubmit = !submitting && !!text.trim();

  // Intro animation for the form
  useGSAP(() => {
    if (!formRef.current) return;
    
    gsap.fromTo(formRef.current, 
      { y: 30, opacity: 0, scale: 0.98 },
      { y: 0, opacity: 1, scale: 1, duration: 0.8, ease: "power3.out", delay: 0.2 }
    );
  }, { scope: formRef });

  return (
    <form ref={formRef} onSubmit={handleSubmit} className="glass-card rounded-2xl p-6 sm:p-8 glow-border transition-all duration-300">
      {/* Natural language input */}
      <div className="space-y-2.5 relative group">
        <div className="absolute -inset-0.5 bg-gradient-to-r from-primary/30 to-indigo-500/30 rounded-lg blur opacity-0 group-focus-within:opacity-100 transition duration-1000 group-hover:duration-200 pointer-events-none" />
        <label htmlFor="prompt" className="relative text-sm font-medium text-foreground/80 flex items-center gap-1.5">
          <Sparkles className="h-3.5 w-3.5 text-primary/70" />
          描述你想生成的动画
        </label>
        <Textarea
          id="prompt"
          placeholder='例如："用动画演示勾股定理的证明过程"'
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={8}
          disabled={submitting}
          className="relative resize-none min-h-[160px] max-h-[300px] overflow-y-auto bg-background/60 border-white/5 text-foreground placeholder:text-muted-foreground/40 focus:border-primary/30 focus:ring-primary/20 transition-all duration-300 text-[15px] leading-relaxed shadow-inner"
        />
        
        {/* Templates short list */}
        <div className="flex flex-wrap gap-2 mt-3">
          {TEMPLATES.slice(0, 2).map((t) => (
            <button
              key={t.text}
              type="button"
              onClick={() => handleTemplate(t.text)}
              disabled={submitting}
              className="text-[11px] flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-white/10 bg-white/5 text-white/50 hover:text-white/80 hover:bg-white/10 hover:border-white/20 transition-all cursor-pointer"
            >
              <span>{t.icon}</span>
              <span className="truncate max-w-[180px]">{t.text}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Advanced options */}
      <div className="pt-4">
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 pb-2">
          {/* Voice */}
          <div className="flex items-center gap-4">
            <label className="text-[11px] font-medium text-white/30 uppercase tracking-wider shrink-0 w-6">音色</label>
            <Select value={voiceId} onValueChange={(v) => v && setVoiceId(v)} disabled={submitting}>
              <SelectTrigger className="w-full bg-transparent border-white/10 hover:border-white/20 focus:border-primary/40 focus:ring-primary/20 transition-colors h-8 text-[11px] text-white/80 shadow-none font-medium">
                <SelectValue>{getLabel(VOICES, voiceId)}</SelectValue>
              </SelectTrigger>
              <SelectContent className="bg-black/80 backdrop-blur-xl border border-white/10">
                {VOICES.map((v) => (
                  <SelectItem key={v.id} value={v.id} className="text-[11px] text-white/70 focus:bg-white/10 focus:text-white">{v.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Quality */}
          <div className="flex items-center gap-4">
            <label className="text-[11px] font-medium text-white/30 uppercase tracking-wider shrink-0 w-6">画质</label>
            <Select value={quality} onValueChange={(v) => v && setQuality(v as "high" | "medium" | "low")} disabled={submitting}>
              <SelectTrigger className="w-full bg-transparent border-white/10 hover:border-white/20 focus:border-primary/40 focus:ring-primary/20 transition-colors h-8 text-[11px] text-white/80 shadow-none font-medium">
                <SelectValue>{getLabel(QUALITIES, quality)}</SelectValue>
              </SelectTrigger>
              <SelectContent className="bg-black/80 backdrop-blur-xl border border-white/10">
                {QUALITIES.map((q) => (
                  <SelectItem key={q.value} value={q.value} className="text-[11px] text-white/70 focus:bg-white/10 focus:text-white">{q.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Preset */}
          <div className="flex items-center gap-4">
            <label className="text-[11px] font-medium text-white/30 uppercase tracking-wider shrink-0 w-6">模式</label>
            <Select value={preset} onValueChange={(v) => v && setPreset(v as "default" | "educational" | "presentation" | "proof" | "concept")} disabled={submitting}>
              <SelectTrigger className="w-full bg-transparent border-white/10 hover:border-white/20 focus:border-primary/40 focus:ring-primary/20 transition-colors h-8 text-[11px] text-white/80 shadow-none font-medium">
                <SelectValue>{getLabel(PRESETS, preset)}</SelectValue>
              </SelectTrigger>
              <SelectContent className="bg-black/80 backdrop-blur-xl border border-white/10">
                {PRESETS.map((p) => (
                  <SelectItem key={p.value} value={p.value} className="text-[11px] text-white/70 focus:bg-white/10 focus:text-white">{p.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Duration */}
          <div className="flex items-center gap-4">
            <label className="text-[11px] font-medium text-white/30 uppercase tracking-wider shrink-0 w-6">时长</label>
            <Select
              value={String(targetDurationSeconds)}
              onValueChange={(v) =>
                v && setTargetDurationSeconds(Number(v) as TaskDurationSeconds)
              }
              disabled={submitting}
            >
              <SelectTrigger className="w-full bg-transparent border-white/10 hover:border-white/20 focus:border-primary/40 focus:ring-primary/20 transition-colors h-8 text-[11px] text-white/80 shadow-none font-medium">
                <SelectValue>{getLabel(DURATIONS, String(targetDurationSeconds))}</SelectValue>
              </SelectTrigger>
              <SelectContent className="bg-black/80 backdrop-blur-xl border border-white/10">
                {DURATIONS.map((duration) => (
                  <SelectItem key={duration.value} value={String(duration.value)} className="text-[11px] text-white/70 focus:bg-white/10 focus:text-white">
                    {duration.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      {/* Skip TTS toggle */}
      <label className="flex items-center gap-2.5 text-sm cursor-pointer group select-none mt-4 mb-4">
        <div className={`relative w-4 h-4 rounded border transition-colors duration-200 ${noTts ? "bg-primary border-primary" : "border-border/60 group-hover:border-foreground/30 bg-background/30"}`}>
          <input
            type="checkbox"
            checked={noTts}
            onChange={(e) => setNoTts(e.target.checked)}
            disabled={submitting}
            className="sr-only"
          />
          {noTts && (
            <svg className="absolute inset-0 m-auto w-3 h-3 text-primary-foreground pointer-events-none" viewBox="0 0 12 12" fill="none">
              <path d="M2 6l3 3l5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          )}
        </div>
        <span className="text-muted-foreground/80 group-hover:text-foreground/70 transition-colors text-[13px]">跳过语音合成（仅静音视频）</span>
      </label>

      {/* Error message */}
      {error && (
        <p className="text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2.5 animate-fade-in-up mb-4">{error}</p>
      )}

      {/* Submit button */}
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
          ) : (
            <>
              <Wand2 className="mr-2 h-4 w-4" />
              开始生成
              <div className="absolute inset-0 bg-white/20 blur opacity-0 hover:opacity-100 transition-opacity duration-300" />
            </>
          )}
        </Button>
      </motion.div>
    </form>
  );
}
