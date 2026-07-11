import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgentForge Studio — AI SRS Generator",
  description:
    "Turn a raw software idea into a complete IEEE-830 SRS, diagrams, and JSON with agentic AI.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
