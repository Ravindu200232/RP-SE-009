"""Deterministic test of the interview->generation path: assemble_intake +
graph._apply_intake overrides, then a real build of a no-auth app whose pages
use explicitly chosen sections (incl a custom one). No LLM / no GPU."""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import interview, graph, nextgen

# ---- 1. intake overrides ----
answers = {
    "pages": [
        {"value": "classes", "label": "Classes", "template": "gallery"},
        {"value": "pricing", "label": "Pricing", "template": "pricing"},
        {"value": "contact", "label": "Contact", "template": "contact"},
    ],
    "components": {
        "classes": ["hero", "gallery", "stats", "WaitlistForm"],   # incl a custom one
        "pricing": ["hero", "pricing", "faq"],
        "contact": ["hero", "contact_form"],
    },
    "auth": False,
    "roles": ["Member", "Trainer"],
    "theme": "cyberpunk",
    "entities": [{"name": "Member", "layout": "split-pane"}, {"name": "Payment", "layout": "spreadsheet"}],
}
intake = interview.assemble_intake(answers)
state = {
    "logs": [],
    "entities": [{"name": "Member", "label": "Members", "crud_layout": "table", "fields": []},
                 {"name": "Payment", "label": "Payments", "crud_layout": "table", "fields": []}],
    "roles": ["Admin"], "marketing_pages": [{"name": "Old", "slug": "old", "template": "features"}],
    "theme_style": "minimal", "is_utility_tool": False, "intake": intake,
}
graph._apply_intake(state)
assert [e["crud_layout"] for e in state["entities"]] == ["split-pane", "spreadsheet"], state["entities"]
assert [p["slug"] for p in state["marketing_pages"]] == ["classes", "pricing", "contact"], state["marketing_pages"]
assert state["roles"] == ["Member", "Trainer"]
assert state["theme_style"] == "cyberpunk"
assert intake["auth"] is False
print("INTAKE OVERRIDES OK:", [(p['slug'], p['sections']) for p in state["marketing_pages"]])

# ---- 2. real build of a no-auth app with the chosen sections ----
OUT = os.path.join("output", "prj_intake_test")
nextgen.create_project(OUT)
nextgen.write_status(OUT, "pages", "test")
ents = [{"name": "Member", "label": "Members", "slug": "members", "icon": "Users", "crud_layout": "split-pane",
         "fields": [{"name": "full_name", "label": "Full Name", "type": "text"}, {"name": "plan", "label": "Plan", "type": "text"}]}]
links = [{"label": "Home", "href": "/"}] + [{"label": p["name"], "href": "/" + p["slug"]} for p in state["marketing_pages"]]
side = [{"label": "Dashboard", "href": "/dashboard", "icon": "LayoutDashboard"},
        {"label": "Members", "href": "/e/members", "icon": "Users"}]
nextgen.write_site(OUT, "FlexFit", "Train smarter.", links, side, ents, ["Member", "Trainer"],
                   {"nav": "blur", "footer": "centered", "dash": "glass", "list": "striped"}, auth=False)
nextgen.write_theme(OUT, "violet", "Space Grotesk", "Inter", "cyberpunk")
nextgen.write_layout_meta(OUT, "FlexFit", "Train smarter.",
                          "https://fonts.googleapis.com/css2?family=Space+Grotesk&family=Inter&display=swap", "cyberpunk")
bp = {"domain": "gym", "key_features": ["Class booking", "Membership plans", "Trainer scheduling"],
      "terminology": ["Reps", "Sets", "Macros"], "entities": [{"name": "Member"}]}
nextgen.write_marketing_pages(OUT, state["marketing_pages"], "FlexFit", bp)
nextgen.write_db(OUT, {"users": [{"id": "1", "name": "A", "email": "a@a.com", "password": "x", "role": "Member"}],
                       "Member": [{"id": "1", "full_name": "Jane", "plan": "Gold"}]})

# checks on generated source
nav = open(os.path.join(OUT, "src", "components", "shell", "Navbar.jsx"), encoding="utf-8").read()
assert "site.auth !== false" in nav, "navbar not auth-aware"
classes_pg = open(os.path.join(OUT, "src", "app", "(marketing)", "classes", "page.jsx"), encoding="utf-8").read()
assert "Waitlistform" in classes_pg or "WaitlistForm" in classes_pg, "custom section missing"
print("custom 'WaitlistForm' section rendered on classes page:", "WaitlistForm" in classes_pg)
print("site.auth=false present:", '"auth": false' in open(os.path.join(OUT, "src", "lib", "site.js"), encoding="utf-8").read())

print("building...")
ok, out = nextgen.run_build(OUT)
print("BUILD", "OK" if ok else "FAILED")
if not ok:
    print(out[-2000:])
