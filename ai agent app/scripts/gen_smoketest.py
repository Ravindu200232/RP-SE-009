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
import os
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
from agents.architect import validate_spec                 # noqa: E402
from agents.product_context import context_hash            # noqa: E402
from agents.refiner import RefinerAgent                    # noqa: E402

PROD_DIR = BASE_DIR / "production-ready"
LOGS_DIR = BASE_DIR / "logs"
GENERIC_ENTITIES = {"entry", "item", "record", "data", "thing", "element", "calculation", "object"}


# Counted from the analyzer's own log lines — the claim of this whole design is that the generator,
# not the repair harness, is what makes an app build, so it has to be measured per run.
COUNTS = {"clean_first_try": 0, "micro_repairs": 0, "preflight_failures": 0,
          "truncations": 0, "final_build_invocations": 0}


def _emit(ev, payload=None):
    """Minimal stdout progress sink (mirrors the orchestrator event contract)."""
    payload = payload or {}
    if ev == "phase":
        print(f"  > phase: {payload.get('name','')}", flush=True)
    elif ev == "log":
        text = payload.get("text", "")
        if text.startswith("preflight: ") and text.endswith("clean on raw candidate"):
            COUNTS["clean_first_try"] += 1
        elif text.startswith("preflight: ") and "clean after" in text:
            COUNTS["micro_repairs"] += 1
        elif "preflight NOT clean" in text:
            COUNTS["preflight_failures"] += 1
        if "no corresponding closing tag" in text:
            COUNTS["truncations"] += 1
        if text.startswith("next build "):
            COUNTS["final_build_invocations"] += 1
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


def _cached_valid_spec(idea: str) -> tuple[dict, Path] | None:
    """Reuse only an exact-input, hash-valid Nemotron plan from an unpublished staging build."""
    if os.environ.get("LOCODE_SMOKE_REPLAN") == "1":
        return None
    candidates = sorted(
        PROD_DIR.glob(".*.smoke-staging/.locode/product-context.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (value.get("version") != "product-context/v1" or value.get("rawInput") != idea or
                value.get("contextHash") != context_hash(value)):
            continue
        spec = value.get("normalizedSpec")
        if isinstance(spec, dict) and not validate_spec(spec):
            return spec, path
    return None


def run(slug: str, idea: str) -> dict:
    for key in COUNTS:
        COUNTS[key] = 0
    model = llm.GEN_MODEL
    architect_model = llm.ARCHITECT_MODEL
    llm.log_config(model)
    print(f"== {slug} == planning with {architect_model}; generating with {model} "
          f"@ num_ctx={llm.BASE_OPTS['num_ctx']}", flush=True)
    t0 = time.time()

    runtime = llm.runtime_profile(prewarm=True)
    print(f"  runtime: {runtime['quantization']} {runtime['context']} {runtime['processor']}", flush=True)
    cached = _cached_valid_spec(idea)
    if cached:
        spec, cached_path = cached
        print(f"  planner: reused validated Nemotron product-context/v1 from "
              f"{cached_path.parent.parent.parent.name}", flush=True)
    else:
        cloud = llm.cloud_profile(prewarm=True)
        print(f"  planner: {cloud['model']} {cloud['context']} {cloud['processor']}", flush=True)
        refined = RefinerAgent(None, architect_model).refine(idea)
        try:
            spec = json.loads(refined)
        except Exception as e:
            return {"slug": slug, "error": f"refine-failed: {e}"}
    spec["build_model"] = model

    pname = re.sub(r"[^a-z0-9]", "", str(spec.get("project_name", "")).replace("-", ""))[:24] or slug
    target_dir = PROD_DIR / pname
    proj_dir = PROD_DIR / f".{pname}.smoke-staging"
    proj_dir.mkdir(parents=True, exist_ok=True)
    resume_context_hash = None
    resume_sources: dict[str, bytes] = {}
    if cached:
        try:
            cached_context = json.loads(cached_path.read_text(encoding="utf-8"))
            resume_context_hash = str(cached_context.get("contextHash") or "") or None
            cached_root = cached_path.parent.parent
            for source in cached_root.glob("components/features/**/*.tsx"):
                resume_sources[source.relative_to(cached_root).as_posix()] = source.read_bytes()
        except (OSError, json.JSONDecodeError, ValueError):
            resume_context_hash, resume_sources = None, {}
    import shutil
    for child in list(proj_dir.iterdir()):
        if child.name in ("node_modules", "package-lock.json"):
            continue
        shutil.rmtree(child) if child.is_dir() else child.unlink()
    for rel, source in resume_sources.items():
        destination = proj_dir / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source)
    if resume_sources:
        print(f"  resume: restored {len(resume_sources)} staged feature file(s); each must pass "
              "current preflight before reuse", flush=True)

    result = orchestrator.generate_app(spec, proj_dir, _emit, install=True, fix=True,
                                       fix_iters=1, runtime_checked=True,
                                       resume_context_hash=resume_context_hash)
    if result.get("built"):
        from agents.publish import publish_stage
        backup = PROD_DIR / f".{pname}.smoke-backup"
        proj_dir, residual_stage = publish_stage(proj_dir, target_dir, backup)
        if residual_stage:
            print("  publish: green target complete; an empty locked staging shell remains", flush=True)

    loc = proj_dir / ".locode"
    context_path = loc / "product-context.json"
    try:
        product_context = json.loads(context_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        product_context = {}
    dup = _dup_write_counts(loc / "PROGRESS.md")
    over2 = {p: n for p, n in dup.items() if n > 2}
    ents = _entities(loc)
    generic = [e for e in ents if e.lower() in GENERIC_ENTITIES]
    report = {
        "slug": slug,
        "idea": idea,
        "project": pname,
        "app_kind": spec.get("app_kind"),
        "auth": spec.get("auth"),
        "roles": [r.get("name") for r in spec.get("roles", [])],
        "page_manifest": [
            {
                "path": page.get("path"),
                "title": page.get("title"),
                "kind": page.get("kind"),
                "access": page.get("access"),
                "archetype": page.get("archetype"),
                "layout": page.get("layout"),
                "functions": page.get("functions"),
            }
            for page in spec.get("pages", []) if isinstance(page, dict)
        ],
        "design_fingerprint": {
            "preset": (spec.get("design") or {}).get("preset"),
            "mode": (spec.get("design") or {}).get("mode"),
            "navStyle": (spec.get("design") or {}).get("navStyle"),
            "visualSignature": (spec.get("design") or {}).get("visualSignature"),
            "palette": (spec.get("design") or {}).get("palette"),
            "typography": (spec.get("design") or {}).get("typography"),
        },
        "context_hash": product_context.get("contextHash"),
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
        "metrics": result.get("metrics"),
        "elapsed_sec": round(time.time() - t0, 1),
    }
    LOGS_DIR.mkdir(exist_ok=True)
    (LOGS_DIR / f"smoketest-{slug}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n==== REPORT:", slug, "====", flush=True)
    print(json.dumps({k: report[k] for k in
                      ("project", "app_kind", "auth", "page_manifest", "design_fingerprint",
                       "context_hash", "counts", "built", "entities", "generic_entities",
                       "components_tracked", "locations_md_present", "max_writes_per_file",
                       "files_written_over_2x", "missing", "generator", "metrics",
                       "elapsed_sec")}, indent=2), flush=True)
    return report


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: python scripts/gen_smoketest.py <slug> \"<idea>\"")
        sys.exit(2)
    # Windows Start-Process may split an unquoted idea into multiple argv entries.
    # Rejoin all remaining words so the Architect always receives the lossless input.
    run(sys.argv[1], " ".join(sys.argv[2:]))
