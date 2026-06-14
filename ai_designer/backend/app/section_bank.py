"""Section bank — landing pages composed from REMIXED design pieces.

The pieces were learned from the user's own projects (CleanMate, lms-ui,
Audio shop, photoShop, CTSE) and rewritten into our token + copy-slot system:
each section is an independent JSX fragment with UNIQUE const names and a
unique slice of the copy anchors, so any combination stays valid JSX and
`landing_copy.apply` fills every chosen section. A composed landing = one
hero + a shuffled subset of middle sections + closing CTA/footer — hundreds of
orderings, so no two generated sites assemble the same page.
"""
import os
import random

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "library_next", "sections")

HEROES = [
    ("HeroSlider", "hero_slider.jsx"), ("HeroSplitRadial", "hero_split_radial.jsx"),
    ("HeroGradientGlow", "hero_gradient_glow.jsx"), ("HeroMinimalLeft", "hero_minimal_left.jsx"),
    ("HeroProductCard", "hero_product_card.jsx"), ("HeroEditorialSerif", "hero_editorial_serif.jsx"),
    ("HeroSplitScreen", "hero_split_screen.jsx"), ("HeroStatsStrip", "hero_stats_strip.jsx"),
    ("HeroCenteredClean", "hero_centered_clean.jsx"), ("HeroPhotoLeftDark", "hero_photo_left_dark.jsx"),
]
_HERO_BY_FILE = {f: (n, f) for n, f in HEROES}
MIDDLES = [
    ("StatsAmbient", "stats_ambient.jsx"),
    ("FeatureTiles", "feature_tiles.jsx"),
    ("GalleryMosaic", "gallery_mosaic.jsx"),
    ("WhyChooseSplit", "whychoose_split.jsx"),
    ("ReviewsGrid", "reviews_grid.jsx"),
    ("PricingTiers", "pricing_tiers.jsx"),
    ("FaqList", "faq_list.jsx"),
    ("BannerCta", "banner_cta.jsx"),
]
CLOSER = ("CtaFooter", "cta_footer.jsx")

_HEADER = """'use client';
import * as React from 'react';
import { useState } from 'react';
import Link from 'next/link';
import { Icon } from '@/components/ui/icon';

"""


def _read(fname: str) -> str:
    with open(os.path.join(_DIR, fname), encoding="utf-8") as f:
        return f.read()


def compose_landing(rng: random.Random | None = None, hero_file: str | None = None) -> tuple[str, str]:
    """Return (description, source) for a freshly remixed landing page.
    `hero_file` (from the component bank's input-matched pick) overrides the
    random hero choice."""
    rng = rng or random.Random()
    hero = _HERO_BY_FILE.get(hero_file) or rng.choice(HEROES)
    pool = MIDDLES if hero[1] != "hero_stats_strip.jsx" else [m for m in MIDDLES if m[0] != "StatsAmbient"]
    count = rng.randint(4, 6)
    middles = rng.sample(pool, min(count, len(pool)))
    # FeatureTiles early reads better; FaqList late; keep sampled order otherwise.
    middles.sort(key=lambda m: 0 if m[0] == "FeatureTiles" else (2 if m[0] == "FaqList" else 1))

    chosen = [hero] + middles + [CLOSER]
    parts = [_HEADER]
    for _, fname in chosen:
        parts.append(_read(fname).rstrip() + "\n\n")

    render = "\n      ".join(f"<{name} />" for name, _ in chosen)
    parts.append(
        "export default function Home() {\n"
        "  return (\n"
        "    <div className=\"w-full\">\n"
        f"      {render}\n"
        "    </div>\n"
        "  );\n"
        "}\n"
    )
    desc = hero[0] + " + " + "/".join(m[0] for m in middles)
    return desc, "".join(parts)
