# Phase 1: Planning

## 目标

Phase 1 把用户自然语言需求转换为教学动画的结构化构建契约。该阶段只负责规划，不写代码、不读文件、不渲染，也不生成面向用户阅读的自由格式计划。

## 输入

来自 `pipeline.py`：

- `user_text`: 用户原始需求。
- `target_duration_seconds`: 目标视频时长。
- `preset`: 产品风格预设，例如 `default`、`educational`、`proof`。
- `quality`: 后续渲染质量目标，例如 `high`、`medium`、`low`。
- `render_mode`: 后续渲染模式，当前主要是 `full` 或 `segments`。

Phase 1 system prompt 来自 `prompts.get_planning_prompt()`，负责定义阶段边界和 `phase1_planning` schema 契约。Phase 1 user prompt 来自 `pipeline_phases12.build_scene_plan_prompt()`，只传入用户需求、目标时长和产品约束，不接收或暴露任务目录、插件目录等路径。

## 工具权限

主路径：

- `tools=[]`
- `allowed_tools=[]`
- `disallowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"]`
- `skills=[]`

Phase 1 不开放 `Read`、`Glob`、`Grep`、`Bash`。插件仍通过 `ClaudeAgentOptions.plugins` 注入到运行时配置，但 Phase 1 不依赖读取插件文件。当前不引入 plugin-read fallback；如果真实 Agent 运行证明 schema 规划需要额外 reference，再单独设计只读插件 reference 的受限模式。

## 输出

Agent 只允许通过 SDK structured output 返回 `Phase1PlanningOutput`：

```json
{
  "build_spec": {
    "mode": "string",
    "learning_goal": "string",
    "audience": "string",
    "target_duration_seconds": 60,
    "beats": [
      {
        "id": "beat_001_intro",
        "title": "Intro",
        "visual_goal": "Show the setup",
        "narration_intent": "Introduce the setup",
        "target_duration_seconds": 12,
        "required_elements": [],
        "segment_required": true
      }
    ]
  }
}
```

`build_spec` 是 Phase 2 的唯一权威输入。Phase 1 不再要求、接收或修复 `markdown_plan`。

SDK 当前使用 `PhaseSchemaRegistry.output_format_schema("phase1_planning")`，实际传给 SDK 的结构为：

```python
{
  "type": "json_schema",
  "name": "phase1_planning",
  "strict": True,
  "schema": {...}
}
```

本地会对 schema 做 `$defs/$ref` 内联，以减少 CLI 兼容风险。

## 解析边界

Pipeline 创建 dispatcher 时设置：

```python
expected_output="phase1_planning"
```

因此 Phase 1 的 `ResultMessage.structured_output` 只按 `Phase1PlanningOutput` 验证，不再同时尝试 `PipelineOutput`、`ResultMessage.result` 文本 fallback 或 assistant 可见文本 JSON fallback。Phase 1 验收后，进入 Phase 2 前才切换为：

```python
expected_output="pipeline_output"
```

这个边界用于避免 Phase 1/Phase 2 schema 双轨解析造成误判和噪声日志。

## 本地派生与冻结

为了给 Phase 2 和日志提供稳定上下文，pipeline 会在本地用 `render_build_spec_markdown()` 从 `build_spec` 派生确定性的 Markdown 文本，并写入 `dispatcher.partial_plan_text`。这不是 Agent 输出，也不是 Phase 1 schema 字段。

Phase 1 验收成功后，pipeline 会立即把结构化结果冻结写入任务目录：

```text
backend/output/{task_id}/phase1_planning.json
```

该文件内容是 `Phase1PlanningOutput.model_dump()`，用于独立核对 Phase 1 是否成功。它不依赖 Phase 2、渲染、TTS 或最终 mux 是否完成。

同时 dispatcher 会保存 `phase1_diagnostics_snapshot`，记录 Phase 1 当时的 structured output 状态、输出文件路径和 beat 数量。后续阶段失败时，失败诊断优先使用这份冻结快照，避免 Phase 2 的最后一次 `ResultMessage` 覆盖 Phase 1 状态。

## 验收规则

- structured output 必须能验证为 `Phase1PlanningOutput`。
- 缺失或无效时直接失败，并打印 `raw_structured_output_present`、`raw_structured_output_type` 和 schema validation error。
- 不运行 Phase 1 no-tools repair pass。
- 不从 assistant 可见文本解析或兜底生成 `build_spec`。
- 如果 `build_spec.target_duration_seconds` 与请求目标不一致，pipeline 修正为请求目标并打印 warning。

## 传给下一阶段

Phase 1 验收后写入 dispatcher：

- `partial_build_spec`: `build_spec.model_dump()`。
- `partial_target_duration_seconds`: 请求目标时长。
- `partial_plan_text`: 从 `build_spec` 本地确定性渲染的实现上下文。
- `phase1_output_path`: `phase1_planning.json` 的绝对路径。
- `phase1_diagnostics_snapshot`: Phase 1 当时的冻结诊断快照。

随后发出状态事件：

```json
{
  "task_status": "running",
  "phase": "scene",
  "message": "Structured build_spec accepted. Beginning implementation pass."
}
```

该状态事件会携带 Phase 1 专用最小 `pipeline_output` 快照写入数据库，内容只包含 `phase1_planning`、请求目标时长和本地派生的 `plan_text`。它不调用完整 `get_persistable_pipeline_output()`，因此不会触发视频文件发现、segment fallback 或 Phase 2 输出推断。

## 当前风险

- Agent SDK 的 structured output 通道仍是 Phase 1 成败的单点；这是有意设计，避免可见文本和 schema 双轨漂移。
- 如果模型忽略 schema，Phase 1 会失败而不是降级。这样更早暴露契约问题，避免 Phase 2 基于劣质规划继续消耗渲染成本。
- `phase1_planning.json` 只能证明 Phase 1 已验收成功；它不代表 Phase 2、渲染或最终视频成功。
