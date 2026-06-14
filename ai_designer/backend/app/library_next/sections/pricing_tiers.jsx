// SECTION: pricing (owns `const tiers`).
function PricingTiers() {
  const tiers = [
    { name: 'Starter', price: 19, popular: false, items: ['Item A', 'Item B', 'Item C', 'Item D'] },
    { name: 'Professional', price: 49, popular: true, items: ['Everything in Starter', 'Item E', 'Item F', 'Item G', 'Item H'] },
    { name: 'Enterprise', price: 99, popular: false, items: ['Everything in Pro', 'Item I', 'Item J', 'Item K'] },
  ];
  return (
    <section className="bg-muted/40 px-4 py-24 md:px-6">
      <div className="mx-auto max-w-7xl">
        <div className="mx-auto mb-14 max-w-2xl text-center">
          <h2 className="font-display text-3xl font-bold md:text-5xl">Simple pricing</h2>
          <p className="mt-3 text-muted-foreground">One sentence about pricing philosophy.</p>
        </div>
        <div className="grid items-start gap-6 md:grid-cols-3">
          {tiers.map((t) => (
            <div key={t.name} className={'rounded-2xl border bg-card p-7 ' + (t.popular ? 'relative shadow-xl ring-2 ring-primary' : 'shadow-sm')}>
              {t.popular && <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-primary px-3 py-1 text-xs font-semibold text-primary-foreground">Most popular</span>}
              <h3 className="text-lg font-semibold">{t.name}</h3>
              <p className="my-4"><span className="font-display text-4xl font-bold">${t.price}</span><span className="text-sm text-muted-foreground">/month</span></p>
              <ul className="mb-7 space-y-2.5 text-sm text-muted-foreground">
                {t.items.map((it) => <li key={it} className="flex items-center gap-2"><Icon name="check" className="h-4 w-4 text-primary" />{it}</li>)}
              </ul>
              <Link href="/register" className={'block rounded-xl px-5 py-3 text-center font-semibold transition ' + (t.popular ? 'bg-primary text-primary-foreground hover:opacity-90' : 'border hover:bg-accent')}>Choose {t.name}</Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
