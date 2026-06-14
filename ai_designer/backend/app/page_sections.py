"""Domain-driven section composer for the public (marketing) pages.

The complaint this solves: every app's secondary pages looked identical. Here
each page is assembled from a VARIED pack of sections whose copy is filled from
the Deep Research blueprint's own domain data (key_features, terminology,
entities, image_subjects). So a school's "Admissions" page and a restaurant's
"Menu Management" page are built from different sections AND different words -
a human can tell what the product is for at a glance. All deterministic and
build-safe (no LLM in the hot path), server components, <div> roots (the
(marketing) layout already provides <main> + Navbar).
"""
import re

# ----------------------------------------------------------------- text helpers
def _t(s, n=200):
    s = str(s or "").replace("{", "").replace("}", "").replace("<", "").replace(">", "")
    return s[:n]


def _title(s):
    return _t(s, 60)


def _img(asset, h, extra=""):
    """bg-image tile that degrades to a tinted block when the asset is missing."""
    return (
        f'<div className="{h} w-full overflow-hidden rounded-2xl bg-gradient-to-br '
        f'from-primary/20 to-primary/5 {extra}" '
        f'style={{{{ backgroundImage: "url(/assets/{asset})", backgroundSize: "cover", '
        f'backgroundPosition: "center" }}}} />'
    )


# ----------------------------------------------------------------- section builders
def hero_split(kicker, title, sub, asset, cta="Get started", cta2="Learn more"):
    return (
        '      <section data-component-id="hero" data-component-label="Page hero" className="border-b">\n'
        '        <div className="mx-auto grid max-w-6xl items-center gap-10 px-6 py-16 md:grid-cols-2 md:py-24">\n'
        '          <div>\n'
        '            <p className="mb-3 inline-block rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-primary">' + _t(kicker, 40) + '</p>\n'
        '            <h1 className="font-display text-4xl font-bold tracking-tight md:text-5xl">' + _title(title) + '</h1>\n'
        '            <p className="mt-5 text-lg text-muted-foreground">' + _t(sub, 200) + '</p>\n'
        '            <div className="mt-7 flex flex-wrap gap-3">\n'
        '              <a href="/register" className="rounded-xl bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground">' + _t(cta, 24) + '</a>\n'
        '              <a href="/login" className="rounded-xl border px-6 py-3 text-sm font-semibold">' + _t(cta2, 24) + '</a>\n'
        '            </div>\n'
        '          </div>\n'
        '          ' + _img(asset, "h-72 md:h-96") + '\n'
        '        </div>\n'
        '      </section>\n'
    )


def hero_centered(kicker, title, sub, asset):
    return (
        '      <section data-component-id="hero" data-component-label="Page hero" className="relative border-b">\n'
        '        ' + _img(asset, "absolute inset-0 h-full opacity-15", "rounded-none") + '\n'
        '        <div className="relative mx-auto max-w-3xl px-6 py-20 text-center md:py-28">\n'
        '          <p className="mb-3 text-sm font-semibold uppercase tracking-wider text-primary">' + _t(kicker, 40) + '</p>\n'
        '          <h1 className="font-display text-4xl font-bold tracking-tight md:text-6xl">' + _title(title) + '</h1>\n'
        '          <p className="mx-auto mt-5 max-w-2xl text-lg text-muted-foreground">' + _t(sub, 220) + '</p>\n'
        '        </div>\n'
        '      </section>\n'
    )


def feature_grid(title, items):
    cards = ""
    for f in items[:6]:
        ft = f.get("title") if isinstance(f, dict) else f
        fd = f.get("text") if isinstance(f, dict) else ("Built in for " + str(f).lower() + ".")
        cards += (
            '          <div className="rounded-2xl border bg-card p-6 shadow-sm">\n'
            '            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary"><CheckCircle2 className="h-5 w-5" /></div>\n'
            '            <h3 className="font-display text-lg font-semibold">' + _title(ft) + '</h3>\n'
            '            <p className="mt-2 text-sm text-muted-foreground">' + _t(fd, 150) + '</p>\n'
            '          </div>\n'
        )
    return (
        '      <section className="mx-auto max-w-6xl px-6 py-20">\n'
        '        <h2 className="mb-3 font-display text-3xl font-bold">' + _title(title) + '</h2>\n'
        '        <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">\n' + cards + '        </div>\n'
        '      </section>\n'
    )


def process_steps(title, steps):
    cells = ""
    for i, s in enumerate(steps[:4], 1):
        st = s.get("title") if isinstance(s, dict) else s
        sd = s.get("text") if isinstance(s, dict) else ""
        cells += (
            '          <div className="relative rounded-2xl border bg-card p-6">\n'
            '            <span className="mb-3 flex h-9 w-9 items-center justify-center rounded-full bg-primary font-display text-sm font-bold text-primary-foreground">' + str(i) + '</span>\n'
            '            <h3 className="font-display text-base font-semibold">' + _title(st) + '</h3>\n'
            '            <p className="mt-1.5 text-sm text-muted-foreground">' + _t(sd, 120) + '</p>\n'
            '          </div>\n'
        )
    return (
        '      <section className="border-y bg-muted/30">\n'
        '        <div className="mx-auto max-w-6xl px-6 py-20">\n'
        '          <h2 className="mb-8 font-display text-3xl font-bold">' + _title(title) + '</h2>\n'
        '          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">\n' + cells + '          </div>\n'
        '        </div>\n      </section>\n'
    )


def split_image_text(title, body, asset, flip=False):
    img = '          ' + _img(asset, "h-72 md:h-80") + '\n'
    txt = (
        '          <div>\n'
        '            <h2 className="font-display text-3xl font-bold">' + _title(title) + '</h2>\n'
        '            <p className="mt-4 text-muted-foreground">' + _t(body, 320) + '</p>\n'
        '          </div>\n'
    )
    inner = (txt + img) if flip else (img + txt)
    return (
        '      <section className="mx-auto grid max-w-6xl items-center gap-10 px-6 py-20 md:grid-cols-2">\n'
        + inner + '      </section>\n'
    )


def stats_band(stats):
    cells = "".join(
        '          <div><p className="font-display text-4xl font-bold text-primary">' + _t(n, 12) +
        '</p><p className="mt-1 text-sm text-muted-foreground">' + _t(l, 30) + '</p></div>\n'
        for n, l in stats
    )
    return (
        '      <section className="border-y bg-muted/30">\n'
        '        <div className="mx-auto grid max-w-6xl grid-cols-2 gap-8 px-6 py-14 md:grid-cols-4">\n'
        + cells + '        </div>\n      </section>\n'
    )


def gallery(assets, caption="Inside the experience"):
    body = "".join('          ' + _img(a, "h-56") + "\n" for a in assets[:6])
    return (
        '      <section className="mx-auto max-w-6xl px-6 py-20">\n'
        '        <h2 className="mb-8 font-display text-3xl font-bold">' + _title(caption) + '</h2>\n'
        '        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">\n' + body + '        </div>\n'
        '      </section>\n'
    )


def terminology_chips(title, terms):
    chips = "".join(
        '          <span className="rounded-full border bg-card px-4 py-2 text-sm font-medium">' + _t(t, 30) + '</span>\n'
        for t in terms[:12]
    )
    return (
        '      <section className="mx-auto max-w-5xl px-6 py-20 text-center">\n'
        '        <h2 className="mb-8 font-display text-3xl font-bold">' + _title(title) + '</h2>\n'
        '        <div className="flex flex-wrap justify-center gap-3">\n' + chips + '        </div>\n'
        '      </section>\n'
    )


def testimonial(quote, who):
    return (
        '      <section className="mx-auto max-w-4xl px-6 py-20">\n'
        '        <figure className="rounded-3xl border bg-card p-10 text-center shadow-sm">\n'
        '          <blockquote className="font-display text-2xl font-medium leading-snug">&ldquo;' + _t(quote, 220) + '&rdquo;</blockquote>\n'
        '          <figcaption className="mt-5 text-sm text-muted-foreground">' + _t(who, 60) + '</figcaption>\n'
        '        </figure>\n      </section>\n'
    )


def faq(items):
    rows = ""
    for q, a in items[:5]:
        rows += (
            '          <div className="rounded-2xl border bg-card p-6">\n'
            '            <h3 className="font-display text-base font-semibold">' + _title(q) + '</h3>\n'
            '            <p className="mt-2 text-sm text-muted-foreground">' + _t(a, 220) + '</p>\n'
            '          </div>\n'
        )
    return (
        '      <section className="mx-auto max-w-3xl px-6 py-20">\n'
        '        <h2 className="mb-8 font-display text-3xl font-bold">Frequently asked questions</h2>\n'
        '        <div className="space-y-4">\n' + rows + '        </div>\n      </section>\n'
    )


def pricing(app_name):
    tiers = [("Starter", "$0", ["Core features", "Up to 3 users", "Community support"]),
             ("Professional", "$29", ["Everything in Starter", "Unlimited users", "Advanced analytics", "Priority support"]),
             ("Enterprise", "Custom", ["SSO & audit logs", "Dedicated manager", "Custom SLAs & onboarding"])]
    cols = ""
    for name, price, feats in tiers:
        pop = name == "Professional"
        items = "".join(
            '              <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-primary" />' + _t(x, 40) + '</li>\n'
            for x in feats)
        cols += (
            '          <div className="rounded-2xl border ' + ('border-primary shadow-lg' if pop else 'bg-card') + ' p-7">\n'
            '            <h3 className="font-display text-lg font-semibold">' + name + '</h3>\n'
            '            <p className="mt-3"><span className="font-display text-4xl font-bold">' + price + '</span><span className="text-muted-foreground">/mo</span></p>\n'
            '            <ul className="mt-6 space-y-3">\n' + items + '            </ul>\n'
            '            <a href="/register" className="mt-7 block rounded-xl ' + ('bg-primary text-primary-foreground' if pop else 'border') + ' px-4 py-2.5 text-center text-sm font-semibold">Choose ' + name + '</a>\n'
            '          </div>\n'
        )
    return (
        '      <section className="mx-auto max-w-6xl px-6 py-20">\n'
        '        <h2 className="mb-8 text-center font-display text-3xl font-bold">Simple, transparent pricing</h2>\n'
        '        <div className="grid gap-6 md:grid-cols-3">\n' + cols + '        </div>\n      </section>\n'
    )


def cta_band(app_name, label="Create your account"):
    return (
        '      <section className="mx-auto max-w-6xl px-6 pb-24 pt-4">\n'
        '        <div className="rounded-3xl bg-primary px-8 py-14 text-center text-primary-foreground">\n'
        '          <h2 className="font-display text-3xl font-bold">Ready to get started with ' + _t(app_name, 30) + '?</h2>\n'
        '          <p className="mx-auto mt-3 max-w-xl opacity-90">Join today and see why teams choose us.</p>\n'
        '          <a href="/register" className="mt-7 inline-block rounded-xl bg-background px-6 py-3 font-semibold text-foreground">' + _t(label, 30) + '</a>\n'
        '        </div>\n      </section>\n'
    )


def contact_section(app_name):
    """Static (server-safe) contact form section - for pages that include the
    'contact_form' component without making the whole page a client component."""
    fields = (
        '            <input placeholder="Your name" className="w-full rounded-xl border bg-background px-4 py-2.5 text-sm" />\n'
        '            <input type="email" placeholder="Email address" className="w-full rounded-xl border bg-background px-4 py-2.5 text-sm" />\n'
        '            <textarea rows={5} placeholder="How can we help?" className="w-full rounded-xl border bg-background px-4 py-2.5 text-sm" />\n'
    )
    return (
        '      <section className="mx-auto max-w-3xl px-6 py-20">\n'
        '        <h2 className="mb-2 font-display text-3xl font-bold">Get in touch</h2>\n'
        '        <p className="mb-8 text-muted-foreground">Send us a message and our team will get back to you.</p>\n'
        '        <form className="space-y-4 rounded-2xl border bg-card p-6 shadow-sm">\n' + fields +
        '            <button type="button" className="w-full rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground">Send message</button>\n'
        '        </form>\n      </section>\n'
    )


def custom_block(title):
    """Render a user-typed custom component as a titled section so nothing the
    user asked for is silently dropped."""
    return (
        '      <section className="mx-auto max-w-5xl px-6 py-16">\n'
        '        <h2 className="font-display text-2xl font-bold">' + _title(title) + '</h2>\n'
        '        <p className="mt-3 max-w-2xl text-muted-foreground">A dedicated ' + _t(str(title).lower(), 40) +
        ' section, tailored to this product.</p>\n'
        '      </section>\n'
    )


# ----------------------------------------------------------------- packs per template
# Values match the interview's COMPONENT_LIBRARY so a ticked component maps
# straight to a builder (see render_section below).
_PACKS = {
    "features": ["features", "steps", "stats"],
    "content":  ["split", "features", "terminology"],
    "about":    ["split", "stats", "testimonial"],
    "gallery":  ["gallery", "split", "terminology"],
    "pricing":  ["pricing", "faq"],
}
_KNOWN_KINDS = {"hero", "features", "steps", "stats", "split", "gallery", "pricing",
                "faq", "testimonial", "terminology", "contact_form", "cta"}
_HERO_IMG = ["hero.jpg", "banner.jpg", "about1.jpg", "feature1.jpg", "gallery1.jpg", "cta.jpg"]
_STAT_SETS = [
    [("12k+", "Active users"), ("99.9%", "Uptime"), ("4.9/5", "Rating"), ("24/7", "Support")],
    [("50+", "Integrations"), ("3 min", "To get started"), ("100%", "Cloud-based"), ("ISO", "Certified")],
    [("2x", "Faster workflow"), ("-40%", "Manual work"), ("10k+", "Records managed"), ("A+", "Security")],
]


def _features_for(bp, idx, page_name):
    """Domain features, rotated so each page surfaces a DIFFERENT slice."""
    feats = [f for f in (bp.get("key_features") or []) if str(f).strip()]
    if len(feats) < 3:
        dom = bp.get("domain", "your team")
        feats = feats + [f"Purpose-built for {dom}", "Secure role-based access",
                         "Real-time updates", "Reports & analytics", "Mobile friendly", "Easy onboarding"]
    k = (idx * 2) % max(1, len(feats))
    rot = feats[k:] + feats[:k]
    return [{"title": str(f).strip().capitalize(),
             "text": f"{page_name}: {str(f).strip().lower()} - included from day one."} for f in rot[:6]]


def _steps_for(bp, page_name):
    ents = [e.get("name") if isinstance(e, dict) else e for e in (bp.get("entities") or [])]
    base = [("Create your account", "Sign up in seconds and set up your workspace."),
            (f"Add your {(ents[0] if ents else 'records')}", "Bring your data in - import or create from scratch."),
            ("Invite your team", "Give each role exactly the access it needs."),
            ("Go live", f"Run {page_name.lower()} end to end, all in one place.")]
    return [{"title": t, "text": d} for t, d in base]


def _faq_for(bp, app_name):
    dom = bp.get("domain", "this")
    return [
        (f"What is {app_name}?", f"{app_name} is a complete platform for {dom}, covering everything from day-to-day operations to reporting."),
        ("Do I need to install anything?", "No - it runs entirely in your browser on desktop, tablet and mobile."),
        ("Can I control who sees what?", "Yes. Access is role-based, so every user only sees the screens meant for them."),
        ("Is my data secure?", "All records are access-controlled and every sensitive change is auditable."),
        ("Can I try it for free?", "Yes - start on the free Starter plan and upgrade when you grow."),
    ]


_AI_SYS = (
    "Generate ONE self-contained marketing website <section> in JSX. Rules: use ONLY Tailwind "
    "utility classes and plain elements (section, div, h2, h3, p, span, a, ul, li, button). "
    "NO imports, NO React components, NO icons, NO curly-brace { } expressions or variables - "
    "ONLY static text. Wrap everything in a single <section className=\"...\"> ... </section>. "
    "Return ONLY that JSX and nothing else."
)


def _extract_section(text):
    t = re.sub(r"```(?:jsx|tsx|js|react)?", "", text or "").replace("```", "").strip()
    m = re.search(r"<section\b.*</section>", t, re.S)
    return m.group(0).strip() if m else ""


def _valid_section(sec):
    """Only accept pure-static JSX (no expressions/imports) so it always builds."""
    if not sec or len(sec) < 80:
        return False
    if "{" in sec or "}" in sec:          # no JS expressions / undefined vars
        return False
    if any(b in sec for b in ("import ", "function ", "=>", "</script", "${", "`")):
        return False
    return sec.count("<section") == 1 and sec.count("</section>") == 1


def _ai_section(kind, name, app_name, kicker):
    """Gemma writes one section's JSX; returns it only if it passes validation,
    else None so the caller uses the deterministic builder (fallback)."""
    try:
        from app.agents import get_llm
        from langchain_core.messages import SystemMessage, HumanMessage
        user = (f"Website: {app_name} (domain: {kicker}). Page: {name}. Section type: {kind}. "
                "Write real, specific, on-brand copy for this exact domain.")
        out = get_llm(temperature=0.6, num_predict=1200, json_mode=False).invoke(
            [SystemMessage(content=_AI_SYS), HumanMessage(content=user)]).content
        sec = _extract_section(out)
        if _valid_section(sec):
            return "\n      " + sec + "\n"
    except Exception:
        pass
    return None


def freeform_section(prompt, app_name=""):
    """A brand-new section described in natural language (Select-Element 'add
    section'). Gemma writes it (validated); else a clean deterministic band."""
    sec = _ai_section(str(prompt)[:80], str(prompt)[:50], app_name or "this site", "")
    if sec:
        return sec
    title = _title(str(prompt)[:50]) or "New Section"
    return ('\n      <section className="mx-auto max-w-5xl px-6 py-16">\n'
            '        <h2 className="font-display text-3xl font-bold">' + _t(title, 60) + '</h2>\n'
            '        <p className="mt-3 max-w-2xl text-muted-foreground">' + _t(str(prompt), 160) + '</p>\n'
            '      </section>\n')


def compose_marketing_page(page, bp, idx, app_name, ai_sections=False):
    """Build one full marketing page (server component) from a varied section pack.
    With ai_sections, each non-hero section is written by Gemma (validated; falls
    back to the deterministic builder when the AI output isn't safe to ship)."""
    name = page.get("name", "Page")
    slug = page.get("slug", "page")
    template = page.get("template", "content")
    purpose = page.get("purpose") or f"Everything about {name.lower()} in {app_name}."
    kicker = bp.get("domain", app_name) or app_name
    img_subjects = bp.get("image_subjects") or []
    hero_asset = _HERO_IMG[idx % len(_HERO_IMG)]

    # hero alternates by page index so even same-template pages differ
    hero = (hero_split(kicker, name, purpose, hero_asset)
            if idx % 2 == 0 else hero_centered(kicker, name, purpose, hero_asset))

    feats = _features_for(bp, idx, name)
    terms = bp.get("terminology") or img_subjects

    def render_section(kind):
        if kind == "features":
            return feature_grid(f"What {name} gives you", feats)
        if kind == "steps":
            return process_steps(f"How {name.lower()} works", _steps_for(bp, name))
        if kind == "stats":
            return stats_band(_STAT_SETS[idx % len(_STAT_SETS)])
        if kind == "split":
            blurb = (feats[0]["text"] if feats else purpose) + " " + (
                f"{app_name} brings {kicker} together so nothing falls through the cracks.")
            return split_image_text(f"Built for {kicker}", blurb, _HERO_IMG[(idx + 2) % len(_HERO_IMG)], flip=(idx % 2 == 1))
        if kind == "terminology":
            return terminology_chips(f"The language of {kicker}", terms) if terms else ""
        if kind == "gallery":
            return gallery(["gallery1.jpg", "feature1.jpg", "gallery2.jpg", "about1.jpg", "gallery3.jpg", "feature2.jpg"], f"{name} gallery")
        if kind == "pricing":
            return pricing(app_name)
        if kind == "faq":
            return faq(_faq_for(bp, app_name))
        if kind == "testimonial":
            return testimonial(f"Switching to {app_name} was the best decision we made for our {kicker} operations this year.", f"A happy {kicker} customer")
        if kind == "contact_form":
            return contact_section(app_name)
        if kind == "cta":
            return cta_band(app_name)
        if kind not in _KNOWN_KINDS:    # a custom component the user typed in
            return custom_block(kind)
        return ""

    # Explicit components (from the interview) win; else the template's default pack.
    chosen = [k for k in (page.get("sections") or []) if k and k != "hero"]
    kinds = chosen if chosen else _PACKS.get(template, _PACKS["content"])
    def one(k):
        if ai_sections:
            ai = _ai_section(k, name, app_name, kicker)
            if ai:
                return ai
        return render_section(k)

    body = hero + "".join(one(k) for k in kinds)
    if not chosen or "cta" not in chosen:   # always close with a call to action
        body += cta_band(app_name)

    return (
        "import { CheckCircle2 } from 'lucide-react';\n\n"
        "export default function Page() {\n"
        "  return (\n"
        '    <div data-component-id="page-' + re.sub(r"[^a-z0-9-]", "", slug) + '" data-component-label="' + _t(name, 30) + ' page">\n'
        + body +
        "    </div>\n"
        "  );\n}\n"
    )
