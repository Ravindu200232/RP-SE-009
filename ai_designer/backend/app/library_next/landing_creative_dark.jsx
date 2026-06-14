'use client';
import * as React from 'react';
import { useState } from 'react';
import Link from 'next/link';
import { Icon } from '@/components/ui/icon';

export default function Home() {
  const [faqOpen, setFaqOpen] = useState(-1);
  const hide = (e) => { e.currentTarget.style.display = 'none'; };

  const features = [
    { icon: 'zap', title: 'Feature one', text: 'One sentence about this capability.' },
    { icon: 'shield', title: 'Feature two', text: 'One sentence about this capability.' },
    { icon: 'chart', title: 'Feature three', text: 'One sentence about this capability.' },
    { icon: 'users', title: 'Feature four', text: 'One sentence about this capability.' },
    { icon: 'clock', title: 'Feature five', text: 'One sentence about this capability.' },
    { icon: 'star', title: 'Feature six', text: 'One sentence about this capability.' },
  ];
  const stats = [['10k+', 'Customers'], ['99.9%', 'Uptime'], ['4.9/5', 'Avg rating'], ['24/7', 'Support']];
  const tiers = [
    { name: 'Starter', price: 19, popular: false, items: ['Item A', 'Item B', 'Item C', 'Item D'] },
    { name: 'Professional', price: 49, popular: true, items: ['Everything in Starter', 'Item E', 'Item F', 'Item G', 'Item H'] },
    { name: 'Enterprise', price: 99, popular: false, items: ['Everything in Pro', 'Item I', 'Item J', 'Item K'] },
  ];
  const faqs = [
    { q: 'Question one?', a: 'Two-sentence answer.' },
    { q: 'Question two?', a: 'Two-sentence answer.' },
    { q: 'Question three?', a: 'Two-sentence answer.' },
    { q: 'Question four?', a: 'Two-sentence answer.' },
    { q: 'Question five?', a: 'Two-sentence answer.' },
  ];
  const quotes = [
    { n: 'Full Name', r: 'Role, Company', t: 'Two-sentence testimonial quote.' },
    { n: 'Full Name', r: 'Role, Company', t: 'Two-sentence testimonial quote.' },
    { n: 'Full Name', r: 'Role, Company', t: 'Two-sentence testimonial quote.' },
  ];

  return (
    <div className="w-full bg-slate-950 text-slate-100 overflow-hidden">
      {/* HERO */}
      <section className="relative pt-24 pb-20 px-4">
        <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[640px] h-[640px] rounded-full bg-ACCENT-600/20 blur-3xl -z-0 pointer-events-none"></div>
        <div className="relative max-w-7xl mx-auto grid lg:grid-cols-2 gap-12 items-center">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-ACCENT-400/30 bg-ACCENT-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-ACCENT-300 mb-6">
              <Icon name="zap" className="w-3.5 h-3.5" /> Tagline category
            </div>
            <h1 className="font-display text-5xl md:text-7xl font-bold tracking-tight leading-[1.05] mb-6">
              Headline part <span className="text-transparent bg-clip-text bg-gradient-to-r from-ACCENT-400 to-ACCENT-200">accent words</span> here
            </h1>
            <p className="text-lg text-slate-400 max-w-xl mb-10">One or two sentences describing the product value for the target user.</p>
            <div className="flex flex-wrap items-center gap-4">
              <Link href="/register" className="bg-ACCENT-600 hover:bg-ACCENT-500 text-white rounded-xl px-7 py-3.5 font-semibold shadow-lg shadow-ACCENT-600/30 transition">Get Started Free</Link>
              <Link href="/login" className="inline-flex items-center gap-2 text-slate-300 hover:text-white font-medium px-4 py-3.5 transition">Sign in <Icon name="arrow-right" className="w-4 h-4" /></Link>
            </div>
            <div className="mt-10 flex items-center gap-3 text-sm text-slate-500">
              <div className="flex -space-x-2">
                {['A', 'B', 'C', 'D'].map((c) => (
                  <div key={c} className="w-8 h-8 rounded-full bg-gradient-to-br from-ACCENT-500 to-ACCENT-700 border-2 border-slate-950 flex items-center justify-center text-[10px] font-bold text-white">{c}</div>
                ))}
              </div>
              Loved by 10,000+ teams
            </div>
          </div>
          <div className="relative">
            <div className="absolute inset-0 bg-gradient-to-tr from-ACCENT-600/30 to-transparent rounded-3xl blur-2xl -z-0"></div>
            <img src="/assets/hero.jpg" alt="" onError={hide} className="relative rounded-3xl border border-white/10 shadow-2xl w-full object-cover" />
            <div className="absolute -bottom-5 -left-5 bg-slate-900/90 backdrop-blur border border-white/10 rounded-2xl px-5 py-3 shadow-xl">
              <p className="text-xs text-slate-400">Live metric</p>
              <p className="text-xl font-bold text-ACCENT-300">+128%</p>
            </div>
          </div>
        </div>
      </section>

      {/* LOGOS */}
      <section className="py-10 border-y border-white/5">
        <div className="max-w-7xl mx-auto px-4 flex flex-wrap items-center justify-center gap-x-12 gap-y-4 text-slate-600 font-semibold tracking-wide">
          {['BRANDONE', 'NORTHLY', 'VERTEX', 'OPALCO', 'LUMINA'].map((b) => <span key={b} className="hover:text-slate-400 transition">{b}</span>)}
        </div>
      </section>

      {/* FEATURES bento */}
      <section className="py-24 px-4">
        <div className="max-w-7xl mx-auto">
          <div className="max-w-2xl mx-auto text-center mb-14">
            <p className="text-xs font-semibold uppercase tracking-widest text-ACCENT-400 mb-3">Why us</p>
            <h2 className="font-display text-3xl md:text-5xl font-bold mb-4">Section heading about capabilities</h2>
            <p className="text-slate-400">One supporting sentence for this section.</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((f) => (
              <div key={f.title} className="group rounded-2xl border border-white/10 bg-white/[0.03] p-6 hover:bg-white/[0.06] hover:border-ACCENT-400/30 transition">
                <div className="w-11 h-11 rounded-xl bg-ACCENT-500/15 text-ACCENT-300 flex items-center justify-center mb-4 group-hover:scale-110 transition"><Icon name={f.icon} className="w-5 h-5" /></div>
                <h3 className="font-semibold text-lg mb-1.5">{f.title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{f.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section className="py-20 px-4 border-y border-white/5 bg-white/[0.02]">
        <div className="max-w-7xl mx-auto">
          <h2 className="font-display text-3xl md:text-4xl font-bold text-center mb-14">How it works</h2>
          <div className="grid md:grid-cols-3 gap-8">
            {[
              { n: '1', t: 'Step one title', d: 'Two sentences describing the first step of the journey.' },
              { n: '2', t: 'Step two title', d: 'Two sentences describing the second step of the journey.' },
              { n: '3', t: 'Step three title', d: 'Two sentences describing the third step of the journey.' },
            ].map((s) => (
              <div key={s.n} className="relative rounded-2xl border border-white/10 bg-white/[0.03] p-7">
                <div className="w-10 h-10 rounded-full bg-ACCENT-600 text-white flex items-center justify-center font-bold mb-4">{s.n}</div>
                <h3 className="font-semibold text-lg mb-1.5">{s.t}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{s.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* GALLERY */}
      <section className="py-10 px-4">
        <div className="max-w-7xl mx-auto grid md:grid-cols-3 gap-6">
          <img src="/assets/gallery1.jpg" alt="" onError={hide} className="rounded-2xl border border-white/10 h-56 w-full object-cover" />
          <img src="/assets/gallery2.jpg" alt="" onError={hide} className="rounded-2xl border border-white/10 h-56 w-full object-cover" />
          <img src="/assets/gallery3.jpg" alt="" onError={hide} className="rounded-2xl border border-white/10 h-56 w-full object-cover" />
        </div>
      </section>

      {/* STATS */}
      <section className="py-20 px-4">
        <div className="max-w-5xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          {stats.map(([n, l]) => (
            <div key={l}><p className="font-display text-4xl md:text-5xl font-bold text-ACCENT-300">{n}</p><p className="text-sm text-slate-500 mt-1">{l}</p></div>
          ))}
        </div>
      </section>

      {/* BANNER */}
      <section className="px-4 pb-24">
        <div className="max-w-7xl mx-auto relative rounded-3xl overflow-hidden">
          <img src="/assets/banner.jpg" alt="" onError={hide} className="w-full h-72 object-cover" />
          <div className="absolute inset-0 bg-gradient-to-r from-slate-950/90 to-transparent flex items-center">
            <div className="p-10 max-w-md">
              <h3 className="font-display text-2xl md:text-3xl font-bold mb-2">Banner headline</h3>
              <p className="text-slate-300 text-sm">One supporting sentence over the photo.</p>
            </div>
          </div>
        </div>
      </section>

      {/* TESTIMONIALS */}
      <section className="py-24 px-4 bg-white/[0.02] border-y border-white/5">
        <div className="max-w-7xl mx-auto">
          <h2 className="font-display text-3xl md:text-4xl font-bold text-center mb-14">What customers say</h2>
          <div className="grid md:grid-cols-3 gap-6">
            {quotes.map((q) => (
              <div key={q.n + q.r} className="rounded-2xl border border-white/10 bg-slate-900/60 p-6">
                <div className="flex gap-1 text-ACCENT-400 mb-4">{[0, 1, 2, 3, 4].map((i) => <Icon key={i} name="star" className="w-4 h-4" />)}</div>
                <p className="text-slate-300 leading-relaxed mb-6">"{q.t}"</p>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-ACCENT-500 to-ACCENT-700 flex items-center justify-center font-bold text-white">{String(q.n || '?').charAt(0)}</div>
                  <div><p className="font-semibold text-sm">{q.n}</p><p className="text-xs text-slate-500">{q.r}</p></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* PRICING */}
      <section className="py-24 px-4">
        <div className="max-w-7xl mx-auto">
          <div className="max-w-2xl mx-auto text-center mb-14">
            <h2 className="font-display text-3xl md:text-5xl font-bold mb-3">Simple pricing</h2>
            <p className="text-slate-400">One sentence about pricing philosophy.</p>
          </div>
          <div className="grid md:grid-cols-3 gap-6 items-start">
            {tiers.map((t) => (
              <div key={t.name} className={'rounded-2xl border p-7 ' + (t.popular ? 'border-ACCENT-400/50 bg-ACCENT-500/[0.07] ring-1 ring-ACCENT-400/40 relative' : 'border-white/10 bg-white/[0.03]')}>
                {t.popular && <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-ACCENT-500 text-white text-xs font-semibold px-3 py-1">Most popular</span>}
                <h3 className="font-semibold text-lg">{t.name}</h3>
                <p className="my-4"><span className="font-display text-4xl font-bold">${t.price}</span><span className="text-slate-500 text-sm">/month</span></p>
                <ul className="space-y-2.5 text-sm text-slate-300 mb-7">
                  {t.items.map((it) => <li key={it} className="flex items-center gap-2"><Icon name="check" className="w-4 h-4 text-ACCENT-400" />{it}</li>)}
                </ul>
                <Link href="/register" className={'block text-center rounded-xl px-5 py-3 font-semibold transition ' + (t.popular ? 'bg-ACCENT-600 hover:bg-ACCENT-500 text-white' : 'border border-white/15 hover:bg-white/5 text-slate-200')}>Choose {t.name}</Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-24 px-4 max-w-3xl mx-auto">
        <h2 className="font-display text-3xl md:text-4xl font-bold text-center mb-12">Frequently asked questions</h2>
        <div className="space-y-3">
          {faqs.map((f, i) => (
            <div key={f.q} className="rounded-xl border border-white/10 bg-white/[0.03]">
              <button onClick={() => setFaqOpen(faqOpen === i ? -1 : i)} className="w-full flex items-center justify-between px-5 py-4 text-left font-medium">
                {f.q}
                <Icon name="chevron-down" className={'w-4 h-4 text-ACCENT-400 transition-transform ' + (faqOpen === i ? 'rotate-180' : '')} />
              </button>
              {faqOpen === i && <p className="px-5 pb-4 text-sm text-slate-400 leading-relaxed">{f.a}</p>}
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="px-4 pb-24">
        <div className="max-w-5xl mx-auto rounded-3xl bg-gradient-to-r from-ACCENT-700 to-ACCENT-500 p-12 text-center relative overflow-hidden">
          <div className="absolute -top-20 -right-20 w-64 h-64 rounded-full bg-white/10 blur-2xl"></div>
          <h2 className="font-display text-3xl md:text-5xl font-bold text-white mb-4">Final call-to-action headline</h2>
          <p className="text-white/80 mb-8 max-w-xl mx-auto">One sentence of encouragement.</p>
          <Link href="/register" className="inline-block bg-white text-slate-900 hover:bg-slate-100 rounded-xl px-8 py-3.5 font-semibold shadow-xl transition">Start now - it's free</Link>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="border-t border-white/10 py-14 px-4">
        <div className="max-w-7xl mx-auto grid md:grid-cols-4 gap-10">
          <div>
            <div className="flex items-center gap-2.5 mb-3">
              <img src="/assets/logo.jpg" alt="" onError={hide} className="h-8 w-8 rounded-lg object-cover" />
              <span className="font-display font-bold text-lg">App Name</span>
            </div>
            <p className="text-sm text-slate-500">One-line app description.</p>
          </div>
          <div><p className="font-semibold mb-3 text-sm">Product</p><div className="space-y-2 text-sm text-slate-500"><Link href="/features" className="block hover:text-slate-300">Features</Link><Link href="/about" className="block hover:text-slate-300">About</Link><Link href="/contact" className="block hover:text-slate-300">Contact</Link></div></div>
          <div><p className="font-semibold mb-3 text-sm">Account</p><div className="space-y-2 text-sm text-slate-500"><Link href="/login" className="block hover:text-slate-300">Sign in</Link><Link href="/register" className="block hover:text-slate-300">Get started</Link></div></div>
          <div><p className="font-semibold mb-3 text-sm">Contact</p><p className="text-sm text-slate-500">hello@example.com<br />+1 (555) 010-2030</p></div>
        </div>
        <p className="text-center text-xs text-slate-600 mt-10">(c) 2026 App Name. All rights reserved.</p>
      </footer>
    </div>
  );
}
