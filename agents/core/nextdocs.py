"""
Next.js's own error pages, fetched for the fix prompt.

When Next reports an error it names the page that explains it:

    Route "/products/[slug]": Next.js encountered uncached data during
    prerendering. …
    Learn more: https://nextjs.org/docs/messages/blocking-prerender-dynamic

Those pages are written for agents — the canonical fix, the trade-offs against
the alternatives, and the mistakes a first attempt usually makes. They are the
one part of the Next.js documentation that is **not** bundled into the npm
package, so they have to come over the network.

AgentForge already captures the text containing that link, in both `next_stderr()`
and `_npm_build_errors()`. All this module does is notice the link, fetch the
markdown once, cache it, and hand it back so the fix prompt can carry the
official answer instead of the model's recollection of one.

Deliberately quiet: a build must never fail because a documentation site was
unreachable. Every error path returns "" and logs at debug level.

The model cannot do this itself — `agents/core/commands.py` bans curl, wget and
PowerShell — so the fetch happens here, in AgentForge's Python.
"""
import logging
import re
import threading
from pathlib import Path

import requests

log = logging.getLogger("nextdocs")


MESSAGE_LINK_RE = re.compile(
    r"nextjs\.org/docs/messages/([a-z0-9][a-z0-9-]{2,60})", re.I)

BASE = "https://nextjs.org/docs/messages"
TIMEOUT = 12


MAX_BYTES = 60_000


MAX_PAGES = 2

_lock = threading.Lock()
_mem: dict = {}


def cache_dir() -> Path:
    return Path.home() / ".agentforge" / "docs" / "messages"


def slugs_in(text: str) -> list:
    """Every error-page slug named in a blob of build or server output."""
    seen, out = set(), []
    for m in MESSAGE_LINK_RE.finditer(text or ""):
        s = m.group(1).lower()
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def fetch(slug: str, *, offline: bool = False) -> str:
    """
    The markdown for one error page, or "".

    Cached in memory for the process and on disk across runs, because the same
    handful of errors recur across every project a user generates.
    """
    slug = (slug or "").strip().lower()

    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,60}", slug):
        return ""

    with _lock:
        if slug in _mem:
            return _mem[slug]

    fp = cache_dir() / f"{slug}.md"
    try:
        if fp.is_file():
            body = fp.read_text(encoding="utf-8")
            with _lock:
                _mem[slug] = body
            return body
    except Exception as e:
        log.debug(f"docs cache read failed for {slug}: {e}")

    if offline:
        return ""

    try:
        r = requests.get(f"{BASE}/{slug}.md", timeout=TIMEOUT,
                         headers={"Accept": "text/markdown"})
        if r.status_code != 200:
            log.debug(f"docs {slug}: HTTP {r.status_code}")
            return ""
        body = r.text[:MAX_BYTES]

        if (not body.strip()
                or "<!DOCTYPE" in body[:200]
                or body.lstrip().startswith("# Page Not Found")):
            log.debug(f"docs {slug}: no such page")
            return ""
    except Exception as e:
        log.debug(f"docs {slug} unreachable: {e}")
        return ""

    try:
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(body, encoding="utf-8")
    except Exception as e:
        log.debug(f"docs cache write failed for {slug}: {e}")

    with _lock:
        _mem[slug] = body
    return body


def guidance_for(text: str, *, offline: bool = False,
                 max_pages: int = MAX_PAGES) -> str:
    """
    The prompt section for whatever error pages `text` names, or "".

    Returns markdown ready to append to a fix prompt. Empty when the output
    names no page, when nothing could be fetched, or when the network is down —
    the caller appends it unconditionally and gets nothing on the quiet path.
    """
    parts = []
    for slug in slugs_in(text)[:max_pages]:
        body = fetch(slug, offline=offline)
        if body:
            parts.append(f"### {slug}\n{body.strip()}")
    if not parts:
        return ""
    return ("## How Next.js says to fix this\n"
            "These are Next.js's own error pages for the errors above. They "
            "give the canonical fix and the trade-offs. Follow them rather "
            "than guessing.\n\n" + "\n\n".join(parts))
