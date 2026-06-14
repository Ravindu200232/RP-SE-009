'use client';
import * as React from 'react';
import Link from 'next/link';
import { Icon } from '@/components/ui/icon';

export default function About() {
  const hide = (e) => { e.currentTarget.style.display = 'none'; };

  const pillars = [
    { t: 'Pillar one title', d: 'Two sentences describing this pillar of the experience in warm, concrete language.' },
    { t: 'Pillar two title', d: 'Two sentences describing this pillar of the experience in warm, concrete language.' },
    { t: 'Pillar three title', d: 'Two sentences describing this pillar of the experience in warm, concrete language.' },
  ];
  const quotes = [
    { n: 'Full Name', r: 'Role, Company', t: 'Two-sentence testimonial quote.' },
    { n: 'Full Name', r: 'Role, Company', t: 'Two-sentence testimonial quote.' },
  ];
  const stats = [['10k+', 'Customers'], ['99.9%', 'Uptime'], ['4.9/5', 'Avg rating'], ['24/7', 'Support']];

  return (
    <div className="w-full">
      {/* mission hero */}
      <section className="px-4 pb-14 pt-20">
        <div className="mx-auto max-w-3xl text-center">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-primary">Our story</p>
          <h1 className="font-display text-4xl font-bold tracking-tight md:text-6xl">Heading about the people behind it</h1>
          <p className="mt-5 text-lg text-muted-foreground">Three sentences telling the story - the founding idea, the craft, and the promise to the customer.</p>
        </div>
      </section>

      {/* story split with photos */}
      <section className="px-4 pb-24">
        <div className="mx-auto grid max-w-7xl items-center gap-12 lg:grid-cols-2">
          <div className="grid grid-cols-2 gap-5">
            <img src="/assets/about1.jpg" alt="" onError={hide} className="mt-8 h-72 w-full rounded-2xl object-cover shadow-md" />
            <img src="/assets/about2.jpg" alt="" onError={hide} className="h-72 w-full rounded-2xl object-cover shadow-md" />
          </div>
          <div>
            <h2 className="mb-5 font-display text-3xl font-bold md:text-4xl">Benefits heading goes here</h2>
            <p className="mb-7 leading-relaxed text-muted-foreground">Two sentences on the overall benefit story for this audience.</p>
            <ul className="space-y-3.5">
              {['Benefit point one', 'Benefit point two', 'Benefit point three'].map((b) => (
                <li key={b} className="flex items-center gap-3">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary"><Icon name="check" className="h-3.5 w-3.5" /></span>
                  <span className="text-sm">{b}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* values / pillars */}
      <section className="bg-muted/50 px-4 py-20">
        <div className="mx-auto max-w-7xl">
          <h2 className="mb-12 text-center font-display text-3xl font-bold md:text-4xl">Section heading about the experience</h2>
          <div className="grid gap-6 md:grid-cols-3">
            {pillars.map((p, i) => (
              <div key={p.t} className="rounded-2xl border bg-card p-7 shadow-sm">
                <p className="mb-3 font-display text-4xl font-bold text-primary/20">0{i + 1}</p>
                <h3 className="mb-2 text-lg font-semibold">{p.t}</h3>
                <p className="text-sm leading-relaxed text-muted-foreground">{p.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* stats */}
      <section className="px-4 py-20">
        <div className="mx-auto grid max-w-5xl grid-cols-2 gap-8 text-center md:grid-cols-4">
          {stats.map(([n, l]) => (
            <div key={l}><p className="font-display text-4xl font-bold text-primary md:text-5xl">{n}</p><p className="mt-1 text-sm text-muted-foreground">{l}</p></div>
          ))}
        </div>
      </section>

      {/* quotes */}
      <section className="px-4 pb-24">
        <div className="mx-auto grid max-w-5xl gap-8 md:grid-cols-2">
          {quotes.map((q) => (
            <div key={q.n + q.r} className="rounded-3xl border bg-card p-8 shadow-sm">
              <p className="mb-6 font-display text-xl leading-relaxed">"{q.t}"</p>
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-full bg-primary font-bold text-primary-foreground">{String(q.n || '?').charAt(0)}</div>
                <div><p className="text-sm font-semibold">{q.n}</p><p className="text-xs text-muted-foreground">{q.r}</p></div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="px-4 pb-24">
        <div className="mx-auto max-w-5xl rounded-3xl bg-primary p-12 text-center text-primary-foreground">
          <h2 className="mb-3 font-display text-3xl font-bold md:text-4xl">Final call-to-action headline</h2>
          <p className="mb-7 opacity-85">One sentence of encouragement.</p>
          <Link href="/register" className="inline-block rounded-xl bg-background px-8 py-3.5 font-semibold text-foreground shadow-xl transition hover:opacity-90">Get Started</Link>
        </div>
      </section>
    </div>
  );
}
