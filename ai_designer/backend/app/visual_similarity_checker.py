"""Visual similarity checker — prevents the same visual signature appearing twice.

Computes a signature from a design blueprint and compares it against the
shared design_history.json. Returns a similarity score and recommendation.
Called BEFORE page generation so the Design Agent can be told to pivot if
the new blueprint is too close to a recent app.
"""
import json
import os

# Fields that carry the most visual weight for distinguishing apps.
# Structural fields (listing_variant, filter_placement, page_layout_variant)
# are included so two apps with same colors but same structure still fail.
_SIG_FIELDS = [
    "navbar_style",
    "hero_composition",
    "card_style",
    "dashboard_shell",
    "background_style",
    "button_style",
    "layout_style",
    "domain_mood",
    # Structural layout fields — prevent same-skeleton pages with different colors
    "listing_variant",
    "filter_placement",
    "page_layout_variant",
]

_PALETTE_KEYS = ["primary", "accent", "background"]


def compute_signature(blueprint: dict) -> dict:
    return {f: str(blueprint.get(f, "")).lower().strip() for f in _SIG_FIELDS}


def _field_sim(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return 1.0 if a == b else 0.0


def _palette_sim(a: dict, b: dict) -> float:
    if not a or not b:
        return 0.0
    hits = sum(1 for k in _PALETTE_KEYS if a.get(k) and a.get(k) == b.get(k))
    return hits / len(_PALETTE_KEYS)


def compute_similarity(
    sig_a: dict,
    sig_b: dict,
    palette_a: dict | None = None,
    palette_b: dict | None = None,
) -> float:
    """Compute similarity score [0.0, 1.0] between two design signatures."""
    if not sig_a or not sig_b:
        return 0.0

    total = sum(_field_sim(sig_a.get(f, ""), sig_b.get(f, "")) for f in _SIG_FIELDS)
    count = len(_SIG_FIELDS)

    # Palette gets double weight (strong visual signal)
    if palette_a and palette_b:
        total += _palette_sim(palette_a, palette_b) * 2
        count += 2

    return round(total / count, 4) if count else 0.0


def check_similarity(
    blueprint: dict,
    history_path: str,
    exclude_app_name: str = "",
) -> dict:
    """Check a blueprint against design history.

    Args:
        blueprint: the new design blueprint
        history_path: path to design_history.json
        exclude_app_name: app name to skip in history (pass the current app's name
            to avoid false-positive same-app self-comparison)

    Returns:
        {
          "similarity": float,   # max pairwise similarity to any recent *other* app
          "too_similar": bool,   # True when similarity > 0.75
          "most_similar_app": str or None,
          "recommendation": str,
        }
    """
    history: list = []
    try:
        if os.path.exists(history_path):
            with open(history_path, encoding="utf-8") as f:
                history = json.load(f)
            if not isinstance(history, list):
                history = []
    except Exception:
        pass

    if not history:
        return {
            "similarity": 0.0,
            "too_similar": False,
            "most_similar_app": None,
            "recommendation": "No design history — first generation is always unique.",
        }

    new_sig = compute_signature(blueprint)
    new_palette = blueprint.get("color_palette", {})

    max_sim = 0.0
    most_similar: str | None = None

    # Compare against the last 15 apps only (older ones are less relevant)
    exclude_lower = exclude_app_name.strip().lower()
    for h in history[-15:]:
        if exclude_lower and h.get("app_name", "").strip().lower() == exclude_lower:
            continue  # Skip same-app entries — self-comparison is not a real failure
        h_sig = compute_signature(h)
        h_palette = h.get("color_palette", {})
        sim = compute_similarity(new_sig, h_sig, new_palette, h_palette)
        if sim > max_sim:
            max_sim = sim
            most_similar = h.get("app_name")

    too_similar = max_sim > 0.75

    if too_similar:
        recommendation = (
            f"Too similar to '{most_similar}' (score={max_sim:.2f}). "
            "Design Agent should change navbar_style, hero_composition, and primary colour."
        )
    elif max_sim > 0.5:
        recommendation = (
            f"Moderate similarity to '{most_similar}' ({max_sim:.2f}). "
            "Consider varying card_style or background_style."
        )
    else:
        recommendation = f"Good visual diversity (max similarity={max_sim:.2f})."

    return {
        "similarity": max_sim,
        "too_similar": too_similar,
        "most_similar_app": most_similar,
        "recommendation": recommendation,
    }
