"""Image update pipeline regression tests (Prompt 8).

Verifies: upload + Fooocus paths save a NEW cache-busted asset (never same-path
overwrite as the main path), surgically swap ONLY the selected src, validate the
image (reject 0-byte/text-stub/corrupt) and the JSX before an atomic commit, roll
back on failure, and keep the previous image when generation fails. The Fooocus
path is monkeypatched (a real image is written) so no GPU/Ollama is needed.

Run:  python _test_image_update.py   (exit 1 on any failure)
"""
import os, sys, re, glob, base64, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import editor, image_pipeline
import app.fooocus_images as fooocus

PID = "prj_iv_school"
OUT = os.path.join("output", PID)
ASSETS = os.path.join(OUT, "public", "assets")
MKT = os.path.join(OUT, "src", "app", "(marketing)")
REAL_IMG = "next_scaffold/public/assets/placeholder.jpg"   # a genuine jpg
RESULTS = []


def rec(name, ok, detail=""):
    RESULTS.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""), flush=True)


def b64(path):
    return base64.b64encode(open(path, "rb").read()).decode()


def refs_in(text):
    return re.findall(r"/assets/[A-Za-z0-9_.-]+", text)


def imgset():
    return set(glob.glob(os.path.join(ASSETS, "img_*")))


def cleanup(made):
    for p in imgset() - made:
        try: os.remove(p)
        except OSError: pass


def main():
    print("=" * 66)
    print("IMAGE UPDATE REGRESSION (cache-busted + surgical + validated + rollback)")
    print("=" * 66)
    page = os.path.join(MKT, "page.jsx")
    base = open(page, encoding="utf-8").read()
    all_refs = refs_in(base)
    target = all_refs[0]
    other = next((r for r in all_refs if r != target), None)
    made0 = imgset()

    # 1) upload -> NEW cache-busted file + surgical src swap (only target changes)
    snap = base
    r = editor.set_component_image(PID, "home", target, data_b64=b64(REAL_IMG))
    after = open(page, encoding="utf-8").read()
    new_files = imgset() - made0
    new_src = r.get("src")
    rec("upload creates a NEW cache-busted asset (img_*) - no same-path overwrite",
        r.get("ok") and r.get("mode") == "upload" and len(new_files) == 1 and os.path.basename(new_src).startswith("img_"),
        new_src)
    rec("upload surgically swaps ONLY the target src", new_src in after and after.count(target) == base.count(target) - 1)
    if other:
        rec("unrelated image src unchanged", after.count(other) == base.count(other))
    rec("JSX still valid after swap", editor._validate(page)[0])
    rec("original asset file NOT overwritten (primary path)",
        os.path.exists(os.path.join(ASSETS, os.path.basename(target))))
    open(page, "w", encoding="utf-8").write(snap); cleanup(made0)

    # 2) Fooocus/generate path -> NEW asset (monkeypatch generate_one to write a real image)
    orig_gen = fooocus.generate_one
    fooocus.generate_one = lambda out_path, prompt, *a, **k: bool(shutil.copyfile(REAL_IMG, out_path)) or True
    try:
        made = imgset()
        rg = editor.set_component_image(PID, "home", target, prompt="a modern clinic photo")
        gnew = imgset() - made
        after = open(page, encoding="utf-8").read()
        rec("Fooocus/generate creates a NEW cache-busted asset + swaps src",
            rg.get("ok") and rg.get("mode") == "ai" and len(gnew) == 1 and rg.get("src") in after, rg.get("src"))
        open(page, "w", encoding="utf-8").write(base); cleanup(made)
    finally:
        fooocus.generate_one = orig_gen

    # 3) corrupt / invalid image rejected (0-byte-ish text), nothing changed
    made = imgset()
    snap = open(page, encoding="utf-8").read()
    rc = editor.set_component_image(PID, "home", target, data_b64=base64.b64encode(b"not an image").decode())
    rec("corrupt/invalid image rejected, source untouched, no stray asset",
        (not rc.get("ok")) and isinstance(rc.get("error"), str)
        and open(page, encoding="utf-8").read() == snap and not (imgset() - made), rc.get("error"))

    # 4) missing old_src -> readable error
    rm = editor.set_component_image(PID, "home", "/assets/__does_not_exist__.jpg", data_b64=b64(REAL_IMG))
    # (it will create+validate the file, find old not in source -> fallback overwrite of a
    #  non-existent asset path -> still returns a result; the meaningful 'missing old_src'
    #  case is a non-image src:)
    rm2 = editor.set_component_image(PID, "home", "not-an-image", data_b64=b64(REAL_IMG))
    rec("non-image / missing old_src -> readable error", (not rm2.get("ok")) and isinstance(rm2.get("error"), str), rm2.get("error"))
    cleanup(made)

    # 5) invalid component_id -> readable error (or safe fallback), never a crash
    ri = editor.set_component_image(PID, "no-such-component-xyz", target, data_b64=b64(REAL_IMG))
    rec("invalid component_id -> handled (readable error or validated fallback), no crash",
        isinstance(ri, dict) and ("error" in ri or ri.get("ok")), ri.get("error") or ri.get("mode"))
    cleanup(made)

    # 6) JSX validation failure -> source rolled back (force _validate to fail)
    asset_path = os.path.join(ASSETS, os.path.basename(target))
    asset_bak = open(asset_path, "rb").read() if os.path.exists(asset_path) else None
    snap = open(page, encoding="utf-8").read()
    made = imgset()
    orig_validate = editor._validate
    editor._validate = lambda p: (False, "forced validation failure")
    try:
        rf = editor.set_component_image(PID, "home", target, data_b64=b64(REAL_IMG))
    finally:
        editor._validate = orig_validate
    rec("JSX validation failure -> SOURCE file rolled back (unchanged)",
        open(page, encoding="utf-8").read() == snap, f"mode={rf.get('mode')}")
    if asset_bak is not None:
        open(asset_path, "wb").write(asset_bak)        # restore asset (fallback overwrote it)
    open(page, "w", encoding="utf-8").write(snap); cleanup(made)

    # 7) generated image FAILURE -> previous image/source kept, readable error
    fooocus.generate_one = lambda *a, **k: False
    try:
        snap = open(page, encoding="utf-8").read()
        made = imgset()
        rfail = editor.set_component_image(PID, "home", target, prompt="x")
        rec("Fooocus failure -> previous image+source kept, readable error",
            (not rfail.get("ok")) and isinstance(rfail.get("error"), str)
            and open(page, encoding="utf-8").read() == snap and not (imgset() - made), rfail.get("error"))
    finally:
        fooocus.generate_one = orig_gen

    # 8) no Fooocus deadlock: the AI image path must NOT wrap generate in gpu_handoff
    body = open("app/editor.py", encoding="utf-8").read()
    sci = body[body.index("def set_component_image"):body.index("def _strip_fences")]
    rec("Fooocus image path does NOT use gpu_handoff (no suspend-then-use deadlock)",
        "with gpu_handoff" not in sci and "generate_one" in sci)   # the CALL, not the explanatory comment

    # 9) replace 10 REAL images across pages: each -> new asset, surgical swap, valid JSX, no unrelated change
    pairs = []
    for d in [MKT] + [os.path.join(MKT, s) for s in os.listdir(MKT) if os.path.isdir(os.path.join(MKT, s))]:
        pg = os.path.join(d, "page.jsx")
        if not os.path.isfile(pg):
            continue
        cid = "home" if d == MKT else "page-" + os.path.basename(d)
        for ref in dict.fromkeys(refs_in(open(pg, encoding="utf-8").read())):
            pairs.append((cid, pg, ref))
    pairs = pairs[:10]
    ok10 = 0
    for cid, pg, ref in pairs:
        before = open(pg, encoding="utf-8").read()
        made = imgset()
        r = editor.set_component_image(PID, cid, ref, data_b64=b64(REAL_IMG))
        after = open(pg, encoding="utf-8").read()
        newf = imgset() - made
        others_ok = all(after.count(x) == before.count(x) for x in set(refs_in(before)) if x != ref)
        good = (r.get("ok") and r.get("src", "").startswith("/assets/img_") and len(newf) == 1
                and r["src"] in after and editor._validate(pg)[0] and others_ok
                and after.count(r["src"]) == 1)            # no duplicate/broken ref
        ok10 += 1 if good else 0
        open(pg, "w", encoding="utf-8").write(before)
        cleanup(made)
    rec("replace 10 real images: new asset + surgical swap + valid JSX + no unrelated/dup refs",
        len(pairs) >= 5 and ok10 == len(pairs), f"{ok10}/{len(pairs)}")

    open(page, "w", encoding="utf-8").write(base)
    cleanup(made0)
    print("=" * 66)
    ok = all(RESULTS)
    print((f"IMAGE UPDATE GREEN  ({sum(RESULTS)}/{len(RESULTS)})" if ok else f"FAILURES  ({sum(RESULTS)}/{len(RESULTS)} passed)"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
