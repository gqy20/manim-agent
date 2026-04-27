"use client";

import { TaskForm } from "@/components/task-form";

export function CreateClient({ initialPrompt = "" }: { initialPrompt?: string }) {
  return (
    <main className="relative min-h-[var(--app-content-height)] overflow-hidden px-4 pb-12 pt-5 sm:px-6 lg:px-8">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-[12%] top-[-24rem] h-[36rem] w-[58rem] rounded-full bg-[radial-gradient(circle,oklch(0.72_0.11_250/0.115),transparent_66%)] blur-3xl" />
        <div className="absolute bottom-[-16rem] right-[-8rem] h-[30rem] w-[34rem] rounded-full bg-[radial-gradient(circle,oklch(0.78_0.15_70/0.07),transparent_68%)] blur-3xl" />
        <div className="absolute inset-0 bg-[linear-gradient(115deg,transparent_0%,oklch(1_0_0/0.016)_48%,transparent_70%)]" />
      </div>

      <div className="relative mx-auto flex w-full max-w-[1440px] flex-col gap-4">
        <section className="flex flex-col gap-3 pt-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.32em] text-primary/60">
              Create / Manim Video
            </p>
            <h1 className="mt-2 text-xl font-semibold tracking-normal text-foreground/90">
              创建动画任务
            </h1>
          </div>
          <p className="text-sm text-foreground/68">先理解，再生成。</p>
        </section>

        <TaskForm initialPrompt={initialPrompt} />
      </div>
    </main>
  );
}
