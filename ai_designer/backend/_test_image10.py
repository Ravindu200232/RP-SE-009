"""10-image-replace accuracy test for the deterministic image pipeline.
Each case clicks a real image component and uploads a new file; set_component_image
must (1) save a fresh asset, (2) surgically repoint that component's src in source,
(3) keep the file compiling (@babel via _commit). The source file is restored after
every case so results don't compound, and all created assets are cleaned up.

A case PASSES when ok=True AND the new src is actually present in the source file
(true substitution) - i.e. NOT the in-place overwrite fallback."""
import os, sys, time, json, base64, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import editor

PID = "prj_iv_school"
OUT = os.path.join("output", PID)
ASSETS = os.path.join(OUT, "public", "assets")

# a real, valid JPEG to use as the "uploaded" bytes
seed = next((p for p in glob.glob(os.path.join(ASSETS, "*.jpg"))
             if not os.path.basename(p).startswith("img_")), None)
UP_B64 = base64.b64encode(open(seed, "rb").read()).decode() if seed else ""

# (component_id, current src) - real elements across pages, components and the shared-asset case
CASES = [
    ("page-courses",          "/assets/hero.jpg"),
    ("page-courses",          "/assets/gallery1.jpg"),
    ("page-courses",          "/assets/about1.jpg"),
    ("navbar",                "/assets/logo.jpg"),
    ("hero",                  "/assets/banner.jpg"),
    ("hero",                  "/assets/about1.jpg"),
    ("page-events-calendar",  "/assets/feature1.jpg"),
    ("page-exams",            "/assets/about1.jpg"),
    ("page-teacher-portal",   "/assets/banner.jpg"),
    ("sidebar",               "/assets/logo.jpg"),
]

before = set(glob.glob(os.path.join(ASSETS, "img_*")))
results = []
for i, (cid, src) in enumerate(CASES, 1):
    rel, path = editor.resolve_component_file(OUT, cid)
    snap = open(path, encoding="utf-8").read() if path and os.path.exists(path) else None
    t = time.time()
    try:
        r = editor.set_component_image(PID, cid, src, data_b64=UP_B64)
    except Exception as e:
        r = {"ok": False, "error": "EXC " + str(e)[:120]}
    secs = round(time.time() - t, 2)

    new_src = r.get("src", "")
    after = open(path, encoding="utf-8").read() if path and os.path.exists(path) else ""
    substituted = bool(new_src) and new_src != src and new_src in after
    file_made = bool(new_src) and os.path.exists(os.path.join(ASSETS, os.path.basename(new_src)))
    # PASS = applied, compiles, AND it was a true src substitution (not the overwrite fallback)
    ok = bool(r.get("ok")) and substituted and file_made

    if snap is not None:                       # restore the source file (non-destructive)
        with open(path, "w", encoding="utf-8") as f:
            f.write(snap)
    results.append({"n": i, "cid": cid, "src": src, "file": rel, "ok": ok,
                    "mode": r.get("mode"), "substituted": substituted, "secs": secs,
                    "error": r.get("error")})
    print(f"{i:2} ok={ok!s:5} mode={(r.get('mode') or '-'):16} sub={substituted!s:5} "
          f"{secs:5}s | {cid:20} {src}", flush=True)

# cleanup every asset this test created
for p in set(glob.glob(os.path.join(ASSETS, "img_*"))) - before:
    try: os.remove(p)
    except OSError: pass

okc = sum(1 for r in results if r["ok"])
print("\n" + "=" * 64)
print(f"IMAGE REPLACE ACCURACY: {okc}/{len(results)} = {100*okc/len(results):.0f}%")
print(f"  avg {sum(r['secs'] for r in results)/len(results):.2f}s  "
      f"(true substitution: {sum(1 for r in results if r['substituted'])}/{len(results)})")
fails = [r for r in results if not r["ok"]]
if fails:
    print("FAILURES:")
    for r in fails:
        print(f"  #{r['n']} {r['cid']} {r['src']} -> mode={r['mode']} err={r['error']}")
json.dump(results, open("_test_image10.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("-> _test_image10.json")
