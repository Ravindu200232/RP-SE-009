"""Small, deterministic repairs for malformed scenario locator grammar."""
from __future__ import annotations

import re

from .flows import Selector, parse_selector


_WRAPPED_ROLE = re.compile(r"^role=([a-z]+)(?:\s+name=(.+))?$", re.I)
_WRAPPED_FIELD = re.compile(r"^field=([A-Za-z][A-Za-z0-9_-]{1,30})$", re.I)
_WRAPPED_KIND = re.compile(r"^(testid|label|placeholder|href|text)=(.+)$", re.I)


def _plain_pattern(selector) -> str:
    if not selector:
        return ""
    text = str(getattr(selector, "pattern", "") or "").strip()
    if getattr(selector, "is_regex", False):
        return text
    return text.strip("'\"")


def normalize_scenario_selectors(sc) -> list[str]:
    """Unwrap selector grammar that a model accidentally placed inside text.

    This never guesses product copy.  It only turns shapes such as
    ``EXPECT_TEXT :: role=combobox`` into the selector operation they plainly
    encode.  Returning notes makes the correction visible in the build log.
    """
    notes: list[str] = []
    for step in getattr(sc, "steps", []) or []:
        sel = getattr(step, "selector", None)
        if not sel or getattr(sel, "kind", "") != "text":
            continue
        raw = _plain_pattern(sel)
        if not raw:
            continue

        replacement = None
        m = _WRAPPED_ROLE.fullmatch(raw)
        if m:
            role = m.group(1).lower()
            rest = (m.group(2) or "/.*/").strip()
            parsed, why = parse_selector(f"role={role} name={rest}")
            if not why:
                replacement = parsed
        else:
            m = _WRAPPED_FIELD.fullmatch(raw)
            if m:
                parsed, why = parse_selector(f"field={m.group(1)}")
                if not why:
                    replacement = parsed
            else:
                m = _WRAPPED_KIND.fullmatch(raw)
                if m and m.group(1).lower() != "text":
                    parsed, why = parse_selector(raw)
                    if not why:
                        replacement = parsed

        if replacement is None:
            continue

        old = step.describe()
        step.selector = replacement
        if step.verb == "EXPECT_TEXT":
            step.verb = "WAIT_FOR"
        notes.append(f"{old} -> {step.describe()}")
    return notes
