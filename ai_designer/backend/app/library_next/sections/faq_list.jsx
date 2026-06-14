// SECTION: faq (owns `const faqs` + faqOpen state).
function FaqList() {
  const faqs = [
    { q: 'Question one?', a: 'Two-sentence answer.' },
    { q: 'Question two?', a: 'Two-sentence answer.' },
    { q: 'Question three?', a: 'Two-sentence answer.' },
    { q: 'Question four?', a: 'Two-sentence answer.' },
    { q: 'Question five?', a: 'Two-sentence answer.' },
  ];
  const [faqOpen, setFaqOpen] = useState(-1);
  return (
    <section className="px-4 py-24 md:px-6">
      <div className="mx-auto max-w-3xl">
        <h2 className="mb-12 text-center font-display text-3xl font-bold md:text-4xl">Frequently asked questions</h2>
        <div className="space-y-3">
          {faqs.map((f, i) => (
            <div key={f.q} className="rounded-xl border bg-card">
              <button onClick={() => setFaqOpen(faqOpen === i ? -1 : i)} className="flex w-full items-center justify-between px-5 py-4 text-left font-medium">
                {f.q}
                <Icon name="chevron-down" className={'h-4 w-4 text-primary transition-transform ' + (faqOpen === i ? 'rotate-180' : '')} />
              </button>
              {faqOpen === i && <p className="px-5 pb-4 text-sm leading-relaxed text-muted-foreground">{f.a}</p>}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
