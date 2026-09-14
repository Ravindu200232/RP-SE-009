"""Render the approved specification into the four shared agent handoff files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from types import SimpleNamespace

FILES = ("app.md", "sitemap.md", "prototype.md", "builder.md")


def _markdown(value, level=2) -> str:
    if isinstance(value, dict):
        return "\n\n".join(f"{'#' * min(level, 6)} {str(key).replace('_', ' ').title()}\n\n{_markdown(item, level + 1)}"
                           for key, item in value.items() if item not in (None, "", [], {}))
    if isinstance(value, list):
        return "\n\n".join(_markdown(item, level) if isinstance(item, (dict, list)) else f"- {item}" for item in value)
    return str(value if value is not None else "")


def write_handoff(target: Path, srs: dict, stack: str = "", *, refresh=False) -> Path:
    target = Path(target)
    spec = srs.get("srs_document") or srs
    tech = {"nextjs-mongo": "Next.js (App Router) + React + MongoDB/Mongoose",
            "mern-microservices": "React (Vite) + Express microservices + MongoDB/Mongoose + API gateway"}
    selected = SimpleNamespace(id=stack or "nextjs-mongo", tech=tech.get(stack or "nextjs-mongo", stack),
                               language="JavaScript (ESM)", rules=())
    description = _markdown({key: value for key, value in spec.items() if key not in ("approved_plan", "approved_plan_markdown", "builder_handoff")})
    signature = hashlib.sha256((description + selected.id).encode()).hexdigest()
    marker = target / "manifest.json"
    if not refresh and marker.is_file():
        previous = json.loads(marker.read_text(encoding="utf-8"))
        if previous.get("source") == signature and all((target / name).is_file() for name in FILES):
            return target
    target.mkdir(parents=True, exist_ok=True)
    # Keep the source's routes and links intact; no app-category inferred screens.
    route_sections = {}
    def routes(value, prefix=""):
        if isinstance(value, dict):
            for key, item in value.items():
                label = f"{prefix}.{key}".strip(".")
                if any(word in key.lower() for word in ("screen", "page", "route", "navigation", "journey", "flow", "role")):
                    route_sections[label] = item
                elif isinstance(item, (dict, list)):
                    routes(item, label)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                routes(item, f"{prefix}.{index}")
    routes(spec)
    contents = {
        "app.md": "# Application specification\n\n" + description + "\n",
        "sitemap.md": "# Site map\n\n" + (_markdown(route_sections) if route_sections else
            "Use the screens, roles and navigation described in app.md. Preserve their routes and relationships; do not invent an application category.") + "\n",
        "prototype.md": "# Design and HTML prototype\n\n"
            "Read app.md, sitemap.md and builder.md to understand the whole application. Apply the user's design customization. "
            "Build every specified screen as a complete, responsive HTML application in .agentforge/prototype/, using CSS for its design and JavaScript for working interactions. "
            "Start with index.html and link the screens so the specified journeys can be explored. Use meaningful content from the specification and include the relevant loading, empty, error and success states. "
            "Keep shared visual choices in styles.css and behavior in local scripts. Scope browser storage keys to this project. "
            "The prototype demonstrates interactions with sample data; never put credentials into it. "
            "Read existing files when continuing and change only what the request needs. Report missing information or failed validation clearly.\n\n"
            + _markdown(spec.get("ui_ux_requirements") or {}) + "\n",
        "builder.md": f"# Developer and QA handoff\n\nSelected stack: {selected.tech}. Language: {selected.language}.\n\n"
            "Read app.md and sitemap.md, then the generated files in .agentforge/prototype/. Build the application in the selected stack from that specification and the user's latest prototype. "
            "Preserve its screens, navigation, layout, content and interactions while connecting the real data and integrations. "
            "The planning and SRS reviews have already happened; proceed with implementation without generating another product plan. "
            "Use environment variables for configured credentials and this project's assigned runtime ports. "
            "Implement the specified access rules, validation and error handling. Verify the behavior changed with appropriate unit, integration and browser checks, "
            "repair actionable failures, and stop with a clear explanation if the same failure repeats without progress. "
            "Keep tests and their results with this application and report verification limitations accurately.\n\n"
            + "\n".join(f"- {rule}" for rule in selected.rules) + "\n",
    }
    for name, content in contents.items():
        from ..services.storage import write_text
        write_text(target / name, content)
    write_text(marker, json.dumps({"source": signature, "stack": selected.id, "files": list(FILES)}))
    return target
