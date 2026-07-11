"""Diagram generation from the SRS JSON.

Produces detailed Mermaid sources for all seven required diagram types, writes
``.mmd`` files, and renders ``.svg`` + ``.png`` via mermaid-cli (``mmdc`` or
``npx @mermaid-js/mermaid-cli``) when present. If no renderer is found the
``.mmd`` sources are still produced (and the PDF embeds a readable source),
so the pipeline never hard-fails.

These deterministic builders are intentionally rich (full ERD with keys + all
relationships, grouped use cases, decision-laden activity, sequence with alt
fragments, layered component + deployment topology). The DiagramGeneratorAgent
can further improve them with the LLM, falling back here per-diagram.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from ..config import settings
from ..services import storage

_CARD = {
    "one_to_many": "||--o{",
    "many_to_one": "}o--||",
    "one_to_one": "||--||",
    "many_to_many": "}o--o{",
}
_UNIVERSAL = {"users", "roles", "permissions", "audit_logs", "notifications"}


def _san(text: str, limit: int = 34) -> str:
    text = re.sub(r"[\"'\[\]{}()|<>#;`]", "", str(text)).replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return (text[: limit - 1] + "…") if len(text) > limit else text


def _ent(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", str(name)) or "entity"


# ── Use Case ─────────────────────────────────────────────────
def use_case_diagram(doc: dict) -> str:
    roles = doc.get("roles", [])[:7]
    pages = doc.get("protected_pages", []) or []
    lines = ["flowchart LR", "  classDef actor fill:#EEF2FF,stroke:#6366F1,color:#3730A3;",
             "  classDef uc fill:#F8FAFC,stroke:#94A3B8,color:#0F172A;"]
    sys_name = _san(doc.get("project_name", "System"), 32)
    lines.append(f'  subgraph SYSTEM["{sys_name}"]')
    lines.append("    direction TB")

    uc_ids: dict[str, str] = {}
    n = 0
    # Use cases = key functions grouped under their page/module (richer than before).
    for p in pages[:6]:
        grp = _ent(p.get("page_name", f"grp{n}"))
        lines.append(f'    subgraph {grp}_g["{_san(p.get("page_name", "Module"), 24)}"]')
        for fn in (p.get("functions", []) or [])[:4]:
            uid = f"U{n}"
            uc_ids[f"{p.get('page_name')}::{fn}"] = uid
            lines.append(f'      {uid}(["{_san(fn, 26)}"]):::uc')
            n += 1
        lines.append("    end")
    if n == 0:
        for i, mod in enumerate(doc.get("main_modules", [])[:8]):
            lines.append(f'    U{i}(["{_san(mod)}"]):::uc')
            uc_ids[mod] = f"U{i}"
    lines.append("  end")

    # Actors connect to the use cases their role is allowed to perform.
    for i, r in enumerate(roles):
        rid = f"A{i}"
        lines.append(f'  {rid}["{_san(r.get("role_name", "Actor"))}"]:::actor')
        rk = r.get("role_key")
        linked = 0
        for p in pages:
            if rk in (p.get("allowed_roles") or []):
                for fn in (p.get("functions", []) or [])[:4]:
                    uid = uc_ids.get(f"{p.get('page_name')}::{fn}")
                    if uid:
                        lines.append(f"  {rid} --> {uid}")
                        linked += 1
            if linked >= 4:
                break
        if linked == 0 and uc_ids:
            lines.append(f"  {rid} --> {next(iter(uc_ids.values()))}")
    return "\n".join(lines)


# ── Activity ─────────────────────────────────────────────────
def activity_diagram(doc: dict) -> str:
    wf = (doc.get("business_workflows") or [{}])[0]
    steps = wf.get("steps", []) or ["Start", "Process request", "Save", "Notify", "End"]
    title = _san(wf.get("workflow_name", "Main Workflow"), 40)
    lines = ["flowchart TD",
             "  classDef dec fill:#FEF3C7,stroke:#F59E0B,color:#92400E;",
             f'  START(["Start: {title}"]) --> s0']
    prev = None
    for i, step in enumerate(steps):
        nid = f"s{i}"
        low = step.lower()
        if any(k in low for k in ("pay", "approve", "verify", "check", "confirm", "valid")):
            # decision branch
            lines.append(f'  {nid}{{"{_san(step, 36)}?"}}:::dec')
            ok, bad = f"s{i}_ok", f"s{i}_no"
            lines.append(f'  {nid} -->|yes| {ok}["Proceed"]')
            lines.append(f'  {nid} -->|no| {bad}["Reject / retry"]')
            lines.append(f"  {bad} --> {nid}")
            if prev is not None:
                lines.append(f"  {prev} --> {nid}")
            prev = ok
        else:
            lines.append(f'  {nid}["{_san(step, 40)}"]')
            if prev is not None:
                lines.append(f"  {prev} --> {nid}")
            elif i == 0:
                pass  # START already points to s0
            prev = nid
    lines.append(f'  {prev} --> DONE(["End"])')
    return "\n".join(lines)


# ── Sequence ─────────────────────────────────────────────────
def sequence_diagram(doc: dict) -> str:
    wf = (doc.get("business_workflows") or [{}])[0]
    steps = wf.get("steps", []) or ["Submit request", "Validate", "Persist", "Respond"]
    has_pay = any(i.get("type") == "payment" for i in doc.get("integration_requirements", []))
    lines = ["sequenceDiagram", "  autonumber",
             "  actor U as User", "  participant W as Web App",
             "  participant A as API", "  participant DB as Database",
             "  participant N as Notifier"]
    if has_pay:
        lines.append("  participant P as Payment Gateway")
    for i, step in enumerate(steps[:9]):
        s = _san(step, 42)
        phase = i % 3
        if phase == 0:
            lines.append(f"  U->>W: {s}")
            lines.append(f"  activate W")
            lines.append(f"  W->>A: POST /api ({_san(step, 22)})")
            lines.append(f"  activate A")
        elif phase == 1:
            if has_pay and any(k in step.lower() for k in ("pay", "checkout")):
                lines.append("  A->>P: charge()")
                lines.append("  alt payment succeeds")
                lines.append("    P-->>A: paid")
                lines.append("    A->>DB: save transaction")
                lines.append("  else payment fails")
                lines.append("    P-->>A: declined")
                lines.append("    A-->>W: error")
                lines.append("  end")
            else:
                lines.append(f"  A->>DB: {s}")
                lines.append("  DB-->>A: ok")
        else:
            lines.append(f"  A->>N: notify ({_san(step, 18)})")
            lines.append("  A-->>W: result")
            lines.append("  deactivate A")
            lines.append("  W-->>U: update UI")
            lines.append("  deactivate W")
    return "\n".join(lines)


# ── ERD (full detail) ────────────────────────────────────────
def erd_diagram(doc: dict) -> str:
    db = doc.get("database_design", {})
    tables = db.get("tables", [])[:22]
    lines = ["erDiagram"]
    names = {t["table_name"] for t in tables}
    for t in tables:
        ent = _ent(t["table_name"])
        lines.append(f"  {ent} {{")
        for fld in (t.get("fields", []) or [])[:12]:
            typ = re.sub(r"[^A-Za-z0-9_]", "_", str(fld.get("type", "string")))
            name = re.sub(r"[^A-Za-z0-9_]", "_", str(fld.get("name", "field")))
            if fld.get("primary_key"):
                key = " PK"
            elif fld.get("type") == "foreign_key":
                key = " FK"
            elif fld.get("unique"):
                key = " UK"
            else:
                key = ""
            lines.append(f"    {typ} {name}{key}")
        lines.append("  }")
    for rel in db.get("relationships", []):
        a = str(rel.get("from", "")).split(".")[0]
        b = str(rel.get("to", "")).split(".")[0]
        if a in names and b in names and a != b:
            card = _CARD.get(rel.get("type", "one_to_many"), "||--o{")
            label = _san(rel.get("description", "rel"), 22).replace("…", "").strip() or "relates"
            lines.append(f'  {_ent(a)} {card} {_ent(b)} : "{label}"')
    return "\n".join(lines)


# ── System Context ───────────────────────────────────────────
def system_context_diagram(doc: dict) -> str:
    name = _san(doc.get("project_name", "System"), 26)
    lines = ["flowchart TB",
             "  classDef sys fill:#EEF2FF,stroke:#6366F1,color:#3730A3,stroke-width:2px;",
             "  classDef actor fill:#F0FDF4,stroke:#16A34A,color:#166534;",
             "  classDef ext fill:#FFF7ED,stroke:#EA580C,color:#9A3412;",
             "  classDef data fill:#F1F5F9,stroke:#64748B,color:#0F172A;",
             f'  SYS["{name}\\n(Web Platform)"]:::sys']
    for i, r in enumerate(doc.get("roles", [])[:7]):
        lines.append(f'  A{i}["{_san(r.get("role_name", "User"))}"]:::actor')
        lines.append(f"  A{i} -- uses --> SYS")
    for i, integ in enumerate(doc.get("integration_requirements", [])[:6]):
        lbl = _san(integ.get("name", "External"), 22)
        lines.append(f'  X{i}["{lbl}"]:::ext')
        lines.append(f"  SYS -- integrates --> X{i}")
    lines.append('  DB[("Application DB")]:::data')
    lines.append('  FS[("File / Object Storage")]:::data')
    lines.append("  SYS -- reads/writes --> DB")
    lines.append("  SYS -- stores files --> FS")
    return "\n".join(lines)


# ── Component ────────────────────────────────────────────────
def component_diagram(doc: dict) -> str:
    modules = [m for m in doc.get("main_modules", []) if m.lower() not in ("settings",)][:9]
    lines = ["flowchart TB",
             "  classDef svc fill:#F8FAFC,stroke:#6366F1,color:#0F172A;",
             '  subgraph CLIENT["Client Layer"]',
             '    WEB["Web SPA / PWA"]', '    MOB["Mobile (PWA)"]', "  end",
             '  subgraph GATE["API Gateway / BFF"]', '    GW["REST API Gateway + Auth"]', "  end",
             '  subgraph SERVICES["Domain Services"]']
    for i, mod in enumerate(modules):
        lines.append(f'    C{i}["{_san(mod, 24)} Service"]:::svc')
    lines.append("  end")
    lines.append('  subgraph DATA["Data Layer"]')
    lines.append('    DB[("Primary DB")]')
    lines.append('    CACHE[("Cache")]')
    lines.append('    MQ["Message Queue"]')
    lines.append("  end")
    lines.append("  WEB --> GW")
    lines.append("  MOB --> GW")
    for i, _ in enumerate(modules):
        lines.append(f"  GW --> C{i}")
        lines.append(f"  C{i} --> DB")
    lines.append("  GW --> CACHE")
    if any(n.get("event") for n in doc.get("notification_rules", [])):
        lines.append('  NOTIF["Notification Worker"]:::svc')
        lines.append("  MQ --> NOTIF")
        lines.append("  SERVICES --> MQ")
    if doc.get("integration_requirements"):
        lines.append('  EXT["External Integrations"]')
        lines.append("  SERVICES --> EXT")
    return "\n".join(lines)


# ── Deployment ───────────────────────────────────────────────
def deployment_diagram(doc: dict) -> str:
    has_pay = any(i.get("type") == "payment" for i in doc.get("integration_requirements", []))
    lines = ["flowchart LR",
             '  subgraph EDGE["Edge"]', '    Browser["Browser / Mobile"]', '    CDN["CDN (static assets)"]', "  end",
             '  subgraph CLOUD["Cloud / Cluster"]',
             '    LB["Load Balancer / TLS"]',
             '    subgraph WEBTIER["Web Tier"]', '      Web1["Next.js #1"]', '      Web2["Next.js #2"]', "    end",
             '    subgraph APITIER["API Tier"]', '      Api1["API #1"]', '      Api2["API #2"]', "    end",
             '    subgraph DATATIER["Data Tier"]',
             '      DBp[("DB Primary")]', '      DBr[("DB Replica")]', '      Cache[("Redis")]', '      OBJ[("Object Storage")]',
             "    end",
             '    MQ["Message Queue"]', '    Worker["Background Workers"]',
             "  end"]
    lines += [
        "  Browser --> CDN --> LB",
        "  LB --> Web1", "  LB --> Web2",
        "  Web1 --> Api1", "  Web2 --> Api2",
        "  Api1 --> DBp", "  Api2 --> DBp",
        "  DBp --> DBr",
        "  Api1 --> Cache", "  Api2 --> Cache",
        "  Api1 --> OBJ",
        "  Api1 --> MQ --> Worker",
    ]
    if has_pay:
        lines.append('  Api1 --> Pay["Payment Gateway"]')
    return "\n".join(lines)


_BUILDERS = [
    ("use_case", "Use Case Diagram", use_case_diagram),
    ("activity", "Activity Diagram", activity_diagram),
    ("sequence", "Sequence Diagram", sequence_diagram),
    ("erd", "Entity Relationship Diagram", erd_diagram),
    ("system_context", "System Context Diagram", system_context_diagram),
    ("component", "Component / Microservice Diagram", component_diagram),
    ("deployment", "Deployment Diagram", deployment_diagram),
]
DIAGRAM_KINDS = [b[0] for b in _BUILDERS]
DIAGRAM_TITLES = {b[0]: b[1] for b in _BUILDERS}


def build_diagrams(srs: dict) -> list[dict]:
    """Return deterministic diagram artifacts (with Mermaid source)."""
    doc = srs.get("srs_document", srs)
    out: list[dict] = []
    for kind, title, fn in _BUILDERS:
        try:
            source = fn(doc)
        except Exception as exc:  # noqa: BLE001 - never let one diagram break the set
            source = f'flowchart TD\n  err["{kind} generation failed: {exc}"]'
        out.append({"id": f"dia_{kind}", "kind": kind, "title": title,
                    "format": "mermaid", "source": source})
    return out


def build_one(kind: str, srs: dict) -> dict:
    """Deterministic single-diagram fallback by kind."""
    doc = srs.get("srs_document", srs)
    fn = dict((b[0], b[2]) for b in _BUILDERS).get(kind)
    src = fn(doc) if fn else f'flowchart TD\n  x["{kind}"]'
    return {"id": f"dia_{kind}", "kind": kind, "title": DIAGRAM_TITLES.get(kind, kind),
            "format": "mermaid", "source": src}


def _find_renderer() -> list[str] | None:
    cli = (settings.mermaid_cli or "").strip()
    if cli.lower() in ("", "off", "none", "disabled", "__none__"):
        return None
    exe = shutil.which(cli) or shutil.which("mmdc")
    if exe:
        return [exe]
    npx = shutil.which("npx")
    if npx:
        return [npx, "-y", "@mermaid-js/mermaid-cli"]
    return None


def render_diagrams(project_id: str, diagrams: list[dict]) -> list[dict]:
    """Write .mmd files and render .svg/.png with a mermaid renderer when available."""
    ddir = storage.diagrams_dir(project_id)
    renderer = _find_renderer()
    for d in diagrams:
        mmd_path = ddir / f"{d['kind']}.mmd"
        mmd_path.write_text(d["source"], encoding="utf-8")
        d["mmd_path"] = str(mmd_path)
        if not renderer:
            continue
        for ext in ("png", "svg"):
            out_path = ddir / f"{d['kind']}.{ext}"
            try:
                subprocess.run(
                    [*renderer, "-i", str(mmd_path), "-o", str(out_path), "-b", "white",
                     "-s", "2" if ext == "png" else "1"],
                    check=True, capture_output=True, timeout=120,
                )
                if out_path.exists():
                    d[f"{ext}_path"] = str(out_path)
            except Exception:  # noqa: BLE001 - render is best-effort
                pass
    return diagrams
