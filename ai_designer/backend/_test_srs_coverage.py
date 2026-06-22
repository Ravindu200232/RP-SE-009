"""SRS Coverage Test Suite.

Validates that parse_srs_input() extracts all 25 SRS template sections and
that data_model_planner propagates them into the data model output.

Run:  python _test_srs_coverage.py
      python _test_srs_coverage.py <path-to-srs.txt>  (test a specific file)
Exit code is non-zero if any test fails.
"""
import os, sys, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import srs as srs_mod
from app import data_model_planner as dmp

RESULTS = []

# All 25 top-level sections defined in the SRS template
SRS_SECTIONS = [
    "document_title", "project_name", "version", "document_language",
    "system_category", "prepared_for", "app_summary", "app_type",
    "authentication_requirement", "roles", "main_modules", "database_design",
    "public_landing_website", "application_pages", "role_access_matrix",
    "functional_requirements", "business_workflows", "validation_rules",
    "non_functional_requirements", "api_requirements", "reporting_requirements",
    "notification_requirements", "security_requirements", "ui_ux_requirements",
    "acceptance_criteria", "future_enhancements",
]

# Parsed output keys that each SRS section maps to
SECTION_TO_PARSED_KEY = {
    "document_title":           "app_name",          # used as fallback for app_name
    "project_name":             "app_name",          # used as fallback for app_name
    "version":                  None,                # metadata, not in parsed output (OK)
    "document_language":        None,                # metadata, not in parsed output (OK)
    "system_category":          "system_category",
    "prepared_for":             None,                # metadata, not in parsed output (OK)
    "app_summary":              "app_name",          # app_summary.app_name -> app_name
    "app_type":                 "app_type",
    "authentication_requirement": "authentication_requirement",
    "roles":                    "roles",
    "main_modules":             "main_modules",
    "database_design":          "entities",          # database_design.tables -> entities
    "public_landing_website":   "marketing_pages",   # .pages -> marketing_pages
    "application_pages":        "app_pages",
    "role_access_matrix":       "role_access_matrix",
    "functional_requirements":  "key_features",
    "business_workflows":       "business_workflows",
    "validation_rules":         "validation_rules",
    "non_functional_requirements": "non_functional_requirements",
    "api_requirements":         "api_requirements",
    "reporting_requirements":   "reporting_requirements",
    "notification_requirements":"notification_requirements",
    "security_requirements":    "security_requirements",
    "ui_ux_requirements":       "ui_ux_requirements",
    "acceptance_criteria":      "acceptance_criteria",
    "future_enhancements":      "future_enhancements",
}

# Metadata-only sections (not required to produce parsed output keys)
METADATA_ONLY = {"version", "document_language", "prepared_for"}

def rec(num, name, passed, detail=""):
    RESULTS.append((num, passed))
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] #{num} {name}" + (f"  -> {detail}" if detail else ""), flush=True)


def load_srs(path):
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    # strip markdown code fences if present
    raw = re.sub(r"^```\w*\n", "", raw.strip(), flags=re.M)
    raw = re.sub(r"\n```$", "", raw.strip(), flags=re.M)
    return raw


def test_detection(raw, srs_name):
    detected = srs_mod.detect(raw)
    rec(1, f"detect() identifies {srs_name} as SRS", detected, f"detect={detected}")
    return detected


def test_parse_returns_all_sections(parsed, srs_name, srs_num):
    """Check that every non-metadata section maps to a populated parsed key."""
    covered, missing = [], []
    for section, key in SECTION_TO_PARSED_KEY.items():
        if section in METADATA_ONLY or key is None:
            covered.append(section)
            continue
        val = parsed.get(key)
        if val is None:
            missing.append(f"{section}->{key}=None")
        elif isinstance(val, (list, dict)) and not val:
            missing.append(f"{section}->{key}=empty")
        else:
            covered.append(section)

    total = len([s for s in SECTION_TO_PARSED_KEY if s not in METADATA_ONLY and SECTION_TO_PARSED_KEY[s]])
    n_covered = len([s for s in covered if s not in METADATA_ONLY and SECTION_TO_PARSED_KEY.get(s)])
    pct = round(100 * n_covered / total) if total else 0
    rec(srs_num, f"{srs_name} sections covered: {n_covered}/{total} ({pct}%)",
        pct == 100, "missing: " + (", ".join(missing) or "none"))
    return pct, missing


def test_entities(parsed, srs_name, num):
    ents = parsed.get("entities") or []
    has_fields = all(len(e.get("fields") or []) >= 1 for e in ents)
    rec(num, f"{srs_name} entities: {len(ents)} with fields", len(ents) >= 3 and has_fields,
        f"{len(ents)} entities, all_have_fields={has_fields}")


def test_roles(parsed, srs_name, num):
    roles = parsed.get("roles") or []
    rec(num, f"{srs_name} roles: {len(roles)} extracted", len(roles) >= 2,
        ", ".join(roles[:6]))


def test_marketing_pages(parsed, srs_name, num):
    pages = parsed.get("marketing_pages") or []
    rec(num, f"{srs_name} marketing pages: {len(pages)}", len(pages) >= 2,
        ", ".join(p["name"] for p in pages[:5]))


def test_app_pages(parsed, srs_name, num):
    pages = parsed.get("app_pages") or []
    has_roles = any((p.get("allowed_roles") or []) for p in pages)
    rec(num, f"{srs_name} app_pages: {len(pages)} with roles", len(pages) >= 3 and has_roles,
        f"{len(pages)} pages, roles_wired={has_roles}")


def test_business_workflows(parsed, srs_name, num):
    wfs = parsed.get("business_workflows") or []
    has_steps = all(len(w.get("steps") or []) >= 1 for w in wfs)
    rec(num, f"{srs_name} business_workflows: {len(wfs)}", bool(wfs) and has_steps,
        (", ".join(w["name"] for w in wfs[:4]) or "none"))


def test_reporting(parsed, srs_name, num):
    reps = parsed.get("reporting_requirements") or []
    rec(num, f"{srs_name} reporting_requirements: {len(reps)}", bool(reps),
        ", ".join(r.get("name", "") for r in reps[:4]))


def test_notifications(parsed, srs_name, num):
    notifs = parsed.get("notification_requirements") or []
    rec(num, f"{srs_name} notification_requirements: {len(notifs)}", bool(notifs),
        ", ".join(n.get("event", "") for n in notifs[:3]))


def test_security(parsed, srs_name, num):
    sec = parsed.get("security_requirements") or []
    rec(num, f"{srs_name} security_requirements: {len(sec)}", bool(sec),
        str(sec[0])[:60] if sec else "none")


def test_ui_ux(parsed, srs_name, num):
    ux = parsed.get("ui_ux_requirements") or {}
    rec(num, f"{srs_name} ui_ux_requirements: {len(ux)} keys", bool(ux),
        str(list(ux.keys())[:4]))


def test_acceptance(parsed, srs_name, num):
    ac = parsed.get("acceptance_criteria") or []
    rec(num, f"{srs_name} acceptance_criteria: {len(ac)}", bool(ac),
        str(ac[0])[:60] if ac else "none")


def test_future(parsed, srs_name, num):
    fe = parsed.get("future_enhancements") or []
    rec(num, f"{srs_name} future_enhancements: {len(fe)}", bool(fe),
        str(fe[0])[:60] if fe else "none")


def test_auth_requirement(parsed, srs_name, num):
    auth = parsed.get("authentication_requirement") or {}
    rec(num, f"{srs_name} authentication_requirement: {len(auth)} flags", bool(auth),
        str(list(auth.keys())[:4]))


def test_main_modules(parsed, srs_name, num):
    mods = parsed.get("main_modules") or []
    rec(num, f"{srs_name} main_modules: {len(mods)}", bool(mods),
        ", ".join(mods[:5]))


def test_validation_rules(parsed, srs_name, num):
    vrs = parsed.get("validation_rules") or []
    rec(num, f"{srs_name} validation_rules: {len(vrs)}", bool(vrs),
        str(vrs[0] if vrs else "none")[:80])


def test_system_category(parsed, srs_name, num):
    cat = parsed.get("system_category") or ""
    rec(num, f"{srs_name} system_category extracted", bool(cat), cat[:80])


def test_data_model_propagation(parsed, srs_name, base_num):
    """Verify data_model_planner picks up all extra SRS sections."""
    try:
        dm = dmp.plan_data_model("", app_name=parsed.get("app_name"), srs=parsed)
    except Exception as e:
        rec(base_num, f"{srs_name} data_model_planner: raised {e}", False)
        return

    checks = [
        ("srs_workflows", "business_workflows wired into data model"),
        ("srs_notifications", "notifications wired into data model"),
        ("srs_reports", "reporting wired into data model"),
        ("srs_security", "security wired into data model"),
        ("srs_ui_ux", "ui_ux wired into data model"),
        ("srs_acceptance", "acceptance_criteria wired into data model"),
        ("srs_future", "future_enhancements wired into data model"),
        ("srs_validation", "validation_rules wired into data model"),
        ("srs_auth", "auth_requirements wired into data model"),
        ("srs_modules", "main_modules wired into data model"),
        ("srs_system_category", "system_category wired into data model"),
    ]
    for i, (key, label) in enumerate(checks):
        val = dm.get(key)
        ok = bool(val)
        rec(base_num + i, f"{srs_name} {label}", ok,
            f"{key}={'present' if ok else 'MISSING'}")

    # Also check workflow_rules were assigned to at least one entity
    ents_with_workflows = [e["name"] for e in dm.get("entities", [])
                           if e.get("workflow_rules")]
    rec(base_num + len(checks), f"{srs_name} workflow_rules assigned to entities",
        bool(ents_with_workflows), str(ents_with_workflows[:3]))


def run_file(path, srs_name, base_num=1):
    print(f"\n{'='*60}")
    print(f"  SRS FILE: {srs_name}")
    print(f"{'='*60}")
    raw = load_srs(path)

    detected = test_detection(raw, srs_name)
    if not detected:
        print("  SKIP: not detected as SRS, skipping remaining tests.")
        return

    parsed = srs_mod.parse_srs_input(raw)
    if not parsed:
        print("  FAIL: parse_srs_input returned None")
        RESULTS.append((base_num, False))
        return

    print(f"\n  --- Core parsing ---")
    pct, missing = test_parse_returns_all_sections(parsed, srs_name, base_num + 1)
    test_entities(parsed, srs_name, base_num + 2)
    test_roles(parsed, srs_name, base_num + 3)
    test_marketing_pages(parsed, srs_name, base_num + 4)
    test_app_pages(parsed, srs_name, base_num + 5)

    print(f"\n  --- New sections (SRS coverage) ---")
    test_system_category(parsed, srs_name, base_num + 6)
    test_main_modules(parsed, srs_name, base_num + 7)
    test_auth_requirement(parsed, srs_name, base_num + 8)
    test_business_workflows(parsed, srs_name, base_num + 9)
    test_validation_rules(parsed, srs_name, base_num + 10)
    test_reporting(parsed, srs_name, base_num + 11)
    test_notifications(parsed, srs_name, base_num + 12)
    test_security(parsed, srs_name, base_num + 13)
    test_ui_ux(parsed, srs_name, base_num + 14)
    test_acceptance(parsed, srs_name, base_num + 15)
    test_future(parsed, srs_name, base_num + 16)

    print(f"\n  --- Data model propagation ---")
    test_data_model_propagation(parsed, srs_name, base_num + 17)

    return pct


if __name__ == "__main__":
    desktop = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
    default_files = [
        (os.path.join(desktop, "MegaMart Retail srs.txt"), "MegaMart"),
        (os.path.join(desktop, "MediPlus Pharmacy POS srs.txt"), "MediPlus"),
        (os.path.join(desktop, "GrandVisita Hotel Srs.txt"), "GrandVista"),
        (os.path.join(desktop, "EduSphere srs.txt"), "EduSphere"),
        (os.path.join(desktop, "AutoHub Vehicle Sales srs.txt"), "AutoHub"),
    ]

    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        files = [(sys.argv[1], os.path.basename(sys.argv[1]))]
    else:
        files = [(p, n) for p, n in default_files if os.path.exists(p)]

    if not files:
        print("ERROR: No SRS files found. Pass a file path or place SRS files on the Desktop.")
        sys.exit(1)

    all_pcts = []
    for i, (path, name) in enumerate(files):
        pct = run_file(path, name, base_num=i * 100 + 1)
        if pct is not None:
            all_pcts.append((name, pct))

    print(f"\n{'='*60}")
    print("  COVERAGE SUMMARY")
    print(f"{'='*60}")
    for name, pct in all_pcts:
        filled = pct // 5
        bar = "#" * filled + "-" * (20 - filled)
        print(f"  {name:20s} [{bar}] {pct}%")

    total = len(RESULTS)
    passed = sum(1 for _, ok in RESULTS if ok)
    failed = total - passed
    print(f"\n  Tests: {total}  PASS: {passed}  FAIL: {failed}")
    avg_cov = round(sum(p for _, p in all_pcts) / len(all_pcts)) if all_pcts else 0
    print(f"  Average SRS section coverage: {avg_cov}%")
    sys.exit(0 if failed == 0 else 1)
