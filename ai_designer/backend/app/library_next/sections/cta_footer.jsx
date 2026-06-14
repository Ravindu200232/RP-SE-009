// SECTION: closing CTA + footer (owns cta anchors + footer_tag + App Name).
function CtaFooter() {
  return (
    <>
      <section className="px-4 pb-24 md:px-6">
        <div className="relative mx-auto max-w-5xl overflow-hidden rounded-[2rem] bg-primary p-12 text-center text-primary-foreground">
          <div className="absolute -right-16 -top-16 h-56 w-56 rounded-full bg-white/10 blur-2xl" />
          <h2 className="relative mb-3 font-display text-3xl font-bold md:text-5xl">Final call-to-action headline</h2>
          <p className="relative mb-8 opacity-85">One sentence of encouragement.</p>
          <Link href="/register" className="relative inline-block rounded-xl bg-background px-8 py-3.5 font-semibold text-foreground shadow-xl transition hover:opacity-90">Start now - it's free</Link>
        </div>
      </section>
      <footer className="border-t px-4 py-12 md:px-6">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-6">
          <div className="flex items-center gap-2.5">
            <img src="/assets/logo.jpg" alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }} className="h-8 w-8 rounded-lg object-cover" />
            <div>
              <p className="font-display text-lg font-bold leading-tight">App Name</p>
              <p className="text-xs text-muted-foreground">One-line app description.</p>
            </div>
          </div>
          <div className="flex gap-6 text-sm text-muted-foreground">
            <Link href="/features" className="hover:text-foreground">Features</Link>
            <Link href="/about" className="hover:text-foreground">About</Link>
            <Link href="/contact" className="hover:text-foreground">Contact</Link>
            <Link href="/login" className="hover:text-foreground">Sign in</Link>
          </div>
          <p className="text-xs text-muted-foreground">(c) 2026 App Name</p>
        </div>
      </footer>
    </>
  );
}
