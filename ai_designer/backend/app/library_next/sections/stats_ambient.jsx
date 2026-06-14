// SECTION: stats (owns `const stats`). Inspired by the user's LMS stats band -
// ambient radial washes + wide-tracking eyebrow + big numbers.
function StatsAmbient() {
  const stats = [['10k+', 'Customers'], ['99.9%', 'Uptime'], ['4.9/5', 'Avg rating'], ['24/7', 'Support']];
  return (
    <section className="relative overflow-hidden py-20 md:py-28">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,hsl(var(--primary)/0.08),transparent_40%),radial-gradient(circle_at_bottom_right,hsl(var(--primary)/0.07),transparent_35%)]" />
      <div className="relative mx-auto max-w-7xl px-4 md:px-6">
        <div className="mx-auto mb-14 max-w-3xl text-center">
          <p className="text-sm font-semibold uppercase tracking-[0.3em] text-primary">By the numbers</p>
          <h2 className="mt-4 font-display text-3xl font-bold tracking-tight md:text-5xl">Section heading about capabilities</h2>
          <p className="mt-4 text-base leading-7 text-muted-foreground md:text-lg">One supporting sentence for this section.</p>
        </div>
        <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
          {stats.map(([n, l]) => (
            <div key={l} className="rounded-2xl border bg-background/70 p-7 text-center shadow-sm backdrop-blur">
              <p className="font-display text-4xl font-bold text-primary md:text-5xl">{n}</p>
              <p className="mt-2 text-sm text-muted-foreground">{l}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
