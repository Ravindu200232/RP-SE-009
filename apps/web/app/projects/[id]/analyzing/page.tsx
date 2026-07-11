"use client";

import { use, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/header";
import { api } from "@/lib/api";
import { useAgentStream } from "@/lib/use-agent-stream";

export default function AnalyzingPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [idea, setIdea] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { latest } = useAgentStream(id);
  const started = useRef(false);

  useEffect(() => {
    api.getProject(id).then((d) => setIdea(d.project.raw_idea)).catch(() => {});
  }, [id]);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    api
      .analyze(id)
      .then(() => {
        // Brief pause so the user sees completion, then go to questions.
        setTimeout(() => router.push(`/projects/${id}/questions`), 600);
      })
      .catch((e) => setError((e as Error).message));
  }, [id, router]);

  const progress = Math.max(8, Math.round(latest?.progress ?? 12));
  const message = latest?.message ?? "Reading your idea…";

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex flex-1 flex-col items-center justify-center px-4">
        <div className="flex w-full max-w-md flex-col items-center text-center">
          <p className="text-sm text-muted-foreground">Reading your idea:</p>
          <p className="mt-1 max-w-sm truncate text-sm italic text-foreground">
            &ldquo;{idea || "…"}&rdquo;
          </p>

          <div className="my-10 afs-spinner" />

          <h2 className="text-lg font-semibold">Agent 1 is analyzing your idea…</h2>
          <p className="mt-1 text-sm text-muted-foreground">{message}</p>

          <div className="mt-5 h-2 w-full overflow-hidden rounded-full bg-secondary">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="mt-2 text-sm font-medium text-primary">{progress}%</p>

          {error && (
            <p className="mt-4 text-sm text-danger">
              {error} — <button className="underline" onClick={() => location.reload()}>retry</button>
            </p>
          )}
        </div>
      </main>
    </div>
  );
}
