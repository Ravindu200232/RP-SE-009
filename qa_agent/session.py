"""
The shell that lets tests be written while the app is still being generated.

The requirement was "don't touch the generation" — it runs however it likes and
the QA work happens beside it on a separate model call. The hook is one
callback: the architect fires `on_phase` with
`{"phase": i, "status": "active", "files": [...]}` and then `{"status":
"done"}` once those files are on disk, and the callbacks dict is assembled in
`server.py`, not in the architect. Wrapping that one callback is the whole hook.

Generation itself is now a single continuous pass rather than one model turn
per phase (`ArchitectAgent.build_app`), which changes nothing here: the phases
are still announced, they are just driven by the files that have landed. A
phase arrives complete, so a queued job is still a coherent slice of the app.

Three properties this file exists to guarantee:

* **The architect never waits.** The wrapper calls the original callback first
  and enqueues afterwards; every exception is swallowed. A broken QA agent must
  not be able to stop a build.
* **`arch.convo` is never touched.** Every model call builds its own message
  list and hands it to `arch._stream`, which takes messages as a parameter —
  the same reason `AnalyzerAgent` can already query the model mid-build.
* **Generated code is read from disk, never from `arch.files`.** The generation
  thread is mutating that dict; iterating it from here would raise
  `dictionary changed size during iteration`. `AnalyzerAgent.source_files()`
  already reads from disk and its docstring says "Deliberately not
  `arch.files`" — here that is load-bearing rather than tidy.
"""
import json
import logging
import queue
import re
import threading
import time
from pathlib import Path

from agents.commands import CommandRunner
from agents.ollama_client import is_cloud_model

from .spec import MAX_PER_PHASE, QAReport, select_targets


QA_AUTHOR_WORKERS = 4

log = logging.getLogger("qa.session")


QA_MAX_COMMANDS = 200


TEST_PATH_RE = re.compile(r"^tests/unit/[A-Za-z0-9][A-Za-z0-9._/-]*\.test\.jsx?$")

QA_DIR = ".agentforge/qa"
MANIFEST = f"{QA_DIR}/manifest.json"


HELPER_HOMES = {

    "oid": "request.js", "postJson": "request.js", "getJson": "request.js",
    "postForm": "request.js", "patchJson": "request.js",
    "putJson": "request.js", "deleteJson": "request.js",

    "__seed": "mongoMock.js", "__reset": "mongoMock.js", "__all": "mongoMock.js",
    "serialize": "mongoMock.js",

    "__setUser": "authMock.js",

    "__setPath": "navMock.js", "__resetNav": "navMock.js",
}


HELPER_SPIES = {
    "push": "navMock.js", "replace": "navMock.js", "back": "navMock.js",
    "forward": "navMock.js", "refresh": "navMock.js", "prefetch": "navMock.js",
    "redirect": "navMock.js", "notFound": "navMock.js",
}
_IMPORT_LINE_RE = re.compile(r"^\s*import\b.*$", re.M)


STUBBED_MODULES = ("next/link", "lucide-react")
_VI_MOCK_RE = re.compile(
    r"vi\s*\.\s*mock\s*\(\s*['\"](next/link|lucide-react)['\"]")


_NEEDS = (

    (re.compile(r"\buse(?:Router|Pathname|SearchParams|Params"
                r"|SelectedLayoutSegment)\s*\(|from\s*['\"]next/navigation['\"]"),
     "next/navigation", "navMock.js"),
    (re.compile(r"from\s*['\"]@/lib/mongodb['\"]|require\(['\"]@/lib/mongodb['\"]"),
     "@/lib/mongodb", "mongoMock.js"),
    (re.compile(r"from\s*['\"]@/lib/auth['\"]|require\(['\"]@/lib/auth['\"]"),
     "@/lib/auth", "authMock.js"),
)


def required_mocks(target_src: str) -> list[tuple[str, str]]:
    """`[(module, helper)]` this application file's test cannot run without."""
    return [(mod, helper) for rx, mod, helper in _NEEDS
            if rx.search(target_src or "")]


def mock_line(module: str, helper: str) -> str:
    return f"vi.mock('{module}', () => import('../../helpers/{helper}'))"


def ensure_mocks(body: str, target_src: str) -> str:
    """
    Add any `vi.mock` the file under test requires and the test left out.

    Placed at the very top, above the imports. `vi.mock` is hoisted either way,
    so this is about where a reader expects to find it — and about `vi` being
    in scope, which is why the vitest import goes in alongside when the test
    did not already have one.
    """
    if not body or not target_src:
        return body
    missing = [(mod, helper) for mod, helper in required_mocks(target_src)
               if not re.search(rf"vi\s*\.\s*mock\s*\(\s*['\"]{re.escape(mod)}['\"]",
                                body)]
    if not missing:
        return body

    lines = [mock_line(mod, helper) for mod, helper in missing]
    if not re.search(r"\bimport\s*\{[^}]*\bvi\b[^}]*\}\s*from\s*['\"]vitest['\"]", body):
        lines.insert(0, "import { vi } from 'vitest'")
    return "\n".join(lines) + "\n" + body


def drop_redundant_mocks(body: str) -> str:
    """
    Remove a `vi.mock` for a module that already works — next/link, lucide-react.

    Not a style preference. `vi.mock` overrides `resolve.alias`, so a test that
    mocks a module AgentForge already stubs replaces a correct stub with its own,
    and the usual mistake is fatal: returning `{ Link: … }` where Next's module
    has a **default** export gives `No "default" export is defined on the
    "next/link" mock` on every case in the file. Measured, four in one file, and
    it survived both repair rounds.

    `lucide-react` is the same failure with a different name and it is worse,
    because the mock has to list every icon the component imports. A test that
    hand-rolls one and forgets `Utensils` fails with `No "Utensils" export is
    defined on the "lucide-react" mock` — five of one build's twelve remaining
    failures, all in files whose components were fine. The real package renders
    plain SVGs under jsdom and needs no mock at all.

    Deleting it strictly improves the test: what the mock was standing in for
    still renders, and every export exists.

    Brace-aware rather than a regex, because the factory is multi-line and
    nested — `() => ({ Link: ({href, children}) => <a href={href}>… })`.
    """
    while True:
        m = _VI_MOCK_RE.search(body)
        if not m:
            return body

        i, depth = body.index("(", m.start()), 0
        for j in range(i, len(body)):
            c = body[j]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    end = j + 1
                    if body[end:end + 1] == ";":
                        end += 1
                    while body[end:end + 1] == "\n":
                        end += 1
                    body = body[:m.start()] + body[end:]
                    break
        else:
            return body


def add_helper_imports(body: str) -> str:
    """
    Add the import for any AgentForge helper the test calls but did not import.

    A mechanical repair, done in Python because it is provably correct: these
    three modules are AgentForge's, so which one exports `oid` is known rather than
    inferred. Measured across two real builds, a missing `oid` import was the
    single largest cause of failures — 8 of 15 in one run — and it survived
    both repair rounds, because to the fixer `TypeError: oid is not a function`
    looks like any other runtime error.

    Fixing it here rather than by adding another prompt rule keeps the test
    file ordinary and portable: it still runs on its own, with real imports.
    """
    if not body:
        return body

    def already_imported(name: str) -> bool:
        return bool(re.search(rf"import\s*\{{[^}}]*\b{re.escape(name)}\b[^}}]*\}}\s*"
                              rf"from\s*['\"][^'\"]*helpers/", body))

    missing = {}
    for name, home in HELPER_HOMES.items():
        if not re.search(rf"(?<![.\w]){re.escape(name)}\s*\(", body):
            continue
        if already_imported(name):
            continue
        missing.setdefault(home, []).append(name)

    for name, home in HELPER_SPIES.items():
        if not re.search(rf"expect\s*\(\s*{re.escape(name)}\s*[,)]", body):
            continue
        if already_imported(name):
            continue
        missing.setdefault(home, []).append(name)

    if not missing:
        return body

    lines = []
    for home, names in sorted(missing.items()):
        lines.append(f"import {{ {', '.join(sorted(names))} }} "
                     f"from '../../helpers/{home}'")
    block = "\n".join(lines)

    last = None
    for m in _IMPORT_LINE_RE.finditer(body):
        last = m
    if last:
        return body[:last.end()] + "\n" + block + body[last.end():]
    return block + "\n" + body


class QASession:
    """
    Owns the timing, the queue and the manifest. Holds no model logic.

    Bound to an `ArchitectAgent` after construction because the pipeline builds
    the callbacks dict before the architect exists — the wrapper has to be in
    that dict at construction time.
    """

    @staticmethod
    def model_for(session, arch) -> str:
        """
        Which model a QA-side call runs on.

        QA is picked separately from the build. A local agent model is a
        perfectly reasonable choice for generating an app, and it is also the
        one choice that used to turn the whole QA half off — authoring tests,
        repairing them and driving the browser are cloud-only. Choosing the QA
        model on its own is what makes "build locally, verify on a cloud model"
        possible, and this is where that choice actually reaches the wire:
        every QA agent borrows `arch._stream`, which defaults to the *build*
        model unless it is told otherwise.

        Falls back to the build model, which is what a same-model run is.
        """
        return (getattr(session, "model", "") or ""
                or getattr(arch, "model", "") or "")

    def __init__(self, project_dir, *, callbacks: dict = None,
                 model: str = "", enabled: bool = True):
        self.project_dir = Path(project_dir)
        self.cb = callbacks or {}
        self.model = model
        self.enabled = enabled
        self.arch = None
        self.author = None

        self.cmd = CommandRunner(
            self.project_dir,
            npm_bin=self.cb.get("npm_bin", "npm"),
            node_bin=self.cb.get("node_bin", "node"),
            on_log=lambda lvl, txt: self._fire("on_log", lvl, txt),
            on_event=lambda ev: self._fire("on_command", ev),
            max_calls=QA_MAX_COMMANDS)

        self._q = queue.Queue()
        self._workers = []
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self._pending = {}

        self._buffer = []
        self._queued = set()
        self._runner_lock = threading.Lock()
        self.manifest = {}
        self.report = QAReport()
        self.concurrent = False
        self.jobs_done = 0
        self.tokens = 0

    def _fire(self, name, *a):
        fn = self.cb.get(name)
        if fn and callable(fn):
            try:
                fn(*a)
            except Exception as e:
                log.warning(f"callback {name} failed: {e}")

    def _log(self, lvl, txt):

        if self.cb and self.cb.get("on_log"):
            self._fire("on_log", lvl, txt)
            return
        log.info(txt)

    def bind(self, arch, analyzer=None):
        """Attach the architect once it exists, and decide the timing model."""
        from .author import UnitTestAuthor
        self.arch = arch

        if not self.manifest:
            self.load_manifest()
        adopted = self.adopt_orphans()
        if adopted:
            log.info(f"adopted {adopted} test file(s) already on disk")

        self.concurrent = is_cloud_model(self.model or getattr(arch, "model", ""))
        self.author = UnitTestAuthor(arch, self.project_dir,
                                     callbacks=self.cb, analyzer=analyzer,
                                     session=self)

        if self.concurrent:
            threading.Thread(target=self._warm_runner, daemon=True,
                             name="agentforge-qa-install").start()
        return self

    def _warm_runner(self):
        """Install the test runner ahead of the first authoring job."""
        try:
            self.ensure_runner()
        except Exception as e:
            log.warning(f"qa: warming the runner: {e}")

    def on_phase(self, inner):
        """
        Wrap the pipeline's `on_phase` callback. Never replaces it.

        The `active` fire is the one that carries `files`; the `done` fire is
        the one that means the code is on disk. Both are needed, which is why
        the file list is stashed on the first and consumed on the second.
        """
        def wrapped(payload):
            try:
                inner(payload)
            finally:
                if not self.enabled or not self.arch:
                    return
                try:
                    self._observe(payload)
                except Exception as e:
                    log.warning(f"qa on_phase: {e}")
        return wrapped

    def _observe(self, p):
        idx = p.get("phase", 0)
        if not isinstance(idx, int) or idx <= 0:
            return
        status = p.get("status")
        if status == "active":
            self._pending[idx] = list(p.get("files") or [])
        elif status == "done":

            self._enqueue(idx, self._pending.pop(idx, []))

    def on_file_written(self, inner):
        """
        Wrap the pipeline's `on_file_written`. Never replaces it.

        This is the hook that makes authoring overlap generation at all. The
        phase hook can only fire once every file a task planned is on disk,
        which is a whole turn away and sometimes the whole build away; this
        one fires the moment a file exists, which — now that the client
        actually streams — is while the model is still writing the next one.
        """
        def wrapped(path, size, content):
            try:
                inner(path, size, content)
            finally:
                if not self.enabled or not self.arch or not self.concurrent:
                    return
                try:
                    self._note_file(path)
                except Exception as e:
                    log.warning(f"qa on_file_written: {e}")
        return wrapped

    def _note_file(self, path):
        """Hold a freshly written file until there are enough for one turn."""
        rel = (path or "").strip().lstrip("./").replace("\\", "/")
        if not rel.endswith((".js", ".jsx")):
            return
        with self._lock:
            if rel in self._queued or rel in self._buffer:
                return
            self._buffer.append(rel)
            if len(self._buffer) < MAX_PER_PHASE:
                return
            batch, self._buffer = self._buffer, []
        self._enqueue(self._phase_of(batch[0]), batch)

    def flush_files(self):
        """Queue a part-full batch — a turn ended, or generation is over."""
        with self._lock:
            batch, self._buffer = self._buffer, []
        if batch:
            self._enqueue(self._phase_of(batch[0]), batch)

    def _phase_of(self, rel: str) -> int:
        """Which plan task a file belongs to, for the authoring prompt's
        "## This phase" line. Zero when the plan does not claim it."""
        try:
            for i, ph in enumerate(self.arch.plan.get("phases") or [], start=1):
                for f in ph.get("files") or []:
                    got = (f.get("path") if isinstance(f, dict) else f) or ""
                    if got.lstrip("./").replace("\\", "/") == rel:
                        return i
        except Exception:
            pass
        return 0

    def _enqueue(self, phase, files):
        with self._lock:
            files = [f for f in files if f not in self._queued]
            if not files:
                return
            self._queued.update(files)
            self._q.put((phase, list(files)))
        if self.concurrent:
            self._ensure_workers()

    def _ensure_workers(self):
        """
        Enough workers for what is queued, up to `QA_AUTHOR_WORKERS`.

        Serial authoring was the whole cost: measured on one build, eleven
        files took 715s one turn at a time, against a generation window of
        188s to hide it in. The jobs are independent — separate conversations,
        separate files, separate vitest invocations — so the only shared thing
        is the model, which serves parallel streams at full context.
        """
        cap = QA_AUTHOR_WORKERS if self.concurrent else 1
        with self._lock:
            self._workers = [w for w in self._workers if w.is_alive()]
            want = min(cap, len(self._workers) + self._q.qsize())
            new = [threading.Thread(target=self._pump, daemon=True,
                                    name=f"agentforge-qa-{i}")
                   for i in range(len(self._workers), want)]
            self._workers.extend(new)
        for w in new:
            w.start()

    def _busy(self) -> bool:
        return any(w.is_alive() for w in self._workers)

    def _pump(self):
        while not self._cancel.is_set():
            try:
                phase, files = self._q.get(timeout=0.25)
            except queue.Empty:
                return
            try:
                self._run_job(phase, files)
            except Exception as e:
                self._log("WARN", f"   ⚠ QA phase {phase}: {e}")
                log.exception("qa job")
            finally:
                self._q.task_done()

    def ensure_runner(self) -> bool:
        """
        Harness on disk and vitest installed, once per session.

        The author now RUNS what it writes, so the runner has to exist while
        tests are being authored — not at the unit stage, which is where it
        used to be installed and which is minutes later. Measured on one build:
        the runner arrived at 697s and every test was authored between 401s and
        607s, so the author could only ever write blind.

        Lazy rather than a fixed point in the pipeline: the app's own
        `npm install` happens partway through generation, and the first
        authoring job lands somewhere either side of it depending on how fast
        the model wrote. Asking here means asking exactly when it matters.
        `install()` guards on `deps_present()`, so this costs a directory stat
        after the first call and the unit stage's own call becomes a no-op.

        Held under its own lock because authoring runs several jobs at once and
        they all start by asking for this. `_runner_ready` is only set once
        `install()` has returned, so without the lock the first four workers
        would each see False and run a concurrent `npm install` into the same
        node_modules.
        """
        if getattr(self, "_runner_ready", False):
            return True
        with self._runner_lock:
            if getattr(self, "_runner_ready", False):
                return True
            from .harness import TestHarness
            try:
                h = TestHarness(self.project_dir, callbacks=self.cb, cmd=self.cmd)
                h.materialise()
                self._runner_ready = bool(h.install())
            except Exception as e:
                self._log("WARN", f"   ⚠ could not prepare the test runner: {e}")
                log.exception("qa: ensure_runner")
                self._runner_ready = False
            return self._runner_ready

    def _run_job(self, phase, files):
        targets = select_targets(files, self.read_source, phase=phase,
                                 already=len(self.manifest),
                                 protected=getattr(self.arch, "NEXT_PROTECTED", None))
        if not targets:
            log.debug(f"qa: phase {phase} has nothing worth testing")
            return
        self._fire("on_phase", {"phase": -14, "title": f"Writing tests — phase {phase}",
                                "status": "active"})
        self.ensure_runner()
        written = self.author.write_for(targets, phase)
        self.jobs_done += 1
        self._fire("on_phase", {"phase": -14, "title": f"Writing tests — phase {phase}",
                                "status": "done", "written": len(written),
                                "files": written})

    def read_source(self, rel):
        """
        One generated file, from disk.

        Never `arch.files` — the generation thread owns that dict and is
        writing to it while this runs.
        """
        try:
            fp = self.arch._safe_path(rel) if self.arch else (self.project_dir / rel)
            if not fp.is_file():
                return None
            return fp.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            log.debug(f"read_source {rel}: {e}")
            return None

    def write_test_file(self, rel, content, *, target="", phase=0, tier=0):
        """
        Write one test, outside `arch.files` entirely.

        Deliberately not `arch.write_file`, for three measured reasons:

        * `unresolved_packages()` scans every `.js`/`.jsx` in `arch.files`
          regardless of directory, so a test would make `vitest` and `jsdom`
          look like missing imports and `install_unresolved()` would spend an
          LLM turn installing them in the middle of generation;
        * `_verify_output()` counts files outside the scaffold to decide
          whether the model produced anything, and tests would mask an empty
          build;
        * `write_file` unlinks the twin stem, so writing `x.test.jsx` would
          delete an existing `x.test.js`.
        """
        rel = (rel or "").strip().lstrip("./").replace("\\", "/")
        if not TEST_PATH_RE.match(rel):
            self._log("WARN", f"   ⛔ {rel} is not a test path — skipped")
            return False

        target_src = (self.read_source(target) or "") if target else ""
        content = add_helper_imports(
            ensure_mocks(drop_redundant_mocks(content), target_src))
        try:
            fp = self.arch._safe_path(rel) if self.arch else (self.project_dir / rel)
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content.rstrip() + "\n", encoding="utf-8")
        except Exception as e:
            self._log("ERROR", f"   ❌ could not write {rel}: {e}")
            return False

        with self._lock:
            self.manifest[rel] = {"target": target, "phase": phase,
                                  "tier": tier, "stale": False}
            self.report.written = sorted(self.manifest)
        self._save_manifest()
        size = f"{len(content) / 1024:.1f}KB" if len(content) >= 1024 else f"{len(content)}B"
        self._fire("on_file_written", rel, size, content)
        self._log("INFO", f"   🧪 {rel}  ({size})")
        return True

    def _save_manifest(self):
        try:
            d = self.project_dir / QA_DIR
            d.mkdir(parents=True, exist_ok=True)

            with self._lock:
                snapshot = dict(self.manifest)
            (self.project_dir / MANIFEST).write_text(
                json.dumps(snapshot, indent=2), encoding="utf-8")
        except Exception as e:
            log.debug(f"manifest: {e}")

    def load_manifest(self):
        """Restore the manifest when the pipeline reopens a project."""
        try:
            fp = self.project_dir / MANIFEST
            if fp.is_file():
                self.manifest = json.loads(fp.read_text(encoding="utf-8"))
                self.report.written = sorted(self.manifest)
        except Exception as e:
            log.debug(f"manifest load: {e}")
        return self.manifest

    def adopt_orphans(self) -> int:
        """
        Register test files that are on disk but not in the manifest.

        Two ways they get there. A manifest is written wholesale from
        `self.manifest`, and a session starts empty — so before `bind()`
        learned to load the file first, the one test a feature wrote replaced
        the twelve the build wrote. And a project can simply arrive with tests
        in it.

        Either way the effect is the same and it is quiet: `has_tests()` is
        false so the stage skips, and `target_of()` returns "" so the bug fixer
        arbitrates a failure without knowing which file it is about — it can
        then only conclude the test is wrong.

        The target is inferred from where the test lives, which is the same
        mapping `test_path_for` uses in the other direction. A guess that turns
        out wrong is no worse than the "" it replaces.
        """
        found = 0
        for fp in sorted((self.project_dir / "tests" / "unit").rglob("*.test.*")):
            rel = str(fp.relative_to(self.project_dir)).replace("\\", "/")
            if not TEST_PATH_RE.match(rel):
                continue
            entry = self.manifest.get(rel)
            if entry and entry.get("target"):
                continue

            if entry:
                target = self._infer_target(rel)
                if not target:
                    continue
                entry["target"] = target
            else:
                self.manifest[rel] = {"target": self._infer_target(rel),
                                      "phase": 0, "tier": 0, "stale": False,
                                      "adopted": True}
            found += 1
        if found:
            self.report.written = sorted(self.manifest)
            self._save_manifest()
        return found

    def _infer_target(self, test_rel: str) -> str:
        """The app file a test path implies, or '' when nothing matches."""
        stem = test_rel[len("tests/unit/"):].rsplit(".test.", 1)[0]
        if stem.startswith("api/"):
            cand = [f"app/api/{stem[4:]}/route.js"]
        else:
            cand = [f"{stem}.jsx", f"{stem}.js",
                    f"components/{stem.split('/')[-1]}.jsx"]
        for c in cand:
            if (self.project_dir / c).is_file():
                return c
        return ""

    def target_of(self, test_path):
        return (self.manifest.get(test_path) or {}).get("target", "")

    def mark_stale(self, rewritten):
        """
        Note tests whose subject changed after they were written.

        Seam A's repair pass can rewrite app files; a test authored against the
        old body is not wrong so much as out of date, and the bug fixer treats
        that as a prior rather than evidence about the code.
        """
        touched = {(p or "").lstrip("./").replace("\\", "/") for p in (rewritten or ())}
        n = 0
        for test, meta in self.manifest.items():
            if meta.get("target") in touched:
                meta["stale"] = True
                n += 1
        if n:
            self._save_manifest()
            self._log("INFO", f"   🧪 {n} test(s) marked stale — their target was repaired")
        return n

    def drain(self, timeout: float = 900):
        """
        Finish the queued work, or give up cleanly.

        On a local model nothing has run yet: the workers start here and the
        whole batch is serial, so generation was never competing for the GPU.
        Cancellation is checked between jobs, never mid-stream, so a test that
        is half-written is still finished and saved.

        The timeout is an abandonment point, not a schedule — whatever is still
        queued when it expires does not get written here, it gets written by
        the backfill one turn at a time. At 180s that was the normal outcome
        rather than the exception: on one build the drain waited out its full
        180s having authored nothing, and the eleven files it dropped cost the
        backfill 715s afterwards. It is now long enough that expiring means
        something is genuinely wrong, and the log says so plainly.
        """
        if not self.enabled or not self.arch:
            return self.report
        self.flush_files()
        if not self._q.empty():
            self._ensure_workers()
        deadline = time.time() + max(0.0, timeout)
        while time.time() < deadline:
            if self._q.empty() and not self._busy():
                break
            time.sleep(0.1)
        if not self._q.empty() or self._busy():
            self._cancel.set()
            self._log("WARN", f"   ⏳ QA authoring gave up after {timeout:.0f}s "
                              f"with {self._q.qsize()} batch(es) still queued — "
                              f"the backfill will pick them up, serially")
        for w in self._workers:
            w.join(timeout=5)
        if self.manifest:
            self._log("INFO", f"   🧪 {len(self.manifest)} test file(s) written "
                              f"while the app was being generated")
        return self.report

    def stop(self):
        self._cancel.set()
        for w in self._workers:
            w.join(timeout=5)

    def has_tests(self):
        return bool(self.manifest)
