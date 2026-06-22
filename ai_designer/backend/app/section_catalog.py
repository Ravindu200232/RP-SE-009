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
  const stats = [['12k+', 'Active users'], ['99.9%', 'Uptime'], ['4.9/5', 'Avg rating'], ['40+', 'Countries']];
  return (
    <section className="__SEC__ px-4 py-20 md:px-6">
      <div className="mx-auto max-w-6xl">
        <div className="grid gap-8 text-center sm:grid-cols-2 lg:grid-cols-4">
          {stats.map(([n, l]) => (
            <div key={l}>
              <div className="font-display text-4xl font-extrabold md:text-5xl __HEAD__">{n}</div>
              <div className="mt-2 text-sm uppercase tracking-wide __MUTED__">{l}</div>
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
    { n: '01', t: 'Create your account', d: 'Sign up in seconds — no credit card required to get started.' },
    { n: '02', t: 'Set things up', d: 'Import your data or start fresh with a guided, friendly setup.' },
    { n: '03', t: 'Go live', d: 'Invite your team and watch everything click into place.' },
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
              <h3 className="mt-4 text-lg font-semibold __HEAD__">{s.t}</h3>
              <p className="mt-2 text-sm leading-relaxed __MUTED__">{s.d}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}"""

F["testimonials_grid"] = """function __NAME__() {
  const quotes = [
    { t: 'It replaced four different tools and saved us a full day every week.', n: 'Maya R.', r: 'Operations Lead' },
    { t: 'Onboarding was painless and support actually answers. Rare these days.', n: 'Daniel K.', r: 'Founder' },
    { t: 'The dashboards alone are worth it — we finally trust our numbers.', n: 'Priya S.', r: 'Head of Growth' },
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
            <figure key={c.n} className="__CARD__ rounded-2xl p-6">
              <div className="mb-3 flex gap-0.5 text-primary">{[0,1,2,3,4].map((i) => (<Icon key={i} name="star" className="h-4 w-4" />))}</div>
              <blockquote className="text-sm leading-relaxed __HEAD__">&ldquo;{c.t}&rdquo;</blockquote>
              <figcaption className="mt-4 text-sm font-semibold __HEAD__">{c.n}<span className="block text-xs font-normal __MUTED__">{c.r}</span></figcaption>
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
    { name: 'Starter', price: 0, popular: false, items: ['1 workspace', 'Core features', 'Community support'] },
    { name: 'Pro', price: 24, popular: true, items: ['Unlimited workspaces', 'Advanced analytics', 'Priority support'] },
    { name: 'Scale', price: 59, popular: false, items: ['SSO & roles', 'Audit logs', 'Dedicated manager'] },
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
              <div className="mt-4 font-display text-4xl font-extrabold __HEAD__">${t.price}<span className="text-base font-medium __MUTED__">/mo</span></div>
              <ul className="mt-5 space-y-2 text-sm __MUTED__">{t.items.map((f) => (<li key={f} className="flex items-center gap-2"><Icon name="check" className="h-4 w-4 text-primary" />{f}</li>))}</ul>
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

# ── NEW SECTION FAMILIES (Category-specific, world-class) ─────────────────────

F["product_showcase"] = """function __NAME__() {
  const products = [
    { name: 'Premium Edition', price: '$249', badge: 'Best Seller', rating: 4.9, reviews: 1240, img: 'product1.jpg' },
    { name: 'Standard Pack', price: '$149', badge: 'Popular', rating: 4.7, reviews: 890, img: 'product2.jpg' },
    { name: 'Starter Kit', price: '$79', badge: 'New', rating: 4.8, reviews: 560, img: 'product3.jpg' },
    { name: 'Pro Bundle', price: '$399', badge: 'Limited', rating: 5.0, reviews: 320, img: 'product4.jpg' },
  ];
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-7xl">
        <div className="mb-12 flex items-end justify-between">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest __EYE__">Featured Products</p>
            <h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">Handpicked for you</h2>
          </div>
          <Link href="/products" className="hidden text-sm font-semibold text-primary sm:block">View all <Icon name="arrow-right" className="inline h-4 w-4" /></Link>
        </div>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {products.map((p) => (
            <div key={p.name} className="__CARD__ overflow-hidden rounded-2xl shadow-sm transition hover:-translate-y-1 hover:shadow-lg">
              <div className="relative h-52 overflow-hidden bg-muted">
                <img src={'/assets/' + p.img} alt={p.name} className="h-full w-full object-cover" />
                <span className="absolute left-3 top-3 rounded-full bg-primary px-2.5 py-1 text-xs font-semibold text-primary-foreground">{p.badge}</span>
              </div>
              <div className="p-4">
                <h3 className="font-semibold __HEAD__">{p.name}</h3>
                <div className="mt-1 flex items-center gap-1">
                  <div className="flex gap-0.5 text-primary">{[0,1,2,3,4].map((i)=>(<Icon key={i} name="star" className="h-3 w-3" />))}</div>
                  <span className="text-xs __MUTED__">({p.reviews})</span>
                </div>
                <div className="mt-3 flex items-center justify-between">
                  <span className="font-display text-lg font-bold text-primary">{p.price}</span>
                  <button className="rounded-xl bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground transition hover:opacity-90">Add to Cart</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}"""

F["review_wall"] = """function __NAME__() {
  const reviews = [
    { q: 'Absolutely transformed how we manage daily operations. Worth every penny.', a: 'Sarah K.', r: 'Business Owner', stars: 5 },
    { q: 'Setup was effortless and the results were immediate. My team loves it.', a: 'Marcus T.', r: 'Product Manager', stars: 5 },
    { q: 'Best decision we made this year. Customer support is top-notch too.', a: 'Priya M.', r: 'Director of Operations', stars: 5 },
    { q: 'Intuitive, powerful, and reliable. Ticked every box on our checklist.', a: 'James L.', r: 'CTO', stars: 5 },
    { q: 'Replaced three separate tools. Now everything lives in one clean place.', a: 'Nina R.', r: 'Head of Growth', stars: 5 },
    { q: 'Our team was up and running in under an hour. Impressive onboarding.', a: 'Carlos B.', r: 'Team Lead', stars: 5 },
  ];
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-7xl">
        <div className="mx-auto mb-14 max-w-2xl text-center">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest __EYE__">Reviews</p>
          <h2 className="font-display text-3xl font-bold md:text-5xl __HEAD__">10,000+ happy customers</h2>
          <p className="mt-4 __MUTED__">Real reviews from real people who use it every day.</p>
        </div>
        <div className="columns-1 gap-6 sm:columns-2 lg:columns-3">
          {reviews.map((r) => (
            <figure key={r.a} className="__CARD__ mb-6 break-inside-avoid rounded-2xl p-6">
              <div className="mb-3 flex gap-0.5 text-primary">{[...Array(r.stars)].map((_,i)=>(<Icon key={i} name="star" className="h-4 w-4" />))}</div>
              <blockquote className="text-sm leading-relaxed __HEAD__">&ldquo;{r.q}&rdquo;</blockquote>
              <figcaption className="mt-4 flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/15 font-semibold text-primary text-sm">{r.a[0]}</div>
                <div><p className="text-sm font-semibold __HEAD__">{r.a}</p><p className="text-xs __MUTED__">{r.r}</p></div>
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}"""

F["course_cards"] = """function __NAME__() {
  const courses = [
    { title: 'Fundamentals', level: 'Beginner', duration: '6h', students: '12,400', img: 'course1.jpg', badge: 'Most Popular' },
    { title: 'Advanced Topics', level: 'Intermediate', duration: '9h', students: '8,200', img: 'course2.jpg', badge: 'Bestseller' },
    { title: 'Expert Mastery', level: 'Advanced', duration: '14h', students: '5,600', img: 'course3.jpg', badge: 'New' },
    { title: 'Project Bootcamp', level: 'All Levels', duration: '20h', students: '3,100', img: 'course4.jpg', badge: 'Featured' },
  ];
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-7xl">
        <div className="mb-12 flex items-end justify-between">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest __EYE__">Curriculum</p>
            <h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">Pick your learning path</h2>
          </div>
          <Link href="/courses" className="hidden text-sm font-semibold text-primary sm:block">All courses <Icon name="arrow-right" className="inline h-4 w-4" /></Link>
        </div>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {courses.map((c) => (
            <div key={c.title} className="__CARD__ overflow-hidden rounded-2xl shadow-sm transition hover:-translate-y-1 hover:shadow-md">
              <div className="relative h-44 overflow-hidden bg-muted">
                <img src={'/assets/' + c.img} alt={c.title} className="h-full w-full object-cover" />
                <span className="absolute left-3 top-3 rounded-full bg-primary px-2.5 py-1 text-xs font-bold text-primary-foreground">{c.badge}</span>
              </div>
              <div className="p-4">
                <h3 className="font-semibold __HEAD__">{c.title}</h3>
                <div className="mt-2 flex items-center gap-3 text-xs __MUTED__">
                  <span className="flex items-center gap-1"><Icon name="clock" className="h-3 w-3" />{c.duration}</span>
                  <span className="flex items-center gap-1"><Icon name="users" className="h-3 w-3" />{c.students}</span>
                </div>
                <div className="mt-3 flex items-center justify-between">
                  <span className="rounded-lg bg-primary/10 px-2 py-1 text-xs font-medium text-primary">{c.level}</span>
                  <Link href="/enroll" className="text-xs font-semibold text-primary">Enroll <Icon name="arrow-right" className="inline h-3 w-3" /></Link>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}"""

F["doctor_cards"] = """function __NAME__() {
  const doctors = [
    { name: 'Dr. Emily Chen', spec: 'Cardiology', exp: '14 yrs', rating: 4.9, img: 'doctor1.jpg', avail: 'Mon, Wed, Fri' },
    { name: 'Dr. James Patel', spec: 'Neurology', exp: '18 yrs', rating: 4.8, img: 'doctor2.jpg', avail: 'Tue, Thu' },
    { name: 'Dr. Sarah Wilson', spec: 'Pediatrics', exp: '10 yrs', rating: 5.0, img: 'doctor3.jpg', avail: 'Mon-Fri' },
    { name: 'Dr. Michael Roy', spec: 'Orthopedics', exp: '22 yrs', rating: 4.9, img: 'doctor4.jpg', avail: 'Wed, Sat' },
  ];
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-7xl">
        <div className="mx-auto mb-12 max-w-2xl text-center">
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest __EYE__">Our Specialists</p>
          <h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">Expert doctors, compassionate care</h2>
        </div>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {doctors.map((d) => (
            <div key={d.name} className="__CARD__ overflow-hidden rounded-2xl text-center shadow-sm transition hover:-translate-y-1 hover:shadow-md">
              <div className="h-52 overflow-hidden"><img src={'/assets/' + d.img} alt={d.name} className="h-full w-full object-cover" /></div>
              <div className="p-5">
                <h3 className="font-semibold __HEAD__">{d.name}</h3>
                <p className="text-sm text-primary">{d.spec}</p>
                <div className="mt-2 flex items-center justify-center gap-3 text-xs __MUTED__">
                  <span>{d.exp} exp.</span>
                  <span>·</span>
                  <span className="flex items-center gap-0.5"><Icon name="star" className="h-3 w-3 text-primary" />{d.rating}</span>
                </div>
                <p className="mt-2 text-xs __MUTED__">Available: {d.avail}</p>
                <button className="mt-4 w-full rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition hover:opacity-90">Book Appointment</button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}"""

F["property_grid"] = """function __NAME__() {
  const props = [
    { title: 'Modern City Apartment', type: 'For Sale', price: '$485,000', beds: 3, baths: 2, sqft: '1,250', img: 'property1.jpg', badge: 'Featured' },
    { title: 'Suburban Family Home', type: 'For Sale', price: '$620,000', beds: 4, baths: 3, sqft: '2,100', img: 'property2.jpg', badge: 'New' },
    { title: 'Downtown Studio', type: 'For Rent', price: '$2,400/mo', beds: 1, baths: 1, sqft: '650', img: 'property3.jpg', badge: 'Hot' },
    { title: 'Luxury Penthouse', type: 'For Sale', price: '$1,250,000', beds: 5, baths: 4, sqft: '3,800', img: 'property4.jpg', badge: 'Premium' },
    { title: 'Garden Townhouse', type: 'For Rent', price: '$3,200/mo', beds: 3, baths: 2, sqft: '1,600', img: 'property5.jpg', badge: '' },
    { title: 'Commercial Office Space', type: 'For Lease', price: '$8,500/mo', beds: 0, baths: 4, sqft: '4,200', img: 'property6.jpg', badge: 'Available' },
  ];
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-7xl">
        <div className="mb-12 flex items-end justify-between">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest __EYE__">Listings</p>
            <h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">Find your perfect property</h2>
          </div>
          <Link href="/properties" className="hidden text-sm font-semibold text-primary sm:block">View all <Icon name="arrow-right" className="inline h-4 w-4" /></Link>
        </div>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {props.map((p) => (
            <div key={p.title} className="__CARD__ overflow-hidden rounded-2xl shadow-sm transition hover:-translate-y-1 hover:shadow-lg">
              <div className="relative h-52 overflow-hidden">
                <img src={'/assets/' + p.img} alt={p.title} className="h-full w-full object-cover" />
                {p.badge && (<span className="absolute left-3 top-3 rounded-full bg-primary px-3 py-1 text-xs font-bold text-primary-foreground">{p.badge}</span>)}
                <span className="absolute right-3 top-3 rounded-full bg-background/90 px-3 py-1 text-xs font-semibold __HEAD__">{p.type}</span>
              </div>
              <div className="p-5">
                <h3 className="font-semibold __HEAD__">{p.title}</h3>
                <p className="mt-1 font-display text-xl font-bold text-primary">{p.price}</p>
                <div className="mt-3 flex gap-4 text-xs __MUTED__">
                  {p.beds > 0 && (<span className="flex items-center gap-1"><Icon name="home" className="h-3.5 w-3.5" />{p.beds} beds</span>)}
                  <span className="flex items-center gap-1"><Icon name="droplet" className="h-3.5 w-3.5" />{p.baths} baths</span>
                  <span className="flex items-center gap-1"><Icon name="maximize" className="h-3.5 w-3.5" />{p.sqft} sqft</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}"""

F["blog_grid"] = """function __NAME__() {
  const posts = [
    { title: 'How to get started in 10 minutes', category: 'Guide', date: 'Jun 12', readTime: '5 min', img: 'blog1.jpg' },
    { title: 'The ultimate checklist for success', category: 'Tips', date: 'Jun 8', readTime: '8 min', img: 'blog2.jpg' },
    { title: 'Behind the scenes: our latest update', category: 'News', date: 'Jun 3', readTime: '4 min', img: 'blog3.jpg' },
    { title: 'Five mistakes to avoid as a beginner', category: 'Advice', date: 'May 29', readTime: '6 min', img: 'blog4.jpg' },
    { title: 'A deep dive into advanced workflows', category: 'Advanced', date: 'May 24', readTime: '12 min', img: 'blog5.jpg' },
    { title: 'Customer spotlight: scaling with us', category: 'Story', date: 'May 18', readTime: '7 min', img: 'blog6.jpg' },
  ];
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-7xl">
        <div className="mb-12 flex items-end justify-between">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest __EYE__">Latest Articles</p>
            <h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">From the blog</h2>
          </div>
          <Link href="/blog" className="hidden text-sm font-semibold text-primary sm:block">All posts <Icon name="arrow-right" className="inline h-4 w-4" /></Link>
        </div>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {posts.map((p) => (
            <article key={p.title} className="__CARD__ overflow-hidden rounded-2xl shadow-sm transition hover:-translate-y-1 hover:shadow-md">
              <div className="h-48 overflow-hidden"><img src={'/assets/' + p.img} alt={p.title} className="h-full w-full object-cover" /></div>
              <div className="p-5">
                <div className="mb-3 flex items-center gap-3">
                  <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary">{p.category}</span>
                  <span className="text-xs __MUTED__">{p.date}</span>
                  <span className="text-xs __MUTED__">· {p.readTime} read</span>
                </div>
                <h3 className="text-base font-semibold leading-snug __HEAD__">{p.title}</h3>
                <Link href="/blog/post" className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-primary">Read more <Icon name="arrow-right" className="h-3 w-3" /></Link>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}"""

F["video_section"] = """function __NAME__() {
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-5xl">
        <div className="mx-auto mb-10 max-w-2xl text-center">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest __EYE__">See it in action</p>
          <h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">A two-minute walkthrough</h2>
          <p className="mt-3 __MUTED__">Watch how teams get from zero to productive in just a few clicks.</p>
        </div>
        <div className="relative overflow-hidden rounded-3xl __CARD__ shadow-2xl">
          <div className="aspect-video w-full bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center">
            <button className="flex h-20 w-20 items-center justify-center rounded-full bg-primary shadow-xl transition hover:scale-110">
              <Icon name="play" className="h-8 w-8 text-primary-foreground ml-1" />
            </button>
          </div>
        </div>
        <div className="mt-10 grid gap-6 text-center sm:grid-cols-3">
          {[['2 min', 'Quick overview'], ['No sign-up', 'Watch instantly'], ['HD quality', 'Crystal clear']].map(([v, l]) => (
            <div key={l}><div className="font-display text-2xl font-bold __HEAD__">{v}</div><div className="mt-1 text-sm __MUTED__">{l}</div></div>
          ))}
        </div>
      </div>
    </section>
  );
}"""

F["map_section"] = """function __NAME__() {
  const locations = [
    { city: 'New York', address: '350 Fifth Avenue, Manhattan', phone: '+1 212 555 0100', hours: 'Mon-Sat 9am-8pm' },
    { city: 'Los Angeles', address: '100 Wilshire Blvd, Santa Monica', phone: '+1 310 555 0200', hours: 'Mon-Sun 9am-9pm' },
    { city: 'Chicago', address: '233 S Wacker Dr, Loop', phone: '+1 312 555 0300', hours: 'Mon-Fri 8am-7pm' },
  ];
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-7xl">
        <div className="mx-auto mb-12 max-w-2xl text-center">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest __EYE__">Find us</p>
          <h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">Locations near you</h2>
        </div>
        <div className="grid gap-6 lg:grid-cols-3">
          {locations.map((l) => (
            <div key={l.city} className="__CARD__ rounded-2xl p-6 shadow-sm">
              <h3 className="text-lg font-bold __HEAD__">{l.city}</h3>
              <div className="mt-4 space-y-3">
                <div className="flex items-start gap-3"><Icon name="map-pin" className="mt-0.5 h-4 w-4 shrink-0 text-primary" /><p className="text-sm __MUTED__">{l.address}</p></div>
                <div className="flex items-center gap-3"><Icon name="phone" className="h-4 w-4 shrink-0 text-primary" /><p className="text-sm __MUTED__">{l.phone}</p></div>
                <div className="flex items-center gap-3"><Icon name="clock" className="h-4 w-4 shrink-0 text-primary" /><p className="text-sm __MUTED__">{l.hours}</p></div>
              </div>
              <button className="mt-5 w-full rounded-xl border border-primary/30 px-4 py-2 text-sm font-semibold text-primary transition hover:bg-primary/5">Get Directions</button>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}"""

F["process_split"] = """function __NAME__() {
  const steps = [
    { n: '01', t: 'Define your goals', d: 'Tell us what you want to achieve and we map out the fastest path to get there.' },
    { n: '02', t: 'We build together', d: 'Collaborative sessions, constant feedback, and a shared view of progress at every stage.' },
    { n: '03', t: 'Launch and grow', d: 'Go live with confidence. Ongoing support means you keep improving long after day one.' },
  ];
  const imgs = ['process1.jpg', 'process2.jpg', 'process3.jpg'];
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-6xl">
        <div className="mx-auto mb-16 max-w-2xl text-center">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest __EYE__">How we work</p>
          <h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">From idea to impact</h2>
        </div>
        <div className="space-y-20">
          {steps.map((s, i) => {
            const side = i % 2 === 0 ? 'right' : 'left';
            const img = imgs[i % imgs.length];
            return (
            <div key={s.n} className={`grid items-center gap-10 lg:grid-cols-2 ${side === 'left' ? 'lg:grid-flow-dense' : ''}`}>
              <div className={side === 'left' ? 'lg:col-start-2' : ''}>
                <div className="font-display text-5xl font-extrabold text-primary/30">{s.n}</div>
                <h3 className="mt-2 font-display text-2xl font-bold __HEAD__">{s.t}</h3>
                <p className="mt-3 leading-relaxed __MUTED__">{s.d}</p>
              </div>
              <div className={`overflow-hidden rounded-3xl ${side === 'left' ? 'lg:col-start-1 lg:row-start-1' : ''}`}>
                <img src={'/assets/' + img} alt={s.t} className="h-72 w-full object-cover" />
              </div>
            </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}"""

F["brand_story"] = """function __NAME__() {
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-7xl">
        <div className="grid gap-12 lg:grid-cols-2 lg:items-center">
          <div>
            <p className="mb-3 text-xs font-semibold uppercase tracking-widest __EYE__">Our Story</p>
            <h2 className="font-display text-3xl font-bold leading-tight md:text-5xl __HEAD__">We started with a problem. We built the solution.</h2>
            <p className="mt-5 text-lg leading-relaxed __MUTED__">Frustrated by tools that were either too simple or too expensive, we set out to build something different — powerful enough for serious work, simple enough that anyone could use it from day one.</p>
            <p className="mt-4 leading-relaxed __MUTED__">Today thousands of teams rely on us every day, and we&apos;re just getting started.</p>
            <div className="mt-8 flex gap-6">
              {[['2018', 'Founded'], ['50K+', 'Customers'], ['99.9%', 'Uptime'], ['40+', 'Countries']].map(([v,l])=>(
                <div key={l}><div className="font-display text-2xl font-bold __HEAD__">{v}</div><div className="text-xs __MUTED__">{l}</div></div>
              ))}
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="overflow-hidden rounded-3xl"><img src="/assets/about1.jpg" alt="" className="h-60 w-full object-cover" /></div>
            <div className="mt-6 overflow-hidden rounded-3xl"><img src="/assets/about2.jpg" alt="" className="h-60 w-full object-cover" /></div>
          </div>
        </div>
      </div>
    </section>
  );
}"""

F["feature_tabs"] = """function __NAME__() {
  const { useState } = React;
  const tabs = [
    { id: 'overview', label: 'Overview', icon: 'layout', content: 'Get an instant overview of everything happening in your workspace — updates, tasks, and insights in one unified dashboard.' },
    { id: 'analytics', label: 'Analytics', icon: 'chart', content: 'Deep-dive into your data with live charts, custom reports, and trend indicators that make decisions obvious.' },
    { id: 'automation', label: 'Automation', icon: 'zap', content: 'Set rules once, let the system handle the rest. From routing to reminders, the busywork disappears.' },
    { id: 'collaboration', label: 'Collaboration', icon: 'users', content: 'Comments, @mentions, shared views, and real-time cursors keep every teammate on the same page.' },
  ];
  const [active, setActive] = useState('overview');
  const cur = tabs.find(t => t.id === active);
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-5xl">
        <div className="mx-auto mb-12 max-w-2xl text-center">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest __EYE__">Platform</p>
          <h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">Everything you need, nothing you don&apos;t</h2>
        </div>
        <div className="flex flex-wrap justify-center gap-3 mb-10">
          {tabs.map(t => (
            <button key={t.id} onClick={() => setActive(t.id)} className={`flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold transition ${active === t.id ? 'bg-primary text-primary-foreground shadow-sm' : '__CARD__ __HEAD__ hover:bg-primary/5'}`}>
              <Icon name={t.icon} className="h-4 w-4" />{t.label}
            </button>
          ))}
        </div>
        <div className="__CARD__ rounded-3xl p-8 md:p-12 shadow-sm">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-primary/15 text-primary"><Icon name={cur.icon} className="h-6 w-6" /></div>
            <div>
              <h3 className="text-xl font-semibold __HEAD__">{cur.label}</h3>
              <p className="mt-2 leading-relaxed __MUTED__">{cur.content}</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}"""

F["pricing_plans"] = """function __NAME__() {
  const plans = [
    { name: 'Free', price: '$0', period: '/month', desc: 'Perfect for individuals getting started', features: ['Up to 3 projects', '5 team members', '1 GB storage', 'Basic analytics', 'Email support'], cta: 'Get started', primary: false },
    { name: 'Pro', price: '$29', period: '/month', desc: 'For growing teams that need more power', features: ['Unlimited projects', '25 team members', '50 GB storage', 'Advanced analytics', 'Priority support', 'Custom integrations', 'API access'], cta: 'Start free trial', primary: true },
    { name: 'Enterprise', price: '$99', period: '/month', desc: 'For large organizations at scale', features: ['Everything in Pro', 'Unlimited members', '500 GB storage', 'Custom reporting', 'Dedicated manager', 'SLA guarantee', 'On-premise option'], cta: 'Contact sales', primary: false },
  ];
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-6xl">
        <div className="mx-auto mb-14 max-w-2xl text-center">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest __EYE__">Pricing</p>
          <h2 className="font-display text-3xl font-bold md:text-5xl __HEAD__">Simple, transparent pricing</h2>
          <p className="mt-4 __MUTED__">No surprises. Cancel anytime. Upgrade whenever you&apos;re ready.</p>
        </div>
        <div className="grid gap-6 lg:grid-cols-3">
          {plans.map((p) => (
            <div key={p.name} className={`relative rounded-2xl p-8 shadow-sm ${p.primary ? 'bg-primary text-primary-foreground ring-2 ring-primary' : '__CARD__'}`}>
              {p.primary && (<span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-primary-foreground px-4 py-1 text-xs font-bold text-primary">Most Popular</span>)}
              <h3 className={`text-lg font-bold ${p.primary ? 'text-primary-foreground' : '__HEAD__'}`}>{p.name}</h3>
              <div className="mt-3 flex items-end gap-1">
                <span className={`font-display text-4xl font-extrabold ${p.primary ? 'text-primary-foreground' : '__HEAD__'}`}>{p.price}</span>
                <span className={`mb-1 text-sm ${p.primary ? 'text-primary-foreground/70' : '__MUTED__'}`}>{p.period}</span>
              </div>
              <p className={`mt-2 text-sm ${p.primary ? 'text-primary-foreground/80' : '__MUTED__'}`}>{p.desc}</p>
              <ul className="mt-6 space-y-3">
                {p.features.map((f) => (
                  <li key={f} className={`flex items-center gap-2 text-sm ${p.primary ? 'text-primary-foreground' : '__HEAD__'}`}>
                    <Icon name="check" className={`h-4 w-4 shrink-0 ${p.primary ? 'text-primary-foreground' : 'text-primary'}`} />{f}
                  </li>
                ))}
              </ul>
              <Link href="/register" className={`mt-8 block rounded-xl px-6 py-3 text-center text-sm font-semibold transition ${p.primary ? 'bg-primary-foreground text-primary hover:opacity-90' : 'bg-primary text-primary-foreground hover:opacity-90'}`}>{p.cta}</Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}"""

F["event_cards"] = """function __NAME__() {
  const events = [
    { title: 'Annual Summit 2025', date: 'Jul 15-17', location: 'San Francisco, CA', type: 'Conference', seats: '2,000+', img: 'event1.jpg' },
    { title: 'Workshop: Advanced Techniques', date: 'Jul 28', location: 'Online (Live)', type: 'Workshop', seats: '200', img: 'event2.jpg' },
    { title: 'Community Meetup', date: 'Aug 5', location: 'New York, NY', type: 'Networking', seats: '500', img: 'event3.jpg' },
    { title: 'Product Launch: v3.0', date: 'Aug 20', location: 'Online', type: 'Launch Event', seats: 'Unlimited', img: 'event4.jpg' },
  ];
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-7xl">
        <div className="mb-12 flex items-end justify-between">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest __EYE__">Events</p>
            <h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">Upcoming events</h2>
          </div>
          <Link href="/events" className="hidden text-sm font-semibold text-primary sm:block">All events <Icon name="arrow-right" className="inline h-4 w-4" /></Link>
        </div>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {events.map((e) => (
            <div key={e.title} className="__CARD__ overflow-hidden rounded-2xl shadow-sm transition hover:-translate-y-1 hover:shadow-md">
              <div className="h-40 overflow-hidden"><img src={'/assets/' + e.img} alt={e.title} className="h-full w-full object-cover" /></div>
              <div className="p-4">
                <span className="rounded-lg bg-primary/10 px-2 py-1 text-xs font-semibold text-primary">{e.type}</span>
                <h3 className="mt-2 text-sm font-bold __HEAD__">{e.title}</h3>
                <div className="mt-2 space-y-1 text-xs __MUTED__">
                  <div className="flex items-center gap-1.5"><Icon name="calendar" className="h-3.5 w-3.5 text-primary" />{e.date}</div>
                  <div className="flex items-center gap-1.5"><Icon name="map-pin" className="h-3.5 w-3.5 text-primary" />{e.location}</div>
                  <div className="flex items-center gap-1.5"><Icon name="users" className="h-3.5 w-3.5 text-primary" />{e.seats} seats</div>
                </div>
                <button className="mt-3 w-full rounded-xl bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground transition hover:opacity-90">Register</button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}"""

F["integrations_grid"] = """function __NAME__() {
  const tools = [
    'Slack', 'Notion', 'GitHub', 'Jira', 'Figma', 'Zapier',
    'Salesforce', 'HubSpot', 'Stripe', 'Shopify', 'Google', 'Zoom',
  ];
  return (
    <section className="__SEC__ px-4 py-24 md:px-6">
      <div className="mx-auto max-w-5xl">
        <div className="mx-auto mb-12 max-w-2xl text-center">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest __EYE__">Integrations</p>
          <h2 className="font-display text-3xl font-bold md:text-4xl __HEAD__">Works with your favourite tools</h2>
          <p className="mt-4 __MUTED__">Connect in one click. 80+ integrations available out of the box.</p>
        </div>
        <div className="grid grid-cols-3 gap-4 sm:grid-cols-4 lg:grid-cols-6">
          {tools.map((t) => (
            <div key={t} className="__CARD__ flex flex-col items-center rounded-2xl p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
              <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary font-bold text-sm">{t[0]}</div>
              <span className="text-xs font-semibold __HEAD__">{t}</span>
            </div>
          ))}
        </div>
        <p className="mt-8 text-center text-sm __MUTED__">...and 70+ more. <Link href="/integrations" className="text-primary font-semibold">View all</Link></p>
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
    # ── new category-specific families ──
    "product_showcase": ["shop", "store", "ecommerce", "marketplace", "product", "retail"],
    "review_wall":      ["shop", "ecommerce", "marketplace", "restaurant", "hotel", "service", "any"],
    "course_cards":     ["education", "lms", "course", "learning", "school", "training"],
    "doctor_cards":     ["healthcare", "clinic", "hospital", "medical", "health", "dental"],
    "property_grid":    ["real-estate", "property", "rental", "apartment", "housing", "estate"],
    "blog_grid":        ["blog", "news", "magazine", "content", "media", "publishing", "any"],
    "video_section":    ["any", "saas", "education", "onboarding", "explainer"],
    "map_section":      ["restaurant", "hotel", "service", "clinic", "agency", "business"],
    "process_split":    ["agency", "service", "consulting", "saas", "any"],
    "brand_story":      ["any", "startup", "agency", "corporate", "about"],
    "feature_tabs":     ["saas", "platform", "tool", "app", "software", "any"],
    "pricing_plans":    ["saas", "subscription", "service", "b2b", "any"],
    "event_cards":      ["event", "conference", "entertainment", "community", "education"],
    "integrations_grid":["saas", "platform", "tool", "tech", "software", "enterprise"],
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
