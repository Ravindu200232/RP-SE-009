'use client';
import * as React from 'react';
import { useState } from 'react';
import Link from 'next/link';
import { Icon } from '@/components/ui/icon';

export default function Features() {
  const [faqOpen, setFaqOpen] = useState(-1);
  const hide = (e) => { e.currentTarget.style.display = 'none'; };

  const features = [
    { icon: 'zap', title: 'Feature one', text: 'One sentence about this capability and the benefit it brings.' },
    { icon: 'shield', title: 'Feature two', text: 'One sentence about this capability and the benefit it brings.' },
    { icon: 'chart', title: 'Feature three', text: 'One sentence about this capability and the benefit it brings.' },
    { icon: 'users', title: 'Feature four', text: 'One sentence about this capability and the benefit it brings.' },
    { icon: 'clock', title: 'Feature five', text: 'One sentence about this capability and the benefit it brings.' },
    { icon: 'star', title: 'Feature six', text: 'One sentence about this capability and the benefit it brings.' },
  ];
  const stats = [['10k+', 'Customers'], ['99.9%', 'Uptime'], ['4.9/5', 'Avg rating'], ['24/7', 'Support']];
  const faqs = [
    { q: 'Question one?', a: 'Two-sentence answer.' },
    { q: 'Question two?', a: 'Two-sentence answer.' },
    { q: 'Question three?', a: 'Two-sentence answer.' },
    { q: 'Question four?', a: 'Two-sentence answer.' },
    { q: 'Question five?', a: 'Two-sentence answer.' },
  ];

  return (
    <div className="w-full">
      {/* header */}
      <section className="px-4 pb-14 pt-20">
        <div className="mx-auto max-w-3xl text-center">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-primary">Features</p>
          <h1 className="font-display text-4xl font-bold tracking-tight md:text-6xl">Section heading about what you get</h1>
          <p className="mt-5 text-lg text-muted-foreground">One supporting sentence for this section.</p>
        </div>
      </section>

      {/* photo intro band */}
      <section className="px-4 pb-20">
        <div className="mx-auto grid max-w-7xl gap-6 md:grid-cols-2">
          <img src="/assets/feature1.jpg" alt="" onError={hide} className="h-72 w-full rounded-3xl object-cover shadow-md" />
          <img src="/assets/feature2.jpg" alt="" onError={hide} className="h-72 w-full rounded-3xl object-cover shadow-md" />
        </div>
      </section>

      {/* feature grid */}
      <section className="px-4 pb-24">
        <div className="mx-auto grid max-w-7xl gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <div key={f.title} className="rounded-2xl border bg-card p-6 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
              <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary"><Icon name={f.icon} className="h-5 w-5" /></div>
              <h3 className="mb-1.5 text-lg font-semibold">{f.title}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* stats band */}
      <section className="bg-muted/50 px-4 py-16">
        <div className="mx-auto grid max-w-5xl grid-cols-2 gap-8 text-center md:grid-cols-4">
          {stats.map(([n, l]) => (
            <div key={l}><p className="font-display text-4xl font-bold text-primary md:text-5xl">{n}</p><p className="mt-1 text-sm text-muted-foreground">{l}</p></div>
          ))}
        </div>
      </section>

      {/* FAQ */}
      <section className="px-4 py-24">
        <div className="mx-auto max-w-3xl">
          <h2 className="mb-10 text-center font-display text-3xl font-bold md:text-4xl">Frequently asked questions</h2>
          <div className="space-y-3">
            {faqs.map((f, i) => (
              <div key={f.q} className="rounded-xl border bg-card">
                <button onClick={() => setFaqOpen(faqOpen === i ? -1 : i)} className="flex w-full items-center justify-between px-5 py-4 text-left font-medium">
                  {f.q}
                  <Icon name="chevron-down" className={'h-4 w-4 text-primary transition-transform ' + (faqOpen === i ? 'rotate-180' : '')} />
                </button>
                {faqOpen === i && <p className="px-5 pb-4 text-sm leading-relaxed text-muted-foreground">{f.a}</p>}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="px-4 pb-24">
        <div className="mx-auto max-w-5xl rounded-3xl bg-primary p-12 text-center text-primary-foreground">
          <h2 className="mb-3 font-display text-3xl font-bold md:text-4xl">Final call-to-action headline</h2>
          <p className="mb-7 opacity-85">One sentence of encouragement.</p>
          <Link href="/register" className="inline-block rounded-xl bg-background px-8 py-3.5 font-semibold text-foreground shadow-xl transition hover:opacity-90">Get Started Free</Link>
        </div>
      </section>
    </div>
  );
}
