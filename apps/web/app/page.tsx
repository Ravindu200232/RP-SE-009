"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Bot, Loader2, Mic, Plus, Sparkles, X } from "lucide-react";
import { Header } from "@/components/header";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function IntakePage() {
  const router = useRouter();
  const [idea, setIdea] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const recRef = useRef<{ rec: MediaRecorder; chunks: Blob[] } | null>(null);

  const canCreate = idea.trim().length > 3 || files.length > 0;

  async function toggleRecording() {
    if (recording) {
      recRef.current?.rec.stop();
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks, { type: "audio/webm" });
        const f = new File([blob], `voice-${Date.now()}.webm`, { type: "audio/webm" });
        setFiles((prev) => [...prev, f]);
        setRecording(false);
      };
      recRef.current = { rec, chunks };
      rec.start();
      setRecording(true);
    } catch {
      setError("Microphone not available. You can still type or attach files.");
    }
  }

  async function create() {
    if (!canCreate || busy) return;
    setBusy(true);
    setError(null);
    try {
      const { project } = await api.createProject(idea.trim() || "(see attached files)");
      for (const f of files) {
        const mode = f.type.startsWith("audio")
          ? "voice"
          : f.type.includes("pdf")
            ? "pdf"
            : f.type.startsWith("image")
              ? "image"
              : "text";
        await api.uploadFile(project.id, f, mode);
      }
      router.push(`/projects/${project.id}/analyzing`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex flex-1 items-center justify-center px-4">
        <div className="w-full max-w-2xl animate-fade-in">
          <div className="mb-6 flex flex-col items-center text-center">
            <div className="mb-3 flex items-center gap-2.5">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-secondary">
                <Bot className="h-5 w-5 text-foreground" />
              </div>
              <div className="text-left">
                <div className="text-sm font-semibold leading-tight">AgentForge Studio</div>
                <div className="text-xs text-muted-foreground">New Project Intake</div>
              </div>
            </div>
            <h1 className="text-3xl font-bold tracking-tight md:text-4xl">What do you want to build?</h1>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">
              Describe your software idea and our AI agents will handle the rest — from requirements to
              deployment.
            </p>
          </div>

          <div className="rounded-2xl border border-border bg-card p-2 shadow-sm">
            <textarea
              value={idea}
              onChange={(e) => setIdea(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) create();
              }}
              placeholder="e.g. A hotel booking platform where guests can search rooms, make bookings, pay online, and hotel admins can manage inventory and view revenue reports…"
              className="min-h-[150px] w-full resize-none bg-transparent p-3 text-sm placeholder:text-muted-foreground focus:outline-none"
            />
            {files.length > 0 && (
              <div className="flex flex-wrap gap-2 px-3 pb-2">
                {files.map((f, i) => (
                  <span key={i} className="inline-flex items-center gap-1 rounded-md bg-secondary px-2 py-1 text-xs">
                    {f.name}
                    <button onClick={() => setFiles((p) => p.filter((_, j) => j !== i))} aria-label="Remove">
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
            <div className="flex items-center justify-between px-2 pb-1">
              <div className="flex items-center gap-1">
                <input
                  ref={fileRef}
                  type="file"
                  multiple
                  accept=".pdf,image/*,audio/*,.txt"
                  className="hidden"
                  onChange={(e) => e.target.files && setFiles((p) => [...p, ...Array.from(e.target.files!)])}
                />
                <Button variant="ghost" size="icon" onClick={() => fileRef.current?.click()} aria-label="Attach">
                  <Plus className="h-4 w-4 text-muted-foreground" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={toggleRecording}
                  aria-label="Record voice"
                  className={cn(recording && "bg-danger/10 text-danger")}
                >
                  <Mic className={cn("h-4 w-4", recording ? "text-danger" : "text-muted-foreground")} />
                </Button>
                {recording && <span className="text-xs text-danger">Recording… tap mic to stop</span>}
              </div>
              <span className="pr-2 text-xs text-muted-foreground">Ctrl + Enter to create</span>
            </div>
          </div>

          {error && <p className="mt-3 text-center text-sm text-danger">{error}</p>}

          <Button onClick={create} disabled={!canCreate || busy} size="lg" className="mt-4 w-full">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            Create Project with AI Agents
          </Button>
        </div>
      </main>
    </div>
  );
}
