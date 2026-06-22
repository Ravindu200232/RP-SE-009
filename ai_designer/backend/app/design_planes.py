"""World-class design planes for every app category.

Each PLANE defines:
  - section_sequence: ordered list of (family, tone, position_label)
    → 12-16 unique sections per landing page (minimum 10 enforced)
  - visual_style / color_family / landing_template
  - hero_variant / nav_style / footer_style
  - section_pools: allowed section families for this category
  - template_inspiration: which of the 17 premium templates shaped this plane

The planes are distilled from deep analysis of 17 premium Next.js templates
(ai-saas-starter-kit, andromeda, bigspring, blinder, finwise, geeky, logoipsum,
meta-droid, dimension, vpn, nextly, next-saas-starter, open-react, plutonium,
SaasCandy, tailnext, tailwind-landing) — their section patterns, color choices,
and structural ideas are encoded here as deterministic sequences.

`get_plane(category_id, app_type?)` returns the right plane; then
`pick_sections(plane, n, rng, prompt_text)` selects varied, deduplicated
sections from the plane's pools.
"""
from __future__ import annotations
import random

# ---------------------------------------------------------------------------
# Plane schema
# ---------------------------------------------------------------------------
# section_sequence entry: (family_name, tone, label)
# tone: "light" | "soft" | "dark" | "accent"
# label: human tag for debugging ("hero", "features", "cta", ...)

# ---------------------------------------------------------------------------
# 20 world-class design planes
# ---------------------------------------------------------------------------
PLANES: dict[str, dict] = {}

# ── 1. Public Website ────────────────────────────────────────────────────────
# Inspiration: tailnext (11 sections), meta-droid (10 sections), nextly (9 sections)
# Pattern: rich editorial storytelling, hero + social proof + multiple feature sections
PLANES["public_website"] = {
    "visual_style": "editorial",
    "color_family": "warm",
    "landing_template": "editorial-photo",
    "hero_variant": "full-image",
    "nav_style": "transparent-topnav",
    "footer_style": "rich",
    "template_inspiration": ["tailnext", "meta-droid", "nextly"],
    "section_sequence": [
        # label / family / tone
        ("hero",             "hero_cinematic",       "light"),
        ("social_proof",     "logos_strip",           "soft"),
        ("intro",            "split_image_left",      "light"),
        ("features",         "features_grid",         "soft"),
        ("benefits",         "value_props",           "light"),
        ("gallery",          "gallery",               "dark"),
        ("process",          "steps",                 "soft"),
        ("stats",            "stats_band",            "dark"),
        ("testimonials",     "testimonials_grid",     "light"),
        ("team",             "team",                  "soft"),
        ("split_story",      "feature_split",         "light"),
        ("faq",              "faq",                   "soft"),
        ("newsletter",       "newsletter",            "accent"),
        ("cta",              "cta_band",              "dark"),
    ],
    "section_pools": [
        "features_grid", "value_props", "stats_band", "logos_strip", "steps",
        "testimonials_grid", "testimonial_big", "faq", "cta_band", "gallery",
        "team", "contact_split", "newsletter", "timeline", "feature_split",
        "bento", "split_image_left", "banner_announce", "metrics_cards",
        "review_wall", "video_section", "process_split", "brand_story",
    ],
    "min_sections": 12,
}

# ── 2. E-commerce / Online Selling ──────────────────────────────────────────
# Inspiration: blinder (LogoGrid+Features+ToolKit pattern), tailwind-landing (BusinessCategories+FeaturesPlanet)
# Pattern: product-first, conversion-optimized, review-heavy
PLANES["ecommerce"] = {
    "visual_style": "bold",
    "color_family": "vibrant",
    "landing_template": "editorial-photo",
    "hero_variant": "product-showcase",
    "nav_style": "action-topnav",
    "footer_style": "rich",
    "template_inspiration": ["blinder", "tailwind-landing", "SaasCandy"],
    "section_sequence": [
        ("hero",             "hero_product",          "light"),
        ("categories",       "category_tiles",        "soft"),
        ("featured",         "product_showcase",      "light"),
        ("logos",            "logos_strip",           "soft"),
        ("benefits",         "value_props",           "dark"),
        ("features",         "features_grid",         "light"),
        ("how_it_works",     "steps",                 "soft"),
        ("reviews",          "review_wall",           "light"),
        ("stats",            "stats_band",            "accent"),
        ("testimonials",     "testimonials_grid",     "soft"),
        ("comparison",       "comparison",            "light"),
        ("pricing",          "pricing",               "soft"),
        ("faq",              "faq",                   "light"),
        ("cta",              "cta_band",              "dark"),
    ],
    "section_pools": [
        "product_showcase", "category_tiles", "features_grid", "stats_band",
        "logos_strip", "review_wall", "testimonials_grid", "pricing",
        "faq", "cta_band", "steps", "value_props", "comparison",
        "gallery", "banner_announce", "newsletter", "bento", "metrics_cards",
    ],
    "min_sections": 12,
}

# ── 3. Business Management / ERP ─────────────────────────────────────────────
# Inspiration: SaasCandy (Services+Features+ProductDoc+Plans+FAQ+Partners), bigspring
# Pattern: enterprise trust, feature depth, integration showcase
PLANES["business_erp"] = {
    "visual_style": "enterprise",
    "color_family": "cool",
    "landing_template": "saas-light",
    "hero_variant": "dashboard-preview",
    "nav_style": "action-topnav",
    "footer_style": "comprehensive",
    "template_inspiration": ["SaasCandy", "bigspring", "next-saas-starter"],
    "section_sequence": [
        ("hero",             "hero_dashboard",        "light"),
        ("logos",            "logos_strip",           "soft"),
        ("services",         "features_grid",         "light"),
        ("benefits",         "value_props",           "soft"),
        ("feature_deep",     "bento",                 "dark"),
        ("how_it_works",     "steps",                 "light"),
        ("modules",          "category_tiles",        "soft"),
        ("stats",            "metrics_cards",         "dark"),
        ("comparison",       "comparison",            "light"),
        ("testimonials",     "testimonials_grid",     "soft"),
        ("integrations",     "feature_split",         "light"),
        ("pricing",          "pricing",               "soft"),
        ("faq",              "faq",                   "light"),
        ("cta",              "cta_band",              "accent"),
    ],
    "section_pools": [
        "features_grid", "bento", "metrics_cards", "logos_strip", "steps",
        "testimonials_grid", "pricing", "faq", "cta_band", "comparison",
        "category_tiles", "value_props", "feature_split", "timeline",
        "banner_announce", "stats_band", "contact_split", "team",
    ],
    "min_sections": 13,
}

# ── 4. Booking / Reservation ─────────────────────────────────────────────────
# Inspiration: nextly (Video+Benefits x2+Testimonials+FAQ+CTA), finwise (Stats+Benefits+Pricing)
# Pattern: booking-flow-first, availability-focused, trust-building
PLANES["booking"] = {
    "visual_style": "clean",
    "color_family": "cool",
    "landing_template": "saas-light",
    "hero_variant": "search-booking",
    "nav_style": "transparent-topnav",
    "footer_style": "standard",
    "template_inspiration": ["nextly", "finwise", "tailnext"],
    "section_sequence": [
        ("hero",             "hero_booking",          "light"),
        ("logos",            "logos_strip",           "soft"),
        ("how_to_book",      "steps",                 "light"),
        ("features",         "features_grid",         "soft"),
        ("categories",       "category_tiles",        "light"),
        ("benefits",         "value_props",           "dark"),
        ("video",            "video_section",         "soft"),
        ("stats",            "stats_band",            "accent"),
        ("reviews",          "review_wall",           "light"),
        ("testimonials",     "testimonials_grid",     "soft"),
        ("pricing",          "pricing",               "light"),
        ("faq",              "faq",                   "soft"),
        ("cta",              "cta_band",              "dark"),
    ],
    "section_pools": [
        "hero_booking", "steps", "features_grid", "category_tiles", "stats_band",
        "logos_strip", "review_wall", "testimonials_grid", "pricing",
        "faq", "cta_band", "value_props", "video_section", "gallery",
        "team", "contact_split", "newsletter", "metrics_cards",
    ],
    "min_sections": 12,
}

# ── 5. Education / Learning ───────────────────────────────────────────────────
# Inspiration: andromeda (educational editorial), bigspring (docs/education tags)
# Pattern: course showcase, learning path, instructor trust, outcome stats
PLANES["education"] = {
    "visual_style": "editorial",
    "color_family": "cool",
    "landing_template": "saas-light",
    "hero_variant": "editorial",
    "nav_style": "action-topnav",
    "footer_style": "rich",
    "template_inspiration": ["andromeda", "bigspring", "tailnext"],
    "section_sequence": [
        ("hero",             "hero_editorial",        "light"),
        ("stats",            "stats_band",            "accent"),
        ("course_catalog",   "course_cards",          "light"),
        ("how_it_works",     "steps",                 "soft"),
        ("features",         "features_grid",         "light"),
        ("categories",       "category_tiles",        "soft"),
        ("instructors",      "team",                  "dark"),
        ("outcomes",         "value_props",           "light"),
        ("testimonials",     "testimonials_grid",     "soft"),
        ("video",            "video_section",         "light"),
        ("timeline",         "timeline",              "soft"),
        ("pricing",          "pricing",               "light"),
        ("faq",              "faq",                   "soft"),
        ("cta",              "cta_band",              "dark"),
    ],
    "section_pools": [
        "course_cards", "category_tiles", "team", "features_grid", "stats_band",
        "logos_strip", "testimonials_grid", "pricing", "faq", "cta_band",
        "steps", "value_props", "video_section", "timeline", "bento",
        "newsletter", "contact_split", "gallery", "banner_announce",
    ],
    "min_sections": 13,
}

# ── 6. Healthcare / Medical ───────────────────────────────────────────────────
# Inspiration: bigspring (health tags), nextly (trust + benefits pattern)
# Pattern: trust-first, clinical, doctor profiles, patient journey
PLANES["healthcare"] = {
    "visual_style": "clean",
    "color_family": "cool",
    "landing_template": "saas-light",
    "hero_variant": "split",
    "nav_style": "action-topnav",
    "footer_style": "comprehensive",
    "template_inspiration": ["bigspring", "nextly", "SaasCandy"],
    "section_sequence": [
        ("hero",             "hero_clinical",         "light"),
        ("logos",            "logos_strip",           "soft"),
        ("services",         "features_grid",         "light"),
        ("specialties",      "category_tiles",        "soft"),
        ("doctors",          "doctor_cards",          "light"),
        ("how_it_works",     "steps",                 "soft"),
        ("stats",            "stats_band",            "dark"),
        ("benefits",         "value_props",           "light"),
        ("testimonials",     "testimonials_grid",     "soft"),
        ("split_story",      "split_image_left",      "light"),
        ("faq",              "faq",                   "soft"),
        ("contact",          "contact_split",         "light"),
        ("cta",              "cta_band",              "accent"),
    ],
    "section_pools": [
        "doctor_cards", "features_grid", "category_tiles", "stats_band",
        "logos_strip", "testimonials_grid", "faq", "cta_band", "steps",
        "value_props", "split_image_left", "contact_split", "team",
        "gallery", "banner_announce", "metrics_cards", "timeline",
    ],
    "min_sections": 12,
}

# ── 7. Finance / Payment ──────────────────────────────────────────────────────
# Inspiration: finwise (clean FinTech — Hero+Logos+Benefits+Pricing+Testimonials+FAQ+Stats+CTA)
# Pattern: trust + security + stats-heavy + clean professional
PLANES["finance"] = {
    "visual_style": "enterprise",
    "color_family": "cool",
    "landing_template": "saas-light",
    "hero_variant": "dashboard-preview",
    "nav_style": "action-topnav",
    "footer_style": "comprehensive",
    "template_inspiration": ["finwise", "plutonium", "next-saas-starter"],
    "section_sequence": [
        ("hero",             "hero_dashboard",        "light"),
        ("logos",            "logos_strip",           "soft"),
        ("stats",            "stats_band",            "dark"),
        ("features",         "features_grid",         "light"),
        ("benefits",         "value_props",           "soft"),
        ("security",         "bento",                 "dark"),
        ("how_it_works",     "steps",                 "light"),
        ("metrics",          "metrics_cards",         "soft"),
        ("pricing",          "pricing",               "light"),
        ("comparison",       "comparison",            "soft"),
        ("testimonials",     "testimonials_grid",     "light"),
        ("faq",              "faq",                   "soft"),
        ("contact",          "contact_split",         "light"),
        ("cta",              "cta_band",              "accent"),
    ],
    "section_pools": [
        "features_grid", "bento", "metrics_cards", "stats_band", "logos_strip",
        "testimonials_grid", "pricing", "comparison", "faq", "cta_band",
        "steps", "value_props", "contact_split", "timeline", "banner_announce",
    ],
    "min_sections": 13,
}

# ── 8. Social / Community ─────────────────────────────────────────────────────
# Inspiration: logoipsum (Partners+Features+Gallery+Testimonials+BlogPosts), open-react
# Pattern: community-first, feed preview, engagement-focused
PLANES["social"] = {
    "visual_style": "bold",
    "color_family": "vibrant",
    "landing_template": "creative-dark",
    "hero_variant": "card-stack",
    "nav_style": "action-topnav",
    "footer_style": "standard",
    "template_inspiration": ["logoipsum", "open-react", "meta-droid"],
    "section_sequence": [
        ("hero",             "hero_social",           "dark"),
        ("stats",            "stats_band",            "accent"),
        ("features",         "features_grid",         "soft"),
        ("how_it_works",     "steps",                 "dark"),
        ("community",        "gallery",               "light"),
        ("benefits",         "value_props",           "soft"),
        ("creators",         "team",                  "dark"),
        ("testimonials",     "testimonials_grid",     "light"),
        ("bento",            "bento",                 "soft"),
        ("pricing",          "pricing",               "dark"),
        ("faq",              "faq",                   "light"),
        ("newsletter",       "newsletter",            "accent"),
        ("cta",              "cta_band",              "dark"),
    ],
    "section_pools": [
        "features_grid", "gallery", "stats_band", "logos_strip", "steps",
        "testimonials_grid", "pricing", "faq", "cta_band", "team",
        "value_props", "bento", "newsletter", "timeline", "banner_announce",
        "review_wall", "metrics_cards",
    ],
    "min_sections": 12,
}

# ── 9. SaaS / Productivity ────────────────────────────────────────────────────
# Inspiration: ai-saas-starter (Hero+Features+ToolsTab+BenefitsGrid+Testimonials+Pricing+FAQ),
#              blinder (Hero+LogoGrid+Features+CTA+ToolKit+Testimonials+FooterCTA),
#              open-react (Illustrations+Hero+Workflows+Features+Testimonials+CTA)
# Pattern: feature-packed, pricing-focused, bento grids, social proof heavy
PLANES["saas"] = {
    "visual_style": "premium-dark",
    "color_family": "vibrant",
    "landing_template": "creative-dark",
    "hero_variant": "dashboard-preview",
    "nav_style": "floating-nav",
    "footer_style": "rich",
    "template_inspiration": ["ai-saas-starter", "blinder", "open-react", "plutonium"],
    "section_sequence": [
        ("hero",             "hero_saas",             "dark"),
        ("logos",            "logos_strip",           "dark"),
        ("features",         "bento",                 "dark"),
        ("how_it_works",     "steps",                 "soft"),
        ("features_deep",    "features_grid",         "dark"),
        ("stats",            "stats_band",            "accent"),
        ("workflows",        "feature_split",         "dark"),
        ("comparison",       "comparison",            "soft"),
        ("pricing",          "pricing",               "dark"),
        ("testimonials",     "testimonials_grid",     "soft"),
        ("big_quote",        "testimonial_big",       "dark"),
        ("faq",              "faq",                   "soft"),
        ("newsletter",       "newsletter",            "dark"),
        ("cta",              "cta_band",              "accent"),
    ],
    "section_pools": [
        "bento", "features_grid", "feature_split", "stats_band", "logos_strip",
        "testimonials_grid", "testimonial_big", "pricing", "comparison", "faq",
        "cta_band", "steps", "value_props", "banner_announce", "newsletter",
        "timeline", "metrics_cards", "video_section",
    ],
    "min_sections": 13,
}

# ── 10. Admin / Dashboard ─────────────────────────────────────────────────────
# Inspiration: SaasCandy (Services+Features+ProductDoc+Plans), bigspring (clean admin feel)
# Pattern: module showcase, permission-aware, data-first
PLANES["admin_dashboard"] = {
    "visual_style": "enterprise",
    "color_family": "cool",
    "landing_template": "saas-light",
    "hero_variant": "dashboard-preview",
    "nav_style": "sidebar",
    "footer_style": "minimal",
    "template_inspiration": ["SaasCandy", "bigspring", "next-saas-starter"],
    "section_sequence": [
        ("hero",             "hero_dashboard",        "light"),
        ("stats",            "metrics_cards",         "soft"),
        ("features",         "features_grid",         "light"),
        ("modules",          "bento",                 "soft"),
        ("how_it_works",     "steps",                 "light"),
        ("permissions",      "value_props",           "soft"),
        ("comparison",       "comparison",            "light"),
        ("integrations",     "logos_strip",           "soft"),
        ("stats2",           "stats_band",            "dark"),
        ("testimonials",     "testimonials_grid",     "light"),
        ("pricing",          "pricing",               "soft"),
        ("faq",              "faq",                   "light"),
        ("cta",              "cta_band",              "accent"),
    ],
    "section_pools": [
        "features_grid", "bento", "metrics_cards", "stats_band", "logos_strip",
        "testimonials_grid", "pricing", "comparison", "faq", "cta_band",
        "steps", "value_props", "feature_split", "category_tiles", "timeline",
    ],
    "min_sections": 12,
}

# ── 11. Content Management ────────────────────────────────────────────────────
# Inspiration: andromeda (Blog/Content — HomeBanner+Features+ShortIntro+SpecialFeatures+Testimonials+CTA),
#              geeky (Banner+Featured+Recent+Sidebar), logoipsum (Gallery+Blog Posts)
# Pattern: editorial heavy, blog grid, author showcase, content-first
PLANES["content_management"] = {
    "visual_style": "editorial",
    "color_family": "warm",
    "landing_template": "editorial-photo",
    "hero_variant": "editorial",
    "nav_style": "centered-topnav",
    "footer_style": "rich",
    "template_inspiration": ["andromeda", "geeky", "logoipsum"],
    "section_sequence": [
        ("hero",             "hero_editorial",        "light"),
        ("featured",         "blog_grid",             "light"),
        ("categories",       "category_tiles",        "soft"),
        ("features",         "features_grid",         "light"),
        ("split",            "split_image_left",      "soft"),
        ("authors",          "team",                  "light"),
        ("stats",            "stats_band",            "dark"),
        ("how_it_works",     "steps",                 "soft"),
        ("gallery",          "gallery",               "light"),
        ("testimonials",     "testimonials_grid",     "soft"),
        ("newsletter",       "newsletter",            "accent"),
        ("pricing",          "pricing",               "light"),
        ("faq",              "faq",                   "soft"),
        ("cta",              "cta_band",              "dark"),
    ],
    "section_pools": [
        "blog_grid", "gallery", "team", "features_grid", "category_tiles",
        "stats_band", "testimonials_grid", "newsletter", "pricing", "faq",
        "cta_band", "steps", "split_image_left", "timeline", "banner_announce",
        "testimonial_big", "contact_split",
    ],
    "min_sections": 13,
}

# ── 12. Service Marketplace ───────────────────────────────────────────────────
# Inspiration: tailwind-landing (BusinessCategories+FeaturesPlanet+LargeTestimonial),
#              blinder (LogoGrid+ToolKit pattern)
# Pattern: provider showcase, category browsing, trust signals heavy
PLANES["service_marketplace"] = {
    "visual_style": "bold",
    "color_family": "vibrant",
    "landing_template": "saas-light",
    "hero_variant": "search-booking",
    "nav_style": "action-topnav",
    "footer_style": "rich",
    "template_inspiration": ["tailwind-landing", "blinder", "tailnext"],
    "section_sequence": [
        ("hero",             "hero_booking",          "light"),
        ("stats",            "stats_band",            "accent"),
        ("categories",       "category_tiles",        "light"),
        ("featured",         "product_showcase",      "soft"),
        ("how_it_works",     "steps",                 "dark"),
        ("features",         "features_grid",         "light"),
        ("providers",        "team",                  "soft"),
        ("reviews",          "review_wall",           "light"),
        ("testimonials",     "testimonials_grid",     "soft"),
        ("logos",            "logos_strip",           "light"),
        ("pricing",          "pricing",               "soft"),
        ("faq",              "faq",                   "light"),
        ("newsletter",       "newsletter",            "accent"),
        ("cta",              "cta_band",              "dark"),
    ],
    "section_pools": [
        "product_showcase", "category_tiles", "team", "features_grid", "stats_band",
        "logos_strip", "review_wall", "testimonials_grid", "pricing",
        "faq", "cta_band", "steps", "value_props", "gallery",
        "banner_announce", "newsletter", "bento", "contact_split",
    ],
    "min_sections": 13,
}

# ── 13. Logistics / Transport ─────────────────────────────────────────────────
# Inspiration: SaasCandy (enterprise multi-section), bigspring (clean corporate)
# Pattern: tracking-focused, operational efficiency, trust + fleet showcase
PLANES["logistics"] = {
    "visual_style": "enterprise",
    "color_family": "cool",
    "landing_template": "saas-light",
    "hero_variant": "stats-first",
    "nav_style": "action-topnav",
    "footer_style": "comprehensive",
    "template_inspiration": ["SaasCandy", "bigspring", "finwise"],
    "section_sequence": [
        ("hero",             "hero_dashboard",        "dark"),
        ("stats",            "stats_band",            "accent"),
        ("features",         "features_grid",         "light"),
        ("services",         "category_tiles",        "soft"),
        ("tracking",         "bento",                 "dark"),
        ("how_it_works",     "steps",                 "light"),
        ("metrics",          "metrics_cards",         "soft"),
        ("benefits",         "value_props",           "dark"),
        ("logos",            "logos_strip",           "light"),
        ("testimonials",     "testimonials_grid",     "soft"),
        ("comparison",       "comparison",            "light"),
        ("faq",              "faq",                   "soft"),
        ("contact",          "contact_split",         "light"),
        ("cta",              "cta_band",              "accent"),
    ],
    "section_pools": [
        "features_grid", "bento", "metrics_cards", "stats_band", "logos_strip",
        "testimonials_grid", "comparison", "faq", "cta_band", "steps",
        "value_props", "category_tiles", "contact_split", "feature_split",
        "timeline", "banner_announce",
    ],
    "min_sections": 13,
}

# ── 14. Real Estate / Property ────────────────────────────────────────────────
# Inspiration: editorial-photo template (estate/hotel tags), tailnext (Team+Contact sections)
# Pattern: visual-heavy, property grid, location-based, agent trust
PLANES["real_estate"] = {
    "visual_style": "editorial",
    "color_family": "warm",
    "landing_template": "editorial-photo",
    "hero_variant": "full-image",
    "nav_style": "transparent-topnav",
    "footer_style": "rich",
    "template_inspiration": ["tailnext", "meta-droid", "open-react"],
    "section_sequence": [
        ("hero",             "hero_property_search",  "light"),
        ("stats",            "stats_band",            "dark"),
        ("listings",         "property_grid",         "light"),
        ("categories",       "category_tiles",        "soft"),
        ("features",         "features_grid",         "light"),
        ("about",            "split_image_left",      "soft"),
        ("agents",           "team",                  "light"),
        ("gallery",          "gallery",               "dark"),
        ("testimonials",     "testimonials_grid",     "light"),
        ("how_it_works",     "steps",                 "soft"),
        ("map",              "map_section",           "light"),
        ("faq",              "faq",                   "soft"),
        ("contact",          "contact_split",         "light"),
        ("cta",              "cta_band",              "accent"),
    ],
    "section_pools": [
        "property_grid", "gallery", "team", "features_grid", "stats_band",
        "testimonials_grid", "faq", "cta_band", "steps", "category_tiles",
        "split_image_left", "contact_split", "map_section", "timeline",
        "review_wall", "banner_announce", "newsletter",
    ],
    "min_sections": 13,
}

# ── 15. Government / Public Service ──────────────────────────────────────────
# Inspiration: bigspring (corporate, trustworthy), SaasCandy (comprehensive sections)
# Pattern: trust-first, accessibility, services directory, transparent process
PLANES["government"] = {
    "visual_style": "enterprise",
    "color_family": "cool",
    "landing_template": "saas-light",
    "hero_variant": "split",
    "nav_style": "action-topnav",
    "footer_style": "comprehensive",
    "template_inspiration": ["bigspring", "SaasCandy", "finwise"],
    "section_sequence": [
        ("hero",             "hero_civic",            "light"),
        ("stats",            "stats_band",            "accent"),
        ("services",         "features_grid",         "light"),
        ("categories",       "category_tiles",        "soft"),
        ("how_it_works",     "steps",                 "light"),
        ("benefits",         "value_props",           "soft"),
        ("announcements",    "timeline",              "light"),
        ("logos",            "logos_strip",           "soft"),
        ("testimonials",     "testimonials_grid",     "light"),
        ("split",            "split_image_left",      "soft"),
        ("faq",              "faq",                   "light"),
        ("contact",          "contact_split",         "soft"),
        ("newsletter",       "newsletter",            "accent"),
        ("cta",              "cta_band",              "dark"),
    ],
    "section_pools": [
        "features_grid", "category_tiles", "timeline", "stats_band", "logos_strip",
        "testimonials_grid", "faq", "cta_band", "steps", "value_props",
        "split_image_left", "contact_split", "newsletter", "banner_announce",
        "metrics_cards", "team",
    ],
    "min_sections": 13,
}

# ── 16. Entertainment / Media ─────────────────────────────────────────────────
# Inspiration: meta-droid (dark futuristic — About+Explore+GetStarted+WhatsNew+World+Insights+Feedback),
#              plutonium (bold dark gradient)
# Pattern: visual-immersive, dark aesthetic, content-grid, community elements
PLANES["entertainment"] = {
    "visual_style": "premium-dark",
    "color_family": "vibrant",
    "landing_template": "creative-dark",
    "hero_variant": "full-image",
    "nav_style": "transparent-topnav",
    "footer_style": "minimal",
    "template_inspiration": ["meta-droid", "plutonium", "ai-saas-starter"],
    "section_sequence": [
        ("hero",             "hero_cinematic",        "dark"),
        ("featured",         "gallery",               "dark"),
        ("categories",       "category_tiles",        "dark"),
        ("about",            "split_image_left",      "dark"),
        ("features",         "bento",                 "dark"),
        ("stats",            "stats_band",            "accent"),
        ("creators",         "team",                  "dark"),
        ("community",        "testimonials_grid",     "soft"),
        ("how_it_works",     "steps",                 "dark"),
        ("newsletter",       "newsletter",            "dark"),
        ("faq",              "faq",                   "soft"),
        ("cta",              "cta_band",              "accent"),
    ],
    "section_pools": [
        "gallery", "bento", "team", "stats_band", "category_tiles",
        "testimonials_grid", "faq", "cta_band", "steps", "split_image_left",
        "newsletter", "banner_announce", "feature_split", "review_wall",
        "video_section", "metrics_cards",
    ],
    "min_sections": 11,
}

# ── 17. AI / Automation ───────────────────────────────────────────────────────
# Inspiration: ai-saas-starter (full AI SaaS — Hero+CoreFeatures+ToolsTab+BenefitsGrid+Testimonials+Pricing+FAQ),
#              blinder (GradientWrapper sections, ToolKit), open-react (Workflows section)
# Pattern: AI capability showcase, workflow visualization, bento grids, dark premium
PLANES["ai_automation"] = {
    "visual_style": "premium-dark",
    "color_family": "vibrant",
    "landing_template": "creative-dark",
    "hero_variant": "ai-demo",
    "nav_style": "floating-nav",
    "footer_style": "minimal",
    "template_inspiration": ["ai-saas-starter", "blinder", "open-react", "meta-droid"],
    "section_sequence": [
        ("hero",             "hero_ai",               "dark"),
        ("logos",            "logos_strip",           "dark"),
        ("bento",            "bento",                 "dark"),
        ("features",         "features_grid",         "soft"),
        ("workflows",        "feature_split",         "dark"),
        ("tools",            "category_tiles",        "dark"),
        ("stats",            "stats_band",            "accent"),
        ("how_it_works",     "steps",                 "dark"),
        ("comparison",       "comparison",            "soft"),
        ("testimonials",     "testimonials_grid",     "dark"),
        ("big_quote",        "testimonial_big",       "soft"),
        ("pricing",          "pricing",               "dark"),
        ("faq",              "faq",                   "soft"),
        ("cta",              "cta_band",              "accent"),
    ],
    "section_pools": [
        "bento", "features_grid", "feature_split", "category_tiles", "stats_band",
        "logos_strip", "testimonials_grid", "testimonial_big", "pricing",
        "comparison", "faq", "cta_band", "steps", "value_props",
        "banner_announce", "newsletter", "video_section", "timeline",
    ],
    "min_sections": 13,
}

# ── 18. Security / Access Control ────────────────────────────────────────────
# Inspiration: plutonium (dark, security feel), bigspring (corporate clean)
# Pattern: trust + compliance + feature matrix, clean and authoritative
PLANES["security"] = {
    "visual_style": "enterprise",
    "color_family": "cool",
    "landing_template": "saas-light",
    "hero_variant": "dashboard-preview",
    "nav_style": "action-topnav",
    "footer_style": "comprehensive",
    "template_inspiration": ["plutonium", "bigspring", "SaasCandy"],
    "section_sequence": [
        ("hero",             "hero_dashboard",        "dark"),
        ("logos",            "logos_strip",           "soft"),
        ("features",         "features_grid",         "light"),
        ("security_bento",   "bento",                 "dark"),
        ("how_it_works",     "steps",                 "light"),
        ("stats",            "stats_band",            "accent"),
        ("comparison",       "comparison",            "light"),
        ("benefits",         "value_props",           "soft"),
        ("testimonials",     "testimonials_grid",     "light"),
        ("pricing",          "pricing",               "soft"),
        ("faq",              "faq",                   "light"),
        ("cta",              "cta_band",              "dark"),
    ],
    "section_pools": [
        "features_grid", "bento", "stats_band", "logos_strip",
        "testimonials_grid", "pricing", "comparison", "faq", "cta_band",
        "steps", "value_props", "banner_announce", "metrics_cards",
    ],
    "min_sections": 11,
}

# ── 19. Internal Company Portal ───────────────────────────────────────────────
# Inspiration: SaasCandy (Services+ProductDoc pattern), bigspring (corporate trust)
# Pattern: portal functionality, role-based sections, onboarding focus
PLANES["internal_portal"] = {
    "visual_style": "enterprise",
    "color_family": "cool",
    "landing_template": "saas-light",
    "hero_variant": "dashboard-preview",
    "nav_style": "sidebar",
    "footer_style": "minimal",
    "template_inspiration": ["SaasCandy", "bigspring", "finwise"],
    "section_sequence": [
        ("hero",             "hero_dashboard",        "light"),
        ("features",         "features_grid",         "soft"),
        ("modules",          "category_tiles",        "light"),
        ("how_it_works",     "steps",                 "soft"),
        ("bento",            "bento",                 "light"),
        ("stats",            "metrics_cards",         "soft"),
        ("benefits",         "value_props",           "dark"),
        ("logos",            "logos_strip",           "light"),
        ("testimonials",     "testimonials_grid",     "soft"),
        ("faq",              "faq",                   "light"),
        ("cta",              "cta_band",              "accent"),
    ],
    "section_pools": [
        "features_grid", "bento", "metrics_cards", "category_tiles", "logos_strip",
        "testimonials_grid", "faq", "cta_band", "steps", "value_props",
        "timeline", "banner_announce", "feature_split",
    ],
    "min_sections": 10,
}

# ── 20. Hybrid Web App ────────────────────────────────────────────────────────
# Inspiration: all templates — hybrid apps need versatility
# Pattern: public landing + app preview + feature showcase + social proof
PLANES["hybrid_app"] = {
    "visual_style": "clean",
    "color_family": "vibrant",
    "landing_template": "saas-light",
    "hero_variant": "dashboard-preview",
    "nav_style": "action-topnav",
    "footer_style": "rich",
    "template_inspiration": ["tailnext", "ai-saas-starter", "open-react"],
    "section_sequence": [
        ("hero",             "hero_saas",             "light"),
        ("logos",            "logos_strip",           "soft"),
        ("features",         "bento",                 "light"),
        ("how_it_works",     "steps",                 "soft"),
        ("features_deep",    "features_grid",         "dark"),
        ("categories",       "category_tiles",        "soft"),
        ("stats",            "stats_band",            "accent"),
        ("testimonials",     "testimonials_grid",     "light"),
        ("comparison",       "comparison",            "soft"),
        ("pricing",          "pricing",               "light"),
        ("faq",              "faq",                   "soft"),
        ("newsletter",       "newsletter",            "dark"),
        ("cta",              "cta_band",              "accent"),
    ],
    "section_pools": [
        "bento", "features_grid", "stats_band", "logos_strip", "category_tiles",
        "testimonials_grid", "pricing", "comparison", "faq", "cta_band",
        "steps", "value_props", "newsletter", "banner_announce", "feature_split",
        "timeline", "metrics_cards", "video_section",
    ],
    "min_sections": 12,
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_plane(category_id: str, app_type: str | None = None) -> dict:
    """Return the design plane for a category (with fallback to saas)."""
    plane = PLANES.get(category_id) or PLANES["saas"]
    # Future: per-app-type overrides go here
    return plane


# Structural archetypes: families that share the same visual layout pattern.
# pick_sections() uses this to prevent two sections with identical structure
# on the same page (e.g. stats_band + metrics_cards both render as "4-stat row").
_STRUCTURAL_ARCHETYPE: dict[str, str] = {
    "stats_band":       "stats-row",
    "metrics_cards":    "stats-row",
    "testimonials_grid":"social-proof",
    "testimonial_big":  "social-proof",
    "review_wall":      "social-proof",
    "pricing":          "pricing",
    "pricing_plans":    "pricing",
    "feature_split":    "image-split",
    "split_image_left": "image-split",
    "process_split":    "image-split",
    "cta_band":         "cta",
    "banner_announce":  "cta",
    "features_grid":    "feature-cards",
    "bento":            "feature-cards",
    "course_cards":     "catalog-cards",
    "doctor_cards":     "catalog-cards",
    "property_grid":    "catalog-cards",
    "category_tiles":   "catalog-cards",
    "event_cards":      "catalog-cards",
    "gallery":          "image-gallery",
    "product_showcase": "image-gallery",
}


def pick_sections(
    plane: dict,
    n: int,
    rng: random.Random,
    prompt_text: str = "",
    exclude_families: list[str] | None = None,
) -> list[tuple[str, str]]:
    """Pick N unique section (family, tone) pairs from a plane's pool.

    Strategy:
    1. Use the plane's section_sequence as the preferred order (premium quality).
    2. If n > len(sequence), pad from section_pools with variety-scored picks.
    3. Never repeat a family.
    4. Never repeat a structural archetype (prevents two "4-stat rows" etc.).
    5. Enforce plane['min_sections'] as floor.

    Returns list of (family, tone) tuples.
    """
    exclude = set(exclude_families or [])
    n = max(n, plane.get("min_sections", 12))

    chosen: list[tuple[str, str]] = []
    seen: set[str] = set(exclude)
    seen_archetypes: set[str] = set()

    def _admit(family: str) -> bool:
        if family in seen:
            return False
        arch = _STRUCTURAL_ARCHETYPE.get(family)
        if arch and arch in seen_archetypes:
            return False
        return True

    def _record(family: str) -> None:
        seen.add(family)
        arch = _STRUCTURAL_ARCHETYPE.get(family)
        if arch:
            seen_archetypes.add(arch)

    # Phase 1: walk the curated sequence
    for (_, family, tone) in plane["section_sequence"]:
        if not _admit(family):
            continue
        if family.startswith("hero_"):
            family = _resolve_hero(family, plane)
        if not _admit(family):
            continue
        chosen.append((family, tone))
        _record(family)
        if len(chosen) >= n:
            return chosen

    # Phase 2: pad from pools if sequence was exhausted
    pool = [f for f in plane["section_pools"] if not f.startswith("hero_")]
    rng.shuffle(pool)
    for family in pool:
        if not _admit(family):
            continue
        idx = len(chosen)
        tone_cycle = ["light", "soft", "dark", "accent", "soft", "light", "dark", "soft"]
        chosen.append((family, tone_cycle[idx % len(tone_cycle)]))
        _record(family)
        if len(chosen) >= n:
            break

    return chosen


def _resolve_hero(hero_variant: str, plane: dict) -> str:
    """Map hero_* variants to real section catalog family names."""
    mapping = {
        "hero_saas": "feature_split",          # full-width split with mockup
        "hero_dashboard": "bento",              # bento reveals the dashboard
        "hero_booking": "split_image_left",     # split with search form
        "hero_editorial": "split_image_left",   # editorial split
        "hero_product": "gallery",              # product imagery showcase
        "hero_cinematic": "gallery",            # full-bleed cinematic
        "hero_clinical": "split_image_left",    # clean clinical split
        "hero_social": "bento",                 # social bento grid
        "hero_ai": "bento",                     # AI capability bento
        "hero_property_search": "split_image_left",  # property search hero
        "hero_civic": "split_image_left",       # government civic hero
    }
    return mapping.get(hero_variant, "feature_split")


def section_tone(plane: dict, family: str) -> str:
    """Look up the recommended tone for a family in a plane's sequence."""
    for (_, f, t) in plane["section_sequence"]:
        if _resolve_hero(f, plane) == family or f == family:
            return t
    return "light"


def plane_visual_style(category_id: str) -> str:
    return PLANES.get(category_id, PLANES["saas"])["visual_style"]


def plane_landing_template(category_id: str) -> str:
    return PLANES.get(category_id, PLANES["saas"])["landing_template"]


def all_plane_ids() -> list[str]:
    return list(PLANES.keys())
