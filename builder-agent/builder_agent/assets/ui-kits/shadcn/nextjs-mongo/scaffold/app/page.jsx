import { ArrowUpRight } from 'lucide-react';
import { Badge } from '@/components/ui/badge.jsx';
import { Button } from '@/components/ui/button.jsx';
import { Card, CardContent, CardHeader } from '@/components/ui/card.jsx';

export default function HomePage() {
  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-16 lg:px-10 lg:py-24">
      <Badge>Shadcn scaffold ready</Badge>
      <div className="mt-8 grid items-end gap-10 lg:grid-cols-[1.25fr_.75fr]">
        <div><h1 className="max-w-3xl font-display text-5xl font-semibold tracking-tight lg:text-7xl">Build the product from this working canvas.</h1><p className="mt-6 max-w-2xl text-lg leading-8 text-slate-600">The UI kit, tokens, test runner and application boundary are already connected.</p></div>
        <Card><CardHeader><h2 className="text-lg font-semibold">Ready for domain content</h2></CardHeader><CardContent><p className="text-sm leading-6 text-slate-600">Replace this starter composition with the approved plan and selected page blocks.</p><Button className="mt-5">Start composing <ArrowUpRight size={16} /></Button></CardContent></Card>
      </div>
    </main>
  );
}
