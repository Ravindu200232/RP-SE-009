"""Reusable, domain-agnostic SRS-app verifier.

Runs the 11 required checks against a generated app, driven entirely by that
app's own SRS fixture (no hardcoded domain). Works for ANY SRS that follows the
template:
  1  build (.next present)
  2  every public_landing_website.pages route generated
  3  every application_pages route generated
  4  each public page contains its own SRS section content
  5  no other-domain content leaked into public pages
  6  no "Page" suffix in nav labels
  7  RBAC: pageAccess + canAccessPage + guards; customer not on /admin
  8  every database table has a model
  9  every entity API route + auth/reports/notifications
  10 workflow services exist
  11 reports + notifications generated

Usage: python _test_srs_apps.py            # all 4
       python _test_srs_apps.py grandvista # one
"""
import json
import os
import re
import sys

BACKEND = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND)
from app import srs
from app import srs_public_page_generator as pub

APPS = [
    ("grandvista", "_srs_grandvista.json", "prj_grandvista"),
    ("edusphere", "_srs_edusphere.json", "prj_edusphere"),
    ("megamart", "_srs_megamart.json", "prj_megamart"),
    ("autohub", "_srs_autohub.json", "prj_autohub"),
    ("fitzone", "_srs_fitzone.json", "prj_fitzone"),
    ("beautyzen", "_srs_beautyzen.json", "prj_beautyzen"),
    ("propease", "_srs_propease.json", "prj_propease"),
    ("cloudkitchen", "_srs_cloudkitchen.json", "prj_cloudkitchen"),
    ("petcare", "_srs_petcare.json", "prj_petcare"),
]

SIG = {
    "grandvista": ["reservation", "housekeeping", "suite", "concierge", "hotel", "check-out"],
    "edusphere": ["student", "teacher", "tuition", "lesson", "classroom", "school", "admission", "timetable", "syllabus", "pupil"],
    "megamart": ["grocery", "supermarket", "aisle", "warehouse"],
    "autohub": ["vehicle", "mechanic", "dealership", "showroom", "mileage", "odometer"],
    "mediplus": ["medicine", "dosage", "tablet", "pharmacy", "nmra"],
    "fitzone": ["zumba", "hiit", "crossfit", "supplement", "workout plan", "diet plan", "membership plan", "personal trainer"],
    "beautyzen": ["manicure", "pedicure", "beautician", "hairstylist", "eyelash", "nail art", "spa package"],
    "propease": ["landlord", "tenancy", "conveyancing", "realtor", "leasehold", "freehold", "property viewings"],
    "cloudkitchen": ["ghost kitchen", "dark kitchen", "kitchen display", "delivery rider", "multi-brand"],
    "petcare": ["veterinarian", "deworming", "spay", "neuter", "pet grooming", "vaccination schedule"],
}
HEALTHCARE_TEMPLATE = ["cardiology", "pediatric", "patient portal", "book an appointment",
                       "specialist care", "neighbourhood pharmacy", "nmra", "generic names"]

AUTH_TABLES = {"users", "roles", "permissions", "role_permissions", "audit_logs"}
SKIP_APP_ROUTES = {"/login", "/register", "/logout", "/dashboard", "/"}
STOP = {"section", "with", "and", "the", "for", "your", "page", "preview", "details", "quick",
        "links", "us", "our", "by", "category", "from", "list", "of", "to", "a", "map"}


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def safe_route(route):
    return re.sub(r"[^a-zA-Z0-9/_-]", "", route or "").strip("/")


def _singular(w):
    """Normalize a collection/entity token to a comparable singular form so
    entity 'VehicleInquiry' matches api dir 'vehicleInquiries', 'Category' ->
    'categories', 'RoomType' -> 'roomTypes', etc."""
    w = re.sub(r"[^a-z0-9]", "", str(w).lower())
    if w.endswith("ies") and len(w) > 3:
        return w[:-3] + "y"
    if w.endswith(("sses", "ches", "shes", "xes", "zes")) and len(w) > 4:
        return w[:-2]   # classes->class, boxes->box (NOT warehouses->warehous)
    if w.endswith("s") and not w.endswith("ss") and len(w) > 1:
        return w[:-1]   # warehouses->warehouse, stores->store
    return w


def topics(section):
    head = re.split(r"\bwith\b", section, maxsplit=1, flags=re.I)[0]
    return [w for w in re.findall(r"[a-z]+", head.lower()) if len(w) >= 4 and w not in STOP]


def extract_array(text, key):
    idx = text.find(key)
    if idx == -1:
        return None
    start = text.find("[", idx)
    if start == -1:
        return None
    depth, i = 0, start
    while i < len(text):
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    return None


def run_app(key, fixture, pid):
    print(f"\n{'='*64}\n{key}  ({pid})\n{'='*64}")
    results = []

    def rec(n, name, ok, detail=""):
        results.append(bool(ok))
        print(f"  [{'PASS' if ok else 'FAIL'}] {n:>2} {name}" + (f"  -> {detail}" if detail else ""))

    raw = read(os.path.join(BACKEND, fixture))
    doc = json.loads(raw).get("srs_document", {})
    parsed = srs.parse_srs_input(raw)
    prj = os.path.join(BACKEND, "output", pid)
    src = os.path.join(prj, "src")
    mkt = os.path.join(src, "app", "(marketing)")
    appd = os.path.join(src, "app", "(app)")
    apidir = os.path.join(src, "app", "api")

    # T1 build
    rec(1, "build (.next present)", os.path.isdir(os.path.join(prj, ".next")))

    # T2 public routes
    pub_pages = doc.get("public_landing_website", {}).get("pages", [])
    miss = []
    for p in pub_pages:
        route = p.get("route", "")
        if route in ("/", ""):
            ok = os.path.isfile(os.path.join(mkt, "page.jsx")) or os.path.isfile(os.path.join(mkt, "home-page", "page.jsx"))
        else:
            slug = pub._slug_for_page(p.get("page_name", ""), route)
            ok = os.path.isfile(os.path.join(mkt, slug, "page.jsx"))
        if not ok:
            miss.append(p.get("page_name"))
    rec(2, f"public routes generated ({len(pub_pages)})", not miss, f"missing: {miss}" if miss else "all present")

    # T3 app routes
    app_pages = doc.get("application_pages", [])
    miss3 = []
    checked3 = 0
    for p in app_pages:
        route = p.get("route", "")
        if route in SKIP_APP_ROUTES or (p.get("page_type") == "auth") or route.startswith(("/login", "/register")):
            continue
        checked3 += 1
        if not os.path.isfile(os.path.join(appd, *safe_route(route).split("/"), "page.jsx")):
            miss3.append(route)
    rec(3, f"app routes generated ({checked3})", not miss3, f"missing: {miss3}" if miss3 else "all present")

    # T4 public content (each page contains its own section topics) + T5 banned
    banned = []
    for k, words in SIG.items():
        if k != key:
            banned += words
    banned += HEALTHCARE_TEMPLATE
    content_fail, leaks = [], []
    for p in pub_pages:
        route = p.get("route", "")
        if route in ("/", ""):
            f = os.path.join(mkt, "home-page", "page.jsx")
            if not os.path.isfile(f):
                f = os.path.join(mkt, "page.jsx")
        else:
            f = os.path.join(mkt, pub._slug_for_page(p.get("page_name", ""), route), "page.jsx")
        txt = read(f).lower()
        if not txt:
            continue
        for b in banned:
            if re.search(r"\b" + re.escape(b) + r"\b", txt):
                leaks.append(f"{p.get('page_name')}:'{b}'")
        checkable = [s for s in (p.get("sections") or []) if pub._classify(s) not in ("hero", "footer", "cta")]
        hit = sum(1 for s in checkable if (not topics(s)) or any(re.search(r"\b" + re.escape(w) + r"\b", txt) for w in topics(s)))
        if checkable and hit / len(checkable) < 0.6:
            content_fail.append(f"{p.get('page_name')} {hit}/{len(checkable)}")
    rec(4, "public pages contain own SRS section content", not content_fail, f"weak: {content_fail}" if content_fail else "ok")

    # also scan generated APP pages (pos/portal/admin sections) for pharmacy/
    # healthcare template terms — the hardcoded-template leak vector. Skipped only
    # for an actual pharmacy app.
    MEDICAL_EXEMPT = {"mediplus", "petcare"}
    if key not in MEDICAL_EXEMPT:
        pharma = ["medicine", "prescription", "pharmacist", "pharmacy", "dosage",
                  "tablet", "medicinebatch"] + HEALTHCARE_TEMPLATE
        for root, _dirs, fs in os.walk(appd):
            for fn in fs:
                if not fn.endswith(".jsx"):
                    continue
                t = read(os.path.join(root, fn)).lower()
                for b in pharma:
                    if re.search(r"\b" + re.escape(b) + r"\b", t):
                        leaks.append("app/" + os.path.relpath(os.path.join(root, fn), appd).replace("\\", "/") + f":'{b}'")
    rec(5, "no cross-domain content in public + app pages", not leaks, f"leaks: {leaks[:8]}" if leaks else "clean")

    # T6 nav labels
    site_js = read(os.path.join(src, "lib", "site.js"))
    arr = extract_array(site_js, "marketingLinks")
    labels = []
    if arr:
        try:
            labels = [l.get("label", "") for l in json.loads(arr)]
        except Exception:
            pass
    bad6 = [l for l in labels if l.lower().strip().endswith("page")]
    rec(6, "no 'Page' suffix in nav labels", not bad6, f"bad: {bad6}" if bad6 else f"{len(labels)} labels clean")

    # T7 RBAC
    access_js = read(os.path.join(src, "lib", "access.js"))
    layout = read(os.path.join(appd, "layout.jsx"))
    has_core = all(k in access_js for k in ("pageAccess", "canAccessPage", "getVisibleNavItems"))
    cust_on_admin = False
    m = re.search(r"pageAccess\s*=\s*(\{.*?\})\s*;", access_js, re.DOTALL)
    if m:
        try:
            pa = json.loads(m.group(1))
            for route, roles in pa.items():
                if route.startswith("/admin") and any("customer" in str(r).lower() or str(r).lower() == "guest" for r in roles):
                    cust_on_admin = True
        except Exception:
            pass
    rec(7, "RBAC (pageAccess/canAccessPage/getVisibleNavItems + guard, no customer on /admin)",
        has_core and "canAccessPage" in layout and not cust_on_admin,
        f"core={has_core} guard={'canAccessPage' in layout} custOnAdmin={cust_on_admin}")

    # T8 models
    tables = [t.get("table_name") for t in doc.get("database_design", {}).get("tables", [])]
    biz_tables = [t for t in tables if t not in AUTH_TABLES]
    models_dir = os.path.join(src, "lib", "models")
    model_files = {f.lower() for f in os.listdir(models_dir)} if os.path.isdir(models_dir) else set()
    ent_names = [e["name"] for e in parsed.get("entities", [])]
    miss8 = [e for e in ent_names if f"{e.lower()}.js" not in model_files]
    rec(8, f"models for all business tables ({len(ent_names)} entities / {len(biz_tables)} tables)",
        not miss8 and len(ent_names) >= len(biz_tables) * 0.85,
        f"missing models: {miss8}" if miss8 else f"{len(model_files)} model files")

    # T9 API routes
    api_dirs = {d.lower() for d in os.listdir(apidir)} if os.path.isdir(apidir) else set()
    norm_dirs = {_singular(d) for d in api_dirs}
    miss9 = [e for e in ent_names if _singular(e) not in norm_dirs]
    infra = [x for x in ("auth", "reports", "notifications") if x not in api_dirs]
    rec(9, f"entity API routes + auth/reports/notifications ({len(api_dirs)} dirs)",
        not miss9 and not infra, f"missing entity APIs: {miss9} infra: {infra}" if (miss9 or infra) else "all present")

    # T10 workflows -> services
    svc_dir = os.path.join(src, "lib", "services")
    svc = os.listdir(svc_dir) if os.path.isdir(svc_dir) else []
    workflows = doc.get("business_workflows", [])
    rec(10, f"workflow services exist ({len(svc)} services / {len(workflows)} workflows)",
        len(svc) >= max(3, int(len(ent_names) * 0.6)) and any("NotificationService" in s for s in svc),
        f"{len(svc)} service files")

    # T11 reports + notifications
    reports_page = any(os.path.isfile(os.path.join(appd, *r.split("/"), "page.jsx")) for r in ("admin/reports", "reports"))
    notif_model = os.path.isfile(os.path.join(models_dir, "Notification.js"))
    notif_svc = os.path.isfile(os.path.join(svc_dir, "NotificationService.js"))
    rec(11, "reports page + notification model/service + APIs",
        reports_page and notif_model and notif_svc and "reports" in api_dirs and "notifications" in api_dirs,
        f"reportsPage={reports_page} notifModel={notif_model} notifSvc={notif_svc}")

    passed = sum(results)
    print(f"  ---- {key}: {passed}/{len(results)} passed ----")
    return key, pid, passed, len(results), results


def main():
    only = sys.argv[1].lower() if len(sys.argv) > 1 else None
    targets = [a for a in APPS if not only or a[0] == only]
    summary = [run_app(*a) for a in targets]
    print(f"\n{'='*64}\nOVERALL\n{'='*64}")
    allgreen = True
    for key, pid, passed, total, _ in summary:
        allgreen = allgreen and passed == total
        print(f"  {key:12} {passed}/{total} {'PASS' if passed == total else 'FAIL'}")
    return 0 if allgreen else 1


if __name__ == "__main__":
    sys.exit(main())
