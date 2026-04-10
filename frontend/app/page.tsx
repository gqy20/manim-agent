import { TaskForm } from "@/components/task-form";
import { Logo } from "@/components/logo";

/* ── Math decoration SVGs ───────────────────────── */

function MathDecorations() {
  return (
    <div className="relative w-full h-full min-h-[420px] overflow-hidden" aria-hidden="true">
      {/* Floating coordinate system */}
      <svg
        className="math-deco math-deco-strong animate-float-slow absolute -top-2 -right-4 w-40 h-40 sm:w-52 sm:h-52"
        viewBox="0 0 120 120"
        fill="none"
      >
        <path d="M20 100 L20 20 L100 20" stroke="currentColor" strokeWidth="1" opacity="0.6"/>
        <path d="M20 80 Q 50 60, 90 35" stroke="currentColor" strokeWidth="1.5" fill="none" className="animate-draw-in" opacity="0.8"/>
        <circle cx="90" cy="35" r="3" fill="currentColor" opacity="0.5"/>
        <path d="M16 24 L20 20 L24 24" stroke="currentColor" strokeWidth="1" fill="none" opacity="0.5"/>
        <path d="M96 16 L100 20 L96 24" stroke="currentColor" strokeWidth="1" fill="none" opacity="0.5"/>
        <text x="28" y="95" fill="currentColor" fontSize="7" opacity="0.4" fontFamily="monospace">x</text>
        <text x="92" y="30" fill="currentColor" fontSize="7" opacity="0.4" fontFamily="monospace">y</text>
      </svg>

      {/* Floating triangle (geometry) */}
      <svg
        className="math-deco animate-float-reverse absolute top-8 right-[30%] w-24 h-24 sm:w-32 sm:h-32"
        viewBox="0 0 80 80"
        fill="none"
      >
        <path d="M10 65 L40 15 L70 65 Z" stroke="currentColor" strokeWidth="1.2" fill="oklch(0.7 0.18 250 / 4%)" strokeLinejoin="round"/>
        <path d="M10 65 L40 65" stroke="currentColor" strokeWidth="0.8" strokeDasharray="3 3" opacity="0.4"/>
        <path d="M36 61 L36 69 L44 69" stroke="currentColor" strokeWidth="0.8" opacity="0.4"/>
        <circle cx="40" cy="15" r="2" fill="currentColor" opacity="0.3"/>
      </svg>

      {/* Floating circle + tangent */}
      <svg
        className="math-deco math-deco-strong animate-float-medium absolute bottom-4 left-2 w-28 h-28 sm:w-36 sm:h-36"
        viewBox="0 0 90 90"
        fill="none"
      >
        <circle cx="45" cy="45" r="28" stroke="currentColor" strokeWidth="1" opacity="0.5"/>
        <line x1="17" y1="45" x2="73" y2="45" stroke="currentColor" strokeWidth="0.8" opacity="0.3"/>
        <line x1="45" y1="17" x2="45" y2="73" stroke="currentColor" strokeWidth="0.8" opacity="0.3"/>
        <circle cx="45" cy="45" r="3" fill="currentColor" opacity="0.25"/>
        <path d="M63 27 Q 72 38, 68 48" stroke="currentColor" strokeWidth="1" fill="none" opacity="0.4"/>
      </svg>

      {/* Floating formula fragment */}
      <div className="math-deco animate-float-slow absolute bottom-12 right-8 font-mono text-xs tracking-wider opacity-[0.07] select-none hidden sm:block">
        ∫₀^∞ e^(-x²) dx = √π / 2
      </div>

      {/* Subtle grid pattern */}
      <svg className="absolute inset-0 w-full h-full opacity-[0.03]" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
            <path d="M 32 0 L 0 0 0 32" fill="none" stroke="currentColor" strokeWidth="0.5"/>
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)"/>
      </svg>

      {/* Center glow orb */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-48 h-48 sm:w-64 sm:h-64 rounded-full bg-primary/[0.03] blur-3xl pointer-events-none"/>
    </div>
  );
}

/* ── Feature pills ───────────────────────────────── */

const FEATURES = [
  { label: "自然语言驱动", detail: "描述即可生成" },
  { label: "Manim 渲染引擎", detail: "出版级动画质量" },
  { label: "语音合成配音", detail: "多音色可选" },
];

function FeaturePills() {
  return (
    <div className="flex flex-wrap justify-center gap-3 mt-6">
      {FEATURES.map((f) => (
        <span
          key={f.label}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs bg-background/40 border border-border/40 text-muted-foreground/80 backdrop-blur-sm"
        >
          <span className="w-1 h-1 rounded-full bg-primary/50"/>
          {f.label}
          <span className="text-muted-foreground/40 text-[10px]">{f.detail}</span>
        </span>
      ))}
    </div>
  );
}

/* ── Page ───────────────────────────────────────── */

export default function HomePage() {
  return (
    <main className="flex-1 flex flex-col items-center justify-center px-4 py-12 sm:py-16 relative overflow-hidden">
      {/* Hero section — two column on large screens */}
      <div className="w-full max-w-5xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8 sm:mb-10 animate-fade-in-up">
          <div className="inline-flex items-center gap-2 mb-4 px-3 py-1.5 rounded-full bg-primary/[0.06] border border-primary/[0.12] text-xs text-primary/70 font-medium backdrop-blur-sm">
            <Logo size={14} />
            AI 驱动的数学可视化工具
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight leading-[1.1] glow-text mb-4">
            用文字生成<br className="sm:hidden" />数学动画
          </h1>
          <p className="text-muted-foreground text-base sm:text-lg max-w-lg mx-auto leading-relaxed">
            描述你的想法，剩下的交给 AI。<br className="hidden sm:block" />
            从概念到动画，只需一句话。
          </p>
        </div>

        {/* Main content: form + decorations */}
        <div className="grid lg:grid-cols-5 gap-6 lg:gap-8 items-start">
          {/* Form column */}
          <div className="lg:col-span-3 animate-fade-in-up animate-delay-100">
            <TaskForm />
          </div>

          {/* Decoration column — visible on lg+ screens */}
          <div className="hidden lg:block lg:col-span-2 animate-fade-in-up animate-delay-300">
            <MathDecorations />
          </div>
        </div>

        {/* Feature pills */}
        <FeaturePills />
      </div>
    </main>
  );
}
