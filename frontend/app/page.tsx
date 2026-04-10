import { TaskForm } from "@/components/task-form";
import { Logo } from "@/components/logo";
import { ScrambleTitle, AnimatedMathDecorations } from "@/components/gsap-effects";

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
    <main className="flex-1 flex flex-col items-center justify-center px-4 py-8 sm:py-12 relative overflow-hidden">
      {/* Hero section */}
      <div className="w-full max-w-3xl mx-auto relative z-10">
        {/* Header */}
        <div className="text-center mb-8 animate-fade-in-up">
          <div className="inline-flex items-center gap-2 mb-4 px-3 py-1.5 rounded-full bg-primary/[0.06] border border-primary/[0.12] text-xs text-primary/70 font-medium backdrop-blur-sm">
            <Logo size={14} />
            AI 数学动画生成器
          </div>
          <ScrambleTitle 
            text="用文字生成数学动画" 
            className="text-4xl sm:text-5xl font-bold tracking-tight leading-[1.1] glow-text mb-4" 
          />
          <p className="text-muted-foreground text-base max-w-md mx-auto leading-relaxed">
            描述你的想法，一句话自动生成专业的 Manim 动画。
          </p>
        </div>

        {/* Main content: form */}
        <div className="w-full animate-fade-in-up animate-delay-100">
          <TaskForm />
        </div>

        {/* Feature pills */}
        <FeaturePills />
      </div>
      
      {/* Background decorations */}
      <div className="absolute inset-0 pointer-events-none z-0 opacity-40">
        <AnimatedMathDecorations />
      </div>
    </main>
  );
}
