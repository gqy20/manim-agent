---
name: scene-plan
description: Create a scene plan before writing Manim code. Use when the task needs beat-by-beat planning, scene segmentation, narration outline, pacing decisions, or visual teaching structure before implementation. Trigger for requests like "plan the animation", "split this into scenes", "design the storyboard", "how should this Manim lesson be structured", or before building a teaching animation that needs stronger structure.
version: 1.0.0
argument-hint: " [topic-or-goal]"
allowed-tools: [Read, Glob, Grep]
---

# Scene Plan

在编写代码之前为动画生成紧凑的计划。

## 输出格式

返回包含以下章节的纯 Markdown 计划，按顺序排列：

1. `Mode`（模式）
2. `Learning Goal`（学习目标）
3. `Audience`（受众）
4. `Beat List`（Beat 列表）
5. `Narration Outline`（解说大纲）
6. `Visual Risks`（视觉风险）
7. `Build Handoff`（构建交接）

## Beat 列表规则

- 默认使用 3 到 6 个 beats。
- 为每个 beat 取一个简短标题。
- 每个 beat 只承载一个新的教学点。
- 对每个 beat 包含：
  - `Goal`（目标）
  - `Visuals`（视觉效果）
  - `Key motion`（关键运动）
  - `Max duration`（最大时长）

## 解说规则

- 将解说映射到 beats，而非代码块。
- 保持解说口语化和自然。
- 默认每个 beat 一到两句话。
- 除非用户要求，否则不要编写完整的最终配音脚本。

## 规划启发式

- 从对象、问题或公式开始。
- 在解释之前构建铺垫。
- 每次只展示一个关系。
- 以收获帧结束。
- 如果任务是数学类的，优先使用视觉递进而非文字密度。

## 仅在需要时使用参考文件

所有参考文件位于 `<plugin_dir>/references/` 下。以下路径相对于插件根目录：

- beat 模板，读取 `references/beat-patterns.md`。
- 计划形状，读取 `references/scene-plan-template.md`。
- 失败模式，读取 `references/planning-anti-patterns.md`。
- 每个 beat Visuals 字段中的空间规划（屏幕区域、元素位置、尺寸），读取 `references/spatial-composition.md`。

## 构建交接

以一个简短的 `Build Handoff` 章节结尾，告诉实现步骤：

- 推荐的文件名
- 推荐的主 Scene 类名
- 预期的场景流程（一行描述）
- 任何约束条件（如"避免 MathTex"或"保持所有标签在屏幕上"）
- **推荐组件**（来自 `components/` 库）（如"对推导 beats 使用 `ProofStepStack`"，"使用 `TeachingScene` 作为基类"，"使用 `ZoneLayout` 进行屏幕分区"）
- `Skill Signature: mp-scene-plan-v1`

### 构建交接的组件选择指南

在编写 Build Handoff 时，根据场景模式推荐组件：

| 场景模式 | 推荐组件 |
|-----------|----------------------|
| `proof-walkthrough` | `ProofStepStack`, `StepLabel`, `StepKind`, `FormulaTransform`, `TeachingScene` |
| `geometry-construction` | `LabelGroup`, `HighlightBox`, `Callout`, `ZoneLayout`, `mixed_text` |
| `function-visualization` | `cjk_title`, `math_line`, `Callout`, `ZoneLayout` |
| `concept-explainer` | `TitleCard`, `EndingCard`, `reveal`, `emphasize`, `shrink_to_corner` |
| `quick-demo` | `cjk_text`, `math_line`, `write_in`, 基础布局 |
