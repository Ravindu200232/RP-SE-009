"""
Add a feature to a finished app.

`ArchitectAgent.update()` already edits a project, but it cannot do this job.
Its thread is seeded with `_context_snapshot(max_files=18, per_file=2000)`: at
most eighteen files, each truncated mid-file. Measured across the ten Next
projects on disk that is 18 of 60, 18 of 55, 18 of 34 — and the selection is a
fixed priority list, not a function of the request. On the project that reported
a broken login it showed the model the route with the broken imports and *not*
the module that failed to export them, so no phrasing of the instruction could
have fixed the bug.

So this agent works the way the analyzer does: it is handed an inventory of
every file — one line each — and pulls the bodies it actually needs. On the
models in use here a whole project is 27-37k tokens, so the read budget is
never the constraint; the point is that the model chooses.

Two phases, because "which files change" and "what they become" are different
questions and only the first produces something checkable:

  PLAN   the model names the files, the packages and the routes, in a strict
         line format. That list becomes the write allowlist.
  WRITE  the model implements exactly that list, with the current body of every
         file it is editing, and anything off-list is dropped.

Declared packages are installed *before* the write turn, so the model writes
against a package that exists rather than one that has to be discovered by a
failing build afterwards.
"""
from __future__ import annotations

import logging
import re
import textwrap
from dataclasses import dataclass, field

from .architect import FileStreamParser


LOCAL_IMPORT_RE = re.compile(
    r"""from\s+['"]@/(components/[\w./-]+)['"]""")

log = logging.getLogger("features")

MAX_FILES = 8
MAX_PACKAGES = 3
MAX_READS = 12

PLAN_LINE_RE = re.compile(
    r"^\s*(SUMMARY|PACKAGE|FILE|ROUTE|DONE)\b\s*(?:::)?\s*(.*)$", re.M)


@dataclass
class FeatureSpec:
    summary: str = ""
    files: list = field(default_factory=list)
    packages: list = field(default_factory=list)
    routes: list = field(default_factory=list)
    written: list = field(default_factory=list)
    rejected: list = field(default_factory=list)

    context: dict = field(default_factory=dict)

    def paths(self) -> set:
        return {f["path"] for f in self.files}

    def is_empty(self) -> bool:
        return not self.files


PLAN_SYSTEM = """\
You are deciding how to add ONE feature to an existing Next.js 16 App Router +
MongoDB project. You are NOT writing code yet.

You are given the project's plan, the routes it serves, and THE COMPLETE
SOURCE OF EVERY FILE. Nothing is hidden and there is nothing to ask for. If you
still want to re-read something, emit `<read_file path="lib/auth.js"/>`, but you
should not need to.

A FEATURE IS NEVER ONLY NEW FILES. Adding one changes things that already
exist, and those edits are the half that gets forgotten. Before you answer,
walk the project and ask what BREAKS or goes STALE because of this change:

  • Does a new field belong on seeded documents? `lib/seed.js` then changes —
    and say so in the `why`, because data already in the database will not have
    the field until it is re-seeded.
  • Does something new need linking to? The page or nav that should link to it
    is an edit, or the feature ships unreachable.
  • Does a shared component need a new prop? Then it changes, and so does
    every caller — count them before you decide it is worth it.
  • Does an API route need a new field in its response? That is an edit, and
    the client that reads it is another.
  • Does an existing page now show something it did not? That page is an edit.

List those edits alongside the new files. A plan that is all `new` for a
feature touching an existing app is usually a plan that missed something.

Then output ONLY these lines, nothing else, no prose, no code fences:

SUMMARY :: one sentence describing the change
PACKAGE :: <npm-package>            (only if genuinely needed; omit otherwise)
FILE :: new|edit :: <path> :: server|client :: why this file changes
ROUTE :: /new-route                 (only for pages or handlers you add)
DONE

Rules:
  • At most 8 FILE lines and 3 PACKAGE lines. Choose the smallest set that
    actually delivers the feature.
  • Every path is project-relative: app/…, components/…, lib/….
  • `edit` means the file already exists; `new` means it does not. Get this
    right — it decides whether you are shown its current contents.
  • Do not list a file you only read for context. List what must CHANGE.
  • Do not plan authentication or a database connection unless the feature
    genuinely needs one; this app already has them. `lib/seed.js` IS fair game
    when the feature gives seeded records a new field.
"""


REPAIR_SYSTEM = """\
You are deciding WHICH FILES must change to fix a bug in a running Next.js 16
App Router + MongoDB project. You are NOT writing code yet.

You are given the project's plan, an inventory of every source file (one line
each), the routes it serves, and the errors the app actually produced when it
was exercised in a browser. To read a file, emit exactly:
<read_file path="app/cart/page.jsx"/>
One per line; you will be given the contents and may then read more. Read the
files the errors point at, and the files those import — a stack frame names the
place the app died, which is often not the place that is wrong.

Then output ONLY these lines, nothing else, no prose, no code fences:

SUMMARY :: one sentence naming the cause, not the symptom
PACKAGE :: <npm-package>            (only if an import genuinely resolves to nothing)
FILE :: new|edit :: <path> :: server|client :: what is wrong in this file
DONE

Rules:
  • List the SMALLEST set of files that actually fixes the errors. A fix that
    rewrites six files to repair one 500 is a worse outcome than the 500.
  • "Only plain objects can be passed to Client Components" reported five
    times on one page is ONE bug, and the file to change is usually the client
    component receiving the prop — not the five call sites. A page passing
    `icon={DollarSign}` to a `'use client'` card is fixed by making the card
    take an icon NAME and look it up, which is two files at most.
  • Every path is project-relative: app/…, components/…, lib/….
  • `edit` means the file already exists; `new` means it does not. Get this
    right — it decides whether you are shown its current contents.
  • Do not list a file you only read for context. List what must CHANGE.
  • A route that redirects an unauthenticated visitor to /login is CORRECT
    behaviour, not a bug. Do not plan to remove a login requirement.
  • lib/mongodb.js, lib/auth.js, lib/auth-client.js and next.config.mjs are
    written by AgentForge and are correct. The bug is not there.
  • If the errors do not name a real defect in the application code, output
    SUMMARY and DONE with no FILE lines. An empty plan is a valid answer.
"""


class FeaturesAgent:
    """Composition over ArchitectAgent, exactly like AnalyzerAgent."""

    def __init__(self, arch, project_dir=None, *, callbacks=None, analyzer=None,
                 model=None):
        self.arch = arch
        self.project_dir = project_dir or arch.project_dir
        self.cb = callbacks or {}

        self.model = model or None
        if analyzer is None:
            from .analyzer import AnalyzerAgent
            analyzer = AnalyzerAgent(arch, self.project_dir, callbacks=self.cb)
        self.az = analyzer

    def _fire(self, name, *a):
        fn = self.cb.get(name)
        if fn and callable(fn):
            try:
                fn(*a)
            except Exception as e:
                log.warning(f"callback {name} failed: {e}")

    def _log(self, lvl, txt):
        self._fire("on_log", lvl, txt)
        log.info(txt)

    def _budget_chars(self) -> int:
        return self.az._budget_chars()

    def full_source(self, budget: int = 0) -> str:
        """
        Every source file in the project, complete.

        The inventory-plus-`read_file` loop this replaced was a guessing game:
        the model saw one line per file and had to know, in advance, which
        bodies it would need. It reliably read the file the request named and
        missed the one that quietly depended on it — which is how a feature
        that added a `slug` to the seed shipped without anyone noticing that
        the database already held documents that would never get one.

        A whole Next project here is 27-37k tokens against a 262k window. There
        is no reason to make the model ask.

        Ordered so the parts that constrain everything else come first, and
        truncated from the end if a project ever does outgrow the budget — a
        cut-off leaf component costs less than a missing `lib/mongodb.js`.
        """
        files = self.az.source_files()
        budget = budget or int(self._budget_chars() * 0.55)

        def rank(rel):
            if rel.startswith("lib/"):
                return 0
            if rel.endswith(("layout.jsx", "layout.js")):
                return 1
            if "/api/" in rel:
                return 2
            if rel.startswith("app/"):
                return 3
            return 4

        out, used = [], 0
        for rel in sorted(files, key=lambda r: (rank(r), r)):
            body = files[rel]
            block = f"--- {rel} ---\n{body}\n"
            if used + len(block) > budget:
                out.append(f"--- {rel} ---\n(omitted — the context budget "
                           f"ran out here)\n")
                continue
            out.append(block)
            used += len(block)
        return "\n".join(out)

    def plan_feature(self, request: str, max_reads: int = MAX_READS) -> FeatureSpec:
        routes = self.az.enumerate_routes()
        user = (f"## The project's plan\n{self.az.plan_text()[:6000]}\n\n"
                f"## Routes it serves\n{self.az.route_table(routes)}\n\n"
                f"## The feature to add\n{request}\n\n"
                f"## THE WHOLE PROJECT, every file\n{self.full_source()}\n\n"
                f"You have all of it. Work out what this feature touches — "
                f"including the files that only break BECAUSE of it — then "
                f"output the plan lines.")
        return self._plan(PLAN_SYSTEM, user, max_reads, "Feature planning")

    def plan_repair(self, errors: str, *, server_log: str = "",
                    max_reads: int = MAX_READS) -> FeatureSpec:
        """
        Same two-phase shape, pointed at a bug instead of a feature.

        The runtime fix loop used to hand the whole error blob straight to
        `ArchitectAgent.update()`, which meant the model picking the files and
        writing them in one breath, with only the architect's fixed 18-file
        snapshot to go on — and the file a stack frame names is regularly not
        the file that is wrong. Deciding first, against an inventory of the
        whole project and whatever bodies the model asks to read, is the same
        reason this module exists at all.
        """
        routes = self.az.enumerate_routes()
        parts = [f"## The project's plan\n{self.az.plan_text()[:4000]}",
                 f"## Every source file\n{self.az.inventory()}",
                 f"## Routes it serves\n{self.az.route_table(routes)}",
                 f"## What went wrong when the app ran\n```\n{errors[:6000]}\n```"]
        if server_log.strip():
            parts.append("## The dev server's own output\n"
                         f"```\n{server_log[:4000]}\n```")
        parts.append("Read what you need, then output the plan lines.")
        return self._plan(REPAIR_SYSTEM, "\n\n".join(parts), max_reads,
                          "Repair planning", allow_empty=True)

    MEMORY_TURNS = 12
    MEMORY_CHARS = 60_000

    def _memory(self) -> list:
        """
        The tail of the conversation the app was generated in.

        An edit made against a fresh context can only see the code; this is how
        it also sees the reasoning. The build thread records which component
        owns which prop, why a page is a server component, what the seed
        actually contains — everything the file inventory shows the *result* of
        and never the *reason* for. Reloaded from `.agentforge/convo.json`, so this
        works an hour later and in a new process, not only mid-build.

        The system prompt is dropped: this is being replayed under a different
        one. What is kept is the plan turn plus the most recent exchanges,
        which is where the app's conventions were actually settled.
        """
        convo = getattr(self.arch, "convo", None) or []
        if len(convo) < 3:
            return []
        body = [m for m in convo if m.get("role") in ("user", "assistant")]
        if not body:
            return []

        head, tail = body[:1], body[1:][-self.MEMORY_TURNS:]
        kept, total = [], 0
        for m in reversed(head + tail):
            c = (m.get("content") or "")[:8000]
            if total + len(c) > self.MEMORY_CHARS:
                break
            kept.append({"role": m["role"], "content": c})
            total += len(c)
        kept.reverse()
        if not kept:
            return []
        return ([{"role": "user", "content":
                  "For context, this is how we built this app together. "
                  "Remember these decisions — the change below has to fit "
                  "them."}]
                + kept
                + [{"role": "assistant", "content":
                    "Understood. I remember this project and the choices we "
                    "made in it."}])

    def _plan(self, system: str, user: str, max_reads: int, what: str,
              *, allow_empty: bool = False) -> FeatureSpec:
        """The read-then-decide loop both planners share."""
        convo = ([{"role": "system", "content": system}]
                 + self._memory()
                 + [{"role": "user", "content": user}])
        budget, reads = self._budget_chars(), 0
        spec = FeatureSpec()

        context = {}

        for attempt in (1, 2):
            while True:
                buf = []
                try:
                    self.arch._stream(convo, buf.append, temperature=0.3,
                                      model=self.model)
                except Exception as e:
                    self._log("WARN", f"   ⚠ {what} failed: {e}")
                    spec.context = context
                    return spec
                reply = "".join(buf)
                convo.append({"role": "assistant", "content": reply})

                wanted = self.az.READ_RE.findall(reply)
                used = sum(len(m["content"]) for m in convo)
                if wanted and reads < max_reads and used < budget:
                    served = []
                    for rel in wanted[:4]:
                        reads += 1
                        body = self.az._read_for_model(rel)
                        context[rel] = body
                        served.append(f"--- {rel} ---\n{body}")
                    self._log("INFO", f"   📖 read {', '.join(wanted[:4])}")
                    convo.append({"role": "user",
                                  "content": "\n\n".join(served) +
                                             "\n\nContinue."})
                    continue
                break

            spec = self._parse(reply)
            spec.context = context
            if not spec.is_empty():
                return spec

            if allow_empty and re.search(r"^\s*(SUMMARY|DONE)\b", reply, re.M):
                self._log("INFO", f"   ✅ {what}: nothing needs to change")
                return spec
            if attempt == 1:

                self._log("WARN", "   ⚠ Could not read the plan — retrying")
                convo.append({"role": "user", "content":
                    "That did not parse. Output ONLY the plan lines, starting "
                    "with SUMMARY and ending with DONE. One FILE line per file "
                    "that must change, in exactly this form:\n"
                    "FILE :: edit :: app/page.js :: server :: adds the link\n"
                    "No prose, no code, no markdown."})
        return spec

    def _parse(self, reply: str) -> FeatureSpec:
        spec = FeatureSpec()
        for kind, rest in PLAN_LINE_RE.findall(reply):
            rest = rest.strip().strip("`")
            if kind == "SUMMARY":
                spec.summary = rest[:200]
            elif kind == "PACKAGE" and rest:
                name = rest.split("::")[0].strip().strip("`")
                if self.arch.PKG_NAME_RE.match(name) and \
                        name not in self.arch.NODE_BUILTINS:
                    spec.packages.append(name)
            elif kind == "ROUTE" and rest.startswith("/"):
                spec.routes.append(rest.split()[0])
            elif kind == "FILE":
                parts = [p.strip().strip("`") for p in rest.split("::")]
                if len(parts) < 2:
                    continue
                action = parts[0].lower()

                path = parts[1].strip().lstrip("./").replace("\\", "/")
                if action not in ("new", "edit") or ".." in path:
                    continue
                if not path.startswith(("app/", "components/", "lib/")):
                    continue
                spec.files.append({
                    "path": path, "action": action,
                    "kind": (parts[2].lower() if len(parts) > 2 else ""),
                    "why": (parts[3] if len(parts) > 3 else "")})

        seen, unique = set(), []
        for f in spec.files:
            if f["path"] in seen:
                continue
            seen.add(f["path"])
            unique.append(f)
        spec.files = unique[:MAX_FILES]
        spec.packages = list(dict.fromkeys(spec.packages))[:MAX_PACKAGES]
        return spec

    def apply(self, request: str, spec: FeatureSpec) -> int:
        if spec.is_empty():
            return 0

        for pkg in spec.packages:
            self._log("INFO", f"   📦 npm install {pkg}")
            self.az.cmd.run(f"npm install {pkg}")

        files = self.az.source_files()
        allowed = spec.paths()

        bodies = []
        for f in spec.files:
            body = files.get(f["path"])
            if body:
                bodies.append(f"--- {f['path']} (COMPLETE current contents) "
                              f"---\n{body}")

        shown = set(allowed)
        for f in spec.files:
            for mod in dict.fromkeys(LOCAL_IMPORT_RE.findall(files.get(f["path"], ""))):
                if len(shown) >= len(allowed) + 4:
                    break
                for ext in (".jsx", ".js", ""):
                    rel = f"{mod}{ext}"
                    if rel in files and rel not in shown:
                        shown.add(rel)
                        bodies.append(f"--- {rel} (for reference — do NOT "
                                      f"rewrite it) ---\n{files[rel]}")
                        break
        for helper in ("app/layout.jsx", "app/layout.js", "lib/mongodb.js"):
            if helper in files and helper not in shown:
                shown.add(helper)
                bodies.append(f"--- {helper} (for reference — do not rewrite) "
                              f"---\n{files[helper][:3000]}")

        listing = "\n".join(
            f"  • {f['path']}  [{f['action']}]"
            f"{'  — ' + f['why'] if f['why'] else ''}" for f in spec.files)

        user = textwrap.dedent(f"""\
            ## The feature
            {request}

            ## Your own plan for it
            {spec.summary}

            ## Write exactly these files, complete, and NOTHING else
            {listing}

            ## Files
            {chr(10).join(bodies)}

            Rewrite each `edit` file in full. Change ONLY what this feature
            needs and bring everything else back exactly as it was — the other
            exports, the existing styling, the surrounding structure, the
            sections above and below it. Nothing already on the page may move,
            change colour, lose a class or be reformatted. Reuse the helpers
            this project already has instead of writing new ones, and match the
            palette, spacing, radius and heading sizes of the files shown to
            you for reference.

            If you need an npm package that is not installed, ask for it BEFORE
            the file that imports it, on its own line:

            <run_command>npm install embla-carousel-react</run_command>

            One package per command, real npm names only. Already installed, so
            never ask for these: react, react-dom, next, mongodb, tailwindcss,
            lucide-react, framer-motion, better-auth.

            One <write_file path="…"> block per file.
            """)

        convo = ([{"role": "system", "content": self.arch._builder_sys()}]
                 + self._memory()
                 + [{"role": "user", "content": user}])

        def on_end(path, content):
            key = (path or "").strip().lstrip("./").replace("\\", "/")
            if key not in allowed:
                spec.rejected.append(key)
                self._log("WARN", f"   ⛔ {key} is not in the plan — skipped")
                return
            self._fire("on_file_start", key)
            self._fire("on_file_end", key, content)
            if self.arch.write_file(key, content):
                spec.written.append(key)

        parser = FileStreamParser(
            on_text=lambda t: None,
            on_file_start=lambda p: None,
            on_file_token=lambda t: None,
            on_file_end=on_end)
        raw = []

        def feed(tok):
            raw.append(tok)
            parser.feed(tok)

        try:
            self.arch._stream(convo, feed, temperature=0.4, model=self.model)
        except Exception as e:
            self._log("WARN", f"   ⚠ Feature write failed: {e}")
        parser.close()

        for out in self.arch.run_requested_commands("".join(raw)):
            self._log("INFO", f"   📦 {out.splitlines()[0][:110]}")

        if spec.written:
            self.arch.repair_missing_imports()
            self.arch.apply_next_fixes()
            self.arch.sync_dependencies()
        return len(spec.written)

    def remember(self, request: str, spec: FeatureSpec) -> bool:
        """
        Write this feature into the build thread, so the next edit knows it.

        Without this the memory only ever flows one way. `plan_feature` and
        `apply` build their own message lists — deliberately, so a feature can
        never corrupt a running build — which means a feature adds nothing to
        `arch.convo` and `save_convo()` afterwards has nothing to save. On a
        project generated before the thread was persisted at all, that leaves
        it permanently without one: every feature starts from the inventory
        again, and none of them remember each other.

        So the exchange is recorded here, as a compact receipt rather than the
        raw turns — the request, the decision, and the files. Same shape
        `_stub_files` leaves behind, and for the same reason: the code is on
        disk, the reasoning is what is worth carrying.
        """
        if not spec.written:
            return False
        arch = self.arch
        try:
            if not arch.convo:

                arch.convo = [
                    {"role": "system", "content": arch._builder_sys()},
                    {"role": "user", "content":
                        "This is the app we are working on.\n\n## The plan\n"
                        + (arch.plan_md or self.az.plan_text() or "")[:8000]},
                    {"role": "assistant", "content":
                        "Understood. I have the plan for this project."},
                ]
            files = "\n".join(
                f"  • {f['path']} ({f['action']})"
                + (f" — {f['why']}" if f.get("why") else "")
                for f in spec.files if f["path"] in spec.written)
            arch.convo.append({"role": "user", "content":
                               f"Add this feature: {request}"})
            arch.convo.append({"role": "assistant", "content":
                               f"{spec.summary or 'Done.'}\n\nFiles:\n{files}"})
            arch._trim_convo()
            return True
        except Exception as e:
            log.warning(f"could not record the feature: {e}")
            return False

    def update_plan(self, request: str, spec: FeatureSpec) -> bool:
        """
        Append a `## Feature —` section, after the writes and filtered by what
        actually landed.

        The ordering is load-bearing. `AnalyzerAgent.planned_paths()` scrapes
        backticked paths out of this prose, so a path written into plan.md that
        never reached disk becomes a MISSING_FILE *blocker* on the very next
        scan — and the analyzer would then try to "repair" a file that was
        never meant to exist. Listing only files that exist makes the check
        stronger instead: a silently failed write stays invisible to the plan
        and is caught by the build check on its own terms.
        """
        landed = [f for f in spec.files if f["path"] in spec.written]
        if not landed:
            return False
        md = self.arch.plan_md or ""
        title = (spec.summary or request).strip().rstrip(".")[:70]
        section = [f"\n## Feature — {title}\n",
                   (spec.summary or request).strip()[:400], "", "Files:"]
        for f in landed:
            section.append(f"- `{f['path']}` — {f['why'] or f['action']}")
        if spec.routes:
            section.append("")
            section.append("Routes: " + ", ".join(f"`{r}`" for r in spec.routes))
        block = "\n".join(section) + "\n"

        marker = "\n## Definition of Done"
        if marker in md:
            md = md.replace(marker, block + marker, 1)
        else:
            md = md.rstrip() + "\n" + block
        self.arch.plan_md = md
        self.arch.write_file("plan.md", md)
        return True

    def run(self, request: str) -> FeatureSpec:
        self._fire("on_phase", {"phase": -9, "title": "Planning the feature",
                                "status": "active"})
        spec = self.plan_feature(request)
        self._fire("on_phase", {"phase": -9, "title": "Planning the feature",
                                "status": "done"})
        if spec.is_empty():
            self._log("WARN", "   ⚠ The model did not name any files to change")
            return spec

        self._log("INFO", f"   🧩 {spec.summary or request[:60]}")
        for f in spec.files:
            self._log("INFO", f"      {f['action']:4} {f['path']}")
        self._fire("on_feature_plan", {
            "summary": spec.summary, "files": spec.files,
            "packages": spec.packages, "routes": spec.routes})

        self._fire("on_phase", {"phase": -10, "title": "Writing the feature",
                                "status": "active"})
        n = self.apply(request, spec)
        self._fire("on_phase", {"phase": -10, "title": "Writing the feature",
                                "status": "done", "written": n})
        if n:
            self.update_plan(request, spec)

            self.remember(request, spec)
        return spec
