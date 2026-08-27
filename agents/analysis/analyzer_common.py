"""
Post-generation audit.

Generation can finish "successfully" and still ship a broken app, because every
gate in the pipeline answers a different question from "did we build what the
plan said". Measured against the nine generated projects on disk:

* one project promises 19 source files in its `plan.md` and has **17 missing** —
  the build was interrupted, nothing noticed, and the UI lists it as finished;
* another silently never wrote the `app/api/logout/route.js` it planned;
* a third links to four pages that do not exist.

None of those is a compile error, so `next build` is happy. Nothing imports a
Next.js page, so import repair cannot see a missing one. And a login whose
seeded password hash is wrong returns a perfectly valid 401, so Playwright
screenshots a working form and the pipeline goes green.

So this module reads the finished project back and compares it against the plan.
The split is deliberate:

* **file paths are checked in Python** — measured 0 false positives across all
  nine projects, so this needs no model and no tokens;
* **meaning is checked by the model** — "does this app actually do what the plan
  described" is not a regex, and trying to make it one produces noise;
* **credentials are checked by a real HTTP request** — the login page here shows
  `user1@example.com` while the seed *generates* emails from a template, so no
  static comparison can settle it.

The analyzer runs on whatever model the build used; there is nothing extra to
configure.
"""
import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from agents.planning.architect import FileStreamParser
from agents.core.commands import CommandRunner
from agents.core import nextdocs
from agents.core.exports_common import FRAMEWORK_EXPORTS, strip_noncode as _strip_noncode
from agents.core.exports_checks import check_default_imports, check_named_imports
from agents.core.exports_parse import parse_imports, resolve_local

log = logging.getLogger("analyzer")


SKIP_DIRS = {"node_modules", ".git", ".next", "dist", "out", ".vite", ".agentforge",
             ".turbo", "public", "coverage"}
SOURCE_EXT = {".js", ".jsx", ".mjs", ".css", ".json", ".md"}
CODE_EXT = {".js", ".jsx", ".mjs"}


NEXT_ROOTS = ("app/", "components/", "lib/")


ROOT_SOURCE = {"middleware.js", "middleware.jsx", "instrumentation.js"}
MAX_FILE_BYTES = 200_000

REPAIRABLE_MAJOR = frozenset({
    "UNBUILT_PROMISE", "BROKEN_CONTRACT", "MISSING_PLANNED_DATA",
    "INERT_CONTROL", "ROLE_REDIRECT", "ROLE_HOME_MISSING",
    "ROLE_PAGE_UNGUARDED", "MISSING_WORKFLOW_CONTROL", "LAYOUT_CHROME", "LINT",
})


PROSE_PATH_RE = re.compile(r"`((?:app|components|lib)/[^`]+?\.jsx?)`")


PLACEHOLDER_RE = re.compile(r"[*?<>\s]|\.\.\.")


LINK_HREF_RE = re.compile(
    r"""<Link\b[^>]*?href\s*=\s*(?:["'](/[^"']*)["']|\{\s*["'](/[^"']*)["']\s*\})""")
ROUTER_PUSH_RE = re.compile(r"""router\.(?:push|replace)\(\s*["'](/[^"']*)["']""")


FETCH_URL_RE = re.compile(r"""fetch\(\s*['"](/api/[A-Za-z0-9_\-/\[\]]*)['"]""")


BCRYPT_LITERAL_RE = re.compile(r"""["'](\$2[aby]?\$\d\d\$[^"']*)["']""")

HTTP_METHOD_RE = re.compile(
    r"export\s+(?:async\s+)?(?:function\s+|const\s+)"
    r"(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b")

SEVERITIES = ("blocker", "major", "minor")


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    path: str = ""
    fix: str = ""

    extra: list = field(default_factory=list)

    def line(self) -> str:
        where = f"{self.path}: " if self.path else ""
        return f"[{self.severity}] {where}{self.message}"


@dataclass
class AnalyzerReport:
    findings: list = field(default_factory=list)
    planned: list = field(default_factory=list)
    missing: list = field(default_factory=list)
    routes: dict = field(default_factory=dict)
    dead_links: list = field(default_factory=list)
    unresolved: list = field(default_factory=list)
    credentials: dict = field(default_factory=dict)
    written: int = 0

    def blockers(self) -> list:
        return [f for f in self.findings if f.severity == "blocker"]

    def is_clean(self) -> bool:
        return not self.blockers()

    def summary(self) -> str:
        if not self.findings:
            return "no problems found"
        by = {s: sum(1 for f in self.findings if f.severity == s)
              for s in SEVERITIES}
        return ", ".join(f"{n} {s}" for s, n in by.items() if n)

    def as_prompt_block(self, limit: int = 25) -> str:
        ranked = sorted(self.findings, key=lambda f: SEVERITIES.index(f.severity))
        lines = []
        for i, f in enumerate(ranked[:limit], 1):
            lines.append(f"{i}. {f.line()}")
            if f.fix:
                lines.append(f"   → {f.fix}")
        if len(ranked) > limit:
            lines.append(f"… and {len(ranked) - limit} more")
        return "\n".join(lines)

__all__ = [name for name in globals() if not name.startswith("__")]
