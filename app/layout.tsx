import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agent 3 — QA & Review Platform",
  description: "Automated quality analysis, testing, and review for MERN and Next.js projects",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-gray-950 text-gray-100 antialiased">
        {children}
      </body>
    </html>
  );
}
