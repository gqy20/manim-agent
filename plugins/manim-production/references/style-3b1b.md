# 3b1b (ThreeBlueOneBrown) Style Profile

This reference documents the visual style characteristics of Grant Sanderson's
3Blue1Brown educational math videos, mapped to concrete Manim configuration
values extracted from the installed Manim package source code.

All color values below are **exact hex codes** from `manim/utils/color/manim_colors.py`.
The 3b1b LaTeX template is from `manim/utils/tex_templates.py`.

## Color Palette

### 核心调色板

| 角色 | 颜色 | Hex 值 | Manim 常量 |
|------|------|--------|------------|
| 背景 | 深蓝黑 | `#050A14` | 3b1b 约定（非 Manim 默认） |
| 主文字 / 主要对象 | 白色 | `#FFFFFF` | VMobject 默认 |
| 主强调色 | 蓝色 | `#58C4DD` | `BLUE_C` |
| 次强调色 | 绿色 | `#83C167` | `GREEN_C` |
| 高亮 / 强调 | 金黄色 | `#F7D96F` | `YELLOW_C` |
| 警告 / 变换 | 红色 | `#FC6255` | `RED_C`（也是 Circle 默认色） |
| 弱化 / 去强调 | 灰色 | `#888888` | `GRAY_C` |
| 极弱化 | 深灰 | `#444444` | `GRAY_D` |

### 完整色阶速查表（每色 5 级：_A 最亮 → _E 最暗）

#### 蓝色 (BLUE)

| 色阶 | 常量 | Hex 值 | 典型用途 |
|------|------|--------|----------|
| _A | `BLUE_A` | `#C7E9F1` | 高亮背景、发光效果 |
| _B | `BLUE_B` | `#58C4DD` | 浅蓝强调 |
| **_C** | **`BLUE_C`** | **`#29ABCA`** | **默认蓝色主色** |
| _D | `BLUE_D` | `#236B8E` | 深蓝背景、暗区域 |
| _E | `BLUE_E` | `#1B6DA2` | 最深蓝（极少用） |

#### 绿色 (GREEN)

| 色阶 | 常量 | Hex 值 | 典型用途 |
|------|------|--------|----------|
| _A | `GREEN_A` | `#C9E2AE` | 浅绿背景 |
| _B | `GREEN_B` | `#83C167` | 浅绿强调 |
| **_C** | **`GREEN_C`** | **`#77B05D`** | **默认绿色主色** |
| _D | `GREEN_D` | `#699C52` | 深绿背景 |

#### 黄色 (YELLOW)

| 色阶 | 常量 | Hex 值 | 典型用途 |
|------|------|--------|----------|
| _A | `YELLOW_A` | `#FFF1B6` | 极浅黄背景 |
| _B | `YELLOW_B` | `#F7D96F` | 黄金高亮 |
| **_C** | **`YELLOW_C`** | **`#F4D345`** | **默认黄色主色** |
| _D | `YELLOW_D` | `#E8C11C` | 深黄警告 |

#### 金色 (GOLD)

| 色阶 | 常量 | Hex 值 | 典型用途 |
|------|------|--------|----------|
| _A | `GOLD_A` | `#F7C797` | 暖色浅背景 |
| _B | `GOLD_B` | `#F9B775` | 暖色高亮 |
| **_C** | **`GOLD_C`** | **`#F0AC5F`** | **默认金色** |
| _D | `GOLD_D` | `#E1A158` | 深金色 |

#### 红色 (RED)

| 色阶 | 常量 | Hex 值 | 典型用途 |
|------|------|--------|----------|
| _A | `RED_A` | `#F7A1A3` | 浅红提示 |
| _B | `RED_B` | `#FC6255` | 红色强调 |
| **_C** | **`RED_C`** | **`#E65A4C`** | **默认红色主色** |
| _D | `RED_D` | `#CF5044` | 深红错误/警告 |

#### 灰色 (GRAY)

| 色阶 | 常量 | Hex 值 | 典型用途 |
|------|------|--------|----------|
| _A | `GRAY_A` | `#DDDDDD` | 浅灰占位符 |
| _B | `GRAY_B` | `#BBBBBB` | 中灰次要文本 |
| **_C** | **`GRAY_C`** | **`#888888`** | **默认灰色（去强调）** |
| _D | `GRAY_D` | `#444444` | 深灰极弱化 |

### 数学教育语义色映射

```
已知条件、输入值              → BLUE_C (#29ABCA)
变换过程、变化                → RED_C (#E65A4C) 或 YELLOW_C (#F4D345)
结果、结论                    → GREEN_C (#77B05D)
临时高亮                      → GOLD_B (#F9B775) 或 YELLOW_B (#F7D96F)
注释、标签                    → WHITE (#FFFFFF) 降低不透明度
弱化 / 背景信息               → GRAY_C (#888888) 或 GRAY_D (#444444)
```

**规则：** 单个场景最多使用 4–5 种独立颜色（不含白/灰/黑）。
同一变量始终使用同一颜色。

### 色阶使用指南

| 用途 | 推荐色阶 | 说明 |
|------|----------|------|
| 主内容元素 | **_C（中间档）** | 如 `BLUE_C`、`GREEN_C` —— 默认推荐 |
| 高亮 / 发光效果 | **_A / _B（亮）** | 如 `BLUE_A`、`YELLOW_B` —— glow、强调边框 |
| 背景 / 暗区域 | **_D / _E（暗）** | 如 `GRAY_D`、`BLUE_E` —— 背景矩形、暗淡元素 |
| 渐变过渡 | **相邻色阶** | 如 `BLUE_B → BLUE_D` —— 渐变动画 |

## Background Configuration

```python
# In Scene config or global config:
config.background_color = "#050A14"  # Deep dark blue (not pure black)
config.background_opacity = 1.0
```

Why not pure black (`#000000`):
- Pure black looks flat and harsh on screen
- `#050A14` has subtle depth; feels like "space"
- Matches the 3b1b aesthetic of a dark void where mathematics lives

## Typography

### 数学字体（3b1b LaTeX 模板）

3b1b 模板（`TexTemplateLibrary.threeb1b`）使用以下 LaTeX 前言：

```latex
\usepackage[english]{babel}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}        % T1 字体编码（更好的符号支持）
\usepackage{lmodern}              % Latin Modern（干净的数学字体）
\usepackage{amsmath}, {amssymb}   % 标准数学包
\usepackage{dsfont}                % DS 字体（自定义符号）
\usepackage{setspace}
\usepackage{tipa}                 % 音标和注释
\usepackage{relsize}             % 相对字号
\usepackage{textcomp}            # 文本比较
\usepackage{mathrsfs}            % 数学花体字母
\usepackage{calligra}             # 装饰性草书字母
\usepackage{wasysym}             # WAS 符号
\usepackage{physics}              # 物理记号
\usepackage{xcolor}
\usepackage{microtype}            # 微排版
\DisableLigatures{encoding = *, family = * }  % 禁用连字
\linespread{1}                  % 略松的行距
```

关键要点：
- **Latin Modern** 是数学字体 —— 干净、专业、高可读性
- **T1 编码** —— 正确的符号渲染（如 ℕ → `\ell`）
- **连字禁用** —— 防止不必要的字符合并
- **略松间距** —— 小尺寸下更易读

### 推荐中文字体（按平台优先级）

| 平台 | 首选字体 | 备选字体 | 开源替代 | Pango 名称 |
|------|----------|----------|----------|------------|
| Windows | 微软雅黑 | 黑体 (SimHei) | 思源黑体 SC | `Microsoft YaHei` / `SimHei` / `Source Han Sans SC` |
| macOS | 苹方 (PingFang SC) | 华文黑体 (STHeiti) | 思源黑体 SC | `PingFang SC` / `STHeiti` |
| Linux | 思源黑体 SC | Noto Sans CJK SC | 文泉驿微米黑 | `Source Han Sans SC` / `Noto Sans CJK SC` |

**组件默认值：** `FONT_CONFIG.cn_font = "Microsoft YaHei"`（Windows 优先）

### Text() 用法（Pango 渲染，非 LaTeX）

```python
# 中文文本（始终用 Text()，永远不用 Tex/MathTex 处理 CJK）：
cjk_text("导数")                    # 自动 Microsoft YaHei, NORMAL weight
cjk_title("勾股定理")               # 自动 BOLD weight, heading_2 scale

# 英文标签：
cjk_text("slope", weight=NORMAL)    # 英文也走 Pango 渲染

# 小注释：
subtitle("Q.E.D.")                  # 自动 LIGHT weight, annotation scale
```

### 完整字号层级表（@1080p 分辨率）

| 元素 | 组件常量 | Scale | 约等像素值 | 视觉效果 |
|------|----------|-------|-----------|----------|
| 大标题（片头） | `TEXT_SIZES.display` | 1.4 | ~50 px | 醒目、主导画面 |
| 一级标题（场景名） | `TEXT_SIZES.heading_1` | 1.15 | ~41 px | 清晰但不压倒 |
| 二级标题（beat 标题） | `TEXT_SIZES.heading_2` | 1.0 | ~36 px | 标准标题大小 |
| 三级标题（子节） | `TEXT_SIZES.heading_3` | 0.85 | ~31 px | 次级标题 |
| 大正文（解说主体） | `TEXT_SIZES.body_large` | 0.7 | ~25 px | 主要解说文字 |
| 正文（默认） | `TEXT_SIZES.body` | 0.6 | ~22 px | 标准正文 |
| 小正文（次要说明） | `TEXT_SIZES.body_small` | 0.5 | ~18 px | 辅助说明 |
| 注释/标签 | `TEXT_SIZES.annotation` | 0.45 | ~16 px | 对象旁标注 |
| 说明文字 | `TEXT_SIZES.caption` | 0.4 | ~14 px | 图例/脚注 |
| 小说明 | `TEXT_SIZES.caption_small` | 0.35 | ~13 px | 极小说明 |
| 脚注 | `TEXT_SIZES.fine_print` | 0.3 | ~11 px | 最小可读 |
| 主公式 | `TEXT_SIZES.math_main` | 1.0 | 48 px | MathTex 默认 |
| 行内公式 | `TEXT_SIZES.math_inline` | 0.6 | ~29 px | 嵌入文本中 |
| 坐标轴标签 | `TEXT_SIZES.label` | 0.5 | ~24 px | 轴/图例 |

> **基准值：** `FONT_CONFIG.text_font_size = 36`（Text() 基础像素），`FONT_CONFIG.math_font_size = 48`（MathTex 基础像素）

### 字重使用矩阵

| \ | NORMAL | BOLD | LIGHT | SEMIBOLD |
|---|---------|------|-------|----------|
| **标题/beat title** | - | **推荐** | - | 可接受 |
| **正文解说** | **推荐** | 强调时 | - | - |
| **注释/标签** | - | - | **推荐** | 可接受 |
| **强调关键词** | - | **必须 + 高亮色** | - | - |
| **变量标签** | **推荐** | - | - | - |

可用字重常量（`FONT_WEIGHTS.*`）：`NORMAL`, `BOLD`, `THIN`, `ULTRALIGHT`, `LIGHT`, `SEMILIGHT`, `BOOK`, `MEDIUM`, `SEMIBOLD`, `ULTRABOLD`, `HEAVY`, `ULTRAHEAVY`

### 行距与段落间距规范

| 场景 | line_spacing 值 | 说明 |
|------|-----------------|------|
| 多行解说文本 | 0.85 – 0.95 | 收紧以节省屏幕空间 |
| 独立标题 | 1.0 – 1.1 | 默认或略宽松 |
| 公式对齐 | 不适用 | 使用 MathTex 的 `alignment` 参数 |
| 列表项 | 1.0 – 1.2 | 列表间留出呼吸空间 |

### 中英混排策略

```python
# 正确做法：拆分为独立 mobject 再组合
mixed_text("其中", r"x = \sqrt{2}")
# → VGroup(Text("其中", font="Microsoft YaHei"), MathTex(r"x = \sqrt{2}"))

# 错误做法：将中文放入 MathTex
MathTex(r"其中 x = \sqrt{2}")  # ❌ 中文会渲染为豆腐块或报错
```

## Geometry & Shape Defaults

From Manim source defaults:

| Mobject | Default fill | Default stroke | Notes |
|----------|-------------|---------------|-------|
| `Circle()` | `RED` (#FC6255) | `None` (filled) | Red circle — use `color=BLUE_C` instead |
| `Polygon()` | `BLUE` (#58C4DD) | `None` (filled) | Blue polygon — good default |
| `Rectangle()` / `Square()` | `WHITE` (#FFFFFF) | `None` (filled) | White rectangle — use with `color=BLUE_D` |
| `Line()` | `WHITE` | Width = 4 | White line — add `color=GRAY_C` |
| `Dot()` | `WHITE` | Radius varies | White dot — use `color=YELLOW_C` for emphasis |
| `Arrow()` | `WHITE` | Width = 4 | White arrow — use `color=GRAY_C` for neutral |

**3b1b 规则：** 始终设置显式颜色。永远不要依赖默认值。

## Stroke & Fill 规范

### 默认描边宽度（stroke_width）

| Mobject 类型 | 默认 stroke_width | 推荐值 | 说明 |
|--------------|-------------------|--------|------|
| `Line()` / `DashedLine()` | 4 | **2–3** | 细线更精致 |
| `Arrow()` | 4 | **3** | 箭头略粗于普通线 |
| `Circle()` / `Ellipse()` | 取决于 fill | **2–3**（仅描边模式） | 圆形轮廓 |
| `Rectangle()` / `Square()` | 取决于 fill | **2–3**（仅描边模式） | 方形轮廓 |
| `Polygon()` | 取决于 fill | **2–3**（仅描边模式） | 多边形轮廓 |
| `Brace()` / `Arc()` | ~2 | **2** | 装饰性元素保持细 |
| `Text()` / `MathTex()` | 0（填充渲染） | 不适用 | 文字不设描边 |

### 填充透明度（fill_opacity）约定

| 用途 | fill_opacity | 示例 |
|------|-------------|------|
| 实心形状 | `1.0` | 几何图形主体 |
| 半透明高亮 | `0.15 – 0.25` | 强调框、选中区域 |
| 微妙背景 | `0.05 – 0.1` | glow 效果、暗化层 |
| 不可见填充（仅描边） | `0.0` | 轮廓形状 |

### 描边 vs 填充选择决策树

```
需要表示的元素是什么？
├── 线段 / 路径 / 边界
│   └── 使用描边模式（stroke_width > 0, fill_opacity = 0）
│       例：Line(), DashedLine(), Arc()
│
├── 封闭区域 / 面积
│   ├── 需要强调面积感？
│   │   └── 是 → 填充 + 描边（fill_opacity=0.2~0.4, stroke_width=2~3）
│   │       例：三角形区域、正方形面积
│   │
│   └── 否 → 仅描边（fill_opacity=0, stroke_width=2~3）
│           例：坐标轴框架、辅助线
│
├── 标签 / 注释文字
│   └── 无描边无填充（纯文本 mobject）
│       例：cjk_text(), MathTex()
│
└── 高亮 / 强调效果
    └── BackgroundRectangle 或 SurroundingRectangle
        （fill_opacity=0.08~0.15, color=语义色）
```

### 常用样式组合速查

```python
# 主几何图形（实心半透明 + 描边）
triangle = Polygon(a, b, c, fill_color=BLUE_C, fill_opacity=0.25,
                   stroke_color=BLUE_D, stroke_width=2.5)

# 辅助线（虚线，低对比度）
aux_line = DashedLine(p1, p2, color=GRAY_C, dash_length=0.1,
                       stroke_width=1.5)

# 强调框（微透明背景 + 亮色边框）
highlight = SurroundingRectangle(target, color=YELLOW_B,
                                  buff=0.12, stroke_width=2.5)

# Glow 效果（极低透明度背景矩形）
glow = BackgroundRectangle(target, fill_opacity=0.08, color=BLUE_C,
                            buff=0.15)
```

## Animation Style Characteristics

### Speed

3b1b animations tend to be **slightly faster than Manim defaults**:

| Animation type | 3b1b typical duration | Manim default | Adjustment |
|--------------|----------------------|---------------|-----------|
| FadeIn / reveal | 0.4–0.6 s | 1.0 s | Shorter — confident appearance |
| Transform / morph | 1.5–2.5 s | 1.0–2.0 s | Similar or slightly longer |
| Write (text writing) | 1.0–1.8 s | 1.0–1.5 s | Similar |
| Emphasis (Indicate) | 0.5–0.8 s | 1.0 s | Crisper — quick pop |
| Wait (pause) | 0.3–0.6 s | 1.0 s | Much shorter — keeps momentum |

### Easing preferences

3b1b animations feel smooth because they favor **ease-out** functions:

| Situation | 3b1b preference | Rationale |
|----------|----------------|-----------|
| Objects appearing | `ease_out_cubic` | Fast start → gentle stop = natural "materializing" |
| Objects transforming | `ease_in_out_sine` | Both ends soft = fluid morphing |
| Emphasis moments | `ease_out_back` | Slight overshoot catches eye |
| Continuous motion | `smooth` (sigmoid) | Never jarring |
| Disappearing | `ease_in_cubic` | Slow fade = gentle exit, not abrupt cut |

### Camera usage

3b1b uses camera movement **sparingly but intentionally**:

- **Zoom in**: When revealing detail in a complex formula after showing overview
- **Pan**: When transitioning between spatially separated diagram regions
- **Reset**: Always return to full view after zoom — never end zoomed in
- **No rotation**: 3b1b almost never rotates the coordinate system
- **Max 1–2 camera movements per scene** — more feels seasick

## Compositional Patterns Specific to 3b1b

### The "Glow" effect

3b1b scenes often have a subtle glow around key elements.
Achieve in Manim via:

```python
from manim.mobject.geometry.shape_matchers import SurroundingRectangle

# Soft highlight box with low-opacity background
glow = BackgroundRectangle(
    target_formula,
    fill_opacity=0.08,
    color=BLUE_C,
    buff=0.15,
)
self.play(FadeIn(glow), run_time=0.8)
```

Use opacity 0.05–0.15 for subtle glow; 0.2+ for strong emphasis.

### Label placement conventions

3b1b labels follow consistent patterns:

- **Variable labels**: Below or to the right of the variable, slightly smaller
- **Value labels**: Near the point being labeled, offset by SMALL_BUFF
- **Equation group labels**: Underneath, centered, connected by Brace
- **Dimension labels**: Along the dimension line, using smaller font
- **All labels**: White or light gray on dark background; never compete with content color

### The "linger" pattern

After a transformation completes, 3b1b often shows both old and new briefly,
then shrinks old to corner:

```python
old = original.copy()
self.play(
    Transform(original, new),
    old.animate.scale(0.5).to_corner(DL).set_opacity(0.5),
    run_time=2.0,
)
# Both visible during transform; old fades to corner afterward
self.wait(0.5)
# Now only new remains prominent, old is small reference in corner
```

## Complete Style Configuration Block

Put this at the top of your scene file or in a shared config:

```python
from manim.utils.color import manim_colors as C
from manim.utils.tex import TexTemplate, TexTemplateLibrary

# ── Colors ──
BG = "#050A14"           # Dark background (3b1b signature)
TEXT = C.WHITE
MATH = C.WHITE
PRIMARY = C.BLUE_C       # #58C4DD
SECONDARY = C.GREEN_C   # #83C167
ACCENT = C.YELLOW_C     # #F7D96F
WARN = C.RED_C         # #FC6255
DIM = C.GRAY_C         # #888888
DIM2 = C.GRAY_D        # #444444

# ── LaTeX Template (3b1b style) ──
TEX_TEMPLATE = TexTemplateLibrary.threeb1b

# ── Common styled object factory ──
def StyledMath(tex_string, *, color=MATH, **kwargs):
    return MathTex(tex_string, tex_template=TEX_TEMPLATE, color=color, **kwargs)

def StyledLabel(text_string, *, color=DIM, font_size=28, **kwargs):
    return Text(text_string, color=color, font_size=font_size, **kwargs)

def StyledTitle(text_string, *, color=TEXT, font_size=56, **kwargs):
    return Text(text_string, color=color, font_size=font_size, weight=BOLD, **kwargs)
```

## Quality Settings for 3b1b Output

```bash
# Development / iteration (fast):
manim -qm scene.py          # 720p30fps — fast renders

# Final production (3b1b standard is 1080p60fps):
manim -qh scene.py          # 1080p60fps — matches YouTube HD

# If hosting on 4K platform:
manim -qk scene.py          # 3840p2160 — presentation quality
```

3b1b uploads at 1080p60fps typically. This is Manim's `high_quality`
preset — no special configuration needed beyond `-qh`.

## Quick Reference Card

```
BACKGROUND:   #050A14 (dark blue, not pure black)
TEXT/MATH:    #FFFFFF (white)
PRIMARY:      #29ABCA (blue_c)
SECONDARY:    #77B05D (green_c)
HIGHLIGHT:     #F4D345 (yellow_c)
WARNING:       #E65A4C (red_c)
DIM:           #888888 (gray_c)
STROKE_WIDTH:  2-3 (lines), 2.5 (shapes), 0 (text)

FONT (math):   Latin Modern (via threeb1b template)
FONT (CJK):    Microsoft YaHei (FONT_CONFIG.cn_font)
FONT (EN):     Segoe UI (FONT_CONFIG.en_font)
FONT (mono):   Consolas (FONT_CONFIG.mono_font)

WEIGHTS:       title=BOLD, body=NORMAL, annotation=LIGHT
SIZE HIERARCHY: display(1.4) > h1(1.15) > h2(1.0) > h3(0.85)
               > body_lg(0.7) > body(0.6) > body_sm(0.5)
               > annot(0.45) > caption(0.4) > fine(0.3)

COLOR SHADES:  _A(lightest) -> _B -> **_C(default)** -> _D -> _E(darkest)
SHADE USAGE:   main=_C, highlight=_A/_B, bg=_D/_E, gradient=adjacent

QUALITY:       -qh (1080p60fps) for final
ANIM SPEED:    Slightly faster than defaults (reveals ~0.5s, transforms ~2s)
EASING:        ease_out for appears, ease_in_out for transforms, ease_out_back for emphasis
CAMERA:        Max 1-2 movements per scene; always reset; never rotate
LABEL RULE:    Chinese->Text(), Math->MathTex(), never mix; white/dim on dark bg
MAX COLORS:    4-5 per scene + white/gray/black
FILL OPACITY:  solid=1.0, highlight=0.15-0.25, glow=0.05-0.10, outline=0.0
```