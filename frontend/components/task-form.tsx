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
import { Loader2 } from "lucide-react";

const VOICES = [
  { id: "female-tianmei", label: "Tianmei (Sweet)" },
  { id: "male-qn-qingse", label: "Qingse (Fresh)" },
  { id: "presenter_male", label: "Presenter (Professional)" },
  { id: "audiobook_male_1", label: "Audiobook (Narrator)" },
  { id: "female-shaonv", label: "Shaonv (Lively)" },
];

const QUALITIES = [
  { value: "high", label: "High (720p)" },
  { value: "medium", label: "Medium (480p)" },
  { value: "low", label: "Low (360p)" },
];

const PRESETS = [
  { value: "default", label: "Default" },
  { value: "educational", label: "Educational" },
  { value: "presentation", label: "Presentation" },
  { value: "proof", label: "Proof" },
  { value: "concept", label: "Concept Visualization" },
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
      setError(err instanceof Error ? err.message : "Failed to create task");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-2xl mx-auto">
      {/* Natural language input */}
      <div className="space-y-2">
        <label htmlFor="prompt" className="text-sm font-medium">
          Describe your animation
        </label>
        <Textarea
          id="prompt"
          placeholder='e.g. "Explain the Pythagorean theorem with a visual proof"'
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={5}
          disabled={submitting}
          className="resize-none"
        />
      </div>

      {/* Options row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="space-y-2">
          <label className="text-sm font-medium">Voice</label>
          <Select value={voiceId} onValueChange={(v) => v && setVoiceId(v)} disabled={submitting}>
            <SelectTrigger>
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
          <label className="text-sm font-medium">Quality</label>
          <Select
            value={quality}
            onValueChange={(v) => v && setQuality(v as "high" | "medium" | "low")}
            disabled={submitting}
          >
            <SelectTrigger>
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
          <label className="text-sm font-medium">Mode</label>
          <Select value={preset} onValueChange={(v) => v && setPreset(v as "default" | "educational" | "presentation" | "proof" | "concept")} disabled={submitting}>
            <SelectTrigger>
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
      <label className="flex items-center gap-2 text-sm cursor-pointer">
        <input
          type="checkbox"
          checked={noTts}
          onChange={(e) => setNoTts(e.target.checked)}
          disabled={submitting}
          className="rounded"
        />
        Skip TTS (silent video only)
      </label>

      {/* Error message */}
      {error && (
        <p className="text-sm text-red-500">{error}</p>
      )}

      {/* Submit */}
      <Button type="submit" disabled={submitting || !text.trim()} size="lg" className="w-full">
        {submitting ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Creating task...
          </>
        ) : (
          "Generate Video"
        )}
      </Button>
    </form>
  );
}
