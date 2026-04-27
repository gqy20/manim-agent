"use client";

import { TaskForm } from "@/components/task-form";

export function CreateClient({ initialPrompt = "" }: { initialPrompt?: string }) {
  return (
    <main className="relative min-h-[var(--app-content-height)] overflow-hidden px-4 pb-8 pt-6 sm:px-6 lg:px-8">
      <div className="pointer-events-none absolute inset-x-0 top-0 mx-auto h-80 w-[min(980px,90vw)] rounded-full bg-primary/[0.025] blur-3xl" />
      <div className="relative mx-auto flex w-full max-w-[1500px] flex-col gap-5">
        <section className="flex shrink-0 items-end justify-between gap-4">
          <h1 className="text-[clamp(1.55rem,2.4vw,2.35rem)] font-semibold tracking-normal text-foreground/90">
            新建任务
          </h1>
        </section>

        <div className="min-h-0">
          <TaskForm initialPrompt={initialPrompt} />
        </div>
      </div>
    </main>
  );
}
