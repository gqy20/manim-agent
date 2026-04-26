# Phase 2: Implementation

## 目标

Phase 2 根据 Phase 1 已验收的 `build_spec` 编写、运行并修正 Manim 场景，产出可验证的实现结果。

该阶段允许使用工具，但 structured output 只走 Phase 2 专用 schema。Phase 2 不从 assistant 可见文本解析结果，不使用 `ResultMessage.result` fallback，也不通过文件扫描兜底生成实现契约。

Phase 2 只负责实现和渲染，不重新规划，不做 TTS，不做 mux，不上传，不生成面向用户阅读的自由格式总结。

## 输入

来自 `pipeline.py` 和 Phase 1 冻结产物：

- `user_text`: 用户原始需求，用于保留任务语义。
- `target_duration_seconds`: 目标视频时长。
- `build_spec`: Phase 1 输出的结构化构建契约，是 Phase 2 的唯一权威规划输入。
- `resolved_cwd`: 当前任务目录，所有文件读写和渲染产物都应限制在这里。
- `render_mode`: `full` 或 `segments`。
- Phase 2 system prompt: 来自 `prompts.get_implementation_prompt()`。
- Phase 2 user prompt: 来自 `pipeline_phases12.build_implementation_prompt()`。

`plan_text` 仍保存在 dispatcher 和数据库快照中，用于日志、人类核对和后续兼容上下文；但 Phase 2 首轮 prompt 在存在 `build_spec` 时不再同时附带完整 `plan_text`，避免同一规划内容在 Markdown 和 JSON 之间双轨漂移。

## System Prompt

Phase 2 不再复用通用 `prompts.get_prompt()`。

当前使用 `prompts.get_implementation_prompt()`，只描述 Phase 2 边界：

- 不重新规划。
- 不做 TTS、mux、上传或最终用户总结。
- 只实现、渲染并返回 Phase 2 structured output。
- 所有文件限制在任务目录内。
- 默认写 `scene.py` 和 `GeneratedScene`。
- narration 默认返回自然简体中文。

Phase 2 system prompt 还负责约束可稳定渲染的生成方式：

- 使用 beat-first 代码结构：每个 `build_spec.beats[*].id` 对应一个同名方法，例如 `beat_001_setup()`。
- `construct()` 只负责编排，按 Phase 1 顺序调用各 beat 方法，不把全部动画逻辑直接堆在 `construct()`。
- 跨 beat 共享的 mobject 必须保存在 `self.<name>` 或明确的 scene state 中。
- 每个 beat 方法末尾必须停留在清晰完成态，并包含不少于 `0.3s` 的 hold。
- 不在 `Text()` 中直接使用 Unicode 上标或非常用数学符号，例如 `²`、`³`、`√`、`≤`、`≥`。
- 只有在当前任务中确认 LaTeX 能成功渲染后，才使用 `MathTex` 表达公式；否则用多个安全 `Text` 对象组合上标标签。
- 每个 beat 必须先到达清晰可读的完成态，并短暂停留，再切换到下一个 beat 标题。
- 几何割补、重排、等积证明类动画必须展示干净的重排完成态，再进入结论。
- 最终证明画面应使用不重叠的等式布局：左侧视觉对象，中间等号或等价提示，右侧视觉和。

## User Prompt

Phase 2 user prompt 由 `build_implementation_prompt()` 生成，负责传入任务实例数据：

- 原始 `user_text`。
- 目标时长。
- `render_mode` 的交付要求。
- Phase 1 的 `build_spec` JSON。

当存在 `build_spec` 时，user prompt 不再附带完整 `plan_text`。如果未来出现没有 `build_spec` 的兼容路径，才会退回使用 `plan_text` 作为上下文；主流程不依赖该路径。

## Skill 使用

Phase 2 不禁用 tools，也不设置 `skills=[]`。运行时通过 `ClaudeAgentOptions.plugins` 注入本地 `manim-production` plugin。

system prompt 要求按以下顺序把 plugin skills 作为阶段 cue 使用：

1. `scene-build`: 根据 `build_spec` 实现场景。
2. `scene-direction`: 调整视觉调度和节奏。
3. `layout-safety`: 在密集布局或修复渲染前后做安全审查。
4. `narration-sync`: 将最终 narration 对齐已实现 beats。
5. `render-review`: 渲染后检查明显视觉和产物问题。

这里不是 Python 代码显式调用 skill API，而是通过 Claude Agent SDK 的 plugin/skill 运行时和提示词约束让 Agent 进入对应 workflow。Agent 不应通过 shell、import、`ls`、`find` 等方式探测 plugin 是否存在。

Plugin skills 只描述工作流和质量标准，不再定义主流程 output schema。Phase 2 输出字段只由 `Phase2ImplementationOutput` 定义。

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

Agent 只允许通过 SDK structured output 返回 `Phase2ImplementationOutput`。Pipeline 使用：

```python
PhaseSchemaRegistry.output_format_schema("phase2_implementation")
```

Phase 2 输出只包含实现阶段事实：

- `video_output`: `full` 模式下渲染出的主 MP4。
- `scene_file`
- `scene_class`
- `narration`
- `implemented_beats`
- `build_summary`
- `deviations_from_plan`
- `render_mode`
- `segment_render_complete`
- `segment_video_paths`
- `source_code`

示例：

```json
{
  "scene_file": "scene.py",
  "scene_class": "GeneratedScene",
  "video_output": "media/videos/scene/1080p60/GeneratedScene.mp4",
  "narration": "自然口语化中文解说文本。",
  "implemented_beats": ["Intro", "Main idea"],
  "build_summary": "Built the requested animation flow.",
  "deviations_from_plan": [],
  "render_mode": "full",
  "segment_render_complete": false,
  "segment_video_paths": [],
  "source_code": "from manim import *\n..."
}
```

Phase 2 不要求 Agent 返回 `beat_to_narration_map`、`narration_coverage_complete` 或 `estimated_narration_duration_seconds`。这些字段由 pipeline 基于 Phase 1 `build_spec` 和最终 narration 本地派生，并合并到后续 `PipelineOutput`。

## 解析边界

进入 Phase 2 前，dispatcher 设置：

```python
expected_output = "phase2_implementation"
```

因此 Phase 2 的 `ResultMessage.structured_output` 只按 `Phase2ImplementationOutput` 验证，不同时尝试：

- `PipelineOutput`
- `ResultMessage.result` 文本 fallback
- assistant 可见文本 JSON fallback
- 文件系统扫描生成契约

Phase 2 验收成功后，进入 Phase 3 前才切换为：

```python
expected_output = "pipeline_output"
```

## 验收规则

- `implemented_beats` 不能为空。
- `build_summary` 不能为空。
- `narration` 不能为空。
- `full` 模式下必须有真实 `video_output`，且路径指向存在的 MP4 文件。
- `segments` 模式下必须存在真实 segment 文件，并设置 `segment_render_complete=true`。
- Phase 2 gate 前不会自动发现或回填 `video_output` / `segment_video_paths`。
- Phase 2 structured output 通过后，pipeline 会运行本地脚本分析并写入：

```text
backend/output/{task_id}/phase2_script_analysis.json
```

该分析检查：

- `scene.py` 是否包含 `GeneratedScene`。
- 是否存在与 Phase 1 beat ids 对齐的 beat 方法。
- `construct()` 是否按顺序调用这些 beat 方法。
- 每个 beat 方法是否有完成态 hold。
- 静态估算的 `run_time + wait` 是否明显低于目标时长。
- 是否在 `Text()` 中直接使用不稳定数学 glyph。
- 是否存在典型硬编码 offset 式伪拼接逻辑。

脚本分析失败时，Phase 2 直接失败，不进入 Phase 3。

## 本地派生

Phase 2 验收后，pipeline 会把 `Phase2ImplementationOutput` 投影成后续阶段使用的 `PipelineOutput`。

以下字段不由 Agent 输出，而是由 pipeline 基于 Phase 1 `build_spec` 和 Phase 2 narration 派生：

- `beat_to_narration_map`
- `narration_coverage_complete`
- `estimated_narration_duration_seconds`
- `target_duration_seconds`
- `plan_text`
- `phase1_planning`
- `phase2_implementation`

这样可以避免 skill 文档、prompt 和 schema 同时维护同一批派生字段。

## 冻结与写库

Phase 2 验收成功后立即冻结写入：

```text
backend/output/{task_id}/phase2_implementation.json
backend/output/{task_id}/phase2_scene.py
backend/output/{task_id}/phase2_video.mp4
```

`phase2_scene.py` 是 Agent 实际生成脚本的稳定副本。`phase2_video.mp4` 是 Phase 2 主渲染视频的稳定副本。`phase2_implementation.json` 中的 `scene_file` 和 `video_output` 会指向这些顶层稳定 artifact，而不是 Manim 深层 `media/` 缓存路径。

随后 pipeline 发出携带 Phase 2 快照的状态事件写入数据库：

```json
{
  "task_status": "running",
  "phase": "scene",
  "message": "Structured implementation output accepted. Resolving render output.",
  "pipeline_output": {
    "...": "Phase2/PipelineOutput snapshot"
  }
}
```

该写入发生在 Phase 3 之前，因此可以独立核对 Phase 2 是否完成，不依赖后续 render review、TTS、mux 或最终视频是否成功。

后端 cleanup 可以删除 `media/`、`audio/`、`review_frames/`、`__pycache__` 等缓存目录，但必须保留顶层冻结 artifact。这样失败任务也能事后复查 Phase 2 的结构化输出、代码脚本和主渲染视频。

## 传给下一阶段

Phase 2 gate 通过后，Phase 3 接收已经投影好的 `PipelineOutput`，继续做渲染产物解析和质量 review。

Phase 3 以后才允许 dispatcher 回到 `expected_output="pipeline_output"`，因为后续阶段处理的是全 pipeline 工作模型，而不是 Phase 2 专用契约。

## 当前风险

- skill 使用仍由 Agent 运行时和提示词共同驱动，不是代码层硬调用；如果后续 SDK 提供稳定的显式 skill selection，可以再收紧。
- Agent 可能产出视频路径但遗漏实现 bookkeeping 或 narration，因此 Phase 2 gate 必须继续保留。
- segment 模式对路径和真实文件存在性更敏感，需要继续加强端到端测试。
