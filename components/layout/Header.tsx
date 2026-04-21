"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldCheck, Home, Activity, BarChart2, Bug, FileText } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Setup", icon: Home },
];

export function Header({ runId }: { runId?: string }) {
  const pathname = usePathname();

  const runNav = runId
    ? [
        { href: `/run/${runId}`, label: "Progress", icon: Activity },
        { href: `/results/${runId}`, label: "Results", icon: BarChart2 },
        { href: `/findings/${runId}`, label: "Findings", icon: Bug },
        { href: `/reports/${runId}`, label: "Reports", icon: FileText },
      ]
    : [];

  const allNav = [...NAV_ITEMS, ...runNav];

  return (
    <header className="sticky top-0 z-50 bg-gray-900/50 backdrop-blur-sm border-b border-gray-800">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5">
          <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center">
            <ShieldCheck className="h-4 w-4 text-white" />
          </div>
          <span className="font-semibold text-white text-sm">Agent 3</span>
          <span className="text-gray-500 text-xs">QA Platform</span>
        </Link>

        {/* Navigation */}
        <nav className="flex items-center gap-1">
          {allNav.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all",
                pathname === href
                  ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
                  : "text-gray-400 hover:text-gray-200 hover:bg-gray-800"
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </Link>
          ))}
        </nav>

        {/* Status badge */}
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-xs text-gray-400">Local</span>
        </div>
      </div>
    </header>
  );
}
