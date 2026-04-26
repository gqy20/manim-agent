# Phase 3.5: Narration Generation

## 目标

Phase 3.5 在渲染确认后生成适合 TTS 的自然口播文案。它是一个独立的 no-tools LLM pass，不读写文件、不渲染、不做任何后处理。

## 输入

| 参数 | 来源 | 说明 |
|------|------|------|
| `user_text` | 用户原始输入 | 用于提取话题 hint |
| `target_duration_seconds` | Pipeline 配置 | 目标视频时长，影响口播长度 |
| `plan_text` | Phase 1 规划文本 | 提供整体结构上下文 |
| `po.implemented_beats` | Phase 2B 结构化输出 | 已实现的 beat 列表 |
| `po.beat_to_narration_map` | Phase 2B 结构化输出 | beat → 口播片段映射 |
| `po.build_summary` | Phase 2B 结构化输出 | 构建摘要 |
| `po.duration_seconds` | Phase 3 实测时长 | 真实视频时长 |
| `po.narration` (已有) | Phase 2B 可能已写入 | 复用验证路径 |

## System Prompt

Phase 3.5 使用专用 `NARRATION_SYSTEM_PROMPT`（定义在 `prompts.py`），**不再复用 Phase 2B 的 implementation system prompt**。

该 prompt 明确边界：

- 只做 narration 生成。
- 不写代码、不编辑文件。
- 不渲染、不重新渲染。
- 不探测视频文件。
- 不执行 TTS、mux、上传或任何后处理步骤。

## 工具权限

主路径为 **no-tools LLM pass**（`allowed_tools=[]`）：

- 不读文件。
- 不写文件。
- 不渲染。
- 不探测路径。

## 输出（结构化 Schema）

Phase 3.5 通过 SDK `output_format` 返回 `Phase3_5NarrationOutput`：

```python
class Phase3_5NarrationOutput(BaseModel):
    narration: str           # 完整口播中文文本
    beat_coverage: list[str] # 覆盖的 beat 标题列表（有序）
    char_count: int          # 总字符数
    generation_method: str   # "llm" / "template" / "reused"
```

### 三条生成路径

1. **LLM 主路径**：调用 `query()` 带 `output_format=PhaseSchemaRegistry.output_format_schema("phase3_5_narration")`，从 `ResultMessage.structured_output` 解析并验证为 `Phase3_5NarrationOutput`。
2. **collected_text 兼容路径**：如果 structured output 不可用但 dispatcher 收集到了文本，经 `_looks_like_spoken_narration()` 验证后包装为 `Phase3_5NarrationOutput(generation_method="llm")`。
3. **模板回退路径**：LLM 完全失败时，由 `_build_template_narration()` 从 beat 结构组装口语化中文，返回 `Phase3_5NarrationOutput(generation_method="template")`。
4. **复用路径**：如果 `po.narration` 已存在且通过 `_looks_like_spoken_narration()` 验证，直接包装为 `Phase3_5NarrationOutput(generation_method="reused")`，跳过 LLM 调用。

## 验收规则

### 口播质量检查 (`_looks_like_spoken_narration`)

启发式函数，拒绝以下垃圾输入：

- 长度 < 15 字符
- 包含指令性文字（"请制作"、"请帮我"、"生成一段" 等）
- 仅标题无正文（< 20 字符且无口语标记）
- 通过以下条件之一则接受：
  - ≥ 2 个口语标记词（"我们"、"大家"、"首先"、"接下来" 等）
  - ≥ 1 个口语标记 + 长度 > 25
  - 长度 > 50

### 模板回退保证

模板回退永远不会返回空内容或垃圾：

- 自动添加开场白（"大家好，今天我们来学习{topic}。"）
- 按 beat 数量添加过渡词（"首先"、"接下来"、"最后"）
- 添加结束语（"以上就是今天的内容，谢谢大家的观看。"）
- 即使 beats 为空也有默认占位（`beat_coverage=["默认内容"]`）

## 写回 PipelineOutput

生成成功后：

```python
narration_text = narration_output.narration
if po is not None:
    po.narration = narration_text
```

下游 Phase 4 (TTS) 直接读取 `po.narration` 作为合成源文本。

## 当前风险

- 模板 fallback 语义较粗糙，仅做基本连接词组装。
- 中文字符长度估算只能近似匹配真实 TTS 时长。
- LLM pass 无工具权限，无法读取实际视频帧来校对口播与画面的时间对齐。
