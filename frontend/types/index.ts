export type TaskStatus = "pending" | "running" | "completed" | "failed" | "stopped";
export type TaskDurationSeconds = 30 | 60 | 180 | 300;

export interface TaskCreatePayload {
  user_text: string;
  voice_id: string;
  model: string;
  quality: "high" | "medium" | "low";
  preset: "default" | "educational" | "presentation" | "proof" | "concept";
  no_tts: boolean;
  bgm_enabled: boolean;
  bgm_prompt: string | null;
  bgm_volume: number;
  target_duration_seconds: TaskDurationSeconds;
}

export interface ClarifyContentPayload {
  user_text: string;
}

export interface ContentClarifyData {
  topic_interpretation: string;
  core_question: string;
  prerequisite_concepts: string[];
  explanation_path: string[];
  scope_boundaries: string[];
  optional_branches: string[];
  animation_focus: string[];
  ambiguity_notes: string[];
  clarified_brief_cn: string;
  recommended_request_cn: string;
}

export interface ClarifyContentResponse {
  original_user_text: string;
  clarification: ContentClarifyData;
}

export interface PipelineOutputData {
  video_output: string | null;
  final_video_output: string | null;
  scene_file: string | null;
  scene_class: string | null;
  duration_seconds: number | null;
  narration: string | null;
  implemented_beats: string[];
  build_summary: string | null;
  deviations_from_plan: string[];
  beat_to_narration_map: string[];
  narration_coverage_complete: boolean | null;
  estimated_narration_duration_seconds: number | null;
  render_mode?: string | null;
  segment_render_complete?: boolean | null;
  timeline_path?: string | null;
  timeline_total_duration_seconds?: number | null;
  segment_render_plan_path?: string | null;
  segment_video_paths?: string[];
  audio_concat_path?: string | null;
  source_code: string | null;
  audio_path: string | null;
  bgm_path: string | null;
  bgm_prompt: string | null;
  bgm_duration_ms: number | null;
  bgm_volume: number | null;
  audio_mix_mode: string | null;
  subtitle_path: string | null;
  extra_info_path: string | null;
  tts_mode: string | null;
  tts_duration_ms: number | null;
  tts_word_count: number | null;
  tts_usage_characters: number | null;
  run_turns: number | null;
  run_tool_use_count: number | null;
  run_tool_stats: Record<string, number>;
  run_duration_ms: number | null;
  run_cost_usd: number | null;
  target_duration_seconds: number | null;
  plan_text: string | null;
  mode?: string | null;
  learning_goal?: string | null;
  audience?: string | null;
  phase1_planning?: Phase1PlanningOutput | null;
  phase2_implementation?: Phase2ImplementationOutput | null;
  phase3_render_review?: Phase3RenderReviewOutput | null;
  phase4_tts?: Phase4TTSOutput | null;
  phase5_mux?: Phase5MuxOutput | null;
  beats?: PipelineBeat[] | null;
  audio_segments?: AudioSegmentOutput[];
  review_summary: string | null;
  review_approved: boolean | null;
  review_blocking_issues: string[];
  review_suggested_edits: string[];
  review_frame_paths: string[];
  review_frame_analyses?: FrameAnalysisOutput[];
  review_vision_analysis_used?: boolean | null;
  intro_requested?: boolean | null;
  outro_requested?: boolean | null;
  intro_spec?: Record<string, unknown> | null;
  outro_spec?: Record<string, unknown> | null;
  intro_video_path?: string | null;
  outro_video_path?: string | null;
  intro_outro_backend?: string | null;
}

export interface BuildSpecBeat {
  id: string;
  title: string;
  visual_goal: string;
  narration_intent: string;
  target_duration_seconds: number | null;
  required_elements: string[];
  segment_required: boolean;
}

export interface BuildSpec {
  mode: string;
  learning_goal: string;
  audience: string;
  target_duration_seconds: number | null;
  beats: BuildSpecBeat[];
}

export interface Phase1PlanningOutput {
  build_spec: BuildSpec;
}

export interface Phase2ImplementationOutput {
  scene_file: string | null;
  scene_class: string | null;
  video_output: string | null;
  implemented_beats: string[];
  build_summary: string | null;
  narration: string | null;
  deviations_from_plan: string[];
  render_mode: string | null;
  segment_render_complete: boolean | null;
  segment_video_paths: string[];
  source_code: string | null;
}

export interface FrameAnalysisOutput {
  frame_path: string;
  timestamp_label: string;
  visual_assessment: string;
  issues_found: string[];
}

export interface Phase3RenderReviewOutput {
  approved: boolean;
  summary: string;
  blocking_issues: string[];
  suggested_edits: string[];
  frame_analyses: FrameAnalysisOutput[];
  vision_analysis_used: boolean;
}

export interface Phase4TTSOutput {
  audio_path: string | null;
  narration: string | null;
  estimated_narration_duration_seconds: number | null;
  tts_mode: string | null;
  tts_duration_ms: number | null;
  tts_word_count: number | null;
  tts_usage_characters: number | null;
  extra_info_path: string | null;
}

export interface Phase5MuxOutput {
  final_video_output: string | null;
  duration_seconds: number | null;
  audio_mix_mode: string | null;
  bgm_path: string | null;
  bgm_prompt: string | null;
  bgm_duration_ms: number | null;
  bgm_volume: number | null;
  subtitle_path: string | null;
}

export interface PipelineBeat {
  id: string;
  title?: string;
  visual_goal?: string;
  narration_intent?: string;
  target_duration_seconds?: number | null;
  required_elements?: string[];
  segment_required?: boolean;
  audio_path?: string | null;
  subtitle_path?: string | null;
  extra_info_path?: string | null;
  actual_audio_duration_seconds?: number | null;
  tts_mode?: string | null;
}

export interface AudioSegmentOutput {
  beat_id: string;
  audio_path: string | null;
  subtitle_path: string | null;
  extra_info_path: string | null;
  duration_seconds: number | null;
  tts_mode: string | null;
}

export interface Task {
  id: string;
  user_text: string;
  status: TaskStatus;
  created_at: string;
  completed_at: string | null;
  video_path: string | null;
  error: string | null;
  options: TaskCreatePayload;
  pipeline_output: PipelineOutputData | null;
}

export interface ToolStartPayload {
  tool_use_id: string;
  name: string;
  input_summary: Record<string, unknown>;
}

export interface ToolResultPayload {
  tool_use_id: string;
  name: string;
  is_error: boolean;
  content: string | null;
  duration_ms: number | null;
}

export interface ThinkingPayload {
  thinking: string;
  preview: string | null;
  signature: string;
}

export interface ProgressPayload {
  turn: number;
  total_tokens: number;
  tool_uses: number;
  elapsed_ms: number;
  last_tool_name: string | null;
}

export interface StatusPayload {
  task_status: TaskStatus;
  phase: "init" | "scene" | "render" | "tts" | "mux" | "done" | null;
  message: string | null;
  video_path?: string | null;
  pipeline_output?: PipelineOutputData | null;
}

export type SSEEventType =
  | "log"
  | "status"
  | "error"
  | "tool_start"
  | "tool_result"
  | "thinking"
  | "progress";

export type StructuredPayload =
  | ToolStartPayload
  | ToolResultPayload
  | ThinkingPayload
  | ProgressPayload
  | StatusPayload;

export interface SSEEvent {
  type: SSEEventType;
  data: string | StructuredPayload;
  timestamp: string;
}

export function isToolStart(
  evt: SSEEvent,
): evt is SSEEvent & { data: ToolStartPayload } {
  return evt.type === "tool_start" && typeof evt.data === "object";
}

export function isToolResult(
  evt: SSEEvent,
): evt is SSEEvent & { data: ToolResultPayload } {
  return evt.type === "tool_result" && typeof evt.data === "object";
}

export function isThinking(
  evt: SSEEvent,
): evt is SSEEvent & { data: ThinkingPayload } {
  return evt.type === "thinking" && typeof evt.data === "object";
}

export function isProgress(
  evt: SSEEvent,
): evt is SSEEvent & { data: ProgressPayload } {
  return evt.type === "progress" && typeof evt.data === "object";
}

export function isStatusPayload(
  evt: SSEEvent,
): evt is SSEEvent & { data: StatusPayload } {
  return (
    evt.type === "status" &&
    typeof evt.data === "object" &&
    evt.data !== null &&
    "task_status" in evt.data
  );
}
