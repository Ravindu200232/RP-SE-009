"""Professional, code-backed website SECTION library (1000+ records).

Sections are full-width page blocks (hero, navbar, pricing, doctor search, lab
report preview, footer, ...) assembled from the original component renderers in
`professional_components.py`. Like the component library this contains NO copied
websites, brand names, logos, source copy, exact layouts, or external image URLs:
every record is generated from abstract `section_type x visual_family x variant`
combinations and renders responsive, accessible Tailwind/JSX.

Each section composes real components, so a generated page reads as a varied,
professional layout instead of one repeated card skeleton.
"""
from __future__ import annotations

from collections import Counter
import copy

from app import professional_components as pc
from app.professional_components import (
    VISUAL_FAMILIES,
    DOMAINS,
    family_style,
    render_block,
    scan_text_for_violations,
    scan_jsx_for_violations,
    search_records,
)

_icon = pc._icon
_t = pc._t
_attr = pc._attr
_img = pc._img
_chip = pc._chip
_stars = pc._stars
_eyebrow = pc._eyebrow


# --------------------------------------------------------------------------- #
# Section vocabulary
# --------------------------------------------------------------------------- #

SECTION_TYPES = [
    "hero",
    "navbar",
    "feature grid",
    "service grid",
    "stats strip",
    "trust badges",
    "product showcase",
    "pricing",
    "testimonials",
    "faq",
    "cta banner",
    "footer",
    "gallery",
    "timeline",
    "booking flow",
    "search panel",
    "dashboard preview",
    "app preview",
    "portal preview",
    "report preview",
    "team section",
    "department grid",
    "doctor search",
    "appointment cta",
    "patient portal",
    "lab report preview",
    "vehicle inventory grid",
    "product collection grid",
    "restaurant menu preview",
    "reservation section",
    "travel destination hero",
    "itinerary cards",
    "property search",
    "property listing grid",
    "fitness program cards",
    "trainer profile section",
    "course catalog",
    "learning path section",
    "ai api panel",
    "developer workflow section",
    "fintech transaction preview",
]

SECTION_VARIANTS = ["soft", "elevated"]

# Semantic group of each section type — the meaning of the block, used by route
# intelligence + duplicate prevention (route_block_rules / page_quality_gate).
_SECTION_SEMANTIC_GROUP = {
    "hero": "hero", "travel destination hero": "hero", "navbar": "nav", "footer": "footer",
    "feature grid": "generic_features", "service grid": "generic_services", "stats strip": "stats",
    "trust badges": "trust", "product showcase": "ecommerce_collection",
    "product collection grid": "ecommerce_collection", "pricing": "generic_pricing",
    "testimonials": "testimonials", "faq": "faq", "cta banner": "cta", "gallery": "gallery",
    "timeline": "process", "booking flow": "booking", "search panel": "search",
    "dashboard preview": "dashboard_metrics", "app preview": "app_preview",
    "portal preview": "provider_tools", "report preview": "invoice_reporting",
    "team section": "profile_directory", "department grid": "patient_services",
    "doctor search": "doctor_search", "appointment cta": "appointment_booking",
    "patient portal": "patient_services", "lab report preview": "lab_report",
    "vehicle inventory grid": "vehicle_inventory", "restaurant menu preview": "restaurant_menu",
    "reservation section": "reservation_booking", "itinerary cards": "itinerary_packages",
    "property search": "property_listing", "property listing grid": "property_listing",
    "fitness program cards": "fitness_programs", "trainer profile section": "trainer_profiles",
    "course catalog": "education_courses", "learning path section": "education_courses",
    "ai api panel": "ai_console", "developer workflow section": "ai_console",
    "fintech transaction preview": "invoice_reporting",
}


def semantic_group_for(section_type: str) -> str:
    """The semantic group (meaning) of a section type, e.g. 'property_listing'."""
    return _SECTION_SEMANTIC_GROUP.get(section_type, "generic_content")


SECTION_TYPE_DOMAINS = {
    "hero": [],
    "navbar": [],
    "feature grid": ["saas", "ai-devtools", "business-ops"],
    "service grid": ["healthcare", "business-ops", "agency", "fitness"],
    "stats strip": ["saas", "business-ops", "fintech"],
    "trust badges": [],
    "product showcase": ["ecommerce"],
    "pricing": ["saas", "fintech", "ecommerce", "business-ops"],
    "testimonials": [],
    "faq": [],
    "cta banner": [],
    "footer": [],
    "gallery": ["media", "agency", "travel", "restaurant"],
    "timeline": ["business-ops", "education", "agency"],
    "booking flow": ["healthcare", "restaurant", "travel", "fitness"],
    "search panel": ["real-estate", "travel", "ecommerce", "automotive"],
    "dashboard preview": ["saas", "business-ops", "fintech"],
    "app preview": ["saas", "ai-devtools", "community"],
    "portal preview": ["healthcare", "business-ops", "saas"],
    "report preview": ["business-ops", "fintech", "saas"],
    "team section": ["agency", "community", "healthcare"],
    "department grid": ["healthcare"],
    "doctor search": ["healthcare"],
    "appointment cta": ["healthcare"],
    "patient portal": ["healthcare"],
    "lab report preview": ["healthcare"],
    "vehicle inventory grid": ["automotive"],
    "product collection grid": ["ecommerce"],
    "restaurant menu preview": ["restaurant"],
    "reservation section": ["restaurant"],
    "travel destination hero": ["travel"],
    "itinerary cards": ["travel"],
    "property search": ["real-estate"],
    "property listing grid": ["real-estate"],
    "fitness program cards": ["fitness"],
    "trainer profile section": ["fitness"],
    "course catalog": ["education"],
    "learning path section": ["education"],
    "ai api panel": ["ai-devtools"],
    "developer workflow section": ["ai-devtools"],
    "fintech transaction preview": ["fintech"],
}

_PAGE_LANDING = {
    "hero", "feature grid", "service grid", "stats strip", "trust badges",
    "product showcase", "pricing", "testimonials", "faq", "cta banner", "gallery",
    "timeline", "department grid", "appointment cta", "vehicle inventory grid",
    "product collection grid", "restaurant menu preview", "reservation section",
    "travel destination hero", "itinerary cards", "property listing grid",
    "fitness program cards", "trainer profile section", "course catalog",
    "learning path section", "ai api panel", "developer workflow section", "team section",
}
_PAGE_APP = {"dashboard preview", "app preview", "portal preview", "report preview",
             "patient portal", "fintech transaction preview"}
_PAGE_SEARCH = {"search panel", "doctor search", "property search"}
_PAGE_DETAIL = {"lab report preview"}
_PAGE_CHROME = {"navbar", "footer"}
_PAGE_FLOW = {"booking flow"}


def _page_type(section_type: str) -> str:
    if section_type in _PAGE_APP:
        return "app"
    if section_type in _PAGE_SEARCH:
        return "search"
    if section_type in _PAGE_DETAIL:
        return "detail"
    if section_type in _PAGE_CHROME:
        return "chrome"
    if section_type in _PAGE_FLOW:
        return "flow"
    return "landing"


SECTION_DEPENDENCIES = {
    "hero": ["cta button group", "badge", "image panel", "trust badge"],
    "navbar": ["nav item", "button", "logo cloud item"],
    "feature grid": ["feature card"],
    "service grid": ["service card"],
    "stats strip": ["stat card"],
    "trust badges": ["trust badge", "logo cloud item"],
    "product showcase": ["product card", "badge"],
    "pricing": ["pricing card"],
    "testimonials": ["testimonial card"],
    "faq": ["accordion item"],
    "cta banner": ["cta button group"],
    "footer": ["footer link group", "logo cloud item"],
    "gallery": ["image panel"],
    "timeline": ["timeline item"],
    "booking flow": ["timeline item", "form field", "cta button group"],
    "search panel": ["search box", "badge"],
    "dashboard preview": ["dashboard metric card", "chart preview card", "table preview"],
    "app preview": ["dashboard metric card", "tab item", "image panel"],
    "portal preview": ["dashboard metric card", "table preview", "cta button group"],
    "report preview": ["table preview", "stat card"],
    "team section": ["profile card"],
    "department grid": ["service card"],
    "doctor search": ["search box", "doctor card"],
    "appointment cta": ["cta button group", "trust badge"],
    "patient portal": ["dashboard metric card", "table preview", "cta button group"],
    "lab report preview": ["table preview", "badge", "stat card"],
    "vehicle inventory grid": ["vehicle card", "search box"],
    "product collection grid": ["product card", "badge"],
    "restaurant menu preview": ["restaurant menu card", "tab item"],
    "reservation section": ["form field", "cta button group", "trust badge"],
    "travel destination hero": ["search box", "badge", "cta button group"],
    "itinerary cards": ["travel package card", "timeline item"],
    "property search": ["search box", "property card"],
    "property listing grid": ["property card"],
    "fitness program cards": ["service card", "badge"],
    "trainer profile section": ["trainer card"],
    "course catalog": ["course card", "tab item"],
    "learning path section": ["timeline item", "course card"],
    "ai api panel": ["feature card", "button"],
    "developer workflow section": ["timeline item", "feature card"],
    "fintech transaction preview": ["table preview", "dashboard metric card", "stat card"],
}

_LAYOUT_TAGS = {
    "hero": ["split", "media-right", "above-the-fold"],
    "navbar": ["bar", "sticky-ready", "responsive-menu"],
    "feature grid": ["grid", "3-col", "cards"],
    "service grid": ["grid", "3-col", "cards"],
    "stats strip": ["strip", "4-col", "metrics"],
    "trust badges": ["row", "logo-cloud", "centered"],
    "product showcase": ["grid", "4-col", "media-cards"],
    "pricing": ["grid", "3-col", "comparison"],
    "testimonials": ["grid", "3-col", "social-proof"],
    "faq": ["stack", "accordion", "single-col"],
    "cta banner": ["banner", "centered", "gradient-ready"],
    "footer": ["columns", "multi-col", "site-wide"],
    "gallery": ["masonry", "media", "grid"],
    "timeline": ["timeline", "vertical", "process"],
    "booking flow": ["steps", "form", "split"],
    "search panel": ["search", "filters", "sticky-ready"],
    "dashboard preview": ["dashboard", "grid", "data-dense"],
    "app preview": ["preview", "tabs", "media"],
    "portal preview": ["portal", "grid", "data-dense"],
    "report preview": ["report", "table", "data-dense"],
    "team section": ["grid", "4-col", "profiles"],
    "department grid": ["grid", "3-col", "directory"],
    "doctor search": ["search", "list", "directory"],
    "appointment cta": ["banner", "conversion", "centered"],
    "patient portal": ["portal", "grid", "data-dense"],
    "lab report preview": ["report", "table", "detail"],
    "vehicle inventory grid": ["grid", "filters", "media-cards"],
    "product collection grid": ["grid", "4-col", "collection"],
    "restaurant menu preview": ["grid", "tabs", "menu"],
    "reservation section": ["form", "split", "conversion"],
    "travel destination hero": ["hero", "search", "immersive"],
    "itinerary cards": ["grid", "timeline", "media-cards"],
    "property search": ["search", "grid", "listings"],
    "property listing grid": ["grid", "3-col", "listings"],
    "fitness program cards": ["grid", "3-col", "programs"],
    "trainer profile section": ["grid", "4-col", "profiles"],
    "course catalog": ["grid", "tabs", "catalog"],
    "learning path section": ["timeline", "grid", "path"],
    "ai api panel": ["split", "code", "console"],
    "developer workflow section": ["timeline", "grid", "process"],
    "fintech transaction preview": ["app", "table", "data-dense"],
}


# --------------------------------------------------------------------------- #
# Section shell + header helpers
# --------------------------------------------------------------------------- #

def _header(style, eyebrow=None, title=None, subtitle=None, align="left"):
    if not (eyebrow or title or subtitle):
        return ""
    wrap = "mx-auto max-w-2xl text-center" if align == "center" else "max-w-2xl"
    parts = [f'<div className="{wrap}">']
    if eyebrow:
        parts.append(_eyebrow(eyebrow, style))
    if title:
        parts.append(
            f'<h2 className="mt-2 text-2xl font-bold tracking-tight {style["heading"]} '
            f'sm:text-3xl lg:text-4xl">{_t(title, "Section title", 90)}</h2>'
        )
    if subtitle:
        parts.append(
            f'<p className="mt-3 text-base leading-relaxed {style["muted"]} sm:text-lg">'
            f'{_t(subtitle, "", 200)}</p>'
        )
    parts.append("</div>")
    return "".join(parts)


def _shell(style, body, header="", alt=False, pad="py-16 sm:py-20 lg:py-24"):
    bg = style["page_alt"] if alt else style["page"]
    attrs = style.get("section_attrs", "")
    return (
        f'<section {attrs} className="{bg}">'
        f'<div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 {pad}">{header}{body}</div></section>'
    )


def _grid(cards, cols="sm:grid-cols-2 lg:grid-cols-3", top="mt-10"):
    return f'<div className="{top} grid gap-5 {cols}">{cards}</div>'


def _many(component_type, items, style):
    return "".join(render_block(component_type, it, style) for it in items)


# --------------------------------------------------------------------------- #
# Section renderers
# --------------------------------------------------------------------------- #

def render_hero(props, style, rec):
    title = _t(props.get("title"), "Build experiences people trust", 90)
    sub = _t(props.get("subtitle"),
             "A faster, calmer way to ship the product your customers deserve — responsive, "
             "accessible, and ready for production from day one.", 200)
    badge = _chip(props.get("eyebrow", "New · 2024 release"), style, "spark")
    cta = render_block("cta button group",
                       {"primary": props.get("primary", "Get started"),
                        "secondary": props.get("secondary", "Book a demo")}, style)
    trust = _many("trust badge",
                  props.get("trust") or [{"label": "Audited yearly", "sub": "Independent review"},
                                         {"label": "99.9% uptime", "sub": "Resilient by design"}],
                  style)
    # Premium domain panel instead of a blank gray image box (hero_visuals).
    from app import hero_visuals
    panel = hero_visuals.hero_panel(props.get("domain") or style.get("family", ""), style,
                                    variant=props.get("hero_panel_variant", "primary"),
                                    image=props.get("image"))
    body = (
        f'<div className="grid items-center gap-10 lg:grid-cols-2">'
        f'<div className="max-w-xl">{badge}'
        f'<h1 className="mt-4 text-4xl font-bold tracking-tight {style["heading"]} sm:text-5xl lg:text-6xl">{title}</h1>'
        f'<p className="mt-5 text-lg leading-relaxed {style["muted"]}">{sub}</p>'
        f'<div className="mt-7">{cta}</div>'
        f'<div className="mt-7 flex flex-wrap gap-3">{trust}</div></div>'
        f'<div>{panel}</div></div>'
    )
    return _shell(style, body, pad="py-12 sm:py-14 lg:py-20")


def render_navbar(props, style, rec):
    brand = _t(props.get("brand"), "Brightline", 24)
    initials = "".join(w[0] for w in brand.split()[:2]).upper() or "BL"
    links = props.get("links") or ["Product", "Solutions", "Pricing", "Resources"]
    nav = "".join(render_block("nav item", {"label": l, "active": i == 0}, style)
                  for i, l in enumerate(links))
    actions = (
        f'<div className="hidden items-center gap-2 md:flex">'
        f'<button type="button" className="{style["btn_secondary"]} px-4 py-2 text-sm">Sign in</button>'
        f'<button type="button" className="{style["btn_primary"]} px-4 py-2 text-sm">Get started</button></div>'
    )
    attrs = style.get("section_attrs", "")
    return (
        f'<header {attrs} className="{style["page"]} border-b {style["border"]}">'
        f'<nav className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3.5 sm:px-6 lg:px-8" aria-label="Primary">'
        f'<a href="#" className="flex items-center gap-2">'
        f'<span className="flex h-8 w-8 items-center justify-center rounded-lg {style["accent"]} {style["on_accent"]} text-sm font-bold" aria-hidden="true">{initials}</span>'
        f'<span className="text-base font-semibold {style["heading"]}">{brand}</span></a>'
        f'<div className="hidden items-center gap-1 md:flex">{nav}</div>'
        f'{actions}'
        f'<button type="button" aria-label="Open menu" className="md:hidden {style["accent_text"]}">{_icon("plus", "h-6 w-6")}</button>'
        f'</nav></header>'
    )


def render_feature_grid(props, style, rec):
    feats = props.get("features") or [
        {"title": "Composable blocks", "description": "Drop-in sections that adapt to any layout and screen size.", "icon": "spark"},
        {"title": "Accessible by default", "description": "Semantic markup, focus states, and contrast handled for you.", "icon": "shield"},
        {"title": "Lightning fast", "description": "Tuned for performance so first paint stays effortless.", "icon": "bolt"},
        {"title": "Fully responsive", "description": "Mobile, tablet, and desktop layouts from a single source.", "icon": "check"},
        {"title": "Themeable", "description": "Swap palettes and corner language without touching markup.", "icon": "star"},
        {"title": "Production-ready", "description": "Battle-tested patterns you can ship with confidence.", "icon": "calendar"},
    ]
    body = _grid(_many("feature card", feats, style))
    return _shell(style, body,
                  _header(style, "Capabilities", "Everything your team needs to ship",
                          "A practical toolkit of polished, reusable building blocks."))


def render_service_grid(props, style, rec):
    services = props.get("services") or [
        {"title": "Strategy", "description": "Align goals, audience, and a measurable plan.", "icon": "spark"},
        {"title": "Design", "description": "Interfaces that feel calm, clear, and on-brand.", "icon": "star"},
        {"title": "Delivery", "description": "Reliable build and launch with ongoing support.", "icon": "bolt"},
    ]
    body = _grid(_many("service card", services, style))
    return _shell(style, body,
                  _header(style, "Services", "How we help", "Focused offerings, delivered end to end."), alt=True)


def render_stats_strip(props, style, rec):
    stats = props.get("stats") or [
        {"value": "12k+", "label": "Active teams", "delta": "+18% YoY"},
        {"value": "99.9%", "label": "Uptime", "delta": "Last 12 months"},
        {"value": "4.9/5", "label": "Avg. rating", "delta": "2,300 reviews"},
        {"value": "48", "label": "Countries", "delta": "Global coverage"},
    ]
    body = f'<dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">{_many("stat card", stats, style)}</dl>'
    return _shell(style, body, pad="py-12 sm:py-16")


def render_trust_badges(props, style, rec):
    badges = _many("trust badge", props.get("badges") or [
        {"label": "Encrypted", "sub": "End-to-end"},
        {"label": "Compliant", "sub": "Independently audited"},
        {"label": "Reliable", "sub": "99.9% uptime"},
    ], style)
    logos = "".join(render_block("logo cloud item", {"label": l}, style)
                    for l in (props.get("partners") or ["Northwind", "Cedar Co", "Atlas Labs", "Vela", "Quay"]))
    body = (
        f'<div className="flex flex-wrap items-center justify-center gap-3">{badges}</div>'
        f'<div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">{logos}</div>'
    )
    return _shell(style, body, _header(style, None, "Trusted by teams everywhere", None, align="center"), pad="py-12 sm:py-16")


def render_product_showcase(props, style, rec):
    products = props.get("products") or [
        {"title": "Aurora Lamp", "price": "$89", "category": "Lighting", "image": "/generated/product-1.jpg"},
        {"title": "Drift Chair", "price": "$240", "category": "Seating", "image": "/generated/product-2.jpg"},
        {"title": "Pebble Speaker", "price": "$129", "category": "Audio", "image": "/generated/product-3.jpg"},
        {"title": "Field Bottle", "price": "$28", "category": "Outdoor", "image": "/generated/product-4.jpg"},
    ]
    body = _grid(_many("product card", products, style), cols="grid-cols-2 lg:grid-cols-4")
    return _shell(style, body, _header(style, "Featured", "Shop the collection", "Hand-picked pieces, ready to ship."))


def render_pricing(props, style, rec):
    plans = props.get("plans") or [
        {"plan": "Starter", "price": "$0", "period": "/ mo", "features": ["1 project", "Community support", "Core blocks"]},
        {"plan": "Growth", "price": "$49", "period": "/ mo", "featured": True,
         "features": ["Unlimited projects", "Priority support", "Advanced analytics", "Team roles"]},
        {"plan": "Scale", "price": "$129", "period": "/ mo", "features": ["SSO & SAML", "Audit logs", "Dedicated manager", "SLA"]},
    ]
    body = _grid(_many("pricing card", plans, style), cols="lg:grid-cols-3")
    return _shell(style, body, _header(style, "Pricing", "Simple, transparent plans",
                                       "Start free, upgrade when you grow.", align="center"))


def render_testimonials(props, style, rec):
    quotes = props.get("testimonials") or [
        {"quote": "The rollout was seamless and our team finally has one source of truth.", "author": "Priya N.", "role": "Operations Lead"},
        {"quote": "We shipped a polished site in days, not months. Support was outstanding.", "author": "Marco D.", "role": "Founder"},
        {"quote": "Accessibility and performance came for free. That never happens.", "author": "Aisha K.", "role": "Engineering Manager"},
    ]
    body = _grid(_many("testimonial card", quotes, style))
    return _shell(style, body, _header(style, "Loved by customers", "What people are saying", None), alt=True)


def render_faq(props, style, rec):
    faqs = props.get("faqs") or [
        {"question": "How does onboarding work?", "answer": "A guided setup, sample data, and a specialist on your first call."},
        {"question": "Can I cancel anytime?", "answer": "Yes — plans are month-to-month with no lock-in."},
        {"question": "Do you support exports?", "answer": "Export to common formats whenever you need your data."},
        {"question": "Is my data secure?", "answer": "Encryption in transit and at rest, with regular independent audits."},
    ]
    items = _many("accordion item", faqs, style)
    body = f'<div className="mx-auto mt-10 max-w-3xl space-y-3">{items}</div>'
    return _shell(style, body, _header(style, "FAQ", "Questions, answered", None, align="center"))


def render_cta_banner(props, style, rec):
    title = _t(props.get("title"), "Ready to get started?", 80)
    sub = _t(props.get("subtitle"), "Join thousands of teams shipping faster with a calmer workflow.", 160)
    cta = render_block("cta button group", {"primary": props.get("primary", "Start free"),
                                            "secondary": props.get("secondary", "Contact sales")}, style)
    body = (
        f'<div className="{style["accent_grad"]} {style["radius"]} px-6 py-12 text-center sm:px-12 sm:py-16">'
        f'<h2 className="mx-auto max-w-2xl text-2xl font-bold tracking-tight text-white sm:text-3xl lg:text-4xl">{title}</h2>'
        f'<p className="mx-auto mt-3 max-w-xl text-base text-white/85 sm:text-lg">{sub}</p>'
        f'<div className="mt-7 flex justify-center">{cta}</div></div>'
    )
    return _shell(style, body)


def render_footer(props, style, rec):
    brand = _t(props.get("brand"), "Brightline", 24)
    groups = props.get("groups") or [
        {"heading": "Product", "links": ["Features", "Pricing", "Integrations", "Changelog"]},
        {"heading": "Company", "links": ["About", "Careers", "Press", "Contact"]},
        {"heading": "Resources", "links": ["Docs", "Guides", "Support", "Status"]},
        {"heading": "Legal", "links": ["Privacy", "Terms", "Security"]},
    ]
    cols = "".join(render_block("footer link group", g, style) for g in groups)
    attrs = style.get("section_attrs", "")
    return (
        f'<footer {attrs} className="{style["page"]} border-t {style["border"]}">'
        f'<div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">'
        f'<div className="grid gap-10 lg:grid-cols-[1.4fr_repeat(4,1fr)]">'
        f'<div className="max-w-xs"><span className="text-lg font-semibold {style["heading"]}">{brand}</span>'
        f'<p className="mt-3 text-sm leading-relaxed {style["muted"]}">Polished, responsive building blocks for modern teams.</p></div>'
        f'{cols}</div>'
        f'<div className="mt-10 flex flex-col items-start justify-between gap-3 border-t {style["border"]} pt-6 sm:flex-row sm:items-center">'
        f'<p className="text-xs {style["muted"]}">© 2024 {brand}. All rights reserved.</p>'
        f'<p className="text-xs {style["muted"]}">Made for production.</p></div></div></footer>'
    )


def render_gallery(props, style, rec):
    captions = props.get("captions") or ["Studio", "On location", "Behind the scenes", "Detail", "Process", "Final"]
    panels = "".join(
        render_block("image panel", {"image": f"/generated/gallery-{i + 1}.jpg", "caption": c}, style)
        for i, c in enumerate(captions[:6])
    )
    body = f'<div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{panels}</div>'
    return _shell(style, body, _header(style, "Gallery", "Selected work", None))


def render_timeline(props, style, rec):
    steps = props.get("steps") or [
        {"time": "Step 1", "title": "Discovery", "description": "We map your goals and align on a clear plan."},
        {"time": "Step 2", "title": "Design", "description": "We craft the experience and validate early."},
        {"time": "Step 3", "title": "Build", "description": "We ship in focused, reviewable increments."},
        {"time": "Step 4", "title": "Launch", "description": "We release, measure, and keep improving."},
    ]
    items = _many("timeline item", steps, style)
    body = f'<ol className="mt-10 grid gap-8 sm:grid-cols-2">{items}</ol>'
    return _shell(style, body, _header(style, "Process", "A clear path from start to launch", None))


def render_booking_flow(props, style, rec):
    steps = _many("timeline item", [
        {"time": "1", "title": "Choose a service", "description": "Pick what you need from a clear menu."},
        {"time": "2", "title": "Pick a time", "description": "See real availability and select a slot."},
        {"time": "3", "title": "Confirm", "description": "Add details and get instant confirmation."},
    ], style)
    fields = (
        render_block("form field", {"label": "Full name", "placeholder": "Your name"}, style)
        + render_block("form field", {"label": "Email", "type": "email", "placeholder": "you@example"}, style)
        + render_block("form field", {"label": "Preferred date", "type": "date", "helper": "We will confirm within an hour."}, style)
    )
    cta = render_block("cta button group", {"primary": "Confirm booking", "secondary": "Back"}, style)
    body = (
        f'<div className="mt-10 grid gap-10 lg:grid-cols-2">'
        f'<ol className="space-y-8">{steps}</ol>'
        f'<div className="{style["card"]} space-y-4 p-5 sm:p-6">{fields}<div className="pt-2">{cta}</div></div></div>'
    )
    return _shell(style, body, _header(style, "Booking", "Reserve in three steps", None))


def render_search_panel(props, style, rec):
    box = render_block("search box", {"placeholder": props.get("placeholder", "Search by keyword, name, or location"),
                                      "label": "Search"}, style)
    chips = "".join(_chip(c, style) for c in (props.get("filters") or ["All", "Popular", "Nearby", "Top rated", "New"]))
    body = (
        f'<div className="mx-auto max-w-3xl">{box}'
        f'<div className="mt-4 flex flex-wrap justify-center gap-2">{chips}</div></div>'
    )
    return _shell(style, body, _header(style, "Find what you need", "Start your search", None, align="center"), pad="py-12 sm:py-16")


def render_dashboard_preview(props, style, rec):
    metrics = _many("dashboard metric card", [
        {"label": "Revenue", "value": "$84.2k", "trend": "+12%"},
        {"label": "Active users", "value": "12,480", "trend": "+8%"},
        {"label": "Churn", "value": "1.4%", "trend": "-0.3%", "direction": "down"},
    ], style)
    chart = render_block("chart preview card", {"title": "Monthly revenue"}, style)
    table = render_block("table preview", {"title": "Recent activity"}, style)
    body = (
        f'<div className="mt-10 grid gap-5 lg:grid-cols-3">{metrics}</div>'
        f'<div className="mt-5 grid gap-5 lg:grid-cols-2">{chart}{table}</div>'
    )
    return _shell(style, body, _header(style, "Dashboard", "Everything at a glance", None), alt=True)


def render_app_preview(props, style, rec):
    tabs = "".join(render_block("tab item", {"label": l, "selected": i == 0}, style)
                   for i, l in enumerate(["Overview", "Activity", "Settings"]))
    metrics = _many("dashboard metric card", [
        {"label": "Tasks done", "value": "318", "trend": "+24"},
        {"label": "In progress", "value": "27", "trend": "+5"},
    ], style)
    panel = render_block("image panel", {"image": "/generated/app-1.jpg", "caption": "Workspace preview"}, style)
    body = (
        f'<div className="mt-10 grid items-start gap-8 lg:grid-cols-2">'
        f'<div><div className="flex gap-1 border-b {style["border"]}">{tabs}</div>'
        f'<div className="mt-5 grid gap-5 sm:grid-cols-2">{metrics}</div></div>'
        f'<div>{panel}</div></div>'
    )
    return _shell(style, body, _header(style, "Product", "A workspace your team will love", None))


def render_portal_preview(props, style, rec):
    metrics = _many("dashboard metric card", [
        {"label": "Open requests", "value": "8", "trend": "-2", "direction": "down"},
        {"label": "Documents", "value": "142", "trend": "+6"},
        {"label": "Messages", "value": "3", "trend": "new"},
    ], style)
    table = render_block("table preview", {"title": "Your records", "headers": ["Reference", "Type", "Status", "Updated"]}, style)
    cta = render_block("cta button group", {"primary": "Open portal", "secondary": "Get help"}, style)
    body = (
        f'<div className="mt-10 grid gap-5 sm:grid-cols-3">{metrics}</div>'
        f'<div className="mt-5">{table}</div><div className="mt-6">{cta}</div>'
    )
    return _shell(style, body, _header(style, "Self-service", "Your secure portal", None), alt=True)


def render_report_preview(props, style, rec):
    stats = _many("stat card", [
        {"value": "$1.24M", "label": "Total processed", "delta": "+9.2% MoM"},
        {"value": "3,902", "label": "Transactions", "delta": "+412 this week"},
    ], style)
    table = render_block("table preview", {"title": "Statement", "headers": ["Date", "Description", "Status", "Amount"]}, style)
    body = (
        f'<div className="mt-10 grid gap-5 sm:grid-cols-2">{stats}</div>'
        f'<div className="mt-5">{table}</div>'
    )
    return _shell(style, body, _header(style, "Reports", "Clear, exportable reporting", None))


def render_team_section(props, style, rec):
    people = props.get("team") or [
        {"name": "Jordan Avery", "role": "Founder", "bio": "Leads product and design strategy."},
        {"name": "Sam Okoye", "role": "Engineering", "bio": "Builds the platform and tooling."},
        {"name": "Lena Park", "role": "Operations", "bio": "Keeps delivery smooth and on time."},
        {"name": "Mara Liu", "role": "Success", "bio": "Partners with customers end to end."},
    ]
    body = _grid(_many("profile card", people, style), cols="sm:grid-cols-2 lg:grid-cols-4")
    return _shell(style, body, _header(style, "Team", "The people behind the work", None, align="center"))


def render_department_grid(props, style, rec):
    depts = props.get("departments") or [
        {"title": "Cardiology", "description": "Heart health, diagnostics, and ongoing care.", "icon": "heart", "points": ["ECG & imaging", "Specialist clinics"]},
        {"title": "Pediatrics", "description": "Compassionate care for infants to teens.", "icon": "user", "points": ["Well-child visits", "Vaccinations"]},
        {"title": "Orthopedics", "description": "Bone, joint, and mobility treatment.", "icon": "shield", "points": ["Sports injuries", "Rehab support"]},
        {"title": "Neurology", "description": "Diagnosis and care for the nervous system.", "icon": "spark", "points": ["Advanced imaging", "Care plans"]},
        {"title": "Dermatology", "description": "Skin health, screening, and treatment.", "icon": "star", "points": ["Screenings", "Procedures"]},
        {"title": "Emergency", "description": "24/7 urgent and emergency services.", "icon": "bolt", "points": ["Always open", "Rapid triage"]},
    ]
    body = _grid(_many("service card", depts, style))
    return _shell(style, body, _header(style, "Departments", "Specialist care, all in one place",
                                       "Find the right department and book in minutes."))


def render_doctor_search(props, style, rec):
    box = render_block("search box", {"placeholder": "Search by specialty, name, or symptom", "label": "Find a doctor"}, style)
    chips = "".join(_chip(c, style) for c in ["Cardiology", "Pediatrics", "Dermatology", "Neurology", "Telehealth"])
    docs = _many("doctor card", props.get("doctors") or [
        {"name": "Dr. Amara Singh", "specialty": "Cardiology", "availability": "Today 3:30 PM"},
        {"name": "Dr. Eli Rosen", "specialty": "Pediatrics", "availability": "Tomorrow 9:00 AM"},
        {"name": "Dr. Noor Haddad", "specialty": "Dermatology", "availability": "Today 5:15 PM"},
        {"name": "Dr. Ken Mori", "specialty": "Neurology", "availability": "Wed 11:00 AM"},
    ], style)
    body = (
        f'<div className="mx-auto max-w-3xl">{box}'
        f'<div className="mt-4 flex flex-wrap justify-center gap-2">{chips}</div></div>'
        f'<div className="mt-10 grid gap-5 sm:grid-cols-2">{docs}</div>'
    )
    return _shell(style, body, _header(style, "Find a doctor", "Search our specialists", None, align="center"))


def render_appointment_cta(props, style, rec):
    cta = render_block("cta button group", {"primary": "Book an appointment", "secondary": "Call the clinic"}, style)
    trust = _many("trust badge", [
        {"label": "Same-week visits", "sub": "Across departments"},
        {"label": "Secure records", "sub": "Encrypted portal"},
    ], style)
    body = (
        f'<div className="{style["card"]} grid items-center gap-6 p-6 sm:p-10 lg:grid-cols-[1.3fr_0.7fr]">'
        f'<div><h2 className="text-2xl font-bold tracking-tight {style["heading"]} sm:text-3xl">Care when you need it</h2>'
        f'<p className="mt-3 text-base {style["muted"]}">Book online in minutes and get a confirmation right away.</p>'
        f'<div className="mt-6">{cta}</div></div>'
        f'<div className="flex flex-col gap-3">{trust}</div></div>'
    )
    return _shell(style, body)


def render_patient_portal(props, style, rec):
    metrics = _many("dashboard metric card", [
        {"label": "Upcoming visits", "value": "2", "trend": "next: Tue"},
        {"label": "Prescriptions", "value": "5", "trend": "1 refill due"},
        {"label": "Messages", "value": "3", "trend": "new"},
    ], style)
    table = render_block("table preview", {"title": "Recent visits", "headers": ["Date", "Department", "Provider", "Status"]}, style)
    cta = render_block("cta button group", {"primary": "Request a refill", "secondary": "Message care team"}, style)
    body = (
        f'<div className="mt-10 grid gap-5 sm:grid-cols-3">{metrics}</div>'
        f'<div className="mt-5">{table}</div><div className="mt-6">{cta}</div>'
    )
    return _shell(style, body, _header(style, "Patient portal", "Your health, organized", None), alt=True)


def render_lab_report_preview(props, style, rec):
    badges = "".join(_chip(c, style) for c in ["Final", "Reviewed", "Normal range"])
    stats = _many("stat card", [
        {"value": "Normal", "label": "Overall result", "delta": "Within reference"},
        {"value": "12", "label": "Markers tested", "delta": "All reported"},
    ], style)
    table = render_block("table preview", {"title": "Lab results", "headers": ["Marker", "Result", "Range", "Flag"]}, style)
    body = (
        f'<div className="mb-6 flex flex-wrap gap-2">{badges}</div>'
        f'<div className="grid gap-5 sm:grid-cols-2">{stats}</div>'
        f'<div className="mt-5">{table}</div>'
    )
    return _shell(style, body, _header(style, "Lab report", "Clear, readable results", None))


def render_vehicle_inventory_grid(props, style, rec):
    box = render_block("search box", {"placeholder": "Search make, model, or budget", "label": "Search inventory"}, style)
    vehicles = _many("vehicle card", props.get("vehicles") or [
        {"name": "Volt GT Electric", "price": "$42,500", "specs": ["2024", "Electric", "Auto"], "image": "/generated/vehicle-1.jpg"},
        {"name": "Trail Ridge SUV", "price": "$36,900", "specs": ["2023", "Hybrid", "AWD"], "image": "/generated/vehicle-2.jpg"},
        {"name": "Cove Sedan", "price": "$28,400", "specs": ["2024", "Petrol", "Auto"], "image": "/generated/vehicle-3.jpg"},
        {"name": "Harbor Van", "price": "$39,750", "specs": ["2023", "Diesel", "Manual"], "image": "/generated/vehicle-4.jpg"},
    ], style)
    body = f'<div className="mx-auto max-w-3xl">{box}</div>{_grid(vehicles)}'
    return _shell(style, body, _header(style, "Inventory", "Browse certified vehicles", None, align="center"))


def render_product_collection_grid(props, style, rec):
    products = props.get("products") or [
        {"title": "Aurora Lamp", "price": "$89", "category": "Lighting", "image": "/generated/product-1.jpg"},
        {"title": "Drift Chair", "price": "$240", "category": "Seating", "image": "/generated/product-2.jpg"},
        {"title": "Pebble Speaker", "price": "$129", "category": "Audio", "image": "/generated/product-3.jpg"},
        {"title": "Field Bottle", "price": "$28", "category": "Outdoor", "image": "/generated/product-4.jpg"},
        {"title": "Loom Throw", "price": "$64", "category": "Home", "image": "/generated/product-5.jpg"},
        {"title": "Trace Watch", "price": "$199", "category": "Wearables", "image": "/generated/product-6.jpg"},
    ]
    body = _grid(_many("product card", products, style), cols="grid-cols-2 lg:grid-cols-3")
    return _shell(style, body, _header(style, "Collection", "Explore the full range", None))


def render_restaurant_menu_preview(props, style, rec):
    tabs = "".join(render_block("tab item", {"label": l, "selected": i == 0}, style)
                   for i, l in enumerate(["Starters", "Mains", "Desserts", "Drinks"]))
    dishes = _many("restaurant menu card", props.get("dishes") or [
        {"name": "Charred Citrus Salmon", "price": "$24", "description": "Wild-caught fillet, charred citrus, herb oil.", "tags": ["Gluten-free"]},
        {"name": "Wild Mushroom Risotto", "price": "$19", "description": "Slow-stirred arborio, thyme, aged cheese.", "tags": ["Vegetarian"]},
        {"name": "Harvest Grain Bowl", "price": "$16", "description": "Roasted vegetables, seeds, tahini drizzle.", "tags": ["Vegan", "Chef's pick"]},
        {"name": "Espresso Tart", "price": "$11", "description": "Dark chocolate, sea salt, crisp pastry.", "tags": ["Dessert"]},
    ], style)
    body = (
        f'<div className="mt-8 flex flex-wrap gap-1 border-b {style["border"]}">{tabs}</div>'
        f'<div className="mt-8 grid gap-5 sm:grid-cols-2">{dishes}</div>'
    )
    return _shell(style, body, _header(style, "Menu", "A taste of the kitchen", None))


def render_reservation_section(props, style, rec):
    fields = (
        render_block("form field", {"label": "Name", "placeholder": "Your name"}, style)
        + render_block("form field", {"label": "Party size", "type": "number", "placeholder": "2"}, style)
        + render_block("form field", {"label": "Date & time", "type": "datetime-local", "helper": "We hold tables for 15 minutes."}, style)
    )
    cta = render_block("cta button group", {"primary": "Reserve a table", "secondary": "View hours"}, style)
    hours = "".join(
        f'<li className="flex items-center justify-between text-sm {style["muted"]}"><span>{d}</span><span>{h}</span></li>'
        for d, h in [("Mon–Thu", "5:00 – 10:00 PM"), ("Fri–Sat", "5:00 PM – 12:00 AM"), ("Sun", "4:00 – 9:00 PM")]
    )
    body = (
        f'<div className="grid gap-10 lg:grid-cols-2">'
        f'<div className="{style["card"]} space-y-4 p-5 sm:p-6">{fields}<div className="pt-2">{cta}</div></div>'
        f'<div className="{style["card"]} p-5 sm:p-6"><h3 className="text-base font-semibold {style["heading"]}">Opening hours</h3>'
        f'<ul className="mt-4 space-y-2">{hours}</ul>'
        f'<p className="mt-4 inline-flex items-center gap-1 text-sm {style["muted"]}">{_icon("pin", "h-4 w-4")}14 Harbor Lane, Old Town</p></div></div>'
    )
    return _shell(style, body, _header(style, "Reservations", "Book your table", None), alt=True)


def render_travel_destination_hero(props, style, rec):
    title = _t(props.get("title"), "Find your next escape", 80)
    box = render_block("search box", {"placeholder": "Where to? Try a city or region", "label": "Search destinations"}, style)
    chips = "".join(_chip(c, style, "pin") for c in ["Beaches", "Mountains", "Cities", "Wine country"])
    panel = render_block("image panel", {"image": "/generated/travel-hero.jpg", "caption": "Curated stays worldwide"}, style)
    body = (
        f'<div className="grid items-center gap-10 lg:grid-cols-2">'
        f'<div>{_chip("New routes for 2024", style, "spark")}'
        f'<h1 className="mt-4 text-4xl font-bold tracking-tight {style["heading"]} sm:text-5xl lg:text-6xl">{title}</h1>'
        f'<p className="mt-4 text-lg {style["muted"]}">Hand-picked destinations, flexible dates, and trusted local guides.</p>'
        f'<div className="mt-6">{box}</div>'
        f'<div className="mt-4 flex flex-wrap gap-2">{chips}</div></div>'
        f'<div>{panel}</div></div>'
    )
    return _shell(style, body, pad="py-16 sm:py-20 lg:py-24")


def render_itinerary_cards(props, style, rec):
    packages = _many("travel package card", props.get("packages") or [
        {"name": "Coastal Escape · 5 Nights", "price": "$1,290", "region": "Amalfi Coast", "image": "/generated/travel-1.jpg"},
        {"name": "Alpine Trails · 7 Nights", "price": "$1,740", "region": "Dolomites", "image": "/generated/travel-2.jpg"},
        {"name": "Desert Lights · 4 Nights", "price": "$980", "region": "Atlas Range", "image": "/generated/travel-3.jpg"},
    ], style)
    body = _grid(packages, cols="sm:grid-cols-2 lg:grid-cols-3")
    return _shell(style, body, _header(style, "Itineraries", "Trips designed around you", None))


def render_property_search(props, style, rec):
    box = render_block("search box", {"placeholder": "City, neighborhood, or ZIP", "label": "Search properties"}, style)
    chips = "".join(_chip(c, style) for c in ["For sale", "For rent", "New", "Open house", "Reduced"])
    listings = _many("property card", props.get("properties") or [
        {"title": "Sunlit 3-Bed Townhouse", "price": "$615,000", "address": "Maple Heights", "image": "/generated/property-1.jpg"},
        {"title": "Modern Loft Downtown", "price": "$430,000", "address": "River District", "image": "/generated/property-2.jpg"},
        {"title": "Garden Cottage", "price": "$389,000", "address": "Elmwood", "image": "/generated/property-3.jpg"},
    ], style)
    body = (
        f'<div className="mx-auto max-w-3xl">{box}'
        f'<div className="mt-4 flex flex-wrap justify-center gap-2">{chips}</div></div>{_grid(listings)}'
    )
    return _shell(style, body, _header(style, "Property search", "Find your next home", None, align="center"))


def render_property_listing_grid(props, style, rec):
    listings = _many("property card", props.get("properties") or [
        {"title": "Sunlit 3-Bed Townhouse", "price": "$615,000", "address": "Maple Heights", "image": "/generated/property-1.jpg"},
        {"title": "Modern Loft Downtown", "price": "$430,000", "address": "River District", "image": "/generated/property-2.jpg"},
        {"title": "Garden Cottage", "price": "$389,000", "address": "Elmwood", "image": "/generated/property-3.jpg"},
        {"title": "Hillside Retreat", "price": "$720,000", "address": "North Ridge", "image": "/generated/property-4.jpg"},
        {"title": "Courtyard Apartment", "price": "$295,000", "address": "Old Town", "image": "/generated/property-5.jpg"},
        {"title": "Lakeview Bungalow", "price": "$540,000", "address": "Cedar Bay", "image": "/generated/property-6.jpg"},
    ], style)
    body = _grid(listings)
    return _shell(style, body, _header(style, "Listings", "Homes you'll love", None))


def render_fitness_program_cards(props, style, rec):
    programs = props.get("programs") or [
        {"title": "Strength 101", "description": "Build a foundation with progressive lifting.", "icon": "bolt", "points": ["3x / week", "All levels"]},
        {"title": "HIIT Burn", "description": "High-intensity intervals for fast results.", "icon": "spark", "points": ["30-min sessions", "Equipment-free"]},
        {"title": "Mobility & Flow", "description": "Improve range, balance, and recovery.", "icon": "heart", "points": ["Low impact", "Guided"]},
    ]
    body = _grid(_many("service card", programs, style))
    return _shell(style, body, _header(style, "Programs", "Train with a plan that fits", None))


def render_trainer_profile_section(props, style, rec):
    trainers = _many("trainer card", props.get("trainers") or [
        {"name": "Maya Coleman", "discipline": "Strength & Conditioning", "image": "/generated/trainer-1.jpg"},
        {"name": "Theo Banks", "discipline": "Mobility & Recovery", "image": "/generated/trainer-2.jpg"},
        {"name": "Ruby Hart", "discipline": "HIIT & Cardio", "image": "/generated/trainer-3.jpg"},
        {"name": "Owen Diaz", "discipline": "Endurance Coaching", "image": "/generated/trainer-4.jpg"},
    ], style)
    body = _grid(trainers, cols="sm:grid-cols-2 lg:grid-cols-4")
    return _shell(style, body, _header(style, "Coaches", "Meet your trainers", None, align="center"), alt=True)


def render_course_catalog(props, style, rec):
    tabs = "".join(render_block("tab item", {"label": l, "selected": i == 0}, style)
                   for i, l in enumerate(["All", "Design", "Development", "Business"]))
    courses = _many("course card", props.get("courses") or [
        {"title": "Foundations of UX Research", "level": "Beginner", "instructor": "Dr. Lena Park", "lessons": "24 lessons", "image": "/generated/course-1.jpg"},
        {"title": "Modern Frontend Patterns", "level": "Intermediate", "instructor": "Sam Okoye", "lessons": "32 lessons", "image": "/generated/course-2.jpg"},
        {"title": "Product Strategy Essentials", "level": "All levels", "instructor": "Mara Liu", "lessons": "18 lessons", "image": "/generated/course-3.jpg"},
    ], style)
    body = (
        f'<div className="mt-8 flex flex-wrap gap-1 border-b {style["border"]}">{tabs}</div>{_grid(courses)}'
    )
    return _shell(style, body, _header(style, "Catalog", "Learn something new", None))


def render_learning_path_section(props, style, rec):
    steps = _many("timeline item", [
        {"time": "Module 1", "title": "Fundamentals", "description": "Core concepts and vocabulary."},
        {"time": "Module 2", "title": "Hands-on practice", "description": "Build real projects step by step."},
        {"time": "Module 3", "title": "Capstone", "description": "Apply everything to a portfolio piece."},
    ], style)
    courses = _many("course card", [
        {"title": "Path: UX Designer", "level": "Track", "instructor": "6 courses", "lessons": "84 lessons", "image": "/generated/course-1.jpg"},
        {"title": "Path: Frontend Engineer", "level": "Track", "instructor": "7 courses", "lessons": "96 lessons", "image": "/generated/course-2.jpg"},
    ], style)
    body = (
        f'<div className="mt-10 grid gap-10 lg:grid-cols-2">'
        f'<ol className="space-y-8">{steps}</ol>'
        f'<div className="grid gap-5">{courses}</div></div>'
    )
    return _shell(style, body, _header(style, "Learning paths", "A guided route to mastery", None))


def render_ai_api_panel(props, style, rec):
    lines = [
        ("$ ", "curl -X POST /v1/agents/run \\"),
        ("  ", "-H authorization: Bearer ... \\"),
        ("  ", "-d task=summarize -d input=thread"),
        ("", ""),
        ("→ ", "status: ok · latency: 240ms"),
        ("→ ", "tokens: 1,284 · model: fast-1"),
    ]
    code = "".join(
        f'<span className="block"><span className="{style["accent_text"]}">{_t(p, "", 8)}</span>{_t(t, "", 80)}</span>'
        for p, t in lines
    )
    panel = (
        f'<div className="{style["card"]} overflow-hidden font-mono">'
        f'<div className="flex items-center gap-1.5 border-b {style["border"]} px-4 py-3">'
        f'<span className="h-3 w-3 rounded-full bg-rose-400"></span>'
        f'<span className="h-3 w-3 rounded-full bg-amber-400"></span>'
        f'<span className="h-3 w-3 rounded-full bg-emerald-400"></span>'
        f'<span className="ml-2 text-xs {style["muted"]}">api.session</span></div>'
        f'<pre className="overflow-x-auto px-4 py-4 text-xs leading-relaxed {style["heading"]} sm:text-sm">{code}</pre></div>'
    )
    feats = render_block("feature card", {"title": "One API, every model", "description": "Route requests to the right model with a single call.", "icon": "spark"}, style) \
        + render_block("feature card", {"title": "Built-in observability", "description": "Trace latency, tokens, and cost out of the box.", "icon": "bolt"}, style)
    body = (
        f'<div className="grid items-center gap-10 lg:grid-cols-2">'
        f'<div>{_eyebrow("Developer API", style)}'
        f'<h2 className="mt-2 text-2xl font-bold tracking-tight {style["heading"]} sm:text-3xl lg:text-4xl">Ship AI features in minutes</h2>'
        f'<p className="mt-3 text-base {style["muted"]} sm:text-lg">A clean, typed API with predictable latency and transparent usage.</p>'
        f'<div className="mt-6 grid gap-4 sm:grid-cols-2">{feats}</div></div>'
        f'<div>{panel}</div></div>'
    )
    return _shell(style, body)


def render_developer_workflow_section(props, style, rec):
    steps = _many("timeline item", [
        {"time": "Commit", "title": "Push your change", "description": "Trigger pipelines automatically on every commit."},
        {"time": "Build", "title": "Run checks", "description": "Tests, lint, and types run in parallel."},
        {"time": "Ship", "title": "Deploy safely", "description": "Preview, approve, and roll out with confidence."},
    ], style)
    feats = render_block("feature card", {"title": "Fast feedback", "description": "Catch issues before they reach production.", "icon": "bolt"}, style) \
        + render_block("feature card", {"title": "Repeatable", "description": "The same workflow for every project and team.", "icon": "check"}, style)
    body = (
        f'<div className="mt-10 grid gap-10 lg:grid-cols-2">'
        f'<ol className="space-y-8">{steps}</ol>'
        f'<div className="grid gap-4">{feats}</div></div>'
    )
    return _shell(style, body, _header(style, "Workflow", "From commit to production", None), alt=True)


def render_fintech_transaction_preview(props, style, rec):
    metrics = _many("dashboard metric card", [
        {"label": "Balance", "value": "$24,180", "trend": "+2.4%"},
        {"label": "Incoming", "value": "$6,420", "trend": "+12%"},
        {"label": "Outgoing", "value": "$3,910", "trend": "-4%", "direction": "down"},
    ], style)
    stat = render_block("stat card", {"value": "0.0%", "label": "Failed payments", "delta": "Last 30 days"}, style)
    table = render_block("table preview", {"title": "Transactions", "headers": ["Date", "Merchant", "Status", "Amount"]}, style)
    body = (
        f'<div className="mt-10 grid gap-5 sm:grid-cols-3">{metrics}</div>'
        f'<div className="mt-5 grid gap-5 lg:grid-cols-[0.8fr_1.2fr]">{stat}{table}</div>'
    )
    return _shell(style, body, _header(style, "Payments", "Move money with confidence", None))


SECTION_RENDERERS = {
    "hero": render_hero,
    "navbar": render_navbar,
    "feature grid": render_feature_grid,
    "service grid": render_service_grid,
    "stats strip": render_stats_strip,
    "trust badges": render_trust_badges,
    "product showcase": render_product_showcase,
    "pricing": render_pricing,
    "testimonials": render_testimonials,
    "faq": render_faq,
    "cta banner": render_cta_banner,
    "footer": render_footer,
    "gallery": render_gallery,
    "timeline": render_timeline,
    "booking flow": render_booking_flow,
    "search panel": render_search_panel,
    "dashboard preview": render_dashboard_preview,
    "app preview": render_app_preview,
    "portal preview": render_portal_preview,
    "report preview": render_report_preview,
    "team section": render_team_section,
    "department grid": render_department_grid,
    "doctor search": render_doctor_search,
    "appointment cta": render_appointment_cta,
    "patient portal": render_patient_portal,
    "lab report preview": render_lab_report_preview,
    "vehicle inventory grid": render_vehicle_inventory_grid,
    "product collection grid": render_product_collection_grid,
    "restaurant menu preview": render_restaurant_menu_preview,
    "reservation section": render_reservation_section,
    "travel destination hero": render_travel_destination_hero,
    "itinerary cards": render_itinerary_cards,
    "property search": render_property_search,
    "property listing grid": render_property_listing_grid,
    "fitness program cards": render_fitness_program_cards,
    "trainer profile section": render_trainer_profile_section,
    "course catalog": render_course_catalog,
    "learning path section": render_learning_path_section,
    "ai api panel": render_ai_api_panel,
    "developer workflow section": render_developer_workflow_section,
    "fintech transaction preview": render_fintech_transaction_preview,
}


# --------------------------------------------------------------------------- #
# Record factory + build
# --------------------------------------------------------------------------- #

_PREVIEWS = {
    "hero": "Split hero: headline, supporting copy, dual CTA, trust row, and a captioned media panel.",
    "navbar": "Responsive top bar with brand mark, primary links, auth actions, and a mobile menu toggle.",
    "feature grid": "Three-column grid of icon feature cards with a centered section header.",
    "service grid": "Service cards with bulleted inclusions and a per-card call to action.",
    "stats strip": "Compact four-up metric strip for headline numbers and deltas.",
    "trust badges": "Centered trust badges over a responsive partner logo cloud.",
    "product showcase": "Media-led product cards with price, rating, and add action.",
    "pricing": "Three-tier pricing with a highlighted recommended plan.",
    "testimonials": "Social-proof grid of star-rated quotes with author identity.",
    "faq": "Single-column accordion of common questions.",
    "cta banner": "Full-width gradient conversion banner with dual CTA.",
    "footer": "Multi-column site footer with brand blurb and legal row.",
    "gallery": "Responsive media gallery with caption overlays.",
    "timeline": "Two-column vertical process timeline.",
    "booking flow": "Three-step booking with a form panel and confirmation CTA.",
    "search panel": "Prominent search with quick filter chips.",
    "dashboard preview": "Metric cards over a chart and recent-activity table.",
    "app preview": "Tabbed product preview with metrics and a media panel.",
    "portal preview": "Self-service portal with metrics, records table, and actions.",
    "report preview": "Summary stats with an exportable statement table.",
    "team section": "Four-up team profile grid.",
    "department grid": "Department directory built from service cards.",
    "doctor search": "Doctor finder with search, specialty chips, and result cards.",
    "appointment cta": "Appointment conversion block with trust reassurance.",
    "patient portal": "Patient portal with visit metrics, history table, and quick actions.",
    "lab report preview": "Readable lab report with status badges, summary stats, and results table.",
    "vehicle inventory grid": "Searchable certified-vehicle inventory grid.",
    "product collection grid": "Full product collection grid with categories.",
    "restaurant menu preview": "Tabbed menu with dish cards and dietary tags.",
    "reservation section": "Table reservation form paired with opening hours and location.",
    "travel destination hero": "Immersive destination hero with a search and theme chips.",
    "itinerary cards": "Itinerary package cards with region and price.",
    "property search": "Property search with filters and listing results.",
    "property listing grid": "Three-column property listing grid.",
    "fitness program cards": "Program cards describing schedule and level.",
    "trainer profile section": "Trainer profile grid with disciplines.",
    "course catalog": "Tabbed course catalog with level and instructor.",
    "learning path section": "Guided learning path timeline beside track cards.",
    "ai api panel": "Developer API section with a faux console panel and feature cards.",
    "developer workflow section": "Commit-to-production workflow timeline with feature cards.",
    "fintech transaction preview": "Account metrics with a transactions table.",
}

_SECTION_A11Y = (
    "Landmark/semantic regions, a single section heading hierarchy, descriptive alt "
    "text on imagery, keyboard-reachable controls, and visible focus states."
)


def _make_section_record(stype, family, variant, serial, local_index):
    fam = pc._FAMILIES.get(family, {})
    quality = min(99, 85 + ((serial + local_index) % 13))
    type_domains = SECTION_TYPE_DOMAINS.get(stype, [])
    source = type_domains if type_domains else fam.get("domains", [])
    domain_fit = []
    for d in source:
        if d not in domain_fit:
            domain_fit.append(d)
    fn = SECTION_RENDERERS[stype]
    label = pc._FAMILY_LABELS.get(family, family)
    deps = SECTION_DEPENDENCIES.get(stype, [])
    return {
        "section_id": f"sec-{serial:04d}",
        "name": f"{label} {stype.title()} · {variant} #{local_index + 1:02d}",
        "section_type": stype,
        "semantic_group": semantic_group_for(stype),
        "page_type": _page_type(stype),
        "domain_fit": domain_fit,
        "visual_family": family,
        "variant": variant,
        "quality_score": quality,
        "required_props": [],
        "optional_props": _section_props(stype),
        "component_dependencies": list(deps),
        "layout_tags": list(_LAYOUT_TAGS.get(stype, ["section", "responsive"])),
        "responsive_support": ["mobile", "tablet", "desktop"],
        "accessibility_notes": _SECTION_A11Y,
        "code_ref": f"app/professional_sections.py::{fn.__name__}",
        "render_function_name": fn.__name__,
        "preview_description": _PREVIEWS.get(stype, f"{label} {stype} section."),
        "selection_summary": (
            f"{label} {stype} ({variant}) — fits {', '.join(domain_fit[:3]) or 'general'} pages; "
            f"composes {', '.join(deps[:3]) or 'native markup'}."
        ),
    }


def _section_props(stype):
    return {
        "hero": ["title", "subtitle", "primary", "secondary", "image"],
        "navbar": ["brand", "links"],
        "feature grid": ["features"],
        "pricing": ["plans"],
        "doctor search": ["doctors"],
        "vehicle inventory grid": ["vehicles"],
        "property listing grid": ["properties"],
        "restaurant menu preview": ["dishes"],
        "course catalog": ["courses"],
    }.get(stype, ["title", "subtitle"])


def _build_sections():
    records, serial = [], 1
    counters = Counter()
    for stype in SECTION_TYPES:
        for family in VISUAL_FAMILIES:
            for variant in SECTION_VARIANTS:
                records.append(_make_section_record(stype, family, variant, serial, counters[stype]))
                counters[stype] += 1
                serial += 1
    return records


SECTIONS = _build_sections()
_SECTION_INDEX = {s["section_id"]: s for s in SECTIONS}

_SECTION_BLOB_FIELDS = (
    "name", "section_type", "page_type", "visual_family", "domain_fit",
    "layout_tags", "preview_description", "selection_summary",
)


# --------------------------------------------------------------------------- #
# Public API (section half)
# --------------------------------------------------------------------------- #

def get_all_sections() -> list:
    return copy.deepcopy(SECTIONS)


def get_section_by_id(section_id: str):
    record = _SECTION_INDEX.get(str(section_id or "").strip())
    return copy.deepcopy(record) if record else None


def get_sections_by_type(section_type: str, family: str = None, max_results: int = 50) -> list:
    out = [
        s for s in SECTIONS
        if s["section_type"] == section_type and (family is None or s["visual_family"] == family)
    ]
    return copy.deepcopy(out[:max_results])


def search_sections(prompt: str, page_type: str = None, max_results: int = 50) -> list:
    return search_records(
        SECTIONS, prompt, max_results,
        blob_fields=_SECTION_BLOB_FIELDS, type_field="section_type",
        page_type=page_type, type_domains_map=SECTION_TYPE_DOMAINS,
    )


def render_section(section_id: str, props: dict = None) -> str:
    record = _SECTION_INDEX.get(str(section_id or "").strip())
    if not record:
        return f'<section className="py-12 text-center text-sm text-slate-500">Unknown section: {_t(section_id, "?", 40)}</section>'
    style = family_style(record["visual_family"], record.get("variant", "soft"))
    style["section_attrs"] = (
        f'data-section-type="{record["section_type"]}" '
        f'data-visual-family="{record["visual_family"]}" '
        f'data-section-id="{record["section_id"]}"'
    )
    fn = SECTION_RENDERERS[record["section_type"]]
    return fn(dict(props or {}), style, record)


def summarize_sections(records=None) -> dict:
    records = records if records is not None else SECTIONS
    return {
        "total": len(records),
        "section_types": sorted({r["section_type"] for r in records}),
        "page_types": sorted({r["page_type"] for r in records}),
        "visual_families": sorted({r["visual_family"] for r in records}),
        "domains": sorted({d for r in records for d in r.get("domain_fit", [])}),
        "type_counts": dict(Counter(r["section_type"] for r in records)),
        "family_counts": dict(Counter(r["visual_family"] for r in records)),
    }


SECTION_REQUIRED_FIELDS = {
    "section_id", "name", "section_type", "page_type", "domain_fit", "visual_family",
    "quality_score", "required_props", "optional_props", "component_dependencies",
    "layout_tags", "responsive_support", "accessibility_notes", "code_ref",
    "render_function_name", "preview_description", "selection_summary",
}


def validate_sections(min_count: int = 1000) -> dict:
    errors = []
    records = SECTIONS
    if len(records) < min_count:
        errors.append(f"expected >= {min_count} sections, found {len(records)}")
    ids = [r["section_id"] for r in records]
    if len(set(ids)) != len(ids):
        errors.append("section ids are not unique")
    types = {r["section_type"] for r in records}
    if len(types) < 20:
        errors.append(f"expected >= 20 section types, found {len(types)}")
    families = {r["visual_family"] for r in records}
    if len(families) < 15:
        errors.append(f"expected >= 15 visual families, found {len(families)}")
    domains = {d for r in records for d in r.get("domain_fit", [])}
    if len(domains) < 15:
        errors.append(f"expected >= 15 domains, found {len(domains)}")

    for record in records:
        missing = SECTION_REQUIRED_FIELDS - set(record)
        if missing:
            errors.append(f"{record.get('section_id')} missing {sorted(missing)}")
        if not isinstance(record.get("quality_score"), (int, float)) or record.get("quality_score", 0) < 80:
            errors.append(f"{record.get('section_id')} quality_score below 80")
        for field in ("name", "selection_summary", "preview_description", "accessibility_notes"):
            for issue in scan_text_for_violations(record.get(field, "")):
                errors.append(f"{record.get('section_id')} {field}: {issue}")

    # Render smoke test: one representative per section type must render valid JSX.
    for stype in SECTION_TYPES:
        sample = next((r for r in records if r["section_type"] == stype), None)
        if not sample:
            errors.append(f"no record for section type {stype}")
            continue
        jsx = render_section(sample["section_id"], {})
        if not (isinstance(jsx, str) and jsx.lstrip().startswith("<") and "className=" in jsx):
            errors.append(f"{stype} did not render valid JSX")
        for issue in scan_jsx_for_violations(jsx):
            errors.append(f"{stype} render: {issue}")
    return {
        "ok": not errors,
        "errors": errors,
        "section_count": len(records),
        "type_count": len(types),
        "family_count": len(families),
        "domain_count": len(domains),
        "page_types": sorted({r["page_type"] for r in records}),
    }
