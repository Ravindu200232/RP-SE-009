"""The verified starting point an empty workspace begins from.

The alternative is asking the model to write twenty boilerplate files from
memory before it reaches the first line of the actual product. That boilerplate
- the manifest, the database connection, the runner configs, the gateway - is
where most first-round failures came from, and none of it was ever specific to
the task. So it is copied, not written, and the model starts at the part that
actually differs.

Never touches a workspace that already contains a project.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import stack_for
from .skills import ASSET_ROOT

TEMPLATE_ROOT = ASSET_ROOT / "templates"

# A `.tpl` suffix stops npm treating the template as a workspace and stops a
# project's own runner discovering the template's suites. Scaffolding strips it.
TEMPLATE_SUFFIX = ".tpl"

# The engine's own directories do not make a workspace non-empty: a task that
# was planned, saved or restored has these and is still greenfield.
#
# `.env.example` is one of them, and leaving it out cost a whole stack: the
# setup step writes the names it asked about there, so a build that was asked
# anything at all arrived here with one file in the workspace, was declared to
# contain a project, and never got its template. The MERN builds that went
# through that had no .gitignore - which is also why their security review
# read the client bundle and reported four findings against React's own code.
ENGINE_ENTRIES = frozenset({".agent", ".agents", ".agentforge", ".git", ".gitignore",
                            ".env", ".env.local", ".env.example",
                            ".vscode", ".idea", "node_modules"})


@dataclass
class Scaffold:
    scaffolded: bool = False
    stack: str = ""
    files: list[str] = field(default_factory=list)
    preserved: list[str] = field(default_factory=list)
    reason: str = ""


def is_greenfield(workspace: Path | str) -> bool:
    try:
        return all(entry.name in ENGINE_ENTRIES for entry in Path(workspace).iterdir())
    except OSError:
        return False


def _template_files(root: Path) -> list[tuple[Path, str]]:
    files = []
    for source in sorted(root.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(root).as_posix()
        # Everything under scaffold/ is a skeleton to copy later, not part of
        # the project yet, so it keeps its guard suffix: stripping it there
        # would put a package.json npm might install and a test file the
        # project's runner would execute into a directory meant to be inert.
        inert = relative.startswith("scaffold/")
        target = (relative[:-len(TEMPLATE_SUFFIX)]
                  if not inert and relative.endswith(TEMPLATE_SUFFIX) else relative)
        files.append((source, target))
    return sorted(files, key=lambda pair: pair[1])


def _package_name(workspace: Path) -> str:
    base = re.sub(r"[^a-z0-9._-]+", "-", workspace.resolve().name.lower()).strip("-._")
    return base or "app"


def install_template(workspace: Path | str, stack_id: str = "") -> Scaffold:
    workspace = Path(workspace)
    stack = stack_for(stack_id)
    result = Scaffold(stack=stack.id)
    root = TEMPLATE_ROOT / stack.id

    if not root.is_dir():
        result.reason = f"No template ships for the {stack.id} stack."
        return result
    if not is_greenfield(workspace):
        result.reason = "The workspace already contains a project."
        return result

    try:
        for source, target in _template_files(root):
            destination = workspace / target
            destination.parent.mkdir(parents=True, exist_ok=True)
            # A file the workspace already has wins: a restored task can hold a
            # .gitignore or an .env, and the user's version is not ours to take.
            if destination.exists():
                result.preserved.append(target)
                continue
            body = source.read_text(encoding="utf-8", errors="replace")
            # Only the root manifest takes the folder's name. Renaming a nested
            # one gives every workspace the same name and npm refuses to install.
            if target == "package.json":
                body = re.sub(r'"name": "[^"]*"', f'"name": "{_package_name(workspace)}"', body, count=1)
            destination.write_text(body, encoding="utf-8", newline="")
            result.files.append(target)
    except OSError as error:
        result.reason = f"The template could not be written: {error}"
        return result

    result.scaffolded = bool(result.files)
    return result


def template_notice(result: Scaffold) -> str:
    """What the model is told about a workspace it did not create.

    Without this the first thing it does is write, from memory, the files that
    are already there - and the scaffold's whole value is lost.
    """
    if not result.scaffolded:
        return ""
    return "\n".join([
        f"SCAFFOLD: this empty workspace was initialised from the verified {result.stack} "
        "template before you started.",
        "them instead of installing or mixing another UI system.",
        "Every file below was installed, unit-tested, built and served before it became a "
        "template. Treat it as working code:",
        "\n".join(f"- {name}" for name in result.files),
        "",
        "Build on it. Do not rewrite these files from memory, and do not recreate a manifest, "
        "runner config, database connection, gateway or runtime script that is already here - "
        "read the file first and change only what this task needs.",
        "What is deliberately absent is yours to write: models, routes, pages, components, each "
        "service's own server, and the real stylesheet. The placeholder page and starter "
        "stylesheet exist only so the scaffold builds; replace them.",
        "Every path above is a file that already exists, so writeFile refuses it: to replace one "
        "outright pass overwrite:true, and to change part of one use patchFile. Reading the "
        "error to discover that costs a turn per file.",
        "If a scaffold/ directory is present it holds skeletons to copy, not files to run - read "
        "its README before adding a service or any other repeated part.",
        "The scaffold was verified before it shipped. Implement the complete product first, then "
        "install dependencies once and follow the build, runtime, unit and E2E order from the "
        "stack pack; do not spend an extra pass retesting the untouched placeholder.",
    ])


# The packages that turn the markup into a styled page. Losing one of these is
# the only kind of missing dependency that raises nothing at all: the build
# passes, the app serves, every test goes green, and the page renders as
# unstyled HTML because `@tailwind utilities` was a directive nobody compiled.
STYLING_TOOLCHAIN = ("tailwindcss", "postcss", "autoprefixer")

# The config files those packages read. Written by the scaffold; without them
# the toolchain is installed and still does nothing.
STYLING_CONFIGS = ("tailwind.config.mjs", "tailwind.config.js",
                   "postcss.config.mjs", "postcss.config.js")


def restore_styling(workspace: Path | str, stack_id: str = "") -> list[str]:
    """Put back the styling toolchain the scaffold shipped, if it went missing.

    A build rewrote package.json and the new one was the template's, byte for
    byte, minus three lines: tailwindcss, postcss and autoprefixer. The configs
    went with them. Everything still built and served, every suite passed, and
    the bakery it had just drawn so carefully came out as black text on white
    with the images stacked down the left.

    Nothing here overrules a project's own choices - only what the scaffold put
    there and the build dropped without replacing it. A project that genuinely
    has no stylesheet keeps none: the check is skipped unless the CSS still
    asks for Tailwind.
    """
    root = Path(workspace)
    template = TEMPLATE_ROOT / (stack_id or "")
    if not template.is_dir():
        return []

    manifest = root / "package.json"
    source = template / "package.json.tpl"
    if not manifest.is_file() or not source.is_file():
        return []

    # Only if the application still expects Tailwind to compile something.
    css = list(root.glob("app/globals.css")) + list(root.glob("**/globals.css"))
    wants = any("@tailwind" in p.read_text(encoding="utf-8", errors="replace")
                or "tailwindcss" in p.read_text(encoding="utf-8", errors="replace")
                for p in css[:5] if p.is_file())
    if not wants:
        return []

    try:
        have = json.loads(manifest.read_text(encoding="utf-8"))
        shipped = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []

    restored = []
    dev = have.setdefault("devDependencies", {})
    shipped_dev = {**shipped.get("dependencies", {}), **shipped.get("devDependencies", {})}
    for name in STYLING_TOOLCHAIN:
        if name in shipped_dev and name not in dev and name not in have.get("dependencies", {}):
            dev[name] = shipped_dev[name]
            restored.append(name)
    if restored:
        have["devDependencies"] = dict(sorted(dev.items()))
        manifest.write_text(json.dumps(have, indent=2) + "\n", encoding="utf-8")

    for name in STYLING_CONFIGS:
        origin = template / name
        if origin.is_file() and not (root / name).is_file():
            (root / name).write_text(origin.read_text(encoding="utf-8"), encoding="utf-8")
            restored.append(name)

    return restored
