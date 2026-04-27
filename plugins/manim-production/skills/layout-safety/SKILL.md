---
name: layout-safety
description: Audit Manim scene layouts for overlap, crowding, and frame overflow as an implementation-time advisory check. Use when arranging labels, formulas, callouts, braces, tables, or any dense beat where geometry-based layout checks can catch collisions earlier than frame review.
version: 1.0.0
argument-hint: " [layout-checkpoint-or-dense-beat]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep]
---

# Layout Safety

在实现期间对有视觉碰撞风险的 beat 使用此 skill。

## 为什么存在此 skill

- Manim 定位辅助函数如 `next_to()` 和 `arrange()` 使用成对边界对齐。
- 它们不会为你解决全局布局或检查第三方碰撞。
- 密集数学 beat 需要在最终渲染审查之前进行显式的几何检查。

## 主要目标

- 在最终渲染前捕获标签、公式、箭头和标注的重叠。
- 将重要 mobject 保持在安全边距内。
- 将布局问题转化为具体、可测量的修复，而非模糊的"减少拥挤"反馈。

## 审计工作流

1. 在 `construct()` 中识别最密集的 beat 或检查点。
2. 规范辅助实现位于本 skill 的 `scripts/layout_safety.py` 中。
3. 在 `scene.py` 存在后直接用 Python 运行该脚本。
4. 优先使用 `--checkpoint-mode after-play` 以捕获拥挤的过渡状态 beat，而不仅是最终帧。
5. 如果审计标记了问题，检查它并在警告反映真实布局问题时调整间距、缩放或 beat 结构。
6. 仅在布局稳定后移除临时调试脚手架。

## 推荐命令

```bash
# 默认（AABB + 边界点精化）—— 推荐
python scripts/layout_safety.py scene.py GeneratedScene --checkpoint-mode after-play

# 快速模式（仅 AABB）—— 迭代开发阶段可用
python scripts/layout_safety.py scene.py GeneratedScene --no-refine
```

仅在明确需要最终帧时使用 `--checkpoint-mode final`。

## 预期输出

- 退出码 `0`：在采样检查点中未发现布局问题
- 退出码 `1`：发现一个或多个重叠、拥挤或帧溢出问题
- 退出码 `2`：审计脚本无法加载或运行场景

**Issue 类型说明：**

| kind | 含义 | 处理优先级 |
|------|------|------------|
| `overlap-refined` | 经边界点确认的真实重叠 | **必须修复** |
| `overlap` | AABB 重叠（未精化或低置信度） | 建议检查 |
| `overlap-false-positive` | AABB 误报，精化后排除 | 可忽略 |
| `crowding-horizontal/vertical` | 间距小于阈值但未重叠 | 建议增大间距 |
| `frame-overflow` | 对象超出安全帧边距 | 必须调整位置 |

将退出码 `1` 视为审查信号，而非场景不可用的证明。某些数学上有意义的布局会故意将标签、标记或轮廓放在相同的局部边界内。

## 检查内容

- 位于同一焦点对象旁边的文本、MathTex 和标签
- 可能侵入公式的括号、箭头和字幕
- 靠近帧边缘的表格、坐标轴标签和图例
- 旧对象尚未完全离开新对象就已到达的过渡状态

## 检测层级

审计脚本使用**三层检测**，从快到精逐步过滤：

| 层级 | 方法 | 精度 | 性能 | 用途 |
|------|------|------|------|------|
| **L1: AABB 初筛** | 轴对齐包围盒（`get_critical_point`） | 低（矩形近似） | O(n²) 极快 | 所有对象对的快速初筛 |
| **L2: 边界点精化** | `get_boundary_point()` 采样 + 形状感知 | 高（区分圆/方/通用） | 仅对 L1 报疑配对 | 排除圆形/曲线的假阳性 |
| **L3: 帧溢出检测** | `is_off_screen()` + 安全边距 | 精确 | O(n) | 检测对象是否超出安全画面区域 |

### L2 精化策略详解

脚本根据 mobject 的类名自动分类形状类型：

| 形状类型 | 判定依据 | 精化方法 |
|----------|----------|----------|
| `CIRCULAR` | 类名含 Circle/Dot/Ellipse/Arc | 圆心距离 vs 半径之和 |
| `RECTANGULAR` | 类名含 Square/Rect/Text/MathTex/Line | AABB 已够精确，跳过精化 |
| `GENERIC` | 其他所有形状 | 8 方向边界点采样交叉验证 |

### 假阳性处理

AABB 对以下场景会产生误报：

| 场景 | AABB 结果 | 精化后结果 | 原因 |
|------|-----------|------------|------|
| 对角放置的两个圆 | overlap | cleared | 圆弧缩进 AABB 角区 |
| 圆形旁紧贴的标签 | overlap | 取决于实际距离 | 标签矩形侵入圆的 AABB 角 |
| 曲线（Arc）与附近对象 | overlap | 采样确认 | 曲线边界不规则 |

解读精化结果的规则：
- `overlap-refined`（置信度 ≥ 60%）→ **必须处理**的真实重叠
- `overlap`（未精化或低置信度）→ **建议检查**的重叠
- `overlap-false-positive` → 可忽略，但记录在案以备人工复核

### 运行模式

```bash
# 默认：AABB + 边界点精化（推荐）
python scripts/layout_safety.py scene.py GeneratedScene --checkpoint-mode after-play

# 快速模式：仅 AABB（适合迭代开发阶段）
python scripts/layout_safety.py scene.py GeneratedScene --no-refine

# 最终检查：精化模式 + 更严格的最小间距
python scripts/layout_safety.py scene.py GeneratedScene --min-gap 0.2 --refine
```

## 修复策略

- 增大 `next_to()` 或 `arrange()` 中的 `buff`
- 用 `scale_to_fit_width()` 减小对象宽度
- 将一个密集 beat 拆分为两个更清晰的 beat
- 将解释性文本移到不同边缘或角落
- 在引入新对象之前淡出或变换旧的强调对象

## 应避免的做法

- 假设 `next_to()` 能防止所有碰撞
- 仅在拥挤状态发生在 beat 中间时检查最终帧
- 向已经密集的构图添加更多高亮框或括号
- 看到 `overlap-false-positive` 就认为检测无效 —— 它说明 AABB 在该形状组合下不够精确，应信任精化结果
- 使用 `--no-refine` 模式做最终质量检查 —— 精化模式才是完整检测

## Pipeline 自动集成

layout_safety 不仅可在实现期间手动调用，还会在 pipeline 执行流程中**自动运行**：

| 时机 | 触发方式 | 模式 |
|------|----------|------|
| **Phase 2B 完成后** | `pipeline.py` 自动调用 | dry-run + after-play |
| **实现期间手动** | LLM agent 按 SKILL.md 指导执行 | --refine / --no-refine |

### 自动集成的行为

1. **自动执行**：Phase 2B（渲染实现）完成后、Phase 3（渲染审查）前，pipeline 以 subprocess 方式调用 `layout_safety.py`
2. **结果持久化**：审计结果写入 `{output_dir}/debug/layout_audit.json`
3. **结构化输出**：结果写入 `PipelineOutput.layout_audit` 字段，包含：
   - `ran` — 是否成功执行
   - `exit_code` — 0=安全, 1=有问题, 2=错误
   - `checked_count` — 检查的 mobject 数量
   - `issues` — issue 列表（kind, message, subjects）
   - `blocking` — 是否有阻塞性问题（overlap-refined / frame-overflow）
   - `artifact_path` — debug JSON 路径
4. **不阻塞但警示**：blocking issues 不中断 pipeline（布局问题可能是设计意图），但会：
   - 在日志中输出 `[BUILD][WARN]` 前缀警告
   - 写入 structured output 供前端展示
   - Phase 3 render review 可读取 `layout_audit.json` 作为参考

### 降级策略

| 场景 | 行为 |
|------|------|
| scene_file 不存在 | 跳过审计，返回 `ran=False` |
| layout_safety.py 不存在 | 跳过审计，返回 `ran=False` |
| manim 未安装 / 导入失败 | 退出码=2，记录错误但不崩溃 |
| 审计超时（>60s） | 终止子进程，返回超时结果 |
| scene 加载失败 | 退出码=2，记录错误 |
