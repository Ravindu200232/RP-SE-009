// SECTION: hero (owns hero anchors). Inspired by the user's CleanMate hero -
// split radial background, italic accent in a serif display headline, pill CTA
// with a circular arrow chip.
function HeroSplitRadial() {
  return (
    <section className="relative overflow-hidden">
      <div className="absolute inset-0 -z-10">
        <div className="absolute right-0 top-0 hidden h-full w-1/2 bg-[radial-gradient(ellipse_at_center,hsl(var(--primary)/0.14),transparent_65%)] lg:block" />
        <div className="absolute left-0 top-0 hidden h-full w-1/2 bg-muted/40 lg:block" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,hsl(var(--primary)/0.10),transparent_60%)] lg:hidden" />
      </div>
      <div className="mx-auto grid max-w-7xl items-center gap-12 px-4 pb-24 pt-16 md:px-6 lg:grid-cols-12 lg:pt-24">
        <div className="lg:col-span-7">
          <p className="mb-5 text-xs font-semibold uppercase tracking-[0.3em] text-primary">Tagline category</p>
          <h1 className="font-display text-5xl font-medium leading-[0.99] tracking-[-0.02em] md:text-7xl">
            Headline part <span className="italic text-primary">accent words</span> here
          </h1>
          <p className="mt-6 max-w-[560px] text-[17px] leading-relaxed text-muted-foreground">One or two sentences describing the product value for the target user.</p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link href="/register" className="group inline-flex items-center gap-2 rounded-full bg-primary py-2 pl-6 pr-2 text-[15px] font-semibold text-primary-foreground shadow-lg transition hover:opacity-90">
              Get Started Free
              <span className="ml-1 grid h-9 w-9 place-items-center rounded-full bg-ACCENT-200 text-ACCENT-900 transition-transform group-hover:translate-x-0.5">
                <Icon name="arrow-right" className="h-4 w-4" />
              </span>
            </Link>
            <Link href="/login" className="rounded-full border px-6 py-3 text-[15px] font-semibold transition hover:bg-accent">Sign in</Link>
          </div>
          <p className="mt-7 text-sm text-muted-foreground">Loved by 10,000+ teams</p>
        </div>
        <div className="relative lg:col-span-5">
          <img src="/assets/hero.jpg" alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }}
            className="w-full rounded-[2rem] object-cover shadow-2xl" />
          <div className="absolute -bottom-5 -left-5 rounded-2xl border bg-background px-5 py-3.5 shadow-xl">
            <p className="text-xs text-muted-foreground">This month</p>
            <p className="font-display text-xl font-bold text-primary">+2,340 records</p>
          </div>
        </div>
      </div>
    </section>
  );
}
