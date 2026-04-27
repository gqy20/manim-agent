---
name: narration-sync
description: Keep narration spoken, beat-aligned, and visually synchronized for Manim teaching animations. Use when writing, reviewing, or refining narration so it matches the current visual beat instead of sounding like a detached summary.
version: 1.0.0
argument-hint: " [narration-or-plan]"
allowed-tools: [Read, Glob, Grep]
---

# Narration Sync

使用此 skill 来保持配音与观众当前所见内容对齐。

## 主要目标

- 让解说听起来像口语，而不是幻灯片要点。
- 将解说与 beats 对齐，而非代码块。
- 让解说聚焦于当前视觉动作。
- 覆盖完整动画流程，而不是压缩成一句话总结。

## 解说规则

- 默认每个 beat 写一到两句口语文本。
- 描述当前正在出现、移动、变化或被比较的内容。
- 避免在视觉到达之前预先解释后续步骤。
- 当一句话就够用时避免长句堆叠。
- 如果画布已经很密集，让解说更简单而不是添加更多文本。

## 对齐规则

- 每个 beat 应有对应的解说片段。
- 解说应按与视觉 beats 相同的顺序排列。
- 如果场景在实现过程中改变了顺序，更新解说以匹配。
- 如果某个 beat 主要是视觉的，使用较短的解说行而非用额外解释填充沉默。

## 应避免的做法

- 一句话总结整个动画。
- 读起来像证明记录而非口语的解说。
- 引入屏幕上尚未出现的术语。
- 逐字重复屏幕文本而不添加引导。

## 审查清单

- 每行解说能否映射到特定 beat？
- 解说是否描述当前视觉状态而非未来步骤？
- 口语节奏是否足够短以听起来自然？
- 解说是否覆盖从开场到结尾的完整动画？

## Pipeline 交接

当此 skill 在主 pipeline 中使用时，将最终解说写入运行时提供的实现 schema。除非当前运行时 schema 明确要求，否则不要添加单独的解说映射字段。

Pipeline 从已批准的 Phase 1 `build_spec` 加上最终解说推导 beat 到解说的对应关系、覆盖率标志和时长估算。
