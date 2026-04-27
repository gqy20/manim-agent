"use client";

import { TaskForm } from "@/components/task-form";

export function CreateClient({ initialPrompt = "" }: { initialPrompt?: string }) {
  return (
    <main className="relative min-h-[var(--app-content-height)] overflow-hidden px-4 pb-12 pt-5 sm:px-6 lg:px-8">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-[9%] top-[-26rem] h-[38rem] w-[64rem] rounded-full bg-[radial-gradient(circle,oklch(0.7_0.095_235/0.14),transparent_67%)] blur-3xl" />
        <div className="absolute bottom-[-17rem] right-[-7rem] h-[32rem] w-[36rem] rounded-full bg-[radial-gradient(circle,oklch(0.79_0.12_78/0.075),transparent_70%)] blur-3xl" />
        <div className="absolute inset-0 bg-[linear-gradient(112deg,transparent_0%,oklch(1_0_0/0.02)_46%,transparent_68%)]" />
      </div>

      <div className="relative mx-auto flex w-full max-w-[1440px] flex-col gap-4">
        <section className="animate-fade-in-up flex flex-col gap-3 pt-2 sm:flex-row sm:items-end sm:justify-between">
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
