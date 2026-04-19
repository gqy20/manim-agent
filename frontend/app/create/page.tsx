import { CreateClient } from "./create-client";

export default async function CreatePage({
  searchParams,
}: {
  searchParams: Promise<{ prompt?: string }>;
}) {
  const resolvedSearchParams = await searchParams;
  const prompt = typeof resolvedSearchParams.prompt === "string" ? resolvedSearchParams.prompt : "";

  return <CreateClient initialPrompt={prompt} />;
}
