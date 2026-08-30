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

from agents.core.runtime.command_runner import CommandRunner
from agents.core.llm.llm_client import is_cloud_model

from qa_agent.unit.spec import MAX_PER_PHASE, QAReport, select_targets


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




class QASessionBase:
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
        # Author tests while generation is happening.
        self.defer_execution = True
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
        from qa_agent.unit.author_write import UnitTestAuthor
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
        """Install the test runner as soon as the scaffold actually exists.

        `bind()` runs before ArchitectAgent writes package.json. The old warm
        thread called `npm install` immediately, so every new project began with
        one guaranteed npm failure (or, worse, npm creating metadata before the
        scaffold owned it). Polling here costs no build time — this is already a
        background thread — and preserves the intended overlap once package.json
        lands.
        """
        try:
            deadline = time.time() + 180
            package = self.project_dir / "package.json"
            while (not package.is_file() and not self._cancel.is_set()
                   and time.time() < deadline):
                time.sleep(0.25)
            if not package.is_file() or self._cancel.is_set():
                log.debug("qa: scaffold never became ready for runner warm-up")
                return
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


__all__ = [name for name in globals() if not name.startswith("__")]
