# Scope flow: read evidence -> follow imports -> choose the smallest safe set.

LOCAL_IMPORT_RE = re.compile(r"""from\s+['"]@/(components/[\w./-]+)['"]""")


_DECLINED_RE = re.compile(
    r"\b(?:"
    r"does\s+not\s+exist|is\s+not\s+(?:present|there|in\s+the)|not\s+found|"
    r"could\s+not\s+(?:find|locate)|cannot\s+(?:find|locate)|can't\s+(?:find|locate)|"
    r"unable\s+to\s+(?:find|locate)|"
    r"no\s+(?:such|matching|element|section|tools?)\b|"
    r"nothing\s+(?:to\s+change|matching|matches)|"
    r"there\s+is\s+no\b|there\s+are\s+no\b|"
    r"i\s+(?:did\s+not|didn't|do\s+not|don't)\s+(?:find|see|change)|"
    r"left\s+(?:it\s+)?unchanged|changed\s+nothing|no\s+changes?\s+(?:were\s+)?made"
    r")",
    re.I)


# Quote the selected source line, falling back to class or visible text.
def _where_in_file(before: str, element: dict, line: int = 0) -> str:
    """Quote the selected source line, falling back to class or visible text."""
    lines = before.splitlines()
    if not lines:
        return ""

    # Returns a short quoted form of selected text so selection evidence stays readable in prompts.
    def quote(n: int) -> str:
        """Prepare the quote value or state used by this focused pipeline step."""
        return (f"It is written on line {n + 1}:\n"
                f"{lines[n]}\n\n"
                f"That is the element they pointed at. Change what THAT tag "
                f"renders — not the tag above it, not the one nested inside "
                f"it, and not a sibling that happens to look similar.")

    if 0 < line <= len(lines):
        return quote(line - 1)

    classes = str(element.get("className") or "").strip()
    if classes:
        for probe in (classes, " ".join(classes.split()[:4])):
            if not probe:
                continue
            for n, text in enumerate(lines):
                if probe in text:
                    return quote(n)

    text = str(element.get("text") or "").strip()[:40]
    if len(text) >= 4:
        for n, row in enumerate(lines):
            if text in row:
                return quote(n)
    return ""


# Describe the first and last elements of a section selection.
def _section_span(element: dict) -> str:
    """Describe the first and last elements of a section selection."""
    sec = element.get("section") or {}
    first, last = sec.get("start"), sec.get("end")
    if not isinstance(first, dict) or not isinstance(last, dict):
        return ""
    # From: agents/features/selection_rules.py
    return (f"  1. {describe(first).splitlines()[0]}\n"
            f"  2. {describe(last).splitlines()[0]}")


_MAP_IMPORT_RE = re.compile(r"""from\s+['"]@/(components/[^'"]+)['"]""")
_MAP_METHOD_RE = re.compile(
    r"export\s+(?:async\s+)?(?:function|const)\s+(GET|POST|PUT|PATCH|DELETE)")
_MAP_COLLECTION_RE = re.compile(r"""getCollection\s*\(\s*['"]([a-zA-Z0-9_]+)['"]""")


# Builds a fresh short route, API, component, lib, and data map.
def _project_map(arch) -> str:
    """Build a fresh compact route, API, component, lib, and data map."""
    pages, apis, comps, libs, colls = [], [], set(), [], set()
    for rel, body in sorted(arch.files.items()):
        if not rel.endswith((".js", ".jsx")):
            continue
        # From: agents/planner/builder/project_memory.py
        colls.update(_MAP_COLLECTION_RE.findall(body))
        if rel.startswith("app/") and rel.rsplit("/", 1)[-1].startswith("page."):
            seg = rel[len("app/"):].rsplit("/", 1)[0]
            route = "/" if seg.startswith("page.") else "/" + seg
            kind = ("client"
                    if body.lstrip()[:40].lstrip("\"'").startswith("use client")
                    else "server")
            uses = [m.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                    for m in dict.fromkeys(_MAP_IMPORT_RE.findall(body))]
            pages.append((route, rel, kind, uses))
        elif rel.startswith("app/") and rel.rsplit("/", 1)[-1].startswith("layout."):
            seg = rel[len("app/"):].rsplit("/", 1)[0]
            uses = [m.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                    for m in dict.fromkeys(_MAP_IMPORT_RE.findall(body))]
            pages.append(("/" if seg.startswith("layout.") else "/" + seg,
                          rel, "layout", uses))
        elif rel.startswith("app/api/") and rel.rsplit("/", 1)[-1].startswith("route."):
            ms = sorted(set(_MAP_METHOD_RE.findall(body)))
            apis.append(("/" + rel[len("app/"):].rsplit("/", 1)[0],
                         rel, ", ".join(ms) or "—"))
        elif rel.startswith("components/"):
            comps.add(rel)
        elif rel.startswith("lib/"):
            libs.append(rel)
    if not pages and not apis:
        return ""

    out = ["## The whole project, so you do not have to guess where things are",
           "", "### Routes"]
    for route, rel, kind, uses in sorted(pages, key=lambda p: p[0]):
        line = f"- `{route}` → {rel} ({kind})"
        if uses:
            line += " — renders " + ", ".join(uses[:6])
        out.append(line)
    out += ["", "### API", *[f"- `{r}` → {f} [{m}]" for r, f, m in sorted(apis)]]
    unused = sorted(c for c in comps
                    if not any(c.rsplit("/", 1)[-1].rsplit(".", 1)[0] in u
                               for _, _, _, us in pages for u in us))
    out += ["", "### Components",
            *[f"- {c}" for c in sorted(comps)]]
    if unused:
        out.append(f"  (rendered by no route: {', '.join(unused)})")
    if libs:
        out += ["", "### lib", *[f"- {l}" for l in sorted(libs)]]
    if colls:
        out += ["", "### MongoDB collections",
                "- " + ", ".join(sorted(colls))]
    out += ["", "A layout wraps every route beneath it — the navbar, header "
                "and footer are in a layout, never in the page."]
    return "\n".join(out)


# Every route `rel` appears on. Never raises — scope advice is not worth failing an edit over.
def _shared_routes(arch, rel: str) -> list:
    """Every route `rel` appears on. Never raises — scope advice is not worth
    failing an edit over."""
    try:
        # From: agents/features/selection_rules.py
        return routes_rendering(arch.files, rel)
    except Exception as e:
        log.debug(f"shared routes {rel}: {e}")
        return []


# Report shared-route reach without blocking a pointed edit.
def _log_reach(rel: str, shared: list, route: str = "") -> None:
    """Report shared-route reach without blocking a pointed edit."""
    if len(shared) <= 1:
        return
    where = route or "this page"
    # From: agents/build/tester_common.py
    elog("WARN", f"   \U0001f310 {rel} is on {len(shared)} routes, so this changes "
                 f"all of them: {', '.join(shared[:6])}"
                 + (f" (+{len(shared) - 6} more)" if len(shared) > 6 else ""))
    # From: agents/build/tester_common.py
    elog("INFO", f"      Add \u201c\u2014 on {where} only\u201d next time to keep the "
                 f"others as they are.")


# Returns ``""``, ``scoped``, or ``asked`` for a shared-route edit.
def _scope_verdict(rel: str, shared: list, instruction: str,
                   route: str = "", ask: bool = True) -> str:
    """Return ``""``, ``scoped``, or ``asked`` for a shared-route edit."""
    if len(shared) <= 1:
        return ""
    where = route or "this page"
    # From: agents/features/selection_rules.py
    if looks_like_global(instruction):
        # From: agents/build/tester_common.py
        elog("WARN", f"   🌐 {rel} is rendered on {len(shared)} routes — "
                     f"changing all of them, as asked")
        return ""
    # From: agents/features/selection_rules.py
    if looks_like_page_only(instruction):
        # From: agents/build/tester_common.py
        elog("INFO", f"   📐 {rel} is on {len(shared)} routes — changing "
                     f"{where} only, as asked")
        return "scoped"
    if not ask:
        # Said, not asked.
        # From: agents/build/tester_common.py
        elog("WARN", f"   🌐 {rel} is on {len(shared)} routes, so this changes "
                     f"all of them: {', '.join(shared[:6])}"
                     + (f" (+{len(shared) - 6} more)" if len(shared) > 6 else ""))
        # From: agents/build/tester_common.py
        elog("INFO", f"      Add “— on {where} only” next time to keep the "
                     f"others as they are.")
        return ""
    # From: agents/build/tester_common.py
    elog("WARN", f"   🛑 Not done yet — that lives in {rel}, which is rendered "
                 f"on {len(shared)} routes, not just {where}:")
    # From: agents/build/tester_common.py
    elog("WARN", f"      {', '.join(shared[:8])}"
                 + (f" (+{len(shared) - 8} more)" if len(shared) > 8 else ""))
    # From: agents/build/tester_common.py
    elog("INFO", f"      Say “{instruction.strip()[:60]} — everywhere” to "
                 f"change all of them,")
    # From: agents/build/tester_common.py
    elog("INFO", f"      or “{instruction.strip()[:60]} — on {where} only” to "
                 f"keep the others as they are.")
    emit({"type": "ask", "kind": "scope", "file": rel, "routes": shared[:12],
          "route": route,
          "options": [f"{instruction.strip()[:60]} — on {where} only",
                      f"{instruction.strip()[:60]} — everywhere"]})
    eprog("Waiting for you", 0)

    edone("", "", preview=route or "/")
    return "asked"


# Describe whether editing a file affects one route or many.
def _reach_label(arch, rel: str, route: str = "") -> str:
    """Describe whether editing a file affects one route or many."""
    try:
        # From: agents/features/selection_rules.py
        reach = routes_rendering(arch.files, rel)
    except Exception as e:
        log.debug(f"reach label {rel}: {e}")
        return "wraps this route — you MAY rewrite this one"
    if len(reach) > 1:
        return (f"rendered on ALL {len(reach)} routes — editing this changes "
                f"every one of them, not just {route or 'this page'}")
    if len(reach) == 1:
        return f"{reach[0]} only — safe to edit for this route"
    return "wraps this route — you MAY rewrite this one"


# Returns layouts and their components wrapping a Next.js page.
def _layout_chain(arch, path: str, cap: int = 3) -> list:
    """Return layouts and their components wrapping a Next.js page."""
    out, seen = [], set()
    if not path.startswith("app/"):
        return out
    parts = path[len("app/"):].split("/")[:-1]

    for i in range(len(parts), -1, -1):
        stem = "/".join(["app"] + parts[:i] + ["layout"])
        for ext in (".jsx", ".js"):
            body = arch.files.get(stem + ext)
            if body and stem + ext not in seen:
                seen.add(stem + ext)
                out.append((stem + ext, body))
            if len(out) >= cap:
                return out

    for _, body in list(out):
        for spec in dict.fromkeys(LOCAL_IMPORT_RE.findall(body)):
            for ext in (".jsx", ".js", ""):
                sub = arch.files.get(f"{spec}{ext}")
                if sub and f"{spec}{ext}" not in seen:
                    seen.add(f"{spec}{ext}")
                    out.append((f"{spec}{ext}", sub))
                    break
            if len(out) >= cap + 3:
                return out
    return out


CONNECTED_BUDGET = 90_000  # related source for a focused visual repair


# Transitive import/caller/API/data neighborhood for a visual owner.
def connected_files(arch, path: str, cap: int = 28) -> list:
    """Transitive import/caller/API/data neighborhood for a visual owner."""
    files = getattr(arch, "files", None) or {}
    if path not in files:
        return []
    try:
        # From: agents/core/workspace/source_workspace.py
        paths = WorkspaceTools(arch).dependency_paths(
            [path], max_depth=4, cap=max(2, int(cap) + 1))
    except Exception as e:
        log.debug(f"connected dependency graph {path}: {e}")
        paths = [path]
    out = []
    for rel in paths:
        if rel == path:
            continue
        out.append((rel, "connected to"))
        if len(out) >= cap:
            break
    return out


# Quote writable dependency neighbors within the prompt budget.
def _neighbours(arch, path: str, before: str, cap: int = 28) -> str:
    """Quote writable dependency neighbors within the prompt budget."""
    files = getattr(arch, "files", None) or {}
    blocks, spent = [], 0
    for rel, how in connected_files(arch, path, cap):
        body = files.get(rel) or ""
        if not body:
            continue
        if spent + len(body) > CONNECTED_BUDGET:
            blocks.append(f"--- {rel} ({how} {path}) — too long to quote here; "
                          f"it exists and you may not break its exports ---")
            continue
        spent += len(body)
        blocks.append(f"--- {rel} ({how} {path}) ---\n{body}")
    return "\n\n".join(blocks)
