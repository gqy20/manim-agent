# Phase 4: TTS

## 目标

Phase 4 把最终 narration 转成音频、字幕和可选的 beat-level 音频资产。

## 输入

- `video_output`
- `po.narration`
- `voice_id`
- `model`
- `target_duration_seconds`
- `bgm_enabled`
- `bgm_prompt`
- `bgm_volume`
- `output_path`
- `render_mode`
- `segment_video_paths`

## 外部依赖

- MiniMax TTS
- 可选背景音乐生成客户端
- FFmpeg 音频拼接

## 输出

音频编排结果，通常包含：

- `audio_path`
- `subtitle_path`
- `duration_ms`
- 可选 `bgm_path`
- 可选拼接后的 `audio_track`

同时会更新 `PipelineOutput` 中的音频、字幕和 BGM 相关字段。

## 验收规则

- TTS 必须返回可用音频路径。
- BGM 生成失败时，回退到纯人声音频，不阻断主流程。
- narration 明显短于视频时，保留完整视频并允许尾部静音，而不是截断视频。

## 当前风险

- 外部 TTS 服务不稳定时会直接影响最终视频生成。
- beat-level 音频和字幕对齐仍依赖估算与编排策略。
