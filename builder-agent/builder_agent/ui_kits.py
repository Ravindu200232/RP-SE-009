"""UI-kit scaffold overlays and requirement-curated page compositions."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from .skills import ASSET_ROOT


UI_KIT_ROOT = ASSET_ROOT / "ui-kits"
DEFAULT_UI_KIT = "shadcn"
MATERIAL_SOURCE_REF = "v9.4.0"
BLOCK_FILE_IGNORES = frozenset({
    ".git", ".next", ".turbo", "coverage", "dist", "node_modules", "test-results",
})
UI_KITS = {
    "shadcn": {
        "name": "Shadcn",
        "description": "Source-owned Tailwind and Radix primitives that are easy to reshape.",
        "usage": "Compose the installed local primitives and keep product components in domain folders.",
    },
    "chakra": {
        "name": "Chakra UI",
        "description": "Accessible React primitives with a token-first styling system.",
        "usage": "Use Chakra layout primitives and recipes through the installed provider.",
        "blockNote": "Chakra's official full-page blocks are Chakra Pro and require a Pro API key. The official Chakra v3 builder skill and framework scaffold remain available.",
    },
    "material": {
        "name": "Material UI",
        "description": "A broad production system for dense applications and workflows.",
        "usage": "Use MUI components and the installed theme; tie sx values to theme tokens.",
    },
}


GROUP_SIGNALS = {
    "hero": ("landing page", "home page", "homepage", "public site", "marketing", "hero"),
    "dashboard": ("dashboard", "analytics", "kpi", "metrics"),
    "application-shell": ("portal", "admin console", "back office", "management system"),
    "banner": ("banner", "announcement", "campaign", "notice bar"),
    "promo-banner": ("promotion", "promo", "free shipping"),
    "data-table": ("table", "records", "admin sees", "manage users"),
    "product-list": ("products", "catalog", "catalogue", "browse products"),
    "product-detail": ("product detail", "item detail"),
    "product-gallery": ("product gallery", "image gallery"),
    "shopping-cart": ("shopping cart", "cart"),
    "checkout": ("checkout", "payment", "place order"),
    "login": ("login", "sign in"),
    "signup": ("signup", "sign up", "register", "create account"),
    "settings-profile": ("settings", "profile", "preferences"),
    "order-history": ("order history", "past orders"),
    "order-summary": ("order summary", "receipt"),
    "navbar": ("navigation bar", "navbar"),
    "footer": ("footer",),
    "faq": ("faq", "frequently asked"),
    "pricing": ("pricing", "plans", "subscription tiers"),
    "testimonial": ("testimonials", "reviews", "customer stories"),
    "contact": ("contact page", "contact form"),
    "blog": ("blog", "articles"),
    "blog-post": ("blog post", "article page"),
    "team": ("team page", "staff"),
    "timeline": ("timeline", "history timeline"),
    "todo-list": ("todo", "task list"),
    "projects": ("project list", "projects"),
    "project": ("project detail",),
    "service": ("service detail",),
    "services": ("services page",),
}


@dataclass
class KitInstall:
    id: str = ""
    name: str = ""
    files: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class BlockInstall:
    files: list[str] = field(default_factory=list)
    reason: str = ""


def normalize_ui_kit(value: str | None) -> str:
    candidate = str(value or "").strip().lower()
    return candidate if candidate in UI_KITS else DEFAULT_UI_KIT


def ui_kit_of(workspace: Path | str) -> str:
    try:
        body = json.loads((Path(workspace) / ".agentforge/ui-kit.json").read_text(
            encoding="utf-8"))
        candidate = str(body.get("id") or "").strip().lower()
        return candidate if candidate in UI_KITS else ""
    except (OSError, ValueError, AttributeError):
        return ""


def catalogue(ui_kit: str) -> list[dict]:
    kit = normalize_ui_kit(ui_kit)
    try:
        body = json.loads((UI_KIT_ROOT / kit / "catalog.json").read_text(encoding="utf-8"))
        items = body.get("items") or []
        return [dict(item, uiLibrary=kit) for item in items
                if isinstance(item, dict) and item.get("id") and item.get("source")
                and item.get("preview") and (item.get("registry") or item.get("sourcePath"))]
    except (OSError, ValueError, AttributeError):
        return []


def planner_catalogue(ui_kit: str) -> str:
    kit = normalize_ui_kit(ui_kit)
    blocks = catalogue(kit)
    rows = [
        "UI BLOCK CURATION (use the approved requirements; this is not a separate feature list):",
        f"The selected UI framework is {UI_KITS[kit]['name']}.",
        "Below are real provider blocks available to this build. Choose only blocks required by "
        "screens in the plan. Do not choose a dashboard, banner, checkout, hero or other category "
        "unless the requested product needs it.",
    ]
    if not blocks:
        rows.extend([
            "This provider has no free full-block source available to install. Do not invent "
            "block names or substitute hand-made gallery items; build directly with its installed "
            "framework primitives.",
            "End the plan with exactly this line:",
            "UI BLOCKS :: none",
        ])
        return "\n".join(rows)
    grouped: dict[str, list[str]] = {}
    for block in blocks:
        grouped.setdefault(block.get("category", "block"), []).append(block["id"])
    rows.append("Available provider ids, grouped by their real category:")
    rows.extend(f"- {category}: {', '.join(ids)}"
                for category, ids in sorted(grouped.items()))
    rows.extend([
        "End the plan with exactly one line in this form, using every id needed to implement "
        "the requirements and no unrelated ids. There is no block-count limit; choose as many "
        "complete provider structures as the approved routes need:",
        "UI BLOCKS :: id, id",
    ])
    return "\n".join(rows)


def relevant_blocks(requirements_and_plan: str, ui_kit: str) -> list[dict]:
    text = str(requirements_and_plan or "")
    blocks = catalogue(ui_kit)
    marker = re.findall(r"UI BLOCKS\s*::\s*([^\n]+)", text, flags=re.IGNORECASE)
    if marker:
        named = {part.strip().strip("`").lower() for part in marker[-1].split(",")}
        return [block for block in blocks if block["id"] in named]
    lower = re.sub(r"\s+", " ", text.lower())
    groups = {group for group, signals in GROUP_SIGNALS.items()
              if any(signal in lower for signal in signals)}
    return [block for block in blocks if block.get("category") in groups]


def _merge_manifest(path: Path, patch: dict) -> None:
    body = json.loads(path.read_text(encoding="utf-8"))
    for field in ("dependencies", "devDependencies", "overrides"):
        additions = patch.get(field) or {}
        if additions:
            body[field] = {**(body.get(field) or {}), **additions}
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8", newline="")


def install_ui_kit(workspace: Path | str, stack: str, ui_kit: str) -> KitInstall:
    kit = normalize_ui_kit(ui_kit)
    root = UI_KIT_ROOT / kit / stack
    result = KitInstall(id=kit, name=UI_KITS[kit]["name"])
    try:
        config = json.loads((root / "kit.json").read_text(encoding="utf-8"))
        scaffold = root / "scaffold"
        if not scaffold.is_dir():
            result.reason = f"No {result.name} overlay ships for {stack}."
            return result
        for source in sorted(scaffold.rglob("*")):
            if not source.is_file():
                continue
            relative = source.relative_to(scaffold)
            destination = Path(workspace) / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            result.files.append(relative.as_posix())
        manifest = Path(workspace) / config["manifest"]
        _merge_manifest(manifest, config)
        if config["manifest"] not in result.files:
            result.files.append(config["manifest"])
        state = Path(workspace) / ".agentforge/ui-kit.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps({"id": kit, "name": result.name}, indent=2) + "\n",
                         encoding="utf-8", newline="")
        result.files.append(".agentforge/ui-kit.json")
    except (OSError, ValueError, KeyError) as error:
        result.reason = f"The {result.name} scaffold overlay could not be applied: {error}"
    return result


def install_blocks(workspace: Path | str, stack: str, ui_kit: str,
                   block_ids: list[str] | tuple[str, ...]) -> BlockInstall:
    kit = normalize_ui_kit(ui_kit)
    result = BlockInstall()
    blocks = catalogue(kit)
    known = {block["id"]: block for block in blocks}
    selected = [block_id for block_id in dict.fromkeys(block_ids or [])
                if block_id in known]
    if not selected:
        return result
    project_root = Path(workspace)
    frontend_root = project_root / "client" if stack == "mern-microservices" else project_root
    if kit == "material":
        return _install_material_sources(project_root, [known[item] for item in selected])
    if kit != "shadcn":
        result.reason = f"{UI_KITS[kit]['name']} has no free full-block source to install."
        return result

    def tracked_files():
        # Prune dependency/build trees before walking into them. Filtering the
        # results of rglob still traversed every node_modules entry after the
        # registry CLI installed dependencies, making a successful block add
        # appear to hang for minutes while Python scanned tens of thousands of
        # irrelevant files.
        for directory, child_dirs, filenames in os.walk(frontend_root):
            child_dirs[:] = [name for name in child_dirs if name not in BLOCK_FILE_IGNORES]
            folder = Path(directory)
            for filename in filenames:
                yield folder / filename

    before = {path: path.stat().st_mtime_ns for path in tracked_files()}
    executable = "npx.cmd" if os.name == "nt" else "npx"
    command = [executable, "--yes", "shadcn@latest", "add",
               *[known[block_id]["registry"] for block_id in selected],
               "--yes", "--overwrite", "--cwd", str(frontend_root)]
    try:
        completed = subprocess.run(command, cwd=str(frontend_root), capture_output=True,
                                   text=True, timeout=600, check=False)
        if completed.returncode:
            detail = "\n".join(part.strip() for part in
                               (completed.stdout, completed.stderr) if part.strip())
            detail = detail or "registry install failed"
            result.reason = detail[-1200:]
            return result
        after = [path for path in tracked_files()
                 if before.get(path) != path.stat().st_mtime_ns]
        result.files = [path.relative_to(project_root).as_posix() for path in sorted(after)]
        # A successful no-diff run means the exact registry sources were
        # already present. Keep it idempotent for follow-up builds instead of
        # reporting a false install failure.
    except (OSError, subprocess.TimeoutExpired) as error:
        result.reason = str(error)
    return result


def _github_json(url: str):
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "AgentForge-ui-block-installer",
    })
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def _download(url: str, destination: Path) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "AgentForge-ui-block-installer"})
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(body)
    return destination.as_posix()


def _install_material_sources(project_root: Path, selected: list[dict]) -> BlockInstall:
    """Save exact MIT-licensed MUI template sources beside the project.

    Material UI publishes its free page templates as source directories rather
    than as a registry package. One directory listing locates each selected
    tree, and the raw files download concurrently. The builder then adapts these
    provider files to the approved routes instead of reproducing them from a
    screenshot or generating a lookalike component.
    """
    result = BlockInstall()
    api_root = ("https://api.github.com/repos/mui/material-ui/contents/"
                "docs/data/material/getting-started/templates"
                f"?ref={MATERIAL_SOURCE_REF}")
    try:
        entries = _github_json(api_root)
        by_name = {entry.get("name"): entry for entry in entries if isinstance(entry, dict)}
        wanted = [*selected]
        if "shared-theme" in by_name:
            wanted.append({"id": "shared-theme", "sourcePath":
                           "docs/data/material/getting-started/templates/shared-theme"})

        downloads = []
        destination_root = project_root / ".agentforge" / "provider-blocks" / "material"
        for block in wanted:
            name = block["sourcePath"].rstrip("/").split("/")[-1]
            entry = by_name.get(name)
            if not entry or not entry.get("git_url"):
                raise OSError(f"Material UI source directory {name!r} was not found")
            tree = _github_json(f"{entry['git_url']}?recursive=1")
            for item in tree.get("tree") or []:
                if item.get("type") != "blob":
                    continue
                relative = str(item.get("path") or "").strip("/")
                if not relative or relative.startswith("."):
                    continue
                raw = (f"https://raw.githubusercontent.com/mui/material-ui/{MATERIAL_SOURCE_REF}/"
                       f"{block['sourcePath']}/{relative}")
                downloads.append((raw, destination_root / name / relative))

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda pair: _download(*pair), downloads))
        result.files = [
            (destination_root / block["sourcePath"].rstrip("/").split("/")[-1])
            .relative_to(project_root).as_posix()
            for block in wanted
        ]
    except (OSError, ValueError, KeyError, urllib.error.URLError) as error:
        result.reason = f"Material UI provider source could not be saved: {error}"
    return result
