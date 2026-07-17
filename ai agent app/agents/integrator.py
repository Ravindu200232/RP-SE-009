"""
agents/integrator.py — Integrator / Reviewer agent.

A deterministic integration pass over the LLM-generated frontend. Small models
reliably make two integration mistakes that a page-load test won't always catch:

  1. Calling the wrong endpoint segment — fetch('/api/task') when the route the
     API agent created is /api/tasks. We snap these to the nearest real segment.
  2. Forgetting the "use client" directive on an interactive component.

Both are fixed here without another flaky LLM round-trip, so wiring is correct by
construction against the fixed API contract.
"""
import logging
import re

from agents.scaffold import route_name

log = logging.getLogger("integrator")

_INTERACTIVE = re.compile(
    r"\b(useState|useEffect|useRef|useMemo|useCallback|onClick|onChange|onSubmit|"
    r"onInput|motion\.|AnimatePresence|useReducer|useContext)\b"
)
_FETCH_SEG = re.compile(r"""(['"`])/api/([A-Za-z0-9_-]+)""")


class IntegratorAgent:
    def __init__(self, write, valid_segments):
        self.write = write                       # write(relpath, content)
        self.valid = set(valid_segments or [])   # e.g. {'tasks', 'categories'}

    def review(self, files: dict) -> list:
        warnings = []
        for rel, content in list(files.items()):
            if not rel.endswith((".jsx", ".tsx")):
                continue
            new = self._ensure_use_client(content)
            new, w = self._snap_fetch_segments(rel, new)
            warnings.extend(w)
            if new != content:
                self.write(rel, new)
        if warnings:
            log.info("   Integrator applied %d fix(es): %s", len(warnings), "; ".join(warnings[:5]))
        else:
            log.info("   Integrator: frontend/API wiring clean")
        return warnings

    def _ensure_use_client(self, code: str) -> str:
        head = code.lstrip()
        if head.startswith(("'use client'", '"use client"')):
            return code
        if _INTERACTIVE.search(code):
            return "'use client'\n\n" + code
        return code

    def _snap_fetch_segments(self, rel: str, code: str):
        if not self.valid:
            return code, []
        warnings = []

        def repl(m):
            quote, seg = m.group(1), m.group(2)
            if seg in self.valid:
                return m.group(0)
            target = self._nearest(seg)
            if target:
                warnings.append(f"{rel}: /api/{seg} -> /api/{target}")
                return f"{quote}/api/{target}"
            return m.group(0)

        return _FETCH_SEG.sub(repl, code), warnings

    def _nearest(self, seg: str):
        """Map a wrong segment to a real one (singular/plural/case variants)."""
        cand = {seg.lower(), route_name(seg), seg.rstrip("s").lower()}
        cand.add(route_name(seg.rstrip("s")))
        for c in cand:
            if c in self.valid:
                return c
        # Prefix match as a last resort (e.g. 'todo' -> 'todos')
        for v in self.valid:
            if v.startswith(seg.lower()) or seg.lower().startswith(v.rstrip("s")):
                return v
        return None
