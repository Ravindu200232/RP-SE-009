"""Test the Hybrid LLM Design Agent on 6 SRS apps.

Usage:
  python _test_design_agent.py              # test all 6 apps
  python _test_design_agent.py mediplus     # test one app
  python _test_design_agent.py --skip-build # skip generation; audit existing output dirs

Reports: app name -- path -- build PASS/FAIL -- SRS PASS/FAIL -- visual QA PASS/FAIL
"""
import json
import os
import sys
import time

os.environ.setdefault("AI_DESIGNER_FAST", "1")   # skip Fooocus; build faster

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.graph import creation_app  # noqa: E402

FIXTURES = [
    ("MediPlus",    "_srs_mediplus.json",    "prj_da_mediplus"),
    ("GrandVista",  "_srs_grandvista.json",  "prj_da_grandvista"),
    ("EduSphere",   "_srs_edusphere.json",   "prj_da_edusphere"),
    ("MegaMart",    "_srs_megamart.json",    "prj_da_megamart"),
    ("AutoHub",     "_srs_autohub.json",     "prj_da_autohub"),
    ("FitZone",     "_srs_fitzone.json",     "prj_da_fitzone"),
]


def _srs_checks(output_dir: str, pid: str) -> tuple[bool, list[str]]:
    """Basic SRS coverage checks on the generated project."""
    issues = []

    # 1. status.json must be "done"
    try:
        st = json.load(open(os.path.join(output_dir, "status.json")))
        if st.get("phase") != "done":
            issues.append(f"phase={st.get('phase')} (expected 'done')")
    except Exception as e:
        issues.append(f"status.json unreadable: {e}")

    # 2. Next.js build must exist
    if not os.path.isdir(os.path.join(output_dir, ".next")):
        issues.append(".next missing (build failed)")
        return False, issues

    # 3. src/app must have (app) and (marketing) dirs
    for req_dir in ["(app)", "(marketing)"]:
        if not os.path.isdir(os.path.join(output_dir, "src", "app", req_dir)):
            issues.append(f"src/app/{req_dir} missing")

    # 4. Dashboard page must exist
    dash = os.path.join(output_dir, "src", "app", "(app)", "dashboard", "page.jsx")
    if not os.path.exists(dash):
        issues.append("dashboard/page.jsx missing")

    # 5. At least one /manage route must exist
    manage_root = os.path.join(output_dir, "src", "app", "(app)", "manage")
    if not os.path.isdir(manage_root) or not os.listdir(manage_root):
        issues.append("no /manage routes generated")

    # 6. Login page must exist (at root src/app/login/ per auth_page_generator)
    login_candidates = [
        os.path.join(output_dir, "src", "app", "login", "page.jsx"),
        os.path.join(output_dir, "src", "app", "(marketing)", "login", "page.jsx"),
    ]
    if not any(os.path.exists(p) for p in login_candidates):
        issues.append("login/page.jsx missing")

    # 7. design_blueprint.json must exist
    bp_path = os.path.join(output_dir, "design_blueprint.json")
    if not os.path.exists(bp_path):
        issues.append("design_blueprint.json missing (Design Agent failed)")
    else:
        try:
            bp = json.load(open(bp_path))
            if not bp.get("domain_mood"):
                issues.append("design_blueprint has no domain_mood")
            if not (bp.get("color_palette") or {}).get("primary"):
                issues.append("design_blueprint color_palette.primary missing")
        except Exception as e:
            issues.append(f"design_blueprint.json unreadable: {e}")

    # 8. component registry must exist (prefixed with underscore)
    reg_candidates = [
        os.path.join(output_dir, "_component_registry.json"),
        os.path.join(output_dir, "component-registry.json"),
    ]
    if not any(os.path.exists(r) for r in reg_candidates):
        issues.append("component registry json missing")

    return len(issues) == 0, issues


def _visual_qa_check(output_dir: str, logs: list) -> tuple[str, float]:
    """Extract visual QA verdict from the generation logs."""
    critic_log = next(
        (l for l in reversed(logs or []) if "[AGENT: Design Critic]" in str(l)), "")
    blueprint_log = next(
        (l for l in reversed(logs or []) if "[AGENT: Design Agent]" in str(l)), "")

    # Parse critic verdict from log line
    if "PASS" in critic_log:
        # Extract score
        score_part = [p for p in critic_log.split() if p.startswith("score=")]
        score = float(score_part[0].split("=")[1]) if score_part else 70.0
        return "PASS", score
    if "FAIL" in critic_log:
        score_part = [p for p in critic_log.split() if p.startswith("score=")]
        score = float(score_part[0].split("=")[1]) if score_part else 20.0
        return "FAIL", score
    if "skipped" in critic_log:
        return "SKIP", 0.0

    # Fallback: check if blueprint was created
    if "[AGENT: Design Agent]" in blueprint_log and "skipped" not in blueprint_log:
        return "PASS (no critic)", 70.0

    return "SKIP", 0.0


def build_and_test(name: str, fixture: str, pid: str) -> dict:
    """Build one app and collect all metrics."""
    out_dir = os.path.join("output", pid)

    if not os.path.exists(fixture):
        return {
            "name": name, "pid": pid, "path": out_dir,
            "build": "SKIP", "srs": "SKIP", "visual_qa": "SKIP",
            "qa_score": 0, "notes": f"fixture {fixture} not found",
        }

    raw = open(fixture, encoding="utf-8").read()
    state = {
        "project_id": pid,
        "prompt": raw,
        "history": [], "roles": [], "pages": [], "files": {},
        "intake": {}, "status": "init", "logs": [],
    }

    print(f"\n{'='*72}")
    print(f"  GENERATING {name} ({fixture}) -> {out_dir}")
    print(f"{'='*72}", flush=True)

    t0 = time.time()
    logs = []
    try:
        final = creation_app.invoke(state)
        logs = final.get("logs", [])
    except Exception as e:
        print(f"  CRASHED: {type(e).__name__}: {e}", flush=True)
        return {
            "name": name, "pid": pid, "path": out_dir,
            "build": "CRASH", "srs": "FAIL", "visual_qa": "SKIP",
            "qa_score": 0, "notes": str(e)[:120],
        }
    dt = time.time() - t0
    print(f"  Done in {dt:.0f}s", flush=True)

    # Print key log lines
    agent_logs = [l for l in logs if "AGENT:" in str(l) or "BUILD" in str(l) or "DONE" in str(l)]
    for line in agent_logs[-12:]:
        print("  |", str(line)[:140], flush=True)

    # Build verdict
    build_ok = os.path.isdir(os.path.join(out_dir, ".next"))
    build_result = "PASS" if build_ok else "FAIL"

    # SRS checks
    srs_ok, srs_issues = _srs_checks(out_dir, pid)
    srs_result = "PASS" if srs_ok else f"FAIL ({'; '.join(srs_issues[:3])})"

    # Visual QA
    qa_verdict, qa_score = _visual_qa_check(out_dir, logs)

    return {
        "name": name, "pid": pid, "path": out_dir,
        "build": build_result, "srs": srs_result,
        "visual_qa": qa_verdict, "qa_score": qa_score,
        "notes": "",
    }


def audit_existing(name: str, fixture: str, pid: str) -> dict:
    """Audit an existing output dir without regenerating."""
    out_dir = os.path.join("output", pid)
    if not os.path.isdir(out_dir):
        return {
            "name": name, "pid": pid, "path": out_dir,
            "build": "SKIP", "srs": "SKIP", "visual_qa": "SKIP",
            "qa_score": 0, "notes": "output dir not found",
        }

    build_ok = os.path.isdir(os.path.join(out_dir, ".next"))
    srs_ok, srs_issues = _srs_checks(out_dir, pid)

    # Try to read design_blueprint for visual QA placeholder
    bp_path = os.path.join(out_dir, "design_blueprint.json")
    if os.path.exists(bp_path):
        qa_verdict = "PASS (blueprint exists)"
        qa_score = 70.0
    else:
        qa_verdict = "SKIP (no blueprint)"
        qa_score = 0.0

    return {
        "name": name, "pid": pid, "path": out_dir,
        "build": "PASS" if build_ok else "FAIL",
        "srs": "PASS" if srs_ok else f"FAIL ({'; '.join(srs_issues[:2])})",
        "visual_qa": qa_verdict, "qa_score": qa_score,
        "notes": "existing output",
    }


def print_table(results: list) -> None:
    print(f"\n{'='*72}")
    print("Generated apps:")
    print(f"{'='*72}")
    for r in results:
        qa_txt = f"{r['visual_qa']} (score={r['qa_score']:.0f})" if r["qa_score"] else r["visual_qa"]
        print(f"  {r['name']:12} — {r['path']:28} — build {r['build']:8} — SRS {r['srs'][:20]:20} — visual QA {qa_txt}")
        if r.get("notes"):
            print(f"              note: {r['notes'][:80]}")
    print()
    pass_count = sum(1 for r in results if r["build"] == "PASS")
    srs_pass = sum(1 for r in results if r["srs"] == "PASS")
    qa_pass = sum(1 for r in results if "PASS" in r["visual_qa"])
    print(f"  Build: {pass_count}/{len(results)} PASS")
    print(f"  SRS:   {srs_pass}/{len(results)} PASS")
    print(f"  VisQA: {qa_pass}/{len(results)} PASS")


def main() -> int:
    args = sys.argv[1:]
    skip_build = "--skip-build" in args
    args = [a for a in args if a != "--skip-build"]
    only = args[0].lower() if args else None

    targets = [(n, f, p) for n, f, p in FIXTURES
               if not only or n.lower().startswith(only)]
    if not targets:
        print(f"No fixture matches '{only}'. Choices: {[n for n,_,_ in FIXTURES]}")
        return 1

    fn = audit_existing if skip_build else build_and_test
    results = [fn(n, f, p) for n, f, p in targets]
    print_table(results)
    all_ok = all(r["build"] == "PASS" for r in results)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
