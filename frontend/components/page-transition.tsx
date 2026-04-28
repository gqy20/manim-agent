"use client";

import { usePathname } from "next/navigation";
import { useRef } from "react";

import { gsap, useGSAP } from "@/lib/gsap";
import { usePrefersReducedMotion } from "@/lib/motion";

const TRANSITION_PATHS = [
  "M -20 50 Q 25 10, 55 45 T 120 48",
  "M -10 85 Q 40 55, 80 82 T 140 78",
  "M 60 -15 Q 90 30, 115 25 T 170 35",
  "M 5 55 L 245 55",
  "M 100 110 L 100 5",
];

const SYMBOLS = [
  { ch: "int", x: "12%", y: "18%" },
  { ch: "pi", x: "72%", y: "24%" },
  { ch: "sum", x: "36%", y: "72%" },
  { ch: "inf", x: "84%", y: "68%" },
  { ch: "lim", x: "56%", y: "14%" },
  { ch: "dx", x: "18%", y: "78%" },
];

export function PageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const rootRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const reduceMotion = usePrefersReducedMotion();

  useGSAP(() => {
    if (!rootRef.current) return;

    if (reduceMotion) {
      gsap.set(rootRef.current, { opacity: 1, y: 0, filter: "none", scale: 1 });
      gsap.set(overlayRef.current, { opacity: 0 });
      return;
    }

    gsap.fromTo(
      rootRef.current,
      { opacity: 0, y: 8, filter: "blur(5px)", scale: 0.996 },
      {
        opacity: 1,
        y: 0,
        filter: "blur(0px)",
        scale: 1,
        duration: 0.42,
        ease: "power3.out",
      },
    );
  }, { scope: rootRef, dependencies: [pathname, reduceMotion] });

  useGSAP(() => {
    if (!overlayRef.current || reduceMotion) return;

    const overlay = overlayRef.current;
    const paths = overlay.querySelectorAll<SVGPathElement>("[data-transition-path]");
    const symbols = overlay.querySelectorAll<HTMLElement>("[data-transition-symbol]");

    paths.forEach((path) => {
      const length = typeof path.getTotalLength === "function" ? path.getTotalLength() + 12 : 220;
      gsap.set(path, { strokeDasharray: length, strokeDashoffset: length, opacity: 0 });
    });

    gsap.set(symbols, { opacity: 0, scale: 0.65, y: 8 });

    const tl = gsap.timeline();
    tl.set(overlay, { opacity: 1 })
      .to(paths, {
        strokeDashoffset: 0,
        opacity: 0.22,
        duration: 0.52,
        ease: "power2.inOut",
        stagger: 0.045,
      }, 0)
      .to(symbols, {
        opacity: 0.12,
        scale: 1,
        y: 0,
        duration: 0.38,
        ease: "power3.out",
        stagger: 0.035,
      }, 0.05)
      .to(paths, {
        opacity: 0,
        duration: 0.25,
        ease: "power2.out",
      }, 0.5)
      .to(symbols, {
        opacity: 0,
        scale: 1.12,
        duration: 0.22,
        ease: "power2.out",
      }, 0.48)
      .to(overlay, {
        opacity: 0,
        duration: 0.18,
        ease: "power2.out",
      }, 0.58);
  }, { scope: overlayRef, dependencies: [pathname, reduceMotion] });

  return (
    <>
      <div
        ref={overlayRef}
        className="pointer-events-none fixed inset-0 z-[9999] overflow-hidden opacity-0"
        aria-hidden="true"
      >
        <div className="absolute inset-0 bg-background/26 backdrop-blur-[2px]" />
        <svg
          viewBox="-10 -10 290 130"
          preserveAspectRatio="xMidYMid slice"
          className="absolute inset-0 h-full w-full"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <linearGradient id="page-transition-path" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="oklch(0.78 0.1 220)" stopOpacity="0.8" />
              <stop offset="100%" stopColor="oklch(0.74 0.12 285)" stopOpacity="0.18" />
            </linearGradient>
          </defs>
          {TRANSITION_PATHS.map((d, index) => (
            <path
              key={d}
              data-transition-path
              d={d}
              fill="none"
              stroke="url(#page-transition-path)"
              strokeWidth={index === 0 ? 1.2 : 0.7}
              strokeLinecap="round"
              vectorEffect="non-scaling-stroke"
            />
          ))}
        </svg>
        <div className="absolute inset-0">
          {SYMBOLS.map((symbol) => (
            <span
              key={`${symbol.ch}-${symbol.x}-${symbol.y}`}
              data-transition-symbol
              className="absolute select-none font-mono text-[clamp(1rem,2.8vw,2.4rem)] tracking-normal text-primary"
              style={{ left: symbol.x, top: symbol.y }}
            >
              {symbol.ch}
            </span>
          ))}
        </div>
      </div>
      <div ref={rootRef} key={pathname} className="min-h-full">
        {children}
      </div>
    </>
  );
}
