"""Art Director quality pass for browser-visible generated design.

This module scores the abstract Design Genome and applies original premium
composition presets. It does not copy websites, brand material, assets, text, or
layouts. The output is only internal design direction: Tailwind-safe classes,
component treatment labels, image roles, and quality diagnostics.
"""
from __future__ import annotations

import copy
import re


QUALITY_CRITERIA = [
    "hero_impact",
    "visual_hierarchy",
    "typography_scale",
    "spacing_rhythm",
    "card_polish",
    "section_variety",
    "image_usage_quality",
    "cta_clarity",
    "page_specific_uniqueness",
    "professional_feel",
    "mobile_responsiveness",
    "excessive_repetition",
    "empty_space_balance",
]


HEALTHCARE_PREMIUM_PRESETS = {
    "clinical-trust-light": {
        "id": "clinical-trust-light",
        "name": "Clinical trust light",
        "body_class": "min-h-screen bg-sky-50 text-slate-950",
        "hero_class": "relative overflow-hidden border-b border-sky-100 bg-gradient-to-br from-white via-sky-50 to-blue-100",
        "hero_layout": "large trust copy + doctor image panel + emergency/booking rail",
        "h1_class": "font-display text-5xl font-bold leading-[0.96] tracking-tight text-slate-950 md:text-7xl lg:text-8xl",
        "lead_class": "mt-6 max-w-2xl text-xl leading-8 text-slate-600 md:text-2xl",
        "section_rhythm": "premium-spacious",
        "section_class": "bg-white",
        "section_alt_class": "border-y border-sky-100 bg-sky-50/70",
        "card_classes": [
            "rounded-[2rem] border border-sky-100 bg-white p-6 shadow-xl shadow-sky-100/70",
            "rounded-3xl border border-white/70 bg-white/80 p-6 shadow-lg shadow-sky-100/50 backdrop-blur",
            "rounded-2xl border border-blue-100 bg-blue-50/70 p-6 ring-1 ring-blue-100/80",
            "rounded-[1.75rem] border border-slate-200 bg-white p-6 shadow-sm",
        ],
        "primary_cta_class": "rounded-full bg-blue-700 px-7 py-4 text-sm font-bold text-white shadow-xl shadow-blue-200/70 transition hover:bg-blue-800",
        "secondary_cta_class": "rounded-full border border-sky-200 bg-white px-7 py-4 text-sm font-bold text-slate-900 shadow-sm",
        "image_class": "rounded-[2.25rem] border border-white/80 shadow-2xl shadow-sky-200/70",
        "footer_class": "border-t border-sky-100 bg-white text-slate-700",
        "trust_stats": [("24/7", "Emergency line"), ("30+", "Departments"), ("4.8", "Patient score")],
    },
    "patient-first-warm-clinical": {
        "id": "patient-first-warm-clinical",
        "name": "Patient-first warm clinical",
        "body_class": "min-h-screen bg-amber-50 text-slate-950",
        "hero_class": "relative overflow-hidden border-b border-amber-100 bg-gradient-to-br from-amber-50 via-sky-50 to-white",
        "hero_layout": "warm patient story + care actions + portal stack",
        "h1_class": "font-display text-5xl font-bold leading-[0.98] tracking-tight text-slate-950 md:text-7xl",
        "lead_class": "mt-6 max-w-2xl text-xl leading-8 text-slate-600 md:text-2xl",
        "section_rhythm": "editorial",
        "section_class": "bg-white",
        "section_alt_class": "border-y border-amber-100 bg-amber-50/50",
        "card_classes": [
            "rounded-[2rem] border border-amber-100 bg-white p-6 shadow-xl shadow-amber-100/60",
            "rounded-3xl border border-sky-100 bg-sky-50/70 p-6 shadow-sm",
            "rounded-[1.75rem] border border-white/80 bg-white/80 p-6 shadow-lg backdrop-blur",
            "rounded-2xl border border-slate-200 bg-white p-6",
        ],
        "primary_cta_class": "rounded-full bg-slate-950 px-7 py-4 text-sm font-bold text-white shadow-xl shadow-amber-100",
        "secondary_cta_class": "rounded-full border border-amber-200 bg-white px-7 py-4 text-sm font-bold text-slate-900 shadow-sm",
        "image_class": "rounded-[2.5rem] border border-white shadow-2xl shadow-amber-100/80",
        "footer_class": "border-t border-amber-100 bg-white text-slate-700",
        "trust_stats": [("3 min", "Booking"), ("Same day", "Reports"), ("24/7", "Help desk")],
    },
    "modern-healthcare-saas": {
        "id": "modern-healthcare-saas",
        "name": "Modern healthcare SaaS",
        "body_class": "min-h-screen bg-indigo-50 text-slate-950",
        "hero_class": "relative overflow-hidden border-b border-indigo-100 bg-gradient-to-br from-white via-indigo-50 to-cyan-50",
        "hero_layout": "product mockup hero + care search + metrics strip",
        "h1_class": "font-display text-5xl font-bold leading-[0.96] tracking-tight text-slate-950 md:text-7xl lg:text-8xl",
        "lead_class": "mt-6 max-w-2xl text-xl leading-8 text-slate-600",
        "section_rhythm": "data-heavy",
        "section_class": "bg-white",
        "section_alt_class": "border-y border-indigo-100 bg-indigo-50/50",
        "card_classes": [
            "rounded-3xl border border-indigo-100 bg-white p-6 shadow-xl shadow-indigo-100/60",
            "rounded-2xl border border-cyan-100 bg-cyan-50/70 p-6",
            "rounded-[2rem] border border-white/80 bg-white/80 p-6 shadow-lg backdrop-blur",
            "rounded-xl border border-slate-200 bg-white p-5 shadow-sm",
        ],
        "primary_cta_class": "rounded-2xl bg-indigo-700 px-7 py-4 text-sm font-bold text-white shadow-xl shadow-indigo-200/70",
        "secondary_cta_class": "rounded-2xl border border-indigo-200 bg-white px-7 py-4 text-sm font-bold text-slate-900",
        "image_class": "rounded-[2rem] border border-white/80 shadow-2xl shadow-indigo-200/70",
        "footer_class": "border-t border-indigo-100 bg-white text-slate-700",
        "trust_stats": [("Live", "Care graph"), ("18", "Alerts"), ("AES", "Protected")],
    },
    "hospital-command-center": {
        "id": "hospital-command-center",
        "name": "Hospital command center",
        "body_class": "min-h-screen bg-slate-950 text-slate-50",
        "hero_class": "relative overflow-hidden border-b border-slate-800 bg-gradient-to-br from-slate-950 via-slate-900 to-sky-950 text-white",
        "hero_layout": "command center dashboard + emergency rail + secure portal CTA",
        "h1_class": "font-display text-5xl font-bold leading-[0.96] tracking-tight text-white md:text-7xl lg:text-8xl",
        "lead_class": "mt-6 max-w-2xl text-xl leading-8 text-slate-300",
        "section_rhythm": "data-heavy",
        "section_class": "bg-slate-950 text-slate-50",
        "section_alt_class": "border-y border-slate-800 bg-slate-900 text-slate-50",
        "card_classes": [
            "rounded-3xl border border-slate-700 bg-slate-900/90 p-6 text-slate-50 shadow-2xl shadow-slate-950/60",
            "rounded-2xl border border-sky-800 bg-sky-950/45 p-6 text-slate-50",
            "rounded-[2rem] border border-white/10 bg-white/10 p-6 text-slate-50 backdrop-blur",
            "rounded-xl border border-slate-800 bg-slate-950 p-5 text-slate-100",
        ],
        "primary_cta_class": "rounded-2xl bg-sky-400 px-7 py-4 text-sm font-bold text-slate-950 shadow-xl shadow-sky-950/40",
        "secondary_cta_class": "rounded-2xl border border-slate-700 bg-slate-900 px-7 py-4 text-sm font-bold text-slate-100",
        "image_class": "rounded-[2rem] border border-white/10 shadow-2xl shadow-slate-950/80",
        "footer_class": "border-t border-slate-800 bg-slate-950 text-slate-300",
        "trust_stats": [("Live", "Ops board"), ("86%", "Capacity"), ("24h", "Audit")],
    },
    "medical-editorial": {
        "id": "medical-editorial",
        "name": "Medical editorial",
        "body_class": "min-h-screen bg-slate-50 text-slate-950",
        "hero_class": "relative overflow-hidden border-b border-slate-200 bg-gradient-to-br from-white via-sky-50 to-teal-50",
        "hero_layout": "editorial trust headline + image feature + care path cards",
        "h1_class": "font-display text-6xl font-bold leading-[0.92] tracking-tight text-slate-950 md:text-8xl",
        "lead_class": "mt-7 max-w-2xl text-xl leading-9 text-slate-600 md:text-2xl",
        "section_rhythm": "editorial",
        "section_class": "bg-[#fbfcfd]",
        "section_alt_class": "border-y border-slate-200 bg-white",
        "card_classes": [
            "rounded-none border border-slate-200 bg-white p-7 shadow-lg shadow-slate-100",
            "rounded-[2rem] border border-sky-100 bg-sky-50/70 p-6",
            "rounded-3xl border border-slate-200 bg-white p-6 shadow-sm",
            "rounded-none border-l-4 border-l-blue-600 bg-white p-6",
        ],
        "primary_cta_class": "rounded-none bg-slate-950 px-7 py-4 text-sm font-bold text-white shadow-xl shadow-slate-200",
        "secondary_cta_class": "rounded-none border border-slate-300 bg-white px-7 py-4 text-sm font-bold text-slate-950",
        "image_class": "rounded-none border border-slate-200 shadow-2xl shadow-slate-200/80",
        "footer_class": "border-t border-slate-200 bg-white text-slate-700",
        "trust_stats": [("20+", "Specialties"), ("15k", "Patients"), ("4.9", "Trust score")],
    },
}


HEALTHCARE_IMAGE_ROLES = {
    "hero": "hero.jpg",
    "doctor_team": "about1.jpg",
    "department_facility": "gallery1.jpg",
    "dashboard_mockup": "feature1.jpg",
    "security_compliance": "feature2.jpg",
    "patient_portal": "gallery2.jpg",
}


COMMON_IMAGE_ROLES = {
    "hero": "hero.jpg",
    "primary_visual": "gallery1.jpg",
    "detail_visual": "gallery2.jpg",
    "dashboard_mockup": "feature1.jpg",
    "trust_visual": "feature2.jpg",
    "cta_visual": "about1.jpg",
}


DOMAIN_IMAGE_ROLES = {
    "automotive": {
        "hero": "hero.jpg",
        "vehicle_showroom": "gallery1.jpg",
        "inventory_detail": "gallery2.jpg",
        "finance_panel": "feature1.jpg",
        "test_drive": "feature2.jpg",
        "advisor": "about1.jpg",
    },
    "restaurant": {
        "hero": "hero.jpg",
        "food_signature": "gallery1.jpg",
        "dining_room": "gallery2.jpg",
        "reservation_panel": "feature1.jpg",
        "chef_story": "about1.jpg",
        "location_hours": "feature2.jpg",
    },
    "real_estate": {
        "hero": "hero.jpg",
        "property_listing": "gallery1.jpg",
        "neighborhood": "gallery2.jpg",
        "property_search": "feature1.jpg",
        "agent_trust": "about1.jpg",
        "tour_booking": "feature2.jpg",
    },
    "travel": {
        "hero": "hero.jpg",
        "destination": "gallery1.jpg",
        "itinerary": "gallery2.jpg",
        "map_route": "feature1.jpg",
        "guide": "about1.jpg",
        "tour_package": "feature2.jpg",
    },
    "fitness": {
        "hero": "hero.jpg",
        "program": "gallery1.jpg",
        "trainer": "about1.jpg",
        "schedule": "feature1.jpg",
        "transformation": "gallery2.jpg",
        "wellness_cta": "feature2.jpg",
    },
    "ai_devtool": {
        "hero": "hero.jpg",
        "console": "feature1.jpg",
        "workflow": "gallery1.jpg",
        "docs": "gallery2.jpg",
        "security": "feature2.jpg",
        "integration": "about1.jpg",
    },
    "education": {
        "hero": "hero.jpg",
        "course_catalog": "gallery1.jpg",
        "learning_path": "feature1.jpg",
        "instructor": "about1.jpg",
        "media_library": "gallery2.jpg",
        "progress": "feature2.jpg",
    },
    "ecommerce": {
        "hero": "hero.jpg",
        "product_gallery": "gallery1.jpg",
        "collection": "gallery2.jpg",
        "product_detail": "feature1.jpg",
        "checkout_trust": "feature2.jpg",
        "support": "about1.jpg",
    },
    "operations": {
        "hero": "hero.jpg",
        "ops_dashboard": "feature1.jpg",
        "workflow_queue": "gallery1.jpg",
        "resource_matrix": "feature2.jpg",
        "team_planning": "about1.jpg",
        "reports": "gallery2.jpg",
    },
    "portfolio": {
        "hero": "hero.jpg",
        "featured_work": "gallery1.jpg",
        "case_mosaic": "gallery2.jpg",
        "studio_process": "feature1.jpg",
        "capability": "feature2.jpg",
        "team": "about1.jpg",
    },
    "finance": {
        "hero": "hero.jpg",
        "dashboard": "feature1.jpg",
        "ledger": "gallery1.jpg",
        "security": "feature2.jpg",
        "workflow": "gallery2.jpg",
        "trust": "about1.jpg",
    },
}


DOMAIN_PRESET_BASES = {
    "automotive": {
        "visual_family": "automotive-showroom",
        "name": "Automotive showroom",
        "body_class": "min-h-screen bg-neutral-50 text-neutral-950",
        "hero_class": "relative overflow-hidden border-b border-neutral-200 bg-gradient-to-br from-white via-neutral-50 to-zinc-100",
        "hero_layout": "premium showroom stage + inventory action rail + test-drive CTA",
        "h1_class": "font-display text-6xl font-bold leading-[0.92] tracking-tight text-neutral-950 md:text-8xl",
        "lead_class": "mt-6 max-w-2xl text-xl leading-8 text-neutral-600",
        "section_rhythm": "image-heavy",
        "section_class": "bg-white",
        "section_alt_class": "border-y border-neutral-200 bg-neutral-50",
        "card_classes": [
            "overflow-hidden rounded-[2rem] border border-neutral-200 bg-white p-6 shadow-xl shadow-neutral-200/60",
            "rounded-none border border-neutral-300 bg-white p-6",
            "rounded-3xl border border-zinc-200 bg-zinc-50 p-6 shadow-sm",
            "rounded-2xl border border-neutral-200 bg-white p-5 ring-1 ring-neutral-100",
        ],
        "primary_cta_class": "rounded-full bg-neutral-950 px-7 py-4 text-sm font-bold text-white shadow-xl shadow-neutral-300/80",
        "secondary_cta_class": "rounded-full border border-neutral-300 bg-white px-7 py-4 text-sm font-bold text-neutral-950",
        "image_class": "rounded-[2.5rem] border border-white shadow-2xl shadow-neutral-300/80",
        "footer_class": "border-t border-neutral-200 bg-neutral-950 text-neutral-100",
        "quality_rules": ["show inventory action above fold", "include finance CTA", "include test-drive path"],
        "trust_stats": [("36", "Vehicles ready"), ("0-1", "Click inquiry"), ("24h", "Finance check")],
        "rich_components": ["showroom-stage", "inventory-card-grid", "finance-cta-panel", "test-drive-stepper", "spec-comparison"],
    },
    "restaurant": {
        "visual_family": "restaurant-reservation",
        "name": "Restaurant reservation",
        "body_class": "min-h-screen bg-stone-50 text-stone-950",
        "hero_class": "relative overflow-hidden border-b border-orange-200 bg-gradient-to-br from-stone-50 via-orange-50 to-rose-50",
        "hero_layout": "food-led hero + reservation CTA + menu and hours preview",
        "h1_class": "font-display text-6xl font-bold leading-[0.92] tracking-tight text-stone-950 md:text-8xl",
        "lead_class": "mt-6 max-w-2xl text-xl leading-8 text-stone-600",
        "section_rhythm": "image-heavy",
        "section_class": "bg-stone-50",
        "section_alt_class": "border-y border-orange-200 bg-orange-50/80",
        "card_classes": [
            "rounded-[2rem] border border-orange-200 bg-white p-6 shadow-xl shadow-orange-100/70",
            "rounded-none border-y-4 border-y-rose-700 bg-white p-6 shadow-lg",
            "rounded-3xl border border-stone-200 bg-stone-950 p-6 text-stone-50",
            "rounded-full border border-orange-200 bg-white px-6 py-5 shadow-sm",
        ],
        "primary_cta_class": "rounded-full bg-rose-700 px-7 py-4 text-sm font-bold text-white shadow-xl shadow-rose-100",
        "secondary_cta_class": "rounded-full border border-orange-300 bg-white px-7 py-4 text-sm font-bold text-stone-950",
        "image_class": "rounded-[2.5rem] border border-white shadow-2xl shadow-orange-100/80",
        "footer_class": "border-t border-orange-200 bg-stone-950 text-stone-100",
        "quality_rules": ["show reservation CTA", "include menu preview", "include hours and location"],
        "trust_stats": [("7:30", "Next table"), ("42", "Seats left"), ("6-10", "Dinner hours")],
        "rich_components": ["food-hero-gallery", "reservation-panel", "menu-preview-grid", "hours-location-block", "chef-ambience-story"],
    },
    "real_estate": {
        "visual_family": "real-estate-listings",
        "name": "Real estate listings",
        "body_class": "min-h-screen bg-stone-50 text-stone-950",
        "hero_class": "relative overflow-hidden border-b border-emerald-100 bg-gradient-to-br from-white via-emerald-50 to-stone-50",
        "hero_layout": "property search hero + listing cards + agent trust cue",
        "h1_class": "font-display text-5xl font-bold leading-[0.96] tracking-tight text-stone-950 md:text-7xl",
        "lead_class": "mt-6 max-w-2xl text-xl leading-8 text-stone-600",
        "section_rhythm": "spacious",
        "section_class": "bg-stone-50",
        "section_alt_class": "border-y border-emerald-100 bg-white",
        "card_classes": [
            "overflow-hidden rounded-[2rem] border border-stone-200 bg-white p-6 shadow-xl shadow-stone-200/70",
            "rounded-3xl border border-emerald-100 bg-white p-6 shadow-md shadow-emerald-100/60",
            "rounded-xl border border-stone-200 bg-white p-5",
            "rounded-[1.75rem] border border-emerald-200 bg-emerald-50/70 p-6",
        ],
        "primary_cta_class": "rounded-xl bg-emerald-700 px-7 py-4 text-sm font-bold text-white shadow-xl shadow-emerald-100",
        "secondary_cta_class": "rounded-xl border border-emerald-200 bg-white px-7 py-4 text-sm font-bold text-stone-950",
        "image_class": "rounded-[2rem] border border-white shadow-2xl shadow-emerald-100/80",
        "footer_class": "border-t border-emerald-100 bg-white text-stone-700",
        "quality_rules": ["show property search", "include listing card treatment", "include agent trust"],
        "trust_stats": [("18", "New listings"), ("4", "Open tours"), ("24h", "Agent reply")],
        "rich_components": ["property-search-hero", "listing-card-row", "agent-trust-panel", "neighborhood-grid", "tour-cta"],
    },
    "travel": {
        "visual_family": "travel-destination",
        "name": "Travel destination",
        "body_class": "min-h-screen bg-cyan-50 text-slate-950",
        "hero_class": "relative overflow-hidden border-b border-sky-200 bg-gradient-to-br from-cyan-50 via-white to-amber-50",
        "hero_layout": "destination hero + itinerary cards + route/map panel",
        "h1_class": "font-display text-6xl font-bold leading-[0.92] tracking-tight text-slate-950 md:text-8xl",
        "lead_class": "mt-6 max-w-2xl text-xl leading-8 text-slate-600",
        "section_rhythm": "image-heavy",
        "section_class": "bg-cyan-50",
        "section_alt_class": "border-y border-sky-100 bg-white",
        "card_classes": [
            "overflow-hidden rounded-[2.25rem] border border-sky-100 bg-white p-6 shadow-xl shadow-sky-100/80",
            "rounded-2xl border border-dashed border-teal-300 bg-white p-6",
            "rounded-full border border-cyan-200 bg-white px-6 py-5 shadow-sm",
            "rounded-3xl border border-amber-100 bg-amber-50/70 p-6",
        ],
        "primary_cta_class": "rounded-full bg-teal-700 px-7 py-4 text-sm font-bold text-white shadow-xl shadow-teal-100",
        "secondary_cta_class": "rounded-full border border-sky-200 bg-white px-7 py-4 text-sm font-bold text-slate-950",
        "image_class": "rounded-[2.5rem] border border-white shadow-2xl shadow-sky-100/80",
        "footer_class": "border-t border-sky-100 bg-cyan-950 text-cyan-50",
        "quality_rules": ["show destination hero", "include itinerary cards", "include location/map section"],
        "trust_stats": [("24", "Trips ready"), ("3", "Day sample"), ("Local", "Guide support")],
        "rich_components": ["destination-image-hero", "itinerary-card-row", "tour-package-grid", "map-location-panel", "guide-cta"],
    },
    "fitness": {
        "visual_family": "fitness-coaching",
        "name": "Fitness coaching",
        "body_class": "min-h-screen bg-lime-50 text-slate-950",
        "hero_class": "relative overflow-hidden border-b border-lime-200 bg-gradient-to-br from-lime-50 via-white to-emerald-50",
        "hero_layout": "program hero + trainer proof + schedule CTA",
        "h1_class": "font-display text-5xl font-bold leading-[0.94] tracking-tight text-slate-950 md:text-7xl",
        "lead_class": "mt-6 max-w-2xl text-xl leading-8 text-slate-600",
        "section_rhythm": "spacious",
        "section_class": "bg-lime-50",
        "section_alt_class": "border-y border-lime-200 bg-white",
        "card_classes": [
            "rounded-[2rem] border border-lime-200 bg-white p-6 shadow-xl shadow-lime-100/80",
            "overflow-hidden rounded-[1.75rem] border border-emerald-100 bg-white p-6 shadow-md",
            "rounded-full border border-lime-300 bg-lime-100/70 px-6 py-5",
            "rounded-3xl border border-slate-200 bg-white p-6",
        ],
        "primary_cta_class": "rounded-full bg-lime-600 px-7 py-4 text-sm font-bold text-slate-950 shadow-xl shadow-lime-100",
        "secondary_cta_class": "rounded-full border border-lime-300 bg-white px-7 py-4 text-sm font-bold text-slate-950",
        "image_class": "rounded-[2.25rem] border border-white shadow-2xl shadow-lime-100/80",
        "footer_class": "border-t border-lime-200 bg-lime-950 text-lime-50",
        "quality_rules": ["show programs", "include trainer cards", "include schedule CTA"],
        "trust_stats": [("12", "Classes open"), ("5", "Coaches live"), ("3", "Plan tracks")],
        "rich_components": ["fitness-program-hero", "trainer-card-grid", "class-schedule-panel", "transformation-proof", "schedule-cta"],
    },
    "ai_devtool": {
        "visual_family": "developer-console",
        "name": "Developer console",
        "body_class": "min-h-screen bg-slate-950 text-slate-50",
        "hero_class": "relative overflow-hidden border-b border-slate-800 bg-gradient-to-br from-slate-950 via-slate-900 to-violet-950 text-white",
        "hero_layout": "code/API hero + console preview + integration CTA",
        "h1_class": "font-display text-5xl font-bold leading-[0.96] tracking-tight text-white md:text-7xl",
        "lead_class": "mt-6 max-w-2xl text-xl leading-8 text-slate-300",
        "section_rhythm": "data-heavy",
        "section_class": "bg-slate-950 text-slate-50",
        "section_alt_class": "border-y border-slate-800 bg-slate-900 text-slate-50",
        "card_classes": [
            "rounded-2xl border border-slate-700 bg-slate-900/90 p-6 text-slate-50 shadow-2xl shadow-slate-950/60",
            "rounded-lg border border-violet-800 bg-slate-950 p-5 font-mono text-sm text-slate-100 shadow-xl",
            "rounded-[2rem] border border-white/10 bg-white/10 p-6 text-slate-50 backdrop-blur",
            "rounded-xl border border-slate-800 bg-slate-950 p-5 text-slate-100",
        ],
        "primary_cta_class": "rounded-lg bg-violet-500 px-7 py-4 text-sm font-bold text-white shadow-xl shadow-violet-950/40",
        "secondary_cta_class": "rounded-lg border border-slate-700 bg-slate-900 px-7 py-4 text-sm font-bold text-slate-100",
        "image_class": "rounded-2xl border border-white/10 shadow-2xl shadow-slate-950/80",
        "footer_class": "border-t border-slate-800 bg-slate-950 text-slate-300",
        "quality_rules": ["show code/API hero", "include console preview", "include docs/integration section"],
        "trust_stats": [("API", "Ready"), ("99ms", "Run sample"), ("SOC", "Controls")],
        "rich_components": ["code-api-hero", "console-preview-card", "workflow-diagram", "docs-integration-grid", "security-panel"],
    },
    "education": {
        "visual_family": "learning-editorial",
        "name": "Learning editorial",
        "body_class": "min-h-screen bg-amber-50 text-slate-950",
        "hero_class": "relative overflow-hidden border-b border-amber-200 bg-gradient-to-br from-white via-amber-50 to-cyan-50",
        "hero_layout": "course catalog hero + learning path + progress preview",
        "h1_class": "font-display text-6xl font-bold leading-[0.94] tracking-tight text-slate-950 md:text-8xl",
        "lead_class": "mt-6 max-w-2xl text-xl leading-8 text-slate-600",
        "section_rhythm": "editorial",
        "section_class": "bg-amber-50",
        "section_alt_class": "border-y border-amber-200 bg-white",
        "card_classes": [
            "overflow-hidden rounded-[2rem] border border-amber-200 bg-white p-6 shadow-xl shadow-amber-100/70",
            "rounded-2xl border border-cyan-100 bg-cyan-50/70 p-6",
            "rounded-3xl border border-white/80 bg-white/80 p-6 shadow-lg backdrop-blur",
            "rounded-none border border-amber-300 bg-white p-6",
        ],
        "primary_cta_class": "rounded-2xl bg-cyan-700 px-7 py-4 text-sm font-bold text-white shadow-xl shadow-cyan-100",
        "secondary_cta_class": "rounded-2xl border border-amber-300 bg-white px-7 py-4 text-sm font-bold text-slate-900",
        "image_class": "rounded-[2rem] border border-white shadow-2xl shadow-amber-100/80",
        "footer_class": "border-t border-amber-200 bg-white text-slate-700",
        "quality_rules": ["show course catalog", "include learning path", "include progress/module preview"],
        "trust_stats": [("120+", "Lessons"), ("4", "Paths"), ("Live", "Progress")],
        "rich_components": ["course-catalog-hero", "learning-path-stepper", "instructor-card-grid", "module-progress-preview", "enrollment-cta"],
    },
    "ecommerce": {
        "visual_family": "product-commerce",
        "name": "Product commerce",
        "body_class": "min-h-screen bg-stone-50 text-stone-950",
        "hero_class": "relative overflow-hidden border-b border-stone-200 bg-gradient-to-br from-white via-stone-50 to-neutral-100",
        "hero_layout": "product-led hero + collection grid + purchase confidence CTA",
        "h1_class": "font-display text-6xl font-bold leading-[0.92] tracking-tight text-stone-950 md:text-8xl",
        "lead_class": "mt-6 max-w-2xl text-xl leading-8 text-stone-600",
        "section_rhythm": "image-heavy",
        "section_class": "bg-stone-50",
        "section_alt_class": "border-y border-stone-200 bg-white",
        "card_classes": [
            "overflow-hidden rounded-[2rem] border border-stone-200 bg-white p-6 shadow-xl shadow-stone-200/70",
            "rounded-none border border-stone-300 bg-white p-6",
            "rounded-3xl border border-neutral-200 bg-white p-6 shadow-sm",
            "rounded-full border border-stone-200 bg-white px-6 py-5",
        ],
        "primary_cta_class": "rounded-full bg-stone-950 px-7 py-4 text-sm font-bold text-white shadow-xl shadow-stone-200",
        "secondary_cta_class": "rounded-full border border-stone-300 bg-white px-7 py-4 text-sm font-bold text-stone-950",
        "image_class": "rounded-[2.25rem] border border-white shadow-2xl shadow-stone-200/80",
        "footer_class": "border-t border-stone-200 bg-stone-950 text-stone-100",
        "quality_rules": ["show product imagery", "include collection grid", "include buying confidence CTA"],
        "trust_stats": [("Live", "Catalog"), ("0-1", "Checkout path"), ("24h", "Support")],
        "rich_components": ["product-stage-hero", "collection-card-grid", "comparison-panel", "checkout-trust-band", "support-cta"],
    },
    "operations": {
        "visual_family": "operations-console",
        "name": "Operations console",
        "body_class": "min-h-screen bg-slate-50 text-slate-950",
        "hero_class": "relative overflow-hidden border-b border-indigo-100 bg-gradient-to-br from-white via-indigo-50 to-slate-50",
        "hero_layout": "business software hero + ops dashboard + workflow queue",
        "h1_class": "font-display text-5xl font-bold leading-[0.96] tracking-tight text-slate-950 md:text-7xl",
        "lead_class": "mt-6 max-w-2xl text-xl leading-8 text-slate-600",
        "section_rhythm": "data-heavy",
        "section_class": "bg-white",
        "section_alt_class": "border-y border-indigo-100 bg-indigo-50/60",
        "card_classes": [
            "rounded-2xl border border-indigo-100 bg-white p-6 shadow-xl shadow-indigo-100/60",
            "rounded-xl border border-slate-200 bg-white p-5",
            "rounded-[2rem] border border-white/80 bg-white/80 p-6 shadow-lg backdrop-blur",
            "rounded-lg border border-indigo-200 bg-indigo-50/70 p-5",
        ],
        "primary_cta_class": "rounded-lg bg-indigo-700 px-7 py-4 text-sm font-bold text-white shadow-xl shadow-indigo-100",
        "secondary_cta_class": "rounded-lg border border-indigo-200 bg-white px-7 py-4 text-sm font-bold text-slate-900",
        "image_class": "rounded-[2rem] border border-white shadow-2xl shadow-indigo-100/80",
        "footer_class": "border-t border-indigo-100 bg-white text-slate-700",
        "quality_rules": ["show ops dashboard", "include workflow queue", "include reports/resource section"],
        "trust_stats": [("42", "Open tasks"), ("12", "Alerts"), ("Live", "Ops board")],
        "rich_components": ["ops-dashboard-hero", "workflow-queue-grid", "resource-matrix", "team-shift-planner", "reports-panel"],
    },
    "portfolio": {
        "visual_family": "creative-portfolio",
        "name": "Creative portfolio",
        "body_class": "min-h-screen bg-zinc-50 text-zinc-950",
        "hero_class": "relative overflow-hidden border-b border-zinc-200 bg-white",
        "hero_layout": "editorial portfolio hero + case mosaic + project CTA",
        "h1_class": "font-display text-6xl font-bold leading-[0.88] tracking-tight text-zinc-950 md:text-8xl",
        "lead_class": "mt-7 max-w-2xl text-xl leading-9 text-zinc-600",
        "section_rhythm": "editorial",
        "section_class": "bg-zinc-50",
        "section_alt_class": "border-y border-zinc-200 bg-white",
        "card_classes": [
            "rounded-none border border-zinc-300 bg-white p-7 shadow-xl shadow-zinc-200",
            "rounded-[2rem] border border-zinc-200 bg-white p-6 shadow-sm",
            "rounded-none border-l-4 border-l-fuchsia-600 bg-white p-6",
            "rounded-3xl border border-white bg-zinc-100 p-6",
        ],
        "primary_cta_class": "rounded-none bg-fuchsia-600 px-7 py-4 text-sm font-bold text-white shadow-xl shadow-fuchsia-100",
        "secondary_cta_class": "rounded-none border border-zinc-300 bg-white px-7 py-4 text-sm font-bold text-zinc-950",
        "image_class": "rounded-none border border-zinc-200 shadow-2xl shadow-zinc-200/80",
        "footer_class": "border-t border-zinc-200 bg-zinc-950 text-zinc-100",
        "quality_rules": ["show featured work", "include case mosaic", "include project CTA"],
        "trust_stats": [("12", "Case studies"), ("4", "Capabilities"), ("New", "Briefs")],
        "rich_components": ["editorial-portfolio-hero", "case-mosaic-grid", "studio-process-stepper", "capability-grid", "project-cta"],
    },
    "finance": {
        "visual_family": "finance-trust",
        "name": "Finance trust",
        "body_class": "min-h-screen bg-emerald-50 text-slate-950",
        "hero_class": "relative overflow-hidden border-b border-emerald-100 bg-gradient-to-br from-white via-emerald-50 to-teal-50",
        "hero_layout": "finance trust hero + ledger preview + security CTA",
        "h1_class": "font-display text-5xl font-bold leading-[0.96] tracking-tight text-slate-950 md:text-7xl",
        "lead_class": "mt-6 max-w-2xl text-xl leading-8 text-slate-600",
        "section_rhythm": "data-heavy",
        "section_class": "bg-white",
        "section_alt_class": "border-y border-emerald-100 bg-emerald-50/80",
        "card_classes": [
            "rounded-2xl border border-emerald-100 bg-white p-6 shadow-xl shadow-emerald-100/60",
            "rounded-xl border border-emerald-200 bg-emerald-50/70 p-5",
            "rounded-[2rem] border border-white/80 bg-white/80 p-6 shadow-lg backdrop-blur",
            "rounded-lg border border-slate-200 bg-white p-5",
        ],
        "primary_cta_class": "rounded-xl bg-emerald-700 px-7 py-4 text-sm font-bold text-white shadow-xl shadow-emerald-100",
        "secondary_cta_class": "rounded-xl border border-emerald-200 bg-white px-7 py-4 text-sm font-bold text-slate-900",
        "image_class": "rounded-[2rem] border border-white shadow-2xl shadow-emerald-100/80",
        "footer_class": "border-t border-emerald-100 bg-white text-slate-700",
        "quality_rules": ["show finance dashboard", "include trust/security section", "include transaction workflow"],
        "trust_stats": [("99.9%", "Reliable"), ("24h", "Audit"), ("Live", "Cash view")],
        "rich_components": ["finance-dashboard-hero", "ledger-preview", "security-control-grid", "payment-workflow", "trust-cta"],
    },
}


PRESET_VARIANTS = [
    ("signature", "Signature", "shadow-xl"),
    ("editorial", "Editorial", "tracking-tight"),
    ("conversion", "Conversion", "ring-1 ring-primary/10"),
    ("image-led", "Image led", "shadow-2xl"),
    ("compact", "Compact", "shadow-md"),
    ("spacious", "Spacious", "shadow-xl"),
    ("trust", "Trust", "ring-1 ring-slate-100"),
    ("premium", "Premium", "shadow-2xl"),
    ("market", "Market", "shadow-lg"),
    ("studio", "Studio", "shadow-xl"),
]


def _build_domain_preset_library() -> dict:
    presets = {}
    for domain, base in DOMAIN_PRESET_BASES.items():
        for suffix, label, accent_class in PRESET_VARIANTS:
            item = copy.deepcopy(base)
            item["domain"] = domain
            item["id"] = f"{domain}-{suffix}"
            item["name"] = f"{base['name']} {label}"
            item["card_classes"] = [
                (cls + " " + accent_class).strip() if accent_class not in cls else cls
                for cls in item.get("card_classes", [])
            ]
            item["quality_rules"] = list(item.get("quality_rules") or []) + [
                "strong domain-specific hero",
                "varied card skeletons",
                "visible CTA above fold",
                "limited image repetition",
            ]
            item["component_variants"] = list(item.get("rich_components") or [])
            item["image_roles"] = dict(DOMAIN_IMAGE_ROLES.get(domain) or COMMON_IMAGE_ROLES)
            presets[item["id"]] = item
    return presets


ART_DIRECTOR_PRESETS = _build_domain_preset_library()


RICH_COMPONENT_VARIANTS = [
    "premium-image-panel-hero",
    "trust-stat-strip",
    "clinical-bento-grid",
    "icon-feature-cards",
    "dashboard-preview-card",
    "service-catalog-grid",
    "timeline-stepper",
    "split-visual",
    "trust-testimonial",
    "faq-accordion",
    "premium-cta-band",
]


def is_healthcare_genome(genome: dict, prompt: str = "") -> bool:
    hay = " ".join([
        str(prompt or ""),
        str((genome or {}).get("app_category", "")),
        str((genome or {}).get("domain", "")),
        str((genome or {}).get("inspiration_family", "")),
        str((genome or {}).get("visual_family", "")),
        " ".join((genome or {}).get("dna_families") or []),
    ]).lower()
    return any(k in hay for k in ("hospital", "healthcare", "clinic", "patient", "doctor", "medical"))


def classify_art_director_domain(genome: dict, prompt: str = "") -> str:
    hay = " ".join([
        str(prompt or ""),
        str((genome or {}).get("app_category", "")),
        str((genome or {}).get("domain", "")),
        str((genome or {}).get("inspiration_family", "")),
        str((genome or {}).get("visual_family", "")),
        str((genome or {}).get("primary_dna_family", "")),
        " ".join((genome or {}).get("dna_families") or []),
    ]).lower().replace("_", "-")
    if any(k in hay for k in ("hospital", "healthcare", "clinic", "patient", "doctor", "medical")):
        return "healthcare"
    if any(k in hay for k in ("vehicle", "automotive", "car ", "cars", "showroom", "test drive", "trade-in")):
        return "automotive"
    if any(k in hay for k in ("restaurant", "reservation", "menu", "chef", "dining", "table booking")):
        return "restaurant"
    if any(k in hay for k in ("real estate", "real-estate", "property", "listing", "agent", "neighborhood")):
        return "real_estate"
    if any(k in hay for k in ("travel", "tour", "tourism", "destination", "itinerary", "trip", "agency")):
        return "travel"
    if any(k in hay for k in ("fitness", "wellness", "trainer", "coaching", "class schedule", "program")):
        return "fitness"
    if any(k in hay for k in ("developer", "devtool", "api", "code", "automation", "ai tool", "console")):
        return "ai_devtool"
    if any(k in hay for k in ("education", "course", "learning", "lesson", "instructor", "student", "media")):
        return "education"
    if any(k in hay for k in ("ecommerce", "commerce", "product", "catalog", "collection", "storefront", "marketplace")):
        return "ecommerce"
    if any(k in hay for k in ("pos", "erp", "operations", "inventory", "business software", "resource", "workflow queue")):
        return "operations"
    if any(k in hay for k in ("portfolio", "agency", "creative", "studio", "case study")):
        return "portfolio"
    if any(k in hay for k in ("finance", "fintech", "wallet", "ledger", "payment", "invoice")):
        return "finance"
    return ""


def _preset_index(prompt: str, genome: dict, presets: list[str], rng=None) -> int:
    seedish = str((genome or {}).get("app_seed") or "") + "|" + str((genome or {}).get("browser_visible_signature") or "")
    base = sum(ord(c) for c in (seedish + "|" + prompt))
    if rng is not None:
        try:
            base += rng.randrange(10_000)
        except Exception:
            pass
    return base % len(presets)


def select_premium_preset(prompt: str, genome: dict, rng=None) -> dict:
    domain = classify_art_director_domain(genome, prompt)
    if domain == "healthcare":
        keys = list(HEALTHCARE_PREMIUM_PRESETS)
        hay = " ".join([
            str(prompt or ""),
            str((genome or {}).get("domain", "")),
            str((genome or {}).get("browser_visible_signature", "")),
        ]).lower()
        command_words = ("command center", "ops board", "operations dashboard", "capacity", "bed", "queue", "admin", "control room")
        if not any(word in hay for word in command_words):
            keys = [k for k in keys if k != "hospital-command-center"] or keys
        return copy.deepcopy(HEALTHCARE_PREMIUM_PRESETS[keys[_preset_index(prompt, genome, keys, rng)]])
    keys = [pid for pid, preset in ART_DIRECTOR_PRESETS.items() if preset.get("domain") == domain]
    if not keys:
        return {}
    return copy.deepcopy(ART_DIRECTOR_PRESETS[keys[_preset_index(prompt, genome, keys, rng)]])


def art_director_preset_count() -> int:
    return len(HEALTHCARE_PREMIUM_PRESETS) + len(ART_DIRECTOR_PRESETS)


def _criteria_scores(genome: dict, polished: bool = False) -> dict:
    genome = genome or {}
    recipe_ids = " ".join([
        str((genome.get("hero_recipe") or {}).get("id", "")),
        str((genome.get("card_recipe") or {}).get("id", "")),
        " ".join(genome.get("section_recipe_ids") or []),
    ])
    premium = bool(polished or genome.get("art_director_enabled") or genome.get("premium_preset_id"))
    strong_hero = premium or any(x in recipe_ids for x in ("premium", "command", "editorial", "portal", "trust"))
    varied_sections = len(set(genome.get("section_recipe_ids") or genome.get("section_variants") or []))
    no_image = str(genome.get("image_strategy", "")).lower() == "no-image fallback"
    card_style = str(genome.get("card_style", "")).lower()
    rhythm = str(genome.get("layout_rhythm", "")).lower()
    return {
        "hero_impact": 9 if strong_hero else 5,
        "visual_hierarchy": 9 if premium else (7 if "editorial" in rhythm else 5),
        "typography_scale": 9 if premium else (6 if (genome.get("typography_style") or "") else 4),
        "spacing_rhythm": 9 if premium else (7 if rhythm in ("editorial", "image-heavy", "data-heavy") else 5),
        "card_polish": 9 if premium else (7 if card_style in ("glass", "shadow", "image-card") else 4),
        "section_variety": min(10, 4 + varied_sections),
        "image_usage_quality": 8 if premium else (3 if no_image else 6),
        "cta_clarity": 9 if premium else (7 if genome.get("cta_placement") else 4),
        "page_specific_uniqueness": 8 if genome.get("visual_family") else 5,
        "professional_feel": 9 if premium else 5,
        "mobile_responsiveness": 8 if premium else 6,
        "excessive_repetition": 8 if premium else 5,
        "empty_space_balance": 8 if premium else 5,
    }


def score_design_plan(genome: dict, visual: dict | None = None, prompt: str = "") -> dict:
    merged = dict(genome or {})
    if visual:
        merged.update(visual)
    scores = _criteria_scores(merged)
    issues = [k for k, v in scores.items() if v < 7]
    return {
        "score": round(sum(scores.values()) / (len(scores) * 10) * 100, 1),
        "criteria": scores,
        "issues": issues,
        "healthcare": is_healthcare_genome(merged, prompt),
    }


def polish_genome(genome: dict, prompt: str = "", rng=None) -> dict:
    """Apply Art Director decisions to the genome before pages are composed."""
    out = copy.deepcopy(genome or {})
    before = score_design_plan(out, prompt=prompt)
    out["design_quality_before"] = before
    domain = classify_art_director_domain(out, prompt)
    if not domain:
        out["art_director_enabled"] = False
        out["design_quality_after"] = before
        return out

    preset = select_premium_preset(prompt, out, rng=rng)
    if not preset:
        out["art_director_enabled"] = False
        out["design_quality_after"] = before
        return out
    previous_hero_recipe = dict(out.get("hero_recipe") or {})
    previous_hero = (out.get("hero_recipe") or {}).get("id", "base")
    previous_card = (out.get("card_recipe") or {}).get("id", "base")
    previous_cta = (out.get("cta_recipe") or {}).get("id", "base")
    previous_footer = (out.get("footer_recipe") or {}).get("id", "base")
    component_variants = list(preset.get("component_variants") or preset.get("rich_components") or RICH_COMPONENT_VARIANTS)
    if domain == "healthcare":
        component_variants = list(RICH_COMPONENT_VARIANTS)
    section_ids = [f"premium-{preset['id']}-{str(v).replace('_', '-').replace(' ', '-')}" for v in component_variants[:5]]
    image_roles = dict(HEALTHCARE_IMAGE_ROLES if domain == "healthcare" else preset.get("image_roles") or COMMON_IMAGE_ROLES)
    visual_family = preset.get("visual_family") or ("healthcare-clinical" if domain == "healthcare" else out.get("visual_family", ""))
    premium_variant = "premium-healthcare-hero" if domain == "healthcare" else previous_hero_recipe.get("variant") or f"premium-{domain}-hero"
    premium_layout = "premium-healthcare-hero" if domain == "healthcare" else previous_hero_recipe.get("layout") or preset.get("hero_layout", "premium-domain-hero")

    out.update({
        "art_director_enabled": True,
        "art_director_domain": domain,
        "premium_preset": preset,
        "premium_preset_id": preset["id"],
        "premium_preset_name": preset["name"],
        "premium_quality_rules": list(preset.get("quality_rules") or []),
        "visual_family": visual_family,
        "inspiration_family": out.get("inspiration_family") or visual_family,
        "hero_variant": premium_variant,
        "layout_rhythm": preset.get("section_rhythm", "premium-spacious"),
        "spacing_style": preset.get("section_rhythm", out.get("spacing_style", "")),
        "card_style": "premium-" + domain.replace("_", "-"),
        "cta_placement": "hero-split",
        "image_strategy": "role-mapped generated images",
        "image_roles": image_roles,
        "image_reuse_limit": 2,
        "rich_component_variants": component_variants[:10],
        "section_recipe_ids": section_ids,
        "section_recipes": [
            {"id": sid, "layout": sid.replace("premium-", ""), "section_class": preset["section_alt_class"] if i % 2 else preset["section_class"]}
            for i, sid in enumerate(section_ids)
        ],
        "hero_recipe": {
            "id": f"hero-premium-{preset['id']}-{previous_hero}",
            "name": preset["name"] + " hero",
            "layout": premium_layout,
            "variant": premium_variant,
            "section_class": preset["hero_class"],
            "h1_class": preset["h1_class"],
            "first_screen": preset["hero_layout"],
        },
        "card_recipe": {
            "id": f"card-premium-{preset['id']}-{previous_card}",
            "name": preset["name"] + " cards",
            "layout": "mixed premium healthcare cards",
            "className": preset["card_classes"][0],
        },
        "cta_recipe": {
            "id": f"cta-premium-{preset['id']}-{previous_cta}",
            "name": preset["name"] + " CTA",
            "layout": "dual premium CTA",
            "primary_class": preset["primary_cta_class"],
            "secondary_class": preset["secondary_cta_class"],
        },
        "footer_recipe": {
            "id": f"footer-premium-{preset['id']}-{previous_footer}",
            "name": preset["name"] + " footer",
            "layout": "trust footer",
            "className": preset["footer_class"],
        },
    })
    out["first_screen_skeleton"] = "|".join([
        "premium-" + domain,
        preset["id"],
        preset["hero_layout"],
        "|".join(component_variants[:2]),
        "role mapped imagery",
    ])
    visible = str(out.get("browser_visible_signature") or "")
    out["browser_visible_signature"] = "|".join(filter(None, [
        visible,
        "art-director",
        domain,
        preset["id"],
        out["hero_recipe"]["id"],
        out["card_recipe"]["id"],
        ">".join(section_ids[:5]),
        out.get("recipe_source_mode", ""),
        ">".join(out.get("extracted_recipe_ids") or []),
    ]))
    out["design_quality_after"] = score_design_plan(out, prompt=prompt)
    return out


def score_generated_jsx(src: str) -> dict:
    src = src or ""
    section_variants = set(re.findall(r'data-section-variant="([^"]+)"', src))
    component_types = set(re.findall(r'data-art-component="([^"]+)"', src))
    image_refs = re.findall(r'src="((?:/generated|/assets)/[^"]+)"', src)
    role_refs = re.findall(r'data-image-role="([^"]+)"', src)
    for role_block in re.findall(r'data-image-roles="([^"]+)"', src):
        role_refs.extend([r.strip() for r in role_block.split(",") if r.strip()])
    card_markers = re.findall(r'data-card-treatment="([^"]+)"', src)
    max_image_use = max((image_refs.count(x) for x in set(image_refs)), default=0)
    h1_large = bool(re.search(r'text-(?:5xl|6xl|7xl|8xl)', src))
    h2_large = bool(re.search(r'<h2[^>]+text-(?:3xl|4xl|5xl)', src))
    premium_cta = bool(re.search(r'data-premium-cta="true"|premium-cta-band|shadow-xl', src))
    scores = {
        "hero_impact": 9 if "data-art-director=\"true\"" in src and h1_large else 5,
        "visual_hierarchy": 8 if h1_large and h2_large else 5,
        "typography_scale": 9 if h1_large and h2_large else 5,
        "spacing_rhythm": 8 if "py-24" in src or "py-32" in src else 5,
        "card_polish": 8 if len(set(card_markers)) >= 3 or "rounded-[2rem]" in src else 5,
        "section_variety": min(10, 4 + len(section_variants | component_types)),
        "image_usage_quality": 8 if len(set(role_refs)) >= 2 and max_image_use <= 2 else 5,
        "cta_clarity": 9 if premium_cta else 5,
        "page_specific_uniqueness": 8 if "data-page-type" in src and "data-page-section-sequence" in src else 5,
        "professional_feel": 8 if "data-premium-preset" in src else 5,
        "mobile_responsiveness": 8 if "md:" in src and "lg:" in src else 5,
        "excessive_repetition": 8 if len(set(card_markers)) >= 3 and max_image_use <= 2 else 5,
        "empty_space_balance": 8 if "grid" in src and ("shadow-xl" in src or "shadow-2xl" in src) else 5,
    }
    return {
        "score": round(sum(scores.values()) / (len(scores) * 10) * 100, 1),
        "criteria": scores,
        "section_component_types": sorted(section_variants | component_types),
        "image_roles": sorted(set(role_refs)),
        "max_image_reuse": max_image_use,
        "card_treatments": sorted(set(card_markers)),
        "premium_cta": premium_cta,
    }


def quality_gate(src: str, genome: dict | None = None) -> dict:
    score = score_generated_jsx(src)
    issues = []
    if score["criteria"]["hero_impact"] < 7:
        issues.append("weak hero impact")
    if len(score["section_component_types"]) < 3:
        issues.append("not enough section component variety")
    if score["max_image_reuse"] > int((genome or {}).get("image_reuse_limit", 2) or 2):
        issues.append("same image reused too often")
    if len(score["card_treatments"]) < 3:
        issues.append("card treatment repetition too high")
    if not score["premium_cta"]:
        issues.append("premium CTA missing")
    if "data-art-director=\"true\"" in (src or "") and not re.search(r'data-premium-preset="[^"]+"', src or ""):
        issues.append("premium preset missing")
    if "data-art-director=\"true\"" in (src or "") and len(score["image_roles"]) < 3:
        issues.append("domain image roles missing")
    if score["score"] < 72:
        issues.append("overall quality score too low")
    return {"ok": not issues, "issues": issues, "score": score}
