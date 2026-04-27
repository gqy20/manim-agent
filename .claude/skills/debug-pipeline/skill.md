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

> **Windows 中文兼容提示**: 以下 curl 示例仅适用于纯英文内容。如果 title/description 包含中文，**必须使用 Step 4c 中的 Python urllib 模板**（带 UTF-8 wrapper），否则会因 GBK 编码或 JSON 解析失败。

```bash
# 创建 Issue（POST，返回 201）— 仅英文内容时可用 curl
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

# 列出单任务 Issues（GET，无中文 body，curl 安全）
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

#### 1a. 后端健康检查（重要：Windows 编码兼容）

**不要用裸 curl 检查后端！** Windows 下 curl 返回的中文内容可能导致 JSON 解析失败。
使用以下 Python 脚本统一检查：

```python
# health_check.py — 复制到 Bash 中执行
import urllib.request, json, sys, io, socket
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_backend():
    try:
        req = urllib.request.Request('http://127.0.0.1:8471/api/tasks?limit=1', method='GET')
        resp = urllib.request.urlopen(req, timeout=10)
        d = json.loads(resp.read())
        print(f'BACKEND_OK tasks={len(d.get("tasks",[]))}')
        return True
    except urllib.error.HTTPError as e:
        if e.code == 502:
            # 502 可能是后端启动中或根路由未定义，进一步确认
            print('BACKEND_502_MAYBE_STARTING')
            return False
        print(f'BACKEND_ERROR code={e.code} {e.reason[:80]}')
        return False
    except Exception as e:
        print(f'BACKEND_UNREACHABLE {type(e).__name__}: {str(e)[:80]}')
        return False

def check_frontend():
    try:
        req = urllib.request.Request('http://localhost:3147', method='GET')
        resp = urllib.request.urlopen(req, timeout=5)
        print(f'FRONTEND_OK status={resp.status}')
        return True
    except Exception as e:
        print(f'FRONTEND_ERROR {str(e)[:80]}')
        return False

def check_port(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = s.connect_ex(('127.0.0.1', port))
    s.close()
    return result == 0

check_frontend()
if not check_backend():
    if check_port(8471):
        print('PORT_8471_OCCUPIED — 后端进程存在但可能僵死，需手动检查/重启')
    else:
        print('PORT_8471_FREE — 后端未运行')
```

> **关键经验**：
> - 后端根路径 `/` 返回 **502 是正常的**（无定义路由），不代表后端异常
> - 用 `netstat -ano | grep 8471` 或上面 Python 的 `check_port()` 判断端口是否被占用
> - 如果端口被占用但 API 无响应，说明是**僵死进程**，需要用户手动终止后重启
> - Windows 终端默认 GBK 编码，Python 输出中文必须加 `io.TextIOWrapper` 包装

#### 1b. 未运行时启动命令

- 后端：`cd backend && uv run uvicorn main:app --port 8471 --reload`
- 前端：`cd frontend && npm run dev`

#### 1c. 检查 ENABLE_PROMPT_DEBUG

```python
# 在上面的 health_check.py 中追加：
try:
    req = urllib.request.Request(
        'http://127.0.0.1:8471/api/tasks/nonexistent/debug/prompts', method='GET')
    resp = urllib.request.urlopen(req, timeout=5)
except urllib.error.HTTPError as e:
    body = e.read().decode('utf-8','ignore')
    if 'disabled' in body.lower():
        print('PROMPT_DEBUG_DISABLED')
    elif e.code == 404:
        print('PROMPT_DEBUG_ENABLED')  # 404 = 正常（task 不存在），说明 debug 路由已注册
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

**必须使用 Python urllib 创建任务！** curl 在 Windows 下处理中文 user_text 会失败（`error parsing body`）。

```python
# create_task.py — 复制到 Bash 中执行
import urllib.request, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

data = json.dumps({
    'user_text': '<user_text>',           # 中文内容直接写，无需转义
    'voice_id': '<voice_id>',
    'model': 'speech-2.8-hd',
    'quality': '<quality>',
    'preset': '<preset>',
    'no_tts': <no_tts>,
    'bgm_enabled': False,
    'bgm_volume': 0.12,
    'target_duration_seconds': <duration>
}).encode('utf-8')

req = urllib.request.Request(
    'http://127.0.0.1:8471/api/tasks',
    data=data,
    headers={'Content-Type': 'application/json; charset=utf-8'},
    method='POST'
)
resp = urllib.request.urlopen(req, timeout=15)
result = json.loads(resp.read())
print(f'TASK_CREATED id={result["id"]} status={result["status"]}')
print(f'DEBUG_URL=http://localhost:3147/tasks/{result["id"]}/debug')
```

> **关键经验**：
> - **不要用 curl 创建任务** — Windows curl 对中文 JSON body 解析会失败，即使加了 `charset=utf-8`
> - **不要重复提交** — 如果第一次创建失败（如超时），先检查是否已部分创建了任务（查询 `/api/tasks?limit=5`），避免重复任务抢占资源
> - 所有后续 API 调用（轮询、issue 写入等）也建议统一使用 Python urllib + UTF-8 wrapper

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

**主方式: Python 轮询 GET /api/tasks/{task_id}**（每 12-15 秒）

**不要用 curl + python pipe！** Windows 下中文内容会导致 JSON 解析错误。
使用统一的 Python 轮询脚本：

```python
# poll_task.py — 复制到 Bash 中执行
import urllib.request, json, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

TASK_ID = '<task_id>'
PHASE_KEYS = {
    'plan_text': 'P1', 'scene_file': 'P2A', 'scene_class': 'P2A',
    'source_code': 'P2B', 'video_output': 'P3',
    'narration': 'P3.5', 'audio_path': 'P4', 'final_video_output': 'P5',
    'review_approved': 'review', 'tts_duration_ms': 'P4_ms',
    'duration_seconds': 'P5_s', 'error': 'ERR'
}

for i in range(60):  # 最多轮询 60 次（约 12-15 分钟）
    try:
        resp = urllib.request.urlopen(
            f'http://127.0.0.1:8471/api/tasks/{TASK_ID}', timeout=10)
        d = json.loads(resp.read())
    except Exception as e:
        print(f'[{i+1:2d}] POLL_ERROR {e}')
        time.sleep(15)
        continue

    status = d['status']
    po = d.get('pipeline_output') or {}
    info = f'status={status}'
    for k, label in PHASE_KEYS.items():
        v = po.get(k)
        if v:
            if k == 'plan_text': info += f' | P1({len(str(v))}c)'
            elif k == 'source_code': info += f' | P2B({len(str(v))}c)'
            elif k == 'narration': info += f' | P3.5'
            elif k in ('audio_path',): info += f' | P4({po.get("tts_duration_ms","?")}ms)'
            elif k in ('final_video_output',): info += f' | P5({po.get("duration_seconds","?")}s)'
            elif k == 'scene_file': info += f' | scene={v.split("/")[-1] if "/" in str(v) else v}'
            elif k == 'scene_class': info += f' | class={v}'
            elif k == 'review_approved': info += f' | approved={v}'
            elif k == 'error': info += f' | ERR={str(v)[:100]}'
            else: info += f' | {label}={str(v)[:60]}'
    print(f'[{i+1:2d}] {info}')

    if status in ('completed', 'failed', 'stopped'):
        break
    time.sleep(15)
else:
    print('TIMEOUT — 任务仍在运行，建议检查 SSE 或后端日志')
```

**辅助: SSE 事件流**（用于实时追踪 SDK 工具调用进度，特别适合 Phase 2B 长等待期）

```python
# sse_monitor.py — 在另一个终端或后台运行
import urllib.request, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

req = urllib.request.Request(
    'http://127.0.0.1:8471/api/tasks/<task_id>/events',
    method='GET'
)
resp = urllib.request.urlopen(req, timeout=600)
for line in resp:
    line = line.decode('utf-8','ignore').strip()
    if line.startswith('data:'):
        print(line)  # 实时输出 SSE 事件
```

SSE 事件类型: `log` / `status` / `error` / `tool_start` / `tool_result` / `thinking` / `progress`
status phase 序列: `init → planning → scene → script_draft → scene(render) → render → narration → tts → mux -> done`

> **Phase 2B/Phase 3 长时间等待策略**：
> - P2B（SDK 代码生成）通常需要 **5-15 分钟**，期间 pipeline_output 不会更新是正常的
> - 如果 P2B 超过 **10 分钟**无进展：启动 SSE 监控查看是否有 tool_start/tool_result 活动；查看后端日志确认 SDK 进程是否存活
> - 后端日志位置: `backend/logs/manim-agent-<PID>.log`（PID 可通过 `netstat -ano | grep 8471` 获取）

#### 4c. 各阶段核对 + Issue 写入

对每个阶段，按核对清单逐项检查。**每发现一个异常，立即调用以下命令写入 issue**：

```python
# ════════════════════════════════════════════════
# ISSUE 写入模板（每个异常填入具体值）
# ════════════════════════════════════════════════
import urllib.request, json, sys, io
from datetime import datetime, timezone
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

TASK_ID = '<task_id>'
issue = {
    "phase_id": "<当前阶段ID>",
    "title": "<按上面规则表生成标题>",
    "description": "<详细描述: 观察到的实际值 vs 预期值, 可能原因, 影响>",
    "issue_type": "<按规则表选择分类>",
    "severity": "<按规则表选择严重度>",
    "source": "auto-debug",
    "prompt_artifact_path": "<有artifact的阶段填 debug/phaseX.prompt.json>",
    "metadata": {
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "field": "<异常字段名>",
        "actual_value": "<实际观察到的值>",
        "expected": "<预期值",
        "task_status": "<当时任务状态>"
    }
}
data = json.dumps(issue).encode('utf-8')
req = urllib.request.Request(
    f'http://127.0.0.1:8471/api/tasks/{TASK_ID}/debug/issues',
    data=data,
    headers={'Content-Type': 'application/json; charset=utf-8'},
    method='POST'
)
try:
    resp = urllib.request.urlopen(req, timeout=10)
    result = json.loads(resp.read())
    print(f'ISSUE_CREATED id={result.get("id")} title={issue["title"]}')
except urllib.error.HTTPError as e:
    body = e.read().decode('utf-8','ignore')[:200]
    print(f'ISSUE_WRITE_FAILED code={e.code} body={body}')
    # 不抛出异常，继续调试流程
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

```python
# collect_results.py — 复制到 Bash 中执行
import urllib.request, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

TASK_ID = '<task_id>'
BASE = f'http://127.0.0.1:8471/api/tasks/{TASK_ID}'

def get(url):
    return json.loads(urllib.request.urlopen(url, timeout=10).read())

# TaskResponse
d = get(BASE)
print('=== TASK ===')
print(json.dumps(d, ensure_ascii=False, indent=2))

# Prompt Artifacts
try:
    prompts = get(f'{BASE}/debug/prompts')
    print(f'\n=== PROMPTS ({len(prompts.get("phases",[]))} phases) ===')
    for p in prompts.get('phases', []):
        print(f'  {p["phase_id"]}: artifact={p.get("has_artifact",False)} '
              f'size={p.get("size_bytes",0)}')
except Exception as e:
    print(f'\n=== PROMPTS: unavailable ({e}) ===')

# Single-task Issues
try:
    issues_data = get(f'{BASE}/debug/issues')
    issues = issues_data.get('issues', [])
    print(f'\n=== ISSUES (total={issues_data.get("total", len(issues))}) ===')
    for i in issues:
        sev = i.get('severity','?')
        t = i.get('issue_type','?')
        print(f'  [{sev:>8}] [{t:>6}] {i["title"]}  (phase={i.get("phase_id","-")})')
except Exception as e:
    print(f'\n=== ISSUES: unavailable ({e}) ===')

# Global Issues (cross-task view for this task)
try:
    global_issues = get(
        f'http://127.0.0.1:8471/api/tasks/debug/issues?task_id={TASK_ID}&limit=200')
    print(f'\n=== GLOBAL VIEW: {len(global_issues.get("issues",[]))} issues for this task ===')
except Exception as e:
    print(f'\n=== GLOBAL VIEW: unavailable ({e}) ===')

# Local files
import os
debug_dir = f'backend/output/{TASK_ID}/debug'
if os.path.exists(debug_dir):
    print(f'\n=== LOCAL FILES ({debug_dir}) ===')
    for f in sorted(os.listdir(debug_dir)):
        fp = os.path.join(debug_dir, f)
        print(f'  {f} ({os.path.getsize(fp)} bytes)')
else:
    print(f'\n=== LOCAL FILES: {debug_dir} not found ===')
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
| 后端未连接 / 502 | 先检查端口占用（netstat / Python socket），区分「未启动」vs「僵死进程」 | 否 |
| 后端端口被占用但无响应 | 提示用户检查 PID、终止僵死进程后重启 | 否 |
| curl 中文编码错误 | 切换到 Python urllib（所有 API 调用统一用 Python） | 否 |
| 任务创建失败 (400/500) | 显示 API detail；**先查询已有任务确认是否部分创建成功**，避免重复提交 | 否 |
| **阶段异常/失败** | **标注 ✗ + 立即写 issue** | **是** (按规则表) |
| 阶段超时 (>10min 无进展) | 标记 TIMEOUT + 写 issue；启动 SSE 追踪 SDK 活动；查看后端日志 | 是 (type=基础设施 sev=medium) |
| 任务 status=failed | 提取 error + 写全局 issue | 是 (type=基础设施 sev=blocker) |
| Debug Prompts 404 | 切换 Fallback 模式 | 否 (API 不可用) |
| **Issue 写入失败** (404/500) | **打印警告但继续调试** | 跳过该条，不影响流程 |
| SSE 断连 | 回退到轮询 | 是 (type=前端界面 sev=high) |
| Windows GBK 编码错误 | 所有 Python 脚本加 `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')` | 否 |
| 重复任务运行 | 检查 `/api/tasks?limit=5` 确认是否有同 user_text 的并行任务，提示用户停止多余任务 | 否 |

## 注意事项

1. **默认 no_tts=false**: 默认跑完整流程（含 TTS+Mux），如需加速可手动设 no_tts=true 跳过语音合成
2. **默认 quality=medium**: 平衡速度和质量
3. **Issue 写入依赖 ENABLE_PROMPT_DEBUG**: 未启用时进入只读模式，报告中标注 `Issue Write: DISABLED`
4. **Issue 写入失败不阻断调试**: 即使 issue API 报错，仍继续完成后续阶段的核对和报告
5. **Prompt Artifacts 覆盖范围**: 仅 phase1 ~ phase2b 有写入；phase3+ 依赖 pipeline_output
6. **source 字段区分来源**: skill 自动写入的 issue 用 `source="auto-debug"`，用户手动在 Debug 页面创建的用 `source="manual"`
7. **全局 Issues API (`GET /debug/issues`)**: 支持跨任务筛选（status/severity/issue_type/task_id/search），用于发现重复问题模式和系统性风险。前端入口 `/debug/issues`
8. **Issue 标题和描述统一使用中文**: 方便在 Debug 页面的问题池中快速浏览和分类
9. **Windows 编码兼容（重要）**: 所有涉及中文输出的 Python 脚本必须加 UTF-8 stdout wrapper；**不要用 curl 发送包含中文的请求体**，统一使用 Python urllib + `charset=utf-8`
10. **Phase 2B 正常耗时较长**: P2B（SDK 代码生成）通常需要 5-15 分钟，期间 pipeline_output 不更新是正常的。超过 10 分钟无进展时应通过 SSE 或后端日志排查，而非立即判定为失败
11. **避免重复创建任务**: 创建任务前先检查是否有相同 user_text 的 running 任务；curl 失败不代表一定没创建成功，需验证后再重试