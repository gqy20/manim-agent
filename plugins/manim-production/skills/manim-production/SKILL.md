---
name: manim-production
description: Produce, review, or refactor Manim scenes for educational videos with stronger scene structure, narration alignment, mathematical clarity, and render-time self-checks. Use when generating or improving Manim animation code, teaching demos, proof walkthroughs, function visualizations, or geometry scenes.
---

# Manim Production

将此作为 Manim 任务的总工作流路由器。

## 主要职责

- 将任务路由到正确的 Manim 生产阶段。
- 保持阶段顺序：可见规划 → 构建 → 解说对齐 → 渲染审查。
- 使用各专用 skill 的详细规则，而非在此重复。

## 必需的阶段顺序

1. 首先使用 `scene-plan` 并在编码前发出可见计划。
2. 仅在该计划存在后使用 `scene-build`。
3. 在规划和实现期间应用 `scene-direction` 以保持每个 beat 视觉强劲。
4. 在接受实现前对密集 beat 应用 `layout-safety` 作为建议性审计。
5. 在最终确定解说前应用 `narration-sync`。
6. 渲染后在报告成功前使用 `render-review`。
7. 当请求品牌化包装时（可选）在 render-review 之后应用 `intro-outro`。

## Skill 路由

- `scene-plan`：beat 结构、学习序列、解说大纲、构建交接
- `scene-build`：从计划到代码执行、渲染/调试循环、实现优化
- `scene-direction`：开场吸引、焦点层级、运动引导讲解、结尾收获
- `layout-safety`：基于几何的建议性审计，用于实现阶段的重叠和帧安全检查
- `narration-sync`：口语节奏、逐 beat 解说对齐、解说密度控制
- `render-review`：采样帧质量审查和阻塞性问题检测
- `intro-outro`：品牌化片头/片尾设计、Revideo 或 Manim 回退、视频拼接约定

## 任务分类

在构建前选择一种主要模式：

- `quick-demo`
- `concept-explainer`
- `proof-walkthrough`
- `function-visualization`
- `geometry-construction`

## 最小检查项

- 不要在可见计划存在前开始 `scene.py`。
- 当某阶段活跃时不要跳过对应的专用 skill。
- 优先使用一个 `scene.py` 文件和一个主 `Scene` 类，除非任务确实需要更多。
- 如果第一次渲染失败，在重新设计课程之前修复实现问题。
- 如果请求了 intro-outro，在完成前在 structured output 中输出 `intro_spec` 和/或 `outro_spec`。

## 组件库

`components/` 中的可复用 Python 组件，将文档化的模式封装为 LLM 友好的 API。

### 导入模式

```python
from components import (
    BUFFER, COLOR_PALETTE, TEXT_SIZES, SCREEN_ZONES,
    cjk_text, cjk_title, math_line, mixed_text, subtitle,
    TitleCard, EndingCard,
    ProofStepStack, FormulaTransform, StepLabel, StepKind,
    Callout, HighlightBox, LabelGroup,
    ZoneLayout, ModeLayout, SceneMode,
    reveal, write_in, emphasize, transform_step, shrink_to_corner, highlight_circle,
    TeachingScene,
)
```

或单独导入：`from components.text_helpers import cjk_text`

### 组件快速参考

| 你需要什么 | 使用这个 | 模块 |
|---------------|----------|--------|
| 样式常量（缓冲区、颜色、尺寸） | `BUFFER.SMALL`, `COLOR_PALETTE.given`, `TEXT_SIZES.title` | `config.py` |
| 中文文本 | `cjk_text("文本")`, `cjk_title("标题")` | `text_helpers.py` |
| 数学公式 | `math_line(r"a^2+b^2")` | `text_helpers.py` |
| 混合 CJK+数学 | `mixed_text("其中", r"x=2")` | `text_helpers.py` |
| 字幕/注释 | `subtitle("注释")` | `text_helpers.py` |
| 标题卡片 | `TitleCard.get_title_mobjects(title="...")` | `titles.py` |
| 结尾卡片 | `EndingCard.get_ending_mobjects(message="...")` | `titles.py` |
| 证明步骤栈 | `ProofStepStack()` + `.add_step()` + `.build()` | `formula_display.py` |
| 公式变换 | `FormulaTransform(original, target_latex)` | `formula_display.py` |
| 步骤标签 | `StepLabel(StepKind.GIVEN)`, `StepLabel(StepKind.STEP, 1)` | `formula_display.py` |
| 角标注释 | `Callout.create("已知", corner=UL)` | `annotations.py` |
| 高亮框 | `HighlightBox.outline(target)`, `HighlightBox.filled(target)` | `annotations.py` |
| 顶点/角度/长度标签 | `LabelGroup()` + `.add_vertex()` + `.build()` | `annotations.py` |
| 基于区域的布局 | `ZoneLayout()` + `.set_title()` + `.build()` | `layouts.py` |
| 基于模式的布局 | `ModeLayout(SceneMode.PROOF_WALKTHROUGH)` | `layouts.py` |
| 语义动画 | `reveal()`, `write_in()`, `emphasize()`, `transform_step()` | `animation_helpers.py` |
| 缩小到角落 | `shrink_to_corner(obj)` | `animation_helpers.py` |
| 教学 Scene 基类 | `class MyScene(TeachingScene): ...` | `scene_templates.py` |

**规则：** 对常见模式始终优先使用组件函数而非原始 Manim API 调用。组件自动强制一致的样式、正确的 CJK 处理和适当的动画时长。

## 参考

所有参考文件位于 `<plugin_dir>/references/` 下。以下路径相对于插件根目录：

- 场景流程，读取 `references/scene-patterns.md`。
- 解说质量，读取 `references/narration-guidelines.md`。
- 空间 composition（屏幕区域、尺寸、颜色、按模式布局），读取 `references/spatial-composition.md`。
- 动画技巧（运动选择、rate functions、时序、组合），读取 `references/animation-craft.md`。
- 渲染质量（预设、缓存、性能、文件大小），读取 `references/render-quality.md`。
- 3Blue1Brown 视觉风格配置文件（颜色、排版、动画节奏、组合模式），读取 `references/style-3b1b.md`。
- 布局或失败模式，仅按需读取你需要的特定参考。
- 片头/片尾模板和视频组装，读取 `/intro-outro` skill。
