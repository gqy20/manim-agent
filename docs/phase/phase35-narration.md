# Phase 3.5: Narration Generation

## 目标

Phase 3.5 在渲染确认后生成或修正适合 TTS 的自然口播文案。

## 输入

- `user_text`
- `target_duration_seconds`
- `plan_text`
- Phase 3 确认后的 `PipelineOutput`
- `video_output`
- 实际视频时长
- implementation system prompt

## 工具权限

主路径为 no-tools LLM pass：

- 不读文件。
- 不写文件。
- 不渲染。
- 不探测路径。

## 输出

输出一段自然的简体中文口播文本，并写回：

- `po.narration`

## 验收规则

- 口播必须是连续自然语言，不是 bullet list。
- 口播应覆盖实际实现的 beats。
- 如果已有 narration 过短或不适合口播，会重新生成。
- 如果 LLM 输出仍不合格，使用模板 fallback。

## 当前风险

- 模板 fallback 可能语义较粗糙。
- 中文字符长度估算只能近似匹配真实 TTS 时长。
