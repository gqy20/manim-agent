---
name: scene-direction
description: Direct the visual language of a Manim scene so it feels like a guided explanation instead of a static slide deck. Use when improving opening beats, focal hierarchy, motion clarity, transformations, visual pacing, or ending payoff in educational animation tasks.
version: 1.0.1
argument-hint: " [scene-or-plan]"
allowed-tools: [Read, Glob, Grep]
---

# Scene Direction

使用此 skill 来塑造动画在屏幕上的观感。

## 主要目标

- 让前几秒视觉活跃，而不仅仅是标签。
- 每个 beat 保持一个焦点对象、公式或关系。
- 通过运动、变换或强调变化来展示结论。
- 让最终 beat 感觉像是一个收获，而不是剩余的摘要卡片。

## 开场规则

- 在前 3 秒内，同时展示主题和一个可见的对象或图形。
- 避免以空屏幕上仅有的标题开场，除非任务是一个极小的单 beat 演示。
- 优先使用对象优先或对象加标题的开场，而非仅标题开场。
- 让观众在第一个长停顿之前就理解动画的内容。

## Beat 导演规则

- 每个 beat 应只有一个新的视觉创意。
- 每个 beat 应有一个主导焦点。
- 仅在支持焦点对象而非与其竞争时引入新文本。
- 优先使用变换、参数变化、揭示和高亮，而非用全新的静态布局替换整个帧。
- 如果结论重要，为创建它的过渡制作动画。
- 一个 beat 在不依赖解说的情况下观众能看到其完成状态之前不算完成。
  在引入下一个标题之前短暂保持该状态。
- 不要让标题文本领先动画一个 beat。标题应命名当前正在展示的状态，
  而非下一个将要出现的状态。

## 密度规则

- 每个 beat 保持一个主公式或一个主图形。
- 保持辅助文本简短。
- 将长解释移到解说而非画布上。
- 如果一帧感觉拥挤，在添加更多标签之前先简化。

## 结尾规则

- 以稳定的收获帧结束。
- 结尾应清晰解决前面引入的问题、构造或证明。
- 优先使用视觉回顾或最终高亮关系，而非通用项目符号摘要。
- 对于证明/等价结尾，使用从左到右的视觉方程：左侧
  对象或面积，中间 `=` 或等价提示，右侧结果。保持这些区域分离。
- 避免对象重叠、嵌套模糊或需要观众推断哪些形状被添加的最终帧。
- 如果最后一行是如 `c^2 = a^2 + b^2` 的定理，其上方图形必须传达相同关系，
  而非不同的构图。

## 数学文本导演

- 将渲染后的数学文本视为视觉材料。它必须在采样帧中可读，
  而不仅仅是在源代码中语法正确。
- 避免在 `Text()` 标签中使用 Unicode 上标和不常见符号。优先
  使用 `MathTex`（LaTeX 渲染成功后），或手动组合的标签（如基础
  `Text("a")` 加上更小的右上角 `Text("2")`）。
- 注意标题、字幕、公式和对象标签中的豆腐块（`□`）；
  这些是阻塞性问题，不是次要样式问题。

## 运动导演规则（物体如何移动）

上面的 beat 导演规则定义了*什么*在*何时*出现。本节定义
*如何*出现——使用哪种动画类型、easing 和节奏。运动即含义：
屏幕上物体的运动方式本身就是数学信息。

### 运动 = 含义映射

选择与所展示内容数学语义匹配的动画：

| 要传达 | 使用此动画 | 避免 |
|----------|-------------------|-------|
| 引入**新概念** | `GrowFromCenter`, `GrowFromEdge` | `FadeIn`（太突兀） |
| **推导 / 分步**过程 | `Write`, `Create` | 一次性展示所有内容 |
| **等价**或**变换** | `Transform`, `ReplacementTransform` | 消失 + 重新出现 |
| 强调**关键结果** | `Indicate`, `Flash`, `Circumscribe` | 纯颜色闪烁 |
| 展示**对应**或映射 | `Shift` + 可选虚线 | 瞬间跳转 |
| 扩展**现有想法** | `Stretch`, `scale` | 替换为更大版本 |
| 使某物**暂时突出** | `ease_out_back` + 缩放脉冲 | 仅静态高亮 |

### 使用动画辅助函数

`components.animation_helpers` 模块提供语义化动画函数，自动绑定上述运动=含义映射中正确的 `rate_func` 和 `run_time`：

| 要传达 | 辅助函数 | 内部行为 |
|----------|------------------|----------------------|
| 引入**新概念** | `reveal(obj)` | `GrowFromCenter` + `ease_out_cubic` + 自动 run_time |
| **推导 / 分步**过程 | `write_in(obj)` | `Write` + `linear` + 自动 run_time |
| 强调**关键结果** | `emphasize(obj)` | `Indicate` + `ease_out_back` + 自动 run_time |
| **等价**或**变换** | `transform_step(a, b)` | `ReplacementTransform` + `ease_in_out_sine` + 自动 run_time |
| 焦点**圆圈高亮** | `highlight_circle(obj)` | `Circumscribe` + 自动 run_time |
| **视觉持久化**（将旧内容缩小到角落） | `shrink_to_corner(obj)` | `scale(0.45)` + `to_corner(DL)` |

每个辅助函数返回动画对象，因此你仍可在需要时覆盖参数：
```python
self.play(reveal(new_concept), run_time=2.0)  # 覆盖默认时长
```

导入：`from components.animation_helpers import reveal, write_in, emphasize, transform_step, shrink_to_corner`

### Rate function（缓动）选择

`rate_func` 参数控制动画速度随时间的变化方式。
Manim 提供 30+ 个函数；以下是重要的几个：

| 场景 | 推荐 rate_func | 原因 |
|-----------|----------------------|-----|
| **揭示**（FadeIn, Create, Write） | `ease_out_cubic` 或 `ease_out_quad` | 快速启动 → 缓慢停止对出现感觉自然 |
| **变换**（Transform, ReplacementTransform） | `ease_in_out_sine` 或 `smooth` | 两端平滑；适合形状变形 |
| **强调**（Indicate, Flash, Circumscribe） | `ease_out_back` 或 `ease_out_elastic` | 过冲吸引额外注意力到目标 |
| **机械 / 线性运动** | `linear` | 恒定速度 = 机械感 |
| **默认 / 不确定** | `smooth` | S 形曲线；永远不会出错 |
| **永远不要用于揭示** | `ease_in_*` | 慢速启动使出现感觉迟钝 |

### 渐进式揭示纪律

这是专业数学动画（如 3b1b 风格）最重要的运动原则：

> **永远不要一次性展示完整的最终状态。**
> **每次 play() 调用应引入或改变最多 2–3 个 mobject。**

后果：
- 将复杂 beats 拆分为多个 `self.play()` + `self.wait()` 步骤。
- 如果你发现向单个 `play()` 传递 4+ 个 mobject，拆分它。
- 当元素应级联出现时使用 `LaggedStart(lag_ratio=0.15)`
  （这算作一次编排式揭示，而非 N 次独立出现）。
- 当一件事必须在下一件开始前完成时使用 `Succession()`。

### 视觉持久化模式

当 beat 完成时，重要视觉信息应以**减弱形式**保持可见
而非消失：

- 公式变换后，**缩小原始版本**并将其移至角落
  （`to_corner(DL)` 或 `to_corner(DR)`），缩放至 `scale(0.45)`。
- 这让观众在丢失线索时可以回看前面的步骤。
- 仅 `FadeOut` 真正临时性的元素（高亮闪烁、过渡箭头）。
- 永远不要 `FadeOut` 前一个 beat 的主要内容——改用 shrink-to-corner。

### 动画节奏 vs 解说

- 每 beat 的总动画时长 ≈ 口语化解说长度 × 0.12–0.18 s/字符
- 一行 10 字符中文解说（约 3 秒口语）→ 2.5–4 秒动画
- 比解说短的动画感觉仓促；比解说长的动画感觉拖沓
- 每次揭示后使用 `self.wait(0.3–0.8)` 让观众注册所见内容
- **避免 `self.wait(2.0)` 或更长**——会让观众以为视频卡住了

## 审查清单

- 开场是否快速展示了真实的视觉对象？
- 每个 beat 是否有清晰的焦点？
- 重要结论是否通过可见变化展示？
- 结尾是否感觉是 earned 的并与开场相连？
- 内容是否分布在屏幕区域（不是所有内容堆在中央）？
- 注释标签是否放在左/右区域，不与主内容重叠？
- 元素尺寸是否遵循层级（主内容 > 注释 > 脚注）？
