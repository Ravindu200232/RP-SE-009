"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bell, Download, EyeOff, Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";

export function Header() {
  const router = useRouter();
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-card/80 px-4 backdrop-blur">
      <div className="relative flex-1 max-w-xl">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          placeholder="Search projects, requirements, services, artifacts…"
          className="h-9 w-full rounded-lg border border-border bg-secondary/50 pl-9 pr-12 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <kbd className="absolute right-3 top-1/2 -translate-y-1/2 rounded border border-border bg-card px-1.5 text-[10px] text-muted-foreground">
          ⌘K
        </kbd>
      </div>
      <div className="ml-auto flex items-center gap-1">
        <Button variant="ghost" size="icon" aria-label="Toggle visibility">
          <EyeOff className="h-4 w-4 text-muted-foreground" />
        </Button>
        <Button variant="ghost" size="icon" aria-label="Notifications" className="relative">
          <Bell className="h-4 w-4 text-muted-foreground" />
          <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-danger" />
        </Button>
        <Button variant="ghost" size="icon" aria-label="Downloads">
          <Download className="h-4 w-4 text-muted-foreground" />
        </Button>
        <Button onClick={() => router.push("/")} className="ml-1">
          <Plus className="h-4 w-4" />
          New Project
        </Button>
      </div>
    </header>
  );
}
