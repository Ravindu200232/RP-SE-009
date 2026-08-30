# Bug-report flow: reproduce -> scope -> repair -> verify -> keep or roll back.
# Bind to loopback unless LAN access was explicitly enabled.
def bind_host() -> str:
    """Bind to loopback unless LAN access was explicitly enabled."""
    # From: agents/core/llm/llm_settings.py
    return "0.0.0.0" if load_settings().get("lan_access") else "127.0.0.1"


# Is MongoDB usable right now? Cheap, and false rather than raising.
def db_ok() -> bool:
    """Is MongoDB usable right now? Cheap, and false rather than raising."""
    try:
        return bool(MONGO.available)
    except Exception:
        return False


ROUTER_SYSTEM = """\
You are reading one message a user typed about an app they are looking at, and
deciding which tool should handle it. You are NOT fixing anything.

Answer with ONE line and nothing else:

INTENT :: bug :: <one sentence naming what is broken>
INTENT :: feature :: <one sentence naming what to add>
INTENT :: page :: <one sentence naming what should change on this page>
INTENT :: ask :: <the question they are asking>

How to choose:

  • bug — something is broken, erroring, blank, missing, wrong, or not doing
    what it should. "the login does nothing", "this page is white", "prices
    show as NaN", "it crashes when I click save".
  • feature — they want something the app does not do yet. "add reviews",
    "let staff export a CSV", "I need a search box", "make an admin page".
  • page — a change to how the page they are ON looks or reads: layout,
    spacing, wording, colour, order, adding or removing a section. "make this
    two columns", "the heading should say Built With", "move the form up".
  • ask — a question about the app rather than a request to change it. "where
    is the seed data", "what are the demo logins", "how does auth work".

When it could be two, prefer in this order: bug, then page, then feature. A
report that something looks wrong is a bug before it is a restyle, and a
restyle of the current page is cheaper and safer than a feature.
"""

INTENT_RE = re.compile(r"^\s*INTENT\s*::\s*(bug|feature|page|ask)"
                       r"\s*(?:::\s*(.*))?$", re.I | re.M)


# Route one message with a small LLM call; default safely to feature.
def classify_intent(arch, text: str, route: str = "") -> tuple:
    """Route one message with a small LLM call; default safely to feature."""
    user = (f"The user is looking at {route or 'the app'}.\n\n"
            f"They typed:\n{text}\n\nAnswer with the INTENT line.")
    buf = []
    try:
        # From: agents/planner/builder/builder_setup.py
        arch._stream([{"role": "system", "content": ROUTER_SYSTEM},
                      {"role": "user", "content": user}],
                     buf.append, temperature=0.0, timeout=60)
    except Exception as e:
        log.warning(f"intent router failed: {e}")
        return "feature", text
    m = INTENT_RE.search("".join(buf))
    if not m:
        return "feature", text
    return m.group(1).lower(), (m.group(2) or text).strip()


# Classify one chat input and dispatch the matching project action.
def run_chat(proj_name: str, text: str, model: str, route: str = "",
             think: bool = None, qa_model: str = "", console: str = ""):
    """Classify one chat input and dispatch the matching project action."""
    set_tester_emit(emit)
    proj_dir = PROD_DIR / proj_name
    if not proj_dir.is_dir():
        return eerr(f"Project not found: {proj_name}")
    if not ensure_model(model):
        return eerr(f"Cannot load model: {model}")

    # From: agents/pipeline/build/project_preview.py
    # From: agents/planner/builder/app_builder.py
    arch = ArchitectAgent(ollama, model, proj_dir, _agent_callbacks(proj_dir),
                          stack=detect_stack(proj_dir), think=think)
    intent, restated = classify_intent(arch, text, route)
    # From: agents/build/tester_common.py
    elog("INFO", f"💬 {intent} — {restated[:80]}")
    emit({"type": "chat_intent", "intent": intent, "summary": restated})

    if intent == "ask":
        try:
            # From: agents/pipeline/bugs/bug_workflow.py
            run_question(arch, proj_dir, text)
            edone(f"http://localhost:{DEV_PORT}", proj_name)
        finally:
            stop_model(model)
        return
    if intent == "bug":
        # From: agents/pipeline/bugs/bug_workflow.py
        return run_bug_report(proj_name, text, model, route, think, qa_model,
                              console=console)
    if intent == "page" and route:
        # From: agents/features/runtime/pencil/page_update.py
        return run_page_update(proj_name, text, model, route, think)

    # From: agents/features/runtime/feature_update.py
    return run_feature(proj_name, text, model, think, qa_model, route=route, console=console)


# Reproduce the complaint in-browser, using a demo login when possible.
def _reproduce_complaint(proj_dir: Path, route: str, complaint: str, analyzer):
    """Reproduce the complaint in-browser, using a demo login when possible."""
    # Source: reproduce.py — imported helper(s) come from this file.
    from agents.analysis.runtime.browser_reproduction import Reproduction, reproduce

    if not _dev_alive():
        # From: agents/analysis/runtime/browser_reproduction.py
        return Reproduction(route=route or "/", why_not="the dev server is not running")

    login, endpoint = None, ""
    try:
        # From: agents/analysis/runtime/runtime_probe.py
        endpoint = analyzer.find_login_endpoint() or ""
        accounts = (analyzer.arch.plan or {}).get("demo_accounts") or []
        if accounts and endpoint:
            first = accounts[0]
            login = (first.get("email"), first.get("password"))
    except Exception as e:                                      # noqa: BLE001
        log.debug(f"demo login for reproduce: {e}")

    # From: agents/analysis/runtime/browser_reproduction.py
    seen = reproduce(route or "/", complaint, port=DEV_PORT,
                     login=login, login_endpoint=endpoint)
    if not seen.ran:
        # From: agents/build/tester_common.py
        elog("INFO", f"   🔎 Could not open it in a browser — {seen.why_not}")
        return seen

    found = (len(seen.console) + len(seen.page_errors) + len(seen.network))
    # From: agents/build/tester_common.py
    elog("INFO", f"   🔎 Opened {seen.route} in a browser"
                 + (" (signed in)" if seen.signed_in else "")
                 + (f" — {found} thing(s) went wrong" if found
                    else " — the browser reported nothing"))
    if seen.filled:
        # From: agents/build/tester_common.py
        elog("INFO", f"   ⌨ Filled {len(seen.filled)} required field(s) first "
                     f"— {', '.join(seen.filled[:4])}")
    if seen.clicked:
        # From: agents/build/tester_common.py
        elog("INFO", f"   🖱 Clicked '{seen.clicked}' — "
                     + ("the page changed" if seen.changed else "nothing happened"))
    return seen


# Compare normalized before/after symptoms and report whether fixed.
def _report_symptom(before, after) -> bool:
    """Compare normalized before/after symptoms and report whether fixed."""
    if not (before.ran and after.ran):
        # From: agents/build/tester_common.py
        elog("INFO", "   ↻ Could not re-check it in a browser — the change is "
                     "in, but nobody has confirmed the symptom is gone")
        return False

    # From: agents/analysis/runtime/browser_reproduction.py
    was, now = before.signature(), after.signature()
    gone, left, fresh = was - now, was & now, now - was

    if left:
        # From: agents/build/tester_common.py
        elog("WARN", "   ✗ The app builds, but what you reported is STILL "
                     "happening:")
        for line in sorted(left)[:3]:
            # From: agents/build/tester_common.py
            elog("WARN", f"      {line[:150]}")
    elif was:
        # From: agents/build/tester_common.py
        elog("INFO", f"   ✓ The symptom is gone — {len(gone)} fault(s) that "
                     f"happened before this change do not happen now")
    elif before.clicked and not before.changed and after.changed:
        # From: agents/build/tester_common.py
        elog("INFO", f"   ✓ '{before.clicked}' does something now")
    else:
        # From: agents/build/tester_common.py
        elog("INFO", "   ↻ Re-checked in a browser; it was quiet before and "
                     "after, so this one is for you to confirm")

    if fresh:
        # From: agents/build/tester_common.py
        elog("WARN", f"   ⚠ {len(fresh)} new fault(s) that were not there "
                     f"before this change:")
        for line in sorted(fresh)[:3]:
            # From: agents/build/tester_common.py
            elog("WARN", f"      {line[:150]}")
    return bool(was) and not left




# Converts fault line in the format expected by the next pipeline steps.
def _normalise_fault_line(line: str) -> str:
    """Convert fault line in the standard shape used by the rest of the pipeline."""
    text = " ".join(str(line or "").replace("\\", "/").split())
    text = re.sub(r"\b[0-9a-fA-F]{24}\b", "<id>", text)
    text = re.sub(r"\b\d+\b", "#", text)
    return text[:220]


# Stable serious-fault signatures from pasted console/terminal evidence.
def _evidence_fault_signature(text: str) -> set:
    """Stable serious-fault signatures from pasted console/terminal evidence."""
    out = set()
    for line in str(text or "").splitlines():
        raw = line.strip()
        if not raw:
            continue
        serious = any(sig in raw for sig in _TERMINAL_SIGNALS)
        http = re.search(r"\bHTTP\s+([45]\d\d)\s+([A-Z]+)\s+(\S+)", raw)
        if not serious and not http:
            continue
        if http:
            out.add(_normalise_fault_line(
                f"HTTP {http.group(1)} {http.group(2)} {http.group(3)}"))
        else:
            out.add(_normalise_fault_line(raw))
    return out


# Builds a stable signature from current runtime errors and their mapped source files.
def _observation_fault_signature(seen, trace: str = "") -> set:
    """Build a stable signature from current runtime errors and their mapped source files."""
    # From: agents/analysis/runtime/browser_reproduction.py
    sig = {_normalise_fault_line(x) for x in (seen.signature() if seen else set()) if x}
    if seen is not None and getattr(seen, "clicked", "") and not getattr(seen, "changed", False):
        sig.add(_normalise_fault_line("CONTROL_NO_CHANGE " + str(seen.clicked)))
    # From: agents/planner/builder/project_memory.py
    sig.update(_evidence_fault_signature(trace))
    return {x for x in sig if x}


# Converts a Next.js page source path into its browser route.
def _route_for_page_source(rel: str) -> str:
    """Convert a Next.js page source path into its browser route."""
    rel = str(rel or "").replace("\\", "/")
    if not re.fullmatch(r"app/(?:.+/)?page\.(?:js|jsx|ts|tsx)", rel):
        return ""
    parts = rel.split("/")[1:-1]
    segs = [x for x in parts if not (x.startswith("(") and x.endswith(")"))]
    route = "/" + "/".join(segs) if segs else "/"
    return route


# Best concrete page route from the user's live evidence, not a guess at '/'.
def _infer_issue_route(route: str, complaint: str, console: str, trace: str,
                       arch, analyzer=None) -> str:
    """Best concrete page route from the user's live evidence, not a guess at '/'."""
    explicit = str(route or "").split("?", 1)[0].strip()
    if explicit and not explicit.startswith("/"):
        explicit = ""
    blob = "\n".join([str(console or ""), str(trace or "")]).replace("\\", "/")
    files = getattr(arch, "files", {}) or {}

    for rel in files:
        if rel in blob and re.fullmatch(r"app/(?:.+/)?page\.(?:js|jsx|ts|tsx)", rel):
            candidate = _route_for_page_source(rel)
            if candidate and "[" not in candidate:
                return candidate

    gets = re.findall(r"\bGET\s+(/[^\s?]*)[^\n]*?\b(?:200|4\d\d|5\d\d)\b", blob)
    for candidate in reversed(gets):
        if candidate.startswith(("/api/", "/_next/")):
            continue
        if "[" not in candidate:
            return candidate.rstrip("/") or "/"

    if explicit and explicit != "/":
        return explicit.rstrip("/") or "/"

    try:
        # From: agents/analysis/checks/route_checks.py
        routes = analyzer.enumerate_routes() if analyzer is not None else {}
    except Exception:
        routes = {}
    words = {w for w in re.findall(r"[a-z0-9]+", str(complaint or "").lower()) if len(w) >= 4}
    scored = []
    for candidate, meta in (routes or {}).items():
        if meta.get("kind") != "page" or meta.get("dynamic") or candidate.startswith("/api/"):
            continue
        route_words = set(re.findall(r"[a-z0-9]+", candidate.lower()))
        score = len(words & route_words)
        if score:
            scored.append((-score, len(candidate), candidate))
    if scored:
        return sorted(scored)[0][2]
    return explicit or "/"


# Converts an API route source path into its runtime URL.
def _api_url_for_source(rel: str) -> str:
    """Convert an API route source path into its runtime URL."""
    rel = str(rel or "").replace("\\", "/")
    m = re.fullmatch(r"app/api/(.+)/route\.(?:js|jsx|ts|tsx)", rel)
    return "/api/" + m.group(1) if m else ""


# Returns changed pages/APIs without expanding shared UI site-wide.
def _feature_focus_scope(arch, paths, *, declared_routes=None, route_hint: str = ""):
    """Return changed pages/APIs without expanding shared UI site-wide."""
    files = getattr(arch, "files", {}) or {}
    direct_pages, caller_pages, shared_pages, apis = set(), set(), set(), set()

    for route in declared_routes or []:
        route = str(route or "").strip()
        if not route.startswith("/") or "[" in route:
            continue
        (apis if route.startswith("/api/") else direct_pages).add(route.rstrip("/") or "/")

    for rel0 in paths or []:
        rel = str(rel0 or "").replace("\\", "/")
        direct = _route_for_page_source(rel)
        if direct and "[" not in direct:
            direct_pages.add(direct)

        api = _api_url_for_source(rel)
        if api:
            if "[" not in api:
                apis.add(api.rstrip("/") or "/")
            prefix = api.split("[", 1)[0].rstrip("/")
            for owner, body in files.items():
                if not owner.endswith((".js", ".jsx", ".ts", ".tsx")):
                    continue
                if prefix and prefix in str(body or ""):
                    try:
                        # From: agents/features/selection_rules.py
                        # From: agents/planner/builder/project_memory.py
                        caller_pages.update(routes_rendering(files, owner))
                    except Exception:
                        pass
            continue

        if rel.startswith(("components/", "lib/", "hooks/", "utils/")) or rel.startswith("app/layout"):
            try:
                # From: agents/features/selection_rules.py
                # From: agents/planner/builder/project_memory.py
                shared_pages.update(routes_rendering(files, rel))
            except Exception:
                pass

    pages = {r for r in direct_pages | caller_pages
             if r.startswith("/") and not r.startswith("/api/") and "[" not in r}

    if not pages and shared_pages:
        candidates = [r for r in shared_pages
                      if r.startswith("/") and not r.startswith("/api/") and "[" not in r]
        picked = []
        hint = (route_hint or "").rstrip("/") or "/"
        if hint in candidates:
            picked.append(hint)
        if "/" in candidates and "/" not in picked:
            picked.append("/")
        for r in sorted(candidates):
            if r not in picked:
                picked.append(r)
            if len(picked) >= 2:
                break
        # From: agents/planner/builder/project_memory.py
        pages.update(picked)

    if not pages and route_hint and route_hint.startswith("/") and "[" not in route_hint:
        pages.add(route_hint.rstrip("/") or "/")

    return sorted(pages), sorted(apis)
