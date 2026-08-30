"""Resolve a selected DOM element to source and guard whole-file rewrites."""
from __future__ import annotations

import difflib
import logging
import re
from dataclasses import dataclass, field

# Source: import_reader.py — imported helper(s) come from this file.
from agents.core.imports.import_reader import parse_exports, resolve_local
# Source: feature_prompts.py — imported helper(s) come from this file.
from agents.features.feature_prompts import feature_prompt

log = logging.getLogger("picker")

MAX_CANDIDATES = 12

DECISIVE_MARGIN = 1.3

LOCAL_IMPORT_RE = re.compile(
    r"""(?:from|import)\s*['"]((?:\.{1,2}/|@/)[^'"]+)['"]""")


@dataclass
class Resolution:
    path: str = ""
    line: int = 0
    score: int = 0
    candidates: list = field(default_factory=list)
    used_model: bool = False
    reason: str = ""


class ElementResolver:
    # Prepares ElementResolver with the services and starting state it needs before it begins work.
    def __init__(self, arch, analyzer):
        """Prepare this helper with the state it needs."""
        self.arch = arch
        self.az = analyzer

    # Returns the route page, parent layouts, and local imports.
    def route_closure(self, route: str) -> list:
        """Return the route page, parent layouts, and local imports."""
        files = self.az.code_files()
        routes = self.az.enumerate_routes()
        path = (route or "/").split("?")[0].rstrip("/") or "/"

        entry = None
        for url, r in routes.items():
            if r["kind"] != "page":
                continue
            if url == path or self.az._route_matches(path, [url]):
                entry = r["file"]
                break
        seeds = [entry] if entry else []

        segs = [s for s in path.strip("/").split("/") if s]
        for i in range(len(segs), -1, -1):
            for ext in (".js", ".jsx"):
                cand = "/".join(["app"] + segs[:i] + ["layout" + ext])
                if cand in files:
                    seeds.append(cand)

        seen, queue = set(), [s for s in seeds if s]
        while queue:
            rel = queue.pop()
            if rel in seen or rel not in files:
                continue
            seen.add(rel)
            for spec in LOCAL_IMPORT_RE.findall(files[rel]):
                # From: agents/core/imports/import_reader.py
                target = resolve_local(rel, spec, files)
                if target and target not in seen:
                    queue.append(target)
        return sorted(seen)

    # Decide candidates from the available evidence so the next step works on the correct target.
    def score_candidates(self, el: dict, pool: list) -> list:
        """Prepare the score candidates value or state used by this focused pipeline step."""
        files = self.az.code_files()
        pool = [p for p in pool if p in files] or list(files)
        text = (el.get("text") or "").strip()
        cls = (el.get("className") or "").strip()
        attrs = el.get("attrs") or {}
        el_id = (el.get("id") or "").strip()
        testid = attrs.get("data-testid") or ""
        tag = (el.get("tag") or "").lower()

        out = []
        for rel in pool:
            body = files[rel]
            score, lines = 0, []

            # Add evidence weight when this selected-element clue appears in the candidate source file.
            def add_match_score(needle, weight):
                """Add evidence weight when this selected-element clue appears in the candidate source file."""
                nonlocal score
                if not needle or len(str(needle)) < 2 or needle not in body:
                    return
                score += weight
                lines.append(body[:body.index(needle)].count("\n") + 1)

            add_match_score(el_id, 6)
            add_match_score(testid, 6)
            if text and len(text) >= 3:
                add_match_score(text[:80], 5)
            if cls and len(cls) >= 6:
                add_match_score(cls, 4)
            for key in ("placeholder", "alt", "aria-label", "href", "name"):
                add_match_score(attrs.get(key), 4)
            if tag and re.search(rf"<{re.escape(tag)}[\s/>]", body):
                score += 1
            anc = 0
            for a in (el.get("chain") or [])[:6]:
                t = (a.get("text") or "").strip()
                if t and len(t) >= 4 and t[:60] in body and anc < 3:
                    score += 1
                    anc += 1
            if score:
                out.append((rel, score, sorted(set(lines))))
        out.sort(key=lambda c: (-c[1], c[0]))
        return out[:MAX_CANDIDATES]

    # Compare similarly scored UI candidates and choose the one that best matches the user selection evidence.
    def disambiguate(self, el: dict, ranked: list) -> tuple:
        """Prepare the disambiguate value or state used by this focused pipeline step."""
        files = self.az.code_files()
        blocks = []
        for rel, score, lines in ranked[:6]:
            body = files.get(rel, "").splitlines()
            excerpt = []
            for ln in lines[:3]:
                lo, hi = max(0, ln - 3), min(len(body), ln + 3)
                excerpt.append(f"  line {ln}:\n" +
                               "\n".join(f"    {body[i]}" for i in range(lo, hi)))
            blocks.append(f"--- {rel} (score {score}) ---\n" + "\n".join(excerpt))

        system = ("Pick which source file renders the element the user clicked.\n"
                  "Reply with exactly one line and nothing else:\n"
                  "PICK <path> <line>")
        user = (f"Route: {el.get('route', '/')}\n"
                f"Element: <{el.get('tag')}"
                + (f" id=\"{el.get('id')}\"" if el.get("id") else "")
                + (f" class=\"{el.get('className')}\"" if el.get("className") else "")
                + f">{(el.get('text') or '')[:120]}</{el.get('tag')}>\n\n"
                + "\n\n".join(blocks))
        buf = []
        try:
            self.arch._stream([{"role": "system", "content": system},
                               {"role": "user", "content": user}],
                              buf.append, temperature=0.1)
        except Exception as e:
            log.warning(f"disambiguation failed: {e}")
            return ranked[0][0], (ranked[0][2] or [0])[0]
        m = re.search(r"PICK\s+(\S+)\s*(\d+)?", "".join(buf))
        if m and m.group(1).strip("`") in files:
            return m.group(1).strip("`"), int(m.group(2) or 0)
        return ranked[0][0], (ranked[0][2] or [0])[0]

    # Turn the captured UI selection into the final source-file target and element match used by the editor.
    def resolve(self, el: dict) -> Resolution:
        """Resolve current step in the standard shape used by the rest of the pipeline."""
        closure = self.route_closure(el.get("route", "/"))
        ranked = self.score_candidates(el, closure)
        if not ranked:

            ranked = self.score_candidates(el, list(self.az.code_files()))
        if not ranked:
            return Resolution(reason="nothing in the project matches this element")

        top = ranked[0]
        runner = ranked[1][1] if len(ranked) > 1 else 0
        decisive = top[1] > 0 and (runner == 0 or top[1] >= runner * DECISIVE_MARGIN)
        cands = [{"path": p, "score": s} for p, s, _ in ranked]
        if decisive:
            return Resolution(path=top[0], line=(top[2] or [0])[0], score=top[1],
                              candidates=cands, used_model=False,
                              reason="unambiguous")
        path, line = self.disambiguate(el, ranked)
        return Resolution(path=path, line=line,
                          score=next((s for p, s, _ in ranked if p == path), 0),
                          candidates=cands, used_model=True,
                          reason="scores were close; the model chose")


# Maps each local source file to the other files that import it.

# Source: selection_rules.py — selected-element scope and UI safety rules.
from agents.features.selection_rules import (ELEMENT_EDIT_SYSTEM, describe, guard_scope,
    looks_like_addition, looks_like_global, looks_like_page_only, looks_like_removal,
    looks_like_retext, lost_content, render_index, routes_rendering, visible_strings)
