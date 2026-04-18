# AGENTS.md

## 项目概览

`manim-agent` 是一个以 Claude Agent SDK 为核心执行引擎的 Manim 动画视频生成平台，包含：
- **前端**: Next.js (port 3147)，负责任务创建与实时进度展示
- **后端**: FastAPI (port 8471)，负责任务编排、SSE 事件流、PostgreSQL 持久化
- **Agent 层**: `src/manim_agent/`，核心执行引擎，运行 Claude Agent SDK
- **存储**: PostgreSQL (Neon) + 可选 Cloudflare R2

## 关键架构约束

- **任务沙箱**: 每个任务在 `backend/output/{task_id}/` 下运行，Agent 只能读写任务目录（通过 `hooks.py` 拦截）
- **Pipeline 分阶段**: `init → scene → render → tts → mux → done`（共 6 个 phase）
- **结构化输出优先，降级兜底**: Agent SDK 配置 `output_format=PipelineOutput`，另有文件系统扫描等降级路径
- **Windows/Python 3.13 兼容**: Pipeline 在独立线程 + 独立 asyncio loop 中执行（防止 ProactorEventLoop 子进程兼容问题）；测试模式通过 `MANIM_AGENT_TEST_MODE=1` 切换为 inline 执行

## 开发命令

```bash
# 安装依赖（Python + Node）
make install

# 全量测试
make test

# Python linter + formatter check
make lint

# 单独运行 backend 测试
uv run pytest backend/tests/ -v

# 单独运行 manim_agent 测试
uv run pytest tests/ -v

# 单文件测试
uv run pytest tests/test_prompts.py -v

# 启动后端（reload 默认关闭，稳定优先）
make dev-backend

# 启动后端（reload 开启，仅用于短时 config 检查）
make dev-backend-reload

# 启动前端
make dev-frontend

# 同时启动前后端
make dev

# 清理构建产物
make clean
```

## 前端 / 后端运行端口

- 后端 FastAPI: `127.0.0.1:8471`
- 前端 Next.js: `localhost:3147`（可临时切换: `make dev-frontend FE_PORT=3148`）

## 环境变量

关键环境变量（详见 `.env` 或 `backend/main.py`）:
- `MANIM_AGENT_TEST_MODE=1` — 测试模式，Pipeline inline 执行
- `MINIMAX_API_KEY` — TTS API Key
- `DATABASE_URL` — PostgreSQL 连接字符串
- `R2_*` — Cloudflare R2 配置（可选）
- `KEEP_LOCAL_MP4_TASKS=20` — R2 模式下本地保留的 final.mp4 数量
- `NEXTJS_HOST` / `NEXT_PORT` — 前端代理地址

## CLI 入口（独立使用）

```bash
# 完整配音视频
python -m manim_agent "解释傅里叶变换的原理" -o fourier.mp4

# 静音视频
python -m manim_agent "讲解二叉树的遍历方式" --no-tts -o tree.mp4

# 带 BGM
python -m manim_agent "证明勾股定理" --bgm-enabled -o proof.mp4

# 指定音色和质量
python -m manim_agent "讲解微分方程" --voice presenter_male --quality medium -o de.mp4
```

## 目录结构

```
src/manim_agent/          # Agent 执行层（核心库）
  __main__.py             # CLI 入口
  pipeline.py             # Pipeline 主编排器（5-phase）
  dispatcher.py           # SDK 消息 → 结构化事件转换器
  hooks.py                # 工具拦截（防止越界写文件/命令）
  output_schema.py        # PipelineOutput 结构定义
  pipeline_events.py      # SSE 事件类型定义
  tts_client.py           # MiniMax TTS 调用
  video_builder.py        # FFmpeg 合成
  music_client.py         # 背景音乐客户端

backend/                  # FastAPI Web 服务
  main.py                 # 应用入口
  routes.py               # API 路由 + Pipeline 线程编排
  pipeline_runner.py      # 共享 pipeline 执行体
  task_store.py           # PostgreSQL 任务存储
  sse_manager.py          # SSE 订阅 + 缓冲 + replay
  storage/r2_client.py    # R2 上传客户端

frontend/                 # Next.js 前端
  (Next.js 16 + React 19, Tailwind CSS 4, shadcn)

plugins/manim-production/ # Agent 运行时注入的 skill 插件
```

## 测试注意事项

- Backend tests 依赖 PostgreSQL（`DATABASE_URL` 环境变量）
- 部分测试依赖外部服务（Manim、FFmpeg、MiniMax TTS）
- 测试模式 (`MANIM_AGENT_TEST_MODE=1`) 仅影响 Pipeline 执行方式，不影响其他逻辑

## 代码风格

- Python: `ruff check src/ backend/ tests/`
- Python formatter: `ruff format src/ backend/ tests/`
- 目标 Python 版本: 3.12+
- `ruff` 规则: E, F, I, N, W, UP；行长 100

## 重要参考文档

- `docs/current-technical-architecture.md` — 当前系统架构（含与旧文档的差异说明）
- `docs/claude-sdk-migration-plan.md` — SDK 迁移计划
- `frontend/AGENTS.md` — Next.js 特定规则（注意 Next.js 版本有 breaking changes）
