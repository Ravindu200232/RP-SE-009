// SECTION: hero. Dark panel with photo LEFT and copy right - night/media feel.
function HeroPhotoLeftDark() {
  return (
    <section className="bg-zinc-950 px-4 py-20 text-white md:px-6">
      <div className="mx-auto grid max-w-7xl items-center gap-12 lg:grid-cols-2">
        <div className="relative order-2 lg:order-1">
          <div className="pointer-events-none absolute -inset-4 rounded-[2.5rem] bg-ACCENT-500/15 blur-2xl" />
          <img src="/assets/hero.jpg" alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }}
            className="relative h-[440px] w-full rounded-[2rem] border border-white/10 object-cover shadow-2xl" />
        </div>
        <div className="order-1 lg:order-2">
          <p className="mb-5 inline-block rounded-full border border-ACCENT-400/30 bg-ACCENT-500/10 px-4 py-1.5 text-xs font-semibold uppercase tracking-widest text-ACCENT-300">Tagline category</p>
          <h1 className="font-display text-5xl font-bold leading-[1.05] tracking-tight md:text-6xl">
            Headline part <span className="text-ACCENT-400">accent words</span> here
          </h1>
          <p className="mt-6 max-w-xl text-lg text-zinc-400">One or two sentences describing the product value for the target user.</p>
          <div className="mt-9 flex flex-wrap gap-4">
            <Link href="/register" className="rounded-xl bg-ACCENT-500 px-8 py-3.5 font-semibold text-white shadow-xl shadow-ACCENT-500/25 transition hover:bg-ACCENT-400">Get Started Free</Link>
            <Link href="/login" className="rounded-xl border border-white/20 px-8 py-3.5 font-semibold text-zinc-200 transition hover:bg-white/5">Sign in</Link>
          </div>
          <p className="mt-8 text-sm text-zinc-500">Loved by 10,000+ teams</p>
        </div>
      </div>
    </section>
  );
}
