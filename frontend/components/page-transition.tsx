"use client";

import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { useCallback, useMemo, useState } from "react";

const EASE_DRAW = [0.16, 1, 0.3, 1] as const;
const EASE_ERASE = [0.7, 0, 0.84, 0] as const;
const TRANSITION_PRIMARY = "#7ab4d6";
const TRANSITION_PRIMARY_SOFT = "rgba(122, 180, 214, 0.35)";
const TRANSITION_PRIMARY_FAINT = "rgba(122, 180, 214, 0.12)";

let prevDepthGlobal = -1;

function getRouteDepth(pathname: string): number {
  if (pathname === "/") return 0;
  if (pathname.startsWith("/create")) return 1;
  if (pathname.startsWith("/history")) return 1;
  if (pathname.startsWith("/tasks/")) return 2;
  return 1;
}

function detectDirection(pathname: string): number {
  const depth = getRouteDepth(pathname);
  const dir = prevDepthGlobal < 0 ? 0 : depth > prevDepthGlobal ? 1 : depth < prevDepthGlobal ? -1 : 0;
  prevDepthGlobal = depth;
  return dir;
}

interface PathDef {
  d: string;
  length: number;
  delay: number;
  dur: number;
  strokeWidth: number;
  opacity: number;
}

function generateTransitionPaths(direction: number): PathDef[] {
  const forward = direction >= 0;
  const baseDelay = forward ? 0 : 0.05;

  const paths: PathDef[] = [
    {
      d: "M -20 50 Q 25 10, 55 45 T 120 48",
      length: 200,
      delay: baseDelay,
      dur: 0.6,
      strokeWidth: 1.2,
      opacity: 0.18,
    },
    {
      d: "M -10 85 Q 40 55, 80 82 T 140 78",
      length: 210,
      delay: baseDelay + 0.08,
      dur: 0.65,
      strokeWidth: 0.8,
      opacity: 0.1,
    },
    {
      d: "M 60 -15 Q 90 30, 115 25 T 170 35",
      length: 195,
      delay: baseDelay + 0.12,
      dur: 0.55,
      strokeWidth: 1,
      opacity: 0.14,
    },
    {
      d: "M 130 95 Q 160 60, 190 70 T 240 58",
      length: 175,
      delay: baseDelay + 0.04,
      dur: 0.5,
      strokeWidth: 0.7,
      opacity: 0.09,
    },
    {
      d: "M 100 110 L 100 5",
      length: 115,
      delay: baseDelay + 0.18,
      dur: 0.4,
      strokeWidth: 0.6,
      opacity: 0.07,
    },
    {
      d: "M 5 55 L 245 55",
      length: 250,
      delay: baseDelay + 0.14,
      dur: 0.45,
      strokeWidth: 0.5,
      opacity: 0.06,
    },
    {
      d: "M 180 -10 Q 210 40, 230 38 T 270 52",
      length: 165,
      delay: baseDelay + 0.2,
      dur: 0.48,
      strokeWidth: 0.9,
      opacity: 0.11,
    },
    {
      d: "M -5 120 Q 35 90, 70 105 T 135 98",
      length: 185,
      delay: baseDelay + 0.06,
      dur: 0.58,
      strokeWidth: 0.75,
      opacity: 0.13,
    },
  ];

  if (!forward) {
    return paths.map((p) => ({
      ...p,
      d: flipPathH(p.d),
    }));
  }
  return paths;
}

function flipPathH(d: string): string {
  return d
    .split(/(?<=\d)(?=[MLQT])|(?<=[MLQT])(?=-?\d)/g)
    .map((seg) => {
      if (/^[ML]$/.test(seg)) return seg;
      const nums = seg.trim().split(/[\s,]+/).map(Number);
      if (nums.length < 2) return seg;
      return nums
        .map((n, j) => (j % 2 === 0 ? 280 - n : n))
        .join(" ");
    })
    .join(" ");
}

const SYMBOLS = [
  { ch: "∫", x: 8, y: 6, size: 2.8 },
  { ch: "π", x: 72, y: 18, size: 2.2 },
  { ch: "∑", x: 42, y: 68, size: 2.5 },
  { ch: "∞", x: 88, y: 78, size: 2.4 },
  { ch: "∂", x: 22, y: 42, size: 1.9 },
  { ch: "Δ", x: 62, y: 28, size: 2.1 },
  { ch: "θ", x: 78, y: 50, size: 2 },
  { ch: "∇", x: 34, y: 86, size: 2.3 },
  { ch: "Ω", x: 54, y: 12, size: 1.8 },
  { ch: "λ", x: 92, y: 36, size: 2 },
  { ch: "α", x: 14, y: 74, size: 1.7 },
  { ch: "φ", x: 68, y: 90, size: 2.1 },
];

interface SymbolParticleProps {
  sym: (typeof SYMBOLS)[number];
  direction: number;
  index: number;
}

function SymbolParticle({ sym, direction, index }: SymbolParticleProps) {
  const forward = direction >= 0;
  const stagger = index * 0.035;

  const originX = `${sym.x}%`;
  const originY = `${sym.y}%`;

  const scatterX = forward ? [0, (sym.x - 50) * 1.8] : [(sym.x - 50) * 1.8, 0];
  const scatterY = forward ? [0, (sym.y - 50) * 1.6] : [(sym.y - 50) * 1.6, 0];
  const rot = forward ? [0, (index % 2 === 0 ? 1 : -1) * (15 + index * 5)] : [(index % 2 === 0 ? 1 : -1) * (15 + index * 5), 0];
  const opa = forward ? [0.04, 0.14, 0] : [0, 0.1, 0];
  const sca = forward ? [0.4, 1.1, 0.6] : [0.6, 1.05, 0.4];

  return (
    <motion.span
      className="absolute font-serif select-none"
      style={{
        left: originX,
        top: originY,
        fontSize: `clamp(${sym.size - 0.6}rem, ${sym.size}vw, ${sym.size + 0.6}rem)`,
        color: TRANSITION_PRIMARY,
      }}
      initial={false}
      animate={{
        x: scatterX,
        y: scatterY,
        rotate: rot,
        scale: sca,
        opacity: opa,
      }}
      transition={{
        duration: 0.7,
        ease: forward ? EASE_DRAW : EASE_ERASE,
        delay: stagger,
        times: [0, 0.5, 1],
      }}
    >
      {sym.ch}
    </motion.span>
  );
}

interface DrawingCursorProps {
  paths: PathDef[];
  direction: number;
}

function DrawingCursor({ paths, direction }: DrawingCursorProps) {
  const primaryPath = paths[0];
  if (!primaryPath) return null;

  const forward = direction >= 0;

  return (
    <motion.circle
      r={forward ? 0 : 2.5}
      cx={forward ? 0 : 120}
      cy={forward ? 0 : 48}
      fill={TRANSITION_PRIMARY_SOFT}
      filter="url(#trans-glow)"
      initial={false}
      animate={{
        cx: forward ? [0, 120] : [120, 0],
        cy: forward ? [50, 48] : [48, 50],
        r: forward ? [0, 2.5, 1.5] : [2.5, 2, 0],
        opacity: forward ? [0, 0.6, 0] : [0, 0.4, 0],
      }}
      transition={{
        duration: primaryPath.dur + 0.15,
        ease: forward ? EASE_DRAW : EASE_ERASE,
        delay: primaryPath.delay,
        times: forward ? [0, 0.7, 1] : [0, 0.6, 1],
      }}
    />
  );
}

interface GridRevealProps {
  active: boolean;
  direction: number;
}

function GridReveal({ active, direction }: GridRevealProps) {
  const forward = direction >= 0;
  const cellSize = 32;

  const cols = typeof window !== "undefined" ? Math.ceil(window.innerWidth / cellSize) + 2 : 24;
  const rows = typeof window !== "undefined" ? Math.ceil(window.innerHeight / cellSize) + 2 : 16;

  const cells = useMemo(() => {
    const result: { key: string; row: number; col: number; delay: number }[] = [];
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const distFromCenter = Math.sqrt(Math.pow(r - rows / 2, 2) + Math.pow(c - cols / 2, 2));
        const maxDist = Math.sqrt(Math.pow(rows / 2, 2) + Math.pow(cols / 2, 2));
        const normalizedDist = distFromCenter / maxDist;
        result.push({
          key: `${r}-${c}`,
          row: r,
          col: c,
          delay: normalizedDist * (forward ? 0.35 : 0.25),
        });
      }
    }
    return result;
  }, [cols, rows, forward]);

  if (!active) return null;

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <svg className="absolute inset-0 h-full w-full" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <filter id="trans-glow">
            <feGaussianBlur stdDeviation="2.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <linearGradient id="grid-fade-h" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={TRANSITION_PRIMARY} stopOpacity={0} />
            <stop offset="50%" stopColor={TRANSITION_PRIMARY} stopOpacity={forward ? 0.06 : 0.03} />
            <stop offset="100%" stopColor={TRANSITION_PRIMARY} stopOpacity={0} />
          </linearGradient>
          <linearGradient id="grid-fade-v" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={TRANSITION_PRIMARY} stopOpacity={0} />
            <stop offset="50%" stopColor={TRANSITION_PRIMARY} stopOpacity={forward ? 0.06 : 0.03} />
            <stop offset="100%" stopColor={TRANSITION_PRIMARY} stopOpacity={0} />
          </linearGradient>
        </defs>

        {cells.slice(0, 120).map((cell) => (
          <motion.g key={cell.key}>
            <motion.line
              x1={cell.col * cellSize}
              y1={cell.row * cellSize}
              x2={(cell.col + 1) * cellSize}
              y2={cell.row * cellSize}
              stroke="url(#grid-fade-h)"
              strokeWidth={0.5}
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{
                pathLength: forward ? 1 : 0,
                opacity: forward ? [0, 0.5, 0] : [0, 0.3, 0],
              }}
              transition={{
                duration: 0.5,
                ease: forward ? EASE_DRAW : EASE_ERASE,
                delay: cell.delay,
                times: forward ? [0, 0.6, 1] : [0, 0.5, 1],
              }}
            />
            <motion.line
              x1={cell.col * cellSize}
              y1={cell.row * cellSize}
              x2={cell.col * cellSize}
              y2={(cell.row + 1) * cellSize}
              stroke="url(#grid-fade-v)"
              strokeWidth={0.5}
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{
                pathLength: forward ? 1 : 0,
                opacity: forward ? [0, 0.5, 0] : [0, 0.3, 0],
              }}
              transition={{
                duration: 0.5,
                ease: forward ? EASE_DRAW : EASE_ERASE,
                delay: cell.delay + 0.02,
                times: forward ? [0, 0.6, 1] : [0, 0.5, 1],
              }}
            />
          </motion.g>
        ))}
      </svg>
    </div>
  );
}

interface TransitionOverlayProps {
  active: boolean;
  direction: number;
}

function TransitionOverlay({ active, direction }: TransitionOverlayProps) {
  const paths = useMemo(() => generateTransitionPaths(direction), [direction]);
  const forward = direction >= 0;

  return (
    <motion.div
      initial={false}
      animate={{
        opacity: active ? 1 : 0,
      }}
      transition={{ duration: 0.15 }}
      className="pointer-events-none fixed inset-0 z-[9999] overflow-hidden"
      aria-hidden="true"
    >
      <div className="absolute inset-0 bg-background/40 backdrop-blur-[3px]" />

      <GridReveal active={active} direction={direction} />

      <svg
        viewBox="-10 -10 290 130"
        preserveAspectRatio="xMidYMid slice"
        className="absolute inset-0 h-full w-full"
        style={{ overflow: "visible" }}
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <filter id="trans-glow">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <linearGradient id="path-grad-1" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={TRANSITION_PRIMARY} stopOpacity={0.25} />
            <stop offset="100%" stopColor="#8299da" stopOpacity={0.05} />
          </linearGradient>
          <linearGradient id="path-grad-2" x1="1" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#9688dc" stopOpacity={0.15} />
            <stop offset="100%" stopColor={TRANSITION_PRIMARY} stopOpacity={0.04} />
          </linearGradient>
        </defs>

        {paths.map((path, idx) => (
          <motion.path
            key={idx}
            d={path.d}
            fill="none"
            stroke={idx % 2 === 0 ? "url(#path-grad-1)" : "url(#path-grad-2)"}
            strokeWidth={path.strokeWidth}
            strokeLinecap="round"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{
              pathLength: forward ? [0, 1, 1] : [1, 0, 0],
              opacity: forward ? [0, path.opacity, 0] : [0, path.opacity * 0.6, 0],
            }}
            transition={{
              duration: path.dur + (forward ? 0.2 : 0.1),
              ease: forward ? EASE_DRAW : EASE_ERASE,
              delay: path.delay,
              times: forward ? [0, 0.65, 1] : [0, 0.5, 1],
            }}
            style={{ vectorEffect: "non-scaling-stroke" }}
          />
        ))}

        <DrawingCursor paths={paths} direction={direction} />

        <motion.circle
          cx={forward ? 55 : 225}
          cy={forward ? 46 : 44}
          r={0}
          fill="none"
          stroke={TRANSITION_PRIMARY_FAINT}
          strokeWidth={0.6}
          initial={{ pathLength: 0, scale: 0 }}
          animate={{
            pathLength: forward ? [0, 1] : [1, 0],
            scale: forward ? [0, 1] : [1, 0],
            opacity: forward ? [0, 0.2, 0] : [0, 0.12, 0],
          }}
          transition={{
            duration: 0.8,
            ease: forward ? EASE_DRAW : EASE_ERASE,
            delay: forward ? 0.2 : 0,
            times: [0, 0.5, 1],
          }}
        />
      </svg>

      <div className="absolute inset-0">
        {SYMBOLS.map((sym, i) => (
          <SymbolParticle key={sym.ch} sym={sym} direction={direction} index={i} />
        ))}
      </div>
    </motion.div>
  );
}

function buildVariants(direction: number) {
  const yIn = direction > 0 ? 12 : direction < 0 ? -8 : 6;
  const yOut = direction > 0 ? -6 : direction < 0 ? 10 : -5;

  return {
    initial: {
      opacity: 0,
      y: yIn,
      filter: "blur(6px)",
      scale: 0.992,
    },
    animate: {
      opacity: 1,
      y: 0,
      filter: "blur(0px)",
      scale: 1,
      transition: {
        duration: 0.48,
        ease: EASE_DRAW,
      },
    },
    exit: {
      opacity: 0,
      y: yOut,
      filter: "blur(4px)",
      scale: 0.992,
      transition: {
        duration: 0.35,
        ease: EASE_ERASE,
      },
    },
  };
}

export function PageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const direction = detectDirection(pathname);
  const variants = buildVariants(direction);
  const [exiting, setExiting] = useState(false);

  const handleExitStart = useCallback(() => setExiting(true), []);
  const handleExitComplete = useCallback(() => setExiting(false), []);

  return (
    <>
      <TransitionOverlay active={exiting} direction={direction} />
      <AnimatePresence mode="wait">
        <motion.div
          key={pathname}
          variants={variants}
          initial="initial"
          animate="animate"
          exit="exit"
          onAnimationStart={(definition) => {
            if (definition === "exit") handleExitStart();
          }}
          onAnimationComplete={(definition) => {
            if (definition === "exit") handleExitComplete();
          }}
          className="h-full"
          style={{ willChange: "opacity, transform, filter" }}
        >
          {children}
        </motion.div>
      </AnimatePresence>
    </>
  );
}
