import { TaskForm } from "@/components/task-form";

export default async function CreatePage({
  searchParams,
}: {
  searchParams: Promise<{ prompt?: string }>;
}) {
  const resolvedSearchParams = await searchParams;
  const prompt = typeof resolvedSearchParams.prompt === "string" ? resolvedSearchParams.prompt : "";

  return (
    <main className="relative h-[var(--app-content-height)] overflow-hidden px-4 pb-4 pt-4 sm:px-6 lg:px-8">
      <div className="mx-auto flex h-full w-full max-w-[1360px] flex-col gap-2.5">
        <section className="flex shrink-0 flex-col gap-1">
          <div className="flex flex-col gap-1">
            <div className="max-w-3xl">
              <h1 className="text-[clamp(1.6rem,2.8vw,2.45rem)] font-semibold leading-[0.98] tracking-[-0.05em] text-white/92">
                发起一个新的数学动画任务
              </h1>
              <p className="mt-1 text-sm leading-6 text-white/42">
                直接输入主题，配置交付参数，然后进入运行阶段。
              </p>
            </div>
          </div>
        </section>

        <div className="min-h-0 flex-1">
          <TaskForm initialPrompt={prompt} />
        </div>
      </div>

      <div className="pointer-events-none absolute inset-0 z-0 opacity-34">
        <div className="absolute left-[8%] top-[18%] h-56 w-56 rounded-full bg-cyan-400/7 blur-[110px]" />
        <div className="absolute right-[10%] top-[14%] h-72 w-72 rounded-full bg-blue-500/10 blur-[140px]" />
      </div>
    </main>
  );
}
