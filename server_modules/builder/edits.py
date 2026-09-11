# Point-and-edit: showing the agent what you mean instead of describing it.
"""Editing by pointing at the thing.

Two gestures, one message. Clicking an element in the preview attaches it to
the chat with a photograph of itself; drawing over the page attaches the page
with the red line still on it. Then you type the sentence, and both halves go
together - because "this is too cramped" is a picture and a sentence, and
neither is the request on its own.

Each attached element is also traced back to source: the picker scores the
project's own files against what the browser reported (id, test id, text,
classes, ancestors), so the agent starts at the file that really renders it
instead of grepping for a phrase that appears in nine components.

These used to be two separate runs with two separate prompt boxes, and neither
could describe two things at once. Nothing here hard-codes an edit; it locates,
then hands the agent a brief.
"""

# The emit helpers, `PROD_DIR`, `ollama` and `_edit_run` come from the runtime
# parts executed before this one; only real modules are imported here.
from server_modules.services.picker import (ELEMENT_EDIT_SYSTEM, ElementResolver, Resolution, describe,
                                            looks_like_global, looks_like_page_only,
                                            routes_rendering)
from server_modules.services.sources import feature_prompt

MAX_SELECTED = 8
PENCIL_SYSTEM = feature_prompt("PENCIL", foundation=True)

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
def run_element_edit(project: str, prompt: str, elements, model: str,
                     think=None, console: str = "", shots=None,
                     route: str = "") -> None:
    """Act on whatever the user attached: elements, drawings, or both."""
    try:
        proj_dir = _workspace(project)
        if proj_dir is None:
            return
        picked = _as_list(elements)[:MAX_SELECTED]
        pictures = _as_list(shots)[:MAX_SELECTED]
        if not picked and not pictures:
            return eerr("nothing was attached to that message")

        drawn = any(_kind_of(shot) == "drawing" for shot in pictures)
        elog("INFO", ("✏️  " if drawn and not picked else "🖱  ") + prompt[:160])
        eprog("Finding what you pointed at…", 12)

        view = ProjectView(proj_dir)
        found = []
        for element in picked:
            resolution = ElementResolver(ModelView(model), view).resolve(element or {})
            if not resolution.path:
                continue
            emit({"type": "element_picked", "file": resolution.path,
                  "line": resolution.line})
            elog("INFO", f"   {resolution.path}"
                         + (f":{resolution.line}" if resolution.line else "")
                         + (" (the model chose between close matches)"
                            if resolution.used_model else ""))
            found.append((element, resolution))

        here = str(route or "").strip()
        if not here and picked:
            here = str((picked[0] or {}).get("route") or "")
        here = here or "/"
        page_file = ""
        if drawn or not found:
            page = view.enumerate_routes().get(here.rstrip("/") or "/")
            page_file = (page or {}).get("file", "")
            if page_file:
                emit({"type": "element_picked", "file": page_file})

        # Check if targeting an HTML prototype file
        proto_dir = proj_dir / ".agentforge" / "prototype"
        is_proto_target = (
            proto_dir.is_dir() and (
                (not (proj_dir / "package.json").is_file())
                or "/api/prototype" in here
                or here.startswith("/prototype")
                or here.endswith(".html")
                or any("/api/prototype" in str((p or {}).get("route") or "") for p in picked)
                or any(str((p or {}).get("route") or "").endswith(".html") for p in picked)
            )
        )
        if not page_file and is_proto_target:
            target_name = ""
            if ".html" in here:
                target_name = here.split("/")[-1].split("?")[0]
            elif picked:
                for p in picked:
                    p_route = str((p or {}).get("route") or "")
                    if ".html" in p_route:
                        target_name = p_route.split("/")[-1].split("?")[0]
                        break
            if not target_name:
                if (proto_dir / "index.html").is_file():
                    target_name = "index.html"
                else:
                    html_files = sorted(proto_dir.glob("*.html"))
                    if html_files:
                        target_name = html_files[0].name
            if target_name and (proto_dir / target_name).is_file():
                page_file = f".agentforge/prototype/{target_name}"
                emit({"type": "element_picked", "file": page_file})
                elog("INFO", f"   {page_file} (HTML prototype)")
                if not found and picked:
                    try:
                        content_lines = (proto_dir / target_name).read_text("utf-8", errors="replace").splitlines()
                    except OSError:
                        content_lines = []
                    for el in picked:
                        line_num = 0
                        el_text = str((el or {}).get("text") or "").strip()
                        el_id = str((el or {}).get("id") or "").strip()
                        for idx, line in enumerate(content_lines, 1):
                            if el_id and f'id="{el_id}"' in line:
                                line_num = idx
                                break
                            if el_text and len(el_text) > 3 and el_text in line:
                                line_num = idx
                                break
                        resolution = Resolution(path=page_file, line=line_num, used_model=False)
                        found.append((el, resolution))

        if not found and not page_file and not pictures:
            return eerr("that element could not be traced to a source file — "
                        "describe the change instead and it will be searched for")
        # Asking which page they meant is worth it for one element; for a
        # handful it is four questions in a row, and they picked the page.
        if len(found) == 1 and not drawn and _scope_question(
                view, found[0][1], found[0][0], prompt):
            return

        eprog("Changing it…", 40)
        brief = _selection_brief(found, pictures, prompt, here, page_file, model)
        _edit_run(project, prompt, model, think, "", console,
                  kind="pencil" if drawn and not found else "select", brief=brief,
                  route=here, elements=picked)
    except Exception as error:                                       # noqa: BLE001
        log.exception("element edit")
        eerr(f"{type(error).__name__}: {error}")


def _as_list(value) -> list:
    if value is None:
        return []
    return [v for v in (value if isinstance(value, list) else [value]) if v]


def _kind_of(shot) -> str:
    return str((shot or {}).get("kind") or "element") if isinstance(shot, dict) else "element"


def _image_of(shot) -> str:
    """Base64 pixels, however the studio wrapped them."""
    raw = shot.get("image", "") if isinstance(shot, dict) else shot
    raw = str(raw or "")
    return raw.split(",", 1)[1] if raw.startswith("data:") else raw


def _selection_brief(found: list, pictures: list, prompt: str, route: str,
                     page_file: str, model: str) -> str:
    """Everything the agent needs about what was pointed at."""
    drawn = any(_kind_of(shot) == "drawing" for shot in pictures)
    lines = [PENCIL_SYSTEM if drawn and not found else ELEMENT_EDIT_SYSTEM, ""]

    if found:
        lines.append(f"The user clicked {'this element' if len(found) == 1 else 'these elements'}"
                     f" on route {route}:")
        lines.append("")
        for number, (element, resolution) in enumerate(found, 1):
            head = f"{number}. " if len(found) > 1 else ""
            lines.append(head + describe(element or {}))
            lines.append(f"   Rendered by `{resolution.path}`"
                         + (f" around line {resolution.line}." if resolution.line else "."))
            lines.append("")

    if drawn:
        lines.append(f"They also drew on route {route}"
                     + (f", which is rendered by `{page_file}`." if page_file else ".")
                     + " The red line in the screenshot marks the region they mean.")
        lines.append("")
    elif page_file and not found:
        lines.append(f"They were on route {route}, rendered by `{page_file}`.")
        lines.append("")

    seen = _read_shots(pictures, prompt, model)
    if seen:
        lines += ["What the attached screenshots show:", seen, ""]

    lines += [f"What they asked for:\n{prompt}", "",
              "Read every file named above before editing it. Change only what they "
              "asked for, keep every other behaviour and style intact, and verify the "
              "page still renders."]
    return "\n".join(lines)


def _read_shots(pictures: list, prompt: str, model: str) -> str:
    """Turn the attached screenshots into words the coding agent can act on.

    The build model is chosen for code, not for pictures, so an image is read
    once here and travels as text. A model that cannot see says so rather than
    silently ignoring half the request.
    """
    images = [image for image in (_image_of(shot) for shot in pictures) if image]
    if not images:
        return ""
    chosen = model or default_agent_model()
    if not ollama.supports_vision(chosen):
        return ("(screenshots were attached, but the selected model cannot see "
                "images — work from the description above)")
    try:
        reply = ollama.chat(chosen, [
            {"role": "system", "content":
                "You are looking at screenshots of a running web page the user has "
                "pointed at. A red line, if there is one, is their annotation and is "
                "not part of the page. Say what is actually on screen — the layout, "
                "spacing, colours, text, and anything visibly wrong — and which part "
                "the annotation marks. Six sentences at most. No code, no guessing "
                "at intent."},
            {"role": "user",
             "content": prompt[:600] or "What is in these screenshots?",
             "images": images[:4]},
        ], options={"temperature": 0.2}, timeout=180)
        return ((reply.get("message") or {}).get("content") or "").strip()
    except Exception as error:                                       # noqa: BLE001
        log.warning(f"selection vision: {error}")
        return f"(the screenshot could not be read: {error})"


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
