// SECTION: hero. Shop-style hero - copy left, product showcase card right with
// price chip and floating thumbnails (inspired by the user's shop projects).
function HeroProductCard() {
  return (
    <section className="bg-muted/30 px-4 py-20 md:px-6">
      <div className="mx-auto grid max-w-7xl items-center gap-12 lg:grid-cols-2">
        <div>
          <p className="mb-4 inline-block rounded-full bg-primary/10 px-4 py-1.5 text-xs font-semibold uppercase tracking-widest text-primary">Tagline category</p>
          <h1 className="font-display text-5xl font-bold leading-[1.05] tracking-tight md:text-6xl">
            Headline part <span className="text-primary">accent words</span> here
          </h1>
          <p className="mt-5 max-w-xl text-lg text-muted-foreground">One or two sentences describing the product value for the target user.</p>
          <div className="mt-8 flex flex-wrap gap-4">
            <Link href="/register" className="rounded-xl bg-primary px-8 py-3.5 font-semibold text-primary-foreground shadow-lg transition hover:opacity-90">Get Started Free</Link>
            <Link href="/login" className="rounded-xl border bg-background px-8 py-3.5 font-semibold transition hover:bg-accent">Sign in</Link>
          </div>
          <p className="mt-7 text-sm text-muted-foreground">Loved by 10,000+ teams</p>
        </div>
        <div className="relative">
          <div className="rounded-[2rem] border bg-card p-5 shadow-2xl">
            <img src="/assets/hero.jpg" alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }}
              className="h-80 w-full rounded-3xl object-cover" />
            <div className="mt-4 flex items-center justify-between px-2 pb-1">
              <div>
                <p className="font-semibold">Featured</p>
                <p className="text-xs text-muted-foreground">Top pick this week</p>
              </div>
              <span className="rounded-full bg-primary px-4 py-1.5 text-sm font-bold text-primary-foreground">New</span>
            </div>
          </div>
          <img src="/assets/gallery1.jpg" alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }}
            className="absolute -left-6 -bottom-6 hidden h-24 w-24 rounded-2xl border-4 border-background object-cover shadow-xl md:block" />
          <img src="/assets/gallery2.jpg" alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }}
            className="absolute -right-4 top-10 hidden h-20 w-20 rounded-2xl border-4 border-background object-cover shadow-xl md:block" />
        </div>
      </div>
    </section>
  );
}
