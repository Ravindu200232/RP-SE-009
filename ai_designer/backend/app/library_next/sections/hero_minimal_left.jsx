// SECTION: hero. Quiet corporate hero - left-aligned, thin rule, photo right.
function HeroMinimalLeft() {
  return (
    <section className="px-4 py-24 md:px-6">
      <div className="mx-auto grid max-w-7xl items-center gap-14 lg:grid-cols-2">
        <div>
          <div className="mb-6 flex items-center gap-3">
            <span className="h-px w-10 bg-primary" />
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-primary">Tagline category</p>
          </div>
          <h1 className="font-display text-4xl font-semibold leading-[1.08] tracking-tight md:text-6xl">
            Headline part <span className="text-primary">accent words</span> here
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted-foreground">One or two sentences describing the product value for the target user.</p>
          <div className="mt-9 flex flex-wrap gap-4">
            <Link href="/register" className="rounded-lg bg-primary px-7 py-3.5 font-semibold text-primary-foreground shadow transition hover:opacity-90">Get Started Free</Link>
            <Link href="/login" className="rounded-lg border px-7 py-3.5 font-semibold transition hover:bg-accent">Sign in</Link>
          </div>
          <div className="mt-10 flex items-center gap-6 border-t pt-6 text-sm text-muted-foreground">
            <span className="flex items-center gap-1.5"><Icon name="check" className="h-4 w-4 text-primary" /> No credit card</span>
            <span className="flex items-center gap-1.5"><Icon name="check" className="h-4 w-4 text-primary" /> Loved by 10,000+ teams</span>
          </div>
        </div>
        <img src="/assets/hero.jpg" alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }}
          className="h-[460px] w-full rounded-2xl object-cover shadow-lg" />
      </div>
    </section>
  );
}
