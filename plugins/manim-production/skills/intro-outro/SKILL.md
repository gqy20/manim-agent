---
name: intro-outro
description: Design and specify branded intro/outro segments for educational videos. Use when the task requires a title animation opening, branded outro frame, or full video assembly with intro + main content + outro. Advisory skill -- guides generation without blocking the core scene pipeline.
version: 1.0.0
argument-hint: " [intro-outro-config]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep]
---

# 片头 / 片尾

为教育视频设计和指定品牌化的开篇和收尾片段。

## 主要目标

- 产出 **3–5 秒的动画片头**，在主内容前建立视觉身份。
- 产出 **3–5 秒的片尾**，在主内容后提供收获或行动号召。
- 保持两个片段 **模板驱动**，以便用不同标题/消息重新生成。
- 确保 intro/outro 与主 Manim 渲染的场景视频 **无缝拼接**。
- 支持两种生成后端：
  - **Revideo**（首选）：MIT 许可的 TypeScript 框架，支持无头渲染。
  - **Manim 回退**：在 Revideo 不可用时使用现有的 `TitleCard` / `EndingCard` 组件。

这是一个 **建议性 skill** —— 它不会阻塞核心 pipeline。如果没有请求 intro/outro，
pipeline 的输出与当前行为完全一致。

## 此 skill 的激活条件

当以下**任一**条件为真时激活此 skill：

1. 用户明确请求 intro、outro、"片头"、"片尾"或"品牌视频"。
2. pipeline 调用设置了 `--intro-outro` CLI 标志。
3. 任务分类为 `concept-explainer` 且 `target_duration >= 60`。
4. 用户提到品牌化、频道身份、订阅提醒或 CTA。

如果以上条件均不满足，**完全跳过此 skill**。

## 片头模板规范

生成片头时，在 `structured_output.intro_spec` 中输出结构化 spec：

```yaml
title: string                     # 主标题（如 "勾股定理"）
subtitle: string | null           # 副标题行（如 "直角三角形三边关系"）
brand_element: string | null      # 品牌文本/Logo（如频道名称）
duration_seconds: float           # 目标 3.0 - 5.0
animation_style: string           # 以下样式之一
background_color: string          # 十六进制颜色，默认 "#050A14"（3b1b 深色）
accent_color: string              # 十六进制颜色，默认 "#58C4DD"（3b1b 蓝色）
music_cue: string | null           # 短音效描述（如 "柔和提示音"）
```

### 可用的片头样式

| 样式 ID | 视觉效果 | 氛围 | 最适合 |
|----------|---------------|------|----------|
| `fade_in_title` | 标题从黑色淡入，副标题从下方滑上 | 干净、专业 | 正式数学主题 |
| `write_title` | 标题像手写一样逐字出现 | 学术、深思 | 证明、推导 |
| `reveal_from_center` | 标题从中心缩放并带发光脉冲 | 戏剧性、有活力 | 关键概念、定理 |
| `typewriter` | 逐字揭示并带光标闪烁 | 技术、现代 | CS、算法 |

### 片头时序指南

| 总时长 | 标题揭示 | 副标题/品牌出现 | 过渡前停留 |
|---------------|-------------|----------------------|-------------------|
| 3.0 s | 0.0–1.2 s | 1.0–2.0 s | 2.0–3.0 s |
| 4.0 s | 0.0–1.5 s | 1.2–2.5 s | 2.5–4.0 s |
| 5.0 s | 0.0–2.0 s | 1.5–3.5 s | 3.5–5.0 s |

## 片尾模板规范

生成片尾时，在 `structured_output.outro_spec` 中输出结构化 spec：

```yaml
message: string                   # 收获文本（如 "记住：a² + b² = c²"）
cta_text: string | null           # 行动号召（如 "点赞关注，下期见"）
subscribe_reminder: bool          # 显示订阅图标/文本
duration_seconds: float           # 目标 3.0 - 5.0
animation_style: string           # 以下样式之一
background_color: string          # 十六进制颜色，默认 "#050A14"
accent_color: string              # 十六进制颜色，默认 "#83C167"（3b1b 绿色）
```

### 可用的片尾样式

| 样式 ID | 视觉效果 | 氛围 | 最适合 |
|----------|---------------|------|----------|
| `takeaway_card` | 居中消息带微妙的边框发光 | 结论感、满足感 | 证明结尾、关键结果 |
| `cta_banner` | 底部横幅带上滑的 CTA + 订阅图标 | 引人入胜、社交 | 频道增长导向 |
| `minimal_fade` | 消息在深色背景上淡入、保持、淡出 | 平静、反思 | 总结收获 |
| `qed_style` | Q.E.D. 标记先出现，然后收获消息 | 正式、学术 | 证明演示 |

### 片尾时序指南

| 总时长 | 消息出现 | CTA/额外内容出现 | 淡出前停留 |
|---------------|----------------|-------------------|--------------|
| 3.0 s | 0.0–1.0 s | 1.0–2.0 s | 2.0–3.0 s |
| 4.0 s | 0.0–1.5 s | 1.2–2.8 s | 2.8–4.0 s |
| 5.0 s | 0.0–2.0 s | 1.5–3.5 s | 3.5–5.0 s |

## Revideo 集成模式

Revideo 是 intro/outro 生成的首选后端。它是 MIT 许可的、
基于 TypeScript 的框架，支持通过 CLI 进行无头渲染。

### 项目结构约定

将 Revideo 模板文件放在任务目录下：

```
{task_dir}/
├── revideo/
│   ├── intro.tsx            # 片头模板组件
│   ├── intro-config.json    # 片头动态配置
│   ├── outro.tsx            # 片尾模板组件
│   └── outro-config.json    # 片尾动态配置
```

### Config JSON schema

`intro-config.json` 和 `outro-config.json` 都遵循此形状：

```json
{
  "title": "勾股定理",
  "subtitle": "直角三角形三边关系",
  "brandElement": null,
  "duration": 4.0,
  "style": "fade_in_title",
  "backgroundColor": "#050A14",
  "accentColor": "#58C4DD",
  "resolution": { "width": 1920, "height": 1080 },
  "fps": 30
}
```

Outro config 使用 `message`、`ctaText`、`subscribeReminder` 替代 title 字段：

```json
{
  "message": "记住：a² + b² = c²",
  "ctaText": "点赞关注",
  "subscribeReminder": true,
  "duration": 4.0,
  "style": "takeaway_card",
  "backgroundColor": "#050A14",
  "accentColor": "#83C167",
  "resolution": { "width": 1920, "height": 1080 },
  "fps": 30
}
```

### 渲染命令

```bash
# 渲染片头
npx revideo render {task_dir}/revideo/intro.tsx \
  --output {task_dir}/intro.mp4

# 渲染片尾
npx revideo render {task_dir}/revideo/outro.tsx \
  --output {task_dir}/outro.mp4
```

### 模板存根模式

每个 `.tsx` 文件应从其 JSON 同级文件导入 config 并使用标准
Revideo 原语：

```tsx
import { FaDeIn, Rect, Txt, useVideoConfig } from "@revideo/2d";
import { useCurrentFrame, interpolate, spring } from "@revideo/core";
import config from "./intro-config.json";

export default makeScene2D("intro", function* (view) {
  // ... 基于 config.style 的实现 ...
});
```

详细的 API 参考和每种样式的完整模板示例，
参见 `<plugin_dir>/references/revideo-integration.md`。

### 分辨率匹配

**关键：** 所有 Revideo 输出必须匹配 Manim 渲染分辨率：
- 宽度：**1920 px**
- 高度：**1080 px**
- FPS：**30**

这与 Manim 的 `-qh`（1080p）默认输出匹配。分辨率不匹配
会导致拼接失败或黑边。

## Manim 回退模式

当 Revideo 未安装或用户偏好纯 Manim 时，使用现有组件生成 intro/outro
作为独立 Manim 场景。

### 文件放置

```
{task_dir}/
├── intro_scene.py             # 独立片头场景
└── outro_scene.py             # 独立片尾场景
```

### 片头场景模式

使用 `TitleCard` 作为基类或通过工厂方法提取 mobject：

```python
from components.titles import TitleCard

class IntroScene(TitleCard):
    title = "勾股定理"
    subtitle = "直角三角形三边关系"

    def construct(self):
        mobs = self.get_title_mobjects(
            title=self.title,
            subtitle=self.subtitle,
        )
        self.play(Write(mobs["title"]), run_time=1.5)
        if self.subtitle:
            self.play(FadeIn(mobs["subtitle"]), run_time=0.8)
        self.wait(1.0)
```

### 片尾场景模式

使用 `EndingCard` 作为基类：

```python
from components.titles import EndingCard

class OutroScene(EndingCard):
    message = "记住：a² + b² = c²"
    show_qed = True

    def construct(self):
        mobs = self.get_ending_mobjects(
            message=self.message,
            show_qed=self.show_qed,
        )
        if self.show_qed:
            self.play(Write(mobs["qed"]), run_time=1.0)
            self.wait(0.3)
        self.play(FadeIn(mobs["message"]), run_time=1.0)
        self.wait(1.0)
```

### 渲染命令

```bash
# 渲染片头
manim -qh intro_scene.py IntroScene
# 输出：media/videos/intro_scene.mp4

# 渲染片尾
manim -qh outro_scene.py OutroScene
# 输出：media/videos/outro_scene.mp4
```

### 时长控制

为确保 3–5 秒输出：
- 对每个 `self.play()` 调用显式控制 `run_time`。
- 将总 `self.wait()` 限制在 ≤ 1.5 秒。
- 在 intro/outro 场景中避免过长动画（`run_time > 2.0`）。
- 渲染后用 `ffprobe` 验证输出时长。

各样式的详细回退模板，参见 `<plugin_dir>/references/manim-fallback.md`。

## 结构化输出约定

此约定专属于 intro/outro 阶段。它不属于主 Phase 2 实现 schema 的一部分。

当此 skill 处于活跃状态时，填充 `PipelineOutput` 中的以下字段：

| 字段 | 类型 | 何时填充 |
|-------|------|------------------|
| `intro_requested` | `bool` | 如果请求了 intro 始终设为 `true` |
| `outro_requested` | `bool` | 如果请求了 outro 始终设为 `true` |
| `intro_spec` | `dict` | 当请求了 intro 时（见上方 Intro spec） |
| `outro_spec` | `dict` | 当请求了 outro 时（见上方 Outro spec） |
| `intro_video_path` | `str` | 渲染后的 intro MP4 路径（成功渲染后） |
| `outro_video_path` | `str` | 渲染后的 outro MP4 路径（成功渲染后） |
| `intro_outro_backend` | `str` | `"revideo"` 或 `"manim"` |

如果请求了 intro/outro 但渲染失败，将 `_video_path` 设为 `null`
并在 `deviations_from_plan` 中包含错误详情。不要阻塞 pipeline 完成。

## 拼接约定

后端 pipeline 调用 `video_builder.concat_videos()` 来组装最终视频：

```
[intro.mp4] + [main_content.mp4] + [outro.mp4] → final_output.mp4
```

规则：
- 所有输入必须是 **MP4**，相同的 **1920x1080** 分辨率，相同的 **30 fps**。
- 顺序始终是：intro → 主内容 → outro。
- 缺失的片段直接省略（如仅 intro + 主内容）。
- 拼接使用 FFmpeg **流拷贝**（`-c copy`）—— 无重新编码，无损。
- 拼接后的输出 **覆盖** 原始 `final_video_output` 路径。
- 保留 intro/outro 的音频轨道（如 intro 中的音乐提示音）。

## 审查清单

生成 intro/outro 片段后，验证：

- [ ] Intro 时长在 3–5 秒之间（用 ffprobe 检查）。
- [ ] Outro 时长在 3–5 秒之间。
- [ ] 颜色与 `<plugin_dir>/references/style-3b1b.md` 中定义的调色板匹配。
- [ ] 分辨率为 1920x1080 @ 30fps（与主场景匹配）。
- [ ] 文本在目标分辨率下可读（无过小字体）。
- [ ] CTA 文本（如有）与目标受众语言匹配。
- [ ] 片段之间无突兀切换——过渡感觉自然。
- [ ] `intro_spec` / `outro_spec` 已在 structured output 中填充。
- [ ] `intro_video_path` / `outro_video_path` 指向已存在的文件。

## 参考

所有参考文件位于 `<plugin_dir>/references/` 下。以下路径相对于插件根目录：

- Revideo 集成模式、CLI 用法和 API 参考，读取 `references/revideo-integration.md`。
- 带视觉规格和代码草图的片头模板目录，读取 `references/intro-templates.md`。
- 带视觉规格和代码草图的片尾模板目录，读取 `references/outro-templates.md`。
- 带完整场景模板的纯 Manim 回退方案，读取 `references/manim-fallback.md`。
- 3Blue1Brown 视觉风格配置文件（颜色、节奏），读取 `references/style-3b1b.md`。
