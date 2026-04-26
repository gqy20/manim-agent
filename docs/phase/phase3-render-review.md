# Phase 3: Render Review

## 目标

Phase 3 接收 Phase 2B 已验收并冻结的渲染产物，确认真实文件存在，抽取 review frames，并通过独立 Claude Agent 调用判断视频是否可以进入后续 narration/TTS/mux 阶段。

该阶段不写代码、不重新渲染、不修复 Phase 2 契约、不生成最终用户总结。

## 阶段结构

Phase 3 分为两部分：

### Part A — Resolve（门控验证，快速）

检查前置条件是否满足：

- `PipelineOutput` 存在
- `implemented_beats` 非空
- `build_summary` 非空
- `full` 模式下 `video_output` 文件真实存在
- `segments` 模式下 `segment_video_paths` 存在且 `segment_render_complete=true`
- 可通过 `ffprobe` 探测视频时写入 `duration_seconds`

任一条件不满足则直接失败，不进入 Review。

### Part B — Review（独立 Agent 调用，较慢）

通过 `query()` 启动一个**独立的** Claude Agent 进程（绕过主 dispatcher），让它：

1. 读取抽帧图片（只读工具：Read/Glob/Grep）
2. 对每帧进行视觉评估
3. 返回 `Phase3RenderReviewOutput` 结构化 verdict

## 输入

来自 Phase 2B 和 pipeline：

| 参数 | 说明 |
|------|------|
| `PipelineOutput` | Phase 2B 投影后的 pipeline 工作模型 |
| `video_output` | `full` 模式下的 MP4 路径 |
| `segment_video_paths` | `segments` 模式下的 beat-level MP4 列表 |
| `implemented_beats` | 已实现的 beat 列表 |
| `build_summary` | 构建摘要 |
| `target_duration_seconds` | 目标时长 |
| `resolved_cwd` | 任务工作目录 |
| `render_mode` | `"full"` 或 `"segments"` |

## System Prompt

Phase 3 使用专用 `RENDER_REVIEW_SYSTEM_PROMPT`（`prompts.get_render_review_prompt()`），包含完整的 `# Output` 段，明确告知 Agent 每个 schema 字段的含义和约束。

该 prompt 的边界：

- 只做 render review。
- 不写代码。
- 不编辑文件。
- 不重新渲染。
- 不修复 Phase 2 structured output。
- 不做 TTS、mux、上传或最终总结。
- 只返回 `Phase3RenderReviewOutput` structured output。

`render-review` skill 只描述 review 工作流和质量判断标准。输出字段完全由 `Phase3RenderReviewOutput` Pydantic model 定义。

## 工具权限

Review pass 使用只读工具：

- `Read`
- `Glob`
- `Grep`

允许读取抽帧图片和附近 artifact，但不允许写文件、编辑代码或重新渲染。

## 输出

### Phase 3 主函数返回值

- `po`: 已确认的 `PipelineOutput`（附加 review 结果字段）。
- `video_output`: 用于后续 narration/TTS 的视觉视频路径。
- `review_frames`: 抽帧图片路径列表。

### Structured Verdict (`Phase3RenderReviewOutput`)

```json
{
  "approved": true,
  "summary": "Readable and coherent.",
  "blocking_issues": [],
  "suggested_edits": [],
  "frame_analyses": [
    {
      "frame_path": "phase3_review_frames/frame_001.png",
      "timestamp_label": "opening",
      "visual_assessment": "The opening frame is readable.",
      "issues_found": []
    }
  ],
  "vision_analysis_used": true
}
```

## 抽帧隔离

Phase 3 抽帧使用**独立子目录**，避免覆盖 Phase 2B 的 review frames：

| 阶段 | 抽帧目录 |
|------|----------|
| Phase 2B (implementation self-review) | `{output_dir}/review_frames/` |
| Phase 3 (independent render review) | `{output_dir}/phase3_review_frames/` |

通过 `extract_review_frames(video_path, output_dir, implemented_beats, review_subdir="phase3_review_frames")` 实现。

## `no_render_review` 开关（默认关闭）

Phase 3 Render Review **默认禁用**（`no_render_review=True`），跳过独立的 Agent 视觉审查以加速 pipeline。

如需启用，使用 CLI 参数：

```
python -m manim_agent --render-review "你的需求"
```

默认跳过时的行为：

- Part A (Resolve) 正常执行（仍验证 video_output 存在等前置条件）
- Part B (Review) 被跳过
- 自动设置：
  - `po.review_approved = True`
  - `po.review_summary = "Render review skipped (no_render_review=True). Accepting Phase 2B output."`
  - `po.review_blocking_issues = []`
  - `po.review_suggested_edits = []`
  - `po.review_frame_paths = []`
  - `po.review_frame_analyses = []`
  - `po.review_vision_analysis_used = False`

这使默认运行速度更快。需要严格质量门控时用 `--render-review` 显式开启。下游 Phase 3.5/4/5 的数据契约不受影响。

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

如果 Phase 2B 给出的 `PipelineOutput` 或 artifact 不完整，Phase 3 直接失败。保持阶段边界清晰：Phase 2B 负责实现契约和真实视频，Phase 3 只负责验证和 review。

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
- Review 是独立 Agent 调用（`query()` 绕过 dispatcher），耗时较长，默认跳过；需用 `--render-review` 显式启用。
