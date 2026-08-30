"""File Writer for the application builder.

The methods in this file share one easy-to-find responsibility.
"""
from __future__ import annotations

# Source: builder_shared.py — shared builder constants and helper imports.
from agents.planner.builder.builder_shared import (
    _strip_fence,
    render_templates,
)
# Source: react_dom_props.py — safe JSX DOM property normalization.
from agents.core.syntax.react_dom_props import normalize_react_dom_props

class FileWriterMixin:
    """Keep file writer behavior in one place."""

    # Writes one complete generated file and update the in-memory source map.
    def write_file(self, rel: str, content: str) -> bool:
        """Write one complete generated file and update the in-memory source map."""
        try:
            # From: agents/planner/builder/builder_setup.py
            target = self._safe_path(rel)
            key = target.relative_to(self.project_dir.resolve()).as_posix()
            protected = self.NEXT_PROTECTED
            planned = {item.get("path") for item in self._planned_files()}
            if key in protected and not self._scaffolding and key not in planned:
                self._log("WARN", f"   ⛔ kept scaffold-owned default {key}")
                return False
            # From: agents/planner/builder/builder_shared.py
            body = _strip_fence(content).rstrip() + "\n"
            # From: agents/core/syntax/react_dom_props.py
            body = normalize_react_dom_props(key, body)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
            self.files[key], self.write_seq = body, self.write_seq + 1
            size = f"{len(body) / 1024:.1f}KB" if len(body) >= 1024 else f"{len(body)}B"
            self._fire("on_file_written", key, size, body)
            self._log("INFO", f"   📝 {key} ({size})")
            return True
        except Exception as exc:
            self._log("ERROR", f"   ❌ write failed {rel}: {exc}")
            return False

    # Writes one builder-owned support file without treating it as model output.
    def write_own(self, rel: str, content: str) -> bool:
        """Write one builder-owned support file without treating it as model output."""
        return self.write_file(rel, content)

    # Writes the stable runtime files that every generated application needs.
    def scaffold(self) -> None:
        """Write the stable runtime files that every generated application needs."""
        self._log("INFO", f"🧱 Writing {self.stack} runtime defaults")
        self._scaffolding = True
        try:
            # From: agents/planner/builder/builder_shared.py
            defaults = render_templates(self.stack, self.plan, mongo_uri=self.mongo_uri,
                                        db_name=self.db_name, dev_port=self.dev_port)
            for path, body in defaults.items():
                self.write_file(path, body)
                self._scaffold_baseline[path] = body.rstrip() + "\n"
        finally:
            self._scaffolding = False

    # Returns the file paths promised by the approved build plan.
    def _planned_files(self) -> list[dict]:
        """Return the file paths promised by the approved build plan."""
        return [item for item in self.plan.get("file_plan") or [] if isinstance(item, dict) and item.get("path")]

    # Returns the planned files that already exist in the generated source map.
    def _implemented(self, path: str) -> bool:
        """Return the planned files that already exist in the generated source map."""
        body = self.files.get(path)
        return body is not None and body != self._scaffold_baseline.get(path)

    # Returns the planned files that still need to be generated.
    def _outstanding(self) -> list[dict]:
        """Return the planned files that still need to be generated."""
        return [item for item in self._planned_files() if not self._implemented(item["path"])]

    # Checks whether the approved plan still contains unfinished source files.
    def unfinished(self) -> list[str]:
        """Return whether the approved plan still contains unfinished source files."""
        return [item["path"] for item in self._outstanding()]
