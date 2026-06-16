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
    "profile": "src/app/(app)/profile/page.jsx",
    "settings": "src/app/(app)/settings/page.jsx",
    "notifications": "src/app/(app)/notifications/page.jsx",
    "workspace": "src/app/(app)/workspace/[role]/page.jsx",
    "login": "src/app/login/page.jsx",
    "register": "src/app/register/page.jsx",
    "hero": "src/app/(marketing)/page.jsx",
    "home": "src/app/(marketing)/page.jsx",
    "landing": "src/app/(marketing)/page.jsx",
}


def _route_to_file(pathname: str) -> str:
    """Map a live URL path to its Next.js source file - covers the WHOLE app, so an
    element can be selected & edited on ANY page (app pages, CRUD list/detail/edit/new,
    marketing), not just the landing/dashboard."""
    seg = [s for s in re.sub(r"[?#].*$", "", str(pathname or "/")).split("/") if s]
    if not seg:
        return "src/app/(marketing)/page.jsx"
    head = seg[0].lower()
    if head in ("dashboard", "profile", "settings", "notifications"):
        return f"src/app/(app)/{head}/page.jsx"
    if head == "workspace":
        return "src/app/(app)/workspace/[role]/page.jsx"
    if head in ("login", "register"):
        return f"src/app/{head}/page.jsx"
    if head in ("e", "entity", "entities") and len(seg) >= 2:
        if len(seg) == 2:
            return "src/app/(app)/e/[entity]/page.jsx"            # list
        if seg[-1].lower() in ("new", "create"):
            return "src/app/(app)/e/[entity]/new/page.jsx"
        if seg[-1].lower() == "edit":
            return "src/app/(app)/e/[entity]/[id]/edit/page.jsx"
        return "src/app/(app)/e/[entity]/[id]/page.jsx"           # detail
    slug = re.sub(r"[^a-z0-9-]", "", head)                        # a marketing sub-page
    return f"src/app/(marketing)/{slug}/page.jsx"


def resolve_component_file(out_dir: str, component_id: str):
    cid = str(component_id or "").strip()
    if cid.startswith("route:"):                  # inspector route fallback (any page)
        rel = _route_to_file(cid[6:])
    elif cid in _STATIC_MAP:
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


def _extract_element(source: str, tag: str = None, class_name: str = None, text: str = None):
    """Return the EXACT JSX of the selected element (its opening tag through its
    matching closing tag, or the self-closing tag), or None if it can't be isolated.
    Anchored by className first (the inspector always captures it), then by text.
    Nested same-name tags are balanced so we grab the whole element, nothing more."""
    start = -1
    if class_name and class_name.strip():
        cn = class_name.strip()
        for needle in (f'className="{cn}"', f"className='{cn}'"):
            j = source.find(needle)
            if j != -1:
                start = source.rfind("<", 0, j)
                break
        if start == -1 and len(cn) >= 24:        # inspector caps className at 200 -> anchor on a chunk
            j = source.find(f'className="{cn[:40]}')
            if j != -1:
                start = source.rfind("<", 0, j)
    if start == -1 and text and text.strip():
        j = source.find(text.strip()[:60])
        if j != -1:
            start = source.rfind("<", 0, j)
    if start == -1:
        return None
    m = re.match(r"<([A-Za-z][\w.]*)", source[start:])
    if not m:
        return None
    name = m.group(1)
    gt = source.find(">", start)
    if gt == -1:
        return None
    if source[gt - 1] == "/":                     # self-closing element, e.g. <img .../>
        return source[start:gt + 1]
    open_re = re.compile(r"<" + re.escape(name) + r"(?=[\s/>])")
    close_re = re.compile(r"</" + re.escape(name) + r"\s*>")
    depth, pos = 0, start
    while pos < len(source):
        o = open_re.search(source, pos)
        c = close_re.search(source, pos)
        if not c:
            return None
        if o and o.start() < c.start():
            og = source.find(">", o.start())
            if og != -1 and source[og - 1] == "/":
                pos = og + 1                       # nested self-closing: no depth change
            else:
                depth += 1
                pos = (og + 1) if og != -1 else o.end()
        else:
            depth -= 1
            pos = c.end()
            if depth == 0:
                return source[start:pos]
        if pos - start > 24000:                    # element implausibly large -> bail to fallback
            return None
    return None


_SNIPPET_SYS = (
    "You edit ONE JSX element. You are given that element's exact code and a change request. "
    "Return ONLY the COMPLETE updated element - the SAME outer tag with the change applied.\n"
    "INTENT DECODING: the request may have typos, bad grammar, or be vague - infer what the user MEANS. "
    "Fix obvious misspellings ('horizonal'->horizontal, 'bton'->button, 'colr'->color, 'beatiful'->beautiful). "
    "Translate vague style words into concrete Tailwind: premium/beautiful/modern/clean -> subtle shadow "
    "(shadow-sm/shadow-lg), generous rounded corners, balanced padding, refined spacing, smooth 'transition'; "
    "'pop'/'eye-catching' -> stronger accent colour + shadow; 'minimal' -> less, more whitespace. "
    "Use the element's tag + content as context for the true intent.\n"
    "Hard rules: output raw JSX only (NO markdown, NO ``` fences, NO explanation, NO text before/after); "
    "it must be a single valid JSX element; KEEP any data-component-id and the overall structure unless "
    "the request says to change it; do NOT add imports or new component references; classNames stay Tailwind. "
    "If the request truly can't apply, return the element unchanged."
)


def _edit_snippet_llm(snippet: str, prompt: str, tag: str = None, fix_error: str = "", attempt: int = 0) -> str:
    """Send ONLY the selected element to the LLM and return ONLY the updated element.
    Tiny input + tiny output => fast even on CPU (no whole-file context). `fix_error`
    feeds the previous @babel compile error back for the self-healing retry (Step 7)."""
    from app.agents import get_llm, _clean_code
    from langchain_core.messages import SystemMessage, HumanMessage
    user = f"ELEMENT (<{tag or 'element'}>):\n{snippet}\n\nCHANGE REQUEST: {prompt}\n\nReturn the full updated element only."
    if fix_error:
        user += ("\n\nYour PREVIOUS attempt did NOT compile. The validator reported:\n"
                 f"{fix_error}\nReturn the SAME element with the change applied AND that syntax error fixed - valid JSX only, no fences.")
    out = get_llm(temperature=0.15 + 0.2 * attempt, num_predict=2048, json_mode=False).invoke(
        [SystemMessage(content=_SNIPPET_SYS), HumanMessage(content=user)]).content
    return _clean_code(_strip_fences(out or "")).strip()


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

    # 0) exact-text content replace - runs FIRST so a clear "change ... to X" wins
    # over any incidental style word in the request (e.g. the "thin" inside
    # "Everything"). Only fires when there's real new text to insert.
    if text and text.strip() and text.strip() in original:
        nt = _extract_new_text(prompt)
        if nt:
            r = _commit(path, original, original.replace(text.strip(), nt, 1), "TEXT_EDIT", rel)
            if r and r["ok"]:
                return r

    # 1) STYLE_TWEAK - deterministic, no LLM. Map the words to Tailwind classes and
    # splice the literal className in source. Instant + reliable for everyday tweaks.
    if class_name:
        set_c, rem_c = nl_to_classes(prompt, tag)
        if set_c or rem_c:
            r = style_element(project_id, [{"component_id": component_id, "class_name": class_name}], set_c, rem_c)
            if r.get("ok"):
                return {"ok": True, "file": rel, "mode": "STYLE_TWEAK", "classes": set_c, "new_class_name": r.get("new_class_name")}
            # dynamic className (couldn't locate literally) -> fall through to the LLM patch

    # 2) ELEMENT-ONLY ISOLATION (the fast path the user asked for): extract ONLY the
    # selected element's JSX, send JUST that snippet to the LLM, and paste the returned
    # element back exactly where it was. Tiny input + tiny output => seconds even when
    # Fooocus holds the GPU (Gemma on CPU). The rest of the page is NEVER sent or
    # rewritten. Runs under gpu_handoff so an active image batch yields for the call.
    snippet = _extract_element(original, tag, class_name, text)
    if snippet and original.count(snippet) == 1:
        # SELF-HEALING LOOP (Step 7): generate the patched element, validate it; if it
        # doesn't compile, feed the @babel error back to the model and retry. The live
        # file is only ever swapped for a VALID result (validate-then-atomic in _commit).
        err_ctx = ""
        for attempt in range(3):
            with gpu_handoff():
                try:
                    new_el = _edit_snippet_llm(snippet, prompt, tag, fix_error=err_ctx, attempt=attempt)
                except Exception:
                    new_el = ""
            if not (new_el and "<" in new_el and new_el != snippet.strip()):
                break
            r = _commit(path, original, _clean_code(original.replace(snippet, new_el, 1)), "ELEMENT_PATCH", rel)
            if r and r["ok"]:
                return r
            err_ctx = (r or {}).get("detail") or ""   # compile error -> next attempt self-corrects
            if not err_ctx:
                break
        # couldn't self-heal the isolated element -> scoped whole-file fallback below

    # 3) FALLBACK (only when the element can't be isolated, e.g. a dynamic className or
    # no anchor): scoped whole-file rewrite, validated + atomic. Two attempts; the
    # second insists on a real change. A failure here is SAFE - the file is untouched.
    with gpu_handoff():
        scope = (f" Change ONLY the <{tag or 'element'}>" + (f' whose text is "{str(text).strip()[:60]}"' if text else "") + ".") if (tag or text) else ""
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
    ("font-family", re.compile(r"^font-(sans|serif|mono)$")),
    ("text-color", re.compile(r"^text-(" + _COLORS + r")(-\d{2,3})?$|^text-(white|black)$")),
    ("bg-color", re.compile(r"^bg-(" + _COLORS + r")(-\d{2,3})?$|^bg-(white|black|transparent)$")),
    ("border-color", re.compile(r"^border-(" + _COLORS + r")(-\d{2,3})?$|^border-(white|black)$")),
    ("border-width", re.compile(r"^border(-(0|2|4|8))?$")),
    ("ring-width", re.compile(r"^ring(-(0|1|2|4|8))?$")),
    ("rounded", re.compile(r"^rounded(-(sm|md|lg|xl|2xl|3xl|full|none))?$")),
    ("shadow", re.compile(r"^shadow(-(sm|md|lg|xl|2xl|inner|none))?$")),
    ("opacity", re.compile(r"^opacity-\d")),
    ("tracking", re.compile(r"^tracking-(tighter|tight|normal|wide|wider|widest)$")),
    ("leading", re.compile(r"^leading-(none|tight|snug|normal|relaxed|loose|\d+)$")),
    ("font-style", re.compile(r"^(italic|not-italic)$")),
    ("text-transform", re.compile(r"^(uppercase|lowercase|capitalize|normal-case)$")),
    ("text-decoration", re.compile(r"^(underline|line-through|no-underline|overline)$")),
    ("display", re.compile(r"^(block|inline-block|inline|flex|inline-flex|grid|hidden|table)$")),
    ("flex-dir", re.compile(r"^flex-(row|row-reverse|col|col-reverse)$")),
    ("justify", re.compile(r"^justify-(start|center|end|between|around|evenly)$")),
    ("items", re.compile(r"^items-(start|center|end|stretch|baseline)$")),
    ("position", re.compile(r"^(static|relative|absolute|fixed|sticky)$")),
    ("z", re.compile(r"^z-\d")),
    ("w", re.compile(r"^w-")), ("h", re.compile(r"^h-")), ("max-w", re.compile(r"^max-w-")),
    ("gap", re.compile(r"^gap-\d")),
    ("rotate", re.compile(r"^-?rotate-\d")), ("scale", re.compile(r"^scale-\d")),
    ("cursor", re.compile(r"^cursor-")),
    ("overflow", re.compile(r"^overflow-(auto|hidden|scroll|visible|x-auto|x-hidden|y-auto)$")),
    ("blur", re.compile(r"^blur(-\w+)?$")), ("backdrop", re.compile(r"^backdrop-blur(-\w+)?$")),
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

# common edit-vocabulary misspellings -> canonical (word-boundary normalised so the
# deterministic engine still matches when the user mistypes; INTENT DECODING step 1).
_EDIT_TYPOS = {
    "roundd": "rounded", "rouded": "rounded", "rouned": "rounded", "rouned": "rounded",
    "biger": "bigger", "bigr": "bigger", "smaler": "smaller", "smalller": "smaller",
    "shadw": "shadow", "shaddow": "shadow", "shadow": "shadow",
    "colr": "color", "colur": "color", "colour": "color", "coler": "color",
    "padng": "padding", "paddin": "padding", "padidng": "padding", "margn": "margin",
    "horizonal": "horizontal", "horizntal": "horizontal", "vertcal": "vertical",
    "centre": "center", "centr": "center", "allign": "align", "aligne": "align",
    "borderr": "border", "bordr": "border", "transparant": "transparent",
    "beatiful": "beautiful", "beutiful": "beautiful", "gradiant": "gradient", "animaton": "animation",
}


def nl_to_classes(prompt, tag=None):
    """Map a natural-language styling request to Tailwind classes (deterministic,
    no-LLM path). PARAMETRIC across colour / size / weight / font / spacing (every
    side) / radius / shadow / border / ring / opacity / width / height / flex+grid
    layout / transform / animation - so a very wide range of edits apply instantly
    and reliably. Anything it doesn't recognise returns ([],[]) -> element-only LLM."""
    p = " " + str(prompt).lower() + " "
    for _bad, _good in _EDIT_TYPOS.items():     # typo-tolerant (INTENT DECODING)
        if _bad != _good and _bad in p:
            p = re.sub(r"\b" + _bad + r"\b", _good, p)
    s, r = [], []
    has = lambda *ws: any(w in p for w in ws)
    wb = lambda w: bool(re.search(r"\b" + w + r"\b", p))

    def shade():
        m = re.search(r"\b([1-9]00)\b", p)
        if m: return m.group(1)
        if has("darkest"): return "900"
        if has("darker", "deeper"): return "800"
        if wb("dark") or has("deep "): return "700"
        if has("lightest", "palest"): return "100"
        if has("lighter", "paler", "softer"): return "200"
        if wb("light") or wb("pale"): return "300"
        return "500"

    # ---- colour: text / background / border ----
    want_border = wb("border") or wb("outline") or wb("stroke")
    want_bg = (not want_border) and has("background", " bg ", "fill ", "backdrop", "behind it")
    col = next((fam for word, fam in _NL_COLORS.items() if wb(word)), None)
    if col:
        tok = col if col in ("black", "white", "transparent") else f"{col}-{shade()}"
        if want_border:
            s += ["border", "border-" + tok]
        elif want_bg:
            s.append("bg-" + tok)
        else:
            s.append("text-" + tok)
    elif wb("dark"):
        s.append("bg-slate-900" if want_bg else "text-slate-900")
    elif wb("light") and want_bg:
        s.append("bg-slate-100")

    # ---- glass / gradient ----
    if has("glass", "frosted", "glassmorph"):
        s += ["bg-white/20", "backdrop-blur-lg", "border", "border-white/30", "shadow-xl"]
    if has("gradient") and not want_bg:
        s += ["bg-gradient-to-r", "from-primary", "to-primary/60", "bg-clip-text", "text-transparent"]
    elif has("gradient"):
        s += ["bg-gradient-to-br", "from-primary", "to-primary/70"]

    # ---- font size ----
    msz = re.search(r"\btext-([2-9]xl|xs|sm|base|lg|xl)\b", p)
    if msz:
        s.append("text-" + msz.group(1))
    elif has("massive", "giant", "enormous"):
        s.append("text-7xl")
    elif has("huge", "biggest", "hero text"):
        s.append("text-6xl")
    elif has("bigger", "larger", " large", "increase font", "increase size", "increase the text", "bigger text"):
        s.append("text-3xl")
    elif has("smaller", "tiny", "decrease font", "decrease size", "smaller text", "reduce text"):
        s.append("text-sm")

    # ---- font weight ----
    if has("boldest", "heaviest", "extra bold", "extrabold"):
        s.append("font-extrabold")
    elif has("bolder", "make it bold", "heavier") or wb("bold"):
        s.append("font-bold")
    elif has("semibold", "semi bold", "semi-bold"):
        s.append("font-semibold")
    elif (has("lighter", "thinner") or wb("thin")) and not has("thin border", "thin line", "thin stroke", "thin outline"):
        s.append("font-light")

    # ---- font family ----
    if has("serif", "elegant font"):
        s.append("font-serif")
    elif has("monospace", "mono font", "code font", "monospaced"):
        s.append("font-mono")
    elif has("sans serif", "sans-serif"):
        s.append("font-sans")

    # ---- alignment ----
    if has("center", "centre", "middle align", "align middle"):
        s.append("text-center")
    elif has("align right", "to the right", "right align", "right-align"):
        s.append("text-right")
    elif has("align left", "to the left", "left align", "left-align"):
        s.append("text-left")
    elif has("justify text", "justified text"):
        s.append("text-justify")

    # ---- letter / line spacing ----
    if has("more letter spacing", "wider letter", "spaced out", "wide tracking"):
        s.append("tracking-wider")
    elif has("less letter spacing", "tighter letter", "tight tracking"):
        s.append("tracking-tight")
    if has("more line height", "taller lines", "more line spacing", "relaxed line"):
        s.append("leading-relaxed")
    elif has("less line height", "tighter line", "compact line"):
        s.append("leading-tight")

    # ---- transform / decoration / style ----
    if has("uppercase", "all caps", "capital letters"):
        s.append("uppercase")
    elif has("lowercase"):
        s.append("lowercase")
    elif has("capitalize", "title case"):
        s.append("capitalize")
    if wb("italic"):
        s.append("italic")
    if has("strikethrough", "line through", "line-through", "crossed out"):
        s.append("line-through")
    elif has("no underline", "remove underline"):
        s.append("no-underline")
    elif has("underline"):
        s.append("underline")

    # ---- rounding ----
    if has("pill", "fully round", "circle", "circular", "round shape"):
        s.append("rounded-full")
    elif has("very rounded", "extra rounded", "more rounded"):
        s.append("rounded-3xl")
    elif has("slightly rounded", "small radius"):
        s.append("rounded")
    elif has("rounded", "round corner", "round the corner", "soft corner"):
        s.append("rounded-2xl")
    elif has("sharp corner", "square corner", "no rounding", "no radius", "no rounded"):
        s.append("rounded-none")

    # ---- shadow ----
    if has("biggest shadow", "huge shadow"):
        s.append("shadow-2xl")
    elif has("big shadow", "strong shadow", "drop shadow", "large shadow"):
        s.append("shadow-xl")
    elif has("subtle shadow", "small shadow", "soft shadow", "light shadow"):
        s.append("shadow-sm")
    elif has("no shadow", "remove shadow", "flat look"):
        s.append("shadow-none")
    elif wb("shadow"):
        s.append("shadow-lg")

    # ---- border width / ring ----
    if has("no border", "remove border", "remove the border", "without border", "borderless"):
        s.append("border-0")
    elif has("thick border", "thicker border", "bold border"):
        s.append("border-4")
    elif has("thin border", "1px border", "add a border", "add border") or (wb("border") and not col):
        s.append("border")
    if has("ring", "focus ring", "glow ring", "outline ring"):
        s.append("ring-2")

    # ---- opacity ----
    mo = re.search(r"opacity\s*(?:of|to|=)?\s*(\d{1,3})", p) or re.search(r"\b(\d{1,3})\s*%\s*(?:opacity|opaque|transparent)", p)
    if mo:
        v = max(0, min(100, int(mo.group(1)))); s.append(f"opacity-{v if v in (0, 100) else (v // 5) * 5}")
    elif has("semi transparent", "semi-transparent", "half transparent", "translucent"):
        s.append("opacity-50")
    elif has("faded", "more transparent", "see through", "see-through"):
        s.append("opacity-60")
    elif has("fully opaque", "no transparency"):
        s.append("opacity-100")

    # ---- padding ----
    pad = None
    if has("no padding"): pad = "0"
    elif has("huge padding", "lots of padding", "very spacious"): pad = "12"
    elif has("more padding", "more space inside", "more spacious", "bigger padding", "roomier"): pad = "8"
    elif has("less padding", "tighter padding", "compact", "less space inside", "smaller padding"): pad = "2"
    elif wb("padding"): pad = "6"
    if pad is not None:
        if has("horizontal padding", "left and right padding", "side padding"): s.append("px-" + pad)
        elif has("vertical padding", "top and bottom padding"): s.append("py-" + pad)
        elif has("top padding", "padding top", "padding above"): s.append("pt-" + pad)
        elif has("bottom padding", "padding below"): s.append("pb-" + pad)
        else: s.append("p-" + pad)

    # ---- margin ----
    marg = None
    if has("no margin"): marg = "0"
    elif has("more margin", "more space around", "more spacing outside"): marg = "8"
    elif has("less margin", "tighter margin", "reduce margin"): marg = "2"
    if marg is not None:
        if has("top margin", "space above", "margin above", "margin top", "push down"): s.append("mt-" + marg)
        elif has("bottom margin", "space below", "margin below"): s.append("mb-" + marg)
        else: s.append("m-" + marg)
    if has("center horizontally", "center it horizontally", "auto margin", "horizontally centered"):
        s.append("mx-auto")

    # ---- gap (flex/grid) ----
    if has("more gap", "more space between", "bigger gap", "wider gap"): s.append("gap-8")
    elif has("less gap", "smaller gap", "tighter gap", "less space between"): s.append("gap-2")

    # ---- width / height ----
    if has("full width", "full-width", "100% width", "edge to edge"): s.append("w-full")
    elif has("half width"): s.append("w-1/2")
    elif has("fit width", "shrink to fit", "auto width"): s.append("w-auto")
    if has("full screen height", "screen height", "viewport height"): s.append("h-screen")
    elif has("full height", "100% height"): s.append("h-full")
    elif has("taller", "more height", "bigger height"): s.append("h-64")
    elif has("shorter", "less height"): s.append("h-32")
    if has("narrower content", "narrow container", "constrain width"): s.append("max-w-2xl")
    elif has("wider content", "wide container"): s.append("max-w-7xl")

    # ---- display / flex / layout ----
    if has("hide", "remove this", "make it disappear", "make it invisible"): s.append("hidden")
    elif has("show it", "make it visible", "unhide"): s.append("block")
    if has("flex row", "in a row", "horizontal layout", "side by side", "two column", "2 column"): s += ["flex", "flex-row"]
    elif has("flex column", "stack vertically", "vertical layout", "stacked"): s += ["flex", "flex-col"]
    elif has("grid layout", "make a grid"): s.append("grid")
    if has("space between", "spread out"): s.append("justify-between")
    elif has("center horizontally", "justify center", "center the content"): s.append("justify-center")
    if has("align center", "vertically center", "center vertically", "middle vertically"): s.append("items-center")

    # ---- transform: rotate / scale ----
    mrt = re.search(r"rotate\s*(?:by|to)?\s*(-?\d{1,3})", p)
    if mrt:
        deg = int(mrt.group(1)); s.append(f"rotate-{deg}" if deg >= 0 else f"-rotate-{abs(deg)}")
    elif has("tilt", "rotate slightly", "rotate a bit", "skew it"):
        s.append("rotate-3")
    if has("bigger scale", "scale up", "zoom in", "enlarge it"): s.append("scale-110")
    elif has("smaller scale", "scale down", "zoom out", "shrink it"): s.append("scale-90")

    # ---- misc ----
    if has("pointer cursor", "clickable cursor", "hand cursor"): s.append("cursor-pointer")
    if has("clip overflow", "hide overflow"): s.append("overflow-hidden")
    elif has("scrollable", "scroll overflow"): s.append("overflow-auto")
    if has("blur it", "add blur", "blurry"): s.append("blur-sm")

    # ---- animation (defined in globals.css so they render) ----
    if has("marquee", "horizontal scroll", "auto scroll", "auto-scroll", "ticker") or ("scroll" in p and "anim" in p):
        s += ["overflow-hidden", "animate-marquee"]
    elif has("fade in", "fade-in"):
        s.append("animate-fade-in")
    elif has("slide up", "slide-up", "slide in"):
        s.append("animate-slide-up")
    elif has("float", "floating"):
        s.append("animate-float")
    elif has("spin", "rotating animation", "rotate animation"):
        s.append("animate-spin-slow")
    elif has("pulse", "blink", "breathe") and "anim" in p:
        s.append("animate-pulse-slow")
    elif wb("bounce"):
        s.append("animate-bounce")

    out, seen = [], set()
    for c in s:
        if c not in seen:
            seen.add(c); out.append(c)
    return out, r


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

    applied, missed, new_cn = 0, 0, None
    for path, ts in by_file.items():
        rel, original, work = files[path]
        for t in ts:
            cn = str(t.get("class_name") or "")
            target = f'className="{cn}"'
            if not cn or target not in work:        # dynamic className / not literal
                missed += 1
                continue
            new_cn = _apply_classes(cn, set_classes, remove_classes)
            work = work.replace(target, 'className="' + new_cn + '"', 1)
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
    return {"ok": True, "applied": applied, "missed": missed, "files": touched, "new_class_name": new_cn}


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
    # Insert the new section BEFORE the footer so it lands in the body flow (not
    # below the footer, which looked broken). Fall back to the page-wrapper close.
    candidate = None
    for anchor in ("{/* FOOTER */}", "<CtaFooter", "<footer", "{/* CTA */}", "<Footer"):
        i = original.find(anchor)
        if i != -1:
            line_start = original.rfind("\n", 0, i) + 1   # keep the footer's own indentation
            candidate = original[:line_start] + section + "\n" + original[line_start:]
            break
    if candidate is None:
        marker = "\n    </div>\n  );"                       # the page wrapper's closing tag
        if marker not in original:
            return {"ok": False, "error": "could not find where to insert the section"}
        candidate = original.replace(marker, "\n" + section + marker, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(candidate)
    ok, err = _validate(path)         # fast ~1s validate (no full build)
    if not ok:
        with open(path, "w", encoding="utf-8") as f:
            f.write(original)
        return {"ok": False, "reverted": True, "file": rel,
                "error": "the new section was invalid, so it was reverted", "detail": err}
    return {"ok": True, "file": rel, "mode": "add-section"}
