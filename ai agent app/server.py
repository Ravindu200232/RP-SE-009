#!/usr/bin/env python3
"""
WebForge Server  —  HTTP :7824  |  WebSocket :7825
- Dual model selection (refine + build)
- Auto-pull Ollama models if missing
- Stop/unload model immediately after each stage (VRAM conservation)
- Fix loop uses npm run build for real errors + full codebase context
"""
import atexit
import signal
import sys, json, asyncio, logging, threading, time, re, subprocess, os, urllib3
urllib3.disable_warnings()
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler

try:
    import websockets
except ImportError:
    subprocess.run([sys.executable,"-m","pip","install","websockets",
                    "--break-system-packages","-q"])
    import websockets

sys.path.insert(0, str(Path(__file__).parent))
from agents.refiner  import RefinerAgent
from agents.builder  import BuilderAgent, set_stream_callback
from agents.tester   import TesterAgent, set_emit as set_tester_emit
from agents import llm, scaffold, srs_adapter
from agents.schema_agent import SchemaAgent
from agents.api_agent    import ApiAgent
from agents.integrator   import IntegratorAgent
from agents.quality      import build_contract, validate_spec, static_scan, write_manifest, bug_signatures
import shutil

# Windows desktop launches can use cp1252, while pipeline progress messages and
# generated logs contain Unicode symbols.  Never let console encoding terminate
# the backend before the HTTP/WebSocket services start.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def _maybe_set_playwright_env():
    # If Electron didn't set them for some reason, try to infer from app bundle.
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH") and os.environ.get("PLAYWRIGHT_NODEJS_PATH"):
        return

    # When packaged, the backend is typically:
    # /Applications/Locode.app/Contents/Resources/backend/locode-backend-v4
    exe = Path(sys.argv[0]).resolve()
    # .../Resources/backend -> .../Resources
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
    # Packaged mode
    if getattr(sys, "frozen", False):
        exe_path = Path(sys.argv[0]).resolve()
        resources_dir = exe_path.parent.parent  # backend → Resources

        node_bin_dir = resources_dir / "node" / "bin"

        npm_path = node_bin_dir / "npm"
        node_path = node_bin_dir / "node"

        if npm_path.exists() and node_path.exists():
            return str(npm_path), str(node_path)

    # Dev mode fallback
    return shutil.which("npm") or "npm", shutil.which("node") or "node"


NPM_BIN, NODE_BIN = resolve_node_binaries()

print("DEBUG: sys.executable =", sys.executable)
print("DEBUG: Using NPM_BIN  =", NPM_BIN)
print("DEBUG: Using NODE_BIN =", NODE_BIN)

# Ensure PATH includes bundled node
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
OLLAMA_URL = "http://localhost:11434"
# Single Gemma 4 12B model drives every stage (~98K context, thinking low —
# all configured in agents/llm.py). The two names are kept because the UI still
# sends refine_model / build_model fields.
DEFAULT_REFINE = llm.GEN_MODEL
DEFAULT_BUILD  = llm.GEN_MODEL
MAX_FIX    = 3
DEV_PORT   = 3000          # Next.js dev server
UI_PORT    = 7824
WS_PORT    = 7825

for d in [PROD_DIR, LOGS_DIR]: d.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("server")

clients    = set()
MAIN_LOOP  = None
active_vite = {"proc": None, "stderr_lines": []}

# ── Token accounting (feeds the UI savings calculator) ────────────────────────
_TOKENS = {"prompt": 0, "completion": 0, "calls": 0}

def _reset_tokens():
    _TOKENS.update(prompt=0, completion=0, calls=0)

def _add_tokens(p, c):
    _TOKENS["prompt"] += int(p or 0)
    _TOKENS["completion"] += int(c or 0)
    _TOKENS["calls"] += 1

def _stats() -> dict:
    p, c = _TOKENS["prompt"], _TOKENS["completion"]
    return {"prompt_tokens": p, "completion_tokens": c,
            "total_tokens": p + c, "llm_calls": _TOKENS["calls"]}

llm.set_token_callback(_add_tokens)


# ── Broadcast helpers ─────────────────────────────────────────────────────────

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

def elog(lvl, txt):       emit({"type":"log",         "level":lvl,  "text":txt})
def estep(s, st):         emit({"type":"step",         "step":s,     "status":st})
def efile(n, sz, c=""):   emit({"type":"file",         "name":n,     "size":sz,   "content":c})
def edetect(t, s):        emit({"type":"detected",     "site_type":t,"strategy":s})
def eprog(lbl, pct):      emit({"type":"progress",     "step":lbl,   "pct":pct})
def edone(url, proj, stats=None): emit({"type":"done", "url":url, "project":proj, "stats": stats or _stats()})
def eerr(txt):            emit({"type":"error",        "text":txt})
def estream_start(fname): emit({"type":"stream_start", "file":fname})
def estream(fname, tok):  emit({"type":"stream",       "file":fname, "token":tok})
def estream_end(f, c):    emit({"type":"stream_end",   "file":f,     "content":c})


# ── Token streaming ───────────────────────────────────────────────────────────

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


# ── Ollama model management ───────────────────────────────────────────────────

def ensure_model(model: str) -> bool:
    """Check Ollama tags; pull model if missing. Returns True if ready."""
    import requests as req
    try:
        r = req.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        names = [m["name"] for m in r.json().get("models", [])]
        if any(model == n or model.split(":")[0] == n.split(":")[0] for n in names):
            elog("INFO", f"   ✅ Model ready: {model}")
            return True
    except Exception as e:
        elog("WARN", f"   Ollama check failed: {e}")

    elog("INFO", f"   📥 Pulling {model} from Ollama (first time only)…")
    try:
        r = req.post(f"{OLLAMA_URL}/api/pull",
                     json={"name": model}, stream=True, timeout=600)
        last_pct = -1
        for line in r.iter_lines():
            if not line: continue
            try:
                chunk = json.loads(line)
                status = chunk.get("status", "")
                if chunk.get("total"):
                    pct = int(chunk.get("completed", 0) / chunk["total"] * 100)
                    if pct != last_pct and pct % 10 == 0:
                        elog("INFO", f"   📥 {model}: {pct}%")
                        last_pct = pct
                if "success" in status:
                    elog("INFO", f"   ✅ {model} pulled!")
                    return True
            except: pass
        return True
    except Exception as e:
        elog("ERROR", f"   ❌ Pull failed: {e}")
        return False

def stop_model(model: str):
    """Unload model from VRAM immediately after use."""
    import requests as req
    try:
        req.post(f"{OLLAMA_URL}/api/generate",
                 json={"model": model, "keep_alive": 0}, timeout=8)
        elog("INFO", f"   🗑️  Unloaded {model}")
    except: pass

def ensure_node_deps(proj_dir: Path) -> bool:
    next_bin = proj_dir / "node_modules" / ".bin" / (
        "next.cmd" if os.name == "nt" else "next"
    )

    if next_bin.exists():
        return True

    elog("INFO", "📦 Installing dependencies (npm install)…")

    try:
        r = subprocess.run(
            [NPM_BIN, "install"],
            cwd=proj_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if r.returncode == 0:
            elog("INFO", "   ✅ npm install complete")
            return True
        elog("ERROR", f"   ❌ npm install failed:\n{r.stderr[:300]}")
        return False
    except Exception as e:
        elog("ERROR", f"   ❌ npm install crashed: {e}")
        return False
# ── Vite management ───────────────────────────────────────────────────────────

def _kill_port(port: int):
    """Force-kill any process holding a port on Windows or POSIX."""
    if os.name == "nt":
        try:
            result = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, timeout=8)
            pids = set()
            needle = f":{port}"
            for line in result.stdout.splitlines():
                if needle in line and "LISTENING" in line.upper():
                    bits = line.split()
                    if bits and bits[-1].isdigit():
                        pids.add(bits[-1])
            for pid in pids:
                subprocess.run(["taskkill", "/PID", pid, "/T", "/F"], capture_output=True, timeout=8)
            if pids:
                time.sleep(0.8)
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


def start_vite(proj_dir: Path):
    """Kill old Vite fully, then start fresh on exact DEV_PORT."""
    # Step 1: terminate tracked process and wait for it to die
    if active_vite["proc"]:
        try:
            active_vite["proc"].terminate()
            try: active_vite["proc"].wait(timeout=4)
            except subprocess.TimeoutExpired:
                try: active_vite["proc"].kill()
                except: pass
        except Exception:
            pass
        active_vite["proc"] = None
    # Step 2: force-kill anything still holding DEV_PORT
    _kill_port(DEV_PORT)
    # A production build and the dev compiler use incompatible artifacts under
    # the same .next directory. Always start dev from a clean cache after the
    # preflight build/fix pass, otherwise stale chunk manifests can yield
    # "Cannot find module './<chunk>.js'" despite valid source code.
    next_dir = (Path(proj_dir) / ".next").resolve()
    project_root = Path(proj_dir).resolve()
    if next_dir.parent == project_root and next_dir.exists():
        shutil.rmtree(next_dir, ignore_errors=True)
    active_vite["stderr_lines"] = []

    def _run():
        try:
            p = subprocess.Popen(
                # next dev on a fixed port. -p is the Next.js port flag.
                [NPM_BIN, "run", "dev", "--", "-p", str(DEV_PORT)],
                cwd=proj_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=os.environ.copy(),
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


# ── UIBuilder: BuilderAgent subclass that emits to WebSocket ─────────────────

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


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run_pipeline(prompt: str = "", refine_model: str = None, build_model: str = None,
                 srs: dict = None):
    """v2 rule-based multi-agent pipeline: fixed core + LLM agents + line-level bug-fix.
    Accepts a role-wise SRS, an AutoHub SRS, or a free-text prompt. No templates."""
    from agents import orchestrator, rolewise
    model = build_model or DEFAULT_BUILD
    set_stream_callback(on_token)
    _reset_tokens()
    llm.log_config(model)
    try:
        elog("INFO", "━" * 40)
        elog("INFO", f"💡 {(prompt or 'structured SRS input')[:90]}")
        elog("INFO", f"🧠 Model: {model}  (gemma only — rule-based agents)")
        elog("INFO", "━" * 40)
        eprog("Checking model…", 3)
        if not ensure_model(model):
            eerr(f"Cannot load model: {model}"); return {"status": "failed"}

        # ── Stage 1: input → spec (deterministic for SRS; refiner for free text) ──
        estep("refine", "active")
        eprog("Reading the input…", 8)
        spec = None
        # A structured SRS pasted into the free-text idea box arrives as `prompt`
        # (srs=None). Detect JSON that is actually an SRS and route it through the
        # deterministic adapter instead of the free-text refiner — otherwise the
        # refiner falls back to a generic placeholder app (the "Item" model).
        if srs is None and prompt and prompt.lstrip().startswith("{"):
            try:
                maybe = json.loads(prompt)
            except Exception:
                maybe = None
            if isinstance(maybe, dict) and (
                    rolewise.is_rolewise_srs(maybe) or srs_adapter.is_srs(maybe)):
                elog("INFO", "🧠 Detected structured SRS JSON in the prompt — using the adapter")
                srs = maybe
        if srs is not None:
            if rolewise.is_rolewise_srs(srs):
                elog("INFO", "🧠 Agent 1 — role-wise SRS adapter")
                spec = rolewise.adapt_rolewise(srs)
            elif srs_adapter.is_srs(srs):
                elog("INFO", "🧠 Agent 1 — SRS adapter")
                spec = srs_adapter.adapt(srs)
        if spec is None and prompt:
            elog("INFO", "🧠 Agent 1 — Architect (free text)")
            refined = RefinerAgent(OLLAMA_URL, model).refine(prompt)
            try: spec = json.loads(refined)
            except Exception: spec = None
        if not spec or not spec.get("data_model"):
            eerr("Could not derive an app spec from the input"); return {"status": "failed"}
        estep("refine", "done")
        spec["build_model"] = model
        edetect(spec.get("site_type", "app"), "fullstack-next")
        elog("INFO", f"   collections={[m.get('name') for m in spec.get('data_model', [])]}")

        pname = re.sub(r"[^a-z0-9]", "", str(spec.get("project_name", "")).replace("-", ""))[:24] \
            or re.sub(r"[^a-z]", "", (prompt or "app")[:15].lower()) or "app"
        proj_dir = PROD_DIR / pname
        if proj_dir.exists():
            for c in list(proj_dir.iterdir()):
                if c.name in ("node_modules", "package-lock.json"):
                    continue
                try: shutil.rmtree(c) if c.is_dir() else c.unlink()
                except Exception: pass
        proj_dir.mkdir(parents=True, exist_ok=True)
        elog("INFO", f"   📁 {proj_dir}")

        # ── emit adapter: orchestrator events → UI stream ──
        def oemit(ev, payload=None):
            if ev == "token":
                on_token(payload if isinstance(payload, str) else "")
                return
            payload = payload or {}
            if ev == "phase":
                nm = payload.get("name", "")
                stepmap = {"core": "schema", "memory": "schema", "planner": "refine",
                           "models": "schema", "routes": "schema", "logic": "schema",
                           "components": "build", "layouts": "build",
                           "pages": "build", "verify-complete": "build",
                           "install": "serve", "build+fix": "test"}
                pctmap = {"core": 10, "planner": 14, "models": 20, "routes": 30,
                          "logic": 40, "components": 48, "layouts": 58, "pages": 64,
                          "verify-complete": 74, "install": 80, "build+fix": 86}
                estep(stepmap.get(nm, "build"), "active")
                if nm in pctmap:
                    eprog(nm.replace("-", " ").title(), pctmap[nm])
                elog("INFO", f"▶ {nm}")
            elif ev == "log":
                elog("INFO", f"   {payload.get('text', '')}")
            elif ev == "start":
                on_token(f"\x00START:{payload.get('label', 'file')}")
            elif ev == "end":
                on_token("\x00END")
            elif ev == "file":
                c = payload.get("content", ""); n = payload.get("path", "")
                sz = f"{len(c)//1024}KB" if len(c) >= 1024 else f"{len(c)}B"
                efile(n, sz, c)

        # ── Stages 2-8: fixed core + agents + line-level bug-fix loop ──
        # Prevention over repair: tight rules + component-wise small files + the per-file
        # validation gate keep the residual bug count inside a small fix loop (3 rounds).
        result = orchestrator.generate_app(spec, proj_dir, oemit, install=True, fix=True, fix_iters=3)
        stop_model(model)  # free VRAM for serve/browser

        if not result.get("built"):
            eerr("Build did not reach green after the fix loop — serving current candidate")

        # ── Serve ──
        estep("serve", "active")
        eprog("Starting Next.js…", 92)
        _kill_port(DEV_PORT)
        start_vite(proj_dir)
        if wait_for_vite(120):
            url = f"http://localhost:{DEV_PORT}"
            estep("serve", "done"); eprog("Done!", 100)
            elog("INFO", f"🎉 Live at {url}")
            edone(url, pname)
            return {"status": "passed" if result.get("built") else "served-with-warnings",
                    "project": pname, "url": url}
        eerr("Next.js did not start")
        return {"status": "failed", "project": pname}
    except Exception as e:
        eerr(f"Pipeline error: {e}")
        log.exception("v2 pipeline error")
        return {"status": "failed", "errors": [str(e)]}
    finally:
        set_stream_callback(None)


def list_projects() -> list:
    """Return all projects in production-ready/ with metadata."""
    projects = []
    if not PROD_DIR.exists():
        return projects
    for d in sorted(PROD_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        pkg = d / "package.json"
        title = d.name
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text())
                title = data.get("name", d.name)
            except: pass
        # Count source files (components, pages, models, API routes)
        src_files = (list(d.glob("components/*.jsx")) + list(d.glob("components/*.tsx"))
                     + list(d.glob("app/**/*.jsx")) + list(d.glob("app/**/*.tsx"))
                     + list(d.glob("models/*.js")) + list(d.glob("models/*.ts"))
                     + list(d.glob("app/api/**/route.js")) + list(d.glob("app/api/**/route.ts")))
        projects.append({
            "name": d.name,
            "title": title,
            "mtime": int(d.stat().st_mtime),
            "file_count": len(src_files),
            "quality_status": (json.loads((d / "verification" / "report.json").read_text(encoding="utf-8")).get("status")
                                if (d / "verification" / "report.json").exists() else "unknown"),
        })
    return projects


def get_project_files(proj_name: str) -> dict:
    """Read all source files from a project directory, return as {path: content}."""
    proj_dir = PROD_DIR / proj_name
    if not proj_dir.exists():
        return {}
    files = {}

    def _add(rel):
        fp = proj_dir / rel
        if fp.exists() and rel not in files:
            try:
                content = fp.read_text(encoding="utf-8", errors="replace")
                sz = f"{len(content)//1024:.1f}KB" if len(content) >= 1024 else f"{len(content)}B"
                files[rel] = {"content": content, "size": sz}
            except Exception:
                pass

    # Key files first, in a sensible reading order. _add() skips any that are
    # absent, so listing both the .ts (current) and .js (legacy) names is safe.
    for rel in ["app/page.tsx", "app/layout.tsx", "app/globals.css",
                "lib/mongodb.ts", "lib/api.ts", "lib/mongodb.js", "lib/api.js",
                "package.json", "next.config.mjs",
                "tailwind.config.ts", "tailwind.config.js"]:
        _add(rel)
    # Section components, models, and API route handlers.
    for sub, pat in [("components", "*.jsx"), ("components", "*.tsx"),
                     ("models", "*.ts"), ("models", "*.js")]:
        d = proj_dir / sub
        if d.exists():
            for fp in sorted(d.glob(pat)):
                _add(f"{sub}/{fp.name}")
    api_dir = proj_dir / "app" / "api"
    if api_dir.exists():
        for fp in sorted(list(api_dir.rglob("route.ts")) + list(api_dir.rglob("route.js"))):
                _add(fp.relative_to(proj_dir).as_posix())
    verification = proj_dir / "verification"
    if verification.exists():
        for fp in sorted(verification.rglob("*")):
            if fp.is_file() and fp.suffix in {".json", ".png"}:
                _add(fp.relative_to(proj_dir).as_posix())
    return files


# ── Update pipeline ───────────────────────────────────────────────────────────

def _existing_api_contract(proj_dir: Path) -> str:
    """Reconstruct the REST contract from the route folders already on disk."""
    api_dir = proj_dir / "app" / "api"
    if not api_dir.exists():
        return "This app has no backend API."
    segs = sorted({p.parent.name
                   for p in (list(api_dir.rglob("route.ts")) + list(api_dir.rglob("route.js")))
                   if p.parent.name and p.parent.name != "[id]"})
    if not segs:
        return "This app has no backend API."
    lines = ["The backend already exists. Use ONLY these relative endpoints with fetch():"]
    for s in segs:
        lines.append(f"  - GET/POST /api/{s} ; GET/PUT/DELETE /api/{s}/<id> (records keyed by _id)")
    return "\n".join(lines)


def _decide_targets(update_prompt: str, components: list, codebase_ctx: str,
                    model: str) -> list:
    """Ask the model which section component(s) to modify or create. Tiny, fast call."""
    comp_list = ", ".join(components) if components else "(none)"
    prompt = (
        f"A Next.js project has these page section components: {comp_list}\n\n"
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
        raw = llm.chat([{"role": "user", "content": prompt}], model=model,
                       num_predict=80, extra_opts={"temperature": 0.0}, timeout=45)
        m = re.search(r'\[([^\]]+)\]', raw)
        if m:
            names = json.loads(f"[{m.group(1)}]")
            return [n.strip() for n in names if isinstance(n, str) and n.strip()]
    except Exception as e:
        log.warning(f"   _decide_targets failed: {e}")
    return []


def _build_update_prompt(component_name: str, existing_code: str,
                         update_request: str, codebase_ctx: str,
                         is_new: bool, contract: str = "") -> str:
    """Targeted per-component update prompt — runs through builder._gen() like a fresh gen."""
    import textwrap as tw
    if is_new:
        return tw.dedent(f"""\
            Add a NEW section component called '{component_name}' to an existing Next.js page.

            USER REQUEST: {update_request}

            ── BACKEND API CONTRACT ──
            {contract}

            EXISTING CODEBASE (imports, styles, data patterns):
            {codebase_ctx[:1500]}

            Requirements:
            - First line: 'use client'
            - <section id="{component_name.lower()}"> full-bleed band, explicit dark background,
              max-w-7xl inner container, framer-motion whileInView reveals, real copy
            - For data, fetch the RELATIVE API routes above (records keyed by _id)
            - export default function {component_name}()
            - Output ONLY the complete JSX starting with 'use client'
            """)
    return tw.dedent(f"""\
        Modify the existing '{component_name}' Next.js client component as requested.

        USER REQUEST: {update_request}

        ── BACKEND API CONTRACT ──
        {contract}

        EXISTING COMPONENT CODE (modify THIS — keep everything not mentioned):
        {existing_code}

        OTHER FILES FOR CONTEXT (do NOT modify these):
        {codebase_ctx[:1200]}

        Requirements:
        - Apply ONLY the requested changes — preserve all other functionality
        - Keep 'use client' as the first line; keep the same visual design elsewhere
        - Follow all JSX rules: hoist regex, hoist divisions, no split components
        - export default function {component_name}()
        - Output ONLY the COMPLETE updated component JSX starting with 'use client'
        """)


def run_update_pipeline(proj_name: str, update_prompt: str, build_model: str = None):
    """
    Load an existing Next.js project, decide which section component(s) to change,
    re-generate each through builder._gen() → _write_one(), then test and fix.
    """
    model = build_model or DEFAULT_BUILD
    set_stream_callback(on_token)
    set_tester_emit(emit)
    _reset_tokens()
    llm.log_config(model)

    proj_dir = PROD_DIR / proj_name
    if not proj_dir.exists():
        eerr(f"Project not found: {proj_name}"); return

    try:
        elog("INFO", "━" * 40)
        elog("INFO", f"✏️  Updating: {proj_name}")
        elog("INFO", f"📝 Request: {update_prompt[:80]}")
        elog("INFO", f"🧠 Model: {model}")
        elog("INFO", "━" * 40)

        # ── Step 1: Load all existing files into builder ──────────────────────
        estep("refine", "active")
        eprog("Loading project…", 5)

        builder = UIBuilder(OLLAMA_URL, model, proj_dir)

        # Populate built_files from disk — builder needs this for context + fix loop
        file_data = get_project_files(proj_name)
        for rel, info in file_data.items():
            builder.built_files[rel] = info["content"]
            efile(rel, info["size"], info["content"])

        comp_dir   = proj_dir / "components"
        components = sorted({f.stem for pat in ("*.jsx", "*.tsx")
                             for f in comp_dir.glob(pat)}) if comp_dir.exists() else []
        contract   = _existing_api_contract(proj_dir)

        def _comp_path(name: str) -> str:
            # Resolve a component's real key (legacy .jsx or current .tsx); new
            # components default to .tsx.
            for ext in (".tsx", ".jsx"):
                k = f"components/{name}{ext}"
                if k in builder.built_files:
                    return k
            return f"components/{name}.tsx"
        elog("INFO", f"   📂 Loaded {len(file_data)} files | Components: {components}")

        estep("refine", "done")
        eprog("Analysing request…", 15)

        # ── Step 2: Load model + decide which components to touch ─────────────
        if not ensure_model(model):
            eerr(f"Cannot load model: {model}"); return

        codebase_ctx = builder._build_codebase_context()

        estep("build", "active")
        eprog("Deciding targets…", 22)

        targets = _decide_targets(update_prompt, components, codebase_ctx, model)
        targets = [t for t in targets if re.match(r"^[A-Z][A-Za-z0-9_]*$", t)]

        if not targets:
            # Fallback: ask the user's prompt to name the component directly,
            # or default to regenerating the component whose name appears in the request.
            for comp in components:
                if comp.lower() in update_prompt.lower():
                    targets = [comp]
                    break
            if not targets and components:
                # Last resort: pick the most content-heavy component (most likely to be the one)
                targets = [max(
                    components,
                    key=lambda c: len(builder.built_files.get(_comp_path(c), ""))
                )]
                elog("WARN", f"   Could not infer target — defaulting to largest component: {targets}")
            elif not targets:
                eerr("No components found in project"); return

        elog("INFO", f"   🎯 Targets: {targets}")

        # ── Step 3: Generate each target component ────────────────────────────
        updated_count = 0
        pct_per_comp  = max(1, 30 // len(targets))   # divide build progress across targets

        for i, comp_name in enumerate(targets):
            fpath    = _comp_path(comp_name)
            is_new   = comp_name not in components
            existing = builder.built_files.get(fpath, "")

            if is_new:
                elog("INFO", f"   ➕ Creating new component: {comp_name}")
            else:
                elog("INFO", f"   ✏️  Updating: {fpath}")

            eprog(f"Generating {comp_name}…", 25 + i * pct_per_comp)

            prompt = _build_update_prompt(
                comp_name, existing, update_prompt, codebase_ctx, is_new, contract
            )

            # _gen() handles: streaming to UI, token emission, extraction, raw output caching
            new_code = builder._gen(comp_name, prompt)

            if not new_code:
                elog("WARN", f"   LLM returned nothing for {comp_name} — skipping")
                continue

            # _write_one() handles: _extract_valid_component, _sanitize_jsx,
            # built_files update, disk write, UI file event via _on_write
            builder._write_one(fpath, new_code)
            updated_count += 1
            elog("INFO", f"   ✓ {fpath} written")

            # If it's a new component, add it to app/page.tsx imports/rendering
            if is_new:
                _inject_component_into_app(builder, proj_dir, comp_name)

        if updated_count == 0:
            eerr("No components were updated — LLM may have failed to generate valid JSX")
            return

        # Deterministic integration pass over the regenerated components.
        _api = proj_dir / "app" / "api"
        valid = sorted({p.parent.name
                        for p in (list(_api.rglob("route.ts")) + list(_api.rglob("route.js")))
                        if p.parent.name and p.parent.name != "[id]"}) \
            if _api.exists() else []
        touched = {_comp_path(t): builder.built_files.get(_comp_path(t), "")
                   for t in targets if builder.built_files.get(_comp_path(t))}
        IntegratorAgent(builder._write_one, valid).review(touched)

        stop_model(model)

        estep("build", "done")
        eprog("Components updated", 58)
        elog("INFO", f"   ✅ {updated_count}/{len(targets)} component(s) updated")

        # ── Step 4: Restart Next.js ───────────────────────────────────────────
        estep("serve", "active")
        eprog("Restarting Next.js…", 65)
        elog("INFO", "🌐 Restarting Next.js…")
        if not ensure_node_deps(proj_dir):
            eerr("Dependency install failed")
            return
        try:
            builder.suppress_type_errors()
        except Exception as e:
            elog("WARN", f"   type-error suppression skipped: {e}")
        start_vite(proj_dir)
        wait_for_vite(60)

        # ── Step 5: Test + fix loop (identical to run_pipeline) ───────────────
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
                elog("WARN", f"   ⚠ Max fix attempts reached — applying targeted fallbacks")
                from agents.builder import _safe_component
                # Targeted: only replace components named in the still-red build;
                # keep innocent components. Fall back to all only if unlocalizable.
                npm_errors = builder._npm_build_errors()
                broken = set(builder._identify_broken(npm_errors)) if npm_errors.strip() else set()
                nuke_all = bool(npm_errors.strip()) and not broken
                for fpath_s, src in list(builder.built_files.items()):
                    if not (fpath_s.startswith("components/") and fpath_s.endswith((".jsx", ".tsx"))):
                        continue
                    comp_name_s = fpath_s.split("/")[-1].replace(".jsx", "").replace(".tsx", "")
                    if len(src.strip()) < 400 or fpath_s in broken or nuke_all:
                        safe = _safe_component(comp_name_s)
                        (proj_dir / fpath_s).write_text(safe, encoding="utf-8")
                        builder.built_files[fpath_s] = safe
                        elog("WARN", f"   🛟 Safe fallback → {fpath_s}")
                estep("test", "done")
                break

            npm_errors = builder._npm_build_errors()
            vs_errors  = vite_stderr()
            all_errors = "\n".join(errors) + "\n" + npm_errors + "\n" + vs_errors

            elog("INFO", f"   📋 next build:\n{npm_errors[:250] or '  (none)'}")
            emit({"type": "test_fixing", "attempt": attempt, "errors": errors[:5]})
            elog("INFO", f"   🔧 Fixing attempt {attempt}/{MAX_FIX}…")

            if not ensure_model(model):
                elog("WARN", "   Cannot reload model — skipping fix")
                break

            builder.fix_with_errors(all_errors)
            stop_model(model)

            elog("INFO", "   🔄 Restarting Next.js after fix…")
            if not ensure_node_deps(proj_dir):
                eerr("Dependency install failed")
                return
            start_vite(proj_dir)
            wait_for_vite(35)

        # ── Done ──────────────────────────────────────────────────────────────
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
    Add a newly-created section to app/page.tsx so it renders: an import line
    plus a <CompName /> just before the footer. No-op if already referenced.
    """
    # Current projects use page.tsx; tolerate legacy page.jsx.
    page_rel = "app/page.tsx"
    app_path = proj_dir / "app" / "page.tsx"
    if not app_path.exists():
        page_rel = "app/page.jsx"
        app_path = proj_dir / "app" / "page.jsx"
    if not app_path.exists():
        return

    app_code = app_path.read_text(encoding="utf-8")
    if f"import {comp_name} " in app_code:
        return

    try:
        lines = app_code.splitlines()
        last_import = max(
            (i for i, l in enumerate(lines) if l.strip().startswith("import")),
            default=0
        )
        lines.insert(last_import + 1, f"import {comp_name} from '@/components/{comp_name}'")
        new_app = "\n".join(lines)

        # Insert the tag just before the footer (or </main> as a fallback).
        insert_tag = f"      <{comp_name} />\n"
        anchor = new_app.rfind("<footer")
        if anchor == -1:
            anchor = new_app.rfind("</main>")
        if anchor != -1:
            new_app = new_app[:anchor] + insert_tag + new_app[anchor:]

        app_path.write_text(new_app, encoding="utf-8")
        builder.built_files[page_rel] = new_app
        sz = f"{len(new_app)//1024:.1f}KB" if len(new_app) >= 1024 else f"{len(new_app)}B"
        efile(page_rel, sz, new_app)
        log.info(f"   ✓ Injected {comp_name} into {page_rel}")
    except Exception as e:
        log.warning(f"   _inject_component_into_app failed: {e}")


# ── WebSocket handler ─────────────────────────────────────────────────────────

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
                    p   = msg.get("prompt", "").strip()
                    rm  = msg.get("refine_model", DEFAULT_REFINE)
                    bm  = msg.get("build_model",  DEFAULT_BUILD)
                    srs = msg.get("srs")  # optional structured SRS JSON
                    if p or srs:
                        threading.Thread(
                            target=run_pipeline, args=(p, rm, bm, srs), daemon=True
                        ).start()
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


# ── HTTP handler ──────────────────────────────────────────────────────────────

class UIHandler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(BASE_DIR / "ui"), **k)
    def log_message(self, *a): pass
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
    def do_GET(self):
        if self.path == "/projects":
            data = json.dumps(list_projects()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        elif self.path.startswith("/files/"):
            proj_name = self.path[7:].strip("/")
            files = get_project_files(proj_name)
            data = json.dumps(files).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        else:
            # SimpleHTTPRequestHandler cannot be prefixed with send_response:
            # doing so emits two HTTP status lines and breaks fetch/browser clients.
            # Serve the UI entrypoint explicitly with no-cache headers instead.
            if self.path in ("/", "/index.html", "") or self.path.endswith(".html"):
                fp = BASE_DIR / "ui" / ("index.html" if self.path in ("/", "") else self.path.lstrip("/"))
                if fp.exists():
                    data = fp.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                    self.send_header("Pragma", "no-cache")
                    self.send_header("Expires", "0")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
            super().do_GET()
    def do_POST(self):
        if self.path == "/build":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            threading.Thread(
                target=run_pipeline,
                args=(body.get("prompt",""),
                      body.get("refine_model", DEFAULT_REFINE),
                      body.get("build_model",  DEFAULT_BUILD),
                      body.get("srs")),
                daemon=True
            ).start()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        elif self.path == "/upload-project":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            name = body.get("name", "imported")
            files = body.get("files", {})
            
            # Sanitize project name
            pname = re.sub(r"[^a-z0-9]", "", name.lower())[:20] or "imported"
            proj_dir = PROD_DIR / pname
            proj_dir.mkdir(parents=True, exist_ok=True)
            
            # Write files to disk
            for rel_path, content in files.items():
                fp = proj_dir / rel_path
                fp.parent.mkdir(parents=True, exist_ok=True)
                try:
                    fp.write_text(content, encoding="utf-8")
                except Exception as e:
                    log.error(f"Failed to write {rel_path}: {e}")
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"ok":True, "project": pname}).encode())
        elif self.path == "/update":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            threading.Thread(
                target=run_update_pipeline,
                args=(body.get("project",""),
                      body.get("prompt",""),
                      body.get("build_model", DEFAULT_BUILD)),
                daemon=True
            ).start()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

def start_http():
    try:
        httpd = HTTPServer(("127.0.0.1", UI_PORT), UIHandler)
        print(f"HTTP server listening on 127.0.0.1:{UI_PORT}")
        httpd.serve_forever()
    except Exception as e:
        print(f"HTTP server failed: {e}")
# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    global MAIN_LOOP
    MAIN_LOOP = asyncio.get_running_loop()
    threading.Thread(target=start_http, daemon=True).start()
    print(f"\n{'━'*46}")
    print(f"  ⚡ Locode v1.0.0 Starting...")
    print(f"  ⚡ UI Server   →  http://127.0.0.1:{UI_PORT}")
    print(f"  🔌 WebSocket   →  ws://127.0.0.1:{WS_PORT}")
    print(f"  🧠 Refine      :  {DEFAULT_REFINE}")
    print(f"  🏗️  Build       :  {DEFAULT_BUILD}")
    print(f"  📝 Local development mode")
    print(f"{'━'*46}\n")
    async with websockets.serve(ws_handler, "127.0.0.1", WS_PORT):
        await asyncio.Future()

        import atexit
import signal

def shutdown_all():
    print("\n🛑 Shutting down Locode backend...")

    # Kill Vite
    if active_vite.get("proc"):
        try:
            active_vite["proc"].terminate()
            active_vite["proc"].wait(timeout=5)
            print("   ✅ Vite stopped")
        except:
            pass

    # Unload models (best effort)
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
