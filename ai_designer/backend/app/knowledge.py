"""Design knowledge base — every page of the user's own five projects, indexed
(`design_knowledge.json`, built by crawling them). When a new request is CLOSE
to something the user has built before, the matched pages' structure guides the
generation - adapted to the new input, never copied wholesale.
"""
import json
import os
import re

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "design_knowledge.json")
_WORD = re.compile(r"[a-z]{3,}")

_DOMAIN_HINTS = {
    "shop": ["product", "cart", "checkout", "store", "order"],
    "store": ["product", "cart", "checkout", "shop", "order"],
    "ecommerce": ["product", "cart", "checkout", "order"],
    "school": ["course", "student", "lms", "lesson", "grade"],
    "learning": ["course", "lms", "lesson", "instructor"],
    "course": ["lms", "lesson", "instructor", "student"],
    "audio": ["product", "shop", "speaker", "headphone"],
    "photo": ["gallery", "album", "portfolio", "booking"],
    "cleaning": ["booking", "service", "schedule"],
    "food": ["menu", "restaurant", "order", "delivery"],
    "restaurant": ["menu", "food", "order", "reservation"],
}


def _load():
    try:
        with open(_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def match(prompt_text: str, top: int = 4) -> list:
    """Top index entries similar to the user's input."""
    words = set(_WORD.findall((prompt_text or "").lower()))
    for w in list(words):
        words.update(_DOMAIN_HINTS.get(w, []))
    if not words:
        return []
    scored = []
    for e in _load():
        tagset = set(e.get("tags", [])) | set(e.get("sections", []))
        hits = len(words & tagset)
        if hits >= 2:
            scored.append((hits + min(e.get("images", 0), 5) * 0.1, e))
    scored.sort(key=lambda x: -x[0])
    return [e for _, e in scored[:top]]


def reference_hint(matches: list) -> str:
    """A short structure hint for the copywriter, distilled from matched pages."""
    if not matches:
        return ""
    parts = []
    for e in matches[:3]:
        bits = []
        if e.get("sections"):
            bits.append("sections: " + ", ".join(e["sections"][:6]))
        if e.get("headings"):
            bits.append("headings like: " + "; ".join(e["headings"][:2]))
        parts.append(f"{e['project']}/{os.path.basename(e['file'])} ({'; '.join(bits)})" if bits else f"{e['project']}/{os.path.basename(e['file'])}")
    return ("The user has built similar pages before - take inspiration from their structure "
            "(adapt it to this app, do not copy): " + " | ".join(parts))


def bias_tags(matches: list) -> str:
    """Extra words appended to the prompt for design selection biasing."""
    tags = []
    for e in matches:
        tags += e.get("sections", [])[:4]
    return " ".join(sorted(set(tags)))
