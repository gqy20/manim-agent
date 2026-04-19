"use client";

import { TaskForm } from "@/components/task-form";
import { useRef, useEffect } from "react";
import gsap from "gsap";

export function CreateClient({ initialPrompt = "" }: { initialPrompt?: string }) {
  const headerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!headerRef.current) return;
    gsap.fromTo(
      headerRef.current,
      { opacity: 0, y: -16 },
      { opacity: 1, y: 0, duration: 0.55, ease: "cubic-bezier(0.16, 1, 0.3, 1)", delay: 0.08 }
    );
  }, []);

  return (
    <main className="relative min-h-[var(--app-content-height)] px-4 pb-6 pt-4 sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-[1560px] flex-col gap-3">
        <section ref={headerRef} className="flex shrink-0 flex-col gap-1">
          <div className="flex flex-col gap-1">
            <div className="max-w-3xl">
              <h1 className="text-[clamp(1.4rem,2.2vw,2rem)] font-medium tracking-[-0.03em] text-foreground/88">
                新建任务
              </h1>
            </div>
          </div>
        </section>

        <div className="min-h-0">
          <TaskForm initialPrompt={initialPrompt} />
        </div>
      </div>
    </main>
  );
}
