'use client';
import * as React from 'react';
import { useState } from 'react';
import Link from 'next/link';
import { Icon } from '@/components/ui/icon';

export default function Home() {
  const [faqOpen, setFaqOpen] = useState(-1);
  const hide = (e) => { e.currentTarget.style.display = 'none'; };

  const numbered = [
    { n: '01', img: '/assets/gallery1.jpg', t: 'Pillar one title', d: 'Two sentences describing this pillar of the experience in warm, concrete language.' },
    { n: '02', img: '/assets/gallery2.jpg', t: 'Pillar two title', d: 'Two sentences describing this pillar of the experience in warm, concrete language.' },
    { n: '03', img: '/assets/gallery3.jpg', t: 'Pillar three title', d: 'Two sentences describing this pillar of the experience in warm, concrete language.' },
  ];
  const quotes = [
    { n: 'Full Name', r: 'Role / context', t: 'Two-sentence testimonial in the customer voice.' },
    { n: 'Full Name', r: 'Role / context', t: 'Two-sentence testimonial in the customer voice.' },
  ];
  const tiers = [
    { name: 'Essential', price: 29, popular: false, items: ['Item A', 'Item B', 'Item C', 'Item D'] },
    { name: 'Signature', price: 59, popular: true, items: ['Everything in Essential', 'Item E', 'Item F', 'Item G'] },
    { name: 'Premier', price: 119, popular: false, items: ['Everything in Signature', 'Item H', 'Item I', 'Item J'] },
  ];
  const faqs = [
    { q: 'Question one?', a: 'Two-sentence answer.' },
    { q: 'Question two?', a: 'Two-sentence answer.' },
    { q: 'Question three?', a: 'Two-sentence answer.' },
    { q: 'Question four?', a: 'Two-sentence answer.' },
  ];

  return (
    <div className="w-full bg-stone-50 text-stone-800">
      {/* HERO - editorial split */}
      <section className="pt-20 pb-16 px-4">
        <div className="max-w-7xl mx-auto grid lg:grid-cols-12 gap-10 items-end">
          <div className="lg:col-span-7">
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-ACCENT-600 mb-5">Eyebrow category</p>
            <h1 className="font-display text-5xl md:text-7xl font-bold tracking-tight text-stone-900 leading-[1.02]">
              A huge editorial<br />headline with an<br /><span className="italic text-ACCENT-600">accent word</span>
            </h1>
          </div>
          <div className="lg:col-span-5 lg:pb-3">
            <p className="text-lg text-stone-600 mb-7 max-w-md">Two sentences setting the scene - what this place or product is, and the feeling it promises.</p>
            <div className="flex flex-wrap items-center gap-4">
              <Link href="/register" className="bg-stone-900 hover:bg-stone-800 text-white rounded-full px-7 py-3.5 font-semibold transition">Get Started</Link>
              <Link href="/login" className="inline-flex items-center gap-2 font-semibold text-stone-700 hover:text-ACCENT-600 transition">Sign in <Icon name="arrow-right" className="w-4 h-4" /></Link>
            </div>
          </div>
        </div>
        <div className="max-w-7xl mx-auto mt-12 relative">
          <img src="/assets/hero.jpg" alt="" onError={hide} className="rounded-3xl w-full h-[420px] object-cover shadow-xl" />
          <div className="absolute bottom-6 left-6 bg-white/90 backdrop-blur rounded-2xl px-6 py-4 shadow-lg">
            <p className="font-display text-2xl font-bold text-stone-900">4.9 <span className="text-amber-500">*****</span></p>
            <p className="text-xs text-stone-500">2,300+ verified reviews</p>
          </div>
        </div>
      </section>

      {/* NUMBERED PILLARS */}
      <section className="py-24 px-4">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-end justify-between mb-14 flex-wrap gap-4">
            <h2 className="font-display text-3xl md:text-5xl font-bold text-stone-900 max-w-lg">Section heading about the experience</h2>
            <p className="text-stone-500 max-w-sm">One supporting sentence inviting the visitor to explore.</p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            {numbered.map((c) => (
              <div key={c.n} className="group">
                <div className="overflow-hidden rounded-2xl mb-5">
                  <img src={c.img} alt="" onError={hide} className="h-52 w-full object-cover group-hover:scale-105 transition duration-500" />
                </div>
                <p className="font-display text-4xl font-bold text-stone-200 mb-2">{c.n}</p>
                <h3 className="font-semibold text-xl text-stone-900 mb-2">{c.t}</h3>
                <p className="text-sm text-stone-600 leading-relaxed">{c.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FULL-BLEED BANNER */}
      <section className="px-4 pb-24">
        <div className="max-w-7xl mx-auto relative rounded-3xl overflow-hidden">
          <img src="/assets/banner.jpg" alt="" onError={hide} className="w-full h-80 object-cover" />
          <div className="absolute inset-0 bg-gradient-to-t from-stone-950/80 via-stone-950/20 to-transparent flex items-end">
            <div className="p-10 flex items-end justify-between w-full flex-wrap gap-6">
              <div className="max-w-md">
                <h3 className="font-display text-3xl font-bold text-white mb-2">Banner headline over the photo</h3>
                <p className="text-stone-200 text-sm">One inviting sentence.</p>
              </div>
              <Link href="/register" className="bg-white text-stone-900 hover:bg-stone-100 rounded-full px-7 py-3.5 font-semibold transition">Book / Start now</Link>
            </div>
          </div>
        </div>
      </section>

      {/* STATS strip */}
      <section className="py-16 px-4 bg-stone-900 text-white">
        <div className="max-w-5xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          {[['12+', 'Years running'], ['98%', 'Happy customers'], ['40k', 'Served monthly'], ['15', 'Awards won']].map(([n, l]) => (
            <div key={l}><p className="font-display text-4xl md:text-5xl font-bold text-ACCENT-400">{n}</p><p className="text-sm text-stone-400 mt-1">{l}</p></div>
          ))}
        </div>
      </section>

      {/* SPLIT highlight */}
      <section className="py-24 px-4">
        <div className="max-w-7xl mx-auto grid lg:grid-cols-2 gap-12 items-center">
          <img src="/assets/about1.jpg" alt="" onError={hide} className="rounded-3xl h-96 w-full object-cover shadow-lg" />
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-ACCENT-600 mb-4">Our story</p>
            <h2 className="font-display text-3xl md:text-4xl font-bold text-stone-900 mb-5">Heading about the people behind it</h2>
            <p className="text-stone-600 leading-relaxed mb-6">Three sentences telling the story - the founding idea, the craft, and the promise to the customer.</p>
            <ul className="space-y-3 mb-8">
              {['Selling point one', 'Selling point two', 'Selling point three'].map((s) => (
                <li key={s} className="flex items-center gap-3 text-stone-700"><span className="w-6 h-6 rounded-full bg-ACCENT-100 text-ACCENT-700 flex items-center justify-center"><Icon name="check" className="w-3.5 h-3.5" /></span>{s}</li>
              ))}
            </ul>
            <Link href="/about" className="inline-flex items-center gap-2 font-semibold text-ACCENT-700 hover:text-ACCENT-800">More about us <Icon name="arrow-right" className="w-4 h-4" /></Link>
          </div>
        </div>
      </section>

      {/* TESTIMONIALS - big quotes */}
      <section className="py-20 px-4 bg-stone-100">
        <div className="max-w-5xl mx-auto grid md:grid-cols-2 gap-8">
          {quotes.map((q) => (
            <div key={q.n + q.r} className="rounded-3xl bg-white p-8 shadow-sm border border-stone-200">
              <p className="font-display text-xl text-stone-800 leading-relaxed mb-6">"{q.t}"</p>
              <div className="flex items-center gap-3">
                <div className="w-11 h-11 rounded-full bg-ACCENT-600 text-white flex items-center justify-center font-bold">{String(q.n || '?').charAt(0)}</div>
                <div><p className="font-semibold text-stone-900">{q.n}</p><p className="text-xs text-stone-500">{q.r}</p></div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* PRICING */}
      <section className="py-24 px-4">
        <div className="max-w-7xl mx-auto">
          <h2 className="font-display text-3xl md:text-5xl font-bold text-stone-900 text-center mb-14">Memberships & plans</h2>
          <div className="grid md:grid-cols-3 gap-6 items-start">
            {tiers.map((t) => (
              <div key={t.name} className={'rounded-3xl p-8 ' + (t.popular ? 'bg-stone-900 text-white shadow-2xl relative' : 'bg-white border border-stone-200 shadow-sm')}>
                {t.popular && <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-ACCENT-500 text-white text-xs font-semibold px-3 py-1">Most popular</span>}
                <h3 className="font-semibold text-lg">{t.name}</h3>
                <p className="my-4"><span className="font-display text-4xl font-bold">${t.price}</span><span className={'text-sm ' + (t.popular ? 'text-stone-400' : 'text-stone-500')}>/month</span></p>
                <ul className={'space-y-2.5 text-sm mb-8 ' + (t.popular ? 'text-stone-300' : 'text-stone-600')}>
                  {t.items.map((it) => <li key={it} className="flex items-center gap-2"><Icon name="check" className="w-4 h-4 text-ACCENT-500" />{it}</li>)}
                </ul>
                <Link href="/register" className={'block text-center rounded-full px-5 py-3 font-semibold transition ' + (t.popular ? 'bg-ACCENT-500 hover:bg-ACCENT-400 text-white' : 'bg-stone-900 hover:bg-stone-800 text-white')}>Choose {t.name}</Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="pb-24 px-4">
        <div className="max-w-3xl mx-auto">
          <h2 className="font-display text-3xl md:text-4xl font-bold text-stone-900 text-center mb-12">Good to know</h2>
          <div className="divide-y divide-stone-200 border-y border-stone-200">
            {faqs.map((f, i) => (
              <div key={f.q}>
                <button onClick={() => setFaqOpen(faqOpen === i ? -1 : i)} className="w-full flex items-center justify-between py-5 text-left font-medium text-stone-900">
                  {f.q}
                  <Icon name="chevron-down" className={'w-4 h-4 text-ACCENT-600 transition-transform ' + (faqOpen === i ? 'rotate-180' : '')} />
                </button>
                {faqOpen === i && <p className="pb-5 text-sm text-stone-600 leading-relaxed">{f.a}</p>}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA + FOOTER */}
      <section className="px-4 pb-20">
        <div className="max-w-5xl mx-auto text-center rounded-3xl bg-ACCENT-600 p-12">
          <h2 className="font-display text-3xl md:text-5xl font-bold text-white mb-4">Final call-to-action headline</h2>
          <p className="text-white/85 mb-8">One sentence of warm encouragement.</p>
          <Link href="/register" className="inline-block bg-white text-stone-900 hover:bg-stone-100 rounded-full px-8 py-3.5 font-semibold shadow-xl transition">Get Started</Link>
        </div>
      </section>
      <footer className="border-t border-stone-200 py-12 px-4">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-6">
          <div className="flex items-center gap-2.5">
            <img src="/assets/logo.jpg" alt="" onError={hide} className="h-8 w-8 rounded-lg object-cover" />
            <span className="font-display font-bold text-lg text-stone-900">App Name</span>
          </div>
          <div className="flex gap-6 text-sm text-stone-500">
            <Link href="/features" className="hover:text-stone-800">Features</Link>
            <Link href="/about" className="hover:text-stone-800">About</Link>
            <Link href="/contact" className="hover:text-stone-800">Contact</Link>
            <Link href="/login" className="hover:text-stone-800">Sign in</Link>
          </div>
          <p className="text-xs text-stone-400">(c) 2026 App Name</p>
        </div>
      </footer>
    </div>
  );
}
