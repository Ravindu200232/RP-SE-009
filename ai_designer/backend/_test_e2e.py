"""End-to-end: walk the one-at-a-time interview (selecting defaults, adding a
CUSTOM page + a free-text requirement + a chosen navbar style), then run the
REAL pipeline and confirm it BUILDS (no route collision) with design honored."""
import os, sys, json, re
os.environ["AI_DESIGNER_FAST"] = "1"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import interview as iv
from app.graph import creation_app


def record(q, d, a):
    a = dict(a)
    qid = q["id"]
    if qid == "pages":
        a["pages"] = d
        a["components"] = a.get("components", {})
    elif qid.startswith("sections:"):
        a.setdefault("components", {})[qid[9:]] = d
    elif qid == "auth":
        a["auth"] = d
    elif qid == "roles":
        a["roles"] = d
    elif qid == "entities":
        a["entities"] = d
    elif qid.startswith("design:"):
        a.setdefault("design", {})[qid[7:]] = d
    elif qid.startswith("cov:"):
        a.setdefault("coverage", {})[qid[4:]] = d
    elif qid.startswith("extra:"):
        a.setdefault("extras", {})[qid[6:]] = d
    elif qid == "theme":
        a["theme"] = d
    return a


plan = iv.build_plan("a hotel booking and management app", "hybrid", "en")
ans = {}
for _ in range(80):
    s = iv.next_step(plan, ans)
    if s.get("done"):
        ans = s["answers"]
        break
    q = s["question"]
    if q["id"] == "pages":
        d = [{"value": o["value"], "label": o["label"], "template": o.get("template", "content")} for o in q["options"][:2]]
        d.append({"value": "photo-gallery", "label": "Photo Gallery", "template": "gallery"})   # CUSTOM page
    elif q["kind"] == "toggle":
        d = q["id"] in ("cov:notifications", "cov:payments")
    elif q["kind"] == "single":
        d = (q["options"][0]["value"] if q.get("options") else (q.get("default") or ""))
        if q["id"] == "design:nav":
            d = "floating"     # explicit navbar choice
    elif q["kind"] == "text":
        d = "Loyalty points and gift vouchers for repeat guests"   # free-text requirement
    elif q["kind"] == "entity_layouts":
        d = q.get("default") or []
    else:
        d = [o["value"] for o in (q.get("options") or [])[:2]]
    ans = record(q, d, ans)

intake = iv.assemble_intake(ans)
print("intake: theme", intake["theme_style"], "| styles", intake.get("styles"),
      "| pages", [p["slug"] for p in intake["pages"]])
print("requirements:", intake["requirements"][:160])

state = {"project_id": "prj_e2e", "prompt": "a hotel booking and management app",
         "history": [], "roles": [], "pages": [], "files": {}, "intake": intake, "status": "i", "logs": []}
final = creation_app.invoke(state)
print("\nSTATUS:", final.get("status"))
try:
    print("phase:", json.load(open("output/prj_e2e/status.json")).get("phase"))
    site = open("output/prj_e2e/src/lib/site.js", encoding="utf-8").read()
    print("site.styles nav (should be 'floating'):", (re.search(r'"nav":\s*"([^"]+)"', site) or [None, "?"])[1])
    print("marketing dirs:", sorted(d for d in os.listdir("output/prj_e2e/src/app/(marketing)") if "." not in d))
    css = open("output/prj_e2e/src/theme.css", encoding="utf-8").read()
    print("paradigm:", (re.search(r"paradigm '([^']+)'", css) or [None, "?"])[1])
except Exception as e:
    print("inspect error:", e)
