// SECTION: hero. Dark glow hero with gradient headline + floating metric chips.
function HeroGradientGlow() {
  return (
    <section className="relative overflow-hidden bg-zinc-950 px-4 py-28 text-white md:px-6">
      <div className="pointer-events-none absolute -top-40 left-1/2 h-[560px] w-[560px] -translate-x-1/2 rounded-full bg-ACCENT-600/25 blur-3xl" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-72 w-72 rounded-full bg-ACCENT-400/10 blur-3xl" />
      <div className="relative mx-auto max-w-4xl text-center">
        <p className="mb-6 inline-block rounded-full border border-ACCENT-400/30 bg-ACCENT-500/10 px-4 py-1.5 text-xs font-semibold uppercase tracking-widest text-ACCENT-300">Tagline category</p>
        <h1 className="font-display text-5xl font-bold leading-[1.04] tracking-tight md:text-7xl">
          Headline part <span className="bg-gradient-to-r from-ACCENT-400 via-ACCENT-300 to-ACCENT-200 bg-clip-text text-transparent">accent words</span> here
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-zinc-400">One or two sentences describing the product value for the target user.</p>
        <div className="mt-9 flex flex-wrap items-center justify-center gap-4">
          <Link href="/register" className="rounded-xl bg-ACCENT-500 px-8 py-3.5 font-semibold text-white shadow-2xl shadow-ACCENT-500/30 transition hover:bg-ACCENT-400">Get Started Free</Link>
          <Link href="/login" className="inline-flex items-center gap-2 px-4 py-3.5 font-medium text-zinc-300 transition hover:text-white">Sign in <Icon name="arrow-right" className="h-4 w-4" /></Link>
        </div>
      </div>
      <div className="relative mx-auto mt-14 max-w-5xl">
        <img src="/assets/hero.jpg" alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }}
          className="w-full rounded-3xl border border-white/10 object-cover opacity-90 shadow-2xl" />
        <div className="absolute -left-4 top-8 hidden rounded-2xl border border-white/10 bg-zinc-900/90 px-5 py-3 shadow-xl backdrop-blur md:block">
          <p className="text-xs text-zinc-400">Live metric</p>
          <p className="font-display text-xl font-bold text-ACCENT-300">+128%</p>
        </div>
        <div className="absolute -right-4 bottom-8 hidden rounded-2xl border border-white/10 bg-zinc-900/90 px-5 py-3 shadow-xl backdrop-blur md:block">
          <p className="text-xs text-zinc-400">Loved by 10,000+ teams</p>
          <p className="font-display text-lg font-bold text-white">***** 4.9</p>
        </div>
      </div>
    </section>
  );
}
