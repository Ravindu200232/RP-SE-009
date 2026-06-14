// SECTION: hero. True 50/50 split screen - copy panel left, full-bleed photo right.
function HeroSplitScreen() {
  return (
    <section className="grid min-h-[80vh] lg:grid-cols-2">
      <div className="flex items-center bg-muted/30 px-6 py-20 md:px-12">
        <div className="max-w-xl">
          <p className="mb-5 text-xs font-semibold uppercase tracking-[0.25em] text-primary">Tagline category</p>
          <h1 className="font-display text-4xl font-bold leading-[1.06] tracking-tight md:text-6xl">
            Headline part <span className="text-primary">accent words</span> here
          </h1>
          <p className="mt-6 text-lg leading-relaxed text-muted-foreground">One or two sentences describing the product value for the target user.</p>
          <div className="mt-9 flex flex-wrap gap-4">
            <Link href="/register" className="rounded-xl bg-primary px-8 py-3.5 font-semibold text-primary-foreground shadow-lg transition hover:opacity-90">Get Started Free</Link>
            <Link href="/login" className="rounded-xl border bg-background px-8 py-3.5 font-semibold transition hover:bg-accent">Sign in</Link>
          </div>
          <p className="mt-8 text-sm text-muted-foreground">Loved by 10,000+ teams</p>
        </div>
      </div>
      <div className="relative min-h-[320px]">
        <img src="/assets/hero.jpg" alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }}
          className="absolute inset-0 h-full w-full object-cover" />
        <div className="absolute bottom-6 left-6 rounded-2xl bg-background/90 px-5 py-3.5 shadow-xl backdrop-blur">
          <p className="text-xs text-muted-foreground">This month</p>
          <p className="font-display text-xl font-bold text-primary">+2,340 records</p>
        </div>
      </div>
    </section>
  );
}
