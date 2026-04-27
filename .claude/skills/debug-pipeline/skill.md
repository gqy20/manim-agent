---
name: debug-pipeline
description: >
  Pipeline 调试工具：在已运行的前后端基础上创建任务、执行 pipeline、
  通过 Debug 页面 API 逐阶段核对运行状态，自动将异常写入 Debug Issue Tracker，
  并输出完整调试报告。
  基于项目内置的 Debug 界面体系（/tasks/{id}/debug），
  利用其 Prompt Artifacts + Issue Tracker + pipeline_output 快照。
---

# Pipeline Debug Skill

在已启动的前端 (http://localhost:3147) 和后端 (http://127.0.0.1:8471) 基础上，
通过后端 API 创建任务，利用项目 **Debug 界面体系** 的同一套 API 进行逐阶段调试，
**发现问题时自动写入 Debug Issue Tracker**（PostgreSQL `debug_issues` 表）。

## 项目 Debug 体系概览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Debug Page: http://localhost:3147/tasks/{id}/debug                           │
│  前端: frontend/app/tasks/[id]/debug/task-debug-client.tsx                    │
├──────────────┬──────────────────────────┬────────────────────────────────────┤
│  阶段列表     │  Prompt Artifact         │  Issue Tracker (问题池)             │
│  (左侧栏)     │  详情 (中间栏)           │  (右侧栏)                            │
│              │                          │                                      │
│  phase1       │  [system] [user]        │  自动写入 + 手动创建                 │
│  phase2a      │  [inputs] [options]     │  12种分类 × 4级严重度                │
│  phase2b      │  [output]               │  关联 phase_id + artifact            │
│  phase3       │  ├ readable view        │  metadata JSONB 存上下文             │
│  phase3_5     │  └ json view            │  open → fixed 状态流转               │
│  phase4       │                          │                                      │
│  phase5       │                          │                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  全局问题页: http://localhost:3147/debug/issues                               │
│  前端: frontend/app/debug/issues/page.tsx                                     │
│  功能: 跨任务查看所有 issues，支持按状态/级别/分类/任务ID/关键词筛选           │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Debug Issue Tracker 机制

Issue 存储在 PostgreSQL `debug_issues` 表（[task_store.py:219](backend/task_store.py#L219)），
所有操作要求 `ENABLE_PROMPT_DEBUG=1`（[routes.py:898](backend/routes.py#L898)）。

### 数据模型 (`DebugIssueCreateRequest`, [models.py:85](backend/models.py#L85))

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `phase_id` | string | 否 | 关联的阶段 ID |
| `title` | string | **是** | 问题标题 (≤240字) |
| `description` | string | **是** | 详细描述 |
| `issue_type` | string | 否 | 分类（见下表），默认 `"other"` |
| `severity` | string | 否 | 严重度（见下表），默认 `"medium"` |
| `status` | string | 否 | 状态，默认 `"open"` |
| `source` | string | 否 | 来源，默认 `"manual"`；skill 写入时用 `"auto-debug"` |
| `prompt_artifact_path` | string | 否 | 关联的 artifact 路径 |
| `related_artifact_path` | string | 否 | 关联的其他 artifact |
| `metadata` | dict | 否 | 扩展元数据 |

### 12 种问题分类 (issue_type)

| 值 | 标签 | 适用场景 |
|----|------|---------|
| `提示词` | 提示词 | system_prompt / user_prompt 导致的问题 |
| `结构化输出` | 结构化输出 | JSON schema 输出解析失败、字段缺失 |
| `脚本结构` | 脚本结构 | scene.py 类定义、方法缺失、语法错误 |
| `渲染执行` | 渲染执行 | manim 渲染失败、超时、帧缺失 |
| `视觉质量` | 视觉质量 | 渲染结果视觉异常（需人工确认） |
| `解说文案` | 解说文案 | narration 为空、覆盖不全、质量问题 |
| `语音合成` | 语音合成 | TTS 调用失败、音频截断 |
| `音视频合成` | 音视频合成 | FFmpeg mux 失败、音画不同步 |
| `基础设施` | 基础设施 | SDK 超时、数据库错误、网络问题 |
| `前端界面` | 前端界面 | SSE 断连、UI 显示异常 |
| `产品体验` | 产品体验 | 流程卡顿、用户体验问题 |
| `其他` | 其他 | 无法归类的 |

### 4 级严重度 (severity)

| 值 | 标签 | 含义 |
|----|------|------|
| `low` | 低 | 非阻塞，可后续优化 |
| `medium` | 中 | 影响质量但不阻断流程 |
| `high` | 高 | 明显缺陷，需要修复 |
| `blocker` | 阻塞 | 完全阻断 pipeline |

### 写入 API

```bash
# 创建 Issue（POST，返回 201）
curl -s -X POST http://127.0.0.1:8471/api/tasks/<task_id>/debug/issues \
  -H "Content-Type: application/json" \
  -d '{
    "phase_id": "<phase_id>",
    "title": "<标题>",
    "description": "<详细描述>",
    "issue_type": "<分类>",
    "severity": "<严重度>",
    "source": "auto-debug",
    "prompt_artifact_path": "<artifact路径>",
    "metadata": { ... }
  }'

# 列出单任务 Issues
curl -s http://127.0.0.1:8471/api/tasks/<task_id>/debug/issues

# ═══ 全局 Issues 列表（跨任务）═══
# GET /api/tasks/debug/issues — 支持筛选参数:
#   limit (1-500, 默认100) | status (open/fixed/ignored)
#   severity (low/medium/high/blocker) | issue_type (12种之一)
#   task_id (按任务过滤) | search (搜索 title/description, ILIKE 模糊匹配)
#
# 示例：查看所有 open 的 blocker 级问题
curl -s "http://127.0.0.1:8471/api/tasks/debug/issues?status=open&severity=blocker&limit=50"
#
# 示例：按关键词搜索 TTS 相关问题
curl -s "http://127.0.0.1:8471/api/tasks/debug/issues?search=TTS&limit=100"
#
# 示例：查看某个任务的所有 issues
curl -s "http://127.0.0.1:8471/api/tasks/debug/issues?task_id=<task_id>&limit=200"

# 更新 Issue（如标记为 fixed）
curl -s -X PATCH http://127.0.0.1:8471/api/tasks/debug/issues/<issue_id> \
  -H "Content-Type: application/json" \
  -d '{"status": "fixed"}'

# 删除 Issue
curl -s -X DELETE http://127.0.0.1:8471/api/tasks/debug/issues/<issue_id>
```

**全局 Issues 页面前端入口**: `http://localhost:3147/debug/issues`
- 前端实现: [page.tsx](frontend/app/debug/issues/page.tsx)
- 统计面板: total / open / blocker 计数
- 筛选条件: 关键词搜索 + task_id + 状态 + 严重度 + 分类
- 每条 issue 卡片可跳转到对应任务的 Debug 页面

### Skill 自动写入规则

在 Step 4c 各阶段核对中，**每检测到一个异常就立即调用 `POST /debug/issues` 写入一条记录**。
写入规则如下：

#### Phase 1 异常 → 自动创建 Issue

| 检测到的异常 | issue_type | severity | title 示例 |
|-------------|------------|----------|-----------|
| `plan_text` 为空 | `提示词` | high | Phase 1 场景规划文本为空，未生成规划内容 |
| `beats` 数组为空 | `结构化输出` | blocker | Phase 1 未生成任何动画节拍(beat)，规划失败 |
| beat 缺少 title 或 visual_goal | `结构化输出` | medium | Phase 1 部分节拍信息不完整，缺少标题或视觉目标 |
| `learning_goal` 或 `audience` 为空 | `提示词` | low | Phase 1 学习目标或目标受众未设定 |
| 阶段抛出异常/error | `基础设施` | high | Phase 1 执行过程中抛出异常: {error摘要} |

#### Phase 2A 异常 → 自动创建 Issue

| 检测到的异常 | issue_type | severity | title 示例 |
|-------------|------------|----------|-----------|
| `scene_file` 为 null | `脚本结构` | blocker | Phase 2A 未生成场景文件(scene.py)，代码输出缺失 |
| `scene_class` 为 null | `脚本结构` | high | Phase 2A 场景类名缺失，无法确定渲染入口 |
| `draft_analysis.accepted` == false | `脚本结构` | high | Phase 2A 脚本草稿分析未通过，存在结构性问题: {issues摘要} |
| repair pass 也失败 | `脚本结构` | blocker | Phase 2A 修复尝试后仍未通过，需人工介入 |
| 阶段超时 (>10min) | `基础设施` | high | Phase 2A 执行时间超过10分钟，可能卡死 |

#### Phase 2B 异常 → 自动创建 Issue

| 检测到的异常 | issue_type | severity | title 示例 |
|-------------|------------|----------|-----------|
| `source_code` 为 null | `脚本结构` | blocker | Phase 2B 未生成源代码，实现阶段完全失败 |
| `implemented_beats` 为空 | `脚本结构` | high | Phase 2B 未实现任何节拍，所有beat均缺失 |
| `deviation_from_plan` 非空 | `结构化输出` | medium | Phase 2B 实现结果与规划存在偏差: {偏差列表摘要} |
| `run_cost_usd` 异常高 (> $5.00) | `基础设施` | high | Phase 2B SDK调用费用异常偏高: ${cost} |
| 阶段抛出异常 | `基础设施` | high | Phase 2B 执行过程中抛出异常: {error摘要} |

#### Phase 3 异常 → 自动创建 Issue

| 检测到的异常 | issue_type | severity | title 示例 |
|-------------|------------|----------|-----------|
| `video_output` 为 null | `渲染执行` | blocker | Phase 3 渲染阶段无视频输出，manim渲染可能失败 |
| `review_approved` == false | `渲染执行` | high | Phase 3 渲染审查未通过，存在质量问题: {blocking_issues摘要} |
| `review_blocking_issues` 非空 | `渲染执行` | blocker | Phase 3 存在阻塞级审查问题，必须修复后才能继续: {issues摘要} |
| `review_frame_paths` 为空 | `渲染执行` | medium | Phase 3 未捕获到任何审查帧，无法进行视觉检查 |
| 阶段抛出异常 | `基础设施` | high | Phase 3 渲染或审查过程抛出异常: {error摘要} |

#### Phase 3.5 异常 → 自动创建 Issue

| 检测到的异常 | issue_type | severity | title 示例 |
|-------------|------------|----------|-----------|
| `narration` 为空 | `解说文案` | high | Phase 3.5 解说文案为空，未生成任何旁白内容 |
| `narration_coverage_complete` == false | `解说文案` | medium | Phase 3.5 解说文案未能覆盖所有节拍，存在遗漏 |
| `beat_to_narration_map` 为空 | `解说文案` | medium | Phase 3.5 未建立节拍到解说的映射关系 |

#### Phase 4 异常 → 自动创建 Issue (no_tts=false 时)

| 检测到的异常 | issue_type | severity | title 示例 |
|-------------|------------|----------|-----------|
| `audio_path` 为 null | `语音合成` | blocker | Phase 4 TTS 语音合成无音频输出，TTS调用可能失败 |
| `tts_duration_ms` == 0 | `语音合成` | high | Phase 4 TTS 生成的音频时长为零，合成结果异常 |
| 阶段抛出异常 | `基础设施` | high | Phase 4 TTS 语音合成过程抛出异常: {error摘要} |

#### Phase 5 异常 → 自动创建 Issue (no_tts=false 时)

| 检测到的异常 | issue_type | severity | title 示例 |
|-------------|------------|----------|-----------|
| `final_video_output` 为 null | `音视频合成` | blocker | Phase 5 音视频合成无最终输出，mux失败 |
| `duration_seconds` == 0 | `音视频合成` | high | Phase 5 最终视频时长为零，合成结果可能损坏 |
| 阶段抛出异常 | `基础设施` | high | Phase 5 FFmpeg音视频合成过程抛出异常: {error摘要} |

#### 通用异常

| 检测到的异常 | issue_type | severity | title 示例 |
|-------------|------------|----------|-----------|
| 任务整体 status=failed | `基础设施` | blocker | Pipeline 整体执行失败，任务终止: {error信息} |
| SSE 断连且轮询也失败 | `前端界面` | high | 监控连接中断，SSE与轮询均无法获取状态 |
| 单阶段超时 >10min 无进展 | `基础设施` | medium | {阶段名称} 执行超时超过10分钟，可能卡死或死循环 |

**每次写入时**：
- `source` 固定为 `"auto-debug"`
- `phase_id` 设为当前阶段
- `prompt_artifact_path` 在有 artifact 的阶段设为对应路径（如 `debug/phase1.prompt.json`）
- `metadata` 包含：`{ "detected_at": "ISO时间", "field": "异常字段名", "actual_value": "实际值", "expected": "预期" }`

---

## 使用方式

用户调用 `/debug-pipeline` 或描述"调试 pipeline"、"运行一个测试任务"等意图时触发。

## 执行流程

### Step 1: 环境检查

```bash
# 检查后端
curl -s http://127.0.0.1:8471/api/tasks?limit=1

# 检查前端
curl -s -o /dev/null -w "%{http_code}" http://localhost:3147
```

未运行则提示启动：
- 后端：`cd backend && uv run uvicorn main:app --port 8471 --reload`
- 前端：`cd frontend && npm run dev`

**额外检查**: 是否启用了 ENABLE_PROMPT_DEBUG（影响 issue 写入能力）
```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8471/api/tasks/nonexistent/debug/prompts
# 返回 404(正常，因为 task 不存在) 而非 "Prompt debug is disabled"
# 如果返回 {"detail":"Prompt debug is disabled"} 则说明未启用
```
如果未启用，提示用户：issue 写入功能不可用，但调试仍可继续（仅读模式）。

### Step 2: 收集任务参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `user_text` | (必填) | 任务描述 |
| `quality` | `medium` | high / medium / low |
| `no_tts` | `false` | 是否跳过 TTS（默认不跳过，跑完整流程） |
| `preset` | `educational` | default / educational / presentation / proof / concept |
| `target_duration_seconds` | `60` | 30 / 60 / 180 / 300 |
| `voice_id` | `female-tianmei` | 语音 |
| `model` | `speech-2.8-hd` | TTS 模型 |
| `bgm_enabled` | `false` | BGM |

无 user_text 时使用预设：
1. **勾股定理**(推荐): `"用动画演示勾股定理：画直角三角形，以三边为边长画正方形，通过面积关系证明 a²+b²=c²"`
2. **二分查找**: `"用动画演示二分查找算法在有序数组 [2,5,8,12,16,23,38,56,72,91] 中查找目标值 23 的过程"`
3. **光的折射**: `"用动画演示光从空气射入水中的折射现象"`

### Step 3: 创建任务

调用 `POST /api/tasks` ([routes.py:409](backend/routes.py#L409))：

```bash
curl -s -X POST http://127.0.0.1:8471/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "user_text": "<user_text>",
    "voice_id": "<voice_id>",
    "model": "speech-2.8-hd",
    "quality": "<quality>",
    "preset": "<preset>",
    "no_tts": <no_tts>,
    "bgm_enabled": false,
    "bgm_volume": 0.12,
    "target_duration_seconds": <duration>
  }'
```

记录返回的 `task_id`。输出链接：
```
Debug 页面: http://localhost:3147/tasks/<task_id>/debug
正常页面: http://localhost:3147/tasks/<task_id>
```

### Step 4: 阶段监控与核对 + Issue 自动写入

#### 4a. 确定数据源模式

```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8471/api/tasks/<task_id>/debug/prompts
```
- **200**: 完整模式（有 prompt artifacts + 可写 issues）
- **404**: Fallback 模式（仅 pipeline_output，issues API 也不可用）

#### 4b. 监控方式

**主方式: 轮询 GET /api/tasks/{task_id}**（每 10-15 秒）

```bash
curl -s http://127.0.0.1:8471/api/tasks/<task_id> | python -c "
import sys, json
d = json.load(sys.stdin)
print(f'status={d[\"status\"]}')
po = d.get('pipeline_output') or {}
for k in ['plan_text','scene_file','video_output','final_video_output','source_code',
           'narration','audio_path','error','review_summary']:
    v = po.get(k)
    if v: print(f'  {k} = {str(v)[:120]}')
"
```

**辅助: SSE 事件流**（[routes.py:929](backend/routes.py#L929)）

```bash
timeout 600 curl -s -N http://127.0.0.1:8471/api/tasks/<task_id>/events 2>/dev/null
```

SSE 事件类型: `log` / `status` / `error` / `tool_start` / `tool_result` / `thinking` / `progress`
status phase 序列: `init → planning → scene → script_draft → scene(render) → render → narration → tts → mux → done`

#### 4c. 各阶段核对 + Issue 写入

对每个阶段，按核对清单逐项检查。**每发现一个异常，立即调用以下命令写入 issue**：

```bash
# ════════════════════════════════════════════════
# ISSUE 写入模板（每个异常填入具体值）
# ════════════════════════════════════════════════
curl -s -X POST http://127.0.0.1:8471/api/tasks/<task_id>/debug/issues \
  -H "Content-Type: application/json" \
  -d '{
    "phase_id": "<当前阶段ID>",
    "title": "<按上面规则表生成标题>",
    "description": "<详细描述: 观察到的实际值 vs 预期值, 可能原因, 影响>",
    "issue_type": "<按规则表选择分类>",
    "severity": "<按规则表选择严重度>",
    "source": "auto-debug",
    "prompt_artifact_path": "<有artifact的阶段填 debug/phaseX.prompt.json>",
    "metadata": {
      "detected_at": "<ISO时间戳>",
      "field": "<异常字段名>",
      "actual_value": "<实际观察到的值>",
      "expected": "<预期值",
      "task_status": "<当时任务状态>"
    }
  }'
```

##### Phase 1 — Scene Planning (`phase1`)
**有 Prompt Artifact**: ✅ | **可读视图**: `Phase1Readable`

| 核对项 | 字段 | 预期 | 异常时 issue 配置 |
|--------|------|------|-------------------|
| 规划文本 | `plan_text` | 非空 | type=`提示词` sev=high |
| 模式 | `mode` | 有值 | type=`结构化输出` sev=medium |
| Beat 数量 | `beats[].len` | > 0 | type=`结构化输出` sev=blocker |
| 学习目标 | `learning_goal` | 有值 | type=`提示词` sev=low |
| 受众 | `audience` | 有值 | type=`提示词` sev=low |
| 完整规划 | `phase1_planning` | 存在 | type=`结构化输出` sev=high |

##### Phase 2A — Script Draft (`phase2a`)
**有 Prompt Artifact**: ✅ | **可读视图**: `Phase2Readable`

| 核对项 | 字段 | 预期 | 异常时 issue 配置 |
|--------|------|------|-------------------|
| 场景文件名 | `scene_file` | 非 null | type=`脚本结构` sev=blocker |
| 场景类名 | `scene_class` | 非 null | type=`脚本结构` sev=high |
| 分析通过 | `artifact.draft_analysis.accepted` | true | type=`脚本结构` sev=high |
| 分析问题列表 | `artifact.draft_analysis.issues` | 空 | type=`脚本结构` sev=medium |
| Repair 结果 | `phase2a-repair` artifact | accepted=true | type=`脚本结构` sev=blocker |

##### Phase 2B — Render Implementation (`phase2b`)
**有 Prompt Artifact**: ✅ | **可读视图**: `Phase2Readable`

| 核对项 | 字段 | 预期 | 异常时 issue 配置 |
|--------|------|------|-------------------|
| 源代码 | `source_code` | 非 null | type=`脚本结构` sev=blocker |
| 已实现 beats | `implemented_beats` | 非空 | type=`脚本结构` sev=high |
| 偏差记录 | `deviation_from_plan` | 空 | type=`结构化输出` sev=medium |
| SDK 轮次 | `run_turns` | > 0 | type=`基础设施` sev=high |
| 费用 USD | `run_cost_usd` | 有值 | type=`基础设施` sev=medium(>$2)/high(>$5) |

##### Phase 3 — Render+Review (`phase3`)
**无 Prompt Artifact** ❌ | **可读视图**: `Phase3Readable`(Fallback)

| 核对项 | 字段 | 预期 | 异常时 issue 配置 |
|--------|------|------|-------------------|
| 渲染产物 | `video_output` | 非 null | type=`渲染执行` sev=blocker |
| 审查通过 | `review_approved` | true | type=`渲染执行` sev=high |
| 阻塞问题 | `review_blocking_issues` | 空 | type=`渲染执行` sev=blocker |
| 建议修改 | `review_suggested_edits` | (可为空) | type=`视觉质量` sev=low |
| 审查帧 | `review_frame_paths` | 非空 | type=`渲染执行` sev=medium |

##### Phase 3.5 — Narration (`phase3_5`)
**无 Prompt Artifact** ❌ | **可读视图**: `NarrationReadable`(Fallback)

| 核对项 | 字段 | 预期 | 异常时 issue 配置 |
|--------|------|------|-------------------|
| 解说文案 | `narration` | 非 null | type=`解说文案` sev=high |
| 覆盖完成 | `narration_coverage_complete` | true | type=`解说文案` sev=medium |
| 映射列表 | `beat_to_narration_map` | 非空 | type=`解说文案` sev=medium |

##### Phase 4 — TTS+Mux (`phase4`) (no_tts=false)
**无 Prompt Artifact** ❌ | **可读视图**: `AudioReadable`(Fallback)

| 核对项 | 字段 | 预期 | 异常时 issue 配置 |
|--------|------|------|-------------------|
| 音频路径 | `audio_path` | 非 null | type=`语音合成` sev=blocker |
| 音频时长 | `tts_duration_ms` | > 0 | type=`语音合成` sev=high |
| 字数 | `tts_word_count` | > 0 | type=`语音合成` sev=medium |

(仅当 no_tts=true 时跳过此阶段，不写 issue)

##### Phase 5 — Mux (`phase5`) (完整流程，含 TTS)
**无 Prompt Artifact** ❌ | **可读视图**: `MuxReadable`(Fallback)

| 核对项 | 字段 | 预期 | 异常时 issue 配置 |
|--------|------|------|-------------------|
| 最终视频 | `final_video_output` | 非 null | type=`音视频合成` sev=blocker |
| 总时长 | `duration_seconds` | > 0 | type=`音视频合成` sev=high |

(仅当 no_tts=true 时跳过此阶段，正常流程均会执行)

### Step 5: 收集 Debug 产物 + 汇总 Issues

```bash
# ═══ TaskResponse ═══
curl -s http://127.0.0.1:8471/api/tasks/<task_id> | python -m json.tool

# ═══ Prompt Debug Index（如启用）═══
curl -s http://127.0.0.1:8471/api/tasks/<task_id>/debug/prompts | python -m json.tool

# ═══ 各阶段 Artifact（如启用）═══
curl -s http://127.0.0.1:8471/api/tasks/<task_id>/debug/prompts/phase1 | python -m json.tool
curl -s http://127.0.0.1:8471/api/tasks/<task_id>/debug/prompts/phase2a | python -m json.tool
curl -s http://127.0.0.1:8471/api/tasks/<task_id>/debug/prompts/phase2b | python -m json.tool

# ═══ 单任务 ISSUES（本次调试自动创建的 + 可能已有的）═══
curl -s http://127.0.0.1:8471/api/tasks/<task_id>/debug/issues | python -c "
import sys, json
data = json.load(sys.stdin)
issues = data.get('issues', [])
print(f'Total issues: {data.get(\"total\", len(issues))}')
for i in issues:
    sev = i.get('severity','?')
    t = i.get('issue_type','?')
    print(f'  [{sev:>8}] [{t:>6}] {i[\"title\"]}  (phase={i.get(\"phase_id\",\"-\")})')
"

# ═══ 全局 ISSUES（跨任务视角，用于发现重复问题模式）═══
# 查看当前任务在全局中的位置
curl -s "http://127.0.0.1:8471/api/tasks/debug/issues?task_id=<task_id>&limit=200" | python -c "
import sys, json
data = json.load(sys.stdin)
issues = data.get('issues', [])
print(f'Global view for this task: {len(issues)} issues')
"

# 查看所有 open 的 blocker/high 问题（跨任务）
curl -s "http://127.0.0.1:8471/api/tasks/debug/issues?status=open&severity=blocker&limit=50" | python -c "
import sys, json
data = json.load(sys.stdin)
issues = data.get('issues', [])
print(f'Open blockers across all tasks: {len(issues)}')
for i in issues[:10]:
    print(f'  [{i[\"severity\"]}] {i[\"title\"]} (task={i[\"task_id\"]}, phase={i.get(\"phase_id\",\"-\")})')
if len(issues) > 10: print(f'  ... and {len(issues)-10} more')
"

# 按关键词搜索同类问题（例如搜索 TTS 相关）
curl -s "http://127.0.0.1:8471/api/tasks/debug/issues?search=TTS&limit=100" | python -c "
import sys, json
data = json.load(sys.stdin)
issues = data.get('issues', [])
print(f'Issues matching \"TTS\": {len(issues)}')
for i in issues[:10]:
    print(f'  [{i[\"severity\"]}] {i[\"title\"]} (task={i[\"task_id\"]})')
"

# ═══ 本地文件 ═══
ls -la backend/output/<task_id>/debug/
```

### Step 6: 生成调试报告

```
╔════════════════════════════════════════════════════════════════╗
║                PIPELINE DEBUG REPORT                           ║
║  Task ID:    <task_id>                                         ║
║  User Text:  <前50字>                                           ║
║  Status:     <completed|failed|stopped>                         ║
║  No TTS:     <true|false>                                       ║
║  Quality:    <quality>                                          ║
║  Data Source: <FULL_PROMPT_DEBUG | FALLBACK_PIPELINE_OUTPUT>     ║
║  Issue Write: <ENABLED | DISABLED(prompt_debug off) | READONLY>  ║
║  Total Time: <created_at → completed_at>                        ║
╠════════════════════════════════════════════════════════════════╣
║  PHASE            STATUS    DURATION   KEY OUTPUT    ISSUES      ║
╠════════════════════════════════════════════════════════════════╣
║  P1 Planning      ✓/✗      00:00:00   N beats       0/N created ║
║  P2A ScriptDraft  ✓/✗      00:00:00   scene=X      0/N created ║
║  P2A-Repair       —/✓/✗    00:00:00   (if trigger)  0/N created ║
║  P2B Impl         ✓/✗      00:00:00   N impl,$X    0/N created ║
║  P3 Review        ✓/✗      00:00:00   approved=Y    0/N created ║
║  P3.5 Narration   ✓/✗      00:00:00   coverage=N%   0/N created ║
║  P4 TTS+Mux       ✓/✗/—    00:00:00   audio=Xms    0/N created ║
║  P5 Mux           ✓/✗/—    00:00:00   final=Xs     0/N created ║
╠════════════════════════════════════════════════════════════════╣
║  ISSUES CREATED THIS SESSION                                 ║
║    Total: <N>  (open: <N> / by severity: high:<N> blocker:<N>)  ║
║    List:                                                      ║
║      [blocker] <issue title> (phaseX)                         ║
║      [high]    <issue title> (phaseX)                         ║
║      ...                                                        ║
╠════════════════════════════════════════════════════════════════╣
║  FINAL OUTPUT                                                ║
║    Video:  <path or null>                                      ║
║    Duration: <seconds>                                          ║
║    Cost:    $<usd> / ¥<cny>                                    ║
║    Error:   <message or null>                                   ║
╠════════════════════════════════════════════════════════════════╣
║  DEBUG LINKS                                                 ║
║    Page:   http://localhost:3147/tasks/<task_id>               ║
║    Debug:  http://localhost:3147/tasks/<task_id>/debug         ║
║    Issues (单任务): Debug 页面右侧「问题池」面板                   ║
║    Issues (全局):  http://localhost:3147/debug/issues           ║
╚════════════════════════════════════════════════════════════════╝
```

图例: ✓=通过 ✗=失败 —=跳过

## 错误处理

| 场景 | 处理方式 | 是否写 issue |
|------|---------|-------------|
| 后端未连接 | 提示启动命令 | 否 |
| 任务创建失败 | 显示 API detail | 否 |
| **阶段异常/失败** | **标注 ✗ + 立即写 issue** | **是** (按规则表) |
| 阶段超时 (>10min) | 标记 TIMEOUT，继续监控 | 是 (type=基础设施 sev=medium) |
| 任务 status=failed | 提取 error + 写全局 issue | 是 (type=基础设施 sev=blocker) |
| Debug Prompts 404 | 切换 Fallback 模式 | 否 (API 不可用) |
| **Issue 写入失败** (404/500) | **打印警告但继续调试** | 跳过该条，不影响流程 |
| SSE 断连 | 回退到轮询 | 是 (type=前端界面 sev=high) |

## 注意事项

1. **默认 no_tts=false**: 默认跑完整流程（含 TTS+Mux），如需加速可手动设 no_tts=true 跳过语音合成
2. **默认 quality=medium**: 平衡速度和质量
3. **Issue 写入依赖 ENABLE_PROMPT_DEBUG**: 未启用时进入只读模式，报告中标注 `Issue Write: DISABLED`
4. **Issue 写入失败不阻断调试**: 即使 issue API 报错，仍继续完成后续阶段的核对和报告
5. **Prompt Artifacts 覆盖范围**: 仅 phase1 ~ phase2b 有写入；phase3+ 依赖 pipeline_output
6. **source 字段区分来源**: skill 自动写入的 issue 用 `source="auto-debug"`，用户手动在 Debug 页面创建的用 `source="manual"`
7. **全局 Issues API (`GET /debug/issues`)**: 支持跨任务筛选（status/severity/issue_type/task_id/search），用于发现重复问题模式和系统性风险。前端入口 `/debug/issues`
8. **Issue 标题和描述统一使用中文**: 方便在 Debug 页面的问题池中快速浏览和分类