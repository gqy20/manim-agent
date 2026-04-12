# Manim Agent Roadmap

## Vision

构建一个**稳定、高质量、可扩展**的 AI 驱动数学动画视频自动生成平台——用户输入自然语言，系统端到端产出专业级教学动画视频。

---

## 当前状态概览

| 阶段 | 状态 | 核心目标 |
|------|------|----------|
| Phase 0: 基础闭环 | ✅ Done | CLI → Web 系统，端到端 pipeline 跑通 |
| Phase 1: 质量与稳定性 | 🔄 In Progress | 提升生成质量，降低失败率，规范 agent 行为 |
| Phase 1.5: 视频后处理增强 | 📋 Planned | TTS 完整性修复、Remotion 片头片尾+字幕、BGM 接入 |
| Phase 2: 产品化增强 | 📋 Planned | 多任务、模板库、用户交互优化 |
| Phase 3: 平台化演进 | 🔮 Future | 多 Agent 协作、素材集成、风格迁移 |

---

## Phase 0: 基础闭环 — ✅ Done

**目标：** 从 CLI 工具演变为完整的 Web 系统，打通"自然语言 → Manim 动画 → TTS 配音 → 最终视频"的全链路。

### 已完成里程碑

- [x] M0.1 Claude Agent SDK 集成（query() 子进程通信）
- [x] M0.2 Manim 脚本自动生成与渲染循环
- [x] M0.3 MiniMax 异步 TTS 合成（音频 + SRT 字幕）
- [x] M0.4 FFmpeg 视频/音频/字幕合成
- [x] M0.5 FastAPI 后端 + PostgreSQL 持久化
- [x] M0.6 Next.js 前端 + SSE 实时事件流
- [x] M0.7 Cloudflare R2 可选对象存储
- [x] M0.8 任务级沙箱隔离（task dir + hook 拦截）
- [x] M0.9 结构化输出（PipelineOutput schema）+ 多层兜底
- [x] M0.10 PipelineEvents 统一事件模型
- [x] M0.11 Railway 云部署（Docker + 非 root 运行）
- [x] M0.12 Plugin/Skill 系统框架（manim-production 插件）
- [x] M0.13 渲染审核门控（render review gate）
- [x] M0.14 目标时长控制与质量门控
- [x] M0.15 任务删除 CLI（含 dry-run）
- [x] M0.16 Advisory layout safety skill

### 关键交付物

- 完整的 Web 平台（FastAPI + Next.js + PostgreSQL + SSE）
- 端到端 5 阶段 pipeline（init → scene → render → tts → mux）
- `plugins/manim-production` skill 插件体系（含 scene-plan / scene-build / scene-direction / layout-safety / narration-sync / render-review）
- Railway 云端可部署

---

## Phase 1: 质量与稳定性 — 🔄 In Progress

**目标：** 解决"能跑出来"到"稳定地产出高质量教学动画"的差距。这是当前最关键的阶段。

### 1.1 内容规范资产建设

> 基于 [`generation-quality-review-and-manim-standards.md`](./generation-quality-review-and-manim-standards.md) 的分析结论

- [ ] **M1.1.1** 完善 manim-production skill references 分文件规范
  - `scene-patterns.md` — 场景结构模板（开场/过渡/结尾）
  - `math-visualization-guidelines.md` — 数学可视化规范（颜色语义、公式高亮）
  - `narration-guidelines.md` — 解说文案规范（口语化、句长、同步规则）
  - `code-style.md` — Manim 代码风格指南（减少硬编码坐标）
  - `anti-patterns.md` — 反模式清单（堆字、中英混排等）
- [ ] **M1.1.2** Prompt 改造为 checklist 风格
  - 加入任务分类（concept_explainer / proof_walkthrough / function_visualization / geometry_construction / quick_demo）
  - 每类任务对应默认镜头结构和节奏模板
  - 加入 render 前自检条目（路径、类名、文本密度、narration 可用性）

### 1.2 Agent 流程强化

- [ ] **M1.2.1** 失败后强制自检流程
  - Write/Bash 被拒绝时的路径修正策略
  - 渲染失败时的诊断优先级（路径 > 类名 > manim 命令 > 动画逻辑）
  - structured output 缺失时的补全流程
- [ ] **M1.2.2** 质量 Review Pass 增强
  - correctness：数学表达是否明显错误
  - clarity：单屏信息是否拥挤
  - motion：动画衔接是否自然
  - narration：解说是否口语化且与画面同步
  - maintainability：代码是否过度硬编码
- [ ] **M1.2.3** （远期）双阶段 Agent 拆分
  - planner/generator：负责首版 scene
  - reviewer：按规范打回修改意见
  - **前提：** 规范资产必须先稳定，否则 reviewer 也无标准可依

### 1.3 工程稳定性

- [x] **M1.3.1** Claude SDK 迁移完成（结构化输出修复、状态 phase 对齐）
- [x] **M1.3.2** Plugin 路径解析统一（从 task cwd 解析）
- [x] **M1.3.3** 渲染审核 verdict 缺失告警
- [x] **M1.3.4** Phase 命名统一（前后端已统一为 `init → scene → render → tts → mux → done`）
- [ ] **M1.3.5** 测试覆盖增强
  - prompt 生成后包含任务分类和自检条目
  - narration 中文口语风格约束测试
  - review 规则识别典型反模式测试
  - 场景结构符合教学动画规范测试

### 1.4 可观测性与调试

- [ ] **M1.4.1** 失败任务诊断页
  - 利用已有的日志、trace、源码捕获能力
  - 展示失败原因分类和修复建议
- [ ] **M1.4.2** 源码回显与二次编辑入口
  - 前端展示生成的 Manim 脚本
  - 支持"手工修复后二次渲染"能力

---

## Phase 1.5: 视频后处理增强 — 📋 Planned（优先启动）

**目标：** 解决当前成品视频的三个核心体验问题——TTS 内容截断、缺乏专业片头片尾、无背景音乐。这是从"能出视频"到"出好视频"的关键跃升。

> **为什么单独成 Phase：** 这三项优化都作用于 pipeline 的 **mux 后处理阶段**，技术耦合度高，适合集中攻关。

### 1.5.1 TTS 内容完整性修复

**现状问题：** MiniMax TTS 合成的配音/字幕存在内容不完整现象，可能原因包括：
- 长文本被 API 静默截断（async 模式上限 50,000 字符，sync 模式 10,000 字符）
- narration 与实际动画时长不匹配导致部分内容被丢弃
- SRT 时间戳与音频不同步
- 特殊字符/标点导致合成异常

**现有基础：** `tts_client.py` 已实现 sync/async 双模式（`SYNC_TEXT_LIMIT = 10_000`，超长自动 fallback async），但缺少以下能力：

- [ ] **M1.5.1.1** TTS 输入预处理增强
  - 按句子/语义单元智能分段（当前只按字符数简单切分，无语义感知）
  - 特殊字符清洗与转义（MiniMax speech-2.8-hd 的语气词标签兼容性验证）
  - 接近 API 限制时的主动分段策略（而非依赖 fallback）
- [ ] **M1.5.1.2** TTS 输出完整性校验
  - 合成后对比输入文本与输出字幕文本，检测缺失段落
  - 音频时长与预期 narration 时长的偏差检测（已有 `_narration_is_too_short_for_video()` 告警，但未阻断）
  - SRT 字幕条数与输入句子数的数量级一致性检查
- [ ] **M1.5.1.3** 失败重试与补偿机制
  - 检测到截断时自动对缺失段落二次 TTS
  - 多段 TTS 结果的拼接与 SRT 时间戳重组
  - 最终产物的完整性断言（作为 pipeline gate，不完整则标记 warning 而非 silent pass）
- [ ] **M1.5.1.4** Narration 质量优化
  - narration 生成规则强化（参考 `narration-sync` skill 和 `narration-guidelines.md`）
  - 确保解说文案口语化、与画面节奏同步、不朗读屏幕已有文字

### 1.5.2 Remotion 集成 — 片头 / 片尾 / 字幕渲染

**现状问题：** 当前 FFmpeg 直接烧录 SRT 字幕，样式固定且不够美观；缺少专业的片头（标题、作者信息）和片尾（关注引导、系列推荐）。

**方案：** 引入 [Remotion](https://www.remotion.dev/)（React-based programmatic video）作为视频后处理层。

- [ ] **M1.5.2.1** Remotion 运行环境搭建
  - 项目中新增 `remotion/` 子目录或独立服务
  - 定义 Remotion composition 基础模板（基于 React 组件）
  - CLI / Node.js 服务集成到现有 Python pipeline（子进程调用 `npx remotion render`）
- [ ] **M1.5.2.2** 片头（Intro）模板
  - 动态标题（从任务主题自动生成）
  - 副标题 / 系列标识
  - 品牌水印或 logo
  - 入场动画（淡入 / 缩放 / 打字机效果等）
  - 可配置的视觉风格（配色、字体、动画类型）
- [ ] **M1.5.2.3** 片尾（Outro）模板
  - 结束语 / 总结卡片
  - 关注 / 订阅引导
  - 相关视频推荐位（预留接口）
  - 退出动画
- [ ] **M1.5.2.4** 字幕渲染升级
  - 用 Remotion 替代 FFmpeg subtitles filter 烧录字幕
  - 支持更丰富的字幕样式（渐入渐出、高亮当前句、多行排版）
  - 字幕位置可配置（底部 / 上方 / 居中浮动）
  - 自动换行与安全区避让
  - 支持中英文字体混排优化
- [ ] **M1.5.2.5** Pipeline 集成
  - mux 阶段改造：Manim 视频 → Remotion 合成（+片头 + 字幕 + 片尾）→ 最终 MP4
  - 向 Remotion 传递动态参数（标题、narration、SRT 数据、风格配置）
  - 渲染性能监控与超时控制
  - Remotion 渲染失败的降级策略（回退到纯 FFmpeg 方案）

### 1.5.3 BGM（背景音乐）增强

**现状：** `src/manim_agent/music_client.py` 已实现 MiniMax Music Generation API（music-2.6 模型），且 **已部分接入 pipeline**：
- `__main__.py` 中已有 `--bgm-enabled` / `--bgm-prompt` / `--bgm-volume` CLI 参数
- pipeline 在 TTS 之后、mux 之前自动调用 `generate_instrumental()`
- `video_builder.build_final_video()` 已支持 `bgm_path` + `bgm_volume` 参数
- BGM 生成失败时有 fallback（静默跳过，仅语音合成）

**待优化项：**

- [ ] **M1.5.3.1** BGM prompt 智能化
  - 当前 `_build_default_bgm_prompt()` 较简单，需根据任务类型（教育/证明/可视化）生成更精准的 prompt
  - 支持情绪标签映射（calm / focused / energetic / mysterious）
- [ ] **M1.5.3.2** Ducking（人声压低）效果
  - 当前 BGM 以固定音量混合，缺少"人声说话时自动降低"的 ducking 效果
  - 需要基于 SRT 时间戳生成音量包络，实现动态压低
- [ ] **M1.5.3.3** BGM 时长精确匹配
  - 当前生成的 BGM 固定长度，需裁剪/循环以匹配实际视频时长
  - 避免视频末尾 BGM 突然截断或过长留白
- [ ] **M1.5.3.4** BGM 质量控制增强
  - 生成后预检（时长是否合理、文件是否可播放）
  - 不满意时的重新生成机制（当前只尝试一次）
  - 前端 UI 增加 BGM 开关（`no_bgm` 参数已存在于 CLI，前端尚未暴露）

### 1.5.4 后处理 Pipeline 扩展

> 当前 pipeline 为 **5 阶段**：`init → scene → render → tts → mux`（BGM 已在 tts 与 mux 之间执行）。
>
> 引入 Remotion 后，将扩展为：

```
当前:     init → scene → render → tts → bgm → mux
Remotion: init → scene → render → tts → bgm → remotion(片头+字幕+片尾) → final_mux
```

- [ ] **M1.5.4.1** 新增 `postprocess` 阶段定义
  - 新增 `remotion_client.py` 封装 Remotion CLI 调用（`npx remotion render`）
  - pipeline_events.py 新增 postprocess / remotion 相关事件类型
  - `video_builder.py` 已支持多轨音频混合（bgm_path + bgm_volume），无需大幅改动
- [ ] **M1.5.4.2** SSE / 前端适配
  - 前端进度条增加 postprocess 阶段展示（当前已有 init/scene/render/tts/mux 五段）
  - 各子步骤（BGM 生成 / Remotion 渲染 / 最终合成）独立进度上报
- [ ] **M1.5.4.3** 降级与容错
  - Remotion 不可用时降级为纯 FFmpeg 方案（保留原 SRT 烧录逻辑，`video_builder` 已支持）
  - BGM 生成失败时不阻塞主流程（已实现 fallback：静默跳过 + warning 日志）
  - TTS 不完整时提供部分产物 + 明确提示（当前仅 warning，需升级为 gate）

---

## Phase 2: 产品化增强 — 📋 Planned

**目标：** 从"单次生成工具"升级为"可重复使用的生产力工具"，提升用户体验和工作效率。

### 2.1 批量与模板

- [ ] **M2.1.1** 批量任务生成
  - 一次输入多个主题，并行/队列生成
  - 批量任务状态总览
- [ ] **M2.1.2** 预设模板库
  - 函数图像、几何证明、算法可视化等常见场景模板
  - 用户自定义模板保存与复用
- [ ] **M2.1.3** 任务历史管理与搜索
  - 按主题/时间/状态筛选历史任务
  - 成功任务的产物归档与复用

### 2.2 用户交互增强

- [ ] **M2.2.1** 迭代编辑模式
  - 用户预览后追加指令修改（如"把颜色改一下""加一个步骤"）
  - 增量渲染而非全量重新生成
  - **技术前提：** 从 query() 迁移到 ClaudeSDKClient（支持交互式会话）
- [ ] **M2.2.2** 参数可视化配置
  - 质量/时长/音色/预设的滑块或预设选择器
  - 实时预览参数效果说明
- [ ] **M2.2.3** 移动端体验优化
  - 已有基础（移动端布局改进），需持续完善

### 2.3 分段合成与长视频

- [ ] **M2.3.1** 长视频分段渲染
  - 自动拆分为多个 Scene 分别渲染
  - 段间过渡动画拼接
- [ ] **M2.3.2** 字幕驱动动画
  - 利用 SRT 时间戳实现逐句同步
  - 动画元素出现时机与语音精确对齐

### 2.4 多语言与音色扩展

- [ ] **M2.4.1** TTS 多语言支持
  - 英文/日文等多语种配音
  - 语言自动检测或用户指定
- [ ] **M2.4.2** 音色市场扩展
  - 更多 MiniMax 音色选项
  - 自定义音色（SSML）支持

---

## Phase 3: 平台化演进 — 🔮 Future

**目标：** 从"单人工具"进化为"多角色协作平台"，支持复杂内容生产工作流。

### 3.1 多 Agent 协作

- [ ] **M3.1.1** 角色分工架构
  - 编剧 Agent（需求分析 → 叙事脚本）
  - 动画师 Agent（脚本 → Manim 代码 → 渲染）
  - 配音师 Agent（脚本审核 → TTS 参数调优）
  - 审核 Agent（成品质量评审 → 打回/通过）
- [ ] **M3.1.2** Agent 间编排协议
  - 标准化的中间产物格式
  - Agent 间的反馈循环机制

### 3.2 素材生态

- [ ] **M3.2.1** 素材库集成
  - 自动搜索/生成配图、图标、背景
  - 公式/符号素材库
- [ ] ~~**M3.2.2** BGM 与音效~~ → 已提前至 **Phase 1.5.3**
- [ ] **M3.2.3** 高级音效系统
  - 转场音效、强调音效（与基础 BGM 分离）
  - 音效素材库 + AI 匹配推荐

### 3.3 高级能力

- [ ] **M3.3.1** 风格迁移
  - 参考现有视频风格，复用到新生成视频
  - 用户自定义视觉风格 profile
- [ ] **M3.3.2** 知识图谱联动
  - 自动建立概念间的关联推荐
  - 系列课程自动规划
- [ ] **M3.3.3** 开放 API & SDK
  - 第三方集成能力
  - 插件市场

---

## 技术债务清单

以下是不属于任何特定 Phase 但需要持续关注的事项：

| 编号 | 问题 | 影响 | 状态 | 建议 |
|------|------|------|------|------|
| TD-01 | 文档偏差（README/PRD/代码不一致） | 新人上手困难 | 🔴 Open | 以 `current-technical-architecture.md` 为基线统一 |
| TD-02 | ~~前后端 phase 命名不统一~~ | 维护成本 | ✅ 已解决 | M1.3.4 完成，已统一为 `init → scene → render → tts → mux → done` |
| TD-03 | 默认 preset 名称（default vs educational） | 配置混淆 | 🟡 需确认 | 代码中已用 `default`，需确认文档是否全部同步 |
| TD-04 | 测试覆盖不足（无质量维度测试） | 回归风险 | 🔴 Open | Phase 1.3.5 中补充 |
| TD-05 | Windows 平台兼容性（线程+独立事件循环） | 部署限制 | 🟡 已有 workaround | Railway 部署已验证；本地开发持续观察 |

---

## 决策记录索引

| ADR | 标题 | 状态 |
|-----|------|------|
| ADR-01 | 不使用 Manim MCP Server | ✅ 已落地 |
| ADR-02 | 使用 MiniMax 异步 TTS | ✅ 已落地 |
| ADR-03 | 使用 query() 函数（非 ClaudeSDKClient） | ⚠️ v1 够用，v2 需迁移 |
| ADR-04 | 正确的 MiniMax API 域名和协议 | ✅ 已落地 |

---

## 更新日志

| 日期 | 变更内容 |
|------|----------|
| 2026-04-12 | 审计修正：BGM 已部分接入 pipeline（修正描述为增强而非从零接入）；pipeline 实际为 5 阶段（非 4 阶段）；TD-02 phase 命名已统一标记完成；TTS 已有 sync/async 双模式基础 |
| 2026-04-12 | 新增 Phase 1.5：视频后处理增强（TTS 完整性修复、Remotion 片头片尾+字幕、BGM 增强） |
| 2026-04-12 | 初始版本，基于 PRD、技术架构文档、质量复盘文档整理 |
