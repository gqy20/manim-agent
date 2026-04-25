# Phase 5: Mux

## 目标

Phase 5 使用 FFmpeg 将视频、TTS 音频、字幕和可选 BGM 合成为最终 MP4。

## 输入

- `video_output`
- Phase 4 的 `audio_path`
- Phase 4 的 `subtitle_path`
- `output_path`
- 可选 `bgm_path`
- `bgm_volume`

## 外部依赖

- FFmpeg

## 输出

- `final_video_output`
- 最终返回的 MP4 路径

如果 `no_tts=true`，会跳过 Phase 4 和 Phase 5，直接返回静音 `video_output`。

## 验收规则

- 输入视频必须存在。
- 音频路径必须存在。
- 合成完成后最终 MP4 路径必须可用于后端 canonical 化和 R2 上传。

## 当前风险

- segment 模式可能需要先构造视觉 track，再 mux 音频。
- FFmpeg 错误需要保留足够日志，方便复盘。
