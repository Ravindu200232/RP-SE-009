import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Code Developer Agent — AI-Powered MERN Generator',
  description: 'Upload your SRS JSON and watch AI agents build your full MERN stack microservice application'
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#080810] text-slate-200 h-screen overflow-hidden">
        {children}
      </body>
    </html>
  );
}
