"""Select-Element targeted edit: the user clicks an element in the live
preview (its data-component-id + context flow up), types a natural-language
change, and Gemma rewrites ONLY that one component's file. The edit is built;
if it doesn't compile the original file is restored, so the preview never
breaks (auto-revert). No full regeneration - the project is updated inline.
"""
import contextlib
import os
import re
import subprocess
from app import nextgen

_VALIDATE_JS = os.path.join(nextgen.BACKEND_DIR, "validate_jsx.js")


@contextlib.contextmanager
def gpu_handoff():
    """Briefly SUSPEND the active Fooocus image generation (non-destructively) so an
    LLM code-edit gets the GPU, then RESUME it exactly where it left off. No-op when
    image generation isn't running. The finally block ALWAYS resumes - even if the
    LLM call crashes - so the image batch can never be left frozen."""
    suspended = []
    try:
        from app import fooocus_images as fi
        if fi.image_gen_active():
            import psutil
            targets = []
            for pid in (fi.fooocus_server_pid(), fi.active_caller_pid()):
                if not pid:
                    continue
                try:
                    pr = psutil.Process(pid)
                    targets.append(pr)
                    targets += pr.children(recursive=True)   # Fooocus worker processes too
                except Exception:
                    pass
            for t in targets:
                try:
                    t.suspend()
                    suspended.append(t)
                except Exception:
                    pass
    except Exception:
        suspended = []   # handoff setup must never break the edit
    try:
        yield
    finally:
        for t in reversed(suspended):
            try:
                t.resume()
            except Exception:
                pass


def _validate(path: str):
    """Fast (~1s) JSX syntax check via @babel/parser - replaces the 60-90s
    `next build` on the edit path. (ok, error). Parser missing -> don't block."""
    try:
        r = subprocess.run(f'node "{_VALIDATE_JS}" "{path}"', shell=True,
                           capture_output=True, text=True, timeout=40)
        return r.returncode == 0, (r.stderr or "")[:200]
    except Exception:
        return True, ""

# data-component-id  ->  source file (relative to the project root)
_STATIC_MAP = {
    "navbar": "src/components/shell/Navbar.jsx",
    "sidebar": "src/components/shell/Sidebar.jsx",
    "dashboard": "src/app/(app)/dashboard/page.jsx",
    "hero": "src/app/(marketing)/page.jsx",
    "home": "src/app/(marketing)/page.jsx",
    "landing": "src/app/(marketing)/page.jsx",
}


def resolve_component_file(out_dir: str, component_id: str):
    cid = str(component_id or "").strip()
    if cid in _STATIC_MAP:
        rel = _STATIC_MAP[cid]
    elif cid.startswith("page:") or cid.startswith("page-"):
        slug = re.sub(r"[^a-z0-9-]", "", cid.split(":", 1)[-1].split("-", 1)[-1].lower())
        rel = f"src/app/(marketing)/{slug}/page.jsx"
    elif cid.startswith("crud") or cid.startswith("entity"):
        rel = "src/app/(app)/e/[entity]/page.jsx"
    else:
        return None, None
    path = os.path.join(out_dir, *rel.split("/"))
    return (rel, path) if os.path.exists(path) else (rel, None)


def _asset_path(out_dir: str, src: str):
    """Resolve an <img src> (e.g. /assets/feature1.jpg) to its file on disk."""
    base = os.path.basename(str(src or "").split("?")[0].rstrip("/")) or ""
    if not base or "." not in base:
        return None
    p = os.path.join(out_dir, "public", "assets", base)
    return p


def replace_image(project_id: str, src: str, data_b64: str = None, prompt: str = None) -> dict:
    """Swap the selected image: either an uploaded file or an AI-regenerated one.
    We overwrite the public asset the <img> already points at, so NO rebuild is
    needed (Next serves /public statically) - instant and 100% reliable."""
    import base64
    out_dir = os.path.join("output", project_id)
    path = _asset_path(out_dir, src)
    if not path:
        return {"ok": False, "error": f"not an image asset: {src}"}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if data_b64:                                  # OPTION A: uploaded file
        try:
            raw = base64.b64decode(data_b64.split(",")[-1])
            with open(path, "wb") as f:
                f.write(raw)
            return {"ok": True, "asset": os.path.basename(path), "mode": "upload"}
        except Exception as e:
            return {"ok": False, "error": f"bad upload: {str(e)[:100]}"}
    if prompt:                                    # OPTION B: AI regenerate (Fooocus)
        from app import fooocus_images
        if not fooocus_images.ensure_fooocus():
            return {"ok": False, "error": "image generator (Fooocus) could not start"}
        ok = fooocus_images.generate_one(path, prompt)
        return {"ok": bool(ok), "asset": os.path.basename(path), "mode": "ai",
                **({} if ok else {"error": "image generation failed"})}
    return {"ok": False, "error": "nothing to do (no file or prompt)"}


def set_component_image(project_id: str, component_id: str, old_src: str,
                        data_b64: str = None, prompt: str = None) -> dict:
    """Point a component's image at a NEW asset (cache-busting + non-destructive).
    Saves the upload / Fooocus output to a fresh file in public/assets, then does a
    deterministic, surgical swap of the old '/assets/<name>' path -> the new one in
    the component source (syntax-checked + atomic os.replace). Falls back to an
    in-place overwrite if the path isn't a literal in source. NO LLM."""
    import base64
    out_dir = os.path.join("output", project_id)
    assets = os.path.join(out_dir, "public", "assets")
    os.makedirs(assets, exist_ok=True)
    old_base = os.path.basename(str(old_src or "").split("?")[0].rstrip("/"))
    if not old_base or "." not in old_base:
        return {"ok": False, "error": f"not an image asset: {old_src}"}
    ext = os.path.splitext(old_base)[1] or ".jpg"
    new_name = "img_" + os.urandom(5).hex() + ext
    new_file = os.path.join(assets, new_name)
    new_path = "/assets/" + new_name

    # 1) materialise the new image (upload bytes or Fooocus generation)
    if data_b64:
        try:
            with open(new_file, "wb") as f:
                f.write(base64.b64decode(str(data_b64).split(",")[-1]))
        except Exception as e:
            return {"ok": False, "error": f"bad upload: {str(e)[:100]}"}
        mode = "upload"
    elif prompt:
        # generate_one already frees the GPU for Fooocus via _unload_llm. (We do NOT
        # use gpu_handoff here - that SUSPENDS Fooocus, which this very call needs.)
        from app import fooocus_images
        if not fooocus_images.generate_one(new_file, prompt):
            return {"ok": False, "error": "image generation failed"}
        mode = "ai"
    else:
        return {"ok": False, "error": "nothing to do (no file or prompt)"}

    # 2) deterministic src substitution in the component source (preferred)
    old_path = "/assets/" + old_base
    rel, path = resolve_component_file(out_dir, component_id)
    if path:
        with open(path, encoding="utf-8") as f:
            source = f.read()
        if old_path in source:
            r = _commit(path, source, source.replace(old_path, new_path), "image", rel)
            if r and r.get("ok"):
                return {"ok": True, "mode": mode, "src": new_path, "file": rel}

    # 3) fallback: overwrite the original asset in place (always works, src unchanged)
    try:
        import shutil
        shutil.copyfile(new_file, os.path.join(assets, old_base))
        return {"ok": True, "mode": mode + "-overwrite", "src": old_path}
    except Exception as e:
        return {"ok": False, "error": f"could not apply image: {str(e)[:100]}"}


def _strip_fences(text: str) -> str:
    t = (text or "").strip()
    m = re.search(r"```(?:jsx|tsx|js|javascript|react)?\s*(.*?)```", t, re.S)
    if m:
        return m.group(1).strip()
    return t


_EDIT_SYS = (
    "You are editing ONE React (JSX) component file from a Next.js app. Apply ONLY the user's "
    "requested change and keep everything else identical. Rules: return the COMPLETE updated file "
    "and NOTHING else (no markdown fences, no commentary). Keep the existing imports, the default "
    "export and any 'use client' directive. Do NOT import components or icons that are not already "
    "imported. Keep the JSX valid."
)


def _extract_new_text(prompt: str):
    """Pull the target text out of a 'change ... to X' / quoted prompt."""
    m = re.search(r'[\"“”\'‘’]([^\"“”\'‘’]{1,90})[\"“”\'‘’]', prompt)
    if m:
        return m.group(1).strip()
    m = re.search(r'(?:change|set|rename|make it say|update|replace).*?\bto\b[:\s]+(.{1,90})', prompt, re.I)
    if m:
        return m.group(1).strip().strip('.').strip()
    return None


# Isolated Block Patch system prompt: classify + verbatim, unique oldCodeBlock.
_PATCH_SYS = (
    "You are a surgical React/JSX editor inside a visual website builder. You get ONE component file "
    "(SOURCE), the SELECTED element, and a REQUEST. Reply with ONLY a JSON object: "
    '{"mode":"STYLE_TWEAK"|"SECTION_REDESIGN","oldCodeBlock":"...","newCodeBlock":"..."}. '
    "Set mode=STYLE_TWEAK when the change is presentation only (colour, background, text size/weight, "
    "alignment, spacing, radius, shadow, opacity) - edit the element's className. Set mode=SECTION_REDESIGN "
    "when structure or content changes (add/remove/reorder elements, new layout, rewrite copy, redesign). "
    "oldCodeBlock MUST be copied CHARACTER-FOR-CHARACTER from SOURCE (exact text, exact whitespace) and be "
    "the SMALLEST contiguous block that appears EXACTLY ONCE in SOURCE and fully covers the target element; "
    "if it is not unique, EXPAND it (add adjacent lines) until it is. newCodeBlock must be valid JSX using "
    "ONLY Tailwind utility classes and elements/imports ALREADY present in SOURCE - introduce no new imports, "
    "components, icons or hooks. Preserve everything outside the block (imports, default export, 'use client'). "
    'If you cannot uniquely locate the element, reply {"mode":"ERROR","reason":"<short>"}.'
)


def _commit(path, original, candidate, mode, rel):
    """Validate-THEN-atomic-write. The new code is written to a temp file and
    syntax-checked with @babel/parser FIRST; only a valid result is os.replace()d
    into place, so the live file is never left broken (inherent auto-revert).
    Returns the result dict, or None when there's nothing to apply."""
    if not candidate or candidate == original or "export default" not in candidate:
        return None
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(candidate)
    ok, err = _validate(tmp)
    if not ok:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return {"ok": False, "reverted": True, "file": rel,
                "error": "the change was invalid JSX, so it was not applied", "detail": err}
    os.replace(tmp, path)   # atomic swap on the same filesystem
    return {"ok": True, "file": rel, "mode": mode}


def edit_component(project_id: str, component_id: str, prompt: str, tag: str = None,
                   text: str = None, class_name: str = None) -> dict:
    """Isolated Block Patch pipeline (sub-3s render, ~1s @babel validate):
      0. STYLE_TWEAK  -> deterministic className splice, NO LLM (instant, 100%).
      1. exact-text   -> deterministic string replace for content edits.
      2. LLM PATCH    -> {mode, oldCodeBlock, newCodeBlock}; UNIQUE-ANCHOR guard
                         (source.count(old) == 1); literal replace; validate; atomic.
      3. fallback     -> scoped whole-file rewrite (validated + atomic).
    Python str.replace is a LITERAL substitution (no regex/$-group corruption)."""
    from app.agents import get_llm, _clean_code, extract_json
    from langchain_core.messages import SystemMessage, HumanMessage

    out_dir = os.path.join("output", project_id)
    if not os.path.isdir(out_dir):
        return {"ok": False, "error": "project not found"}
    rel, path = resolve_component_file(out_dir, component_id)
    if not path:
        return {"ok": False, "error": f"can't resolve component '{component_id}'"}
    with open(path, encoding="utf-8") as f:
        original = f.read()

    # 0) STYLE_TWEAK - deterministic, no LLM. Map the words to Tailwind classes and
    # splice the literal className in source. Instant + reliable for everyday tweaks.
    if class_name:
        set_c, rem_c = nl_to_classes(prompt, tag)
        if set_c or rem_c:
            r = style_element(project_id, [{"component_id": component_id, "class_name": class_name}], set_c, rem_c)
            if r.get("ok"):
                return {"ok": True, "file": rel, "mode": "STYLE_TWEAK", "classes": set_c}
            # dynamic className (couldn't locate literally) -> fall through to the LLM patch

    # 1) exact-text content replace
    if text and text.strip() and text.strip() in original:
        nt = _extract_new_text(prompt)
        if nt:
            r = _commit(path, original, original.replace(text.strip(), nt, 1), "STYLE_TWEAK", rel)
            if r and r["ok"]:
                return r

    # 2 + 3) LLM paths run under GPU HANDOFF: an active background image batch is
    # suspended for the duration of the LLM call(s) and resumed when we leave the
    # block (any return / exception triggers the context manager's finally).
    with gpu_handoff():
        # 2) ISOLATED BLOCK PATCH - classify + verbatim {oldCodeBlock,newCodeBlock}
        try:
            sel = {"tag": tag, "className": (class_name or "")[:160], "text": (str(text) or "")[:80], "componentId": component_id}
            user = f"SOURCE:\n{original}\n\nSELECTED_ELEMENT:\n{sel}\n\nREQUEST:\n{prompt}"
            patch = extract_json(get_llm(temperature=0.1, num_predict=3072, json_mode=True).invoke(
                [SystemMessage(content=_PATCH_SYS), HumanMessage(content=user)]).content) or {}
            mode = patch.get("mode")
            old, new = patch.get("oldCodeBlock"), patch.get("newCodeBlock")
            if mode != "ERROR" and isinstance(old, str) and old and new is not None and original.count(old) == 1:
                r = _commit(path, original, _clean_code(original.replace(old, str(new), 1)),
                            mode if mode in ("STYLE_TWEAK", "SECTION_REDESIGN") else "SECTION_REDESIGN", rel)
                if r and r["ok"]:
                    return r
                # ambiguous / not-unique / invalid -> fall through
        except Exception:
            pass

        # 3) FALLBACK: scoped whole-file rewrite (validated + atomic). Two attempts -
        # the second is hotter + insists on a real change, to catch "returned the file
        # unchanged". A failure here is SAFE: the live file was never touched.
        scope = f" Change ONLY the <{tag or 'element'}>" + (f' whose text is "{str(text).strip()[:60]}"' if text else "") + "." if (tag or text) else ""
        base = f"FILE ({rel}):\n```\n{original}\n```\n\nCHANGE REQUESTED: {prompt}.{scope}\n\nReturn the full updated file."
        for attempt in range(2):
            try:
                nudge = "" if attempt == 0 else " You MUST actually apply the change - the returned file must differ from the original."
                edited = _clean_code(_strip_fences(get_llm(temperature=0.2 + 0.35 * attempt, num_predict=4096, json_mode=False).invoke(
                    [SystemMessage(content=_EDIT_SYS), HumanMessage(content=base + nudge)]).content))
            except Exception:
                continue
            if not edited or "export default" not in edited or len(edited) < max(80, len(original) * 0.4):
                continue
            r = _commit(path, original, edited, "SECTION_REDESIGN", rel)
            if r and r["ok"]:
                return r
        return {"ok": False, "safe": True, "error": "couldn't apply that change - the app is unchanged; try rephrasing"}


# ---- Deterministic visual styling (NO LLM) -------------------------------
_COLORS = ("slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|"
           "emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose")
_TW_GROUPS = [
    ("text-size", re.compile(r"^text-(xs|sm|base|lg|xl|[2-9]xl)$")),
    ("text-align", re.compile(r"^text-(left|center|right|justify)$")),
    ("font-weight", re.compile(r"^font-(thin|extralight|light|normal|medium|semibold|bold|extrabold|black)$")),
    ("text-color", re.compile(r"^text-(" + _COLORS + r")(-\d{2,3})?$|^text-(white|black)$")),
    ("bg-color", re.compile(r"^bg-(" + _COLORS + r")(-\d{2,3})?$|^bg-(white|black|transparent)$")),
    ("rounded", re.compile(r"^rounded(-\w+)?$")),
    ("p", re.compile(r"^p-\d")), ("px", re.compile(r"^px-\d")), ("py", re.compile(r"^py-\d")),
    ("pt", re.compile(r"^pt-\d")), ("pr", re.compile(r"^pr-\d")), ("pb", re.compile(r"^pb-\d")), ("pl", re.compile(r"^pl-\d")),
    ("m", re.compile(r"^m-(\d|auto)")), ("mx", re.compile(r"^mx-(\d|auto)")), ("my", re.compile(r"^my-(\d|auto)")),
    ("mt", re.compile(r"^mt-\d")), ("mr", re.compile(r"^mr-\d")), ("mb", re.compile(r"^mb-\d")), ("ml", re.compile(r"^ml-\d")),
]


def _group_of(cls):
    for name, rx in _TW_GROUPS:
        if rx.match(cls):
            return name
    return None


def _apply_classes(current: str, set_classes, remove_classes):
    """Return a new className string: drop classes in the same Tailwind group as
    each new class (so colours/sizes don't stack), remove requested ones, add new."""
    classes = [c for c in current.split() if c]
    for rm in (remove_classes or []):
        classes = [c for c in classes if c != rm]
    for nc in (set_classes or []):
        grp = _group_of(nc)
        if grp:
            classes = [c for c in classes if _group_of(c) != grp]
        if nc not in classes:
            classes.append(nc)
    out, seen = [], set()
    for c in classes:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return " ".join(out)


_NL_COLORS = {
    "red": "red", "blue": "blue", "navy": "blue", "green": "green", "emerald": "emerald",
    "teal": "teal", "cyan": "cyan", "sky": "sky", "yellow": "yellow", "amber": "amber",
    "orange": "orange", "purple": "purple", "violet": "violet", "indigo": "indigo",
    "pink": "pink", "rose": "rose", "fuchsia": "fuchsia", "lime": "lime", "slate": "slate",
    "gray": "gray", "grey": "gray", "black": "black", "white": "white",
}


def nl_to_classes(prompt, tag=None):
    """Map a natural-language styling request to Tailwind classes - the
    deterministic, no-LLM path. Returns (set_classes, remove_classes) or ([],[])
    when the request isn't a recognised visual tweak (-> falls back to the LLM)."""
    p = " " + str(prompt).lower() + " "
    s, r = [], []
    is_bg = any(w in p for w in ("background", " bg ", "fill", "backdrop"))
    # colour
    for word, col in _NL_COLORS.items():
        if re.search(r"\b" + word + r"\b", p):
            if col in ("black", "white"):
                s.append(("bg-" if is_bg else "text-") + col)
            else:
                shade = "700" if "dark" in p else ("300" if "light" in p else "500")
                s.append(("bg-" if is_bg else "text-") + f"{col}-{shade}")
            break
    # bare "dark"/"light" (no colour word) -> a neutral dark/light surface
    if not any(c.startswith("bg-") or c.startswith("text-") for c in s):
        if "dark" in p:
            s.append("bg-slate-900" if is_bg else "text-slate-900")
        elif "light" in p and is_bg:
            s.append("bg-slate-100")
    # glassmorphism
    if "glass" in p or "frosted" in p:
        s += ["bg-white/20", "backdrop-blur-lg", "border", "border-white/30", "shadow-xl"]
    # font size
    if any(w in p for w in ("huge", "massive", "biggest")):
        s.append("text-5xl")
    elif any(w in p for w in ("bigger", "larger", "large", "increase font", "increase size", "increase the size", "increase text")):
        s.append("text-3xl")
    elif any(w in p for w in ("smaller", "tiny", "decrease font", "decrease size", "decrease text", "reduce size")):
        s.append("text-sm")
    # weight
    if "bolder" in p or "make it bold" in p or "bold" in p or "heavier" in p:
        s.append("font-bold")
    elif "lighter" in p or "thinner" in p or "thin" in p:
        s.append("font-light")
    # alignment
    if "center" in p or "centre" in p or "middle" in p:
        s.append("text-center")
    elif "align right" in p or "to the right" in p or "right align" in p or "right-align" in p:
        s.append("text-right")
    elif "align left" in p or "to the left" in p or "left align" in p or "left-align" in p:
        s.append("text-left")
    # rounding
    if "pill" in p or "fully round" in p:
        s.append("rounded-full")
    elif "rounded" in p or "round corner" in p or "round the corner" in p:
        s.append("rounded-2xl")
    elif "sharp" in p or "square corner" in p or "no rounding" in p:
        s.append("rounded-none")
    # shadow
    if "big shadow" in p or "strong shadow" in p or "drop shadow" in p:
        s.append("shadow-2xl")
    elif "shadow" in p:
        s.append("shadow-lg")
    # spacing
    if "more padding" in p or "more space inside" in p or ("padding" in p and "less" not in p and "no " not in p) or "more spacious" in p:
        s.append("p-8")
    elif "less padding" in p or "tighter" in p or "compact" in p:
        s.append("p-2")
    if "more margin" in p or "more space around" in p or "more space above" in p:
        s.append("m-6")
    # text transforms / misc
    if "uppercase" in p or "all caps" in p or "capital" in p:
        s.append("uppercase")
    if "lowercase" in p:
        s.append("lowercase")
    if "italic" in p:
        s.append("italic")
    if "underline" in p:
        s.append("underline")
    if "hide" in p or "remove this" in p or "make it disappear" in p:
        s.append("hidden")
    if "full width" in p or "full-width" in p:
        s.append("w-full")
    # gradient text
    if "gradient" in p and not is_bg:
        s += ["bg-gradient-to-r", "from-primary", "to-primary/60", "bg-clip-text", "text-transparent"]
    return s, r


def style_element(project_id: str, targets, set_classes=None, remove_classes=None) -> dict:
    """Deterministically tweak Tailwind classes on one or many elements - NO LLM,
    so it's instant. Each target = {component_id, class_name}. Edits the literal
    className string in source; fast-validates each touched file; auto-reverts."""
    out_dir = os.path.join("output", project_id)
    if not os.path.isdir(out_dir):
        return {"ok": False, "error": "project not found"}
    by_file, files = {}, {}     # path -> (rel, original, working)
    for t in (targets or []):
        rel, path = resolve_component_file(out_dir, t.get("component_id"))
        if not path:
            continue
        if path not in files:
            with open(path, encoding="utf-8") as f:
                files[path] = [rel, f.read(), None]
            files[path][2] = files[path][1]
        by_file.setdefault(path, []).append(t)

    applied, missed = 0, 0
    for path, ts in by_file.items():
        rel, original, work = files[path]
        for t in ts:
            cn = str(t.get("class_name") or "")
            target = f'className="{cn}"'
            if not cn or target not in work:        # dynamic className / not literal
                missed += 1
                continue
            work = work.replace(target, 'className="' + _apply_classes(cn, set_classes, remove_classes) + '"', 1)
            applied += 1
        files[path][2] = work

    if applied == 0:
        return {"ok": False, "error": "couldn't locate the element(s) to style (dynamic class)", "missed": missed}

    touched = []
    for path, (rel, original, work) in files.items():
        if work == original:
            continue
        with open(path, "w", encoding="utf-8") as f:
            f.write(work)
        ok, err = _validate(path)
        if not ok:
            with open(path, "w", encoding="utf-8") as f:
                f.write(original)
            return {"ok": False, "reverted": True, "error": "the style change was invalid; reverted", "detail": err}
        touched.append(rel)
    return {"ok": True, "applied": applied, "missed": missed, "files": touched}


def add_section(project_id: str, component_id: str, prompt: str, index: int = None) -> dict:
    """Insert a brand-new section into the public page the user pointed at,
    generated from a natural-language prompt. Build-validated; auto-reverts."""
    out_dir = os.path.join("output", project_id)
    if not os.path.isdir(out_dir):
        return {"ok": False, "error": "project not found"}
    rel, path = resolve_component_file(out_dir, component_id)
    if not path or "(marketing)" not in rel.replace("\\", "/"):
        return {"ok": False, "error": "click an element on a public page to add a section there"}
    from app import page_sections
    with open(path, encoding="utf-8") as f:
        original = f.read()
    section = page_sections.freeform_section(prompt)
    marker = "\n    </div>\n  );"      # the page wrapper's closing tag
    if marker not in original:
        return {"ok": False, "error": "could not find where to insert the section"}
    with open(path, "w", encoding="utf-8") as f:
        f.write(original.replace(marker, "\n" + section + "    </div>\n  );", 1))
    ok, err = _validate(path)         # fast ~1s validate (no full build)
    if not ok:
        with open(path, "w", encoding="utf-8") as f:
            f.write(original)
        return {"ok": False, "reverted": True, "file": rel,
                "error": "the new section was invalid, so it was reverted", "detail": err}
    return {"ok": True, "file": rel, "mode": "add-section"}
