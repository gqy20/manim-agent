# Phase 3: Render Resolve And Review

## 目标

Phase 3 解析并确认真实渲染产物，必要时修复结构化输出，然后抽帧进行视觉 review 和时长检查。

## 输入

- Phase 2 的 `PipelineOutput`。
- `plan_text`: Phase 1 可见 plan。
- `result_summary`: Phase 1 和 Phase 2 的运行摘要。
- `target_duration_seconds`
- `resolved_cwd`
- `render_mode`
- implementation system prompt
- dispatcher 收集到的 SDK result、task notification 和 hook-captured source code。

## 工具权限

结构化输出修复 pass 使用：

- `allowed_tools=[]`

render review pass 使用：

- `Read`
- `Glob`
- `Grep`

review pass 允许读取抽帧图片，但不允许写文件、编辑代码或重新渲染。

## 输出

主输出：

- 已确认的 `PipelineOutput`
- `video_output`
- `review_frames`

review 结构化输出使用 `Phase3RenderReviewOutput`，包括：

- `summary`
- `approved`
- `blocking_issues`
- `suggested_edits`

## 验收规则

- `full` 模式必须存在真实 `video_output` 文件。
- `segments` 模式必须存在真实 `segment_video_paths`。
- `implemented_beats` 和 `build_summary` 必须存在。
- review 不通过或时长偏差过大时阻断。

## fallback

如果结构化输出不完整，但已有真实产物或 raw result text，会运行 no-tools repair pass。repair 只能基于已知 plan、partial output、raw result text 和 artifact inventory 修正结构化输出，不允许继续构建。

## 当前风险

- repair pass 依赖 Agent 能从证据中补齐字段，仍可能失败。
- 文件系统 artifact inventory 是证据来源，不应变成主路径真相来源。
