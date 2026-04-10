# Manim Agent — AI 驱动的数学动画视频自动生成系统

## 1. 产品概述

### 1.1 一句话描述

用户输入自然语言描述，系统自动生成带有专业配音的 Manim 数学/科普动画视频。

### 1.2 核心价值

- **零代码门槛**：用自然语言描述想要的内容，无需了解 Manim API 或动画编程
- **视觉反馈循环**：渲染预览 → 视觉审查 → 迭代优化，保证输出质量
- **专业配音**：集成 MiniMax 高质量 TTS，支持多音色、语气词、字幕时间戳同步
- **端到端自动化**：从文字到成品视频，全流程无人值守

### 1.3 目标用户

- 教育内容创作者（数学/物理/科普讲解视频）
- 知识博主（B站/YouTube 技术类短视频）
- 科研人员（论文中的概念演示动画）

---

## 2. 技术架构

### 2.1 架构总览（Source Layout）

```
manim-agent/                          # 项目根目录
│
├── pyproject.toml                   #     项目配置 & 依赖声明
│
├── src/                             # ◄── 源码根目录（src layout）
│   └── manim_agent/                #     Python 包名
│       ├── __init__.py             #     包初始化 & 版本号
│       │
│       ├── __main__.py             # ◄── 入口：python -m manim_agent
│       │   ├── from . import prompts      #  加载系统提示词
│       │   ├── from . import tts_client   #  TTS 合成调用
│       │   ├── from . import video_builder # FFmpeg 合成调用
│       │   ├── from claude_agent_sdk     #  import query, ClaudeAgentOptions
│       │   │   └── query()               #  ═══ 启动 Claude Code 子进程 ═══
│       │   ├── parse VIDEO_OUTPUT        #  ← 从 AssistantMessage 提取结果
│       │   └── asyncio.run(main())       #  事件循环入口
│       │
│       ├── prompts.py              # ◄── 配置层：系统提示词模板
│       │   └── SYSTEM_PROMPT       #     角色 / 编码指南 / 输出格式约束
│       │
│       ├── tts_client.py           # ◄── 服务层：MiniMax 异步 TTS
│       │   ├── POST /v1/t2a_async_v2   #  创建合成任务 → task_id
│       │   ├── GET  /v1/t2a_async/query #  轮询状态 (间隔3s, 超时300s)
│       │   └── download → {audio, subtitle, extra_info}
│       │                              │
│       │                       api.minimaxi.com (HTTPS)
│       │
│       └── video_builder.py        # ◄── 服务层：FFmpeg 视频合成
│           ├── ffprobe              #     取视频/音频时长
│           ├── 时长对齐策略          #     shortest / tpad / speed
│           └── ffmpeg -i video -i audio -vf subtitles → output.mp4
│
├── output/                          #     运行时输出（gitignore）
│   ├── *.mp4                        #     中间产物 & 最终视频
│   ├── *.mp3                        #     TTS 音频
│   ├── *.srt                        #     字幕文件
│   └── *.json                       #     TTS 元信息


═══════════════════════════════════════════════════════════════════
                    Claude Code CLI (query() 启动的子进程)
═══════════════════════════════════════════════════════════════════

  通信协议: JSONL over stdin/stdout

  ┌─────────────────────────────────────────────────────────────┐
  │                    Claude (AI Agent)                        │
  │                                                             │
  │  接收: system_prompt + user_prompt                         │
  │  输出: Message 流 (AssistantMessage / ResultMessage)        │
  │                                                             │
  │  内置工具 (自主调用，无需 MCP 封装):                          │
  │                                                             │
  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐ │
  │  │ Write    │  │ Edit     │  │ Bash     │  │ Read        │ │
  │  │          │  │          │  │          │  │ (多模态)     │ │
  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘ │
  │       │             │            │               │          │
  │       ▼             ▼            ▼               ▼          │
  │  scenes/       scenes/      manim 命令      渲染产物       │
  │  *.py (新建)   *.py (修改)   -qh/-ql/-s    图片/日志      │
  │       │             │            │               │          │
  │       └──────────┬─┴────────────┘               │          │
  │                  ▼                              ▼          │
  │           media/*.mp4                    last_frame.png    │
  │           (静音视频)                     (视觉反馈)        │
  │                                                             │
  │  工作循环: 写代码 → 渲染 → 审查图片 → 修改 → 重试 ...     │
  │  终止条件: 满意后输出 VIDEO_OUTPUT: <path> 标记              │
  └─────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════
                           外部依赖
═══════════════════════════════════════════════════════════════════

  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
  │ claude-agent │    │    manim     │    │    ffmpeg    │
  │    sdk       │    │   >=0.20.1   │    │  (系统安装)   │
  │  (pip 依赖)  │    │  (pip 依赖)  │    │              │
  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
         │                   │                   │
         │           数学动画渲染引擎         │
         │           Cairo / OpenGL 后端     │ 视频/音频/字幕
         │                                    │ 合成器
  ┌──────▼───────────────────▼──────────────────▼───────────┐
  │                    MiniMax TTS API                       │
  │               api.minimaxi.com                          │
  │                                                         │
  │  model: speech-2.8-hd  |  异步模式 (t2a_async_v2)        │
  │  输出: audio.mp3 + subtitle.srt + extra_info.json       │
  └─────────────────────────────────────────────────────────┘
```

**模块依赖关系**（import 方向）：

```
src/manim_agent/__main__.py
  ├─▶ .prompts            (包内相对导入: SYSTEM_PROMPT 常量)
  ├─▶ claude_agent_sdk    (第三方库: query, ClaudeAgentOptions, Message 类型)
  ├─▶ .tts_client         (包内相对导入: synthesize() → TTSResult)
  └─▶ .video_builder      (包内相对导入: build_final_video() → str)

src/manim_agent/tts_client.py
  └─▶ httpx              (第三方库: HTTP 客户端)

src/manim_agent/video_builder.py
  └─▶ subprocess         (标准库: 调用 ffmpeg/ffprobe)

src/manim_agent/prompts.py
  └─▶ (无依赖)
```

**架构分层**：

| 层级 | 文件 | 类型 | 职责 |
|------|------|------|------|
| 入口 | `src/manim_agent/__main__.py` | 编排器 | CLI → options 构建 → query() → 解析结果 → 串联后续步骤 |
| 配置 | `src/manim_agent/prompts.py` | 纯数据 | SYSTEM_PROMPT 常量 + get_prompt() 模式选择函数 |
| 服务 | `src/manim_agent/tts_client.py` | 异步客户端 | MiniMax API 全流程（创建→轮询→下载） |
| 服务 | `src/manim_agent/video_builder.py` | 异步处理器 | ffprobe + ffmpeg 时长对齐与合成 |
| 运行时 | Claude Code CLI | 子进程 | AI Agent 自主驱动 Write/Edit/Bash/Read 循环 |
| 外部 | MiniMax API / manim / ffmpeg | 依赖 | TTS / 渲染 / 合成 |

**数据流（按执行时序）**：

```
用户输入文本
  │
  ▼
[__main__.py] argparse → user_text
  │
  ▼
[__main__.py] prompts.get_prompt(user_text, preset, quality) → full_prompt
  │
  ▼
[__main__.py] ClaudeAgentOptions(cwd, system_prompt, permission_mode, max_turns)
  │
  ▼
[__main__.py] async for msg in query(prompt=full_prompt, options=options):
  │           │
  │           ├── AssistantMessage.TextBlock → 解析 VIDEO_OUTPUT 行
  │           ├── ToolUseBlock(Bash/manim)     → Claude 在渲染
  │           ├── ToolUseBlock(Write)          → Claude 在写代码
  │           ├── ToolResultBlock               → 渲染结果返回
  │           └── ResultMessage                 → 终止迭代
  │
  ▼
[__main__.py] video_output_path = 解析到的路径
  │
  ▼
[__main__.py] await tts_client.synthesize(script_text, voice_id)
  │           │
  │           ├── POST /v1/t2a_async_v2  → task_id
  │           ├── GET  /v1/t2a_async/query × N (轮询)
  │           └── status=Success → 下载 audio.mp3 + subtitle.srt
  │
  ▼
[__main__.py] await video_builder.build_final_video(video, audio, subtitle, output)
  │           │
  │           ├── ffprobe 取时长
  │           ├── 时长对齐
  │           └── ffmpeg 合成 → final.mp4
  │
  ▼
输出: output/final.mp4 ✓
```
    → [query()] 启动 Claude Code 子进程
    → [Claude] Write(scene.py) → Bash(manim) → Read(图片) → Edit(改代码) ... 循环
    → [Claude] 输出 VIDEO_OUTPUT 标记
    → [__main__.py] 解析 AssistantMessage.TextBlock 提取路径
    → [tts_client] 异步 TTS: 创建任务 → 轮询 → 下载音频+字幕
    → [video_builder] ffmpeg 合并: 视频 + 音频 + 字幕 → 最终 MP4
```

### 2.2 核心运行时：Claude Agent SDK

系统通过 `claude-agent-sdk` 的 `query()` 函数启动 Claude Code CLI 子进程，以 JSONL 协议双向通信。Claude 拥有以下能力：

| 能力 | 来源 | 用途 |
|------|------|------|
| 文件读写 | Claude Code 内置工具 | 编写/修改 Manim Python 代码 |
| 命令执行 | Claude Code 内置工具 | 运行 `manim` 渲染命令 |
| 图片查看 | Claude Code 多模态 | 审查渲染结果的最后一帧截图 |
| 代码推理 | Claude 自身能力 | 编写正确的 Manim 动画代码 |

**不使用 MCP 封装 Manim 操作** — Claude Code 的内置工具已完全覆盖文件操作和命令执行需求。MCP 仅用于 Claude 原生无法完成的外部服务调用（当前仅 TTS）。

### 2.3 外部依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| claude-agent-sdk | >=0.1.58 | Claude Code 子进程通信 |
| manim | >=0.20.1 | 数学动画渲染引擎 |
| httpx | latest | HTTP 客户端（TTS API 调用） |
| ffmpeg | 系统安装 | 视频/音频/字幕合成 |
| MiniMax TTS API | speech-2.8-hd | 异步语音合成 |

---

## 3. 模块详细设计

### 3.1 `src/manim_agent/__main__.py` — 主程序入口

**职责**：CLI 参数解析、SDK 初始化、流程编排、结果收集

```python
# 使用方式示例（通过 python -m 运行）
python -m manim_agent "解释傅里叶变换的原理" --voice female-tianmei --output fourier.mp4
python -m manim_agent "讲解二叉树的遍历方式" --preset educational --output tree.mp4
```

**核心流程**：

```
1. 解析 CLI 参数（文本描述、音色选项、输出路径等）
2. 加载系统提示词模板 (src/manim_agent/prompts.py)
3. 构建 ClaudeAgentOptions：
   - cwd = 项目工作目录
   - system_prompt = 系统提示词字符串
   - permission_mode = "acceptEdits"（允许自动编辑）
   - max_turns = 50（防止无限循环，见 §7.2）
4. 调用 query() 函数，迭代消息流：
     async for message in query(prompt=user_prompt, options=options):
         ...
     # 迭代器在 ResultMessage 时自动终止
5. 从 AssistantMessage 中提取 VIDEO_OUTPUT 路径（§3.1.1 结果提取）
6. 调用 tts_client 合成配音
7. 调用 video_builder 合成最终视频
8. 输出最终文件路径
```

> **为什么用 `query()` 而非 `ClaudeSDKClient`**：
> v1 是一次性流程（发 prompt → 拿结果 → 后处理），不需要中途追问、动态切权限或 interrupt。
> `query()` 是 fire-and-forget 的异步迭代器，2 行代码即可启动；`Client` 需要 ~15 行样板代码。
> 如果 v2 需要交互式能力（用户预览后追加指令），再迁移到 `ClaudeSDKClient` 即可。
> 参考源码 `query.py:11-126`。

#### 3.1.1 结果提取策略

调用 `query()` 后获得异步消息流，遍历直到收到 `ResultMessage`（迭代器自动终止）。

从 `AssistantMessage` 的 `TextBlock.content` 中解析 Claude 输出的结构化标记行：

```python
from claude_agent_sdk import query, AssistantMessage, ResultMessage, TextBlock

video_output_path = None
scene_file = None
scene_class = None

async for msg in query(prompt=user_prompt, options=options):
    if isinstance(msg, AssistantMessage):
        for block in msg.content:
            if isinstance(block, TextBlock):
                for line in block.text.splitlines():
                    if line.startswith("VIDEO_OUTPUT:"):
                        video_output_path = line.split(":", 1)[1].strip()
                    elif line.startswith("SCENE_FILE:"):
                        scene_file = line.split(":", 1)[1].strip()
                    elif line.startswith("SCENE_CLASS:"):
                        scene_class = line.split(":", 1)[1].strip()
    elif isinstance(msg, ResultMessage):
        if msg.is_error:
            raise RuntimeError(
                f"Claude error after {msg.num_turns} turns, "
                f"cost=${msg.total_cost_usd:.4f}"
            )
        # 迭代器在此终止
```

**备选方案 — 结构化输出（v1.1）**：可利用 `ClaudeAgentOptions.output_format` 设置 JSON Schema
强制 Claude 返回 JSON 格式结果，避免文本解析的不确定性。当前 v1 使用文本标记方案以降低复杂度。

**CLI 参数设计**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `text` / 位置参数 | str | 必填 | 自然语言描述的视频内容 |
| `--output`, `-o` | path | `output.mp4` | 输出视频文件路径 |
| `--voice` | str | `female-tianmei` | MiniMax 音色 ID |
| `--model` | str | `speech-2.8-hd` | TTS 模型 |
| `--quality` | str | `high` | 渲染质量 (high/medium/low) |
| `--no-tts` | flag | False | 跳过语音合成，只生成静音视频 |
| `--cwd` | path | 当前目录 | 工作目录 |
| `--prompt-file` | path | None | 从文件读取自定义提示词 |
| `--max-turns` | int | 50 | Claude 最大交互轮次（防止无限循环） |

### 3.2 `src/manim_agent/prompts.py` — 系统提示词模板

**职责**：定义 Claude 的角色、行为规范、Manim 编码指南、输出格式要求

**提示词结构**：

```
# Role
你是一个专业的 Manim 动画工程师和教育内容创作者。
你的任务是根据用户的自然语言描述，编写并渲染出高质量的 Manim 动画视频。

# Capabilities
你可以直接使用以下内置能力：
- Write: 创建和编辑 .py 文件
- Edit: 修改已有代码
- Bash: 执行 manim 渲染命令
- Read: 查看渲染输出的图片和日志

# Workflow Rules
1. 先分析用户需求，规划场景结构
2. 编写完整的 Manim Scene 代码（包含 import、class 定义、construct 方法）
3. 使用 Bash 执行渲染命令验证
4. 如果渲染失败或效果不佳，修改代码重新渲染
5. 最终确认后，报告生成的视频文件路径

# Manim Coding Guidelines
- 使用 Community Edition (manim) 导入：from manim import *
- Scene 类名使用 PascalCase，如 FourierTransformScene
- 合理使用 Wait() 控制节奏
- 颜色使用 BLUE, RED, GREEN, YELLOW, WHITE 等常量
- 字体大小适中（24-48），确保可读性
- 复杂动画分步骤展示，不要一次性堆砌

# Rendering Commands
高质量（默认）: manim -qh <script>.py <ClassName>
中等质量:     manim -qm <script>.py <ClassName>
快速预览:     manim -ql <script>.py <ClassName>
仅最后一帧:   manim -s --format=png <script>.py <ClassName>

# Output Format
完成后必须输出以下格式的结果：
VIDEO_OUTPUT: <生成的mp4文件完整路径>
SCENE_FILE: <使用的Python脚本路径>
SCENE_CLASS: <Scene类名>
DURATION: <估算时长秒数>
```

**预设模式扩展**（可选）：

| 模式 | 适用场景 | 提示词变体 |
|------|----------|-----------|
| `educational` | 教学讲解 | 强调循序渐进、关键公式高亮 |
| `presentation` | 演示汇报 | 强调简洁美观、信息密度 |
| `proof` | 数学证明 | 强调逻辑推导、步骤清晰 |
| `concept` | 概念可视化 | 强调直观比喻、动画流畅 |

### 3.3 `src/manim_agent/tts_client.py` — MiniMax 异步 TTS 客户端

**职责**：封装 MiniMax 异步语音合成全流程（创建任务 → 轮询 → 下载）

#### 3.3.1 API 端点

| 操作 | 方法 | URL |
|------|------|-----|
| 创建任务 | POST | `https://api.minimaxi.com/v1/t2a_async_v2` |
| 查询状态 | GET | `https://api.minimaxi.com/v1/t2a_async/query?task_id={id}` |
| 下载文件 | GET | 通过 file_id 调用文件检索接口 |

备用地址：`https://api-bj.minimaxi.com/v1/t2a_async_v2`

#### 3.3.2 核心接口

```python
@dataclass
class TTSResult:
    audio_path: str           # 音频文件本地路径 (.mp3)
    subtitle_path: str        # 字幕文件本地路径 (.srt)
    extra_info_path: str      # 元信息 JSON 本地路径
    duration_ms: int          # 音频时长（毫秒）
    word_count: int           # 字符计数
    usage_characters: int     # 计费字符数


async def synthesize(
    text: str,
    voice_id: str = "female-tianmei",
    model: str = "speech-2.8-hd",
    output_dir: str = "./output",
    speed: float = 1.0,
    emotion: str | None = None,
) -> TTSResult:
    """
    异步合成语音，返回音频+字幕+元信息的本地文件路径。

    流程:
    1. POST 创建异步任务 → 获得 task_id + file_id
    2. GET 轮询任务状态（间隔 3s，超时 300s）
    3. status=Success 时下载 3 个文件到 output_dir
    4. 返回 TTSResult
    """
```

#### 3.3.3 请求参数

```json
{
  "model": "speech-2.8-hd",
  "text": "<待合成的脚本文本>",
  "language_boost": "auto",
  "voice_setting": {
    "voice_id": "female-tianmei",
    "speed": 1.0,
    "vol": 1.0,
    "pitch": 0,
    "emotion": null
  },
  "audio_setting": {
    "audio_sample_rate": 32000,
    "bitrate": 128000,
    "format": "mp3",
    "channel": 1
  }
}
```

#### 3.3.4 可用音色参考

| voice_id | 性别 | 风格 |
|----------|------|------|
| female-tianmei | 女 | 甜美温柔（默认） |
| male-qn-qingse | 男 | 青年清爽 |
| audiobook_male_1 | 男 | 有声书叙事 |
| female-shaonv | 女 | 少女活泼 |
| presenter_male | 男 | 演讲主持风格 |

> 完整音色列表需从 MiniMax 开放平台声音管理获取。

#### 3.3.5 语气词支持（speech-2.8-hd 专属）

在文本中插入标签即可触发：
`(laughs)` `(chuckle)` `(coughs)` `(sighs)` `(emm)` `(humming)` 等 22 种。

#### 3.3.6 输出文件

异步任务完成后产出 3 个文件：

| 文件 | 格式 | 内容 |
|------|------|------|
| 音频 | .mp3 | 合成的语音数据 |
| 字幕 | .srt | 句级时间戳字幕（用于视频叠加和动画同步） |
| 元信息 | .json | audio_length, sample_rate, word_count 等统计信息 |

#### 3.3.7 错误处理

| 场景 | 处理策略 |
|------|---------|
| API Key 缺失 | 启动时检查，抛出明确错误 |
| 任务创建失败 | 返回 base_resp 错误信息，抛出异常 |
| 轮询超时（>300s） | 抛出 TimeoutError，建议用户缩短文本 |
| 任务失败 | 返回失败原因，抛出异常 |
| 下载失败 | 重试 3 次，仍失败则抛出异常 |
| 网络问题 | 支持 HTTPS_PROXY 环境变量 |

### 3.4 `src/manim_agent/video_builder.py` — 视频合成器

**职责**：将 Manim 渲染的静音视频 + TTS 音频 + SRT 字幕合成为最终成品

#### 3.4.1 核心接口

```python
async def build_final_video(
    video_path: str,         # Manim 渲染的静音 MP4
    audio_path: str,         # TTS 合成的 MP3
    subtitle_path: str | None,  # SRT 字幕文件（可选）
    output_path: str,        # 输出路径
    subtitle_style: dict | None = None,  # 字幕样式配置
) -> str:
    """
    使用 ffmpeg 合成最终视频。

    步骤:
    1. 检查所有输入文件存在
    2. 计算视频时长与音频时长，处理不一致情况
    3. ffmpeg 合并：视频流 + 音频流 + 字幕轨道
    4. 返回输出文件路径
    """
```

#### 3.4.2 FFmpeg 命令逻辑

```bash
# 基础合成（视频 + 音频）
ffmpeg -i input_video.mp4 -i audio.mp3 \
  -map 0:v -map 1:a \
  -c:v copy -c:a aac -shortest \
  -y output.mp4

# 带字幕（使用 subtitles filter）
ffmpeg -i input_video.mp4 -i audio.mp3 \
  -vf "subtitles=subtitle.srt:force_style='FontSize=24,PrimaryColour=&HFFFFFF'" \
  -map 0:v -map 1:a \
  -c:v libx264 -c:a aac -shortest \
  -y output.mp4
```

#### 3.4.3 时长对齐策略

| 情况 | 处理方式 |
|------|---------|
| 视频长于音频 | `-shortest` 截断视频尾部 |
| 音频长于视频 | 视频末帧静态延长（ffmpeg tpad 或 concat） |
| 时长接近（<5%差异） | 微调视频速度匹配音频 |

#### 3.4.4 字幕样式默认值

```python
DEFAULT_SUBTITLE_STYLE = {
    "FontSize": "20",
    "PrimaryColour": "&H00FFFFFF",   # 白色
    "OutlineColour": "&H00000000",   # 黑边
    "Outline": "2",                  # 描边宽度
    "BorderStyle": "3",              # 底部描边（半透明黑底）
    "MarginV": "20",                 # 底部边距
}
```

---

## 4. 数据流详解

### 4.1 完整端到端流程

```
[用户] 输入: "解释傅里叶变换如何将时域信号转换为频域"
    │
    ▼
[__main__.py] 解析参数，加载 prompts.py
    │
    ▼
[ClaudeSDKClient] 发送系统提示词 + 用户需求
    │
    ├─ [Claude] 分析需求 → 规划场景结构
    │      │
    │      ▼
    │   [Write] 创建 fourier_scene.py
    │      │
    │      ▼
    │   [Bash] manim -qh fourier_scene.py FourierScene
    │      │
    │      ├── 成功 → [Read] 查看 last_frame.png
    │      │      │
    │      │      ▼
    │      │   [Claude 视觉审查] 效果满意？
    │      │      ├── 是 → 继续
    │      │      └── 否 → [Edit] 修改代码 → 重新渲染
    │      │
    │      └── 失败 → [Read] 查看错误日志 → 修复代码 → 重新渲染
    │
    ▼
[Claude 输出结果]
VIDEO_OUTPUT: media/fourier_scene.mp4
SCENE_FILE: fourier_scene.py
SCENE_CLASS: FourierScene
    │
    ▼
[tts_client.py]
POST /v1/t2a_async_v2 → task_id=12345
GET /v1/t2a_async/query?task_id=12345 (轮询...)
status=Success → 下载:
  ├── output/audio.mp3
  ├── output/subtitle.srt
  └── output/extra_info.json
    │
    ▼
[video_builder.py]
ffmpeg 合成:
  media/fourier_scene.mp4 (视频)
+ output/audio.mp3 (音频)
+ output/subtitle.srt (字幕)
→ output/fourier_final.mp4
    │
    ▼
[输出] ✓ 最终视频: output/fourier_final.mp4
```

### 4.2 Claude 工作循环详细说明

Claude 在收到用户需求后，会自主进入一个 **写代码 → 渲染 → 审查 → 修改** 的循环，直到满意为止。这个循环完全由 Claude 自主驱动，不需要外部编排：

```
Turn 1: Claude 写出初始 Manim 代码
Turn 2: Claude 执行 manim 渲染命令
Turn 3: Claude 读取渲染结果（图片/日志）
Turn 4: Claude 发现问题（颜色对比度不够），修改代码
Turn 5: Claude 重新渲染
Turn 6: Claude 审查新结果，满意
Turn 7: Claude 输出最终结果（含 VIDEO_OUTPUT 标记）
```

**关键点**：循环次数和深度由 Claude 自主决定。系统提示词设定质量标准和输出格式约束即可。

**边界情况与应对**：

| 边界情况 | 可能表现 | 应对策略 |
|---------|---------|---------|
| 权限不足 | Bash 被拒绝执行 | `permission_mode=acceptEdits` 已预授权；若仍有问题，Claude 会尝试其他方式 |
| manim 未安装 | Bash 返回 command not found | 系统提示词中注明依赖，启动时预检 |
| 渲染超时 | 长时间无输出 | `max_turns` 上限兜底 + 可调用 `interrupt()` |
| 输出路径不确定 | manim 默认输出到 `media/` | 提示词要求 Claude 报告完整路径；也可从 Bash stdout 解析 |
| 多 Scene 文件 | Claude 可能拆分为多个 .py | 结果提取时取最后一个有效 VIDEO_OUTPUT |
| 内存/OOM | 复杂动画导致渲染崩溃 | Claude 自主降低质量参数（-ql）重试 |

---

## 5. 目录结构

```
manim-agent/
├── pyproject.toml                   # 项目配置 & 依赖
├── src/                             # 源码根目录（src layout）
│   └── manim_agent/                # Python 包
│       ├── __init__.py             # 包初始化 & 版本号
│       ├── __main__.py             # CLI 入口 & 流程编排（python -m manim_agent）
│       ├── prompts.py              # Claude 系统提示词模板
│       ├── tts_client.py           # MiniMax 异步 TTS 客户端
│       └── video_builder.py        # FFmpeg 视频合成
├── README.md                        # 项目说明
├── docs/
│   └── PRD.md                      # 产品需求文档（本文档）
├── output/                          # 输出目录（gitignore）
│   ├── *.mp4                       # 中间产物 & 最终视频
│   ├── *.mp3                       # TTS 音频
│   ├── *.srt                       # 字幕文件
│   └── *.json                      # TTS 元信息
├── scenes/                          # Claude 生成的 Manim 脚本（gitignore）
│   └── *.py
└── media/                           # Manim 渲染输出（gitignore）
    └── ...
```

---

## 6. 关键技术决策记录

### ADR-01: 不使用 Manim MCP Server

**决策**：不将 Manim 操作封装为 MCP 工具

**理由**：
1. Claude Code 已内置 Read/Write/Edit/Bash 工具，完全覆盖文件操作和命令执行
2. 封装 MCP 会增加间接层，限制 Claude 的灵活性（比如它想同时看两个文件、跑自定义 manim 参数）
3. Manim 的核心价值在于代码编写和调试迭代，这恰好是 Claude 最强的能力
4. MCP 应保留给真正需要的能力扩展（如 TTS 外部 API）

**替代方案**：在系统提示词中提供 Manim 使用指南和最佳实践，让 Claude 直接使用内置工具。

### ADR-02: 使用 MiniMax 异步 TTS（非同步）

**决策**：使用 `/v1/t2a_async_v2` 异步接口而非 `/v1/t2a_v2` 同步接口

**理由**：
1. **字幕时间戳是刚需**：视频生成需要精确的字幕时间戳来实现动画-语音同步。实测同步模式的 `subtitle_enable` 未返回有效数据；异步模式明确产出 `.srt` 字幕文件
2. **长文本支持**：异步模式支持最长 50,000 字符（文件上传可达 10 万），同步模式 10,000 字符。教育视频脚本通常较长
3. **结构化输出**：异步模式自动产出 3 个独立文件（音频/字幕/元信息 JSON），便于后续 pipeline 处理
4. **代价可控**：仅需增加轮询逻辑（每 3 秒查一次状态，超时 300 秒），对用户体验无影响

### ADR-03: 使用 query() 函数（非 ClaudeSDKClient）

**决策**：主程序使用 `query()` 函数而非 `ClaudeSDKClient`

**理由**：
1. v1 是 **一次性流程**：发 prompt → 等 Claude 干完 → 拿结果 → TTS → ffmpeg。无中途追问、无需动态切权限
2. `query()` **2 行启动** vs Client ~15 行样板代码（async with / connect / query / receive_response）
3. 两者返回的 **消息流完全相同**（都是 `Message` 联合类型），都能拿到 `ResultMessage`、`AssistantMessage`、`ToolUseBlock`
4. `max_turns` 通过 `ClaudeAgentOptions.max_turns` 设置，两种方式都支持
5. 代码更简洁，降低维护成本

**迁移路径**：如果 v2 需要交互能力（用户预览后追加指令），改为 `ClaudeSDKClient` 只需替换入口代码，消息处理逻辑不变。

### ADR-04: 正确的 MiniMax API 域名和协议

**决策**：使用 `api.minimaxi.com`（非 `api.mmx.io`），音频编码使用 hex（非 base64）

**依据**：实测验证。`.io` 域名 SSL 握手失败；官方文档明确 `.com` 域名为主要接入点，`.bj` 为备用。响应体中 `data.audio` 字段为 hex 编码字符串。

---

## 7. 非功能性需求

### 7.1 性能要求

| 指标 | 目标 |
|------|------|
| 单次 TTS 合成 | < 60 秒（通常 10-30 秒） |
| Manim 渲染（中等复杂度） | < 120 秒（取决于 -q 参数） |
| FFmpeg 合成 | < 10 秒 |
| 端到端总耗时 | 取决于 Claude 迭代次数，通常 5-15 分钟 |

### 7.2 可靠性

**TTS 层面**：
- 轮询超时保护（300 秒）
- 下载失败重试 3 次
- API Key 启动时预检

**FFmpeg 层面**：
- 合成前校验所有输入文件存在且可读
- 时长不一致时的对齐策略（§3.4.3）

**SDK / Claude Code 层面**：
- `max_turns` 上限防止无限循环（默认 50 轮）
- `ResultMessage.is_error` 检测：Claude 遇到不可恢复错误时及时终止并报告
- CLI 未安装/不可用：启动时检测，给出明确安装指引
- API 限流 (`RateLimitEvent`)：捕获后等待重试或提示用户稍后再试
- 会话异常中断：`disconnect()` 清理子进程，避免僵尸进程

**Manim 渲染层面**：
- 渲染失败由 Claude 自主诊断和修复（重写代码 → 重新渲染）
- 渲染超时：通过 `interrupt()` 可手动中断（预留接口）

**通用**：
- 输出目录隔离（`output/`），避免覆盖用户文件
- 临时文件清理机制

### 7.3 安全性

- API Key 通过环境变量传入（`MINIMAX_API_KEY`），不硬编码
- 不记录用户输入内容到日志
- 输出目录隔离，避免覆盖用户文件

### 7.4 兼容性

- Python >= 3.12
- Windows 11 / macOS / Linux
- FFmpeg 需预装并在 PATH 中可用

---

## 8. 后续迭代方向（v2+）

### 8.1 短期（v1.1-v1.2）

- [ ] **批量生成**：一次输入多个主题，并行生成多个视频
- [ ] **预设模板库**：常见教学场景的 Manim 代码模板（函数图像、几何证明、算法可视化）
- [ ] **TTS MCP 工具化**：将 tts_client 注册为 SDK MCP Server，让 Claude 可以自主决定何时调用 TTS
- [ ] **进度条显示**：实时展示 Claude 工作阶段和 TTS 进度

### 8.2 中期（v2.0）

- [ ] **分段合成**：长视频拆分为多个 Scene 分别渲染再拼接
- [ ] **字幕驱动动画**：利用 SRT 时间戳让动画元素与语音逐句同步出现
- [ ] **多语言支持**：TTS 支持英文/日文等多语种配音
- [ ] **Web UI**：基于 Streamlit 或 Gradio 的图形界面

### 8.3 长期（v3.0）

- [ ] **Agent 协作**：多 Agent 分工（编剧 Agent → 动画师 Agent → 配音师 Agent → 审核 Agent）
- [ ] **素材库集成**：自动搜索/生成配图、图标等辅助素材
- [ ] **风格迁移**：参考现有视频的风格，复用到新生成的视频中
