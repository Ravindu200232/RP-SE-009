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
# Source: agents/build/tester_browser.py — imported helper(s) come from here.
from agents.build.tester_browser import TesterAgent
# Source: agents/build/tester_common.py — imported helper(s) come from here.
from agents.build.tester_common import set_emit as set_tester_emit
# Source: agents/analysis/analyzer.py — imported helper(s) come from here.
from agents.analysis.analyzer import (AnalyzerAgent, AnalyzerReport, Finding,
                             REPAIRABLE_MAJOR)
# Source: agents/core/nextjs/docs.py — imported helper(s) come from here.
from agents.core.nextjs import docs as nextdocs
# Source: agents/planner/builder/app_builder.py — imported helper(s) come from here.
from agents.planner.builder.app_builder import ArchitectAgent, FileStreamParser
# Source: agents/core/imports/import_checker.py — imported helper(s) come from here.
from agents.core.imports.import_checker import check_named_imports
# Source: agents/core/syntax/syntax_checker.py — imported helper(s) come from here.
from agents.core.syntax.syntax_checker import check_syntax, syntax_messages
# Source: agents/features/feature_writer.py — imported helper(s) come from here.
from agents.features.feature_writer import FeaturesAgent
# Source: agents/features/feature_contract.py — imported helper(s) come from here.
from agents.features.feature_contract import FeatureSpec
# Source: agents/features/pencil_capture.py — imported helper(s) come from here.
from agents.features.pencil_capture import PENCIL_SYSTEM, capture_region
# Source: agents/features/image_generator.py — imported helper(s) come from here.
from agents.features.image_generator import ImageAgent
# Source: agents/features/feature_prompts.py — imported helper(s) come from here.
from agents.features.feature_prompts import feature_image_requested
# Source: agents/features/element_selector.py — imported helper(s) come from here.
from agents.features.element_selector import (ELEMENT_EDIT_SYSTEM, ElementResolver, describe,
                           guard_scope, looks_like_addition, looks_like_global,
                           looks_like_page_only, looks_like_removal,
                           looks_like_retext, routes_rendering)
# Source: agents/data/database_server.py — imported helper(s) come from here.
from agents.data.database_server import MONGO
# Source: agents/data/database_helpers.py — imported helper(s) come from here.
from agents.data.database_helpers import db_name_for
# Source: agents/core/runtime/cancellation.py — imported helper(s) come from here.
from agents.core.runtime import cancellation as cancel
# Source: agents/analysis/repair/bug_fixer.py — imported helper(s) come from here.
from agents.analysis.repair.bug_fixer import BugFixerAgent
# Source: agents/core/runtime/command_runner.py — imported helper(s) come from here.
from agents.core.runtime.command_runner import CommandRunner
# Source: agents/core/workspace/source_workspace.py — imported helper(s) come from here.
from agents.core.workspace.source_workspace import WorkspaceTools, TOOL_HELP
# Source: qa_agent/e2e/e2e.py — imported helper(s) come from here.
from qa_agent.e2e.e2e import E2EAgent
# Source: qa_agent/e2e/debugger_investigate.py — imported helper(s) come from here.
from qa_agent.e2e.debugger_investigate import AgenticE2EDebugger
# Source: qa_agent/e2e/debugger_common.py — imported helper(s) come from here.
from qa_agent.e2e.debugger_common import DebugNotebook
# Source: qa_agent/unit/snapshot.py — imported helper(s) come from here.
from qa_agent.unit.snapshot import FileSnapshot
# Source: qa_agent/core/session_files.py — imported helper(s) come from here.
from qa_agent.core.session_files import QASession
# Source: qa_agent/unit/harness_install.py — imported helper(s) come from here.
from qa_agent.unit.harness_install import TestHarness
# Source: qa_agent/unit/spec.py — imported helper(s) come from here.
from qa_agent.unit.spec import TestFailure, select_targets
# Source: qa_agent/unit/author_write.py — imported helper(s) come from here.
from qa_agent.unit.author_write import UnitTestAuthor
# Source: qa_agent/unit/runner.py — imported helper(s) come from here.
from qa_agent.unit.runner import VitestRunner
# Source: qa_agent/e2e/e2e.py — imported helper(s) come from here.
from qa_agent.e2e.e2e import KIND_SELECTOR
# Source: qa_agent/e2e/e2e_progress.py — imported helper(s) come from here.
from qa_agent.e2e.e2e_progress import (
    failure_signature as _e2e_failure_signature,
    failure_severity as _e2e_failure_severity,
    measure_progress as _e2e_progress,
    normalize_message as _e2e_norm_message,
    extend_round_budget as _e2e_extend_budget,
    stop_after_no_progress as _e2e_stop_no_progress,
    MIN_REPAIR_ROUNDS as E2E_MIN_FIX,
)
# Source: agents/core/llm/llm_client.py — imported helper(s) come from here.
from agents.core.llm.llm_client import (OllamaClient, is_cloud_model, max_context,
                                  get_local_host, load_settings, save_settings,
                                  set_default_client)
import shutil
import copy

# Purpose: Handle maybe set playwright env for this focused step.
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
# Purpose: Handle resolve node binaries for this focused step.
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


# Purpose: Where the generated apps live. Beside the repo unless moved.
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


# Purpose: Pick a sane agent model when the caller didn't name one: the saved.
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


# Purpose: Handle emit for this focused step.
def emit(msg: dict):
    if MAIN_LOOP is None: return
    data = json.dumps(msg, ensure_ascii=False)
    # Purpose: Handle s for this focused step.
    async def _s():
        dead = set()
        for ws in list(clients):
            try: await ws.send(data)
            except: dead.add(ws)
        clients.difference_update(dead)
    asyncio.run_coroutine_threadsafe(_s(), MAIN_LOOP)

# Purpose: Handle elog for this focused step.
def elog(lvl, txt):

    log.info(f"[{lvl}] {txt}")
    emit({"type": "log", "level": lvl, "text": txt})
# Purpose: Handle estep for this focused step.
def estep(s, st):
    if st == "error":
        log.error(f"step {s} failed")
    emit({"type": "step", "step": s, "status": st})
    cancel.check()
# Purpose: Handle efile for this focused step.
def efile(n, sz, c=""):   emit({"type":"file",         "name":n,     "size":sz,   "content":c})
# Purpose: Handle edetect for this focused step.
def edetect(t, s):        emit({"type":"detected",     "site_type":t,"strategy":s})
# Purpose: Handle eprog for this focused step.
def eprog(lbl, pct):
    emit({"type": "progress", "step": lbl, "pct": pct})
    cancel.check()
# Purpose: Handle edone for this focused step.
def edone(url, proj, preview="/"):

    emit({"type": "done", "url": url, "project": proj, "preview": preview})
# Purpose: Handle ecancel for this focused step.
def ecancel(detail: dict):

    emit({"type": "cancelled", **(detail or {})})
# Purpose: A project now exists on disk under this name.
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
