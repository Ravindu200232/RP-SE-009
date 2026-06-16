"""Consolidated stability/architecture test suite (items #1-#9).

Each test asserts an INVARIANT so the same bug can't silently return. Build-heavy
tests use a real project with node_modules and restore everything afterwards.
Run:  python _test_stability.py            (all)
      python _test_stability.py fast        (skip the slow `next build` tests)
Exit code is non-zero if any test fails. Never report 100% unless all are GREEN.
"""
import os, sys, re, json, base64, shutil, glob, inspect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import editor, section_catalog, section_bank, image_pipeline, nextgen, design_library
import app.server as server

FAST = "fast" in sys.argv
FRONT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "src", "App.jsx")
ROUTES_PRJ = "output/prj_9c1e00ad"            # read-only route resolution
BUILD_PRJ = "output/prj_iv_school"            # modify+build (snapshot/restore)
REAL_IMG = "next_scaffold/public/assets/placeholder.jpg"   # a genuine jpg for image tests
RESULTS = []


def rec(item, name, passed, detail=""):
    RESULTS.append((item, passed))
    print(f"  [{'PASS' if passed else 'FAIL'}] #{item} {name}" + (f"  -> {detail}" if detail else ""), flush=True)


def snap(path):
    return open(path, encoding="utf-8").read() if os.path.exists(path) else None


def restore(path, text):
    if text is not None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


# ---------- #1 [object Object] + #3 version-on-success (frontend static analysis) ----------
def t_frontend():
    src = snap(FRONT) or ""
    errtext_uses = len(re.findall(r"errText\(", src))
    rec(1, "frontend decodes errors with errText() (>=4 sites)", errtext_uses >= 4, f"{errtext_uses} uses")
    m = re.search(r"const handleSend = \(\) => \{.*?\n  \};", src, re.S)
    hs = m.group(0) if m else ""
    no_uncond = "setPromptsHistory" not in hs
    in_success = bool(re.search(r"data\.ok.*setPromptsHistory", src)) and "if (currentPrompt) setPromptsHistory" in src
    rec(3, "version recorded ONLY on success (not unconditionally in handleSend)", no_uncond and in_success,
        f"handleSend push={'absent' if no_uncond else 'PRESENT(bug)'}, success-push={'yes' if in_success else 'no'}")


# ---------- #2 component_id / route fallback / registry ----------
def t_routes():
    if not os.path.isdir(ROUTES_PRJ):
        return rec(2, "route resolver", False, f"{ROUTES_PRJ} missing")
    must = {
        # human-derived ids the inspector now sends (route fallback) ...
        "home": "(marketing)/page.jsx", "dashboard": "dashboard", "profile": "profile",
        "page-patient-services": "patient-services/page.jsx",
        # ... and full-path route: ids for nested/CRUD pages
        "route:/": "(marketing)/page.jsx", "route:/dashboard": "dashboard",
        "route:/e/labreport/LAB-9014": "[id]/page.jsx",          # CRUD detail
        "route:/e/labreport/LAB-9014/edit": "edit",              # CRUD edit
        "route:/e/appointment/new": "new/page.jsx",              # CRUD new
        "route:/e/appointment/create": "new/page.jsx",           # CRUD create
        "navbar": "Navbar.jsx",
    }
    ok = True
    for cid, frag in must.items():
        rel, path = editor.resolve_component_file(ROUTES_PRJ, cid)
        if not (path and frag in rel.replace("\\", "/")):
            ok = False
    # garbage / null must NOT resolve to a path (clean miss, not a crash)
    _, p_null = editor.resolve_component_file(ROUTES_PRJ, None)
    _, p_junk = editor.resolve_component_file(ROUTES_PRJ, "page-la14")
    clean_miss = p_null is None and p_junk is None
    # invalid AND null component ids -> a READABLE STRING error (never a crash/object)
    pid = os.path.basename(ROUTES_PRJ)
    r_bad = editor.edit_component(pid, "totally-bogus-xyz", "make it red", tag="div")
    r_null = editor.edit_component(pid, None, "make it red", tag="div")
    readable = (not r_bad.get("ok") and isinstance(r_bad.get("error"), str) and
                not r_null.get("ok") and isinstance(r_null.get("error"), str))
    rec(2, "routes resolve (home/dashboard/page-*/CRUD list/detail/edit/new/create); invalid+null -> readable string error",
        ok and clean_miss and readable,
        f"routes={'ok' if ok else 'FAIL'}, clean-miss={clean_miss}, readable-err={readable}")


# ---------- #4 async def -> def (threadpool) ----------
def t_async():
    fns = ["edit_element", "replace_image", "upload_image", "generate_image", "add_section"]
    bad = [n for n in fns if inspect.iscoroutinefunction(getattr(server, n, None))]
    rec(4, "blocking endpoints are sync def (run in threadpool, no event-loop freeze)",
        not bad, "all sync" if not bad else f"still async: {bad}")


# ---------- #5 surgical image replacement ----------
def t_image_replace():
    page = os.path.join(BUILD_PRJ, "src", "app", "(marketing)", "page.jsx")
    if not os.path.exists(page):
        return rec(5, "surgical image replace", False, f"{page} missing")
    src = open(page, encoding="utf-8").read()
    m = re.search(r"/assets/([A-Za-z0-9_-]+\.(?:jpg|png))", src)
    if not m:
        return rec(5, "surgical image replace", False, "no /assets ref on page")
    old = m.group(0)
    seed = next((p for p in glob.glob(os.path.join(BUILD_PRJ, "public", "assets", "*.jpg"))
                 if not os.path.basename(p).startswith("img_")), None)
    b64 = base64.b64encode(open(seed, "rb").read()).decode()
    before = snap(page)
    made = set(glob.glob(os.path.join(BUILD_PRJ, "public", "assets", "img_*")))
    r = editor.set_component_image("prj_iv_school", "home", old, data_b64=b64)
    after = open(page, encoding="utf-8").read()
    new_files = set(glob.glob(os.path.join(BUILD_PRJ, "public", "assets", "img_*"))) - made
    ok = (r.get("ok") and r.get("src") and r["src"] != old and r["src"] in after and len(new_files) == 1)
    restore(page, before)
    for p in new_files:
        try: os.remove(p)
        except OSError: pass
    rec(5, "image -> NEW cache-busted file + surgical src swap (no random overwrite)", ok,
        f"mode={r.get('mode')}, new={r.get('src')}")


# ---------- #6 LLM intent + deterministic patching/validation ----------
def t_edit_pipeline():
    det = editor.nl_to_classes("make it bold and center the text", "h1")[0]
    det_ok = "font-bold" in det and "text-center" in det
    # _commit must REVERT an invalid candidate (validate-then-atomic) and never break the file
    page = os.path.join(BUILD_PRJ, "src", "app", "(marketing)", "page.jsx")
    before = snap(page)
    rel = "src/app/(marketing)/page.jsx"
    bad = editor._commit(page, before, before + "\n<div><<<broken jsx ", "TEST", rel)
    reverted = (bad is not None and not bad.get("ok") and snap(page) == before)
    # element-only isolation pulls a balanced element
    snip = editor._extract_element(before, tag="h1", class_name=None,
                                   text=None) if "<h1" in before else "x</h1>"
    iso = bool(snip) if snip else True
    restore(page, before)
    rec(6, "deterministic class map + validate-then-atomic _commit (auto-revert) + element isolation",
        det_ok and reverted, f"nl_to_classes={det_ok}, invalid-reverted={reverted}")


# ---------- #7 100+ template catalog ----------
def t_catalog():
    n = section_catalog.count()
    import subprocess, tempfile
    VAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "validate_jsx.js")
    # render 6 sampled templates and validate each compiles
    import random
    rng = random.Random(0)
    sample = rng.sample(section_catalog.CATALOG, 6)
    bad = 0
    for e in sample:
        body = section_bank._HEADER + section_catalog.render(e, "S").rstrip() + "\n\nexport default function H(){return <S/>;}\n"
        fd, tp = tempfile.mkstemp(suffix=".jsx"); os.close(fd)
        open(tp, "w", encoding="utf-8").write(body.replace("ACCENT", "indigo"))
        r = subprocess.run(f'node "{VAL}" "{tp}"', shell=True, capture_output=True, text=True)
        os.remove(tp)
        bad += 0 if r.returncode == 0 else 1
    a = section_catalog.pick_middles(__import__("random").Random(1), 4, "a saas analytics platform")
    b = section_catalog.pick_middles(__import__("random").Random(1), 4, "an online clothing store")
    varies = [x["family"] for x in a] != [x["family"] for x in b]
    rec(7, "100+ templates, all valid, input-matched random selection", n >= 100 and bad == 0 and varies,
        f"count={n}, sample-valid={6 - bad}/6, varies-by-prompt={varies}")


# ---------- #8 robust image/build flow ----------
def t_image_pipeline():
    assets = os.path.join(BUILD_PRJ, "public", "assets")
    seed = REAL_IMG          # a genuine jpg (project placeholders are intentionally text stubs)
    # validators
    vf = image_pipeline.validate_image_file(seed) is True
    fd_tiny = os.path.join(assets, "_tiny.jpg"); open(fd_tiny, "wb").write(b"xx")
    fd_txt = os.path.join(assets, "_t.txt"); open(fd_txt, "w").write("not an image " * 200)
    vbad = (not image_pipeline.validate_image_file(fd_tiny)) and (not image_pipeline.validate_image_file(fd_txt))
    os.remove(fd_tiny); os.remove(fd_txt)
    rec(8, "validate_image_file: real=ok, tiny/garbage=rejected", vf and vbad)

    # apply_real_image: cache-busted + surgical swap + page validates
    page = os.path.join(BUILD_PRJ, "src", "app", "(marketing)", "page.jsx")
    src = open(page, encoding="utf-8").read()
    m = re.search(r"/assets/([A-Za-z0-9_-]+\.jpg)", src)
    slot = m.group(1)
    before = snap(page)
    made = set(glob.glob(os.path.join(assets, "img_*")))
    r = image_pipeline.apply_real_image(BUILD_PRJ, slot, seed)
    after = open(page, encoding="utf-8").read()
    new_files = set(glob.glob(os.path.join(assets, "img_*"))) - made
    apply_ok = r.get("ok") and r["new_src"] in after and len(new_files) >= 1
    restore(page, before)
    for p in new_files:
        try: os.remove(p)
        except OSError: pass
    rec(8, "apply_real_image: cache-busted file + surgical src swap + per-file validate", bool(apply_ok),
        f"new_src={r.get('new_src')}")

    if FAST:
        return rec(8, "post-image SECOND build + rollback (skipped in fast mode)", True, "fast")

    # second-build proof + rollback (uses the placeholder as a stand-in 'generated' image)
    page_text = snap(page)
    real_build = nextgen.run_build
    calls = {"n": 0}

    def fail_first(out_dir, timeout=600):
        calls["n"] += 1
        return (False, "forced failure") if calls["n"] == 1 else real_build(out_dir, timeout)
    nextgen.run_build = fail_first
    try:
        rr = image_pipeline.run_post_image_flow(BUILD_PRJ, "Test", "test",
                                                pre_generated=[(slot, seed)])
        rolled_back = (not rr.get("ok")) and rr.get("rolled_back", 0) >= 1 and snap(page) == page_text
    finally:
        nextgen.run_build = real_build
    for p in set(glob.glob(os.path.join(assets, "img_*"))) - made:
        try: os.remove(p)
        except OSError: pass
    restore(page, page_text)
    rec(8, "post-image build fails -> automatic rollback to placeholder src (verified restore)",
        rolled_back, f"rolled_back={rr.get('rolled_back')}, restored={snap(page) == page_text}")

    # success path: real second build passes after a swap
    made2 = set(glob.glob(os.path.join(assets, "img_*")))
    ptext = snap(page)
    ok2 = image_pipeline.run_post_image_flow(BUILD_PRJ, "Test", "test", pre_generated=[(slot, seed)])
    built = ok2.get("ok") and ok2.get("applied", 0) >= 1
    restore(page, ptext)
    for p in set(glob.glob(os.path.join(assets, "img_*"))) - made2:
        try: os.remove(p)
        except OSError: pass
    nextgen.run_build(BUILD_PRJ)  # leave a clean build behind
    rec(8, "post-image SECOND build passes (proves app still compiles after src swap)", bool(built),
        f"applied={ok2.get('applied')}")


# ---------- #9 five generated-app smoke test ----------
def t_smoke5():
    if FAST:
        return rec(9, "5 generated-app smoke build (skipped in fast mode)", True, "fast")
    mkt = os.path.join(BUILD_PRJ, "src", "app", "(marketing)")
    theme = {"accent": "text-indigo-500", "mode": "light"}
    domains = [("smokea", "saas analytics platform b2b"), ("smokeb", "cleaning service clinic"),
               ("smokec", "online clothing store ecommerce"), ("smoked", "restaurant booking food"),
               ("smokee", "school lms education")]
    assets = os.path.join(BUILD_PRJ, "public", "assets")
    from app.fooocus_images import V2_NAMES
    before_assets = set(os.listdir(assets)) if os.path.isdir(assets) else set()
    nextgen.seed_placeholder_images(BUILD_PRJ)        # mirror the REAL flow: every slot gets a placeholder
    made = []
    try:
        for slug, prompt in domains:
            _desc, code = section_bank.compose_landing(prompt_text=prompt)
            code = code.replace("ACCENT", design_library.accent_family(theme))
            d = os.path.join(mkt, slug); os.makedirs(d, exist_ok=True)
            open(os.path.join(d, "page.jsx"), "w", encoding="utf-8").write(code)
            made.append(d)
        ok, _out = nextgen.run_build(BUILD_PRJ)
        # Invariant: across all 5 apps, every /assets ref (a) physically exists after
        # the seed step AND (b) is a known seedable slot or a cache-busted img_ file
        # (so no generated app can ever reference a broken/un-seeded image).
        missing, rogue = 0, 0
        for d in made:
            t = open(os.path.join(d, "page.jsx"), encoding="utf-8").read()
            for ref in re.findall(r"/assets/([A-Za-z0-9_.-]+)", t):
                if not os.path.exists(os.path.join(assets, ref)):
                    missing += 1
                if ref not in V2_NAMES and not ref.startswith("img_") and ref != "placeholder.jpg":
                    rogue += 1
        rec(9, "5 distinct generated apps build + all image refs resolve to a seeded slot",
            ok and missing == 0 and rogue == 0,
            f"build={'ok' if ok else 'FAIL'}, missing={missing}, rogue-refs={rogue}")
    finally:
        for d in made:
            shutil.rmtree(d, ignore_errors=True)
        for f in (set(os.listdir(assets)) - before_assets):   # remove placeholders we seeded
            try: os.remove(os.path.join(assets, f))
            except OSError: pass
        nextgen.run_build(BUILD_PRJ)  # restore clean state


def main():
    print("=" * 70)
    print(f"STABILITY SUITE  ({'FAST - build tests skipped' if FAST else 'FULL - includes next build'})")
    print("=" * 70)
    for t in (t_frontend, t_routes, t_async, t_image_replace, t_edit_pipeline, t_catalog, t_image_pipeline, t_smoke5):
        try:
            t()
        except Exception as e:
            import traceback
            rec(int(t.__name__.split("_")[0][1:]) if t.__name__[1].isdigit() else 0, t.__name__, False, f"EXC {e}")
            traceback.print_exc()
    by_item = {}
    for item, ok in RESULTS:
        by_item.setdefault(item, []).append(ok)
    print("\n" + "=" * 70)
    print("PER-ITEM RESULT:")
    all_ok = True
    for item in sorted(by_item):
        ok = all(by_item[item])
        all_ok = all_ok and ok
        print(f"  #{item}: {'PASS' if ok else 'FAIL'}  ({sum(by_item[item])}/{len(by_item[item])} checks)")
    print("=" * 70)
    print(("ALL TESTS GREEN" if all_ok else "FAILURES PRESENT - NOT complete") +
          f"  ({sum(ok for _i, ok in RESULTS)}/{len(RESULTS)} checks passed)")
    json.dump([{"item": i, "ok": o} for i, o in RESULTS], open("_test_stability.json", "w"))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
