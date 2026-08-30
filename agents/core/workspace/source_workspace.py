"""Entry point for safe read-only access to the generated project."""
from pathlib import Path
# Source: workspace_shared.py — imported helper(s) come from this file.
from agents.core.workspace.workspace_shared import TOOL_HELP, _TAGS
# Source: file_tools.py — imported helper(s) come from this file.
from agents.core.workspace.file_tools import WorkspaceFileToolsMixin
# Source: dependency_tools.py — imported helper(s) come from this file.
from agents.core.workspace.dependency_tools import WorkspaceDependencyToolsMixin


class WorkspaceTools(WorkspaceFileToolsMixin, WorkspaceDependencyToolsMixin):
    # Prepares WorkspaceTools with the services and starting state it needs before it begins work.
    def __init__(self, arch):
        """Prepare this helper with the state it needs."""
        self.arch = arch
        self.project_dir = Path(getattr(arch, "project_dir", "."))
        self.cache = getattr(arch, "_workspace_tool_cache", None)
        if self.cache is None:
            self.cache = {}
            setattr(arch, "_workspace_tool_cache", self.cache)

    # Returns the project files currently visible to this workspace helper.
    @property
    def files(self) -> dict:
        """Return the project files currently visible to this workspace helper."""
        return getattr(self.arch, "files", None) or {}

    # Returns workspace tool requests collected during the current model turn.
    def requests(self, reply: str) -> list[tuple[str, str]]:
        """Return workspace tool requests collected during the current model turn."""
        hits = []
        text = str(reply or "")
        # From: agents/core/workspace/workspace_shared.py
        for name, rx in _TAGS.items():
            for m in rx.finditer(text):
                # From: agents/data/database_server.py
                hits.append((m.start(), name, m.group(1)))
        hits.sort(key=lambda x: x[0])
        return [(name, arg) for _, name, arg in hits[:4]]

    # Execute one permitted workspace tool request and return its observation.
    def serve(self, reply: str, *, max_calls: int = 4) -> tuple[str, int]:
        """Execute one permitted workspace tool request and return its observation."""
        out, used = [], 0
        for name, arg in self.requests(reply)[:max_calls]:
            key = f"{name}::{arg}".lower()
            if key in self.cache:
                out.append(f"### {name} {arg}\n(refused: exact tool request already served; use the observation already in context)")
                continue
            body = self.run(name, arg)
            self.cache[key] = body
            used += 1
            out.append(f"### {name} {arg}\n{body}")
        return ("\n\n".join(out), used)

    # Runs this pipeline step and returns the result.
    def run(self, name: str, arg: str) -> str:
        """Run this pipeline step and return its result."""
        name = name.lower().strip()
        if name == "read_file":
            # From: agents/core/workspace/file_tools.py
            return self.read_file(arg)
        if name == "search_code":
            # From: agents/core/workspace/file_tools.py
            return self.search_code(arg)
        if name == "list_files":
            # From: agents/core/workspace/file_tools.py
            return self.list_files(arg)
        if name == "route_source":
            # From: agents/core/workspace/file_tools.py
            return self.route_source(arg)
        if name == "importers":
            # From: agents/core/workspace/file_tools.py
            return self.importers(arg)
        if name == "dependency_closure":
            # From: agents/core/workspace/dependency_tools.py
            return self.dependency_closure(arg)
        if name == "dependency_neighborhood":
            # From: agents/core/workspace/dependency_tools.py
            return self.dependency_neighborhood(arg)
        if name == "tests_for":
            # From: agents/core/workspace/dependency_tools.py
            return self.tests_for(arg)
        if name == "route_map":
            # From: agents/core/workspace/dependency_tools.py
            return self.route_map(arg)
        if name == "plan_query":
            # From: agents/core/workspace/dependency_tools.py
            return self.plan_query(arg)
        return f"unknown workspace tool: {name}"

