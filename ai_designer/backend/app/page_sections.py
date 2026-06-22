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


def _img(asset, h, extra="", alt="Generated application image", role="generic"):
    """Normal image element that degrades cleanly when the asset is missing."""
    return (
        f'<img src="/assets/{asset}" alt="{_t(alt, 90)}" '
        f'data-image-role="{_t(role, 48)}" '
        f'className="{h} w-full overflow-hidden rounded-2xl bg-gradient-to-br '
        f'from-primary/20 to-primary/5 object-cover {extra}" />'
    )


def _card_class(style):
    style = str(style or "bordered")
    return {
        "flat": "bg-muted/40 p-6",
        "bordered": "rounded-2xl border bg-card p-6",
        "glass": "rounded-2xl border border-white/60 bg-background/55 p-6 shadow-xl backdrop-blur",
        "shadow": "rounded-2xl border bg-card p-6 shadow-lg",
        "image-card": "overflow-hidden rounded-2xl border bg-card shadow-sm",
        "stat-card": "rounded-2xl border bg-primary/5 p-6 ring-1 ring-primary/10",
    }.get(style, "rounded-2xl border bg-card p-6")


def _space(rhythm):
    return {
        "compact": "py-12",
        "spacious": "py-24",
        "editorial": "py-24 md:py-32",
        "image-heavy": "py-20",
        "data-heavy": "py-16",
        "premium-spacious": "py-24 md:py-32",
    }.get(str(rhythm or "spacious"), "py-20")


_FAMILY_STYLE = {
    "healthcare-clinical": {
        "root": "min-h-screen bg-sky-50 text-slate-950",
        "hero": "border-b border-sky-100 bg-gradient-to-br from-white via-sky-50 to-blue-50",
        "section": "bg-white",
        "section_alt": "border-y border-sky-100 bg-sky-50/70",
        "card_extra": "border-sky-100 bg-white text-slate-950 shadow-sm",
        "primary_cta": "rounded-xl bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-sm hover:bg-blue-700",
        "secondary_cta": "rounded-xl border border-sky-200 bg-white px-6 py-3 text-sm font-semibold text-slate-900",
        "chip": "rounded-xl bg-sky-100 px-3 py-2 text-sky-950",
        "h1": "font-display text-4xl font-bold leading-tight md:text-6xl",
        "footer": "border-t border-sky-100 bg-white text-slate-700",
    },
    "healthcare-trust-saas": {
        "root": "min-h-screen bg-sky-50 text-slate-950",
        "hero": "border-b border-sky-100 bg-gradient-to-br from-white via-sky-50 to-blue-50",
        "section": "bg-white",
        "section_alt": "border-y border-sky-100 bg-sky-50/70",
        "card_extra": "border-sky-100 bg-white text-slate-950 shadow-sm",
        "primary_cta": "rounded-xl bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-sm hover:bg-blue-700",
        "secondary_cta": "rounded-xl border border-sky-200 bg-white px-6 py-3 text-sm font-semibold text-slate-900",
        "chip": "rounded-xl bg-sky-100 px-3 py-2 text-sky-950",
        "h1": "font-display text-4xl font-bold leading-tight md:text-6xl",
        "footer": "border-t border-sky-100 bg-white text-slate-700",
    },
    "ecommerce-product": {
        "root": "min-h-screen bg-neutral-50 text-neutral-950",
        "hero": "border-b border-neutral-200 bg-white",
        "section": "bg-neutral-50",
        "section_alt": "border-y border-neutral-200 bg-white",
        "card_extra": "border-neutral-200 bg-white text-neutral-950 shadow-none",
        "primary_cta": "rounded-full bg-neutral-950 px-7 py-3 text-sm font-semibold text-white",
        "secondary_cta": "rounded-full border border-neutral-300 bg-white px-7 py-3 text-sm font-semibold text-neutral-950",
        "chip": "rounded-full bg-neutral-100 px-3 py-2 text-neutral-800",
        "h1": "font-display text-5xl font-bold leading-none md:text-7xl",
        "footer": "border-t border-neutral-200 bg-neutral-950 text-neutral-100",
    },
    "automotive-showroom": {
        "root": "min-h-screen bg-neutral-50 text-neutral-950",
        "hero": "border-b border-neutral-200 bg-white",
        "section": "bg-white",
        "section_alt": "border-y border-neutral-200 bg-neutral-50",
        "card_extra": "border-neutral-200 bg-white text-neutral-950",
        "primary_cta": "rounded-full bg-neutral-950 px-7 py-3 text-sm font-semibold text-white",
        "secondary_cta": "rounded-full border border-neutral-300 bg-white px-7 py-3 text-sm font-semibold text-neutral-950",
        "chip": "rounded-full bg-neutral-100 px-3 py-2 text-neutral-800",
        "h1": "font-display text-5xl font-bold leading-none md:text-7xl",
        "footer": "border-t border-neutral-200 bg-neutral-950 text-neutral-100",
    },
    "product-commerce": {
        "root": "min-h-screen bg-stone-50 text-stone-950",
        "hero": "border-b border-stone-200 bg-white",
        "section": "bg-stone-50",
        "section_alt": "border-y border-stone-200 bg-white",
        "card_extra": "border-stone-200 bg-white text-stone-950",
        "primary_cta": "rounded-full bg-stone-950 px-7 py-3 text-sm font-semibold text-white",
        "secondary_cta": "rounded-full border border-stone-300 bg-white px-7 py-3 text-sm font-semibold text-stone-950",
        "chip": "rounded-full bg-stone-100 px-3 py-2 text-stone-800",
        "h1": "font-display text-5xl font-bold leading-none md:text-7xl",
        "footer": "border-t border-stone-200 bg-stone-950 text-stone-100",
    },
    "ai-devtools": {
        "root": "min-h-screen bg-slate-950 text-slate-50",
        "hero": "border-b border-slate-800 bg-slate-950 text-slate-50",
        "section": "bg-slate-950 text-slate-50",
        "section_alt": "border-y border-slate-800 bg-slate-900 text-slate-50",
        "card_extra": "border-slate-800 bg-slate-900 text-slate-100 shadow-xl",
        "primary_cta": "rounded-lg bg-violet-500 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-950/30",
        "secondary_cta": "rounded-lg border border-slate-700 bg-slate-900 px-6 py-3 text-sm font-semibold text-slate-100",
        "chip": "rounded-lg bg-slate-800 px-3 py-2 text-slate-200",
        "h1": "font-display text-4xl font-bold leading-tight text-white md:text-6xl",
        "footer": "border-t border-slate-800 bg-slate-950 text-slate-300",
    },
    "developer-console": {
        "root": "min-h-screen bg-slate-950 text-slate-50",
        "hero": "border-b border-slate-800 bg-slate-950 text-slate-50",
        "section": "bg-slate-950 text-slate-50",
        "section_alt": "border-y border-slate-800 bg-slate-900 text-slate-50",
        "card_extra": "border-slate-800 bg-slate-900 text-slate-100 shadow-xl",
        "primary_cta": "rounded-lg bg-violet-500 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-950/30",
        "secondary_cta": "rounded-lg border border-slate-700 bg-slate-900 px-6 py-3 text-sm font-semibold text-slate-100",
        "chip": "rounded-lg bg-slate-800 px-3 py-2 text-slate-200",
        "h1": "font-display text-4xl font-bold leading-tight text-white md:text-6xl",
        "footer": "border-t border-slate-800 bg-slate-950 text-slate-300",
    },
    "education-media": {
        "root": "min-h-screen bg-amber-50 text-slate-950",
        "hero": "border-b border-amber-200 bg-gradient-to-br from-white via-amber-50 to-cyan-50",
        "section": "bg-amber-50",
        "section_alt": "border-y border-amber-200 bg-white",
        "card_extra": "border-amber-200 bg-white text-slate-950 shadow-sm",
        "primary_cta": "rounded-2xl bg-cyan-700 px-6 py-3 text-sm font-semibold text-white",
        "secondary_cta": "rounded-2xl border border-amber-300 bg-white px-6 py-3 text-sm font-semibold text-slate-900",
        "chip": "rounded-2xl bg-amber-100 px-3 py-2 text-amber-950",
        "h1": "font-display text-5xl font-bold leading-tight md:text-7xl",
        "footer": "border-t border-amber-200 bg-white text-slate-700",
    },
    "learning-editorial": {
        "root": "min-h-screen bg-amber-50 text-slate-950",
        "hero": "border-b border-amber-200 bg-gradient-to-br from-white via-amber-50 to-cyan-50",
        "section": "bg-amber-50",
        "section_alt": "border-y border-amber-200 bg-white",
        "card_extra": "border-amber-200 bg-white text-slate-950 shadow-sm",
        "primary_cta": "rounded-2xl bg-cyan-700 px-6 py-3 text-sm font-semibold text-white",
        "secondary_cta": "rounded-2xl border border-amber-300 bg-white px-6 py-3 text-sm font-semibold text-slate-900",
        "chip": "rounded-2xl bg-amber-100 px-3 py-2 text-amber-950",
        "h1": "font-display text-5xl font-bold leading-tight md:text-7xl",
        "footer": "border-t border-amber-200 bg-white text-slate-700",
    },
    "restaurant-reservation": {
        "root": "min-h-screen bg-stone-50 text-stone-950",
        "hero": "border-b border-orange-200 bg-gradient-to-br from-stone-50 via-orange-50 to-rose-50",
        "section": "bg-stone-50",
        "section_alt": "border-y border-orange-200 bg-orange-50/80",
        "card_extra": "border-orange-200 bg-white text-stone-950 shadow-sm",
        "primary_cta": "rounded-full bg-rose-700 px-7 py-3 text-sm font-semibold text-white shadow-md",
        "secondary_cta": "rounded-full border border-orange-300 bg-white px-7 py-3 text-sm font-semibold text-stone-950",
        "chip": "rounded-full bg-orange-100 px-3 py-2 text-orange-950",
        "h1": "font-display text-5xl font-bold leading-none md:text-7xl",
        "footer": "border-t border-orange-200 bg-stone-950 text-stone-100",
    },
    "travel-destination": {
        "root": "min-h-screen bg-cyan-50 text-slate-950",
        "hero": "border-b border-sky-200 bg-gradient-to-br from-cyan-50 via-white to-amber-50",
        "section": "bg-cyan-50",
        "section_alt": "border-y border-sky-100 bg-white",
        "card_extra": "border-sky-100 bg-white text-slate-950 shadow-md shadow-sky-100/60",
        "primary_cta": "rounded-full bg-teal-700 px-7 py-3 text-sm font-semibold text-white shadow-md",
        "secondary_cta": "rounded-full border border-sky-200 bg-white px-7 py-3 text-sm font-semibold text-slate-950",
        "chip": "rounded-full bg-cyan-100 px-3 py-2 text-cyan-950",
        "h1": "font-display text-5xl font-bold leading-none md:text-7xl",
        "footer": "border-t border-sky-100 bg-cyan-950 text-cyan-50",
    },
    "real-estate-listings": {
        "root": "min-h-screen bg-stone-50 text-stone-950",
        "hero": "border-b border-emerald-100 bg-gradient-to-br from-white via-emerald-50 to-stone-50",
        "section": "bg-stone-50",
        "section_alt": "border-y border-emerald-100 bg-white",
        "card_extra": "border-stone-200 bg-white text-stone-950 shadow-sm",
        "primary_cta": "rounded-xl bg-emerald-700 px-6 py-3 text-sm font-semibold text-white",
        "secondary_cta": "rounded-xl border border-emerald-200 bg-white px-6 py-3 text-sm font-semibold text-stone-950",
        "chip": "rounded-xl bg-emerald-100 px-3 py-2 text-emerald-950",
        "h1": "font-display text-5xl font-bold leading-tight md:text-7xl",
        "footer": "border-t border-emerald-100 bg-white text-stone-700",
    },
    "fitness-coaching": {
        "root": "min-h-screen bg-lime-50 text-slate-950",
        "hero": "border-b border-lime-200 bg-gradient-to-br from-lime-50 via-white to-emerald-50",
        "section": "bg-lime-50",
        "section_alt": "border-y border-lime-200 bg-white",
        "card_extra": "border-lime-200 bg-white text-slate-950 shadow-sm",
        "primary_cta": "rounded-full bg-lime-600 px-7 py-3 text-sm font-semibold text-slate-950 shadow-md",
        "secondary_cta": "rounded-full border border-lime-300 bg-white px-7 py-3 text-sm font-semibold text-slate-950",
        "chip": "rounded-full bg-lime-100 px-3 py-2 text-lime-950",
        "h1": "font-display text-5xl font-bold leading-tight md:text-7xl",
        "footer": "border-t border-lime-200 bg-lime-950 text-lime-50",
    },
    "fintech-trust": {
        "root": "min-h-screen bg-emerald-50 text-slate-950",
        "hero": "border-b border-emerald-100 bg-gradient-to-br from-white via-emerald-50 to-teal-50",
        "section": "bg-white",
        "section_alt": "border-y border-emerald-100 bg-emerald-50/80",
        "card_extra": "border-emerald-100 bg-white text-slate-950 shadow-sm",
        "primary_cta": "rounded-xl bg-emerald-700 px-6 py-3 text-sm font-semibold text-white",
        "secondary_cta": "rounded-xl border border-emerald-200 bg-white px-6 py-3 text-sm font-semibold text-slate-900",
        "chip": "rounded-xl bg-emerald-100 px-3 py-2 text-emerald-950",
        "h1": "font-display text-4xl font-bold leading-tight md:text-6xl",
        "footer": "border-t border-emerald-100 bg-white text-slate-700",
    },
    "creative-agency": {
        "root": "min-h-screen bg-zinc-50 text-zinc-950",
        "hero": "border-b border-zinc-200 bg-white",
        "section": "bg-zinc-50",
        "section_alt": "border-y border-zinc-200 bg-white",
        "card_extra": "border-zinc-200 bg-white text-zinc-950 shadow-lg",
        "primary_cta": "rounded-none bg-fuchsia-600 px-6 py-3 text-sm font-semibold text-white",
        "secondary_cta": "rounded-none border border-zinc-300 bg-white px-6 py-3 text-sm font-semibold text-zinc-950",
        "chip": "rounded-none bg-zinc-100 px-3 py-2 text-zinc-900",
        "h1": "font-display text-5xl font-bold leading-none md:text-7xl",
        "footer": "border-t border-zinc-200 bg-zinc-950 text-zinc-100",
    },
    "creative-portfolio": {
        "root": "min-h-screen bg-zinc-50 text-zinc-950",
        "hero": "border-b border-zinc-200 bg-white",
        "section": "bg-zinc-50",
        "section_alt": "border-y border-zinc-200 bg-white",
        "card_extra": "border-zinc-200 bg-white text-zinc-950 shadow-lg",
        "primary_cta": "rounded-none bg-fuchsia-600 px-6 py-3 text-sm font-semibold text-white",
        "secondary_cta": "rounded-none border border-zinc-300 bg-white px-6 py-3 text-sm font-semibold text-zinc-950",
        "chip": "rounded-none bg-zinc-100 px-3 py-2 text-zinc-900",
        "h1": "font-display text-5xl font-bold leading-none md:text-7xl",
        "footer": "border-t border-zinc-200 bg-zinc-950 text-zinc-100",
    },
    "operational-business": {
        "root": "min-h-screen bg-slate-50 text-slate-950",
        "hero": "border-b border-indigo-100 bg-white",
        "section": "bg-white",
        "section_alt": "border-y border-indigo-100 bg-indigo-50/60",
        "card_extra": "border-indigo-100 bg-white text-slate-950 shadow-sm",
        "primary_cta": "rounded-lg bg-indigo-700 px-6 py-3 text-sm font-semibold text-white",
        "secondary_cta": "rounded-lg border border-indigo-200 bg-white px-6 py-3 text-sm font-semibold text-slate-900",
        "chip": "rounded-lg bg-indigo-100 px-3 py-2 text-indigo-950",
        "h1": "font-display text-4xl font-bold leading-tight md:text-6xl",
        "footer": "border-t border-indigo-100 bg-white text-slate-700",
    },
    "operations-console": {
        "root": "min-h-screen bg-slate-50 text-slate-950",
        "hero": "border-b border-indigo-100 bg-white",
        "section": "bg-white",
        "section_alt": "border-y border-indigo-100 bg-indigo-50/60",
        "card_extra": "border-indigo-100 bg-white text-slate-950 shadow-sm",
        "primary_cta": "rounded-lg bg-indigo-700 px-6 py-3 text-sm font-semibold text-white",
        "secondary_cta": "rounded-lg border border-indigo-200 bg-white px-6 py-3 text-sm font-semibold text-slate-900",
        "chip": "rounded-lg bg-indigo-100 px-3 py-2 text-indigo-950",
        "h1": "font-display text-4xl font-bold leading-tight md:text-6xl",
        "footer": "border-t border-indigo-100 bg-white text-slate-700",
    },
    "finance-trust": {
        "root": "min-h-screen bg-emerald-50 text-slate-950",
        "hero": "border-b border-emerald-100 bg-gradient-to-br from-white via-emerald-50 to-teal-50",
        "section": "bg-white",
        "section_alt": "border-y border-emerald-100 bg-emerald-50/80",
        "card_extra": "border-emerald-100 bg-white text-slate-950 shadow-sm",
        "primary_cta": "rounded-xl bg-emerald-700 px-6 py-3 text-sm font-semibold text-white",
        "secondary_cta": "rounded-xl border border-emerald-200 bg-white px-6 py-3 text-sm font-semibold text-slate-900",
        "chip": "rounded-xl bg-emerald-100 px-3 py-2 text-emerald-950",
        "h1": "font-display text-4xl font-bold leading-tight md:text-6xl",
        "footer": "border-t border-emerald-100 bg-white text-slate-700",
    },
    "service-trust": {
        "root": "min-h-screen bg-slate-50 text-slate-950",
        "hero": "border-b border-slate-200 bg-white",
        "section": "bg-white",
        "section_alt": "border-y border-slate-200 bg-slate-50",
        "card_extra": "border-slate-200 bg-white text-slate-950 shadow-sm",
        "primary_cta": "rounded-xl bg-slate-900 px-6 py-3 text-sm font-semibold text-white",
        "secondary_cta": "rounded-xl border border-slate-300 bg-white px-6 py-3 text-sm font-semibold text-slate-950",
        "chip": "rounded-xl bg-slate-100 px-3 py-2 text-slate-800",
        "h1": "font-display text-4xl font-bold leading-tight md:text-6xl",
        "footer": "border-t border-slate-200 bg-white text-slate-700",
    },
}


def _style_key(bp_page):
    return (bp_page or {}).get("visual_family") or (bp_page or {}).get("inspiration_family", "")


def _family_style(bp_page):
    return _FAMILY_STYLE.get(_style_key(bp_page), _FAMILY_STYLE.get((bp_page or {}).get("inspiration_family", ""), _FAMILY_STYLE["healthcare-trust-saas"]))


def _recipe(bp_page, kind):
    return dict((bp_page or {}).get(f"{kind}_recipe") or {})


def _premium_preset(bp_page):
    return dict((bp_page or {}).get("premium_preset") or {})


def _art_director_enabled(bp_page):
    return bool((bp_page or {}).get("art_director_enabled") and _premium_preset(bp_page))


def _section_recipe(bp_page, pos=0):
    recipes = list((bp_page or {}).get("section_recipes") or [])
    return dict(recipes[pos % len(recipes)]) if recipes else {}


def _github_influence(bp_page):
    info = dict((bp_page or {}).get("github_recipe_influence") or {})
    return info if info.get("mode") == "mined-hybrid" else {}


def _with_github_class(bp_page, class_name, target):
    info = _github_influence(bp_page)
    if not info:
        return class_name
    add = str(info.get(f"{target}_class_add") or "").strip()
    if not add:
        return class_name
    return (str(class_name or "") + " " + add).strip()


def _route_root_class(bp_page):
    if _art_director_enabled(bp_page):
        return _premium_preset(bp_page).get("body_class") or _family_style(bp_page)["root"]
    return _family_style(bp_page)["root"]


def _route_hero_class(bp_page):
    if _art_director_enabled(bp_page):
        base = _premium_preset(bp_page).get("hero_class") or _family_style(bp_page)["hero"]
        return _with_github_class(bp_page, base, "hero")
    base = _recipe(bp_page, "hero").get("section_class") or _family_style(bp_page)["hero"]
    return _with_github_class(bp_page, base, "hero")


def _route_section_class(bp_page, pos=0):
    if _art_director_enabled(bp_page):
        preset = _premium_preset(bp_page)
        base = preset.get("section_alt_class" if pos % 2 else "section_class") or _family_style(bp_page)["section"]
        return _with_github_class(bp_page, base, "section")
    st = _family_style(bp_page)
    recipe_class = _section_recipe(bp_page, pos).get("section_class")
    base = recipe_class or (st["section_alt"] if pos % 2 else st["section"])
    return _with_github_class(bp_page, base, "section")


def _route_card_class(bp_page, style=None):
    if _art_director_enabled(bp_page):
        cards = list(_premium_preset(bp_page).get("card_classes") or [])
        if cards:
            return _with_github_class(bp_page, cards[0], "card")
    recipe_class = _recipe(bp_page, "card").get("className")
    base = recipe_class or _card_class(style or (bp_page or {}).get("card_style"))
    return _with_github_class(bp_page, (base + " " + _family_style(bp_page)["card_extra"]).strip(), "card")


def _section_card_class(bp_page, pos=0, style=None):
    if _art_director_enabled(bp_page):
        cards = list(_premium_preset(bp_page).get("card_classes") or [])
        if cards:
            return _with_github_class(bp_page, cards[pos % len(cards)], "card")
    return _route_card_class(bp_page, style)


def _card_treatment(bp_page, pos=0):
    if _art_director_enabled(bp_page):
        cards = list(_premium_preset(bp_page).get("card_classes") or [])
        if cards:
            return "premium-card-" + str(pos % len(cards))
    return (_recipe(bp_page, "card").get("id") or (bp_page or {}).get("card_style") or "card")


def _primary_cta_class(bp_page):
    if _art_director_enabled(bp_page):
        base = _premium_preset(bp_page).get("primary_cta_class") or _family_style(bp_page)["primary_cta"]
        return _with_github_class(bp_page, base, "cta")
    base = _recipe(bp_page, "cta").get("primary_class") or _family_style(bp_page)["primary_cta"]
    return _with_github_class(bp_page, base, "cta")


def _secondary_cta_class(bp_page):
    if _art_director_enabled(bp_page):
        base = _premium_preset(bp_page).get("secondary_cta_class") or _family_style(bp_page)["secondary_cta"]
        return _with_github_class(bp_page, base, "cta")
    base = _recipe(bp_page, "cta").get("secondary_class") or _family_style(bp_page)["secondary_cta"]
    return _with_github_class(bp_page, base, "cta")


def _route_chip_class(bp_page):
    return _family_style(bp_page)["chip"]


def _route_h1_class(bp_page):
    if _art_director_enabled(bp_page):
        return _premium_preset(bp_page).get("h1_class") or _family_style(bp_page)["h1"]
    if _recipe(bp_page, "hero").get("h1_class"):
        return _recipe(bp_page, "hero")["h1_class"]
    typography = str((bp_page or {}).get("typography_style", "")).lower()
    if "editorial" in typography:
        return "font-display text-5xl font-bold leading-tight md:text-7xl"
    if "technical" in typography or "dense" in typography:
        return "font-display text-4xl font-bold leading-tight md:text-6xl"
    return _family_style(bp_page)["h1"]


def _image_ok(strategy):
    return str(strategy or "") != "no-image fallback"


_SECTION_IMAGE_ROLES = {
    "doctor-search-preview": "doctor_team",
    "departments-preview": "department_facility",
    "patient-portal-preview": "patient_portal",
    "lab-report-access": "patient_portal",
    "provider-dashboard-preview": "dashboard_mockup",
    "operations-dashboard-preview": "dashboard_mockup",
    "reports-analytics": "dashboard_mockup",
    "analytics-dashboard": "dashboard_mockup",
    "resource-management": "dashboard_mockup",
    "security-hero": "security_compliance",
    "audit-logs": "security_compliance",
    "data-access-controls": "security_compliance",
    "backup-encryption": "security_compliance",
    "compliance-standards": "security_compliance",
    "care-team": "doctor_team",
    "departments-clinics-grid": "department_facility",
}


def _image_role_for_section(section_id, bp_page=None):
    return _SECTION_IMAGE_ROLES.get(section_id, "dashboard_mockup" if "dashboard" in str(section_id) else "department_facility")


def _image_asset_for_role(role, bp_page=None):
    roles = dict((bp_page or {}).get("image_roles") or {})
    return roles.get(role) or {
        "hero": "hero.jpg",
        "doctor_team": "about1.jpg",
        "department_facility": "gallery1.jpg",
        "dashboard_mockup": "feature1.jpg",
        "security_compliance": "feature2.jpg",
        "patient_portal": "gallery2.jpg",
    }.get(role, "feature1.jpg")


def _rich_component(bp_page, pos=0):
    variants = list((bp_page or {}).get("rich_component_variants") or [])
    return variants[pos % len(variants)] if variants else ""


def _cta_pair(primary="Get started", secondary="Learn more", placement="hero-primary"):
    wrap = "mt-7 flex flex-wrap gap-3"
    if placement == "floating":
        wrap += " rounded-2xl border bg-background/80 p-2 shadow-xl backdrop-blur"
    if placement == "hero-split":
        wrap += " items-center"
    return (
        f'            <div data-genome-cta-placement="{_t(placement, 24)}" className="{wrap}">\n'
        '              <a href="/register" className="rounded-xl bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground">' + _t(primary, 24) + '</a>\n'
        '              <a href="/login" className="rounded-xl border bg-background px-6 py-3 text-sm font-semibold">' + _t(secondary, 24) + '</a>\n'
        '            </div>\n'
    )


def _mock_dashboard(title, items, card_style):
    rows = ""
    for i, item in enumerate(items[:4], 1):
        label = item.get("title") if isinstance(item, dict) else str(item)
        rows += (
            '              <div className="flex items-center justify-between rounded-xl border bg-background px-4 py-3">\n'
            '                <span className="text-sm font-medium">' + _t(label, 34) + '</span>\n'
            '                <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary">Live</span>\n'
            '              </div>\n'
        )
    return (
        '          <div className="' + _card_class(card_style) + '">\n'
        '            <div className="mb-5 flex items-center justify-between">\n'
        '              <div><p className="text-xs font-semibold uppercase tracking-wider text-primary">Command view</p><h3 className="font-display text-xl font-bold">' + _title(title) + '</h3></div>\n'
        '              <div className="h-10 w-10 rounded-xl bg-primary/15" />\n'
        '            </div>\n'
        '            <div className="grid gap-3">\n' + rows + '            </div>\n'
        '            <div className="mt-5 grid grid-cols-3 gap-3 text-center">\n'
        '              <div className="rounded-xl bg-primary/10 p-3"><p className="font-display text-xl font-bold">42</p><p className="text-xs text-muted-foreground">Open</p></div>\n'
        '              <div className="rounded-xl bg-muted p-3"><p className="font-display text-xl font-bold">18</p><p className="text-xs text-muted-foreground">Due</p></div>\n'
        '              <div className="rounded-xl bg-muted p-3"><p className="font-display text-xl font-bold">7</p><p className="text-xs text-muted-foreground">Alerts</p></div>\n'
        '            </div>\n'
        '          </div>\n'
    )


def _hero_visual(kicker, title, sub, asset, visual, feats):
    variant = visual.get("hero_variant", "split")
    card_style = visual.get("card_style", "bordered")
    rhythm = visual.get("layout_rhythm", "spacious")
    image_strategy = visual.get("image_strategy", "hero image")
    cta_placement = visual.get("cta_placement", "hero-primary")
    use_image = _image_ok(image_strategy)
    attr = (
        f'data-genome-hero-variant="{_t(variant, 32)}" '
        f'data-genome-card-style="{_t(card_style, 24)}" '
        f'data-genome-image-strategy="{_t(image_strategy, 32)}" '
        f'data-genome-first-screen="{_t(visual.get("first_screen_skeleton", variant), 120)}"'
    )

    if variant == "full-image":
        media = _img(asset, "absolute inset-0 h-full", "rounded-none opacity-35") if use_image else '<div className="absolute inset-0 bg-primary/10" />'
        return (
            f'      <section data-component-id="hero" data-component-label="Page hero" {attr} className="relative isolate overflow-hidden border-b">\n'
            '        ' + media + '\n'
            '        <div className="absolute inset-0 bg-gradient-to-r from-background via-background/80 to-background/20" />\n'
            f'        <div className="relative mx-auto max-w-6xl px-6 {_space(rhythm)}">\n'
            '          <div className="max-w-2xl">\n'
            '            <p className="mb-4 text-sm font-semibold uppercase tracking-wider text-primary">' + _t(kicker, 42) + '</p>\n'
            '            <h1 className="font-display text-5xl font-bold leading-tight md:text-7xl">' + _title(title) + '</h1>\n'
            '            <p className="mt-6 max-w-xl text-lg text-muted-foreground">' + _t(sub, 220) + '</p>\n'
            + _cta_pair("Book a demo", "Explore services", cta_placement) +
            '          </div>\n'
            '        </div>\n'
            '      </section>\n'
        )

    if variant == "dashboard-preview":
        return (
            f'      <section data-component-id="hero" data-component-label="Page hero" {attr} className="border-b bg-muted/20">\n'
            f'        <div className="mx-auto grid max-w-6xl items-center gap-10 px-6 {_space(rhythm)} lg:grid-cols-[0.9fr_1.1fr]">\n'
            '          <div>\n'
            '            <p className="mb-3 text-sm font-semibold uppercase tracking-wider text-primary">' + _t(kicker, 42) + '</p>\n'
            '            <h1 className="font-display text-4xl font-bold tracking-tight md:text-6xl">' + _title(title) + '</h1>\n'
            '            <p className="mt-5 text-lg text-muted-foreground">' + _t(sub, 220) + '</p>\n'
            + _cta_pair("Open workspace", "View reports", cta_placement) +
            '          </div>\n'
            + _mock_dashboard("Live operations", feats, card_style) +
            '        </div>\n'
            '      </section>\n'
        )

    if variant == "search-booking":
        options = "".join(
            '                <option>' + _t((f.get("title") if isinstance(f, dict) else f), 30) + '</option>\n'
            for f in feats[:4]
        )
        image_block = ('          ' + _img(asset, "h-80 lg:h-[30rem]") + '\n') if use_image else _mock_dashboard("Availability", feats, card_style)
        return (
            f'      <section data-component-id="hero" data-component-label="Page hero" {attr} className="border-b">\n'
            f'        <div className="mx-auto grid max-w-6xl items-center gap-8 px-6 {_space(rhythm)} lg:grid-cols-2">\n'
            '          <div>\n'
            '            <p className="mb-3 inline-flex rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-primary">' + _t(kicker, 42) + '</p>\n'
            '            <h1 className="font-display text-4xl font-bold tracking-tight md:text-6xl">' + _title(title) + '</h1>\n'
            '            <p className="mt-5 text-lg text-muted-foreground">' + _t(sub, 220) + '</p>\n'
            '            <div className="mt-8 rounded-2xl border bg-card p-3 shadow-lg">\n'
            '              <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">\n'
            '                <input placeholder="Search doctors, services, records" className="rounded-xl border bg-background px-4 py-3 text-sm" />\n'
            '                <select className="rounded-xl border bg-background px-4 py-3 text-sm">\n' + options + '                </select>\n'
            '                <a href="/register" className="rounded-xl bg-primary px-5 py-3 text-center text-sm font-semibold text-primary-foreground">Book now</a>\n'
            '              </div>\n'
            '            </div>\n'
            '          </div>\n'
            + image_block +
            '        </div>\n'
            '      </section>\n'
        )

    if variant == "stats-first":
        stats = "".join(
            '            <div className="' + _card_class("stat-card") + '"><p className="font-display text-3xl font-bold text-primary">' + n + '</p><p className="text-sm text-muted-foreground">' + l + '</p></div>\n'
            for n, l in _STAT_SETS[0]
        )
        return (
            f'      <section data-component-id="hero" data-component-label="Page hero" {attr} className="border-b bg-muted/20">\n'
            f'        <div className="mx-auto max-w-6xl px-6 {_space(rhythm)}">\n'
            '          <div className="grid gap-4 md:grid-cols-4">\n' + stats + '          </div>\n'
            '          <div className="mt-12 grid items-end gap-8 md:grid-cols-[1.2fr_0.8fr]">\n'
            '            <div><p className="mb-3 text-sm font-semibold uppercase tracking-wider text-primary">' + _t(kicker, 42) + '</p><h1 className="font-display text-4xl font-bold md:text-6xl">' + _title(title) + '</h1></div>\n'
            '            <div><p className="text-lg text-muted-foreground">' + _t(sub, 220) + '</p>\n'
            + _cta_pair("Start now", "See metrics", cta_placement) +
            '            </div>\n'
            '          </div>\n'
            '        </div>\n'
            '      </section>\n'
        )

    if variant == "card-stack":
        cards = ""
        for i, f in enumerate(feats[:3], 1):
            label = f.get("title") if isinstance(f, dict) else str(f)
            cards += (
                f'            <div className="{_card_class(card_style)} ' + ("md:translate-x-8" if i == 2 else "") + '">\n'
                '              <p className="text-xs font-semibold uppercase tracking-wider text-primary">Priority ' + str(i) + '</p>\n'
                '              <h3 className="mt-2 font-display text-xl font-bold">' + _title(label) + '</h3>\n'
                '              <p className="mt-2 text-sm text-muted-foreground">Track, assign, and resolve this workflow from one shared command surface.</p>\n'
                '            </div>\n'
            )
        return (
            f'      <section data-component-id="hero" data-component-label="Page hero" {attr} className="border-b">\n'
            f'        <div className="mx-auto grid max-w-6xl items-center gap-10 px-6 {_space(rhythm)} lg:grid-cols-[1fr_0.9fr]">\n'
            '          <div>\n'
            '            <p className="mb-3 text-sm font-semibold uppercase tracking-wider text-primary">' + _t(kicker, 42) + '</p>\n'
            '            <h1 className="font-display text-5xl font-bold tracking-tight md:text-7xl">' + _title(title) + '</h1>\n'
            '            <p className="mt-5 text-lg text-muted-foreground">' + _t(sub, 220) + '</p>\n'
            + _cta_pair("Get started", "See workflows", cta_placement) +
            '          </div>\n'
            '          <div className="space-y-4">\n' + cards + '          </div>\n'
            '        </div>\n'
            '      </section>\n'
        )

    if variant == "editorial":
        img = ('          ' + _img(asset, "h-80 md:h-[26rem]") + '\n') if use_image else ""
        return (
            f'      <section data-component-id="hero" data-component-label="Page hero" {attr} className="border-b">\n'
            f'        <div className="mx-auto max-w-6xl px-6 {_space("editorial")}">\n'
            '          <div className="grid gap-10 lg:grid-cols-[1.25fr_0.75fr]">\n'
            '            <div>\n'
            '              <p className="mb-5 text-sm font-semibold uppercase tracking-[0.2em] text-primary">' + _t(kicker, 42) + '</p>\n'
            '              <h1 className="font-display text-5xl font-bold leading-none md:text-7xl">' + _title(title) + '</h1>\n'
            '            </div>\n'
            '            <div className="self-end"><p className="text-xl leading-relaxed text-muted-foreground">' + _t(sub, 240) + '</p>' + _cta_pair("Read the plan", "Enter portal", cta_placement).replace("            ", "              ") + '            </div>\n'
            '          </div>\n'
            + img +
            '        </div>\n'
            '      </section>\n'
        )

    return hero_split(kicker, title, sub, asset, cta="Get started", cta2="Learn more").replace(
        '<section data-component-id="hero" data-component-label="Page hero"',
        f'<section data-component-id="hero" data-component-label="Page hero" {attr}',
        1,
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


def feature_grid(title, items, card_style="bordered", section_variant="feature cards", rhythm="spacious"):
    attr = f'data-genome-section-variant="{_t(section_variant, 32)}" data-genome-card-style="{_t(card_style, 24)}"'
    if section_variant == "icon grid":
        cards = ""
        for f in items[:8]:
            ft = f.get("title") if isinstance(f, dict) else f
            fd = f.get("text") if isinstance(f, dict) else ("Built in for " + str(f).lower() + ".")
            cards += (
                '          <div className="flex items-start gap-4 rounded-xl p-3">\n'
                '            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"><CheckCircle2 className="h-5 w-5" /></div>\n'
                '            <div><h3 className="font-display text-base font-semibold">' + _title(ft) + '</h3>\n'
                '            <p className="mt-1 text-sm text-muted-foreground">' + _t(fd, 130) + '</p></div>\n'
                '          </div>\n'
            )
        return (
            f'      <section {attr} className="mx-auto max-w-6xl px-6 {_space(rhythm)}">\n'
            '        <div className="mb-8 max-w-2xl"><h2 className="font-display text-3xl font-bold">' + _title(title) + '</h2></div>\n'
            '        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">\n' + cards + '        </div>\n'
            '      </section>\n'
        )

    if section_variant == "portal preview":
        return (
            f'      <section {attr} className="border-y bg-muted/20">\n'
            f'        <div className="mx-auto grid max-w-6xl items-center gap-8 px-6 {_space(rhythm)} lg:grid-cols-[0.85fr_1.15fr]">\n'
            '          <div><h2 className="font-display text-3xl font-bold">' + _title(title) + '</h2><p className="mt-4 text-muted-foreground">A role-aware portal view for every team, record, and workflow.</p></div>\n'
            + _mock_dashboard("Portal modules", items, card_style) +
            '        </div>\n'
            '      </section>\n'
        )

    cards = ""
    for f in items[:6]:
        ft = f.get("title") if isinstance(f, dict) else f
        fd = f.get("text") if isinstance(f, dict) else ("Built in for " + str(f).lower() + ".")
        body = ""
        close = ""
        if card_style == "image-card":
            body = '            <div className="h-32 bg-gradient-to-br from-primary/20 to-primary/5" />\n            <div className="p-6">\n'
            close = '            </div>\n'
        cards += (
            '          <div className="' + _card_class(card_style) + '">\n' + body +
            '            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary"><CheckCircle2 className="h-5 w-5" /></div>\n'
            '            <h3 className="font-display text-lg font-semibold">' + _title(ft) + '</h3>\n'
            '            <p className="mt-2 text-sm text-muted-foreground">' + _t(fd, 150) + '</p>\n'
            + close + '          </div>\n'
        )
    return (
        f'      <section {attr} className="mx-auto max-w-6xl px-6 {_space(rhythm)}">\n'
        '        <h2 className="mb-3 font-display text-3xl font-bold">' + _title(title) + '</h2>\n'
        '        <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">\n' + cards + '        </div>\n'
        '      </section>\n'
    )


def process_steps(title, steps, card_style="bordered", section_variant="timeline", rhythm="spacious"):
    cells = ""
    for i, s in enumerate(steps[:4], 1):
        st = s.get("title") if isinstance(s, dict) else s
        sd = s.get("text") if isinstance(s, dict) else ""
        if section_variant == "timeline":
            cells += (
                '          <div className="grid gap-4 md:grid-cols-[120px_1fr]">\n'
                '            <div className="font-display text-3xl font-bold text-primary">0' + str(i) + '</div>\n'
                '            <div className="' + _card_class(card_style) + '">\n'
                '              <h3 className="font-display text-lg font-semibold">' + _title(st) + '</h3>\n'
                '              <p className="mt-2 text-sm text-muted-foreground">' + _t(sd, 150) + '</p>\n'
                '            </div>\n'
                '          </div>\n'
            )
            continue
        cells += (
            '          <div className="relative ' + _card_class(card_style) + '">\n'
            '            <span className="mb-3 flex h-9 w-9 items-center justify-center rounded-full bg-primary font-display text-sm font-bold text-primary-foreground">' + str(i) + '</span>\n'
            '            <h3 className="font-display text-base font-semibold">' + _title(st) + '</h3>\n'
            '            <p className="mt-1.5 text-sm text-muted-foreground">' + _t(sd, 120) + '</p>\n'
            '          </div>\n'
        )
    grid = "space-y-5" if section_variant == "timeline" else "grid gap-5 sm:grid-cols-2 lg:grid-cols-4"
    return (
        f'      <section data-genome-section-variant="{_t(section_variant, 32)}" data-genome-card-style="{_t(card_style, 24)}" className="border-y bg-muted/30">\n'
        f'        <div className="mx-auto max-w-6xl px-6 {_space(rhythm)}">\n'
        '          <h2 className="mb-8 font-display text-3xl font-bold">' + _title(title) + '</h2>\n'
        f'          <div className="{grid}">\n' + cells + '          </div>\n'
        '        </div>\n      </section>\n'
    )


def split_image_text(title, body, asset, flip=False, card_style="bordered", section_variant="split image/text", rhythm="spacious", image_strategy="section images"):
    if _image_ok(image_strategy):
        img = '          ' + _img(asset, "h-72 md:h-80") + '\n'
    else:
        img = '          ' + _mock_dashboard("Workflow snapshot", [{"title": "Intake"}, {"title": "Review"}, {"title": "Report"}], card_style) + '\n'
    txt = (
        '          <div>\n'
        '            <h2 className="font-display text-3xl font-bold">' + _title(title) + '</h2>\n'
        '            <p className="mt-4 text-muted-foreground">' + _t(body, 320) + '</p>\n'
        '          </div>\n'
    )
    inner = (txt + img) if flip else (img + txt)
    return (
        f'      <section data-genome-section-variant="{_t(section_variant, 32)}" data-genome-image-strategy="{_t(image_strategy, 32)}" className="mx-auto grid max-w-6xl items-center gap-10 px-6 {_space(rhythm)} md:grid-cols-2">\n'
        + inner + '      </section>\n'
    )


def stats_band(stats, card_style="stat-card", section_variant="stats band", rhythm="data-heavy"):
    cells = "".join(
        '          <div className="' + (_card_class(card_style) if card_style != "flat" else "p-2") + '"><p className="font-display text-4xl font-bold text-primary">' + _t(n, 12) +
        '</p><p className="mt-1 text-sm text-muted-foreground">' + _t(l, 30) + '</p></div>\n'
        for n, l in stats
    )
    return (
        f'      <section data-genome-section-variant="{_t(section_variant, 32)}" data-genome-card-style="{_t(card_style, 24)}" className="border-y bg-muted/30">\n'
        f'        <div className="mx-auto grid max-w-6xl grid-cols-2 gap-5 px-6 {_space(rhythm)} md:grid-cols-4">\n'
        + cells + '        </div>\n      </section>\n'
    )


def gallery(assets, caption="Inside the experience", card_style="image-card", rhythm="image-heavy"):
    body = "".join('          ' + _img(a, "h-56") + "\n" for a in assets[:6])
    return (
        f'      <section data-genome-section-variant="gallery" data-genome-card-style="{_t(card_style, 24)}" className="mx-auto max-w-6xl px-6 {_space(rhythm)}">\n'
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


def faq(items, card_style="bordered"):
    rows = ""
    for q, a in items[:5]:
        rows += (
            '          <div className="' + _card_class(card_style) + '">\n'
            '            <h3 className="font-display text-base font-semibold">' + _title(q) + '</h3>\n'
            '            <p className="mt-2 text-sm text-muted-foreground">' + _t(a, 220) + '</p>\n'
            '          </div>\n'
        )
    return (
        f'      <section data-genome-section-variant="FAQ" data-genome-card-style="{_t(card_style, 24)}" className="mx-auto max-w-3xl px-6 py-20">\n'
        '        <h2 className="mb-8 font-display text-3xl font-bold">Frequently asked questions</h2>\n'
        '        <div className="space-y-4">\n' + rows + '        </div>\n      </section>\n'
    )


def pricing(app_name, card_style="bordered"):
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
            '          <div className="' + (_card_class(card_style) if not pop else "rounded-2xl border border-primary bg-card p-7 shadow-lg") + '">\n'
            '            <h3 className="font-display text-lg font-semibold">' + name + '</h3>\n'
            '            <p className="mt-3"><span className="font-display text-4xl font-bold">' + price + '</span><span className="text-muted-foreground">/mo</span></p>\n'
            '            <ul className="mt-6 space-y-3">\n' + items + '            </ul>\n'
            '            <a href="/register" className="mt-7 block rounded-xl ' + ('bg-primary text-primary-foreground' if pop else 'border') + ' px-4 py-2.5 text-center text-sm font-semibold">Choose ' + name + '</a>\n'
            '          </div>\n'
        )
    return (
        f'      <section data-genome-section-variant="pricing" data-genome-card-style="{_t(card_style, 24)}" className="mx-auto max-w-6xl px-6 py-20">\n'
        '        <h2 className="mb-8 text-center font-display text-3xl font-bold">Simple, transparent pricing</h2>\n'
        '        <div className="grid gap-6 md:grid-cols-3">\n' + cols + '        </div>\n      </section>\n'
    )


def cta_band(app_name, label="Create your account", placement="section-end", card_style="bordered"):
    floating = placement == "floating"
    wrap = "rounded-3xl bg-primary px-8 py-14 text-center text-primary-foreground"
    if floating:
        wrap = "rounded-3xl border bg-card px-8 py-12 text-center shadow-2xl"
    return (
        f'      <section data-genome-section-variant="CTA" data-genome-cta-placement="{_t(placement, 24)}" data-genome-card-style="{_t(card_style, 24)}" className="mx-auto max-w-6xl px-6 pb-24 pt-4">\n'
        f'        <div className="{wrap}">\n'
        '          <h2 className="font-display text-3xl font-bold">Ready to get started with ' + _t(app_name, 30) + '?</h2>\n'
        '          <p className="mx-auto mt-3 max-w-xl opacity-90">Join today and see why teams choose us.</p>\n'
        '          <a href="/register" className="mt-7 inline-block rounded-xl ' + ("bg-primary px-6 py-3 font-semibold text-primary-foreground" if floating else "bg-background px-6 py-3 font-semibold text-foreground") + '">' + _t(label, 30) + '</a>\n'
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


# ---------------------------------------------------------------- route/page blueprints
def _slugish(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s or "").lower()).strip("-")


def _page_type(page, idx=0):
    """Infer the route's job so secondary marketing pages stop sharing one shell."""
    name = page.get("name", "")
    slug = page.get("slug", "")
    template = page.get("template", "")
    purpose = page.get("purpose", "")
    hay = f"{name} {slug} {template} {purpose}".lower()
    if idx == 0 and (_slugish(slug) in ("", "home", "index") or str(name).lower() == "home"):
        return "overview"
    if any(x in hay for x in ("compliance", "security", "privacy", "audit", "hipaa", "pdpa", "backup", "encryption")):
        return "compliance"
    if any(x in hay for x in ("provider", "doctor", "staff", "portal", "login", "workspace")):
        return "portal"
    if any(x in hay for x in ("clinic", "management", "admin", "operations", "resource", "bed", "room")):
        return "management"
    if any(x in hay for x in ("report", "analytics", "insight", "metric")):
        return "reports"
    if any(x in hay for x in ("appointment", "booking", "schedule", "visit", "queue")):
        return "booking"
    if any(x in hay for x in ("service", "patient", "catalog", "insurance", "payment", "lab")):
        return "services"
    if any(x in hay for x in ("about", "trust", "team", "department")):
        return "about"
    return "services" if idx % 2 else "about"


_DOMAIN_PAGE_DEFAULTS = {
    "automotive":  {"purpose": "vehicle & financing overview",        "audience": "car buyers and owners",
                    "main_cta": "Browse inventory",                   "secondary_cta": "Book a test drive"},
    "fitness":     {"purpose": "programs, trainers, and class schedule","audience": "members and prospective members",
                    "main_cta": "View programs",                      "secondary_cta": "Meet the trainers"},
    "education":   {"purpose": "courses, curriculum, and enrollment", "audience": "students and instructors",
                    "main_cta": "Explore courses",                    "secondary_cta": "Enroll now"},
    "ai-devtools": {"purpose": "API features and developer workflows", "audience": "developers and engineering teams",
                    "main_cta": "Read the docs",                      "secondary_cta": "Try the API"},
    "restaurant":  {"purpose": "menu, reservations, and dining experience","audience": "guests and event planners",
                    "main_cta": "Reserve a table",                    "secondary_cta": "View the menu"},
    "real-estate": {"purpose": "listings, tours, and neighbourhood guides","audience": "buyers, sellers, and renters",
                    "main_cta": "Browse listings",                    "secondary_cta": "Book a tour"},
    "travel":      {"purpose": "destinations, itineraries, and bookings","audience": "travellers and trip planners",
                    "main_cta": "Explore destinations",               "secondary_cta": "Plan a trip"},
    "ecommerce":   {"purpose": "products, collections, and checkout", "audience": "shoppers",
                    "main_cta": "Shop now",                           "secondary_cta": "View collections"},
    "saas":        {"purpose": "features, plans, and onboarding",     "audience": "teams and decision-makers",
                    "main_cta": "Start free",                         "secondary_cta": "See pricing"},
    "fintech":     {"purpose": "financial tools and secure workflows", "audience": "individuals and finance teams",
                    "main_cta": "Get started",                        "secondary_cta": "View pricing"},
    "agency":      {"purpose": "services, portfolio, and capabilities","audience": "clients and partners",
                    "main_cta": "Start a project",                    "secondary_cta": "See our work"},
    "business-ops":{"purpose": "operations, workflows, and team tools","audience": "operations teams and managers",
                    "main_cta": "Get started",                        "secondary_cta": "See pricing"},
    "community":   {"purpose": "community hub and member resources",  "audience": "members and community leaders",
                    "main_cta": "Join the community",                 "secondary_cta": "Explore events"},
    "media":       {"purpose": "stories, content, and media library", "audience": "readers and media teams",
                    "main_cta": "Read now",                           "secondary_cta": "Browse topics"},
    "healthcare":  {"purpose": "hospital overview and care services", "audience": "patients and families",
                    "main_cta": "Book appointment",                   "secondary_cta": "Find a doctor"},
}


_PAGE_BLUEPRINTS = {
    "overview": {
        "purpose": "hospital overview and trust",
        "audience": "patients, families, and care coordinators",
        "main_cta": "Book appointment",
        "secondary_cta": "Find a doctor",
        "first_screen": "trust hero + emergency contact + appointment action + doctor search",
        "hero_variant": "trust-overview",
        "sections": [
            "emergency-contact", "appointment-cta", "doctor-search-preview",
            "departments-preview", "patient-portal-preview",
        ],
    },
    "services": {
        "purpose": "patient service catalog",
        "audience": "patients preparing for care",
        "main_cta": "View patient services",
        "secondary_cta": "Open patient portal",
        "first_screen": "service catalog hero + booking steps",
        "hero_variant": "catalog-hero",
        "sections": [
            "service-catalog", "appointment-booking-flow", "lab-report-access",
            "insurance-payment-info", "patient-faq", "patient-portal-cta",
        ],
    },
    "portal": {
        "purpose": "provider portal access",
        "audience": "doctors, nurses, and clinical staff",
        "main_cta": "Provider login",
        "secondary_cta": "View schedules",
        "first_screen": "portal login hero + live staff dashboard preview",
        "hero_variant": "portal-dashboard",
        "sections": [
            "provider-dashboard-preview", "schedule-queue", "patient-records-workflow",
            "prescription-lab-orders", "provider-login-cta",
        ],
    },
    "management": {
        "purpose": "clinic operations management",
        "audience": "administrators and operations leaders",
        "main_cta": "Open management dashboard",
        "secondary_cta": "Review resources",
        "first_screen": "operations dashboard hero + resource controls",
        "hero_variant": "operations-console",
        "sections": [
            "operations-dashboard-preview", "departments-clinics-grid", "staff-scheduling",
            "resource-management", "reports-analytics",
        ],
    },
    "compliance": {
        "purpose": "privacy, security, and compliance",
        "audience": "security officers and compliance teams",
        "main_cta": "Review security controls",
        "secondary_cta": "Audit access",
        "first_screen": "security hero + compliance control matrix",
        "hero_variant": "security-matrix",
        "sections": [
            "security-hero", "audit-logs", "data-access-controls",
            "compliance-standards", "backup-encryption",
        ],
    },
    "reports": {
        "purpose": "analytics and reporting",
        "audience": "leaders tracking care delivery",
        "main_cta": "View analytics",
        "secondary_cta": "Export reports",
        "first_screen": "analytics hero + KPI board",
        "hero_variant": "analytics-board",
        "sections": [
            "analytics-dashboard", "report-builder", "trend-insights", "export-schedule",
        ],
    },
    "booking": {
        "purpose": "appointment booking workflow",
        "audience": "patients and front desk staff",
        "main_cta": "Schedule appointment",
        "secondary_cta": "Check availability",
        "first_screen": "booking hero + availability form",
        "hero_variant": "booking-flow",
        "sections": [
            "availability-search", "booking-flow", "visit-prep", "confirmation-cta",
        ],
    },
    "about": {
        "purpose": "trust and organizational story",
        "audience": "patients, partners, and community members",
        "main_cta": "Meet the care team",
        "secondary_cta": "Explore departments",
        "first_screen": "story hero + trust markers",
        "hero_variant": "trust-story",
        "sections": [
            "care-team", "quality-standards", "community-impact", "department-story",
        ],
    },
}


_HOME_BLUEPRINT_BY_FAMILY = {
    "healthcare-clinical": {
        "purpose": "hospital overview and trust",
        "audience": "patients, families, and care coordinators",
        "main_cta": "Book appointment",
        "secondary_cta": "Find a doctor",
        "first_screen": "trust hero + emergency contact + appointment action + doctor search",
        "hero_variant": "trust-overview",
        "sections": [
            "emergency-contact", "appointment-cta", "doctor-search-preview",
            "departments-preview", "patient-portal-preview",
        ],
    },
    "automotive-showroom": {
        "purpose": "vehicle inventory discovery and test-drive conversion",
        "audience": "buyers comparing vehicles, finance options, and availability",
        "main_cta": "View inventory",
        "secondary_cta": "Schedule test drive",
        "first_screen": "showroom hero + vehicle search + finance and test-drive CTA",
        "hero_variant": "vehicle-showroom",
        "sections": ["product-spotlight", "inventory-gallery", "financing-options", "test-drive-flow", "commerce-trust-cta"],
    },
    "product-commerce": {
        "purpose": "product catalog discovery and purchase confidence",
        "audience": "buyers comparing collections, benefits, and next steps",
        "main_cta": "Browse products",
        "secondary_cta": "Compare options",
        "first_screen": "product grid hero + collection browsing + purchase CTA",
        "hero_variant": "product-spotlight",
        "sections": ["product-spotlight", "inventory-gallery", "financing-options", "commerce-trust-cta"],
    },
    "developer-console": {
        "purpose": "developer workflow and API adoption",
        "audience": "developers and technical teams",
        "main_cta": "Start building",
        "secondary_cta": "Read docs",
        "first_screen": "developer console hero + API workflow preview",
        "hero_variant": "developer-console",
        "sections": ["developer-console-preview", "api-workflow-preview", "automation-timeline", "docs-security", "developer-cta"],
    },
    "learning-editorial": {
        "purpose": "course discovery and learning momentum",
        "audience": "students, teachers, and content teams",
        "main_cta": "Explore courses",
        "secondary_cta": "View learning paths",
        "first_screen": "course editorial hero + catalog preview",
        "hero_variant": "course-editorial",
        "sections": ["course-catalog", "learning-path", "instructor-tools", "media-library-preview", "enrollment-cta"],
    },
    "restaurant-reservation": {
        "purpose": "restaurant reservations, menu browsing, and local dining confidence",
        "audience": "guests choosing a table, menu, time, and location",
        "main_cta": "Reserve a table",
        "secondary_cta": "View menu",
        "first_screen": "menu-led reservation hero + opening hours + dining preview",
        "hero_variant": "menu-reservation",
        "sections": ["menu-preview", "reservation-flow", "chef-food-gallery", "hours-location", "private-dining-cta"],
    },
    "travel-destination": {
        "purpose": "destination discovery, tour packages, and trip planning",
        "audience": "travelers comparing places, itineraries, and booking options",
        "main_cta": "Plan trip",
        "secondary_cta": "Explore destinations",
        "first_screen": "destination hero + itinerary cards + location-inspired guide",
        "hero_variant": "destination-map",
        "sections": ["destination-gallery", "itinerary-cards", "tour-package-grid", "map-location-section", "guide-cta"],
    },
    "real-estate-listings": {
        "purpose": "property search, listing discovery, and agent trust",
        "audience": "buyers and renters comparing homes, tours, and neighborhoods",
        "main_cta": "View listings",
        "secondary_cta": "Book a tour",
        "first_screen": "property search hero + listing cards + agent trust",
        "hero_variant": "property-search",
        "sections": ["property-search", "listing-cards", "agent-trust", "neighborhood-highlights", "tour-cta"],
    },
    "fitness-coaching": {
        "purpose": "fitness programs, class booking, and coaching proof",
        "audience": "members choosing programs, trainers, and schedules",
        "main_cta": "Start a plan",
        "secondary_cta": "See schedule",
        "first_screen": "program hero + trainer preview + schedule CTA",
        "hero_variant": "program-split",
        "sections": ["program-cards", "trainer-profiles", "class-schedule", "transformation-proof", "fitness-cta"],
    },
    "creative-portfolio": {
        "purpose": "portfolio storytelling and project proof",
        "audience": "clients, collaborators, and creative teams",
        "main_cta": "View work",
        "secondary_cta": "Start a project",
        "first_screen": "editorial portfolio hero + featured work gallery",
        "hero_variant": "portfolio-editorial",
        "sections": ["featured-work-gallery", "studio-process", "capabilities-grid", "client-proof", "project-cta"],
    },
    "finance-trust": {
        "purpose": "financial trust and product proof",
        "audience": "finance teams, customers, and decision makers",
        "main_cta": "View financial dashboard",
        "secondary_cta": "Review security",
        "first_screen": "metrics-first trust hero + secure dashboard preview",
        "hero_variant": "fintech-metrics",
        "sections": ["financial-dashboard-preview", "trust-metrics", "payment-workflow", "security-controls", "finance-cta"],
    },
    "operations-console": {
        "purpose": "operations command center",
        "audience": "operators, managers, and back-office teams",
        "main_cta": "Open operations",
        "secondary_cta": "View workflows",
        "first_screen": "operations metrics hero + workflow board",
        "hero_variant": "operations-console",
        "sections": ["operations-dashboard-preview", "workflow-queue", "inventory-control", "team-shift-planning", "reports-analytics"],
    },
    "ecommerce-product": {
        "purpose": "premium product and marketplace discovery",
        "audience": "buyers comparing products and booking next steps",
        "main_cta": "Browse inventory",
        "secondary_cta": "Book test drive",
        "first_screen": "product spotlight hero + inventory discovery + purchase CTA",
        "hero_variant": "product-spotlight",
        "sections": ["product-spotlight", "inventory-gallery", "financing-options", "test-drive-flow", "commerce-trust-cta"],
    },
    "ai-devtools": {
        "purpose": "developer workflow and API adoption",
        "audience": "developers and technical teams",
        "main_cta": "Start building",
        "secondary_cta": "Read docs",
        "first_screen": "developer console hero + API workflow preview",
        "hero_variant": "developer-console",
        "sections": ["developer-console-preview", "api-workflow-preview", "automation-timeline", "docs-security", "developer-cta"],
    },
    "education-media": {
        "purpose": "course discovery and learning momentum",
        "audience": "students, teachers, and content teams",
        "main_cta": "Explore courses",
        "secondary_cta": "View learning paths",
        "first_screen": "course editorial hero + catalog preview",
        "hero_variant": "course-editorial",
        "sections": ["course-catalog", "learning-path", "instructor-tools", "media-library-preview", "enrollment-cta"],
    },
    "operational-business": {
        "purpose": "operations command center",
        "audience": "operators, managers, and back-office teams",
        "main_cta": "Open operations",
        "secondary_cta": "View workflows",
        "first_screen": "operations metrics hero + workflow board",
        "hero_variant": "operations-console",
        "sections": ["operations-dashboard-preview", "workflow-queue", "inventory-control", "team-shift-planning", "reports-analytics"],
    },
    "creative-agency": {
        "purpose": "portfolio storytelling and project proof",
        "audience": "clients, collaborators, and creative teams",
        "main_cta": "View work",
        "secondary_cta": "Start a project",
        "first_screen": "editorial portfolio hero + featured work gallery",
        "hero_variant": "portfolio-editorial",
        "sections": ["featured-work-gallery", "studio-process", "capabilities-grid", "client-proof", "project-cta"],
    },
    "fintech-trust": {
        "purpose": "financial trust and product proof",
        "audience": "finance teams, customers, and decision makers",
        "main_cta": "View financial dashboard",
        "secondary_cta": "Review security",
        "first_screen": "metrics-first trust hero + secure dashboard preview",
        "hero_variant": "fintech-metrics",
        "sections": ["financial-dashboard-preview", "trust-metrics", "payment-workflow", "security-controls", "finance-cta"],
    },
}


_SECTION_COPY = {
    "emergency-contact": (
        "Emergency contact", "One-tap access to emergency numbers, triage guidance, and the right department when minutes matter.",
        ["Emergency desk", "Ambulance intake", "Critical care escalation"],
    ),
    "appointment-cta": (
        "Appointment booking", "Guide patients from symptom or department search to an available slot with clear next steps.",
        ["Choose specialty", "Pick doctor", "Confirm visit"],
    ),
    "doctor-search-preview": (
        "Doctor search preview", "Let patients filter by specialty, availability, language, and care location before they book.",
        ["Cardiology", "Pediatrics", "Orthopedics", "General care"],
    ),
    "departments-preview": (
        "Departments preview", "Surface the clinics, diagnostic units, and care teams that patients need most often.",
        ["Outpatient", "Laboratory", "Radiology", "Pharmacy", "Emergency", "Surgery"],
    ),
    "patient-portal-preview": (
        "Patient portal preview", "Show patients where appointments, lab reports, prescriptions, and messages live after sign-in.",
        ["Reports", "Visits", "Prescriptions", "Messages"],
    ),
    "service-catalog": (
        "Patient service catalog", "A browsable catalog for consultations, diagnostics, procedures, wellness checks, and follow-up care.",
        ["Consultations", "Diagnostics", "Vaccinations", "Follow-ups", "Telehealth", "Wellness"],
    ),
    "appointment-booking-flow": (
        "Appointment booking flow", "A step-by-step journey that keeps availability, prerequisites, and confirmations in one path.",
        ["Search care", "Select slot", "Confirm details", "Receive reminders"],
    ),
    "lab-report-access": (
        "Lab report access", "Patients can find new results, historical reports, and physician notes without calling the front desk.",
        ["New result alert", "Download PDF", "Share with doctor"],
    ),
    "insurance-payment-info": (
        "Insurance and payments", "Clarify accepted plans, deposits, invoices, and balances before the patient arrives.",
        ["Insurance plans", "Co-pay status", "Online receipts"],
    ),
    "patient-faq": (
        "Patient FAQs", "Answer practical care questions about preparation, documents, payment, arrival times, and follow-up.",
        ["What to bring?", "When to arrive?", "How to view results?"],
    ),
    "patient-portal-cta": (
        "Patient portal CTA", "A focused sign-in path for existing patients who need records, visits, bills, or messages.",
        ["Sign in", "Check reports", "Message care team"],
    ),
    "provider-dashboard-preview": (
        "Provider dashboard preview", "A clinical workspace for today's schedule, queue status, pending results, and urgent follow-ups.",
        ["Today's visits", "Open notes", "Critical labs", "Follow-ups"],
    ),
    "schedule-queue": (
        "Schedule and queue", "Staff see who is checked in, who is waiting, and which rooms or doctors are running behind.",
        ["Checked in", "Waiting", "In consultation", "Ready for billing"],
    ),
    "patient-records-workflow": (
        "Patient records workflow", "Move from visit history to notes, allergies, attachments, and next actions without losing context.",
        ["History", "Vitals", "Notes", "Care plan"],
    ),
    "prescription-lab-orders": (
        "Prescription and lab orders", "Create prescriptions, order tests, and send instructions directly from the encounter workflow.",
        ["Medication", "Lab order", "Radiology", "Instructions"],
    ),
    "provider-login-cta": (
        "Provider login CTA", "A secure entry point for doctors, nurses, and staff to continue clinical work.",
        ["Use SSO", "Verify role", "Open portal"],
    ),
    "operations-dashboard-preview": (
        "Operations dashboard preview", "Administrators watch admissions, queues, billing, rooms, and staffing from one operational board.",
        ["Admissions", "Queue time", "Revenue", "Occupancy"],
    ),
    "departments-clinics-grid": (
        "Departments and clinics grid", "Organize care locations, owners, capacity, and operating hours by department.",
        ["Emergency", "OPD", "Dental", "Pediatrics", "Lab", "Radiology"],
    ),
    "staff-scheduling": (
        "Staff scheduling", "Balance rosters, shifts, leave, and specialty coverage across the hospital day.",
        ["Roster gaps", "Shift swaps", "Coverage alerts"],
    ),
    "resource-management": (
        "Bed, room, and resource management", "Track bed availability, room status, equipment, and care-team assignments in real time.",
        ["Beds", "Rooms", "Equipment", "Transfers"],
    ),
    "reports-analytics": (
        "Reports and analytics", "Turn activity into operational reports for utilization, wait time, revenue, and care quality.",
        ["Utilization", "Wait time", "Billing", "Outcomes"],
    ),
    "security-hero": (
        "Privacy and security hero", "Position privacy, auditability, and protected health information as first-class product concerns.",
        ["Protected records", "Role controls", "Auditable changes"],
    ),
    "audit-logs": (
        "Audit logs", "Track record views, edits, exports, authentication events, and administrator changes.",
        ["Viewed chart", "Updated role", "Exported report", "Changed billing"],
    ),
    "data-access-controls": (
        "Data access controls", "Role-based permissions keep patient, billing, clinical, and administrative data separated.",
        ["Doctor access", "Nurse access", "Billing access", "Admin access"],
    ),
    "compliance-standards": (
        "Compliance standards", "Map operational controls to PDPA/HIPAA-style expectations for privacy, retention, and incident response.",
        ["Privacy policies", "Consent records", "Retention rules", "Incident review"],
    ),
    "backup-encryption": (
        "Backup and encryption", "Explain encryption, backups, recovery windows, and continuity planning in plain language.",
        ["Encrypted storage", "Daily backups", "Recovery testing"],
    ),
    "analytics-dashboard": (
        "Analytics dashboard", "A KPI board for clinical, financial, and operational performance across the organization.",
        ["Visits", "Revenue", "Utilization", "Quality"],
    ),
    "report-builder": (
        "Report builder", "Create recurring reports by department, provider, period, or care workflow.",
        ["Choose data", "Filter views", "Schedule delivery"],
    ),
    "trend-insights": (
        "Trend insights", "Spot pressure points in demand, capacity, quality, and billing before they become blockers.",
        ["Demand", "Capacity", "Revenue", "Quality"],
    ),
    "export-schedule": (
        "Export schedule", "Send reports to the right team on the right cadence without manual spreadsheet work.",
        ["Daily", "Weekly", "Monthly"],
    ),
    "availability-search": (
        "Availability search", "Let patients search open appointment slots by department, doctor, location, and urgency.",
        ["Today", "This week", "Specialist", "Telehealth"],
    ),
    "booking-flow": (
        "Booking flow", "A simple appointment path from need to confirmed visit.",
        ["Select care", "Choose slot", "Confirm patient", "Get reminder"],
    ),
    "visit-prep": (
        "Visit preparation", "Collect documents, insurance details, symptoms, and consent before arrival.",
        ["Documents", "Symptoms", "Insurance", "Consent"],
    ),
    "confirmation-cta": (
        "Confirmation CTA", "Close the booking journey with a clear confirmation and portal next step.",
        ["Confirmed", "Calendar", "Portal"],
    ),
    "care-team": (
        "Care team", "Introduce the people, specialties, and standards behind the hospital experience.",
        ["Doctors", "Nurses", "Technicians", "Coordinators"],
    ),
    "quality-standards": (
        "Quality standards", "Show how the organization measures safety, responsiveness, and continuity of care.",
        ["Safety", "Continuity", "Responsiveness"],
    ),
    "community-impact": (
        "Community impact", "Highlight community programs, preventive care, outreach, and accessibility.",
        ["Screenings", "Education", "Outreach"],
    ),
    "department-story": (
        "Department story", "Connect the hospital's departments to the people and outcomes they support.",
        ["Specialties", "Facilities", "Care paths"],
    ),
    "product-spotlight": (
        "Product spotlight", "Lead with the product, value, and buying action instead of a generic software overview.",
        ["Featured model", "Availability", "Comparison", "Offer"],
    ),
    "inventory-gallery": (
        "Inventory gallery", "A visual browsing section for products, filters, specs, and saved comparisons.",
        ["New arrivals", "Certified stock", "Premium trims", "Compare"],
    ),
    "financing-options": (
        "Financing options", "Make pricing, finance terms, deposits, and trade-in paths clear before a buyer enquires.",
        ["Monthly estimate", "Trade-in", "Deposit", "Pre-approval"],
    ),
    "test-drive-flow": (
        "Test drive flow", "Move shoppers from interest to an appointment with a simple availability path.",
        ["Choose vehicle", "Pick branch", "Select time", "Confirm visit"],
    ),
    "commerce-trust-cta": (
        "Commerce trust CTA", "Close the product journey with a confident next step for browsing or booking.",
        ["Browse", "Book", "Contact"],
    ),
    "developer-console-preview": (
        "Developer console preview", "Show the API surface, project status, usage, and deployment controls immediately.",
        ["API keys", "Requests", "Agents", "Deployments"],
    ),
    "api-workflow-preview": (
        "API workflow preview", "Explain how developers connect, test, automate, and ship from one workspace.",
        ["Connect", "Test", "Automate", "Ship"],
    ),
    "automation-timeline": (
        "Automation timeline", "A sequence view for prompts, code actions, reviews, and production releases.",
        ["Trigger", "Plan", "Run", "Review"],
    ),
    "docs-security": (
        "Docs and security", "Pair quick-start documentation with the security controls teams need before adoption.",
        ["Docs", "Tokens", "Roles", "Audit"],
    ),
    "developer-cta": (
        "Developer CTA", "Give technical buyers a clear path to start building or read the docs.",
        ["Start", "Docs", "Examples"],
    ),
    "course-catalog": (
        "Course catalog", "A browsable course library organized by level, topic, pace, and outcomes.",
        ["Featured courses", "Certificates", "Skill paths", "Live cohorts"],
    ),
    "learning-path": (
        "Learning path", "Guide students through lessons, assignments, assessments, and completion milestones.",
        ["Start", "Practice", "Submit", "Complete"],
    ),
    "instructor-tools": (
        "Instructor tools", "Give teachers a view of classes, submissions, content, and student progress.",
        ["Classes", "Submissions", "Feedback", "Progress"],
    ),
    "media-library-preview": (
        "Media library preview", "Show videos, articles, downloads, and course materials in a content-first layout.",
        ["Video", "Article", "Workbook", "Playlist"],
    ),
    "enrollment-cta": (
        "Enrollment CTA", "Turn discovery into enrollment with a focused course action.",
        ["Enroll", "Save", "Share"],
    ),
    "workflow-queue": (
        "Workflow queue", "Track the operational queue from request intake to completed work.",
        ["Intake", "Assigned", "Blocked", "Done"],
    ),
    "inventory-control": (
        "Inventory control", "Keep stock, suppliers, orders, and exceptions in one command view.",
        ["Stock", "Supplier", "Order", "Exception"],
    ),
    "team-shift-planning": (
        "Team shift planning", "Balance staffing, coverage, handoffs, and alerts for operational teams.",
        ["Roster", "Coverage", "Handoff", "Alert"],
    ),
    "featured-work-gallery": (
        "Featured work gallery", "Lead with high-impact project previews, categories, and outcomes.",
        ["Case study", "Launch", "Identity", "Experience"],
    ),
    "studio-process": (
        "Studio process", "Explain discovery, concepting, prototyping, and launch as a clear client journey.",
        ["Discover", "Shape", "Prototype", "Launch"],
    ),
    "capabilities-grid": (
        "Capabilities grid", "Show the studio's services as concise creative capabilities.",
        ["Strategy", "Design", "Content", "Engineering"],
    ),
    "client-proof": (
        "Client proof", "Use outcomes, testimonials, and project metrics without copying a reference site.",
        ["Outcome", "Quote", "Metric"],
    ),
    "project-cta": (
        "Project CTA", "Invite qualified clients to start a project or view the work archive.",
        ["Brief", "Portfolio", "Contact"],
    ),
    "financial-dashboard-preview": (
        "Financial dashboard preview", "Lead with balances, cash movement, controls, and trusted financial signals.",
        ["Balance", "Cashflow", "Invoices", "Approvals"],
    ),
    "trust-metrics": (
        "Trust metrics", "Make reliability, security, and financial visibility easy to scan.",
        ["Uptime", "Controls", "Audit", "Coverage"],
    ),
    "payment-workflow": (
        "Payment workflow", "Show money movement from request to approval, transfer, and reconciliation.",
        ["Request", "Approve", "Transfer", "Reconcile"],
    ),
    "security-controls": (
        "Security controls", "Explain roles, policies, audit logs, and data protection for financial workflows.",
        ["Roles", "Policies", "Logs", "Encryption"],
    ),
    "finance-cta": (
        "Finance CTA", "Give finance teams a clear way to review the dashboard or security posture.",
        ["Dashboard", "Security", "Demo"],
    ),
    "menu-preview": (
        "Menu preview", "Show signature dishes, categories, prices, and pairing choices before guests reserve.",
        ["Chef picks", "Lunch set", "Family table", "Desserts", "Drinks"],
    ),
    "reservation-flow": (
        "Reservation flow", "Move guests from party size and date to table choice, confirmation, and reminders.",
        ["Party size", "Date", "Time", "Confirm"],
    ),
    "chef-food-gallery": (
        "Chef and food gallery", "Use image-led cards for dishes, chef notes, and seasonal specials without relying on template art.",
        ["Seasonal plate", "Chef note", "Kitchen story", "Private dining"],
    ),
    "hours-location": (
        "Hours and location", "Put opening hours, map-like location cues, parking notes, and phone contact in one block.",
        ["Lunch hours", "Dinner hours", "Parking", "Call ahead"],
    ),
    "private-dining-cta": (
        "Private dining CTA", "Close the restaurant page with group booking, event dining, or direct reservation action.",
        ["Reserve", "Call", "Private room"],
    ),
    "destination-gallery": (
        "Destination gallery", "Lead with destinations, seasons, activity types, and travel moods in visual cards.",
        ["Beach", "Mountain", "City", "Culture", "Nature"],
    ),
    "itinerary-cards": (
        "Itinerary cards", "Preview day-by-day trip structure so travelers can understand the experience quickly.",
        ["Day 1", "Day 2", "Day 3", "Optional"],
    ),
    "tour-package-grid": (
        "Tour package grid", "Compare packages by duration, group size, inclusions, and starting point.",
        ["Weekend", "Family", "Adventure", "Custom"],
    ),
    "map-location-section": (
        "Map and location section", "Use location-inspired panels for route, pickup, landmarks, and travel notes.",
        ["Pickup", "Route", "Landmark", "Guide"],
    ),
    "guide-cta": (
        "Guide CTA", "Invite travelers to plan a trip, ask a guide, or reserve a package.",
        ["Plan", "Ask guide", "Reserve"],
    ),
    "property-search": (
        "Property search", "Let visitors filter listings by location, budget, bedrooms, and tour availability.",
        ["Location", "Budget", "Beds", "Tour"],
    ),
    "listing-cards": (
        "Listing cards", "Show properties as scannable cards with key details, price cues, and status.",
        ["For sale", "For rent", "New listing", "Featured"],
    ),
    "agent-trust": (
        "Agent trust", "Introduce agents, response expectations, valuation help, and neighborhood knowledge.",
        ["Agent", "Valuation", "Tour support", "Local guide"],
    ),
    "neighborhood-highlights": (
        "Neighborhood highlights", "Help buyers compare schools, transit, parks, and lifestyle signals.",
        ["Schools", "Transit", "Parks", "Dining"],
    ),
    "tour-cta": (
        "Tour CTA", "Turn property interest into a viewing, valuation, or agent call.",
        ["Book tour", "Contact agent", "Save listing"],
    ),
    "program-cards": (
        "Program cards", "Present coaching programs by goal, intensity, format, and expected outcome.",
        ["Strength", "Mobility", "Nutrition", "Recovery"],
    ),
    "trainer-profiles": (
        "Trainer profiles", "Show coaches, specialties, availability, and class fit in human-centered cards.",
        ["Coach", "Specialty", "Availability", "Style"],
    ),
    "class-schedule": (
        "Class schedule", "Make session times, levels, capacity, and booking status easy to scan.",
        ["Morning", "Lunch", "Evening", "Weekend"],
    ),
    "transformation-proof": (
        "Transformation proof", "Use progress stats, testimonials, and habit outcomes without generic claims.",
        ["Progress", "Consistency", "Energy", "Confidence"],
    ),
    "fitness-cta": (
        "Fitness CTA", "Close with a class booking, consultation, or plan selection action.",
        ["Book class", "Meet coach", "Start plan"],
    ),
}


def _route_blueprint(page, bp, idx, visual):
    page_type = _page_type(page, idx)
    inspiration_family = visual.get("inspiration_family", "")
    visual_family = visual.get("visual_family") or inspiration_family
    family_for_blueprint = visual_family if visual_family in _HOME_BLUEPRINT_BY_FAMILY else inspiration_family
    if page_type == "overview" and family_for_blueprint in _HOME_BLUEPRINT_BY_FAMILY:
        base = dict(_HOME_BLUEPRINT_BY_FAMILY[family_for_blueprint])
    else:
        base = dict(_PAGE_BLUEPRINTS.get(page_type) or _PAGE_BLUEPRINTS["about"])
    # Override healthcare-default purpose/audience/CTA with domain-correct copy.
    # Skip healthcare itself — _PAGE_BLUEPRINTS already has correct, page-type-specific
    # CTAs for healthcare (e.g. "Provider login", "Open management dashboard"). Applying
    # the generic "Book appointment" override would regress those specific pages.
    try:
        from app import page_block_selector as _pbs
        _dom_prompt = " ".join([str(bp.get("domain", "")), str(page.get("name", ""))])
        _dom_genome = {"visual_family": visual_family, "inspiration_family": inspiration_family}
        _dom = _pbs.resolve_family_and_domain(_dom_prompt, _dom_genome)[1]
        if _dom != "healthcare":
            for _k, _v in (_DOMAIN_PAGE_DEFAULTS.get(_dom) or {}).items():
                base[_k] = _v
    except Exception:
        pass
    sections = list(page.get("sections") or [])
    if sections:
        chosen = [s for s in sections if s in _SECTION_COPY]
        if chosen:
            base["sections"] = chosen
    hero_choices = ["trust-overview", "catalog-hero", "portal-dashboard", "operations-console",
                    "security-matrix", "analytics-board", "booking-flow", "trust-story"]
    card_choices = ["bordered", "glass", "shadow", "image-card", "stat-card", "flat"]
    image_choices = ["hero image", "section images", "dashboard mockup", "gallery", "no-image fallback"]
    base["page_type"] = page_type
    base["name"] = page.get("name", "Page")
    base["slug"] = page.get("slug", "page")
    base["inspiration_family"] = inspiration_family
    base["visual_family"] = visual_family
    base["color_palette_family"] = visual.get("color_palette_family", "")
    base["typography_style"] = visual.get("typography_style", "")
    base["spacing_style"] = visual.get("spacing_style", "")
    base["footer_style"] = visual.get("footer_style", "")
    base["hero_recipe"] = dict(visual.get("hero_recipe") or {})
    base["nav_recipe"] = dict(visual.get("nav_recipe") or {})
    base["section_recipes"] = list(visual.get("section_recipes") or [])
    base["section_recipe_ids"] = list(visual.get("section_recipe_ids") or [])
    base["card_recipe"] = dict(visual.get("card_recipe") or {})
    base["cta_recipe"] = dict(visual.get("cta_recipe") or {})
    base["footer_recipe"] = dict(visual.get("footer_recipe") or {})
    base["browser_visible_signature"] = visual.get("browser_visible_signature", "")
    base["art_director_enabled"] = bool(visual.get("art_director_enabled"))
    base["premium_preset"] = dict(visual.get("premium_preset") or {})
    base["premium_preset_id"] = visual.get("premium_preset_id", "")
    base["premium_preset_name"] = visual.get("premium_preset_name", "")
    base["design_quality_before"] = dict(visual.get("design_quality_before") or {})
    base["design_quality_after"] = dict(visual.get("design_quality_after") or {})
    base["image_roles"] = dict(visual.get("image_roles") or {})
    base["image_reuse_limit"] = visual.get("image_reuse_limit", 2)
    base["rich_component_variants"] = list(visual.get("rich_component_variants") or [])
    base["recipe_source_mode"] = visual.get("recipe_source_mode", "handcrafted")
    base["extracted_design_recipes"] = list(visual.get("extracted_design_recipes") or [])
    base["extracted_recipe_ids"] = list(visual.get("extracted_recipe_ids") or [])
    base["extracted_recipe_families"] = list(visual.get("extracted_recipe_families") or [])
    base["github_recipe_influence"] = dict(visual.get("github_recipe_influence") or {})
    base["dna_profile_ids"] = list(visual.get("dna_profile_ids") or [])
    base["dna_families"] = list(visual.get("dna_families") or [])
    base["primary_dna_family"] = (base["dna_families"][0] if base["dna_families"] else "")
    base["hero_patterns"] = list(visual.get("hero_patterns") or [])
    base["nav_patterns"] = list(visual.get("nav_patterns") or [])
    base["card_patterns"] = list(visual.get("card_patterns") or [])
    base["section_patterns"] = list(visual.get("section_patterns") or [])
    route_hero = base.get("hero_variant") or hero_choices[idx % len(hero_choices)]
    genome_hero = visual.get("hero_variant")
    base["hero_variant"] = f"{route_hero}:{genome_hero}" if genome_hero else route_hero
    base["card_style"] = visual.get("card_style") or card_choices[idx % len(card_choices)]
    base["rhythm"] = visual.get("layout_rhythm") or "spacious"
    base["image_strategy"] = visual.get("image_strategy") or image_choices[idx % len(image_choices)]
    genome_screen = visual.get("first_screen_skeleton") or genome_hero
    if genome_screen:
        base["first_screen"] = f"{base['first_screen']} | {genome_screen}"
    base["cta_placement"] = visual.get("cta_placement") or "section-end"
    base["signature"] = "|".join([
        base["inspiration_family"], base["visual_family"], base["primary_dna_family"], base["page_type"], base["hero_variant"], base["first_screen"], base["card_style"],
        (base.get("hero_recipe") or {}).get("id", ""), (base.get("nav_recipe") or {}).get("id", ""),
        (base.get("card_recipe") or {}).get("id", ""), "~".join(base.get("section_recipe_ids") or []),
        base["image_strategy"], base["cta_placement"], base["main_cta"], base.get("premium_preset_id", ""), "~".join(base["sections"]),
        base.get("recipe_source_mode", ""), "~".join(base.get("extracted_recipe_ids") or []),
    ])
    return base


def _route_kicker(bp, app_name):
    return bp.get("domain", app_name) or app_name


def _route_metrics(page_type):
    return {
        "overview": [("24/7", "Emergency"), ("30+", "Departments"), ("4.8", "Patient score")],
        "services": [("6", "Care paths"), ("3 min", "Booking"), ("100%", "Report access")],
        "portal": [("Today", "Rounds"), ("18", "Pending labs"), ("9", "Queue alerts")],
        "management": [("86%", "Bed use"), ("12", "Open shifts"), ("4", "Resource alerts")],
        "compliance": [("100%", "Role gated"), ("24h", "Audit trail"), ("AES", "Encryption")],
        "reports": [("14", "Dashboards"), ("7", "Scheduled"), ("Live", "Signals")],
        "booking": [("Now", "Open slots"), ("4", "Visit types"), ("SMS", "Reminders")],
        "about": [("20+", "Specialties"), ("15k", "Patients"), ("4.9", "Trust score")],
    }.get(page_type, [("Live", "Ready"), ("Secure", "Access"), ("Fast", "Setup")])


def _mini_metrics(page_type, bp_page=None):
    card_cls = _route_card_class(bp_page, "stat-card") if bp_page else "rounded-xl border bg-background/80 p-4"
    return "".join(
        '              <div className="' + card_cls + '">\n'
        '                <p className="font-display text-2xl font-bold text-primary">' + _t(n, 12) + '</p>\n'
        '                <p className="text-xs text-muted-foreground">' + _t(l, 28) + '</p>\n'
        '              </div>\n'
        for n, l in _route_metrics(page_type)
    )


def _domain_image(bp_page, role, height="h-52 md:h-64", alt="Generated domain visual"):
    preset = _premium_preset(bp_page)
    return _img(
        _image_asset_for_role(role, bp_page),
        height,
        preset.get("image_class", "") if _art_director_enabled(bp_page) else "",
        alt=alt,
        role=role,
    )


def _recipe_showcase_panel(bp_page, app_name, card_style, chip_class):
    family = bp_page.get("visual_family") or bp_page.get("inspiration_family", "")
    card = _route_card_class(bp_page, card_style)
    stat = _route_card_class(bp_page, "stat-card")
    if family == "restaurant-reservation":
        return (
            '          <div className="grid gap-4">\n'
            '            ' + _domain_image(bp_page, "food_signature", "h-56 md:h-72", "Signature dish and dining ambience") + '\n'
            '            <div className="' + card + '"><p className="text-xs font-semibold uppercase tracking-wider text-primary">Tonight menu</p><h3 className="mt-2 font-display text-2xl font-bold">Chef picks and table times</h3><div className="mt-4 grid gap-2 text-sm"><span className="' + chip_class + '">Seasonal plate</span><span className="' + chip_class + '">Private dining</span><span className="' + chip_class + '">Open 6:00-10:30</span></div></div>\n'
            '            <div className="grid gap-4 sm:grid-cols-2"><div className="' + stat + '"><p className="font-display text-2xl font-bold text-primary">7:30</p><p className="text-xs text-muted-foreground">Next table</p></div><div className="' + stat + '"><p className="font-display text-2xl font-bold text-primary">42</p><p className="text-xs text-muted-foreground">Seats left</p></div></div>\n'
            '          </div>\n'
        )
    if family == "travel-destination":
        return (
            '          <div className="grid gap-4">\n'
            '            ' + _domain_image(bp_page, "destination", "h-56 md:h-72", "Featured destination landscape") + '\n'
            '            <div className="' + card + '"><p className="text-xs font-semibold uppercase tracking-wider text-primary">Trip map</p><div className="mt-4 h-44 rounded-3xl bg-gradient-to-br from-cyan-200 via-white to-amber-200 p-4"><div className="h-full rounded-2xl border-2 border-dashed border-teal-500/70" /></div></div>\n'
            '            <div className="grid gap-3 sm:grid-cols-3"><span className="' + chip_class + '">Day 1 coast</span><span className="' + chip_class + '">Day 2 culture</span><span className="' + chip_class + '">Day 3 nature</span></div>\n'
            '          </div>\n'
        )
    if family == "real-estate-listings":
        return (
            '          <div className="grid gap-4">\n'
            '            ' + _domain_image(bp_page, "property_listing", "h-56 md:h-72", "Featured property listing") + '\n'
            '            <div className="' + card + '"><p className="text-xs font-semibold uppercase tracking-wider text-primary">Property search</p><div className="mt-4 grid gap-3 sm:grid-cols-2"><span className="' + chip_class + '">Location</span><span className="' + chip_class + '">Budget</span><span className="' + chip_class + '">Bedrooms</span><span className="' + chip_class + '">Tour time</span></div></div>\n'
            '            <div className="grid gap-4 sm:grid-cols-2"><div className="' + stat + '"><p className="font-display text-2xl font-bold text-primary">18</p><p className="text-xs text-muted-foreground">New listings</p></div><div className="' + stat + '"><p className="font-display text-2xl font-bold text-primary">4</p><p className="text-xs text-muted-foreground">Open tours</p></div></div>\n'
            '          </div>\n'
        )
    if family == "fitness-coaching":
        return (
            '          <div className="grid gap-4">\n'
            '            ' + _domain_image(bp_page, "program", "h-56 md:h-72", "Fitness program training session") + '\n'
            '            <div className="' + card + '"><p className="text-xs font-semibold uppercase tracking-wider text-primary">This week</p><h3 className="mt-2 font-display text-2xl font-bold">Programs, coaches, and class times</h3><div className="mt-4 grid gap-2 sm:grid-cols-2"><span className="' + chip_class + '">Strength</span><span className="' + chip_class + '">Mobility</span><span className="' + chip_class + '">Nutrition</span><span className="' + chip_class + '">Recovery</span></div></div>\n'
            '            <div className="grid gap-4 sm:grid-cols-2"><div className="' + stat + '"><p className="font-display text-2xl font-bold text-primary">12</p><p className="text-xs text-muted-foreground">Classes open</p></div><div className="' + stat + '"><p className="font-display text-2xl font-bold text-primary">5</p><p className="text-xs text-muted-foreground">Coaches live</p></div></div>\n'
            '          </div>\n'
        )
    if family in ("developer-console", "ai-devtools"):
        return (
            '          <div className="grid gap-4">\n'
            '            ' + _domain_image(bp_page, "console", "h-48 md:h-60", "API console and workflow preview") + '\n'
            + _mock_dashboard("API workbench", [{"title": "POST /runs"}, {"title": "Agent trace"}, {"title": "Policy check"}, {"title": "Deploy preview"}], card_style).replace(_card_class(card_style), card, 1).replace('          ', '            ', 1) +
            '          </div>\n'
        )
    if family in ("automotive-showroom", "product-commerce", "ecommerce-product"):
        return (
            '          <div className="grid gap-4">\n'
            '            ' + _domain_image(bp_page, "vehicle_showroom", "h-56 md:h-72", "Premium vehicle showroom") + '\n'
            '            <div className="' + card + '"><p className="text-xs font-semibold uppercase tracking-wider text-primary">Featured inventory</p><div className="mt-4 grid gap-3 sm:grid-cols-2"><span className="' + chip_class + '">Certified</span><span className="' + chip_class + '">Finance ready</span><span className="' + chip_class + '">Compare</span><span className="' + chip_class + '">Book test drive</span></div></div>\n'
            '            <div className="grid gap-4 sm:grid-cols-2"><div className="' + stat + '"><p className="font-display text-2xl font-bold text-primary">36</p><p className="text-xs text-muted-foreground">Available</p></div><div className="' + stat + '"><p className="font-display text-2xl font-bold text-primary">0-1</p><p className="text-xs text-muted-foreground">Click inquiry</p></div></div>\n'
            '          </div>\n'
        )
    if family in ("learning-editorial", "education-media"):
        return (
            '          <div className="grid gap-4">\n'
            '            ' + _domain_image(bp_page, "course_catalog", "h-56 md:h-72", "Course catalog and learning media") + '\n'
            '            <div className="' + card + '"><p className="text-xs font-semibold uppercase tracking-wider text-primary">Course shelf</p><div className="mt-4 grid gap-3"><span className="' + chip_class + '">Featured course</span><span className="' + chip_class + '">Learning path</span><span className="' + chip_class + '">Instructor tools</span></div></div>\n'
            '            <div className="' + stat + '"><p className="font-display text-2xl font-bold text-primary">120+</p><p className="text-xs text-muted-foreground">Lessons ready</p></div>\n'
            '          </div>\n'
        )
    first_sections = list(bp_page.get("sections") or [])[:3]
    cards = ""
    for sid in first_sections[:2]:
        st, sd, items = _SECTION_COPY.get(sid, _SECTION_COPY["service-catalog"])
        chips = "".join('<span className="' + chip_class + '">' + _t(x, 22) + '</span>' for x in items[:4])
        cards += (
            '            <div className="' + card + '">\n'
            '              <p className="text-xs font-semibold uppercase tracking-wider text-primary">' + _t(st, 34) + '</p>\n'
            '              <p className="mt-2 text-sm text-muted-foreground">' + _t(sd, 140) + '</p>\n'
            '              <div className="mt-4 grid grid-cols-2 gap-2 text-sm">' + chips + '</div>\n'
            '            </div>\n'
        )
    return '          <div className="grid gap-4">\n' + cards + '          </div>\n'


def _route_recipe_overview_hero(bp_page, app_name, bp, idx, data):
    recipe = _recipe(bp_page, "hero")
    layout = recipe.get("layout", "split-search")
    name = bp_page["name"]
    kicker = _route_kicker(bp, app_name)
    main = bp_page["main_cta"]
    secondary = bp_page["secondary_cta"]
    card_style = bp_page["card_style"]
    hero_class = _route_hero_class(bp_page)
    h1_class = _route_h1_class(bp_page)
    primary_cta = _primary_cta_class(bp_page)
    secondary_cta = _secondary_cta_class(bp_page)
    chip_class = _route_chip_class(bp_page)
    panel = _recipe_showcase_panel(bp_page, app_name, card_style, chip_class)
    lead = _t(bp_page["purpose"].capitalize() + " for " + bp_page["audience"] + ".", 240)
    if layout in ("immersive-gallery", "destination-map", "showroom-stage", "neighborhood-editorial", "asymmetric-editorial"):
        return (
            f'      <section {data} className="{hero_class}">\n'
            '        <div className="mx-auto grid max-w-7xl gap-8 px-6 py-16 lg:grid-cols-[0.82fr_1.18fr] lg:py-24">\n'
            '          <div className="self-end">\n'
            '            <p className="mb-5 text-sm font-semibold uppercase tracking-[0.22em] text-primary">' + _t(kicker, 42) + '</p>\n'
            '            <h1 className="' + h1_class + '">' + _title(name) + '</h1>\n'
            '            <p className="mt-6 max-w-xl text-lg text-muted-foreground">' + lead + '</p>\n'
            '            <div className="mt-7 flex flex-wrap gap-3"><a href="/register" className="' + primary_cta + '">' + _t(main, 28) + '</a><a href="/login" className="' + secondary_cta + '">' + _t(secondary, 28) + '</a></div>\n'
            '          </div>\n'
            + panel +
            '        </div>\n'
            '      </section>\n'
        )
    if layout in ("stats-command", "schedule-first", "metrics-board"):
        return (
            f'      <section {data} className="{hero_class}">\n'
            '        <div className="mx-auto max-w-7xl px-6 py-14 lg:py-20">\n'
            '          <div className="mb-10 grid gap-3 md:grid-cols-3">\n' + _mini_metrics("overview", bp_page) + '          </div>\n'
            '          <div className="grid items-end gap-10 lg:grid-cols-[1fr_0.9fr]">\n'
            '            <div><p className="mb-4 text-sm font-semibold uppercase tracking-wider text-primary">' + _t(kicker, 42) + '</p><h1 className="' + h1_class + '">' + _title(name) + '</h1><p className="mt-5 max-w-xl text-lg text-muted-foreground">' + lead + '</p><div className="mt-7 flex flex-wrap gap-3"><a href="/register" className="' + primary_cta + '">' + _t(main, 28) + '</a><a href="/login" className="' + secondary_cta + '">' + _t(secondary, 28) + '</a></div></div>\n'
            + panel +
            '          </div>\n'
            '        </div>\n'
            '      </section>\n'
        )
    if layout in ("menu-reservation", "travel-search", "property-search", "search-led", "split-search"):
        search_label = "Search availability"
        if bp_page.get("visual_family") == "restaurant-reservation":
            search_label = "Find a table"
        elif bp_page.get("visual_family") == "travel-destination":
            search_label = "Find a trip"
        elif bp_page.get("visual_family") == "real-estate-listings":
            search_label = "Find a property"
        elif bp_page.get("visual_family") == "fitness-coaching":
            search_label = "Find a class"
        return (
            f'      <section {data} className="{hero_class}">\n'
            '        <div className="mx-auto grid max-w-7xl items-center gap-8 px-6 py-16 lg:grid-cols-[1.02fr_0.98fr] lg:py-20">\n'
            '          <div>\n'
            '            <p className="mb-4 inline-flex rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-primary">' + _t(kicker, 42) + '</p>\n'
            '            <h1 className="' + h1_class + '">' + _title(name) + '</h1>\n'
            '            <p className="mt-5 max-w-xl text-lg text-muted-foreground">' + lead + '</p>\n'
            '            <div className="mt-8 grid gap-3 rounded-3xl border bg-white/85 p-3 shadow-lg backdrop-blur md:grid-cols-[1fr_1fr_auto]">\n'
            '              <input placeholder="' + _t(search_label, 28) + '" className="rounded-2xl border bg-background px-4 py-3 text-sm" />\n'
            '              <input placeholder="Date, category, or location" className="rounded-2xl border bg-background px-4 py-3 text-sm" />\n'
            '              <a href="/register" className="' + primary_cta + ' text-center">' + _t(main, 28) + '</a>\n'
            '            </div>\n'
            '          </div>\n'
            + panel +
            '        </div>\n'
            '      </section>\n'
        )
    return (
        f'      <section {data} className="{hero_class}">\n'
        '        <div className="mx-auto grid max-w-7xl gap-8 px-6 py-16 lg:grid-cols-[1fr_1fr] lg:py-20">\n'
        '          <div>\n'
        '            <p className="mb-4 inline-flex rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-primary">' + _t(kicker, 42) + '</p>\n'
        '            <h1 className="' + h1_class + '">' + _title(name) + '</h1>\n'
        '            <p className="mt-5 max-w-xl text-lg text-muted-foreground">' + lead + '</p>\n'
        '            <div className="mt-7 flex flex-wrap gap-3"><a href="/register" className="' + primary_cta + '">' + _t(main, 28) + '</a><a href="/login" className="' + secondary_cta + '">' + _t(secondary, 28) + '</a></div>\n'
        '          </div>\n'
        + panel +
        '        </div>\n'
        '      </section>\n'
    )


def _premium_stat_strip(bp_page):
    stats = list(_premium_preset(bp_page).get("trust_stats") or _route_metrics(bp_page.get("page_type", "overview")))
    html = ""
    for i, (num, label) in enumerate(stats[:3]):
        html += (
            '              <div data-card-treatment="' + _t(_card_treatment(bp_page, i), 40) + '" className="' + _section_card_class(bp_page, i, "stat-card") + '">\n'
            '                <p className="font-display text-3xl font-bold text-primary md:text-4xl">' + _t(num, 14) + '</p>\n'
            '                <p className="mt-1 text-sm font-medium text-muted-foreground">' + _t(label, 34) + '</p>\n'
            '              </div>\n'
        )
    return html


def _premium_healthcare_visual_panel(bp_page, title="Care command"):
    preset = _premium_preset(bp_page)
    image_asset = _image_asset_for_role("hero", bp_page)
    image = _img(image_asset, "h-[25rem] md:h-[34rem]", preset.get("image_class", ""), alt="Hospital care team and patient support", role="hero")
    card0 = _section_card_class(bp_page, 0, "shadow")
    card1 = _section_card_class(bp_page, 1, "stat-card")
    card2 = _section_card_class(bp_page, 2, "bordered")
    return (
        '          <div data-art-component="premium-image-panel-hero" className="relative min-h-[34rem]">\n'
        '            <div className="absolute -right-4 top-8 h-44 w-44 rounded-full bg-sky-200/40 blur-3xl" />\n'
        '            <div className="relative">\n'
        '              ' + image + '\n'
        '              <div data-card-treatment="' + _t(_card_treatment(bp_page, 0), 40) + '" className="' + card0 + ' absolute -bottom-8 left-6 right-6 md:left-10 md:right-10">\n'
        '                <p className="text-xs font-bold uppercase tracking-[0.22em] text-primary">Emergency ready</p>\n'
        '                <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">\n'
        '                  <div><h3 className="font-display text-2xl font-bold">' + _t(title, 44) + '</h3><p className="mt-2 text-sm text-muted-foreground">Triage, booking, reports, and portal handoff stay visible from the first screen.</p></div>\n'
        '                  <span className="rounded-full bg-rose-100 px-4 py-2 text-sm font-bold text-rose-700">24/7 contact</span>\n'
        '                </div>\n'
        '              </div>\n'
        '            </div>\n'
        '            <div className="absolute left-8 top-10 hidden w-64 rounded-3xl border border-white/80 bg-white/85 p-4 shadow-xl shadow-slate-200/70 backdrop-blur md:block">\n'
        '              <p className="text-xs font-bold uppercase tracking-[0.22em] text-primary">Care timeline</p>\n'
        '              <div className="mt-4 space-y-3 text-sm"><div className="flex items-center justify-between"><span>Appointment</span><span className="font-bold text-primary">09:30</span></div><div className="flex items-center justify-between"><span>Lab report</span><span className="font-bold text-primary">Ready</span></div><div className="flex items-center justify-between"><span>Portal note</span><span className="font-bold text-primary">Sent</span></div></div>\n'
        '            </div>\n'
        '            <div className="absolute right-0 top-6 hidden w-56 grid-cols-1 gap-3 lg:grid">\n'
        '              <div data-card-treatment="' + _t(_card_treatment(bp_page, 1), 40) + '" className="' + card1 + '"><p className="text-xs font-bold uppercase tracking-wider text-primary">Doctor search</p><p className="mt-2 text-sm text-muted-foreground">Specialty, availability, location</p></div>\n'
        '              <div data-card-treatment="' + _t(_card_treatment(bp_page, 2), 40) + '" className="' + card2 + '"><p className="text-xs font-bold uppercase tracking-wider text-primary">Patient portal</p><p className="mt-2 text-sm text-muted-foreground">Visits, lab reports, billing</p></div>\n'
        '            </div>\n'
        '          </div>\n'
    )


def _route_premium_healthcare_hero(bp_page, app_name, bp, idx, data):
    page_type = bp_page["page_type"]
    name = bp_page["name"]
    headline = f"{app_name} hospital care" if page_type == "overview" and str(name).strip().lower() in ("home", "homepage") else name
    kicker = _route_kicker(bp, app_name)
    main = bp_page["main_cta"]
    secondary = bp_page["secondary_cta"]
    hero_class = _route_hero_class(bp_page)
    h1_class = _route_h1_class(bp_page)
    preset = _premium_preset(bp_page)
    lead_class = preset.get("lead_class") or "mt-6 max-w-2xl text-xl leading-8 text-muted-foreground"
    primary_cta = _primary_cta_class(bp_page)
    secondary_cta = _secondary_cta_class(bp_page)
    if page_type == "overview":
        return (
            f'      <section {data} data-art-director="true" data-premium-preset="{_t(bp_page.get("premium_preset_id", ""), 80)}" className="{hero_class}">\n'
            '        <div className="mx-auto grid min-h-[720px] max-w-7xl items-center gap-12 px-6 py-16 lg:grid-cols-[0.95fr_1.05fr] lg:py-20">\n'
            '          <div>\n'
            '            <p className="mb-5 inline-flex rounded-full border border-sky-200 bg-white/80 px-4 py-2 text-xs font-bold uppercase tracking-[0.22em] text-primary shadow-sm">' + _t(kicker, 44) + '</p>\n'
            '            <h1 className="' + h1_class + '">' + _title(headline) + '</h1>\n'
            '            <p className="' + lead_class + '">' + _t(f"{app_name} gives patients a calmer way to book care, find doctors, reach emergency help, and return to records without losing context.", 260) + '</p>\n'
            '            <div data-premium-cta="true" className="mt-9 flex flex-wrap gap-4">\n'
            '              <a href="/register" className="' + primary_cta + '">' + _t(main, 32) + '</a>\n'
            '              <a href="/login" className="' + secondary_cta + '">' + _t(secondary, 32) + '</a>\n'
            '            </div>\n'
            '            <div data-art-component="trust-stat-strip" className="mt-10 grid gap-4 sm:grid-cols-3">\n' + _premium_stat_strip(bp_page) + '            </div>\n'
            '          </div>\n'
            + _premium_healthcare_visual_panel(bp_page, "Care path live") +
            '        </div>\n'
            '      </section>\n'
        )
    if page_type == "services":
        return (
            f'      <section {data} data-art-director="true" data-premium-preset="{_t(bp_page.get("premium_preset_id", ""), 80)}" className="{hero_class}">\n'
            '        <div className="mx-auto grid max-w-7xl gap-10 px-6 py-16 lg:grid-cols-[0.9fr_1.1fr] lg:py-24">\n'
            '          <div><p className="text-sm font-bold uppercase tracking-[0.22em] text-primary">' + _t(kicker, 42) + '</p><h1 className="mt-4 ' + h1_class + '">' + _title(name) + '</h1><p className="' + lead_class + '">A service landing page for patients: care catalog, booking flow, lab reports, insurance, billing, and portal access.</p><div data-premium-cta="true" className="mt-8 flex flex-wrap gap-3"><a href="/register" className="' + primary_cta + '">' + _t(main, 32) + '</a><a href="/login" className="' + secondary_cta + '">' + _t(secondary, 32) + '</a></div></div>\n'
            '          <div data-art-component="service-catalog-grid" className="grid gap-4 sm:grid-cols-2">\n'
            '            <div data-card-treatment="' + _t(_card_treatment(bp_page, 0), 40) + '" className="' + _section_card_class(bp_page, 0) + '"><h3 className="font-display text-xl font-bold">Consultations</h3><p className="mt-2 text-sm text-muted-foreground">Find specialists and available clinics.</p></div>\n'
            '            <div data-card-treatment="' + _t(_card_treatment(bp_page, 1), 40) + '" className="' + _section_card_class(bp_page, 1) + '"><h3 className="font-display text-xl font-bold">Diagnostics</h3><p className="mt-2 text-sm text-muted-foreground">Lab reports and imaging requests.</p></div>\n'
            '            <div data-card-treatment="' + _t(_card_treatment(bp_page, 2), 40) + '" className="' + _section_card_class(bp_page, 2) + '"><h3 className="font-display text-xl font-bold">Payments</h3><p className="mt-2 text-sm text-muted-foreground">Insurance, invoices, and deposits.</p></div>\n'
            '            <div data-card-treatment="' + _t(_card_treatment(bp_page, 3), 40) + '" className="' + _section_card_class(bp_page, 3) + '"><h3 className="font-display text-xl font-bold">Portal</h3><p className="mt-2 text-sm text-muted-foreground">Appointments, messages, and records.</p></div>\n'
            '          </div>\n'
            '        </div>\n'
            '      </section>\n'
        )
    if page_type == "management":
        return (
            f'      <section {data} data-art-director="true" data-premium-preset="{_t(bp_page.get("premium_preset_id", ""), 80)}" className="{hero_class}">\n'
            '        <div className="mx-auto max-w-7xl px-6 py-16 lg:py-24">\n'
            '          <div className="grid gap-8 lg:grid-cols-[0.8fr_1.2fr] lg:items-end"><div><p className="text-sm font-bold uppercase tracking-[0.22em] text-primary">' + _t(kicker, 42) + '</p><h1 className="mt-4 ' + h1_class + '">' + _title(name) + '</h1><p className="' + lead_class + '">Operations software for rooms, beds, queues, staff schedules, and analytics before pressure spreads.</p></div><div data-premium-cta="true" className="flex flex-wrap gap-3 lg:justify-end"><a href="/register" className="' + primary_cta + '">' + _t(main, 36) + '</a><a href="/login" className="' + secondary_cta + '">' + _t(secondary, 36) + '</a></div></div>\n'
            '          <div data-art-component="dashboard-preview-card" className="mt-10 grid gap-4 md:grid-cols-4">\n' + _premium_stat_strip(bp_page) +
            '            <div data-card-treatment="' + _t(_card_treatment(bp_page, 3), 40) + '" className="' + _section_card_class(bp_page, 3) + ' md:col-span-4"><p className="text-xs font-bold uppercase tracking-[0.22em] text-primary">Operations board</p><div className="mt-5 grid gap-3 md:grid-cols-4"><span className="rounded-2xl bg-primary/10 px-4 py-3 text-sm font-semibold text-primary">Rooms</span><span className="rounded-2xl bg-primary/10 px-4 py-3 text-sm font-semibold text-primary">Staff</span><span className="rounded-2xl bg-primary/10 px-4 py-3 text-sm font-semibold text-primary">Resources</span><span className="rounded-2xl bg-primary/10 px-4 py-3 text-sm font-semibold text-primary">Reports</span></div></div>\n'
            '          </div>\n'
            '        </div>\n'
            '      </section>\n'
        )
    if page_type == "compliance":
        return (
            f'      <section {data} data-art-director="true" data-premium-preset="{_t(bp_page.get("premium_preset_id", ""), 80)}" className="{hero_class}">\n'
            '        <div className="mx-auto grid max-w-7xl gap-10 px-6 py-16 lg:grid-cols-[0.95fr_1.05fr] lg:py-24">\n'
            '          <div><p className="text-sm font-bold uppercase tracking-[0.22em] text-primary">' + _t(kicker, 42) + '</p><h1 className="mt-4 ' + h1_class + '">' + _title(name) + '</h1><p className="' + lead_class + '">A security page for privacy, role controls, audit logs, encryption, backup, and compliance workflows.</p><div data-premium-cta="true" className="mt-8 flex flex-wrap gap-3"><a href="/register" className="' + primary_cta + '">' + _t(main, 36) + '</a><a href="/login" className="' + secondary_cta + '">' + _t(secondary, 36) + '</a></div></div>\n'
            '          <div data-art-component="clinical-bento-grid" className="grid gap-4 sm:grid-cols-2">\n'
            '            <div data-card-treatment="' + _t(_card_treatment(bp_page, 0), 40) + '" className="' + _section_card_class(bp_page, 0) + ' sm:col-span-2"><p className="text-xs font-bold uppercase tracking-[0.22em] text-primary">Protected health data</p><h3 className="mt-3 font-display text-3xl font-bold">Access is role-gated by default</h3></div>\n'
            '            <div data-card-treatment="' + _t(_card_treatment(bp_page, 1), 40) + '" className="' + _section_card_class(bp_page, 1) + '"><h3 className="font-display text-xl font-bold">Audit logs</h3><p className="mt-2 text-sm text-muted-foreground">Sensitive events are traceable.</p></div>\n'
            '            <div data-card-treatment="' + _t(_card_treatment(bp_page, 2), 40) + '" className="' + _section_card_class(bp_page, 2) + '"><h3 className="font-display text-xl font-bold">Encryption</h3><p className="mt-2 text-sm text-muted-foreground">Backup and protection stay visible.</p></div>\n'
            '          </div>\n'
            '        </div>\n'
            '      </section>\n'
        )
    return ""


def _route_hero(bp_page, app_name, bp, idx):
    name = bp_page["name"]
    page_type = bp_page["page_type"]
    kicker = _route_kicker(bp, app_name)
    purpose = bp_page["purpose"]
    main = bp_page["main_cta"]
    secondary = bp_page["secondary_cta"]
    first = bp_page["first_screen"]
    card_style = bp_page["card_style"]
    hero_variant = bp_page["hero_variant"]
    asset = _HERO_IMG[idx % len(_HERO_IMG)]
    data = (
        f'data-page-section="{_t(bp_page["sections"][0], 60)}" '
        f'data-page-purpose="{_t(purpose, 90)}" '
        f'data-page-audience="{_t(bp_page["audience"], 90)}" '
        f'data-page-first-screen="{_t(first, 140)}" '
        f'data-page-hero-variant="{_t(hero_variant, 60)}" '
        f'data-inspiration-family="{_t(bp_page.get("inspiration_family", ""), 60)}" '
        f'data-visual-family="{_t(bp_page.get("visual_family", ""), 60)}" '
        f'data-dna-family="{_t(bp_page.get("primary_dna_family", ""), 60)}" '
        f'data-dna-hero-pattern="{_t((bp_page.get("hero_patterns") or [""])[0], 80)}" '
        f'data-hero-recipe="{_t((_recipe(bp_page, "hero").get("id") or ""), 80)}" '
        f'data-nav-recipe="{_t((_recipe(bp_page, "nav").get("id") or ""), 80)}" '
        f'data-card-recipe="{_t((_recipe(bp_page, "card").get("id") or ""), 80)}"'
    )
    hero_class = _route_hero_class(bp_page)
    h1_class = _route_h1_class(bp_page)
    primary_cta = _primary_cta_class(bp_page)
    secondary_cta = _secondary_cta_class(bp_page)
    chip_class = _route_chip_class(bp_page)
    if _art_director_enabled(bp_page) and bp_page.get("visual_family") == "healthcare-clinical":
        premium = _route_premium_healthcare_hero(bp_page, app_name, bp, idx, data)
        if premium:
            return premium
    if page_type == "overview" and bp_page.get("hero_recipe"):
        return _route_recipe_overview_hero(bp_page, app_name, bp, idx, data)
    if page_type == "overview":
        family = bp_page.get("inspiration_family", "")
        if family and family != "healthcare-trust-saas":
            first_sections = list(bp_page.get("sections") or [])[:3]
            cards = ""
            for sid in first_sections[:2]:
                st, sd, items = _SECTION_COPY.get(sid, _SECTION_COPY["service-catalog"])
                chips = "".join('<span className="' + chip_class + '">' + _t(x, 22) + '</span>' for x in items[:4])
                cards += (
                    '            <div className="' + _route_card_class(bp_page, card_style) + '">\n'
                    '              <p className="text-xs font-semibold uppercase tracking-wider text-primary">' + _t(st, 34) + '</p>\n'
                    '              <p className="mt-2 text-sm text-muted-foreground">' + _t(sd, 140) + '</p>\n'
                    '              <div className="mt-4 grid grid-cols-2 gap-2 text-sm">' + chips + '</div>\n'
                    '            </div>\n'
                )
            metrics = {
                "ecommerce-product": [("Live", "Inventory"), ("0-1", "Click inquiry"), ("24h", "Follow-up")],
                "ai-devtools": [("API", "Ready"), ("99ms", "Test run"), ("SOC2", "Controls")],
                "education-media": [("120+", "Lessons"), ("4", "Learning paths"), ("Live", "Progress")],
                "operational-business": [("42", "Open tasks"), ("12", "Alerts"), ("Live", "Ops board")],
                "creative-agency": [("12", "Case studies"), ("4", "Capabilities"), ("New", "Project brief")],
                "fintech-trust": [("99.9%", "Reliable"), ("24h", "Audit trail"), ("Live", "Cash view")],
            }.get(family, [("Live", "Ready"), ("Fast", "Workflow"), ("Secure", "Access")])
            metric_html = "".join(
                '              <div className="' + _route_card_class(bp_page, "stat-card") + '"><p className="font-display text-2xl font-bold text-primary">' + _t(n, 12) + '</p><p className="text-xs text-muted-foreground">' + _t(l, 28) + '</p></div>\n'
                for n, l in metrics
            )
            return (
                f'      <section {data} className="{hero_class}">\n'
                '        <div className="mx-auto grid max-w-6xl gap-8 px-6 py-16 lg:grid-cols-[1fr_1fr] lg:py-20">\n'
                '          <div>\n'
                '            <p className="mb-4 inline-flex rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-primary">' + _t(kicker, 42) + '</p>\n'
                '            <h1 className="' + h1_class + '">' + _title(name) + '</h1>\n'
                '            <p className="mt-5 max-w-xl text-lg text-muted-foreground">' + _t(bp_page["purpose"].capitalize() + " for " + bp_page["audience"] + ".", 240) + '</p>\n'
                '            <div className="mt-7 flex flex-wrap gap-3">\n'
                '              <a href="/register" className="' + primary_cta + '">' + _t(main, 28) + '</a>\n'
                '              <a href="/login" className="' + secondary_cta + '">' + _t(secondary, 28) + '</a>\n'
                '            </div>\n'
                '            <div className="mt-8 grid gap-3 sm:grid-cols-3">\n' + metric_html + '            </div>\n'
                '          </div>\n'
                '          <div className="grid gap-4">\n' + cards + '          </div>\n'
                '        </div>\n'
                '      </section>\n'
            )
        return (
            f'      <section {data} className="{hero_class}">\n'
            '        <div className="mx-auto grid max-w-6xl gap-8 px-6 py-16 lg:grid-cols-[1.05fr_0.95fr] lg:py-20">\n'
            '          <div>\n'
            '            <p className="mb-4 inline-flex rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-primary">' + _t(kicker, 42) + '</p>\n'
            '            <h1 className="' + h1_class + '">' + _title(name) + '</h1>\n'
            '            <p className="mt-5 max-w-xl text-lg text-muted-foreground">' + _t(f"{app_name} gives patients a clear way to book care, find doctors, reach emergency help, and return to their portal.", 240) + '</p>\n'
            '            <div className="mt-7 flex flex-wrap gap-3">\n'
            '              <a href="/register" className="' + primary_cta + '">' + _t(main, 28) + '</a>\n'
            '              <a href="/login" className="' + secondary_cta + '">' + _t(secondary, 28) + '</a>\n'
            '            </div>\n'
            '            <div className="mt-8 grid gap-3 sm:grid-cols-3">\n' + _mini_metrics(page_type, bp_page) + '            </div>\n'
            '          </div>\n'
            '          <div className="grid gap-4">\n'
            '            <div className="' + _route_card_class(bp_page, "shadow") + '"><p className="text-xs font-semibold uppercase tracking-wider text-primary">Emergency</p><h3 className="mt-2 font-display text-2xl font-bold">Call, triage, route</h3><p className="mt-2 text-sm text-muted-foreground">Emergency contact stays visible before patients choose any workflow.</p></div>\n'
            '            <div className="' + _route_card_class(bp_page, card_style) + '"><p className="text-xs font-semibold uppercase tracking-wider text-primary">Doctor search</p><div className="mt-3 grid grid-cols-2 gap-2 text-sm"><span className="' + chip_class + '">Specialty</span><span className="' + chip_class + '">Availability</span><span className="' + chip_class + '">Location</span><span className="' + chip_class + '">Language</span></div></div>\n'
            '          </div>\n'
            '        </div>\n'
            '      </section>\n'
        )
    if page_type == "services":
        return (
            f'      <section {data} className="{hero_class}">\n'
            '        <div className="mx-auto max-w-6xl px-6 py-16 md:py-20">\n'
            '          <div className="max-w-3xl"><p className="text-sm font-semibold uppercase tracking-wider text-primary">' + _t(kicker, 42) + '</p><h1 className="mt-3 ' + h1_class + '">' + _title(name) + '</h1><p className="mt-5 text-lg text-muted-foreground">Browse patient services, understand the booking path, and know exactly where reports, payments, and FAQs live.</p></div>\n'
            '          <div className="mt-10 grid gap-4 md:grid-cols-[1.2fr_0.8fr]">\n'
            '            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">\n'
            '              <div className="' + _route_card_class(bp_page, card_style) + '"><h3 className="font-display font-semibold">Consultations</h3><p className="mt-2 text-sm text-muted-foreground">Specialist and general care.</p></div>\n'
            '              <div className="' + _route_card_class(bp_page, card_style) + '"><h3 className="font-display font-semibold">Diagnostics</h3><p className="mt-2 text-sm text-muted-foreground">Lab and imaging requests.</p></div>\n'
            '              <div className="' + _route_card_class(bp_page, card_style) + '"><h3 className="font-display font-semibold">Follow-ups</h3><p className="mt-2 text-sm text-muted-foreground">Continuity after each visit.</p></div>\n'
            '            </div>\n'
            '            <div className="' + _route_card_class(bp_page, "stat-card") + '"><p className="text-sm font-semibold uppercase tracking-wider text-primary">Next step</p><h3 className="mt-2 font-display text-2xl font-bold">' + _t(main, 32) + '</h3><p className="mt-2 text-sm text-muted-foreground">Start with the service catalog, then move into booking and portal access.</p></div>\n'
            '          </div>\n'
            '        </div>\n'
            '      </section>\n'
        )
    if page_type == "portal":
        return (
            f'      <section {data} className="{hero_class}">\n'
            '        <div className="mx-auto grid max-w-6xl items-center gap-8 px-6 py-16 lg:grid-cols-[0.82fr_1.18fr] lg:py-20">\n'
            '          <div><p className="text-sm font-semibold uppercase tracking-wider text-primary">' + _t(kicker, 42) + '</p><h1 className="mt-3 ' + h1_class + '">' + _title(name) + '</h1><p className="mt-5 text-lg text-muted-foreground">A staff-first portal for schedules, queues, records, prescriptions, and lab orders.</p><a href="/login" className="mt-7 inline-flex ' + primary_cta + '">' + _t(main, 32) + '</a></div>\n'
            + _mock_dashboard("Provider workspace", [{"title": "Today's queue"}, {"title": "Critical lab result"}, {"title": "Unsigned note"}, {"title": "Prescription renewal"}], card_style).replace(_card_class(card_style), _route_card_class(bp_page, card_style), 1) +
            '        </div>\n'
            '      </section>\n'
        )
    if page_type == "management":
        return (
            f'      <section {data} className="{hero_class}">\n'
            '        <div className="mx-auto max-w-6xl px-6 py-16 md:py-20">\n'
            '          <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between"><div><p className="text-sm font-semibold uppercase tracking-wider text-primary">' + _t(kicker, 42) + '</p><h1 className="mt-3 ' + h1_class + '">' + _title(name) + '</h1></div><p className="max-w-md text-muted-foreground">Operations leaders see rooms, staff, queues, and reports before bottlenecks spread.</p></div>\n'
            '          <div className="mt-10 grid gap-4 md:grid-cols-4">\n' + _mini_metrics(page_type, bp_page) +
            '            <div className="' + _route_card_class(bp_page, card_style) + ' md:col-span-2"><p className="text-xs font-semibold uppercase tracking-wider text-primary">Control board</p><h3 className="mt-2 font-display text-xl font-bold">Beds, rooms, staff, reports</h3></div>\n'
            '          </div>\n'
            '        </div>\n'
            '      </section>\n'
        )
    if page_type == "compliance":
        return (
            f'      <section {data} className="{hero_class}">\n'
            '        <div className="mx-auto grid max-w-6xl gap-8 px-6 py-16 lg:grid-cols-[1fr_1fr] lg:py-20">\n'
            '          <div><p className="text-sm font-semibold uppercase tracking-wider text-primary">' + _t(kicker, 42) + '</p><h1 className="mt-3 ' + h1_class + '">' + _title(name) + '</h1><p className="mt-5 text-lg text-muted-foreground">Privacy, access, audit, backup, and encryption controls are presented as operational workflows, not fine print.</p></div>\n'
            '          <div className="grid gap-3">\n'
            '            <div className="' + _route_card_class(bp_page, "stat-card") + '"><p className="text-xs font-semibold uppercase tracking-wider text-primary">Protected health data</p><h3 className="mt-2 font-display text-2xl font-bold">Role gated by default</h3></div>\n'
            '            <div className="grid gap-3 sm:grid-cols-2"><div className="' + _route_card_class(bp_page, card_style) + '"><h3 className="font-display font-semibold">Audit trail</h3><p className="mt-2 text-sm text-muted-foreground">Every sensitive event is traceable.</p></div><div className="' + _route_card_class(bp_page, card_style) + '"><h3 className="font-display font-semibold">Encryption</h3><p className="mt-2 text-sm text-muted-foreground">Data protection stays visible.</p></div></div>\n'
            '          </div>\n'
            '        </div>\n'
            '      </section>\n'
        )
    return _hero_visual(kicker, name, f"{purpose} for {bp_page['audience']}.", asset, {
        "hero_variant": "dashboard-preview" if page_type == "reports" else "search-booking",
        "card_style": card_style,
        "layout_rhythm": bp_page["rhythm"],
        "image_strategy": bp_page["image_strategy"],
        "cta_placement": "hero-primary",
        "first_screen_skeleton": first,
    }, [{"title": x} for x in _SECTION_COPY.get(bp_page["sections"][0], ("", "", []))[2]])


def _section_title(section_id):
    return _SECTION_COPY.get(section_id, (section_id.replace("-", " ").title(), "", []))[0]


def _route_grid_section(section_id, bp_page, columns="lg:grid-cols-3", pos=0):
    title, lead, items = _SECTION_COPY.get(section_id, _SECTION_COPY["service-catalog"])
    card_style = bp_page["card_style"]
    recipe = _section_recipe(bp_page, pos)
    grid_class = recipe.get("grid_class") or f"grid gap-5 sm:grid-cols-2 {columns}"
    art_component = _rich_component(bp_page, pos) or "catalog-grid"
    cards = ""
    for i, item in enumerate(items[:6]):
        treatment = _card_treatment(bp_page, pos + i)
        cards += (
            '          <div data-card-treatment="' + _t(treatment, 40) + '" className="' + _section_card_class(bp_page, pos + i, card_style) + '">\n'
            '            <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary"><CheckCircle2 className="h-5 w-5" /></div>\n'
            '            <h3 className="font-display text-lg font-semibold">' + _title(item) + '</h3>\n'
            '            <p className="mt-2 text-sm text-muted-foreground">' + _t(lead, 130) + '</p>\n'
            '          </div>\n'
        )
    return (
        f'      <section data-page-section="{_t(section_id, 64)}" data-section-variant="catalog-grid" data-art-component="{_t(art_component, 60)}" data-section-recipe="{_t(recipe.get("id", ""), 80)}" data-genome-card-style="{_t(card_style, 24)}" className="{_route_section_class(bp_page, pos)}">\n'
        f'        <div className="mx-auto max-w-6xl px-6 {_space(bp_page["rhythm"])}">\n'
        '        <div className="mb-8 max-w-2xl"><h2 className="font-display text-3xl font-bold">' + _title(title) + '</h2><p className="mt-3 text-muted-foreground">' + _t(lead, 220) + '</p></div>\n'
        f'        <div className="{grid_class}">\n' + cards + '        </div>\n'
        '        </div>\n'
        '      </section>\n'
    )


def _route_flow_section(section_id, bp_page, pos=0):
    title, lead, items = _SECTION_COPY.get(section_id, _SECTION_COPY["appointment-booking-flow"])
    recipe = _section_recipe(bp_page, pos)
    art_component = _rich_component(bp_page, pos) or "timeline-stepper"
    cells = ""
    for i, item in enumerate(items[:4], 1):
        treatment = _card_treatment(bp_page, pos + i)
        cells += (
            '          <div className="grid gap-4 md:grid-cols-[80px_1fr]">\n'
            '            <div className="font-display text-3xl font-bold text-primary">0' + str(i) + '</div>\n'
            '            <div data-card-treatment="' + _t(treatment, 40) + '" className="' + _section_card_class(bp_page, pos + i) + '"><h3 className="font-display text-lg font-semibold">' + _title(item) + '</h3><p className="mt-2 text-sm text-muted-foreground">' + _t(lead, 150) + '</p></div>\n'
            '          </div>\n'
        )
    return (
        f'      <section data-page-section="{_t(section_id, 64)}" data-section-variant="workflow-timeline" data-art-component="{_t(art_component, 60)}" data-section-recipe="{_t(recipe.get("id", ""), 80)}" className="{_route_section_class(bp_page, pos)}">\n'
        f'        <div className="mx-auto max-w-6xl px-6 {_space(bp_page["rhythm"])}">\n'
        '          <div className="mb-8 max-w-2xl"><h2 className="font-display text-3xl font-bold">' + _title(title) + '</h2><p className="mt-3 text-muted-foreground">' + _t(lead, 220) + '</p></div>\n'
        '          <div className="space-y-5">\n' + cells + '          </div>\n'
        '        </div>\n'
        '      </section>\n'
    )


def _route_preview_section(section_id, bp_page, asset="feature1.jpg", flip=False, pos=0):
    title, lead, items = _SECTION_COPY.get(section_id, _SECTION_COPY["patient-portal-preview"])
    recipe = _section_recipe(bp_page, pos)
    art_component = _rich_component(bp_page, pos) or "dashboard-preview-card"
    role = _image_role_for_section(section_id, bp_page)
    if _art_director_enabled(bp_page):
        asset = _image_asset_for_role(role, bp_page)
    labels = [{"title": x} for x in items]
    dashboard = _mock_dashboard(title, labels, bp_page["card_style"]).replace(
        _card_class(bp_page["card_style"]), _route_card_class(bp_page), 1)
    if _image_ok(bp_page["image_strategy"]):
        visual = (
            '          <div className="grid gap-4">\n'
            '            ' + _img(asset, "h-56 md:h-72", (_premium_preset(bp_page).get("image_class", "") if _art_director_enabled(bp_page) else ""), alt=title, role=role) + '\n'
            + dashboard.replace('          ', '            ', 1) +
            '          </div>\n'
        )
    else:
        visual = dashboard
    text = (
        '          <div>\n'
        '            <p className="text-sm font-semibold uppercase tracking-wider text-primary">' + _t(bp_page["purpose"], 42) + '</p>\n'
        '            <h2 className="mt-3 font-display text-3xl font-bold">' + _title(title) + '</h2>\n'
        '            <p className="mt-4 text-muted-foreground">' + _t(lead, 260) + '</p>\n'
        '          </div>\n'
    )
    inner = (text + visual) if flip else (visual + text)
    return (
        f'      <section data-page-section="{_t(section_id, 64)}" data-section-variant="dashboard-preview" data-art-component="{_t(art_component, 60)}" data-section-recipe="{_t(recipe.get("id", ""), 80)}" className="{_route_section_class(bp_page, pos)}">\n'
        f'        <div className="mx-auto grid max-w-6xl items-center gap-10 px-6 {_space(bp_page["rhythm"])} lg:grid-cols-2">\n'
        + inner +
        '        </div>\n'
        '      </section>\n'
    )


def _route_faq_section(section_id, bp_page, pos=0):
    title, lead, items = _SECTION_COPY.get(section_id, _SECTION_COPY["patient-faq"])
    recipe = _section_recipe(bp_page, pos)
    art_component = _rich_component(bp_page, pos) or "faq-accordion"
    rows = ""
    for i, item in enumerate(items[:4]):
        rows += (
            '          <div data-card-treatment="' + _t(_card_treatment(bp_page, pos + i), 40) + '" className="' + _section_card_class(bp_page, pos + i) + '">\n'
            '            <h3 className="font-display text-base font-semibold">' + _title(item) + '</h3>\n'
            '            <p className="mt-2 text-sm text-muted-foreground">' + _t(lead, 180) + '</p>\n'
            '          </div>\n'
        )
    return (
        f'      <section data-page-section="{_t(section_id, 64)}" data-section-variant="page-faq" data-art-component="{_t(art_component, 60)}" data-section-recipe="{_t(recipe.get("id", ""), 80)}" className="{_route_section_class(bp_page, pos)}">\n'
        f'        <div className="mx-auto max-w-4xl px-6 {_space("compact")}">\n'
        '        <h2 className="mb-3 font-display text-3xl font-bold">' + _title(title) + '</h2>\n'
        '        <p className="mb-8 text-muted-foreground">' + _t(lead, 220) + '</p>\n'
        '        <div className="space-y-4">\n' + rows + '        </div>\n'
        '        </div>\n'
        '      </section>\n'
    )


def _route_cta_section(section_id, bp_page, app_name, pos=0):
    title, lead, items = (_SECTION_COPY.get(section_id) or _SECTION_COPY.get(bp_page["sections"][-1])
                          or ("Ready to get started?", f"Take the next step with {app_name}.", []))
    recipe = _section_recipe(bp_page, pos)
    art_component = _rich_component(bp_page, pos) or "premium-cta-band"
    return (
        f'      <section data-page-section="{_t(section_id, 64)}" data-section-variant="purpose-cta" data-art-component="{_t(art_component, 60)}" data-section-recipe="{_t(recipe.get("id", ""), 80)}" data-page-cta="{_t(bp_page["main_cta"], 36)}" className="{_route_section_class(bp_page, pos)}">\n'
        '        <div className="mx-auto max-w-6xl px-6 pb-24 pt-4">\n'
        '        <div data-card-treatment="' + _t(_card_treatment(bp_page, pos), 40) + '" className="grid gap-6 ' + _section_card_class(bp_page, pos, "shadow") + ' md:grid-cols-[1fr_auto] md:items-center">\n'
        '          <div><p className="text-sm font-semibold uppercase tracking-wider text-primary">' + _t(title, 42) + '</p><h2 className="mt-2 font-display text-3xl font-bold">' + _t(app_name, 40) + ' keeps this workflow connected.</h2><p className="mt-3 max-w-2xl text-muted-foreground">' + _t(lead, 240) + '</p></div>\n'
        '          <a href="/register" data-premium-cta="true" className="' + _primary_cta_class(bp_page) + ' text-center">' + _t(bp_page["main_cta"], 36) + '</a>\n'
        '        </div>\n'
        '        </div>\n'
        '      </section>\n'
    )


def _route_footer(bp_page, app_name):
    style = _family_style(bp_page)
    family = bp_page.get("visual_family") or bp_page.get("inspiration_family", "")
    footer_recipe = _recipe(bp_page, "footer")
    links = {
        "healthcare-trust-saas": ["Emergency", "Appointments", "Patient portal", "Compliance"],
        "healthcare-clinical": ["Emergency", "Appointments", "Patient portal", "Compliance"],
        "ecommerce-product": ["Inventory", "Financing", "Trade-in", "Test drive"],
        "automotive-showroom": ["Inventory", "Financing", "Trade-in", "Test drive"],
        "product-commerce": ["Catalog", "Compare", "Support", "Checkout"],
        "ai-devtools": ["Docs", "API status", "Changelog", "Security"],
        "developer-console": ["Docs", "API status", "Changelog", "Security"],
        "education-media": ["Courses", "Learning paths", "Instructors", "Resources"],
        "learning-editorial": ["Courses", "Learning paths", "Instructors", "Resources"],
        "restaurant-reservation": ["Menu", "Reservations", "Hours", "Location"],
        "travel-destination": ["Destinations", "Itineraries", "Packages", "Guides"],
        "real-estate-listings": ["Listings", "Tours", "Agents", "Neighborhoods"],
        "fitness-coaching": ["Programs", "Trainers", "Schedule", "Plans"],
        "fintech-trust": ["Security", "Pricing", "Transactions", "Support"],
        "finance-trust": ["Security", "Pricing", "Transactions", "Support"],
        "creative-agency": ["Work", "Services", "Studio", "Contact"],
        "creative-portfolio": ["Work", "Services", "Studio", "Contact"],
        "operational-business": ["Dashboard", "Workflows", "Reports", "Support"],
        "operations-console": ["Dashboard", "Workflows", "Reports", "Support"],
    }.get(family, ["Overview", "Features", "Support", "Contact"])
    link_html = "".join('<span className="text-sm">' + _t(x, 24) + '</span>\n' for x in links)
    return (
        f'      <footer data-component-id="footer" data-footer-style="{_t(bp_page.get("footer_style", ""), 60)}" data-footer-recipe="{_t(footer_recipe.get("id", ""), 80)}" data-visual-family="{_t(family, 60)}" data-inspiration-family="{_t(bp_page.get("inspiration_family", ""), 60)}" className="{footer_recipe.get("className") or style["footer"]}">\n'
        '        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-6 py-10 md:flex-row md:items-center md:justify-between">\n'
        '          <div><p className="font-display text-lg font-bold">' + _t(app_name, 42) + '</p><p className="mt-2 max-w-md text-sm opacity-75">' + _t(bp_page["purpose"].capitalize() + " for " + bp_page["audience"] + ".", 160) + '</p></div>\n'
        '          <div className="flex flex-wrap gap-4 opacity-80">\n' + link_html + '          </div>\n'
        '        </div>\n'
        '      </footer>\n'
    )


def _route_section(section_id, bp_page, app_name, pos):
    if pos == 0 and section_id in ("emergency-contact", "security-hero"):
        return _route_grid_section(section_id, bp_page, columns="lg:grid-cols-3", pos=pos)
    if any(x in section_id for x in ("flow", "workflow", "queue", "scheduling", "logs", "controls", "builder", "schedule")):
        return _route_flow_section(section_id, bp_page, pos=pos)
    if any(x in section_id for x in ("preview", "portal", "dashboard", "reports", "analytics", "lab-report", "resource", "backup")):
        return _route_preview_section(section_id, bp_page, flip=(pos % 2 == 1), pos=pos)
    if "faq" in section_id:
        return _route_faq_section(section_id, bp_page, pos=pos)
    if "cta" in section_id or section_id in ("confirmation-cta", "provider-login-cta"):
        return _route_cta_section(section_id, bp_page, app_name, pos=pos)
    if any(x in section_id for x in ("grid", "catalog", "departments", "clinics", "standards", "team", "quality", "impact", "story", "payment")):
        return _route_grid_section(section_id, bp_page, columns="lg:grid-cols-3", pos=pos)
    return _route_grid_section(section_id, bp_page, pos=pos)


def _professional_blocks_enabled(visual):
    """Professional block assembly is ON by default. Per-call override via
    visual['professional_blocks']; global override via env
    AI_DESIGNER_PROFESSIONAL_BLOCKS=0."""
    import os
    if isinstance(visual, dict) and "professional_blocks" in visual:
        return bool(visual.get("professional_blocks"))
    return os.getenv("AI_DESIGNER_PROFESSIONAL_BLOCKS", "1").strip().lower() not in ("0", "false", "no", "")


def _assemble_full_page(root_open, body):
    return (
        "import { CheckCircle2 } from 'lucide-react';\n\n"
        "export default function Page() {\n"
        "  return (\n"
        + root_open + body +
        "    </div>\n"
        "  );\n}\n"
    )


def _maybe_professional_body(bp, app_name, visual, bp_page, root_open, legacy_body):
    """Assemble the page body from selected PROFESSIONAL block IDs.

    Falls back to the legacy route-section body if professional blocks are
    disabled, the selector/assembler errors, too few sections render, or the
    assembled page would not pass the design quality gate. Each professional
    section preserves its legacy `data-page-section` identity marker, so the
    page's section taxonomy (and the uniqueness regression) is unchanged.
    """
    if not _professional_blocks_enabled(visual):
        return legacy_body
    from app import page_block_selector as pbs, page_assembler as pasm, design_quality
    prompt = " ".join([str(bp.get("domain", "")), str(bp_page.get("purpose", "")),
                       str(bp_page.get("name", ""))]).strip()
    genome_like = {
        "visual_family": bp_page.get("visual_family", ""),
        "inspiration_family": bp_page.get("inspiration_family", ""),
        "app_seed": "".join(bp_page.get("dna_profile_ids") or [])
        or str(bp_page.get("browser_visible_signature", ""))[:48],
        "dna_profile_ids": list(bp_page.get("dna_profile_ids") or []),
        "hero_recipe": dict(bp_page.get("hero_recipe") or {}),
        "card_style": bp_page.get("card_style", ""),
        # Propagate cross-page exclusion list so sub-pages don't repeat home sections.
        "exclude_families": list(bp_page.get("exclude_families") or []),
    }
    selection = pbs.select_blocks_for_page(prompt, bp_page, genome_like, use_llm=False)
    result = pasm.assemble_marketing_body(selection, bp_page, app_name)
    if not result.get("ok"):
        return legacy_body
    candidate = _assemble_full_page(root_open, result["body"])
    gate = design_quality.quality_gate(candidate, {"image_reuse_limit": bp_page.get("image_reuse_limit", 2)})
    return result["body"] if gate.get("ok") else legacy_body


def _route_section_markers(bp, bp_page):
    """Part 5B: replace healthcare-default markers with domain+intent-specific
    markers for non-healthcare routes, so generated pages never inherit healthcare
    identities. Healthcare keeps its curated markers. Returns the marker list or
    None to leave bp_page['sections'] unchanged."""
    try:
        from app import route_block_rules as _rbr, page_block_selector as _pbs
        prompt = " ".join([str(bp.get("domain", "")), str(bp_page.get("purpose", "")), str(bp_page.get("name", ""))])
        genome_like = {"visual_family": bp_page.get("visual_family", ""),
                       "inspiration_family": bp_page.get("inspiration_family", "")}
        domain = _pbs.resolve_family_and_domain(prompt, genome_like)[1]
        if domain == "healthcare":
            return None
        intent = _rbr.detect_page_intent(domain=domain, slug=bp_page.get("slug", ""),
                                         title=bp_page.get("name", ""), prompt=str(bp.get("domain", "")),
                                         blueprint=bp_page)
        if intent == "homepage":   # home already uses a domain-specific blueprint
            return None
        slots = _rbr.route_blueprint(domain, intent)
        return [s["marker"] for s in slots] if slots else None
    except Exception:
        return None


def _compose_route_blueprint_page(page, bp, idx, app_name, visual):
    bp_page = _route_blueprint(page, bp, idx, visual)
    # Thread cross-page exclusion list into bp_page so _maybe_professional_body
    # can forward it to the block selector via genome_like.
    if visual.get("exclude_families"):
        bp_page["exclude_families"] = list(visual["exclude_families"])
    _markers = _route_section_markers(bp, bp_page)
    if _markers:
        bp_page["sections"] = _markers
    hero = _route_hero(bp_page, app_name, bp, idx)
    sections = "".join(_route_section(s, bp_page, app_name, i + 1) for i, s in enumerate(bp_page["sections"][1:]))
    footer = _route_footer(bp_page, app_name)
    section_names = ",".join(bp_page["sections"])
    safe_slug = re.sub(r"[^a-z0-9-]", "", str(bp_page["slug"]))
    root_open = (
        '    <div data-component-id="page-' + safe_slug + '" data-component-label="' + _t(bp_page["name"], 30) + ' page" '
        'className="' + _route_root_class(bp_page) + '" '
        'data-page-type="' + _t(bp_page["page_type"], 36) + '" '
        'data-page-purpose="' + _t(bp_page["purpose"], 90) + '" '
        'data-page-audience="' + _t(bp_page["audience"], 90) + '" '
        'data-page-cta="' + _t(bp_page["main_cta"], 36) + '" '
        'data-page-card-style="' + _t(bp_page["card_style"], 24) + '" '
        'data-page-image-strategy="' + _t(bp_page["image_strategy"], 36) + '" '
        'data-page-hero-variant="' + _t(bp_page["hero_variant"], 72) + '" '
        'data-inspiration-family="' + _t(bp_page.get("inspiration_family", ""), 60) + '" '
        'data-visual-family="' + _t(bp_page.get("visual_family", ""), 60) + '" '
        'data-color-palette-family="' + _t(bp_page.get("color_palette_family", ""), 60) + '" '
        'data-typography-style="' + _t(bp_page.get("typography_style", ""), 60) + '" '
        'data-spacing-style="' + _t(bp_page.get("spacing_style", ""), 60) + '" '
        'data-hero-recipe="' + _t((_recipe(bp_page, "hero").get("id") or ""), 80) + '" '
        'data-nav-recipe="' + _t((_recipe(bp_page, "nav").get("id") or ""), 80) + '" '
        'data-card-recipe="' + _t((_recipe(bp_page, "card").get("id") or ""), 80) + '" '
        'data-cta-recipe="' + _t((_recipe(bp_page, "cta").get("id") or ""), 80) + '" '
        'data-footer-recipe="' + _t((_recipe(bp_page, "footer").get("id") or ""), 80) + '" '
        'data-section-recipes="' + _t(",".join(bp_page.get("section_recipe_ids") or []), 260) + '" '
        'data-browser-visible-signature="' + _t(bp_page.get("browser_visible_signature", ""), 360) + '" '
        'data-recipe-source-mode="' + _t(bp_page.get("recipe_source_mode", "handcrafted"), 40) + '" '
        'data-extracted-recipe-ids="' + _t(",".join(bp_page.get("extracted_recipe_ids") or []), 260) + '" '
        'data-extracted-recipe-components="' + _t(",".join((_github_influence(bp_page).get("component_types") or [])), 160) + '" '
        'data-extracted-recipe-layout="' + _t(_github_influence(bp_page).get("layout_pattern", ""), 80) + '" '
        'data-art-director="' + ("true" if bp_page.get("art_director_enabled") else "false") + '" '
        'data-premium-preset="' + _t(bp_page.get("premium_preset_id", ""), 80) + '" '
        'data-design-quality-before="' + _t((bp_page.get("design_quality_before") or {}).get("score", ""), 20) + '" '
        'data-design-quality-after="' + _t((bp_page.get("design_quality_after") or {}).get("score", ""), 20) + '" '
        'data-image-reuse-limit="' + _t(bp_page.get("image_reuse_limit", 2), 8) + '" '
        'data-image-roles="' + _t(",".join((bp_page.get("image_roles") or {}).keys()), 180) + '" '
        'data-dna-profile-ids="' + _t(",".join(bp_page.get("dna_profile_ids") or []), 160) + '" '
        'data-dna-family="' + _t(bp_page.get("primary_dna_family", ""), 60) + '" '
        'data-dna-families="' + _t(",".join(bp_page.get("dna_families") or []), 240) + '" '
        'data-dna-hero-pattern="' + _t((bp_page.get("hero_patterns") or [""])[0], 90) + '" '
        'data-dna-nav-pattern="' + _t((bp_page.get("nav_patterns") or [""])[0], 90) + '" '
        'data-dna-card-pattern="' + _t((bp_page.get("card_patterns") or [""])[0], 90) + '" '
        'data-dna-section-patterns="' + _t(",".join(bp_page.get("section_patterns") or []), 260) + '" '
        'data-genome-hero-variant="' + _t(bp_page["hero_variant"], 72) + '" '
        'data-genome-card-style="' + _t(bp_page["card_style"], 24) + '" '
        'data-genome-image-strategy="' + _t(bp_page["image_strategy"], 36) + '" '
        'data-genome-cta-placement="' + _t(bp_page["cta_placement"], 32) + '" '
        'data-page-section-sequence="' + _t(section_names, 260) + '" '
        'data-page-first-screen="' + _t(bp_page["first_screen"], 160) + '" '
        'data-genome-first-screen="' + _t(bp_page["first_screen"], 160) + '" '
        'data-page-visual-signature="' + _t(bp_page["signature"], 360) + '">\n'
    )
    legacy_body = hero + sections + footer
    try:
        body = _maybe_professional_body(bp, app_name, visual, bp_page, root_open, legacy_body)
    except Exception:
        body = legacy_body
    return _assemble_full_page(root_open, body)


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


def compose_marketing_page(page, bp, idx, app_name, ai_sections=False, section_order=None,
                           visual_grammar=None, exclude_families=None):
    """Build one full marketing page (server component) from a varied section pack.
    With ai_sections, each non-hero section is written by Gemma (validated; falls
    back to the deterministic builder when the AI output isn't safe to ship).
    `exclude_families` lists section families already used by earlier pages so this
    page will not repeat them (home-page sections never reappear in sub-pages)."""
    name = page.get("name", "Page")
    slug = page.get("slug", "page")
    template = page.get("template", "content")
    purpose = page.get("purpose") or f"Everything about {name.lower()} in {app_name}."
    kicker = bp.get("domain", app_name) or app_name
    img_subjects = bp.get("image_subjects") or []
    hero_asset = _HERO_IMG[idx % len(_HERO_IMG)]
    visual = dict(visual_grammar or {})
    # Thread exclude_families into the visual dict so _maybe_professional_body can
    # pass it through to the block selector via genome_like.
    if exclude_families:
        visual["exclude_families"] = list(exclude_families)
    section_variants = list(visual.get("section_variants") or [visual.get("section_variant", "feature cards")])
    card_style = visual.get("card_style", "bordered")
    rhythm = visual.get("layout_rhythm", "spacious")
    image_strategy = visual.get("image_strategy", "hero image")
    cta_placement = visual.get("cta_placement", "section-end")

    # Route-level blueprints are the real fix for same-layout pages inside one
    # generated app. The genome still chooses the visual grammar, but the
    # route purpose now chooses a different first-screen skeleton, section
    # sequence, CTA, and component family per page.
    return _compose_route_blueprint_page(page, bp, idx, app_name, visual)

    # Hero is now genome-selected: same prompt runs can open with completely
    # different first-screen skeletons, not just different copy.
    feats = _features_for(bp, idx, name)
    visual.setdefault("first_screen_skeleton", "|".join([
        str(visual.get("nav_variant", "")),
        str(visual.get("hero_variant", "split")),
        str(image_strategy),
        str(cta_placement),
    ]))
    hero = _hero_visual(kicker, name, purpose, hero_asset, visual, feats)

    terms = bp.get("terminology") or img_subjects

    def visual_for(kind, pos):
        chosen = section_variants[pos % len(section_variants)] if section_variants else visual.get("section_variant", "feature cards")
        if kind == "features" and chosen not in ("feature cards", "icon grid", "portal preview", "image-card"):
            chosen = "feature cards"
        if kind == "split" and chosen not in ("split image/text", "portal preview"):
            chosen = "split image/text"
        if kind == "stats":
            chosen = "stats band"
        if kind == "steps":
            chosen = "timeline" if chosen not in ("feature cards", "icon grid") else chosen
        if kind == "gallery":
            chosen = "gallery"
        if kind == "faq":
            chosen = "FAQ"
        if kind == "cta":
            chosen = "CTA"
        return chosen

    def render_section(kind, pos=0):
        section_variant = visual_for(kind, pos)
        if kind == "features":
            return feature_grid(f"What {name} gives you", feats, card_style, section_variant, rhythm)
        if kind == "steps":
            return process_steps(f"How {name.lower()} works", _steps_for(bp, name), card_style, section_variant, rhythm)
        if kind == "stats":
            return stats_band(_STAT_SETS[idx % len(_STAT_SETS)], card_style if card_style in ("flat", "bordered", "glass", "shadow", "stat-card") else "stat-card", section_variant, rhythm)
        if kind == "split":
            blurb = (feats[0]["text"] if feats else purpose) + " " + (
                f"{app_name} brings {kicker} together so nothing falls through the cracks.")
            return split_image_text(f"Built for {kicker}", blurb, _HERO_IMG[(idx + 2) % len(_HERO_IMG)], flip=(idx % 2 == 1),
                                    card_style=card_style, section_variant=section_variant, rhythm=rhythm,
                                    image_strategy=image_strategy)
        if kind == "terminology":
            return terminology_chips(f"The language of {kicker}", terms) if terms else ""
        if kind == "gallery":
            return gallery(["gallery1.jpg", "feature1.jpg", "gallery2.jpg", "about1.jpg", "gallery3.jpg", "feature2.jpg"], f"{name} gallery", card_style, rhythm)
        if kind == "pricing":
            return pricing(app_name, card_style)
        if kind == "faq":
            return faq(_faq_for(bp, app_name), card_style)
        if kind == "testimonial":
            return testimonial(f"Switching to {app_name} was the best decision we made for our {kicker} operations this year.", f"A happy {kicker} customer")
        if kind == "contact_form":
            return contact_section(app_name)
        if kind == "cta":
            return cta_band(app_name, placement=cta_placement, card_style=card_style)
        if kind not in _KNOWN_KINDS:    # a custom component the user typed in
            return custom_block(kind)
        return ""

    # Section order priority: explicit interview components > the genome's section_strategy
    # (generic pages only) > the template's default pack. This is what makes section_strategy
    # change the actual section TYPES + ORDER on generated pages.
    chosen = [k for k in (page.get("sections") or []) if k and k != "hero"]
    default_pack = _PACKS.get(template, _PACKS["content"])
    if chosen:
        kinds = chosen
    elif section_order and template in ("content", "features", "about"):
        kinds = [k for k in section_order if k in _KNOWN_KINDS] or default_pack
    else:
        kinds = default_pack
    def one(k, pos):
        if ai_sections:
            ai = _ai_section(k, name, app_name, kicker)
            if ai:
                return ai
        return render_section(k, pos)

    body = hero + "".join(one(k, i) for i, k in enumerate(kinds))
    if not chosen or "cta" not in chosen:   # always close with a call to action
        body += cta_band(app_name, placement=cta_placement, card_style=card_style)

    return (
        "import { CheckCircle2 } from 'lucide-react';\n\n"
        "export default function Page() {\n"
        "  return (\n"
        '    <div data-component-id="page-' + re.sub(r"[^a-z0-9-]", "", slug) + '" data-component-label="' + _t(name, 30) + ' page">\n'
        + body +
        "    </div>\n"
        "  );\n}\n"
    )
