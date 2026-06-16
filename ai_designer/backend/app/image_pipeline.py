"""Robust post-image build flow (the literal, cache-busted design - NOT same-path
overwrite, which can't prove the app still builds after the src changes).

Order (matches the architecture spec):
  1. app generated with placeholder images        (nextgen.seed_placeholder_images)
  2. first JSX/TS validation                       (validate_all_pages)
  3. first Next.js build                           (nextgen.run_build)        <- caller
  4. generate real images with Fooocus             (fooocus_images.generate_one)
  5. save each as a NEW cache-busted file          public/assets/img_<rand>.jpg
  6. surgically repoint that image's src refs      (swap_image_src)
  7. validate every changed file                   (editor._validate, per file)
  8. second build proves the post-image app builds (nextgen.run_build)
  9. on ANY failure, rollback to the placeholder src + rebuild  (run_post_image_flow)

Everything except the Fooocus call is deterministic + unit-testable (pass a real
image file in place of a generated one).
"""
import os
import shutil

from app import nextgen
from app.editor import _validate          # @babel/parser single-file validator (reused)

_PAGE_EXTS = (".jsx", ".tsx", ".js", ".ts")
_IMG_MAGIC = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"RIFF", b"GIF87a", b"GIF89a")


def validate_image_file(path: str) -> bool:
    """A generated image is VALID only if it exists, is non-trivial (>= 1KB), and
    starts with a real image magic number (JPEG/PNG/WEBP/GIF). Catches 0-byte and
    half-written Fooocus outputs before they ever reach the app."""
    try:
        if not os.path.isfile(path) or os.path.getsize(path) < 1024:
            return False
        with open(path, "rb") as f:
            head = f.read(12)
        return head.startswith(_IMG_MAGIC[:3]) or head[:8] == _IMG_MAGIC[1] or \
            head[:4] == b"RIFF" or head[:6] in (b"GIF87a", b"GIF89a")
    except OSError:
        return False


def _page_files(out_dir: str) -> list:
    out = []
    src = os.path.join(out_dir, "src")
    for dp, _dirs, fns in os.walk(src):
        for fn in fns:
            if fn.endswith(_PAGE_EXTS):
                out.append(os.path.join(dp, fn))
    return out


def validate_all_pages(out_dir: str) -> tuple:
    """Step 2: fast per-file JSX validation of every page/component BEFORE the build,
    so syntax errors are caught in ~1s/file instead of a 60-90s build. Returns
    (ok, [(rel, error), ...])."""
    bad = []
    for path in _page_files(out_dir):
        ok, err = _validate(path)
        if not ok:
            bad.append((os.path.relpath(path, out_dir), err))
    return (len(bad) == 0, bad)


def swap_image_src(out_dir: str, old_src: str, new_src: str) -> tuple:
    """Step 6-7: replace every literal `old_src` with `new_src` across page files,
    VALIDATING each changed file. Returns (ok, backups=[(path, original_text)]).
    On a validation failure it rolls back the files it already changed -> (False, [])."""
    backups = []
    for path in _page_files(out_dir):
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue
        if old_src not in text:
            continue
        backups.append((path, text))
        with open(path, "w", encoding="utf-8") as f:
            f.write(text.replace(old_src, new_src))
        ok, _err = _validate(path)
        if not ok:                                   # rollback everything touched so far
            for p, orig in backups:
                with open(p, "w", encoding="utf-8") as f:
                    f.write(orig)
            return False, []
    return True, backups


def apply_real_image(out_dir: str, slot_name: str, source_image: str) -> dict:
    """Steps 5-7 for ONE image: validate the generated file, copy it to a cache-busted
    name, and repoint `/assets/<slot_name>` -> the new path (validated). Deterministic
    (no Fooocus) so it is fully unit-testable. Returns {ok, new_src, files, backups}."""
    assets = os.path.join(out_dir, "public", "assets")
    if not validate_image_file(source_image):
        return {"ok": False, "error": f"invalid generated image for {slot_name}"}
    ext = os.path.splitext(slot_name)[1] or ".jpg"
    new_name = "img_" + os.urandom(6).hex() + ext           # cache-busted
    new_path = os.path.join(assets, new_name)
    try:
        shutil.copyfile(source_image, new_path)
    except OSError as e:
        return {"ok": False, "error": f"could not save image: {e}"}
    if not validate_image_file(new_path):
        _silent_remove(new_path)
        return {"ok": False, "error": "saved image failed validation"}
    ok, backups = swap_image_src(out_dir, "/assets/" + slot_name, "/assets/" + new_name)
    if not ok:
        _silent_remove(new_path)
        return {"ok": False, "error": f"src swap produced invalid JSX for {slot_name} (rolled back)"}
    return {"ok": True, "slot": slot_name, "new_src": "/assets/" + new_name,
            "files": [p for p, _ in backups], "backups": backups}


def _fooocus_pairs(out_dir: str, app_name: str, prompt: str) -> list:
    """Generate each real image with Fooocus to a temp file -> [(slot, tmp_path)].
    Isolated from the apply/build/rollback logic so the flow is testable without Fooocus."""
    assets = os.path.join(out_dir, "public", "assets")
    from app import fooocus_images
    if not fooocus_images.ensure_fooocus():
        return []
    fooocus_images._unload_llm()
    try:
        jobs = fooocus_images.build_jobs_v2(out_dir, app_name, prompt)
    except Exception:
        return []
    pairs = []
    for job in jobs:
        slot = os.path.basename(job["out"])
        tmp = os.path.join(assets, "_gen_" + slot)
        try:
            if fooocus_images.generate_one(tmp, job["prompt"], job.get("aspect", "landscape")):
                pairs.append((slot, tmp))
        except Exception:
            continue
    return pairs


def run_post_image_flow(out_dir: str, app_name: str, prompt: str, generate: bool = True,
                        pre_generated=None) -> dict:
    """Steps 4-9 orchestrated. `pre_generated` (list of (slot, image_path)) bypasses
    Fooocus - used by tests and any caller that already has images. Otherwise images
    are generated via Fooocus (unless AI_DESIGNER_FAST/generate is off). Each is
    cache-busted + surgically swapped, then the SECOND build runs; on failure every src
    change is rolled back to the placeholder and a final build restores a good app."""
    applied, all_backups, cleanup = [], [], []
    if pre_generated is not None:
        pairs = list(pre_generated)
    elif generate and not os.getenv("AI_DESIGNER_FAST"):
        pairs = _fooocus_pairs(out_dir, app_name, prompt)
        cleanup = [p for _s, p in pairs]              # remove Fooocus temps afterwards
    else:
        pairs = []

    for slot, src_img in pairs:
        try:
            r = apply_real_image(out_dir, slot, src_img)
            if r.get("ok"):
                applied.append(r)
                all_backups += r["backups"]
        except Exception:
            continue
    for tmp in cleanup:
        _silent_remove(tmp)

    # Step 8: the SECOND build proves the app still compiles after the src swaps.
    ok, _out = nextgen.run_build(out_dir)
    if not ok:
        for path, orig in reversed(all_backups):      # Step 9: rollback to placeholder src
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(orig)
            except OSError:
                pass
        nextgen.run_build(out_dir)                     # restore a known-good build
        return {"ok": False, "applied": 0, "rolled_back": len(all_backups),
                "error": "post-image build failed - rolled back to placeholders"}
    return {"ok": True, "applied": len(applied), "images": [a["new_src"] for a in applied]}


def _silent_remove(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
