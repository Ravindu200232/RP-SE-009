"""The customer's own words, in one block any agent can paste into a prompt.

Every model call in the studio is about the same app, so every one of them
reads better for having the customer's actual sentences in front of it. "A POS
for Pubudu Tire Shop, we also do wheel alignment and we sell batteries" tells a
model far more about which options to offer than "retail / fullstack-crud" ever
will — and a customer who cannot describe their build in technical terms can
almost always describe their shop.

Two halves, and the second one is the one that goes missing. The idea is what
they typed in the intake box. The *typed* answers are the sentences they wrote
during the interview instead of ticking a chip — a customer who ticks two
options and then writes a line of their own cared most about the line, so it
belongs in the context of every question that comes after it.
"""
from __future__ import annotations

IDEA_LIMIT = 3000
TYPED_LIMIT = 1500


ATTACHED_LIMIT = 2500


def typed_so_far(session: dict | None) -> list[str]:
    """Every sentence the customer typed themselves, oldest first."""
    out: list[str] = []
    seen: set[str] = set()
    for entry in ((session or {}).get("answers") or {}).values():
        if not isinstance(entry, dict):
            continue
        for raw in (entry.get("custom_text"), entry.get("text")):
            text = str(raw or "").strip()
            if text and text.lower() not in seen:
                seen.add(text.lower())
                out.append(text)
    return out


def attached_so_far(session: dict | None) -> list[str]:
    """`filename: text` for every file they attached to an answer."""
    out: list[str] = []
    seen: set[str] = set()
    for entry in ((session or {}).get("answers") or {}).values():
        if not isinstance(entry, dict):
            continue
        for att in entry.get("attachments") or []:
            text = str((att or {}).get("text") or "").strip()
            name = str((att or {}).get("filename") or "attachment")
            if text and text.lower() not in seen:
                seen.add(text.lower())
                out.append(f"{name}: {text}")
    return out


def customer_context(brief: str = "", session: dict | None = None,
                     project: dict | None = None) -> str:
    """The idea and everything typed since, or "" when we know nothing yet.

    Callers pass whatever they happen to hold — the brief, the interview
    session, the project row — and the first one that carries the idea wins.
    """
    idea = str(brief
               or (session or {}).get("raw_idea")
               or (project or {}).get("raw_idea") or "").strip()
    typed = typed_so_far(session)
    attached = attached_so_far(session)
    if not idea and not typed and not attached:
        return ""

    parts: list[str] = ["THE CUSTOMER'S OWN WORDS — this is their app, and "
                        "their vocabulary is the one to answer in:"]
    if idea:
        parts.append(f'"""\n{idea[:IDEA_LIMIT]}\n"""')
    if typed:
        block = "\n".join(f"- {t}" for t in typed)
        parts.append("What they have typed themselves since:\n"
                     + block[:TYPED_LIMIT])
    if attached:
        block = "\n".join(f"- {a}" for a in attached)
        parts.append("From files they attached to their answers (a photo, a "
                     "PDF or something they said out loud — treat it as them "
                     "talking):\n" + block[:ATTACHED_LIMIT])
    return "\n\n".join(parts)


__all__ = ["customer_context", "typed_so_far", "attached_so_far",
           "IDEA_LIMIT", "TYPED_LIMIT", "ATTACHED_LIMIT"]
