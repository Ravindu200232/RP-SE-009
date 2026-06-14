// SECTION: about/benefits (owns about anchors + Benefit points).
function WhyChooseSplit() {
  return (
    <section className="bg-muted/40 px-4 py-24 md:px-6">
      <div className="mx-auto grid max-w-7xl items-center gap-12 lg:grid-cols-2">
        <div className="relative">
          <img src="/assets/about1.jpg" alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }}
            className="h-[420px] w-full rounded-[2rem] object-cover shadow-xl" />
          <img src="/assets/about2.jpg" alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }}
            className="absolute -bottom-8 -right-4 hidden h-44 w-36 rounded-2xl border-4 border-background object-cover shadow-2xl md:block" />
        </div>
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.3em] text-primary">Why choose us</p>
          <h2 className="mb-5 font-display text-3xl font-bold md:text-4xl">Benefits heading goes here</h2>
          <p className="mb-7 leading-relaxed text-muted-foreground">Two sentences on the overall benefit story for this audience.</p>
          <ul className="space-y-3.5">
            {['Benefit point one', 'Benefit point two', 'Benefit point three', 'Benefit point four'].map((b) => (
              <li key={b} className="flex items-center gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary"><Icon name="check" className="h-3.5 w-3.5" /></span>
                <span className="text-sm">{b}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
