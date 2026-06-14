// SECTION: features (owns `const features`). Icon tiles with hover ring.
function FeatureTiles() {
  const features = [
    { icon: 'zap', title: 'Feature one', text: 'One sentence about this capability and the benefit it brings.' },
    { icon: 'shield', title: 'Feature two', text: 'One sentence about this capability and the benefit it brings.' },
    { icon: 'chart', title: 'Feature three', text: 'One sentence about this capability and the benefit it brings.' },
    { icon: 'users', title: 'Feature four', text: 'One sentence about this capability and the benefit it brings.' },
    { icon: 'clock', title: 'Feature five', text: 'One sentence about this capability and the benefit it brings.' },
    { icon: 'star', title: 'Feature six', text: 'One sentence about this capability and the benefit it brings.' },
  ];
  return (
    <section className="px-4 py-24 md:px-6">
      <div className="mx-auto max-w-7xl">
        <div className="mx-auto mb-14 max-w-2xl text-center">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-primary">Features</p>
          <h2 className="font-display text-3xl font-bold md:text-5xl">Section heading about what you get</h2>
        </div>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <div key={f.title} className="rounded-2xl border bg-card p-6 shadow-sm ring-primary/30 transition hover:-translate-y-0.5 hover:shadow-md hover:ring-2">
              <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary"><Icon name={f.icon} className="h-5 w-5" /></div>
              <h3 className="mb-1.5 text-lg font-semibold">{f.title}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">{f.text}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
