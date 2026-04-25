# Phase 2: Implementation

## 目标

Phase 2 根据 Phase 1 批准的可见 plan 和 `build_spec` 编写、运行并修正 Manim 场景，产出可验证的实现结果。

## 输入

- `user_text`: 用户原始需求。
- `target_duration_seconds`: 目标视频时长。
- `plan_text`: Phase 1 验收后的可见 plan。
- `build_spec`: Phase 1 输出的结构化构建契约。
- `resolved_cwd`: 当前任务目录。
- `render_mode`: `full` 或 `segments`。
- 完整 implementation system prompt，来自 `prompts.get_prompt()`。

## 工具权限

主路径允许：

- `Read`
- `Write`
- `Edit`
- `Bash`
- `Glob`
- `Grep`

Hook 会限制任务越界：

- `Write` / `Edit` 只能写任务目录。
- `Read` 只能读任务目录和批准的本地插件引用。
- `Bash` 不能引用任务目录之外的路径。

## 输出

Phase 2 主要产出 `PipelineOutput` 的实现字段：

- `video_output` 或 segment 模式下的 `segment_video_paths`
- `scene_file`
- `scene_class`
- `narration`
- `implemented_beats`
- `build_summary`
- `deviations_from_plan`
- `beat_to_narration_map`
- `narration_coverage_complete`
- `estimated_narration_duration_seconds`

## 验收规则

- `implemented_beats` 不能为空。
- `build_summary` 不能为空。
- `beat_to_narration_map` 不能为空。
- `narration_coverage_complete` 必须为 true。
- `estimated_narration_duration_seconds` 必须存在。
- `segments` 模式下必须存在真实 segment 文件，并设置 `segment_render_complete=true`。

## 传给下一阶段

Phase 2 输出会先用 Phase 1 `build_spec` 回填可确定的 bookkeeping 字段，再交给 Phase 3 做渲染产物解析和质量 review。

## 当前风险

- Agent 可能产出 video 路径但遗漏实现 bookkeeping，因此 Phase 2 gate 必须保留。
- segment 模式对路径和真实文件存在性更敏感，需要继续加强测试。
