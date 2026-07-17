"""agents/orchestrator.py — v2 agentic build orchestrator.

Drives a full app build from a normalized spec with NO templates:
  fixed core → memory (.locode/*.md incl. TASKS.md + VALID ROUTES) → model/route/logic/page/section
  agents (LLM, streamed) → completeness re-check (regenerate anything missing) → npm install →
  line-level bug-fix loop → (caller serves).

Every file declared by the input is planned in TASKS.md and verified on disk so NOTHING is missed;
the agents receive the VALID ROUTES memory so links never point at a non-existent page (no 404s).

`emit(event_type, payload)` is an optional UI/stream sink. Event types:
  phase{name}, log{text}, start{label}, token(str), end{}, file{path,content}, done{ok}.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path

from agents import core, llm, module_gate, quality, scaffold
from agents.analyzer import Analyzer
from agents.memory import Memory
from agents.scaffold import pascal, route_name
from agents.gen_agents import (ModelAgent, RouteAgent, PageAgent, SectionAgent,
                               LogicAgent, ComponentAgent)
from agents.planner import _component_target
from agents.bugfix_agent import BugFixAgent

NPM = os.environ.get("NPM_BIN", r"C:\Program Files\nodejs\npm.CMD")

SKIP_PATHS = {"/login", "/signup", "/dashboard/users"}

# Declared component types that are NOT emitted as their own reusable file:
# navigation/layout become per-role workspace layouts; atomic controls, plain
# displays and overlays (modals) are composed inline by the page/feature that owns them.
INLINE_COMPONENT_TYPES = {"navigation", "layout", "form_control", "display", "overlay"}


def _contract_target(contract: dict) -> str:
    """Stable file path for a declared component (reuses the planner's feature layout)."""
    pseudo_page = {"owner_role": (contract.get("roles") or ["shared"])[0]}
    return _component_target(pseudo_page, contract.get("name"), contract)


def _module_path(rel: str) -> str:
    """`components/features/menu/MenuItemTable.tsx` → `@/components/features/menu/MenuItemTable`."""
    return "@/" + rel.replace("\\", "/").rsplit(".tsx", 1)[0]


def _strip_strings(text: str) -> str:
    """Drop comments and string/template literals so brace/paren balance is meaningful."""
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r'"(?:\\.|[^"\\])*"', '""', text)
    text = re.sub(r"'(?:\\.|[^'\\])*'", "''", text)
    text = re.sub(r"`(?:\\.|[^`\\])*`", "``", text)  # also removes ${...} interpolations
    return text


def _file_incomplete(text: str) -> bool:
    """Cheap truncation/imbalance signal — the dominant gemma failure on large files."""
    s = (text or "").strip()
    if len(s) < 24:
        return True
    code = _strip_strings(s)
    return code.count("{") != code.count("}") or code.count("(") != code.count(")")


def component_name(page: dict) -> str:
    """Page path → body-component name. Dynamic `[param]` segments are kept as a `By<Param>` token
    (NOT dropped) so two routes that differ ONLY in a dynamic segment don't collapse to the SAME
    `components/pages/<Comp>.tsx` — e.g. `/x/[id]` vs `/x/[slug]`, or `/orders/[id]/edit` vs
    `/orders/edit`. That collapse used to overwrite one page's plan entry and write the shared body
    file twice (the 'same file generated repeatedly' bug). `uniquify_component_names` is the final
    guarantee; this just makes collisions rare at the source."""
    path = str(page.get("path") or "/")
    tokens: list[str] = []
    for s in path.strip("/").split("/"):
        if not s:
            continue
        if s.startswith("["):
            param = s.strip("[].")           # `[id]`→id, `[...slug]`→slug
            tokens.append("By" + pascal(param) if param else "Dyn")
        else:
            tokens.append(pascal(s))
    base = "".join(tokens) if tokens else "Home"
    if str(page.get("kind")) == "detail":
        base += "Detail"
    return base + "Page"


def uniquify_component_names(pages: list[dict]) -> dict[str, str]:
    """path → UNIQUE body-component name. Even after the dynamic-segment disambiguation above two
    pages can still land on one name; a numeric suffix guarantees each page gets its own body file
    (mirrors the dedup in agents/component_pages.compile_component_pages)."""
    out: dict[str, str] = {}
    used: set[str] = set()
    for p in pages:
        base = component_name(p)
        comp, n = base, 2
        while comp in used:
            comp = f"{base}{n}"
            n += 1
        used.add(comp)
        out[str(p.get("path"))] = comp
    return out


def page_file(path: str) -> str:
    clean = str(path or "/").strip("/")
    return f"app/{clean}/page.tsx" if clean else "app/page.tsx"


def _install(project_dir: Path, emit) -> bool:
    """Install dependencies, and make sure what lands is actually complete.

    npm on Windows extracts tens of thousands of tiny files (`@mui/icons-material` alone ships ~21k)
    and loses races with the virus scanner: `TAR_ENTRY_ERROR ENOENT …`, a non-zero exit, and a
    HALF-EXTRACTED tree. npm reconciles packages and versions, not file contents, so a re-run reports
    success and leaves the holes — one app sat on an icons package missing ~6k files, passed the old
    "is next installed?" check on every later run, and failed every build on a real icon. A wipe is
    the only repair."""
    nm = project_dir / "node_modules"
    next_bin = nm / ".bin" / ("next.cmd" if os.name == "nt" else "next")
    if next_bin.exists() and _deps_intact(project_dir):
        emit("log", {"text": "deps present — skipping install"})
        return True
    if nm.exists():
        emit("log", {"text": "node_modules incomplete — wiping before install"})
        shutil.rmtree(nm, ignore_errors=True)
    for attempt in (1, 2):
        emit("log", {"text": "npm install…" if attempt == 1 else "npm install retry (clean)…"})
        try:
            r = subprocess.run([NPM, "install", "--no-audit", "--no-fund"], cwd=str(project_dir),
                               capture_output=True, text=True, timeout=900)
            if r.returncode == 0 and _deps_intact(project_dir):
                return True
            if r.returncode == 0:
                emit("log", {"text": f"npm install (attempt {attempt}) reported success but the tree "
                                     f"is incomplete"})
            else:
                # npm reports failures on stdout as often as stderr; logging only stderr printed an
                # empty reason and hid the cause completely.
                why = ((r.stderr or "") + (r.stdout or "")).strip()[-400:] or f"exit {r.returncode}"
                emit("log", {"text": f"npm install failed (attempt {attempt}): {why}"})
        except Exception as e:  # noqa: BLE001
            emit("log", {"text": f"npm install crashed (attempt {attempt}): {e}"})
        shutil.rmtree(nm, ignore_errors=True)   # never retry on top of a broken tree
    return False


# The kinds that carry a table AND a modal form, measured from real specs: the refiner emits
# `dashboard-list`/`list`/`admin` (never the `table-crud` the design planner names), and those are the
# bodies that land at 300-340 lines. Truncation turned out NOT to track size — the 340-line lists
# compiled clean while a 215-line form was cut off — so this split is for the cost of a RETRY
# (regenerating a 90-line chunk, not a 340-line page) and for pages a human can still read.
CHUNKED_KINDS = {"table-crud", "dashboard-list", "list", "admin", "workflow"}


def _page_chunks(page: dict, existing: list) -> list[dict]:
    """The heavy pieces to generate as their own files, so the page body stays small.

    Only CRUD-shaped pages: they carry a table AND a modal form, which is what pushes a body past 300
    lines. A landing page is bands (already cheap to write) and a detail page is a field list — those
    land clean. Each chunk declares props; the page keeps the state and wires them, and the analyzer
    checks the wiring against the chunk's real signature."""
    kind = str(page.get("kind") or "")
    # `pascal("")` answers "Item", so test the raw value: a page with no resource would otherwise be
    # split into chunks for an entity that does not exist.
    if kind not in CHUNKED_KINDS or not str(page.get("resource") or "").strip():
        return []
    resource = pascal(page["resource"])
    # The refiner never sets `owner_role`, but the path carries it: `/pharmacist/medicines`. Without
    # this every role's page asked for the same `MedicineTable`, the dedup dropped all but the first,
    # and the other nine CRUD pages went on writing their own 340-line bodies. Roles differ for real
    # (admin deletes, cashier only looks), so each gets its own chunk rather than sharing one.
    role = str(page.get("owner_role") or "").strip()
    if not role:
        head = str(page.get("path") or "/").strip("/").split("/")[0]
        role = head if head and head != route_name(resource) else "shared"
    taken = {c.get("name") for c in existing}
    seg = route_name(resource)
    out = []
    for suffix, ctype, props in (
        ("Table", "data_table",
         f"rows: {resource}[]; onEdit: (row: {resource}) => void; onDelete: (id: string) => void"),
        ("FormDialog", "form",
         f"open: boolean; editing: {resource} | null; onClose: () => void; onSaved: () => void"),
    ):
        name = f"{pascal(role)}{resource}{suffix}" if role != "shared" else f"{resource}{suffix}"
        if name in taken:
            continue
        out.append({
            "name": name, "type": ctype, "props": props, "roles": [role],
            "allowed_resources": [resource],
            "task": (f"The {suffix.lower()} for {resource} records at `/api/{seg}`."
                     + (" Render the rows it is given — do NOT fetch; the page owns the data."
                        if suffix == "Table" else
                        f" It owns its own form state: seed from `editing` when set, POST to "
                        f"`/api/{seg}` to create or PUT to `/api/{seg}/<id>` to update, then call "
                        f"`onSaved()` and `onClose()`.")),
        })
    return out


def _deps_intact(project_dir: Path) -> bool:
    """Is node_modules actually usable, or just present?

    Every declared dependency must have a package.json, and `@mui/icons-material` — the package the
    Windows extraction races truncate, since it is ~21k one-file-per-icon modules — must still hold a
    canonical icon. A half-extracted tree keeps its package.json, so npm calls it installed and the
    failure only surfaces as `Module not found: '@mui/icons-material/<Icon>'` at build time."""
    nm = project_dir / "node_modules"
    try:
        pkg = json.loads((project_dir / "package.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return False
    for name in (pkg.get("dependencies") or {}):
        if not (nm.joinpath(*name.split("/")) / "package.json").exists():
            return False
    icons = nm / "@mui" / "icons-material"
    if icons.exists() and not all((icons / f"{i}.js").exists()
                                  for i in ("Add", "Edit", "Delete", "Favorite", "Search")):
        return False
    return True


def _synthesize_single_page(spec: dict, models: list) -> None:
    """Give a single-page spec the one page it implies, so it plans like any other app.

    The whole file plan is built from `spec['pages']`, which the refiner fills for multipage apps
    only — a single-page spec therefore planned models + routes and NO UI at all. It went unnoticed
    because the old keyword scan classified nearly every idea as multipage. The refiner already
    describes the page in `spec['sections']` (Hero, QuickAdd, EntryList, …); SectionAgent already
    renders plain-string sections under its `landing` kind. Only the page entry was missing.
    """
    if spec.get("pages") or spec.get("app_kind") == "multipage-app":
        return
    resource = next((pascal(m["name"]) for m in models
                     if m.get("name") and pascal(m["name"]) != "User"), "")
    page = {
        "path": "/",
        "title": spec.get("title") or spec.get("brand_name") or "Home",
        "kind": "landing",
        "access": "public",
        "sections": [str(s) for s in (spec.get("sections") or []) if str(s).strip()],
    }
    if resource:
        page["resource"] = resource
    spec["pages"] = [page]


def generate_app(spec: dict, project_dir, emit=None, *, install=True, fix=True,
                 fix_iters=3) -> dict:
    emit = emit or (lambda *a, **k: None)
    project_dir = Path(project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)
    model = spec.get("build_model") or llm.GEN_MODEL

    models = list(spec.get("data_model") or [])
    _synthesize_single_page(spec, models)
    pages = [p for p in (spec.get("pages") or [])
             if p.get("path") and str(p.get("kind")) != "auth"
             and str(p.get("path")) not in SKIP_PATHS]
    kits = set(spec.get("kits") or [])

    # ── 0. check the SPEC before generating anything from it ──────────────────
    # `validate_spec` was written and unit-tested but never called on this path — duplicate routes,
    # component-name collisions and unknown role/ref references were free to reach the model, which
    # then spent minutes writing files that could not agree with each other.
    quality_contract = quality.build_contract(spec)
    spec_issues = quality.validate_spec(spec, quality_contract)
    for issue in spec_issues:
        emit("log", {"text": f"spec check: {issue}"})
    if spec_issues:
        emit("log", {"text": f"spec check: {len(spec_issues)} issue(s) — generating anyway, "
                             f"they are reported above"})

    # ── 1. fixed core ─────────────────────────────────────────────────────────
    emit("phase", {"name": "core"})
    core_map = core.core_files(spec)
    for rel, content in core_map.items():
        fp = project_dir / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        emit("file", {"path": rel, "content": content})
    emit("log", {"text": f"core: {len(core_map)} fixed files"})

    # ── 1a. install NOW, alongside generation ────────────────────────────────
    # package.json/tsconfig are deterministic and already on disk, so the install can run while the
    # model works. It used to run after every file was generated, which meant nothing could typecheck
    # a file until the whole app was written — the analyzer needs the app's real node_modules, and by
    # the time the first .tsx is generated (models + routes = several minutes of LLM) this is done.
    install_done: list = []
    install_thread = None
    if install:
        emit("phase", {"name": "install"})

        def _install_bg():
            install_done.append(_install(project_dir, emit))

        install_thread = threading.Thread(target=_install_bg, daemon=True)
        install_thread.start()

    # If the input declares no public "/" page (role-wise apps route to /admin, /waiter, …),
    # add a deterministic root that redirects to /login so "/" never 404s. Only ever in an app that
    # HAS a /login page — a no-auth app was left redirecting "/" to a route that doesn't exist.
    if (scaffold.auth_enabled(spec)
            and not any(str(p.get("path")) == "/" for p in (spec.get("pages") or []))):
        root = ("import { redirect } from 'next/navigation'\n\n"
                "export default function Page() {\n  redirect('/login')\n}\n")
        (project_dir / "app" / "page.tsx").write_text(root, encoding="utf-8")
        emit("file", {"path": "app/page.tsx", "content": root})

    # ── 1b. canonical contract registry — ONE source of truth for entity fields ──
    # Emit typed DTOs (`types/<Entity>.ts`) the frontend consumes so TypeScript catches field-name
    # drift, and CONTRACT.md so every agent uses the SAME field names in models/routes/forms/pages.
    from agents import contract as contract_mod
    registry = contract_mod.build_registry(spec)
    for rel, content in contract_mod.types_files(registry).items():
        fp = project_dir / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        emit("file", {"path": rel, "content": content})
    if registry:
        emit("log", {"text": f"contract: {len(registry)} entity DTO(s) → types/*.ts"})

    # ── 1c. human-like design plan — per-page ARCHETYPE so pages look like what they ARE ──
    from agents.design import planner as design_planner
    design = design_planner.plan(spec)
    locdir = project_dir / ".locode"
    locdir.mkdir(parents=True, exist_ok=True)
    import json as _json
    (locdir / "design-brief.json").write_text(_json.dumps(design["brief"], indent=2, default=str),
                                              encoding="utf-8")
    (locdir / "page-contracts.json").write_text(_json.dumps(design["pages"], indent=2, default=str),
                                               encoding="utf-8")
    emit("log", {"text": "design: archetypes " + ", ".join(
        sorted({c["archetype"] for c in design["pages"]}))})

    # ── 2. memory + agents ────────────────────────────────────────────────────
    mem = Memory(project_dir, spec)
    mem.set_contract(contract_mod.contract_md(registry))

    # The generator's compiler. Built lazily on first use so the install thread (started above) has
    # finished by then — the first .tsx is minutes of LLM away. Every agent shares the one process:
    # it holds an incremental program, so per-file checks stay ~1s instead of rebuilding each time.
    analyzer_box: dict = {}

    def get_analyzer():
        if "a" not in analyzer_box:
            if install_thread and install_thread.is_alive():
                emit("log", {"text": "waiting for install before the first typecheck…"})
                install_thread.join()
            analyzer_box["a"] = Analyzer(project_dir, emit)
        return analyzer_box["a"]

    ma = ModelAgent(project_dir, mem, emit, model, get_analyzer, quality_contract)
    ra = RouteAgent(project_dir, mem, emit, model, get_analyzer, quality_contract)
    la = LogicAgent(project_dir, mem, emit, model, get_analyzer, quality_contract)
    pa = PageAgent(project_dir, mem, emit, model, get_analyzer, quality_contract)
    sa = SectionAgent(project_dir, mem, emit, model, get_analyzer, quality_contract)
    ca = ComponentAgent(project_dir, mem, emit, model, get_analyzer, quality_contract)

    # ── declared inventory (role-wise SRS): every substantial component becomes its own small
    # self-contained file, added to the plan so the completeness re-scan + regen fallback cover them.
    # NOTE: the per-role SIDEBAR is provided by the fixed auth section layout (app/<seg>/layout.tsx →
    # components/Sidebar.tsx); page bodies must NOT render their own sidebar/workspace (that caused the
    # double-sidebar bug), so there is no LayoutAgent/Workspace here.
    contracts = list(spec.get("component_contracts") or [])
    feature_targets: dict[str, str] = {}   # component name → file path
    for c in contracts:
        if not c.get("name") or str(c.get("type")) in INLINE_COMPONENT_TYPES:
            continue
        feature_targets[c["name"]] = _contract_target(c)

    def page_imports(p: dict) -> list[tuple[str, str]]:
        """(ComponentName, module path) for this page's declared components that have files."""
        out, seen = [], set()
        for sec in (p.get("sections") or []):
            if not isinstance(sec, dict):
                continue          # a plain-string label (single-page/AutoHub specs) declares no components
            for cn in (sec.get("components") or []):
                if cn in feature_targets and cn not in seen:
                    seen.add(cn)
                    out.append((cn, _module_path(feature_targets[cn])))
        return out

    # Explicit file plan → every declared artifact, so none is missed. Each entry maps an
    # output path to (kind, payload) used both to generate and to REGENERATE if missing.
    plan: dict[str, tuple] = {}
    for m in models:
        name = pascal(m.get("name", "Item"))
        seg = route_name(name)
        plan[f"models/{name}.ts"] = ("model", m)
        plan[f"app/api/{seg}/route.ts"] = ("route", m)
        plan[f"app/api/{seg}/[id]/route.ts"] = ("route", m)
    logic_plan = []
    names = {pascal(m["name"]) for m in models}
    if "pos" in kits:
        logic_plan.append(("app/api/pos/checkout/route.ts",
                           "POS checkout: validate + decrement stock, write StockMovement per line, "
                           "create the sale and (if an Invoice model exists) an invoice; totals server-side."))
    if "invoicing" in kits and "Invoice" in names:
        logic_plan.append(("app/api/invoices/[id]/payments/route.ts",
                           "Record a payment against the invoice id, derive status unpaid/partial/paid, "
                           "recompute balance; reject overpayment."))
    if "reports" in kits:
        logic_plan.append(("app/api/reports/route.ts",
                           "Return aggregated real values selected by ?type= from the collections."))
    for pth, task in logic_plan:
        plan[pth] = ("logic", (pth, task))
    for name, rel in feature_targets.items():
        contract = next(c for c in contracts if c.get("name") == name)
        plan[rel] = ("component", contract)
    comp_by_path = uniquify_component_names(pages)   # path → UNIQUE body-component name (no collisions)
    for p in pages:
        comp = comp_by_path[str(p.get("path"))]
        # A CRUD page written in one shot lands at 300-340 lines, and that is where the model loses
        # the thread and truncates mid-JSX — measured at ~5% of files, and the only failure a
        # regeneration cannot fix (the rewrite is just as long: 4 diagnostics → 4 → 4). Split the two
        # heavy pieces out; each lands ~90-110 lines and the page keeps the state that drives them.
        for chunk in _page_chunks(p, contracts):
            rel = _contract_target(chunk)
            feature_targets[chunk["name"]] = rel
            contracts.append(chunk)
            plan[rel] = ("component", chunk)
            p.setdefault("sections", [])
            p["sections"].append({"section_name": chunk["name"], "components": [chunk["name"]]})
        plan[page_file(p["path"])] = ("page", (p, comp))
        plan[f"components/pages/{comp}.tsx"] = ("section", (p, comp))

    emit("phase", {"name": "planner"})
    mem.write_all(tasks=list(plan.keys()))
    mem.write_locations(plan)   # .locode/LOCATIONS.md — path map the bug-fixer feeds to the repair LLM
    # Surface the planner + memory in the UI (TASKS.md is the authoritative file checklist).
    locdir = project_dir / ".locode"
    for md in (sorted(locdir.glob("*.md")) if locdir.exists() else []):
        try:
            emit("file", {"path": f".locode/{md.name}", "content": md.read_text(encoding="utf-8")})
        except Exception:
            pass
    emit("log", {"text": f"plan: {len(plan)} files — {len(models)} models, {len(pages)} pages, "
                         f"{len(feature_targets)} components, {len(logic_plan)} logic; "
                         f"valid routes: {len(mem.valid_routes())}"})
    for rel in plan:
        emit("log", {"text": f"  · planned {rel}"})

    def _write(rel: str, content: str):
        fp = project_dir / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        emit("file", {"path": rel, "content": content})

    # With a strong hosted model (Gemini), the LLM generates the app-specific files — models, CRUD
    # routes, components, pages. Only the common framework boilerplate (db, api helpers, tailwind/config,
    # auth, UI primitives, reports) stays deterministic (see core.core_files) so no API tokens are spent
    # regenerating identical-across-apps files.
    def dispatch(kind, payload):
        if kind == "model":
            ma.generate(payload)
        elif kind == "route":
            ra.generate(payload)
        elif kind == "logic":
            la.generate(payload[0], payload[1])
        elif kind == "component":
            ca.generate_contract(payload, _contract_target(payload))
        elif kind == "page":
            pa.generate(payload[0], payload[1])
        elif kind == "section":
            p, comp = payload
            dc = design["by_path"].get(p.get("path"), {})
            sa.generate(p, comp, imports=page_imports(p),
                        archetype=dc.get("archetype", ""), pattern=dc.get("pattern", ""))

    # ── 3-6. generate everything in plan order (deps resolve: models→routes→logic→
    #         declared components→role layouts→page bodies compose them→page wrappers) ──
    emit("phase", {"name": "models"})
    for m in models:
        ma.generate(m)
    emit("phase", {"name": "routes"})
    for m in models:
        ra.generate(m)
    if logic_plan:
        emit("phase", {"name": "logic"})
        for pth, task in logic_plan:
            la.generate(pth, task)
    if feature_targets:
        emit("phase", {"name": "components"})
        for name, rel in feature_targets.items():
            dispatch("component", next(c for c in contracts if c.get("name") == name))
    # Body BEFORE its wrapper: the wrapper imports `@/components/pages/<Comp>`, so generating it first
    # meant importing a file that did not exist yet. The compiler in the loop makes that visible and
    # expensive — every wrapper burned its full regeneration budget on a module the model could not
    # have created. Producers before consumers; the wrapper is now checked against a real body.
    emit("phase", {"name": "pages"})
    for p in pages:
        comp = comp_by_path[str(p.get("path"))]
        dispatch("section", (p, comp))
        pa.generate(p, comp)

    # ── 7. completeness / quality gates — SHARED regen budget ─────────────────
    # Every post-generation gate below (missing, truncated, unresolved-import, field-drift) draws from
    # ONE per-file budget. Previously each gate independently re-`dispatch`ed the same path every round
    # with no "did that help?" check, so a file that a regen couldn't fix was rewritten 6–8× (the
    # `app/api/<x>/route.ts` ×6/×8 bug). Now: at most PREBUILD_REGEN_CAP regens per file across all
    # gates, and the import/drift gates FREEZE a file the moment a regen fails to reduce its own issues.
    PREBUILD_REGEN_CAP = 2
    regen_used: dict[str, int] = {}

    def _regen(rel: str) -> bool:
        """Regenerate a planned file, but never more than PREBUILD_REGEN_CAP times across all gates."""
        if rel not in plan or regen_used.get(rel, 0) >= PREBUILD_REGEN_CAP:
            return False
        regen_used[rel] = regen_used.get(rel, 0) + 1
        dispatch(*plan[rel])
        return True

    def _guarded_gate(scan, rounds: int, label: str) -> dict:
        """Scan→regen loop that stops touching a file once a regen fails to reduce THAT file's issue
        count (or its budget is spent). `scan()` returns {rel: [issues]}. Returns the final leftover."""
        frozen: set[str] = set()
        for _ in range(rounds):
            issues = {r: v for r, v in scan().items() if r not in frozen}
            if not issues:
                return {}
            n = sum(len(v) for v in issues.values())
            emit("log", {"text": f"{label}: {n} issue(s) in {len(issues)} file(s); "
                                 f"regenerating {list(issues)[:5]}"})
            before = {r: len(v) for r, v in issues.items()}
            acted = False
            for rel in list(issues):
                if _regen(rel):
                    acted = True
                else:
                    frozen.add(rel)          # not planned, or budget spent → stop retrying it
            if not acted:
                break
            after = scan()
            for rel, cnt in before.items():
                if len(after.get(rel, [])) >= cnt:   # regen didn't reduce this file's issues → give up
                    frozen.add(rel)
        return scan()

    def missing_files():
        out = []
        for rel in plan:
            fp = project_dir / rel
            if not fp.exists() or fp.stat().st_size < 12:
                out.append(rel)
        return out

    emit("phase", {"name": "verify-complete"})
    for rnd in range(2):
        miss = missing_files()
        if not miss:
            break
        emit("log", {"text": f"regenerating {len(miss)} missing file(s): {miss[:6]}"})
        if not any(_regen(rel) for rel in miss):
            break                                     # budget spent — the build/fix loop takes it from here
    miss = missing_files()
    if miss:
        emit("log", {"text": f"WARNING still missing after retries: {miss}"})
    else:
        emit("log", {"text": f"all {len(plan)} planned files present"})

    # per-file validation gate: regenerate a file if it looks truncated/unbalanced, so truncation is
    # caught at the source (per file) before the build/fix loop accumulates errors.
    regenerated = 0
    for rel in list(plan):
        if not rel.endswith((".ts", ".tsx")):
            continue
        fp = project_dir / rel
        if not fp.exists():
            continue
        try:
            text = fp.read_text(encoding="utf-8")
        except Exception:
            continue
        if _file_incomplete(text) and _regen(rel):
            emit("log", {"text": f"validation gate: regenerating incomplete {rel}"})
            regenerated += 1
    if regenerated:
        emit("log", {"text": f"validation gate regenerated {regenerated} file(s)"})

    # ── 7b. module-existence gate — guarantee every import resolves BEFORE the build ──
    # Deterministic remaps (path drift / case / plural) run inside repair_imports; only files whose
    # imports STILL don't resolve are regenerated — guarded + budgeted so nothing loops.
    leftover = _guarded_gate(lambda: module_gate.repair_imports(project_dir), 3, "module gate")
    if leftover:
        emit("log", {"text": f"module gate: WARNING unresolved imports remain in {list(leftover)[:5]}"})
    else:
        emit("log", {"text": "module gate: all imports resolve"})

    # ── 7c. contract-usage gate — catch model↔frontend field-name drift before the build ──
    from agents.repair import contract_scan
    drift_left = _guarded_gate(lambda: contract_scan.scan_project(project_dir, registry), 2, "contract gate")
    for rel, fs in drift_left.items():
        bad = ", ".join(sorted({f["field"] for f in fs}))
        emit("log", {"text": f"contract gate: {rel} uses unknown fields: {bad}"})

    # ── 7d. what the compiler cannot see ──────────────────────────────────────
    # A green build says nothing about a "Login" button in an app with no login page, or "10k+ Active
    # Members" on an app with no users — both shipped this week. `static_scan` catches exactly those
    # (undeclared-route, undeclared-api, hardcoded metrics, mixed id/_id) and has never once run.
    scan_findings = quality.static_scan(project_dir, quality_contract)
    for f in scan_findings[:12]:
        emit("log", {"text": f"static scan: {f['file']} — {f['message']} [{f['signature']}]"})
    if scan_findings:
        emit("log", {"text": f"static scan: {len(scan_findings)} finding(s) the build will not catch"})
    else:
        emit("log", {"text": "static scan: clean"})

    # ── 8. install + bug-fix loop ─────────────────────────────────────────────
    result = {"models": len(models), "pages": len(pages), "planned": len(plan),
              "missing": miss, "built": None, "static_findings": len(scan_findings)}
    # Generation is over — the analyzer's work is done. Close it here rather than leaking a node
    # process per app; the harness has its own `tsc` and doesn't share this one.
    if "a" in analyzer_box:
        analyzer_box.pop("a").close()
    if install:
        # Started before generation; normally long finished by now. Only its RESULT is needed here.
        if install_thread:
            install_thread.join()
        if not (install_done and install_done[0]):
            emit("done", {"ok": False})
            result["built"] = False
            return result
    if fix:
        emit("phase", {"name": "build+fix"})

        def regen(rel):
            """Last-resort single-file regeneration for the repair harness (leaf files only)."""
            if rel in plan:
                try:
                    dispatch(*plan[rel])
                    return True
                except Exception:  # noqa: BLE001
                    return False
            return False

        # P1 harness: single diagnosis (module+contract+tsc) → producers-first bounded repair →
        # rollback on regression → next-build verify. Converges in 1–2 rounds vs. one-error-per-build.
        from agents.repair.harness import RepairHarness
        harness = RepairHarness(project_dir, emit, model, registry=registry, regen=regen,
                                on_revert=mem.note_reverted)
        result["built"] = harness.run(max_rounds=fix_iters)
        emit("done", {"ok": result["built"]})

    # ── 9. deterministic visual/layout review (informational design QA) ──
    from agents.design.visual_review import review_project
    vr = review_project(project_dir, design)
    if vr:
        total = sum(len(v) for v in vr.values())
        emit("log", {"text": f"visual review: {total} layout note(s) across {len(vr)} page(s)"})
        for rel, notes in list(vr.items())[:8]:
            emit("log", {"text": f"  {rel}: " + ", ".join(sorted({n['rule'] for n in notes}))})
        result["visual_notes"] = total
    else:
        emit("log", {"text": "visual review: no layout issues detected"})
    return result
