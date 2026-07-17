#!/usr/bin/env python3
"""scripts/gen_smoketest.py — headless generate-and-measure harness for the test-and-tighten loop.

Generates ONE app from a free-text idea through the exact v2 pipeline server.py uses
(refiner -> orchestrator.generate_app), but WITHOUT starting the dev server, then writes a
report so we can see, per app:

  - did `next build` reach green?
  - was any file written more than twice? (the 'same file generated repeatedly' regression)
  - are the entities domain-specific, or generic Entry/Item/Calculation?
  - is COMPONENTS.md populated, and is .locode/LOCATIONS.md present?
  - how many planned files were still missing?

Usage:
    python scripts/gen_smoketest.py <slug> "<idea text>"

Writes logs/smoketest-<slug>.json and prints a one-screen summary.
"""
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# The orchestrator logs contain arrows/emoji; Windows stdout defaults to cp1252 and would crash on
# them. Force UTF-8 so the harness never dies on a log line.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from agents import llm, orchestrator                       # noqa: E402
from agents.refiner import RefinerAgent                    # noqa: E402

PROD_DIR = BASE_DIR / "production-ready"
LOGS_DIR = BASE_DIR / "logs"
GENERIC_ENTITIES = {"entry", "item", "record", "data", "thing", "element", "calculation", "object"}


# Counted from the analyzer's own log lines — the claim of this whole design is that the generator,
# not the repair harness, is what makes an app build, so it has to be measured per run.
COUNTS = {"clean_first_try": 0, "analyzer_retries": 0, "gave_up": 0, "truncations": 0,
          "build_fix_passes": 0}


def _emit(ev, payload=None):
    """Minimal stdout progress sink (mirrors the orchestrator event contract)."""
    payload = payload or {}
    if ev == "phase":
        print(f"  > phase: {payload.get('name','')}", flush=True)
    elif ev == "log":
        text = payload.get("text", "")
        if text.startswith("analyzer: ") and text.endswith("clean"):
            COUNTS["clean_first_try"] += 1          # "clean" with no "(after N regeneration(s))"
        elif "diagnostic(s), regenerating" in text:
            COUNTS["analyzer_retries"] += 1
        elif "still has" in text and "regeneration(s)" in text:
            COUNTS["gave_up"] += 1
        if "no corresponding closing tag" in text:
            COUNTS["truncations"] += 1
        if text.startswith("build-fix pass"):
            COUNTS["build_fix_passes"] += 1
        print(f"    {text}", flush=True)
    elif ev == "done":
        print(f"  > done ok={payload.get('ok')}", flush=True)
    # token/start/end/file are intentionally dropped to keep the log readable


def _dup_write_counts(progress_md: Path) -> dict:
    """Parse PROGRESS.md ('- <agent>: wrote <path> (<n>B)') → {path: times_written}."""
    counts: Counter = Counter()
    if not progress_md.exists():
        return {}
    for line in progress_md.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.search(r"wrote\s+(\S+)\s+\(", line)
        if m:
            counts[m.group(1)] += 1
    return dict(counts)


def _entities(loc: Path) -> list[str]:
    ents = []
    f = loc / "ENTITIES.md"
    if f.exists():
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.search(r"\*\*(.+?)\*\*", line)
            if m:
                ents.append(m.group(1))
    return ents


def _components_count(loc: Path) -> int:
    f = loc / "COMPONENTS.md"
    if not f.exists():
        return 0
    txt = f.read_text(encoding="utf-8", errors="replace")
    seg = txt.split("## Produced during this build", 1)[-1]
    return len([l for l in seg.splitlines() if l.strip().startswith("- `")])


def run(slug: str, idea: str) -> dict:
    model = llm.GEN_MODEL
    llm.log_config(model)
    print(f"== {slug} == generating with {model} @ num_ctx={llm.BASE_OPTS['num_ctx']}", flush=True)
    t0 = time.time()

    refined = RefinerAgent(None, model).refine(idea)
    try:
        spec = json.loads(refined)
    except Exception as e:
        return {"slug": slug, "error": f"refine-failed: {e}"}
    spec["build_model"] = model

    pname = re.sub(r"[^a-z0-9]", "", str(spec.get("project_name", "")).replace("-", ""))[:24] or slug
    proj_dir = PROD_DIR / pname
    if proj_dir.exists():
        import shutil
        for c in list(proj_dir.iterdir()):
            if c.name in ("node_modules", "package-lock.json"):
                continue
            try:
                shutil.rmtree(c) if c.is_dir() else c.unlink()
            except Exception:
                pass
    proj_dir.mkdir(parents=True, exist_ok=True)

    result = orchestrator.generate_app(spec, proj_dir, _emit, install=True, fix=True, fix_iters=3)

    loc = proj_dir / ".locode"
    dup = _dup_write_counts(loc / "PROGRESS.md")
    over2 = {p: n for p, n in dup.items() if n > 2}
    ents = _entities(loc)
    generic = [e for e in ents if e.lower() in GENERIC_ENTITIES]
    report = {
        "slug": slug,
        "idea": idea,
        "project": pname,
        "app_kind": spec.get("app_kind"),
        "roles": [r.get("name") for r in spec.get("roles", [])],
        "counts": {"models": result.get("models"), "pages": result.get("pages"),
                   "planned": result.get("planned")},
        "built": result.get("built"),
        "missing": result.get("missing"),
        "entities": ents,
        "generic_entities": generic,
        "components_tracked": _components_count(loc),
        "locations_md_present": (loc / "LOCATIONS.md").exists(),
        "max_writes_per_file": max(dup.values()) if dup else 0,
        "files_written_over_2x": over2,
        # Did the GENERATOR get it right, or did the harness rescue it? `build_fix_passes: 0` is the
        # bar — it means the repair loop had nothing to do.
        "generator": dict(COUNTS),
        "exemplars": sorted(p.stem for p in (loc / "exemplars").glob("*.tsx")),
        "elapsed_sec": round(time.time() - t0, 1),
    }
    LOGS_DIR.mkdir(exist_ok=True)
    (LOGS_DIR / f"smoketest-{slug}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n==== REPORT:", slug, "====", flush=True)
    print(json.dumps({k: report[k] for k in
                      ("project", "app_kind", "counts", "built", "entities", "generic_entities",
                       "components_tracked", "locations_md_present", "max_writes_per_file",
                       "files_written_over_2x", "missing", "generator", "exemplars",
                       "elapsed_sec")}, indent=2), flush=True)
    return report


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: python scripts/gen_smoketest.py <slug> \"<idea>\"")
        sys.exit(2)
    run(sys.argv[1], sys.argv[2])
