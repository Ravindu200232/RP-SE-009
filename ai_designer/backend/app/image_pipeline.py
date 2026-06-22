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
import json
import re
import shutil

from app import nextgen
from app.editor import _validate          # @babel/parser single-file validator (reused)

_PAGE_EXTS = (".jsx", ".tsx", ".js", ".ts")
_IMG_MAGIC = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"RIFF", b"GIF87a", b"GIF89a")
ASSET_PLAN_FILE = "_image_asset_plan.json"
_ASSET_REF_RE = re.compile(r"/assets/([A-Za-z0-9_.-]+)")
_GENERATED_REF_RE = re.compile(r"/generated/([A-Za-z0-9_.-]+)")


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


def _source_files(out_dir: str) -> list:
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


def _slug_name(slot_name: str) -> str:
    base, ext = os.path.splitext(os.path.basename(slot_name))
    ext = ext.lower() if ext.lower() in (".jpg", ".jpeg", ".png", ".webp") else ".jpg"
    base = re.sub(r"([a-z])([0-9])$", r"\1-\2", base.lower())
    base = re.sub(r"[^a-z0-9-]+", "-", base).strip("-") or "image"
    return base + (".jpg" if ext == ".jpeg" else ext)


def _aspect_ratio(aspect: str) -> str:
    return {"square": "1:1", "portrait": "4:5", "landscape": "16:9"}.get(str(aspect or "landscape"), "16:9")


def _section_for_ref(src: str, idx: int, slot_name: str) -> tuple:
    before = src[:idx]
    cid = ""
    label = ""
    for m in re.finditer(r'data-component-id="([^"]+)"', before):
        cid = m.group(1)
    for m in re.finditer(r'data-component-label="([^"]+)"', before):
        label = m.group(1)
    if not cid:
        cid = os.path.splitext(os.path.basename(slot_name))[0]
    return (label or cid.replace("-", " ").title(), cid)


def _default_alt(app_name: str, section_name: str, slot_name: str) -> str:
    base = os.path.splitext(os.path.basename(slot_name))[0].replace("-", " ").replace("_", " ")
    if "logo" in base:
        return f"{app_name} logo"
    return f"{app_name} {section_name or base} image"


def _role_for_ref(src: str, idx: int, slot_name: str, section_name: str) -> str:
    window = src[max(0, idx - 320): idx + 420]
    m = re.search(r'data-image-role="([^"]+)"', window)
    if m:
        return m.group(1)
    slot = os.path.basename(slot_name).lower()
    section = str(section_name or "").lower()
    if "hero" in slot or "hero" in section:
        return "hero"
    if any(x in slot + " " + section for x in ("doctor", "team", "staff")):
        return "doctor_team"
    if any(x in slot + " " + section for x in ("department", "facility", "clinic")):
        return "department_facility"
    if any(x in slot + " " + section for x in ("security", "compliance", "audit", "backup")):
        return "security_compliance"
    if any(x in slot + " " + section for x in ("portal", "patient", "lab")):
        return "patient_portal"
    if any(x in slot + " " + section for x in ("dashboard", "reports", "analytics", "feature")):
        return "dashboard_mockup"
    return "supporting_visual"


def build_asset_plan(out_dir: str, app_name: str, prompt: str) -> list:
    """Scan generated source for placeholder image references and produce the
    concrete plan used by the synchronous image integration step."""
    try:
        from app import fooocus_images
        jobs = fooocus_images.build_jobs_v2(out_dir, app_name, prompt)
    except Exception:
        jobs = []
    job_by_slot = {os.path.basename(j.get("out", "")): j for j in jobs}
    generated_dir = os.path.join(out_dir, "public", "generated")
    plan = []
    seen = set()
    for path in _source_files(out_dir):
        try:
            src = open(path, encoding="utf-8").read()
        except OSError:
            continue
        rel = os.path.relpath(path, out_dir).replace("\\", "/")
        for m in _ASSET_REF_RE.finditer(src):
            slot = m.group(1)
            key = (rel, slot, m.start())
            if key in seen:
                continue
            seen.add(key)
            section_name, component = _section_for_ref(src, m.start(), slot)
            role = _role_for_ref(src, m.start(), slot, section_name)
            job = job_by_slot.get(slot) or {}
            out_name = _slug_name(slot)
            public_url = "/generated/" + out_name
            plan.append({
                "section_name": section_name,
                "image_role": role,
                "image_prompt": job.get("prompt") or f"Professional {role.replace('_', ' ')} image for {app_name}: {section_name}. {prompt[:160]}",
                "target_jsx_file": rel,
                "target_component": component,
                "target_placeholder": "/assets/" + slot,
                "output_file_path": os.path.join(generated_dir, out_name),
                "public_url_path": public_url,
                "alt_text": _default_alt(app_name, section_name, slot),
                "aspect_ratio": _aspect_ratio(job.get("aspect", "landscape")),
                "generator_aspect": job.get("aspect", "landscape"),
                "status": "planned",
            })
    return plan


def write_asset_plan(out_dir: str, plan: list) -> None:
    try:
        with open(os.path.join(out_dir, ASSET_PLAN_FILE), "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2)
    except OSError:
        pass


def _pre_generated_map(pre_generated) -> dict:
    out = {}
    if isinstance(pre_generated, dict):
        iterable = pre_generated.items()
    else:
        iterable = pre_generated or []
    for slot, path in iterable:
        key = os.path.basename(str(slot).replace("/assets/", ""))
        out[key] = path
    return out


def _fallback_source(out_dir: str, slot_name: str) -> str:
    for rel in (os.path.join("public", "assets", slot_name),
                os.path.join("public", "assets", "placeholder.jpg")):
        path = os.path.join(out_dir, rel)
        if validate_image_file(path):
            return path
    return ""


def _copy_image(src: str, dst: str) -> bool:
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        return validate_image_file(dst)
    except OSError:
        return False


def _replace_alt_for_url(text: str, url: str, alt: str) -> str:
    safe_alt = str(alt or "").replace('"', "'")[:120]
    pat = re.compile(r'(<img\b(?=[^>]*\bsrc="' + re.escape(url) + r'")[^>]*\balt=")[^"]*(")', re.S)
    text, n = pat.subn(r"\1" + safe_alt + r"\2", text)
    if n:
        return text
    pat2 = re.compile(r'(<img\b(?=[^>]*\bsrc="' + re.escape(url) + r'")[^>]*)(\s*/?>)', re.S)
    return pat2.sub(r'\1 alt="' + safe_alt + r'"\2', text)


def verify_generated_assets(out_dir: str) -> dict:
    refs = sorted(set(
        "/generated/" + m.group(1)
        for path in _source_files(out_dir)
        for m in _GENERATED_REF_RE.finditer(open(path, encoding="utf-8").read() if os.path.exists(path) else "")
    ))
    missing = []
    for ref in refs:
        p = os.path.join(out_dir, "public", "generated", os.path.basename(ref))
        if not validate_image_file(p):
            missing.append(ref)
    return {"ok": not missing, "refs": refs, "missing": missing}


def integrate_generated_images(out_dir: str, app_name: str, prompt: str, *,
                               generate: bool = True, pre_generated=None, plan: list = None) -> dict:
    """Plan, generate/fallback, save into public/generated, rewrite JSX refs,
    validate changed files, and verify every /generated ref resolves."""
    plan = list(plan if plan is not None else build_asset_plan(out_dir, app_name, prompt))
    write_asset_plan(out_dir, plan)
    if not plan:
        return {"ok": True, "planned": 0, "integrated": 0, "fallback": 0, "refs": []}

    pre = _pre_generated_map(pre_generated)
    by_slot = {}
    for item in plan:
        by_slot.setdefault(os.path.basename(item["target_placeholder"]), item)

    generated, fallback, errors = [], [], []
    can_generate = bool(generate and not os.getenv("AI_DESIGNER_FAST"))
    fooocus_images = None
    if can_generate:
        try:
            from app import fooocus_images as _fooocus_images
            fooocus_images = _fooocus_images
            can_generate = bool(fooocus_images.ensure_fooocus())
            if can_generate:
                fooocus_images._unload_llm()
            else:
                errors.append("Fooocus unavailable; using seeded fallback images")
        except Exception as e:
            can_generate = False
            errors.append(f"Fooocus unavailable ({str(e)[:80]}); using seeded fallback images")
    for slot, item in by_slot.items():
        dst = item["output_file_path"]
        source = pre.get(slot)
        mode = "generated"
        if source and not _copy_image(source, dst):
            errors.append(f"{slot}: supplied image invalid")
            source = None
        if not source and can_generate and fooocus_images is not None:
            try:
                if not fooocus_images.generate_one(dst, item["image_prompt"], item.get("generator_aspect", "landscape")):
                    mode = "fallback"
            except Exception as e:
                mode = "fallback"
                errors.append(f"{slot}: generation failed ({str(e)[:80]})")
        if not validate_image_file(dst):
            fb = _fallback_source(out_dir, slot)
            if fb and _copy_image(fb, dst):
                mode = "fallback"
            else:
                errors.append(f"{slot}: no valid generated or fallback image")
                continue
        (fallback if mode == "fallback" else generated).append(item["public_url_path"])

    nextgen.write_status(out_dir, "image_integrating", "Integrating generated images")
    changed = {}
    for item in plan:
        rel = item["target_jsx_file"]
        path = os.path.join(out_dir, *rel.split("/"))
        if not os.path.exists(path) or not validate_image_file(item["output_file_path"]):
            continue
        if path not in changed:
            changed[path] = open(path, encoding="utf-8").read()
        text = open(path, encoding="utf-8").read()
        text = text.replace(item["target_placeholder"], item["public_url_path"])
        text = _replace_alt_for_url(text, item["public_url_path"], item["alt_text"])
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        item["status"] = "integrated"

    for path, before in changed.items():
        ok, _err = _validate(path)
        if not ok:
            for p, orig in changed.items():
                with open(p, "w", encoding="utf-8") as f:
                    f.write(orig)
            write_asset_plan(out_dir, plan)
            return {"ok": False, "planned": len(plan), "integrated": 0,
                    "fallback": len(fallback), "error": f"image integration produced invalid JSX: {os.path.relpath(path, out_dir)}"}

    verified = verify_generated_assets(out_dir)
    for item in plan:
        if item.get("status") == "integrated":
            item["source"] = "fallback" if item["public_url_path"] in fallback else "generated"
    write_asset_plan(out_dir, plan)
    if not verified["ok"]:
        return {"ok": False, "planned": len(plan), "integrated": len(verified["refs"]),
                "fallback": len(fallback), "missing": verified["missing"], "error": "missing generated image files"}
    return {"ok": True, "planned": len(plan), "integrated": len(verified["refs"]),
            "generated": generated, "fallback": fallback, "errors": errors, "refs": verified["refs"]}


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
