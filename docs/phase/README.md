# Pipeline Phase Documentation

本目录记录 Manim Agent pipeline 各阶段的输入、输出、约束和验收规则。

## 语言规范

提示词和阶段文档统一使用中文作为主说明语言。以下内容保留英文：

- schema 字段名，例如 `build_spec`、`video_output`、`implemented_beats`
- 工具名，例如 `Read`、`Write`、`Edit`、`Bash`、`Glob`、`Grep`
- 文件名、路径模板和命令示例，例如 `scene.py`、`GeneratedScene`
- 插件/skill 名称，例如 `scene-plan`、`render-review`

这样做的目标是让维护者阅读成本低，同时避免破坏 Agent SDK、Pydantic schema、Manim 和插件工作流依赖的英文标识符。

## 阶段索引

- [Phase 1: Planning](./phase1-planning.md)
- [Phase 2: Implementation](./phase2-implementation.md)
- [Phase 3: Render Resolve And Review](./phase3-render-review.md)
- [Phase 3.5: Narration Generation](./phase35-narration.md)
- [Phase 4: TTS](./phase4-tts.md)
- [Phase 5: Mux](./phase5-mux.md)

## 维护规则

- 修改阶段 prompt、schema、gate 或输出优先级时，同步更新对应阶段文档。
- 文档描述当前代码真实行为，不描述理想化未来方案。
- 如果某阶段存在临时兼容路径或 fallback，需要明确标注它是否属于主路径。
