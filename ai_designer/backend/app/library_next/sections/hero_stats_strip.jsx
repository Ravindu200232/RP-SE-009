// SECTION: hero. Centered hero with an inline stats strip under the CTAs
// (owns hero anchors AND `const stats` - composer must not also pick StatsAmbient).
function HeroStatsStrip() {
  const stats = [['10k+', 'Customers'], ['99.9%', 'Uptime'], ['4.9/5', 'Avg rating'], ['24/7', 'Support']];
  return (
    <section className="px-4 pb-20 pt-24 md:px-6">
      <div className="mx-auto max-w-4xl text-center">
        <p className="mb-5 inline-block rounded-full bg-primary/10 px-4 py-1.5 text-xs font-semibold uppercase tracking-widest text-primary">Tagline category</p>
        <h1 className="font-display text-5xl font-bold leading-[1.05] tracking-tight md:text-7xl">
          Headline part <span className="text-primary">accent words</span> here
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">One or two sentences describing the product value for the target user.</p>
        <div className="mt-9 flex flex-wrap items-center justify-center gap-4">
          <Link href="/register" className="rounded-xl bg-primary px-8 py-3.5 font-semibold text-primary-foreground shadow-lg transition hover:opacity-90">Get Started Free</Link>
          <Link href="/login" className="rounded-xl border px-8 py-3.5 font-semibold transition hover:bg-accent">Sign in</Link>
        </div>
      </div>
      <div className="mx-auto mt-14 grid max-w-4xl grid-cols-2 divide-x rounded-2xl border bg-card shadow-sm md:grid-cols-4">
        {stats.map(([n, l]) => (
          <div key={l} className="px-4 py-6 text-center">
            <p className="font-display text-2xl font-bold text-primary md:text-3xl">{n}</p>
            <p className="mt-1 text-xs text-muted-foreground">{l}</p>
          </div>
        ))}
      </div>
      <div className="mx-auto mt-12 max-w-6xl">
        <img src="/assets/hero.jpg" alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }}
          className="max-h-[440px] w-full rounded-3xl object-cover shadow-xl" />
      </div>
    </section>
  );
}
