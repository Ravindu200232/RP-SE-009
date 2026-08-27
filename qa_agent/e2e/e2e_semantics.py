"""App-neutral semantic helpers shared by E2E authoring and execution.

The helpers in this module deliberately know nothing about a sample domain,
route, role, collection, status, test id, or piece of product copy.  They turn
observed words into comparable tokens and keep time-sensitive test data valid
when an exported Playwright spec is run again later.
"""
from __future__ import annotations

from datetime import date, timedelta
import re


_RELATIVE_DATE_RE = re.compile(r"^\{\{date(?P<sign>[+-])(?P<days>\d{1,3})\}\}$", re.I)
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_WORD_RE = re.compile(r"[A-Za-z0-9]+")
_STOP_WORDS = {
    "a", "an", "and", "button", "control", "field", "for", "link",
    "my", "of", "on", "or", "page", "role", "test", "text", "that",
    "the", "this", "to", "with",
}
_MAX_RELATIVE_DAYS = 3650


def _stem(word: str) -> str:
    """Small deterministic normalizer, not a product-vocabulary synonym map."""
    word = str(word or "").lower()
    if len(word) > 5 and word.endswith("ies"):
        return word[:-3] + "y"
    for suffix in ("ing", "ed", "es", "s"):
        if suffix == "s" and word.endswith(("ss", "us", "is")):
            continue
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[:-len(suffix)]
    return word


def semantic_words(text: str) -> set[str]:
    """Comparable words from DOM/source/plan text without domain assumptions."""
    # Split camelCase attributes before punctuation is removed.
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(text or ""))
    out = set()
    for raw in _WORD_RE.findall(expanded):
        word = _stem(raw)
        if len(word) > 2 and word not in _STOP_WORDS:
            out.add(word)
    return out


def relative_date_token(offset_days: int) -> str:
    """Stable declarative token accepted by both Python and JS runners."""
    days = max(-_MAX_RELATIVE_DAYS, min(_MAX_RELATIVE_DAYS, int(offset_days)))
    sign = "+" if days >= 0 else "-"
    return f"{{{{date{sign}{abs(days)}}}}}"


def is_relative_date(value: str) -> bool:
    return bool(_RELATIVE_DATE_RE.fullmatch(str(value or "").strip()))


def is_iso_date(value: str) -> bool:
    text = str(value or "").strip()
    if not _ISO_DATE_RE.fullmatch(text):
        return False
    try:
        date.fromisoformat(text)
        return True
    except ValueError:
        return False


def resolve_runtime_value(value: str, *, today: date | None = None) -> str:
    """Resolve a relative token at execution time; leave all other data alone."""
    text = str(value or "")
    match = _RELATIVE_DATE_RE.fullmatch(text.strip())
    if not match:
        return text
    days = int(match.group("days"))
    if match.group("sign") == "-":
        days = -days
    return ((today or date.today()) + timedelta(days=days)).isoformat()


def js_runtime_value(value: str, js_string) -> str:
    """JavaScript expression equivalent to :func:`resolve_runtime_value`."""
    text = str(value or "")
    match = _RELATIVE_DATE_RE.fullmatch(text.strip())
    if not match:
        return js_string(text)
    days = int(match.group("days"))
    if match.group("sign") == "-":
        days = -days
    return f"relativeDate({days})"


__all__ = [
    "is_iso_date", "is_relative_date", "js_runtime_value",
    "relative_date_token", "resolve_runtime_value", "semantic_words",
]
