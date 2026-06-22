"""Browser-visible visual recipe pools for Design DNA.

Recipes are abstract implementation choices, not copied templates. They map
Design DNA vocabulary onto concrete Tailwind/JSX structure: hero layouts, nav
shapes, card treatments, section wrappers, CTA shapes, and footer layouts.
"""
from __future__ import annotations

import re


VISUAL_FAMILIES = [
    "healthcare-clinical",
    "automotive-showroom",
    "product-commerce",
    "developer-console",
    "learning-editorial",
    "restaurant-reservation",
    "travel-destination",
    "real-estate-listings",
    "fitness-coaching",
    "creative-portfolio",
    "finance-trust",
    "operations-console",
    "service-trust",
]


def _recipe(rid, name, families, layout="", **extra):
    data = {"id": rid, "name": name, "families": list(families), "layout": layout}
    data.update(extra)
    return data


HERO_RECIPES = [
    _recipe("hero-clinical-trust-search", "Clinical trust search hero", ["healthcare-clinical"], "split-search",
            variant="search-booking", first_screen="left trust copy + right appointment search panel",
            section_class="border-b border-sky-100 bg-gradient-to-br from-white via-sky-50 to-blue-50",
            h1_class="font-display text-4xl font-bold leading-tight md:text-6xl"),
    _recipe("hero-emergency-command", "Emergency command hero", ["healthcare-clinical"], "stats-command",
            variant="stats-first", first_screen="emergency strip + care metrics + portal card",
            section_class="border-b border-rose-100 bg-white"),
    _recipe("hero-patient-portal-stack", "Patient portal card stack", ["healthcare-clinical"], "card-stack",
            variant="card-stack", first_screen="care promise + stacked portal workflow cards",
            section_class="border-b border-cyan-100 bg-cyan-50/70"),
    _recipe("hero-showroom-stage", "Showroom stage hero", ["automotive-showroom", "product-commerce"], "showroom-stage",
            variant="full-image", first_screen="large product stage + inventory action rail",
            section_class="border-b border-neutral-200 bg-white",
            h1_class="font-display text-5xl font-bold leading-none md:text-7xl"),
    _recipe("hero-inventory-search", "Inventory search hero", ["automotive-showroom", "product-commerce"], "search-led",
            variant="search-booking", first_screen="inventory filters + featured listing panel",
            section_class="border-b border-neutral-200 bg-neutral-50"),
    _recipe("hero-product-grid-launch", "Product grid launch hero", ["product-commerce"], "product-grid",
            variant="card-stack", first_screen="commerce headline + product tile grid",
            section_class="border-b border-stone-200 bg-stone-50"),
    _recipe("hero-console-workbench", "Console workbench hero", ["developer-console"], "dashboard-console",
            variant="dashboard-preview", first_screen="dark technical console + API run panel",
            section_class="border-b border-slate-800 bg-slate-950 text-slate-50",
            h1_class="font-display text-4xl font-bold leading-tight text-white md:text-6xl"),
    _recipe("hero-code-terminal", "Code terminal hero", ["developer-console"], "terminal-split",
            variant="dashboard-preview", first_screen="terminal panel + technical CTA rail",
            section_class="border-b border-violet-900/60 bg-slate-950 text-slate-50"),
    _recipe("hero-course-editorial", "Course editorial hero", ["learning-editorial"], "editorial-stack",
            variant="editorial", first_screen="large editorial title + course shelf",
            section_class="border-b border-amber-200 bg-gradient-to-br from-white via-amber-50 to-cyan-50",
            h1_class="font-display text-5xl font-bold leading-tight md:text-7xl"),
    _recipe("hero-learning-path", "Learning path hero", ["learning-editorial"], "path-preview",
            variant="card-stack", first_screen="learning path cards + enrollment CTA",
            section_class="border-b border-cyan-100 bg-white"),
    _recipe("hero-menu-reservation", "Menu reservation hero", ["restaurant-reservation"], "menu-reservation",
            variant="search-booking", first_screen="menu preview + reservation form + hours",
            section_class="border-b border-orange-200 bg-gradient-to-br from-stone-50 via-orange-50 to-rose-50",
            h1_class="font-display text-5xl font-bold leading-none md:text-7xl"),
    _recipe("hero-dining-gallery", "Dining gallery hero", ["restaurant-reservation"], "immersive-gallery",
            variant="full-image", first_screen="warm dining image grid + reserve CTA",
            section_class="border-b border-stone-200 bg-stone-950 text-stone-50",
            h1_class="font-display text-5xl font-bold leading-none text-white md:text-7xl"),
    _recipe("hero-destination-map", "Destination map hero", ["travel-destination"], "destination-map",
            variant="full-image", first_screen="destination title + itinerary cards + map path",
            section_class="border-b border-sky-200 bg-gradient-to-br from-cyan-50 via-white to-amber-50",
            h1_class="font-display text-5xl font-bold leading-none md:text-7xl"),
    _recipe("hero-trip-search", "Trip search hero", ["travel-destination"], "travel-search",
            variant="search-booking", first_screen="trip search bar + package cards",
            section_class="border-b border-teal-100 bg-white"),
    _recipe("hero-property-search", "Property search hero", ["real-estate-listings"], "property-search",
            variant="search-booking", first_screen="property filters + listing cards + agent badge",
            section_class="border-b border-emerald-100 bg-gradient-to-br from-white via-emerald-50 to-stone-50"),
    _recipe("hero-neighborhood-editorial", "Neighborhood editorial hero", ["real-estate-listings"], "neighborhood-editorial",
            variant="editorial", first_screen="neighborhood story + property mosaic",
            section_class="border-b border-stone-200 bg-stone-50"),
    _recipe("hero-fitness-program", "Fitness program hero", ["fitness-coaching"], "program-split",
            variant="card-stack", first_screen="program promise + trainer cards + class CTA",
            section_class="border-b border-lime-200 bg-gradient-to-br from-lime-50 via-white to-emerald-50"),
    _recipe("hero-class-schedule", "Class schedule hero", ["fitness-coaching"], "schedule-first",
            variant="stats-first", first_screen="weekly schedule + program tiles",
            section_class="border-b border-emerald-100 bg-white"),
    _recipe("hero-portfolio-asym", "Asymmetric portfolio hero", ["creative-portfolio"], "asymmetric-editorial",
            variant="editorial", first_screen="oversized statement + staggered case tiles",
            section_class="border-b border-zinc-200 bg-white",
            h1_class="font-display text-6xl font-bold leading-none md:text-8xl"),
    _recipe("hero-finance-metrics", "Finance metrics hero", ["finance-trust", "operations-console", "service-trust"], "metrics-board",
            variant="stats-first", first_screen="metric cards + secure dashboard preview",
            section_class="border-b border-emerald-100 bg-gradient-to-br from-white via-emerald-50 to-teal-50"),
]


NAV_RECIPES = [
    _recipe("nav-clinical-utility", "Clinical utility nav", ["healthcare-clinical"], "utility", variant="utility bar", preset="accent-top"),
    _recipe("nav-centered-trust", "Centered trust nav", ["healthcare-clinical", "learning-editorial", "service-trust"], "centered", variant="centered topnav", preset="blur"),
    _recipe("nav-commerce-action", "Commerce action nav", ["automotive-showroom", "product-commerce"], "action", variant="action topnav", preset="accent-solid"),
    _recipe("nav-floating-gallery", "Floating gallery nav", ["travel-destination", "creative-portfolio", "restaurant-reservation"], "floating", variant="floating nav", preset="floating"),
    _recipe("nav-console-utility", "Console utility nav", ["developer-console", "operations-console"], "utility", variant="utility bar", preset="dark"),
    _recipe("nav-course-catalog", "Course catalog nav", ["learning-editorial"], "centered", variant="centered topnav", preset="pill"),
    _recipe("nav-booking-action", "Booking action nav", ["restaurant-reservation", "fitness-coaching"], "action", variant="action topnav", preset="tinted"),
    _recipe("nav-property-search", "Property search nav", ["real-estate-listings"], "action", variant="action topnav", preset="blur"),
    _recipe("nav-sidebar-command", "Sidebar command nav", ["operations-console", "developer-console"], "sidebar", variant="sidebar", preset="tinted"),
    _recipe("nav-minimal-editorial", "Minimal editorial nav", ["creative-portfolio", "finance-trust"], "minimal", variant="centered topnav", preset="minimal"),
]


SECTION_RECIPES = [
    _recipe("section-clinical-band", "Clinical trust band", ["healthcare-clinical"], "trust-band",
            section_class="bg-white", grid_class="grid gap-5 sm:grid-cols-2 lg:grid-cols-3"),
    _recipe("section-emergency-strip", "Emergency strip", ["healthcare-clinical"], "alert-band",
            section_class="border-y border-rose-100 bg-rose-50/70", grid_class="grid gap-4 md:grid-cols-[1.2fr_0.8fr]"),
    _recipe("section-portal-preview", "Portal preview", ["healthcare-clinical", "developer-console", "operations-console"], "preview",
            section_class="bg-slate-50", grid_class="grid gap-6 lg:grid-cols-2"),
    _recipe("section-showroom-gallery", "Showroom gallery", ["automotive-showroom", "product-commerce"], "gallery",
            section_class="bg-white", grid_class="grid gap-5 sm:grid-cols-2 lg:grid-cols-4"),
    _recipe("section-finance-options", "Finance options", ["automotive-showroom", "finance-trust"], "comparison",
            section_class="border-y border-neutral-200 bg-neutral-50", grid_class="grid gap-5 md:grid-cols-3"),
    _recipe("section-product-collection", "Product collection", ["product-commerce"], "collection",
            section_class="bg-stone-50", grid_class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"),
    _recipe("section-console-grid", "Console grid", ["developer-console"], "console-grid",
            section_class="border-y border-slate-800 bg-slate-900 text-slate-50", grid_class="grid gap-4 md:grid-cols-2 lg:grid-cols-3"),
    _recipe("section-api-timeline", "API timeline", ["developer-console"], "timeline",
            section_class="bg-slate-950 text-slate-50", grid_class="grid gap-5"),
    _recipe("section-course-shelf", "Course shelf", ["learning-editorial"], "media-shelf",
            section_class="bg-amber-50", grid_class="grid gap-5 sm:grid-cols-2 lg:grid-cols-3"),
    _recipe("section-learning-path", "Learning path", ["learning-editorial"], "path",
            section_class="border-y border-cyan-100 bg-white", grid_class="grid gap-5 md:grid-cols-4"),
    _recipe("section-menu-preview", "Menu preview", ["restaurant-reservation"], "menu-grid",
            section_class="bg-stone-50", grid_class="grid gap-5 sm:grid-cols-2 lg:grid-cols-3"),
    _recipe("section-hours-location", "Hours location block", ["restaurant-reservation"], "hours-location",
            section_class="border-y border-orange-200 bg-orange-50/80", grid_class="grid gap-5 md:grid-cols-[0.8fr_1.2fr]"),
    _recipe("section-chef-gallery", "Chef and food gallery", ["restaurant-reservation"], "image-gallery",
            section_class="bg-stone-950 text-stone-50", grid_class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"),
    _recipe("section-destination-gallery", "Destination gallery", ["travel-destination"], "destination-gallery",
            section_class="bg-cyan-50", grid_class="grid gap-5 sm:grid-cols-2 lg:grid-cols-4"),
    _recipe("section-itinerary", "Itinerary timeline", ["travel-destination"], "itinerary",
            section_class="border-y border-sky-100 bg-white", grid_class="grid gap-5 md:grid-cols-4"),
    _recipe("section-map-panel", "Map location panel", ["travel-destination", "real-estate-listings"], "map-panel",
            section_class="bg-teal-50/80", grid_class="grid gap-5 md:grid-cols-[1fr_1fr]"),
    _recipe("section-listing-grid", "Listing grid", ["real-estate-listings"], "listing-grid",
            section_class="bg-stone-50", grid_class="grid gap-5 sm:grid-cols-2 lg:grid-cols-3"),
    _recipe("section-agent-proof", "Agent proof", ["real-estate-listings"], "agent-proof",
            section_class="border-y border-emerald-100 bg-white", grid_class="grid gap-5 md:grid-cols-[0.9fr_1.1fr]"),
    _recipe("section-neighborhood", "Neighborhood highlights", ["real-estate-listings"], "neighborhood",
            section_class="bg-emerald-50/70", grid_class="grid gap-5 sm:grid-cols-2 lg:grid-cols-4"),
    _recipe("section-program-cards", "Program cards", ["fitness-coaching"], "program-grid",
            section_class="bg-lime-50", grid_class="grid gap-5 sm:grid-cols-2 lg:grid-cols-3"),
    _recipe("section-trainer-profiles", "Trainer profiles", ["fitness-coaching"], "profile-grid",
            section_class="bg-white", grid_class="grid gap-5 sm:grid-cols-2 lg:grid-cols-4"),
    _recipe("section-class-schedule", "Class schedule", ["fitness-coaching"], "schedule",
            section_class="border-y border-lime-200 bg-lime-100/60", grid_class="grid gap-5 md:grid-cols-4"),
    _recipe("section-case-mosaic", "Case mosaic", ["creative-portfolio"], "case-mosaic",
            section_class="bg-zinc-50", grid_class="grid gap-4 md:grid-cols-4"),
    _recipe("section-editorial-proof", "Editorial proof", ["creative-portfolio"], "editorial-proof",
            section_class="border-y border-zinc-200 bg-white", grid_class="grid gap-6 md:grid-cols-[1.4fr_0.6fr]"),
    _recipe("section-finance-ledger", "Finance ledger preview", ["finance-trust"], "ledger",
            section_class="bg-emerald-50", grid_class="grid gap-5 md:grid-cols-3"),
    _recipe("section-security-cards", "Security cards", ["finance-trust", "developer-console"], "security",
            section_class="border-y border-emerald-100 bg-white", grid_class="grid gap-5 md:grid-cols-3"),
    _recipe("section-operations-board", "Operations board", ["operations-console"], "operations-board",
            section_class="bg-indigo-50/70", grid_class="grid gap-5 md:grid-cols-4"),
    _recipe("section-resource-matrix", "Resource matrix", ["operations-console"], "matrix",
            section_class="border-y border-indigo-100 bg-white", grid_class="grid gap-5 lg:grid-cols-4"),
    _recipe("section-service-benefits", "Service benefits", ["service-trust"], "benefits",
            section_class="bg-white", grid_class="grid gap-5 md:grid-cols-3"),
    _recipe("section-faq-accordion", "FAQ accordion", VISUAL_FAMILIES, "faq",
            section_class="bg-muted/30", grid_class="grid gap-4"),
]


CARD_RECIPES = [
    _recipe("card-soft-clinical", "Soft clinical card", ["healthcare-clinical"], "soft",
            className="rounded-3xl border border-sky-100 bg-white p-6 shadow-sm"),
    _recipe("card-care-path", "Care pathway card", ["healthcare-clinical"], "path",
            className="rounded-2xl border-l-4 border-l-blue-500 bg-white p-6 shadow-sm"),
    _recipe("card-vehicle-tile", "Vehicle tile", ["automotive-showroom"], "image",
            className="overflow-hidden rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm"),
    _recipe("card-spec-sheet", "Spec sheet card", ["automotive-showroom", "product-commerce"], "spec",
            className="rounded-none border border-neutral-300 bg-white p-6"),
    _recipe("card-product-frame", "Product frame card", ["product-commerce"], "image",
            className="overflow-hidden rounded-3xl border border-stone-200 bg-white p-5 shadow-md"),
    _recipe("card-console-glass", "Console glass card", ["developer-console"], "glass",
            className="rounded-2xl border border-slate-700 bg-slate-900/80 p-6 shadow-2xl shadow-slate-950/30"),
    _recipe("card-code-panel", "Code panel card", ["developer-console"], "code",
            className="rounded-lg border border-violet-800 bg-slate-950 p-5 font-mono text-sm shadow-xl"),
    _recipe("card-course-media", "Course media card", ["learning-editorial"], "media",
            className="overflow-hidden rounded-3xl border border-amber-200 bg-white p-5 shadow-sm"),
    _recipe("card-lesson-tile", "Lesson tile", ["learning-editorial"], "lesson",
            className="rounded-2xl border border-cyan-100 bg-cyan-50/70 p-6"),
    _recipe("card-menu-item", "Menu item card", ["restaurant-reservation"], "menu",
            className="rounded-3xl border border-orange-200 bg-white p-6 shadow-sm"),
    _recipe("card-reservation-slip", "Reservation slip", ["restaurant-reservation"], "booking",
            className="rounded-none border-y-4 border-y-rose-600 bg-stone-50 p-6 shadow-lg"),
    _recipe("card-trip-postcard", "Trip postcard card", ["travel-destination"], "image",
            className="overflow-hidden rounded-[2rem] border border-sky-100 bg-white p-5 shadow-lg shadow-sky-100"),
    _recipe("card-itinerary-pass", "Itinerary pass", ["travel-destination"], "pass",
            className="rounded-2xl border border-dashed border-teal-300 bg-white p-6"),
    _recipe("card-listing", "Property listing card", ["real-estate-listings"], "listing",
            className="overflow-hidden rounded-2xl border border-stone-200 bg-white p-5 shadow-sm"),
    _recipe("card-agent", "Agent card", ["real-estate-listings"], "profile",
            className="rounded-3xl border border-emerald-100 bg-white p-6 shadow-md"),
    _recipe("card-program", "Program card", ["fitness-coaching"], "program",
            className="rounded-3xl border border-lime-200 bg-white p-6 shadow-sm"),
    _recipe("card-trainer", "Trainer card", ["fitness-coaching"], "profile",
            className="overflow-hidden rounded-[1.75rem] border border-emerald-100 bg-white p-5 shadow-md"),
    _recipe("card-case-study", "Case study tile", ["creative-portfolio"], "case",
            className="rounded-none border border-zinc-300 bg-white p-6 shadow-lg"),
    _recipe("card-ledger-stat", "Ledger stat card", ["finance-trust", "operations-console"], "stat",
            className="rounded-2xl border border-emerald-100 bg-white p-6 ring-1 ring-emerald-100"),
    _recipe("card-service-panel", "Service panel card", ["service-trust"], "panel",
            className="rounded-2xl border bg-white p-6 shadow-sm"),
]


CTA_RECIPES = [
    _recipe("cta-clinical-dual", "Clinical dual CTA", ["healthcare-clinical"], "dual",
            primary_class="rounded-xl bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-sm hover:bg-blue-700",
            secondary_class="rounded-xl border border-sky-200 bg-white px-6 py-3 text-sm font-semibold text-slate-900"),
    _recipe("cta-commerce-pill", "Commerce pill CTA", ["automotive-showroom", "product-commerce"], "pill",
            primary_class="rounded-full bg-neutral-950 px-7 py-3 text-sm font-semibold text-white",
            secondary_class="rounded-full border border-neutral-300 bg-white px-7 py-3 text-sm font-semibold text-neutral-950"),
    _recipe("cta-console-run", "Console run CTA", ["developer-console"], "technical",
            primary_class="rounded-lg bg-violet-500 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-950/30",
            secondary_class="rounded-lg border border-slate-700 bg-slate-900 px-6 py-3 text-sm font-semibold text-slate-100"),
    _recipe("cta-course-enroll", "Course enroll CTA", ["learning-editorial"], "soft",
            primary_class="rounded-2xl bg-cyan-700 px-6 py-3 text-sm font-semibold text-white",
            secondary_class="rounded-2xl border border-amber-300 bg-white px-6 py-3 text-sm font-semibold text-slate-900"),
    _recipe("cta-reserve-table", "Reserve table CTA", ["restaurant-reservation"], "warm",
            primary_class="rounded-full bg-rose-700 px-7 py-3 text-sm font-semibold text-white shadow-md",
            secondary_class="rounded-full border border-orange-300 bg-white px-7 py-3 text-sm font-semibold text-stone-950"),
    _recipe("cta-plan-trip", "Plan trip CTA", ["travel-destination"], "fresh",
            primary_class="rounded-full bg-teal-700 px-7 py-3 text-sm font-semibold text-white shadow-md",
            secondary_class="rounded-full border border-sky-200 bg-white px-7 py-3 text-sm font-semibold text-slate-950"),
    _recipe("cta-book-tour", "Book tour CTA", ["real-estate-listings"], "trust",
            primary_class="rounded-xl bg-emerald-700 px-6 py-3 text-sm font-semibold text-white",
            secondary_class="rounded-xl border border-emerald-200 bg-white px-6 py-3 text-sm font-semibold text-stone-950"),
    _recipe("cta-start-plan", "Start plan CTA", ["fitness-coaching"], "energy",
            primary_class="rounded-full bg-lime-600 px-7 py-3 text-sm font-semibold text-slate-950 shadow-md",
            secondary_class="rounded-full border border-lime-300 bg-white px-7 py-3 text-sm font-semibold text-slate-950"),
    _recipe("cta-project-brief", "Project brief CTA", ["creative-portfolio"], "editorial",
            primary_class="rounded-none bg-fuchsia-600 px-6 py-3 text-sm font-semibold text-white",
            secondary_class="rounded-none border border-zinc-300 bg-white px-6 py-3 text-sm font-semibold text-zinc-950"),
    _recipe("cta-secure-demo", "Secure demo CTA", ["finance-trust", "operations-console", "service-trust"], "trust",
            primary_class="rounded-xl bg-emerald-700 px-6 py-3 text-sm font-semibold text-white",
            secondary_class="rounded-xl border border-emerald-200 bg-white px-6 py-3 text-sm font-semibold text-slate-900"),
]


FOOTER_RECIPES = [
    _recipe("footer-clinical-support", "Clinical support footer", ["healthcare-clinical"], "support",
            className="border-t border-sky-100 bg-white text-slate-700"),
    _recipe("footer-commerce-dark", "Commerce dark footer", ["automotive-showroom", "product-commerce"], "commerce",
            className="border-t border-neutral-200 bg-neutral-950 text-neutral-100"),
    _recipe("footer-developer-console", "Developer console footer", ["developer-console"], "console",
            className="border-t border-slate-800 bg-slate-950 text-slate-300"),
    _recipe("footer-learning-resource", "Learning resource footer", ["learning-editorial"], "resource",
            className="border-t border-amber-200 bg-white text-slate-700"),
    _recipe("footer-local-hours", "Local hours footer", ["restaurant-reservation"], "local",
            className="border-t border-orange-200 bg-stone-950 text-stone-100"),
    _recipe("footer-travel-guide", "Travel guide footer", ["travel-destination"], "guide",
            className="border-t border-sky-100 bg-cyan-950 text-cyan-50"),
    _recipe("footer-listing-local", "Listing local footer", ["real-estate-listings"], "listing",
            className="border-t border-emerald-100 bg-white text-stone-700"),
    _recipe("footer-wellness-class", "Wellness class footer", ["fitness-coaching"], "class",
            className="border-t border-lime-200 bg-lime-950 text-lime-50"),
    _recipe("footer-studio-index", "Studio index footer", ["creative-portfolio"], "index",
            className="border-t border-zinc-200 bg-zinc-950 text-zinc-100"),
    _recipe("footer-trust-utility", "Trust utility footer", ["finance-trust", "operations-console", "service-trust"], "trust",
            className="border-t border-emerald-100 bg-white text-slate-700"),
]


_POOLS = {
    "hero": HERO_RECIPES,
    "nav": NAV_RECIPES,
    "section": SECTION_RECIPES,
    "card": CARD_RECIPES,
    "cta": CTA_RECIPES,
    "footer": FOOTER_RECIPES,
}

_BANNED = {
    "stripe", "apple", "nike", "linear", "notion", "figma", "vercel", "webflow",
    "tesla", "amazon", "github", "openai", "coursera", "spotify",
}


def _haystack(genome):
    records = genome.get("selected_design_dna") or []
    parts = [
        genome.get("app_category", ""),
        genome.get("domain", ""),
        genome.get("inspiration_family", ""),
        " ".join(genome.get("dna_families") or []),
        " ".join(genome.get("hero_patterns") or []),
        " ".join(genome.get("section_patterns") or []),
        " ".join(r.get("category", "") + " " + r.get("design_family", "") for r in records if isinstance(r, dict)),
    ]
    return " ".join(str(p) for p in parts).lower()


def infer_visual_family(genome):
    hay = _haystack(genome)
    if any(x in hay for x in ("restaurant", "reservation", "dining", "menu", "table booking", "hospitality")):
        return "restaurant-reservation"
    if any(x in hay for x in ("real estate", "property", "listing", "neighborhood", "agent", "mortgage")):
        return "real-estate-listings"
    if any(x in hay for x in ("travel", "tourism", "destination", "trip", "itinerary", "tour ")):
        return "travel-destination"
    if any(x in hay for x in ("fitness", "wellness", "trainer", "coach", "class-booking", "program")):
        return "fitness-coaching"
    if any(x in hay for x in ("ai", "developer", "devtool", "api", "code", "technical", "console")):
        return "developer-console"
    if any(x in hay for x in ("education", "course", "learning", "lesson", "student", "media")):
        return "learning-editorial"
    if any(x in hay for x in ("hospital", "clinic", "healthcare", "patient", "doctor", "clinical", "medical")):
        return "healthcare-clinical"
    if any(x in hay for x in ("vehicle", "automotive", "dealer", "showroom", "test drive")):
        return "automotive-showroom"
    if any(x in hay for x in ("ecommerce", "product", "marketplace", "catalog", "commerce")):
        return "product-commerce"
    if any(x in hay for x in ("portfolio", "agency", "creative", "studio", "case study")):
        return "creative-portfolio"
    if any(x in hay for x in ("finance", "fintech", "payment", "transaction", "ledger", "loan")):
        return "finance-trust"
    if any(x in hay for x in ("pos", "erp", "inventory", "operations", "resource", "workflow-command")):
        return "operations-console"
    return "service-trust"


def _signature_seed(genome):
    raw = "|".join([
        str(genome.get("app_seed", "")),
        ",".join(genome.get("dna_profile_ids") or []),
        ",".join(genome.get("dna_families") or []),
        str(genome.get("layout_rhythm", "")),
    ])
    seed = sum((i + 1) * ord(ch) for i, ch in enumerate(raw))
    app_seed = str(genome.get("app_seed", "") or "")
    try:
        seed += int(app_seed[-2:], 16) * 17
    except Exception:
        pass
    return seed


def _compatible(pool, visual_family):
    return [r for r in pool if visual_family in r.get("families", [])] or [
        r for r in pool if "service-trust" in r.get("families", [])
    ] or list(pool)


def _choose(pool, visual_family, genome, salt=0, rng=None, avoid=None):
    options = _compatible(pool, visual_family)
    if avoid and len(options) > 1:
        options = [o for o in options if o.get("id") != avoid] or options
    base = _signature_seed(genome) + salt
    return dict(options[base % len(options)])


def _choose_many(pool, visual_family, genome, count=5, salt=0, rng=None):
    options = _compatible(pool, visual_family)
    if not options:
        return []
    base = _signature_seed(genome) + salt
    out = []
    for i in range(count):
        out.append(dict(options[(base + i) % len(options)]))
    seen = {}
    for item in out:
        seen[item["id"]] = item
    return list(seen.values())


def select_visual_recipes(genome, rng=None):
    genome = dict(genome or {})
    visual_family = infer_visual_family(genome)
    hero = _choose(HERO_RECIPES, visual_family, genome, 101, rng)
    nav = _choose(NAV_RECIPES, visual_family, genome, 211, rng)
    card = _choose(CARD_RECIPES, visual_family, genome, 307, rng)
    cta = _choose(CTA_RECIPES, visual_family, genome, 401, rng)
    footer = _choose(FOOTER_RECIPES, visual_family, genome, 503, rng)
    sections = _choose_many(SECTION_RECIPES, visual_family, genome, 6, 601, rng)
    first = "|".join([
        visual_family,
        hero.get("id", ""),
        nav.get("id", ""),
        card.get("id", ""),
        hero.get("first_screen", hero.get("layout", "")),
    ])
    browser_sig = "|".join([
        visual_family,
        hero.get("id", ""),
        nav.get("id", ""),
        "~".join(r.get("id", "") for r in sections),
        card.get("id", ""),
        cta.get("id", ""),
        footer.get("id", ""),
        str(genome.get("layout_rhythm", "")),
        str(genome.get("image_strategy", "")),
    ])
    extracted = []
    extracted_influence = {}
    try:
        from app import github_design_sources
        extracted = github_design_sources.select_extracted_recipes(
            genome, visual_family=visual_family, max_recipes=6
        )
        extracted_influence = github_design_sources.summarize_recipe_influence(extracted)
    except Exception as exc:
        genome["extracted_recipe_error"] = str(exc)[:120]
        extracted_influence = {}
    if extracted:
        ids = [r.get("recipe_id", "") for r in extracted[:6]]
        source_stamp = "mined-hybrid:" + ",".join(ids[:3])
        hero["id"] = hero.get("id", "hero") + "__" + ids[0]
        card["id"] = card.get("id", "card") + "__" + ids[min(1, len(ids) - 1)]
        cta["id"] = cta.get("id", "cta") + "__" + ids[-1]
        browser_sig = browser_sig + "|mined-hybrid|" + "~".join(ids)
        first = first + "|" + source_stamp
    return {
        "visual_family": visual_family,
        "hero_recipe": hero,
        "nav_recipe": nav,
        "section_recipes": sections,
        "section_recipe_ids": [r.get("id", "") for r in sections],
        "card_recipe": card,
        "cta_recipe": cta,
        "footer_recipe": footer,
        "first_screen_skeleton": first,
        "browser_visible_signature": browser_sig,
        "recipe_source_mode": "mined-hybrid" if extracted else "handcrafted",
        "extracted_design_recipes": extracted,
        "extracted_recipe_ids": [r.get("recipe_id", "") for r in extracted],
        "extracted_recipe_families": sorted({r.get("visual_family", "") for r in extracted if r.get("visual_family")}),
        "github_recipe_influence": extracted_influence,
    }


def recipe_counts():
    return {name: len(pool) for name, pool in _POOLS.items()}


def validate_recipe_pools():
    errors = []
    required = {"id", "name", "families", "layout"}
    minimums = {"hero": 20, "nav": 10, "section": 30, "card": 20, "cta": 10, "footer": 10}
    all_ids = []
    for name, pool in _POOLS.items():
        if len(pool) < minimums[name]:
            errors.append(f"{name} recipes below minimum: {len(pool)} < {minimums[name]}")
        for rec in pool:
            missing = required - set(rec)
            if missing:
                errors.append(f"{rec.get('id', '<missing>')} missing {sorted(missing)}")
            all_ids.append(rec.get("id", ""))
            blob = repr(rec).lower()
            if any(b in blob for b in _BANNED):
                errors.append(f"{rec.get('id')} includes banned brand vocabulary")
            if re.search(r"https?://|www\.|[a-z0-9-]+\.(?:com|app|ai|io|co|net|org|tech)\b", blob):
                errors.append(f"{rec.get('id')} includes URL-like text")
    if len(all_ids) != len(set(all_ids)):
        errors.append("recipe ids are not unique")
    return {"ok": not errors, "errors": errors, "counts": recipe_counts()}
