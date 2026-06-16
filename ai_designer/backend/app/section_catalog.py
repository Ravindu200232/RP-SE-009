"""Section catalog — 100+ composable section/block templates.

Each FAMILY is one distinct layout (features grid, stats band, pricing, FAQ,
timeline, bento, ...). Every family is rendered in several TONES (light / soft /
dark / accent), so one family yields multiple visually-distinct templates. The
CATALOG is the flat list of (family x tone) entries — 100+ of them — each tagged
with the project kinds it suits.

Selection ("my recommended method") = input-tag match + anti-repeat randomness:
`pick_middles()` scores every entry against the user's prompt tags and samples a
varied subset, so no two generated apps assemble the same page.

Contract that keeps any combination valid JSX:
- render() returns a complete `function <UniqueName>() { ... }`; all data lives in
  FUNCTION-SCOPED consts, so concatenating 100 of them never collides.
- only the shared header (React/useState/Link/Icon) is imported once by the composer.
- only tokens proven to compile are used (Tailwind ignores unknown classes, so the
  build can never break on styling — only on syntax, which we validate).
"""
import random

# tone = the recolouring applied to a section's shell, cards, text and eyebrow.
TONES = {
    "light":  {"sec": "bg-background text-foreground",        "card": "bg-card border",                    "muted": "text-muted-foreground",        "eye": "text-primary",                    "head": "text-foreground"},
    "soft":   {"sec": "bg-muted/40 text-foreground",          "card": "bg-background border",               "muted": "text-muted-foreground",        "eye": "text-primary",                    "head": "text-foreground"},
    "dark":   {"sec": "bg-slate-900 text-white",              "card": "bg-white/5 border border-white/10", "muted": "text-slate-300",               "eye": "text-primary",                    "head": "text-white"},
    "accent": {"sec": "bg-primary text-primary-foreground",   "card": "bg-white/10 border border-white/20","muted": "text-primary-foreground/80",   "eye": "text-primary-foreground/70",      "head": "text-primary-foreground"},
}


def _fill(tpl: str, name: str, t: dict) -> str:
    return (tpl.replace("__NAME__", name).replace("__SEC__", t["sec"]).replace("__CARD__", t["card"])
            .replace("__MUTED__", t["muted"]).replace("__EYE__", t["eye"]).replace("__HEAD__", t["head"]))


# ---- families (each a distinct, self-contained <section>) --------------------
F = {}

F["features_grid"] = """function __NAME__() {
  const items = [
    { icon: 'zap', title: 'Fast by default', text: 'Everything is tuned for speed so your team never waits on the tools.' },
    { icon: 'shield', title: 'Secure & private', text: 'Role-based access and encryption keep sensitive data exactly where it belongs.' },
    { icon: 'chart', title: 'Clear insight', text: 'Live dashboards turn raw activity into decisions you can act on today.' },
    { icon: 'users', title: 'Built for teams', text: 'Shared workspaces, comments and handoffs that keep everyone aligned.' },
    { icon: 'clock', title: 'Save hours weekly', text: 'Automations handle the busywork so people focus on what matters.' },
    { icon: 'sparkles', title: 'Delightful UX', text: 'A clean, modern interface your whole organisation actually enjoys using.' },
  ];
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-7xl">
        <div className="mx-auto mb-14 max-w-2xl text-center">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest __EYE__">Capabilities</p>
          <h2 className="font-display text-3xl font-bold md:text-5xl __HEAD__">Everything you need in one place</h2>
        </div>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((f) => (
            <div key={f.title} className="__CARD__ rounded-2xl p-6 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
              <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary"><Icon name={f.icon} className="h-5 w-5" /></div>
              <h3 className="mb-1.5 text-lg font-semibold __HEAD__">{f.title}</h3>
              <p className="text-sm leading-relaxed __MUTED__">{f.text}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}"""

F["value_props"] = """function __NAME__() {
  const points = ['No setup fees or hidden costs', 'Cancel anytime, keep your data', 'Onboarding in under ten minutes', 'Friendly human support 24/7', 'Works on every device', 'Free updates, forever'];
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2">
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest __EYE__">Why us</p>
          <h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">A simpler way to run the day to day</h2>
          <p className="mt-4 __MUTED__">Replace the patchwork of spreadsheets and tabs with one calm, dependable workspace.</p>
        </div>
        <ul className="grid gap-3 sm:grid-cols-2">
          {points.map((p) => (
            <li key={p} className="__CARD__ flex items-start gap-3 rounded-xl p-4">
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary"><Icon name="check" className="h-4 w-4" /></span>
              <span className="text-sm __HEAD__">{p}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}"""

F["stats_band"] = """function __NAME__() {
  const stats = [{ n: '12k+', l: 'Active users' }, { n: '99.9%', l: 'Uptime' }, { n: '4.9/5', l: 'Avg rating' }, { n: '40+', l: 'Countries' }];
  return (
    <section className="__SEC__ px-4 py-20 md:px-6">
      <div className="mx-auto max-w-6xl">
        <div className="grid gap-8 text-center sm:grid-cols-2 lg:grid-cols-4">
          {stats.map((s) => (
            <div key={s.l}>
              <div className="font-display text-4xl font-extrabold md:text-5xl __HEAD__">{s.n}</div>
              <div className="mt-2 text-sm uppercase tracking-wide __MUTED__">{s.l}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}"""

F["logos_strip"] = """function __NAME__() {
  const names = ['Northwind', 'Acme Co', 'Lumen', 'Vertex', 'Helios', 'Cobalt'];
  return (
    <section className="__SEC__ px-4 py-16 md:px-6">
      <div className="mx-auto max-w-6xl text-center">
        <p className="mb-8 text-xs font-semibold uppercase tracking-widest __MUTED__">Trusted by teams everywhere</p>
        <div className="flex flex-wrap items-center justify-center gap-x-12 gap-y-6">
          {names.map((n) => (<span key={n} className="font-display text-xl font-bold opacity-60 __HEAD__">{n}</span>))}
        </div>
      </div>
    </section>
  );
}"""

F["steps"] = """function __NAME__() {
  const steps = [
    { n: '01', title: 'Create your account', text: 'Sign up in seconds — no credit card required to get started.' },
    { n: '02', title: 'Set things up', text: 'Import your data or start fresh with a guided, friendly setup.' },
    { n: '03', title: 'Go live', text: 'Invite your team and watch everything click into place.' },
  ];
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-6xl">
        <div className="mb-14 max-w-2xl">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest __EYE__">How it works</p>
          <h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">Up and running in three steps</h2>
        </div>
        <div className="grid gap-8 md:grid-cols-3">
          {steps.map((s) => (
            <div key={s.n} className="__CARD__ rounded-2xl p-7">
              <div className="font-display text-4xl font-extrabold text-primary">{s.n}</div>
              <h3 className="mt-4 text-lg font-semibold __HEAD__">{s.title}</h3>
              <p className="mt-2 text-sm leading-relaxed __MUTED__">{s.text}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}"""

F["testimonials_grid"] = """function __NAME__() {
  const quotes = [
    { q: 'It replaced four different tools and saved us a full day every week.', a: 'Maya R.', r: 'Operations Lead' },
    { q: 'Onboarding was painless and support actually answers. Rare these days.', a: 'Daniel K.', r: 'Founder' },
    { q: 'The dashboards alone are worth it — we finally trust our numbers.', a: 'Priya S.', r: 'Head of Growth' },
  ];
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-6xl">
        <div className="mx-auto mb-14 max-w-2xl text-center">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest __EYE__">Loved by customers</p>
          <h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">Don&apos;t just take our word for it</h2>
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          {quotes.map((c) => (
            <figure key={c.a} className="__CARD__ rounded-2xl p-6">
              <div className="mb-3 flex gap-0.5 text-primary">{[0,1,2,3,4].map((i) => (<Icon key={i} name="star" className="h-4 w-4" />))}</div>
              <blockquote className="text-sm leading-relaxed __HEAD__">&ldquo;{c.q}&rdquo;</blockquote>
              <figcaption className="mt-4 text-sm font-semibold __HEAD__">{c.a}<span className="block text-xs font-normal __MUTED__">{c.r}</span></figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}"""

F["testimonial_big"] = """function __NAME__() {
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-3xl text-center">
        <div className="mb-6 flex justify-center gap-1 text-primary">{[0,1,2,3,4].map((i) => (<Icon key={i} name="star" className="h-5 w-5" />))}</div>
        <blockquote className="font-display text-2xl font-medium leading-snug md:text-3xl __HEAD__">&ldquo;This is the first tool the whole team adopted without being asked. It just makes sense.&rdquo;</blockquote>
        <p className="mt-6 text-sm font-semibold __HEAD__">Alex Morgan<span className="ml-2 font-normal __MUTED__">VP of Product, Lumen</span></p>
      </div>
    </section>
  );
}"""

F["pricing"] = """function __NAME__() {
  const tiers = [
    { name: 'Starter', price: '$0', tag: 'For individuals', feats: ['1 workspace', 'Core features', 'Community support'], popular: false },
    { name: 'Pro', price: '$24', tag: 'For growing teams', feats: ['Unlimited workspaces', 'Advanced analytics', 'Priority support'], popular: true },
    { name: 'Scale', price: '$59', tag: 'For organisations', feats: ['SSO & roles', 'Audit logs', 'Dedicated manager'], popular: false },
  ];
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-6xl">
        <div className="mx-auto mb-14 max-w-2xl text-center">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest __EYE__">Pricing</p>
          <h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">Simple, honest pricing</h2>
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          {tiers.map((t) => (
            <div key={t.name} className={'__CARD__ rounded-2xl p-7 ' + (t.popular ? 'ring-2 ring-primary' : '')}>
              {t.popular && <span className="mb-3 inline-block rounded-full bg-primary px-3 py-1 text-xs font-semibold text-primary-foreground">Most popular</span>}
              <h3 className="text-lg font-semibold __HEAD__">{t.name}</h3>
              <p className="text-xs __MUTED__">{t.tag}</p>
              <div className="mt-4 font-display text-4xl font-extrabold __HEAD__">{t.price}<span className="text-base font-medium __MUTED__">/mo</span></div>
              <ul className="mt-5 space-y-2 text-sm __MUTED__">{t.feats.map((f) => (<li key={f} className="flex items-center gap-2"><Icon name="check" className="h-4 w-4 text-primary" />{f}</li>))}</ul>
              <Link href="/register" className="mt-6 block rounded-xl bg-primary px-5 py-3 text-center text-sm font-semibold text-primary-foreground transition hover:opacity-90">Choose {t.name}</Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}"""

F["faq"] = """function __NAME__() {
  const faqs = [
    { q: 'Do I need a credit card to start?', a: 'No. You can explore the full product on the free plan for as long as you like.' },
    { q: 'Can I import my existing data?', a: 'Yes — guided importers bring in spreadsheets and common formats in a few clicks.' },
    { q: 'Is my data secure?', a: 'Everything is encrypted in transit and at rest, with role-based access controls.' },
    { q: 'How does support work?', a: 'Real humans, every day. Most questions are answered within a couple of hours.' },
  ];
  const [open, setOpen] = useState(0);
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-3xl">
        <div className="mb-12 text-center">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest __EYE__">FAQ</p>
          <h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">Questions, answered</h2>
        </div>
        <div className="space-y-3">
          {faqs.map((f, i) => (
            <div key={f.q} className="__CARD__ overflow-hidden rounded-xl">
              <button type="button" onClick={() => setOpen(open === i ? -1 : i)} className="flex w-full items-center justify-between gap-4 p-5 text-left text-sm font-semibold __HEAD__">
                {f.q}<Icon name="chevron-down" className={'h-4 w-4 shrink-0 transition ' + (open === i ? 'rotate-180' : '')} />
              </button>
              {open === i && <p className="px-5 pb-5 text-sm leading-relaxed __MUTED__">{f.a}</p>}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}"""

F["cta_band"] = """function __NAME__() {
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-4xl rounded-3xl bg-primary px-8 py-14 text-center text-primary-foreground shadow-xl md:px-14">
        <h2 className="font-display text-3xl font-bold md:text-4xl">Ready to get started?</h2>
        <p className="mx-auto mt-3 max-w-xl text-primary-foreground/85">Join thousands of teams already working smarter. It only takes a minute.</p>
        <div className="mt-8 flex flex-wrap justify-center gap-4">
          <Link href="/register" className="rounded-xl bg-white px-7 py-3.5 text-sm font-semibold text-slate-900 transition hover:bg-white/90">Get started free</Link>
          <Link href="/contact" className="rounded-xl border border-white/30 px-7 py-3.5 text-sm font-semibold transition hover:bg-white/10">Talk to sales</Link>
        </div>
      </div>
    </section>
  );
}"""

F["gallery"] = """function __NAME__() {
  const imgs = ['/assets/gallery1.jpg', '/assets/gallery2.jpg', '/assets/gallery3.jpg', '/assets/feature1.jpg', '/assets/feature2.jpg', '/assets/about1.jpg'];
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-7xl">
        <div className="mb-12 max-w-2xl">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest __EYE__">Gallery</p>
          <h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">A look inside</h2>
        </div>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
          {imgs.map((src, i) => (
            <div key={i} className={'overflow-hidden rounded-2xl ' + (i === 0 ? 'col-span-2 row-span-2' : '')}>
              <img src={src} alt="" className="h-full w-full object-cover transition duration-500 hover:scale-105" />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}"""

F["team"] = """function __NAME__() {
  const team = [
    { name: 'Jordan Lee', role: 'Founder & CEO', img: '/assets/about1.jpg' },
    { name: 'Sam Okafor', role: 'Head of Design', img: '/assets/feature1.jpg' },
    { name: 'Riya Patel', role: 'Engineering Lead', img: '/assets/feature2.jpg' },
    { name: 'Chris Vale', role: 'Customer Success', img: '/assets/gallery1.jpg' },
  ];
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-6xl">
        <div className="mx-auto mb-14 max-w-2xl text-center">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest __EYE__">Our team</p>
          <h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">The people behind the work</h2>
        </div>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {team.map((m) => (
            <div key={m.name} className="__CARD__ overflow-hidden rounded-2xl text-center">
              <img src={m.img} alt={m.name} className="h-44 w-full object-cover" />
              <div className="p-5"><h3 className="font-semibold __HEAD__">{m.name}</h3><p className="text-xs __MUTED__">{m.role}</p></div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}"""

F["contact_split"] = """function __NAME__() {
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto grid max-w-6xl gap-12 lg:grid-cols-2">
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest __EYE__">Contact</p>
          <h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">Let&apos;s talk</h2>
          <p className="mt-4 __MUTED__">Have a question or want a demo? Send a message and we&apos;ll get back to you within one business day.</p>
          <ul className="mt-8 space-y-4 text-sm __MUTED__">
            <li className="flex items-center gap-3"><Icon name="mail" className="h-5 w-5 text-primary" />hello@example.com</li>
            <li className="flex items-center gap-3"><Icon name="phone" className="h-5 w-5 text-primary" />+1 (555) 012-3456</li>
            <li className="flex items-center gap-3"><Icon name="location" className="h-5 w-5 text-primary" />123 Market Street, Suite 400</li>
          </ul>
        </div>
        <form className="__CARD__ grid gap-4 rounded-2xl p-7">
          <input className="rounded-xl border bg-background px-4 py-3 text-sm text-foreground" placeholder="Your name" />
          <input className="rounded-xl border bg-background px-4 py-3 text-sm text-foreground" placeholder="Email address" />
          <textarea rows={4} className="rounded-xl border bg-background px-4 py-3 text-sm text-foreground" placeholder="How can we help?" />
          <button type="button" className="rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground transition hover:opacity-90">Send message</button>
        </form>
      </div>
    </section>
  );
}"""

F["newsletter"] = """function __NAME__() {
  return (
    <section className="__SEC__ px-4 py-20 md:px-6">
      <div className="mx-auto max-w-3xl text-center">
        <h2 className="font-display text-2xl font-bold md:text-3xl __HEAD__">Get the occasional good email</h2>
        <p className="mx-auto mt-3 max-w-lg __MUTED__">Product tips and the rare announcement. No spam, unsubscribe in one click.</p>
        <form className="mx-auto mt-7 flex max-w-md flex-col gap-3 sm:flex-row">
          <input className="flex-1 rounded-xl border bg-background px-4 py-3 text-sm text-foreground" placeholder="you@example.com" />
          <button type="button" className="rounded-xl bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground transition hover:opacity-90">Subscribe</button>
        </form>
      </div>
    </section>
  );
}"""

F["comparison"] = """function __NAME__() {
  const rows = ['Unlimited projects', 'Real-time collaboration', 'Advanced analytics', 'Priority support', 'Single sign-on'];
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-4xl">
        <div className="mb-12 text-center">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest __EYE__">Compare</p>
          <h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">See how we stack up</h2>
        </div>
        <div className="__CARD__ overflow-hidden rounded-2xl">
          <div className="grid grid-cols-3 border-b p-4 text-sm font-semibold __HEAD__"><span>Feature</span><span className="text-center">Others</span><span className="text-center text-primary">Us</span></div>
          {rows.map((r) => (
            <div key={r} className="grid grid-cols-3 items-center border-b p-4 text-sm last:border-0 __MUTED__">
              <span>{r}</span><span className="flex justify-center"><Icon name="x" className="h-4 w-4 opacity-40" /></span><span className="flex justify-center text-primary"><Icon name="check" className="h-4 w-4" /></span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}"""

F["timeline"] = """function __NAME__() {
  const items = [
    { year: '2021', t: 'The idea', d: 'Started as a weekend project to scratch our own itch.' },
    { year: '2022', t: 'First customers', d: 'Hundreds of teams signed up in the first few months.' },
    { year: '2023', t: 'Going global', d: 'Expanded to 40+ countries and shipped major releases.' },
    { year: '2024', t: 'What\\u2019s next', d: 'Doubling down on automation and an open platform.' },
  ];
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-3xl">
        <div className="mb-12"><p className="mb-3 text-xs font-semibold uppercase tracking-widest __EYE__">Our story</p><h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">How we got here</h2></div>
        <div className="relative space-y-8 border-l-2 border-primary/30 pl-8">
          {items.map((m) => (
            <div key={m.year} className="relative">
              <span className="absolute -left-[39px] flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">{'\\u2022'}</span>
              <div className="text-xs font-semibold uppercase tracking-wide text-primary">{m.year}</div>
              <h3 className="mt-1 text-lg font-semibold __HEAD__">{m.t}</h3>
              <p className="mt-1 text-sm __MUTED__">{m.d}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}"""

F["metrics_cards"] = """function __NAME__() {
  const m = [
    { icon: 'trending-up', n: '+38%', l: 'Faster delivery' },
    { icon: 'users', n: '3.2x', l: 'Team productivity' },
    { icon: 'clock', n: '9 hrs', l: 'Saved per week' },
    { icon: 'shield', n: 'Zero', l: 'Security incidents' },
  ];
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-6xl">
        <div className="mb-12 max-w-2xl"><p className="mb-3 text-xs font-semibold uppercase tracking-widest __EYE__">Outcomes</p><h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">Results teams can measure</h2></div>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {m.map((x) => (
            <div key={x.l} className="__CARD__ rounded-2xl p-6">
              <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary"><Icon name={x.icon} className="h-5 w-5" /></div>
              <div className="font-display text-3xl font-extrabold __HEAD__">{x.n}</div>
              <div className="mt-1 text-sm __MUTED__">{x.l}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}"""

F["feature_split"] = """function __NAME__() {
  const points = ['Drag-and-drop simplicity', 'Live updates across the team', 'Powerful, readable reports'];
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2">
        <div className="order-2 lg:order-1">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest __EYE__">Workflow</p>
          <h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">Designed around how you actually work</h2>
          <p className="mt-4 __MUTED__">No manuals, no training days. Open it up and you already know where everything is.</p>
          <ul className="mt-6 space-y-3">{points.map((p) => (<li key={p} className="flex items-center gap-3 text-sm __HEAD__"><Icon name="check" className="h-5 w-5 text-primary" />{p}</li>))}</ul>
        </div>
        <div className="order-1 overflow-hidden rounded-3xl lg:order-2"><img src="/assets/feature1.jpg" alt="" className="h-full w-full object-cover" /></div>
      </div>
    </section>
  );
}"""

F["bento"] = """function __NAME__() {
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-6xl">
        <div className="mb-12 max-w-2xl"><p className="mb-3 text-xs font-semibold uppercase tracking-widest __EYE__">Platform</p><h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">One workspace, every angle</h2></div>
        <div className="grid gap-4 md:grid-cols-3 md:grid-rows-2">
          <div className="__CARD__ rounded-3xl p-7 md:col-span-2 md:row-span-2"><Icon name="layout-dashboard" className="h-7 w-7 text-primary" /><h3 className="mt-4 text-xl font-semibold __HEAD__">A command centre for everything</h3><p className="mt-2 text-sm __MUTED__">See projects, people and progress in a single, calm view that updates in real time.</p></div>
          <div className="__CARD__ rounded-3xl p-7"><Icon name="zap" className="h-6 w-6 text-primary" /><h3 className="mt-3 font-semibold __HEAD__">Automations</h3><p className="mt-1 text-sm __MUTED__">Let the busywork run itself.</p></div>
          <div className="__CARD__ rounded-3xl p-7"><Icon name="shield" className="h-6 w-6 text-primary" /><h3 className="mt-3 font-semibold __HEAD__">Secure</h3><p className="mt-1 text-sm __MUTED__">Roles, audit logs and SSO.</p></div>
        </div>
      </div>
    </section>
  );
}"""

F["category_tiles"] = """function __NAME__() {
  const cats = [
    { icon: 'sparkles', t: 'Getting started' }, { icon: 'chart', t: 'Analytics' }, { icon: 'users', t: 'Collaboration' },
    { icon: 'settings', t: 'Automation' }, { icon: 'shield', t: 'Security' }, { icon: 'globe', t: 'Integrations' },
  ];
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-6xl">
        <div className="mx-auto mb-12 max-w-2xl text-center"><p className="mb-3 text-xs font-semibold uppercase tracking-widest __EYE__">Explore</p><h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">Browse by what you need</h2></div>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {cats.map((c) => (
            <a key={c.t} href="#" className="__CARD__ group flex items-center gap-4 rounded-2xl p-5 transition hover:border-primary">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary"><Icon name={c.icon} className="h-5 w-5" /></span>
              <span className="font-semibold __HEAD__">{c.t}</span>
              <Icon name="chevron-right" className="ml-auto h-4 w-4 __MUTED__ transition group-hover:translate-x-0.5" />
            </a>
          ))}
        </div>
      </div>
    </section>
  );
}"""

F["banner_announce"] = """function __NAME__() {
  return (
    <section className="__SEC__ px-4 py-12 md:px-6">
      <div className="mx-auto flex max-w-5xl flex-col items-center justify-between gap-4 rounded-2xl border border-primary/30 bg-primary/5 px-7 py-6 text-center sm:flex-row sm:text-left">
        <div className="flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/15 text-primary"><Icon name="sparkles" className="h-5 w-5" /></span><p className="text-sm font-medium __HEAD__">New: automations are here. Save hours every week, starting today.</p></div>
        <Link href="/register" className="shrink-0 rounded-xl bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground transition hover:opacity-90">Try it now</Link>
      </div>
    </section>
  );
}"""

F["split_image_left"] = """function __NAME__() {
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2">
        <div className="overflow-hidden rounded-3xl"><img src="/assets/about1.jpg" alt="" className="h-full w-full object-cover" /></div>
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest __EYE__">About</p>
          <h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">Built by a team that sweats the details</h2>
          <p className="mt-4 __MUTED__">We obsess over the small moments — the loading states, the empty screens, the copy — because that&apos;s where great products are made.</p>
          <Link href="/about" className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-primary">Read our story <Icon name="arrow-right" className="h-4 w-4" /></Link>
        </div>
      </div>
    </section>
  );
}"""

# ---- catalog: register every family in several tones (= 100+ templates) ------
# tags drive input matching; "any" families fit every project kind.
_TAGS = {
    "features_grid": ["saas", "tech", "service", "business", "any"],
    "value_props": ["service", "cleaning", "clinic", "business", "consulting"],
    "stats_band": ["saas", "b2b", "analytics", "finance", "platform"],
    "logos_strip": ["saas", "b2b", "corporate", "startup", "agency"],
    "steps": ["service", "saas", "app", "onboarding", "any"],
    "testimonials_grid": ["any", "service", "shop", "saas", "school"],
    "testimonial_big": ["any", "creative", "studio", "agency"],
    "pricing": ["saas", "service", "subscription", "b2b", "app"],
    "faq": ["any", "service", "saas", "shop", "clinic"],
    "cta_band": ["any", "saas", "service", "startup"],
    "gallery": ["gallery", "photo", "studio", "restaurant", "hotel", "travel", "event", "shop"],
    "team": ["agency", "studio", "corporate", "clinic", "consulting", "about"],
    "contact_split": ["service", "clinic", "agency", "business", "contact"],
    "newsletter": ["media", "blog", "creative", "shop", "any"],
    "comparison": ["saas", "b2b", "tool", "platform"],
    "timeline": ["about", "corporate", "agency", "startup", "studio"],
    "metrics_cards": ["saas", "analytics", "b2b", "finance", "platform"],
    "feature_split": ["saas", "app", "tool", "service", "any"],
    "bento": ["ai", "tech", "saas", "startup", "platform", "creative"],
    "category_tiles": ["shop", "store", "ecommerce", "lms", "school", "media", "directory"],
    "banner_announce": ["any", "saas", "app", "startup"],
    "split_image_left": ["any", "about", "service", "restaurant", "hotel", "salon"],
}
# which tones suit each family (some only read well light/soft).
_TONE_SETS = {
    "cta_band": ["light", "soft", "dark"],         # body is its own primary block
    "banner_announce": ["light", "soft", "dark"],
    "logos_strip": ["light", "soft", "dark"],
    "newsletter": ["light", "soft", "dark", "accent"],
    "stats_band": ["light", "soft", "dark", "accent"],
}
_DEFAULT_TONES = ["light", "soft", "dark", "accent", "soft"]  # 5 => family x 5

CATALOG = []
for _fam in F:
    _tones = _TONE_SETS.get(_fam, _DEFAULT_TONES)
    for _i, _tone in enumerate(_tones):
        CATALOG.append({"family": _fam, "tone": _tone, "key": f"{_fam}.{_tone}.{_i}", "tags": _TAGS.get(_fam, ["any"])})


def render(entry: dict, name: str) -> str:
    """Return a complete, uniquely-named `function <name>() {...}` for an entry."""
    return _fill(F[entry["family"]], name, TONES[entry["tone"]])


def count() -> int:
    return len(CATALOG)


def pick_middles(rng: random.Random, n: int, prompt_text: str = "") -> list:
    """My recommended selection: score every catalog entry by input-tag overlap,
    then sample a varied subset (no repeated family) with randomness for variety."""
    text = (prompt_text or "").lower()

    def score(e):
        s = sum(2 for t in e["tags"] if t != "any" and t in text)
        if "any" in e["tags"]:
            s += 0.5
        return s + rng.random()  # randomness => different page every run

    ordered = sorted(CATALOG, key=score, reverse=True)
    chosen, seen = [], set()
    for e in ordered:
        if e["family"] in seen:
            continue
        chosen.append(e)
        seen.add(e["family"])
        if len(chosen) >= n:
            break
    rng.shuffle(chosen)
    return chosen
