---
name: render-review
description: Review rendered Manim video frames before a task is allowed to succeed. Uses AI vision analysis to inspect sampled frames for opening clarity, beat focus, visual density, conclusion payoff, or other blocking visual issues after rendering.
version: 1.0.1
argument-hint: " [rendered-video-or-frame-set]"
allowed-tools: [Read, Glob, Grep]
vision-enabled: true
---

# Render Review

渲染后、报告成功前使用此 skill。

## 主要目标

- 从实际渲染输出（而不仅仅是从代码）中捕获阻塞性视觉问题。
- 确认开场、中间 beats 和结尾看起来都是有意设计的。
- 拒绝技术上完成但视觉上薄弱或具有误导性的渲染。
- 使用 **逐帧视觉分析**（AI vision）将审查决策建立在实际像素内容基础上。

## 审查工作流

1. **必须使用 Read 工具读取每一张帧图像**——这不是可选的。
2. 对每张帧，使用以下标准形成具体的视觉评估。
3. 如果有计划可用，将评估与预期场景结构进行对比。
4. 决定渲染是否可接受或需要修改。
5. 如果需要修改，为下一轮构建具体说明阻塞问题。

## 逐帧评估

对每个采样帧，报告：

| 维度 | 检查内容 |
|-----------|---------------|
| **屏幕内容** | 可见哪些对象、文本、公式、标签、箭头？ |
| **视觉密度** | 稀疏 / 平衡 / 拥挤 |
| **焦点** | 是否有一个清晰的主要主体？ |
| **标签可读性** | 清晰 / 部分遮挡 / 无法辨认 / 无 |
| **视觉问题** | 重叠、截断、过小、位置错误等 |

每帧都标注其 beat 上下文（如 `opening`、`beat_2__Core formula`、`ending`）。
用此标签交叉验证该 beat 本应展示的内容。

## 阻塞性问题

如果以下任一为真，将渲染标记为阻塞：

- 开场帧大部分为空或仅有标题而无有意义的视觉对象。
- 某 key beat 看起来过度拥挤或视觉混乱。
- 重要结论被陈述但未通过可见变化展示。
- 结尾缺乏清晰的收获点或未解决开场提出的问题。
- 标签、公式或焦点对象竞争过于激烈导致主要意图不清晰。
- Vision 分析报告某帧应有可读内容的标签为"无法辨认"。

## Pipeline 交接

当此 skill 在主 pipeline 中使用时，通过运行时提供的 structured output schema 返回审查结果。不要在此 skill 中重新定义 schema。

交接应明确以下事实：

- 渲染是否可接受。
- 支持该决定的视觉证据。
- 检查了哪些采样帧。
- 哪些问题是阻塞性的，哪些是可选建议。
- 如果需要修改，下一轮构建应改变什么。

## 应避免的做法

- 仅仅因为文件存在就通过渲染。
- 跳过帧图像读取——你必须目视检查每一帧。
- 报告模糊反馈如"做得更好"而没有具体症状。
- 将次要样式偏好视为阻塞性问题。
- 在没有帧本身证据的情况下反驳 vision 分析的结果。
