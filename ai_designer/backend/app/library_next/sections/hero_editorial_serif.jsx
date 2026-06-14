// SECTION: hero. Editorial boutique hero - oversized serif display, full-width
// photo beneath with floating rating card.
function HeroEditorialSerif() {
  return (
    <section className="px-4 pb-16 pt-20 md:px-6">
      <div className="mx-auto max-w-7xl">
        <div className="grid items-end gap-10 lg:grid-cols-12">
          <div className="lg:col-span-7">
            <p className="mb-5 text-xs font-semibold uppercase tracking-[0.3em] text-primary">Tagline category</p>
            <h1 className="font-display text-5xl font-bold leading-[1.0] tracking-tight md:text-7xl">
              Headline part <span className="italic text-primary">accent words</span> here
            </h1>
          </div>
          <div className="lg:col-span-5 lg:pb-2">
            <p className="mb-7 max-w-md text-lg text-muted-foreground">One or two sentences describing the product value for the target user.</p>
            <div className="flex flex-wrap items-center gap-4">
              <Link href="/register" className="rounded-full bg-foreground px-7 py-3.5 font-semibold text-background transition hover:opacity-90">Get Started Free</Link>
              <Link href="/login" className="inline-flex items-center gap-2 font-semibold text-primary transition hover:opacity-80">Sign in <Icon name="arrow-right" className="h-4 w-4" /></Link>
            </div>
          </div>
        </div>
        <div className="relative mt-12">
          <img src="/assets/hero.jpg" alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }}
            className="h-[420px] w-full rounded-[2rem] object-cover shadow-xl" />
          <div className="absolute bottom-6 left-6 rounded-2xl bg-background/95 px-6 py-4 shadow-lg backdrop-blur">
            <p className="font-display text-2xl font-bold">4.9 <span className="text-amber-500">*****</span></p>
            <p className="text-xs text-muted-foreground">Loved by 10,000+ teams</p>
          </div>
        </div>
      </div>
    </section>
  );
}
