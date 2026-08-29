"""Post-repair guards that keep an E2E fix inside the proven root cause."""
from __future__ import annotations

import re


_AUTH_PATTERNS = (
    re.compile(r"\bredirect\s*\(\s*['\"]/?login", re.I),
    re.compile(r"\b(?:router\.)?(?:push|replace)\s*\(\s*['\"]/?login", re.I),
    re.compile(r"\bauth\.api\.getSession\b", re.I),
    re.compile(r"\bgetSession\s*\(", re.I),
    re.compile(r"from\s+['\"]@/lib/auth['\"]", re.I),
)
_ATTR_RE = re.compile(r"\b(name|id|aria-label|data-testid)\s*=\s*['\"]([^'\"]+)['\"]", re.I)


def _words(text: str) -> set[str]:
    raw = set(re.findall(r"[a-z0-9]+", str(text or "").lower()))
    stop = {"field", "button", "role", "input", "selector", "page", "missing",
            "nothing", "matched", "expected", "test", "fix", "app", "the", "a",
            "an", "to", "of", "and", "or", "for", "with"}
    return {w for w in raw if len(w) > 2 and w not in stop}


def _selector_words(failure) -> set[str]:
    text = f"{getattr(failure, 'name', '')} {getattr(failure, 'message', '')}"
    m = re.search(r"(?:field\s+['\"]|field=)([A-Za-z0-9_-]+)", text, re.I)
    if m:
        return _words(m.group(1))
    m = re.search(r"(?:role\s+/|name=/)([^/]+)/", text, re.I)
    if m:
        return _words(m.group(1).replace("\\s", " "))
    m = re.search(r"testid\s+['\"]([^'\"]+)", text, re.I)
    return _words(m.group(1)) if m else set()


def _new_attributes(before: str, after: str) -> list[tuple[str, str]]:
    old = {(k.lower(), v.lower()) for k, v in _ATTR_RE.findall(before or "")}
    return [(k.lower(), v) for k, v in _ATTR_RE.findall(after or "")
            if (k.lower(), v.lower()) not in old]


def validate_repair_invariants(before_files: dict[str, str], after_files: dict[str, str],
                               changed: list[str], verdict: str, diagnosis: dict,
                               failure=None, journey=None) -> list[str]:
    """Return concrete reasons a patch escaped its evidence boundary."""
    verdict = str(verdict or "").upper()
    problems: list[str] = []
    root = " ".join(str(diagnosis.get(k) or "") for k in ("root", "hypothesis", "next"))
    auth_evidence = bool(re.search(r"\bauth|session|401|403|login\b", root, re.I))
    selector_words = _selector_words(failure)

    for rel in changed or []:
        before = str(before_files.get(rel, "") or "")
        after = str(after_files.get(rel, "") or "")
        if not after or before == after:
            continue

        if verdict != "AUTH_FIX" and not auth_evidence:
            for pattern in _AUTH_PATTERNS:
                if len(pattern.findall(after)) > len(pattern.findall(before)):
                    problems.append(
                        f"{rel}: added authentication/login routing while the proven root cause was not auth")
                    break

        if selector_words:
            for attr, value in _new_attributes(before, after):
                if attr not in {"name", "id", "aria-label", "data-testid"}:
                    continue
                got = _words(value)
                if got and not (got & selector_words):
                    line = next((ln for ln in after.splitlines() if value in ln), "")
                    if re.search(r"<(?:input|select|textarea|button)\b", line, re.I):
                        problems.append(
                            f"{rel}: added {attr}={value!r}, which does not match the failing selector concept {sorted(selector_words)}")
                        break
    return list(dict.fromkeys(problems))


def repair_guard_feedback(violations: list[str], diagnosis: dict, failure=None) -> str:
    exact = str(getattr(failure, "name", "") or "")
    return (
        "\n\nREPAIR INVARIANT GUARD\n"
        "The previous candidate patch was rolled back because it changed behavior outside the proven root cause.\n"
        + "\n".join(f"- {v}" for v in violations[:6])
        + f"\nKeep auth/role/route policy unchanged unless the evidence explicitly proves an auth defect.\n"
        + (f"Preserve the exact failing scenario intent: {exact}\n" if exact else "")
        + "Repair the smallest production owner that satisfies the accepted workflow; do not rename a different field to make the test pass.\n"
    )
