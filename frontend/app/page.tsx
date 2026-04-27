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
          className="absolute select-none font-serif text-[clamp(1.1rem,2.5vw,2.1rem)] text-primary/10"
          style={{
            left: `${SYMBOL_POSITIONS[i].left}%`,
            top: `${SYMBOL_POSITIONS[i].top}%`,
            opacity: 0.035,
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
    const container = containerRef.current;
    if (!container || !svgRef.current || !dotRef.current || played.current) return;
    played.current = true;
    let cleanupHover: (() => void) | undefined;

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

      const handleMouseEnter = () => {
        gsap.to(curve, { strokeWidth: 2.5, duration: 0.3 });
        gsap.to(dot, { r: 4.5, duration: 0.3 });
        if (glow) gsap.to(glow, { rx: 18, ry: 10, opacity: 0.25, duration: 0.3 });
      };

      const handleMouseLeave = () => {
        gsap.to(curve, { strokeWidth: 2, duration: 0.3 });
        gsap.to(dot, { r: 3, duration: 0.3 });
        if (glow) gsap.to(glow, { rx: 14, ry: 7, opacity: 0.12, duration: 0.3 });
      };

      container?.addEventListener("mouseenter", handleMouseEnter, { passive: true });
      container?.addEventListener("mouseleave", handleMouseLeave, { passive: true });

      cleanupHover = () => {
        container?.removeEventListener("mouseenter", handleMouseEnter);
        container?.removeEventListener("mouseleave", handleMouseLeave);
      };
    }, container);

    return () => {
      cleanupHover?.();
      ctx.revert();
    };
  }, []);

  return (
    <Link
      ref={containerRef}
      href="/create"
      className="group relative block overflow-hidden rounded-[1.35rem] border border-white/10 bg-[linear-gradient(180deg,oklch(0.17_0.01_250/0.82),oklch(0.12_0.008_250/0.92))] shadow-[0_28px_80px_-46px_oklch(0.72_0.11_250/0.45),inset_0_1px_0_oklch(1_0_0/0.06)] ring-1 ring-primary/[0.03] transition-all duration-300 hover:border-primary/24 hover:shadow-[0_32px_90px_-42px_oklch(0.72_0.11_250/0.58),inset_0_1px_0_oklch(1_0_0/0.08)]"
    >
      <FloatingSymbols />
      <div className="aspect-[1.95/1]">
        <svg ref={svgRef} viewBox="0 0 400 265" fill="none" className="h-full w-full" xmlns="http://www.w3.org/2000/svg">
          <pattern id="pg" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M 20 0 L 0 0 0 20" fill="none" stroke="currentColor" strokeWidth="0.4" opacity="0.12" />
          </pattern>
          <rect width="100%" height="100%" fill="url(#pg)" />

          <line x1="50" y1="190" x2="360" y2="190" stroke="currentColor" strokeWidth="1.2" opacity="0.38" />
          <line x1="120" y1="40" x2="120" y2="205" stroke="currentColor" strokeWidth="1.2" opacity="0.38" />
          <path d="M 355 186 L 360 190 L 355 194" fill="none" stroke="currentColor" strokeWidth="1" opacity="0.28" />
          <path d="M 116 45 L 120 40 L 124 45" fill="none" stroke="currentColor" strokeWidth="1" opacity="0.28" />

          <path
            data-curve
            d="M 70 190 Q 130 60, 200 190 T 330 190"
            stroke="oklch(0.72 0.11 250)"
            strokeWidth="2.25"
            fill="none"
            strokeLinecap="round"
          />

          <path
            data-fill
            d="M 70 190 Q 130 65, 200 190 L 70 190 Z"
            fill="url(#curve-glow)"
          />
          <defs>
            <linearGradient id="curve-glow" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="oklch(0.72 0.11 250)" stopOpacity="0.1" />
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

          <text x="365" y="194" fill="currentColor" fontSize="9" opacity="0.3" fontFamily="monospace">x</text>
          <text x="114" y="33" fill="currentColor" fontSize="9" opacity="0.3" fontFamily="monospace">y</text>
          <text x="194" y="216" fill="currentColor" fontSize="9" opacity="0.25" fontFamily="monospace">f(x)</text>
          <text x="268" y="56" fill="currentColor" fontSize="12" opacity="0.25" fontFamily="monospace">
            ∫ f(x)dx = F(x) + C
          </text>
          <text x="104" y="205" fill="currentColor" fontSize="8" opacity="0.22" fontFamily="monospace">O</text>
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
      <div className="flex items-center justify-center divide-x divide-white/8 text-center">
        {STEPS.map((step, i) => (
          <div key={step.label} data-step className="relative px-4 py-1.5 first:pl-0 last:pr-0 sm:px-6">
            {i <= activeStep && activeStep >= 0 && (
              <span className="absolute -top-px left-1/2 h-px w-4 -translate-x-1/2 bg-primary/40 rounded-full" />
            )}
            <p className={`text-sm font-medium transition-colors duration-500 ${i <= activeStep && activeStep >= 0 ? "text-foreground/90" : "text-foreground/76"}`}>
              {step.label}
            </p>
            <p className="mt-1 text-xs text-foreground/42">{step.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function HomePage() {
  return (
    <main className="relative flex min-h-full flex-col items-center justify-center overflow-hidden px-4 pb-14 pt-[calc(var(--app-header-height)+1rem)] sm:px-6 sm:pb-20 lg:px-8">
      <div className="pointer-events-none absolute inset-x-0 top-[12%] mx-auto h-[520px] w-[min(780px,92vw)] rounded-full bg-primary/[0.035] blur-3xl" aria-hidden="true" />
      <div className="pointer-events-none absolute inset-x-0 top-[36%] mx-auto h-px w-[min(720px,84vw)] bg-gradient-to-r from-transparent via-primary/14 to-transparent" aria-hidden="true" />
      <FloatingSymbols />
      <div className="relative z-10 mx-auto w-full max-w-[720px] -translate-y-3 space-y-9 sm:-translate-y-5 sm:space-y-10">
        <section data-stagger className="space-y-3 text-center">
          <p className="text-[11px] uppercase tracking-[0.32em] text-foreground/38">
            Manim Agent
          </p>
          <h1 className="text-[clamp(2rem,4.2vw,3rem)] font-semibold leading-[1.12] tracking-normal text-foreground">
            用自然语言生成可讲解的数学动画
          </h1>
        </section>

        <div data-stagger className="relative mx-auto max-w-[700px]">
          <PreviewCanvas />
        </div>

        <section data-stagger>
          <FlowSteps />
        </section>
      </div>
    </main>
  );
}
