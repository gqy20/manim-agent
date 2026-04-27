---
name: scene-build
description: Build a Manim scene from an existing scene plan. Use when a beat-by-beat plan already exists and the next step is to draft, implement, render, or refine animation code. Trigger for requests like "build from this plan", "implement this storyboard", "turn this scene plan into Manim", or after running /scene-plan.
version: 1.0.1
argument-hint: " [build-handoff]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep]
---

# Scene Build

从场景计划实现 Manim 代码。

## 前置条件

- 预期当前对话中已有场景计划。
- 如果没有计划存在，先请求一次简短的规划阶段，而不是即兴创建复杂场景。

## 构建工作流

如果调用方说明这是脚本草稿阶段、Phase 2A 或"不要渲染"，
在编写结构完整的 `scene.py` 后就停止。不要运行 Manim，不要
检查媒体文件，也不要在该模式下执行渲染审查。

在 Phase 2A 中，在通过时序自检之前不要提交 structured output：
每个 beat 方法必须包含显式的 `run_time` 和 `wait` 调用，
其总时长至少达到该 beat 目标时长的 80%，
整个脚本的显式时序至少达到所请求目标时长的 60%。
如果估算值低于任一门控，继续编辑 `scene.py`；
不要将此不足报告为偏差或推迟到 Phase 2B 处理。

1. 读取给定的场景计划。
2. 保留 beat 顺序，除非渲染/调试问题需要小幅修改。
3. 编写一个主 `scene.py` 文件，除非用户明确要求更多文件。
4. 保持一个主 `Scene` 类，除非有充分理由拆分。
5. 在最终渲染前对密集 beat 使用 `layout-safety` 作为建议性审计。
6. 在渲染实现阶段，渲染、检查并在结果感觉拥挤时简化。

## Beat 到代码的映射

- 每个 beat 应对应 `construct()` 中的一个可见阶段。
- 为每个已批准的 beat 实现一个方法，当 beat id 是有效的 Python 标识符时使用精确的 beat id 作为方法名，
  例如 `def beat_001_setup(self): ...`。
- 将 `construct()` 保持为调用 beat 方法的轻量级编排方法，按已批准顺序调用。不要将完整动画直接放在 `construct()` 中。
- 对必须跨 beat 持续存在的 mobject 使用 `self.<描述性名称>` 或 `self.scene_state`。
- 在每个 beat 方法内部使用标记 beat 边界的注释。
- 让每个 beat 聚焦于一个展示、变换或强调变化。
- 让解说与当前 beat 对齐。
- 每个 beat 必须在下一个 beat 标题或下一个概念出现之前达到可读的完成帧状态。
- 在每个完成的 beat 状态后插入一个短暂停留（`self.wait(0.3)` 到 `self.wait(0.8)`），以便帧审查可以采样预期结果。
- 不要在前一个 beat 的变换尚未视觉完成时就提前更改标题。

## 质量检查

- 确认代码匹配规划的 beat 顺序。
- 确认标签保持在它们所描述的对象附近。
- 确认密集 beat 已在构图拥挤时经过基于几何的布局安全检查。
- 确认有清晰的结束帧。
- 确认最终解说按顺序覆盖所有 beats。

## 渲染稳定标签

数学标签必须在真实的 Manim/Pango/字体环境中存活，而不仅仅是在源代码中看起来正确。

- 不要将 Unicode 上标或不常见数学字形直接放入 `Text()`，
  包括 `²`、`³`、`√`、`≤`、`≥` 或符号公式。它们在 Windows 字体回退下可能渲染为豆腐块（□）。
- 如果 LaTeX 可用且在此任务中成功渲染过，对公式使用 `MathTex`。
- 如果 LaTeX 不可用，由安全字形组合简单标签。例如，将 `a^2` 创建为包含
  `Text("a")` 加上更小的右上角 `Text("2")` 的 `VGroup`。
- 对标题、对象标签、最终公式和解说相邻字幕一致地使用同一安全标签辅助函数。
- 在渲染实现阶段，在返回 structured output 之前目视检查采样帧中的豆腐块（`□`）。

回退辅助函数示例：

```python
def safe_power_label(base_text, exponent_text="2", font_size=28, color=WHITE):
    base = Text(base_text, font_size=font_size, color=color)
    exp = Text(exponent_text, font_size=font_size * 0.55, color=color)
    exp.next_to(base, UR, buff=0.02)
    return VGroup(base, exp)
```

在 LaTeX 不可用时使用 `safe_power_label("a")` 而不是 `Text("a²")`。

## 面积证明布局规则

对于勾股定理、赵爽弦图、割补、重排或类似面积证明：

- 在结论之前展示重排 beat 的干净完成状态。
- 将源面积、等号标记和目标面积保持在独立的屏幕区域。
- 最终要点应在视觉上等价于 `c^2 = a^2 + b^2`：左侧视觉、中间 `=`、右侧视觉总和。
- 避免最终证明帧中出现嵌套或重叠形状，除非嵌套正是被解释的数学对象。
- 如果三角形移动以揭示/重建正方形，最终位置必须足够整洁，
  使正方形区域无需依赖解说就能显而易见。

## 动画构建规则（如何编写 play() 调用）

### CJK 文本渲染——强制规则

Manim 有三个文本渲染引擎，字符支持互不兼容：

| 引擎 | 类 | CJK 支持 | 用途 |
|------|-----|----------|------|
| Pango | `Text()` | **原生** | 所有中文/日文/韩文文本 |
| LaTeX | `Tex()` | 需要 XeLaTeX 配置 | 带 LaTeX 格式化的英文文本 |
| LaTeX 数学 | `MathTex()` | **不支持中文** | 仅数学公式 |

**强制规则：**
- 中文字符 → **始终使用 `Text()`**，永远不用 `Tex()` 或 `MathTex()`。
- 数学公式 → 始终使用 `MathTex()`，永远不要混入中文。
- 中文+数学混合行 → 将 `Text()` + `MathTex()` 组合到 `VGroup` 中：
  ```python
  VGroup(Text("其中"), MathTex(r"x = \sqrt{2}")).arrange(RIGHT, buff=0.1)
  ```
- 除非必要，不要为 `Text()` 指定自定义 `font`；Pango 自动选择支持 CJK 的系统字体。

### 动画时长边界

每个 `self.play()` 调用都应指定或隐含合理的时长：

| 动画类型 | 最小值 | 推荐值 | 最大值 |
|----------|--------|--------|--------|
| `FadeIn`, `FadeOut` | 0.3 s | **0.5–0.8 s** | 1.5 s |
| `Create`（绘制形状） | 0.5 s | **1.0–1.5 s** | 3 s |
| `Write`（书写文本） | 1.0 s | **1.5–2.0 s** | 4 s |
| `Transform` / `ReplacementTransform` | 1.0 s | **1.5–2.5 s** | 4 s |
| `GrowFromCenter` / `GrowFromEdge` | 0.4 s | **0.8–1.2 s** | 2 s |
| `Indicate` / `Flash` / `Circumscribe` | 0.3 s | **0.5–1.0 s** | 1.5 s |
| `Shift` / `ApplyMethod` | 0.3 s | **0.5–1.0 s** | 2 s |
| `Wait` | 0.1 s | **0.3–0.8 s** | 1.5 s |

时长估算公式：
```
动画秒数 ≈ 解说字符数 × 0.15
```
（中文：正常语速约每秒 15 个字符）

### 动画组合模式

如何在一个 `play()` 调用中组合多个动画：

| 模式 | 适用场景 | 示例 |
|------|----------|------|
| `play()` 的多个参数 | 2–3 个独立的同时变化 | `self.play(FadeIn(a), Transform(b, c))` |
| `AnimationGroup()` | 需要对组时机进行显式控制 | `self.play(AnimationGroup(anim1, anim2, lag_ratio=0.1))` |
| `LaggedStart(*anims, lag_ratio=0.15)` | 相关元素的级联展示 | 公式后的标签逐个出现 |
| `Succession(anim1, anim2)` | 严格顺序（第二个在第一个结束后开始） | 步骤 1 必须在步骤 2 之前完全完成 |
| 分离的 `play()` 调用 | beats 或阶段之间有停顿 | `self.play(step1); self.wait(0.5); self.play(step2)` |

**规则：**
- `AnimationGroup` 嵌套深度不要超过 2 层。
- 为了可读性，优先使用分离的 `play()` 调用而非巨大的 `AnimationGroup`。
- 对 `LaggedStart` 使用 `lag_ratio=0.1–0.2`；更高的值会显得迟缓。

### Updater 使用

仅在以下场景使用 `add_updater()`：

| 场景 | 示例 | 不用于 |
|------|------|--------|
| 标签跟随移动的点 | 曲线上的点，标签跟踪它 | 静态标签 |
| 实时数值显示 | 坐标读数每帧更新 | 一次性标注 |
| 比例缩放 | 两段线段随父级增长保持比例 | 固定布局 |

模式：
```python
# 跟随移动点的标签
label = MathTex(r"(x, y)").add_updater(lambda m: m.next_to(dot, UR))
self.add(label)
# ... 之后，当动画移动点时，标签自动跟随
```

不再需要 updaters 时移除它们：`label.clear_updaters()`。

### Rate function 默认设置

编写 `self.play()` 时，对非显而易见的情况显式设置 `rate_func`：

```python
# 默认（安全）——省略或设置 rate_func=smooth
self.play(Create(circle))

# 揭示 —— ease_out 感觉自然
self.play(FadeIn(text), run_time=0.6, rate_func=ease_out_cubic)

# 变换 —— 两端平滑
self.play(Transform(a, b), run_time=2.0, rate_func=ease_in_out_sine)

# 强调 —— 轻微过冲吸引注意力
self.play(Indicate(term), rate_func=ease_out_back)
```

## 组件库用法

优先使用组件函数而非原始 Manim API 调用。组件自动处理 CJK 安全性、一致样式和正确时长。

### 做 / 不做

| 模式 | 不做（原始 API） | 做（组件） |
|------|------------------|------------|
| 中文文本 | `Text("勾股定理").scale(0.6).set_color(WHITE)` | `cjk_title("勾股定理")` |
| 数学公式 | `MathTex(r"a^2+b^2").scale(1.0).set_color(BLUE)` | `math_line(r"a^2+b^2")` |
| 混合 CJK+数学 | `VGroup(Text("其中"), MathTex(r"x")).arrange(RIGHT)` | `mixed_text("其中", r"x")` |
| 字幕 | `Text("步骤1", font_size=24).set_color(GRAY)` | `subtitle("步骤1")` |
| 标题卡片 | 手动定位 + Write/FadeIn | `TitleCard.get_title_mobjects(title="...")` |
| 证明步骤 | 手动 VGroup arrange + 标签 Text 对象 | `ProofStepStack()` + `.add_step()` + `.build()` |
| 步骤标签 | `Text("已知")` 配合手动样式 | `StepLabel(StepKind.GIVEN)` → "已知" |
| 角标注释 | `Text("条件").to_corner(UL)` | `Callout.create("条件", corner=UL)` |
| 高亮框 | `SurroundingRectangle(target, ...)` | `HighlightBox.outline(target)` |
| 顶点标签 | 多个 `MathTex().next_to()` 调用 | `LabelGroup()` + `.add_vertex("A", pt)` + `.build()` |
| 动画时长 | 猜测 `run_time=1.5` | `reveal(obj)`, `write_in(obj)`, `emphasize(obj)` —— 自动计时 |
| 缓冲值 | 硬编码 `buff=0.25` | `BUFFER.MED_SMALL`, `BUFFER.LARGE` 等 |
| 颜色 | 硬编码 `color=BLUE` | `COLOR_PALETTE.given`, `COLOR_PALETTE.highlight` 等 |

### 组件未覆盖需求时的处理

对于组件库中尚未涵盖的模式：
1. 使用原始 Manim API 但从 `components.config` 导入常量以保持一致性。
2. 遵循上表中的 CJK 规则（中文 → `Text()`，数学 → `MathTex()`）。
3. 使用 `BUFFER.*` 和 `COLOR_PALETTE.*` 替代魔法数字/颜色。

## 仅在需要时使用参考文件

所有参考文件位于 `<plugin_dir>/references/` 下。以下路径相对于插件根目录：

- 代码风格和渲染规范，读取 `references/code-style.md`。
- 数学布局和强调，读取 `references/math-visualization-guidelines.md`。
- 空间 composition、屏幕区域、元素尺寸、调色板和按模式布局模板，读取 `references/spatial-composition.md`。
- 动画选择、rate functions、时序、组合模式和运动技巧，读取 `references/animation-craft.md`。
- 渲染质量预设、缓存行为、文件大小预算、性能瓶颈和渲染器选择，读取 `references/render-quality.md`。
- 3Blue1Brown 视觉风格配置文件（精确颜色十六进制码、LaTeX 模板配置、动画速度/easing 偏好），读取 `references/style-3b1b.md`。
- 常见实现错误和错误修复模式，读取 `references/build-anti-patterns.md`。

## 实现交接

在主 pipeline 内部使用时，通过运行时提供的 structured output schema 返回实现事实。不要在此 skill 中重新定义 schema。

交接应明确以下事实：

- 构建了什么。
- 渲染是否成功。
- 与原始场景计划的任何偏差。
- 最终 Scene 类名。
- 实际实现了哪些规划的 beats，按顺序排列。
- 简要构建摘要。
