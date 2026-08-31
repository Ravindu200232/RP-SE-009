"""Checks a finished app against its plan and observed behavior."""
from __future__ import annotations

import http.cookiejar
import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

# Source: core.py — imported helper(s) come from this file.
from agents.core.nextjs import docs as nextdocs
# Source: command_runner.py — imported helper(s) come from this file.
from agents.core.runtime.command_runner import CommandRunner
# Source: import_checker.py — imported helper(s) come from this file.
from agents.core.imports.import_checker import check_default_imports, check_named_imports
# Source: import_rules.py — imported helper(s) come from this file.
from agents.core.imports.import_rules import FRAMEWORK_EXPORTS, strip_noncode as _strip_noncode
# Source: import_reader.py — imported helper(s) come from this file.
from agents.core.imports.import_reader import parse_imports, resolve_local
# Source: syntax_checker.py — imported helper(s) come from this file.
from agents.core.syntax.syntax_checker import check_syntax
# Source: source_workspace.py — imported helper(s) come from this file.
from agents.core.workspace.source_workspace import TOOL_HELP, WorkspaceTools
# Source: app_builder.py — imported helper(s) come from this file.
from agents.planner.builder.app_builder import FileStreamParser

log = logging.getLogger("analyzer")
SKIP_DIRS = {"node_modules", ".git", ".next", "dist", "out", ".vite", ".agentforge", ".turbo", "public", "coverage"}
SOURCE_EXT = {".js", ".jsx", ".mjs", ".css", ".json", ".md"}
CODE_EXT = {".js", ".jsx", ".mjs"}
NEXT_ROOTS = ("app/", "components/", "lib/")
ROOT_SOURCE = {"middleware.js", "middleware.jsx", "instrumentation.js"}
MAX_FILE_BYTES = 200_000
SEVERITIES = ("blocker", "major", "minor")
REPAIRABLE_MAJOR = frozenset({"UNBUILT_PROMISE", "BROKEN_CONTRACT", "MISSING_PLANNED_DATA", "INERT_CONTROL", "ROLE_REDIRECT", "ROLE_HOME_MISSING", "ROLE_PAGE_UNGUARDED", "MISSING_WORKFLOW_CONTROL", "SEED_IN_LAYOUT", "LINT", "DEAD_LINK", "UNUSED_PLANNED_IMAGE", "NAVBAR_ON_AUTH_PAGE"})
PROSE_PATH_RE = re.compile(r"`((?:app|components|lib)/[^`]+?\.jsx?)`")
PLACEHOLDER_RE = re.compile(r"[*?<>\s]|\.\.\.")
LINK_HREF_RE = re.compile(r"""<Link\b[^>]*?href\s*=\s*(?:["'](/[^"']*)["']|\{\s*["'](/[^"']*)["']\s*\})""")
ROUTER_PUSH_RE = re.compile(r"""(?:router\.(?:push|replace)|redirect)\(\s*["'](/[^"']*)["']""")
FETCH_URL_RE = re.compile(r"""fetch\(\s*[`'"](/api/[A-Za-z0-9_\-/\[\]${}.]*)[`'"]""")
BCRYPT_LITERAL_RE = re.compile(r"""["'](\$2[aby]?\$\d\d\$[^"']*)["']""")
HTTP_METHOD_RE = re.compile(r"export\s+(?:async\s+)?(?:function\s+|const\s+)(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b")
PROMPT_FILE = Path(__file__).with_name("analysis_prompt.txt")

# What the model is asked to go looking for. Written as instructions rather than
# category labels: the deterministic checks below only find the faults someone
# already thought to encode, and the ones that actually reach a served page —
# a missing import, a serialized date, an id that is not an ObjectId — are the
# ones no fixed list caught.
SEMANTIC_LENSES = (
    "Walk each accepted capability from its entry route to the outcome the user "
    "is supposed to see. Does a real control exist, does it reach a handler, "
    "does the handler persist, and does the page show the result without a "
    "manual refresh?",

    "Ask what each planned page does when the data is empty, when the request "
    "fails, and when a field is missing from a row. Look for a value used before "
    "it exists, and for a response rendered as a list when the handler can also "
    "return an object or an error.",

    "Read the source for what throws the moment the page is opened: a component "
    "or helper used without its import, a date or number method called on a "
    "value that arrives serialized as a string, and an id passed to ObjectId "
    "when the seed identifies that collection some other way.",

    "Follow identity and authorization: who the session says the user is, which "
    "routes read it, what a wrong-role visitor actually sees, and whether "
    "sign-in, sign-out and the seeded demo identities work end to end.",

    "Take every href and every router.push target in the shell and the pages, "
    "and check that a page file really serves that exact path. The navigation "
    "written from memory rather than from the route table is the usual "
    "offender, and the footer is on every screen, so one invented path there "
    "is a 404 the whole app carries.",
)

@dataclass
class Finding:
    severity: str
    code: str
    message: str
    path: str = ""
    fix: str = ""
    extra: list = field(default_factory=list)

    # Format this finding as one readable line.
    def line(self) -> str:
        """Format this finding as one readable line."""
        return f"[{self.severity}] " + (f"{self.path}: " if self.path else "") + self.message

@dataclass
class AnalyzerReport:
    findings: list = field(default_factory=list)
    planned: list = field(default_factory=list)
    missing: list = field(default_factory=list)
    routes: dict = field(default_factory=dict)
    dead_links: list = field(default_factory=list)
    unresolved: list = field(default_factory=list)
    credentials: dict = field(default_factory=dict)
    runtime_examples: dict = field(default_factory=dict)
    written: int = 0

    # Returns the findings that are serious enough to block delivery.
    def blockers(self):
        """Return the findings that are serious enough to block delivery."""
        return [f for f in self.findings if f.severity == "blocker"]
    # Returns True when no blocking finding remains.
    def is_clean(self):
        """Return True when no blocking finding remains."""
        return not self.blockers()
    # Turn the current result into a short human-readable summary.
    def summary(self):
        """Turn the current result into a short human-readable summary."""
        if not self.findings: return "no problems found"
        by = {s: sum(f.severity == s for f in self.findings) for s in SEVERITIES}
        return ", ".join(f"{n} {s}" for s, n in by.items() if n)
    # Turn the findings into evidence that can be passed to the repair model.
    def as_prompt_block(self, limit=25):
        """Turn the findings into evidence that can be passed to the repair model."""
        rows = []
        for n, f in enumerate(sorted(self.findings, key=lambda x: SEVERITIES.index(x.severity))[:limit], 1):
            rows.append(f"{n}. {f.line()}")
            if f.fix: rows.append(f"   → {f.fix}")
        if len(self.findings) > limit: rows.append(f"… and {len(self.findings)-limit} more")
        return "\n".join(rows)

__all__ = [name for name in globals() if not name.startswith('__')]
