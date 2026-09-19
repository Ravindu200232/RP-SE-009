"""What a run actually changed on disk, as paths and a diff.

A completed change used to reach the other agent, and the parent
specification, as a single sentence - the one the model wrote about its own
work. Everything else was thrown away when the run ended: which files moved,
what the markup now says, whether a page was added at all. So the builder was
told "the prototype changed" and had to go and find out what that meant, and
the drawing of a page was re-derived from prose that had never seen it.

None of that evidence had to be recovered, because it was already on disk.
`snapshot_project` copies every source file before an edit so that one click
can undo it, and those copies are still there when the run finishes. The
difference between them and the working tree is the change, exactly.

Bounded, because the reader is a model: `MAX_FILES` paths, `MAX_DIFF_CHARS` of
diff in total and `MAX_FILE_DIFF` from any one file, and a file too large or
too binary to diff is named rather than quoted. Truncation is stated in the
text rather than hidden, so nothing downstream mistakes a cut-off diff for a
complete one.
"""
from __future__ import annotations

import difflib
import json
import os
import time
from pathlib import Path

CHANGE_FILE = "change.json"
# The same files `snapshot_project` keeps, so the two sides compare like with like.
TRACKED_EXT = {".js", ".jsx", ".ts", ".tsx", ".css", ".json", ".md", ".html", ".svg"}
SKIP_DIRS = {"node_modules", ".next", ".git", ".agentforge", ".agent", "coverage"}
MAX_FILES = 40
MAX_FILE_BYTES = 400_000
MAX_FILE_DIFF = 8_000
MAX_DIFF_CHARS = 24_000


def change_path(project_dir: Path | str, role: str) -> Path:
    return Path(project_dir) / ".agentforge" / "agents" / str(role) / CHANGE_FILE


def source_root(project_dir: Path | str, role: str) -> Path:
    """Where this role's work lives. The designer's is the prototype alone."""
    project_dir = Path(project_dir)
    return project_dir / ".agentforge" / "prototype" if role == "designer" else project_dir


def _walk(root: Path, project_dir: Path, *, prune: bool = True) -> dict[str, Path]:
    """Every tracked file under `root`, keyed by its path in the project.

    Pruned when walking a live project, where `node_modules` is most of the
    disk. Not pruned when walking a snapshot, which is already the filtered
    copy those rules produced - and which, being a copy of paths that begin
    `.agentforge/prototype/`, the same rules would otherwise discard whole.
    """
    found: dict[str, Path] = {}
    if not root.is_dir():
        return found
    for base, dirs, names in os.walk(root):
        if prune:
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            path = Path(base) / name
            if path.suffix.lower() not in TRACKED_EXT:
                continue
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
                relative = path.relative_to(project_dir).as_posix()
            except (OSError, ValueError):
                continue
            found[relative] = path
    return found


def _text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def capture(project_dir: Path | str, snapshot_id: str, role: str) -> dict:
    """Compare the snapshot this run started from with what is on disk now."""
    project_dir = Path(project_dir)
    store = project_dir / ".agentforge" / "undo" / str(snapshot_id or "") / "files"
    before = _walk(store, store, prune=False)
    after = _walk(source_root(project_dir, role), project_dir)
    rows, diffs, used, truncated = [], [], 0, False

    for relative in sorted(set(before) | set(after)):
        was, now = before.get(relative), after.get(relative)
        kind = "added" if not was else "deleted" if not now else "modified"
        old = _text(was) if was else ""
        new = _text(now) if now else ""
        if old is None or new is None:
            continue                       # unreadable now; naming it says nothing
        if kind == "modified" and old == new:
            continue
        if len(rows) >= MAX_FILES:
            truncated = True
            break
        rows.append({"path": relative, "kind": kind})
        if used >= MAX_DIFF_CHARS:
            truncated = True
            continue
        patch = "".join(difflib.unified_diff(
            old.splitlines(keepends=True), new.splitlines(keepends=True),
            fromfile=f"a/{relative}", tofile=f"b/{relative}", n=3))
        if len(patch) > MAX_FILE_DIFF:
            patch = patch[:MAX_FILE_DIFF] + f"\n… the rest of {relative} is not shown\n"
            truncated = True
        if used + len(patch) > MAX_DIFF_CHARS:
            patch = patch[:max(0, MAX_DIFF_CHARS - used)] + "\n… further changes are not shown\n"
            truncated = True
        diffs.append(patch)
        used += len(patch)

    return {"role": role, "at": time.time(), "files": rows,
            "diff": "".join(diffs), "truncated": truncated}


def from_edit(relative: str, before: str, after: str) -> dict:
    """The change one hand edit made, in the same shape a run's comparison has.

    An edit saved from the visual inspector never starts an agent, so there is
    no snapshot to compare against - but there is no need for one either, since
    the file that is about to be overwritten is the before.
    """
    if before == after:
        return {}
    patch = "".join(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile=f"a/{relative}", tofile=f"b/{relative}", n=3))
    truncated = len(patch) > MAX_FILE_DIFF
    if truncated:
        patch = patch[:MAX_FILE_DIFF] + f"\n… the rest of {relative} is not shown\n"
    return {"role": "designer", "at": time.time(), "truncated": truncated, "diff": patch,
            "files": [{"path": relative, "kind": "modified" if before else "added"}]}


def write(project_dir: Path | str, role: str, change: dict) -> Path:
    """Leave the change for the transaction that runs after this one."""
    path = change_path(project_dir, role)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(change, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read(project_dir: Path | str, role: str) -> dict:
    try:
        return json.loads(change_path(project_dir, role).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def clear(project_dir: Path | str, role: str) -> None:
    """Forget a change once it has been carried.

    A file left behind would be attached to the next run of the same role, and
    the sibling would be shown a diff belonging to work it had already applied.
    """
    try:
        change_path(project_dir, role).unlink(missing_ok=True)
    except OSError:
        pass


def touched(change: dict, *, under: str = "") -> list[str]:
    """The paths this change touched, optionally only those under a prefix."""
    return [str(row.get("path") or "") for row in (change or {}).get("files") or []
            if not under or str(row.get("path") or "").startswith(under)]


def brief(change: dict) -> str:
    """The change as something to put in front of an agent. Empty when there is none."""
    rows = (change or {}).get("files") or []
    if not rows:
        return ""
    lines = ["Files changed by that work:"]
    lines += [f"- {row.get('path')} ({row.get('kind')})" for row in rows]
    patch = str((change or {}).get("diff") or "").strip()
    if patch:
        lines += ["", "What changed in them, as a unified diff:", "```diff", patch, "```"]
    if (change or {}).get("truncated"):
        lines.append("(The list or the diff above was shortened. Read the files themselves "
                     "for anything it does not show.)")
    return "\n".join(lines)
