// SECTION: hero (owns hero anchors). Inspired by the user's LMS hero -
// crossfading background photos with a dark wash and centered copy.
function HeroSlider() {
  const slides = ['/assets/hero.jpg', '/assets/gallery1.jpg', '/assets/banner.jpg'];
  const [bg, setBg] = useState(0);
  React.useEffect(() => {
    const t = setInterval(() => setBg((p) => (p + 1) % slides.length), 5000);
    return () => clearInterval(t);
  }, []);
  return (
    <section className="relative flex min-h-[88vh] items-center justify-center overflow-hidden bg-black text-white">
      {slides.map((s, i) => (
        <img key={s} src={s} alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }}
          className={'absolute inset-0 h-full w-full object-cover transition-opacity duration-1000 ' + (bg === i ? 'opacity-50' : 'opacity-0')} />
      ))}
      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/30 to-black/40" />
      <div className="relative z-10 mx-auto max-w-4xl px-4 py-24 text-center">
        <p className="mb-5 inline-block rounded-full border border-white/25 bg-white/10 px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.3em] backdrop-blur">Tagline category</p>
        <h1 className="font-display text-5xl font-bold leading-[1.04] tracking-tight md:text-7xl">
          Headline part <span className="text-ACCENT-400">accent words</span> here
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-white/80">One or two sentences describing the product value for the target user.</p>
        <div className="mt-9 flex flex-wrap items-center justify-center gap-4">
          <Link href="/register" className="rounded-full bg-ACCENT-500 px-8 py-3.5 font-semibold text-white shadow-xl shadow-ACCENT-500/30 transition hover:bg-ACCENT-400">Get Started Free</Link>
          <Link href="/login" className="rounded-full border border-white/30 px-8 py-3.5 font-semibold text-white/90 backdrop-blur transition hover:bg-white/10">Sign in</Link>
        </div>
        <p className="mt-8 text-sm text-white/60">Loved by 10,000+ teams</p>
        <div className="mt-5 flex items-center justify-center gap-2">
          {slides.map((_, i) => (
            <button key={i} aria-label={'Slide ' + (i + 1)} onClick={() => setBg(i)}
              className={'h-1.5 rounded-full transition-all ' + (bg === i ? 'w-8 bg-ACCENT-400' : 'w-3 bg-white/30 hover:bg-white/50')} />
          ))}
        </div>
      </div>
    </section>
  );
}
