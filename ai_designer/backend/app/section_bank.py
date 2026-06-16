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


def compose_landing(rng: random.Random | None = None, hero_file: str | None = None,
                    prompt_text: str = "") -> tuple[str, str]:
    """Return (description, source) for a freshly remixed landing page.

    A page = one file-based HERO + 4-6 MIDDLE sections drawn from the 100+ entry
    `section_catalog` (input-tag matched + randomised) + the file-based CtaFooter.
    `hero_file` (from the component bank's input-matched pick) overrides the random
    hero. The catalog renders each middle as a uniquely-named, function-scoped
    component, so any combination stays valid JSX."""
    from app import section_catalog
    rng = rng or random.Random()
    hero = _HERO_BY_FILE.get(hero_file) or rng.choice(HEROES)
    count = rng.randint(4, 6)
    middles = section_catalog.pick_middles(rng, count, prompt_text)

    parts = [_HEADER, _read(hero[1]).rstrip() + "\n\n"]
    mid_names = []
    for i, entry in enumerate(middles):
        nm = f"Section{i + 1}"
        parts.append(section_catalog.render(entry, nm).rstrip() + "\n\n")
        mid_names.append(nm)
    parts.append(_read(CLOSER[1]).rstrip() + "\n\n")

    names = [hero[0]] + mid_names + [CLOSER[0]]
    render = "\n      ".join(f"<{nm} />" for nm in names)
    parts.append(
        "export default function Home() {\n"
        "  return (\n"
        "    <div className=\"w-full\">\n"
        f"      {render}\n"
        "    </div>\n"
        "  );\n"
        "}\n"
    )
    desc = hero[0] + " + " + "/".join(e["family"] for e in middles)
    return desc, "".join(parts)
