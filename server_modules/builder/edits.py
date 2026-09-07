# Point-and-edit: the select tool, the pencil, and picture swaps.
"""Editing by pointing at the thing instead of describing it.

Three surfaces, one idea: the user shows the agent what they mean, and the
engine turns that gesture into a precise brief.

* **Select** - they click an element in the preview. The picker scores the
  project's own source against what the browser reported (id, test id, text,
  classes, ancestors), so the agent starts at the file that really renders it
  instead of searching for a phrase that appears in nine components.
* **Pencil** - they draw on the page. The region is photographed at that exact
  scroll position and handed to a vision model, because "make this bit look
  right" is a picture, not a sentence.
* **Pictures** - they replace or regenerate an image in place.

None of these hard-code an edit. They locate, then hand the agent a brief.
"""

import re

# The emit helpers, `PROD_DIR`, `ollama` and `_edit_run` come from the runtime
# parts executed before this one; only real modules are imported here.
from server_modules.services.pencil import PENCIL_SYSTEM, capture_region
from server_modules.services.picker import (ELEMENT_EDIT_SYSTEM, ElementResolver, describe,
                                            looks_like_global, looks_like_page_only,
                                            routes_rendering)

SOURCE_EXT = {".js", ".jsx", ".ts", ".tsx", ".css", ".json"}
SOURCE_SKIP = {"node_modules", ".next", ".git", ".agentforge", ".agent", "coverage",
               "public", "test"}
MAX_SOURCE_BYTES = 400_000


class ProjectView:
    """What the picker needs to know about a project, read from disk.

    The picker was written against the old builder's in-memory file map. Its
    scoring is good and well tested, so it is kept and fed from the filesystem
    rather than rewritten.
    """

    def __init__(self, proj_dir: Path):
        self.root = Path(proj_dir)
        self._files = None

    def code_files(self) -> dict:
        if self._files is not None:
            return self._files
        files = {}
        for path in self.root.rglob("*"):
            if not path.is_file() or path.suffix not in SOURCE_EXT:
                continue
            relative = path.relative_to(self.root)
            if any(part in SOURCE_SKIP for part in relative.parts):
                continue
            try:
                if path.stat().st_size > MAX_SOURCE_BYTES:
                    continue
                files[relative.as_posix()] = path.read_text("utf-8", errors="replace")
            except OSError:
                continue
        self._files = files
        return files

    def enumerate_routes(self) -> dict:
        """URL -> {kind, file}, from where the files sit in the App Router."""
        routes = {}
        for rel in self.code_files():
            parts = rel.split("/")
            if parts[0] not in ("app", "src"):
                continue
            if parts[0] == "src" and len(parts) > 1 and parts[1] == "app":
                parts = parts[1:]
            name = parts[-1]
            if not (name.startswith("page.") or name.startswith("route.")):
                continue
            segments = [s for s in parts[1:-1] if not (s.startswith("(") and s.endswith(")"))]
            url = "/" + "/".join(segments)
            routes[url.rstrip("/") or "/"] = {
                "kind": "page" if name.startswith("page.") else "api", "file": rel}
        return routes

    @staticmethod
    def _route_matches(path: str, urls: list) -> bool:
        """Does this URL match, allowing for dynamic segments?"""
        wanted = [s for s in str(path or "/").strip("/").split("/") if s]
        for url in urls:
            candidate = [s for s in str(url or "/").strip("/").split("/") if s]
            if len(candidate) != len(wanted):
                continue
            if all(want == have or (have.startswith("[") and have.endswith("]"))
                   for want, have in zip(wanted, candidate)):
                return True
        return False


class ModelView:
    """The one model call the picker makes when two files score alike."""

    def __init__(self, model: str):
        self.model = model or default_agent_model()

    def _stream(self, messages, on_token, temperature: float = 0.1):
        reply = ollama.chat(self.model, messages,
                            options={"temperature": temperature}, timeout=120)
        on_token(((reply.get("message") or {}).get("content") or ""))


def _resolve_element(proj_dir: Path, element: dict, model: str):
    view = ProjectView(proj_dir)
    resolution = ElementResolver(ModelView(model), view).resolve(element or {})
    if resolution.path:
        emit({"type": "element_picked", "file": resolution.path, "line": resolution.line})
    return view, resolution


def _scope_question(view: ProjectView, resolution, element: dict, prompt: str) -> bool:
    """Ask which page they meant, but only when the answer changes the edit.

    A shared component on nine routes is the one case where guessing is
    expensive: a wording change meant for one page silently rewrites all of
    them. When the request already says "everywhere" or "on this page", the
    question is noise and is skipped.
    """
    routes = routes_rendering(view.code_files(), resolution.path)
    if len(routes) < 2 or looks_like_global(prompt) or looks_like_page_only(prompt):
        return False
    here = str((element or {}).get("route") or "/")
    emit({"type": "ask", "kind": "scope", "file": resolution.path, "route": here,
          "routes": routes,
          "options": [f"only on {here}", f"on all {len(routes)} routes"]})
    return True


# --------------------------------------------------------------------------
# Select
# --------------------------------------------------------------------------
def run_element_edit(project: str, prompt: str, element: dict, model: str,
                     think=None, console: str = "") -> None:
    """Change the element the user clicked in the preview."""
    try:
        proj_dir = PROD_DIR / str(project or "")
        if not proj_dir.is_dir():
            return eerr(f"there is no project called {project}")
        elog("INFO", f"🖱  {prompt[:160]}")
        eprog("Finding the element…", 12)

        view, resolution = _resolve_element(proj_dir, element, model)
        if not resolution.path:
            return eerr("that element could not be traced to a source file — "
                        "describe the change instead and it will be searched for")
        if _scope_question(view, resolution, element, prompt):
            return

        elog("INFO", f"   {resolution.path}"
                     + (f":{resolution.line}" if resolution.line else "")
                     + (" (the model chose between close matches)" if resolution.used_model else ""))
        eprog("Changing it…", 40)
        brief = "\n".join([
            ELEMENT_EDIT_SYSTEM, "",
            f"The user clicked this element on route {(element or {}).get('route', '/')}:",
            describe(element or {}), "",
            f"It is rendered by `{resolution.path}`"
            + (f" around line {resolution.line}." if resolution.line else "."), "",
            f"What they asked for:\n{prompt}", "",
            "Read that file before editing it. Change only what they asked for, keep every "
            "other behaviour and style intact, and verify the page still renders.",
        ])
        _edit_run(project, prompt, model, think, "", console, kind="select", brief=brief)
    except Exception as error:                                       # noqa: BLE001
        log.exception("element edit")
        eerr(f"{type(error).__name__}: {error}")


# --------------------------------------------------------------------------
# Pencil
# --------------------------------------------------------------------------
def run_pencil_edit(project: str, prompt: str, body: dict, model: str, think=None) -> None:
    """Apply what the user drew over the page."""
    try:
        proj_dir = PROD_DIR / str(project or "")
        if not proj_dir.is_dir():
            return eerr(f"there is no project called {project}")
        elog("INFO", f"✏️  {prompt[:160]}")
        eprog("Finding the page…", 10)

        route = str(body.get("route") or "/")
        capture = capture_region(
            route, viewport=body.get("viewport") or {}, scroll=body.get("scroll") or {},
            strokes=body.get("strokes") or [], port=DEV_PORT)
        if not capture.ok():
            return eerr(capture.error or "the drawing could not be photographed — "
                                         "is the preview running?")

        eprog("Reading the drawing…", 30)
        page = ProjectView(proj_dir).enumerate_routes().get(route.rstrip("/") or "/")
        target = (page or {}).get("file", "")
        if target:
            emit({"type": "element_picked", "file": target})

        described = _describe_drawing(capture, prompt, model)
        elog("INFO", f"   the drawing reads as: {described[:200]}")
        eprog("Redesigning…", 50)

        brief = "\n".join([
            PENCIL_SYSTEM, "",
            f"The user drew on route {route}"
            + (f", which is rendered by `{target}`." if target else "."), "",
            f"What they wrote next to the drawing:\n{prompt}", "",
            f"What the drawing shows:\n{described}", "",
            "Read the page and the components it uses before editing. Make exactly the change "
            "the drawing indicates, in the region it covers, and leave the rest of the page "
            "alone.",
        ])
        _edit_run(project, prompt, model, think, "", "", kind="pencil", brief=brief)
    except Exception as error:                                       # noqa: BLE001
        log.exception("pencil edit")
        eerr(f"{type(error).__name__}: {error}")


def _describe_drawing(capture, prompt: str, model: str) -> str:
    """Ask a vision model what the marks mean, in words the agent can act on."""
    chosen = model or default_agent_model()
    if not ollama.supports_vision(chosen):
        return ("The drawing could not be read: the selected model cannot see images. "
                "Work from the written instruction and the region it refers to.")
    try:
        reply = ollama.chat(chosen, [
            {"role": "system", "content":
                "You are looking at a screenshot of a web page with the user's drawing on top "
                "of it. Say plainly what they are asking to change: which element, and what "
                "should happen to it. Three sentences at most. Do not write code."},
            {"role": "user", "content": prompt[:600] or "What does this drawing ask for?",
             "images": capture.vision_images()},
        ], options={"temperature": 0.2}, timeout=180)
        return ((reply.get("message") or {}).get("content") or "").strip() or "(no description)"
    except Exception as error:                                       # noqa: BLE001
        log.warning(f"pencil vision: {error}")
        return f"The drawing could not be read ({error}). Work from the written instruction."


# --------------------------------------------------------------------------
# Pictures
# --------------------------------------------------------------------------
_GENERATED = re.compile(r"/generated/([A-Za-z0-9._-]+)\.(?:png|jpg|jpeg|webp)")


def _picture_name(element: dict) -> str:
    for field in ("src", "currentSrc", "backgroundImage"):
        match = _GENERATED.search(str((element or {}).get(field) or ""))
        if match:
            return match.group(1)
    attrs = (element or {}).get("attrs") or {}
    match = _GENERATED.search(str(attrs.get("src") or ""))
    return match.group(1) if match else ""


def run_image_edit(project: str, prompt: str, element: dict, model: str, think=None) -> None:
    """Redraw the picture the user pointed at."""
    try:
        proj_dir = PROD_DIR / str(project or "")
        if not proj_dir.is_dir():
            return eerr(f"there is no project called {project}")
        name = _picture_name(element)
        if not name:
            return eerr("that is not a generated picture — pick one the app drew")
        agent = image_agent()
        if not agent.enabled or not agent.available():
            return eerr("no Fooocus is answering, so the picture cannot be redrawn")

        elog("INFO", f"🎨 redrawing {name}")
        eprog("Describing it…", 25)
        alt = str((element or {}).get("alt") or ((element or {}).get("attrs") or {}).get("alt") or "")
        subject = prompt.strip() or alt or name.replace("-", " ")
        eprog("Drawing…", 55)
        target = proj_dir / "public" / "generated" / f"{name}.png"
        if not agent.generate(f"{subject}, {IMAGE_STYLE}", target,
                              aspect=str((element or {}).get("aspect") or "landscape"),
                              force=True):
            return eerr("the picture could not be drawn")
        eprog("Placing it…", 85)
        elog("SUCCESS", f"   {name}.png redrawn")
        eprog("Done", 100)
        edone(f"http://127.0.0.1:{DEV_PORT}", proj_dir.name)
    except Exception as error:                                       # noqa: BLE001
        log.exception("image edit")
        eerr(f"{type(error).__name__}: {error}")


def run_image_swap(project: str, data_b64: str, filename: str, element: dict) -> None:
    """Replace the picture the user pointed at with one they uploaded."""
    try:
        proj_dir = PROD_DIR / str(project or "")
        if not proj_dir.is_dir():
            return eerr(f"there is no project called {project}")
        name = _picture_name(element) or _safe_stem(filename, "upload")
        target = proj_dir / "public" / "generated" / f"{name}.png"
        why = save_uploaded_image(data_b64, target)
        if why:
            return eerr(why)
        elog("SUCCESS", f"   {name}.png replaced with {filename}")
        eprog("Done", 100)
        edone(f"http://127.0.0.1:{DEV_PORT}", proj_dir.name)
    except Exception as error:                                       # noqa: BLE001
        log.exception("image swap")
        eerr(f"{type(error).__name__}: {error}")


# --------------------------------------------------------------------------
# Rewording a request
# --------------------------------------------------------------------------
TUNE_SYSTEM = ("Rewrite the user's request as one clear instruction for a coding agent. "
               "Keep their intent and every specific they gave; add nothing they did not "
               "ask for. If they pointed at an element, name it. Reply with the instruction "
               "only - no preamble, no code, no quotes.")


def tune_instruction(text: str, element: dict, route: str, model: str) -> str:
    """Sharpen a typed request before it is sent. Returns the original on failure."""
    original = str(text or "").strip()
    if len(original) < 12:
        return original
    context = f"Route: {route or '/'}"
    if element:
        context += "\nElement: " + describe(element)
    try:
        reply = ollama.chat(model or default_agent_model(), [
            {"role": "system", "content": TUNE_SYSTEM},
            {"role": "user", "content": f"{context}\n\nRequest: {original}"},
        ], options={"temperature": 0.3}, timeout=90)
        tuned = ((reply.get("message") or {}).get("content") or "").strip().strip('"')
    except Exception as error:                                       # noqa: BLE001
        log.debug(f"tune: {error}")
        return original
    # A "rewrite" that lost half the request is worse than the request.
    return tuned if 12 <= len(tuned) <= max(600, len(original) * 3) else original


LOGO_PROMPT_SYSTEM = (
    "Turn the user's app idea into one image prompt for a logo. Describe a simple, flat, "
    "modern mark on a plain background - a symbol, not a scene, and no lettering. "
    "Reply with the prompt only, on one line.")
