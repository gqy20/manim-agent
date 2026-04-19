"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useRef, useEffect, useState } from "react";
import gsap from "gsap";

const STEPS = [
  { label: "输入", desc: "描述数学概念" },
  { label: "理解", desc: "AI 分析主题" },
  { label: "渲染", desc: "生成动画场景" },
  { label: "合成", desc: "输出视频成片" },
];

const FLOAT_SYMBOLS = ["∫", "π", "∑", "∞", "∂", "Δ", "θ", "λ"];

const SYMBOL_POSITIONS = FLOAT_SYMBOLS.map((_, i) => ({
  left: 12 + i * 13 + ((i * 7 + 3) % 6),
  top: 10 + (i % 3) * 28 + ((i * 11 + 5) % 12),
}));

function FloatingSymbols() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const ctx = gsap.context(() => {
      const symbols = containerRef.current!.querySelectorAll("[data-symbol]");
      symbols.forEach((el) => {
        const dur = gsap.utils.random(5, 8);
        const yDist = gsap.utils.random(15, 30);
        const rot = gsap.utils.random(-6, 6);
        gsap.to(el, {
          y: `-${yDist}`,
          rotation: rot,
          opacity: () => gsap.utils.random(0.04, 0.1),
          duration: dur,
          ease: "sine.inOut",
          repeat: -1,
          yoyo: true,
          delay: gsap.utils.random(0, 2),
        });
      });
    });
    return () => ctx.revert();
  }, []);

  return (
    <div ref={containerRef} className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      {FLOAT_SYMBOLS.map((sym, i) => (
        <span
          key={sym + i}
          data-symbol
          className="absolute font-serif text-[clamp(1.2rem,3vw,2.4rem)] text-primary/0 select-none"
          style={{
            left: `${SYMBOL_POSITIONS[i].left}%`,
            top: `${SYMBOL_POSITIONS[i].top}%`,
            opacity: 0.05,
          }}
        >
          {sym}
        </span>
      ))}
    </div>
  );
}

function PreviewCanvas() {
  const svgRef = useRef<SVGSVGElement>(null);
  const dotRef = useRef<SVGCircleElement>(null);
  const glowRef = useRef<SVGEllipseElement>(null);
  const containerRef = useRef<HTMLAnchorElement>(null);
  const played = useRef(false);

  useEffect(() => {
    if (!svgRef.current || !dotRef.current || played.current) return;
    played.current = true;

    const ctx = gsap.context(() => {
      const curve = svgRef.current!.querySelector("[data-curve]") as SVGPathElement;
      const tangent = svgRef.current!.querySelector("[data-tangent]") as SVGLineElement;
      const pointX = svgRef.current!.querySelector("[data-point-x]") as SVGCircleElement;
      const pointY = svgRef.current!.querySelector("[data-point-y]") as SVGCircleElement;
      const fillArea = svgRef.current!.querySelector("[data-fill]") as SVGPathElement;

      if (!curve) return;

      const len = curve.getTotalLength();

      gsap.set(curve, { strokeDasharray: len, strokeDashoffset: len });
      if (fillArea) gsap.set(fillArea, { opacity: 0 });

      const tl = gsap.timeline({ defaults: { ease: "power2.inOut" } });

      tl.to(curve, {
        strokeDashoffset: 0,
        duration: 2.2,
        delay: 0.35,
      })
        .to(fillArea, { opacity: 1, duration: 0.8 }, "-=0.6")
        .fromTo(
          tangent,
          { opacity: 0, attr: { x1: 165, x2: 165 } },
          { opacity: 0.28, attr: { x2: 245 }, duration: 0.7 },
          "-=0.3"
        )
        .fromTo(pointX, { scale: 0, transformOrigin: "center" }, { scale: 1, duration: 0.4 }, "-=0.4")
        .fromTo(pointY, { scale: 0, transformOrigin: "center" }, { scale: 1, duration: 0.35 }, "-=0.25");

      const dot = dotRef.current!;
      const glow = glowRef.current!;
      const dotTl = gsap.timeline({ repeat: -1, repeatDelay: 1.5, delay: 2.8 });
      const progress = { v: 0 };

      dotTl
        .set([dot, glow], { opacity: 0 })
        .to(progress, {
          v: 1,
          duration: 3.5,
          ease: "none",
          onUpdate: () => {
            const pt = curve.getPointAtLength(progress.v * len);
            gsap.set(dot, { cx: pt.x, cy: pt.y });
            if (glow) gsap.set(glow, { cx: pt.x, cy: pt.y });
          },
        })
        .to([dot, glow], { opacity: 0, duration: 0.3 });

      containerRef.current?.addEventListener("mouseenter", () => {
        gsap.to(curve, { strokeWidth: 2.5, duration: 0.3 });
        gsap.to(dot, { r: 4.5, duration: 0.3 });
        if (glow) gsap.to(glow, { rx: 18, ry: 10, opacity: 0.25, duration: 0.3 });
      }, { passive: true });

      containerRef.current?.addEventListener("mouseleave", () => {
        gsap.to(curve, { strokeWidth: 2, duration: 0.3 });
        gsap.to(dot, { r: 3, duration: 0.3 });
        if (glow) gsap.to(glow, { rx: 14, ry: 7, opacity: 0.12, duration: 0.3 });
      }, { passive: true });
    }, containerRef);

    return () => ctx.revert();
  }, []);

  return (
    <Link
      ref={containerRef}
      href="/create"
      className="group relative block overflow-hidden rounded-2xl border border-border bg-card transition-colors hover:border-primary/25"
    >
      <FloatingSymbols />
      <div className="aspect-[2/1]">
        <svg ref={svgRef} viewBox="0 0 400 265" fill="none" className="h-full w-full" xmlns="http://www.w3.org/2000/svg">
          <pattern id="pg" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M 20 0 L 0 0 0 20" fill="none" stroke="currentColor" strokeWidth="0.4" opacity="0.08" />
          </pattern>
          <rect width="100%" height="100%" fill="url(#pg)" />

          <line x1="50" y1="190" x2="360" y2="190" stroke="currentColor" strokeWidth="1.2" opacity="0.3" />
          <line x1="120" y1="40" x2="120" y2="205" stroke="currentColor" strokeWidth="1.2" opacity="0.3" />
          <path d="M 355 186 L 360 190 L 355 194" fill="none" stroke="currentColor" strokeWidth="1" opacity="0.2" />
          <path d="M 116 45 L 120 40 L 124 45" fill="none" stroke="currentColor" strokeWidth="1" opacity="0.2" />

          <path
            data-curve
            d="M 70 190 Q 130 60, 200 190 T 330 190"
            stroke="oklch(0.72 0.11 250)"
            strokeWidth="2"
            fill="none"
            strokeLinecap="round"
          />

          <path
            data-fill
            d="M 70 190 Q 130 65, 200 190 Q 265 65, 330 190 L 330 190 L 70 190 Z"
            fill="url(#curve-glow)"
          />
          <defs>
            <linearGradient id="curve-glow" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="oklch(0.72 0.11 250)" stopOpacity="0.06" />
              <stop offset="100%" stopColor="oklch(0.72 0.11 250)" stopOpacity="0" />
            </linearGradient>
            <radialGradient id="dot-glow">
              <stop offset="0%" stopColor="oklch(0.72 0.11 250)" stopOpacity="0.3" />
              <stop offset="100%" stopColor="oklch(0.72 0.11 250)" stopOpacity="0" />
            </radialGradient>
          </defs>

          <line data-tangent x1="165" y1="112" x2="245" y2="112" stroke="currentColor" strokeWidth="1" opacity="0.28" strokeDasharray="5 4" />

          <circle data-point-x cx="200" cy="190" r="4.5" fill="oklch(0.72 0.11 250)" opacity="0.6" />
          <circle data-point-y cx="200" cy="112" r="3.5" fill="currentColor" opacity="0.4" />

          <ellipse ref={glowRef} cx="70" cy="190" rx="14" ry="7" fill="url(#dot-glow)" opacity="0" />

          <circle ref={dotRef} cx="70" cy="190" r="3" fill="oklch(0.72 0.11 250)" opacity="0">
            <animate attributeName="r" values="3;4;3" dur="1s" repeatCount="indefinite" />
          </circle>

          <text x="365" y="194" fill="currentColor" fontSize="9" opacity="0.22" fontFamily="monospace">x</text>
          <text x="114" y="33" fill="currentColor" fontSize="9" opacity="0.22" fontFamily="monospace">y</text>
          <text x="194" y="216" fill="currentColor" fontSize="9" opacity="0.18" fontFamily="monospace">f(x)</text>
          <text x="268" y="56" fill="currentColor" fontSize="12" opacity="0.18" fontFamily="monospace">
            ∫ f(x)dx = F(x) + C
          </text>
          <text x="104" y="205" fill="currentColor" fontSize="8" opacity="0.15" fontFamily="monospace">O</text>
        </svg>
      </div>

      <div className="absolute bottom-3 right-3 flex items-center gap-1.5 rounded-full bg-background/60 px-3 py-1.5 text-[11px] text-foreground/40 backdrop-blur-sm opacity-0 transition-opacity group-hover:opacity-100">
        点击创建
        <ArrowRight className="h-3 w-3" />
      </div>
    </Link>
  );
}

function FlowSteps() {
  const stepsRef = useRef<HTMLDivElement>(null);
  const [activeStep, setActiveStep] = useState(-1);

  useEffect(() => {
    if (!stepsRef.current) return;
    const ctx = gsap.context(() => {
      const items = stepsRef.current!.querySelectorAll("[data-step]");
      items.forEach((el, i) => {
        gsap.fromTo(
          el,
          { opacity: 0.34, y: 6 },
          {
            opacity: 0.78,
            y: 0,
            duration: 0.5,
            ease: "cubic-bezier(0.16, 1, 0.3, 1)",
            delay: 1.8 + i * 0.15,
            onStart: () => setActiveStep(i),
          }
        );
      });
    });
    return () => ctx.revert();
  }, []);

  return (
    <div ref={stepsRef}>
      <div className="flex items-center justify-center divide-x divide-border text-center">
        {STEPS.map((step, i) => (
          <div key={step.label} data-step className="relative px-4 py-1 first:pl-0 last:pr-0 sm:px-5">
            {i <= activeStep && activeStep >= 0 && (
              <span className="absolute -top-px left-1/2 h-px w-4 -translate-x-1/2 bg-primary/40 rounded-full" />
            )}
            <p className={`text-sm font-medium transition-colors duration-500 ${i <= activeStep && activeStep >= 0 ? "text-foreground/88" : "text-foreground/78"}`}>
              {step.label}
            </p>
            <p className="mt-0.5 text-xs text-foreground/34">{step.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function HomePage() {
  return (
    <main className="relative flex min-h-full flex-col items-center justify-center px-4 pb-6 pt-[var(--app-header-height)] sm:px-6 lg:px-8">
      <FloatingSymbols />
      <div className="mx-auto w-full max-w-[680px] space-y-7">
        <section data-stagger className="space-y-4 text-center pt-2">
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

        <div data-stagger>
          <PreviewCanvas />
        </div>

        <section data-stagger>
          <FlowSteps />
        </section>
      </div>
    </main>
  );
}
