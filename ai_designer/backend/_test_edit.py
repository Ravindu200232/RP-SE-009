"""Accuracy test for Select-Element targeted edits. Each edit names a component
(by data-component-id), gives a natural-language change with a checkable marker,
and we verify: applied + built green. Plus one deliberately-broken edit to prove
auto-revert keeps the app working."""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import editor

PID = "prj_iv_school"

GOOD = [
    ("navbar", "Add a small tagline that says exactly: Learn Anywhere", "Learn Anywhere",
     "src/components/shell/Navbar.jsx"),
    ("dashboard", "Change the main page heading to exactly: Control Center", "Control Center",
     "src/app/(app)/dashboard/page.jsx"),
    ("page-courses", "Change the big hero heading to exactly: Welcome Students", "Welcome Students",
     "src/app/(marketing)/courses/page.jsx"),
]
BAD = ("dashboard", "Use a brand-new component called <SuperFancyUnicornChart/> at the very top", "SuperFancyUnicornChart")

results = []


def read(rel):
    try:
        return open(os.path.join("output", PID, *rel.split("/")), encoding="utf-8").read()
    except Exception:
        return ""


print("=== GOOD edits (apply + build) ===", flush=True)
for cid, prompt, marker, rel in GOOD:
    t0 = time.time()
    res = editor.edit_component(PID, cid, prompt)
    applied = bool(res.get("ok")) and marker in read(rel)
    results.append({"cid": cid, "prompt": prompt, "ok": res.get("ok"), "marker_present": marker in read(rel),
                    "applied": applied, "error": res.get("error"), "secs": round(time.time() - t0, 1)})
    print(f"  [{cid}] ok={res.get('ok')} marker={marker in read(rel)} applied={applied} ({round(time.time()-t0)}s) {res.get('error') or ''}", flush=True)

print("\n=== BAD edit (must auto-revert) ===", flush=True)
cid, prompt, bad_marker = BAD
before = read("src/app/(app)/dashboard/page.jsx")
res = editor.edit_component(PID, cid, prompt)
after = read("src/app/(app)/dashboard/page.jsx")
reverted_ok = (not res.get("ok")) and (bad_marker not in after) and ("Control Center" in after)  # prior good edit preserved
print(f"  ok={res.get('ok')} reverted={res.get('reverted')} bad_marker_absent={bad_marker not in after} prior_edit_kept={'Control Center' in after} -> revert_ok={reverted_ok}", flush=True)

n_ok = sum(1 for r in results if r["applied"])
print(f"\nACCURACY: {n_ok}/{len(GOOD)} good edits applied+built; auto-revert {'OK' if reverted_ok else 'FAILED'}", flush=True)
json.dump({"good": results, "revert_ok": reverted_ok, "accuracy": f"{n_ok}/{len(GOOD)}"},
          open("_test_edit.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("-> _test_edit.json", flush=True)
