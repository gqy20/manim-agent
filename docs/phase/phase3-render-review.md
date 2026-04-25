# Phase 3: Render Review

## 目标

Phase 3 接收 Phase 2 已验收并冻结的渲染产物，确认真实文件存在，抽取 review frames，并通过 `render-review` structured output 判断视频是否可以进入后续 narration/TTS/mux 阶段。

该阶段不写代码、不重新渲染、不修复 Phase 2 契约、不生成最终用户总结。

## 输入

来自 Phase 2 和 pipeline：

- `PipelineOutput`: Phase 2 投影后的 pipeline 工作模型。
- `video_output`: `full` 模式下应指向 `backend/output/{task_id}/phase2_video.mp4`。
- `segment_video_paths`: `segments` 模式下的真实 beat-level MP4 文件。
- `build_spec` 派生的 beat/narration bookkeeping。
- `implemented_beats`
- `build_summary`
- `target_duration_seconds`
- `resolved_cwd`
- `render_mode`
- Phase 3 system prompt: 来自 `prompts.get_render_review_prompt()`。

Phase 3 可以读取 `plan_text` 作为辅助上下文，但不把它作为结构化契约来源。

## System Prompt

Phase 3 使用专用 `prompts.get_render_review_prompt()`，不再复用 Phase 2 implementation prompt。

该 system prompt 的边界：

- 只做 render review。
- 不写代码。
- 不编辑文件。
- 不重新渲染。
- 不修复 Phase 2 structured output。
- 不做 TTS、mux、上传或最终总结。
- 只返回 `Phase3RenderReviewOutput` structured output。

`render-review` skill 只描述 review 工作流和质量判断标准，不定义输出字段。Phase 3 输出字段只由 `Phase3RenderReviewOutput` 定义。

## 工具权限

render review pass 使用只读工具：

- `Read`
- `Glob`
- `Grep`

review pass 允许读取抽帧图片和附近 artifact，但不允许写文件、编辑代码或重新渲染。

## 输出

Phase 3 主函数返回：

- `po`: 已确认的 `PipelineOutput`。
- `video_output`: 用于 review 和后续 narration/TTS 的视觉视频路径。
- `review_frames`: 抽帧图片路径列表。

render review Agent 只允许通过 SDK structured output 返回 `Phase3RenderReviewOutput`：

```json
{
  "approved": true,
  "summary": "Readable and coherent.",
  "blocking_issues": [],
  "suggested_edits": [],
  "frame_analyses": [
    {
      "frame_path": "review_frames/frame_001.png",
      "timestamp_label": "opening",
      "visual_assessment": "The opening frame is readable.",
      "issues_found": []
    }
  ],
  "vision_analysis_used": true
}
```

## 验收规则

- `PipelineOutput` 必须存在。
- `implemented_beats` 不能为空。
- `build_summary` 不能为空。
- `full` 模式必须存在真实 `video_output` 文件。
- `segments` 模式必须存在真实 `segment_video_paths`，且 `segment_render_complete=true`。
- `video_output` 可被 `ffprobe` 探测时会写入 `duration_seconds`。
- render review structured verdict 必须能验证为 `Phase3RenderReviewOutput`。
- 如果 review 返回 `approved=false`，Phase 3 阻断。
- 如果时长偏差超过规则阈值，Phase 3 阻断。

## 解析边界

Phase 3 不再运行 no-tools repair pass。

如果 Phase 2 给出的 `PipelineOutput` 或 artifact 不完整，Phase 3 直接失败。这样可以保持阶段边界清晰：Phase 2 负责实现契约和真实视频，Phase 3 只负责验证和 review。

## 传给下一阶段

Phase 3 通过后，`PipelineOutput` 会包含：

- `duration_seconds`
- `review_summary`
- `review_approved`
- `review_blocking_issues`
- `review_suggested_edits`
- `review_frame_paths`
- `review_frame_analyses`
- `review_vision_analysis_used`

随后 Phase 3.5/4 使用同一个 `video_output` 继续生成 narration/TTS，Phase 5 再 mux 成最终 `final.mp4`。

## 当前风险

- `render-review` 依赖模型真实读取抽帧；需要继续通过日志和结构化 `frame_analyses` 核对。
- 抽帧质量会影响 review 判断，如果抽帧覆盖不足，可能漏掉中间视觉问题。
- segment 模式会生成 review track，后续还需要明确该 track 与最终 segment mux 的关系。
