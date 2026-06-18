"""50-prompt accuracy test for the Isolated Block Patch edit pipeline.
Each prompt targets a real element (by its literal className) on a built page;
the page is restored to baseline before every prompt so results don't compound.
A result counts as PASS when ok=True (every path validates with @babel before the
atomic write, so ok=True == applied + compiles)."""
import os, sys, re, time, json, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import editor

PID = "prj_iv_school"
PAGE = os.path.join("output", PID, "src", "app", "(marketing)", "courses", "page.jsx")
CID = "page-courses"
src0 = open(PAGE, encoding="utf-8").read()


def find_el(tag, contains):
    m = re.search(r'<' + tag + r'\b[^>]*className="([^"]*' + re.escape(contains) + r'[^"]*)"', src0)
    return {"tag": tag, "class_name": m.group(1)} if m else {"tag": tag, "class_name": ""}


H1 = find_el("h1", "text-4xl")
P = find_el("p", "text-lg")
BTN = find_el("a", "bg-primary")
H2 = find_el("h2", "text-3xl")

STYLE = [
    "change the text color to red", "make the background blue", "make it bigger", "make it smaller",
    "make it bold", "make it lighter", "center the text", "align it to the right", "add rounded corners",
    "make it a pill shape", "add a big shadow", "add more padding", "make it compact", "add a glass effect",
    "make it glassmorphism", "uppercase the text", "make it italic", "underline it", "change color to emerald",
    "use a dark background", "make the text purple", "add a gradient text effect", "make the text huge",
    "navy blue background", "rose text color", "add more margin", "make it full width", "teal text color",
    "amber background", "add a drop shadow",
]
REDESIGN = [
    "add a call-to-action button below this", "add a small subtitle under it",
    "turn this into a two-column layout", "add three bullet points", "wrap this in a bordered card",
    "add a New badge next to it", "add a divider line below", "rewrite the copy to be more exciting",
    "redesign this as a centered hero", "add an arrow icon after the text", "make this a short quote",
    "add a thin border around it", "add a light background card behind it", "split this into two paragraphs",
    "add a Learn more link below", "make the heading larger and add a tagline",
    "convert this into a highlighted callout box", "shorten this text", "add a subtle hover effect",
    "add the word Featured before it",
]

cases = ([(STYLE[i], [H1, P, BTN, H2][i % 4], "style") for i in range(len(STYLE))]
         + [(REDESIGN[i], [H1, BTN, P, H2][i % 4], "redesign") for i in range(len(REDESIGN))])

results = []
for i, (prompt, el, kind) in enumerate(cases, 1):
    with open(PAGE, "w", encoding="utf-8") as f:   # restore baseline before each
        f.write(src0)
    t = time.time()
    try:
        r = editor.edit_component(PID, CID, prompt, tag=el["tag"], text=None, class_name=el["class_name"])
    except Exception as e:
        r = {"ok": False, "error": "EXC " + str(e)[:100]}
    secs = round(time.time() - t, 1)
    results.append({"n": i, "kind": kind, "prompt": prompt, "el": el["tag"],
                    "ok": bool(r.get("ok")), "mode": r.get("mode"), "secs": secs, "error": r.get("error")})
    print(f"{i:2} [{kind:8}] ok={r.get('ok')} mode={r.get('mode') or '-':14} {secs:5}s | {prompt[:46]}", flush=True)

with open(PAGE, "w", encoding="utf-8") as f:
    f.write(src0)   # leave the page as we found it

st = [r for r in results if r["kind"] == "style"]
rd = [r for r in results if r["kind"] == "redesign"]
okc = sum(1 for r in results if r["ok"])
print("\n" + "=" * 60)
print(f"TOTAL: {okc}/{len(results)} = {100*okc/len(results):.0f}%")
print(f"  STYLE_TWEAK : {sum(1 for r in st if r['ok'])}/{len(st)} (avg {sum(r['secs'] for r in st)/len(st):.1f}s)")
print(f"  REDESIGN    : {sum(1 for r in rd if r['ok'])}/{len(rd)} (avg {sum(r['secs'] for r in rd)/len(rd):.1f}s)")
fails = [r for r in results if not r["ok"]]
if fails:
    print("FAILURES:")
    for r in fails:
        print(f"  #{r['n']} [{r['kind']}] {r['prompt'][:50]} -> {r['error']}")
json.dump(results, open("_test_edit50.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("-> _test_edit50.json")
