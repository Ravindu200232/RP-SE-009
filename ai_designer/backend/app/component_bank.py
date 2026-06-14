"""Component bank — N variants per design FAMILY, each tagged with the project
types it suits. Per generation, ONE variant per family is picked to match the
user's input (tag overlap) with anti-repeat history, so the COMPLETE design
(hero + navbar + footer + dashboard + list + sections) changes app to app.

Families and how variants are realized:
- hero      -> section files in library_next/sections (full JSX variants)
- navbar    -> style presets applied by the scaffold Navbar via site.styles.nav
- footer    -> style presets in the composed CtaFooter / template footers
- dashboard -> style presets applied by the scaffold dashboard via site.styles.dash
- list      -> style presets applied by the generic list page via site.styles.list
The registry is the 'memory' of which component suits which projects (tags).
Adding a variant = appending an entry (and a file for hero sections).
"""
import json
import os
import random

_HISTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_component_history.json")

REGISTRY = {
    "hero": [
        {"name": "slider", "file": "hero_slider.jsx", "tags": ["lms", "school", "travel", "hotel", "gallery", "media", "event"]},
        {"name": "split-radial", "file": "hero_split_radial.jsx", "tags": ["service", "cleaning", "clinic", "hospital", "saas", "business"]},
        {"name": "gradient-glow", "file": "hero_gradient_glow.jsx", "tags": ["ai", "tech", "startup", "saas", "gaming", "creative"]},
        {"name": "minimal-left", "file": "hero_minimal_left.jsx", "tags": ["corporate", "finance", "legal", "consulting", "b2b"]},
        {"name": "product-card", "file": "hero_product_card.jsx", "tags": ["shop", "store", "ecommerce", "audio", "product", "retail"]},
        {"name": "editorial-serif", "file": "hero_editorial_serif.jsx", "tags": ["restaurant", "salon", "fashion", "boutique", "photo", "studio"]},
        {"name": "split-screen", "file": "hero_split_screen.jsx", "tags": ["hotel", "estate", "travel", "clinic", "service"]},
        {"name": "stats-strip", "file": "hero_stats_strip.jsx", "tags": ["saas", "b2b", "analytics", "finance", "platform"]},
        {"name": "centered-clean", "file": "hero_centered_clean.jsx", "tags": ["legal", "consulting", "minimal", "portfolio", "corporate"]},
        {"name": "photo-left-dark", "file": "hero_photo_left_dark.jsx", "tags": ["audio", "gaming", "media", "night", "music", "studio"]},
    ],
    "nav": [
        {"name": "solid", "tags": ["corporate", "hospital", "finance", "b2b"]},
        {"name": "blur", "tags": ["saas", "tech", "startup", "modern"]},
        {"name": "pill", "tags": ["creative", "studio", "salon", "fashion", "photo"]},
        {"name": "dark", "tags": ["gaming", "audio", "media", "ai", "night"]},
        {"name": "minimal", "tags": ["editorial", "boutique", "legal", "portfolio"]},
        {"name": "accent-top", "tags": ["shop", "store", "ecommerce", "retail", "food", "restaurant"]},
        {"name": "underline", "tags": ["lms", "school", "education", "consulting"]},
        {"name": "accent-solid", "tags": ["event", "travel", "hotel", "sports"]},
        {"name": "floating", "tags": ["creative", "startup", "modern", "ai"]},
        {"name": "tinted", "tags": ["clinic", "health", "service", "cleaning"]},
    ],
    "footer": [
        {"name": "columns", "tags": ["saas", "corporate", "hospital", "b2b"]},
        {"name": "minimal", "tags": ["editorial", "boutique", "portfolio", "studio"]},
        {"name": "dark", "tags": ["gaming", "audio", "ai", "media"]},
        {"name": "centered", "tags": ["salon", "restaurant", "fashion", "event"]},
        {"name": "gradient", "tags": ["startup", "creative", "tech", "modern"]},
        {"name": "compact", "tags": ["shop", "store", "retail", "tools"]},
        {"name": "tinted", "tags": ["clinic", "health", "school", "lms"]},
        {"name": "bordered", "tags": ["legal", "finance", "consulting"]},
        {"name": "big-brand", "tags": ["media", "agency", "studio", "event"]},
        {"name": "soft", "tags": ["travel", "hotel", "service", "cleaning"]},
    ],
    "dash": [
        {"name": "classic", "tags": ["corporate", "hospital", "finance", "b2b"]},
        {"name": "band", "tags": ["creative", "startup", "modern", "media"]},
        {"name": "tinted", "tags": ["school", "lms", "education", "health"]},
        {"name": "glass", "tags": ["ai", "tech", "gaming", "saas"]},
        {"name": "outline", "tags": ["editorial", "legal", "boutique", "minimal"]},
        {"name": "bold", "tags": ["shop", "store", "ecommerce", "retail", "food"]},
        {"name": "gradient-cards", "tags": ["event", "travel", "agency", "creative"]},
        {"name": "flat", "tags": ["consulting", "b2b", "minimal", "legal"]},
        {"name": "ring", "tags": ["clinic", "health", "service", "salon"]},
        {"name": "mono", "tags": ["finance", "logistics", "warehouse", "admin"]},
    ],
    "list": [
        {"name": "classic", "tags": ["corporate", "hospital", "finance"]},
        {"name": "striped", "tags": ["school", "lms", "education", "b2b"]},
        {"name": "cards", "tags": ["shop", "store", "ecommerce", "photo", "gallery", "product"]},
        {"name": "dense", "tags": ["finance", "logistics", "warehouse", "admin"]},
        {"name": "soft", "tags": ["salon", "clinic", "health", "service"]},
        {"name": "dark-head", "tags": ["gaming", "audio", "media", "ai"]},
        {"name": "bordered", "tags": ["legal", "consulting", "corporate"]},
        {"name": "pill-rows", "tags": ["creative", "studio", "fashion", "event"]},
        {"name": "airy", "tags": ["editorial", "boutique", "travel", "hotel"]},
        {"name": "accent-edge", "tags": ["startup", "saas", "tech", "modern"]},
    ],
}

_SYNONYMS = {
    "hospital": ["clinic", "health", "service"], "school": ["lms", "education"],
    "gym": ["service", "health", "modern"], "fitness": ["service", "health"],
    "restaurant": ["food", "service"], "ecommerce": ["shop", "store", "retail", "product"],
    "store": ["shop", "retail", "product"], "audio": ["product", "shop", "media"],
    "photo": ["studio", "gallery", "creative"], "management": ["corporate", "b2b"],
    "system": ["corporate"], "app": ["modern"], "platform": ["saas", "modern"],
}


def _load_history():
    try:
        with open(_HISTORY, encoding="utf-8") as f:
            return json.load(f)[-4:]
    except Exception:
        return []


def _save_history(hist):
    try:
        with open(_HISTORY, "w", encoding="utf-8") as f:
            json.dump(hist[-4:], f)
    except OSError:
        pass


def pick_components(prompt_text: str) -> dict:
    """One variant per family, biased to the input's domain tags, avoiding the
    previous two runs' choices. Returns {family: entry}."""
    words = set(w for w in (prompt_text or "").lower().split() if len(w) > 2)
    for w in list(words):
        words.update(_SYNONYMS.get(w.strip(".,"), []))
    hist = _load_history()
    recent = {f: [h.get(f) for h in hist[-2:]] for f in REGISTRY}

    chosen = {}
    for family, entries in REGISTRY.items():
        def weight(e):
            w = 1.0 + 1.6 * len(words & set(e["tags"]))
            if e["name"] in recent.get(family, []):
                w *= 0.15
            return w
        chosen[family] = random.choices(entries, weights=[weight(e) for e in entries], k=1)[0]

    hist.append({f: chosen[f]["name"] for f in chosen})
    _save_history(hist)
    return chosen
