"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
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
import type { TaskCreatePayload } from "@/types";
import { Loader2, Wand2 } from "lucide-react";

const VOICES = [
  { id: "female-tianmei", label: "甜美女声" },
  { id: "male-qn-qingse", label: "清新男声" },
  { id: "presenter_male", label: "专业播音" },
  { id: "audiobook_male_1", label: "故事旁白" },
  { id: "female-shaonv", label: "活泼女声" },
];

const QUALITIES = [
  { value: "high", label: "高清 (1080p60)" },
  { value: "medium", label: "标清 (480p)" },
  { value: "low", label: "流畅 (360p)" },
];

const PRESETS = [
  { value: "default", label: "默认" },
  { value: "educational", label: "教学讲解" },
  { value: "presentation", label: "演示汇报" },
  { value: "proof", label: "证明推导" },
  { value: "concept", label: "概念可视化" },
];

export function TaskForm() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [voiceId, setVoiceId] = useState("female-tianmei");
  const [quality, setQuality] = useState<"high" | "medium" | "low">("high");
  const [preset, setPreset] = useState<"default" | "educational" | "presentation" | "proof" | "concept">("default");
  const [noTts, setNoTts] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const payload: TaskCreatePayload = {
        user_text: text.trim(),
        voice_id: voiceId,
        model: "speech-2.8-hd",
        quality,
        preset,
        no_tts: noTts,
      };
      const task = await createTask(payload);
      router.push(`/tasks/${task.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建任务失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="glass-card rounded-2xl p-6 sm:p-8 space-y-6 glow-border transition-all duration-300">
      {/* Natural language input */}
      <div className="space-y-2">
        <label htmlFor="prompt" className="text-sm font-medium text-foreground/80">
          描述你想生成的动画
        </label>
        <Textarea
          id="prompt"
          placeholder='例如："用动画演示勾股定理的证明过程"'
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={4}
          disabled={submitting}
          className="resize-none bg-background/50 border-border/50 text-foreground placeholder:text-muted-foreground/60 focus:border-primary/40 focus:ring-primary/20 transition-colors"
        />
      </div>

      {/* Options row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="space-y-2">
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">音色</label>
          <Select value={voiceId} onValueChange={(v) => v && setVoiceId(v)} disabled={submitting}>
            <SelectTrigger className="bg-background/50 border-border/50 focus:border-primary/40 focus:ring-primary/20 transition-colors">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {VOICES.map((v) => (
                <SelectItem key={v.id} value={v.id}>
                  {v.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">画质</label>
          <Select
            value={quality}
            onValueChange={(v) => v && setQuality(v as "high" | "medium" | "low")}
            disabled={submitting}
          >
            <SelectTrigger className="bg-background/50 border-border/50 focus:border-primary/40 focus:ring-primary/20 transition-colors">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {QUALITIES.map((q) => (
                <SelectItem key={q.value} value={q.value}>
                  {q.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">模式</label>
          <Select value={preset} onValueChange={(v) => v && setPreset(v as "default" | "educational" | "presentation" | "proof" | "concept")} disabled={submitting}>
            <SelectTrigger className="bg-background/50 border-border/50 focus:border-primary/40 focus:ring-primary/20 transition-colors">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PRESETS.map((p) => (
                <SelectItem key={p.value} value={p.value}>
                  {p.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Skip TTS toggle */}
      <label className="flex items-center gap-2.5 text-sm cursor-pointer group select-none">
        <div className={`relative w-4 h-4 rounded border transition-colors ${noTts ? "bg-primary border-primary" : "border-border/60 group-hover:border-border"}`}>
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
        <span className="text-muted-foreground group-hover:text-foreground/80 transition-colors">跳过语音合成（仅静音视频）</span>
      </label>

      {/* Error message */}
      {error && (
        <p className="text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-md px-3 py-2">{error}</p>
      )}

      {/* Submit */}
      <Button
        type="submit"
        disabled={submitting || !text.trim()}
        size="lg"
        className="w-full btn-glow font-medium h-11"
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
          </>
        )}
      </Button>
    </form>
  );
}
