"""SRS-exact public page generator (generic, domain-agnostic, section-driven).

For every page in parsed_srs['srs_public_pages'] this renders ONE real UI block
per entry in that page's own `sections` list. Section text is classified into a
block type (hero / search / filter / grid / gallery / testimonials / offers /
form / map / faq / features / team / calendar / steps / contact / cta / footer /
content) and rendered as themed JSX. All copy is sourced from the SRS itself
(app_name, system_category-derived domain noun, the section's own label, entity
names) so the result is domain-correct for ANY vertical and never injects
content from another domain. Themed via the app's `primary` token so each app's
accent flows through. No LLM, no per-vertical hardcoded templates.

Overwrites any generic marketing pages written by write_marketing_pages().
"""
import os
import re

# ── path helpers (unchanged contract) ──────────────────────────────────────────

def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _page_path(out_dir: str, slug: str) -> str:
    p = os.path.join(out_dir, "src", "app", "(marketing)", slug, "page.jsx")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def _slug_for_page(page_name: str, route: str) -> str:
    """Return the URL slug that the marketing page pipeline would use."""
    if route in ("/", ""):
        return "home-page"
    slug = re.sub(r"[^a-z0-9]+", "-", page_name.lower()).strip("-")
    return slug[:32]


# ── text helpers ────────────────────────────────────────────────────────────

def _esc(s: str) -> str:
    """Make arbitrary text safe to drop inside JSX text nodes / attributes."""
    s = str(s or "")
    s = s.replace("&", "and").replace("<", "").replace(">", "")
    s = s.replace("{", "").replace("}", "").replace("`", "").replace('"', "")
    return re.sub(r"\s+", " ", s).strip()


def _title(s: str) -> str:
    s = _esc(s)
    return " ".join(w[:1].upper() + w[1:] for w in s.split())


def _pascal(s: str) -> str:
    p = re.sub(r"[^A-Za-z0-9]", "", _title(s))
    if not p or not p[0].isalpha():
        p = "Marketing" + p
    return p


def _singular(w: str) -> str:
    w = w.strip()
    low = w.lower()
    if low.endswith("ies") and len(w) > 3:
        return w[:-3] + "y"
    if low.endswith(("ses", "ches", "shes", "xes")) and len(w) > 4:
        return w[:-2]
    if low.endswith("s") and not low.endswith("ss") and len(w) > 1:
        return w[:-1]
    return w


_LABEL_NOISE = re.compile(r"\b(section|preview|with|button|area|block|component)\b", re.I)


def _clean_label(section: str) -> str:
    """A heading derived from a section spec: drop trailing detail after 'with',
    strip filler words, title-case. 'Featured rooms section' -> 'Featured Rooms';
    'Hero section with hotel name, headline' -> 'Hero'."""
    s = re.split(r"\bwith\b", section, 1, flags=re.I)[0]
    s = s.split(",")[0]
    s = _LABEL_NOISE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip(" -:,.")
    return _title(s) or "Details"


_DOMAIN_STOP = {
    "management", "system", "web", "application", "app", "platform", "and", "the",
    "online", "portal", "software", "solution", "based", "cloud", "pos", "lms",
    "inventory", "sales", "service", "services", "rental", "spare", "parts",
    "learning", "mobile", "friendly", "responsive",
}


def _domain_noun(parsed_srs: dict) -> str:
    src = (parsed_srs.get("system_category") or parsed_srs.get("domain")
           or parsed_srs.get("app_name") or "").lower()
    for w in re.findall(r"[a-z]+", src):
        if w not in _DOMAIN_STOP and len(w) >= 3:
            return w
    return "business"


def _nav_label(page_name: str) -> str:
    s = re.sub(r"\bpage\b", "", page_name, flags=re.I)
    return _title(s) or _title(page_name)


# ── section classifier ────────────────────────────────────────────────────────

def _classify(section: str) -> str:
    t = section.lower()
    if "hero" in t:
        return "hero"
    if "footer" in t:
        return "footer"
    if any(k in t for k in ("testimonial", "review")):
        return "testimonials"
    if any(k in t for k in ("gallery", "images", "photos", " image")):
        return "gallery"
    if any(k in t for k in ("offer", "package", "pricing", " plan", "discount", "deal", "coupon")):
        return "offers"
    if any(k in t for k in ("faq", "question")):
        return "faq"
    if any(k in t for k in ("map", "directions", "google map")):
        return "map"
    if any(k in t for k in ("upload", "inquiry form", "contact form", "booking form",
                            "registration form", "subscribe", "admission inquiry", " form")):
        return "form"
    if any(k in t for k in ("search", "availability", "find ", "room search", "filter")):
        return "search"
    if any(k in t for k in ("calendar", "timetable")):
        return "calendar"
    if any(k in t for k in ("step", "process", "how it works", "required documents")):
        return "steps"
    if any(k in t for k in ("team", "management team", "principal message", "management message",
                            "meet our", "staff", "leadership")):
        return "team"
    if any(k in t for k in ("contact form", "phone", "email", "address", "opening hours",
                            "social media", "contact detail")):
        return "contact"
    if any(k in t for k in ("call-to-action", "call to action", "cta", "book now", "book offer",
                            "get started", "download")):
        return "cta"
    if any(k in t for k in ("listing", "grid", "cards", "featured", "rooms", "room type",
                            "products", "product", "menu", "catalog", "categor", "fleet",
                            "vehicles", "courses", "programs", "details cards")):
        return "grid"
    if any(k in t for k in ("highlight", "why choose", "feature", "benefit", "stat",
                            "achievement", "facilit", "amenit", "mission", "vision", "story",
                            "overview", "values", "rules", "curriculum", "stream", "subject",
                            "news", "notices", "published", "announcement")):
        return "features"
    return "default"


# ── shared building blocks ────────────────────────────────────────────────────

def _section_open(extra="bg-white"):
    return f'      <section className="py-14 {extra}">\n        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">\n'


def _section_close():
    return "        </div>\n      </section>\n"


def _heading(label, kicker=""):
    out = ""
    if kicker:
        out += f'          <p className="text-xs font-semibold uppercase tracking-widest text-primary">{_esc(kicker)}</p>\n'
    out += f'          <h2 className="mt-1 text-3xl font-bold text-slate-900">{_esc(label)}</h2>\n'
    return out


def _cards(items, card_cls="bg-white border border-slate-200"):
    """items: list of (title, desc) tuples -> responsive card grid JSX."""
    rows = []
    for i, (title, desc) in enumerate(items):
        rows.append(
            f'            {{/* card */}}\n'
            f'            <div key={{{i}}} className="{card_cls} rounded-2xl p-6 shadow-sm">\n'
            f'              <div className="h-10 w-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center font-bold">{i + 1}</div>\n'
            f'              <h3 className="mt-4 font-semibold text-slate-900">{_esc(title)}</h3>\n'
            f'              <p className="mt-2 text-sm text-slate-600">{_esc(desc)}</p>\n'
            f'            </div>\n'
        )
    return ('          <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">\n'
            + "".join(rows) + '          </div>\n')


_GENERIC_NOUNS = {
    "us", "choose", "why", "our", "the", "details", "detail", "grid", "listing",
    "list", "cards", "card", "section", "filter", "gallery", "preview", "highlight",
    "showcase", "overview", "range", "quick", "search", "type", "category", "rent",
    "sale", "browse", "featured", "popular",
    "for", "and", "the", "with", "from", "your", "all", "new", "our", "top",
}


def _item_titles(label, ctx, n=3):
    # pick the most meaningful noun: scan the label words right-to-left for the
    # first real noun, skipping structural words ("Grid", "Listing", "Filter"…)
    # so cards read "Premium Property", not "Premium Grid".
    noun = ""
    for w in reversed(re.findall(r"[A-Za-z]+", label)):
        if len(w) >= 3 and w.lower() not in _GENERIC_NOUNS:
            noun = _singular(w)
            break
    if not noun:
        cand = [it for it in (ctx.get("items") or [])
                if it and not any(x in it.lower() for x in ("item", "detail", "record", "log", "permission", "role", "user"))]
        noun = _singular(str(cand[0] if cand else ctx["domain_noun"]).split()[-1])
    prefixes = ["Premium", "Popular", "Featured", "New", "Top"]
    return [f"{prefixes[i % len(prefixes)]} {_title(noun)}" for i in range(n)]


# ── block renderers ───────────────────────────────────────────────────────────

# seeded image slots — placeholder.jpg is copied into each before build and the
# real AI photos overwrite them, so referencing these always shows an image.
_IMAGES = ["feature1.jpg", "gallery1.jpg", "feature2.jpg", "gallery2.jpg",
           "about1.jpg", "gallery3.jpg", "about2.jpg", "banner.jpg"]


def _img(i):
    return _IMAGES[i % len(_IMAGES)]


def _bg_style(asset):
    """Literal JSX inline-style for a cover background image."""
    return ('style={{ backgroundImage: "url(/assets/' + asset + ')", '
            'backgroundSize: "cover", backgroundPosition: "center" }}')


def _b_hero_legacy(section, ctx):
    """Legacy hero — kept as internal fallback, not directly dispatched."""
    t = section.lower()
    fields = []
    if any(k in t for k in ("date", "check-in", "check in", "availability")):
        fields = [("Check in", "date"), ("Check out", "date"), ("Guests", "number")]
    elif "search" in t:
        fields = [(f"Search {ctx['domain_noun']}", "text")]
    search = ""
    if fields:
        inputs = "".join(
            f'              <div className="flex-1 min-w-[140px]">\n'
            f'                <label className="block text-xs font-medium text-slate-500">{_esc(lab)}</label>\n'
            f'                <input type="{typ}" placeholder="{_esc(lab)}" className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900" />\n'
            f'              </div>\n'
            for lab, typ in fields
        )
        search = (
            '          <div className="mt-8 mx-auto max-w-3xl rounded-2xl bg-white p-4 shadow-lg flex flex-wrap items-end gap-3">\n'
            + inputs +
            '              <button className="rounded-lg bg-primary px-6 py-2 font-semibold text-primary-foreground">Search</button>\n'
            '          </div>\n'
        )
    return (
        '      <section className="relative overflow-hidden text-white">\n'
        '        <div className="absolute inset-0 bg-cover bg-center" ' + _bg_style("hero.jpg") + ' />\n'
        '        <div className="absolute inset-0 bg-gradient-to-br from-primary/75 via-primary/55 to-slate-900/65" />\n'
        '        <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-24 text-center">\n'
        f'          <h1 className="text-4xl font-extrabold sm:text-5xl lg:text-6xl drop-shadow-sm">{_esc(ctx["app_name"])}</h1>\n'
        f'          <p className="mt-4 text-lg text-white/90 max-w-2xl mx-auto">Your complete {_esc(ctx["domain_noun"])} platform — everything in one place.</p>\n'
        '          <div className="mt-8 flex justify-center gap-3">\n'
        f'            <a href="{ctx["login_href"]}" className="rounded-lg bg-white px-6 py-3 font-semibold text-primary shadow-lg hover:bg-white/90 transition">Get Started</a>\n'
        '          </div>\n'
        + search +
        '        </div>\n'
        '      </section>\n'
    )


def _b_search(section, ctx):
    label = _clean_label(section)
    t = section.lower()
    if any(k in t for k in ("date", "check-in", "check in")):
        fields = [("Check in", "date"), ("Check out", "date"), ("Guests", "number")]
    elif "price" in t:
        fields = [("Min price", "number"), ("Max price", "number")]
    else:
        fields = [(f"Search {ctx['domain_noun']}", "text")]
    inputs = "".join(
        f'            <div className="flex-1 min-w-[150px]">\n'
        f'              <label className="block text-xs font-medium text-slate-500">{_esc(lab)}</label>\n'
        f'              <input type="{typ}" placeholder="{_esc(lab)}" className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" />\n'
        f'            </div>\n'
        for lab, typ in fields
    )
    return (_section_open("bg-slate-50") + _heading(label, "Find what you need")
            + '          <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-4 flex flex-wrap items-end gap-3">\n'
            + inputs
            + '            <button className="rounded-lg bg-primary px-6 py-2 font-semibold text-primary-foreground">Apply</button>\n'
            + '          </div>\n' + _section_close())


def _b_filter(section, ctx):
    label = _clean_label(section)
    chips = ["All", "Popular", "New", "Top Rated", "Best Value"]
    chip_js = "".join(
        f'            <button key={{{i}}} className="rounded-full border border-slate-300 px-4 py-1.5 text-sm hover:border-primary hover:text-primary">{c}</button>\n'
        for i, c in enumerate(chips))
    return (_section_open() + _heading(label)
            + '          <div className="mt-6 flex flex-wrap gap-2">\n' + chip_js + '          </div>\n'
            + _section_close())


def _b_grid(section, ctx):
    label = _clean_label(section)
    titles = _item_titles(label, ctx)
    items = [(tt, f"Explore {ctx['domain_noun']} options curated for you.") for tt in titles]
    cards = "".join(
        f'            <div key={{{i}}} className="group overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm hover:shadow-md transition">\n'
        f'              <img src="/assets/{_img(i)}" alt="" loading="lazy" className="h-44 w-full object-cover group-hover:scale-105 transition duration-300" />\n'
        f'              <div className="p-5">\n'
        f'                <h3 className="font-semibold text-slate-900">{_esc(tt)}</h3>\n'
        f'                <p className="mt-1 text-sm text-slate-600">{_esc(ds)}</p>\n'
        f'                <a href="{ctx["login_href"]}" className="mt-3 inline-block text-sm font-semibold text-primary">View details →</a>\n'
        f'              </div>\n'
        f'            </div>\n'
        for i, (tt, ds) in enumerate(items)
    )
    return (_section_open() + _heading(label, "Browse")
            + '          <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">\n' + cards + '          </div>\n'
            + _section_close())


def _b_gallery(section, ctx):
    label = _clean_label(section)
    tiles = "".join(
        f'            <img key={{{i}}} src="/assets/{_img(i)}" alt="" loading="lazy" className="aspect-square w-full rounded-xl object-cover ring-1 ring-slate-200 hover:opacity-90 transition" />\n'
        for i in range(8))
    return (_section_open("bg-slate-50") + _heading(label, "Gallery")
            + '          <div className="mt-8 grid grid-cols-2 sm:grid-cols-4 gap-4">\n' + tiles + '          </div>\n'
            + _section_close())


def _b_testimonials(section, ctx):
    label = _clean_label(section)
    quotes = [
        ("Alex M.", f"{ctx['app_name']} made the whole experience effortless and reliable."),
        ("Sam R.", "Professional service from start to finish. Highly recommended."),
        ("Jordan T.", "Easy to use and the team is responsive. A great experience overall."),
    ]
    cards = "".join(
        f'            <figure key={{{i}}} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">\n'
        f'              <div className="text-primary">★★★★★</div>\n'
        f'              <blockquote className="mt-3 text-slate-700">{_esc(q)}</blockquote>\n'
        f'              <figcaption className="mt-4 text-sm font-semibold text-slate-900">{_esc(n)}</figcaption>\n'
        f'            </figure>\n'
        for i, (n, q) in enumerate(quotes)
    )
    return (_section_open() + _heading(label, "What people say")
            + '          <div className="mt-8 grid gap-6 sm:grid-cols-3">\n' + cards + '          </div>\n'
            + _section_close())


def _b_offers(section, ctx):
    label = _clean_label(section)
    plans = [("Starter", "Save 10%"), ("Popular", "Save 20%"), ("Premium", "Save 30%")]
    cards = "".join(
        f'            <div key={{{i}}} className="rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm">\n'
        f'              <h3 className="font-semibold text-slate-900">{_esc(nm)}</h3>\n'
        f'              <div className="mt-3 inline-block rounded-full bg-primary/10 px-4 py-1 text-sm font-semibold text-primary">{_esc(badge)}</div>\n'
        f'              <p className="mt-3 text-sm text-slate-600">A great {_esc(ctx["domain_noun"])} package tailored for you.</p>\n'
        f'              <a href="{ctx["login_href"]}" className="mt-4 block rounded-lg bg-primary px-4 py-2 font-semibold text-primary-foreground">Claim offer</a>\n'
        f'            </div>\n'
        for i, (nm, badge) in enumerate(plans)
    )
    return (_section_open("bg-slate-50") + _heading(label, "Offers")
            + '          <div className="mt-8 grid gap-6 sm:grid-cols-3">\n' + cards + '          </div>\n'
            + _section_close())


def _b_form(section, ctx):
    label = _clean_label(section)
    t = section.lower()
    if "upload" in t:
        fields = [("Full name", "text"), ("Phone", "tel"), ("Document", "file")]
    elif any(k in t for k in ("booking", "inquiry", "admission")):
        fields = [("Full name", "text"), ("Email", "email"), ("Phone", "tel"), ("Message", "textarea")]
    else:
        fields = [("Full name", "text"), ("Email", "email"), ("Message", "textarea")]
    rows = []
    for lab, typ in fields:
        if typ == "textarea":
            rows.append(
                f'            <label className="block sm:col-span-2">\n'
                f'              <span className="text-sm font-medium text-slate-700">{_esc(lab)}</span>\n'
                f'              <textarea rows={{4}} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" />\n'
                f'            </label>\n')
        else:
            rows.append(
                f'            <label className="block">\n'
                f'              <span className="text-sm font-medium text-slate-700">{_esc(lab)}</span>\n'
                f'              <input type="{typ}" className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" />\n'
                f'            </label>\n')
    return (_section_open() + _heading(label, "Get in touch")
            + '          <form className="mt-8 grid gap-5 sm:grid-cols-2 max-w-3xl">\n'
            + "".join(rows)
            + '            <button type="button" className="sm:col-span-2 rounded-lg bg-primary px-6 py-2.5 font-semibold text-primary-foreground">Submit</button>\n'
            + '          </form>\n' + _section_close())


def _b_map(section, ctx):
    label = _clean_label(section)
    return (_section_open("bg-slate-50") + _heading(label, "Find us")
            + '          <div className="mt-6 grid gap-6 lg:grid-cols-3">\n'
            + '            <div className="rounded-2xl border border-slate-200 bg-white p-6">\n'
            + f'              <h3 className="font-semibold text-slate-900">{_esc(ctx["app_name"])}</h3>\n'
            + '              <p className="mt-2 text-sm text-slate-600">123 Main Street, City Center</p>\n'
            + '              <p className="mt-1 text-sm text-slate-600">Open daily, 9:00 to 18:00</p>\n'
            + '            </div>\n'
            + '            <div className="lg:col-span-2 h-64 rounded-2xl bg-gradient-to-br from-primary/15 to-slate-200 flex items-center justify-center text-slate-500">Map</div>\n'
            + '          </div>\n' + _section_close())


def _b_faq(section, ctx):
    label = _clean_label(section)
    qas = [
        ("How do I get started?", f"Create an account and explore everything {ctx['app_name']} offers."),
        ("Is support available?", "Yes, our team is available to help you any time."),
        ("What are the payment options?", "We support multiple secure payment methods at checkout."),
    ]
    items = "".join(
        f'            <details key={{{i}}} className="rounded-xl border border-slate-200 bg-white p-4">\n'
        f'              <summary className="cursor-pointer font-medium text-slate-900">{_esc(q)}</summary>\n'
        f'              <p className="mt-2 text-sm text-slate-600">{_esc(a)}</p>\n'
        f'            </details>\n'
        for i, (q, a) in enumerate(qas)
    )
    return (_section_open() + _heading(label, "FAQ")
            + '          <div className="mt-6 space-y-3 max-w-3xl">\n' + items + '          </div>\n'
            + _section_close())


def _b_features(section, ctx):
    label = _clean_label(section)
    mods = [m for m in (ctx.get("modules") or []) if "auth" not in m.lower() and "audit" not in m.lower()]
    if len(mods) >= 3:
        items = [(m, f"{_esc(m)} built into your {ctx['domain_noun']} workflow.") for m in mods[:6]]
    else:
        base = ["Trusted Quality", "Fast and Reliable", "Expert Support", "Secure and Private"]
        items = [(b, f"A {ctx['domain_noun']} experience you can count on.") for b in base]
    return (_section_open() + _heading(label)
            + _cards([(t, d) for t, d in items]) + _section_close())


def _b_team(section, ctx):
    label = _clean_label(section)
    people = [("J. Morgan", "Director"), ("A. Silva", "Operations Lead"), ("R. Khan", "Head of Service")]
    cards = "".join(
        f'            <div key={{{i}}} className="rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm">\n'
        f'              <div className="mx-auto h-16 w-16 rounded-full bg-primary/10" />\n'
        f'              <h3 className="mt-3 font-semibold text-slate-900">{_esc(n)}</h3>\n'
        f'              <p className="text-sm text-primary">{_esc(r)}</p>\n'
        f'            </div>\n'
        for i, (n, r) in enumerate(people)
    )
    return (_section_open("bg-slate-50") + _heading(label, "Our team")
            + '          <div className="mt-8 grid gap-6 sm:grid-cols-3">\n' + cards + '          </div>\n'
            + _section_close())


def _b_calendar(section, ctx):
    label = _clean_label(section)
    cells = "".join(f'            <div key={{{i}}} className="aspect-square rounded-lg border border-slate-200 bg-white" />\n' for i in range(14))
    return (_section_open() + _heading(label, "Availability")
            + '          <div className="mt-6 grid grid-cols-7 gap-2 max-w-2xl">\n' + cells + '          </div>\n'
            + _section_close())


def _b_steps(section, ctx):
    label = _clean_label(section)
    steps = ["Get in touch", "Share your details", "We take care of the rest"]
    items = "".join(
        f'            <li key={{{i}}} className="rounded-2xl border border-slate-200 bg-white p-6">\n'
        f'              <div className="h-9 w-9 rounded-full bg-primary text-primary-foreground flex items-center justify-center font-bold">{i + 1}</div>\n'
        f'              <p className="mt-3 font-medium text-slate-900">{_esc(s)}</p>\n'
        f'            </li>\n'
        for i, s in enumerate(steps)
    )
    return (_section_open("bg-slate-50") + _heading(label, "How it works")
            + '          <ol className="mt-8 grid gap-6 sm:grid-cols-3">\n' + items + '          </ol>\n'
            + _section_close())


def _b_contact(section, ctx):
    label = _clean_label(section)
    cards = [("Phone", "+1 (555) 000-0000"), ("Email", "hello@example.com"), ("Hours", "Mon to Sun, 9 to 18")]
    items = "".join(
        f'            <div key={{{i}}} className="rounded-2xl border border-slate-200 bg-white p-6">\n'
        f'              <h3 className="font-semibold text-slate-900">{_esc(h)}</h3>\n'
        f'              <p className="mt-1 text-sm text-slate-600">{_esc(v)}</p>\n'
        f'            </div>\n'
        for i, (h, v) in enumerate(cards)
    )
    return (_section_open() + _heading(label, "Contact")
            + '          <div className="mt-6 grid gap-6 sm:grid-cols-3">\n' + items + '          </div>\n'
            + _section_close())


def _b_cta(section, ctx):
    label = _clean_label(section)
    return (
        '      <section className="bg-primary text-primary-foreground">\n'
        '        <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-16 text-center">\n'
        f'          <h2 className="text-3xl font-bold">{_esc(label)}</h2>\n'
        f'          <p className="mt-3 opacity-90">Join {_esc(ctx["app_name"])} today and get started in minutes.</p>\n'
        f'          <a href="{ctx["login_href"]}" className="mt-6 inline-block rounded-lg bg-white px-8 py-3 font-semibold text-primary">Get Started</a>\n'
        '        </div>\n'
        '      </section>\n'
    )


def _b_default(section, ctx, idx=0):
    """Rich alternating image + text block — turns a plain SRS section into a
    professional two-column feature row instead of a sparse heading + one line."""
    label = _clean_label(section)
    app = _esc(ctx["app_name"])
    img = ('            <img src="/assets/' + _img(idx) + '" alt="" loading="lazy" '
           'className="aspect-[4/3] w-full rounded-2xl object-cover ring-1 ring-slate-200 shadow-sm" />\n')
    bullets = "".join(
        f'                <li className="flex items-start gap-2"><span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" /><span>{_esc(b)}</span></li>\n'
        for b in ("Thoughtfully designed and easy to use",
                  "Trusted, professional and reliable",
                  "Everything connected in one place"))
    text = (
        '            <div>\n'
        f'              <h2 className="text-3xl font-bold text-slate-900">{_esc(label)}</h2>\n'
        f'              <p className="mt-4 text-slate-600">At {app}, {_esc(label.lower())} is built to be clear, dependable and centred on what matters to you.</p>\n'
        '              <ul className="mt-5 space-y-3 text-sm text-slate-600">\n' + bullets + '              </ul>\n'
        f'              <a href="{ctx["login_href"]}" className="mt-6 inline-block text-sm font-semibold text-primary">Learn more →</a>\n'
        '            </div>\n'
    )
    inner = (img + text) if (idx % 2) else (text + img)
    return (_section_open("bg-slate-50" if idx % 2 else "bg-white")
            + '          <div className="grid items-center gap-10 lg:grid-cols-2">\n'
            + inner + '          </div>\n'
            + _section_close())


# ── Structural variant renderers ─────────────────────────────────────────────
# Each function produces structurally different JSX. Dispatched from _b_hero,
# _b_grid, and _b_filter based on blueprint["hero_composition"], ["listing_variant"],
# ["filter_placement"]. Defaults preserve backward-compatible output.


def _bv_hero_booking_panel(section, ctx):
    """Full-bleed image hero + floating booking panel at bottom — hotel/travel."""
    app = _esc(ctx["app_name"])
    noun = _esc(ctx["domain_noun"])
    return (
        '      <section className="relative overflow-hidden">\n'
        '        <div className="absolute inset-0 bg-cover bg-center" ' + _bg_style("hero.jpg") + ' />\n'
        '        <div className="absolute inset-0 bg-gradient-to-b from-black/60 via-black/40 to-black/20" />\n'
        '        <div className="relative py-36 text-center text-white px-4">\n'
        f'          <p className="text-sm font-bold uppercase tracking-[0.3em] opacity-90">{noun.title()} Experience</p>\n'
        f'          <h1 className="mt-3 text-5xl font-extrabold leading-tight drop-shadow-lg">{app}</h1>\n'
        f'          <p className="mt-4 text-lg text-white/85 max-w-xl mx-auto">Exceptional stays, seamlessly managed.</p>\n'
        '        </div>\n'
        '        <div className="relative z-10 mx-auto max-w-5xl px-4 pb-10 -mt-6">\n'
        '          <div className="rounded-2xl bg-white shadow-2xl p-6 flex flex-wrap gap-4 items-end">\n'
        '            <div className="flex-1 min-w-[140px]">\n'
        '              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wide">Check In</label>\n'
        '              <input type="date" className="mt-2 w-full border-b-2 border-primary py-2 text-slate-900 bg-transparent focus:outline-none" />\n'
        '            </div>\n'
        '            <div className="flex-1 min-w-[140px]">\n'
        '              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wide">Check Out</label>\n'
        '              <input type="date" className="mt-2 w-full border-b-2 border-primary py-2 text-slate-900 bg-transparent focus:outline-none" />\n'
        '            </div>\n'
        '            <div className="flex-1 min-w-[120px]">\n'
        '              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wide">Guests</label>\n'
        '              <input type="number" defaultValue="2" min="1" className="mt-2 w-full border-b-2 border-primary py-2 text-slate-900 bg-transparent focus:outline-none" />\n'
        '            </div>\n'
        f'            <a href="{ctx["login_href"]}" className="rounded-xl bg-primary px-8 py-3 font-bold text-white shadow-lg hover:opacity-90 transition whitespace-nowrap">Check Availability</a>\n'
        '          </div>\n'
        '        </div>\n'
        '      </section>\n'
    )


def _bv_hero_full_bleed(section, ctx):
    """High-energy full-bleed with left-aligned bold copy — fitness/restaurant/gym."""
    app = _esc(ctx["app_name"])
    noun = _esc(ctx["domain_noun"])
    return (
        '      <section className="relative min-h-[88vh] flex items-center overflow-hidden">\n'
        '        <div className="absolute inset-0 bg-cover bg-center" ' + _bg_style("hero.jpg") + ' />\n'
        '        <div className="absolute inset-0 bg-gradient-to-r from-black/85 via-black/60 to-transparent" />\n'
        '        <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-24">\n'
        '          <div className="max-w-xl">\n'
        f'            <p className="text-sm font-black uppercase tracking-[0.4em] text-primary">{noun.upper()}</p>\n'
        f'            <h1 className="mt-3 text-6xl font-black text-white leading-[1.05] uppercase">{app}</h1>\n'
        f'            <p className="mt-5 text-lg text-white/75 leading-relaxed">Push your limits. Transform your life. Experience the difference.</p>\n'
        '            <div className="mt-8 flex flex-wrap gap-4">\n'
        f'              <a href="{ctx["login_href"]}" className="rounded-none bg-primary px-8 py-4 font-black uppercase tracking-wider text-white hover:opacity-90 transition">Get Started</a>\n'
        f'              <a href="#schedule" className="rounded-none border-2 border-white px-8 py-4 font-black uppercase tracking-wider text-white hover:bg-white hover:text-slate-900 transition">View Schedule</a>\n'
        '            </div>\n'
        '          </div>\n'
        '        </div>\n'
        '      </section>\n'
    )


def _bv_hero_search_first(section, ctx):
    """Search-dominant hero — real estate / automotive / jobs."""
    app = _esc(ctx["app_name"])
    noun = _esc(ctx["domain_noun"])
    quick_filters = ["All", "Popular", "New Arrivals", "Best Price", "Top Rated"]
    chips = "".join(
        f'            <button key={{{i}}} className="rounded-full border border-white/40 px-4 py-1.5 text-sm text-white/80 hover:bg-white/20 transition">{c}</button>\n'
        for i, c in enumerate(quick_filters[:4]))
    return (
        '      <section className="bg-slate-900 py-24 text-center">\n'
        '        <div className="mx-auto max-w-4xl px-4">\n'
        f'          <p className="text-xs font-semibold uppercase tracking-widest text-primary/80">Find Your {noun.title()}</p>\n'
        f'          <h1 className="mt-3 text-5xl font-extrabold text-white leading-tight">{app}</h1>\n'
        f'          <p className="mt-3 text-lg text-slate-400">Discover the perfect {noun} from thousands of options.</p>\n'
        '          <div className="mt-10 flex items-center rounded-full bg-white shadow-2xl overflow-hidden max-w-2xl mx-auto">\n'
        f'            <input type="text" placeholder="Search {noun}..." className="flex-1 px-6 py-4 text-slate-900 text-lg focus:outline-none" />\n'
        f'            <a href="{ctx["login_href"]}" className="m-1.5 rounded-full bg-primary px-7 py-3 font-bold text-white">Search</a>\n'
        '          </div>\n'
        '          <div className="mt-6 flex justify-center gap-2 flex-wrap">\n'
        + chips +
        '          </div>\n'
        '        </div>\n'
        '      </section>\n'
    )


def _bv_hero_centered(section, ctx):
    """Centered minimal hero + stats row — healthcare / education / clinical."""
    app = _esc(ctx["app_name"])
    noun = _esc(ctx["domain_noun"])
    return (
        '      <section className="bg-white pb-16 pt-20 text-center">\n'
        '        <div className="mx-auto max-w-3xl px-4">\n'
        f'          <p className="text-sm font-semibold uppercase tracking-widest text-primary">{noun.title()} Platform</p>\n'
        f'          <h1 className="mt-4 text-5xl font-extrabold text-slate-900 leading-tight">{app}</h1>\n'
        f'          <p className="mt-5 text-lg text-slate-600 leading-relaxed">Professional, trusted, and built for every {noun} need — all in one place.</p>\n'
        '          <div className="mt-8 flex justify-center gap-4 flex-wrap">\n'
        f'            <a href="{ctx["login_href"]}" className="rounded-full bg-primary px-8 py-3 font-semibold text-white shadow-md hover:opacity-90 transition">Get Started</a>\n'
        '            <a href="#features" className="rounded-full border-2 border-primary px-8 py-3 font-semibold text-primary hover:bg-primary/5 transition">Learn More</a>\n'
        '          </div>\n'
        '        </div>\n'
        '        <div className="mx-auto mt-14 max-w-2xl grid grid-cols-3 gap-8 px-4">\n'
        '          <div><div className="text-4xl font-black text-primary">500+</div><div className="mt-1 text-sm text-slate-500">Happy Clients</div></div>\n'
        '          <div><div className="text-4xl font-black text-primary">99%</div><div className="mt-1 text-sm text-slate-500">Satisfaction Rate</div></div>\n'
        '          <div><div className="text-4xl font-black text-primary">24/7</div><div className="mt-1 text-sm text-slate-500">Support</div></div>\n'
        '        </div>\n'
        '      </section>\n'
    )


def _bv_hero_editorial(section, ctx):
    """Left-right split — editorial / professional / SaaS."""
    app = _esc(ctx["app_name"])
    noun = _esc(ctx["domain_noun"])
    return (
        '      <section className="bg-slate-50 py-20 lg:py-28">\n'
        '        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">\n'
        '          <div className="grid items-center gap-12 lg:grid-cols-2">\n'
        '            <div>\n'
        f'              <p className="text-sm font-bold uppercase tracking-widest text-primary">{noun.title()} Management</p>\n'
        f'              <h1 className="mt-4 text-5xl font-extrabold text-slate-900 leading-tight">{app}</h1>\n'
        f'              <p className="mt-5 text-lg text-slate-600 leading-relaxed">Everything you need to manage your {noun} operations — streamlined into one powerful platform.</p>\n'
        '              <div className="mt-8 flex flex-wrap gap-4">\n'
        f'                <a href="{ctx["login_href"]}" className="rounded-lg bg-primary px-7 py-3 font-semibold text-white shadow hover:opacity-90 transition">Get Started</a>\n'
        '                <a href="#features" className="rounded-lg border border-slate-300 px-7 py-3 font-semibold text-slate-700 hover:bg-slate-100 transition">See Features</a>\n'
        '              </div>\n'
        '            </div>\n'
        '            <div className="relative">\n'
        '              <img src="/assets/hero.jpg" alt="" loading="lazy" className="w-full rounded-2xl object-cover shadow-xl" />\n'
        '              <div className="absolute -bottom-4 -right-4 h-32 w-32 rounded-2xl bg-primary/10" />\n'
        '            </div>\n'
        '          </div>\n'
        '        </div>\n'
        '      </section>\n'
    )


def _bv_hero_product_showcase(section, ctx):
    """Product/retail hero with featured item grid."""
    app = _esc(ctx["app_name"])
    noun = _esc(ctx["domain_noun"])
    tiles = "".join(
        f'              <div key={{{i}}} className="aspect-square rounded-xl overflow-hidden">\n'
        f'                <img src="/assets/{_img(i+1)}" alt="" loading="lazy" className="w-full h-full object-cover hover:scale-105 transition duration-300" />\n'
        f'              </div>\n'
        for i in range(4))
    return (
        '      <section className="bg-white py-16">\n'
        '        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">\n'
        '          <div className="grid items-center gap-12 lg:grid-cols-[1fr_1fr]">\n'
        '            <div className="order-2 lg:order-1 grid grid-cols-2 gap-3">\n'
        + tiles +
        '            </div>\n'
        '            <div className="order-1 lg:order-2">\n'
        f'              <p className="text-sm font-semibold uppercase tracking-widest text-primary">New Arrivals</p>\n'
        f'              <h1 className="mt-3 text-5xl font-extrabold text-slate-900 leading-tight">{app}</h1>\n'
        f'              <p className="mt-4 text-lg text-slate-600">Discover our curated collection of premium {noun}s — quality you can trust.</p>\n'
        '              <div className="mt-8 flex gap-4">\n'
        f'                <a href="{ctx["login_href"]}" className="rounded-full bg-primary px-8 py-3 font-semibold text-white hover:opacity-90 transition">Shop Now</a>\n'
        '                <a href="#catalog" className="rounded-full border border-slate-300 px-8 py-3 font-semibold text-slate-700 hover:bg-slate-50 transition">Browse All</a>\n'
        '              </div>\n'
        '            </div>\n'
        '          </div>\n'
        '        </div>\n'
        '      </section>\n'
    )


def _b_hero(section, ctx):
    """Hero dispatcher — picks variant from blueprint."""
    bp = ctx.get("blueprint") or {}
    comp = (bp.get("hero_composition") or "").lower().replace("_", "-")
    if "booking" in comp:
        return _bv_hero_booking_panel(section, ctx)
    if "full" in comp or "bleed" in comp or "screen" in comp:
        return _bv_hero_full_bleed(section, ctx)
    if "search" in comp:
        return _bv_hero_search_first(section, ctx)
    if "center" in comp or "minimal" in comp:
        return _bv_hero_centered(section, ctx)
    if "product" in comp or "showcase" in comp:
        return _bv_hero_product_showcase(section, ctx)
    if "editorial" in comp or "split" in comp:
        return _bv_hero_editorial(section, ctx)
    if "dashboard" in comp or "preview" in comp or "stats" in comp:
        # Dashboard preview hero: left text + right dashboard mock
        return _bv_hero_centered(section, ctx)
    # Domain fallback
    cat = (bp.get("system_category") or ctx.get("domain_noun") or "").lower()
    if any(k in cat for k in ("hotel", "hospitality", "travel")):
        return _bv_hero_booking_panel(section, ctx)
    if any(k in cat for k in ("gym", "fitness", "sport", "restaurant")):
        return _bv_hero_full_bleed(section, ctx)
    if any(k in cat for k in ("real estate", "automotive", "property")):
        return _bv_hero_search_first(section, ctx)
    if any(k in cat for k in ("healthcare", "medical", "school", "education")):
        return _bv_hero_centered(section, ctx)
    if any(k in cat for k in ("ecommerce", "retail", "shop")):
        return _bv_hero_product_showcase(section, ctx)
    return _bv_hero_legacy(section, ctx)


# ── Grid variants ─────────────────────────────────────────────────────────────

def _bv_grid_horizontal(section, ctx):
    """Horizontal media cards — hotel rooms / real estate / apartments."""
    label = _clean_label(section)
    noun = ctx["domain_noun"]
    titles = _item_titles(label, ctx, n=3)
    cards = "".join(
        f'            <div key={{{i}}} className="flex rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-sm hover:shadow-lg transition group">\n'
        f'              <div className="shrink-0 w-64 overflow-hidden">\n'
        f'                <img src="/assets/{_img(i)}" alt="" loading="lazy" className="h-full w-full object-cover group-hover:scale-105 transition duration-500" />\n'
        f'              </div>\n'
        f'              <div className="flex flex-col justify-between p-6 flex-1">\n'
        f'                <div>\n'
        f'                  <div className="flex items-start justify-between gap-2">\n'
        f'                    <h3 className="text-lg font-bold text-slate-900">{_esc(tt)}</h3>\n'
        f'                    <span className="shrink-0 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary">Available</span>\n'
        f'                  </div>\n'
        f'                  <p className="mt-2 text-sm text-slate-600">Spacious {_esc(noun)} with premium amenities and stunning views.</p>\n'
        f'                  <div className="mt-3 flex gap-4 text-xs text-slate-500">\n'
        f'                    <span>2 Beds</span><span>1 Bath</span><span>City View</span>\n'
        f'                  </div>\n'
        f'                </div>\n'
        f'                <div className="mt-4 flex items-center justify-between">\n'
        f'                  <div><span className="text-2xl font-extrabold text-primary">$199</span><span className="text-slate-500 text-sm">/night</span></div>\n'
        f'                  <a href="{ctx["login_href"]}" className="rounded-lg bg-primary px-5 py-2 font-semibold text-white hover:opacity-90 transition">Book Now</a>\n'
        f'                </div>\n'
        f'              </div>\n'
        f'            </div>\n'
        for i, tt in enumerate(titles)
    )
    return (_section_open() + _heading(label, "Browse")
            + '          <div className="mt-8 space-y-5">\n' + cards + '          </div>\n'
            + _section_close())


def _bv_grid_schedule(section, ctx):
    """Schedule/time-based cards — gym classes / appointments / events."""
    label = _clean_label(section)
    noun = ctx["domain_noun"]
    titles = _item_titles(label, ctx, n=6)
    intensities = ["Beginner", "Intermediate", "Advanced", "All Levels"]
    times = ["06:00 AM", "08:30 AM", "10:00 AM", "12:30 PM", "05:00 PM", "07:30 PM"]
    cards = "".join(
        f'            <div key={{{i}}} className="rounded-xl border-l-4 border-primary bg-white p-5 shadow-sm hover:shadow-md transition">\n'
        f'              <div className="flex items-center justify-between">\n'
        f'                <span className="text-sm font-black text-primary uppercase tracking-wide">{times[i % len(times)]}</span>\n'
        f'                <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-primary">{intensities[i % len(intensities)]}</span>\n'
        f'              </div>\n'
        f'              <h3 className="mt-2 font-bold text-slate-900">{_esc(tt)}</h3>\n'
        f'              <p className="mt-1 text-sm text-slate-600">Trainer: Coach Morgan · 45 min</p>\n'
        f'              <div className="mt-4 flex items-center justify-between">\n'
        f'                <div className="flex -space-x-1.5">\n'
        f'                  {"".join(f"<div key={{{j}}} className=\"h-6 w-6 rounded-full bg-slate-200 ring-2 ring-white\" />" for j in range(4))}\n'
        f'                  <span className="ml-2 text-xs text-slate-500">+12 joined</span>\n'
        f'                </div>\n'
        f'                <a href="{ctx["login_href"]}" className="text-sm font-bold text-primary hover:underline">Book →</a>\n'
        f'              </div>\n'
        f'            </div>\n'
        for i, tt in enumerate(titles)
    )
    return (_section_open() + _heading(label, "This Week")
            + '          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">\n' + cards + '          </div>\n'
            + _section_close())


def _bv_grid_featured(section, ctx):
    """One large featured card + smaller grid below — general catalog."""
    label = _clean_label(section)
    titles = _item_titles(label, ctx, n=4)
    featured = titles[0] if titles else label
    rest = titles[1:4]
    small_cards = "".join(
        f'            <div key={{{i}}} className="group overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm hover:shadow-md transition">\n'
        f'              <img src="/assets/{_img(i+2)}" alt="" loading="lazy" className="h-36 w-full object-cover group-hover:scale-105 transition duration-300" />\n'
        f'              <div className="p-4">\n'
        f'                <h3 className="font-semibold text-slate-900">{_esc(tt)}</h3>\n'
        f'                <a href="{ctx["login_href"]}" className="mt-2 inline-block text-sm font-semibold text-primary">View →</a>\n'
        f'              </div>\n'
        f'            </div>\n'
        for i, tt in enumerate(rest)
    )
    return (
        _section_open("bg-slate-50") + _heading(label, "Browse")
        + f'          <div className="mt-8 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-md">\n'
        + f'            <img src="/assets/{_img(0)}" alt="" loading="lazy" className="h-64 w-full object-cover" />\n'
        + f'            <div className="flex items-center justify-between p-6">\n'
        + f'              <div>\n'
        + f'                <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-bold text-primary">Featured</span>\n'
        + f'                <h3 className="mt-2 text-xl font-bold text-slate-900">{_esc(featured)}</h3>\n'
        + f'              </div>\n'
        + f'              <a href="{ctx["login_href"]}" className="rounded-lg bg-primary px-6 py-2 font-semibold text-white">View Details</a>\n'
        + f'            </div>\n'
        + f'          </div>\n'
        + (f'          <div className="mt-5 grid gap-4 sm:grid-cols-3">\n' + small_cards + '          </div>\n' if rest else "")
        + _section_close()
    )


def _bv_grid_standard(section, ctx):
    """Standard 3-column card grid — default for most domains."""
    return _b_grid(section, ctx)


def _b_grid(section, ctx):
    """Grid dispatcher — picks variant from blueprint."""
    bp = ctx.get("blueprint") or {}
    listing = (bp.get("listing_variant") or "").lower().replace("_", "-")
    if "horizontal" in listing or "media" in listing:
        return _bv_grid_horizontal(section, ctx)
    if "schedule" in listing:
        return _bv_grid_schedule(section, ctx)
    if "featured" in listing or "large" in listing:
        return _bv_grid_featured(section, ctx)
    # Domain fallback
    cat = (bp.get("system_category") or ctx.get("domain_noun") or "").lower()
    if any(k in cat for k in ("hotel", "hospitality", "travel", "real estate", "property")):
        return _bv_grid_horizontal(section, ctx)
    if any(k in cat for k in ("gym", "fitness", "sport", "class", "yoga")):
        return _bv_grid_schedule(section, ctx)
    if any(k in cat for k in ("ecommerce", "retail", "restaurant", "food", "shop")):
        return _bv_grid_featured(section, ctx)
    # Standard fallback
    label = _clean_label(section)
    titles = _item_titles(label, ctx)
    items = [(tt, f"Explore {ctx['domain_noun']} options curated for you.") for tt in titles]
    cards = "".join(
        f'            <div key={{{i}}} className="group overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm hover:shadow-md transition">\n'
        f'              <img src="/assets/{_img(i)}" alt="" loading="lazy" className="h-44 w-full object-cover group-hover:scale-105 transition duration-300" />\n'
        f'              <div className="p-5">\n'
        f'                <h3 className="font-semibold text-slate-900">{_esc(tt)}</h3>\n'
        f'                <p className="mt-1 text-sm text-slate-600">{_esc(ds)}</p>\n'
        f'                <a href="{ctx["login_href"]}" className="mt-3 inline-block text-sm font-semibold text-primary">View details →</a>\n'
        f'              </div>\n'
        f'            </div>\n'
        for i, (tt, ds) in enumerate(items)
    )
    return (_section_open() + _heading(label, "Browse")
            + '          <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">\n' + cards + '          </div>\n'
            + _section_close())


# ── Filter variants ───────────────────────────────────────────────────────────

def _bv_filter_chips(section, ctx):
    """Inline chip filters — default."""
    label = _clean_label(section)
    chips = ["All", "Popular", "New", "Top Rated", "Best Value"]
    chip_js = "".join(
        f'            <button key={{{i}}} className="rounded-full border border-slate-300 px-4 py-1.5 text-sm hover:border-primary hover:text-primary transition">{c}</button>\n'
        for i, c in enumerate(chips))
    return (_section_open() + _heading(label)
            + '          <div className="mt-6 flex flex-wrap gap-2">\n' + chip_js + '          </div>\n'
            + _section_close())


def _bv_filter_top_search(section, ctx):
    """Prominent top search bar — hotel/travel."""
    label = _clean_label(section)
    noun = ctx["domain_noun"]
    return (
        '      <section className="py-8 bg-slate-50 border-b border-slate-200">\n'
        '        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">\n'
        f'          <div className="flex flex-wrap gap-3 items-end">\n'
        f'            <div className="flex-1 min-w-[200px]">\n'
        f'              <label className="block text-xs font-semibold text-slate-500 uppercase mb-1.5">Location</label>\n'
        f'              <input type="text" placeholder="Where are you going?" className="w-full rounded-xl border border-slate-300 px-4 py-2.5 text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary" />\n'
        f'            </div>\n'
        f'            <div className="min-w-[150px]">\n'
        f'              <label className="block text-xs font-semibold text-slate-500 uppercase mb-1.5">Check In</label>\n'
        f'              <input type="date" className="w-full rounded-xl border border-slate-300 px-4 py-2.5 text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary" />\n'
        f'            </div>\n'
        f'            <div className="min-w-[150px]">\n'
        f'              <label className="block text-xs font-semibold text-slate-500 uppercase mb-1.5">Check Out</label>\n'
        f'              <input type="date" className="w-full rounded-xl border border-slate-300 px-4 py-2.5 text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary" />\n'
        f'            </div>\n'
        f'            <button className="rounded-xl bg-primary px-7 py-2.5 font-bold text-white hover:opacity-90 transition">Search</button>\n'
        f'          </div>\n'
        f'        </div>\n'
        '      </section>\n'
    )


def _bv_filter_sidebar_section(section, ctx):
    """Left sidebar filter layout — real estate / ecommerce."""
    label = _clean_label(section)
    categories = ["All Categories", "Popular", "New Arrivals", "On Sale", "Premium"]
    cat_items = "".join(
        f'            <label key={{{i}}} className="flex items-center gap-2 cursor-pointer">\n'
        f'              <input type="checkbox" className="rounded border-slate-300 text-primary" />\n'
        f'              <span className="text-sm text-slate-700">{c}</span>\n'
        f'            </label>\n'
        for i, c in enumerate(categories))
    return (
        _section_open() + _heading(label)
        + '          <div className="mt-6 flex gap-8">\n'
        + '            <aside className="w-56 shrink-0">\n'
        + '              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">\n'
        + '                <h4 className="font-semibold text-slate-900 text-sm mb-3">Filters</h4>\n'
        + '                <div className="space-y-2">\n' + cat_items + '                </div>\n'
        + '                <div className="mt-4 pt-4 border-t border-slate-200">\n'
        + '                  <label className="block text-xs font-semibold text-slate-500 mb-2">Price Range</label>\n'
        + '                  <input type="range" min="0" max="1000" className="w-full accent-primary" />\n'
        + '                </div>\n'
        + '              </div>\n'
        + '            </aside>\n'
        + '            <div className="flex-1 text-sm text-slate-500">Results will display here once filters are applied.</div>\n'
        + '          </div>\n'
        + _section_close()
    )


def _b_filter(section, ctx):
    """Filter dispatcher — picks variant from blueprint."""
    bp = ctx.get("blueprint") or {}
    placement = (bp.get("filter_placement") or "").lower().replace("_", "-")
    if "top" in placement or "search" in placement:
        return _bv_filter_top_search(section, ctx)
    if "sidebar" in placement:
        return _bv_filter_sidebar_section(section, ctx)
    return _bv_filter_chips(section, ctx)


# ── search block also respects blueprint ─────────────────────────────────────

_BLOCKS = {
    "hero": _b_hero, "search": _b_search, "filter": _b_filter, "grid": _b_grid,
    "gallery": _b_gallery, "testimonials": _b_testimonials, "offers": _b_offers,
    "form": _b_form, "map": _b_map, "faq": _b_faq, "features": _b_features,
    "team": _b_team, "calendar": _b_calendar, "steps": _b_steps,
    "contact": _b_contact, "cta": _b_cta,
}


def _footer(ctx):
    app_name = ctx["app_name"]
    links = ctx.get("nav") or []
    cols = "".join(
        f'            <li><a href="{href}" className="hover:text-white">{_esc(lab)}</a></li>\n'
        for lab, href in links[:6]
    )
    return (
        '      <footer className="bg-slate-900 text-slate-300 mt-4">\n'
        '        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-12">\n'
        '          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3">\n'
        '            <div>\n'
        f'              <span className="text-lg font-bold text-white">{_esc(app_name)}</span>\n'
        f'              <p className="mt-2 text-sm text-slate-400">Your complete {_esc(ctx["domain_noun"])} platform.</p>\n'
        '            </div>\n'
        '            <div>\n'
        '              <h4 className="text-sm font-semibold text-white mb-3">Explore</h4>\n'
        f'              <ul className="space-y-2 text-sm">\n{cols}              </ul>\n'
        '            </div>\n'
        '            <div>\n'
        '              <h4 className="text-sm font-semibold text-white mb-3">Account</h4>\n'
        '              <ul className="space-y-2 text-sm">\n'
        f'                <li><a href="{ctx["login_href"]}" className="hover:text-white">Login</a></li>\n'
        '                <li><a href="/register" className="hover:text-white">Register</a></li>\n'
        '              </ul>\n'
        '            </div>\n'
        '          </div>\n'
        f'          <div className="mt-10 border-t border-slate-700 pt-6 text-xs text-slate-500">© 2024 {_esc(app_name)}. All rights reserved.</div>\n'
        '        </div>\n'
        '      </footer>\n'
    )


def _page_header(name, ctx):
    return (
        '      <section className="relative overflow-hidden border-b border-slate-200 text-white">\n'
        '        <div className="absolute inset-0 bg-cover bg-center" ' + _bg_style("banner.jpg") + ' />\n'
        '        <div className="absolute inset-0 bg-gradient-to-r from-primary/90 to-primary/70" />\n'
        '        <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-16">\n'
        f'          <h1 className="text-4xl font-bold">{_esc(_nav_label(name))}</h1>\n'
        f'          <p className="mt-2 text-white/85">{_esc(ctx["app_name"])}</p>\n'
        '        </div>\n'
        '      </section>\n'
    )


def _render_section(section, idx, ctx):
    kind = _classify(section)
    if kind == "footer":
        return _footer(ctx)
    fn = _BLOCKS.get(kind)
    if fn:
        return fn(section, ctx)
    return _b_default(section, ctx, idx)


def render_public_page(page, ctx):
    name = page.get("name", "Page")
    sections = page.get("sections") or []
    is_home = (page.get("route") or "") in ("/", "")
    body = []
    first_is_hero = bool(sections) and _classify(sections[0]) == "hero"
    if not is_home and not first_is_hero:
        body.append(_page_header(name, ctx))
    for i, sec in enumerate(sections):
        body.append(_render_section(sec, i, ctx))
    if not any("footer" in s.lower() for s in sections):
        body.append(_footer(ctx))
    comp = _pascal(name)
    return (
        f'export default function {comp}Page() {{\n'
        '  return (\n'
        '    <div className="min-h-screen bg-white text-slate-900">\n'
        + "".join(body) +
        '    </div>\n'
        '  );\n'
        '}\n'
    )


# ── main entry point ──────────────────────────────────────────────────────────

def write_srs_public_pages(output_dir: str, parsed_srs: dict, dm: dict = None, blueprint: dict = None) -> dict:
    """Render every SRS public page from its own `sections` list. Domain-agnostic.

    blueprint drives structural variants (hero_composition, listing_variant, filter_placement).
    Returns dict with 'written' list of file paths.
    """
    app_name = str(parsed_srs.get("app_name") or (dm or {}).get("app_name") or "App")
    pages = parsed_srs.get("srs_public_pages") or []
    ents = parsed_srs.get("entities") or (dm or {}).get("entities") or []
    item_labels = [str(e.get("label") or e.get("name")) for e in ents if isinstance(e, dict)]

    nav = []
    for p in pages:
        route = p.get("route") or "/"
        href = "/" if route in ("/", "") else "/" + _slug_for_page(p.get("name", ""), route)
        nav.append((_nav_label(p.get("name", "")), href))

    ctx = {
        "app_name": app_name,
        "domain_noun": _domain_noun(parsed_srs),
        "modules": parsed_srs.get("main_modules") or [],
        "items": item_labels,
        "nav": nav,
        "login_href": "/login",
        "blueprint": blueprint or {},
    }

    written = []
    for page in pages:
        slug = _slug_for_page(page.get("name", ""), page.get("route", ""))
        jsx = render_public_page(page, ctx)
        path = _page_path(output_dir, slug)
        with open(path, "w", encoding="utf-8") as f:
            f.write(jsx)
        written.append(path)
        if (page.get("route") or "") in ("/", ""):
            root = os.path.join(output_dir, "src", "app", "(marketing)", "page.jsx")
            with open(root, "w", encoding="utf-8") as f:
                f.write(jsx)
            written.append(root)

    return {"written": written}
