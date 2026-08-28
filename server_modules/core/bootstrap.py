# Shared startup state and process setup.
"""
AgentForge Server  —  HTTP :7824  |  WebSocket :7825
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
from agents.build.tester_browser import TesterAgent
from agents.build.tester_common import set_emit as set_tester_emit
from agents.analysis.analyzer import (AnalyzerAgent, AnalyzerReport, Finding,
                             REPAIRABLE_MAJOR)
from agents.core import nextdocs
from agents.planner.architecture import ArchitectAgent, FileStreamParser
from agents.core.exports_checks import check_named_imports
from agents.core.exports_syntax import check_syntax, syntax_messages
from agents.features.features_apply import FeaturesAgent
from agents.features.features_common import FeatureSpec
from agents.features.capture import PENCIL_SYSTEM, capture_region
from agents.features.images import ImageAgent
from agents.features.source_guidance import feature_image_requested
from agents.features.picker import (ELEMENT_EDIT_SYSTEM, ElementResolver, describe,
                           guard_scope, looks_like_addition, looks_like_global,
                           looks_like_page_only, looks_like_removal,
                           looks_like_retext, routes_rendering)
from agents.data.mongo_lifecycle import MONGO
from agents.data.mongo_common import db_name_for
from agents.core import cancel
from agents.analysis.bugfixer_apply import BugFixerAgent
from agents.core.commands import CommandRunner
from agents.core.workspace import WorkspaceTools, TOOL_HELP
from qa_agent.e2e.e2e import E2EAgent
from qa_agent.e2e.debugger_investigate import AgenticE2EDebugger
from qa_agent.e2e.debugger_common import DebugNotebook
from qa_agent.unit.snapshot import FileSnapshot
from qa_agent.core.session_files import QASession
from qa_agent.unit.harness_install import TestHarness
from qa_agent.unit.spec import TestFailure, select_targets
from qa_agent.unit.author_write import UnitTestAuthor
from qa_agent.unit.runner import VitestRunner
from qa_agent.e2e.e2e import KIND_SELECTOR
from qa_agent.e2e.e2e_progress import (
    failure_signature as _e2e_failure_signature,
    failure_severity as _e2e_failure_severity,
    measure_progress as _e2e_progress,
    normalize_message as _e2e_norm_message,
    extend_round_budget as _e2e_extend_budget,
    stop_after_no_progress as _e2e_stop_no_progress,
    MIN_REPAIR_ROUNDS as E2E_MIN_FIX,
)
from agents.core.ollama_client import (OllamaClient, is_cloud_model, max_context,
                                  get_local_host, load_settings, save_settings,
                                  set_default_client)
import shutil
import copy

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



node_dir = str(Path(NODE_BIN).parent)
if node_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{node_dir}:{os.environ.get('PATH','')}"

if hasattr(sys, "_MEIPASS"):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent


def _projects_dir() -> Path:
    """Where the generated apps live. Beside the repo unless moved.

    `AGENTFORGE_PROJECTS` can move generated apps outside the repository.
    This is useful for synced folders because generated `node_modules` trees
    contain many transient files that should not be uploaded with source.

    A relative value is taken from the repo; an absolute one is used as is.
    Created if it does not exist, so pointing at a fresh folder just works.
    """
    raw = os.environ.get("AGENTFORGE_PROJECTS", "").strip()
    if not raw:
        return BASE_DIR / "production-ready"
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = BASE_DIR / p
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"⚠️  AGENTFORGE_PROJECTS={raw!r} cannot be used ({e}) — "
              f"falling back to production-ready/ beside the repo")
        return BASE_DIR / "production-ready"
    return p


PROD_DIR = _projects_dir()
if PROD_DIR != BASE_DIR / "production-ready":
    print(f"📁 projects live at {PROD_DIR} (AGENTFORGE_PROJECTS)")
elif "OneDrive" in str(PROD_DIR):
    print("⚠️  production-ready/ is inside OneDrive — every build's node_modules "
          "gets synced and npm install runs several times slower. Set "
          "AGENTFORGE_PROJECTS to a folder outside OneDrive "
          "(e.g. C:\\AgentForge\\projects) and restart.")
LOGS_DIR = BASE_DIR / "logs"
OLLAMA_URL = get_local_host()
DEFAULT_REFINE = "llama3.1:8b"
DEFAULT_BUILD  = "qwen2.5-coder:14b"
MAX_FIX    = 6


RUNTIME_DEADLINE = 900

# Pictures draw on the GPU beside the build, so the run never waits on them
# except once, right before the browser journeys that photograph the app.
IMAGE_FINAL_WAIT = 0
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
    cancel.check()
def efile(n, sz, c=""):   emit({"type":"file",         "name":n,     "size":sz,   "content":c})
def edetect(t, s):        emit({"type":"detected",     "site_type":t,"strategy":s})
def eprog(lbl, pct):
    emit({"type": "progress", "step": lbl, "pct": pct})
    cancel.check()
def edone(url, proj, preview="/"):

    emit({"type": "done", "url": url, "project": proj, "preview": preview})
def ecancel(detail: dict):

    emit({"type": "cancelled", **(detail or {})})
def eproject(name: str):
    """
    A project now exists on disk under this name.

    Sent as soon as the directory is made rather than when the build finishes,
    because that is when it becomes a real thing someone can see: the sidebar
    used to stay empty for the whole of a build and then a project appeared at
    the end, which reads as nothing having happened for twenty minutes.
    """
    emit({"type": "project", "project": str(name)})


cancel.log = elog
