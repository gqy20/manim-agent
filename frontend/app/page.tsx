import { TaskForm } from "@/components/task-form";

export default function HomePage() {
  return (
    <main className="flex-1 flex flex-col items-center justify-center px-4 py-16 sm:py-20">
      {/* Hero */}
      <div className="text-center max-w-xl mx-auto mb-10 animate-fade-in-up">
        <h1 className="text-4xl sm:text-5xl font-bold tracking-tight leading-tight glow-text mb-3">
          用文字生成数学动画
        </h1>
        <p className="text-muted-foreground text-base">
          描述你的想法，剩下的交给 AI
        </p>
      </div>

      {/* Form */}
      <div className="w-full max-w-2xl animate-fade-in-up animate-delay-200">
        <TaskForm />
      </div>
    </main>
  );
}
