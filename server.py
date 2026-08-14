#!/usr/bin/env python3
"""
WebForge Server  —  HTTP :7824  |  WebSocket :7825
- Dual model selection (refine + build)
- Auto-pull Ollama models if missing
- Stop/unload model immediately after each stage (VRAM conservation)
- Fix loop uses npm run build for real errors + full codebase context
"""
import atexit
import base64
import signal
import sys, json, asyncio, logging, threading, time, re, socket, subprocess, os, textwrap, urllib3, uuid, io
urllib3.disable_warnings()


for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlsplit

import requests

try:
    import websockets
except ImportError:
    subprocess.run([sys.executable,"-m","pip","install","websockets",
                    "--break-system-packages","-q"])
    import websockets

sys.path.insert(0, str(Path(__file__).parent))


sys.path.insert(0, str(Path(__file__).parent / "srs-agent"))
from agents.refiner  import RefinerAgent
from agents.builder  import BuilderAgent, set_stream_callback
from agents.tester   import TesterAgent, set_emit as set_tester_emit
from agents.analyzer import AnalyzerAgent, AnalyzerReport, Finding
from agents import nextdocs
from agents.architect import ArchitectAgent, FileStreamParser
from agents.exports import check_named_imports, check_syntax, syntax_messages
from agents.features import FeaturesAgent
from agents.capture import PENCIL_SYSTEM, capture_region
from agents.images import ImageAgent
from agents.picker import (ELEMENT_EDIT_SYSTEM, ElementResolver, describe,
                           guard_scope, looks_like_addition, looks_like_global,
                           looks_like_page_only, looks_like_removal,
                           looks_like_retext, routes_rendering)
from agents.mongo import MONGO, db_name_for
from agents.bugfixer import BugFixerAgent
from agents.commands import CommandRunner
from qa_agent import (E2EAgent, FileSnapshot, QASession, TestHarness,
                      UnitTestAuthor, VitestRunner, select_targets)
from qa_agent.e2e import KIND_SELECTOR
from agents.ollama_client import (OllamaClient, is_cloud_model, max_context,
                                  get_local_host, load_settings, save_settings,
                                  set_default_client)
import shutil

def _maybe_set_playwright_env():

    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH") and os.environ.get("PLAYWRIGHT_NODEJS_PATH"):
        return

    exe = Path(sys.argv[0]).resolve()

    resources = exe.parent.parent

    pw = resources / "ms-playwright"
    node = resources / "node" / "bin" / "node"

    if pw.exists():
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(pw))
        os.environ.setdefault("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD", "1")

    if node.exists():
        os.environ.setdefault("PLAYWRIGHT_NODEJS_PATH", str(node))

_maybe_set_playwright_env()
def resolve_node_binaries():

    if getattr(sys, "frozen", False):
        exe_path = Path(sys.argv[0]).resolve()
        resources_dir = exe_path.parent.parent

        node_bin_dir = resources_dir / "node" / "bin"

        npm_path = node_bin_dir / "npm"
        node_path = node_bin_dir / "node"

        if npm_path.exists() and node_path.exists():
            return str(npm_path), str(node_path)

    return shutil.which("npm") or "npm", shutil.which("node") or "node"


NPM_BIN, NODE_BIN = resolve_node_binaries()

print("DEBUG: sys.executable =", sys.executable)
print("DEBUG: Using NPM_BIN  =", NPM_BIN)
print("DEBUG: Using NODE_BIN =", NODE_BIN)


node_dir = str(Path(NODE_BIN).parent)
if node_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{node_dir}:{os.environ.get('PATH','')}"

if hasattr(sys, "_MEIPASS"):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent

print(f"DEBUG: BASE_DIR = {BASE_DIR}")
print(f"DEBUG: UI_DIR = {BASE_DIR / 'ui'}")
PROD_DIR = BASE_DIR / "production-ready"
LOGS_DIR = BASE_DIR / "logs"
OLLAMA_URL = get_local_host()
DEFAULT_REFINE = "llama3.1:8b"
DEFAULT_BUILD  = "qwen2.5-coder:14b"
MAX_FIX    = 6


RUNTIME_DEADLINE = 900
DEV_PORT   = 5173
UI_PORT    = 7824
WS_PORT    = 7825


SRS_PORT   = 7826


DEPLOY_PORT = 7834


NEXT_READY_TIMEOUT = 180
NEXT_BUILD_TIMEOUT = 300

for d in [PROD_DIR, LOGS_DIR]: d.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("server")

clients    = set()
MAIN_LOOP  = None
active_vite = {"proc": None, "stderr_lines": []}


ollama = OllamaClient(OLLAMA_URL)
set_default_client(ollama)


def default_agent_model() -> str:
    """
    Pick a sane agent model when the caller didn't name one: the saved
    choice, else the largest-context cloud model Ollama actually offers,
    else the local build default.
    """
    saved = str(load_settings().get("agent_model", "")).strip()
    if saved:
        return saved
    try:
        cloud = ollama.discover().get("cloud") or []
        if cloud:
            return cloud[0]["id"]
    except Exception:
        pass
    return DEFAULT_BUILD


def emit(msg: dict):
    if MAIN_LOOP is None: return
    data = json.dumps(msg, ensure_ascii=False)
    async def _s():
        dead = set()
        for ws in list(clients):
            try: await ws.send(data)
            except: dead.add(ws)
        clients.difference_update(dead)
    asyncio.run_coroutine_threadsafe(_s(), MAIN_LOOP)

def elog(lvl, txt):

    log.info(f"[{lvl}] {txt}")
    emit({"type": "log", "level": lvl, "text": txt})
def estep(s, st):
    if st == "error":
        log.error(f"step {s} failed")
    emit({"type": "step", "step": s, "status": st})
def efile(n, sz, c=""):   emit({"type":"file",         "name":n,     "size":sz,   "content":c})
def edetect(t, s):        emit({"type":"detected",     "site_type":t,"strategy":s})
def eprog(lbl, pct):      emit({"type":"progress",     "step":lbl,   "pct":pct})
def edone(url, proj, preview="/"):

    emit({"type": "done", "url": url, "project": proj, "preview": preview})


def _route_of(payload: dict) -> str:
    """The page a picker-driven edit was made on, for the preview reload."""
    route = (payload or {}).get("route") or "/"
    route = str(route).strip()

    return route if route.startswith("/") and "//" not in route else "/"
def eerr(txt):

    log.error(txt)
    emit({"type": "error", "text": txt})
def estream_start(fname): emit({"type":"stream_start", "file":fname})
def estream(fname, tok):  emit({"type":"stream",       "file":fname, "token":tok})
def estream_end(f, c):    emit({"type":"stream_end",   "file":f,     "content":c})
def ephase(payload):      emit({**payload, "type":"phase"})
def echat(text):          emit({"type":"agent_msg",    "text":text})
def ememory(stats):       emit({"type":"memory",       **stats})
def emongo(payload):      emit({**payload, "type":"mongo"})
def ecommand(payload):    emit({**payload, "type":"command"})


def ecreds(accounts, source="plan", verified=None):
    """
    The generated app's demo accounts, for AgentForge's own UI.

    Generated apps used to print these on their own login page — a "Demo
    Accounts" card above the sign-in form listing five addresses and a shared
    password. The prompts now forbid that, so the accounts have to reach the
    developer some other way, and this is it.
    """
    emit({"type": "demo_accounts", "accounts": accounts,
          "source": source, "verified": verified})


_cur_stream = {"name": None, "buf": ""}

def on_token(token: str):
    if token.startswith("\x00START:"):
        fname = token[7:]
        _cur_stream["name"] = fname
        _cur_stream["buf"]  = ""
        estream_start(fname)
    elif token == "\x00END":
        fname = _cur_stream["name"]
        content = _cur_stream["buf"]
        estream_end(fname, content)
        _cur_stream["name"] = None
        _cur_stream["buf"]  = ""
    else:
        _cur_stream["buf"] += token
        estream(_cur_stream["name"] or "generating…", token)


def ensure_model(model: str) -> bool:
    """Check Ollama tags; pull model if missing. Returns True if ready."""

    if is_cloud_model(model):
        via = "API key" if ollama.api_key else \
              "signed-in Ollama" if ollama.signed_in() else None
        if via:
            elog("INFO", f"   ☁️  Cloud model ready: {model} via {via} "
                         f"(ctx {max_context(model):,})")
        else:

            elog("WARN", f"   ☁️  {model}: no API key and Ollama isn't signed "
                         f"in — trying anyway")
        return True

    if ollama.has_model(model):
        elog("INFO", f"   ✅ Model ready: {model}")
        return True

    elog("INFO", f"   📥 Pulling {model} from Ollama (first time only)…")
    ok = ollama.pull(model, on_progress=lambda p: elog("INFO", f"   📥 {model}: {p}%"))
    if ok:
        elog("INFO", f"   ✅ {model} pulled!")
    else:
        elog("ERROR", f"   ❌ Pull failed: {model}")
    return ok

def stop_model(model: str):
    """Unload model from VRAM immediately after use."""
    if is_cloud_model(model):
        return
    ollama.unload(model)
    elog("INFO", f"   🗑️  Unloaded {model}")

def _deps_ready(proj_dir: Path) -> bool:
    """
    Are node_modules already correct for this package.json?

    Stack-agnostic by construction: instead of probing for a specific binary
    (the old code looked for `vite`, which never exists under Next and so made
    `npm install` re-run on every call), check that every dependency
    package.json declares is physically installed.

    That single test also covers the case this needs to catch — when
    `sync_dependencies()` adds a package, its folder is absent and an install
    is triggered — while still recognising installs done by older versions of
    AgentForge, so existing projects are not needlessly reinstalled.
    """
    nm = proj_dir / "node_modules"
    if not nm.is_dir():
        return False
    try:
        pkg = json.loads((proj_dir / "package.json").read_text(encoding="utf-8"))
    except Exception:
        return False
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    if not deps:
        return False

    return all((nm / name / "package.json").exists() for name in deps)


def ensure_node_deps(proj_dir: Path) -> bool:
    if _deps_ready(proj_dir):
        return True

    first = not (proj_dir / "node_modules").is_dir()
    elog("INFO", "📦 Installing dependencies (npm install)…")

    from qa_agent.harness import NPM_LOCK
    with NPM_LOCK:
        try:
            r = subprocess.run(
                [NPM_BIN, "install", "--no-audit", "--no-fund",
                 "--prefer-offline", "--loglevel=error"],
                cwd=proj_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=900 if first else 300,
            )
            if r.returncode == 0:
                elog("INFO", "   ✅ npm install complete")
                return True
            elog("ERROR", f"   ❌ npm install failed:\n{(r.stderr or '')[:300]}")
            return False
        except subprocess.TimeoutExpired:
            elog("ERROR", "   ❌ npm install timed out")
            return False
        except Exception as e:
            elog("ERROR", f"   ❌ npm install crashed: {e}")
            return False


def detect_stack(proj_dir: Path) -> str:
    """
    Which framework a generated project uses.

    Projects created before the Next.js migration are Vite and must keep
    getting Vite prompts, a Vite dev server and Vite test heuristics.
    """
    try:
        pkg = json.loads((proj_dir / "package.json").read_text(encoding="utf-8"))
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        if "next" in deps:
            return "next"
        if "vite" in deps:
            return "vite"
    except Exception:
        pass
    if (proj_dir / "next.config.mjs").exists() or (proj_dir / "app").is_dir():
        return "next"
    return "vite"


def _kill_proc_tree(proc):
    """Kill a dev server *and its children* — npm/next spawn workers."""
    if proc is None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, timeout=15)
            return

        try:
            pgid = os.getpgid(proc.pid)
            own_group = pgid != os.getpgid(0)
        except Exception:
            pgid, own_group = None, False

        if own_group:
            try:
                os.killpg(pgid, signal.SIGTERM)
                proc.wait(timeout=4)
            except Exception:
                pass
            try:
                os.killpg(pgid, signal.SIGKILL)
            except Exception:
                pass
            return

        try:
            proc.terminate()
            proc.wait(timeout=4)
        except Exception:
            pass
        try:
            proc.kill()
        except Exception:
            pass
    except Exception:
        pass


def _kill_port(port: int):
    """Force-kill whatever holds a port, on Windows as well as POSIX."""
    if os.name == "nt":
        try:
            out = subprocess.run(["netstat", "-ano", "-p", "TCP"],
                                 capture_output=True, text=True,
                                 timeout=10).stdout
            pids = set()
            for line in out.splitlines():
                parts = line.split()

                if len(parts) >= 5 and parts[1].rsplit(":", 1)[-1] == str(port):
                    pids.add(parts[-1])
            for pid in pids - {"0", "4"}:
                subprocess.run(["taskkill", "/F", "/T", "/PID", pid],
                               capture_output=True, timeout=10)
            if pids:
                time.sleep(0.5)
        except Exception:
            pass
        return

    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=5
        )
        pids = [p.strip() for p in result.stdout.strip().split() if p.strip()]
        for pid in pids:
            try: subprocess.run(["kill", "-9", pid], timeout=3, capture_output=True)
            except: pass
        if pids:
            time.sleep(0.5)
    except Exception:
        pass


def _stop_dev_proc():
    """Terminate the tracked dev server, whatever stack it is."""
    if active_vite.get("proc"):
        _kill_proc_tree(active_vite["proc"])
        active_vite["proc"] = None


def start_vite(proj_dir: Path):
    """Kill old Vite fully, then start fresh on exact DEV_PORT."""

    _stop_dev_proc()

    _kill_port(DEV_PORT)
    active_vite["stderr_lines"] = []
    active_vite["stack"] = "vite"

    def _run():
        try:
            p = subprocess.Popen(

                [NPM_BIN, "run", "dev", "--", "--port", str(DEV_PORT),
                 "--host", "--strictPort"],
                cwd=proj_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=os.environ.copy(),

                **({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                   if os.name == "nt" else {"start_new_session": True}),
            )
            active_vite["proc"] = p

            def _stderr():
                for line in p.stderr:
                    l = line.strip()
                    if l:
                        active_vite["stderr_lines"].append(l)
                        if any(k in l for k in ["Error","error","failed","SyntaxError"]):
                            elog("WARN", f"   [vite] {l[:120]}")
            threading.Thread(target=_stderr, daemon=True).start()

            for line in p.stdout:
                l = line.strip()
                if l: elog("INFO", f"   [vite] {l}")
        except Exception as e:
            elog("ERROR", f"   Vite crashed: {e}")

    threading.Thread(target=_run, daemon=True).start()

def wait_for_vite(timeout: int = 40) -> bool:
    """Poll DEV_PORT until Vite responds HTTP 200 or timeout expires."""
    import urllib.request, urllib.error
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = urllib.request.urlopen(
                f"http://127.0.0.1:{DEV_PORT}", timeout=2
            )
            if r.status == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def vite_stderr() -> str:
    lines = active_vite.get("stderr_lines", [])
    err = [l for l in lines if any(k in l for k in
        ["Error","error","SyntaxError","ReferenceError","TypeError",
         "Cannot find","is not defined","failed","plugin:vite"])]
    return "\n".join(err[-40:])


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text or "")


def start_next(proj_dir: Path, port: int = DEV_PORT):
    """
    Start `next dev` on DEV_PORT.

    Note this cannot reuse start_vite: `--host` and `--strictPort` are Vite
    flags, and `next dev` exits immediately on unknown arguments. Next is
    launched directly through node rather than `npm run dev`, which removes a
    process layer and makes the tree far more reliable to kill.
    """
    _stop_dev_proc()
    _kill_port(port)
    active_vite["stderr_lines"] = []
    active_vite["ready"] = False
    active_vite["stack"] = "next"

    next_bin = proj_dir / "node_modules" / "next" / "dist" / "bin" / "next"
    flags = bundler_flag(proj_dir)
    if next_bin.exists():
        argv = [NODE_BIN, str(next_bin), "dev", *flags,
                "--port", str(port), "--hostname", "127.0.0.1"]
    else:
        argv = [NPM_BIN, "run", "dev", "--", *flags,
                "--port", str(port), "--hostname", "127.0.0.1"]

    env = {**os.environ,
           "NEXT_TELEMETRY_DISABLED": "1",
           "PORT": str(port),
           "NODE_ENV": "development",
           "BROWSER": "none",

           "FORCE_COLOR": "0", "NO_COLOR": "1"}

    kwargs = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
              if os.name == "nt" else {"start_new_session": True})

    def _run():
        try:
            p = subprocess.Popen(
                argv, cwd=proj_dir,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", env=env, **kwargs)
            active_vite["proc"] = p

            def _pump(stream, is_err):
                for line in stream:
                    l = _strip_ansi(line).strip()
                    if not l:
                        continue
                    active_vite["stderr_lines"].append(l)
                    if len(active_vite["stderr_lines"]) > 400:
                        del active_vite["stderr_lines"][:200]

                        active_vite["dropped"] = active_vite.get("dropped", 0) + 200
                    if any(k in l for k in ("Ready in", "✓ Ready", "- Local:")):
                        active_vite["ready"] = True
                    if is_err or any(k in l for k in
                                     ("Error", "error", "Failed to compile")):
                        elog("WARN", f"   [next] {l[:140]}")
                    else:
                        elog("INFO", f"   [next] {l[:140]}")

            threading.Thread(target=_pump, args=(p.stderr, True), daemon=True).start()
            _pump(p.stdout, False)
        except Exception as e:
            elog("ERROR", f"   Next.js crashed: {e}")

    threading.Thread(target=_run, daemon=True).start()


def wait_for_next(timeout: int = NEXT_READY_TIMEOUT, port: int = DEV_PORT) -> bool:
    """
    Wait for `next dev` to serve the index route.

    Readiness and compilation are separate: the server accepts connections
    quickly but then blocks while compiling `/`. So poll cheaply for liveness,
    then spend one long request warming the route — which also means Playwright
    never pays for the cold compile. A 500 counts as ready: the server is up
    and a page is throwing, which is exactly what the tester needs to see.
    """
    import urllib.request, urllib.error

    deadline = time.time() + timeout
    live = False
    while time.time() < deadline:
        if active_vite.get("ready"):
            live = True
            break
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                live = True
                break
        except OSError:
            pass
        proc = active_vite.get("proc")
        if proc is not None and proc.poll() is not None:
            elog("ERROR", "   ❌ Next.js dev server exited during startup")
            return False
        time.sleep(0.3)

    if not live:
        elog("ERROR", f"   ❌ Next.js did not start within {timeout}s")
        return False

    remaining = max(30, int(deadline - time.time()))
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=remaining)
        elog("INFO", "   ✅ Next.js compiled and serving")
        return True
    except urllib.error.HTTPError as e:

        elog("WARN", f"   ⚠ Next.js served HTTP {e.code} on /")
        return True
    except Exception as e:
        elog("WARN", f"   ⚠ Next.js warm-up request failed: {e}")
        return True


def next_stderr() -> str:
    """Compile errors from the Next dev server, for the LLM fix prompt."""
    lines = active_vite.get("stderr_lines", [])
    keys = ("Failed to compile", "Module not found", "Can't resolve", "⨯",
            "Error:", "SyntaxError", "ReferenceError", "TypeError",
            "is not exported from", "is not defined",
            "MongoServerSelectionError", "MongoNetworkError", "ECONNREFUSED")
    return "\n".join([l for l in lines if any(k in l for k in keys)][-40:])


def dev_log_mark() -> int:
    """Absolute position of the next line the dev server will print."""
    return (active_vite.get("dropped", 0)
            + len(active_vite.get("stderr_lines", [])))


_DEV_NOISE = re.compile(
    r"^\s*(?:[○✓⚡]|- Local:|- Network:|Ready in\b|Compiling\b|✓ Compiled\b"
    r"|GET .*\b[23]\d\d in\b|POST .*\b[23]\d\d in\b|Attention:|▲ Next\.js)")


def dev_log_since(mark: int, limit: int = 60) -> str:
    """
    Everything the dev server printed since `mark`.

    This exists because `next_stderr()` decides what matters by keyword, and a
    plain `TypeError: Cannot read properties of undefined … at Inventory
    (app/inventory/page.js:86:48)` — the shape of every 500 seen in this
    project — has its *useful* half on continuation lines that no keyword
    matches. Windowing the buffer around the request instead is exact: whatever
    the server printed while we were probing is, by construction, about that
    probe.

    Pairs with `logging.browserToTerminal`, which puts client-side errors into
    the same stream with a `[browser] … (file:line)` prefix.
    """
    lines = active_vite.get("stderr_lines", [])
    start = max(0, mark - active_vite.get("dropped", 0))
    fresh = [l for l in lines[start:] if not _DEV_NOISE.match(l)]
    return "\n".join(fresh[-limit:])


def start_dev_server(proj_dir: Path, stack: str = None):
    """Dispatch to the right dev server for the project's stack."""
    stack = stack or detect_stack(proj_dir)
    if stack == "next":
        start_next(proj_dir)
    else:
        start_vite(proj_dir)


def _dev_alive(timeout: float = 2.0) -> bool:
    """Is the dev server answering right now? Silent — no logs, no waiting."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{DEV_PORT}/",
                                    timeout=timeout) as r:
            return r.status < 500
    except Exception:
        return False


def wait_for_dev(stack: str, timeout: int = None) -> bool:
    if stack == "next":
        return wait_for_next(timeout or NEXT_READY_TIMEOUT)
    return wait_for_vite(timeout or 40)


def dev_stderr(stack: str) -> str:
    return next_stderr() if stack == "next" else vite_stderr()


class UIBuilder(BuilderAgent):
    """Thin wrapper — overrides _on_write and _install_deps to emit UI events."""

    def _on_write(self, fname: str, sz: str, content: str):
        efile(fname, sz, content)

    def _install_deps(self) -> bool:
        estep("install", "active")
        eprog("npm install…", 60)
        elog("INFO", "📦 npm install…")
        try:
            r = subprocess.run(
                [NPM_BIN, "install"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=180,
            )
            if r.returncode == 0:
                estep("install", "done")
                eprog("Dependencies ready", 75)
                elog("INFO", "   ✅ npm install complete")
                return True
            estep("install", "error")
            elog("ERROR", f"   npm failed: {r.stderr[:200]}")
            return False
        except FileNotFoundError:
            estep("install", "error")
            elog("ERROR", f"   npm binary not found at: {NPM_BIN}")
            return False


def run_pipeline(prompt: str, refine_model: str, build_model: str):
    set_stream_callback(on_token)
    set_tester_emit(emit)
    try:
        elog("INFO", "━" * 40)
        elog("INFO", f"💡 {prompt[:90]}")
        elog("INFO", f"🧠 Refine: {refine_model}   🏗️  Build: {build_model}")
        elog("INFO", "━" * 40)

        eprog("Checking refine model…", 3)
        if not ensure_model(refine_model):
            eerr(f"Cannot load refine model: {refine_model}"); return

        estep("refine", "active")
        eprog("Refining idea…", 8)
        elog("INFO", f"🧠 Agent 1 — {refine_model}")

        refiner = RefinerAgent(OLLAMA_URL, refine_model)
        refined = refiner.refine(prompt)
        if not refined:
            eerr("Refiner failed — is Ollama running?"); return

        estep("refine", "done")
        try:
            s = json.loads(refined)
            edetect(s.get("site_type", "?"), s.get("strategy", "?"))
            elog("INFO", f"   type={s.get('site_type')}  strategy={s.get('strategy')}")
        except: pass

        stop_model(refine_model)

        eprog("Checking build model…", 18)
        if not ensure_model(build_model):
            eerr(f"Cannot load build model: {build_model}"); return

        spec = {}
        try: spec = json.loads(refined)
        except: pass

        raw_name = spec.get("project_name",
                   re.sub(r"[^a-z]", "", prompt[:15].lower()))
        pname = re.sub(r"[^a-z0-9]", "", raw_name)[:20] or "project"

        proj_dir = _project_dir_for(pname, "vite")
        pname = proj_dir.name
        proj_dir.mkdir(parents=True, exist_ok=True)
        elog("INFO", f"   📁 {proj_dir}")

        estep("build", "active")
        eprog("Generating components…", 22)
        elog("INFO", f"🏗️  Agent 2 — {build_model}")

        builder = UIBuilder(OLLAMA_URL, build_model, proj_dir)
        if not builder.build(refined):
            eerr("Build failed"); return

        estep("build", "done")
        eprog("Components ready", 55)

        stop_model(build_model)

        estep("serve", "active")
        eprog("Starting Vite…", 72)
        elog("INFO", f"🌐 Starting Vite on :{DEV_PORT}")
        if not ensure_node_deps(proj_dir):
            eerr("Failed to install dependencies"); return
        start_vite(proj_dir)
        wait_for_vite(35)

        estep("test", "active")
        eprog("Running tests…", 80)
        elog("INFO", "🧪 Agent 3 — Playwright")
        emit({"type": "test_start"})

        tester = TesterAgent(proj_dir, DEV_PORT)

        npm_errors = ""

        for attempt in range(1, MAX_FIX + 2):
            elog("INFO", f"   🔬 Test run #{attempt}")
            emit({"type": "test_run", "attempt": attempt})

            errors = tester.test()

            if not errors:
                elog("INFO", "   🎉 All tests passed!")
                estep("test", "done")
                break

            if attempt > MAX_FIX:
                elog("WARN", f"   ⚠ Max fix attempts ({MAX_FIX}) reached — writing guaranteed fallbacks")

                from agents.builder import _safe_component
                for fpath, src in list(builder.built_files.items()):
                    if not (fpath.startswith("src/components/") and fpath.endswith(".jsx")):
                        continue
                    comp_name = fpath.split("/")[-1].replace(".jsx", "")
                    fp = proj_dir / fpath

                    if len(src.strip()) < 400 or npm_errors.strip():
                        safe = _safe_component(comp_name)
                        fp.write_text(safe, encoding="utf-8")
                        builder.built_files[fpath] = safe
                        elog("WARN", f"   🛟 Safe fallback written → {fpath}")
                estep("test", "done")
                break

            npm_errors = builder._npm_build_errors()
            vs_errors  = vite_stderr()
            all_errors = "\n".join(errors) + "\n" + npm_errors + "\n" + vs_errors

            elog("INFO", f"   📋 npm build output:\n{npm_errors[:300] or '  (none)'}")

            emit({"type": "test_fixing", "attempt": attempt,
                  "errors": errors[:5]})
            elog("INFO", f"   🔧 Fixing (attempt {attempt}/{MAX_FIX})…")

            if not ensure_model(build_model):
                elog("WARN", "   Cannot load build model for fix — skipping")
                break

            builder.fix_with_errors(all_errors)
            stop_model(build_model)

            elog("INFO", "   🔄 Restarting Vite…")
            if not ensure_node_deps(proj_dir):
                eerr("Dependency install failed")
                return
            start_vite(proj_dir)
            wait_for_vite(35)

        url = f"http://localhost:{DEV_PORT}"
        estep("serve", "done")
        eprog("Done!", 100)
        elog("INFO", f"🎉 Live at {url}")
        edone(url, pname)

    except Exception as e:
        eerr(f"Pipeline error: {e}")
        log.exception("Pipeline error")
    finally:
        set_stream_callback(None)


AGENT_STEPS = ["plan", "scaffold", "generate", "install", "test", "serve"]


def _npm_build_errors(proj_dir: Path, stack: str = "vite"):
    """
    `npm run build` surfaces real compile errors the dev server hides.

    Returns ``(error_text, conclusive)``. The second value matters: a timed-out
    `next build` used to return "" here, which the fix loop then read as "no
    errors" and shipped a broken app. An inconclusive check must never look
    like a clean one.
    """
    timeout = NEXT_BUILD_TIMEOUT if stack == "next" else 120
    env = {**os.environ, "CI": "true", "NEXT_TELEMETRY_DISABLED": "1",
           "NO_COLOR": "1", "FORCE_COLOR": "0"}
    try:
        r = subprocess.run([NPM_BIN, "run", "build"], cwd=proj_dir,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        log.warning("build check timed out")
        return "", False
    except Exception as e:
        log.warning(f"build check failed: {e}")
        return "", False

    txt = _strip_ansi((r.stdout or "") + "\n" + (r.stderr or ""))

    if r.returncode == 0:

        bad = [ln.strip() for ln in txt.splitlines()
               if "Attempted import error" in ln]
        if bad:
            return ("The build compiled, but these imports do not resolve and "
                    "the pages that make them will throw as soon as they are "
                    "opened:\n" + "\n".join(dict.fromkeys(bad))[:2000]), True
        return "", True

    i = txt.find("Failed to compile")
    if i >= 0:
        txt = txt[i:]
    return txt.strip()[:2500], True


def _redact_uri(uri: str) -> str:
    """`mongodb+srv://user:pass@host/db` → `mongodb+srv://user:***@host` —
    safe to show in the UI."""
    if not uri:
        return ""
    shown = re.sub(r"://([^:/@]+):[^@]*@", r"://\1:***@", uri)
    return shown[:60] + ("…" if len(shown) > 60 else "")


def _open_project(proj_name: str):
    """Boot an existing project so the preview iframe has something to show."""
    try:
        proj_dir = PROD_DIR / proj_name
        if not proj_dir.exists():
            eerr(f"Project not found: {proj_name}")
            return
        stack = detect_stack(proj_dir)
        elog("INFO", f"📂 Opening {proj_name} ({stack})")
        if stack == "next":
            MONGO.ensure_running()
        if not ensure_node_deps(proj_dir):
            eerr("Failed to install dependencies")
            return
        start_dev_server(proj_dir, stack)
        if wait_for_dev(stack):
            edone(f"http://localhost:{DEV_PORT}", proj_name)
        if stack == "next":
            _announce_project_credentials(proj_dir)
    except Exception as e:
        eerr(f"Could not open {proj_name}: {e}")
        log.exception("open project failed")


def _announce_project_credentials(proj_dir: Path):
    """
    Show an existing project's demo accounts when it is opened.

    Generated apps no longer print these on their own login page, so without
    this there is no way to sign in to an app you built last week.
    """
    try:
        arch = ArchitectAgent(ollama, DEFAULT_BUILD, proj_dir, stack="next")
        arch.load_existing()
        AnalyzerAgent(arch, proj_dir,
                      base_url=f"http://localhost:{DEV_PORT}",
                      callbacks=_analyzer_callbacks())._announce_credentials()
    except Exception as e:
        log.warning(f"could not read demo accounts: {e}")


def _slug(text: str, fallback: str = "app") -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    s = re.sub(r"-+", "-", s)[:28].strip("-")
    return s or fallback


def _has_app(d: Path) -> bool:
    """True when a directory already holds someone's application code.

    Only the scaffold's own placeholders don't count — those are what an
    interrupted build leaves behind, and stepping back into one is fine.
    """
    for root in ("app", "components", "lib", "src", "pages"):
        base = d / root
        if not base.is_dir():
            continue
        for fp in base.rglob("*"):
            if fp.is_file() and fp.suffix in {".js", ".jsx", ".mjs"}:
                rel = str(fp.relative_to(d)).replace("\\", "/")
                if rel not in ArchitectAgent.NEXT_SCAFFOLD:
                    return True
    return False


def next_major(proj_dir: Path) -> int:
    """The installed Next.js major version, or 0 when it cannot be read."""
    try:
        pj = proj_dir / "node_modules" / "next" / "package.json"
        if not pj.is_file():
            pj = proj_dir / "package.json"
            v = json.loads(pj.read_text(encoding="utf-8")) \
                    .get("dependencies", {}).get("next", "")
        else:
            v = json.loads(pj.read_text(encoding="utf-8")).get("version", "")
        m = re.search(r"(\d+)", v or "")
        return int(m.group(1)) if m else 0
    except Exception:
        return 0


def bundler_flag(proj_dir: Path) -> list:
    """
    `['--webpack']` on Next 16+, `[]` before it.

    Next 16 made Turbopack the default, and Turbopack words its diagnostics
    differently from the `Failed to compile` / `Module not found` /
    `Can't resolve` strings that `run_build_fix_loop`, `next_stderr` and
    `agents/tester.py` all match on. Pinning the bundler pins that vocabulary.

    It must be conditional, not unconditional: **Next 15.5.22 has no
    `--webpack` flag at all** — verified, its `dev --help` lists only `--turbo`
    and `--turbopack` — and `next dev` exits immediately on an unknown
    argument. Passing it to the eleven projects already on disk would kill
    every one of their dev servers.
    """
    return ["--webpack"] if next_major(proj_dir) >= 16 else []


def _project_dir_for(pname: str, stack: str) -> Path:
    """
    Where a new build should write.

    A NEW build never writes into a directory that already holds an app.

    This used to return `base` whenever `detect_stack(base) == stack`, which
    made "a Next.js app is already here" the *condition for reuse* rather than
    for avoidance — the suffixing loop below was unreachable for same-stack
    collisions. Since `_slug(prompt[:40])` keys a project on the first forty
    characters of the prompt, three prompts sharing an SRS preamble landed in
    one folder. Nothing ever empties a directory and `write_file` only
    overwrites, so a POS app, a school app and a car dealership ended up
    superimposed: 66 route URLs on disk against a 31-file plan.

    The build itself never noticed — `arch.files` starts empty. The analyzer
    did, because it reads from disk by design: every leftover
    `fetch('/api/attendance')` became a DEAD_ENDPOINT blocker, and the repair
    pass wrote nine route handlers for two dead applications. Because
    `db_name_for` also follows the directory name, the new app inherited the old
    one's `users` collection and its own seed never ran.

    Editing an existing project is unaffected — that path goes through
    `_open_for_edit`, not here.
    """
    base = PROD_DIR / pname
    if not base.exists() or not any(base.iterdir()):
        return base
    if not _has_app(base) and detect_stack(base) == stack:
        return base
    for i in range(2, 100):
        alt = PROD_DIR / f"{pname}-{i}"
        if not alt.exists() or not any(alt.iterdir()):
            elog("INFO", f"   📁 {pname} already holds a "
                         f"{detect_stack(base)} project — using {alt.name}")
            return alt
    return base


def _agent_callbacks(proj_dir: Path) -> dict:
    """Bridge ArchitectAgent events onto the existing WebSocket protocol."""
    return {
        "on_log":      lambda lvl, txt: elog(lvl, txt),
        "on_chat":     lambda text: echat(text),
        "on_progress": lambda label, pct: eprog(label, pct),
        "on_memory":   lambda stats: ememory(stats),
        "on_phase":    lambda p: ephase(p),
        "on_file_start":   lambda path: estream_start(path),
        "on_file_token":   lambda path, tok: estream(path, tok),
        "on_file_end":     lambda path, content: estream_end(path, content),
        "on_file_written": lambda path, size, content: efile(path, size, content),
        "on_command":  lambda ev: ecommand(ev),

        "npm_bin": NPM_BIN,
        "node_bin": NODE_BIN,
    }


MONGO.set_callbacks({
    "on_log":    lambda lvl, txt: elog(lvl, txt),
    "on_status": lambda s: emongo(s),
})


def _analyzer_callbacks() -> dict:
    """The analyzer speaks the same WS protocol as everything else."""
    return {
        "on_log":     lambda lvl, txt: elog(lvl, txt),
        "on_phase":   lambda p: ephase(p),
        "on_command": lambda ev: ecommand(ev),
        "on_mongo":   lambda ev: emongo(ev),
        "on_test":    lambda status, msg, detail="": emit(
            {"type": "test_result", "status": status, "msg": msg,
             "detail": detail}),
        "on_file_start": lambda path: estream_start(path),
        "on_file_end":   lambda path, content: estream_end(path, content),
        "on_creds":      lambda accounts, source, verified: ecreds(
            accounts, source, verified),
        "on_feature_plan": lambda payload: emit({**payload,
                                                 "type": "feature_plan"}),
        "npm_bin": NPM_BIN,
        "node_bin": NODE_BIN,
    }


_DB_ERROR_MARKERS = ("MongoServerSelectionError", "MongoNetworkError",
                     "ECONNREFUSED", "MONGODB_URI", "/api/health",
                     "connect ETIMEDOUT")


def _filter_db_noise(text: str, db_ok: bool) -> str:
    if db_ok or not text:
        return text
    keep = [ln for ln in text.splitlines()
            if not any(m in ln for m in _DB_ERROR_MARKERS)]
    return "\n".join(keep)


_TERMINAL_SIGNALS = (
    "Only plain objects can be passed",
    "Functions cannot be passed directly",
    "Event handlers cannot be passed",
    "cannot be passed directly to Client Components",
    "Classes or other objects with methods are not supported",
    "Objects are not valid as a React child",
    "Maximum update depth exceeded",
    "Hydration failed",
    "Text content does not match",
    "only works in a Client Component",
    "Unhandled Runtime Error",
    "Unhandled Rejection",
    "Module not found",
    "is not exported from",
    "is not a function",
    "is not defined",
    "Cannot read properties",
    "ReferenceError",
    "SyntaxError",
    "⨯",
)


def terminal_faults(text: str, limit: int = 6) -> list:
    """
    The dev server's own complaints, one entry per distinct fault.

    Deduplicated on the message itself: a serialisation error on a dashboard
    with five stat cards prints five near-identical blocks, and sending all
    five to the fix prompt spends the budget saying one thing.
    """
    if not text:
        return []
    seen, out = set(), []
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 12 or not any(s in line for s in _TERMINAL_SIGNALS):
            continue

        key = re.sub(r"[{<].*", "", line)[:90]
        if key in seen:
            continue
        seen.add(key)
        out.append(line[:400])
        if len(out) >= limit:
            break
    return out


MAX_BUILD_FIX = 3


def run_build_fix_loop(arch, proj_dir: Path, db_ok: bool,
                       max_rounds: int = MAX_BUILD_FIX) -> bool:
    """
    Compile the app and let the model repair whatever `next build` rejects.

    This runs BEFORE the dev server starts, which matters twice over: `next
    build` and `next dev` share `.next/`, so building first avoids clobbering a
    running server; and a compile error is a far cheaper, far more precise
    signal than waiting for Playwright to notice a blank page.

    The model fixes with its own tools — `write_file` for code, `run_command`
    for a missing package — so `Module not found: Can't resolve 'bcryptjs'` is
    something it can actually resolve instead of merely rewriting around.

    Returns True when the build is clean.
    """
    for rnd in range(1, max_rounds + 1):
        estep("build", "active")
        eprog(f"Compiling (round {rnd})…", min(84 + rnd * 2, 92))
        ephase({"phase": -3, "title": f"Build check {rnd}/{max_rounds}",
                "status": "active"})
        elog("INFO", f"🔨 npm run build (round {rnd}/{max_rounds})…")

        errors, conclusive = _npm_build_errors(proj_dir, "next")

        if not conclusive:
            elog("WARN", "   ⚠ Build check timed out — could not verify")
            ephase({"phase": -3, "title": f"Build check {rnd}/{max_rounds}",
                    "status": "done"})
            return False
        if not errors:
            elog("INFO", "   ✅ Build clean")
            estep("build", "done")
            ephase({"phase": -3, "title": "Build clean", "status": "done"})
            return True

        lines = [ln.rstrip() for ln in errors.strip().splitlines() if ln.strip()]
        first = lines[0][:120] if lines else "?"
        elog("WARN", f"   ❌ Build failed: {first}")

        for ln in lines[1:9]:
            elog("WARN", f"      {ln[:160]}")
        emit({"type": "test_fixing", "attempt": rnd,
              "errors": errors.splitlines()[:5]})

        if rnd == max_rounds:
            elog("WARN", f"   ⚠ Still failing after {max_rounds} rounds — "
                         f"serving anyway so you can see it")
            ephase({"phase": -3, "title": f"Build check {rnd}/{max_rounds}",
                    "status": "done"})
            return False

        guidance = nextdocs.guidance_for(errors)
        if guidance:
            elog("INFO", f"   📖 {', '.join(nextdocs.slugs_in(errors)[:2])} "
                         f"— attached Next.js's own fix guide")

        arch.update(textwrap.dedent(f"""\
            `npm run build` failed. Fix every error below.

            Read the error carefully and choose the right tool:
              • a missing npm package  → <run_command>npm install <name></run_command>
                and only then rewrite the file that imports it
              • anything else          → rewrite the affected file completely

            ```
            {_filter_db_noise(errors, db_ok)[:4000]}
            ```
            """) + ("\n" + guidance if guidance else ""))

        ensure_node_deps(proj_dir)
        ephase({"phase": -3, "title": f"Build check {rnd}/{max_rounds}",
                "status": "done"})

    return False


MAX_QA_FIX = 4
QA_DEADLINE = 1800


MAX_QA_STALLS = 2


QA_TIERS = {
    0: "the usual repair",
    1: "the reason the last write was refused, and more of the file's context",
    2: "permission to fix the component instead of the test",

    3: "the harness itself as a suspect, and permission to name it",
}
MAX_QA_TIER = max(QA_TIERS)


QA_FIX_WORKERS = 4


def _qa_callbacks() -> dict:
    """The QA agents speak the protocol the UI already renders."""
    cb = _analyzer_callbacks()
    cb["on_file_written"] = lambda path, size, content: efile(path, size, content)
    return cb


def _qa_skip(qa, why):
    elog("WARN", f"   ⚠ Unit tests skipped — {why}")
    if qa:
        qa.report.skipped_reason = why
    emit({"type": "test_result", "status": "skip",
          "msg": "Unit tests skipped", "detail": why})


def read_qa_results(proj_name: str) -> dict:
    """
    Everything the QA stages left on disk for one project. Read only.

    Four files, three of which already existed and one of which
    `write_qa_report` adds. They are gathered here rather than in the browser
    because `/api/files/` cannot reach them — its `SKIP_DIRS` contains
    `.agentforge` and its `SRC_EXT` is `{.js,.jsx,.css}`, so both the directory and
    the extension are excluded.

    Missing files are reported as missing rather than as zeros. A stage that
    never ran and a stage that ran and found nothing are different facts, and a
    dashboard that shows 0 for both is lying about one of them.
    """
    proj_dir = PROD_DIR / proj_name
    if not proj_dir.is_dir():
        return {"error": f"no such project: {proj_name}"}
    qa_dir = proj_dir / ".agentforge" / "qa"

    def load(path, default=None):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    out = {"project": proj_name, "have": {}}

    out["vitest"] = load(qa_dir / "vitest.json")
    out["have"]["vitest"] = out["vitest"] is not None

    out["manifest"] = load(qa_dir / "manifest.json", {})
    out["have"]["manifest"] = bool(out["manifest"])

    out["report"] = load(qa_dir / "report.json")
    out["have"]["report"] = out["report"] is not None

    history = []
    try:
        for line in (qa_dir / "history.jsonl").read_text(
                encoding="utf-8").splitlines():
            if line.strip():
                try:
                    history.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    out["history"] = history
    out["have"]["history"] = bool(history)

    lh = load(proj_dir / ".agentforge" / "lighthouse.json")
    if lh:
        cats = lh.get("categories") or {}
        audits = lh.get("audits") or {}
        out["performance"] = {
            "scores": {k: round((v or {}).get("score") * 100)
                       for k, v in cats.items()
                       if isinstance((v or {}).get("score"), (int, float))},
            "metrics": {k: (audits.get(k) or {}).get("displayValue")
                        for k in ("largest-contentful-paint",
                                  "cumulative-layout-shift",
                                  "total-blocking-time",
                                  "first-contentful-paint", "speed-index")
                        if audits.get(k)},
            "fetchTime": lh.get("fetchTime", ""),
            "runtimeError": (lh.get("runtimeError") or {}).get("code", ""),
        }
    out["have"]["performance"] = "performance" in out

    tests = {}
    for sub in ("tests/unit", "tests/e2e", "tests/quarantine"):
        d = proj_dir / sub
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*")):
            if f.is_file() and f.suffix in (".js", ".jsx"):
                try:
                    rel = str(f.relative_to(proj_dir)).replace("\\", "/")
                    tests[rel] = f.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
    out["tests"] = tests
    out["have"]["tests"] = bool(tests)
    return out


def _srs_get(path: str, timeout: float = 20.0):
    """One read from the SRS agent. Returns None rather than raising."""
    try:
        r = requests.get(f"http://127.0.0.1:{SRS_PORT}{path}", timeout=timeout)
        return r if r.status_code == 200 else None
    except requests.RequestException:
        return None


def adopt_srs(srs_id: str, proj_dir: Path) -> bool:
    """
    Move an SRS into the project it produced.

    An SRS is written before the project exists — the interview happens first,
    and there is nothing to name a folder after until a build starts. So it is
    staged under production-ready/.srs/<srs_id>/ and adopted here, which is the
    first moment both halves are known.

    The staging copy is deliberately NOT removed. Building twice from one SRS
    has to keep working, and deleting is how twenty minutes of interview gets
    lost to a build that failed for an unrelated reason.

    Four artifacts are fetched rather than copied, because the SRS writes them
    on demand and they are not on disk: the approved plan, the handoff, the
    interview, and the PDF. Doing it here rather than inside the SRS keeps that
    package free of any knowledge of AgentForge.

    Never fatal. A missing SRS tab is not worth failing a build over.
    """
    from datetime import datetime, timezone
    try:
        staging = PROD_DIR / ".srs" / srs_id
        dest = proj_dir / ".agentforge" / "srs"
        dest.mkdir(parents=True, exist_ok=True)

        copied = 0
        if staging.is_dir():
            for src in staging.rglob("*"):
                if not src.is_file():
                    continue
                target = dest / src.relative_to(staging)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target)
                copied += 1

        base = f"/projects/{srs_id}"

        plan = _srs_get(f"{base}/plan")
        if plan is not None:
            body = plan.json()
            markdown = body.get("markdown") or ""
            if markdown:
                (dest / "plan.md").write_text(markdown, encoding="utf-8")
            (dest / "plan.json.srs").write_text(
                json.dumps(body.get("plan") or {}, indent=2), encoding="utf-8")

        handoff = _srs_get(f"{base}/builder-handoff")
        if handoff is not None:
            body = handoff.json()
            (dest / "handoff.json").write_text(json.dumps(body, indent=2),
                                               encoding="utf-8")
            (dest / "handoff.txt").write_text(body.get("prompt") or "",
                                              encoding="utf-8")

        interview = _srs_get(f"{base}/interview")
        if interview is not None:
            (dest / "interview.json").write_text(
                json.dumps(interview.json(), indent=2), encoding="utf-8")

        if not (dest / "srs_latest.json").exists():
            document = _srs_get(f"{base}/srs-json")
            if document is not None:
                (dest / "srs_latest.json").write_text(
                    json.dumps(document.json(), indent=2), encoding="utf-8")
                elog("INFO", "   📄 SRS document fetched (staging had none)")

        d_dir = dest / "diagrams"
        have_diagrams = d_dir.is_dir() and any(d_dir.glob("*.mmd"))
        if not have_diagrams:
            drawn = _srs_get(f"{base}/diagrams")
            if drawn is not None:
                d_dir.mkdir(parents=True, exist_ok=True)
                wrote = 0
                for item in (drawn.json() or {}).get("diagrams") or []:
                    kind = str(item.get("kind") or item.get("name") or "").strip()
                    source = item.get("source") or item.get("mermaid") or ""
                    if not kind or not source:
                        continue
                    (d_dir / f"{kind}.mmd").write_text(source, encoding="utf-8")
                    wrote += 1

                    if item.get("svg"):
                        (d_dir / f"{kind}.svg").write_text(item["svg"],
                                                           encoding="utf-8")
                if wrote:
                    elog("INFO", f"   🖼 {wrote} diagram(s) fetched (staging had none)")

        pdf = _srs_get(f"{base}/download/pdf", timeout=120)
        if pdf is not None and pdf.content:
            (dest / "SRS_latest.pdf").write_bytes(pdf.content)

        (dest / "link.json").write_text(json.dumps({
            "srs_id": srs_id,
            "adopted_at": datetime.now(timezone.utc).isoformat(),
            "staged_at": str(staging),
            "files_copied": copied,
        }, indent=2), encoding="utf-8")

        elog("INFO", f"   📄 SRS adopted from {srs_id} ({copied} files)")
        return True
    except Exception as e:
        elog("WARN", f"   ⚠️  Could not adopt the SRS: {type(e).__name__}: {e}")
        return False


def _srs_app_name(srs_id: str) -> str:
    """
    What the customer called their app, from the staged SRS. "" if unknown.

    Read from the staging folder rather than over HTTP because this runs
    before the project directory exists, which is before `adopt_srs` has
    anything to copy into.
    """
    if not srs_id:
        return ""
    try:
        doc = json.loads((PROD_DIR / ".srs" / srs_id / "srs_latest.json")
                         .read_text(encoding="utf-8"))
        doc = doc.get("srs_document") or doc
        summary = doc.get("app_summary")
        name = ((summary or {}).get("app_name") if isinstance(summary, dict)
                else "") or doc.get("project_name") or ""
        name = " ".join(str(name).split())

        return name if 0 < len(name) <= 40 else ""
    except Exception:
        return ""


def _srs_name_line(proj_dir: Path) -> str:
    """
    What the customer named their app, said before anything else.

    The handoff prompt does not carry the name at all — `render_prompt` opens
    with the category, "An Online Store web application.", and never mentions
    it. Appending the name after that prompt was not enough: measured on a
    real build, the architect was handed "THE APP IS CALLED: The Cheese Board"
    in the detail section and still shipped `artisan-cheese-reserve`, with the
    words "Cheese Board" nowhere in the UI.

    So it goes FIRST, above the prompt. The customer was asked what to call
    their app and typed an answer; inventing a different one is the build
    disagreeing with the only part of the spec they wrote themselves.
    """
    try:
        doc = json.loads((proj_dir / ".agentforge" / "srs" / "srs_latest.json")
                         .read_text(encoding="utf-8"))
        doc = doc.get("srs_document") or doc
    except Exception:
        return ""
    summary = doc.get("app_summary")
    name = ((summary or {}).get("app_name") if isinstance(summary, dict)
            else "") or doc.get("project_name") or ""
    name = " ".join(str(name).split())
    if not name or len(name) > 60:
        return ""
    return (f"THE APP IS CALLED “{name}”. The customer chose that name. Use it "
            f"exactly, in the header, the page title, the sign-in screen and "
            f"`package.json`. Do not invent another one.\n\n")


def _srs_brief(proj_dir: Path, model: str) -> str:
    """
    What the SRS knows that its handoff prompt had to leave out.

    The handoff prompt is capped at 1200 words and 8000 characters, and that
    cap is not ours: `builder_brief.py` says plainly that it exists because the
    builder it was written for replies with at most 8192 tokens and never sets
    `num_ctx`. AgentForge has neither limit — the architect runs on a model whose
    window AgentForge measures. Handing it a brief trimmed to fit a different
    program's budget throws away the database design, the roles, the
    non-functional requirements and the acceptance criteria for no reason.

    So the prompt still goes first, unchanged and on its own terms, and this is
    appended underneath it. Diagrams, ambiguities and risks are deliberately
    left out: they are for the person reading the SRS tab, and an architect
    cannot act on any of them.

    Sized against the model's real context window, and says what it dropped.
    """
    srs_dir = proj_dir / ".agentforge" / "srs"
    try:
        doc = json.loads((srs_dir / "srs_latest.json").read_text(encoding="utf-8"))
        doc = doc.get("srs_document") or doc
    except Exception:
        return ""
    if not doc:
        return ""

    def rows(items, key=None, id_key=None):
        """
        One line per item, whatever shape the item is.

        The fallback chain is the SRS's own key names, checked against a
        generated document rather than guessed — the same list, for the same
        reason, as `line()` in studio/components/srs/views.jsx. Four sections
        here were silently empty for every build ever run because this chain
        was missing `criterion` and `page_name`, and because the callers below
        passed the wrong key: a table is `table_name`, not `name`, and a role
        is `role_name` — `role` is the ACCESS MATRIX's key, not the role
        list's. An empty section does not read as a bug; it reads as a
        specification that had nothing to say.
        """
        out = []
        for item in (items or []):
            ident = ""
            if isinstance(item, str):
                text = item
            elif isinstance(item, dict):
                text = (item.get(key) if key else None) or (
                    item.get("requirement") or item.get("description")
                    or item.get("criterion") or item.get("rule")
                    or item.get("text") or item.get("page_name")
                    or item.get("role_name") or item.get("name") or "")
                if id_key:
                    ident = " ".join(str(item.get(id_key) or "").split())
            else:
                text = str(item)
            text = " ".join(str(text).split())
            if text:
                out.append(f"- {ident}  {text}" if ident else f"- {text}")
        return out

    def page_rows(pages):
        """Name, route, who may open it, and what it is for."""
        out = []
        for p in (pages or []):
            if isinstance(p, str):
                out.append(f"- {p}")
                continue
            if not isinstance(p, dict):
                continue
            name = " ".join(str(p.get("page_name") or p.get("name") or "").split())
            if not name:
                continue
            line = f"- {name}"
            if p.get("route"):
                line += f"  ({p['route']})"
            roles = [str(r) for r in (p.get("allowed_roles") or []) if str(r).strip()]
            if roles:
                line += f"  — {', '.join(roles)}"
            fns = [" ".join(str(f).split()) for f in (p.get("functions") or [])
                   if str(f).strip()]
            if fns:
                line += f"\n    {' '.join(fns)}"
            out.append(line)
        return out

    parts = ["\n\n---\n\nThe approved specification this was planned from.",
             "The prompt above is a short summary of it. Where the two differ, "
             "follow this specification — except where the prompt states a fact "
             "about this machine, such as the app's name or a logo already on "
             "disk, which it knows and this does not."]

    titles = []

    def section(title, lines):
        if lines:
            parts.append(f"\n{title}\n" + "\n".join(lines))
            titles.append(title)

    tables = (doc.get("database_design") or {}).get("tables") or []
    shaped = []
    for t in tables:
        if not isinstance(t, dict):
            continue
        cols = t.get("columns") or t.get("fields") or []
        names = [c if isinstance(c, str) else (c.get("name") or c.get("column") or "")
                 for c in cols]
        names = [n for n in names if n]
        name = t.get("table_name") or t.get("name")
        if name:
            shaped.append(f"- {name}: {', '.join(names) or 'no columns given'}")

    matrix = []
    for row in (doc.get("role_access_matrix") or []):
        if not isinstance(row, dict):
            continue
        who = row.get("role") or row.get("role_name")
        if not who:
            continue
        pages = ", ".join(str(p) for p in (row.get("allowed_pages") or []))
        can = ", ".join(str(f) for f in (row.get("allowed_functions") or []))
        matrix.append(f"- {who} may open: {pages or 'nothing listed'}"
                      + (f"\n    and may: {can}" if can else ""))

    flows = []
    for w in (doc.get("business_workflows") or []):
        if not isinstance(w, dict):
            continue
        name = w.get("workflow_name") or w.get("name")
        steps = [" ".join(str(s).split()) for s in (w.get("steps") or [])
                 if str(s).strip()]
        if name and steps:
            flows.append(f"- {name}: "
                         + " → ".join(f"{i}. {s}" for i, s in enumerate(steps, 1)))

    section("REQUIREMENTS", rows(doc.get("functional_requirements"), id_key="id"))
    section("DATA", shaped)
    section("ROLES", rows(doc.get("roles"), key="role_name"))
    section("PAGES THAT REQUIRE A LOGIN", page_rows(doc.get("protected_pages")))
    section("PAGES THAT MUST BE PUBLIC", page_rows(doc.get("public_pages")))
    section("WHO CAN REACH WHAT", matrix)
    section("HOW THE WORK FLOWS", flows)
    section("DONE MEANS", rows(doc.get("acceptance_criteria"), key="criterion",
                               id_key="id"))
    section("VALIDATION RULES", rows(doc.get("validation_rules"), key="rule",
                                     id_key="field"))
    section("SECURITY", rows(doc.get("security_requirements")))
    section("QUALITIES", rows(doc.get("non_functional_requirements"), id_key="id"))
    section("ASSUMPTIONS ALREADY AGREED", rows(doc.get("assumptions")))

    text = "\n".join(parts)

    from agents.architect import CHARS_PER_TOKEN, HISTORY_BUDGET
    budget = int(max_context(model) * HISTORY_BUDGET * CHARS_PER_TOKEN / 6)
    if len(text) > budget:
        cut = text.rfind("\n", 0, budget)
        dropped = text[cut:].count("\n- ") if cut > 0 else text.count("\n- ")
        text = text[:cut if cut > 0 else budget] + "\n"

        lost = [t for t in titles if f"\n{t}\n" not in text]
        elog("WARN", f"   ✂ SRS brief trimmed to {budget:,} chars for {model} — "
                     f"{dropped} line(s) left out (they are all in the SRS tab)"
                     + (f"; sections lost: {', '.join(lost)}" if lost else ""))
    elog("INFO", f"   📄 Architect briefed with the SRS ({len(text):,} chars "
                 f"of a {budget:,} budget)")
    return text


def read_srs_results(proj_name: str) -> dict:
    """
    Everything the SRS tab shows, gathered server-side.

    Same reasons as read_qa_results: `.agentforge/` is excluded from every project
    walk, so the browser cannot reach any of this on its own. And the same
    convention — a `have` map, with missing reported as missing. "No
    ambiguities were found" and "the ambiguity stage never ran" are different
    facts and a tab showing an empty list for both is lying about one.
    """
    proj_dir = PROD_DIR / proj_name
    if not proj_dir.is_dir():
        return {"error": f"no such project: {proj_name}"}
    srs_dir = proj_dir / ".agentforge" / "srs"

    def load(path, default=None):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def text(path, default=""):
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return default

    out = {"project": proj_name, "have": {}}
    if not srs_dir.is_dir():

        out["have"] = {k: False for k in
                       ("document", "plan", "handoff", "interview",
                        "diagrams", "pdf")}
        return out

    out["link"] = load(srs_dir / "link.json", {}) or {}

    document = load(srs_dir / "srs_latest.json", {}) or {}
    out["document"] = document.get("srs_document") or document
    out["have"]["document"] = bool(out["document"])

    out["plan"] = text(srs_dir / "plan.md")
    out["have"]["plan"] = bool(out["plan"].strip())

    out["handoff"] = load(srs_dir / "handoff.json", {}) or {}
    out["have"]["handoff"] = bool(out["handoff"].get("prompt"))

    out["interview"] = load(srs_dir / "interview.json", {}) or {}
    out["have"]["interview"] = bool(out["interview"].get("transcript"))

    diagrams = []
    d_dir = srs_dir / "diagrams"
    if d_dir.is_dir():
        for mmd in sorted(d_dir.glob("*.mmd")):
            svg = mmd.with_suffix(".svg")
            body = text(svg) if svg.is_file() else ""
            diagrams.append({
                "name": mmd.stem,
                "mermaid": text(mmd),
                "svg": body if 0 < len(body) <= 400_000 else "",
                "png": (mmd.with_suffix(".png")).is_file(),
            })
    out["diagrams"] = diagrams
    out["have"]["diagrams"] = bool(diagrams)

    out["have"]["pdf"] = (srs_dir / "SRS_latest.pdf").is_file()
    return out


DEPLOY_RUNS: dict = {}
DEPLOY_LOCK = threading.Lock()


DEPLOY_DONE = {"LIVE", "FAILED", "ROLLED_BACK", "DESTROYED"}


def _deploy_call(method: str, path: str, body=None, timeout=(2, None)):
    """One request to the deployment agent. Raises with a readable message."""
    r = requests.request(method, f"http://127.0.0.1:{DEPLOY_PORT}{path}",
                         json=body, timeout=timeout)
    try:
        data = r.json()
    except Exception:
        data = {"error": (r.text or "")[:400]}
    if r.status_code >= 400:
        raise RuntimeError(data.get("error") or f"HTTP {r.status_code}")
    return data


def _deploy_mongo_uri(settings: dict) -> str:
    """
    The database the deployed app will use.

    NOT simply AgentForge's `mongodb_uri`. That one exists so a build can be
    pointed at a different local mongod, and it is very often a loopback
    address — which would be written into AWS Secrets Manager or a Vercel
    production environment as the production database and fail there in a way
    that looks nothing like a settings mistake. A loopback URI is rejected
    rather than deployed.
    """
    explicit = str(settings.get("deploy_mongodb_uri", "")).strip()
    if explicit:
        return explicit
    fallback = str(settings.get("mongodb_uri", "")).strip()
    if fallback and not re.search(r"(?:@|//)(?:127\.0\.0\.1|localhost|\[::1\])",
                                  fallback):
        return fallback
    return ""


def deploy_settings_summary() -> dict:
    """
    What is configured for deploying, and nothing that could be replayed.

    Same rule as /api/settings: a secret is reported as set, with the last four
    characters, and never echoed. The Deploy tab uses this to say which of the
    three accounts still needs connecting.
    """
    s = load_settings()
    token = str(s.get("vercel_token", "")).strip()
    mongo = _deploy_mongo_uri(s)

    cli_token = False
    try:
        from deployment_agent.vercel_auth import _candidate_auth_files
        cli_token = any(p.is_file() for p in _candidate_auth_files())
    except Exception:                                           # noqa: BLE001
        pass
    return {
        "vercel_cli_signed_in": cli_token,
        "aws_profile": str(s.get("aws_profile", "")).strip(),
        "aws_region": str(s.get("aws_region", "")).strip(),
        "aws_start_url": str(s.get("aws_start_url", "")).strip(),
        "aws_sso_region": str(s.get("aws_sso_region", "")).strip(),
        "vercel_token_set": bool(token),
        "vercel_token_hint": (f"…{token[-4:]}" if token else ""),
        "mongodb_uri_set": bool(mongo),
        "mongodb_uri_hint": _redact_uri(mongo),
        "deploy_model": str(s.get("deploy_model", "")).strip(),
    }


def start_deployment(project: str, target: str, opts: dict) -> dict:
    """Begin a deployment and answer immediately. Raises ValueError if it cannot."""
    if not project:
        raise ValueError("project is required")
    proj_dir = PROD_DIR / project
    if not proj_dir.is_dir():
        raise ValueError(f"no such project: {project}")
    if target not in ("vercel", "aws_ec2", "aws_ecs"):
        raise ValueError(f"unsupported target: {target}")
    if DEPLOY_API["state"] in ("off", "import-failed"):
        raise ValueError("the deployment agent is not running")

    settings = load_settings()
    mongo = str(opts.get("mongodb_uri", "")).strip() or _deploy_mongo_uri(settings)
    if not mongo:
        raise ValueError("no production MongoDB URI — set one in Settings")

    if target.startswith("aws_") and not str(settings.get("aws_profile", "")).strip():
        raise ValueError("no AWS account connected — sign in from Settings")

    with DEPLOY_LOCK:
        current = DEPLOY_RUNS.get(project)
        if current and current.get("state") not in DEPLOY_DONE and not current.get("error"):
            raise ValueError("a deployment for this project is already running")
        DEPLOY_RUNS[project] = {
            "project": project, "target": target, "run_id": "",
            "state": "STARTING", "phase": "analysis", "percent": 0,
            "message": "Starting…", "error": "", "url": "",
            "started": time.time(), "finished": None, "events": [],

            "cursor": 0,
        }

    threading.Thread(target=_deploy_autopilot,
                     args=(project, target, dict(opts), mongo, settings),
                     daemon=True).start()
    return dict(DEPLOY_RUNS[project])


def _deploy_set(project: str, **patch):
    run = DEPLOY_RUNS.get(project)
    if run is not None:
        run.update(patch)


def _deploy_drain_events(project: str, run_id: str, after: int) -> int:
    """
    Pull whatever the agent has emitted since `after` into AgentForge's log.

    Returns the new cursor. This is the whole reason the agent's websocket on
    :7835 was not ported — the same events are in its SQLite with an id, and a
    cursor read is both simpler and replayable after a reload.
    """
    try:
        data = _deploy_call("GET", f"/api/runs/{run_id}/events?after={after}",
                            timeout=(2, 30))
    except Exception:
        return after
    run = DEPLOY_RUNS.get(project)
    for ev in data.get("events") or []:
        after = max(after, int(ev.get("event_id") or 0))
        msg = str(ev.get("message") or "").strip()
        if not msg:
            continue
        kind = str(ev.get("type") or "")
        level = {"error": "ERROR", "warning": "WARN"}.get(kind, "INFO")
        elog(level, f"   🚀 {msg}")
        if run is not None:
            run["events"] = (run["events"] + [{
                "id": int(ev.get("event_id") or 0),
                "type": kind, "stage": ev.get("stage") or "",
                "status": ev.get("status") or "",
                "percent": int(ev.get("percent") or 0), "message": msg,
            }])[-400:]
            if kind != "log":
                run["phase"] = ev.get("stage") or run["phase"]
                run["percent"] = int(ev.get("percent") or run["percent"])
                run["message"] = msg
    return after


def _deploy_serving(run: dict) -> bool:
    """Is the thing actually answering? Measured, not inferred from a score."""
    url = str((run.get("repo") or {}).get("application_url") or "").strip()
    if not url:
        return False
    for path in ("/api/health", "/"):
        try:
            r = requests.get(url.rstrip("/") + path, timeout=(5, 20),
                             allow_redirects=False)
            if r.status_code < 400:
                return True
        except requests.RequestException:
            continue
    return False


def _deploy_wait(project: str, run_id: str, until: set, deadline: float,
                 settle_from: set = frozenset(), settle_after: float = 240.0) -> dict:
    """
    Poll the run until it reaches one of `until`, draining events as it goes.

    The cursor lives on the run, not in this function. It is called twice —
    once to wait for the review and once for the deployment — and a local
    cursor starting at 0 the second time replayed every analysis event into
    the log and into the stepper a second time.

    `settle_from` exists because the agent's own path to LIVE is not reachable
    in every configuration. Its monitor promotes VALIDATING to LIVE only when a
    readiness score clears 90, and that score's ceiling is exactly 100 with no
    headroom: skipping the production build alone zeroes a 15-point category,
    so the ceiling becomes 85 and the run can never be promoted no matter how
    healthy the deployment is. This function used to wait the full 5400s for a
    state that would never arrive and then report a live, serving site as
    "the deployment agent stopped responding".

    So after `settle_after` seconds parked in one of those states, the site
    itself is asked. A URL that answers is the answer.
    """
    parked_since = None
    while time.time() < deadline:
        run_state = DEPLOY_RUNS.get(project) or {}
        cursor = _deploy_drain_events(project, run_id,
                                      int(run_state.get("cursor") or 0))
        _deploy_set(project, cursor=cursor)
        try:
            run = _deploy_call("GET", f"/api/runs/{run_id}", timeout=(2, 30))
        except Exception as e:
            elog("WARN", f"   ⚠️  could not read the deployment: {e}")
            time.sleep(4)
            continue
        state = str(run.get("state") or "")
        _deploy_set(project, state=state, run_id=run_id)
        if state in until:
            _deploy_set(project,
                        cursor=_deploy_drain_events(project, run_id, cursor))
            return run
        if state in settle_from:
            parked_since = parked_since or time.time()
            if time.time() - parked_since > settle_after and _deploy_serving(run):
                elog("INFO", "   🚀 the site is answering; not waiting for the "
                             "agent's readiness score")
                _deploy_set(project, cursor=_deploy_drain_events(project, run_id, cursor))
                return {**run, "state": "LIVE"}
        else:
            parked_since = None
        time.sleep(2.5)

    try:
        run = _deploy_call("GET", f"/api/runs/{run_id}", timeout=(2, 30))
        if _deploy_serving(run):
            return {**run, "state": "LIVE"}
    except Exception:                                           # noqa: BLE001
        pass
    raise TimeoutError("the deployment agent stopped responding")


def _deploy_autopilot(project: str, target: str, opts: dict,
                      mongo: str, settings: dict):
    """analyze → wait for review → deploy → wait for terminal → adopt."""
    proj_dir = PROD_DIR / project
    try:
        elog("INFO", f"🚀 Deploying {project} to "
                     f"{'Vercel' if target == 'vercel' else 'AWS EC2'}")
        started = _deploy_call("POST", "/api/runs/analyze", {
            "cloud_consent": True,
            "path": str(proj_dir),
            "target": target,
            "validate_container": bool(opts.get("validate_container", True)),
        })
        run_id = str(started.get("run_id") or "")
        _deploy_set(project, run_id=run_id, state="ANALYZING",
                    message="Reading the project…")
        elog("INFO", f"   🚀 run {run_id[:8]} — analysing")

        run = _deploy_wait(project, run_id, {"REVIEW_READY", "FAILED"},
                           time.time() + 3600)
        if run.get("state") != "REVIEW_READY":
            raise RuntimeError(run.get("error")
                               or "analysis did not reach a reviewable state")

        plan = run.get("plan") or {}
        if not plan.get("model_used"):
            raise RuntimeError(
                "the deployment plan was written without a model, and the agent "
                "will not deploy one — check the deploy model in Settings")

        body = {"approved": True, "mongodb_uri": mongo}
        if target == "vercel":
            token = str(settings.get("vercel_token", "")).strip()
            if token:
                body["vercel_token"] = token
        else:

            body["aws_profile"] = str(settings.get("aws_profile", "")).strip()
            body["region"] = (str(settings.get("aws_region", "")).strip()
                              or "ap-south-1")

        _deploy_set(project, state="DEPLOYING", message="Deploying…")
        elog("INFO", "   🚀 review passed — deploying")
        _deploy_call("POST", f"/api/runs/{run_id}/deploy", body)

        run = _deploy_wait(project, run_id, DEPLOY_DONE, time.time() + 5400,
                           settle_from={"VALIDATING"}, settle_after=240)

        url = str((run.get("repo") or {}).get("application_url") or "")
        _deploy_set(project, url=url, finished=time.time())
        if run.get("state") == "LIVE":
            elog("SUCCESS", f"   🚀 live{f' at {url}' if url else ''}")
        else:
            _deploy_set(project, error=str(run.get("error") or "")
                        or f"deployment ended {run.get('state')}")
            elog("ERROR", f"   🚀 deployment ended {run.get('state')}"
                          f" — {run.get('error') or 'no reason given'}")
        adopt_deploy(run_id, proj_dir)
    except Exception as e:
        _deploy_set(project, error=f"{type(e).__name__}: {e}",
                    state="FAILED", finished=time.time())
        elog("ERROR", f"   🚀 deployment failed — {type(e).__name__}: {e}")


def adopt_deploy(run_id: str, proj_dir: Path) -> bool:
    """
    Put the deployment's record into the project it deployed.

    Same shape and the same reason as adopt_srs: the agent keeps its state in
    production-ready/.deploy/, which no project walk reaches, and reopening a
    project a week later should still show what was deployed and where.

    Never fatal. A missing record is not worth failing a finished deploy over.
    """
    from datetime import datetime, timezone
    try:
        dest = proj_dir / ".agentforge" / "deploy"
        dest.mkdir(parents=True, exist_ok=True)

        run = _deploy_call("GET", f"/api/runs/{run_id}", timeout=(2, 60))
        (dest / "run.json").write_text(json.dumps(run, indent=2), encoding="utf-8")

        events = _deploy_call("GET", f"/api/runs/{run_id}/events?after=0",
                              timeout=(2, 60))
        (dest / "events.json").write_text(json.dumps(events, indent=2),
                                          encoding="utf-8")

        try:
            snap = _deploy_call("GET", f"/api/runs/{run_id}/monitor",
                                timeout=(2, 120))
            (dest / "monitor.json").write_text(json.dumps(snap, indent=2),
                                               encoding="utf-8")
        except Exception:
            pass

        (dest / "link.json").write_text(json.dumps({
            "run_id": run_id,
            "adopted_at": datetime.now(timezone.utc).isoformat(),
            "state": run.get("state", ""),
            "target": (run.get("plan") or {}).get("target", ""),
        }, indent=2), encoding="utf-8")

        elog("INFO", f"   🚀 deployment record saved ({run.get('state')})")
        return True
    except Exception as e:
        elog("WARN", f"   ⚠️  Could not save the deployment record: "
                     f"{type(e).__name__}: {e}")
        return False


def retire_deploy(proj_dir: Path, run_id: str) -> bool:
    """Move a finished deployment's record out of the way, keeping every byte.

    The counterpart to `adopt_deploy`. Teardown deletes the cloud resources and
    marks the agent's run DESTROYED, but it never touched this folder — so the
    Deploy tab went on drawing an instance, a stack and a live status bar for
    infrastructure that no longer existed. Pressing Delete appeared to do
    nothing, which is exactly how it was reported.

    Archived rather than deleted, because the record IS the evidence: the event
    stream, the readiness score and the last monitor snapshot exist nowhere
    else once the stack is gone, and they are what a write-up is built from.
    `.agentforge/deploy-archive/<run_id>/` keeps them where the project is, and the
    agent's own evidence rows and export endpoints are keyed by run id and
    untouched by any of this.
    """
    from datetime import datetime, timezone
    try:
        live = proj_dir / ".agentforge" / "deploy"
        if not live.is_dir():
            return False
        archive = proj_dir / ".agentforge" / "deploy-archive" / (run_id or "unknown")
        archive.parent.mkdir(parents=True, exist_ok=True)
        if archive.exists():

            archive = archive.with_name(f"{archive.name}-{int(time.time())}")
        shutil.move(str(live), str(archive))

        (proj_dir / ".agentforge" / "deploy-deleted.json").write_text(
            json.dumps({"run_id": run_id,
                        "deleted_at": datetime.now(timezone.utc).isoformat(),
                        "archive": archive.name}, indent=2),
            encoding="utf-8")
        log.info(f"Retired deployment record to {archive.name}")
        return True
    except Exception as e:

        log.warning(f"Could not retire deployment record: {type(e).__name__}: {e}")
        return False


def _deploy_run_state(run_id: str, fallback: str) -> str:
    """The run's state according to the agent, not according to a stale file.

    `run.json` is a snapshot taken by `adopt_deploy` when the deployment
    finished, and nothing rewrites it afterwards — so a run torn down later
    still reads LIVE there for ever. The agent is the only authority.

    Falls back to whatever the file said when the agent cannot be reached: a
    Deploy tab that hides a real deployment because the agent was briefly down
    would be a worse answer than a slightly stale one.
    """
    if not run_id:
        return fallback
    try:
        fresh = _deploy_call("GET", f"/api/runs/{run_id}", timeout=(2, 5))
        return str(fresh.get("state") or fallback)
    except Exception:
        return fallback


def read_deploy_results(proj_name: str) -> dict:
    """
    Everything the Deploy tab shows, gathered server-side.

    Two sources, and they answer different questions: `live` is the deployment
    running right now in this AgentForge, and `last` is what is on disk from a
    previous one. A tab that only had the first would go blank on every reload.
    """
    proj_dir = PROD_DIR / proj_name
    if not proj_dir.is_dir():
        return {"error": f"no such project: {proj_name}"}

    def load(path, default=None):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    d_dir = proj_dir / ".agentforge" / "deploy"
    live = DEPLOY_RUNS.get(proj_name)
    out = {
        "project": proj_name,
        "agent": deploy_status(),
        "live": dict(live) if live else None,
        "have": {"last": False},
        "settings": deploy_settings_summary(),
    }
    if d_dir.is_dir():
        run = load(d_dir / "run.json", {}) or {}

        if run and _deploy_run_state(run.get("id", ""),
                                     run.get("state", "")) == "DESTROYED":
            retire_deploy(proj_dir, run.get("id", ""))
            run = {}
        if run:
            out["have"]["last"] = True
            out["last"] = {
                "run_id": run.get("id", ""),
                "state": run.get("state", ""),
                "target": (run.get("plan") or {}).get("target", ""),
                "readiness": run.get("readiness") or {},

                "repo_state": run.get("repo") or {},
                "error": run.get("error") or "",
                "link": load(d_dir / "link.json", {}) or {},

                "monitor": load(d_dir / "monitor.json", {}) or {},
                "events_count": len(load(d_dir / "events.json", {}).get("events", [])
                                    if isinstance(load(d_dir / "events.json", {}), dict)
                                    else load(d_dir / "events.json", []) or []),
            }

    marker = load(proj_dir / ".agentforge" / "deploy-deleted.json", {}) or {}
    if marker and not out["have"]["last"]:
        out["deleted"] = marker
    return out


def write_qa_report(proj_dir: Path, qa, *, unit=None, security=None,
                    audit=None, e2e=None, perf=None, runtime=None,
                    security_ran: bool = True) -> bool:
    """
    Put everything the QA stages learned on disk, once, at the end.

    Most of it exists nowhere else. `emit()` is fire-and-forget with no history
    and no replay, so a page opened after a build — or reloaded during one —
    sees nothing that already happened; and every stage's return value was
    discarded by its caller. The vitest report, the round-one history and the
    Lighthouse audits are already files, but the security findings, the e2e
    flow, the unresolved cases and the suspects lived only in memory and died
    with the run.

    Written next to the reports it summarises, so it travels with the project.
    Never fatal: a build that produced an app is not worth failing over a
    dashboard file.
    """
    from datetime import datetime, timezone

    rep = getattr(qa, "report", None)

    def failure(f):
        return {"file": getattr(f, "test_file", ""), "case": getattr(f, "name", ""),
                "target": getattr(f, "target", ""), "kind": getattr(f, "kind", ""),
                "message": getattr(f, "message", "")}

    def finding(f):
        return {"severity": getattr(f, "severity", ""), "code": getattr(f, "code", ""),
                "path": getattr(f, "path", ""), "message": getattr(f, "message", ""),
                "fix": getattr(f, "fix", "")}

    doc = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "unit": dict(unit or {}),
        "suite": {
            "passed": getattr(rep, "passed", 0) if rep else 0,
            "failures": [failure(f) for f in (getattr(rep, "failures", []) or [])],
            "unresolved": list(getattr(rep, "unresolved", []) or []) if rep else [],
            "suspects": list(getattr(rep, "suspects", []) or []) if rep else [],
            "quarantined": list(getattr(rep, "quarantined", []) or []) if rep else [],
            "written": list(getattr(rep, "written", []) or []) if rep else [],
            "skipped_reason": getattr(rep, "skipped_reason", "") if rep else "",
        },
        "security": {

            "ran": bool(security_ran),
            "findings": [finding(f) for f in (security or [])],
            "audit": dict(audit or {}),
        },
        "e2e": dict(e2e or {}),
        "performance": dict(perf or {}),

        "runtime": list(runtime or []),
    }
    try:
        out = proj_dir / ".agentforge" / "qa" / "report.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")
        return True
    except Exception as e:
        log.warning(f"could not write the QA report: {e}")
        return False


def _report_unfixed(errors) -> None:
    """
    Name the runtime bugs that are shipping, rather than "serving as-is".

    "Reached 3 fix attempts — serving as-is" told the user a number of
    attempts and nothing about what is broken. What ships matters more than
    how hard it was tried.
    """
    if not errors:
        return
    elog("WARN", f"   ❗ the app is being served with {len(errors)} known "
                 f"problem(s):")
    for e in errors[:6]:
        elog("WARN", f"      ✗ {' '.join(str(e).split())[:110]}")
    emit({"type": "test_result", "status": "fail",
          "msg": f"{len(errors)} runtime problem(s) unfixed",
          "detail": " | ".join(str(e).splitlines()[0][:80] for e in errors[:4])})


def _leave_unresolved(runner, failures, why: str) -> int:
    """
    Stop repairing, and say plainly that the suite is NOT green.

    This replaces what used to happen here, which was to rewrite each still-red
    case as `it.skip` and, where that did not take, move the whole file to
    `tests/quarantine/` — a directory the vitest config excludes. Either way
    the next run reported zero failures, so every exit from the repair loop
    ended in the words "the suite is green". It was not: across the projects on
    disk that is 30 skipped cases and 32 set-aside files being counted as
    passing. Deleting a case removes it from BOTH sides of the ratio, so the
    percentage improves precisely because the evidence left.

    `agents/bugfixer.py` already refuses a repair that introduces `it.skip`.
    AgentForge has to obey the rule it enforces on the model.

    So: nothing is moved, nothing is silenced. The cases stay in the suite, red
    and runnable, recorded on the report under their own names. A caller that
    wants to try again has everything it needs to; a caller that ships anyway
    ships with the truth attached.
    """
    from qa_agent.runner import diagnose, diagnose_all

    if not failures:
        return 0
    files = _by_test_file(failures)
    qa_report = getattr(runner, "qa", None)
    if qa_report is not None and hasattr(qa_report, "report"):
        seen = {(u.get("file"), u.get("case"))
                for u in getattr(qa_report.report, "unresolved", [])}
        for f in failures:
            if (f.test_file, f.name) in seen:
                continue
            qa_report.report.unresolved.append({
                "file": f.test_file, "case": f.name, "target": f.target,
                "message": f.message, "why": why,
                "diagnosis": diagnose(f.stack or f.message or ""),
            })
    top = diagnose_all(failures)
    elog("WARN", f"   ❗ {len(failures)} case(s) in {len(files)} file(s) are "
                 f"still failing — {why}")
    if top:
        elog("WARN", "   ❗ " + ", ".join(f"{n} × {name}" for name, n in top[:3]))
    for f in failures[:6]:
        elog("WARN", f"      ✗ {f.test_file} — {f.name[:70]}")
    return len(files)


_CASE_LINE_RE = re.compile(
    r"^(\s*)(it|test)(\s*(?:\.\s*\w+)?\s*\(\s*)(['\"`])(.+?)\4", re.M)


def _backfill_tests(arch, proj_dir: Path, qa) -> int:
    """
    Author tests for every testworthy file the per-task jobs never reached.

    Tests are written as each task lands, and `select_targets` hands out at
    most `MAX_PER_PHASE` per task — so a task that writes seven components gets
    four of them tested and the other three are never mentioned again. Measured
    on a finished build: sixteen testworthy files, five with a test, and
    nothing in the log to say the other eleven had been skipped rather than
    judged not worth testing.

    Runs after `qa.drain()` and before Seam A, for the same reason the drain is
    there: the analyzer can rewrite application code, and a test written
    against the pre-repair body describes a file that no longer exists.
    """

    if not qa or not getattr(qa, "enabled", True) or not qa.author:
        return 0
    try:
        from qa_agent.spec import GENERATED, select_targets
    except Exception as e:
        log.debug(f"backfill: {e}")
        return 0

    SKIP = ("node_modules", ".next", "tests/", ".agentforge", "public/")
    srcs = []
    for f in proj_dir.glob("**/*.js*"):
        if not f.is_file():
            continue
        rel = str(f.relative_to(proj_dir)).replace("\\", "/")
        if rel in GENERATED or any(s in rel for s in SKIP):
            continue
        srcs.append(rel)

    tested = {m.get("target") for m in qa.manifest.values() if m.get("target")}
    todo = [r for r in srcs if r not in tested]
    if not todo:
        return 0

    targets = select_targets(todo, qa.read_source, phase=0,
                             already=len(qa.manifest),
                             protected=getattr(arch, "NEXT_PROTECTED", None),
                             limit=len(todo))
    if not targets:
        return 0

    elog("INFO", f"   🧪 {len(targets)} file(s) still have no test — writing "
                 f"them now")
    ephase({"phase": -14, "title": "Backfilling tests", "status": "active"})
    written = []
    try:
        qa.ensure_runner()
        written = qa.author.write_for(targets, 0)
    except Exception as e:
        elog("WARN", f"   ⚠ Backfill failed: {e}")
        log.exception("backfill")
    ephase({"phase": -14, "title": "Backfilling tests", "status": "done",
            "written": len(written)})

    still = [t.path for t in targets
             if t.path not in {m.get("target") for m in qa.manifest.values()}]
    if still:
        elog("WARN", f"   ⚠ {len(still)} file(s) remain untested: "
                     f"{', '.join(p.split('/')[-1] for p in still[:4])}")
    return len(written)


ROUND_ONE_FLOOR = 90


def _record_round_one(proj_dir: Path, qa, passed: int, failures: list) -> None:
    """
    Say how round one went as a RATE, name what dominated it, and keep it.

    The count on its own does not travel: "5 failing" means something different
    in a 20-case suite and an 80-case one, and it says nothing about why. Every
    authoring fix this stage has had came from classifying failures by hand
    across every project on disk after the fact. This puts that same answer on
    screen for one build, every build, so the next regression announces itself
    instead of waiting for someone to go looking.
    """
    from datetime import datetime, timezone

    from qa_agent.runner import diagnose_all

    total = passed + len(failures)
    if not total:
        return
    rate = passed * 100 // total
    elog("INFO", f"   📊 round 1: {passed}/{total} passing ({rate}%)")

    top = diagnose_all(failures)
    if top:
        elog("INFO", "   📊 " + ", ".join(f"{n} × {name}" for name, n in top[:3]))
    if rate < ROUND_ONE_FLOOR:
        elog("WARN", f"   ⚠ round-1 pass rate {rate}% — below the "
                     f"{ROUND_ONE_FLOOR}% floor")

    try:
        hist = proj_dir / ".agentforge" / "qa" / "history.jsonl"
        hist.parent.mkdir(parents=True, exist_ok=True)
        with hist.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "cases": total, "passed": passed, "failed": len(failures),
                "rate": rate, "floor": ROUND_ONE_FLOOR,
                "top": [{"class": n, "count": c} for n, c in top[:5]],
            }) + "\n")
    except Exception as e:
        log.warning(f"could not append qa history: {e}")


def drop_tests_for_missing_targets(proj_dir: Path, qa) -> list:
    """
    Remove tests whose subject no longer exists, before the suite runs.

    A test is written against a file. If that file is later deleted, emptied,
    or reduced to a comment, the test is not failing — there is nothing left
    for it to be about, and no repair can make it honest. It will burn every
    repair round and then be set aside at the end, which is how one build lost
    nine cases without ever saying why.

    Measured: `components/SiteNav.jsx` was written, nothing imported it, a
    later repair replaced its body with a comment explaining the removal, and
    `SiteNav.test.jsx` kept nine cases pointed at it. The quarantine note the
    fixer eventually wrote said exactly that — after nine cases had already
    been counted as lost.

    "Exists" means "still exports something". A file of pure comments is a
    removed component with an explanation attached, and that is the shape this
    is looking for.
    """
    if not qa or not getattr(qa, "manifest", None):
        return []
    dropped = []
    for test_path, meta in sorted(qa.manifest.items()):
        target = (meta or {}).get("target") or ""
        if not target:
            continue
        tf = proj_dir / target
        why = ""
        if not tf.is_file():
            why = "the file it tests was deleted"
        else:
            try:
                body = tf.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if not re.search(r"^\s*export\b", body, re.M):
                why = "the file it tests exports nothing — it was removed"
        if not why:
            continue
        try:
            (proj_dir / test_path).unlink(missing_ok=True)
        except OSError as e:
            log.debug(f"drop {test_path}: {e}")
            continue
        dropped.append((test_path, target, why))

    for test_path, _, _ in dropped:
        qa.manifest.pop(test_path, None)
    if dropped:
        qa._save_manifest()
        qa.report.written = sorted(qa.manifest)
        elog("WARN", f"   🗑 {len(dropped)} test file(s) removed before the run "
                     f"— their subject is gone:")
        for test_path, target, why in dropped:
            elog("WARN", f"      {test_path} → {target}: {why}")
    return dropped


def run_qa_unit_stage(arch, proj_dir: Path, qa, *, build_ok: bool) -> dict:
    """
    Install the runner, run the generated tests, and repair what fails.

    Placed between `run_build_fix_loop` and `start_next` — the only window in
    the pipeline where nothing holds `.next/`, which matters because a fix to
    application code has to be re-compiled before it can be trusted.

    Three rules keep this from being a way to make an app worse:

    * **Nothing runs unless the build is green.** A red build means the failure
      the tests report is a symptom, and repairing symptoms is how a doom loop
      starts.
    * **A code fix must survive a rebuild.** `FileSnapshot` holds the bytes; if
      the build goes green→red, or the failure count does not strictly
      decrease, the round is reverted byte for byte.
    * **A QA failure never fails the pipeline.** Every path here returns, and
      the app is served either way.
    """
    out = {"ran": False, "passed": 0, "failed": 0, "fixed": 0, "code_fixes": 0}
    if not qa or not qa.has_tests():
        return out
    if not build_ok:
        _qa_skip(qa, "the build is not green, so a failing test would be a "
                     "symptom rather than the bug")
        return out

    deadline = time.time() + QA_DEADLINE
    ephase({"phase": -15, "title": "Running unit tests", "status": "active"})

    harness = TestHarness(proj_dir, callbacks=_qa_callbacks(), cmd=qa.cmd)
    harness.materialise()
    if not harness.install():
        _qa_skip(qa, "the test runner could not be installed")
        ephase({"phase": -15, "title": "Running unit tests", "status": "done"})
        return out

    orphaned = drop_tests_for_missing_targets(proj_dir, qa)
    if not qa.has_tests():
        _qa_skip(qa, "every generated test was written against a file that no "
                     "longer exists")
        ephase({"phase": -15, "title": "Running unit tests", "status": "done"})
        return out

    runner = VitestRunner(proj_dir, cmd=qa.cmd, callbacks=_qa_callbacks(),
                          session=qa)
    fixer = BugFixerAgent(arch, proj_dir, callbacks=_qa_callbacks(), session=qa,
                          model=QASession.model_for(qa, arch))
    snap = FileSnapshot(proj_dir)

    previous, stalls, best = None, 0, None

    tier = 0

    watch = None

    baseline_cases = set()
    for rnd in range(1, MAX_QA_FIX + 2):
        passed, failures, ok = runner.run(paths=watch)
        if ok and rnd == 1:
            baseline_cases = runner.case_names()
        if not ok:
            _qa_skip(qa, "the test runner produced no report")
            break
        out.update(ran=True, passed=passed, failed=len(failures))
        qa.report.passed, qa.report.failures = passed, failures
        _emit_qa_results(passed, failures, rnd)

        if rnd == 1:
            _record_round_one(proj_dir, qa, passed, failures)

        if not failures:
            elog("INFO", f"   ✅ {passed} unit test(s) passed")
            break

        if rnd > MAX_QA_FIX:
            elog("WARN", f"   ❌ {len(failures)} unit test(s) still failing "
                         f"after {MAX_QA_FIX} repair round(s)")
        else:
            elog("WARN", f"   ❌ {len(failures)} unit test(s) failing "
                         f"(round {rnd}/{MAX_QA_FIX})")
        if rnd > MAX_QA_FIX:
            _leave_unresolved(runner, failures,
                             "still failing after every repair round")
            break
        if time.time() > deadline:
            _qa_skip(qa, f"the {QA_DEADLINE}s QA budget is spent")
            _leave_unresolved(runner, failures,
                             f"the {QA_DEADLINE}s QA budget ran out before "
                             f"this could be repaired")
            break

        now_cases = {(f.test_file, f.name) for f in failures}
        worse = (previous is not None
                 and not (now_cases < previous and len(failures) < len(best)))
        if worse:
            stalls += 1
            new_red = sorted(now_cases - previous)
            why = (f"broke {len(new_red)} case(s) that were passing"
                   if new_red else
                   f"did not reduce the failures ({len(best)} → {len(failures)})")
            elog("WARN", f"   ↩ round {rnd - 1} {why} — reverting it")
            reverted = snap.restore()
            if reverted:
                elog("INFO", f"   ↩ restored {len(reverted)} file(s)")
            if stalls >= MAX_QA_STALLS:

                if best is not None:
                    failures = best
                    out["failed"] = len(failures)
                    qa.report.failures = failures

                if tier < MAX_QA_TIER:
                    tier += 1
                    stalls = 0
                    elog("INFO", f"   ⤴ two rounds made no progress — "
                                 f"escalating to {QA_TIERS[tier]} "
                                 f"({tier}/{MAX_QA_TIER})")
                else:
                    elog("WARN", f"   ⚠ every repair strategy is spent — "
                                 f"{len(failures)} case(s) still failing")
                    _leave_unresolved(runner, failures,
                                      "every repair strategy was tried and "
                                      "none of them made it pass")
                    break
            else:
                elog("INFO", f"   ↻ trying again ({stalls}/{MAX_QA_STALLS})")
        else:
            stalls = 0
            previous, best = now_cases, failures

            snap.forget()

        ephase({"phase": -16, "title": f"Fixing failing tests (round {rnd})",
                "status": "active"})
        groups = _by_test_file(failures)
        snap.capture([g[0].test_file for g in groups]
                     + [g[0].target for g in groups if g[0].target])

        code_written, lock = [], threading.Lock()

        def repair(group):
            if time.time() > deadline:
                return
            try:
                v = fixer.fix(group, build_ok=build_ok, round_no=rnd,
                              tier=tier)
            except Exception as e:
                elog("WARN", f"   ⚠ repair failed on {group[0].test_file}: {e}")
                log.exception("qa fix")
                return
            with lock:
                if v.quarantine:
                    runner.quarantine(v.test_file, v.evidence or "set aside")
                elif v.touched_code:
                    code_written.append(v.written)
                    out["code_fixes"] += 1
                elif v.written:
                    out["fixed"] += 1

        with ThreadPoolExecutor(max_workers=QA_FIX_WORKERS) as pool:
            list(pool.map(repair, groups))

        watch = sorted({g[0].test_file for g in groups})
        ephase({"phase": -16, "title": f"Fixing failing tests (round {rnd})",
                "status": "done"})

        if code_written:
            elog("INFO", f"   🔨 re-checking the build after "
                         f"{len(code_written)} code fix(es)")
            if not run_build_fix_loop(arch, proj_dir, True, max_rounds=1):
                elog("WARN", "   ↩ a QA code fix broke the build — reverting "
                             "every file this round touched")
                snap.restore(code_written)
                out["code_fixes"] -= len(code_written)

                elog("WARN", f"   ↩ {len(failures)} case(s) still red after "
                             f"the revert")

    saw_everything = watch is None
    if watch is not None and ok:
        passed, failures, ok = runner.run()
        if ok:
            saw_everything = True
            out.update(passed=passed, failed=len(failures))
            qa.report.passed, qa.report.failures = passed, failures
            if failures:
                elog("WARN", f"   ⚠ {len(failures)} test(s) the targeted runs "
                             f"did not cover are failing")

    if failures:
        _leave_unresolved(runner, failures, "still failing when the stage ended")
        out["failed"] = len(failures)
        qa.report.failures = failures

    left = runner.skipped() if saw_everything else []
    if left:
        out["skipped"] = len(left)
        elog("WARN", f"   ❗ {len(left)} case(s) are marked it.skip and never "
                     f"ran — they are not passing")
        for path, name in left[:5]:
            elog("WARN", f"      ⤬ {path} — {name[:70]}")

    gone = (runner.vanished(baseline_cases)
            if baseline_cases and saw_everything else [])
    if gone:
        out["deleted"] = len(gone)
        elog("WARN", f"   ❗ {len(gone)} case(s) that existed at the start of "
                     f"the stage are gone from the suite")
        for path, name in gone[:5]:
            elog("WARN", f"      ⤬ {path} — {name[:70]}")

    if orphaned:
        out["orphaned"] = [t for t, _, _ in orphaned]
    out["clean"] = not failures and not left and not gone

    ephase({"phase": -15, "title": "Running unit tests", "status": "done"})
    if fixer.verdicts:
        elog("INFO", f"   🧪 {fixer.summary()}")
    for s in qa.report.suspects[:5]:
        emit({"type": "test_result", "status": "warn",
              "msg": f"Possible bug in {s['test']}", "detail": s["note"]})
    return out


MAX_E2E_FIX = 15


def _report_unparseable(arch) -> list:
    """
    Generated files with a bracket left open, named out loud.

    Next only compiles what something imports, so a component nothing imports
    is never parsed by anything — not the build, not the browser pass, not a
    test. Measured: `components/FinancialSummary.jsx` shipped with
    `.reduce((sum, r => …, 0)` missing a paren, `npm run build` said "Compiled
    successfully", and the only gate that noticed blamed the TEST file and
    deleted it. Dead code, but dead broken code, written as if it worked.

    The same counting the test author uses, pointed at the app instead.
    """
    from qa_agent.author import UnitTestAuthor as _A

    broken = []
    for rel, body in sorted(arch.files.items()):
        if not rel.endswith((".js", ".jsx")) or rel.startswith("tests/"):
            continue
        try:
            said = _A._unbalanced(_A, body)
        except Exception as e:
            log.debug(f"bracket scan {rel}: {e}")
            continue
        if said:
            broken.append((rel, said))
    if broken:
        elog("WARN", f"   ⚠ {len(broken)} generated file(s) do not parse. "
                     f"Nothing imports them yet, so the build compiles anyway "
                     f"— they are still broken:")
        for rel, said in broken[:6]:
            elog("WARN", f"      ✗ {rel} — {said}")
    return broken


def _remeasure_unit(proj_dir: Path, qa, unit: dict, arch=None) -> dict:
    """
    Run the unit suite once more, on the bytes that are actually shipping.

    Returns the same shape `run_qa_unit_stage` does, with the counts replaced
    by what a fresh run just saw. Anything that stops the run — no tests, no
    runner, a runner that produces no report — leaves the stage's own numbers
    alone and says so, because an unmeasured number is still better than a
    number this function made up.
    """
    unit = dict(unit or {})
    if not unit.get("ran") or not qa or not getattr(qa, "enabled", False):
        return unit
    try:
        runner = VitestRunner(proj_dir, cmd=qa.cmd, callbacks=_qa_callbacks(),
                              session=qa)
        passed, failures, ok = runner.run()
    except Exception as e:
        elog("WARN", f"   ⚠ could not re-check the unit tests at the end: {e}")
        log.exception("final unit re-measure")
        unit["final_check"] = "did not run"
        return unit
    if not ok:
        unit["final_check"] = "did not run"
        return unit

    was_p, was_f = unit.get("passed", 0), unit.get("failed", 0)
    unit.update(passed=passed, failed=len(failures),
                clean=not failures, final_check="measured at the end")
    if qa.report is not None:
        qa.report.passed, qa.report.failures = passed, failures

    if (passed, len(failures)) == (was_p, was_f):
        elog("INFO", f"   ✅ still {passed}/{passed + len(failures)} after every "
                     f"other stage")
        return unit
    if len(failures) > was_f:

        elog("WARN", f"   ⚠ the repairs after the unit stage broke "
                     f"{len(failures) - was_f} more case(s) — {passed} passing, "
                     f"{len(failures)} failing on the code that is shipping "
                     f"(the unit stage ended on {was_p}/{was_f})")
        for f in failures[:6]:
            elog("WARN", f"      ✗ {f.test_file} — {f.name}")
    else:
        elog("INFO", f"   ✅ {passed} passing, {len(failures)} failing on the "
                     f"code that is shipping (the unit stage ended on "
                     f"{was_p}/{was_f})")

    if failures and arch is not None:
        passed, failures = _repair_after_stages(proj_dir, qa, arch, runner,
                                                failures)
        unit.update(passed=passed, failed=len(failures), clean=not failures)
        if qa.report is not None:
            qa.report.passed, qa.report.failures = passed, failures
    return unit


MAX_AFTER_FIX = 2


def _repair_after_stages(proj_dir: Path, qa, arch, runner, failures):
    """
    Bring the tests back in line with the code that shipped.

    Deliberately narrow. The application code these cases now disagree with was
    changed on purpose, by the runtime, end-to-end and security stages, to fix
    faults those stages proved were real — so it is not up for revision here.
    The test is the stale artefact: it describes the version of the route that
    was on disk when it was written.

    Every failure is therefore marked as testing a rewritten target before the
    fixer sees it, which is exactly what `stale` means and puts the right
    sentence in front of the model. Nothing is set aside and nothing is
    skipped: whatever is still red at the end is reported red.
    """
    for f in failures:
        try:
            f.stale = True
        except Exception:
            pass
    fixer = BugFixerAgent(arch, proj_dir, callbacks=_qa_callbacks(), session=qa,
                          model=QASession.model_for(qa, arch))
    for rnd in range(1, MAX_AFTER_FIX + 1):
        groups = _by_test_file(failures)
        ephase({"phase": -16, "title": "Re-aligning tests with the shipped code",
                "status": "active"})
        elog("INFO", f"   🔧 re-aligning {len(groups)} test file(s) with the "
                     f"code the later stages left behind (round {rnd}/"
                     f"{MAX_AFTER_FIX})")

        def repair(group):
            try:
                fixer.fix(group, build_ok=True, round_no=rnd, tier=0)
            except Exception as e:
                elog("WARN", f"   ⚠ re-alignment failed on "
                             f"{group[0].test_file}: {e}")
                log.exception("post-stage fix")

        with ThreadPoolExecutor(max_workers=QA_FIX_WORKERS) as pool:
            list(pool.map(repair, groups))
        ephase({"phase": -16, "title": "Re-aligning tests with the shipped code",
                "status": "done"})

        passed, failures, ok = runner.run()
        if not ok:
            elog("WARN", "   ⚠ the re-run produced no report — keeping the "
                         "last numbers that were measured")
            return passed, failures
        if not failures:
            elog("INFO", f"   ✅ {passed}/{passed} — the suite is green on the "
                         f"code that is shipping")
            return passed, failures
        elog("WARN", f"   ❌ {len(failures)} still failing after round {rnd}")
    _leave_unresolved(runner, failures,
                      "the code changed after these tests were written and "
                      "they could not be brought back into line")
    return passed, failures


def _e2e_detail(failures) -> list:
    """
    What actually failed, in the shape the report already uses for unit cases.

    The stage returned counts and nothing else, so a report could say
    `failed: 1` and hold no record of what the 1 was — not the step, not the
    page, not the message, and not the requests the browser made. That is the
    one failure in the whole pipeline nobody could look up afterwards.
    """
    out = []
    for f in failures or ():
        out.append({
            "case": getattr(f, "name", ""),
            "target": getattr(f, "target", ""),
            "kind": getattr(f, "kind", ""),
            "message": getattr(f, "message", ""),
            "stack": (getattr(f, "stack", "") or "")[:2000],
        })
    return out


def run_qa_e2e_stage(arch, proj_dir: Path, qa, analyzer, *, build_ok: bool,
                     db_ok: bool) -> dict:
    """
    Sign in as a real seeded account and use the app.

    Runs after the tester loop has settled rather than straight after
    `wait_for_next()`: that loop stops and restarts the dev server between
    attempts, so a flow started inside it would be driving a server about to be
    killed.

    The two failure kinds are handled differently on purpose. A selector that
    matched nothing means the scenario was written wrong — one re-author, and
    no application file is ever touched for it. A 500 or an uncaught exception
    means the app is broken, and only those reach the fixer.
    """
    out = {"ran": False, "flow": "", "passed": 0, "failed": 0, "fixed": 0}
    if not qa or not qa.enabled:
        return out
    if not build_ok:
        elog("WARN", "   ⚠ End-to-end flow skipped — the build is not green")
        return out
    if not db_ok:

        elog("WARN", "   ⚠ End-to-end flow skipped — no database")
        return out

    ephase({"phase": -17, "title": "End-to-end flow", "status": "active"})
    agent = E2EAgent(arch, proj_dir, callbacks=_qa_callbacks(), session=qa,
                     analyzer=analyzer, base_url=f"http://localhost:{DEV_PORT}")
    try:
        out.update(_e2e_rounds(agent, arch, proj_dir, qa, analyzer, out))
    except Exception as e:
        elog("WARN", f"   ⚠ End-to-end flow failed: {e}")
        log.exception("qa e2e")
    ephase({"phase": -17, "title": "End-to-end flow", "status": "done"})
    return out


def _e2e_rounds(agent, arch, proj_dir, qa, analyzer, out):

    mark = dev_log_mark()
    sc = agent.author()
    why = sc.is_runnable()
    for _ in range(1):
        if not why:
            break
        elog("WARN", f"   ⚠ the flow was not usable — {why}")
        sc = agent.author(previous=sc, why=why)
        why = sc.is_runnable()
    if why:
        elog("WARN", f"   ⚠ End-to-end flow skipped — {why}")
        return out

    out["flow"] = sc.title
    elog("INFO", f"   🎭 {sc.title}  ({len(sc.steps)} steps)")
    agent.write_spec(sc)
    failures = agent.run(sc)
    out["ran"] = True

    if failures and all(f.kind == KIND_SELECTOR for f in failures):
        elog("WARN", f"   ↻ {failures[0].message[:90]} — rewriting the flow")

        sc2 = agent.author(previous=sc, why=failures[0].message,
                           page=failures[0].target)
        if not sc2.is_runnable():
            agent.write_spec(sc)

            out["failed"] = len(failures)
            out["unwritable"] = len(failures)
            out["failures"] = _e2e_detail(failures)
            return out
        sc = sc2
        agent.write_spec(sc)
        failures = agent.run(sc)

    if not failures:
        elog("INFO", "   ✅ the end-to-end flow passed")
        emit({"type": "test_result", "status": "pass",
              "msg": f"End-to-end: {sc.title}",
              "detail": f"{len(sc.steps)} steps"})
        return out

    out["failed"] = len(failures)
    out["failures"] = _e2e_detail(failures)
    for f in failures[:5]:
        emit({"type": "test_result", "status": "fail",
              "msg": f"End-to-end: {f.name}", "detail": f.message[:200]})

    for rnd in range(1, MAX_E2E_FIX + 1):

        real = list(failures)
        if not real:
            elog("WARN", "   ⚠ the flow did not reach what it was looking for "
                         "— reporting it rather than guessing at a fix")
            break

        ephase({"phase": -18, "title": f"Repairing the app (round {rnd})",
                "status": "active"})
        elog("INFO", f"   🔧 End-to-end repair round {rnd}/{MAX_E2E_FIX} — "
                     f"{len(real)} crash(es)")

        report = "\n\n".join(f"{f.name}\n{f.message}\n{f.stack[:600]}".strip()
                             for f in real[:6])
        trace = _filter_db_noise(dev_log_since(mark), True)

        snap = FileSnapshot(proj_dir)
        snap.capture([p for p in arch.files
                      if p.startswith(("app/", "components/", "lib/"))])
        fixed = _repair_runtime(arch, proj_dir, qa, analyzer, report, trace,
                                rnd, model=QASession.model_for(qa, arch))
        ephase({"phase": -18, "title": f"Repairing the app (round {rnd})",
                "status": "done", "written": len(fixed)})
        if not fixed:
            elog("WARN", "   ⚠ nothing was changed — stopping here")
            break

        _stop_dev_proc()
        built = run_build_fix_loop(arch, proj_dir, True, max_rounds=1)
        if not built:
            elog("WARN", "   ↩ the end-to-end fix broke the build — reverting "
                         "this round")
            snap.restore(fixed)
        else:
            out["fixed"] += len(fixed)
        start_next(proj_dir)
        wait_for_next()
        if not built:
            break

        mark = dev_log_mark()
        failures = agent.run(sc)
        out["failed"] = len(failures)
        out["failures"] = _e2e_detail(failures)
        if not failures:
            elog("INFO", f"   ✅ the end-to-end flow passes after round {rnd}")
            emit({"type": "test_result", "status": "pass",
                  "msg": f"End-to-end: {sc.title}",
                  "detail": f"fixed in {rnd} round(s)"})
            break
        elog("WARN", f"   ⚠ still failing after round {rnd}: "
                     f"{failures[0].message[:90]}")
    else:
        elog("WARN", f"   ⚠ {MAX_E2E_FIX} repair rounds spent — serving as-is")
    return out


def _by_test_file(failures):
    """Group failures by test file — one model call per file, not per case."""
    groups = {}
    for f in failures:
        groups.setdefault(f.test_file, []).append(f)
    return [groups[k] for k in sorted(groups)]


def _emit_qa_results(passed, failures, rnd):
    """One event per case, capped, so the counter in the UI is truthful."""
    if passed:
        emit({"type": "test_result", "status": "pass",
              "msg": f"{passed} unit test(s) passed",
              "detail": f"round {rnd}"})
    for f in failures[:40]:
        emit({"type": "test_result", "status": "fail",
              "msg": f"{f.name}",
              "detail": f"{f.test_file} — {f.message[:200]}"})


def _repair_runtime(arch, proj_dir: Path, qa, analyzer, all_errors: str,
                    dev_errors: str, attempt: int, model: str = None) -> list:
    """
    Plan which files a runtime failure touches, then repair exactly those.

    This stage used to be one `arch.update(all_errors)`: the model choosing the
    files and rewriting them in the same breath, seeing only the architect's
    fixed 18-file snapshot. On a project with forty source files the file a
    stack frame names is regularly not in that snapshot, so the fix landed in
    whatever the model happened to be shown — which is the same reason
    `agents/features.py` exists at all.

    Two agents instead, split the way an edit already is:
    `FeaturesAgent.plan_repair` reads the whole inventory, pulls the bodies it
    asks for and names the files; `BugFixerAgent.fix_runtime` writes them, with
    that plan as the write allowlist and the scope guard behind it.

    The blunt path stays as the fallback. An empty plan while the probe is
    still red means the two disagree, and handing the disagreement to the model
    is a better answer than quietly doing nothing.

    Returns the paths written — the caller snapshots those and restores them if
    the fix turns out not to compile.
    """

    planner = FeaturesAgent(arch, proj_dir, callbacks=_analyzer_callbacks(),
                            analyzer=analyzer, model=model)
    fixer = BugFixerAgent(arch, proj_dir, callbacks=_qa_callbacks(), session=qa,
                          model=model)

    spec = None
    try:
        spec = planner.plan_repair(all_errors, server_log=dev_errors)
    except Exception as e:
        elog("WARN", f"   ⚠ Repair planning failed: {e}")
        log.exception("runtime repair: plan")

    written = []
    if spec and not spec.is_empty():
        elog("INFO", f"   🧭 {spec.summary or 'Repair planned'} "
                     f"— {len(spec.files)} file(s)")
        for pkg in spec.packages:
            elog("INFO", f"   📦 npm install {pkg}")
            try:
                arch.cmd.run(f"npm install {pkg}")
            except Exception as e:
                elog("WARN", f"   ⚠ npm install {pkg} failed: {e}")
        try:
            written = fixer.fix_runtime(all_errors, spec,
                                        server_log=dev_errors, round_no=attempt)
        except Exception as e:
            elog("WARN", f"   ⚠ Runtime repair failed: {e}")
            log.exception("runtime repair: fix")

    if written:
        elog("INFO", f"   ✅ Repaired {len(written)} file(s): "
                     f"{', '.join(written)}")
        return written

    elog("WARN", "   ⚠ Targeted repair changed nothing — falling back to a "
                 "whole-thread fix")
    arch.update(textwrap.dedent(f"""\
        The app builds, but fails at runtime. Fix every error below.

        Rewrite the affected files completely. If the cause is a
        missing package, install it first with
        <run_command>npm install <name></run_command>.

        ```
        {all_errors[:4000]}
        ```
        """))
    return []


def _think_flag(msg: dict):
    """
    The UI's thinking switch, as Ollama's tri-state.

    True and False are both instructions — `false` actively suppresses a
    reasoning model's thinking, which is the whole point of being able to turn
    it off. A request that carries no flag at all leaves the model's own
    default alone, so an older client keeps behaving exactly as it did.
    """
    v = msg.get("think")
    return None if v is None else bool(v)


def _find_fooocus_config() -> str:
    """Where Fooocus keeps its config, looked for rather than assumed.

    This was one absolute path with a drive letter in it, and the install has
    since moved from E: to D: to C:. Each time, the path in the source pointed
    at a drive that was not mounted — harmless, because it is only a fallback
    for reading model paths, but it is also never right for anybody else.

    Only used when `image_host` gives nothing away; the agent finds the running
    Fooocus on its own port regardless. Cheap enough to run at import: a
    handful of `is_file()` calls on paths that mostly do not exist.
    """
    # The two layouts the installer produces, plus the one the zip makes when
    # it is extracted into a folder of its own name.
    inside = ("Fooocus/config.txt", "config.txt", "fooocus_config.json")
    roots = [Path(f"{d}:/") for d in "CDEFG"] + [Path.home()]
    for root in roots:
        try:
            if not root.exists():
                continue
            for folder in sorted(root.glob("Fooocus*")):
                for rel in inside:
                    candidate = folder / rel
                    if candidate.is_file():
                        return str(candidate)
                # …/Fooocus_win64_x/Fooocus_win64_x/Fooocus/config.txt
                nested = folder / folder.name
                for rel in inside:
                    candidate = nested / rel
                    if candidate.is_file():
                        return str(candidate)
        except OSError:
            continue
    return ""


FOOOCUS_CONFIG = _find_fooocus_config()


def image_agent(callbacks: dict = None) -> ImageAgent:
    """The configured Fooocus, whether or not it is switched on."""
    s = load_settings()
    return ImageAgent(host=str(s.get("image_host", "")).strip(),
                      config_path=str(s.get("image_config", FOOOCUS_CONFIG)),
                      callbacks=callbacks or _analyzer_callbacks(),
                      enabled=bool(s.get("image_enabled", False)))


def _image_settings() -> dict:
    s = load_settings()
    return {
        "image_enabled": bool(s.get("image_enabled", False)),
        "image_host": str(s.get("image_host", "")),
        "image_config": str(s.get("image_config", FOOOCUS_CONFIG)),
        "lan_access": bool(s.get("lan_access", False)),
    }


# Measured, not guessed: Next's rewrite refuses a request body over 10 MiB with
# a bare 500 that never reaches this process, so a cap above what the transport
# carries is a promise the endpoint cannot keep. base64 inflates by 4/3, which
# puts the real ceiling near 7.8 MB of file; the rest is room for the filename
# and the other JSON fields.
UPLOAD_IMAGE_MAX = 7_500_000
UPLOAD_IMAGE_SIDE = 2048


def _safe_stem(raw: str, fallback: str = "upload") -> str:
    """A name from the browser, reduced to something that cannot leave the folder.

    Both the picture name and the project name are pasted straight into a path,
    so `../../` in either walks out of `public/generated` and writes wherever it
    likes. Taking the basename first and then keeping only safe characters means
    neither a separator nor a drive letter survives.
    """
    stem = Path(str(raw or "").replace("\\", "/")).name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-.")
    return (Path(stem).stem or fallback)[:60]


def save_uploaded_image(raw_b64: str, out: Path) -> str:
    """Write a browser upload to `out` as a real PNG. Returns "" or the reason.

    Re-encoded rather than saved as it arrived, because the file is copied
    byte-for-byte to `public/logo.png` at build time — a JPEG sitting at a .png
    path is a lie the rest of the pipeline has no reason to expect. Re-encoding
    also settles webp, bmp and animated gif, and is the point at which a corrupt
    upload is caught rather than becoming a broken image in the built app.
    """
    raw = str(raw_b64 or "")
    if raw.lstrip().startswith("data:") and "," in raw[:64]:
        raw = raw.split(",", 1)[1]          # a browser data: URL
    if not raw.strip():
        return "no image was sent"
    try:
        blob = base64.b64decode(raw, validate=False)
    except Exception as e:                                      # noqa: BLE001
        return f"that is not valid base64 ({e})"
    if not blob:
        return "the image was empty"
    if len(blob) > UPLOAD_IMAGE_MAX:
        return f"the image is larger than {UPLOAD_IMAGE_MAX // 1_000_000} MB"

    try:
        from PIL import Image
    except Exception:                                           # noqa: BLE001
        # No Pillow: only a file that is already a PNG can be trusted at a
        # .png path, and passing anything else through would be the lie above.
        if blob[:8] != b"\x89PNG\r\n\x1a\n":
            return "Pillow is not installed, so only PNG files can be uploaded"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(blob)
        return ""

    try:
        img = Image.open(io.BytesIO(blob))
        img.load()
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")
        img.thumbnail((UPLOAD_IMAGE_SIDE, UPLOAD_IMAGE_SIDE))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
    except Exception as e:                                      # noqa: BLE001
        return f"that file could not be read as an image ({e})"

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(buf.getvalue())
    return ""


IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
AUDIO_EXT = (".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac")
ATTACH_TEXT_CAP = 6000


def read_attachment(filename: str, data_b64: str, proj_dir: Path = None) -> dict:
    """Turn one attached file into something an editing prompt can carry.

    The three editing tools all take a single instruction string and hand it to
    a model, so the cheapest way to let somebody attach a document to one of
    them is to make the attachment *part of that string*. No edit path changes,
    no new websocket message, and the three tools cannot drift apart.

    A picture is the one case with two possible meanings — "put this on the
    page" and "make it look like this" — and guessing is worse than serving
    both: the file is saved into the project where an `<img>` can point at it,
    AND it is read, so the description goes into the prompt. Which one the user
    meant is in their own words, where the model can see it.

    The readers are the SRS agent's, already installed and already exercised by
    the intake: text layer first for a PDF and the vision model for the pages it
    cannot reach, faster-whisper for audio.
    """
    name = str(filename or "upload")
    lower = name.lower()
    out = {"kind": "file", "text": "", "url": "", "note": ""}

    try:
        if lower.endswith(IMAGE_EXT):
            out["kind"] = "image"
            stem = _safe_stem(name, "attached")
            where = ((proj_dir / "public" / "generated") if proj_dir
                     else (LOGS_DIR / "images")) / f"{stem}.png"
            why = save_uploaded_image(data_b64, where)
            if why:
                out["note"] = why
                return out
            out["url"] = f"/generated/{stem}.png"

            from srs_agent.app.extraction import read_image
            res = asyncio.run(read_image(base64.b64decode(_strip_data_url(data_b64)), name))
            out["text"] = (res.get("text") or "").strip()
            out["note"] = res.get("warning") or res.get("error") or ""
            return out

        raw = base64.b64decode(_strip_data_url(data_b64))

        if lower.endswith(".pdf"):
            out["kind"] = "pdf"
            from srs_agent.app.extraction import read_pdf
            res = asyncio.run(read_pdf(raw, name))
        elif lower.endswith(AUDIO_EXT):
            out["kind"] = "audio"
            from srs_agent.app.extraction import transcribe_audio
            res = transcribe_audio(raw, name)
        else:
            out["kind"] = "text"
            res = {"text": raw.decode("utf-8", "ignore")}

        out["text"] = (res.get("text") or "").strip()
        out["note"] = res.get("warning") or res.get("error") or ""
    except Exception as e:                                      # noqa: BLE001
        log.warning(f"attachment {name}: {e}")
        out["note"] = f"{name} could not be read ({e})"
    return out


def _strip_data_url(raw: str) -> str:
    raw = str(raw or "")
    if raw.lstrip().startswith("data:") and "," in raw[:64]:
        return raw.split(",", 1)[1]
    return raw


INLINE_BUDGET = 6_000_000
PREVIEW_SIDE = 900


def preview_uri(out: Path) -> str:
    """A data: URI for `out`, shrinking it rather than giving up when it is big.

    The caller shows this as the picture; there is no second source to fall back
    on, so returning "" means the screen says nothing was produced while every
    other field says something was. That branch used to be unreachable — Fooocus
    caps its aspects at about a megapixel, so a generated PNG never approached
    the budget — and an upload at 2048² makes it live: a photograph re-encodes
    to seven to nine megabytes whatever size the JPEG that carried it was.

    So the budget now governs how the preview is made, not whether there is one.
    The file on disk is untouched; it is the full-resolution picture the build
    copies. Only the copy travelling to the browser is scaled.
    """
    try:
        raw = out.read_bytes()
    except OSError as e:
        log.debug(f"inline {out}: {e}")
        return ""

    if len(raw) <= INLINE_BUDGET:
        return "data:image/png;base64," + base64.b64encode(raw).decode()

    try:
        from PIL import Image

        img = Image.open(io.BytesIO(raw))
        img.load()
        img.thumbnail((PREVIEW_SIDE, PREVIEW_SIDE))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
    except Exception as e:                                      # noqa: BLE001
        log.debug(f"preview {out}: {e}")
        return ""
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def run_image_stage(arch, proj_dir: Path) -> int:
    """
    Generate the pictures the plan asked for, into the project's public folder.

    Runs after the files are written and before the build check, for two
    reasons: the markup already references `/generated/<key>.png`, so the paths
    are settled; and a missing image is not a compile error, so nothing
    downstream has to wait on the GPU to find out whether the app builds.

    Every failure here is survivable. An app with a broken <img> is worth
    shipping; a build that died because a GPU was busy is not.
    """
    plan_images = (arch.plan or {}).get("images") or []
    if not plan_images:
        return 0
    agent = image_agent()
    if not agent.enabled:
        elog("INFO", f"   🖼 {len(plan_images)} image(s) planned — image "
                     f"generation is off, so the app ships with the tags in "
                     f"place and the files missing")
        return 0
    if not agent.available():
        elog("WARN", "   ⚠ No Fooocus is answering — the planned images are "
                     "skipped. Start it, or set its address in Settings.")
        return 0

    ephase({"phase": -21, "title": f"Generating {len(plan_images)} image(s)",
            "status": "active"})
    out_dir = proj_dir / "public" / "generated"
    made = 0
    for n, im in enumerate(plan_images, start=1):
        eprog(f"Image {n}/{len(plan_images)}…", 78)
        if agent.generate(im["prompt"], out_dir / f"{im['key']}.png",
                          aspect=im.get("aspect", "landscape")):
            made += 1
    ephase({"phase": -21, "title": f"Generating {len(plan_images)} image(s)",
            "status": "done", "written": made})
    elog("INFO" if made else "WARN",
         f"   🎨 {made}/{len(plan_images)} image(s) generated")
    return made


_GEN_IMG_RE = re.compile(r"/generated/([A-Za-z0-9._-]+)\.(?:png|jpg|jpeg|webp)")


_GEN_IMG_TPL_RE = re.compile(
    r"/generated/\$\{([^}]{1,80})\}\.(?:png|jpg|jpeg|webp)")


_SEED_LABEL_RE = re.compile(r"\b(?:name|title|label)\s*:\s*['\"]([^'\"]{1,80})['\"]")


def _seeded_values(arch, field: str) -> dict:
    """
    `{value: label}` for every literal `field: '…'` in the project's seed.

    The label is the `name`/`title`/`label` in the SAME object literal, found
    by walking out to the braces either side rather than by parsing
    JavaScript.

    The braces are the whole point. A fixed-size window around the match
    reaches back into the object before it, and `search` returns the first
    match it finds there — so every row was paired with its predecessor's
    name: `snake-plant` came back labelled "Fiddle Leaf Fig", and five plants
    would have been drawn as the wrong species. An empty label is harmless
    (the filename is used instead); a confidently wrong one is not.
    """
    field_re = re.compile(r"\b" + re.escape(field) + r"\s*:\s*['\"]([^'\"]{1,80})['\"]")
    out = {}
    for rel, body in arch.files.items():
        if "seed" not in rel.lower() or not rel.endswith(".js"):
            continue
        for m in field_re.finditer(body):
            value = m.group(1).strip()
            if not value or "/" in value:
                continue
            open_at = body.rfind("{", 0, m.start())
            close_at = body.find("}", m.end())
            span = body[(open_at + 1 if open_at != -1 else 0):
                        (close_at if close_at != -1 else len(body))]
            label = _SEED_LABEL_RE.search(span)
            out.setdefault(value, label.group(1).strip() if label else "")
    return out


_IMG_TAG_RE = re.compile(
    r"<(?:Image|img)\b[^>]*?>", re.S | re.I)
_ALT_RE = re.compile(r"""\balt\s*=\s*["'{]\s*([^"'}]{3,120})""")

IMAGE_STYLE = ("photographic, natural light, shallow depth of field, "
               "no text, no watermark, no people looking at the camera")


def _fill_missing_images(arch, proj_dir: Path, why: str = "an edit") -> int:
    """
    Draw any picture the app now asks for and does not have.

    An edit that adds a section usually adds a picture with it — the model
    writes `<img src="/generated/spa-suite.png" alt="a hotel spa suite" />`
    because that is what the markup needs, and then nothing draws it, so the
    page ships with a broken image. The build has an image stage, but it only
    reads `plan.images`, which is written once before any edit exists.

    So: after an edit, look at what the source references, compare it with
    what is on disk, and generate the difference. The alt text is the prompt —
    it is already a description of the picture, written by the model that
    decided the picture belonged there.

    Never fatal. An app with one missing image is worth serving; a failed edit
    because a GPU was busy is not.
    """
    wanted = {}
    for rel, body in arch.files.items():
        if not rel.endswith((".jsx", ".js", ".css")):
            continue
        for tag in _IMG_TAG_RE.findall(body):
            names = _GEN_IMG_RE.findall(tag)
            if not names:
                continue
            alt = _ALT_RE.search(tag)
            for name in names:
                wanted.setdefault(name, (alt.group(1).strip() if alt else "",
                                         rel))

        for name in _GEN_IMG_RE.findall(body):
            wanted.setdefault(name, ("", rel))

        for expr in _GEN_IMG_TPL_RE.findall(body):
            field = expr.strip().split(".")[-1].strip()
            if not field.isidentifier():
                continue
            rows = _seeded_values(arch, field)
            if not rows:

                elog("WARN", f"   🖼 {rel} builds its image path from "
                             f"`{expr.strip()}` and no seeded `{field}` values "
                             f"were found — those pictures cannot be drawn and "
                             f"the page will 404 on every one")
                continue
            for value, label in rows.items():
                wanted.setdefault(value, (label, rel))

    out_dir = proj_dir / "public" / "generated"
    missing = {n: v for n, v in wanted.items()
               if not (out_dir / f"{n}.png").is_file()}
    if not missing:
        return 0

    agent = image_agent()
    if not agent.enabled or not agent.available():
        elog("WARN", f"   🖼 {len(missing)} picture(s) {why} added are not "
                     f"drawn — image generation is off or no Fooocus is "
                     f"answering: {', '.join(sorted(missing))}")
        return 0

    idea = (arch.plan or {}).get("description") or (arch.plan or {}).get("title") or ""
    made = 0
    ephase({"phase": -21, "title": f"Drawing {len(missing)} picture(s)",
            "status": "active"})
    for name, (alt, rel) in sorted(missing.items()):

        subject = alt or name.replace("-", " ").replace("_", " ")
        prompt = f"{subject}, {IMAGE_STYLE}"
        if idea:
            prompt = f"{subject}, for {idea[:80]}, {IMAGE_STYLE}"
        elog("INFO", f"   🎨 {name}.png — {subject[:70]}")
        try:
            if agent.generate(prompt, out_dir / f"{name}.png",
                              aspect="landscape"):
                made += 1
            else:
                elog("WARN", f"   ⚠ {name}.png could not be drawn")
        except Exception as e:
            elog("WARN", f"   ⚠ {name}.png failed: {e}")
            log.debug(f"fill image {name}", exc_info=True)
    ephase({"phase": -21, "title": f"Drawing {len(missing)} picture(s)",
            "status": "done", "written": made})
    elog("INFO" if made else "WARN",
         f"   🖼 {made}/{len(missing)} picture(s) drawn for {why}")
    return made


def check_seed_duplicates(proj_dir: Path) -> list:
    """
    Rows the seed wrote more than once, counted in the live database.

    `ensureSeeded()` runs on a cold start, so it runs again on every dev-server
    restart, and whether that is harmless depends entirely on whether the seed
    is idempotent. Two static attempts at deciding that from `lib/seed.js` were
    both wrong — the first reported thirty-one of forty-two projects including
    ones upserting on `{ email }`, the second missed six that were genuinely
    duplicating and flagged four that were not. The causes are too varied to
    read off the source: no guard, an unstable key, a key that is not unique,
    a seed that races itself.

    Counting is not a guess. A clinic seeded five pets and six appointments and
    the collection held eighty-four; a shop seeded a handful of reviews and
    held seventy-six. Whatever the reason, that is the bug the user sees — the
    same dog fourteen times on the ward board.
    """
    try:
        from pymongo import MongoClient
    except ImportError:
        return []
    name = proj_dir.name
    try:
        db = MongoClient(MONGO.uri_for(name),
                         serverSelectionTimeoutMS=5000)[db_name_for(name)]
        collections = [c for c in db.list_collection_names()
                       if c not in ("user", "session", "account",
                                    "verification", "jwks")]
    except Exception as e:
        log.debug(f"seed duplicate check: {e}")
        return []

    out = []
    for coll in collections:
        try:

            sample = db[coll].find_one()
            if not sample:
                continue
            keys = [k for k in sample
                    if k not in ("_id", "createdAt", "updatedAt", "date")]
            if not keys:
                continue
            dupes = list(db[coll].aggregate([
                {"$group": {"_id": {k: f"${k}" for k in keys},
                            "n": {"$sum": 1}}},
                {"$match": {"n": {"$gt": 1}}},
                {"$sort": {"n": -1}},
                {"$limit": 3},
            ], maxTimeMS=8000))
        except Exception as e:
            log.debug(f"seed duplicates in {coll}: {e}")
            continue
        if dupes:
            worst = dupes[0]["n"]
            total = db[coll].count_documents({})
            out.append(f"{coll}: {total} row(s), and the seed's data is "
                       f"repeated up to {worst} times — every restart writes "
                       f"it again")
    return out


def run_security_stage(arch, proj_dir: Path, analyzer) -> tuple:
    """
    Ask whether the app is safe to put in front of people, and fix what is not.

    Every other gate asks whether it WORKS. This one is the only thing between
    a generated app and an open `PATCH /api/orders/[id]` that lets a stranger
    mark anybody's order collected — which compiles, renders, passes its tests
    and answers its route probe.

    Blockers and majors go to `analyzer.repair`, the same call the route-error
    path uses, because a described flaw and a fixed one are not the same
    deliverable. Minors are reported and left.
    """
    from agents.security import SecurityAgent

    ephase({"phase": -22, "title": "Security check", "status": "active"})
    agent = SecurityAgent(proj_dir, callbacks=_analyzer_callbacks(),
                          cmd=getattr(arch, "cmd", None))
    findings, counts = agent.run()

    if counts:
        worst = ", ".join(f"{n} {sev}" for sev, n in counts.items())
        bad = counts.get("critical", 0) + counts.get("high", 0)
        elog("WARN" if bad else "INFO",
             f"   🔐 npm audit: {worst}")
        emit({"type": "test_result",
              "status": "fail" if bad else "warn",
              "msg": "Dependencies", "detail": worst})
    else:
        emit({"type": "test_result", "status": "pass",
              "msg": "Dependencies", "detail": "no known advisories"})

    for dupe in check_seed_duplicates(proj_dir):
        elog("WARN", f"   🌱 {dupe}")
        emit({"type": "test_result", "status": "warn", "msg": "Seed data",
              "detail": dupe[:160]})

    if not findings:
        elog("INFO", "   🔐 No security problems found in the generated code")
        emit({"type": "test_result", "status": "pass", "msg": "Security",
              "detail": "nothing found"})
        ephase({"phase": -22, "title": "Security check", "status": "done"})

        return [], counts

    for f in findings:
        elog("WARN", f"   🔐 [{f.severity}] {f.path}: {f.message[:110]}")
        emit({"type": "test_result", "status": "fail", "msg": f"Security: {f.code}",
              "detail": f"{f.path} — {f.message[:160]}"})

    serious = [f for f in findings if f.severity in ("blocker", "major")]
    written = 0
    if serious:
        elog("INFO", f"   🔧 Repairing {len(serious)} security finding(s)")

        snap = FileSnapshot(proj_dir)
        snap.capture([p for p in arch.files
                      if p.startswith(("app/", "components/", "lib/"))])
        report = AnalyzerReport()
        report.findings = serious
        report.missing = []
        try:
            written = analyzer.repair(report) or 0
        except Exception as e:
            elog("WARN", f"   ⚠ Security repair failed: {e}")
            log.exception("security repair")
        if written:

            _stop_dev_proc()

            arch.repair_missing_imports()
            if not run_build_fix_loop(arch, proj_dir, MONGO.available,
                                      max_rounds=1):

                elog("WARN", "   ↩ the security fix broke the build — "
                             "reverting it, and the finding stands")
                snap.restore(written)
                written = 0
                run_build_fix_loop(arch, proj_dir, MONGO.available,
                                   max_rounds=1)
            start_next(proj_dir)
            wait_for_next()
            still, _ = agent.run()
            gone = len(findings) - len(still)
            elog("INFO" if gone else "WARN",
                 f"   🔐 {gone} of {len(findings)} finding(s) closed")

            findings = still

    ephase({"phase": -22, "title": "Security check", "status": "done",
            "written": written})
    return findings, counts


IMAGE_PROMPT_SYSTEM = """\
You turn a few words from someone looking at a web page into a prompt for an
image generator. Reply with the prompt and nothing else — no preamble, no
quotation marks, no explanation, one line, under about thirty words.

You are given what the picture is now and what they asked for instead. What
they asked for wins; the old description is only there for what they did not
mention — the same room, the same product, the same time of day, unless they
said otherwise.

Name the subject, then the setting, then the light, then the style:

    a corner reading nook with a worn leather armchair, tall bookshelves
    behind, late afternoon light through a sash window, photographic, shallow
    depth of field

What ruins it, every time:
  • text of any kind — generators cannot spell, and a sign or a label comes
    back as nonsense. Never ask for words, logos, signage or a menu board.
  • naming the website instead of the picture: "a hero image for a hotel
    booking site" produces a screenshot of a website, not a hotel
  • crowds and faces — one person at most, and never looking at the camera
  • "4k, ultra detailed, trending on artstation" and the rest of that list;
    they do nothing here
"""

LOGO_PROMPT_SYSTEM = """\
You turn a description of an app into a prompt for an image generator that will
draw its LOGO. Reply with the prompt and nothing else — no preamble, no
quotation marks, no explanation, one line.

A logo is a MARK, not a scene. Name the object, the style, the colours and the
background, in that order, and keep it under about twenty-five words:

    a minimal line-art coffee bean, deep green on white, flat vector, centred,
    plenty of white space

What ruins it, every time:
  • describing the business instead of the mark — "a shop where visitors browse
    beans and staff sign in" produces a photograph of a shop
  • people, hands, storefronts, interiors, or anything with depth of field
  • text or lettering — generators cannot spell, and a logo with mangled words
    is unusable
  • "logo design", "brand identity", "mockup" — those return a presentation
    board with six variations on it

Pick ONE object that stands for the business, one or two colours that suit it,
and say it plainly.
"""


LIGHTHOUSE = "lighthouse@12"


def run_perf_stage(proj_dir: Path) -> dict:
    """
    Lighthouse against the running app, reported and never blocking.

    A slow page is a judgement call, not a defect. A build that refuses to
    finish over a performance score would be a build that refuses to finish
    over a hero image somebody may well have wanted, so this stage says what it
    measured and gets out of the way.

    Driven through the Chromium Playwright has already downloaded — the tester
    and the e2e pass both use it — so there is no second browser to install.
    """
    ephase({"phase": -23, "title": "Performance", "status": "active"})
    chrome = _playwright_chromium()
    if not chrome:
        elog("INFO", "   ⚡ No Chromium available — the performance check is "
                     "skipped")
        ephase({"phase": -23, "title": "Performance", "status": "done"})
        return {}

    out = proj_dir / ".agentforge" / "lighthouse.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = CommandRunner(proj_dir, npm_bin=NPM_BIN, node_bin=NODE_BIN,
                        on_log=lambda lvl, txt: elog(lvl, txt), max_calls=6)
    env_was = os.environ.get("CHROME_PATH")
    os.environ["CHROME_PATH"] = chrome
    try:

        rel = out.relative_to(proj_dir).as_posix()

        res = cmd.run(
            f"npx --yes {LIGHTHOUSE} http://127.0.0.1:{DEV_PORT} "
            f"--output=json --output-path={rel} --quiet "
            f'--chrome-flags="--headless=new --no-sandbox"',
            timeout=300)
    finally:
        if env_was is None:
            os.environ.pop("CHROME_PATH", None)
        else:
            os.environ["CHROME_PATH"] = env_was

    if not out.is_file():
        elog("WARN", "   ⚠ Lighthouse produced no report — the performance "
                     "check is skipped")
        log.debug(f"lighthouse: {(res.output or '')[-400:]}")
        ephase({"phase": -23, "title": "Performance", "status": "done"})
        return {}

    try:
        data = json.loads(out.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        elog("WARN", f"   ⚠ Could not read the Lighthouse report: {e}")
        ephase({"phase": -23, "title": "Performance", "status": "done"})
        return {}

    err = data.get("runtimeError") or {}
    if err.get("code"):
        elog("WARN", f"   ⚠ Lighthouse could not measure the app: "
                     f"{err.get('code')} — "
                     f"{str(err.get('message', ''))[:120]}")
        ephase({"phase": -23, "title": "Performance", "status": "done"})
        return {}

    scores, cats = {}, data.get("categories") or {}
    for key in ("performance", "accessibility", "best-practices", "seo"):
        raw = (cats.get(key) or {}).get("score")
        if raw is None:
            continue
        pct = int(round(raw * 100))
        scores[key] = pct
        emit({"type": "test_result",
              "status": "pass" if pct >= 90 else ("warn" if pct >= 50 else "fail"),
              "msg": f"Lighthouse: {key.replace('-', ' ')}", "detail": f"{pct}/100"})

    audits = data.get("audits") or {}
    metrics = " · ".join(
        f"{name} {(audits.get(key) or {}).get('displayValue', '?')}"
        for name, key in (("LCP", "largest-contentful-paint"),
                          ("CLS", "cumulative-layout-shift"),
                          ("TBT", "total-blocking-time"))
        if audits.get(key))
    elog("INFO", "   ⚡ " + " · ".join(f"{k.replace('-', ' ')} {v}"
                                       for k, v in scores.items()))
    if metrics:
        elog("INFO", f"   ⚡ {metrics}")

    scores["measured_on"] = "next dev — not a production build"
    elog("INFO", "   ⚡ measured against `next dev`: routes compile on first "
                 "request and the JavaScript is unminified, so these are not "
                 "the numbers the built app would give")

    ephase({"phase": -23, "title": "Performance", "status": "done"})
    return scores


def _playwright_chromium() -> str:
    """The Chromium Playwright installed, or "" — Lighthouse needs a browser."""
    root = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    if not root.is_dir():
        return ""

    for d in sorted(root.glob("chromium-*"), reverse=True):
        for sub, exe in (("chrome-win64", "chrome.exe"),
                         ("chrome-win", "chrome.exe"),
                         ("chrome-linux", "chrome"),
                         ("chrome-mac", "Chromium.app/Contents/MacOS/Chromium")):
            p = d / sub / exe
            if p.is_file():
                return str(p)
    return ""


def bind_host() -> str:
    """
    The address the servers listen on.

    Loopback by default, because AgentForge's HTTP surface can start builds, edit
    files and run npm — none of which belongs on an open port by accident.
    `lan_access` widens it to the whole network, which is what makes the image
    endpoint reachable from the other workstation: a second machine running
    AgentForge can then borrow this one's GPU through /api/image.
    """
    return "0.0.0.0" if load_settings().get("lan_access") else "127.0.0.1"


def db_ok() -> bool:
    """Is MongoDB usable right now? Cheap, and false rather than raising."""
    try:
        return bool(MONGO.available)
    except Exception:
        return False


ROUTER_SYSTEM = """\
You are reading one message a user typed about an app they are looking at, and
deciding which tool should handle it. You are NOT fixing anything.

Answer with ONE line and nothing else:

INTENT :: bug :: <one sentence naming what is broken>
INTENT :: feature :: <one sentence naming what to add>
INTENT :: page :: <one sentence naming what should change on this page>
INTENT :: ask :: <the question they are asking>

How to choose:

  • bug — something is broken, erroring, blank, missing, wrong, or not doing
    what it should. "the login does nothing", "this page is white", "prices
    show as NaN", "it crashes when I click save".
  • feature — they want something the app does not do yet. "add reviews",
    "let staff export a CSV", "I need a search box", "make an admin page".
  • page — a change to how the page they are ON looks or reads: layout,
    spacing, wording, colour, order, adding or removing a section. "make this
    two columns", "the heading should say Built With", "move the form up".
  • ask — a question about the app rather than a request to change it. "where
    is the seed data", "what are the demo logins", "how does auth work".

When it could be two, prefer in this order: bug, then page, then feature. A
report that something looks wrong is a bug before it is a restyle, and a
restyle of the current page is cheaper and safer than a feature.
"""

INTENT_RE = re.compile(r"^\s*INTENT\s*::\s*(bug|feature|page|ask)"
                       r"\s*(?:::\s*(.*))?$", re.I | re.M)


def classify_intent(arch, text: str, route: str = "") -> tuple:
    """
    `(intent, restated)` for one message the user typed.

    One small model call, on the build model, with nothing but the message and
    the page they are on. It is deliberately not given the source: deciding
    "is this a complaint or a request" needs the sentence, not the project, and
    a router that reads 48k tokens to answer a four-word question is a router
    nobody will leave switched on.

    Falls back to `feature` — the most conservative route, because it plans
    before it writes and shows its plan.
    """
    user = (f"The user is looking at {route or 'the app'}.\n\n"
            f"They typed:\n{text}\n\nAnswer with the INTENT line.")
    buf = []
    try:
        arch._stream([{"role": "system", "content": ROUTER_SYSTEM},
                      {"role": "user", "content": user}],
                     buf.append, temperature=0.0, timeout=60)
    except Exception as e:
        log.warning(f"intent router failed: {e}")
        return "feature", text
    m = INTENT_RE.search("".join(buf))
    if not m:
        return "feature", text
    return m.group(1).lower(), (m.group(2) or text).strip()


def run_chat(proj_name: str, text: str, model: str, route: str = "",
             think: bool = None, qa_model: str = ""):
    """
    One input for everything: read what the user wants, then do it.

    AgentForge's tools each solve a different shape of problem and each has its own
    tab, which asks the user to classify their own request before they are
    allowed to make it. Nobody thinks "this is a page-scoped restyle" — they
    think "this bit looks wrong". So the classification happens here instead,
    and the tabs become an implementation detail.
    """
    set_tester_emit(emit)
    proj_dir = PROD_DIR / proj_name
    if not proj_dir.is_dir():
        return eerr(f"Project not found: {proj_name}")
    if not ensure_model(model):
        return eerr(f"Cannot load model: {model}")

    arch = ArchitectAgent(ollama, model, proj_dir, _agent_callbacks(proj_dir),
                          stack=detect_stack(proj_dir), think=think)
    intent, restated = classify_intent(arch, text, route)
    elog("INFO", f"💬 {intent} — {restated[:80]}")
    emit({"type": "chat_intent", "intent": intent, "summary": restated})

    if intent == "ask":
        return run_question(arch, proj_dir, text)
    if intent == "bug":
        return run_bug_report(proj_name, restated, model, route, think, qa_model)
    if intent == "page" and route:
        return run_page_update(proj_name, restated, model, route, think)

    return run_feature(proj_name, restated, model, think, qa_model)


def run_bug_report(proj_name: str, complaint: str, model: str, route: str = "",
                   think: bool = None, qa_model: str = ""):
    """
    Repair something the user says is broken.

    The user's sentence is evidence, not a diagnosis — so it is handed to the
    repair path alongside what the dev server actually printed while the page
    was being loaded. "The login does nothing" plus a stack trace naming
    `app/api/auth` is a fixable report; either alone is a guess.
    """
    set_tester_emit(emit)
    try:
        proj_dir, arch, stack = _open_for_edit(proj_name, model, think)
        if arch is None:
            return
        analyzer = AnalyzerAgent(arch, proj_dir,
                                 base_url=f"http://localhost:{DEV_PORT}",
                                 callbacks=_analyzer_callbacks())
        elog("INFO", f"🐛 {complaint[:80]}")
        eprog("Reproducing…", 20)

        if not _dev_alive():
            elog("INFO", "   ▶ Starting the dev server to reproduce it")
            start_dev_server(proj_dir, stack)
            wait_for_dev(stack)

        mark = dev_log_mark()
        if route and _dev_alive():
            try:
                import urllib.request

                urllib.request.urlopen(f"http://127.0.0.1:{DEV_PORT}{route}",
                                       timeout=45).read(1)
            except Exception as e:
                log.debug(f"reproduce {route}: {e}")
        trace = _filter_db_noise(dev_log_since(mark), True)
        faults = terminal_faults(trace)

        report = (f"The user reports: {complaint}\n\n"
                  f"They were on {route or 'the app'}.")
        if faults:
            report += (f"\n\nThe dev server printed this while that page "
                       f"was loading:\n" + f"\n".join(faults[:4]))
            elog("INFO", f"   📋 {len(faults)} matching server error(s)")
        else:
            elog("INFO", "   📋 The server logged nothing — going on the "
                         "report alone")

        eprog("Repairing…", 45)

        fixed = _repair_runtime(arch, proj_dir, None, analyzer, report,
                                trace, 1)
        if not fixed:
            eerr("Nothing was changed — the report did not point at a defect "
                 "this could find")
            return
        elog("INFO", f"   ✅ {len(fixed)} file(s) changed")
        arch.save_convo()

        eprog("Checking…", 80)
        _fill_missing_images(arch, proj_dir)
        verify_after_edit(arch, proj_dir, proj_name, stack=stack,
                          build_rounds=0, probe=False, analyzer=analyzer)
        _autofix_from_terminal(arch, fixed[0], {"route": route}, mark,
                               proj_dir=proj_dir, analyzer=analyzer, model=model)
        eprog("Done!", 100)
        edone(f"http://localhost:{DEV_PORT}", proj_name,
              preview=_route_of({"route": route}))
    except Exception as e:
        eerr(f"Bug fix error: {e}")
        log.exception("run_bug_report")
    finally:
        stop_model(model)


def run_question(arch, proj_dir: Path, question: str):
    """
    Answer a question about the app without touching it.

    Reads the whole project, because "where does the login go" is answerable
    from the source and not from a summary of it. Writes nothing — the one
    branch of the chat that cannot change the app.
    """
    try:
        analyzer = AnalyzerAgent(arch, proj_dir,
                                 callbacks=_analyzer_callbacks())
        agent = FeaturesAgent(arch, proj_dir, callbacks=_analyzer_callbacks(),
                              analyzer=analyzer)
        convo = [
            {"role": "system", "content":
                "You are answering a question about a Next.js app you can see "
                "in full. Answer in two or three sentences, naming the exact "
                "files and values involved. Do not write code unless a two "
                "line snippet is the clearest answer. Do not suggest changes "
                "unless asked."},
            {"role": "user", "content":
                f"## The project\n{agent.full_source()}\n\n"
                f"## The question\n{question}"},
        ]
        buf = []
        arch._stream(convo, buf.append, temperature=0.2, timeout=120)
        answer = "".join(buf).strip() or "I could not work that out."
        echat(answer)
        elog("INFO", "   💬 answered")
    except Exception as e:
        eerr(f"Could not answer: {e}")
        log.exception("run_question")


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def verify_after_edit(arch, proj_dir: Path, proj_name: str, *,
                      stack: str = "next", build_rounds: int = 2,
                      probe: bool = True, analyzer=None) -> dict:
    """
    Everything that has to be true after a tool edits a project.

    `run_agent_update` shipped whatever the model wrote and restarted the dev
    server: no compile check, no request to any route. Every tool that edits an
    existing app funnels through here instead, so "the model said it changed
    three files" and "the app still works" stop being the same claim.

    Returns {'build_ok', 'routes_failed', 'broken_imports', 'syntax_broken'}.
    """
    out = {"build_ok": True, "routes_failed": [], "broken_imports": 0,
           "syntax_broken": []}
    if stack != "next":

        start_dev_server(proj_dir, stack)
        wait_for_dev(stack)
        return out

    analyzer = analyzer or AnalyzerAgent(
        arch, proj_dir, base_url=f"http://localhost:{DEV_PORT}",
        callbacks=_analyzer_callbacks())

    compiling = bool(build_rounds) and not _truthy("LOCODE_SKIP_BUILD_CHECK")

    if compiling:

        _stop_dev_proc()
        ensure_node_deps(proj_dir)

    problems, why_not = check_syntax(proj_dir, arch.files)
    if why_not:

        elog("INFO", f"   ⚠ Syntax not checked — {why_not}")
    elif problems:
        elog("WARN", f"🧩 {len(problems)} file(s) do not parse — repairing")
        ephase({"phase": -6, "title": "Fixing broken syntax", "status": "active"})
        report = AnalyzerReport()
        report.findings = [
            Finding(severity="blocker", code="SYNTAX_ERROR", path=p["path"],
                    message=msg)
            for p, msg in zip(problems, syntax_messages(problems))
        ]
        for line in syntax_messages(problems):
            elog("WARN", f"   ✗ {line}")
        try:
            analyzer.repair(report)
        except Exception as e:
            elog("WARN", f"   ⚠ Syntax repair failed: {e}")
            log.exception("verify_after_edit: syntax repair")
        still, _ = check_syntax(proj_dir, arch.files)
        elog("INFO" if not still else "WARN",
             "   ✅ Every file parses" if not still
             else f"   ⚠ {len(still)} still unparseable")
        out["syntax_broken"] = [p["path"] for p in still]
        ephase({"phase": -6, "title": "Fixing broken syntax", "status": "done"})

    broken = check_named_imports(arch.files)
    out["broken_imports"] = len(broken)
    if broken:
        elog("WARN", f"🔗 {len(broken)} import(s) name something the target "
                     f"module does not export")
        ephase({"phase": -7, "title": "Fixing broken imports", "status": "active"})
        report = AnalyzerReport()
        report.findings = analyzer.broken_imports()
        try:
            analyzer.repair(report)
        except Exception as e:
            elog("WARN", f"   ⚠ Import repair failed: {e}")
            log.exception("verify_after_edit: import repair")
        still = check_named_imports(arch.files)
        out["broken_imports"] = len(still)
        elog("INFO" if not still else "WARN",
             "   ✅ Every import resolves" if not still
             else f"   ⚠ {len(still)} still unresolved")
        ephase({"phase": -7, "title": "Fixing broken imports", "status": "done"})

    if compiling:
        out["build_ok"] = run_build_fix_loop(arch, proj_dir, MONGO.available,
                                             max_rounds=build_rounds)
        if not out["build_ok"]:
            estep("build", "error")
        start_dev_server(proj_dir, stack)
    elif not _dev_alive():

        start_dev_server(proj_dir, stack)

    if not wait_for_dev(stack):
        elog("WARN", "   ⚠ Dev server did not come up — skipping the route probe")
        return out

    if probe:
        report = analyzer.scan()
        mark = dev_log_mark()
        analyzer.probe_routes(report)
        failed = [f for f in report.findings if f.code == "ROUTE_ERROR"]
        if failed:
            elog("WARN", f"   ❌ {len(failed)} route(s) failing — repairing")
            ephase({"phase": -8, "title": "Fixing failing routes", "status": "active"})
            report.findings = failed
            report.missing = []

            trace = _filter_db_noise(dev_log_since(mark), True)
            try:
                analyzer.repair(report, server_log=trace)
            except Exception as e:
                elog("WARN", f"   ⚠ Route repair failed: {e}")
                log.exception("verify_after_edit: route repair")
            ephase({"phase": -8, "title": "Fixing failing routes", "status": "done"})

            _stop_dev_proc()
            ensure_node_deps(proj_dir)
            start_dev_server(proj_dir, stack)
            if wait_for_dev(stack):
                again = analyzer.scan()
                analyzer.probe_routes(again)
                failed = [f for f in again.findings if f.code == "ROUTE_ERROR"]
        out["routes_failed"] = [f.message for f in failed]

    return out


_WATCHED_PKGS = ("agents", "qa_agent")


def _own_sources():
    for pkg in _WATCHED_PKGS:
        for p in (BASE_DIR / pkg).glob("*.py"):
            if p.is_file():
                yield f"{pkg}/{p.name}", p


_AGENT_MTIMES = {rel: p.stat().st_mtime for rel, p in _own_sources()}


def warn_if_agents_stale():
    """
    Say so when AgentForge's own code has changed since this process started.

    Python does not reload an imported module, so editing `agents/architect.py`
    while the server runs changes nothing about what it generates — and there is
    no symptom until a generated app misbehaves in a way the source says it
    cannot. That happened here: a fix landed at 04:41, the server had started at
    03:48, and every build for the next hours was scaffolded by the old version
    while the file on disk looked correct.

    A warning, not a reload: swapping modules under a running build is worse
    than the problem.
    """
    stale = []
    for rel, p in _own_sources():
        try:
            if p.stat().st_mtime > _AGENT_MTIMES.get(rel, 0) + 1:
                stale.append(rel)
        except OSError:
            continue
    if stale:
        elog("WARN", f"⚠ {', '.join(sorted(stale))} changed since this server "
                     f"started — restart AgentForge for it to take effect")
    return stale


def run_agent_pipeline(prompt: str, model: str, think: bool = None,
                       qa_model: str = "", resume_project: str = "",
                       logo: str = "", srs_id: str = ""):
    """
    Raw prompt → LLM plan.md → LLM writes every file in one continuous pass.

    No templates, no refiner: the model owns the whole project. One chat
    thread runs the entire build so it remembers what it already wrote.
    """
    warn_if_agents_stale()
    set_tester_emit(emit)
    try:
        cloud = is_cloud_model(model)
        elog("INFO", "━" * 40)
        elog("INFO", f"🤖 Agent mode — {prompt[:80]}")
        elog("INFO", f"{'☁️  Cloud' if cloud else '💻 Local'}: {model}   "
                     f"ctx {max_context(model):,}"
                     + ("   🤔 thinking on" if think else
                        "   ⚡ thinking off" if think is False else ""))
        elog("INFO", "━" * 40)

        eprog("Checking model…", 2)
        if not ensure_model(model):
            eerr(f"Cannot load model: {model}")
            return

        if resume_project:

            proj_dir = PROD_DIR / resume_project
            if not (proj_dir / ".agentforge" / "plan.json").is_file():
                eerr(f"{resume_project} has no plan to resume from")
                return
            pname = proj_dir.name
        else:

            proj_dir = _project_dir_for(
                _slug(_srs_app_name(srs_id) or prompt[:40]), "next")
            pname = proj_dir.name
        proj_dir.mkdir(parents=True, exist_ok=True)
        elog("INFO", f"   📁 {proj_dir}")

        logo_ready = False
        if logo:
            try:
                src = Path(logo)
                if src.is_file():
                    dest = proj_dir / "public" / "logo.png"
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(src.read_bytes())
                    logo_ready = True
                    elog("INFO", "   🖼 Using the logo you approved")
                else:
                    elog("WARN", f"   ⚠ The approved logo is gone: {logo}")
            except OSError as e:
                elog("WARN", f"   ⚠ Could not copy the logo: {e}")

        if srs_id:
            adopt_srs(srs_id, proj_dir)

        mongo_thread = threading.Thread(target=MONGO.ensure_running, daemon=True)
        mongo_thread.start()

        estep("plan", "active")

        cb = _agent_callbacks(proj_dir)

        qa_model = qa_model or model
        qa = QASession(proj_dir, callbacks=_qa_callbacks(), model=qa_model,
                       enabled=is_cloud_model(qa_model))
        if qa.enabled and qa_model != model:
            elog("INFO", f"   🧪 QA runs on {qa_model}")
        if not qa.enabled:

            elog("WARN", "   ⚠ QA is cloud-only — no unit tests, no "
                         "end-to-end flow, and no signed-in page sweep for "
                         f"{qa_model}. Pick a cloud QA model to get them.")
        cb["on_phase"] = qa.on_phase(cb["on_phase"])
        cb["on_file_written"] = qa.on_file_written(cb["on_file_written"])
        arch = ArchitectAgent(ollama, model, proj_dir, cb,
                              stack="next",
                              mongo_uri=MONGO.uri_for(pname),
                              db_name=db_name_for(pname),

                              dev_port=DEV_PORT,
                              think=think)
        qa.bind(arch)

        if resume_project:

            arch.load_existing()
            left = len(arch.unfinished())
            elog("INFO", f"⏭️  Resuming {pname} — {left} file(s) still missing")
            ok = arch.resume()
        else:

            brief = prompt
            if logo_ready:
                brief += ("\n\nThe app's logo already exists at `/logo.png` "
                          "(public/logo.png). Use it in the header and the "
                          "footer with a plain <img> and the app's name as its "
                          "alt text. Do not generate another logo, and do not "
                          "render the app name as text where the logo belongs.")
            if srs_id:

                brief = (_srs_name_line(proj_dir) + brief
                         + _srs_brief(proj_dir, model))
            ok = arch.run(brief)
        if not ok:
            estep("plan", "error")
            eerr("Agent failed to generate the project")
            qa.stop()
            return
        estep("plan", "done")
        estep("generate", "done")

        elog("INFO", f"   ✅ {len(arch.files)} files written "
                     f"({arch.tokens_out:,} tokens generated)")
        _report_unparseable(arch)

        try:
            run_image_stage(arch, proj_dir)

            _fill_missing_images(arch, proj_dir, "the pages")
        except Exception as e:
            elog("WARN", f"   ⚠ Image stage failed: {e}")
            log.exception("image stage")

        analyzer = AnalyzerAgent(arch, proj_dir,
                                 base_url=f"http://localhost:{DEV_PORT}",
                                 callbacks=_analyzer_callbacks(),
                                 allow_reseed=True)

        qa.drain(timeout=180)
        _backfill_tests(arch, proj_dir, qa)

        qa_targets = FileSnapshot(proj_dir)
        qa_targets.capture(sorted({m.get("target") for m in qa.manifest.values()
                                   if m.get("target")}))
        try:
            analyzer.run()
        except Exception as e:
            elog("WARN", f"   ⚠ Analyzer failed: {e}")
            log.exception("analyzer (seam A)")
        qa.mark_stale(qa_targets.changed())

        mongo_thread.join(timeout=120)
        db_ok = MONGO.available
        if not db_ok:
            elog("WARN", "   ⚠ No database — the app is generated, but pages "
                         "that read data will error until MongoDB is available.")

        estep("install", "active")
        eprog("npm install…", 84)
        if not ensure_node_deps(proj_dir):
            estep("install", "error")
            eerr("Failed to install dependencies")
            return
        estep("install", "done")

        if db_ok:
            try:
                r = MONGO.reset_project_db(proj_dir, node_bin=NODE_BIN)
                if r.get("dropped"):
                    elog("INFO", f"   🧹 Cleared {r['db']} — {r['dropped']} "
                                 f"collection(s) left by a previous app")
            except Exception as e:
                log.warning(f"fresh-db reset skipped: {e}")

        build_ok = run_build_fix_loop(arch, proj_dir, db_ok)
        if not build_ok:

            estep("build", "error")

        unit_pending = False

        unit_out, e2e_out, runtime_errors = {}, {}, []
        try:
            unit = run_qa_unit_stage(arch, proj_dir, qa, build_ok=build_ok)
            unit_out = unit or {}

            unit_pending = not unit.get("ran") and not build_ok
        except Exception as e:
            elog("WARN", f"   ⚠ Unit test stage failed: {e}")
            log.exception("qa unit stage")

        estep("serve", "active")
        eprog("Starting Next.js…", 90)
        start_next(proj_dir)
        wait_for_next()

        estep("test", "active")
        emit({"type": "test_start"})
        tester = TesterAgent(proj_dir, DEV_PORT, stack="next")

        runtime_deadline = time.time() + RUNTIME_DEADLINE
        prev_sig = None

        for attempt in range(1, MAX_FIX + 2):
            emit({"type": "test_run", "attempt": attempt})

            mark = dev_log_mark()
            errors = tester.test()

            faults = terminal_faults(_filter_db_noise(dev_log_since(mark), db_ok))
            for f in faults:
                if not any(f[:60] in e for e in errors):
                    errors.append(f"Dev server error: {f}")
                    emit({"type": "test_result", "status": "fail",
                          "msg": "Dev server error", "detail": f[:160]})
                    elog("WARN", f"   ❌ terminal: {f[:110]}")

            if not db_ok:
                errors = [e for e in errors
                          if not any(m in e for m in _DB_ERROR_MARKERS)]

            if not errors:

                elog("INFO", "   🎉 Tests passed — no errors")
                estep("test", "done")
                break

            now_sig = frozenset(e.splitlines()[0][:120] for e in errors)
            if prev_sig is not None and now_sig >= prev_sig:
                elog("WARN", f"   ⚠ attempt {attempt - 1} changed none of the "
                             f"{len(now_sig)} error(s) — further attempts would "
                             f"repeat it")
                _report_unfixed(errors)
                estep("test", "done")
                break
            prev_sig = now_sig

            if time.time() > runtime_deadline:
                elog("WARN", f"   ⚠ the {RUNTIME_DEADLINE}s runtime-repair "
                             f"budget is spent with {len(errors)} error(s) left")
                _report_unfixed(errors)
                estep("test", "done")
                break

            if attempt > MAX_FIX:
                elog("WARN", f"   ⚠ Reached {MAX_FIX} fix attempts with "
                             f"{len(errors)} error(s) still unfixed")
                _report_unfixed(errors)
                estep("test", "done")
                break

            dev_errors = _filter_db_noise(dev_log_since(mark), db_ok)
            if not dev_errors.strip():
                dev_errors = _filter_db_noise(next_stderr(), db_ok)
            all_errors = "\n".join(errors[:8]) + "\n" + dev_errors

            if getattr(tester, "mcp_report", ""):
                all_errors = tester.mcp_report + "\n\n" + all_errors

            guidance = nextdocs.guidance_for(all_errors)
            if guidance:
                all_errors += "\n" + guidance

            emit({"type": "test_fixing", "attempt": attempt, "errors": errors[:5]})
            elog("INFO", f"   🔧 Agent fixing (attempt {attempt}/{MAX_FIX})…")
            ephase({"phase": -2, "title": f"Fixing errors (try {attempt})",
                    "status": "active"})

            _stop_dev_proc()

            _repair_runtime(arch, proj_dir, qa, analyzer, all_errors,
                            dev_errors, attempt)

            ephase({"phase": -2, "title": f"Fixing errors (try {attempt})",
                    "status": "done"})
            ensure_node_deps(proj_dir)

            run_build_fix_loop(arch, proj_dir, db_ok, max_rounds=2)
            start_next(proj_dir)
            wait_for_next()

        if unit_pending:
            _stop_dev_proc()
            if run_build_fix_loop(arch, proj_dir, db_ok, max_rounds=1):
                build_ok = True
                elog("INFO", "   ↻ the build is green now — running the unit "
                             "tests that were skipped for it")
                try:
                    run_qa_unit_stage(arch, proj_dir, qa, build_ok=True)
                except Exception as e:
                    elog("WARN", f"   ⚠ Unit test stage failed: {e}")
                    log.exception("qa unit stage (retry)")
            else:
                elog("WARN", "   ⚠ the build is still not green — the unit "
                             "tests stay skipped")
            start_next(proj_dir)
            wait_for_next()

        try:
            e2e_out = run_qa_e2e_stage(arch, proj_dir, qa, analyzer,
                                       build_ok=build_ok, db_ok=db_ok) or {}
        except Exception as e:
            elog("WARN", f"   ⚠ End-to-end stage failed: {e}")
            log.exception("qa e2e stage")

        try:
            seam_c_mark = dev_log_mark()
            analyzer.run_runtime(
                mongo=MONGO, node_bin=NODE_BIN, use_model=build_ok,
                dev_log=lambda: _filter_db_noise(
                    dev_log_since(seam_c_mark), db_ok))
        except Exception as e:
            elog("WARN", f"   ⚠ Verification failed: {e}")
            log.exception("analyzer (seam C)")

        runtime_errors = list(errors or [])
        sec_findings, sec_audit, perf_scores = [], {}, {}

        sec_ran = False
        try:
            sec_findings, sec_audit = run_security_stage(arch, proj_dir, analyzer)
            sec_ran = True
        except Exception as e:
            elog("WARN", f"   ⚠ Security stage failed, so nothing is known "
                         f"about whether this app is safe: {e}")
            log.exception("security stage")
        try:
            perf_scores = run_perf_stage(proj_dir)
        except Exception as e:
            elog("WARN", f"   ⚠ Performance stage failed: {e}")
            log.exception("perf stage")

        unit_out = _remeasure_unit(proj_dir, qa, unit_out, arch)

        write_qa_report(proj_dir, qa, unit=unit_out, security=sec_findings,
                        audit=sec_audit, perf=perf_scores, e2e=e2e_out,
                        runtime=runtime_errors, security_ran=sec_ran)

        url = f"http://localhost:{DEV_PORT}"

        serving = False
        try:
            with socket.create_connection(("127.0.0.1", DEV_PORT), timeout=2):
                serving = True
        except OSError:

            serving = wait_for_next(20)
        if serving:
            estep("serve", "done")
            eprog("Done!", 100)
            elog("INFO", f"🎉 Live at {url}")
        else:
            estep("serve", "error")
            eprog("Built, but not serving", 100)
            elog("WARN", "   ⚠ The app was built and tested, but nothing is "
                         f"answering on port {DEV_PORT}. The files and the "
                         "test results are all on disk — use the reload button "
                         "on the preview to try serving it again.")
        edone(url, pname)

    except Exception as e:
        eerr(f"Agent error: {e}")
        log.exception("Agent pipeline error")
    finally:
        try:
            qa.stop()
        except Exception:
            pass
        stop_model(model)


def _open_for_edit(proj_name: str, model: str, think: bool = None):
    """Common preamble for every tool that edits an existing project."""
    t0 = time.time()
    proj_dir = PROD_DIR / proj_name
    if not proj_dir.exists():
        eerr(f"Project not found: {proj_name}")
        return None, None, None
    if not ensure_model(model):
        eerr(f"Cannot load model: {model}")
        return None, None, None
    stack = detect_stack(proj_dir)
    if stack == "next":
        MONGO.ensure_running()
    arch = ArchitectAgent(ollama, model, proj_dir, _agent_callbacks(proj_dir),
                          stack=stack,
                          mongo_uri=MONGO.uri_for(proj_name) if stack == "next" else "",
                          db_name=db_name_for(proj_name) if stack == "next" else "",
                          dev_port=DEV_PORT, think=think)
    arch.load_existing()
    elog("INFO", f"   ⏱ open {time.time() - t0:.1f}s")
    return proj_dir, arch, arch.stack


def run_feature(proj_name: str, request: str, model: str, think: bool = None,
                qa_model: str = ""):
    """
    Add one feature to an existing project.

    Unlike `run_agent_update`, the model is shown an inventory of every file and
    pulls what it needs, decides which files change *before* writing any of
    them, and is then held to that list. It also inherits the conversation the
    app was generated in — reloaded from `.agentforge/convo.json` — so a feature
    added an hour later is written by something that remembers the project's
    conventions rather than re-deriving them from the file listing.

    A feature is not finished when its files are written. It has to compile, it
    has to leave every OTHER page still working, and it gets unit tests of its
    own, on the same terms the build's own code did.
    """
    set_tester_emit(emit)
    try:
        proj_dir, arch, stack = _open_for_edit(proj_name, model, think)
        if arch is None:
            return
        elog("INFO", f"🧩 Feature — {request[:70]}")
        if arch.convo:
            elog("INFO", f"   🧠 Remembering the build ({len(arch.convo)} turns)")
        eprog("Planning…", 15)

        analyzer = AnalyzerAgent(arch, proj_dir,
                                 base_url=f"http://localhost:{DEV_PORT}",
                                 callbacks=_analyzer_callbacks())
        agent = FeaturesAgent(arch, proj_dir, callbacks=_analyzer_callbacks(),
                              analyzer=analyzer)
        eprog("Writing…", 40)
        spec = agent.run(request)
        if not spec.written:
            eerr("The feature agent changed nothing")
            return
        elog("INFO", f"   ✅ {len(spec.written)} file(s) written")
        if spec.rejected:
            elog("WARN", f"   ⛔ {len(spec.rejected)} write(s) outside the plan "
                         f"were dropped")

        arch.save_convo()

        if any(f.endswith("lib/seed.js") for f in spec.written) and db_ok():
            try:
                r = MONGO.reset_project_db(proj_dir, node_bin=NODE_BIN)
                if r.get("dropped"):
                    elog("INFO", f"   🧹 The seed changed — cleared {r['db']} "
                                 f"({r['dropped']} collection(s)) so it runs "
                                 f"again with the new shape")
            except Exception as e:
                elog("WARN", f"   ⚠ Could not re-seed after the seed changed: "
                             f"{e}. Records written before this feature will "
                             f"not have its new fields.")

        eprog("Verifying…", 70)
        _fill_missing_images(arch, proj_dir)
        res = verify_after_edit(arch, proj_dir, proj_name, stack=stack,
                                analyzer=analyzer)
        if res["routes_failed"]:
            elog("WARN", f"   ⚠ {len(res['routes_failed'])} route(s) still "
                         f"failing")

        eprog("Testing the feature…", 85)

        _feature_tests(arch, proj_dir, spec, model, qa_model,
                       build_ok=res["build_ok"])
        eprog("Done!", 100)
        edone(f"http://localhost:{DEV_PORT}", proj_name)
    except Exception as e:
        eerr(f"Feature error: {e}")
        log.exception("run_feature")
    finally:
        stop_model(model)


def _feature_tests(arch, proj_dir: Path, spec, model: str, qa_model: str, *,
                   build_ok: bool):
    """
    Unit-test the feature that was just added, then run the whole suite.

    Two separate claims, and both matter. The new files get tests of their own,
    on the same terms the build's code did — a feature that ships untested is
    the one place the app's coverage silently goes backwards. And the FULL
    suite runs afterwards, not just the new tests: the way a feature breaks an
    app is almost never in its own files, it is in the shared component it
    edited on the way past.

    Skipped when the build is red — a failing test against code that does not
    compile says nothing — and when the QA model is local, since QA is
    cloud-only.
    """
    qa_model = qa_model or model
    qa = QASession(proj_dir, callbacks=_qa_callbacks(), model=qa_model,
                   enabled=is_cloud_model(qa_model))
    if not qa.enabled:
        elog("WARN", "   ⚠ QA is cloud-only — the feature ships untested. "
                     "Pick a cloud QA model to have tests written for it.")
        return qa
    if not build_ok:
        elog("WARN", "   ⚠ Skipping the feature's tests — the build is not green")
        return qa
    qa.bind(arch)

    targets = select_targets(spec.written, qa.read_source,
                             already=len(qa.manifest))
    if not targets:
        elog("INFO", "   🧪 Nothing in this feature is worth a unit test")
    else:
        elog("INFO", f"   🧪 Writing tests for {len(targets)} new file(s)")
        author = UnitTestAuthor(arch, proj_dir, callbacks=_qa_callbacks(),
                                session=qa)
        written = author.write_for(targets)
        elog("INFO", f"   🧪 {len(written)} test file(s) written")

    if not qa.has_tests():
        return qa
    ephase({"phase": -15, "title": "Running unit tests", "status": "active"})
    harness = TestHarness(proj_dir, callbacks=_qa_callbacks(), cmd=qa.cmd)
    harness.materialise()
    if not harness.install():
        _qa_skip(qa, "the test runner could not be installed")
        ephase({"phase": -15, "title": "Running unit tests", "status": "done"})
        return qa
    try:
        run_qa_unit_stage(arch, proj_dir, qa, build_ok=True)
    except Exception as e:
        elog("WARN", f"   ⚠ Unit test stage failed: {e}")
        log.exception("feature unit tests")
    ephase({"phase": -15, "title": "Running unit tests", "status": "done"})
    return qa


UNDO_DIR = LOGS_DIR / "undo"


def _snapshot(proj_name: str, paths, files: dict) -> str:
    """
    Copy files aside before a whole-file rewrite.

    Outside the project directory on purpose: the project is walked to build the
    export zip, so a `.agentforge-undo/` inside it would ship to the user.
    """
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = UNDO_DIR / proj_name / stamp
    saved = 0
    for rel in paths:
        body = files.get(rel)
        if body is None:
            continue
        fp = base / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(body, encoding="utf-8")
        saved += 1
    return stamp if saved else ""


def restore_snapshot(proj_name: str, stamp: str = "") -> dict:
    base = UNDO_DIR / proj_name
    if not base.is_dir():
        return {"ok": False, "error": "nothing to undo"}
    if not stamp:
        stamps = sorted(p.name for p in base.iterdir() if p.is_dir())
        if not stamps:
            return {"ok": False, "error": "nothing to undo"}
        stamp = stamps[-1]
    src = base / stamp
    if not src.is_dir():
        return {"ok": False, "error": f"no snapshot {stamp}"}
    proj_dir = PROD_DIR / proj_name
    restored = []
    for fp in src.rglob("*"):
        if not fp.is_file():
            continue
        rel = fp.relative_to(src).as_posix()
        dest = proj_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(fp.read_text(encoding="utf-8"), encoding="utf-8")
        restored.append(rel)
    return {"ok": True, "restored": restored, "id": stamp}


def _one_line(arch, system: str, ask: str, timeout: int = 120) -> str:
    """
    One line of prose from the model, with whatever it wrapped it in removed.

    Shared by the logo prompt and the picture prompt: both ask for a single
    sentence and both get "Sure! Here's a prompt:" in front of it often enough
    to matter.
    """
    r = ollama.chat(arch.model, [{"role": "system", "content": system},
                                 {"role": "user", "content": ask[:2400]}],
                    options={"temperature": 0.7}, timeout=timeout)
    text = ((r.get("message") or {}).get("content") or "").strip()
    return text.splitlines()[-1].strip().strip('"').strip("'") if text else ""


def run_image_edit(proj_name: str, instruction: str, element: dict,
                   model: str, think: bool = None):
    """
    Redraw the picture the user pointed at, and swap it in.

    Editing markup cannot change a photograph, so pointing at an image and
    typing "a quieter room at dusk" had nowhere to go: the element edit would
    rewrite the `<img>` tag around the same file, or reach for a stock URL it
    invented. This draws a new one and rewrites the reference.

    The current `src` is the anchor. It is a literal string in the source, so
    finding what to rewrite needs no model and no resolver — and when it is not
    in the source (a path that came out of the database) that is worth saying
    plainly rather than editing the wrong thing.
    """
    set_tester_emit(emit)
    try:
        proj_dir, arch, stack = _open_for_edit(proj_name, model, think)
        if arch is None:
            return

        old_src = (str(element.get("src") or "").strip()
                   or str(element.get("bg") or "").strip())
        alt = str((element.get("attrs") or {}).get("alt") or "").strip()
        if not old_src:
            eerr("That is not a picture — there is nothing to redraw")
            return

        ref = old_src
        for cut in (f"http://localhost:{DEV_PORT}", f"http://127.0.0.1:{DEV_PORT}"):
            if ref.startswith(cut):
                ref = ref[len(cut):]
        holders = [rel for rel, body in arch.files.items()
                   if ref and ref in body]
        if not holders:
            eerr(f"That picture's address ({ref[:70]}) is not written in any "
                 f"file — it probably comes from the database, so change it "
                 f"there or in the seed")
            return

        agent = image_agent()
        if not agent.enabled:
            eerr("Image generation is switched off — turn it on in Settings")
            return
        if not agent.available():
            eerr("No Fooocus is answering — start it, or set its address in "
                 "Settings")
            return

        ephase({"phase": -21, "title": "Drawing the picture", "status": "active"})
        eprog("Writing the image prompt…", 20)
        idea = (arch.plan or {}).get("description") or ""
        ask = (f"## The picture now\n{alt or ref}\n\n"
               f"## What they want instead\n{instruction}\n"
               + (f"\n## The app it is for\n{idea[:200]}\n" if idea else ""))
        try:
            prompt = _one_line(arch, IMAGE_PROMPT_SYSTEM, ask) or instruction
        except Exception as e:
            log.debug(f"image prompt: {e}")
            prompt = instruction
        elog("INFO", f"   🎨 {prompt[:100]}")

        eprog("Drawing…", 45)
        name = agent.slug(prompt)
        out = proj_dir / "public" / "generated" / f"{name}.png"

        if not agent.generate(prompt, out, aspect="landscape", force=True):
            ephase({"phase": -21, "title": "Drawing the picture",
                    "status": "done", "written": 0})
            eerr("The picture could not be drawn")
            return
        new_ref = f"/generated/{name}.png"

        olds = {rel: arch.files[rel] for rel in holders}
        undo_id = _snapshot(proj_name, holders, olds)
        for rel in holders:
            arch.write_file(rel, olds[rel].replace(ref, new_ref))
            estream_start(rel)
            estream_end(rel, arch.files[rel])
            elog("INFO", f"   🖼 {rel} — {ref[:40]} → {new_ref}")
        if undo_id:
            emit({"type": "undo_point", "id": undo_id, "files": holders})
        ephase({"phase": -21, "title": "Drawing the picture",
                "status": "done", "written": len(holders)})
        arch.save_convo()

        eprog("Done!", 100)
        edone(f"http://localhost:{DEV_PORT}", proj_name,
              preview=_route_of(element))
    except Exception as e:
        eerr(f"Image edit error: {e}")
        log.exception("run_image_edit")
    finally:
        stop_model(model)


def run_image_swap(proj_name: str, data_b64: str, filename: str, element: dict):
    """
    Put the user's own picture where the one they pointed at is.

    The same swap `run_image_edit` performs, with the file coming from them
    instead of from Fooocus — so it needs no image model, no language model and
    no network, and answers in about as long as the file takes to decode. That
    matters beyond speed: "use this exact picture" is not a thing a generator
    can be asked for, however carefully the prompt is written.

    The reference is rewritten rather than the file overwritten. Overwriting
    `/generated/x.png` in place would be shorter, but it only works when the
    picture already lives there — this way a `/logo.png`, a path under
    `/images/`, or anything else written literally in the source is swapped by
    exactly the same code, and the old file stays on disk for the undo.
    """
    set_tester_emit(emit)
    try:
        proj_dir, arch, stack = _open_for_edit(proj_name, "", None)
        if arch is None:
            return

        old_src = (str(element.get("src") or "").strip()
                   or str(element.get("bg") or "").strip())
        if not old_src:
            eerr("That is not a picture — there is nothing to replace")
            return

        ref = old_src
        for cut in (f"http://localhost:{DEV_PORT}", f"http://127.0.0.1:{DEV_PORT}"):
            if ref.startswith(cut):
                ref = ref[len(cut):]
        holders = [rel for rel, body in arch.files.items() if ref and ref in body]
        if not holders:
            eerr(f"That picture's address ({ref[:70]}) is not written in any "
                 f"file — it probably comes from the database, so change it "
                 f"there or in the seed")
            return

        ephase({"phase": -21, "title": "Placing your picture", "status": "active"})
        eprog("Reading the file…", 30)

        name = _safe_stem(filename, "uploaded")
        out = proj_dir / "public" / "generated" / f"{name}.png"
        why = save_uploaded_image(data_b64, out)
        if why:
            ephase({"phase": -21, "title": "Placing your picture",
                    "status": "done", "written": 0})
            eerr(why)
            return

        new_ref = f"/generated/{name}.png"
        if new_ref == ref:
            # Already the reference in the source: the file on disk has just
            # been replaced, so there is nothing to rewrite and the only thing
            # left is to tell the browser to look again.
            ephase({"phase": -21, "title": "Placing your picture",
                    "status": "done", "written": 0})
            elog("INFO", f"   🖼 replaced {new_ref}")
            eprog("Done!", 100)
            edone(f"http://localhost:{DEV_PORT}", proj_name,
                  preview=_route_of(element))
            return

        eprog("Pointing the page at it…", 70)
        olds = {rel: arch.files[rel] for rel in holders}
        undo_id = _snapshot(proj_name, holders, olds)
        for rel in holders:
            arch.write_file(rel, olds[rel].replace(ref, new_ref))
            estream_start(rel)
            estream_end(rel, arch.files[rel])
            elog("INFO", f"   🖼 {rel} — {ref[:40]} → {new_ref}")
        if undo_id:
            emit({"type": "undo_point", "id": undo_id, "files": holders})
        ephase({"phase": -21, "title": "Placing your picture",
                "status": "done", "written": len(holders)})
        arch.save_convo()

        eprog("Done!", 100)
        edone(f"http://localhost:{DEV_PORT}", proj_name,
              preview=_route_of(element))
    except Exception as e:
        eerr(f"Image swap error: {e}")
        log.exception("run_image_swap")


def run_element_edit(proj_name: str, instruction: str, element: dict,
                     model: str, think: bool = None):
    """
    Change the one element the user pointed at, and nothing else.

    Resolution is deterministic first — the route's import closure, then literal
    text and class matching — and only reaches the model when the leading
    candidate is not clear. The write is allowlisted to the resolved file, and
    `guard_scope` measures the diff afterwards, because "make this teal" and
    "rewrite this page" arrive as the same kind of tool call.
    """
    set_tester_emit(emit)
    try:
        proj_dir, arch, stack = _open_for_edit(proj_name, model, think)
        if arch is None:
            return
        analyzer = AnalyzerAgent(arch, proj_dir,
                                 base_url=f"http://localhost:{DEV_PORT}",
                                 callbacks=_analyzer_callbacks())
        resolver = ElementResolver(arch, analyzer)

        elog("INFO", f"🎯 {describe(element).splitlines()[0][:90]}")
        eprog("Finding the code…", 15)
        t_resolve = time.time()
        res = resolver.resolve(element)
        elog("INFO", f"   ⏱ resolve {time.time() - t_resolve:.1f}s")
        if not res.path:
            eerr(f"Could not find the code for that element — {res.reason}")
            return
        elog("INFO", f"   📍 {res.path}:{res.line or '?'} "
                     f"({'model chose' if res.used_model else 'unambiguous'})")
        shared = _shared_routes(arch, res.path)
        emit({"type": "element_picked", "file": res.path, "line": res.line,
              "score": res.score, "candidates": res.candidates[:6],
              "used_model": res.used_model, "shared_routes": shared[:12]})
        page_route = _route_of(element)
        verdict = _scope_verdict(res.path, shared, instruction, route=page_route)
        if verdict == "asked":
            return
        if verdict == "scoped":

            return run_page_update(proj_name, instruction, model, page_route,
                                   think)

        before = arch.files.get(res.path, "")
        if not before:
            eerr(f"{res.path} is empty or unreadable")
            return
        anchor = (element.get("text") or "").strip()[:60]
        removing = looks_like_removal(instruction)
        adding = looks_like_addition(instruction)
        retexting = looks_like_retext(instruction)

        eprog("Editing…", 40)
        ephase({"phase": -11, "title": "Editing the element", "status": "active"})

        mark = dev_log_mark()
        t_write = time.time()
        ok, written = _element_write_round(arch, res.path, before, instruction,
                                           element, anchor, removing, adding,
                                           retexting)
        elog("INFO", f"   ⏱ model {time.time() - t_write:.1f}s")
        if not ok:
            ephase({"phase": -11, "title": "Editing the element", "status": "done"})
            return

        undo_id = _snapshot(proj_name, [res.path], {res.path: before})
        arch.write_file(res.path, written)
        estream_start(res.path)
        estream_end(res.path, written)
        if undo_id:
            emit({"type": "undo_point", "id": undo_id, "files": [res.path]})
        ephase({"phase": -11, "title": "Editing the element", "status": "done",
                "written": 1})

        eprog("Verifying…", 75)
        t_verify = time.time()

        _fill_missing_images(arch, proj_dir)
        verify_after_edit(arch, proj_dir, proj_name, stack=stack,
                          build_rounds=0, probe=False, analyzer=analyzer)
        _autofix_from_terminal(arch, res.path, element, mark,
                               proj_dir=proj_dir, analyzer=analyzer, model=model)
        elog("INFO", f"   ⏱ verify {time.time() - t_verify:.1f}s")
        eprog("Done!", 100)
        edone(f"http://localhost:{DEV_PORT}", proj_name,
              preview=_route_of(element))
    except Exception as e:
        eerr(f"Element edit error: {e}")
        log.exception("run_element_edit")
    finally:
        stop_model(model)


LOCAL_IMPORT_RE = re.compile(r"""from\s+['"]@/(components/[\w./-]+)['"]""")


def _section_span(element: dict) -> str:
    """
    The two elements that bound the selected section: its first and its last.

    A click reports one node. When that node is a section rather than a leaf,
    one node is not enough to act on — "put a band under this" needs to know
    where "this" ends, and a model given only the opening element guesses the
    boundary from the markup and regularly guesses a different one than the
    user drew. So the picker sends both edges and they are described here in
    the order they appear.

    Empty when the selection was a single element, which is the common case and
    needs no span at all.
    """
    sec = element.get("section") or {}
    first, last = sec.get("start"), sec.get("end")
    if not isinstance(first, dict) or not isinstance(last, dict):
        return ""
    return (f"  1. {describe(first).splitlines()[0]}\n"
            f"  2. {describe(last).splitlines()[0]}")


_MAP_IMPORT_RE = re.compile(r"""from\s+['"]@/(components/[^'"]+)['"]""")
_MAP_METHOD_RE = re.compile(
    r"export\s+(?:async\s+)?(?:function|const)\s+(GET|POST|PUT|PATCH|DELETE)")
_MAP_COLLECTION_RE = re.compile(r"""getCollection\s*\(\s*['"]([a-zA-Z0-9_]+)['"]""")


def _project_map(arch) -> str:
    """
    Where everything lives, in about a page of text.

    An edit request arrives with one file's source and no idea what else
    exists, so "add a cancel button that calls the bookings API" has to be
    answered by guessing the route's path and shape. Guessing is how a repair
    invented `@/components/CartContext` and how "remove the navbar" was aimed
    at a page that never had one.

    Built from the files on disk every time it is asked for, NOT written once
    at the end of a build. A map generated at build time is wrong the moment
    the first feature lands, and a stale map is worse than none — it sends the
    model confidently to a file that moved. This costs nothing to rebuild:
    measured at 1,287 characters for a 40-file project, against 76,000
    characters of source.
    """
    pages, apis, comps, libs, colls = [], [], set(), [], set()
    for rel, body in sorted(arch.files.items()):
        if not rel.endswith((".js", ".jsx")):
            continue
        colls.update(_MAP_COLLECTION_RE.findall(body))
        if rel.startswith("app/") and rel.rsplit("/", 1)[-1].startswith("page."):
            seg = rel[len("app/"):].rsplit("/", 1)[0]
            route = "/" if seg.startswith("page.") else "/" + seg
            kind = ("client"
                    if body.lstrip()[:40].lstrip("\"'").startswith("use client")
                    else "server")
            uses = [m.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                    for m in dict.fromkeys(_MAP_IMPORT_RE.findall(body))]
            pages.append((route, rel, kind, uses))
        elif rel.startswith("app/") and rel.rsplit("/", 1)[-1].startswith("layout."):
            seg = rel[len("app/"):].rsplit("/", 1)[0]
            uses = [m.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                    for m in dict.fromkeys(_MAP_IMPORT_RE.findall(body))]
            pages.append(("/" if seg.startswith("layout.") else "/" + seg,
                          rel, "layout", uses))
        elif rel.startswith("app/api/") and rel.rsplit("/", 1)[-1].startswith("route."):
            ms = sorted(set(_MAP_METHOD_RE.findall(body)))
            apis.append(("/" + rel[len("app/"):].rsplit("/", 1)[0],
                         rel, ", ".join(ms) or "—"))
        elif rel.startswith("components/"):
            comps.add(rel)
        elif rel.startswith("lib/"):
            libs.append(rel)
    if not pages and not apis:
        return ""

    out = ["## The whole project, so you do not have to guess where things are",
           "", "### Routes"]
    for route, rel, kind, uses in sorted(pages, key=lambda p: p[0]):
        line = f"- `{route}` → {rel} ({kind})"
        if uses:
            line += " — renders " + ", ".join(uses[:6])
        out.append(line)
    out += ["", "### API", *[f"- `{r}` → {f} [{m}]" for r, f, m in sorted(apis)]]
    unused = sorted(c for c in comps
                    if not any(c.rsplit("/", 1)[-1].rsplit(".", 1)[0] in u
                               for _, _, _, us in pages for u in us))
    out += ["", "### Components",
            *[f"- {c}" for c in sorted(comps)]]
    if unused:
        out.append(f"  (rendered by no route: {', '.join(unused)})")
    if libs:
        out += ["", "### lib", *[f"- {l}" for l in sorted(libs)]]
    if colls:
        out += ["", "### MongoDB collections",
                "- " + ", ".join(sorted(colls))]
    out += ["", "A layout wraps every route beneath it — the navbar, header "
                "and footer are in a layout, never in the page."]
    return "\n".join(out)


def _shared_routes(arch, rel: str) -> list:
    """Every route `rel` appears on. Never raises — scope advice is not worth
    failing an edit over."""
    try:
        return routes_rendering(arch.files, rel)
    except Exception as e:
        log.debug(f"shared routes {rel}: {e}")
        return []


def _scope_verdict(rel: str, shared: list, instruction: str,
                   route: str = "") -> str:
    """
    `""` go ahead · `"scoped"` do it for this route only · `"asked"` stop.

    The picker paths edit exactly the file they resolve to, and a click on a
    footer resolves to the file that RENDERS it — usually a layout or a shared
    component. So "remove the footer", said while looking at /login, quietly
    took it off the whole site, and the preview afterwards showed /login,
    where it did indeed look right.

    Asking rather than guessing was the explicit call. A wrong guess either
    deletes something from eleven pages nobody was looking at, or refuses what
    was plainly asked; neither is recoverable without noticing, and one of them
    is not noticeable at all.

    No new protocol: the question goes out as log lines and the next
    instruction is the answer. Which means the answer has to be recognised —
    hence `looks_like_page_only` as well as `looks_like_global`, or "on /login
    only" is not global, and the same question gets asked forever.
    """
    if len(shared) <= 1:
        return ""
    where = route or "this page"
    if looks_like_global(instruction):
        elog("WARN", f"   🌐 {rel} is rendered on {len(shared)} routes — "
                     f"changing all of them, as asked")
        return ""
    if looks_like_page_only(instruction):
        elog("INFO", f"   📐 {rel} is on {len(shared)} routes — changing "
                     f"{where} only, as asked")
        return "scoped"
    elog("WARN", f"   🛑 Not done yet — that lives in {rel}, which is rendered "
                 f"on {len(shared)} routes, not just {where}:")
    elog("WARN", f"      {', '.join(shared[:8])}"
                 + (f" (+{len(shared) - 8} more)" if len(shared) > 8 else ""))
    elog("INFO", f"      Say “{instruction.strip()[:60]} — everywhere” to "
                 f"change all of them,")
    elog("INFO", f"      or “{instruction.strip()[:60]} — on {where} only” to "
                 f"keep the others as they are.")
    emit({"type": "ask", "kind": "scope", "file": rel, "routes": shared[:12],
          "route": route,
          "options": [f"{instruction.strip()[:60]} — on {where} only",
                      f"{instruction.strip()[:60]} — everywhere"]})
    eprog("Waiting for you", 0)
    return "asked"


def _reach_label(arch, rel: str, route: str = "") -> str:
    """
    How many routes a file is on, said plainly enough to act on.

    The point is the difference between the two answers. "You MAY rewrite this
    one" is true of both a layout that wraps twelve routes and a layout that
    wraps one, and only one of them is safe to delete a footer from.
    """
    try:
        reach = routes_rendering(arch.files, rel)
    except Exception as e:
        log.debug(f"reach label {rel}: {e}")
        return "wraps this route — you MAY rewrite this one"
    if len(reach) > 1:
        return (f"rendered on ALL {len(reach)} routes — editing this changes "
                f"every one of them, not just {route or 'this page'}")
    if len(reach) == 1:
        return f"{reach[0]} only — safe to edit for this route"
    return "wraps this route — you MAY rewrite this one"


def _layout_chain(arch, path: str, cap: int = 3) -> list:
    """
    The layouts that wrap this page, outermost last, with what they render.

    A page does not import its layout — Next composes them — so following the
    page's own imports never reaches `app/layout.jsx`, and the navbar, header
    and footer live there. Asking to "remove the navbar from the login page"
    then sends the model a file with no navbar in it and no way to obey:
    measured, one such edit reasoned for eleven minutes and changed nothing.

    Returns `[(path, body)]` for the layout chain and the components those
    layouts render, so the chrome is on the table when the request is about it.
    """
    out, seen = [], set()
    if not path.startswith("app/"):
        return out
    parts = path[len("app/"):].split("/")[:-1]

    for i in range(len(parts), -1, -1):
        stem = "/".join(["app"] + parts[:i] + ["layout"])
        for ext in (".jsx", ".js"):
            body = arch.files.get(stem + ext)
            if body and stem + ext not in seen:
                seen.add(stem + ext)
                out.append((stem + ext, body))
            if len(out) >= cap:
                return out

    for _, body in list(out):
        for spec in dict.fromkeys(LOCAL_IMPORT_RE.findall(body)):
            for ext in (".jsx", ".js", ""):
                sub = arch.files.get(f"{spec}{ext}")
                if sub and f"{spec}{ext}" not in seen:
                    seen.add(f"{spec}{ext}")
                    out.append((f"{spec}{ext}", sub))
                    break
            if len(out) >= cap + 3:
                return out
    return out


def _neighbours(arch, path: str, before: str, cap: int = 4) -> str:
    """
    The components this file renders, in full.

    The clicked element on its own is not enough to write beside. A page is
    mostly composition — the section above the click lives in
    `components/Hero.jsx` — and "match what is already there" is not
    something anyone can do without seeing it. This is the difference
    between a new section that looks like the site and one that looks
    bolted on.
    """
    blocks = []
    for spec in dict.fromkeys(LOCAL_IMPORT_RE.findall(before)):
        for ext in (".jsx", ".js", ""):
            body = arch.files.get(f"{spec}{ext}")
            if body:
                blocks.append(f"--- {spec}{ext} (rendered by {path} — for "
                              f"reference, do NOT rewrite it) ---\n{body}")
                break
        if len(blocks) >= cap:
            break
    return "\n\n".join(blocks)


MAX_ELEMENT_AUTOFIX = 2


def _autofix_from_terminal(arch, path, element, mark, rounds=MAX_ELEMENT_AUTOFIX,
                           proj_dir: Path = None, analyzer=None, model: str = None):
    """
    Read what the dev server said about the edit, and rewrite the file if it
    complained.

    An element edit skips the production build on purpose — it is nine seconds
    of writing against minutes of compiling, for three lines. What replaces it
    is this: request the edited route so Next compiles it, then read the
    server's own terminal. A broken edit says so there, in the exact words a
    model can act on, and the file to rewrite is already known — no planning
    pass, no allowlist to derive.

    When those rounds run out the failure goes to the BUG FIXER rather than
    being served broken. This loop only ever rewrites the one file the edit
    touched, which is the right first guess and the wrong last one: a redesign
    can break a child component, a shared import or a page that renders the
    same file, and none of those are `path`. `_repair_runtime` plans which
    files a failure actually spans and repairs those.

    That escalation is what makes it safe to stop pre-judging the size of an
    edit. The scope guard used to refuse a large rewrite in case it broke
    something; now the rewrite lands, and anything it broke is diagnosed from
    the running app instead of guessed at from a diff.

    Returns True when the route is clean, False when it is still broken.
    """
    import urllib.error
    import urllib.request

    route = _route_of(element)
    for rnd in range(1, rounds + 1):

        status = None
        try:
            with urllib.request.urlopen(
                    f"http://localhost:{DEV_PORT}{route}", timeout=60) as r:
                status = r.status
        except urllib.error.HTTPError as e:
            status = e.code
        except Exception as e:
            log.debug(f"autofix probe {route}: {e}")

        faults = terminal_faults(_filter_db_noise(dev_log_since(mark), True))
        if not faults and (status is None or status < 400):
            if rnd > 1:
                elog("INFO", f"   ✅ {route} is clean after the repair")
            return True

        if rnd > rounds:
            break
        detail = "\n".join(faults[:4]) or f"{route} returned HTTP {status}"
        elog("WARN", f"   🔧 {route} broke — repairing ({rnd}/{rounds}): "
                     f"{detail.splitlines()[0][:100]}")
        ephase({"phase": -19, "title": f"Repairing the edit (round {rnd})",
                "status": "active"})

        before = arch.files.get(path, "")
        fix = (f"The edit you just made broke this page. The dev server "
               f"reports:\n\n```\n{detail[:2000]}\n```\n\n"
               f"Rewrite {path} so the page works again, keeping the change "
               f"that was asked for. Fix only the cause — everything else in "
               f"the file comes back exactly as it is now.")
        mark = dev_log_mark()
        ok, written = _element_write_round(arch, path, before, fix, element,
                                           "", False, True, attempts=1)
        ephase({"phase": -19, "title": f"Repairing the edit (round {rnd})",
                "status": "done", "written": 1 if ok else 0})
        if not ok:
            break
        arch.write_file(path, written)
        estream_start(path)
        estream_end(path, written)

    # Still broken, and this loop has nothing left to try — it can only ever
    # rewrite `path`, and by now the cause is somewhere else.
    if proj_dir is not None:
        faults = terminal_faults(_filter_db_noise(dev_log_since(mark), True))
        detail = "\n".join(faults[:6]) or f"{route} is failing after an edit"
        elog("WARN", f"   🐞 Handing {route} to the bug fixer")
        ephase({"phase": -20, "title": "Bug fixer", "status": "active"})
        try:
            helper = analyzer or AnalyzerAgent(
                arch, proj_dir, base_url=f"http://localhost:{DEV_PORT}",
                callbacks=_analyzer_callbacks())
            written = _repair_runtime(arch, proj_dir, None, helper, detail,
                                      detail, 1, model)
            ephase({"phase": -20, "title": "Bug fixer", "status": "done",
                    "written": len(written or [])})
            if written:
                elog("INFO", f"   🐞 Bug fixer rewrote {len(written)} file(s)")
                if _autofix_from_terminal(arch, path, element, dev_log_mark(),
                                          rounds=1):
                    return True
        except Exception as e:
            ephase({"phase": -20, "title": "Bug fixer", "status": "done"})
            elog("WARN", f"   ⚠ Bug fixer failed: {e}")
            log.exception("autofix: runtime repair")

    elog("WARN", f"   ⚠ {route} is still reporting errors — serving as-is")
    return False


PICTURES_RULE = (
    "PICTURES ARE FREE — ASK FOR ONE AND IT IS DRAWN. When the request wants "
    "an image, a photo, a picture, an icon, a logo or a background, write an "
    "ordinary tag pointing into /generated/ and describe the picture in the "
    "alt text:\n"
    "    <img src=\"/generated/sourdough-loaf.png\" "
    "alt=\"a rustic sourdough loaf on a wooden board, warm morning light\" "
    "className=\"...\" />\n"
    "The file does not exist yet and that is fine — the alt text is the "
    "prompt, and every picture referenced this way is generated and written "
    "to disk the moment your edit lands. Use a short kebab-case filename and "
    "write the alt text the way you would describe the shot to a "
    "photographer: subject, setting, style, light.\n"
    "Never use a stock photo URL, never link to an external host, and never "
    "leave a placeholder box where a picture was asked for.\n"
    "PUT IT WHERE IT CAN BE SEEN. A picture that was asked for is the point of "
    "the change, so it goes in the flow of the section at full strength — no "
    "`opacity-20`, no `mix-blend-multiply`, and no gradient laid over it. This "
    "is the shape that keeps coming back and it renders as nothing at all:\n"
    "    <div className=\"absolute inset-0 z-0 opacity-20\">\n"
    "      <img … className=\"… mix-blend-multiply\" />\n"
    "      <div className=\"absolute inset-0 bg-gradient-to-b from-white "
    "to-white\" />\n"
    "    </div>\n"
    "Twenty per cent opacity under a white gradient on a white section is an "
    "invisible picture, and the person who asked for it sees no change. Only "
    "make one a faint background when the request actually said watermark, "
    "texture, or subtle background — and even then keep it above `opacity-60`. "
    "Otherwise give it real size: a hero band, a card image, a figure beside "
    "the text, something with width and height that a reader would notice.\n\n")


def _edit_rules(adding: bool) -> str:
    """
    The fence around a picker edit, in the two shapes it comes in.

    Adding and updating need different sentences. "Only add the new section"
    read against an update request is an instruction to change nothing, and
    "do whatever they asked to this section" read against an add is an
    invitation to rewrite the one they pointed at instead of putting a new one
    beside it. What both share is the part that is never negotiable: routes,
    entities and functions.
    """
    shared = ("DO NOT CHANGE: api routes, entities, functions. The routes stay "
              "at the same paths with the same methods and the same request "
              "and response shapes. The data entities keep their fields and "
              "their names. Every function keeps its name, its parameters and "
              "what it does.\n\n"
              + PICTURES_RULE)
    if adding:
        return shared + (
            "DO NOT CHANGE THE OLD SECTIONS — ONLY ADD THE NEW ONE. Every "
            "section already on this page comes back byte-for-byte as it is "
            "now: same markup, same classes, same order, same blank lines. "
            "Your entire change is the new section, placed where they asked "
            "for it.\n\n")
    return shared + (
        "DO NOT CHANGE ANY CODE SEGMENT THAT IS NOT THE SELECTED ONE. Other "
        "sections, other components, the imports, the exports — all of it "
        "comes back byte-for-byte as it is now. Inside the selection, do "
        "whatever they asked: text, animation, layout, the complete design, "
        "or removing it altogether if that is the request.\n\n")


def _element_write_round(arch, path, before, instruction, element, anchor,
                         removing, adding=False, retexting=False, attempts=2):
    """Ask for the rewrite; reject anything that overran and retry once."""
    near = _neighbours(arch, path, before)
    span = _section_span(element)
    user = (f"## The element the user clicked\n{describe(element)}\n\n"
            + (f"## The section they selected — it runs from the first of "
               f"these to the second\n{span}\n\n" if span else "")
            + f"Route: {element.get('route', '/')}\n\n"
            + f"## What they want\n{instruction}\n\n"
            + _edit_rules(adding)
            + f"## The complete current source of {path}\n{before}"
            + (f"\n\n## The components it renders, so you can match "
               f"them\n{near}" if near else ""))
    convo = [{"role": "system", "content": ELEMENT_EDIT_SYSTEM},
             {"role": "user", "content": user}]

    for attempt in range(1, attempts + 1):
        got = {}
        parser = FileStreamParser(
            on_text=lambda t: None,
            on_file_start=lambda p: None,
            on_file_token=lambda t: None,
            on_file_end=lambda p, c: got.__setitem__("body", c))
        buf = []

        def feed(tok):
            buf.append(tok)
            parser.feed(tok)

        try:
            arch._stream(convo, feed, temperature=0.3,
                         timeout=arch.EDIT_TIMEOUT)
        except Exception as e:
            eerr(f"The model failed: {e}")
            return False, ""
        parser.close()
        reply = "".join(buf)

        for out in arch.run_requested_commands(reply):
            elog("INFO", f"   📦 {out.splitlines()[0][:110]}")

        need = re.search(r"^\s*NEED\s+(\S+)\s*$", reply, re.M)
        if need and "body" not in got:
            eerr(f"That change needs {need.group(1).strip('`')}, which this tool "
                 f"does not edit — use the Feature tab instead")
            return False, ""
        body = got.get("body", "")
        if not body:

            head = " ".join(reply.split())[:300] or "(empty response)"

            if re.search(r"(?:does not exist|is not present|not found|"
                         r"cannot find|no (?:such|tools|section))", reply, re.I):
                elog("INFO", f"   ✅ Nothing to change — {head[:160]}")
                eerr("That element is not on this page — nothing was changed")
                return False, ""
            elog("WARN", f"   ⚠ no <write_file> block — model said: {head}")
            if attempt < attempts:
                convo.append({"role": "assistant", "content": reply[:2000]})
                convo.append({"role": "user", "content":
                    "That was not a file. Output the COMPLETE file inside "
                    f"one <write_file path=\"{path}\">…</write_file> block, "
                    "starting immediately with '<write_file'. No markdown "
                    "fences, no explanation, no summary."})
                continue
            eerr("The model returned no file")
            return False, ""

        why = None
        if not body.strip():
            why = "the rewrite is empty"
        elif len(body) < 0.5 * len(before):
            why = (f"the rewrite is {len(body)} characters against "
                   f"{len(before)} before — the file was truncated")
        if not why:
            return True, body

        elog("WARN", f"   ⛔ Rejected: {why[:110]}")
        if attempt == attempts:
            eerr("The edit changed far more than the element — nothing was "
                 "written")
            return False, ""
        convo.append({"role": "assistant", "content": reply[:2000]})
        convo.append({"role": "user", "content":
            f"That rewrite was rejected: {why}\n\nTry again. Output the "
            f"COMPLETE file, byte-identical to the original except for the "
            f"element described above."})
    return False, ""


def _vision_model(preferred: str) -> str:
    """
    The model to send an image to.

    DEFAULT_BUILD (`qwen2.5-coder:14b`) has no vision capability, so this fires
    often. Borrowing one for a single call beats refusing the tool; returning ""
    means the caller degrades to text-only rather than failing.
    """
    try:
        if ollama.supports_vision(preferred):
            return preferred
    except Exception:
        pass
    saved = str(load_settings().get("vision_model", "")).strip()
    if saved:
        return saved
    try:
        cat = ollama.catalog()
        pool = (cat.get("cloud") or []) + (cat.get("local") or [])
        for entry in pool:
            if entry.get("vision"):
                return entry["id"]
    except Exception as e:
        log.warning(f"could not find a vision model: {e}")
    return ""


def _pencil_write_round(arch, path, before, instruction, element, shot,
                        vis_model, payload, attempts=2):
    vp = payload.get("viewport") or {}
    text = (f"Route: {element.get('route') or payload.get('route') or '/'}   "
            f"Viewport: {vp.get('w', '?')}×{vp.get('h', '?')} "
            f"({vp.get('mode', 'desktop')})\n")
    if shot and shot.ok():
        c = shot.crop
        text += (f"The red freehand annotation marks the region to redesign.\n"
                 f"Region in the page: x={c.get('x')} y={c.get('y')} "
                 f"{c.get('width')}×{c.get('height')}\n")
        if shot.logged_in:
            text += "The capture is of the signed-in view.\n"
    else:
        text += ("No screenshot is available. Redesign the element described "
                 "below.\n")
    if element:
        text += f"\nElement under the drawing:\n{describe(element)}\n"
    text += (f"\n## What the user asked for\n{instruction}\n\n"
             f"## The complete current source of {path}\n{before}")

    msg = {"role": "user", "content": text}
    if shot and shot.ok():

        msg["images"] = [shot.png_b64]

    convo = [{"role": "system", "content": PENCIL_SYSTEM}, msg]
    anchor = (element.get("text") or "").strip()[:60]

    for attempt in range(1, attempts + 1):
        got = {}
        parser = FileStreamParser(
            on_text=lambda t: None,
            on_file_start=lambda p: None,
            on_file_token=lambda t: None,
            on_file_end=lambda p, c: got.__setitem__("body", c))
        try:
            arch._stream(convo, parser.feed, temperature=0.4,
                         model=vis_model, timeout=arch.EDIT_TIMEOUT)
        except Exception as e:
            eerr(f"The model failed: {e}")
            return False, ""
        parser.close()
        body = got.get("body", "")
        if not body:
            eerr("The model returned no file")
            return False, ""

        # Only a broken file is refused now, never a big edit. The old ceiling
        # answered "did this change more than I expected" and threw the work
        # away when it had — which is what a redesign always does. What tests
        # the result instead runs after this: the syntax gate, the export gate,
        # the route probe, and the bug fixer for whatever is still wrong.
        why = guard_scope(before, body, anchor=anchor,
                          removing=looks_like_removal(instruction),
                          designing=True)
        if not why:
            return True, body
        elog("WARN", f"   ⛔ Rejected: {why[:110]}")
        if attempt == attempts:
            eerr(f"The model did not return a usable file — {why}")
            return False, ""
        convo.append({"role": "user", "content":
            f"That rewrite was rejected: {why}\n\nReturn the complete file "
            f"again, with the change applied."})
    return False, ""


def run_pencil_edit(proj_name: str, instruction: str, payload: dict,
                    model: str, think=None):
    """
    Redesign the region the user drew over.

    The image is captured server-side: a browser cannot rasterise an iframe from
    the parent document, so same-origin buys DOM access for the picker and
    nothing at all for pixels.

    `think` is a real parameter now. Both dispatchers have always passed five
    arguments and the body has always read `think`, so every pencil edit raised
    TypeError on the first line inside the `try` and surfaced as "Pencil edit
    error" — the tool has never once run. Defaulted so a four-argument caller
    keeps working.
    """
    set_tester_emit(emit)
    element = payload.get("element") or {}
    try:
        proj_dir, arch, stack = _open_for_edit(proj_name, model, think)
        if arch is None:
            return
        analyzer = AnalyzerAgent(arch, proj_dir,
                                 base_url=f"http://localhost:{DEV_PORT}",
                                 callbacks=_analyzer_callbacks())
        resolver = ElementResolver(arch, analyzer)

        route = payload.get("route") or element.get("route") or "/"
        eprog("Finding the code…", 12)
        res = resolver.resolve({**element, "route": route})
        if not res.path:
            eerr(f"Could not find the code for that region — {res.reason}")
            return
        elog("INFO", f"   📍 {res.path}:{res.line or '?'}")
        shared = _shared_routes(arch, res.path)
        emit({"type": "element_picked", "file": res.path, "line": res.line,
              "score": res.score, "candidates": res.candidates[:6],
              "used_model": res.used_model, "shared_routes": shared[:12]})
        verdict = _scope_verdict(res.path, shared, instruction, route=route)
        if verdict == "asked":
            return
        if verdict == "scoped":
            return run_page_update(proj_name, instruction, model, route, think)

        before = arch.files.get(res.path, "")
        if not before:
            eerr(f"{res.path} is empty or unreadable")
            return

        vis_model = _vision_model(model)
        shot = None
        if vis_model:
            eprog("Capturing the region…", 30)
            ephase({"phase": -12, "title": "Capturing the region",
                    "status": "active"})
            creds = analyzer.demo_credentials()
            shot = capture_region(
                route, viewport=payload.get("viewport") or {},
                scroll=payload.get("scroll") or {},
                strokes=payload.get("strokes") or [], port=DEV_PORT,
                login=(creds[0] if creds else None),
                login_endpoint=analyzer.find_login_endpoint())
            ephase({"phase": -12, "title": "Capturing the region",
                    "status": "done"})
            if not shot.ok():
                elog("WARN", f"   ⚠ Screenshot failed ({shot.error}) — using the "
                             f"element description instead")
                shot = None
            elif vis_model != model:
                elog("INFO", f"   👁 {model} has no vision — using {vis_model} "
                             f"for this one call")
        else:
            elog("WARN", "   ⚠ No vision-capable model is available — the "
                         "drawing is used only to locate the region")

        eprog("Redesigning…", 50)
        ephase({"phase": -13, "title": "Redesigning", "status": "active"})

        mark = dev_log_mark()
        ok, written = _pencil_write_round(arch, res.path, before, instruction,
                                          element, shot, vis_model or model,
                                          payload)
        ephase({"phase": -13, "title": "Redesigning", "status": "done",
                "written": 1 if ok else 0})
        if not ok:
            return

        undo_id = _snapshot(proj_name, [res.path], {res.path: before})
        arch.write_file(res.path, written)
        estream_start(res.path)
        estream_end(res.path, written)
        if undo_id:
            emit({"type": "undo_point", "id": undo_id, "files": [res.path]})

        eprog("Verifying…", 78)
        _fill_missing_images(arch, proj_dir)
        verify_after_edit(arch, proj_dir, proj_name, stack=stack,
                          build_rounds=0, probe=False, analyzer=analyzer)
        _autofix_from_terminal(arch, res.path, payload, mark,
                               proj_dir=proj_dir, analyzer=analyzer, model=model)
        eprog("Done!", 100)
        edone(f"http://localhost:{DEV_PORT}", proj_name,
              preview=_route_of(payload))
    except Exception as e:
        eerr(f"Pencil edit error: {e}")
        log.exception("run_pencil_edit")
    finally:
        stop_model(model)


PAGE_UPDATE_SYSTEM = """\
You are rewriting ONE page of a Next.js 16 App Router app, in place.

You are given the complete current source of that page, the components it
renders, and what the user wants changed. Everything you need is here.

DO EVERYTHING THEY ASKED FOR. Rewrite the copy, change the animations,
restructure the layout, redesign the page end to end — if that is the request,
that is the job, and no change is too large.

THAT INCLUDES REMOVING THINGS. "Take the sidebar out", "drop the stats band",
"get rid of the hero" — do exactly that, and delete the markup properly rather
than hiding it behind a class. Removal is a normal request, not a special case.

WHAT MUST NOT HAPPEN is a part of the page disappearing that they never
mentioned. A request to tighten the spacing leaves every section still on the
page. A request to restyle the cards leaves the FAQ below them alone. One
question before you answer: is anything gone that they did not ask you to
remove? If so, put it back.

Do not invent content either. No placeholder addresses, phone numbers, social
links, testimonials or statistics that the app has no data for: an empty column
is better than a fabricated one.

WHAT IS NEVER YOURS TO CHANGE:
  • API routes — same paths, same methods, same request and response shapes.
  • Entities — the collections and the fields on them keep their names.
  • Functions — every one keeps its name, its parameters and what it does.
  • Exports — other files import them.
  • Props — a component called with `product={p}` is still called that way.
  • 'use client' stays exactly where it is, or stays absent. If something you
    add needs a hook or a handler and this file is a Server Component, put that
    piece in its own small 'use client' component and render it here.

IF YOU NEED A PACKAGE THAT IS NOT INSTALLED, ask for it BEFORE the file:

<run_command>npm install embla-carousel-react</run_command>

One package per command, real npm names, `npm install` only. Already there, so
never ask for: react, react-dom, next, mongodb, tailwindcss, lucide-react,
framer-motion, better-auth.

Output the COMPLETE file in exactly one <write_file path="…"> block. No
markdown fences, no explanation.
"""


def _page_file_for(arch, analyzer, route: str) -> str:
    """The page file a route renders, or '' when the route is unknown."""
    route = (route or "/").split("?")[0].rstrip("/") or "/"
    try:
        for url, meta in (analyzer.enumerate_routes() or {}).items():
            if meta.get("kind") == "page" and (url.rstrip("/") or "/") == route:
                return meta.get("file", "")
    except Exception as e:
        log.debug(f"page file for {route}: {e}")

    stem = "app" + ("" if route == "/" else route) + "/page"
    for ext in (".jsx", ".js"):
        if (stem + ext) in arch.files:
            return stem + ext
    return ""


def run_page_update(proj_name: str, instruction: str, model: str, route: str,
                    think: bool = None):
    """
    Rewrite the page the user is looking at, and nothing else.

    The general update path hands the model an 18-file snapshot and lets it
    choose what to touch. When the user is looking at one page and describing
    what they want it to look like, that is both slower and less accurate than
    handing over that page in full — and it is the difference between "change
    the layout of this page" and an edit that lands in a shared component and
    changes four other screens.

    Behaviour is fenced off in the prompt rather than by scope: the file may
    change as much as the request needs, but the routes, entities, functions,
    exports and props it defines may not.
    """
    set_tester_emit(emit)
    try:
        proj_dir, arch, stack = _open_for_edit(proj_name, model, think)
        if arch is None:
            return
        analyzer = AnalyzerAgent(arch, proj_dir,
                                 base_url=f"http://localhost:{DEV_PORT}",
                                 callbacks=_analyzer_callbacks())
        path = _page_file_for(arch, analyzer, route)
        if not path or path not in arch.files:
            eerr(f"No page file found for {route or '/'} — use the Feature "
                 f"tab for changes that span more than one page")
            return

        before = arch.files[path]
        elog("INFO", f"📄 Page update — {route or '/'} → {path}")
        eprog("Rewriting the page…", 35)
        ephase({"phase": -20, "title": f"Rewriting {route or '/'}",
                "status": "active"})

        near = _neighbours(arch, path, before)
        chain = _layout_chain(arch, path)

        chrome = "\n\n".join(f"--- {p} ({_reach_label(arch, p, route)}) ---\n{b}"
                             for p, b in chain)
        pmap = _project_map(arch)
        user = ((f"{pmap}\n\n" if pmap else "")
                + f"## The page\nRoute: {route or '/'}\nFile: {path}\n\n"
                f"## What the user wants\n{instruction}\n\n"
                f"DO NOT CHANGE: api routes, entities, functions. The routes "
                f"stay at the same paths with the same methods and the same "
                f"request and response shapes. The data entities keep their "
                f"fields and their names. Every function keeps its name, its "
                f"parameters and what it does.\n\n"
                f"Everything else on this page is yours: the layout, the copy, "
                f"the animation, the whole design if that is what they asked "
                f"for — including removing a section if they asked for that. "
                f"Only what they did not mention stays exactly as it is.\n\n"
                f"## The COMPLETE current source of {path}\n{before}"
                + (f"\n\n## The components it renders, so you can match "
                   f"them\n{near}" if near else "")
                + (f"\n\n## The layout wrapping this route, and what it renders"
                   f"\nThe navbar, header, footer and page shell live HERE, not "
                   f"in the page — Next composes the layout around it, so the "
                   f"page's own source will not mention them. If what was asked "
                   f"for is one of those, rewrite the file below that actually "
                   f"contains it and leave the page alone.\n\n"
                   f"A layout wraps EVERY route beneath it. Removing a navbar "
                   f"from the root layout removes it from the whole site, which "
                   f"is almost never what one page's request meant. Each file "
                   f"below says how many routes it is on — read that before "
                   f"you touch it.\n\n"
                   f"### Taking chrome off THIS route only\n"
                   f"A nested layout does NOT do it. `app/…/layout.jsx` renders "
                   f"INSIDE the root layout, so anything the root renders is "
                   f"still there — this was the advice here before and it "
                   f"cannot work. What works:\n"
                   f"  1. Move the markup into a small component under "
                   f"`components/` with `'use client'` on line 1.\n"
                   f"  2. In it, `const pathname = usePathname()` from "
                   f"`next/navigation`, and `return null` for the routes it "
                   f"should not appear on.\n"
                   f"  3. Render that component from the layout in place of "
                   f"the markup you moved.\n"
                   f"Do NOT put `'use client'` on the root layout — it exports "
                   f"`metadata` and owns `<html>`/`<body>`, and both stop "
                   f"working in a client component. A nested layout is still "
                   f"the right answer for ADDING chrome to one route.\n\n"
                   f"{chrome}"
                   if chrome else ""))
        convo = [{"role": "system", "content": PAGE_UPDATE_SYSTEM},
                 {"role": "user", "content": user}]

        mark = dev_log_mark()

        writable = {path} | {p for p, _ in chain}
        writable.add("/".join(path.split("/")[:-1]) + "/layout.jsx")
        got, raw = {}, []

        def took(pth, content):

            key = (pth or "").strip().lstrip("./").replace("\\", "/")

            fresh = (key.startswith("components/")
                     and key.endswith((".jsx", ".js"))
                     and key not in arch.files)
            if key not in writable and not fresh:
                elog("WARN", f"   ⛔ ignored a write to {key} — this edit may "
                             f"only touch {', '.join(sorted(writable))}, or a "
                             f"new file under components/")
                return
            if fresh:
                elog("INFO", f"   ➕ {key} — new component for this route's "
                             f"chrome")
            got[key] = content

        parser = FileStreamParser(
            on_text=lambda t: None, on_file_start=lambda pth: None,
            on_file_token=lambda t: None,
            on_file_end=took)

        def feed(tok):
            raw.append(tok)
            parser.feed(tok)

        t0 = time.time()
        try:
            arch._stream(convo, feed, temperature=0.3, timeout=arch.EDIT_TIMEOUT)
        except Exception as e:
            eerr(f"The model failed: {e}")
            return
        parser.close()
        elog("INFO", f"   ⏱ model {time.time() - t0:.1f}s")

        for out in arch.run_requested_commands("".join(raw)):
            elog("INFO", f"   📦 {out.splitlines()[0][:110]}")

        if not got:
            head = " ".join("".join(raw).split())[:300] or "(empty response)"
            elog("WARN", f"   ⚠ no <write_file> block — model said: {head}")
            eerr("The model returned no file")
            return

        olds, keep = {}, {}
        for key, content in got.items():
            was = arch.files.get(key, "")
            why = guard_scope(was, content, designing=True) if was else ""
            if why:
                elog("WARN", f"   ⛔ Rejected {key}: {why[:120]}")
                continue
            olds[key] = was
            keep[key] = content
        if not keep:
            eerr("The rewrite was rejected — nothing was written")
            return

        undo_id = _snapshot(proj_name, list(keep), olds)
        for key, content in keep.items():
            arch.write_file(key, content)
            estream_start(key)
            estream_end(key, content)
            if key != path:
                elog("INFO", f"   📐 {key} — the chrome lives here, not in "
                             f"{path}")
        if undo_id:
            emit({"type": "undo_point", "id": undo_id, "files": list(keep)})
        ephase({"phase": -20, "title": f"Rewriting {route or '/'}",
                "status": "done", "written": len(keep)})
        arch.save_convo()

        eprog("Checking the page…", 75)
        t1 = time.time()
        _fill_missing_images(arch, proj_dir)
        verify_after_edit(arch, proj_dir, proj_name, stack=stack,
                          build_rounds=0, probe=False, analyzer=analyzer)
        _autofix_from_terminal(arch, path, {"route": route}, mark,
                               proj_dir=proj_dir, analyzer=analyzer, model=model)
        elog("INFO", f"   ⏱ verify {time.time() - t1:.1f}s")

        eprog("Done!", 100)
        edone(f"http://localhost:{DEV_PORT}", proj_name,
              preview=_route_of({"route": route}))
    except Exception as e:
        eerr(f"Page update error: {e}")
        log.exception("run_page_update")
    finally:
        stop_model(model)


def run_agent_update(proj_name: str, instruction: str, model: str,
                     think: bool = None):
    """Agentic edit of an existing project — same write_file loop."""
    set_tester_emit(emit)
    try:
        proj_dir = PROD_DIR / proj_name
        if not proj_dir.exists():
            eerr(f"Project not found: {proj_name}")
            return
        if not ensure_model(model):
            eerr(f"Cannot load model: {model}")
            return

        stack = detect_stack(proj_dir)
        elog("INFO", f"✏️  Agent update ({stack}) — {instruction[:70]}")
        eprog("Reading project…", 10)

        if stack == "next":
            MONGO.ensure_running()

        arch = ArchitectAgent(ollama, model, proj_dir, _agent_callbacks(proj_dir),
                              stack=stack,
                              mongo_uri=MONGO.uri_for(proj_name) if stack == "next" else "",
                              db_name=db_name_for(proj_name) if stack == "next" else "",
                              think=think)
        arch.load_existing()
        stack = arch.stack

        eprog("Applying changes…", 35)
        n = arch.update(instruction)
        if not n:
            eerr("Agent made no changes")
            return
        elog("INFO", f"   ✅ {n} file(s) updated")

        arch.save_convo()

        eprog("Verifying…", 80)
        _fill_missing_images(arch, proj_dir)
        res = verify_after_edit(arch, proj_dir, proj_name, stack=stack)
        if res["routes_failed"]:
            elog("WARN", f"   ⚠ {len(res['routes_failed'])} route(s) still "
                         f"failing: {'; '.join(res['routes_failed'][:3])}")

        eprog("Done!", 100)
        edone(f"http://localhost:{DEV_PORT}", proj_name)
    except Exception as e:
        eerr(f"Agent update error: {e}")
        log.exception("Agent update error")
    finally:
        stop_model(model)


SRC_ROOTS = ("app", "components", "lib", "src", "pages")
SKIP_DIRS = {"node_modules", ".next", ".git", "dist", "out", ".vite", ".turbo",
             ".agentforge"}
SRC_EXT = {".js", ".jsx", ".css"}


def _iter_source(proj_dir: Path):
    """Every source file in a project, whatever layout it uses."""
    for root in SRC_ROOTS:
        base = proj_dir / root
        if not base.is_dir():
            continue
        for fp in base.rglob("*"):
            if not fp.is_file() or fp.suffix not in SRC_EXT:
                continue
            if any(s in fp.parts for s in SKIP_DIRS):
                continue
            yield fp


def _deploy_marker(project_dir: Path) -> dict | None:
    """Whether this project was ever deployed, from disk alone.

    Two `is_file()` probes and, for the few that match, a 149-byte read. It has
    to stay that cheap: `list_projects()` runs this per project on every
    `/projects` call. `read_deploy_results()` answers a richer version of the
    same question but makes an HTTP call to the agent and can rewrite the
    project's record, so it must never be reached from here.

    The deleted case is checked FIRST. Teardown moves `deploy/` away to
    `deploy-archive/`, so a torn-down project has no `link.json` and would
    otherwise be indistinguishable from one that was never deployed.

    `state` is deliberately not read out of `link.json`. That file is written
    once when the run is adopted and never rewritten, so a torn-down deployment
    still reads LIVE there for ever — the same trap documented on
    `_deploy_run_state`. What is returned here is a historical fact, "this was
    deployed, to AWS", never a claim that anything is currently running.
    """
    agentforge = project_dir / ".agentforge"
    if (agentforge / "deploy-deleted.json").is_file():
        return {"state": "deleted", "target": ""}
    link = agentforge / "deploy" / "link.json"
    if not link.is_file():
        return None
    try:
        target = str(json.loads(link.read_text(encoding="utf-8")).get("target") or "")
    except Exception:
        target = ""
    return {"state": "deployed", "target": target}


def list_projects() -> list:
    """Return all projects in production-ready/ with metadata."""
    projects = []
    if not PROD_DIR.exists():
        return projects
    for d in sorted(PROD_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):

        if not d.is_dir() or d.name.startswith("."):
            continue
        pkg = d / "package.json"
        title = d.name
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text())
                title = data.get("name", d.name)
            except: pass
        projects.append({
            "name": d.name,
            "title": title,
            "mtime": int(d.stat().st_mtime),
            "file_count": sum(1 for _ in _iter_source(d)),
            "stack": detect_stack(d),

            "unfinished": _unfinished_count(d),

            "deployed": _deploy_marker(d),
        })
    return projects


def _unfinished_count(proj_dir: Path) -> int:
    """
    Planned files with nothing on disk. 0 for a complete or foreign app.

    Each planned path is stat'd directly — no directory walk. The first version
    of this globbed the project for `*.js*` to build a stem set, which walks
    `node_modules`: tens of thousands of files per project, sixteen projects
    per listing, and `/projects` stopped answering at all. The plan already
    says exactly which paths to look for, so there is nothing to search for.

    The `.js` / `.jsx` pair is the one real ambiguity — `write_file`
    canonicalises the extension, so a plan naming `page.js` can be satisfied by
    `page.jsx` — and that is two extra stat calls, not a walk.
    """
    try:
        fp = proj_dir / ".agentforge" / "plan.json"
        if not fp.is_file():
            return 0
        plan = json.loads(fp.read_text(encoding="utf-8"))
        planned = [f.get("path", "") for ph in (plan.get("phases") or [])
                   for f in (ph.get("files") or []) if f.get("path")]
        missing = 0
        for rel in planned:
            rel = rel.lstrip("./")
            stem = re.sub(r"\.jsx?$", "", rel)
            if any((proj_dir / c).is_file()
                   for c in (rel, stem + ".js", stem + ".jsx")):
                continue
            missing += 1
        return missing
    except Exception as e:
        log.debug(f"unfinished count for {proj_dir.name}: {e}")
        return 0


FILE_PRIORITY = [
    "app/page.js", "app/page.jsx", "app/layout.js", "lib/mongodb.js",
    "app/globals.css", "next.config.mjs", "jsconfig.json",
    "src/App.jsx", "src/main.jsx", "src/index.css", "index.html",
    "vite.config.js", "package.json", "tailwind.config.js", "plan.md",
]
MAX_LISTED_FILES = 120
MAX_FILE_BYTES = 256_000


def get_project_files(proj_name: str) -> dict:
    """Read all source files from a project directory, return as {path: content}."""
    proj_dir = PROD_DIR / proj_name
    if not proj_dir.exists():
        return {}

    def add(files: dict, rel: str, fp: Path):
        try:
            if fp.stat().st_size > MAX_FILE_BYTES:
                return
            content = fp.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return
        sz = (f"{len(content)/1024:.1f}KB" if len(content) >= 1024
              else f"{len(content)}B")
        files[rel] = {"content": content, "size": sz}

    files = {}
    for rel in FILE_PRIORITY:
        fp = proj_dir / rel
        if fp.exists() and rel not in files:
            add(files, rel, fp)

    for fp in sorted(_iter_source(proj_dir)):
        if len(files) >= MAX_LISTED_FILES:
            break
        rel = str(fp.relative_to(proj_dir)).replace("\\", "/")
        if rel not in files:
            add(files, rel, fp)

    for sub in ("tests/unit", "tests/e2e"):
        base = proj_dir / sub
        if not base.is_dir():
            continue
        for fp in sorted(base.rglob("*")):
            if len(files) >= MAX_LISTED_FILES:
                break
            if fp.is_file() and fp.suffix in SRC_EXT:
                rel = str(fp.relative_to(proj_dir)).replace("\\", "/")
                if rel not in files:
                    add(files, rel, fp)
    return files


def _decide_targets(update_prompt: str, components: list, codebase_ctx: str,
                    build_model: str) -> list:
    """
    Ask the LLM to decide which existing component(s) to modify — or whether
    a new component is needed. Returns list of component names (strings).
    Uses a tiny, fast call so it doesn't waste tokens.
    """
    import requests as req

    comp_list = ", ".join(components) if components else "(none)"
    prompt = (
        f"A React project has these components: {comp_list}\n\n"
        f"The user wants to: {update_prompt}\n\n"
        f"CODEBASE SUMMARY:\n{codebase_ctx[:1200]}\n\n"
        "Which component(s) must be MODIFIED or CREATED to fulfil the request?\n"
        "Reply with ONLY a JSON array of component names, e.g.: [\"Hero\", \"Navbar\"]\n"
        "Rules:\n"
        "- Use existing names exactly as listed above when modifying\n"
        "- Use a new PascalCase name when a new component is needed\n"
        "- Maximum 3 components per update\n"
        "- Reply with ONLY the JSON array. No explanation."
    )
    try:
        r = req.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model":    build_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream":   False,
                "options":  {"temperature": 0.0, "num_predict": 80},
            },
            timeout=45,
        )
        r.raise_for_status()
        raw = r.json()["message"]["content"].strip()

        m = re.search(r'\[([^\]]+)\]', raw)
        if m:
            names = json.loads(f"[{m.group(1)}]")
            return [n.strip() for n in names if isinstance(n, str) and n.strip()]
    except Exception as e:
        log.warning(f"   _decide_targets failed: {e}")
    return []


def _build_update_prompt(component_name: str, existing_code: str,
                         update_request: str, codebase_ctx: str,
                         is_new: bool) -> str:
    """
    Construct a targeted per-component update prompt.
    This goes through builder._gen() exactly like a fresh generation.
    """
    import textwrap as tw
    if is_new:
        return tw.dedent(f"""\
            Add a NEW component called '{component_name}' to an existing React project.

            USER REQUEST: {update_request}

            EXISTING CODEBASE (for context — imports, styles, data patterns):
            {codebase_ctx[:1500]}

            Requirements:
            - Export default function {component_name}()
            - Match the visual style and color scheme of the existing site
            - framer-motion animations, Tailwind CSS, react-icons/fi
            - Real content matching the request — no placeholder text
            - Outermost div MUST have an explicit dark background class
            - Output ONLY the complete JSX starting with imports
            """)
    else:
        return tw.dedent(f"""\
            Modify the existing '{component_name}' React component as requested.

            USER REQUEST: {update_request}

            EXISTING COMPONENT CODE (modify THIS — keep everything not mentioned in the request):
            {existing_code}

            OTHER FILES FOR CONTEXT (imports, shared styles — do NOT modify these):
            {codebase_ctx[:1200]}

            Requirements:
            - Apply ONLY the changes the user requested — preserve all other functionality
            - Keep the same visual design for parts not mentioned in the request
            - Export default function {component_name}()
            - Follow all JSX rules: hoist regex, hoist divisions, no split components
            - Output ONLY the COMPLETE updated component JSX starting with imports
            """)


def run_update_pipeline(proj_name: str, update_prompt: str, build_model: str):
    """
    Load an existing project, decide which components to change, re-generate
    each one through the standard builder._gen() → _write_one() pipeline,
    then test and fix exactly like a fresh build.
    """
    set_stream_callback(on_token)
    set_tester_emit(emit)

    proj_dir = PROD_DIR / proj_name
    if not proj_dir.exists():
        eerr(f"Project not found: {proj_name}"); return

    try:
        elog("INFO", "━" * 40)
        elog("INFO", f"✏️  Updating: {proj_name}")
        elog("INFO", f"📝 Request: {update_prompt[:80]}")
        elog("INFO", f"🏗️  Model: {build_model}")
        elog("INFO", "━" * 40)

        estep("refine", "active")
        eprog("Loading project…", 5)

        builder = UIBuilder(OLLAMA_URL, build_model, proj_dir)

        file_data = get_project_files(proj_name)
        for rel, info in file_data.items():
            builder.built_files[rel] = info["content"]

            efile(rel, info["size"], info["content"])

        comp_dir   = proj_dir / "src" / "components"
        components = sorted(f.stem for f in comp_dir.glob("*.jsx")) if comp_dir.exists() else []
        elog("INFO", f"   📂 Loaded {len(file_data)} files | Components: {components}")

        estep("refine", "done")
        eprog("Analysing request…", 15)

        if not ensure_model(build_model):
            eerr(f"Cannot load build model: {build_model}"); return

        codebase_ctx = builder._build_codebase_context()

        estep("build", "active")
        eprog("Deciding targets…", 22)

        targets = _decide_targets(update_prompt, components, codebase_ctx, build_model)
        targets = [t for t in targets if re.match(r"^[A-Z][A-Za-z0-9_]*$", t)]

        if not targets:

            for comp in components:
                if comp.lower() in update_prompt.lower():
                    targets = [comp]
                    break
            if not targets and components:

                targets = [max(
                    components,
                    key=lambda c: len(builder.built_files.get(f"src/components/{c}.jsx", ""))
                )]
                elog("WARN", f"   Could not infer target — defaulting to largest component: {targets}")
            elif not targets:
                eerr("No components found in project"); return

        elog("INFO", f"   🎯 Targets: {targets}")

        updated_count = 0
        pct_per_comp  = max(1, 30 // len(targets))

        for i, comp_name in enumerate(targets):
            fpath    = f"src/components/{comp_name}.jsx"
            is_new   = comp_name not in components
            existing = builder.built_files.get(fpath, "")

            if is_new:
                elog("INFO", f"   ➕ Creating new component: {comp_name}")
            else:
                elog("INFO", f"   ✏️  Updating: {fpath}")

            eprog(f"Generating {comp_name}…", 25 + i * pct_per_comp)

            prompt = _build_update_prompt(
                comp_name, existing, update_prompt, codebase_ctx, is_new
            )

            new_code = builder._gen(comp_name, prompt)

            if not new_code:
                elog("WARN", f"   LLM returned nothing for {comp_name} — skipping")
                continue

            builder._write_one(fpath, new_code)
            updated_count += 1
            elog("INFO", f"   ✓ {fpath} written")

            if is_new:
                _inject_component_into_app(builder, proj_dir, comp_name)

        if updated_count == 0:
            eerr("No components were updated — LLM may have failed to generate valid JSX")
            return

        stop_model(build_model)

        estep("build", "done")
        eprog("Components updated", 58)
        elog("INFO", f"   ✅ {updated_count}/{len(targets)} component(s) updated")

        estep("serve", "active")
        eprog("Restarting Vite…", 65)
        elog("INFO", "🌐 Restarting Vite…")
        if not ensure_node_deps(proj_dir):
            eerr("Dependency install failed")
            return
        start_vite(proj_dir)
        wait_for_vite(35)

        estep("test", "active")
        eprog("Testing…", 75)
        elog("INFO", "🧪 Testing updated build…")
        emit({"type": "test_start"})

        tester = TesterAgent(proj_dir, DEV_PORT)
        npm_errors = ""

        for attempt in range(1, MAX_FIX + 2):
            elog("INFO", f"   🔬 Test run #{attempt}")
            emit({"type": "test_run", "attempt": attempt})

            errors = tester.test()

            if not errors:
                elog("INFO", "   🎉 All tests passed!")
                estep("test", "done")
                break

            if attempt > MAX_FIX:
                elog("WARN", f"   ⚠ Max fix attempts reached — applying safe fallbacks")
                from agents.builder import _safe_component
                for fpath_s, src in list(builder.built_files.items()):
                    if not (fpath_s.startswith("src/components/") and fpath_s.endswith(".jsx")):
                        continue
                    comp_name_s = fpath_s.split("/")[-1].replace(".jsx", "")
                    if len(src.strip()) < 400 or npm_errors.strip():
                        safe = _safe_component(comp_name_s)
                        (proj_dir / fpath_s).write_text(safe, encoding="utf-8")
                        builder.built_files[fpath_s] = safe
                        elog("WARN", f"   🛟 Safe fallback → {fpath_s}")
                estep("test", "done")
                break

            npm_errors = builder._npm_build_errors()
            vs_errors  = vite_stderr()
            all_errors = "\n".join(errors) + "\n" + npm_errors + "\n" + vs_errors

            elog("INFO", f"   📋 npm build:\n{npm_errors[:250] or '  (none)'}")
            emit({"type": "test_fixing", "attempt": attempt, "errors": errors[:5]})
            elog("INFO", f"   🔧 Fixing attempt {attempt}/{MAX_FIX}…")

            if not ensure_model(build_model):
                elog("WARN", "   Cannot reload build model — skipping fix")
                break

            builder.fix_with_errors(all_errors)
            stop_model(build_model)

            elog("INFO", "   🔄 Restarting Vite after fix…")
            if not ensure_node_deps(proj_dir):
                eerr("Dependency install failed")
                return
            start_vite(proj_dir)
            wait_for_vite(35)

        url = f"http://localhost:{DEV_PORT}"
        estep("serve", "done")
        eprog("Done!", 100)
        elog("INFO", f"🎉 Updated → {url}")
        edone(url, proj_name)

    except Exception as e:
        eerr(f"Update error: {e}")
        log.exception("Update pipeline error")
    finally:
        set_stream_callback(None)


def _inject_component_into_app(builder, proj_dir: Path, comp_name: str):
    """
    When a new component is created, add it to App.jsx so it renders.
    Adds an import line and a <CompName /> tag inside the main div.
    Only modifies App.jsx — safe no-op if the component is already referenced.
    """
    app_path = proj_dir / "src" / "App.jsx"
    if not app_path.exists():
        return

    app_code = app_path.read_text(encoding="utf-8")

    if f"import {comp_name}" in app_code:
        return

    try:

        last_import = max(
            (i for i, l in enumerate(app_code.splitlines()) if l.strip().startswith("import")),
            default=0
        )
        lines = app_code.splitlines()
        lines.insert(last_import + 1, f"import {comp_name} from './components/{comp_name}'")

        new_app = "\n".join(lines)

        insert_tag = f"      <{comp_name} />\n"
        last_div   = new_app.rfind("</div>")
        if last_div != -1:
            new_app = new_app[:last_div] + insert_tag + new_app[last_div:]

        app_path.write_text(new_app, encoding="utf-8")
        builder.built_files["src/App.jsx"] = new_app
        sz = f"{len(new_app)//1024:.1f}KB" if len(new_app) >= 1024 else f"{len(new_app)}B"
        efile("src/App.jsx", sz, new_app)
        log.info(f"   ✓ Injected {comp_name} into App.jsx")
    except Exception as e:
        log.warning(f"   _inject_component_into_app failed: {e}")


async def ws_handler(websocket, path=None):
    clients.add(websocket)
    log.info(f"WS connected ({len(clients)})")
    try:
        await websocket.send(json.dumps({
            "type": "log", "level": "INFO",
            "text": "✅ WebForge connected — enter a prompt and click Build"
        }))
        async for raw in websocket:
            try:
                msg = json.loads(raw)
                if msg.get("type") == "build":
                    p  = msg.get("prompt", "").strip()
                    rm = msg.get("refine_model", DEFAULT_REFINE)
                    bm = msg.get("build_model",  DEFAULT_BUILD)
                    if p:
                        threading.Thread(
                            target=run_pipeline, args=(p, rm, bm), daemon=True
                        ).start()
                elif msg.get("type") == "agent_build":
                    p  = msg.get("prompt", "").strip()
                    am = msg.get("model") or default_agent_model()
                    th = _think_flag(msg)
                    qm = (msg.get("qa_model") or "").strip()
                    if p:
                        threading.Thread(
                            target=run_agent_pipeline,
                            args=(p, am, th, qm, "",
                                  str(msg.get("logo", "")).strip(),
                                  str(msg.get("srs_id", "")).strip()),
                            daemon=True).start()
                elif msg.get("type") == "agent_resume":
                    proj = msg.get("project", "").strip()
                    am = msg.get("model") or default_agent_model()
                    if proj:
                        threading.Thread(
                            target=run_agent_pipeline,
                            args=("", am, _think_flag(msg),
                                  (msg.get("qa_model") or "").strip(), proj),
                            daemon=True).start()
                elif msg.get("type") == "chat":
                    proj = msg.get("project", "").strip()
                    p    = msg.get("prompt", "").strip()
                    am   = msg.get("model") or default_agent_model()
                    if proj and p:
                        threading.Thread(
                            target=run_chat,
                            args=(proj, p, am, (msg.get("route") or "").strip(),
                                  _think_flag(msg),
                                  (msg.get("qa_model") or "").strip()),
                            daemon=True).start()
                elif msg.get("type") == "agent_update":
                    proj = msg.get("project", "").strip()
                    p    = msg.get("prompt", "").strip()
                    am   = msg.get("model") or default_agent_model()
                    rt   = (msg.get("route") or "").strip()
                    if proj and p:

                        threading.Thread(
                            target=(run_page_update if rt else run_agent_update),
                            args=((proj, p, am, rt, _think_flag(msg)) if rt
                                  else (proj, p, am, _think_flag(msg))),
                            daemon=True).start()
                elif msg.get("type") == "pencil_edit":
                    proj = msg.get("project", "").strip()
                    p    = msg.get("prompt", "").strip()
                    am   = msg.get("model") or default_agent_model()
                    if proj and p:
                        threading.Thread(
                            target=run_pencil_edit,
                            args=(proj, p, msg, am, _think_flag(msg)),
                            daemon=True).start()
                elif msg.get("type") == "element_edit":
                    proj = msg.get("project", "").strip()
                    p    = msg.get("prompt", "").strip()
                    am   = msg.get("model") or default_agent_model()
                    if proj and p:
                        threading.Thread(
                            target=run_element_edit,
                            args=(proj, p, msg.get("element") or {}, am,
                                  _think_flag(msg)),
                            daemon=True).start()
                elif msg.get("type") == "image_edit":
                    proj = msg.get("project", "").strip()
                    p    = msg.get("prompt", "").strip()
                    am   = msg.get("model") or default_agent_model()
                    if proj and p:
                        threading.Thread(
                            target=run_image_edit,
                            args=(proj, p, msg.get("element") or {}, am,
                                  _think_flag(msg)),
                            daemon=True).start()
                elif msg.get("type") == "feature":
                    proj = msg.get("project", "").strip()
                    p    = msg.get("prompt", "").strip()
                    am   = msg.get("model") or default_agent_model()
                    if proj and p:
                        threading.Thread(
                            target=run_feature,
                            args=(proj, p, am, _think_flag(msg),
                                  (msg.get("qa_model") or "").strip()),
                            daemon=True).start()
                elif msg.get("type") == "update":
                    proj = msg.get("project", "").strip()
                    p    = msg.get("prompt", "").strip()
                    bm   = msg.get("build_model", DEFAULT_BUILD)
                    if proj and p:
                        threading.Thread(
                            target=run_update_pipeline, args=(proj, p, bm), daemon=True
                        ).start()
            except json.JSONDecodeError: pass
    except websockets.exceptions.ConnectionClosed: pass
    finally:
        clients.discard(websocket)
        log.info(f"WS disconnected ({len(clients)})")


HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate",
              "proxy-authorization", "te", "trailer", "trailers",
              "transfer-encoding", "upgrade"}


LOCODE_PREFIX = "/__agentforge"


class _UIServer(ThreadingHTTPServer):
    """
    ThreadingHTTPServer that does not shout when a browser hangs up.

    Every verification stops the dev server, builds, and starts it again. The
    UI's iframe keeps requesting through the proxy the whole time, and each
    request that is cut off mid-write raises WinError 10053/10054 out of
    `wfile.write`. The default `handle_error` prints a full traceback per
    request: one measured feature run produced 424 of them, which buried the
    build's own output and is the reason a log had to be grepped to find out
    what happened.

    A dropped client connection is not an error anyone can act on, so it is
    logged at debug. Anything else still gets the traceback it deserves.
    """

    daemon_threads = True

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionAbortedError, ConnectionResetError,
                            BrokenPipeError, TimeoutError)):
            log.debug(f"client went away: {type(exc).__name__}")
            return
        super().handle_error(request, client_address)


class UIHandler(SimpleHTTPRequestHandler):

    protocol_version = "HTTP/1.1"

    def __init__(self, *a, **k):
        self._no_cache = False

        super().__init__(*a, directory=str(BASE_DIR), **k)

    def log_message(self, *a): pass

    def end_headers(self):

        if self._no_cache:
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self._no_cache = False
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _json(self, payload, code=200):
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _split(self):
        """(is_ours, path_without_the_prefix). See LOCODE_PREFIX."""
        path = urlsplit(self.path).path
        if path == LOCODE_PREFIX or path.startswith(LOCODE_PREFIX + "/"):
            return True, path[len(LOCODE_PREFIX):] or "/"
        return False, path

    def _is_websocket(self) -> bool:
        return ("upgrade" in self.headers.get("Connection", "").lower()
                and self.headers.get("Upgrade", "").lower() == "websocket")

    def do_GET(self):
        ours, path = self._split()
        if not ours:
            if self._is_websocket():
                return self._proxy_websocket()

            if path == "/" and self.headers.get("Sec-Fetch-Dest") == "document":
                self.send_response(302)
                self.send_header("Location", LOCODE_PREFIX + "/")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            return self._proxy("GET")
        if path.startswith("/api/"):
            return self._guarded(self._api_get, path[4:])
        return self._serve_ui(path)

    def do_HEAD(self):
        ours, path = self._split()
        if not ours:
            return self._proxy("HEAD")

        del path
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_PUT(self):     self._proxy_or_405("PUT")
    def do_PATCH(self):   self._proxy_or_405("PATCH")
    def do_DELETE(self):  self._proxy_or_405("DELETE")

    def _proxy_or_405(self, method):
        ours, _ = self._split()
        if ours:
            return self._json({"error": "method not allowed"}, 405)
        self._proxy(method)

    def _serve_ui(self, path):
        """There is no UI on this port any more — say so, and point at the one.

        This used to serve a single-file HTML app out of `ui/`, which the
        Electron shell loaded. Both are gone: the studio is the UI, it runs on
        its own port, and it reaches this server only for `/__agentforge/api/*`.

        A bare 404 here would be technically correct and completely unhelpful —
        the address still looks like the application's, so anyone who lands on
        it deserves to be told where the application went.
        """
        del path
        body = (
            "<!doctype html><meta charset=utf-8>"
            "<title>AgentForge</title>"
            "<body style=\"font:14px/1.6 system-ui;max-width:34rem;margin:12vh auto;"
            "padding:0 1.5rem;color:#e6e6e6;background:#111\">"
            "<h1 style=\"font-size:1.1rem\">AgentForge is not served on this port</h1>"
            f"<p>This is the backend API on :{UI_PORT}. The studio runs separately —"
            " <a style=\"color:#22d3ee\" href=\"http://localhost:3000/__agentforge\">"
            "http://localhost:3000/__agentforge</a></p>"
            "<p style=\"color:#888\">Start both with <code>start.bat</code>.</p>"
        ).encode()
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _api_get(self, path):

        if path.startswith("/srs/"):
            return self._proxy_srs("GET", path[4:])
        if path == "/srs-status":
            return self._json(srs_status())

        if path.startswith("/jobs/"):
            return self._json(job_poll(path[len("/jobs/"):]))

        if path.startswith("/deploy/jobs/"):
            try:
                return self._json(deploy_job_poll(path[13:].strip("/")))
            except KeyError as e:
                return self._json({"error": str(e)}, 404)
        if path.startswith("/deploy/"):
            return self._proxy_deploy("GET", "/api" + path[7:])
        if path == "/deploy-status":
            return self._json(deploy_status())
        if path.startswith("/deploy-results/"):
            return self._json(read_deploy_results(path[16:].strip("/")))
        if path == "/projects":
            self._json(list_projects())
        elif path == "/image-check":

            agent = image_agent()
            host = agent.base_url()

            import socket
            lan = ""
            if load_settings().get("lan_access"):
                try:
                    lan = f"http://{socket.gethostbyname(socket.gethostname())}:{UI_PORT}"
                except OSError:
                    lan = ""
            self._json({"enabled": agent.enabled, "available": bool(host),
                        "host": host or "", "lan_url": lan,
                        "lan_access": bool(load_settings().get("lan_access"))})
        elif path == "/models":

            self._json(ollama.catalog())
        elif path == "/settings":
            s = load_settings()
            key = ollama.api_key
            uri = str(s.get("mongodb_uri", "")).strip()
            self._json({
                "ollama_host": ollama.host,
                "cloud_enabled": bool(key),

                "api_key_hint": (f"…{key[-4:]}" if key else ""),
                "local_num_ctx": s.get("local_num_ctx", max_context("llama3.1:8b")),
                "agent_model": s.get("agent_model", default_agent_model()),
                **_image_settings(),
                "mongodb_uri_set": bool(uri),
                "mongodb_uri_hint": _redact_uri(uri),
                "mongo": MONGO.status(),

                "deploy": deploy_settings_summary(),
            })
        elif path == "/mongo":
            self._json(MONGO.status())
        elif path.startswith("/files/"):
            self._json(get_project_files(path[7:].strip("/")))
        elif path.startswith("/qa/"):
            self._json(read_qa_results(path[4:].strip("/")))
        elif path.startswith("/srs-results/"):
            self._json(read_srs_results(path[13:].strip("/")))
        elif path.startswith("/qa-pdf/"):

            # Rendered on request rather than written by the QA stage: the
            # testing tab keeps changing as tests are repaired and re-run, and
            # a PDF written once at the end of the build would be stale the
            # first time somebody fixes a test.
            proj = path[8:].strip("/")
            qa = read_qa_results(proj)
            if qa.get("error"):
                return self._json(qa, 404)
            try:
                from qa_agent.report_pdf import build_qa_pdf
                out = (PROD_DIR / proj / ".agentforge" / "qa"
                       / "Test_Report.pdf")
                build_qa_pdf(qa, out, project=proj)
                self._plain(200, out.read_bytes(), "application/pdf",
                            extra=(("Content-Disposition",
                                    f'attachment; filename="{proj}-test-report.pdf"'),))
            except Exception as e:                              # noqa: BLE001
                log.exception("qa pdf")
                self._json({"error": f"the test report could not be built: {e}"}, 500)
        elif path.startswith("/srs-pdf/"):

            pdf = (PROD_DIR / path[9:].strip("/") / ".agentforge" / "srs"
                   / "SRS_latest.pdf")
            if pdf.is_file():
                self._plain(200, pdf.read_bytes(), "application/pdf",
                            extra=(("Content-Disposition",
                                    'inline; filename="SRS.pdf"'),))
            else:
                self._json({"error": "no SRS PDF for this project"}, 404)
        else:
            self._json({"error": f"unknown endpoint {path}"}, 404)

    def do_POST(self):
        ours, path = self._split()
        if not ours:
            return self._proxy("POST")

        length = int(self.headers.get("Content-Length", 0) or 0)
        self._raw = self.rfile.read(length) if length else b""
        if not path.startswith("/api/"):
            return self._json({"error": "not found"}, 404)
        self._guarded(self._api_post, path[4:])

    def _guarded(self, fn, path):
        """
        Run an API branch and turn a crash into an answer.

        Without this, an exception anywhere in a handler unwinds into
        `BaseHTTPRequestHandler`, which sends a 500 with an EMPTY body. The
        browser shows "HTTP 500" and that is the entire diagnosis available to
        anybody — measured on the logo panel, where a failed draw said exactly
        that and nothing else, on a machine where the image host had been up
        thirty seconds earlier.

        The traceback goes to the log and the message goes to the caller. An
        API that falls over should still be able to say what it fell over.
        """
        try:
            fn(path)
        except Exception as e:
            log.exception(f"api {path}")
            elog("WARN", f"   ⚠ {path} failed: {type(e).__name__}: {e}")
            try:
                self._json({"error": f"{type(e).__name__}: {e}"}, 500)
            except Exception:
                pass

    _raw = b""

    def _body(self) -> dict:
        if not self._raw:
            return {}
        try:
            return json.loads(self._raw)
        except Exception:
            return {}

    def _api_post(self, path):

        if path.startswith("/srs/"):
            return self._proxy_srs("POST", path[4:])

        if path == "/jobs":
            body = self._body()
            try:
                return self._json(job_start(
                    str(body.get("method", "POST")).upper(),
                    str(body.get("path", "")),
                    body.get("body") or {}))
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
        if path == "/deploy/jobs":
            body = self._body()
            try:
                return self._json(deploy_job_start(
                    str(body.get("method", "POST")).upper(),
                    "/api" + str(body.get("path", "")),
                    body.get("body") or {}))
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
        if path.startswith("/deploy/"):
            return self._proxy_deploy("POST", "/api" + path[7:])
        if path == "/deploy-start":
            body = self._body()
            try:
                return self._json(start_deployment(
                    str(body.get("project", "")).strip(),
                    str(body.get("target", "vercel")).strip(),
                    body))
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
        if path == "/build":
            body = self._body()
            threading.Thread(
                target=run_pipeline,
                args=(body.get("prompt",""),
                      body.get("refine_model", DEFAULT_REFINE),
                      body.get("build_model",  DEFAULT_BUILD)),
                daemon=True
            ).start()
            self._json({"ok": True})
        elif path == "/resume":
            body = self._body()
            threading.Thread(
                target=run_agent_pipeline,
                args=("", body.get("model") or default_agent_model(),
                      _think_flag(body),
                      (body.get("qa_model") or "").strip(),
                      body.get("project", "").strip()),
                daemon=True
            ).start()
            self._json({"ok": True})
        elif path == "/logo-prompt":

            body = self._body()
            idea = str(body.get("prompt", "")).strip()
            if not idea:
                return self._json({"error": "prompt is required"}, 400)
            model = (body.get("model") or default_agent_model()).strip()
            try:
                r = ollama.chat(model, [
                    {"role": "system", "content": LOGO_PROMPT_SYSTEM},
                    {"role": "user", "content": idea[:1200]},
                ], options={"temperature": 0.7}, timeout=120)
                text = ((r.get("message") or {}).get("content") or "").strip()

                text = text.splitlines()[-1].strip().strip('"').strip("'")
            except Exception as e:
                log.debug(f"logo prompt: {e}")
                text = ""
            self._json({"ok": True, "prompt": text})
        elif path == "/image":

            body = self._body()
            prompt = str(body.get("prompt", "")).strip()
            if not prompt:
                return self._json({"error": "prompt is required"}, 400)
            agent = image_agent()
            if not agent.enabled:
                return self._json({"error": "image generation is switched off"}, 409)
            if not agent.available():
                return self._json(
                    {"error": "no Fooocus is answering — start it, or set "
                              "image_host to the machine that runs it"}, 503)
            name = str(body.get("name", "")) or agent.slug(prompt)
            proj = str(body.get("project", "")).strip()
            out = ((PROD_DIR / proj / "public" / "generated") if proj
                   else (LOGS_DIR / "images")) / f"{name}.png"
            ok = agent.generate(prompt, out,
                                aspect=str(body.get("aspect", "landscape")),
                                seed=int(body.get("seed", 0) or 0),
                                force=bool(body.get("force")))
            if not ok:
                return self._json({"error": "generation failed"}, 502)

            self._json({"ok": True, "file": str(out), "name": name,
                        "data_uri": preview_uri(out),
                        "url": (f"/generated/{name}.png" if proj else "")})
        elif path == "/image-upload":

            # The same contract as /image, with a file instead of a prompt: the
            # caller cannot tell which one drew the picture, so "upload my own"
            # needs no second path through the logo screen or the build.
            #
            # Unlike /image this needs no Fooocus, which is the point — it is
            # what somebody uses when the generator is off, unreachable, or has
            # simply not produced the mark they already own.
            body = self._body()
            name = _safe_stem(body.get("name") or body.get("filename"), "upload")
            proj = _safe_stem(body.get("project", ""), "")
            out = ((PROD_DIR / proj / "public" / "generated") if proj
                   else (LOGS_DIR / "images")) / f"{name}.png"

            why = save_uploaded_image(body.get("data_base64", ""), out)
            if why:
                return self._json({"error": why}, 400)

            self._json({"ok": True, "file": str(out), "name": name,
                        "data_uri": preview_uri(out),
                        "url": (f"/generated/{name}.png" if proj else "")})
        elif path == "/agent-build":
            body = self._body()
            threading.Thread(
                target=run_agent_pipeline,
                args=(body.get("prompt", ""),
                      body.get("model") or default_agent_model(),
                      _think_flag(body),
                      (body.get("qa_model") or "").strip(),
                      "", str(body.get("logo", "")).strip(),
                      str(body.get("srs_id", "")).strip()),
                daemon=True
            ).start()
            self._json({"ok": True})
        elif path == "/pencil-edit":
            body = self._body()
            threading.Thread(
                target=run_pencil_edit,
                args=(body.get("project", ""), body.get("prompt", ""), body,
                      body.get("model") or default_agent_model(),
                      _think_flag(body)),
                daemon=True
            ).start()
            self._json({"ok": True})
        elif path == "/element-edit":
            body = self._body()
            threading.Thread(
                target=run_element_edit,
                args=(body.get("project", ""), body.get("prompt", ""),
                      body.get("element") or {},
                      body.get("model") or default_agent_model(),
                      _think_flag(body)),
                daemon=True
            ).start()
            self._json({"ok": True})
        elif path == "/image-edit":

            body = self._body()
            threading.Thread(
                target=run_image_edit,
                args=(body.get("project", ""), body.get("prompt", ""),
                      body.get("element") or {},
                      body.get("model") or default_agent_model(),
                      _think_flag(body)),
                daemon=True
            ).start()
            self._json({"ok": True})
        elif path == "/attach":

            # Read a file for one of the editing chats. The answer is text the
            # browser folds into its prompt, so the selection, section and
            # feature tools each gain attachments without any of them changing.
            body = self._body()
            proj = _safe_stem(body.get("project", ""), "")
            proj_dir = (PROD_DIR / proj) if proj and (PROD_DIR / proj).is_dir() else None
            got = read_attachment(str(body.get("filename", "")),
                                  body.get("data_base64", ""), proj_dir)
            text = got["text"][:ATTACH_TEXT_CAP]
            if len(got["text"]) > ATTACH_TEXT_CAP:
                text += "\n… (the rest was left out to keep the prompt workable)"
            got["text"] = text
            self._json({"ok": True, **got})
        elif path == "/image-swap":

            # HTTP, not the websocket the other edit tools use: this carries a
            # file, and a multi-megabyte base64 frame is not what that socket is
            # for. The work still runs in a thread and reports over the socket,
            # so the log, the phases and the undo point arrive exactly as they
            # do for every other edit.
            body = self._body()
            threading.Thread(
                target=run_image_swap,
                args=(body.get("project", ""), body.get("data_base64", ""),
                      body.get("filename", ""), body.get("element") or {}),
                daemon=True
            ).start()
            self._json({"ok": True})
        elif path == "/undo":
            body = self._body()
            self._json(restore_snapshot(body.get("project", ""),
                                        body.get("id", "")))
        elif path == "/feature":
            body = self._body()
            threading.Thread(
                target=run_feature,
                args=(body.get("project", ""),
                      body.get("prompt", ""),
                      body.get("model") or default_agent_model(),
                      _think_flag(body),
                      (body.get("qa_model") or "").strip()),
                daemon=True
            ).start()
            self._json({"ok": True})
        elif path == "/agent-update":
            body = self._body()
            threading.Thread(
                target=(run_page_update if (body.get("route") or "").strip()
                        else run_agent_update),
                args=((body.get("project", ""), body.get("prompt", ""),
                       body.get("model") or default_agent_model(),
                       (body.get("route") or "").strip(), _think_flag(body))
                      if (body.get("route") or "").strip() else
                      (body.get("project", ""), body.get("prompt", ""),
                       body.get("model") or default_agent_model(),
                       _think_flag(body))),
                daemon=True
            ).start()
            self._json({"ok": True})
        elif path.startswith("/open/"):
            proj = path[6:].strip("/")
            threading.Thread(target=_open_project, args=(proj,), daemon=True).start()
            self._json({"ok": True})
        elif path == "/mongo/prefetch":
            threading.Thread(target=MONGO.prefetch, daemon=True).start()
            self._json({"ok": True})
        elif path == "/settings":
            body = self._body()
            patch = {}
            if "ollama_api_key" in body:
                patch["ollama_api_key"] = str(body["ollama_api_key"]).strip()
            if "mongodb_uri" in body:
                patch["mongodb_uri"] = str(body["mongodb_uri"]).strip()
            if body.get("ollama_host"):
                patch["ollama_host"] = str(body["ollama_host"]).strip()
            if "lan_access" in body:
                patch["lan_access"] = bool(body["lan_access"])
            if "image_enabled" in body:
                patch["image_enabled"] = bool(body["image_enabled"])
            if "image_host" in body:
                patch["image_host"] = str(body["image_host"]).strip()
            if "image_config" in body:
                patch["image_config"] = str(body["image_config"]).strip()
            if body.get("local_num_ctx"):
                try:
                    patch["local_num_ctx"] = max(4096, int(body["local_num_ctx"]))
                except (TypeError, ValueError):
                    pass
            if body.get("agent_model"):
                patch["agent_model"] = str(body["agent_model"]).strip()

            if "srs_model" in body:
                patch["srs_model"] = str(body["srs_model"]).strip()

            if "deploy_model" in body:
                patch["deploy_model"] = str(body["deploy_model"]).strip()
            for key in ("aws_profile", "aws_region", "aws_start_url",
                        "aws_sso_region"):
                if key in body:
                    patch[key] = str(body[key]).strip()
            if "vercel_token" in body:
                v = str(body["vercel_token"]).strip()
                patch["vercel_token"] = "" if v == "-" else v
            if "deploy_mongodb_uri" in body:
                v = str(body["deploy_mongodb_uri"]).strip()
                patch["deploy_mongodb_uri"] = "" if v == "-" else v
            ok = save_settings(patch)
            if patch.get("ollama_host"):
                ollama.host = patch["ollama_host"].rstrip("/")
            self._json({"ok": ok, "cloud_enabled": bool(ollama.api_key),
                        "cloud_reachable": ollama.cloud_reachable()
                        if ollama.api_key else False})
        elif path == "/upload-project":
            body = self._body()
            name = body.get("name", "imported")
            files = body.get("files", {})

            pname = re.sub(r"[^a-z0-9]", "", name.lower())[:20] or "imported"
            proj_dir = PROD_DIR / pname
            proj_dir.mkdir(parents=True, exist_ok=True)

            for rel_path, content in files.items():
                fp = proj_dir / rel_path
                fp.parent.mkdir(parents=True, exist_ok=True)
                try:
                    fp.write_text(content, encoding="utf-8")
                except Exception as e:
                    log.error(f"Failed to write {rel_path}: {e}")

            self._json({"ok": True, "project": pname})
        elif path == "/update":
            body = self._body()
            threading.Thread(
                target=run_update_pipeline,
                args=(body.get("project",""),
                      body.get("prompt",""),
                      body.get("build_model", DEFAULT_BUILD)),
                daemon=True
            ).start()
            self._json({"ok": True})
        else:
            self._json({"error": f"unknown endpoint {path}"}, 404)

    def _proxy(self, method: str):
        url = f"http://127.0.0.1:{DEV_PORT}{self.path}"
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length and self.headers.get("Transfer-Encoding"):
            return self._plain(411, b"chunked request bodies are not proxied")
        body = self.rfile.read(length) if length else None

        headers = {k: v for k, v in self.headers.items()
                   if k.lower() not in HOP_BY_HOP}

        headers["X-Forwarded-Host"] = self.headers.get("Host", "")
        headers["X-Forwarded-Proto"] = "http"
        headers["X-Forwarded-For"] = "127.0.0.1"
        headers["Accept-Encoding"] = "identity"

        try:
            r = requests.request(method, url, headers=headers, data=body,
                                 stream=True, allow_redirects=False,
                                 timeout=(2, 300))
        except requests.RequestException:
            return self._preview_unavailable()

        self.send_response(r.status_code)
        upstream_length = None

        for k, v in r.raw.headers.items():
            kl = k.lower()
            if kl in HOP_BY_HOP or kl == "content-encoding":
                continue
            if kl == "content-length":
                upstream_length = v
            if kl == "set-cookie":
                v = re.sub(r";\s*Secure", "", v, flags=re.I)
            self.send_header(k, v)
        if upstream_length is None:

            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()

        if method == "HEAD":
            return
        try:
            for chunk in r.raw.stream(65536, decode_content=False):
                self.wfile.write(chunk)
        except Exception:
            self.close_connection = True

    def _proxy_srs(self, method: str, path: str):
        """
        Hand this request to the SRS agent on SRS_PORT.

        A near-copy of _proxy rather than a flag on it, because the two differ
        in the one place that decides whether this works at all: _proxy reads
        with a 300s timeout, and both an SRS generation and the event stream
        outlive that. A read timeout here does not slow anything down — it cuts
        the interview off mid-answer.

        `path` arrives with the /api and /srs prefixes already stripped, and
        without its query string: _split() drops it, so it is put back here.
        """
        if SRS_API["state"] in ("off", "import-failed"):
            return self._json({"error": "the SRS agent is not running",
                               "srs": srs_status()}, 503)

        query = urlsplit(self.path).query
        url = f"http://127.0.0.1:{SRS_PORT}{path}" + (f"?{query}" if query else "")

        body = self._raw or None
        headers = {k: v for k, v in self.headers.items()
                   if k.lower() not in HOP_BY_HOP}
        headers["Accept-Encoding"] = "identity"

        try:
            r = requests.request(method, url, headers=headers, data=body,
                                 stream=True, allow_redirects=False,

                                 timeout=(2, None))
        except requests.RequestException as e:
            return self._json({"error": f"SRS agent unreachable: {e}",
                               "srs": srs_status()}, 502)

        self.send_response(r.status_code)
        upstream_length = None
        for k, v in r.raw.headers.items():
            kl = k.lower()
            if kl in HOP_BY_HOP or kl == "content-encoding":
                continue
            if kl == "content-length":
                upstream_length = v
            self.send_header(k, v)

        self.send_header("Access-Control-Allow-Origin", "*")
        if upstream_length is None:

            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()

        try:
            for chunk in r.raw.stream(65536, decode_content=False):
                self.wfile.write(chunk)
        except Exception:
            self.close_connection = True

    def _proxy_deploy(self, method: str, path: str):
        """
        Hand this request to the deployment agent on DEPLOY_PORT.

        `path` arrives as the studio wrote it, with `/deploy` stripped — every
        route on that agent lives under `/api/`, so `/deploy/runs` becomes
        `/api/runs` here rather than making the studio say `/deploy/api/runs`.

        Same read timeout as _proxy_srs, and for the same reason: a read
        deadline here would not slow anything down, it would cut off a
        deployment mid-flight.
        """
        if DEPLOY_API["state"] in ("off", "import-failed"):
            return self._json({"error": "the deployment agent is not running",
                               "deploy": deploy_status()}, 503)

        query = urlsplit(self.path).query
        url = (f"http://127.0.0.1:{DEPLOY_PORT}{path}"
               + (f"?{query}" if query else ""))

        body = self._raw or None
        headers = {k: v for k, v in self.headers.items()
                   if k.lower() not in HOP_BY_HOP}
        headers["Accept-Encoding"] = "identity"

        try:
            r = requests.request(method, url, headers=headers, data=body,
                                 stream=True, allow_redirects=False,
                                 timeout=(2, None))
        except requests.RequestException as e:
            return self._json({"error": f"deployment agent unreachable: {e}",
                               "deploy": deploy_status()}, 502)

        self.send_response(r.status_code)
        upstream_length = None
        for k, v in r.raw.headers.items():
            kl = k.lower()
            if kl in HOP_BY_HOP or kl == "content-encoding":
                continue
            if kl == "content-length":
                upstream_length = v
            self.send_header(k, v)
        if upstream_length is None:
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()

        if method == "HEAD":
            return
        try:
            for chunk in r.raw.stream(65536, decode_content=False):
                self.wfile.write(chunk)
        except Exception:
            self.close_connection = True

    def _plain(self, code, body: bytes, ctype="text/plain; charset=utf-8",
               extra=()):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _preview_unavailable(self):
        """The dev server is not up. Documents get a page; assets fail fast."""
        dest = self.headers.get("Sec-Fetch-Dest", "")
        wants_page = (dest in ("document", "iframe")
                      or "text/html" in self.headers.get("Accept", ""))
        if not wants_page:

            return self._plain(502, b"")
        page = (b"<!doctype html><meta charset=utf-8>"
                b"<title>Preview not running</title>"
                b"<style>body{font:14px system-ui;background:#0b0d10;color:#8b949e;"
                b"display:grid;place-items:center;height:100vh;margin:0}"
                b"b{color:#e6edf3;font-weight:600}</style>"
                b"<div style=text-align:center><p><b>Preview not running</b>"
                b"<p>Waiting for the dev server\xe2\x80\xa6"
                b"<p><button onclick=location.reload() style=\"font:inherit;"
                b"padding:6px 14px;border-radius:6px;border:1px solid #30363d;"
                b"background:#161b22;color:#e6edf3;cursor:pointer\">Retry</button>"
                b"</div><script>setTimeout(()=>location.reload(),2000)</script>")
        self._plain(503, page, "text/html; charset=utf-8",
                    extra=(("Retry-After", "2"), ("Cache-Control", "no-store")))

    def _proxy_websocket(self):
        """
        Relay the HMR socket byte for byte.

        Dropping it would force a full iframe reload after every element or
        pencil edit, throwing away scroll position, form state and the
        logged-in view — exactly the state those tools operate on.
        """
        try:
            up = socket.create_connection(("127.0.0.1", DEV_PORT), timeout=5)
        except OSError:
            self.close_connection = True
            try:
                self.wfile.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            except Exception:
                pass
            return

        self.close_connection = True
        try:
            head = f"{self.command} {self.path} HTTP/1.1\r\n".encode()
            for k, v in self.headers.items():
                head += f"{k}: {v}\r\n".encode()
            up.sendall(head + b"\r\n")

            self.connection.settimeout(None)
            up.settimeout(None)

            def pump_down():
                try:
                    while True:
                        data = up.recv(65536)
                        if not data:
                            break
                        self.wfile.write(data)
                        self.wfile.flush()
                except Exception:
                    pass
                finally:
                    try:
                        self.connection.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass

            t = threading.Thread(target=pump_down, daemon=True)
            t.start()
            while True:

                data = self.rfile.read1(65536)
                if not data:
                    break
                up.sendall(data)
        except Exception:
            pass
        finally:
            try:
                up.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            up.close()


SRS_API = {"state": "off", "port": SRS_PORT, "error": ""}


def start_srs_api():
    """
    Run the SRS agent's FastAPI app. Intended as a daemon thread's target.

    Two separate try blocks on purpose: an import failure and a runtime failure
    are different problems with different fixes, and one combined handler loses
    which of them happened — which is the only thing the report is for.

    Nothing here may propagate. A broken SRS is a tab that explains itself,
    never an AgentForge that will not start.
    """
    try:
        from srs_agent import mount
    except Exception as e:
        SRS_API.update(state="import-failed", error=f"{type(e).__name__}: {e}")
        print(f"⚠️  SRS agent unavailable — {SRS_API['error']}")
        return

    SRS_API.update(state="starting", error="")
    try:
        mount.serve(port=SRS_PORT)
        SRS_API.update(state="stopped")
    except Exception as e:
        SRS_API.update(state="crashed", error=f"{type(e).__name__}: {e}")
        print(f"⚠️  SRS agent stopped — {SRS_API['error']}")


def srs_status() -> dict:
    """
    Is the SRS agent actually there?

    `state` is what the thread believes; `listening` is measured. They disagree
    exactly when it matters — during the second or two of startup, and after a
    crash inside uvicorn that never reached the exception handler.
    """
    import socket
    listening = False
    try:
        with socket.create_connection(("127.0.0.1", SRS_PORT), timeout=0.5):
            listening = True
    except OSError:
        pass
    return {**SRS_API, "listening": listening}


DEPLOY_API = {"state": "off", "port": DEPLOY_PORT, "error": ""}


def start_deploy_api():
    """
    Run the deployment agent's HTTP server. Intended as a daemon thread's target.

    Two try blocks, like start_srs_api: an import failure and a runtime failure
    are different problems with different fixes.
    """
    try:
        sys.path.insert(0, str(BASE_DIR / "deployment-agent"))
        from deploy_agent import mount
    except Exception as e:
        DEPLOY_API.update(state="import-failed", error=f"{type(e).__name__}: {e}")
        print(f"⚠️  Deployment agent unavailable — {DEPLOY_API['error']}")
        return

    DEPLOY_API.update(state="starting", error="")
    try:
        mount.serve(port=DEPLOY_PORT)
        DEPLOY_API.update(state="stopped")
    except Exception as e:
        DEPLOY_API.update(state="crashed", error=f"{type(e).__name__}: {e}")
        print(f"⚠️  Deployment agent stopped — {DEPLOY_API['error']}")


def deploy_status() -> dict:
    """What the thread believes, plus whether the port is measurably there."""
    import socket
    listening = False
    try:
        with socket.create_connection(("127.0.0.1", DEPLOY_PORT), timeout=0.5):
            listening = True
    except OSError:
        pass
    return {**DEPLOY_API, "listening": listening}


_JOBS: dict = {}
_JOBS_LOCK = threading.Lock()
_JOBS_KEEP_FINISHED_S = 900
_JOBS_MAX = 200


_JOB_PATHS = ("/image", "/logo-prompt")


def _jobs_reap():
    now = time.time()
    done = [(j["finished"], jid) for jid, j in _JOBS.items() if j.get("finished")]
    for finished, jid in done:
        if now - finished > _JOBS_KEEP_FINISHED_S:
            _JOBS.pop(jid, None)
    if len(_JOBS) > _JOBS_MAX:
        for _, jid in sorted(done)[:len(_JOBS) - _JOBS_MAX]:
            _JOBS.pop(jid, None)


def _job_run(job_id: str, method: str, path: str, body):
    job = _JOBS[job_id]
    try:
        r = requests.request(
            method, f"http://127.0.0.1:{UI_PORT}{LOCODE_PREFIX}/api{path}",
            json=body if method != "GET" else None,

            timeout=(5, None))
        job["http_status"] = r.status_code
        try:
            job["result"] = r.json()
        except Exception:
            job["result"] = {"text": r.text}

        job["status"] = "done"
    except Exception as e:
        job["status"] = "error"
        job["error"] = f"{type(e).__name__}: {e}"
    finally:
        job["finished"] = time.time()


def job_start(method: str, path: str, body) -> dict:
    """Begin the work and answer immediately."""
    path = str(path or "")
    if not path.startswith("/"):
        raise ValueError("path must be absolute")
    if path.split("?")[0] not in _JOB_PATHS:
        raise ValueError(f"{path} cannot be run as a job")
    with _JOBS_LOCK:
        _jobs_reap()
        job_id = "job_" + uuid.uuid4().hex[:20]
        _JOBS[job_id] = {"status": "running", "path": path,
                         "started": time.time(), "finished": None,
                         "http_status": None, "result": None, "error": ""}
    threading.Thread(target=_job_run, args=(job_id, method, path, body),
                     daemon=True).start()
    return {"job_id": job_id, "status": "running", "path": path}


def job_poll(job_id: str) -> dict:
    job = _JOBS.get(job_id)
    if job is None:

        return {"job_id": job_id, "status": "unknown",
                "error": "no such job — it may have expired"}
    elapsed = (job.get("finished") or time.time()) - job["started"]
    return {"job_id": job_id, **job, "elapsed": round(elapsed, 1)}


_DEPLOY_JOBS: dict = {}
_DEPLOY_JOBS_LOCK = threading.Lock()
_DEPLOY_KEEP_FINISHED_S = 900
_DEPLOY_MAX_JOBS = 200


def _deploy_reap():
    now = time.time()
    done = [(j["finished"], jid) for jid, j in _DEPLOY_JOBS.items() if j.get("finished")]
    for finished, jid in done:
        if now - finished > _DEPLOY_KEEP_FINISHED_S:
            _DEPLOY_JOBS.pop(jid, None)
    if len(_DEPLOY_JOBS) > _DEPLOY_MAX_JOBS:
        for _, jid in sorted(done)[:len(_DEPLOY_JOBS) - _DEPLOY_MAX_JOBS]:
            _DEPLOY_JOBS.pop(jid, None)


def _deploy_job_run(job_id: str, method: str, path: str, body):
    job = _DEPLOY_JOBS[job_id]
    try:
        r = requests.request(method, f"http://127.0.0.1:{DEPLOY_PORT}{path}",
                             json=body if method != "GET" else None,

                             timeout=(2, None))
        job["http_status"] = r.status_code
        try:
            job["result"] = r.json()
        except Exception:
            job["result"] = {"text": r.text}

        job["status"] = "done"
    except Exception as e:
        job["status"] = "error"
        job["error"] = f"{type(e).__name__}: {e}"
    finally:
        job["finished"] = time.time()


def deploy_job_start(method: str, path: str, body) -> dict:
    """Begin the work and answer immediately."""
    if not path.startswith("/"):
        raise ValueError("path must be absolute")

    if path.startswith("/jobs"):
        raise ValueError("jobs cannot run jobs")
    with _DEPLOY_JOBS_LOCK:
        _deploy_reap()
        job_id = "djob_" + uuid.uuid4().hex[:20]
        _DEPLOY_JOBS[job_id] = {"status": "running", "path": path,
                                "started": time.time(), "finished": None,
                                "http_status": None, "result": None, "error": ""}
    threading.Thread(target=_deploy_job_run,
                     args=(job_id, method, path, body), daemon=True).start()
    return {"job_id": job_id, "status": "running", "path": path}


def deploy_job_poll(job_id: str) -> dict:
    job = _DEPLOY_JOBS.get(job_id)
    if job is None:

        raise KeyError("no such job (it may have expired)")
    elapsed = (job.get("finished") or time.time()) - job["started"]
    return {"job_id": job_id, **job, "elapsed": round(elapsed, 1)}


def start_http():
    try:

        httpd = _UIServer((bind_host(), UI_PORT), UIHandler)
        print(f"HTTP server listening on 127.0.0.1:{UI_PORT}")
        httpd.serve_forever()
    except Exception as e:
        print(f"HTTP server failed: {e}")


async def main():
    global MAIN_LOOP
    MAIN_LOOP = asyncio.get_running_loop()

    threading.Thread(target=MONGO.ensure_running, daemon=True).start()
    threading.Thread(target=start_srs_api, daemon=True).start()
    threading.Thread(target=start_deploy_api, daemon=True).start()
    threading.Thread(target=start_http, daemon=True).start()
    print(f"\n{'━'*46}")
    print(f"  ⚡ AgentForge v1.0.0 Starting...")
    print(f"  ⚡ UI Server   →  http://127.0.0.1:{UI_PORT}")
    print(f"  🔌 WebSocket   →  ws://127.0.0.1:{WS_PORT}")
    print(f"  📄 SRS agent   →  http://127.0.0.1:{SRS_PORT}")
    print(f"  🚀 Deploy      →  http://127.0.0.1:{DEPLOY_PORT}")
    print(f"  🧠 Refine      :  {DEFAULT_REFINE}")
    print(f"  🏗️  Build       :  {DEFAULT_BUILD}")
    print(f"  📝 Local development mode")
    print(f"{'━'*46}\n")
    async with websockets.serve(ws_handler, bind_host(), WS_PORT):
        await asyncio.Future()


def shutdown_all():
    print("\n🛑 Shutting down AgentForge backend...")

    if active_vite.get("proc"):
        try:
            _stop_dev_proc()
            print("   ✅ Dev server stopped")
        except:
            pass

    try:
        MONGO.stop()
    except:
        pass

    try:
        stop_model(DEFAULT_REFINE)
        stop_model(DEFAULT_BUILD)
        print("   ✅ Ollama models unloaded")
    except:
        pass

atexit.register(shutdown_all)

def handle_signal(sig, frame):
    shutdown_all()
    sys.exit(0)

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Stopped.")
        if active_vite["proc"]:
            try: active_vite["proc"].terminate()
            except: pass