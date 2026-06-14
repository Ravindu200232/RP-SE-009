// SECTION: hero. Ultra-clean centered hero - no photo, generous whitespace,
// soft dotted backdrop (for corporate/legal/minimal domains).
function HeroCenteredClean() {
  return (
    <section className="relative overflow-hidden px-4 py-32 md:px-6">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle,hsl(var(--primary)/0.06)_1px,transparent_1px)] [background-size:24px_24px]" />
      <div className="relative mx-auto max-w-3xl text-center">
        <p className="mb-6 text-xs font-semibold uppercase tracking-[0.3em] text-primary">Tagline category</p>
        <h1 className="font-display text-5xl font-bold leading-[1.05] tracking-tight md:text-7xl">
          Headline part <span className="underline decoration-primary decoration-4 underline-offset-8">accent words</span> here
        </h1>
        <p className="mx-auto mt-7 max-w-xl text-lg text-muted-foreground">One or two sentences describing the product value for the target user.</p>
        <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
          <Link href="/register" className="rounded-lg bg-primary px-9 py-4 font-semibold text-primary-foreground shadow-lg transition hover:opacity-90">Get Started Free</Link>
          <Link href="/login" className="inline-flex items-center gap-2 px-4 py-4 font-semibold text-primary transition hover:opacity-80">Sign in <Icon name="arrow-right" className="h-4 w-4" /></Link>
        </div>
        <p className="mt-10 text-sm text-muted-foreground">Loved by 10,000+ teams</p>
      </div>
    </section>
  );
}
