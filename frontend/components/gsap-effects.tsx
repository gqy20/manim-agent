"use client";

import { useRef } from "react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";

const CHARS = "∑∫∆∇∞πθΩαβγδεζμξρστφχψω+-*/=≈≠≡≤≥";

export function ScrambleTitle({ text, className }: { text: string; className?: string }) {
  const textRef = useRef<HTMLHeadingElement>(null);

  useGSAP(() => {
    if (!textRef.current) return;
    const el = textRef.current;
    
    const obj = { value: 0 };
    const length = text.length;

    gsap.to(obj, {
      value: 100,
      duration: 0.4, // 极速解码，只保留瞬间的闪烁感
      ease: "power2.out",
      onUpdate: () => {
        const progress = obj.value / 100;
        const revealCount = Math.floor(progress * length);
        
        let scrambled = "";
        for (let i = 0; i < length; i++) {
          if (i < revealCount) {
            scrambled += text[i];
          } else {
            scrambled += CHARS[Math.floor(Math.random() * CHARS.length)];
          }
        }
        el.innerText = scrambled;
      }
    });
  }, [text]);

  return <h1 ref={textRef} className={className}>{text}</h1>;
}

export function AnimatedMathDecorations() {
  const containerRef = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    if (!containerRef.current) return;
    
    // Select all paths, lines, and circles that use a stroke (excluding the subtle background grid)
    const elements = containerRef.current.querySelectorAll<SVGGeometryElement>(
      "svg.math-deco path[stroke], svg.math-deco line[stroke], svg.math-deco circle[stroke]"
    );
    
    // Pre-computed path lengths (these SVGs are static)
    const PATH_LENGTHS: Record<string, number> = {
      "M20 100 L20 20 L100 20": 162,
      "M20 80 Q 50 60, 90 35": 98,
      "M10 65 L40 15 L70 65": 142,
      "M10 65 L40 65": 60,
      "M36 61 L36 69 L44 69": 16,
      "M45 17 L73 17": 28,
      "M63 27 Q 72 38, 68 48": 46,
    };
    const CIRCUMFERENCE_2R = (r: number) => 2 * Math.PI * r + 10;

    elements.forEach(el => {
      const d = el.getAttribute("d") ?? "";
      // Circle elements have no "d" attribute — use circumference
      const isCircle = el.tagName.toLowerCase() === "circle";
      let length: number;

      if (isCircle) {
        const r = parseFloat(el.getAttribute("r") ?? "28");
        length = CIRCUMFERENCE_2R(r);
      } else if (PATH_LENGTHS[d]) {
        length = PATH_LENGTHS[d];
      } else if (typeof el.getTotalLength === "function") {
        length = el.getTotalLength() + 10;
      } else {
        length = 200; // fallback
      }

      gsap.set(el, {
        strokeDasharray: length,
        strokeDashoffset: length,
      });

      // Simulate Manim's Create() animation
      gsap.to(el, {
        strokeDashoffset: 0,
        duration: gsap.utils.random(2, 4),
        ease: "power2.inOut",
        delay: gsap.utils.random(0, 0.8),
      });
    });
  }, { scope: containerRef });

  return (
    <div ref={containerRef} className="relative w-full h-full min-h-[420px] overflow-hidden" aria-hidden="true">
      {/* Floating coordinate system */}
      <svg className="math-deco math-deco-strong animate-float-slow absolute -top-2 -right-4 w-40 h-40 sm:w-52 sm:h-52" viewBox="0 0 120 120" fill="none">
        <path d="M20 100 L20 20 L100 20" stroke="currentColor" strokeWidth="1" opacity="0.6"/>
        <path d="M20 80 Q 50 60, 90 35" stroke="currentColor" strokeWidth="1.5" fill="none" opacity="0.8"/>
        <circle cx="90" cy="35" r="3" fill="currentColor" opacity="0.5"/>
        <path d="M16 24 L20 20 L24 24" stroke="currentColor" strokeWidth="1" fill="none" opacity="0.5"/>
        <path d="M96 16 L100 20 L96 24" stroke="currentColor" strokeWidth="1" fill="none" opacity="0.5"/>
        <text x="28" y="95" fill="currentColor" fontSize="7" opacity="0.4" fontFamily="monospace">x</text>
        <text x="92" y="30" fill="currentColor" fontSize="7" opacity="0.4" fontFamily="monospace">y</text>
      </svg>

      {/* Floating triangle (geometry) */}
      <svg className="math-deco animate-float-reverse absolute top-8 right-[30%] w-24 h-24 sm:w-32 sm:h-32" viewBox="0 0 80 80" fill="none">
        <path d="M10 65 L40 15 L70 65 Z" stroke="currentColor" strokeWidth="1.2" fill="oklch(0.72 0.11 250 / 3%)" strokeLinejoin="round"/>
        <path d="M10 65 L40 65" stroke="currentColor" strokeWidth="0.8" opacity="0.4"/>
        <path d="M36 61 L36 69 L44 69" stroke="currentColor" strokeWidth="0.8" opacity="0.4"/>
        <circle cx="40" cy="15" r="2" fill="currentColor" opacity="0.3"/>
      </svg>

      {/* Floating circle + tangent */}
      <svg className="math-deco math-deco-strong animate-float-medium absolute bottom-4 left-2 w-28 h-28 sm:w-36 sm:h-36" viewBox="0 0 90 90" fill="none">
        <circle cx="45" cy="45" r="28" stroke="currentColor" strokeWidth="1" opacity="0.5"/>
        <line x1="17" y1="45" x2="73" y2="45" stroke="currentColor" strokeWidth="0.8" opacity="0.3"/>
        <line x1="45" y1="17" x2="45" y2="73" stroke="currentColor" strokeWidth="0.8" opacity="0.3"/>
        <circle cx="45" cy="45" r="3" fill="currentColor" opacity="0.25"/>
        <path d="M63 27 Q 72 38, 68 48" stroke="currentColor" strokeWidth="1" fill="none" opacity="0.4"/>
      </svg>

      {/* Subtle grid pattern */}
      <svg className="absolute inset-0 w-full h-full opacity-[0.03]" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
            <path d="M 32 0 L 0 0 0 32" fill="none" stroke="currentColor" strokeWidth="0.5"/>
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)"/>
      </svg>
      
      {/* Floating formula fragment */}
      <div className="math-deco animate-float-slow absolute bottom-12 right-8 font-mono text-xs tracking-wider opacity-[0.07] select-none hidden sm:block">
        ∫₀^∞ e^(-x²) dx = √π / 2
      </div>

      {/* Center glow orb — removed for cleaner look */}
    </div>
  );
}
