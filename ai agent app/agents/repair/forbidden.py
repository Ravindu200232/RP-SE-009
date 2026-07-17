"""agents/repair/forbidden.py — the forbidden-fake-repair guard (P1).

A repair must be a genuine fix, never a suppression. This rejects a patch that INTRODUCES any banned
construct (counted vs. the file's prior text, so pre-existing ones don't block an unrelated fix):
`@ts-ignore`, `@ts-nocheck`, `@ts-expect-error`, `as any`, `ignoreBuildErrors`, `ignoreDuringBuilds`,
file-level `eslint-disable`, and `next.config` type/lint bypasses. Deleting tests or replacing required
data with static mock arrays is caught by the harness's scope/coverage checks, not here.
"""
from __future__ import annotations

import re

_BANNED = [
    (re.compile(r"@ts-ignore"), "@ts-ignore"),
    (re.compile(r"@ts-nocheck"), "@ts-nocheck"),
    (re.compile(r"@ts-expect-error"), "@ts-expect-error"),
    (re.compile(r"\bas\s+any\b"), "as any"),
    (re.compile(r"<\s*any\s*>"), "<any> cast"),
    (re.compile(r"ignoreBuildErrors"), "typescript.ignoreBuildErrors"),
    (re.compile(r"ignoreDuringBuilds"), "eslint.ignoreDuringBuilds"),
    (re.compile(r"/\*\s*eslint-disable\s*\*/"), "file-level eslint-disable"),
    (re.compile(r"(?m)^\s*//\s*eslint-disable\b(?!-next-line)"), "file-level eslint-disable"),
]


def introduced(new_text: str, old_text: str = "") -> list[str]:
    """Banned constructs the patch ADDS (present more often in new than old). Empty == clean."""
    hits: list[str] = []
    for rx, name in _BANNED:
        if len(rx.findall(new_text or "")) > len(rx.findall(old_text or "")):
            hits.append(name)
    # de-dup, preserve order
    seen, out = set(), []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out
