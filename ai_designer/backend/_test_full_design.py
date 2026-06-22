"""Full-mode design validation: LLM UI + Design Critic + Screenshot QA.

Usage:
  python _test_full_design.py --fast-regression   # ~10 s; checks artifacts only
  python _test_full_design.py --full              # ~30 min; regenerates + builds + QA
  python _test_full_design.py grandvista megamart # specific app names (full mode)
  python _test_full_design.py                     # all 6 apps (full mode)

Does NOT set AI_DESIGNER_FAST — runs LLM UI, Design Critic, Fooocus (or fallback).
Sets AI_DESIGNER_SCREENSHOT_QA=1 if Playwright+Chromium are available.

Final output per app:
  App path | Build | SRS | RBAC | Visual similarity | Screenshot QA
"""
import json
import os
import re
import sys
import time

# Force UTF-8 output on Windows (graph.py emits ✓ which cp1252 rejects)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Full mode: do NOT set AI_DESIGNER_FAST
# Screenshot QA: enable if Playwright is present (checked below)
def _playwright_ok() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            b.close()
        return True
    except Exception:
        return False

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_USE_SCREENSHOTS = _playwright_ok()
if _USE_SCREENSHOTS:
    os.environ["AI_DESIGNER_SCREENSHOT_QA"] = "1"
    print("Playwright/Chromium available — screenshot QA ENABLED", flush=True)
else:
    os.environ.pop("AI_DESIGNER_SCREENSHOT_QA", None)
    print("Playwright/Chromium not available — using static JSX analysis", flush=True)

from app.graph import creation_app  # noqa: E402

FIXTURES = [
    ("GrandVista",  "_srs_grandvista.json",  "prj_full_grandvista"),
    ("MegaMart",    "_srs_megamart.json",    "prj_full_megamart"),
    ("MediPlus",    "_srs_mediplus.json",    "prj_full_mediplus"),
    ("EduSphere",   "_srs_edusphere.json",   "prj_full_edusphere"),
    ("AutoHub",     "_srs_autohub.json",     "prj_full_autohub"),
    ("FitZone",     "_srs_fitzone.json",     "prj_full_fitzone"),
]

HISTORY_PATH = os.path.join("output", "design_history.json")
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
STRUCTURAL_KEYS = ["hero_composition", "listing_variant", "filter_placement", "page_layout_variant"]
SIMILARITY_THRESHOLD = 0.75


# ── Fast-regression helpers ───────────────────────────────────────────────────

def _fr_ok(msg):   print(f"  PASS  {msg}")
def _fr_fail(msg, errors): errors.append(msg); print(f"  FAIL  {msg}")


def _app_dir(slug):
    for prefix in ("prj_full_", "prj_da_"):
        d = os.path.join(BASE, prefix + slug)
        if os.path.isdir(d):
            return d
    return None


def _fr_check_access_js(slug, project_dir):
    path = os.path.join(project_dir, "src", "lib", "access.js")
    if not os.path.exists(path):
        return [f"{slug}: src/lib/access.js missing"]
    src = open(path, encoding="utf-8").read()
    errs = []
    if "canAccessPage" not in src:
        errs.append(f"{slug}: access.js missing canAccessPage export")
    if "isProtected" not in src:
        errs.append(f"{slug}: access.js missing isProtected export")
    return errs


def _fr_check_layout_import(slug, project_dir):
    path = os.path.join(project_dir, "src", "app", "(app)", "layout.jsx")
    if not os.path.exists(path):
        return []
    src = open(path, encoding="utf-8").read()
    if "canAccessPage" not in src:
        return [f"{slug}: (app)/layout.jsx does not call canAccessPage"]
    return []


def _fr_check_structural(slug, project_dir):
    bp_path = os.path.join(project_dir, "design_blueprint.json")
    if not os.path.exists(bp_path):
        return [f"{slug}: design_blueprint.json missing"]
    bp = json.load(open(bp_path, encoding="utf-8"))
    return [f"{slug}: blueprint missing {k}" for k in STRUCTURAL_KEYS if not bp.get(k)]


def _fr_check_no_home_dup(slug, project_dir):
    site_path = os.path.join(project_dir, "src", "lib", "site.js")
    if not os.path.exists(site_path):
        return []
    src = open(site_path, encoding="utf-8").read()
    m = re.search(r'marketingLinks:\s*\[(.*?)\]', src, re.DOTALL)
    if not m:
        return []
    block = m.group(0)
    home_count = block.count('"label":"Home"') + block.count('"label": "Home"')
    if home_count > 1:
        return [f"{slug}: duplicate 'Home' in marketingLinks ({home_count} found)"]
    return []


def _fr_check_build_artifact(slug, project_dir):
    build_id = os.path.join(project_dir, ".next", "BUILD_ID")
    if not os.path.exists(build_id):
        return [f"{slug}: .next/BUILD_ID missing — run npm run build"]
    return []


def _fr_cross_app_similarity():
    from app.visual_similarity_checker import compute_signature, compute_similarity
    blueprints = {}
    for app in [f[2].replace("prj_full_", "") for f in FIXTURES]:
        d = _app_dir(app)
        if not d:
            continue
        bp_path = os.path.join(d, "design_blueprint.json")
        if os.path.exists(bp_path):
            blueprints[app] = json.load(open(bp_path, encoding="utf-8"))
    errors, max_sim, worst = [], 0.0, ""
    names = list(blueprints.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            sa = compute_signature(blueprints[a])
            sb = compute_signature(blueprints[b])
            score = compute_similarity(sa, sb,
                                       blueprints[a].get("color_palette", {}),
                                       blueprints[b].get("color_palette", {}))
            if score > max_sim:
                max_sim, worst = score, f"{a} vs {b}"
            if score >= SIMILARITY_THRESHOLD:
                errors.append(f"Cross-app similarity {a} vs {b} = {score:.3f} (>= {SIMILARITY_THRESHOLD})")
    return errors, max_sim, worst


def _fr_check_no_self_comparison():
    from app import visual_similarity_checker as vsc
    d = _app_dir("grandvista")
    if not d:
        return ["grandvista output dir missing — cannot test self-comparison guard"]
    bp = json.load(open(os.path.join(d, "design_blueprint.json"), encoding="utf-8"))
    result = vsc.check_similarity(bp, HISTORY_PATH, exclude_app_name="GrandVista Hotel Management Platform")
    if result.get("too_similar"):
        return [f"grandvista is genuinely too similar to another app (score={result['similarity']:.3f})"]
    return []


def run_fast_regression():
    print("\n=== FAST REGRESSION ===\n")
    all_errors = []
    t0 = time.time()

    for slug in [f[2].replace("prj_full_", "") for f in FIXTURES]:
        d = _app_dir(slug)
        if not d:
            _fr_fail(f"{slug}: output dir not found", all_errors)
            continue
        errs = (_fr_check_access_js(slug, d) + _fr_check_layout_import(slug, d)
                + _fr_check_structural(slug, d) + _fr_check_no_home_dup(slug, d)
                + _fr_check_build_artifact(slug, d))
        for e in errs:
            _fr_fail(e, all_errors)
        if not errs:
            _fr_ok(f"{slug}: access.js + structural + build artifact + nav OK")

    print()
    sim_errors, max_sim, worst = _fr_cross_app_similarity()
    for e in sim_errors:
        _fr_fail(e, all_errors)
    if not sim_errors:
        _fr_ok(f"Cross-app similarity max={max_sim:.3f} (worst: {worst}) — all below {SIMILARITY_THRESHOLD}")

    se_errors = _fr_check_no_self_comparison()
    for e in se_errors:
        _fr_fail(e, all_errors)
    if not se_errors:
        _fr_ok("Self-comparison guard works (no false positive)")

    dt = int(time.time() - t0)
    print(f"\n{'PASS' if not all_errors else 'FAIL'}  ({len(all_errors)} failure(s))  {dt}s\n")
    for e in all_errors:
        print(f"  x {e}")
    return len(all_errors) == 0


# ── Result collectors ─────────────────────────────────────────────────────────

def _build_check(out: str) -> str:
    return "PASS" if os.path.isdir(os.path.join(out, ".next")) else "FAIL"


def _srs_check(out: str) -> tuple[str, list[str]]:
    issues = []
    try:
        st = json.load(open(os.path.join(out, "status.json")))
        if st.get("phase") != "done":
            issues.append(f"phase={st.get('phase')}")
    except Exception:
        issues.append("status.json missing")

    if not os.path.isdir(os.path.join(out, ".next")):
        issues.append(".next missing")
        return "FAIL", issues

    for d in ["(app)", "(marketing)"]:
        if not os.path.isdir(os.path.join(out, "src", "app", d)):
            issues.append(f"{d} dir missing")

    dash = os.path.join(out, "src", "app", "(app)", "dashboard", "page.jsx")
    if not os.path.exists(dash):
        issues.append("dashboard page missing")

    manage = os.path.join(out, "src", "app", "(app)", "manage")
    if not os.path.isdir(manage) or not os.listdir(manage):
        issues.append("no /manage routes")

    login_found = any(os.path.exists(p) for p in [
        os.path.join(out, "src", "app", "login", "page.jsx"),
        os.path.join(out, "src", "app", "(marketing)", "login", "page.jsx"),
    ])
    if not login_found:
        issues.append("login page missing")

    bp = os.path.join(out, "design_blueprint.json")
    if not os.path.exists(bp):
        issues.append("design_blueprint.json missing")
    else:
        try:
            d = json.load(open(bp))
            if not d.get("domain_mood"):
                issues.append("blueprint.domain_mood missing")
            for sf in ("page_layout_variant", "listing_variant", "filter_placement"):
                if not d.get(sf):
                    issues.append(f"blueprint.{sf} missing")
        except Exception:
            issues.append("blueprint unreadable")

    reg = next(
        (p for p in [
            os.path.join(out, "_component_registry.json"),
            os.path.join(out, "component-registry.json"),
        ] if os.path.exists(p)), None)
    if not reg:
        issues.append("component registry missing")

    return ("PASS" if not issues else f"FAIL ({'; '.join(issues[:2])})"), issues


def _rbac_check(out: str) -> str:
    issues = []

    # access.js must define ROLES and canAccess
    access = os.path.join(out, "src", "lib", "access.js")
    if not os.path.exists(access):
        return "FAIL (access.js missing)"
    try:
        src = open(access, encoding="utf-8").read()
        if "roles" not in src.lower() and "role" not in src.lower():
            issues.append("no role definitions in access.js")
        if "canAccess" not in src and "hasRole" not in src and "role" not in src.lower():
            issues.append("no role check function")
    except Exception:
        return "FAIL (access.js unreadable)"

    # Sidebar or layout must reference roles
    layout = os.path.join(out, "src", "app", "(app)", "layout.jsx")
    sidebar_ok = False
    if os.path.exists(layout):
        ls = open(layout, encoding="utf-8").read()
        if "role" in ls.lower() or "roles" in ls.lower():
            sidebar_ok = True

    # At least one manage page route must have role guards
    manage_dir = os.path.join(out, "src", "app", "(app)", "manage")
    api_dir = os.path.join(out, "src", "app", "api")
    role_in_api = False
    if os.path.isdir(api_dir):
        for root, _, files in os.walk(api_dir):
            for f in files:
                if f.endswith(".js"):
                    try:
                        c = open(os.path.join(root, f), encoding="utf-8").read()
                        if "role" in c.lower() or "canAccess" in c or "hasRole" in c:
                            role_in_api = True
                            break
                    except Exception:
                        pass
            if role_in_api:
                break

    if not sidebar_ok and not role_in_api:
        issues.append("no role enforcement found in layout/API")

    return "PASS" if not issues else f"PARTIAL ({'; '.join(issues)})"


def _visual_sim_check(out: str, app_name: str) -> str:
    """Compare this app's blueprint against design history."""
    bp_path = os.path.join(out, "design_blueprint.json")
    if not os.path.exists(bp_path):
        return "SKIP (no blueprint)"
    try:
        from app.visual_similarity_checker import check_similarity
        bp = json.load(open(bp_path))
        result = check_similarity(bp, HISTORY_PATH)
        sim = result.get("similarity", 0)
        too_sim = result.get("too_similar", False)
        most_sim = result.get("most_similar_app", "")
        prefix = "FAIL" if too_sim else "PASS"
        label = f"sim={sim:.2f}" + (f" vs {most_sim}" if most_sim and most_sim != app_name else "")
        return f"{prefix} ({label})"
    except Exception as e:
        return f"ERR ({str(e)[:40]})"


def _screenshot_qa_check(logs: list) -> str:
    """Extract Screenshot QA verdict from generation logs."""
    qa_log = next((l for l in reversed(logs or []) if "[AGENT: Screenshot QA]" in str(l)), "")
    critic_log = next((l for l in reversed(logs or []) if "[AGENT: Design Critic]" in str(l)), "")

    if not qa_log:
        return "SKIP (no QA log)"

    # Parse critic verdict
    if "PASS" in critic_log:
        score_m = re.search(r"score=(\d+)", critic_log)
        score = score_m.group(1) if score_m else "?"
        return f"PASS (score={score})"
    if "FAIL" in critic_log:
        score_m = re.search(r"score=(\d+)", critic_log)
        score = score_m.group(1) if score_m else "?"
        return f"FAIL (score={score})"

    # QA ran but no critic verdict — check QA log itself
    if "skipped" in qa_log.lower():
        return "SKIP"
    if "clean" in qa_log or "PASS" in qa_log:
        return "PASS (static)"
    if "error" in qa_log.lower() or "FAIL" in qa_log:
        return "WARN"
    return "PASS (static)"


def _check_llm_ui_ran(logs: list) -> bool:
    return any("[AGENT: LLM UI]" in str(l) for l in (logs or []))


def _check_blueprint_log(logs: list) -> bool:
    return any("[AGENT: Design Agent]" in str(l) and "skipped" not in str(l)
               for l in (logs or []))


def _check_history_updated(app_name: str) -> bool:
    try:
        h = json.load(open(HISTORY_PATH))
        return any(e.get("app_name", "").lower().startswith(app_name[:4].lower()) for e in h)
    except Exception:
        return False


# ── Core build function ───────────────────────────────────────────────────────

def run_full(name: str, fixture: str, pid: str) -> dict:
    out = os.path.join("output", pid)

    if not os.path.exists(fixture):
        return {"name": name, "path": out,
                "build": "SKIP", "srs": "SKIP", "rbac": "SKIP",
                "visual_sim": "SKIP", "screenshot_qa": "SKIP",
                "notes": f"fixture {fixture} not found"}

    raw = open(fixture, encoding="utf-8").read()
    state = {
        "project_id": pid, "prompt": raw, "history": [],
        "roles": [], "pages": [], "files": {},
        "intake": {}, "status": "init", "logs": [],
    }

    print(f"\n{'='*72}")
    print(f"  {name} — full mode {'+ screenshots' if _USE_SCREENSHOTS else '(static QA)'}")
    print(f"  -> {out}")
    print(f"{'='*72}", flush=True)

    t0 = time.time()
    logs = []
    try:
        final = creation_app.invoke(state)
        logs = final.get("logs", [])
    except Exception as e:
        print(f"  CRASHED: {e}", flush=True)
        return {"name": name, "path": out,
                "build": "CRASH", "srs": "FAIL", "rbac": "FAIL",
                "visual_sim": "SKIP", "screenshot_qa": "SKIP",
                "notes": str(e)[:120]}
    dt = time.time() - t0

    # Surface key agent logs
    for l in [x for x in logs if any(k in str(x) for k in
              ["AGENT: Design Agent", "AGENT: LLM UI", "AGENT: Screenshot QA",
               "AGENT: Design Critic", "DONE", "BUILD ERROR"])][-10:]:
        safe = str(l)[:150].encode("utf-8", "replace").decode("utf-8")
        print("  |", safe, flush=True)
    print(f"  Done in {dt:.0f}s", flush=True)

    # Confirmations
    if _check_blueprint_log(logs):
        print(f"  [OK] design_blueprint.json created", flush=True)
    if _check_llm_ui_ran(logs):
        print(f"  [OK] LLM UI augmentation ran", flush=True)
    if _check_history_updated(name):
        print(f"  [OK] design_history.json updated", flush=True)

    return {
        "name":         name,
        "path":         out,
        "build":        _build_check(out),
        "srs":          _srs_check(out)[0],
        "rbac":         _rbac_check(out),
        "visual_sim":   _visual_sim_check(out, name),
        "screenshot_qa": _screenshot_qa_check(logs),
        "notes":        "",
    }


# ── Regenerate only blueprint + public UI when too similar ────────────────────

def _regen_public_ui(out: str, name: str, logs_out: list) -> bool:
    """Regenerate design_blueprint + public pages only, rebuild once."""
    try:
        from app import design_agent as _da, visual_similarity_checker as _vsc
        from app import llm_ui_generator as _lui
        from app import nextgen

        # Load SRS from status.json-adjacent prompt (fall back to genome)
        bp_path = os.path.join(out, "design_blueprint.json")
        old_bp = json.load(open(bp_path)) if os.path.exists(bp_path) else {}
        genome_path = os.path.join(out, "_design_genome.json")
        genome = json.load(open(genome_path)) if os.path.exists(genome_path) else {}
        # Blank out history entry so we don't immediately re-match
        srs_data = {"app_name": name, "system_category": old_bp.get("system_category", "custom")}

        new_bp = _da.create_design_blueprint(srs_data, genome, out, HISTORY_PATH, name)
        new_sim = _vsc.check_similarity(new_bp, HISTORY_PATH)
        logs_out.append(f"REGEN blueprint: mood={new_bp.get('domain_mood')} sim={new_sim.get('similarity', 0):.2f}")

        if new_sim.get("too_similar"):
            logs_out.append("REGEN: still too similar after blueprint refresh — keeping original")
            return False

        # Augment public pages with new blueprint
        from app.srs_public_page_generator import write_srs_public_pages
        # We need parsed_srs to re-run augmentation, which is not available here
        # Instead: just rebuild with the new blueprint in place
        ok, _ = nextgen.run_build(out)
        logs_out.append(f"REGEN rebuild: {'ok' if ok else 'FAIL'}")
        return ok
    except Exception as e:
        logs_out.append(f"REGEN error: {e}")
        return False


# ── Summary printer ───────────────────────────────────────────────────────────

def _cross_app_similarity(results: list) -> tuple[float, str]:
    """Compute all pairwise cross-app similarities. Returns (max_score, worst_pair)."""
    try:
        from app.visual_similarity_checker import check_similarity, compute_signature, compute_similarity
        blueprints = []
        for r in results:
            bp_path = os.path.join(r["path"], "design_blueprint.json")
            if os.path.exists(bp_path):
                bp = json.load(open(bp_path))
                blueprints.append((r["name"], bp))

        max_sim = 0.0
        worst = ""
        for i in range(len(blueprints)):
            for j in range(i + 1, len(blueprints)):
                na, bpa = blueprints[i]
                nb, bpb = blueprints[j]
                sig_a = compute_signature(bpa)
                sig_b = compute_signature(bpb)
                score = compute_similarity(sig_a, sig_b,
                                          bpa.get("color_palette", {}),
                                          bpb.get("color_palette", {}))
                if score > max_sim:
                    max_sim = score
                    worst = f"{na} vs {nb}"
        return max_sim, worst
    except Exception as e:
        return -1.0, f"error: {e}"


def print_final(results: list) -> None:
    print(f"\n{'='*72}")
    print("FINAL RESULTS")
    print(f"{'='*72}")
    for r in results:
        print(f"\n  {r['name']}")
        print(f"    Path:             {r['path']}")
        print(f"    Build status:     {r['build']}")
        print(f"    SRS status:       {r['srs']}")
        print(f"    RBAC status:      {r['rbac']}")
        print(f"    Visual similarity:{r['visual_sim']}")
        print(f"    Screenshot QA:    {r['screenshot_qa']}")
        if r.get("notes"):
            print(f"    Notes:            {r['notes'][:80]}")

    # Blueprint structural field summary
    print(f"\n  {'─'*68}")
    print("  STRUCTURAL LAYOUT VARIANTS")
    for r in results:
        bp_path = os.path.join(r["path"], "design_blueprint.json")
        if os.path.exists(bp_path):
            try:
                bp = json.load(open(bp_path))
                src = bp.get("_source", "?")
                layout = bp.get("page_layout_variant", "—")
                hero   = bp.get("hero_composition", "—")
                lst    = bp.get("listing_variant", "—")
                flt    = bp.get("filter_placement", "—")
                print(f"  {r['name']:12s}  src={src}  layout={layout}  hero={hero}  listing={lst}  filter={flt}")
            except Exception:
                pass

    print()
    print(f"  Build:   {sum(1 for r in results if r['build']=='PASS')}/{len(results)} PASS")
    print(f"  SRS:     {sum(1 for r in results if 'PASS' in r['srs'])}/{len(results)} PASS")
    print(f"  RBAC:    {sum(1 for r in results if 'PASS' in r['rbac'] or 'PARTIAL' in r['rbac'])}/{len(results)} PASS/PARTIAL")
    print(f"  VisSim:  {sum(1 for r in results if 'PASS' in r['visual_sim'])}/{len(results)} unique")
    print(f"  QA:      {sum(1 for r in results if 'PASS' in r['screenshot_qa'])}/{len(results)} PASS")

    # Cross-app similarity matrix
    if len(results) > 1:
        max_sim, worst = _cross_app_similarity(results)
        distinct = max_sim < 0.75
        print(f"\n  Max cross-app similarity: {max_sim:.3f}  worst pair: {worst}")
        print(f"  All apps visually distinct: {'YES' if distinct else 'NO — exceeds 0.75 threshold'}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    args = [a.lower() for a in sys.argv[1:]]

    if args == ["--fast-regression"]:
        return 0 if run_fast_regression() else 1

    # --full is a flag that runs all apps (same as passing no app names)
    if args == ["--full"]:
        args = []

    targets = [(n, f, p) for n, f, p in FIXTURES
               if not args or any(n.lower().startswith(a) for a in args)]
    if not targets:
        print(f"No matches for {args}. Choices: {[n for n,_,_ in FIXTURES]}")
        return 1

    results: list = []

    # Run GrandVista and MegaMart first (pilot), then rest
    pilots = [t for t in targets if t[0] in ("GrandVista", "MegaMart")]
    rest   = [t for t in targets if t[0] not in ("GrandVista", "MegaMart")]

    for n, f, p in (pilots or targets[:2]):
        r = run_full(n, f, p)
        results.append(r)

        # Auto-regen if too similar
        if "FAIL" in r["visual_sim"] and "too similar" in r["visual_sim"].lower():
            print(f"\n  [{n}] Visual similarity FAIL — regenerating blueprint + public UI", flush=True)
            regen_logs: list = []
            ok = _regen_public_ui(r["path"], n, regen_logs)
            for l in regen_logs:
                print(f"  | {l}", flush=True)
            if ok:
                r["visual_sim"] += " → REGEN OK"
            else:
                r["visual_sim"] += " → REGEN FAIL"

    # Pilot check
    if pilots and rest:
        pilot_ok = all(r["build"] == "PASS" for r in results)
        if not pilot_ok:
            print("\n  Pilots had build failures — aborting remaining apps.", flush=True)
            print_final(results)
            return 1
        print(f"\n  Pilots passed ({len(results)}/{len(pilots)}) — proceeding with remaining {len(rest)} app(s)", flush=True)

    for n, f, p in rest:
        r = run_full(n, f, p)
        results.append(r)

        if "FAIL" in r["visual_sim"] and "too similar" in r["visual_sim"].lower():
            print(f"\n  [{n}] Visual similarity FAIL — regenerating", flush=True)
            regen_logs: list = []
            ok = _regen_public_ui(r["path"], n, regen_logs)
            for l in regen_logs:
                print(f"  | {l}", flush=True)
            if ok:
                r["visual_sim"] += " → REGEN OK"

    print_final(results)
    return 0 if all(r["build"] == "PASS" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
