"""Diagram generation from the SRS JSON.

Produces Mermaid sources for all seven required diagram types, writes ``.mmd``
files, and renders ``.svg`` + ``.png`` via mermaid-cli when a working one can be
found. If none can, the ``.mmd`` sources are still produced (the PDF draws its
own vector fallback and the browser renders Mermaid live), so the pipeline never
hard-fails — but the failure is now *reported* rather than swallowed.

Everything here is derived from the **approved plan** carried on the SRS. That
matters most for the use-case diagram: its use cases are the things the plan
says each person can do, not a list of page names. A use-case diagram whose
bubbles are screens is a sitemap, and four bubbles all reading "Where these
records are l…" is not a diagram at all.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from typing import Callable

from ..config import settings
from ..services import storage

_CARD = {
    "one_to_many": "||--o{",
    "many_to_one": "}o--||",
    "one_to_one": "||--||",
    "many_to_many": "}o--o{",
}


_LABEL = 60
_EDGE_LABEL = 40


def _san(text: str, limit: int = _LABEL) -> str:
    """A label safe to put inside a Mermaid quoted string.

    Truncation, when it is needed at all, happens on a word boundary — a label
    reading "Each user refers to o" is worse than one that is simply shorter.
    """
    text = re.sub(r"[\"'\[\]{}()|<>#;`]", "", str(text)).replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:-")
    return (cut or text[:limit]) + "…"


def _br(text: str, limit: int = _LABEL) -> str:
    """Mermaid does not read `\\n` inside a label — it needs `<br/>`."""
    return _san(text, limit).replace(" — ", "<br/>")


def _ent(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", str(name)) or "entity"


def _plan(doc: dict) -> dict:
    """The plan these diagrams are drawn from.

    `effective_plan` first: it is the same shape rebuilt from the document as
    it stands, written after a customization so a revised specification redraws
    from what it now says rather than from what was approved weeks ago.
    `approved_plan` is frozen by design and remains the fallback — and the only
    source for a document that has never been revised.
    """
    return doc.get("effective_plan") or doc.get("approved_plan") or {}


def _verb(text: str) -> str:
    """A use case reads as an action. Strip a leading article if one crept in."""
    text = str(text or "").strip().rstrip(".")
    return re.sub(r"^(?:the|a|an)\s+", "", text, flags=re.IGNORECASE)


MAX_ACTORS = 7
MAX_USE_CASES = 14


def actors_and_use_cases(doc: dict) -> tuple[list[dict], list[dict]]:
    """Who uses the system, and what each of them does.

    Read off the approved plan: `users[].can_do` is already a list of verb
    phrases the customer confirmed ("Scan barcodes", "Take payment"), which is
    exactly what a use case is. `features` are capabilities nobody in particular
    owns, so every actor gets them.

    Returns `(actors, use_cases)`, where an actor carries the ids of the use
    cases it performs:
        ([{"id": "A0", "label": "Cashier", "does": ["U0", "U1"]}],
         [{"id": "U0", "label": "Scan barcodes"}])

    Both this module and `diagram_draw` (the PDF) call it, so the two renderings
    of the same diagram cannot disagree.
    """
    plan = _plan(doc)
    use_cases: list[dict] = []
    by_text: dict[str, str] = {}

    def use_case(text: str) -> str | None:
        label = _san(_verb(text), _LABEL)
        if not label:
            return None
        key = label.casefold()
        if key in by_text:
            return by_text[key]
        if len(use_cases) >= MAX_USE_CASES:
            return None
        uid = f"U{len(use_cases)}"
        by_text[key] = uid
        use_cases.append({"id": uid, "label": label})
        return uid

    people = plan.get("users") or []
    if not people:

        allowed = {m.get("role"): m.get("allowed_functions") or []
                   for m in (doc.get("role_access_matrix") or [])}
        people = [{"role": r.get("role_name") or r.get("role_key"),
                   "can_do": allowed.get(r.get("role_key")) or []}
                  for r in (doc.get("roles") or [])]

    actors: list[dict] = []
    for person in people[:MAX_ACTORS]:
        label = _san(person.get("role") or "User", 28)
        if not label:
            continue
        does = [uid for uid in (use_case(d) for d in (person.get("can_do") or [])) if uid]
        actors.append({"id": f"A{len(actors)}", "label": label, "does": does})

    if not actors:
        actors = [{"id": "A0", "label": "User", "does": []}]

    shared = [uid for uid in (use_case(f) for f in (plan.get("features") or [])) if uid]
    if not shared and not any(a["does"] for a in actors):

        shared = [uid for uid in (use_case(m) for m in (doc.get("main_modules") or [])) if uid]
    for a in actors:
        a["does"] = a["does"] + [u for u in shared if u not in a["does"]]

    return actors, use_cases


def use_case_diagram(doc: dict) -> str:
    actors, use_cases = actors_and_use_cases(doc)
    lines = ["flowchart LR",
             "  classDef actor fill:#EEF2FF,stroke:#6366F1,color:#3730A3;",
             "  classDef uc fill:#F8FAFC,stroke:#94A3B8,color:#0F172A;"]
    lines.append(f'  subgraph SYSTEM["{_san(doc.get("project_name", "System"), 40)}"]')
    lines.append("    direction TB")
    for uc in use_cases:
        lines.append(f'    {uc["id"]}(["{uc["label"]}"]):::uc')
    lines.append("  end")

    for a in actors:
        lines.append(f'  {a["id"]}["{a["label"]}"]:::actor')
        for uid in a["does"]:
            lines.append(f'  {a["id"]} --> {uid}')
    return "\n".join(lines)


_DECISION_WORDS = ("pay", "approve", "verify", "check", "confirm", "validate")


def _is_decision(step: str) -> bool:

    words = set(re.findall(r"[a-z]+", step.lower()))
    return bool(words & set(_DECISION_WORDS))


def activity_diagram(doc: dict) -> str:
    workflows = doc.get("business_workflows") or []
    plan_flows = _plan(doc).get("workflows") or []
    if workflows:
        wf, steps = workflows[0], workflows[0].get("steps") or []
        title = wf.get("workflow_name", "Main Workflow")
    elif plan_flows:
        wf, steps = plan_flows[0], plan_flows[0].get("steps") or []
        title = wf.get("name", "Main Workflow")
    else:

        steps = [f for f in (_plan(doc).get("features") or [])][:6]
        title = "Using the application"

    steps = [s for s in steps if str(s).strip()][:9] or ["Open the application",
                                                         "Do the main task",
                                                         "See the result"]
    lines = ["flowchart TD",
             "  classDef dec fill:#FEF3C7,stroke:#F59E0B,color:#92400E;",
             f'  START(["Start: {_san(title, 48)}"])']
    prev = "START"
    for i, step in enumerate(steps):
        nid = f"s{i}"
        if _is_decision(str(step)):
            lines.append(f'  {nid}{{"{_san(step)}?"}}:::dec')
            lines.append(f"  {prev} --> {nid}")
            ok, bad = f"{nid}_ok", f"{nid}_no"
            lines.append(f'  {nid} -->|yes| {ok}["Continue"]')
            lines.append(f'  {nid} -->|no| {bad}["Correct and retry"]')
            lines.append(f"  {bad} --> {nid}")
            prev = ok
        else:
            lines.append(f'  {nid}["{_san(step)}"]')
            lines.append(f"  {prev} --> {nid}")
            prev = nid
    lines.append('  DONE(["End"])')
    lines.append(f"  {prev} --> DONE")
    return "\n".join(lines)


def _endpoints(doc: dict) -> list[tuple[str, str]]:
    """Real API calls, so the diagram stops saying `POST /api` for everything."""
    out = []
    for a in doc.get("api_design") or []:
        method, path = str(a.get("method", "")), str(a.get("path", ""))
        if method and path and "/auth/" not in path:
            out.append((method, path))
    return out


def sequence_diagram(doc: dict) -> str:
    workflows = doc.get("business_workflows") or []
    steps = (workflows[0].get("steps") if workflows else None) or \
            (_plan(doc).get("features") or []) or \
            ["Open a screen", "Save a change", "See the result"]
    steps = [s for s in steps if str(s).strip()][:6]

    tables = (doc.get("database_design", {}) or {}).get("tables") or []
    notifies = bool(doc.get("notification_rules"))
    pays = any(i.get("type") == "payment" for i in doc.get("integration_requirements") or [])

    lines = ["sequenceDiagram", "  autonumber",
             "  actor U as User", "  participant W as Web App", "  participant A as API"]
    if tables:
        lines.append("  participant DB as Database")

    if notifies:
        lines.append("  participant N as Notifier")
    if pays:
        lines.append("  participant P as Payment Gateway")

    endpoints = _endpoints(doc)
    for i, step in enumerate(steps):
        label = _san(step, 48)
        method, path = endpoints[i % len(endpoints)] if endpoints else ("POST", "/api/action")

        lines.append(f"  U->>W: {label}")
        lines.append("  activate W")
        lines.append(f"  W->>A: {method} {path}")
        lines.append("  activate A")
        if pays and any(k in str(step).lower() for k in ("pay", "checkout")):
            lines.append("  A->>P: take payment")
            lines.append("  alt payment succeeds")
            lines.append("    P-->>A: approved")
            if tables:
                lines.append("    A->>DB: record the payment")
            lines.append("  else payment declined")
            lines.append("    P-->>A: declined")
            lines.append("  end")
        elif tables:
            lines.append(f"  A->>DB: read and write {_san(tables[i % len(tables)]['table_name'], 24)}")
            lines.append("  DB-->>A: ok")
        if notifies:
            lines.append("  A->>N: send notification")
        lines.append("  A-->>W: result")
        lines.append("  deactivate A")
        lines.append("  W-->>U: show the result")
        lines.append("  deactivate W")
    return "\n".join(lines)


def erd_diagram(doc: dict) -> str:
    db = doc.get("database_design", {}) or {}
    tables = (db.get("tables") or [])[:22]
    lines = ["erDiagram"]
    names = {t.get("table_name") for t in tables}

    for t in tables:
        lines.append(f"  {_ent(t.get('table_name', 'entity'))} {{")
        for fld in (t.get("fields") or [])[:14]:
            name = re.sub(r"[^A-Za-z0-9_]", "_", str(fld.get("name", "field")))
            raw = str(fld.get("type", "string"))

            typ = "uuid" if raw == "foreign_key" else re.sub(r"[^A-Za-z0-9_]", "_", raw)
            if fld.get("primary_key"):
                key = " PK"
            elif raw == "foreign_key" or fld.get("references"):
                key = " FK"
            elif fld.get("unique"):
                key = " UK"
            else:
                key = ""
            lines.append(f"    {typ} {name}{key}")
        lines.append("  }")

    seen: set[tuple[str, str, str]] = set()
    for rel in db.get("relationships") or []:
        a = str(rel.get("from", "")).split(".")[0]
        b = str(rel.get("to", "")).split(".")[0]
        if a not in names or b not in names or a == b:
            continue
        card = _CARD.get(rel.get("type", "one_to_many"), "||--o{")
        edge = (a, b, card)
        if edge in seen:
            continue
        seen.add(edge)
        label = _san(rel.get("description") or "", _EDGE_LABEL)

        if "…" in label:
            label = "relates to"
        lines.append(f'  {_ent(a)} {card} {_ent(b)} : "{label or "relates to"}"')
    return "\n".join(lines)


def system_context_diagram(doc: dict) -> str:
    name = _san(doc.get("project_name", "System"), 32)
    kind = _san((doc.get("app_type") or {}).get("primary_type", "Web application"), 28)
    integrations = (doc.get("integration_requirements") or [])[:6]
    tables = (doc.get("database_design", {}) or {}).get("tables") or []

    lines = ["flowchart TB",
             "  classDef sys fill:#EEF2FF,stroke:#6366F1,color:#3730A3,stroke-width:2px;",
             "  classDef actor fill:#F0FDF4,stroke:#16A34A,color:#166534;",
             "  classDef data fill:#F1F5F9,stroke:#64748B,color:#0F172A;"]
    if integrations:
        lines.append("  classDef ext fill:#FFF7ED,stroke:#EA580C,color:#9A3412;")

    lines.append(f'  SYS["{name}<br/>{kind}"]:::sys')

    actors, _ = actors_and_use_cases(doc)
    for a in actors:
        lines.append(f'  {a["id"]}["{a["label"]}"]:::actor')
        lines.append(f'  {a["id"]} -- uses --> SYS')
    for i, integ in enumerate(integrations):
        lines.append(f'  X{i}["{_san(integ.get("name", "External service"), 28)}"]:::ext')
        lines.append(f"  SYS -- integrates with --> X{i}")
    if tables:
        lines.append('  DB[("Application data")]:::data')
        lines.append("  SYS -- reads and writes --> DB")
    return "\n".join(lines)


def component_diagram(doc: dict) -> str:
    """Screens, the application, and what it stores.

    A screen is not a microservice. The old version emitted "Dashboard Service"
    and "Sale Terminal Service" for what were plainly pages, and declared a
    message queue that nothing was ever connected to.
    """
    plan = _plan(doc)
    screens = [s.get("name") for s in (plan.get("screens") or []) if s.get("name")][:8]
    if not screens:
        screens = [p.get("page_name") for p in
                   (doc.get("public_pages") or []) + (doc.get("protected_pages") or [])][:8]
    screens = [s for s in screens if s] or ["Main screen"]

    tables = [t.get("table_name") for t in
              ((doc.get("database_design", {}) or {}).get("tables") or [])][:8]
    auth = bool((doc.get("authentication_requirement") or {}).get("login_required"))
    notifies = bool(doc.get("notification_rules"))
    integrations = doc.get("integration_requirements") or []

    lines = ["flowchart TB",
             "  classDef ui fill:#EEF2FF,stroke:#6366F1,color:#3730A3;",
             "  classDef svc fill:#F8FAFC,stroke:#94A3B8,color:#0F172A;",
             "  classDef data fill:#F1F5F9,stroke:#64748B,color:#0F172A;",
             '  subgraph CLIENT["Screens"]']
    for i, s in enumerate(screens):
        lines.append(f'    P{i}["{_san(s, 32)}"]:::ui')
    lines.append("  end")

    lines.append('  subgraph APP["Application"]')
    lines.append('    GW["Request handling"]:::svc')
    if auth:
        lines.append('    AUTH["Sign-in and permissions"]:::svc')
    lines.append("  end")

    if tables:
        lines.append('  subgraph DATA["Stored data"]')
        for i, t in enumerate(tables):
            lines.append(f'    D{i}[("{_san(str(t).replace("_", " "), 28)}")]:::data')
        lines.append("  end")

    for i, _ in enumerate(screens):
        lines.append(f"  P{i} --> GW")
    if auth:
        lines.append("  GW --> AUTH")
    for i, _ in enumerate(tables):
        lines.append(f"  GW --> D{i}")

    if notifies:
        lines.append('  NOTIF["Notifications"]:::svc')
        lines.append("  GW --> NOTIF")
    for i, integ in enumerate(integrations[:4]):
        lines.append(f'  X{i}["{_san(integ.get("name", "External service"), 28)}"]:::svc')
        lines.append(f"  GW --> X{i}")
    return "\n".join(lines)


def deployment_diagram(doc: dict) -> str:
    stack = (doc.get("app_type") or {}).get("example_stack") or {}
    frontend = _san(stack.get("frontend", "Web application"), 26)
    backend = _san(stack.get("backend", "API"), 26)
    database = _san(stack.get("database", "Database"), 26)
    auth = bool((doc.get("authentication_requirement") or {}).get("login_required"))
    integrations = (doc.get("integration_requirements") or [])[:3]
    uploads = any("upload" in str(f).lower() or "image" in str(f).lower()
                  for f in (_plan(doc).get("features") or []))

    lines = ["flowchart LR",
             "  classDef node fill:#F8FAFC,stroke:#94A3B8,color:#0F172A;",
             '  subgraph EDGE["User device"]',
             '    Browser["Browser"]:::node',
             "  end",
             '  subgraph HOST["Hosting"]',
             f'    Web["{frontend}"]:::node',
             f'    Api["{backend}"]:::node',
             "  end",
             '  subgraph STORE["Data"]',
             f'    DB[("{database}")]:::node']
    if uploads:
        lines.append('    OBJ[("Uploaded files")]:::node')
    lines.append("  end")
    lines += ["  Browser --> Web", "  Web --> Api", "  Api --> DB"]
    if uploads:
        lines.append("  Api --> OBJ")
    if auth:
        lines.append('  Api --> SESS["Session store"]:::node')
    for i, integ in enumerate(integrations):
        lines.append(f'  Api --> X{i}["{_san(integ.get("name", "External service"), 26)}"]:::node')
    return "\n".join(lines)


_BUILDERS = [
    ("use_case", "Use Case Diagram", use_case_diagram),
    ("activity", "Activity Diagram", activity_diagram),
    ("sequence", "Sequence Diagram", sequence_diagram),
    ("erd", "Entity Relationship Diagram", erd_diagram),
    ("system_context", "System Context Diagram", system_context_diagram),
    ("component", "Component Diagram", component_diagram),
    ("deployment", "Deployment Diagram", deployment_diagram),
]
DIAGRAM_KINDS = [b[0] for b in _BUILDERS]
DIAGRAM_TITLES = {b[0]: b[1] for b in _BUILDERS}


_SUBGRAPH = re.compile(r"^subgraph\s+([A-Za-z][\w]*)")


_DECL = re.compile(r"\b([A-Za-z][\w]*)\s*(?:\[\(§\)\]|\(\[§\]\)|\[§\]|\(§\)|\{§\})")
_ARROW = re.compile(r"\s*(?:-{2,}>|={2,}>|-\.-+>|-{3,}|={3,})\s*")
_IDENT = re.compile(r"^[A-Za-z][\w]*$")
_SKIP = ("classDef", "class ", "%%", "direction", "flowchart", "graph", "style", "linkStyle")


def _flowchart_problems(source: str) -> list[str]:
    nodes: set[str] = set()
    containers: set[str] = set()
    endpoints: list[str] = []
    opens = closes = 0

    for raw in source.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.count('"') % 2:
            return [f"unbalanced quotes: {line[:60]}"]
        if line == "end":
            closes += 1
            continue
        m = _SUBGRAPH.match(line)
        if m:
            opens += 1
            containers.add(m.group(1))
            continue
        if line.startswith(_SKIP):
            continue

        s = re.sub(r'"[^"]*"', "§", line)
        s = re.sub(r"\|[^|]*\|", " ", s)
        s = re.sub(r":::\w+", "", s)
        s = re.sub(r"--\s*[^->]+?\s*-->", " --> ", s)

        for d in _DECL.finditer(s):
            nodes.add(d.group(1))
        s = _DECL.sub(r"\1", s)

        parts = [p.strip() for p in _ARROW.split(s)]
        if len(parts) > 1:
            for p in parts:
                if _IDENT.match(p):
                    endpoints.append(p)
                    nodes.add(p) if p not in containers else None

    problems: list[str] = []
    if opens != closes:
        problems.append(f"{opens} subgraph vs {closes} end")
    if len(nodes) < 2:
        problems.append(f"only {len(nodes)} nodes")
    if not endpoints:
        problems.append("no edges")
    linked = set(endpoints)
    orphans = sorted(nodes - linked)
    if orphans:
        problems.append("unconnected node(s): " + ", ".join(orphans[:5]))
    return problems


def mermaid_problems(kind: str, source: str) -> list[str]:
    """Everything structurally wrong with this diagram. Empty means it is fine."""
    src = (source or "").strip()
    if len(src) < 30:
        return ["source is empty or a stub"]
    head = src.splitlines()[0].strip().lower()

    if kind == "erd":
        if not head.startswith("erdiagram"):
            return ["must start with erDiagram"]

        opens = len(re.findall(r"^\s*\w+\s*\{\s*$", src, re.M))
        closes = len(re.findall(r"^\s*\}\s*$", src, re.M))
        if opens != closes:
            return [f"{opens} entity blocks opened, {closes} closed"]
        return [] if opens else ["no entities"]

    if kind == "sequence":
        if not head.startswith("sequencediagram"):
            return ["must start with sequenceDiagram"]
        problems = []
        acts = len(re.findall(r"^\s*activate\s", src, re.M))
        deacts = len(re.findall(r"^\s*deactivate\s", src, re.M))
        if acts != deacts:
            problems.append(f"{acts} activate vs {deacts} deactivate")
        if len(re.findall(r"^\s*(?:actor|participant)\s", src, re.M)) < 2:
            problems.append("fewer than two participants")
        declared = set(re.findall(r"^\s*(?:actor|participant)\s+(\w+)", src, re.M))
        used = set(re.findall(r"^\s*(\w+)\s*-[->]+>?", src, re.M))
        used |= set(re.findall(r"-[->]+>?\s*(\w+)\s*:", src, re.M))
        unknown = sorted(used - declared - {"alt", "else", "end", "loop", "opt"})
        if unknown:
            problems.append("undeclared participant(s): " + ", ".join(unknown[:5]))
        return problems

    if not (head.startswith("flowchart") or head.startswith("graph")):
        return ["must start with flowchart or graph"]
    return _flowchart_problems(src)


def valid_mermaid(kind: str, source: str) -> bool:
    return not mermaid_problems(kind, source)


def build_diagrams(srs: dict, on_error: Callable[[str], None] | None = None) -> list[dict]:
    """Return deterministic diagram artifacts (with Mermaid source)."""
    doc = srs.get("srs_document", srs)
    out: list[dict] = []
    for kind, title, fn in _BUILDERS:
        try:
            source = fn(doc)
        except Exception as exc:  # noqa: BLE001 - never let one diagram break the set
            if on_error:
                on_error(f"{kind}: builder raised {type(exc).__name__}: {exc}")
            source = (f'flowchart TD\n  err["{_san(f"{kind} could not be drawn")}"]\n'
                      f'  detail["{_san(str(exc), 80)}"]\n  err --> detail')
        else:

            problems = mermaid_problems(kind, source)
            if problems and on_error:
                on_error(f"{kind}: template produced invalid Mermaid — {'; '.join(problems)}")
        out.append({"id": f"dia_{kind}", "kind": kind, "title": title,
                    "format": "mermaid", "source": source})
    return out


def build_one(kind: str, srs: dict) -> dict:
    """Deterministic single-diagram fallback by kind."""
    doc = srs.get("srs_document", srs)
    fn = dict((b[0], b[2]) for b in _BUILDERS).get(kind)
    src = fn(doc) if fn else f'flowchart TD\n  a["{kind}"]\n  b["unavailable"]\n  a --> b'
    return {"id": f"dia_{kind}", "kind": kind, "title": DIAGRAM_TITLES.get(kind, kind),
            "format": "mermaid", "source": src}


_UNSET = object()
_RENDERER_CACHE: object = _UNSET


def _works(cmd: list[str]) -> bool:
    """Does this command actually run?

    `shutil.which` is not enough. A globally installed mermaid-cli that has been
    removed leaves its launcher shim behind, so `which("mmdc")` succeeds and
    every render then dies with MODULE_NOT_FOUND — silently, because the caller
    swallowed it. Probe once, believe the exit code.

    The timeout is generous because `npx -y` may download the package the first
    time it is asked.
    """
    try:
        return subprocess.run(cmd + ["--version"], capture_output=True,
                              timeout=120).returncode == 0
    except Exception:  # noqa: BLE001 - not on PATH, not executable, too slow
        return False


def _find_renderer(refresh: bool = False) -> list[str] | None:
    """The first mermaid-cli invocation that actually works, or None."""
    global _RENDERER_CACHE
    if not refresh and _RENDERER_CACHE is not _UNSET:
        return _RENDERER_CACHE  # type: ignore[return-value]

    cli = (settings.mermaid_cli or "").strip()
    if cli.lower() in ("", "off", "none", "disabled", "__none__"):
        _RENDERER_CACHE = None
        return None

    candidates: list[list[str]] = []
    for name in (cli, "mmdc"):
        exe = shutil.which(name) if name else None
        if exe and [exe] not in candidates:
            candidates.append([exe])
    npx = shutil.which("npx")
    if npx:
        candidates.append([npx, "-y", "@mermaid-js/mermaid-cli"])

    for cmd in candidates:
        if _works(cmd):
            _RENDERER_CACHE = cmd
            return cmd
    _RENDERER_CACHE = None
    return None


def render_diagrams(project_id: str, diagrams: list[dict],
                    on_error: Callable[[str], None] | None = None) -> list[dict]:
    """Write .mmd files and render .svg/.png when a working renderer exists."""
    ddir = storage.diagrams_dir(project_id)
    renderer = _find_renderer()
    if not renderer and on_error:
        on_error("No working Mermaid renderer found — diagrams are written as .mmd "
                 "only. Install one with: npm i -g @mermaid-js/mermaid-cli")

    for d in diagrams:
        mmd_path = ddir / f"{d['kind']}.mmd"
        mmd_path.write_text(d["source"], encoding="utf-8")
        d["mmd_path"] = str(mmd_path)
        if not renderer:
            continue

        for ext in ("svg", "png"):
            out_path = ddir / f"{d['kind']}.{ext}"
            try:
                subprocess.run(
                    [*renderer, "-i", str(mmd_path), "-o", str(out_path), "-b", "white",
                     "-s", "2" if ext == "png" else "1"],
                    check=True, capture_output=True, timeout=180,
                )
                if out_path.exists():
                    d[f"{ext}_path"] = str(out_path)
            except subprocess.CalledProcessError as exc:
                if on_error:
                    detail = (exc.stderr or b"").decode("utf-8", "replace").strip()
                    on_error(f"{d['kind']}.{ext} render failed: {detail[-400:] or exc}")
                break
            except Exception as exc:  # noqa: BLE001 - timeout, missing binary
                if on_error:
                    on_error(f"{d['kind']}.{ext} render failed: {type(exc).__name__}: {exc}")
                break
    return diagrams
