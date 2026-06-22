"""Premium hero visual panels (no more gray placeholder boxes).

A large blank gray hero image looks unfinished, and stubbed/placeholder images
are common. Instead of betting the hero on a single big image, `hero_panel`
composes a domain-specific "product mockup" panel — a stacked preview card with
real domain rows plus floating accent cards/chips — so the first screen always
reads as intentional and finished even when no real image exists.

Used by `professional_sections.render_hero`. Different pages of the same app get
different panel variants (home = strongest, secondary = compact) so heroes are
not all identical.
"""
from __future__ import annotations

from app import professional_components as pc

_t = pc._t
_icon = pc._icon


def _family_domain(family: str) -> str:
    return {
        "clinical-trust": "healthcare", "healthcare-saas": "healthcare",
        "premium-automotive": "vehicle", "restaurant-editorial": "restaurant",
        "travel-destination": "travel", "real-estate-listing": "real-estate",
        "fitness-coaching": "fitness", "education-editorial": "education",
        "ecommerce-premium": "ecommerce", "saas-gradient": "saas",
        "devtool-console": "ai-devtools", "fintech-trust": "fintech",
        "agency-editorial": "agency", "community-social": "community",
        "dashboard-operations": "business-ops",
    }.get(family, "saas")


# domain -> (eyebrow, title, rows[(label,value)], badge_text, icon)
_PANELS = {
    "healthcare": ("Today", "Care schedule",
                   [("Dr. A. Rivera · Cardiology", "09:30"), ("Lab results", "Ready"),
                    ("Prescription refill", "2 due")], "Next visit · 3:30 PM", "calendar"),
    "real-estate": ("Saved", "Your shortlist",
                    [("Maple Heights · 3 bd", "$615k"), ("River Loft · 2 bd", "$430k"),
                     ("Garden Cottage", "$389k")], "3 tours booked", "pin"),
    "fitness": ("This week", "Your plan",
                [("HIIT Burn · Studio A", "Mon 6:00"), ("Strength 101", "Wed 7:00"),
                 ("Mobility flow", "Fri 6:30")], "2 seats left", "bolt"),
    "restaurant": ("Tonight", "Your table",
                   [("Table for two", "7:30 PM"), ("Chef's tasting menu", "$48"),
                    ("Window seat", "Confirmed")], "Reserved", "star"),
    "travel": ("Your trip", "Coastal escape",
               [("Amalfi Coast", "5 nights"), ("Guided sunset sail", "Day 3"),
                ("Boutique stay", "Sea view")], "From $1,290", "pin"),
    "vehicle": ("Your match", "Volt GT Electric",
                [("List price", "$42,500"), ("Finance", "$520 / mo"),
                 ("Range", "412 mi")], "Book a test drive", "bolt"),
    "ai-devtools": ("api.run", "agents/run",
                    [("POST /v1/agents/run", "240 ms"), ("tokens", "1,284"),
                     ("model", "fast-1")], "status · ok", "spark"),
    "education": ("Your path", "UX Designer track",
                  [("Module 2 · Research", "60%"), ("Next lesson", "Interviews"),
                   ("Capstone", "Locked")], "On track", "play"),
    "ecommerce": ("Cart", "Your picks",
                  [("Aurora Lamp", "$89"), ("Drift Chair", "$240"),
                   ("Pebble Speaker", "$129")], "Free shipping", "star"),
    "fintech": ("Account", "This month",
                [("Balance", "$24,180"), ("Incoming", "$6,420"),
                 ("Outgoing", "$3,910")], "+2.4%", "bolt"),
    "business-ops": ("Operations", "Live board",
                     [("Open orders", "27"), ("Low stock", "4"),
                      ("Shipments", "12")], "All on track", "spark"),
}
_DEFAULT_PANEL = ("Overview", "Your workspace",
                  [("Revenue", "$84.2k"), ("Active users", "12,480"),
                   ("Tasks done", "318")], "+12% this month", "spark")


def hero_panel(domain_or_family: str, style: dict, variant: str = "primary", image=None) -> str:
    """Return a polished, domain-specific hero panel (never a blank gray box)."""
    domain = domain_or_family if domain_or_family in _PANELS else _family_domain(domain_or_family)
    eyebrow, title, rows, badge, icon = _PANELS.get(domain, _DEFAULT_PANEL)

    compact = variant == "secondary"
    shown = rows[:2] if compact else rows[:3]
    mono = " font-mono" if domain == "ai-devtools" else ""

    # A small REAL cover image on the mockup card: the panel stays a polished
    # data mockup (never a blank gray box) but always integrates one generated
    # image, so even photo-light domains (devtools/console) have real imagery on
    # the first screen. `hero.jpg` is a canonical generated slot, so it always
    # resolves (real image, or the tasteful gradient fallback).
    cover_h = "h-16" if compact else "h-24 sm:h-28"
    cover = pc._img(image, title, f"{cover_h} w-full {style['radius']} object-cover",
                    "/generated/hero.jpg")

    row_html = "".join(
        f'<div className="flex items-center justify-between gap-4 border-t {style["border"]} py-2.5 first:border-t-0">'
        f'<span className="text-sm{mono} {style["muted"]}">{_t(label, "Item", 40)}</span>'
        f'<span className="text-sm{mono} font-semibold {style["heading"]}">{_t(value, "", 18)}</span></div>'
        for label, value in shown
    )

    floating = (
        f'<div className="absolute -bottom-4 -left-4 hidden items-center gap-2 rounded-xl {style["surface"]} '
        f'{style["border_w"]} {style["border"]} px-3 py-2 shadow-lg sm:flex">'
        f'<span className="flex h-7 w-7 items-center justify-center rounded-lg {style["accent"]} {style["on_accent"]}">'
        f'{_icon(icon, "h-4 w-4")}</span>'
        f'<span className="text-xs font-semibold {style["heading"]}">{_t(badge, "", 28)}</span></div>'
    )

    return (
        f'<div className="relative">'
        f'<div className="{style["card"]} p-5 sm:p-6">'
        f'<div className="mb-4 overflow-hidden {style["radius"]}">{cover}</div>'
        f'<div className="flex items-center justify-between">'
        f'<div><p className="text-xs font-semibold uppercase tracking-wide {style["accent_text"]}">{_t(eyebrow, "Live", 24)}</p>'
        f'<h3 className="mt-0.5 text-base font-semibold{mono} {style["heading"]} sm:text-lg">{_t(title, "Preview", 40)}</h3></div>'
        f'<span className="flex h-9 w-9 items-center justify-center rounded-xl {style["chip_bg"]} {style["accent_text"]}">{_icon(icon, "h-5 w-5")}</span></div>'
        f'<div className="mt-3">{row_html}</div>'
        f'<div className="mt-4 flex items-center justify-between border-t {style["border"]} pt-3">'
        f'<span className="inline-flex items-center gap-1.5 rounded-full {style["chip_bg"]} {style["chip_text"]} px-3 py-1 text-xs font-medium">{_icon("check", "h-3.5 w-3.5")}{_t(badge, "Ready", 28)}</span>'
        f'<span className="text-xs {style["muted"]}">Updated just now</span></div></div>'
        f'{floating}</div>'
    )
