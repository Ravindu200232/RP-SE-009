"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, FileText, Plus } from "lucide-react";
import type { Project } from "@agentforge/shared";
import { Header } from "@/components/header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { timeAgo } from "@/lib/utils";

const statusVariant: Record<string, "default" | "success" | "warning" | "neutral"> = {
  approved: "success",
  customized: "success",
  generated: "default",
  questioning: "warning",
  needs_clarification: "warning",
  analyzing: "warning",
  error: "warning",
};

function destFor(p: Project): string {
  if (["generated", "approved", "customized"].includes(p.status)) return `/projects/${p.id}/analyzer?tab=srs`;
  if (["questioning", "needs_clarification"].includes(p.status)) return `/projects/${p.id}/questions`;
  return `/projects/${p.id}/analyzing`;
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .listProjects()
      .then((d) => setProjects(d.projects))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Projects</h1>
            <p className="text-sm text-muted-foreground">Your generated SRS documents and drafts.</p>
          </div>
          <Link href="/">
            <Button>
              <Plus className="h-4 w-4" /> New Project
            </Button>
          </Link>
        </div>

        {loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : projects.length === 0 ? (
          <Card className="flex flex-col items-center gap-3 p-10 text-center">
            <FileText className="h-8 w-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">No projects yet. Describe an idea to get started.</p>
            <Link href="/">
              <Button>
                <Plus className="h-4 w-4" /> New Project
              </Button>
            </Link>
          </Card>
        ) : (
          <div className="space-y-2">
            {projects.map((p) => (
              <Link key={p.id} href={destFor(p)}>
                <Card className="flex items-center justify-between p-4 transition-colors hover:border-primary/50 hover:bg-secondary/40">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold">{p.title}</div>
                    <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                      <Badge variant="neutral">{p.detected_domain}</Badge>
                      <span>v{p.current_version}</span>
                      <span>· {timeAgo(p.updated_at)}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant={statusVariant[p.status] || "neutral"} className="capitalize">
                      {p.status.replace(/_/g, " ")}
                    </Badge>
                    <ArrowRight className="h-4 w-4 text-muted-foreground" />
                  </div>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
