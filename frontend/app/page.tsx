import { TaskForm } from "@/components/task-form";

export default function HomePage() {
  return (
    <main className="flex-1 container py-12">
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-bold tracking-tight">
          AI Math Animation Generator
        </h1>
        <p className="mt-2 text-muted-foreground max-w-lg mx-auto">
          Describe your concept in natural language and get a professional
          Manim animation with voiceover.
        </p>
      </div>
      <TaskForm />
    </main>
  );
}
