"""agents/design/visual_review.py — deterministic visual/layout review (P4).

The spec's rule "LLM visual recommendations must still pass DETERMINISTIC browser checks" means the
authority is a set of deterministic checks, not a model's opinion. This module runs those checks
statically on the generated page/component source (no browser needed) to catch the layout defects that
most often survive generation:

  - a raw `<table>` (not the overflow-wrapped `<Table>` primitive) with no horizontal-scroll wrapper
    → horizontal overflow on mobile;
  - a page body with no responsive width container (`max-w-*` / `container` / `min-h-*`);
  - an interactive archetype (form / pos / receipt) with no primary action control;
  - a landing page missing its nav or its >=4 sections.

A full Playwright screenshot pass at mobile/tablet/laptop/desktop widths is the live counterpart; these
static checks are its fast, always-available floor and gate the same defects pre-render.
"""
from __future__ import annotations

import re
from pathlib import Path

_SKIP = {"node_modules", ".next", ".locode"}


def review_text(rel: str, text: str, archetype: str = "") -> list[dict]:
    f: list[dict] = []

    def add(rule, detail):
        f.append({"file": rel, "rule": rule, "detail": detail})

    # 1. raw wide table without a horizontal-scroll wrapper (the <Table> primitive already wraps).
    if re.search(r"<table[\s>]", text) and "overflow" not in text:
        add("table-overflow", "raw <table> without an overflow-x wrapper — use the <Table> primitive or wrap in overflow-x-auto")

    # 2. responsive width container present?
    if re.search(r"export default function", text) and not re.search(r"max-w-|container|min-h-|w-full", text):
        add("no-responsive-container", "no max-w-* / container / min-h-* — content may overflow or stretch")

    # 3. interactive archetypes need a primary action control.
    if archetype in ("form", "pos", "receipt"):
        if not re.search(r"<button|<Button|type=[\"']submit[\"']|onSubmit", text):
            add("no-primary-action", f"{archetype} page has no button/submit — the primary action is missing")

    # 4. landing needs a nav + several sections.
    if archetype == "landing":
        if "<nav" not in text and "<Nav" not in text:
            add("landing-no-nav", "landing page has no <nav> (brand + Login/Sign up)")
        if len(re.findall(r"<section", text)) < 4:
            add("landing-thin", "landing page has fewer than 4 <section> bands")

    return f


def review_project(project_dir, design: dict | None = None) -> dict:
    """{rel: [findings]} across page bodies. `design['by_path']` supplies each page's archetype."""
    project_dir = Path(project_dir)
    by_path = (design or {}).get("by_path", {})
    # map component file -> archetype via the design plan's page paths (best-effort by component name)
    arch_by_component = {}
    for path, dc in by_path.items():
        segs = [s for s in str(path).strip("/").split("/") if s and not s.startswith("[")]
        comp = ("".join(s.title().replace("-", "") for s in segs) or "Home") + "Page"
        arch_by_component[comp] = dc.get("archetype", "")
    report: dict[str, list[dict]] = {}
    pages_dir = project_dir / "components" / "pages"
    if pages_dir.exists():
        for fp in pages_dir.glob("*.tsx"):
            try:
                text = fp.read_text(encoding="utf-8")
            except Exception:
                continue
            arch = arch_by_component.get(fp.stem, "")
            found = review_text(fp.name, text, arch)
            if found:
                report[f"components/pages/{fp.name}"] = found
    return report
