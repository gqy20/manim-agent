# 生成质量复盘与 Manim 规范落地建议

本文基于当前仓库里的真实提示词、测试、日志和历史生成脚本抽样整理，目标不是讨论理想方案，而是回答三个实际问题：

1. 当前生成内容的质量问题主要出在哪一层
2. 提示词和智能体流程还可以怎样继续优化
3. Manim 规范更适合放进 `skill`、知识库，还是两者组合

## 1. 当前状态判断

从工程能力看，项目已经明显强于普通 “让 LLM 写一段 manim 代码” 的原型：

- 有独立 task dir 和 hook 限制，能约束 agent 不乱写仓库
- 有 `PipelineOutput` 结构化输出，避免完全依赖自由文本
- 有源码回传、日志回放、SSE、TTS 和 mux 后处理
- 有多层 render output 兜底路径

但从“内容质量”看，当前系统仍然偏向“能跑出来”而不是“稳定地产出高质量教学动画”。

也就是说，系统对工程可靠性投入很多，对动画设计规范、数学表达规范、叙事节奏规范的投入还不够。

## 2. 抽样发现的问题

### 2.1 Prompt 目前更像执行约束，不像质量规范

`src/manim_agent/prompts.py` 和 `src/manim_agent/__main__.py` 里最明确的约束主要集中在：

- 工作目录必须在 task dir
- 默认写 `scene.py`
- 默认类名 `GeneratedScene`
- 直接运行 `manim -qh scene.py GeneratedScene`
- narration 默认中文

这些规则能提升成功率，但只解决“怎么执行”，没有充分解决“怎么做得更好”。

当前 prompt 里的 Manim 规范仍然偏泛，例如：

- 合理使用 `Wait()`
- 字体大小适中
- 复杂动画分步骤展示

这些指令太宽，模型很难稳定收敛到一致的产出风格。

### 2.2 历史脚本说明质量波动很大

抽样看到的历史产物呈现两个极端：

- 简单样例如 `fade_circle.py` 很干净，但几乎没有教学价值
- 复杂样例如 `pythagorean_theorem.py`、`quadratic_function.py` 虽然信息量高，但已经出现明显的内容层问题

典型问题包括：

- 文案混中英，语言风格不统一
- 屏幕文本过多，容易堆字
- 公式展示、图形展示、讲解节奏没有统一模板
- 复杂场景里局部实现是“手工堆坐标”，可维护性差
- 没有显式区分 “演示型动画” 和 “讲解型动画”
- 没有约束每个 scene 的镜头节奏、停顿长度、单屏信息密度

### 2.3 失败日志说明 agent 仍然频繁违背环境规则

日志里反复出现：

- 试图写入 `D:\root\...`
- 试图写入仓库根目录或用户目录
- 试图从 repo root 执行命令
- 渲染成功但没有稳定返回有效 `structured_output`

这说明两件事：

- 当前 prompt 对执行约束虽然写了，但还没有强到足以改变模型默认习惯
- agent 还缺少“失败后自检并修正路径策略”的显式流程

### 2.4 测试对“质量”的约束还不够

现有测试主要覆盖：

- prompt 字符串是否包含关键片段
- structured output 是否可解析
- narration 是否优先使用 structured output
- source code 是否被 hook 捕获

这类测试能守住框架稳定性，但几乎没有守住“内容质量”：

- 没有测试 narration 风格
- 没有测试 scene 结构是否符合教学动画规范
- 没有测试代码是否优先使用 Manim 常见构造模式
- 没有测试单屏文本密度、颜色一致性、对象命名、动画时长分布

## 3. 内容质量问题应分三层解决

当前最容易混淆的一点，是把所有问题都归咎于 system prompt。实际上这里应该拆成三层：

### 3.1 第一层：执行型规则

目标是提升成功率，避免 agent 跑偏。

适合放入：

- system prompt
- `_build_user_prompt()` 的执行补充
- hooks 的报错文案

内容包括：

- 文件必须写在 task dir
- 只能用相对路径
- 渲染失败时优先检查路径、类名、输出文件
- 如果 hook 拒绝了路径，必须立即改用 `scene.py`

这一层当前已经有，但还可以更显式、更像 checklist。

### 3.2 第二层：内容型规范

目标是提高动画质量和教学可读性。

适合放入：

- 独立的 Manim 规范文档
- 可被 agent 主动加载的 skill/reference

内容包括：

- 教学动画的镜头结构
- 颜色层级和语义映射
- 文本数量和字数上限
- 常见数学对象的推荐展示方式
- 常见反模式

这一层不适合全部塞进 system prompt，因为会太长，而且不同任务只需要其中一部分。

### 3.3 第三层：评审与回路

目标是让 agent 不是“一次生成就交付”，而是“生成后自检”。

适合放入：

- pipeline 中新增一个 review pass
- 或在同一 agent 内增加 “render 前自检 / render 后复盘” 明确步骤

内容包括：

- narration 是否口语化、是否和镜头同步
- 画面是否单屏过载
- 是否出现大段 Text 堆叠
- 是否存在不必要的手工坐标硬编码
- 是否存在颜色或字体风格漂移

如果不引入这一层，仅靠 prompt 很难稳定提高结果。

## 4. Prompt 应该怎样优化

建议把当前 prompt 从“宽泛要求”改成“分阶段检查单”。

### 4.1 加入固定的产出结构

让 agent 在脑中先遵循这样的规划：

1. 先判断任务属于哪一类
2. 再选择对应的 scene 模板
3. 再生成代码
4. 再做渲染前检查
5. 再渲染
6. 再填写 structured output

任务类型建议至少分成：

- `concept_explainer`
- `proof_walkthrough`
- `function_visualization`
- `geometry_construction`
- `quick_demo`

不同类型对应不同的默认节奏和布局。

### 4.2 把“好动画”的要求写成可执行约束

不要只写“分步骤展示”，而要写成更具体的硬规则，例如：

- 单个镜头同时出现的新概念不超过 1 到 2 个
- 单屏文字最多 2 到 3 行，每行尽量短
- 关键公式一次只强调一处变化
- 新对象进入时先建立空间关系，再做变换
- 复杂推导要分成 “设定 -> 变化 -> 结论”

### 4.3 明确 narration 和画面之间的关系

当前 narration 只要求“自然中文、口语化”，还不够。

建议加入：

- narration 只描述观众当前正在看到的内容
- 不要提前讲还没出现的对象
- 不要朗读屏幕上已经完整展示的大段文字
- 每一句 narration 尽量对应一个动画 beat

### 4.4 增加失败后的强制自检流程

可以在 prompt 里明确：

- 如果第一次 `Write` 或 `Bash` 被拒绝，先修正路径策略，不要继续尝试相似错误路径
- 如果渲染失败，先检查 `scene.py`、`GeneratedScene`、相对路径和 manim 命令，再考虑改动画逻辑
- 如果拿不到 `video_output`，必须检查 structured output 是否填全

这类规则对成功率帮助会比继续追加“风格形容词”更大。

## 5. Agent 流程应怎样优化

只改 prompt 还不够，建议把 pipeline 变成 “生成 + 自检”。

### 5.1 增加 render 前自检

在实际运行 `manim` 前，让 agent 显式检查：

- 是否只写了 task dir 内文件
- 主文件是否为 `scene.py`
- 主类是否可运行
- 是否包含明显超长文本块
- 是否有 narration 可用

### 5.2 增加质量 review pass

推荐在生成代码后加入一次轻量 review，哪怕仍然由同一个 agent 完成，也比没有强。

review 维度建议固定为：

- correctness：数学表达是否明显错误
- clarity：单屏信息是否拥挤
- motion：动画衔接是否自然
- narration：解说是否像口语
- maintainability：代码是否过度硬编码

### 5.3 长远上可以引入双阶段 agent

如果后面追求稳定质量，可以把角色拆成：

- `planner/generator`：负责首版 scene
- `reviewer`：负责按规范打回修改意见

但在当前阶段，不建议一上来就做多 agent 编排，因为真正缺的是规范资产，不是 agent 数量。

## 6. Manim 规范适合放 skill 还是知识库

结论先说：

- 执行流程和操作守则，适合放 `skill`
- 详细 Manim 规范和案例，适合放 `skill` 下的 `references/`
- 不建议只做一个松散知识库，也不建议把所有规范硬塞进 system prompt

也就是：最合适的是 “Skill + References” 组合。

### 6.1 为什么不建议只靠 system prompt

因为 Manim 规范一旦写细，会非常长，容易带来三个问题：

- 上下文成本高
- 不是每次任务都需要全部规范
- prompt 越长，执行约束反而越容易被淹没

### 6.2 为什么不建议只做知识库

纯知识库的问题是“知道有规范”不等于“会主动按规范执行”。

如果没有 skill 作为入口，agent 很可能：

- 不知道何时加载哪份规范
- 只零散引用，不形成稳定工作流
- 在压力大时退回自己的默认写法

### 6.3 为什么推荐 Skill + References

因为它正好符合这个问题的两类需求：

- `SKILL.md` 负责工作流和决策规则
- `references/` 负责细节规范和范例

推荐结构：

```text
manim-production/
├── SKILL.md
└── references/
    ├── scene-patterns.md
    ├── math-visualization-guidelines.md
    ├── narration-guidelines.md
    ├── code-style.md
    └── anti-patterns.md
```

### 6.4 这个 skill 里应该放什么

`SKILL.md` 里只放高价值、强约束内容：

- 如何判断任务类型
- 每类任务用什么 scene 模板
- 生成前要检查什么
- 渲染失败优先检查什么
- 什么时候去读哪份 reference

例如：

- 做几何构造时，读取 `scene-patterns.md`
- 做教学讲解时，读取 `narration-guidelines.md`
- 做函数图像时，读取 `math-visualization-guidelines.md`

### 6.5 references 里应该放什么

建议分文件维护，避免一份大而全文档：

- `scene-patterns.md`
  - 开场、过渡、结尾模板
  - proof / concept / geometry / function 的推荐结构
- `math-visualization-guidelines.md`
  - 颜色语义
  - 公式高亮方式
  - 坐标系、标签、重点对象的展示规范
- `narration-guidelines.md`
  - 口语化要求
  - 句长建议
  - “讲看到的，不讲未来的” 规则
- `code-style.md`
  - Manim 推荐写法
  - 尽量减少魔法数字
  - 能用对象关系就不要硬编码屏幕坐标
- `anti-patterns.md`
  - 单屏堆字
  - 中英混排漂移
  - 过多 `Text`
  - 解释和动画不同步
  - 用大量手工坐标拼图但不封装

## 7. 具体落地建议

建议按下面顺序推进，而不是一次性大改。

### Phase 1：先补规范，不急着改多 agent

- 新建一个 `manim-production` skill
- 把当前 prompt 中与执行无关、但与质量有关的规范移入 references
- 保留 system prompt 里的硬性执行约束

### Phase 2：把 prompt 改成 checklist 风格

- 在 `prompts.py` 里增加任务分类
- 明确每类任务的默认镜头结构
- 加入 render 前质量自检条目

### Phase 3：补测试

至少新增三类测试：

- prompt 生成后是否包含任务分类和自检条目
- narration 是否符合中文口语风格约束
- review 规则是否能识别典型反模式

### Phase 4：再考虑 reviewer agent

当规范稳定后，再决定是否引入单独 reviewer。
否则 reviewer 也会变成“没有评分标准的第二个模型”。

## 8. 优先级最高的几个改动

如果只做最有价值的几件事，我建议优先做：

1. 建立 `manim-production` skill，而不是继续无限堆 system prompt
2. 把 Manim 质量规范拆成 `references/` 分文件维护
3. 在 prompt 中加入任务分类和 render 前自检
4. 在 pipeline 中增加一次质量 review 或自检步骤
5. 为 narration、scene 结构和反模式补测试

## 9. 一句话结论

当前项目已经把 “agent 跑通 pipeline” 这件事做到了 70 分以上，但 “稳定地产出高质量 Manim 教学动画” 这件事还缺少一套可复用的内容规范资产。

这套资产最适合用 “`skill` 负责流程，`references` 负责 Manim 规范” 的方式落地，而不是继续单纯加长 system prompt。
