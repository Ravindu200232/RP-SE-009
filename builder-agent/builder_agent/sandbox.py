"""Workspace jail for every filesystem operation.

Paths reaching the file tools came out of a language model, so they cannot be
trusted: `../../etc/passwd`, an absolute system path, or a symlink pointing out
of the project all have to be refused before `open()` ever sees them. Every
file tool resolves through `Sandbox.resolve`; nothing opens a raw model-supplied
path.

What this does not protect against is an approved shell command that writes
outside the workspace. Commands run with the invoking user's privileges: the
jail constrains the file tools and `policy.py` constrains the shell. Real
isolation needs a container.
"""
from __future__ import annotations

import os
from pathlib import Path

from .errors import SecurityError

# Directories that are noise for a walk and expensive to descend.
IGNORED_DIRS = frozenset({
    "node_modules", ".git", ".svn", ".hg", "dist", "build", "out", "target",
    "coverage", ".next", ".nuxt", ".cache", ".turbo", ".venv", "venv",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".gradle", ".idea",
    ".vscode", "vendor", ".agent", ".terraform",
})

# Dot-directories that are the agent's own work and must stay findable.
#
# `.agentforge` holds the drawing - the pages the drawing pass writes and then
# has to search and revise. It was ignored here and, being a dot-directory,
# ignored twice over, so `search` could not see a file the same agent had just
# written. Every query came back "No match ... search for a shorter fragment",
# which is what the message advises, so a run hunting a class it had written
# went `href="gallery"` -> `href=` -> `href` -> `nav` -> `the`, each shorter
# and each empty, until the phase was spent. The pages were there the whole
# time; nothing could look at them.
VISIBLE_DOT_DIRS = frozenset({".agentforge"})

BINARY_SUFFIXES = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".avif", ".tiff",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv", ".flac", ".webm",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".exe", ".dll", ".so",
    ".dylib", ".bin", ".o", ".a", ".class", ".jar", ".pyc", ".wasm",
    ".db", ".sqlite", ".sqlite3",
})


def looks_binary(path: Path) -> bool:
    """Suffix first, then a NUL byte in the first 8 KiB."""
    if path.suffix.lower() in BINARY_SUFFIXES:
        return True
    try:
        with path.open("rb") as handle:
            return b"\0" in handle.read(8192)
    except OSError:
        return False


class Sandbox:
    """Resolves model-supplied paths, or refuses them."""

    def __init__(self, root: str | Path, *, role: str = "") -> None:
        self.root = Path(root).resolve()
        self.role = role
        # Resolve symlinks in the root once (/tmp -> /private/tmp on macOS) so
        # later real-path comparisons line up instead of always failing.
        try:
            self.real_root = self.root.resolve(strict=False)
        except OSError:
            self.real_root = self.root

    def resolve(self, raw: str, must_exist: bool = False) -> Path:
        if not isinstance(raw, str) or not raw.strip():
            raise SecurityError("A file path is required", path=raw)
        text = raw.strip()
        if "\0" in text:
            raise SecurityError("Path contains a null byte", path=raw)

        target = (self.root / text).resolve() if not os.path.isabs(text) else Path(text).resolve()
        if not self._inside(target):
            raise SecurityError(
                f"Path escapes the workspace: {text!r} resolves outside {self.root}. "
                "File tools may only touch files inside the workspace.",
                path=text, resolved=str(target))

        # A write targets a file that does not exist yet, so the symlink check
        # has to run against the deepest parent that does.
        nearest = self._nearest_real(target)
        if nearest and not self._inside(nearest):
            raise SecurityError(
                f"Path resolves through a symlink to outside the workspace: {text!r} -> {nearest}",
                path=text, resolved=str(nearest))

        if must_exist and not target.exists():
            raise SecurityError(f"No such file or directory: {self.relative(target)}", path=text)
        self.check_access(target)
        return target

    def check_access(self, target: Path, *, write: bool = False) -> None:
        if not self.role:
            return
        relative = self.relative(target).casefold()
        if relative == ".":
            if write:
                raise SecurityError("The workspace root cannot be changed")
            return
        parts = relative.split("/")
        if any(part.startswith(".env") and part != ".env.example" for part in parts):
            raise SecurityError("Credential values are available to the runtime, not the agent tools")
        handoff = relative.startswith(".agentforge/handoff/") and target.suffix.lower() == ".md"
        prototype = relative == ".agentforge/prototype" or relative.startswith(".agentforge/prototype/")
        own = relative == f".agentforge/agents/{self.role}" or relative.startswith(f".agentforge/agents/{self.role}/")
        # What the customer handed in: pictures uploaded on the design screen
        # and files dropped into the chat. Both are told to the agent by path,
        # and a path it is refused is worse than one it was never given - it
        # reads as the file being missing. Readable by either role, writable by
        # neither: these are the customer's originals, and an agent that edits
        # one silently changes what was asked for.
        given = (relative in (".agentforge/images", ".agentforge/uploads")
                 or relative.startswith(".agentforge/images/")
                 or relative.startswith(".agentforge/uploads/"))
        ancestors = relative in (".agentforge", ".agentforge/handoff", ".agentforge/agents")
        if self.role == "designer":
            allowed = prototype or own or (not write and (handoff or given or ancestors))
        else:
            allowed = (not relative.startswith(".agentforge") and not relative.startswith(".agent/")) or own
            allowed = allowed or (not write and (handoff or prototype or given or ancestors))
        if not allowed or (write and handoff):
            raise SecurityError(f"{self.role} cannot {'write' if write else 'read'} {relative}")

    def _inside(self, target: Path) -> bool:
        for root in (self.root, self.real_root):
            if target == root or root in target.parents:
                return True
        return False

    def _nearest_real(self, target: Path) -> Path | None:
        current = target
        for _ in range(64):
            try:
                return current.resolve(strict=True)
            except OSError:
                if current.parent == current:
                    return None
                current = current.parent
        return None

    def relative(self, target: Path | str) -> str:
        """Workspace-relative display path, as the model and user both see it."""
        try:
            rel = Path(target).resolve().relative_to(self.root)
        except (ValueError, OSError):
            return str(target)
        return str(rel).replace("\\", "/") or "."

    def allows(self, raw: str) -> bool:
        try:
            self.resolve(raw)
            return True
        except SecurityError:
            return False

    def state_dir(self, *parts: str) -> Path:
        """`.agent/<parts>` inside the workspace, created on demand."""
        directory = self.root.joinpath(".agent", *parts)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def walk(self, start: Path | None = None, limit: int = 6000):
        """Yield source-ish files, skipping the directories nobody wants read."""
        seen = 0
        for base, dirs, names in os.walk(start or self.root):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS
                       and (not d.startswith(".") or d in VISIBLE_DOT_DIRS)]
            for name in names:
                path = Path(base) / name
                if path.suffix.lower() in BINARY_SUFFIXES:
                    continue
                try:
                    self.resolve(str(path))
                except SecurityError:
                    continue
                yield path
                seen += 1
                if seen >= limit:
                    return
