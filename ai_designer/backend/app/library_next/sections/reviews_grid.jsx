// SECTION: testimonials (owns `const quotes`). Oversized quote marks.
function ReviewsGrid() {
  const quotes = [
    { n: 'Full Name', r: 'Role, Company', t: 'Two-sentence testimonial quote.' },
    { n: 'Full Name', r: 'Role, Company', t: 'Two-sentence testimonial quote.' },
    { n: 'Full Name', r: 'Role, Company', t: 'Two-sentence testimonial quote.' },
  ];
  return (
    <section className="px-4 py-24 md:px-6">
      <div className="mx-auto max-w-7xl">
        <h2 className="mb-14 text-center font-display text-3xl font-bold md:text-4xl">What customers say</h2>
        <div className="grid gap-6 md:grid-cols-3">
          {quotes.map((q) => (
            <div key={q.n + q.r} className="relative rounded-2xl border bg-card p-7 shadow-sm">
              <span className="pointer-events-none absolute -top-3 left-5 font-display text-7xl leading-none text-primary/15">"</span>
              <p className="relative mb-6 leading-relaxed">{q.t}</p>
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary font-bold text-primary-foreground">{String(q.n || '?').charAt(0)}</div>
                <div><p className="text-sm font-semibold">{q.n}</p><p className="text-xs text-muted-foreground">{q.r}</p></div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
