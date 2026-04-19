import Link from "next/link";
import { ArrowRight } from "lucide-react";

const STEPS = [
  { label: "输入", desc: "描述数学概念" },
  { label: "理解", desc: "AI 分析主题" },
  { label: "渲染", desc: "生成动画场景" },
  { label: "合成", desc: "输出视频成片" },
];

function PreviewCanvas() {
  return (
    <Link
      href="/create"
      className="group relative block overflow-hidden rounded-2xl border border-border bg-card transition-colors hover:border-primary/25"
    >
      <div className="aspect-[2/1]">
        <svg viewBox="0 0 400 265" fill="none" className="h-full w-full" xmlns="http://www.w3.org/2000/svg">
          {/* Grid */}
          <pattern id="pg" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M 20 0 L 0 0 0 20" fill="none" stroke="currentColor" strokeWidth="0.4" opacity="0.08" />
          </pattern>
          <rect width="100%" height="100%" fill="url(#pg)" />

          {/* Axes */}
          <line x1="50" y1="190" x2="360" y2="190" stroke="currentColor" strokeWidth="1.2" opacity="0.3" />
          <line x1="120" y1="40" x2="120" y2="205" stroke="currentColor" strokeWidth="1.2" opacity="0.3" />
          <path d="M 355 186 L 360 190 L 355 194" fill="none" stroke="currentColor" strokeWidth="1" opacity="0.2" />
          <path d="M 116 45 L 120 40 L 124 45" fill="none" stroke="currentColor" strokeWidth="1" opacity="0.2" />

          {/* Sine wave — fully contained in viewBox */}
          <path
            d="M 70 190 Q 130 60, 200 190 T 330 190"
            stroke="oklch(0.72 0.11 250)"
            strokeWidth="2"
            fill="none"
            strokeLinecap="round"
          />

          {/* Subtle glow under curve */}
          <path
            d="M 70 190 Q 130 65, 200 190 Q 265 65, 330 190 L 330 190 L 70 190 Z"
            fill="url(#curve-glow)"
          />
          <defs>
            <linearGradient id="curve-glow" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="oklch(0.72 0.11 250)" stopOpacity="0.06" />
              <stop offset="100%" stopColor="oklch(0.72 0.11 250)" stopOpacity="0" />
            </linearGradient>
          </defs>

          {/* Tangent line */}
          <line x1="165" y1="112" x2="245" y2="112" stroke="currentColor" strokeWidth="1" opacity="0.28" strokeDasharray="5 4" />

          {/* Points */}
          <circle cx="200" cy="190" r="4.5" fill="oklch(0.72 0.11 250)" opacity="0.6" />
          <circle cx="200" cy="112" r="3.5" fill="currentColor" opacity="0.4" />

          {/* Labels */}
          <text x="365" y="194" fill="currentColor" fontSize="9" opacity="0.22" fontFamily="monospace">x</text>
          <text x="114" y="33" fill="currentColor" fontSize="9" opacity="0.22" fontFamily="monospace">y</text>
          <text x="194" y="216" fill="currentColor" fontSize="9" opacity="0.18" fontFamily="monospace">f(x)</text>

          {/* Formula */}
          <text x="268" y="56" fill="currentColor" fontSize="12" opacity="0.18" fontFamily="monospace">
            ∫ f(x)dx = F(x) + C
          </text>

          {/* Origin label */}
          <text x="104" y="205" fill="currentColor" fontSize="8" opacity="0.15" fontFamily="monospace">O</text>
        </svg>
      </div>

      {/* Hover hint */}
      <div className="absolute bottom-3 right-3 flex items-center gap-1.5 rounded-full bg-background/60 px-3 py-1.5 text-[11px] text-foreground/40 backdrop-blur-sm opacity-0 transition-opacity group-hover:opacity-100">
        点击创建
        <ArrowRight className="h-3 w-3" />
      </div>
    </Link>
  );
}

export default function HomePage() {
  return (
    <main className="flex min-h-full flex-col items-center justify-center px-4 pb-6 pt-[var(--app-header-height)] sm:px-6 lg:px-8">
      <div className="mx-auto w-full max-w-[680px] space-y-7">
        {/* Header */}
        <section className="space-y-4 text-center pt-2">
          <p className="text-[11px] uppercase tracking-[0.25em] text-foreground/32">
            Manim Agent
          </p>
          <h1 className="text-[clamp(1.75rem,4vw,2.5rem)] font-semibold leading-[1.18] tracking-[-0.02em] text-foreground">
            用自然语言生成可讲解的数学动画
          </h1>
          <p className="mx-auto max-w-[420px] text-[0.9rem] leading-relaxed text-foreground/46">
            描述一个数学概念，系统自动完成理解、规划、渲染和音频编排，
            输出带旁白讲解的 Manim 动画视频。
          </p>
        </section>

        {/* Product preview — clickable */}
        <PreviewCanvas />

        {/* Flow steps */}
        <section>
          <div className="flex items-center justify-center divide-x divide-border text-center">
            {STEPS.map((step) => (
              <div key={step.label} className="px-4 py-1 first:pl-0 last:pr-0 sm:px-5">
                <p className="text-sm font-medium text-foreground/78">{step.label}</p>
                <p className="mt-0.5 text-xs text-foreground/34">{step.desc}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
