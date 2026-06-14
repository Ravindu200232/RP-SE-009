function Home() {
  const { useState } = React;
  const { Link } = ReactRouterDOM;
  const { Icon } = window;
  const [faqOpen, setFaqOpen] = useState(-1);
  const [email, setEmail] = useState('');
  const [subscribed, setSubscribed] = useState(false);
  const hide = (e) => { e.currentTarget.style.display = 'none'; };

  const features = [
    { icon: 'zap', title: 'Feature one', text: 'One sentence about this capability and the benefit it brings.' },
    { icon: 'shield', title: 'Feature two', text: 'One sentence about this capability and the benefit it brings.' },
    { icon: 'chart', title: 'Feature three', text: 'One sentence about this capability and the benefit it brings.' },
    { icon: 'users', title: 'Feature four', text: 'One sentence about this capability and the benefit it brings.' },
    { icon: 'clock', title: 'Feature five', text: 'One sentence about this capability and the benefit it brings.' },
    { icon: 'star', title: 'Feature six', text: 'One sentence about this capability and the benefit it brings.' },
  ];
  const steps = [
    { n: '01', t: 'Step one title', d: 'Two short sentences describing this step of the journey.' },
    { n: '02', t: 'Step two title', d: 'Two short sentences describing this step of the journey.' },
    { n: '03', t: 'Step three title', d: 'Two short sentences describing this step of the journey.' },
  ];
  const tiers = [
    { name: 'Starter', price: 0, popular: false, items: ['Item A', 'Item B', 'Item C', 'Item D'] },
    { name: 'Professional', price: 39, popular: true, items: ['Everything in Starter', 'Item E', 'Item F', 'Item G', 'Item H'] },
    { name: 'Enterprise', price: 89, popular: false, items: ['Everything in Pro', 'Item I', 'Item J', 'Item K'] },
  ];
  const quotes = [
    { n: 'Full Name', r: 'Role, Company', t: 'Two-sentence testimonial about the concrete result they achieved.' },
    { n: 'Full Name', r: 'Role, Company', t: 'Two-sentence testimonial about the concrete result they achieved.' },
    { n: 'Full Name', r: 'Role, Company', t: 'Two-sentence testimonial about the concrete result they achieved.' },
  ];
  const faqs = [
    { q: 'Question one?', a: 'Two-sentence answer with a concrete detail.' },
    { q: 'Question two?', a: 'Two-sentence answer with a concrete detail.' },
    { q: 'Question three?', a: 'Two-sentence answer with a concrete detail.' },
    { q: 'Question four?', a: 'Two-sentence answer with a concrete detail.' },
    { q: 'Question five?', a: 'Two-sentence answer with a concrete detail.' },
  ];

  return (
    <div className="w-full bg-white text-slate-800">
      {/* HERO */}
      <section className="relative pt-20 pb-24 px-4 overflow-hidden">
        <div className="absolute top-0 right-0 w-[480px] h-[480px] rounded-full bg-ACCENT-100 blur-3xl -z-0 opacity-70 pointer-events-none"></div>
        <div className="relative max-w-7xl mx-auto grid lg:grid-cols-2 gap-14 items-center">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-ACCENT-200 bg-ACCENT-50 px-3 py-1 text-xs font-semibold text-ACCENT-700 mb-6">
              <span className="w-2 h-2 rounded-full bg-ACCENT-500 animate-pulse"></span> New: announcement text
            </div>
            <h1 className="font-display text-5xl md:text-6xl font-bold tracking-tight text-slate-900 leading-[1.08] mb-6">
              Headline with an <span className="text-ACCENT-600">accent phrase</span> in it
            </h1>
            <p className="text-lg text-slate-600 max-w-xl mb-9">Two sentences explaining what the product does and who it is for, in plain confident language.</p>
            <div className="flex flex-wrap gap-4 mb-9">
              <Link to="/register" className="bg-ACCENT-600 hover:bg-ACCENT-700 text-white rounded-xl px-7 py-3.5 font-semibold shadow-lg shadow-ACCENT-600/25 transition">Get Started Free</Link>
              <Link to="/login" className="border border-slate-200 hover:border-slate-300 hover:bg-slate-50 text-slate-700 rounded-xl px-7 py-3.5 font-semibold transition">Sign in</Link>
            </div>
            <div className="flex items-center gap-6 text-sm text-slate-500">
              <span className="flex items-center gap-1.5"><Icon name="check" className="w-4 h-4 text-ACCENT-600" /> No credit card</span>
              <span className="flex items-center gap-1.5"><Icon name="check" className="w-4 h-4 text-ACCENT-600" /> Free 14-day trial</span>
            </div>
          </div>
          <div className="relative">
            <img src="assets/hero.jpg" alt="" onError={hide} className="rounded-3xl shadow-2xl border border-slate-100 w-full object-cover" />
            <div className="absolute -bottom-6 -left-6 bg-white rounded-2xl shadow-xl border border-slate-100 px-5 py-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-ACCENT-100 text-ACCENT-600 flex items-center justify-center"><Icon name="chart" className="w-5 h-5" /></div>
                <div><p className="text-xs text-slate-500">This month</p><p className="font-bold text-slate-900">+2,340 records</p></div>
              </div>
            </div>
            <div className="absolute -top-5 -right-5 bg-white rounded-2xl shadow-xl border border-slate-100 px-4 py-3 flex items-center gap-2">
              <div className="flex -space-x-2">{['A', 'B', 'C'].map((c) => <div key={c} className="w-7 h-7 rounded-full bg-ACCENT-500 border-2 border-white text-white text-[10px] font-bold flex items-center justify-center">{c}</div>)}</div>
              <p className="text-xs font-semibold text-slate-700">+10k users</p>
            </div>
          </div>
        </div>
      </section>

      {/* LOGOS */}
      <section className="py-9 border-y border-slate-100 bg-slate-50/60">
        <div className="max-w-7xl mx-auto px-4">
          <p className="text-center text-xs uppercase tracking-widest text-slate-400 mb-5">Trusted by teams at</p>
          <div className="flex flex-wrap items-center justify-center gap-x-12 gap-y-3 text-slate-400 font-bold tracking-wide">
            {['BRANDONE', 'NORTHLY', 'VERTEX', 'OPALCO', 'LUMINA', 'KITEWORK'].map((b) => <span key={b}>{b}</span>)}
          </div>
        </div>
      </section>

      {/* FEATURES */}
      <section className="py-24 px-4">
        <div className="max-w-7xl mx-auto">
          <div className="max-w-2xl mx-auto text-center mb-14">
            <p className="text-xs font-semibold uppercase tracking-widest text-ACCENT-600 mb-3">Features</p>
            <h2 className="font-display text-3xl md:text-5xl font-bold text-slate-900 mb-4">Section heading about what you get</h2>
            <p className="text-slate-600">One supporting sentence for this section.</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((f) => (
              <div key={f.title} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition">
                <div className="w-11 h-11 rounded-xl bg-ACCENT-50 text-ACCENT-600 flex items-center justify-center mb-4"><Icon name={f.icon} className="w-5 h-5" /></div>
                <h3 className="font-semibold text-slate-900 text-lg mb-1.5">{f.title}</h3>
                <p className="text-sm text-slate-600 leading-relaxed">{f.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* HOW IT WORKS + image band */}
      <section className="py-20 px-4 bg-slate-50">
        <div className="max-w-7xl mx-auto">
          <h2 className="font-display text-3xl md:text-4xl font-bold text-slate-900 text-center mb-14">How it works</h2>
          <div className="grid md:grid-cols-3 gap-8 mb-16">
            {steps.map((s) => (
              <div key={s.n} className="relative rounded-2xl bg-white border border-slate-200 p-7 shadow-sm">
                <span className="font-display text-5xl font-bold text-ACCENT-100 absolute top-4 right-6">{s.n}</span>
                <div className="w-10 h-10 rounded-full bg-ACCENT-600 text-white flex items-center justify-center font-bold mb-4">{s.n.slice(1)}</div>
                <h3 className="font-semibold text-slate-900 mb-1.5">{s.t}</h3>
                <p className="text-sm text-slate-600">{s.d}</p>
              </div>
            ))}
          </div>
          <div className="grid md:grid-cols-2 gap-6">
            <img src="assets/feature.jpg" alt="" onError={hide} className="rounded-3xl h-64 w-full object-cover shadow-md" />
            <img src="assets/gallery1.jpg" alt="" onError={hide} className="rounded-3xl h-64 w-full object-cover shadow-md" />
          </div>
        </div>
      </section>

      {/* STATS */}
      <section className="py-20 px-4">
        <div className="max-w-5xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          {[['10k+', 'Active users'], ['99.9%', 'Uptime SLA'], ['4.9/5', 'Average rating'], ['150+', 'Integrations']].map(([n, l]) => (
            <div key={l}><p className="font-display text-4xl md:text-5xl font-bold text-ACCENT-600">{n}</p><p className="text-sm text-slate-500 mt-1">{l}</p></div>
          ))}
        </div>
      </section>

      {/* BENEFITS + photos */}
      <section className="py-20 px-4">
        <div className="max-w-7xl mx-auto grid lg:grid-cols-2 gap-12 items-center">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-ACCENT-600 mb-3">Why teams switch</p>
            <h2 className="font-display text-3xl md:text-4xl font-bold text-slate-900 mb-5">Benefits heading goes here</h2>
            <p className="text-slate-600 leading-relaxed mb-7">Two sentences on the overall benefit story for this audience.</p>
            <ul className="space-y-3.5">
              {['Benefit point one', 'Benefit point two', 'Benefit point three', 'Benefit point four', 'Benefit point five'].map((b) => (
                <li key={b} className="flex items-center gap-3 text-slate-700">
                  <span className="w-6 h-6 rounded-full bg-ACCENT-100 text-ACCENT-700 flex items-center justify-center shrink-0"><Icon name="check" className="w-3.5 h-3.5" /></span>{b}
                </li>
              ))}
            </ul>
          </div>
          <div className="grid grid-cols-2 gap-5">
            <img src="assets/gallery2.jpg" alt="" onError={hide} className="rounded-2xl h-72 w-full object-cover shadow-md mt-8" />
            <img src="assets/gallery3.jpg" alt="" onError={hide} className="rounded-2xl h-72 w-full object-cover shadow-md" />
          </div>
        </div>
      </section>

      {/* BANNER */}
      <section className="px-4 pb-4">
        <div className="max-w-7xl mx-auto relative rounded-3xl overflow-hidden">
          <img src="assets/banner.jpg" alt="" onError={hide} className="w-full h-64 object-cover" />
          <div className="absolute inset-0 bg-gradient-to-r from-slate-900/80 to-transparent flex items-center">
            <div className="p-10 max-w-md">
              <h3 className="font-display text-2xl md:text-3xl font-bold text-white mb-2">Banner headline</h3>
              <p className="text-slate-200 text-sm">One supporting sentence over the photo.</p>
            </div>
          </div>
        </div>
      </section>

      {/* TESTIMONIALS */}
      <section className="py-24 px-4 bg-slate-50">
        <div className="max-w-7xl mx-auto">
          <h2 className="font-display text-3xl md:text-4xl font-bold text-slate-900 text-center mb-14">Loved by professionals</h2>
          <div className="grid md:grid-cols-3 gap-6">
            {quotes.map((q) => (
              <div key={q.n + q.r} className="rounded-2xl bg-white border border-slate-200 p-6 shadow-sm">
                <div className="flex gap-1 text-amber-400 mb-4">{[0, 1, 2, 3, 4].map((i) => <Icon key={i} name="star" className="w-4 h-4" />)}</div>
                <p className="text-slate-700 leading-relaxed mb-6">"{q.t}"</p>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-ACCENT-600 text-white flex items-center justify-center font-bold">{String(q.n || '?').charAt(0)}</div>
                  <div><p className="font-semibold text-sm text-slate-900">{q.n}</p><p className="text-xs text-slate-500">{q.r}</p></div>
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
            <h2 className="font-display text-3xl md:text-5xl font-bold text-slate-900 mb-3">Plans for every team</h2>
            <p className="text-slate-600">One sentence about pricing philosophy.</p>
          </div>
          <div className="grid md:grid-cols-3 gap-6 items-start">
            {tiers.map((t) => (
              <div key={t.name} className={'rounded-2xl border p-7 bg-white ' + (t.popular ? 'border-ACCENT-300 ring-2 ring-ACCENT-500 shadow-xl relative' : 'border-slate-200 shadow-sm')}>
                {t.popular && <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-ACCENT-600 text-white text-xs font-semibold px-3 py-1">Most popular</span>}
                <h3 className="font-semibold text-slate-900 text-lg">{t.name}</h3>
                <p className="my-4"><span className="font-display text-4xl font-bold text-slate-900">${t.price}</span><span className="text-slate-500 text-sm">/month</span></p>
                <ul className="space-y-2.5 text-sm text-slate-600 mb-7">
                  {t.items.map((it) => <li key={it} className="flex items-center gap-2"><Icon name="check" className="w-4 h-4 text-ACCENT-600" />{it}</li>)}
                </ul>
                <Link to="/register" className={'block text-center rounded-xl px-5 py-3 font-semibold transition ' + (t.popular ? 'bg-ACCENT-600 hover:bg-ACCENT-700 text-white' : 'border border-slate-200 hover:bg-slate-50 text-slate-700')}>Choose {t.name}</Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-20 px-4 bg-slate-50">
        <div className="max-w-3xl mx-auto">
          <h2 className="font-display text-3xl md:text-4xl font-bold text-slate-900 text-center mb-12">Frequently asked questions</h2>
          <div className="space-y-3">
            {faqs.map((f, i) => (
              <div key={f.q} className="rounded-xl bg-white border border-slate-200">
                <button onClick={() => setFaqOpen(faqOpen === i ? -1 : i)} className="w-full flex items-center justify-between px-5 py-4 text-left font-medium text-slate-900">
                  {f.q}
                  <Icon name="chevron-down" className={'w-4 h-4 text-ACCENT-600 transition-transform ' + (faqOpen === i ? 'rotate-180' : '')} />
                </button>
                {faqOpen === i && <p className="px-5 pb-4 text-sm text-slate-600 leading-relaxed">{f.a}</p>}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* NEWSLETTER CTA */}
      <section className="py-24 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="font-display text-3xl md:text-5xl font-bold text-slate-900 mb-4">Final call-to-action headline</h2>
          <p className="text-slate-600 mb-8 max-w-xl mx-auto">One sentence of encouragement to join.</p>
          {subscribed ? (
            <p className="inline-flex items-center gap-2 text-ACCENT-700 bg-ACCENT-50 border border-ACCENT-200 rounded-xl px-5 py-3 font-medium"><Icon name="check" className="w-5 h-5" /> Thanks - you're on the list!</p>
          ) : (
            <form onSubmit={(e) => { e.preventDefault(); if (email.trim()) setSubscribed(true); }} className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto">
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Work email" className="flex-1 bg-white border border-slate-300 rounded-xl px-4 py-3 text-slate-900 placeholder-slate-400 focus:ring-2 focus:ring-ACCENT-500 focus:outline-none" />
              <button type="submit" className="bg-ACCENT-600 hover:bg-ACCENT-700 text-white rounded-xl px-6 py-3 font-semibold transition">Get started</button>
            </form>
          )}
        </div>
      </section>

      {/* FOOTER */}
      <footer className="border-t border-slate-200 py-14 px-4 bg-slate-50">
        <div className="max-w-7xl mx-auto grid md:grid-cols-4 gap-10">
          <div>
            <div className="flex items-center gap-2.5 mb-3">
              <img src="assets/logo.jpg" alt="" onError={hide} className="h-8 w-8 rounded-lg object-cover" />
              <span className="font-display font-bold text-lg text-slate-900">App Name</span>
            </div>
            <p className="text-sm text-slate-500">One-line app description.</p>
          </div>
          <div><p className="font-semibold mb-3 text-sm text-slate-900">Product</p><div className="space-y-2 text-sm text-slate-500"><Link to="/features" className="block hover:text-slate-800">Features</Link><Link to="/about" className="block hover:text-slate-800">About</Link><Link to="/contact" className="block hover:text-slate-800">Contact</Link></div></div>
          <div><p className="font-semibold mb-3 text-sm text-slate-900">Account</p><div className="space-y-2 text-sm text-slate-500"><Link to="/login" className="block hover:text-slate-800">Sign in</Link><Link to="/register" className="block hover:text-slate-800">Get started</Link></div></div>
          <div><p className="font-semibold mb-3 text-sm text-slate-900">Contact</p><p className="text-sm text-slate-500">hello@example.com<br />+1 (555) 010-2030</p></div>
        </div>
        <p className="text-center text-xs text-slate-400 mt-10">(c) 2026 App Name. All rights reserved.</p>
      </footer>
    </div>
  );
}
window.Home = Home;
