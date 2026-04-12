import TaskDetailClient from "./task-detail-client";

// Static export: no pre-rendered params; FastAPI SPA fallback handles /tasks/:id
export function generateStaticParams() {
  return [];
}

export default function TaskDetailPage() {
  return <TaskDetailClient />;
}
