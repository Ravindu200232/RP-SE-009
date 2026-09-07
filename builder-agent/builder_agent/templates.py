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
ENGINE_ENTRIES = frozenset({".agent", ".agents", ".agentforge", ".git", ".gitignore",
                            ".env", ".env.local", ".vscode", ".idea", "node_modules"})


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
        "If a scaffold/ directory is present it holds skeletons to copy, not files to run - read "
        "its README before adding a service or any other repeated part.",
        "Run the install once, then the tests, before adding features: a scaffold that does not "
        "go green is worth knowing about immediately.",
    ])
