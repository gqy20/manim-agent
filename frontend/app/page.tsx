import Link from "next/link";
import { ArrowRight, History } from "lucide-react";

import { AnimatedMathDecorations, ScrambleTitle } from "@/components/gsap-effects";

const SIGNALS = [
  "理解主题边界与讲解重点",
  "生成结构化 build spec 约束实现",
  "输出渲染、旁白、配乐与最终成片",
];

export default function HomePage() {
  return (
    <main className="relative h-[var(--app-content-height)] overflow-hidden px-4 pb-6 pt-6 sm:px-6 sm:pt-8 lg:px-8 lg:pb-8 lg:pt-10">
      <div className="mx-auto grid h-full w-full max-w-[1360px] items-start gap-8 lg:grid-cols-[minmax(0,1.02fr)_minmax(390px,0.9fr)] lg:gap-12">
        <section className="relative z-10 max-w-[660px] pt-6 lg:pt-10">
          <p className="text-[11px] uppercase tracking-[0.34em] text-cyan-300/62">Manim Agent</p>
          <ScrambleTitle
            text="用文字生成数学动画"
            className="mt-5 max-w-[6.7ch] text-[clamp(3rem,6vw,5.3rem)] font-semibold leading-[0.88] tracking-[-0.085em] glow-text"
          />

          <p className="mt-8 max-w-[31rem] text-[1rem] leading-[1.95] text-white/44">
            用自然语言定义主题，由系统完成理解、规划、渲染和音频编排。
            <br className="hidden md:block" />
            把复杂流程藏在后面，把真正的工作面留给创作。
          </p>

          <div className="mt-10 flex flex-wrap items-center gap-4">
            <Link
              href="/create"
              className="inline-flex items-center gap-2 rounded-full border border-cyan-400/18 bg-cyan-400/10 px-6 py-3.5 text-sm font-medium text-cyan-200 transition hover:border-cyan-300/30 hover:bg-cyan-400/16"
            >
              进入工作台
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/history"
              className="inline-flex items-center gap-2 text-sm text-white/42 transition hover:text-white/76"
            >
              <History className="h-4 w-4" />
              查看历史任务
            </Link>
          </div>
        </section>

        <section className="relative z-10 lg:mt-8">
          <div className="relative overflow-hidden rounded-[34px] border border-white/7 bg-[linear-gradient(180deg,rgba(7,12,19,0.92),rgba(7,11,18,0.78))] p-6 shadow-[0_28px_90px_rgba(2,6,23,0.42)]">
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(34,211,238,0.12),transparent_24%),radial-gradient(circle_at_bottom_left,rgba(59,130,246,0.08),transparent_34%)]" />
            <div className="pointer-events-none absolute inset-0 opacity-30">
              <AnimatedMathDecorations />
            </div>

            <div className="relative z-10 flex h-[min(56vh,520px)] flex-col rounded-[28px] border border-white/8 bg-black/14 p-7">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.28em] text-white/28">
                    Mathematical motion studio
                  </p>
                  <h2 className="mt-5 max-w-[13ch] text-[1.9rem] font-medium leading-[1.08] tracking-[-0.055em] text-white/92">
                    一个更安静的工作流，用来产出可讲解的数学动画。
                  </h2>
                </div>
                <div className="mt-1 h-3 w-3 rounded-full bg-cyan-300/70 shadow-[0_0_16px_rgba(34,211,238,0.45)]" />
              </div>

              <div className="mt-8 space-y-3">
                {SIGNALS.map((item, index) => (
                  <div
                    key={item}
                    className="flex items-start gap-3 rounded-[18px] border border-white/7 bg-black/14 px-4 py-3.5"
                  >
                    <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/[0.04] text-[10px] font-mono text-white/44">
                      0{index + 1}
                    </div>
                    <p className="text-sm leading-6 text-white/54">{item}</p>
                  </div>
                ))}
              </div>

              <div className="mt-auto border-t border-white/8 pt-4">
                <p className="text-[11px] uppercase tracking-[0.26em] text-white/28">One page, one job</p>
                <p className="mt-2 max-w-[38rem] text-sm leading-7 text-white/46">
                  首页负责建立理解，创建页负责提交任务，任务页负责观看与控制。每个页面只做一件事。
                </p>
              </div>
            </div>
          </div>
        </section>
      </div>

      <div className="pointer-events-none absolute inset-0 z-0 opacity-40">
        <div className="absolute left-[12%] top-[18%] h-56 w-56 rounded-full bg-cyan-400/8 blur-[110px]" />
        <div className="absolute right-[10%] top-[14%] h-72 w-72 rounded-full bg-blue-500/10 blur-[140px]" />
        <div className="absolute bottom-[10%] left-[18%] h-44 w-44 rounded-full bg-emerald-400/6 blur-[100px]" />
      </div>
    </main>
  );
}
