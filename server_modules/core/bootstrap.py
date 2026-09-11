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
import html
import signal
import zipfile
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



# Each agent is its own package beside this file. Adding them to the path here
# keeps every import below a plain one, and keeps the server from caring where
# on disk they sit. `__file__` is the repository root: these runtime parts are
# executed into one shared namespace by server_runtime.py.
_REPO_ROOT = Path(__file__).resolve().parent
for _agent_root in ("srs-agent", "builder-agent", "qa-agent", "deployment-agent"):
    _path = str(_REPO_ROOT / _agent_root)
    if _path not in sys.path:
        sys.path.insert(0, _path)

from builder_agent.llm import (OllamaClient, is_cloud_model, max_context,
                               get_local_host, load_settings, save_settings,
                               set_default_client)
from server_modules.services import cancel
from server_modules.services.images import ImageAgent
from server_modules.services.mongo import MONGO
from server_modules.services.mongo_common import db_name_for
from server_modules.services.sources import feature_image_requested

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
IMAGE_FINAL_WAIT = 120
# Legacy preferred port; live app addresses come from RUNTIMES.
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


# Which project the thread emitting a message is working on. A run has its own
# thread, so this is per-run without anything having to be threaded through
# every call that reports something.
RUN = threading.local()


def working_on(project: str = ""):
    """Say which project this thread's messages belong to."""
    RUN.project = str(project or "")


def stamp_owner(msg: dict) -> dict:
    """Name the project a message came from, unless it already names one."""
    if "project" in msg:
        return msg
    owner = getattr(RUN, "project", "")
    return {**msg, "project": owner} if owner else msg


def emit(msg: dict):
    """Publish one message, stamped with the project it came from.

    Without the stamp every client showed every line: a run left going in one
    project wrote its output into whichever project was on screen, so a food
    delivery app's feed filled up with another project's npm commands. A
    message that already names its project keeps that name; one that names
    none is about the server itself and is shown wherever anyone is looking.
    """
    if MAIN_LOOP is None: return
    data = json.dumps(stamp_owner(msg), ensure_ascii=False)
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
