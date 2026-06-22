"""Professional, code-backed UI component library (1000+ records).

This module is the COMPONENT half of the local block/component library used to
make the AI generator output look professional instead of basic. It does NOT
copy real websites, brand names, logos, source copy, exact layouts, or external
image URLs. Every record is generated from abstract, original combinations of:

    component_type  x  visual_family  x  variant

Each generated record carries rich metadata plus a real, renderable JSX template
function. Templates use Tailwind CSS, are responsive (mobile / tablet / desktop),
use accessible semantic HTML, and only reference safe local image slots such as
`/generated/hero.jpg` (never external or copied asset paths).

The same anti-copy helpers, family style packs, search, and validation utilities
are reused by `professional_sections.py`, and the unified public API is exposed
by `block_component_registry.py`.
"""
from __future__ import annotations

from collections import Counter
import copy
import re


# --------------------------------------------------------------------------- #
# Vocabulary: domains, visual families, component types
# --------------------------------------------------------------------------- #

DOMAINS = [
    "healthcare",
    "automotive",
    "restaurant",
    "real-estate",
    "travel",
    "fitness",
    "education",
    "ecommerce",
    "saas",
    "ai-devtools",
    "business-ops",
    "fintech",
    "agency",
    "community",
    "media",
]

# 15 professional visual families. Each is a coherent, original "skin": palette,
# corner language, shadow weight, accent system. Keyed by slug.
VISUAL_FAMILIES = [
    "clinical-trust",
    "healthcare-saas",
    "premium-automotive",
    "restaurant-editorial",
    "travel-destination",
    "real-estate-listing",
    "fitness-coaching",
    "education-editorial",
    "ecommerce-premium",
    "saas-gradient",
    "devtool-console",
    "fintech-trust",
    "agency-editorial",
    "community-social",
    "dashboard-operations",
]

COMPONENT_TYPES = [
    "button",
    "badge",
    "stat card",
    "feature card",
    "service card",
    "product card",
    "vehicle card",
    "property card",
    "course card",
    "profile card",
    "doctor card",
    "trainer card",
    "restaurant menu card",
    "travel package card",
    "pricing card",
    "testimonial card",
    "dashboard metric card",
    "chart preview card",
    "table preview",
    "search box",
    "form field",
    "nav item",
    "tab item",
    "accordion item",
    "timeline item",
    "cta button group",
    "image panel",
    "logo cloud item",
    "trust badge",
    "footer link group",
]

# Variant modifiers add depth/border variety on top of the family skin.
VARIANTS = ["soft", "elevated", "outline"]


# --------------------------------------------------------------------------- #
# Family style packs
# --------------------------------------------------------------------------- #

_FAMILY_LABELS = {
    "clinical-trust": "Clinical Trust",
    "healthcare-saas": "Healthcare SaaS",
    "premium-automotive": "Premium Automotive",
    "restaurant-editorial": "Restaurant Editorial",
    "travel-destination": "Travel Destination",
    "real-estate-listing": "Real Estate Listing",
    "fitness-coaching": "Fitness Coaching",
    "education-editorial": "Education Editorial",
    "ecommerce-premium": "Ecommerce Premium",
    "saas-gradient": "SaaS Gradient",
    "devtool-console": "Devtool Console",
    "fintech-trust": "FinTech Trust",
    "agency-editorial": "Agency Editorial",
    "community-social": "Community Social",
    "dashboard-operations": "Dashboard Operations",
}

# Per-family token sets. Missing tokens fall back to _STYLE_DEFAULTS.
_FAMILIES = {
    "clinical-trust": {
        "domains": ["healthcare"], "theme": "light",
        "page": "bg-white text-slate-900", "page_alt": "bg-sky-50/60",
        "surface": "bg-white", "surface_alt": "bg-sky-50", "border": "border-sky-100",
        "heading": "text-slate-900", "muted": "text-slate-600",
        "accent": "bg-sky-600", "accent_hover": "hover:bg-sky-700", "accent_text": "text-sky-700",
        "accent_grad": "bg-gradient-to-r from-sky-600 to-blue-600",
        "chip_bg": "bg-sky-50", "chip_text": "text-sky-700", "focus": "focus-visible:ring-sky-500/50",
        "radius": "rounded-2xl",
    },
    "healthcare-saas": {
        "domains": ["healthcare", "saas"], "theme": "light",
        "page": "bg-white text-slate-900", "page_alt": "bg-teal-50/60",
        "surface": "bg-white", "surface_alt": "bg-teal-50", "border": "border-teal-100",
        "heading": "text-slate-900", "muted": "text-slate-600",
        "accent": "bg-teal-600", "accent_hover": "hover:bg-teal-700", "accent_text": "text-teal-700",
        "accent_grad": "bg-gradient-to-r from-teal-600 to-cyan-600",
        "chip_bg": "bg-teal-50", "chip_text": "text-teal-700", "focus": "focus-visible:ring-teal-500/50",
        "radius": "rounded-2xl",
    },
    "premium-automotive": {
        "domains": ["automotive", "ecommerce"], "theme": "light",
        "page": "bg-neutral-50 text-neutral-950", "page_alt": "bg-white",
        "surface": "bg-white", "surface_alt": "bg-neutral-100", "border": "border-neutral-200",
        "heading": "text-neutral-950", "muted": "text-neutral-600",
        "accent": "bg-neutral-900", "accent_hover": "hover:bg-neutral-800", "accent_text": "text-neutral-900",
        "accent_grad": "bg-gradient-to-r from-neutral-900 to-neutral-700",
        "chip_bg": "bg-neutral-100", "chip_text": "text-neutral-700", "focus": "focus-visible:ring-neutral-900/30",
        "radius": "rounded-lg", "pill": "rounded-lg",
    },
    "restaurant-editorial": {
        "domains": ["restaurant", "media"], "theme": "light",
        "page": "bg-stone-50 text-stone-900", "page_alt": "bg-orange-50/70",
        "surface": "bg-white", "surface_alt": "bg-orange-50", "border": "border-orange-200/80",
        "heading": "text-stone-900", "muted": "text-stone-600",
        "accent": "bg-rose-700", "accent_hover": "hover:bg-rose-800", "accent_text": "text-rose-700",
        "accent_grad": "bg-gradient-to-r from-rose-700 to-orange-600",
        "chip_bg": "bg-orange-100", "chip_text": "text-orange-800", "focus": "focus-visible:ring-rose-600/40",
        "radius": "rounded-3xl",
    },
    "travel-destination": {
        "domains": ["travel"], "theme": "light",
        "page": "bg-white text-slate-900", "page_alt": "bg-cyan-50/70",
        "surface": "bg-white", "surface_alt": "bg-cyan-50", "border": "border-cyan-100",
        "heading": "text-slate-900", "muted": "text-slate-600",
        "accent": "bg-teal-600", "accent_hover": "hover:bg-teal-700", "accent_text": "text-teal-700",
        "accent_grad": "bg-gradient-to-r from-teal-600 to-cyan-500",
        "chip_bg": "bg-cyan-50", "chip_text": "text-cyan-700", "focus": "focus-visible:ring-teal-500/50",
        "radius": "rounded-3xl",
    },
    "real-estate-listing": {
        "domains": ["real-estate"], "theme": "light",
        "page": "bg-stone-50 text-stone-900", "page_alt": "bg-emerald-50/60",
        "surface": "bg-white", "surface_alt": "bg-emerald-50", "border": "border-emerald-100",
        "heading": "text-stone-900", "muted": "text-stone-600",
        "accent": "bg-emerald-700", "accent_hover": "hover:bg-emerald-800", "accent_text": "text-emerald-700",
        "accent_grad": "bg-gradient-to-r from-emerald-700 to-teal-600",
        "chip_bg": "bg-emerald-50", "chip_text": "text-emerald-700", "focus": "focus-visible:ring-emerald-600/40",
        "radius": "rounded-2xl",
    },
    "fitness-coaching": {
        "domains": ["fitness"], "theme": "light",
        "page": "bg-white text-slate-900", "page_alt": "bg-lime-50/70",
        "surface": "bg-white", "surface_alt": "bg-lime-50", "border": "border-lime-200",
        "heading": "text-slate-900", "muted": "text-slate-600",
        "accent": "bg-lime-600", "accent_hover": "hover:bg-lime-700", "on_accent": "text-slate-950",
        "accent_text": "text-lime-700",
        "accent_grad": "bg-gradient-to-r from-lime-500 to-emerald-600",
        "chip_bg": "bg-lime-100", "chip_text": "text-lime-800", "focus": "focus-visible:ring-lime-500/50",
        "radius": "rounded-3xl",
    },
    "education-editorial": {
        "domains": ["education", "media"], "theme": "light",
        "page": "bg-white text-slate-900", "page_alt": "bg-amber-50/70",
        "surface": "bg-white", "surface_alt": "bg-amber-50", "border": "border-amber-200",
        "heading": "text-slate-900", "muted": "text-slate-600",
        "accent": "bg-cyan-700", "accent_hover": "hover:bg-cyan-800", "accent_text": "text-cyan-700",
        "accent_grad": "bg-gradient-to-r from-cyan-700 to-amber-500",
        "chip_bg": "bg-amber-100", "chip_text": "text-amber-800", "focus": "focus-visible:ring-cyan-600/40",
        "radius": "rounded-2xl",
    },
    "ecommerce-premium": {
        "domains": ["ecommerce"], "theme": "light",
        "page": "bg-stone-50 text-stone-900", "page_alt": "bg-white",
        "surface": "bg-white", "surface_alt": "bg-stone-100", "border": "border-stone-200",
        "heading": "text-stone-900", "muted": "text-stone-600",
        "accent": "bg-stone-900", "accent_hover": "hover:bg-stone-800", "accent_text": "text-stone-900",
        "accent_grad": "bg-gradient-to-r from-stone-900 to-stone-700",
        "chip_bg": "bg-stone-100", "chip_text": "text-stone-700", "focus": "focus-visible:ring-stone-900/30",
        "radius": "rounded-2xl",
    },
    "saas-gradient": {
        "domains": ["saas"], "theme": "light",
        "page": "bg-white text-slate-900", "page_alt": "bg-indigo-50/70",
        "surface": "bg-white", "surface_alt": "bg-indigo-50", "border": "border-indigo-100",
        "heading": "text-slate-900", "muted": "text-slate-600",
        "accent": "bg-indigo-600", "accent_hover": "hover:bg-indigo-700", "accent_text": "text-indigo-700",
        "accent_grad": "bg-gradient-to-r from-indigo-600 to-violet-600",
        "chip_bg": "bg-indigo-50", "chip_text": "text-indigo-700", "focus": "focus-visible:ring-indigo-500/50",
        "radius": "rounded-2xl",
    },
    "devtool-console": {
        "domains": ["ai-devtools", "business-ops"], "theme": "dark",
        "page": "bg-slate-950 text-slate-100", "page_alt": "bg-slate-900",
        "surface": "bg-slate-900", "surface_alt": "bg-slate-800/60", "border": "border-slate-800",
        "heading": "text-white", "muted": "text-slate-400",
        "accent": "bg-violet-500", "accent_hover": "hover:bg-violet-400", "accent_text": "text-violet-300",
        "accent_grad": "bg-gradient-to-r from-violet-600 to-fuchsia-600",
        "chip_bg": "bg-slate-800", "chip_text": "text-slate-200", "focus": "focus-visible:ring-violet-500/50",
        "input_bg": "bg-slate-900", "radius": "rounded-xl", "pill": "rounded-lg",
    },
    "fintech-trust": {
        "domains": ["fintech", "business-ops"], "theme": "light",
        "page": "bg-white text-slate-900", "page_alt": "bg-emerald-50/50",
        "surface": "bg-white", "surface_alt": "bg-slate-50", "border": "border-slate-200",
        "heading": "text-slate-900", "muted": "text-slate-600",
        "accent": "bg-emerald-600", "accent_hover": "hover:bg-emerald-700", "accent_text": "text-emerald-700",
        "accent_grad": "bg-gradient-to-r from-emerald-600 to-teal-600",
        "chip_bg": "bg-emerald-50", "chip_text": "text-emerald-700", "focus": "focus-visible:ring-emerald-500/50",
        "radius": "rounded-2xl",
    },
    "agency-editorial": {
        "domains": ["agency", "media"], "theme": "light",
        "page": "bg-white text-zinc-950", "page_alt": "bg-zinc-50",
        "surface": "bg-white", "surface_alt": "bg-zinc-100", "border": "border-zinc-300",
        "heading": "text-zinc-950", "muted": "text-zinc-600",
        "accent": "bg-fuchsia-600", "accent_hover": "hover:bg-fuchsia-700", "accent_text": "text-fuchsia-700",
        "accent_grad": "bg-gradient-to-r from-fuchsia-600 to-rose-500",
        "chip_bg": "bg-zinc-900", "chip_text": "text-white", "focus": "focus-visible:ring-fuchsia-500/50",
        "radius": "rounded-none", "pill": "rounded-none",
    },
    "community-social": {
        "domains": ["community"], "theme": "light",
        "page": "bg-white text-slate-900", "page_alt": "bg-violet-50/70",
        "surface": "bg-white", "surface_alt": "bg-violet-50", "border": "border-violet-100",
        "heading": "text-slate-900", "muted": "text-slate-600",
        "accent": "bg-violet-600", "accent_hover": "hover:bg-violet-700", "accent_text": "text-violet-700",
        "accent_grad": "bg-gradient-to-r from-violet-600 to-pink-600",
        "chip_bg": "bg-pink-50", "chip_text": "text-pink-700", "focus": "focus-visible:ring-violet-500/50",
        "radius": "rounded-3xl",
    },
    "dashboard-operations": {
        "domains": ["business-ops", "saas"], "theme": "light",
        "page": "bg-slate-50 text-slate-900", "page_alt": "bg-white",
        "surface": "bg-white", "surface_alt": "bg-indigo-50/60", "border": "border-slate-200",
        "heading": "text-slate-900", "muted": "text-slate-600",
        "accent": "bg-indigo-600", "accent_hover": "hover:bg-indigo-700", "accent_text": "text-indigo-700",
        "accent_grad": "bg-gradient-to-r from-indigo-600 to-blue-600",
        "chip_bg": "bg-indigo-50", "chip_text": "text-indigo-700", "focus": "focus-visible:ring-indigo-500/50",
        "radius": "rounded-2xl",
    },
}

_STYLE_DEFAULTS = {
    "theme": "light", "on_accent": "text-white", "pill": "rounded-full",
    "input_bg": "bg-white", "subtle": "", "radius": "rounded-2xl",
}

_VARIANT_GEOMETRY = {
    "soft": {"shadow": "shadow-sm", "border_w": "border"},
    "elevated": {"shadow": "shadow-lg", "border_w": "border"},
    "outline": {"shadow": "shadow-none", "border_w": "border-2"},
}


def family_style(family: str, variant: str = "soft") -> dict:
    """Return a fully-resolved style pack for a (family, variant) pair.

    Includes raw palette tokens plus pre-composed class strings (`card`,
    `btn_primary`, `btn_secondary`, `input`) so renderers stay short and the
    whole library looks consistent.
    """
    base = dict(_STYLE_DEFAULTS)
    base.update(_FAMILIES.get(family, _FAMILIES["dashboard-operations"]))
    base.setdefault("subtle", base["muted"])
    geom = _VARIANT_GEOMETRY.get(variant, _VARIANT_GEOMETRY["soft"])
    style = dict(base)
    style["family"] = family
    style["label"] = _FAMILY_LABELS.get(family, family)
    style["variant"] = variant
    style["shadow"] = geom["shadow"]
    style["border_w"] = geom["border_w"]

    radius = base["radius"]
    pill = base.get("pill", "rounded-full")
    focus = base["focus"]
    style["card"] = f"{geom['border_w']} {base['border']} {base['surface']} {radius} {geom['shadow']}"
    style["btn_primary"] = (
        f"inline-flex items-center justify-center gap-2 {pill} {base['accent']} {base['on_accent']} "
        f"px-4 py-2.5 sm:px-5 text-sm font-semibold {base['accent_hover']} transition "
        f"focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 {focus}"
    )
    style["btn_secondary"] = (
        f"inline-flex items-center justify-center gap-2 {pill} border {base['border']} {base['surface']} "
        f"{base['accent_text']} px-4 py-2.5 sm:px-5 text-sm font-semibold hover:opacity-90 transition "
        f"focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 {focus}"
    )
    style["input"] = (
        f"w-full {radius} border {base['border']} {base.get('input_bg', 'bg-white')} px-3.5 py-2.5 "
        f"text-sm {base['heading']} placeholder:{base['muted']} focus:outline-none "
        f"focus-visible:ring-2 {focus}"
    )
    return style


# --------------------------------------------------------------------------- #
# JSX render helpers (safe text, icons, images)
# --------------------------------------------------------------------------- #

def _t(value, default: str = "", limit: int = 160) -> str:
    """Sanitize a text node: drop characters that would break JSX, fall back."""
    text = str(value if value is not None else "").strip()
    text = text.replace("<", "").replace(">", "").replace("{", "").replace("}", "")
    text = re.sub(r"\s+", " ", text).strip()
    return (text or default)[:limit]


def _attr(value, default: str = "", limit: int = 120) -> str:
    """Sanitize an attribute value (also strips quotes)."""
    return _t(value, default, limit).replace('"', "").replace("'", "")


_SAFE_IMG_RE = re.compile(r"^/generated/[a-z0-9][a-z0-9/_-]*\.(?:jpg|jpeg|png|webp)$")


def safe_img_src(value, fallback: str = "/generated/placeholder.jpg") -> str:
    """Only ever allow safe local generated image slots; never external/copied."""
    candidate = str(value or "").strip().lower()
    return candidate if _SAFE_IMG_RE.match(candidate) else fallback


def _img(src, alt, cls: str, fallback: str = "/generated/placeholder.jpg") -> str:
    safe = safe_img_src(src, fallback)
    return (
        f'<img src="{safe}" alt="{_attr(alt, "Illustrative generated image", 90)}" '
        f'loading="lazy" className="{cls}" />'
    )


# name -> (path data, filled?)
_ICONS = {
    "check": ("M4.5 12.5l5 5 10-11", False),
    "arrow": ("M5 12h14M13 6l6 6-6 6", False),
    "search": ("M21 21l-4.35-4.35M11 19a8 8 0 1 1 0-16 8 8 0 0 1 0 16z", False),
    "chevron": ("M6 9l6 6 6-6", False),
    "star": ("M12 2.5l2.9 6.1 6.6.9-4.8 4.6 1.2 6.6L12 18.6 6.1 21.3l1.2-6.6L2.5 9.5l6.6-.9z", True),
    "shield": ("M12 3l7 3v5c0 4.6-3 7.9-7 9-4-1.1-7-4.4-7-9V6z", False),
    "pin": ("M12 21s-6-5.3-6-10a6 6 0 1 1 12 0c0 4.7-6 10-6 10zM12 11.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z", False),
    "clock": ("M12 7.5V12l3 1.8M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z", False),
    "bolt": ("M13 2L4.5 13.5H11l-1 8.5L19.5 10H13z", False),
    "play": ("M8 5.5v13l11-6.5z", False),
    "plus": ("M12 5v14M5 12h14", False),
    "user": ("M12 12.5a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM5 20a7 7 0 0 1 14 0", False),
    "heart": ("M12 21s-7-4.6-9.3-9.2C1 8.4 3 4.8 6.4 4.8c2 0 3.2 1.1 3.6 2 .4-.9 1.6-2 3.6-2 3.4 0 5.4 3.6 3.7 7C19 16.4 12 21 12 21z", False),
    "calendar": ("M7 3v3m10-3v3M4 9h16M5 6h14a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1z", False),
    "spark": ("M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M18 6l-2.5 2.5M8.5 15.5L6 18", False),
    "dot": ("M12 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2z", True),
}


def _icon(name: str, cls: str = "h-5 w-5") -> str:
    data, filled = _ICONS.get(name, _ICONS["dot"])
    if filled:
        return (
            f'<svg aria-hidden="true" viewBox="0 0 24 24" fill="currentColor" '
            f'className="{cls}"><path d="{data}" /></svg>'
        )
    return (
        f'<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'strokeWidth="1.8" className="{cls}"><path strokeLinecap="round" '
        f'strokeLinejoin="round" d="{data}" /></svg>'
    )


def _chip(text, style, icon: str = "") -> str:
    lead = _icon(icon, "h-3.5 w-3.5") if icon else ""
    return (
        f'<span className="inline-flex items-center gap-1.5 rounded-full {style["chip_bg"]} '
        f'{style["chip_text"]} px-3 py-1 text-xs font-medium sm:text-[0.8rem]">{lead}'
        f'{_t(text, "Label", 40)}</span>'
    )


def _stars(rating, style) -> str:
    try:
        full = max(0, min(5, int(round(float(rating)))))
    except (TypeError, ValueError):
        full = 5
    stars = "".join(
        _icon("star", f'h-4 w-4 {"text-amber-500" if i < full else style["muted"]}')
        for i in range(5)
    )
    return f'<div className="flex items-center gap-0.5" aria-label="Rated {full} out of 5">{stars}</div>'


def _eyebrow(text, style) -> str:
    return (
        f'<p className="text-xs font-semibold uppercase tracking-[0.18em] {style["accent_text"]} '
        f'sm:text-[0.78rem]">{_t(text, "Overview", 48)}</p>'
    )


# --------------------------------------------------------------------------- #
# Component renderers — each returns a single-root, responsive JSX string
# --------------------------------------------------------------------------- #

def render_button(props, style):
    label = _t(props.get("label"), "Get started", 40)
    kind = "secondary" if props.get("variant") == "secondary" else "primary"
    cls = style["btn_secondary"] if kind == "secondary" else style["btn_primary"]
    return (
        f'<button type="button" className="{cls}">'
        f'<span>{label}</span>{_icon("arrow", "h-4 w-4")}</button>'
    )


def render_badge(props, style):
    return _chip(props.get("label", "New"), style, props.get("icon", "spark"))


def render_stat_card(props, style):
    value = _t(props.get("value"), "98%", 16)
    label = _t(props.get("label"), "Patient satisfaction", 48)
    delta = _t(props.get("delta"), "+4.2% this quarter", 40)
    return (
        f'<article className="{style["card"]} p-5 sm:p-6">'
        f'<dt className="text-sm font-medium {style["muted"]}">{label}</dt>'
        f'<dd className="mt-2 text-3xl font-bold tracking-tight {style["heading"]} sm:text-4xl">{value}</dd>'
        f'<p className="mt-2 inline-flex items-center gap-1 text-xs font-semibold {style["accent_text"]}">'
        f'{_icon("bolt", "h-3.5 w-3.5")}{delta}</p></article>'
    )


def render_feature_card(props, style):
    title = _t(props.get("title"), "Built for scale", 48)
    desc = _t(props.get("description"), "Production-ready building blocks that adapt to every screen and workflow.", 160)
    return (
        f'<article className="{style["card"]} p-5 sm:p-6">'
        f'<div className="flex h-11 w-11 items-center justify-center rounded-xl {style["chip_bg"]} {style["accent_text"]}">'
        f'{_icon(props.get("icon", "spark"), "h-5 w-5")}</div>'
        f'<h3 className="mt-4 text-lg font-semibold tracking-tight {style["heading"]} sm:text-xl">{title}</h3>'
        f'<p className="mt-2 text-sm leading-relaxed {style["muted"]}">{desc}</p>'
        f'<a href="#" className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold {style["accent_text"]}">'
        f'Learn more {_icon("arrow", "h-4 w-4")}</a></article>'
    )


def render_service_card(props, style):
    title = _t(props.get("title"), "Consultation", 48)
    desc = _t(props.get("description"), "End-to-end support delivered by a specialist team you can rely on.", 150)
    points = props.get("points") or ["Dedicated specialist", "Same-week scheduling", "Transparent pricing"]
    items = "".join(
        f'<li className="flex items-start gap-2 text-sm {style["muted"]}">'
        f'<span className="mt-0.5 {style["accent_text"]}">{_icon("check", "h-4 w-4")}</span>'
        f'<span>{_t(p, "Included", 48)}</span></li>'
        for p in list(points)[:4]
    )
    return (
        f'<article className="{style["card"]} flex h-full flex-col p-5 sm:p-6">'
        f'<div className="flex h-11 w-11 items-center justify-center rounded-xl {style["chip_bg"]} {style["accent_text"]}">'
        f'{_icon(props.get("icon", "shield"), "h-5 w-5")}</div>'
        f'<h3 className="mt-4 text-lg font-semibold tracking-tight {style["heading"]}">{title}</h3>'
        f'<p className="mt-2 text-sm leading-relaxed {style["muted"]}">{desc}</p>'
        f'<ul className="mt-4 space-y-2">{items}</ul>'
        f'<a href="#" className="mt-5 inline-flex items-center gap-1.5 text-sm font-semibold {style["accent_text"]}">'
        f'View service {_icon("arrow", "h-4 w-4")}</a></article>'
    )


def render_product_card(props, style):
    title = _t(props.get("title"), "Studio Headphones", 48)
    price = _t(props.get("price"), "$189", 16)
    return (
        f'<article className="{style["card"]} group overflow-hidden p-3 sm:p-4">'
        f'<div className="overflow-hidden rounded-xl {style["surface_alt"]}">'
        f'{_img(props.get("image"), title, "aspect-[4/3] w-full object-cover transition duration-500 group-hover:scale-105", "/generated/product-1.jpg")}</div>'
        f'<div className="mt-3 flex items-start justify-between gap-2">'
        f'<div><h3 className="text-sm font-semibold {style["heading"]} sm:text-base">{title}</h3>'
        f'<p className="mt-0.5 text-xs {style["muted"]}">{_t(props.get("category"), "Premium audio", 40)}</p></div>'
        f'<p className="shrink-0 text-base font-bold {style["heading"]}">{price}</p></div>'
        f'<div className="mt-3 flex items-center justify-between">{_stars(props.get("rating", 5), style)}'
        f'<button type="button" className="{style["btn_primary"]} px-3 py-1.5 text-xs">Add</button></div></article>'
    )


def render_vehicle_card(props, style):
    name = _t(props.get("name"), "Volt GT Electric", 48)
    price = _t(props.get("price"), "$42,500", 16)
    specs = props.get("specs") or ["2024", "Electric", "Automatic"]
    spec_row = "".join(
        f'<span className="inline-flex items-center gap-1 rounded-md {style["surface_alt"]} px-2 py-1 text-xs {style["muted"]}">'
        f'{_t(s, "Spec", 18)}</span>'
        for s in list(specs)[:4]
    )
    return (
        f'<article className="{style["card"]} group overflow-hidden p-3 sm:p-4">'
        f'<div className="relative overflow-hidden rounded-lg {style["surface_alt"]}">'
        f'{_img(props.get("image"), name, "aspect-[16/10] w-full object-cover transition duration-500 group-hover:scale-105", "/generated/vehicle-1.jpg")}'
        f'<span className="absolute left-3 top-3 rounded-md {style["accent"]} {style["on_accent"]} px-2 py-1 text-xs font-semibold">Certified</span></div>'
        f'<h3 className="mt-3 text-base font-semibold {style["heading"]} sm:text-lg">{name}</h3>'
        f'<div className="mt-2 flex flex-wrap gap-1.5">{spec_row}</div>'
        f'<div className="mt-3 flex items-center justify-between border-t {style["border"]} pt-3">'
        f'<p className="text-lg font-bold {style["heading"]}">{price}</p>'
        f'<button type="button" className="{style["btn_primary"]} px-3 py-1.5 text-xs">Book test drive</button></div></article>'
    )


def render_property_card(props, style):
    title = _t(props.get("title"), "Sunlit 3-Bed Townhouse", 48)
    price = _t(props.get("price"), "$615,000", 16)
    address = _t(props.get("address"), "Maple Heights, Riverside", 60)
    facts = props.get("facts") or ["3 bd", "2 ba", "1,820 sqft"]
    fact_row = "".join(
        f'<span className="inline-flex items-center gap-1 text-xs {style["muted"]}">{_icon("dot", "h-3 w-3")}{_t(f, "—", 16)}</span>'
        for f in list(facts)[:4]
    )
    return (
        f'<article className="{style["card"]} group overflow-hidden p-3 sm:p-4">'
        f'<div className="relative overflow-hidden rounded-xl {style["surface_alt"]}">'
        f'{_img(props.get("image"), title, "aspect-[3/2] w-full object-cover transition duration-500 group-hover:scale-105", "/generated/property-1.jpg")}'
        f'<span className="absolute right-3 top-3 rounded-full {style["surface"]} px-2.5 py-1 text-xs font-semibold {style["accent_text"]} shadow-sm">For sale</span></div>'
        f'<p className="mt-3 text-lg font-bold {style["heading"]}">{price}</p>'
        f'<h3 className="text-sm font-semibold {style["heading"]} sm:text-base">{title}</h3>'
        f'<p className="mt-1 inline-flex items-center gap-1 text-xs {style["muted"]}">{_icon("pin", "h-3.5 w-3.5")}{address}</p>'
        f'<div className="mt-3 flex flex-wrap items-center gap-3 border-t {style["border"]} pt-3">{fact_row}</div></article>'
    )


def render_course_card(props, style):
    title = _t(props.get("title"), "Foundations of UX Research", 56)
    return (
        f'<article className="{style["card"]} group overflow-hidden p-3 sm:p-4">'
        f'<div className="relative overflow-hidden rounded-xl {style["surface_alt"]}">'
        f'{_img(props.get("image"), title, "aspect-[16/9] w-full object-cover transition duration-500 group-hover:scale-105", "/generated/course-1.jpg")}'
        f'<span className="absolute left-3 top-3 rounded-full {style["accent"]} {style["on_accent"]} px-2.5 py-1 text-xs font-semibold">{_t(props.get("level"), "Beginner", 18)}</span></div>'
        f'<h3 className="mt-3 text-base font-semibold tracking-tight {style["heading"]} sm:text-lg">{title}</h3>'
        f'<p className="mt-1 text-xs {style["muted"]}">{_t(props.get("instructor"), "With Dr. Lena Park", 48)}</p>'
        f'<div className="mt-3 flex items-center justify-between border-t {style["border"]} pt-3">'
        f'<span className="inline-flex items-center gap-1 text-xs {style["muted"]}">{_icon("play", "h-3.5 w-3.5")}{_t(props.get("lessons"), "24 lessons", 18)}</span>'
        f'{_stars(props.get("rating", 5), style)}</div></article>'
    )


def render_profile_card(props, style):
    name = _t(props.get("name"), "Jordan Avery", 40)
    role = _t(props.get("role"), "Product Designer", 40)
    return (
        f'<article className="{style["card"]} p-5 text-center sm:p-6">'
        f'<div className="mx-auto h-20 w-20 overflow-hidden rounded-full {style["surface_alt"]}">'
        f'{_img(props.get("avatar"), name, "h-full w-full object-cover", "/generated/avatar-1.jpg")}</div>'
        f'<h3 className="mt-4 text-base font-semibold {style["heading"]} sm:text-lg">{name}</h3>'
        f'<p className="text-sm {style["accent_text"]}">{role}</p>'
        f'<p className="mt-2 text-sm leading-relaxed {style["muted"]}">{_t(props.get("bio"), "Crafting calm, accessible interfaces for teams that move fast.", 140)}</p>'
        f'<div className="mt-4 flex justify-center gap-2">'
        f'<a href="#" aria-label="Profile" className="flex h-9 w-9 items-center justify-center rounded-full {style["surface_alt"]} {style["accent_text"]}">{_icon("user", "h-4 w-4")}</a>'
        f'<a href="#" aria-label="Message" className="flex h-9 w-9 items-center justify-center rounded-full {style["surface_alt"]} {style["accent_text"]}">{_icon("spark", "h-4 w-4")}</a></div></article>'
    )


def render_doctor_card(props, style):
    name = _t(props.get("name"), "Dr. Amara Singh", 40)
    specialty = _t(props.get("specialty"), "Cardiology", 40)
    return (
        f'<article className="{style["card"]} flex gap-4 p-4 sm:p-5">'
        f'<div className="h-20 w-20 shrink-0 overflow-hidden rounded-2xl {style["surface_alt"]}">'
        f'{_img(props.get("avatar"), name, "h-full w-full object-cover", "/generated/doctor-1.jpg")}</div>'
        f'<div className="min-w-0 flex-1">'
        f'<h3 className="text-base font-semibold {style["heading"]} sm:text-lg">{name}</h3>'
        f'<p className="text-sm {style["accent_text"]}">{specialty}</p>'
        f'<div className="mt-1">{_stars(props.get("rating", 5), style)}</div>'
        f'<p className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-emerald-600">{_icon("clock", "h-3.5 w-3.5")}{_t(props.get("availability"), "Next: today 3:30 PM", 40)}</p>'
        f'<button type="button" className="{style["btn_primary"]} mt-3 w-full px-3 py-2 text-xs sm:w-auto">Book appointment</button></div></article>'
    )


def render_trainer_card(props, style):
    name = _t(props.get("name"), "Maya Coleman", 40)
    discipline = _t(props.get("discipline"), "Strength & Conditioning", 40)
    return (
        f'<article className="{style["card"]} group overflow-hidden p-3 sm:p-4">'
        f'<div className="overflow-hidden rounded-2xl {style["surface_alt"]}">'
        f'{_img(props.get("image"), name, "aspect-[4/5] w-full object-cover transition duration-500 group-hover:scale-105", "/generated/trainer-1.jpg")}</div>'
        f'<h3 className="mt-3 text-base font-semibold {style["heading"]} sm:text-lg">{name}</h3>'
        f'<p className="text-sm {style["accent_text"]}">{discipline}</p>'
        f'<p className="mt-1 text-xs {style["muted"]}">{_t(props.get("sessions"), "320+ coached sessions", 40)}</p>'
        f'<button type="button" className="{style["btn_primary"]} mt-3 w-full px-3 py-2 text-xs">Book a session</button></article>'
    )


def render_menu_card(props, style):
    name = _t(props.get("name"), "Charred Citrus Salmon", 48)
    price = _t(props.get("price"), "$24", 12)
    tags = props.get("tags") or ["Gluten-free", "Chef's pick"]
    tag_row = "".join(f'{_chip(t, style)}' for t in list(tags)[:3])
    return (
        f'<article className="{style["card"]} flex gap-4 p-4 sm:p-5">'
        f'<div className="h-20 w-20 shrink-0 overflow-hidden rounded-2xl {style["surface_alt"]}">'
        f'{_img(props.get("image"), name, "h-full w-full object-cover", "/generated/dish-1.jpg")}</div>'
        f'<div className="min-w-0 flex-1">'
        f'<div className="flex items-baseline justify-between gap-3">'
        f'<h3 className="text-base font-semibold {style["heading"]} sm:text-lg">{name}</h3>'
        f'<span className="shrink-0 text-base font-bold {style["accent_text"]}">{price}</span></div>'
        f'<p className="mt-1 text-sm leading-relaxed {style["muted"]}">{_t(props.get("description"), "Wild-caught fillet, charred citrus, herb oil, seasonal greens.", 120)}</p>'
        f'<div className="mt-2 flex flex-wrap gap-1.5">{tag_row}</div></div></article>'
    )


def render_travel_package_card(props, style):
    name = _t(props.get("name"), "Coastal Escape · 5 Nights", 56)
    price = _t(props.get("price"), "$1,290", 16)
    return (
        f'<article className="{style["card"]} group overflow-hidden p-3 sm:p-4">'
        f'<div className="relative overflow-hidden rounded-2xl {style["surface_alt"]}">'
        f'{_img(props.get("image"), name, "aspect-[4/3] w-full object-cover transition duration-500 group-hover:scale-105", "/generated/travel-1.jpg")}'
        f'<span className="absolute left-3 top-3 inline-flex items-center gap-1 rounded-full {style["surface"]} px-2.5 py-1 text-xs font-semibold {style["accent_text"]} shadow-sm">{_icon("pin", "h-3.5 w-3.5")}{_t(props.get("region"), "Amalfi Coast", 24)}</span></div>'
        f'<h3 className="mt-3 text-base font-semibold {style["heading"]} sm:text-lg">{name}</h3>'
        f'<p className="mt-1 text-sm {style["muted"]}">{_t(props.get("highlights"), "Boutique stays, guided tastings, sunset sail.", 90)}</p>'
        f'<div className="mt-3 flex items-center justify-between border-t {style["border"]} pt-3">'
        f'<p className="text-sm {style["muted"]}">from <span className="text-lg font-bold {style["heading"]}">{price}</span></p>'
        f'<button type="button" className="{style["btn_primary"]} px-3 py-1.5 text-xs">View trip</button></div></article>'
    )


def render_pricing_card(props, style):
    plan = _t(props.get("plan"), "Growth", 24)
    price = _t(props.get("price"), "$49", 12)
    period = _t(props.get("period"), "/ month", 16)
    featured = bool(props.get("featured"))
    feats = props.get("features") or ["Unlimited projects", "Priority support", "Advanced analytics", "Team roles"]
    rows = "".join(
        f'<li className="flex items-start gap-2 text-sm {style["muted"]}">'
        f'<span className="mt-0.5 {style["accent_text"]}">{_icon("check", "h-4 w-4")}</span>{_t(f, "Feature", 56)}</li>'
        for f in list(feats)[:6]
    )
    ring = f'ring-2 ring-offset-2 {style["focus"].replace("focus-visible:ring-", "ring-")}' if featured else ""
    ribbon = (
        f'<span className="absolute -top-3 left-6 rounded-full {style["accent"]} {style["on_accent"]} px-3 py-1 text-xs font-semibold">Most popular</span>'
        if featured else ""
    )
    return (
        f'<article className="{style["card"]} relative flex h-full flex-col p-6 sm:p-7 {ring}">{ribbon}'
        f'<h3 className="text-sm font-semibold uppercase tracking-wide {style["accent_text"]}">{plan}</h3>'
        f'<p className="mt-3 flex items-baseline gap-1"><span className="text-4xl font-bold tracking-tight {style["heading"]}">{price}</span>'
        f'<span className="text-sm {style["muted"]}">{period}</span></p>'
        f'<ul className="mt-5 flex-1 space-y-2.5">{rows}</ul>'
        f'<button type="button" className="{style["btn_primary"]} mt-6 w-full">Choose {plan}</button></article>'
    )


def render_testimonial_card(props, style):
    quote = _t(props.get("quote"), "The rollout was seamless and the team finally has one source of truth.", 220)
    author = _t(props.get("author"), "Priya N.", 40)
    role = _t(props.get("role"), "Operations Lead", 40)
    return (
        f'<figure className="{style["card"]} flex h-full flex-col p-5 sm:p-6">'
        f'<div className="{style["accent_text"]}">{_stars(props.get("rating", 5), style)}</div>'
        f'<blockquote className="mt-3 flex-1 text-sm leading-relaxed {style["heading"]}">{quote}</blockquote>'
        f'<figcaption className="mt-4 flex items-center gap-3 border-t {style["border"]} pt-4">'
        f'<div className="h-10 w-10 overflow-hidden rounded-full {style["surface_alt"]}">{_img(props.get("avatar"), author, "h-full w-full object-cover", "/generated/avatar-2.jpg")}</div>'
        f'<div><p className="text-sm font-semibold {style["heading"]}">{author}</p>'
        f'<p className="text-xs {style["muted"]}">{role}</p></div></figcaption></figure>'
    )


def render_metric_card(props, style):
    label = _t(props.get("label"), "Active users", 40)
    value = _t(props.get("value"), "12,480", 16)
    trend = _t(props.get("trend"), "+8.1%", 12)
    up = not str(props.get("direction", "up")).startswith("down")
    trend_cls = "text-emerald-600" if up else "text-rose-600"
    bars = "".join(
        f'<span className="w-1.5 rounded-full {style["accent"]} opacity-70 {h}" aria-hidden="true"></span>'
        for h in ("h-5", "h-8", "h-4", "h-11", "h-7", "h-12")
    )
    return (
        f'<article className="{style["card"]} p-4 sm:p-5">'
        f'<div className="flex items-center justify-between">'
        f'<p className="text-sm font-medium {style["muted"]}">{label}</p>'
        f'<span className="inline-flex items-center gap-1 text-xs font-semibold {trend_cls}">{_icon("bolt", "h-3.5 w-3.5")}{trend}</span></div>'
        f'<p className="mt-2 text-2xl font-bold tracking-tight {style["heading"]} sm:text-3xl">{value}</p>'
        f'<div className="mt-3 flex h-12 items-end gap-1.5" aria-hidden="true">{bars}</div></article>'
    )


def render_chart_card(props, style):
    title = _t(props.get("title"), "Revenue by month", 48)
    bars = "".join(
        f'<rect x="{12 + i * 30}" y="{120 - h}" width="18" height="{h}" rx="4" className="{style["accent_text"]}" fill="currentColor" opacity="0.85" />'
        for i, h in enumerate((40, 65, 50, 88, 72, 100))
    )
    return (
        f'<article className="{style["card"]} p-5 sm:p-6">'
        f'<div className="flex items-center justify-between">'
        f'<h3 className="text-sm font-semibold {style["heading"]} sm:text-base">{title}</h3>'
        f'{_chip(props.get("range", "Last 6 mo"), style)}</div>'
        f'<svg viewBox="0 0 200 130" role="img" aria-label="{_attr(title, "Chart", 48)}" className="mt-4 h-32 w-full">'
        f'<line x1="8" y1="120" x2="196" y2="120" stroke="currentColor" className="{style["muted"]}" strokeWidth="1" opacity="0.3" />{bars}</svg></article>'
    )


def render_table_preview(props, style):
    title = _t(props.get("title"), "Recent orders", 48)
    headers = props.get("headers") or ["Reference", "Customer", "Status", "Amount"]
    head = "".join(
        f'<th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide {style["muted"]}">{_t(h, "Col", 24)}</th>'
        for h in list(headers)[:6]
    )
    rows = "".join(
        f'<tr className="border-t {style["border"]}">'
        f'<td className="px-4 py-3 text-sm font-medium {style["heading"]}">#INV-{1042 + r}</td>'
        f'<td className="px-4 py-3 text-sm {style["muted"]}">Account {r + 1}</td>'
        f'<td className="px-4 py-3">{_chip("Paid" if r % 2 == 0 else "Pending", style)}</td>'
        f'<td className="px-4 py-3 text-right text-sm font-semibold {style["heading"]}">${(r + 3) * 124}.00</td></tr>'
        for r in range(4)
    )
    return (
        f'<div className="{style["card"]} overflow-hidden">'
        f'<div className="flex items-center justify-between px-4 py-3 sm:px-5">'
        f'<h3 className="text-sm font-semibold {style["heading"]} sm:text-base">{title}</h3>'
        f'<a href="#" className="text-xs font-semibold {style["accent_text"]}">View all</a></div>'
        f'<div className="overflow-x-auto"><table className="w-full min-w-[34rem] border-t {style["border"]}">'
        f'<thead className="{style["surface_alt"]}"><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div></div>'
    )


def render_search_box(props, style):
    placeholder = _attr(props.get("placeholder"), "Search listings, names, or keywords", 60)
    label = _t(props.get("label"), "Search", 24)
    return (
        f'<form className="{style["card"]} flex flex-col gap-2 p-2 sm:flex-row sm:items-center" role="search">'
        f'<label className="sr-only" htmlFor="pcl-search">{label}</label>'
        f'<div className="flex flex-1 items-center gap-2 px-2">'
        f'<span className="{style["muted"]}">{_icon("search", "h-5 w-5")}</span>'
        f'<input id="pcl-search" type="search" placeholder="{placeholder}" '
        f'className="w-full bg-transparent py-2 text-sm {style["heading"]} placeholder:{style["muted"]} focus:outline-none" /></div>'
        f'<button type="submit" className="{style["btn_primary"]} sm:w-auto">Search</button></form>'
    )


def render_form_field(props, style):
    label = _t(props.get("label"), "Full name", 40)
    fid = "pcl-" + re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or "pcl-field"
    helper = _t(props.get("helper"), "We will never share your details.", 80)
    placeholder = _attr(props.get("placeholder"), "Enter a value", 40)
    return (
        f'<div className="space-y-1.5 sm:space-y-2">'
        f'<label htmlFor="{fid}" className="block text-sm font-medium {style["heading"]}">{label}</label>'
        f'<input id="{fid}" type="{_attr(props.get("type"), "text", 16)}" placeholder="{placeholder}" '
        f'className="{style["input"]}" />'
        f'<p className="text-xs {style["muted"]}">{helper}</p></div>'
    )


def render_nav_item(props, style):
    label = _t(props.get("label"), "Solutions", 28)
    active = bool(props.get("active"))
    state = f'{style["accent_text"]} font-semibold' if active else f'{style["muted"]} hover:{style["accent_text"].replace("text-", "text-")}'
    aria = ' aria-current="page"' if active else ""
    return (
        f'<a href="#"{aria} className="inline-flex items-center px-3 py-2 text-sm sm:text-[0.95rem] '
        f'font-medium transition {state}">{label}</a>'
    )


def render_tab_item(props, style):
    label = _t(props.get("label"), "Overview", 28)
    selected = bool(props.get("selected"))
    cls = (
        f'border-b-2 {style["accent_text"]} font-semibold'
        if selected else f'border-b-2 border-transparent {style["muted"]}'
    )
    border_color = style["border"].replace("border-", "border-b-") if selected else ""
    return (
        f'<button type="button" role="tab" aria-selected="{"true" if selected else "false"}" '
        f'className="px-3 py-2.5 text-sm sm:text-[0.95rem] transition hover:opacity-80 {cls} {border_color}">{label}</button>'
    )


def render_accordion_item(props, style):
    q = _t(props.get("question"), "How does onboarding work?", 80)
    a = _t(props.get("answer"), "You get a guided setup, sample data, and a specialist on your first call.", 200)
    return (
        f'<div className="{style["card"]} overflow-hidden">'
        f'<button type="button" aria-expanded="false" '
        f'className="flex w-full items-center justify-between gap-4 px-4 py-4 text-left sm:px-5">'
        f'<span className="text-sm font-semibold {style["heading"]} sm:text-base">{q}</span>'
        f'<span className="{style["accent_text"]}">{_icon("chevron", "h-5 w-5")}</span></button>'
        f'<div className="px-4 pb-4 text-sm leading-relaxed {style["muted"]} sm:px-5">{a}</div></div>'
    )


def render_timeline_item(props, style):
    time_label = _t(props.get("time"), "Step 1", 24)
    title = _t(props.get("title"), "Discovery call", 48)
    desc = _t(props.get("description"), "We map your goals and align on a clear, measurable plan.", 140)
    return (
        f'<li className="relative pl-8 sm:pl-10">'
        f'<span className="absolute left-0 top-1 flex h-6 w-6 items-center justify-center rounded-full {style["accent"]} {style["on_accent"]}">'
        f'{_icon("check", "h-3.5 w-3.5")}</span>'
        f'<span className="absolute left-[11px] top-7 h-full w-px {style["border"]} bg-current opacity-20" aria-hidden="true"></span>'
        f'<p className="text-xs font-semibold uppercase tracking-wide {style["accent_text"]}">{time_label}</p>'
        f'<h3 className="mt-1 text-base font-semibold {style["heading"]}">{title}</h3>'
        f'<p className="mt-1 text-sm leading-relaxed {style["muted"]}">{desc}</p></li>'
    )


def render_cta_group(props, style):
    primary = _t(props.get("primary"), "Get started", 28)
    secondary = _t(props.get("secondary"), "Talk to sales", 28)
    return (
        f'<div className="flex flex-col gap-3 sm:flex-row sm:items-center">'
        f'<button type="button" className="{style["btn_primary"]}"><span>{primary}</span>{_icon("arrow", "h-4 w-4")}</button>'
        f'<button type="button" className="{style["btn_secondary"]}">{secondary}</button></div>'
    )


def render_image_panel(props, style):
    caption = _t(props.get("caption"), "Designed for real workflows", 60)
    return (
        f'<figure className="relative overflow-hidden {style["radius"]} {style["border_w"]} {style["border"]} {style["shadow"]}">'
        f'{_img(props.get("image"), caption, "aspect-[16/10] w-full object-cover", "/generated/panel-1.jpg")}'
        f'<figcaption className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent px-4 py-3 text-sm font-medium text-white sm:px-5">{caption}</figcaption></figure>'
    )


def render_logo_item(props, style):
    label = _t(props.get("label"), "Partner", 20)
    initials = "".join(w[0] for w in label.split()[:2]).upper() or "AB"
    return (
        f'<div className="flex items-center justify-center gap-2 {style["radius"]} {style["surface_alt"]} px-4 py-3 sm:px-5">'
        f'<span className="flex h-7 w-7 items-center justify-center rounded-md {style["accent"]} {style["on_accent"]} text-xs font-bold" aria-hidden="true">{initials}</span>'
        f'<span className="text-sm font-semibold {style["muted"]}">{label}</span></div>'
    )


def render_trust_badge(props, style):
    label = _t(props.get("label"), "Encrypted & secure", 32)
    sub = _t(props.get("sub"), "End-to-end protection", 40)
    return (
        f'<div className="inline-flex items-center gap-2.5 {style["radius"]} {style["border_w"]} {style["border"]} {style["surface"]} px-3.5 py-2.5 sm:px-4">'
        f'<span className="flex h-8 w-8 items-center justify-center rounded-lg {style["chip_bg"]} {style["accent_text"]}">{_icon("shield", "h-4 w-4")}</span>'
        f'<span><span className="block text-sm font-semibold {style["heading"]}">{label}</span>'
        f'<span className="block text-xs {style["muted"]}">{sub}</span></span></div>'
    )


def render_footer_links(props, style):
    heading = _t(props.get("heading"), "Product", 28)
    links = props.get("links") or ["Features", "Pricing", "Integrations", "Changelog"]
    items = "".join(
        f'<li><a href="#" className="text-sm {style["muted"]} transition hover:{style["accent_text"].replace("text-", "text-")}">{_t(l, "Link", 28)}</a></li>'
        for l in list(links)[:6]
    )
    return (
        f'<div className="space-y-3">'
        f'<h4 className="text-xs font-semibold uppercase tracking-wide {style["heading"]} sm:text-sm">{heading}</h4>'
        f'<ul className="space-y-2">{items}</ul></div>'
    )


# component_type -> renderer
RENDERERS = {
    "button": render_button,
    "badge": render_badge,
    "stat card": render_stat_card,
    "feature card": render_feature_card,
    "service card": render_service_card,
    "product card": render_product_card,
    "vehicle card": render_vehicle_card,
    "property card": render_property_card,
    "course card": render_course_card,
    "profile card": render_profile_card,
    "doctor card": render_doctor_card,
    "trainer card": render_trainer_card,
    "restaurant menu card": render_menu_card,
    "travel package card": render_travel_package_card,
    "pricing card": render_pricing_card,
    "testimonial card": render_testimonial_card,
    "dashboard metric card": render_metric_card,
    "chart preview card": render_chart_card,
    "table preview": render_table_preview,
    "search box": render_search_box,
    "form field": render_form_field,
    "nav item": render_nav_item,
    "tab item": render_tab_item,
    "accordion item": render_accordion_item,
    "timeline item": render_timeline_item,
    "cta button group": render_cta_group,
    "image panel": render_image_panel,
    "logo cloud item": render_logo_item,
    "trust badge": render_trust_badge,
    "footer link group": render_footer_links,
}


def render_block(component_type: str, props: dict = None, style: dict = None) -> str:
    """Render a single component by type with an explicit style pack.

    Used internally and by `professional_sections.py` to compose sections.
    """
    fn = RENDERERS.get(component_type)
    if not fn:
        return f'<div className="text-sm text-slate-500">Unknown block: {_t(component_type, "block", 40)}</div>'
    return fn(dict(props or {}), style or family_style("dashboard-operations", "soft"))


# --------------------------------------------------------------------------- #
# Domain affinity, search, anti-copy validation (shared with sections)
# --------------------------------------------------------------------------- #

_TYPE_DOMAINS = {
    "stat card": ["business-ops", "saas", "fintech"],
    "feature card": ["saas", "ai-devtools", "business-ops"],
    "service card": ["healthcare", "business-ops", "agency", "fitness"],
    "product card": ["ecommerce"],
    "vehicle card": ["automotive"],
    "property card": ["real-estate"],
    "course card": ["education"],
    "profile card": ["community", "agency"],
    "doctor card": ["healthcare"],
    "trainer card": ["fitness"],
    "restaurant menu card": ["restaurant"],
    "travel package card": ["travel"],
    "pricing card": ["saas", "fintech", "ecommerce", "business-ops"],
    "testimonial card": [],
    "dashboard metric card": ["business-ops", "saas", "fintech"],
    "chart preview card": ["business-ops", "saas", "fintech"],
    "table preview": ["business-ops", "fintech", "saas"],
    "search box": [],
    "form field": [],
    "nav item": [],
    "tab item": [],
    "accordion item": [],
    "timeline item": [],
    "cta button group": [],
    "image panel": [],
    "logo cloud item": [],
    "trust badge": [],
    "footer link group": [],
    "button": [],
    "badge": [],
}

# Domain -> keyword vocabulary. Single words match on token; multi-word match on phrase.
DOMAIN_KEYWORDS = {
    "healthcare": ["hospital", "clinic", "health", "patient", "doctor", "medical", "appointment",
                   "lab", "emergency", "portal", "care", "nurse", "pharmacy", "telehealth"],
    "automotive": ["vehicle", "car", "auto", "automotive", "dealer", "dealership", "showroom",
                   "inventory", "financing", "drive", "motor", "ev"],
    "restaurant": ["restaurant", "menu", "dining", "food", "reservation", "table", "chef",
                   "cuisine", "eatery", "bistro"],
    "real-estate": ["property", "listing", "home", "house", "rent", "mortgage", "agent",
                    "neighborhood", "apartment", "realty", "real estate"],
    "travel": ["travel", "tour", "trip", "destination", "itinerary", "vacation", "flight",
               "hotel", "tourism", "explore", "getaway"],
    "fitness": ["fitness", "gym", "workout", "trainer", "coach", "wellness", "class",
                "program", "exercise", "studio"],
    "education": ["course", "education", "learning", "lesson", "student", "school", "lms",
                  "curriculum", "instructor", "training", "catalog", "academy"],
    "ecommerce": ["ecommerce", "shop", "store", "product", "cart", "checkout", "retail",
                  "marketplace", "collection", "sale"],
    "saas": ["saas", "software", "platform", "dashboard", "workflow", "productivity", "app",
             "tool", "subscription", "onboarding"],
    "ai-devtools": ["ai", "api", "developer", "devtool", "code", "sdk", "automation", "agent",
                    "ml", "model", "terminal", "console"],
    "business-ops": ["pos", "erp", "inventory", "operations", "business", "admin", "report",
                     "logistics", "supply", "back-office", "ops"],
    "fintech": ["fintech", "finance", "payment", "bank", "transaction", "wallet", "invoice",
                "ledger", "crypto", "money", "loan", "billing"],
    "agency": ["agency", "portfolio", "creative", "studio", "brand", "design", "marketing",
               "case study"],
    "community": ["community", "social", "forum", "member", "network", "feed", "group",
                  "creator", "profile"],
    "media": ["media", "content", "blog", "news", "magazine", "video", "publishing",
              "editorial", "podcast"],
}

_BANNED_NAMES = {
    "stripe", "apple", "nike", "linear", "notion", "figma", "vercel", "framer", "webflow",
    "slack", "dropbox", "airtable", "miro", "asana", "monday", "clickup", "calendly",
    "square", "shopify", "toast", "lightspeed", "clover", "odoo", "zoho", "quickbooks",
    "xero", "tesla", "ikea", "amazon", "etsy", "glossier", "patagonia", "gymshark",
    "mailchimp", "hubspot", "intercom", "typeform", "canva", "headspace", "duolingo",
    "grammarly", "discord", "reddit", "github", "linkedin", "pinterest", "openai",
    "anthropic", "perplexity", "cursor", "replit", "gitlab", "supabase", "cloudflare",
    "wise", "revolut", "monzo", "mercury", "ramp", "brex", "paypal", "coinbase",
    "robinhood", "coursera", "edx", "udemy", "spotify", "masterclass", "airbnb",
    "booking.com", "expedia", "zillow", "redfin", "doordash", "uber", "netflix",
}

_URL_RE = re.compile(r"(https?://|www\.|[a-z0-9-]+\.(?:com|app|ai|io|co|net|org|tech|dev|xyz)\b)", re.I)
_IMAGE_PATH_RE = re.compile(r"(/assets/|/generated/|[A-Za-z0-9_-]+\.(?:jpg|jpeg|png|webp|svg|gif)\b)", re.I)


def _tokens(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", str(text or "").lower()))


def prompt_domains(prompt: str) -> set:
    """Infer which domains a free-text prompt is about."""
    low = " " + str(prompt or "").lower() + " "
    words = _tokens(prompt)
    active = set()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if " " in kw:
                if kw in low:
                    active.add(domain)
                    break
            elif kw in words:
                active.add(domain)
                break
    return active


def _record_blob(record: dict, fields) -> str:
    parts = []
    for key in fields:
        value = record.get(key)
        if isinstance(value, list):
            parts.extend(str(v) for v in value)
        elif value is not None:
            parts.append(str(value))
    return " ".join(parts).lower()


def search_records(records, prompt, max_results=50, blob_fields=(), type_field="component_type",
                   domain_field="domain_fit", page_type=None, diversify=True,
                   type_domains_map=None):
    """Generic domain-aware search reused by components and sections.

    Ranks by domain intent (a record whose *type* targets an active domain wins),
    then literal keyword overlap, then quality. A light per-type / per-family
    diversity pass keeps results from collapsing into one repeated block.
    """
    prompt = str(prompt or "")
    words = _tokens(prompt)
    pdomains = prompt_domains(prompt)
    type_domains_map = type_domains_map if type_domains_map is not None else _TYPE_DOMAINS
    max_results = max(1, int(max_results or 50))

    def in_scope(record):
        return not (page_type and record.get("page_type") and record.get("page_type") != page_type)

    scored = []
    for record in records:
        if not in_scope(record):
            continue
        blob = _record_blob(record, blob_fields)
        lexical = sum(2 for w in words if len(w) > 1 and re.search(rf"\b{re.escape(w)}\b", blob))
        type_dom = set(type_domains_map.get(record.get(type_field, ""), []))
        rec_dom = set(record.get(domain_field, []))
        type_boost = 55 * len(pdomains & type_dom)
        fit_boost = 12 * len(pdomains & rec_dom)
        type_word_boost = 10 * len(words & _tokens(record.get(type_field, "")))
        score = lexical + type_boost + fit_boost + type_word_boost
        if score:
            scored.append((score, record.get("quality_score", 0), record.get(_id_field(record), ""), record))
    if not scored:
        scored = [
            (record.get("quality_score", 0), record.get("quality_score", 0),
             record.get(_id_field(record), ""), record)
            for record in records if in_scope(record)
        ]
    scored.sort(key=lambda row: (-row[0], -row[1], row[2]))

    type_cap = max(2, max_results // 5)
    fam_cap = max(3, max_results // 3)
    selected, deferred = [], []
    type_counts, fam_counts = Counter(), Counter()
    for _score, _q, _id, record in scored:
        if len(selected) >= max_results:
            break
        t = record.get(type_field, "")
        fam = record.get("visual_family", "")
        if diversify and (type_counts[t] >= type_cap or fam_counts[fam] >= fam_cap):
            deferred.append(record)
            continue
        selected.append(record)
        type_counts[t] += 1
        fam_counts[fam] += 1
    for record in deferred:  # backfill if diversity caps left us short
        if len(selected) >= max_results:
            break
        selected.append(record)
    return copy.deepcopy(selected[:max_results])


def _id_field(record: dict) -> str:
    return "component_id" if "component_id" in record else "section_id"


# --------------------------------------------------------------------------- #
# Record factory + library build
# --------------------------------------------------------------------------- #

_TYPE_PROPS = {
    "button": (["label"], ["variant", "icon"]),
    "badge": (["label"], ["icon"]),
    "stat card": (["value", "label"], ["delta"]),
    "feature card": (["title", "description"], ["icon"]),
    "service card": (["title", "description"], ["points", "icon"]),
    "product card": (["title", "price"], ["image", "category", "rating"]),
    "vehicle card": (["name", "price"], ["image", "specs"]),
    "property card": (["title", "price", "address"], ["image", "facts"]),
    "course card": (["title"], ["image", "level", "instructor", "lessons", "rating"]),
    "profile card": (["name", "role"], ["avatar", "bio"]),
    "doctor card": (["name", "specialty"], ["avatar", "rating", "availability"]),
    "trainer card": (["name", "discipline"], ["image", "sessions"]),
    "restaurant menu card": (["name", "price"], ["image", "description", "tags"]),
    "travel package card": (["name", "price"], ["image", "region", "highlights"]),
    "pricing card": (["plan", "price"], ["period", "features", "featured"]),
    "testimonial card": (["quote", "author"], ["role", "avatar", "rating"]),
    "dashboard metric card": (["label", "value"], ["trend", "direction"]),
    "chart preview card": (["title"], ["range"]),
    "table preview": (["title"], ["headers"]),
    "search box": ([], ["placeholder", "label"]),
    "form field": (["label"], ["helper", "placeholder", "type"]),
    "nav item": (["label"], ["active"]),
    "tab item": (["label"], ["selected"]),
    "accordion item": (["question", "answer"], []),
    "timeline item": (["title"], ["time", "description"]),
    "cta button group": (["primary"], ["secondary"]),
    "image panel": ([], ["image", "caption"]),
    "logo cloud item": (["label"], []),
    "trust badge": (["label"], ["sub"]),
    "footer link group": (["heading"], ["links"]),
}

_A11Y_NOTES = {
    "button": "Native <button> with type, visible focus ring, and icon marked aria-hidden.",
    "badge": "Inline status pill with sufficient contrast and decorative icon hidden from AT.",
    "search box": "Wrapped in role=search with an associated (sr-only) label and submit button.",
    "form field": "Explicit <label htmlFor>, helper text, and a visible focus ring.",
    "table preview": "Semantic <table> with scoped <th> headers and horizontal scroll on mobile.",
    "nav item": "Anchor with aria-current on the active item and a clear hover/focus state.",
    "tab item": "role=tab with aria-selected reflecting state.",
    "accordion item": "Toggle exposes aria-expanded; panel text meets contrast.",
    "image panel": "Decorative imagery carries descriptive alt text; caption is real text, not baked-in.",
    "doctor card": "Rating exposes aria-label; availability and CTA are keyboard reachable.",
}


def _props_summary(required, optional):
    bits = []
    if required:
        bits.append("requires " + ", ".join(required))
    if optional:
        bits.append("optional " + ", ".join(optional[:4]))
    return "; ".join(bits) or "no props required"


def _make_component_record(ctype, family, variant, serial, local_index):
    fam = _FAMILIES.get(family, {})
    quality = min(99, 84 + ((serial + local_index) % 14))
    type_domains = _TYPE_DOMAINS.get(ctype, [])
    # Domain-specific types (doctor/vehicle/property/...) are defined by their TYPE,
    # not the visual skin. Generic types (button, badge, testimonial...) inherit the
    # family's natural domains. This keeps domain search crisp.
    source = type_domains if type_domains else fam.get("domains", [])
    domain_fit = []
    for d in source:
        if d not in domain_fit:
            domain_fit.append(d)
    required, optional = _TYPE_PROPS.get(ctype, ([], []))
    fn = RENDERERS[ctype]
    label = _FAMILY_LABELS.get(family, family)
    return {
        "component_id": f"cmp-{serial:04d}",
        "name": f"{label} {ctype.title()} · {variant} #{local_index + 1:02d}",
        "component_type": ctype,
        "domain_fit": domain_fit,
        "visual_family": family,
        "variant": variant,
        "quality_score": quality,
        "required_props": list(required),
        "optional_props": list(optional),
        "responsive_support": ["mobile", "tablet", "desktop"],
        "accessibility_notes": _A11Y_NOTES.get(
            ctype,
            "Semantic markup, descriptive alt text on imagery, and visible focus states throughout.",
        ),
        "code_ref": f"app/professional_components.py::{fn.__name__}",
        "render_function_name": fn.__name__,
        "selection_summary": (
            f"{label} {ctype} in the {variant} treatment — "
            f"fits {', '.join(domain_fit[:3]) or 'general'} products; {_props_summary(required, optional)}."
        ),
    }


def _build_components():
    records, serial = [], 1
    counters = Counter()
    for ctype in COMPONENT_TYPES:
        for family in VISUAL_FAMILIES:
            for variant in VARIANTS:
                records.append(_make_component_record(ctype, family, variant, serial, counters[ctype]))
                counters[ctype] += 1
                serial += 1
    return records


COMPONENTS = _build_components()
_COMPONENT_INDEX = {c["component_id"]: c for c in COMPONENTS}

_COMPONENT_BLOB_FIELDS = (
    "name", "component_type", "visual_family", "domain_fit", "selection_summary",
)


# --------------------------------------------------------------------------- #
# Public API (component half)
# --------------------------------------------------------------------------- #

def get_all_components() -> list:
    return copy.deepcopy(COMPONENTS)


def get_component_by_id(component_id: str):
    record = _COMPONENT_INDEX.get(str(component_id or "").strip())
    return copy.deepcopy(record) if record else None


def get_components_by_type(component_type: str, family: str = None, max_results: int = 50) -> list:
    out = [
        c for c in COMPONENTS
        if c["component_type"] == component_type and (family is None or c["visual_family"] == family)
    ]
    return copy.deepcopy(out[:max_results])


def search_components(prompt: str, max_results: int = 50) -> list:
    return search_records(
        COMPONENTS, prompt, max_results,
        blob_fields=_COMPONENT_BLOB_FIELDS, type_field="component_type",
    )


def render_component(component_id: str, props: dict = None) -> str:
    record = _COMPONENT_INDEX.get(str(component_id or "").strip())
    if not record:
        return f'<div className="text-sm text-slate-500">Unknown component: {_t(component_id, "?", 40)}</div>'
    style = family_style(record["visual_family"], record.get("variant", "soft"))
    return render_block(record["component_type"], props, style)


def summarize_components(records=None) -> dict:
    records = records if records is not None else COMPONENTS
    return {
        "total": len(records),
        "component_types": sorted({r["component_type"] for r in records}),
        "visual_families": sorted({r["visual_family"] for r in records}),
        "domains": sorted({d for r in records for d in r.get("domain_fit", [])}),
        "type_counts": dict(Counter(r["component_type"] for r in records)),
        "family_counts": dict(Counter(r["visual_family"] for r in records)),
    }


# --------------------------------------------------------------------------- #
# Validation helpers (shared)
# --------------------------------------------------------------------------- #

def scan_text_for_violations(text: str) -> list:
    """Return anti-copy violations for METADATA text (URLs, image paths, brands)."""
    issues = []
    low = str(text or "")
    if _URL_RE.search(low):
        issues.append(f"url-like text: {low[:60]}")
    if _IMAGE_PATH_RE.search(low):
        issues.append(f"image-path-like text: {low[:60]}")
    lowered = low.lower()
    for banned in sorted(_BANNED_NAMES, key=len, reverse=True):
        if " " in banned or "." in banned:
            if banned in lowered:
                issues.append(f"banned brand: {banned}")
                break
        elif re.search(rf"\b{re.escape(banned)}\b", lowered):
            issues.append(f"banned brand: {banned}")
            break
    return issues


def scan_jsx_for_violations(jsx: str) -> list:
    """Return anti-copy violations for RENDERED JSX. Local /generated/*.jpg slots
    are allowed; any other asset path, URL, or brand name is a violation."""
    issues = []
    low = str(jsx or "")
    if _URL_RE.search(low):
        issues.append("url in rendered jsx")
    for src in re.findall(r'src="([^"]*)"', low):
        if not _SAFE_IMG_RE.match(src.lower()):
            issues.append(f"non-allowed asset path: {src}")
    lowered = low.lower()
    for banned in sorted(_BANNED_NAMES, key=len, reverse=True):
        if " " in banned or "." in banned:
            if banned in lowered:
                issues.append(f"banned brand in jsx: {banned}")
                break
        elif re.search(rf"\b{re.escape(banned)}\b", lowered):
            issues.append(f"banned brand in jsx: {banned}")
            break
    return issues


COMPONENT_REQUIRED_FIELDS = {
    "component_id", "name", "component_type", "domain_fit", "visual_family",
    "quality_score", "required_props", "optional_props", "responsive_support",
    "accessibility_notes", "code_ref", "render_function_name", "selection_summary",
}


def validate_components(min_count: int = 1000) -> dict:
    errors = []
    records = COMPONENTS
    if len(records) < min_count:
        errors.append(f"expected >= {min_count} components, found {len(records)}")
    ids = [r["component_id"] for r in records]
    if len(set(ids)) != len(ids):
        errors.append("component ids are not unique")
    types = {r["component_type"] for r in records}
    if len(types) < 25:
        errors.append(f"expected >= 25 component types, found {len(types)}")
    families = {r["visual_family"] for r in records}
    if len(families) < 15:
        errors.append(f"expected >= 15 visual families, found {len(families)}")
    domains = {d for r in records for d in r.get("domain_fit", [])}
    if len(domains) < 15:
        errors.append(f"expected >= 15 domains, found {len(domains)}")

    for record in records:
        missing = COMPONENT_REQUIRED_FIELDS - set(record)
        if missing:
            errors.append(f"{record.get('component_id')} missing {sorted(missing)}")
        if not isinstance(record.get("quality_score"), (int, float)) or record.get("quality_score", 0) < 80:
            errors.append(f"{record.get('component_id')} quality_score below 80")
        for field in ("name", "selection_summary", "accessibility_notes"):
            for issue in scan_text_for_violations(record.get(field, "")):
                errors.append(f"{record.get('component_id')} {field}: {issue}")

    # Render smoke test: one representative per component type must render valid JSX.
    for ctype in COMPONENT_TYPES:
        sample = next((r for r in records if r["component_type"] == ctype), None)
        if not sample:
            errors.append(f"no record for component type {ctype}")
            continue
        jsx = render_component(sample["component_id"], {})
        if not (isinstance(jsx, str) and jsx.startswith("<") and "className=" in jsx):
            errors.append(f"{ctype} did not render valid JSX")
        for issue in scan_jsx_for_violations(jsx):
            errors.append(f"{ctype} render: {issue}")
    return {
        "ok": not errors,
        "errors": errors,
        "component_count": len(records),
        "type_count": len(types),
        "family_count": len(families),
        "domain_count": len(domains),
    }
