# Manim Agent

AI 驱动的数学动画视频自动生成系统。输入自然语言描述，自动生成带有专业配音的 Manim 动画视频。

## 核心特性

- **零代码门槛** — 用自然语言描述想要的内容，无需了解 Manim API
- **视觉反馈循环** — Claude 自主写代码 → 渲染 → 审查 → 迭代优化
- **专业配音** — 集成 MiniMax TTS，支持多音色、字幕时间戳同步
- **端到端自动化** — 从文字到成品视频，全流程无人值守

## 系统要求

- Python >= 3.12
- [Manim](https://www.manim.community/) >= 0.20.1
- [FFmpeg](https://ffmpeg.org/)（需在 PATH 中可用）
- MiniMax API Key（环境变量 `MINIMAX_API_KEY`）

## 安装

```bash
# 克隆项目
git clone <repo-url>
cd manim-agent

# 使用 uv 安装（推荐）
uv sync --group dev
uv pip install -e .

# 或使用 pip
pip install -e ".[dev]"

# 安装系统依赖（如果尚未安装）
# Manim: pip install manim>=0.20.1
# FFmpeg: https://ffmpeg.org/download.html
```

## 快速开始

### 基本用法

```bash
# 设置 API Key
export MINIMAX_API_KEY='your-minimax-api-key'

# 生成视频（含 TTS 配音）
python -m manim_agent "解释傅里叶变换的原理" -o fourier.mp4

# 生成静音视频（跳过 TTS）
python -m manim_agent "讲解二叉树的遍历方式" --no-tts -o tree.mp4

# 使用指定音色和质量
python -m manim_agent "证明勾股定理" \
  --voice presenter_male \
  --quality medium \
  -o proof.mp4
```

### 预设模式

| 模式 | 适用场景 |
|------|----------|
| `educational`（默认） | 教学讲解，循序渐进 |
| `presentation` | 演示汇报，简洁美观 |
| `proof` | 数学证明，逻辑推导 |
| `concept` | 概念可视化，直观比喻 |

## 项目架构

```
src/manim_agent/
├── __init__.py      # 包初始化 & 版本号
├── __main__.py      # CLI 入口 & 流程编排
├── prompts.py       # Claude 系统提示词模板 + 预设模式
├── tts_client.py    # MiniMax 异步 TTS 客户端
└── video_builder.py # FFmpeg 视频合成器
```

### 数据流

```
用户文本 → parse_args() → query(Claude SDK) → extract_result()
    ↓
[可选] synthesize(TTS) → build_final_video(FFmpeg) → final.mp4
```

## CLI 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `text` | 自然语言描述（必填） | — |
| `-o, --output` | 输出视频路径 | `output.mp4` |
| `--voice` | MiniMax 音色 ID | `female-tianmei` |
| `--model` | TTS 模型 | `speech-2.8-hd` |
| `--quality` | 渲染质量 (`high`/`medium`/`low`) | `high` |
| `--no-tts` | 跳过语音合成 | `false` |
| `--cwd` | 工作目录 | 当前目录 |
| `--prompt-file` | 自定义提示词文件 | — |
| `--max-turns` | Claude 最大交互轮次 | `50` |

## 开发指南

### 运行测试

```bash
# 全量测试
uv run pytest tests/ -v

# 带覆盖率报告
uv run pytest tests/ -v --cov=src/manim_agent --cov-report=term-missing

# 单模块测试
uv run pytest tests/test_prompts.py -v
```

### TDD 工作流

项目采用测试驱动开发：

1. 先写测试（`tests/test_*.py`）→ 跑红
2. 写实现（`src/manim_agent/*.py`）→ 跑绿
3. 提交（conventional commits）

### 代码风格

```bash
# 检查
uv run ruff check src/ tests/

# 格式化
uv run ruff format src/ tests/
```

## 可用音色

| voice_id | 风格 |
|----------|------|
| `female-tianmei` | 甜美温柔（默认） |
| `male-qn-qingse` | 青年清爽 |
| `audiobook_male_1` | 有声书叙事 |
| `female-shaonv` | 少女活泼 |
| `presenter_male` | 演讲主持 |

> 完整列表请访问 [MiniMax 开放平台](https://www.minimaxi.com/)。

## License

MIT
