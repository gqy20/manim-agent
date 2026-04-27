---
name: layout-safety
description: Audit Manim scene layouts for overlap, crowding, and frame overflow as an implementation-time advisory check. Use when arranging labels, formulas, callouts, braces, tables, or any dense beat where geometry-based layout checks can catch collisions earlier than frame review.
version: 1.0.0
argument-hint: " [layout-checkpoint-or-dense-beat]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep]
---

# Layout Safety

在实现期间对有视觉碰撞风险的 beat 使用此 skill。

## 为什么存在此 skill

- Manim 定位辅助函数如 `next_to()` 和 `arrange()` 使用成对边界对齐。
- 它们不会为你解决全局布局或检查第三方碰撞。
- 密集数学 beat 需要在最终渲染审查之前进行显式的几何检查。

## 主要目标

- 在最终渲染前捕获标签、公式、箭头和标注的重叠。
- 将重要 mobject 保持在安全边距内。
- 将布局问题转化为具体、可测量的修复，而非模糊的"减少拥挤"反馈。

## 审计工作流

1. 在 `construct()` 中识别最密集的 beat 或检查点。
2. 规范辅助实现位于本 skill 的 `scripts/layout_safety.py` 中。
3. 在 `scene.py` 存在后直接用 Python 运行该脚本。
4. 优先使用 `--checkpoint-mode after-play` 以捕获拥挤的过渡状态 beat，而不仅是最终帧。
5. 如果审计标记了问题，检查它并在警告反映真实布局问题时调整间距、缩放或 beat 结构。
6. 仅在布局稳定后移除临时调试脚手架。

## 推荐命令

```bash
python scripts/layout_safety.py scene.py GeneratedScene --checkpoint-mode after-play
```

仅在明确需要最终帧时使用 `--checkpoint-mode final`。

## 预期输出

- 退出码 `0`：在采样检查点中未发现布局问题
- 退出码 `1`：发现一个或多个重叠、拥挤或帧溢出问题
- 退出码 `2`：审计脚本无法加载或运行场景

将退出码 `1` 视为审查信号，而非场景不可用的证明。某些数学上有意义的布局会故意将标签、标记或轮廓放在相同的局部边界内。

## 检查内容

- 位于同一焦点对象旁边的文本、MathTex 和标签
- 可能侵入公式的括号、箭头和字幕
- 靠近帧边缘的表格、坐标轴标签和图例
- 旧对象尚未完全离开新对象就已到达的过渡状态

## 修复策略

- 增大 `next_to()` 或 `arrange()` 中的 `buff`
- 用 `scale_to_fit_width()` 减小对象宽度
- 将一个密集 beat 拆分为两个更清晰的 beat
- 将解释性文本移到不同边缘或角落
- 在引入新对象之前淡出或变换旧的强调对象

## 应避免的做法

- 假设 `next_to()` 能防止所有碰撞
- 仅在拥挤状态发生在 beat 中间时检查最终帧
- 向已经密集的构图添加更多高亮框或括号
