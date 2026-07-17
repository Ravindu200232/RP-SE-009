"""agents/memory.py — the per-build markdown memory the generation agents share.

The generator writes a `.locode/` knowledge base into every project (a dotdir Next.js ignores,
so it never affects the build). Each agent READS the slices it needs (MODELS/ROUTES/API + the
rule doc) and, after producing an artifact, the memory is UPDATED so later agents stay consistent
across many files. This is the "large memory" that keeps gemma4:12b coherent.

Docs:
  PROJECT.md    — app summary, roles, theme
  ENTITIES.md   — entity list (human overview)
  MODELS.md     — every model + fields + refs (the canonical data memory)
  ROUTES.md     — every page route + kind + access + resource
  API.md        — every API endpoint + method (the api-links memory)
  COMPONENTS.md — reusable components produced
  TASKS.md      — ordered build task list
  PROGRESS.md   — append-only log of files written
"""
from __future__ import annotations

import re
from pathlib import Path

from agents.scaffold import pascal, route_name, _palette


def _slug(text: str) -> str:
    """A shape key ('section:table-crud', 'component:data_table') as a safe filename."""
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "x"


# ── field / model rendering ───────────────────────────────────────────────────

def _field_line(f: dict) -> str:
    parts = [f"`{f.get('name')}`", str(f.get("type", "String"))]
    if f.get("enum"):
        parts.append("enum[" + " | ".join(str(v) for v in f["enum"]) + "]")
    if f.get("ref"):
        parts.append(f"ref->{f['ref']}")
    flags = []
    if f.get("required"):
        flags.append("required")
    if f.get("unique"):
        flags.append("unique")
    if f.get("isEmbeddedArray"):
        flags.append("embedded[]")
    if "default" in f:
        flags.append(f"default={f['default']}")
    if flags:
        parts.append("(" + ", ".join(flags) + ")")
    return "  - " + " ".join(parts)


class Memory:
    def __init__(self, project_dir, spec: dict):
        self.dir = Path(project_dir) / ".locode"
        self.spec = spec
        self.models = list(spec.get("data_model") or [])
        self.roles = list(spec.get("roles") or [])
        self.pages = list(spec.get("pages") or [])
        self.kits = list(spec.get("kits") or [])
        self._progress: list[str] = []
        self._components: list[str] = []
        self._contract: str = ""   # CONTRACT.md — the ONLY valid field names per entity (set by orchestrator)

    def set_contract(self, md: str):
        self._contract = md or ""

    def contract_md(self) -> str:
        return self._contract

    # ── model / api helpers used by agents ────────────────────────────────────
    def model_names(self) -> list[str]:
        return [pascal(m.get("name", "Item")) for m in self.models]

    def entity(self, name: str) -> dict | None:
        want = pascal(name)
        return next((m for m in self.models if pascal(m.get("name", "")) == want), None)

    def seg_for(self, name: str) -> str:
        return route_name(pascal(name))

    def valid_routes(self) -> list[str]:
        """Every page route that actually exists in the built app (for link-correctness)."""
        out, seen = [], set()
        for p in self.pages:
            r = str(p.get("path") or "").strip()
            if r and r not in seen:
                seen.add(r); out.append(r)
        for extra in ("/login", "/dashboard", "/dashboard/users"):
            if extra not in seen:
                seen.add(extra); out.append(extra)
        return out

    def routes_block(self) -> str:
        """The authoritative list of linkable routes — agents must not invent others."""
        lines = ["# VALID ROUTES — the ONLY pages that exist. Never link (href) anywhere else "
                 "or the app 404s.", ""]
        for p in self.pages:
            if str(p.get("kind")) == "auth":
                continue
            lines.append(f"- `{p.get('path')}`  ({p.get('kind')}, {p.get('access', 'public')})")
        lines.append("- `/login`  (sign in)")
        lines.append("- `/dashboard/users`  (admin only)")
        return "\n".join(lines) + "\n"

    # ── document builders ─────────────────────────────────────────────────────
    def project_md(self) -> str:
        s = self.spec
        acc, acc2 = _palette(s)
        lines = [f"# PROJECT — {s.get('title', 'App')}", "",
                 s.get("description", ""), "",
                 f"- Theme: {s.get('color_scheme', '')}",
                 f"- Palette: accent `{acc}`, accent2 `{acc2}`",
                 f"- Audience: {s.get('target_audience', '')}",
                 f"- Kits/behaviours: {', '.join(self.kits) or '(none)'}", "",
                 "## Roles"]
        for r in self.roles:
            lines.append(f"- `{r.get('name')}` ({r.get('label', '')}) — {r.get('access', '')}")
        return "\n".join(lines) + "\n"

    def models_md(self) -> str:
        lines = ["# MODELS", "",
                 "Every generated Mongoose model. Refs MUST point at a model name below.", ""]
        for m in self.models:
            name = pascal(m.get("name", "Item"))
            lines.append(f"## {name}  (collection `{m.get('collection', route_name(name))}`)")
            for f in (m.get("fields") or []):
                if f.get("name"):
                    lines.append(_field_line(f))
            lines.append("")
        return "\n".join(lines) + "\n"

    def entities_md(self) -> str:
        lines = ["# ENTITIES", ""]
        for m in self.models:
            name = pascal(m.get("name", "Item"))
            nfields = len([f for f in (m.get('fields') or []) if f.get('name')])
            lines.append(f"- **{name}** — {nfields} fields, route `/api/{route_name(name)}`")
        return "\n".join(lines) + "\n"

    def routes_md(self) -> str:
        lines = ["# ROUTES", "", "Every page route the app must expose.", ""]
        for p in self.pages:
            acc = p.get("access", "public")
            res = p.get("resource") or "-"
            lines.append(f"- `{p.get('path')}` — kind=`{p.get('kind')}` access=`{acc}` resource=`{res}`")
            if p.get("sections"):
                names = [s.get("section_name") if isinstance(s, dict) else str(s) for s in p["sections"]]
                names = [n for n in names if n]
                if names:
                    lines.append(f"    sections: {', '.join(names)}")
            if p.get("functions"):
                lines.append(f"    functions: {', '.join(str(f) for f in p['functions'][:6])}")
        return "\n".join(lines) + "\n"

    def api_md(self) -> str:
        lines = ["# API endpoints", "",
                 "Fixed envelope: success `{ success:true, data }`, error `{ success:false, error }`.",
                 "Auth: `/api/auth/login|logout|me|register`. Admin: `/api/admin/users`.", "",
                 "## CRUD (per model)"]
        for m in self.models:
            seg = route_name(pascal(m.get("name", "Item")))
            lines.append(f"- `/api/{seg}` — GET list, POST create")
            lines.append(f"- `/api/{seg}/[id]` — GET one, PUT update, DELETE")
        if self.kits:
            lines.append("")
            lines.append("## Business logic")
            if "pos" in self.kits:
                lines.append("- `/api/pos/checkout` — POST (validate+decrement stock, create sale/invoice)")
            if "invoicing" in self.kits:
                lines.append("- `/api/invoices/[id]/payments` — POST (record payment, derive status)")
            if "reports" in self.kits:
                lines.append("- `/api/reports?type=` — GET (aggregated real values)")
        return "\n".join(lines) + "\n"

    def components_md(self) -> str:
        lines = ["# COMPONENTS", ""]
        contracts = self.spec.get("component_contracts") or []
        if contracts:
            lines += ["## Declared (from the input) — every one MUST be generated", ""]
            for c in contracts:
                res = ", ".join(c.get("allowed_resources") or []) or "-"
                roles = ", ".join(c.get("roles") or []) or "-"
                lines.append(f"- `{c.get('name')}` — type={c.get('type', 'display')}; "
                             f"roles={roles}; resources={res}")
            lines.append("")
        lines += ["## Produced during this build", ""]
        lines += [f"- `{c}`" for c in self._components] or ["(none yet)"]
        return "\n".join(lines) + "\n"

    def _is_rolewise(self) -> bool:
        return bool(self.spec.get("component_contracts")) or any(
            p.get("id") and isinstance(p.get("sections"), list) for p in self.pages)

    def tasks_md(self, tasks: list[str]) -> str:
        flat = "# TASKS\n\n" + "\n".join(f"{i+1}. {t}" for i, t in enumerate(tasks)) + "\n"
        # For a role-wise SRS, lead with the full role→page→section→component→function tree
        # (the "complete task" the input declares), then the concrete build-file checklist.
        if self._is_rolewise():
            try:
                from agents.planner import build_plan, _tasks_markdown
                tree = _tasks_markdown(self.spec, build_plan(self.spec)).rstrip()
                files = "\n".join(f"{i+1}. {t}" for i, t in enumerate(tasks))
                return f"{tree}\n\n## Generated build files\n\n{files}\n"
            except Exception:
                pass
        return flat

    def progress_md(self) -> str:
        return "# PROGRESS\n\n" + "\n".join(f"- {p}" for p in self._progress) + "\n"

    # ── disk + mutation ───────────────────────────────────────────────────────
    def write_all(self, tasks: list[str] | None = None):
        self.dir.mkdir(parents=True, exist_ok=True)
        docs = {
            "PROJECT.md": self.project_md(),
            "ENTITIES.md": self.entities_md(),
            "MODELS.md": self.models_md(),
            "ROUTES.md": self.routes_md(),
            "API.md": self.api_md(),
            "COMPONENTS.md": self.components_md(),
            "PROGRESS.md": self.progress_md(),
        }
        if self._contract:
            docs["CONTRACT.md"] = self._contract
        if tasks is not None:
            docs["TASKS.md"] = self.tasks_md(tasks)
        for name, text in docs.items():
            (self.dir / name).write_text(text, encoding="utf-8")

    def locations_md(self, plan: dict) -> str:
        """LOCATIONS.md — a compact {kind → on-disk path} map so the bug-fixer LLM knows WHERE each
        entity/model/route/api/page/component lives. Built from the orchestrator's file plan
        (path → (kind, payload)); this is the 'short memory with locations' the repair loop injects."""
        buckets: dict[str, list[str]] = {}
        for rel, entry in (plan or {}).items():
            kind = entry[0] if isinstance(entry, (list, tuple)) and entry else "other"
            buckets.setdefault(kind, []).append(rel)
        label = {"model": "Models (Mongoose)", "route": "API routes (CRUD)",
                 "logic": "API routes (business logic)", "component": "Feature components",
                 "page": "Page route wrappers", "section": "Page bodies"}
        lines = ["# LOCATIONS", "",
                 "Where each generated artifact lives on disk. Use these EXACT paths and names — "
                 "never invent new ones.", ""]
        for kind in ("model", "route", "logic", "component", "page", "section"):
            rels = sorted(buckets.get(kind) or [])
            if not rels:
                continue
            lines.append(f"## {label.get(kind, kind)}")
            lines += [f"- `{r}`" for r in rels]
            lines.append("")
        return "\n".join(lines) + "\n"

    def write_locations(self, plan: dict):
        self._flush("LOCATIONS.md", self.locations_md(plan))

    # ── exemplars: the app teaching itself ───────────────────────────────────
    # One app asks for the same shape a dozen times (12 tables + 12 form dialogs, one per
    # role×resource) and each was written cold, as if the eleven siblings that just compiled had never
    # existed. A file the compiler passed on the FIRST try is the best instruction available for the
    # next one of its shape — better than any rule, because it argues with nothing: it simply shows
    # the props that exist. It is not a template; the model reads a working sibling and writes its own
    # file for a different entity.
    #
    # Deliberately per-app (under this project's `.locode/`), NOT shared across runs: an exemplar
    # captured before a rule fix would faithfully teach the mistake that fix removed. Each one here
    # was verified minutes ago, by this run's compiler, under this run's rules.
    def store_exemplar(self, shape: str, code: str):
        if not shape or not (code or "").strip():
            return
        d = self.dir / "exemplars"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{_slug(shape)}.tsx").write_text(code, encoding="utf-8")

    def exemplar(self, shape: str) -> str | None:
        if not shape:
            return None
        try:
            return (self.dir / "exemplars" / f"{_slug(shape)}.tsx").read_text(encoding="utf-8")
        except OSError:
            return None

    def note_component(self, rel: str):
        if rel not in self._components:
            self._components.append(rel)
        self._flush("COMPONENTS.md", self.components_md())

    def note_progress(self, line: str):
        self._progress.append(line)
        self._flush("PROGRESS.md", self.progress_md())

    def note_reverted(self, rel: str):
        """Re-label the most recent `wrote <rel>` entry as a reverted regeneration.

        A repair regen that fails its guard still writes the file before being rolled back, so an
        untouched log counts it as real churn — that alone put a healthy file at 5 'writes'. The entry
        stays (the attempt is history) but no longer reads as a write that survived."""
        for i in range(len(self._progress) - 1, -1, -1):
            if f"wrote {rel} " in self._progress[i]:
                self._progress[i] = self._progress[i].replace(
                    f"wrote {rel} ", f"regen REVERTED (no-op) {rel} ", 1)
                self._flush("PROGRESS.md", self.progress_md())
                return

    def _flush(self, name: str, text: str):
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            (self.dir / name).write_text(text, encoding="utf-8")
        except Exception:
            pass

    # ── prompt context slices ─────────────────────────────────────────────────
    def context(self, *names: str) -> str:
        """Concatenate named memory docs for injection into an agent prompt."""
        builders = {
            "PROJECT": self.project_md, "MODELS": self.models_md, "ENTITIES": self.entities_md,
            "ROUTES": self.routes_md, "API": self.api_md, "COMPONENTS": self.components_md,
            "LINKS": self.routes_block, "CONTRACT": self.contract_md,
        }
        return "\n\n".join(builders[n]() for n in names if n in builders and builders[n]())
