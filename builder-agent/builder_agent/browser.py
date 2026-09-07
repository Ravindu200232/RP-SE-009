"""The browser the end-to-end journeys actually run in.

Direct Chrome DevTools Protocol, in a throwaway profile, driven by the engine
itself. No project-owned test framework is generated to verify a project: a
journey is data the model writes, the engine executes it, and what comes back
is an exit status the ledger can record.

Locators resolve through the accessibility tree, in this order: an explicit CSS
selector, an exact accessible name, a normalised name, then exactly one
containing match. Ambiguity is an error rather than a guess, because a journey
that silently clicks the wrong "Delete" is worse than one that fails.

Failures are classified by owner, which is the part that makes repair
convergent:

* `E2E_SELECTOR_MISMATCH` / `E2E_SELECTOR_AMBIGUOUS` - fix the journey.
* `E2E_UI_TARGET_MISSING` - fix the product, the route or the state.
* an assertion, console, network or 5xx failure - fix production behaviour.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from .errors import ToolError

CONNECT_TIMEOUT = 15
CALL_TIMEOUT = 25
MAX_STEPS = 80


# ---------------------------------------------------------------------------
# Finding a browser
# ---------------------------------------------------------------------------
def discover_browser() -> str | None:
    """A Chromium-family executable, from the environment or the usual places.

    Playwright's vendored Chromium counts: this repository already ships one
    for the deployment agent, and using it saves the user a second download.
    """
    explicit = os.environ.get("AGENT_BROWSER_EXECUTABLE", "").strip()
    if explicit:
        if Path(explicit).is_file():
            return explicit
        raise ToolError(f"AGENT_BROWSER_EXECUTABLE does not exist: {explicit}")

    candidates: list[Path] = []
    vendored = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "").strip()
    for root in filter(None, [vendored, str(Path.home() / "AppData/Local/ms-playwright"),
                              str(Path.home() / ".cache/ms-playwright")]):
        base = Path(root)
        if base.is_dir():
            candidates += sorted(base.glob("chromium*/chrome-*/chrome.exe"))
            candidates += sorted(base.glob("chromium*/chrome-*/chrome"))
            candidates += sorted(base.glob("chromium*/chrome-*/Chromium.app/Contents/MacOS/Chromium"))

    if os.name == "nt":
        for root in filter(None, (os.environ.get("PROGRAMFILES"),
                                  os.environ.get("PROGRAMFILES(X86)"),
                                  os.environ.get("LOCALAPPDATA"))):
            candidates += [
                Path(root, "Google/Chrome/Application/chrome.exe"),
                Path(root, "Microsoft/Edge/Application/msedge.exe"),
                Path(root, "Chromium/Application/chrome.exe"),
            ]
    elif os.sys.platform == "darwin":
        candidates += [
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
            Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        ]
    else:
        for name in ("google-chrome", "google-chrome-stable", "chromium",
                     "chromium-browser", "microsoft-edge"):
            found = shutil.which(name)
            if found:
                candidates.append(Path(found))

    for candidate in candidates:
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            continue
    return None


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------
class Cdp:
    """Synchronous JSON-RPC over the DevTools websocket.

    The engine is synchronous everywhere else, so the asyncio loop lives in one
    background thread and every call blocks on a future. Making the whole
    engine async to accommodate one websocket would be a much larger change for
    no benefit the run can observe.
    """

    def __init__(self, url: str) -> None:
        self.url = url
        self._id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._events: dict[str, list] = {}
        self._ws = None
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self.closed = False

    def _run(self, coro, timeout: float):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    def connect(self) -> "Cdp":
        import websockets

        async def _open():
            self._ws = await websockets.connect(self.url, max_size=64 * 1024 * 1024,
                                                ping_interval=None)
            asyncio.ensure_future(self._reader())

        try:
            self._run(_open(), CONNECT_TIMEOUT)
        except Exception as error:  # noqa: BLE001 - surfaced as a tool failure
            raise ToolError(f"Could not connect to the browser debugging endpoint: {error}") from None
        return self

    async def _reader(self) -> None:
        try:
            async for raw in self._ws:
                try:
                    message = json.loads(raw)
                except (TypeError, ValueError):
                    continue
                if "id" in message:
                    future = self._pending.pop(message["id"], None)
                    if future and not future.done():
                        future.set_result(message)
                    continue
                for handler in list(self._events.get(message.get("method", ""), ())):
                    try:
                        handler(message.get("params") or {}, message.get("sessionId"))
                    except Exception:  # noqa: BLE001 - a listener cannot break the run
                        pass
        except Exception:  # noqa: BLE001 - the socket closing is normal
            pass
        finally:
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(ToolError("Browser debugging connection closed."))
            self._pending.clear()

    def on(self, method: str, handler) -> None:
        self._events.setdefault(method, []).append(handler)

    def send(self, method: str, params: dict | None = None, session: str | None = None,
             timeout: float = CALL_TIMEOUT) -> dict:
        if self.closed or self._ws is None:
            raise ToolError("Browser debugging connection is not open.")
        self._id += 1
        message = {"id": self._id, "method": method, "params": params or {}}
        if session:
            message["sessionId"] = session

        async def _call():
            future = self._loop.create_future()
            self._pending[message["id"]] = future
            await self._ws.send(json.dumps(message))
            return await future

        try:
            reply = self._run(_call(), timeout)
        except TimeoutError:
            self._pending.pop(message["id"], None)
            raise ToolError(f"{method} timed out after {timeout}s.") from None
        if reply.get("error"):
            raise ToolError(f"{method}: {reply['error'].get('message')}")
        return reply.get("result") or {}

    def close(self) -> None:
        self.closed = True
        try:
            if self._ws is not None:
                self._run(self._ws.close(), 5)
        except Exception:  # noqa: BLE001 - closing a dead socket is fine
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


class Page:
    """One tab, plus everything that went wrong in it."""

    def __init__(self, cdp: Cdp, target_id: str, session: str) -> None:
        self.cdp = cdp
        self.target_id = target_id
        self.session = session
        self.diagnostics: list[dict] = []
        self._install_listeners()

    def _install_listeners(self) -> None:
        for domain in ("Page", "Runtime", "Network", "Log", "DOM"):
            try:
                self.cdp.send(f"{domain}.enable", {}, self.session)
            except ToolError:
                pass

        def console(params, session):
            if session != self.session:
                return
            entry = params.get("entry") or {}
            if entry.get("level") == "error":
                self._note("console error", entry.get("text", ""), entry.get("url", ""))

        def exception(params, session):
            if session != self.session:
                return
            detail = params.get("exceptionDetails") or {}
            text = (detail.get("exception") or {}).get("description") or detail.get("text") or ""
            self._note("page error", text, detail.get("url", ""))

        def failed(params, session):
            if session != self.session:
                return
            self._note("request failed", params.get("errorText", ""), params.get("url", ""))

        def response(params, session):
            if session != self.session:
                return
            info = params.get("response") or {}
            status = int(info.get("status") or 0)
            if status >= 500:
                self._note(f"HTTP {status}", info.get("statusText", ""), info.get("url", ""))

        self.cdp.on("Log.entryAdded", console)
        self.cdp.on("Runtime.exceptionThrown", exception)
        self.cdp.on("Network.loadingFailed", failed)
        self.cdp.on("Network.responseReceived", response)

    def _note(self, kind: str, text: str, url: str = "") -> None:
        # Bounded: a page in a redirect loop can emit thousands of these, and
        # the useful ones are always the first few.
        if len(self.diagnostics) < 60:
            self.diagnostics.append({"kind": kind, "text": str(text)[:400], "url": str(url)[:300]})

    def reset_diagnostics(self) -> None:
        self.diagnostics = []

    # -- navigation ------------------------------------------------------
    def navigate(self, url: str, timeout: float = 30) -> None:
        self.cdp.send("Page.navigate", {"url": url}, self.session, timeout=timeout)
        self.wait_ready(timeout)

    def wait_ready(self, timeout: float = 30) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            state = self.evaluate("document.readyState")
            if state in ("interactive", "complete"):
                # Give client-side rendering a moment to paint before asserting.
                time.sleep(0.35)
                return
            time.sleep(0.1)

    def evaluate(self, expression: str, timeout: float = CALL_TIMEOUT):
        result = self.cdp.send("Runtime.evaluate",
                               {"expression": expression, "returnByValue": True,
                                "awaitPromise": True}, self.session, timeout=timeout)
        if result.get("exceptionDetails"):
            detail = result["exceptionDetails"]
            raise ToolError((detail.get("exception") or {}).get("description")
                            or detail.get("text") or "Script evaluation failed.")
        return (result.get("result") or {}).get("value")

    @property
    def url(self) -> str:
        try:
            return str(self.evaluate("location.href") or "")
        except ToolError:
            return ""

    def text(self, limit: int = 6000) -> str:
        try:
            return str(self.evaluate("document.body ? document.body.innerText : ''") or "")[:limit]
        except ToolError:
            return ""

    # -- accessibility ---------------------------------------------------
    def a11y(self) -> list[dict]:
        nodes = self.cdp.send("Accessibility.getFullAXTree", {}, self.session,
                              timeout=40).get("nodes", [])
        out = []
        for node in nodes:
            if node.get("ignored"):
                continue
            role = ((node.get("role") or {}).get("value") or "").lower()
            name = (node.get("name") or {}).get("value") or ""
            if not role:
                continue
            out.append({"role": role, "name": name,
                        "backendDOMNodeId": node.get("backendDOMNodeId"),
                        "value": (node.get("value") or {}).get("value")})
        return out

    def snapshot(self, limit: int = 120) -> str:
        rows = [f"{n['role']}: {n['name']}" for n in self.a11y()
                if n["name"] or n["role"] in ("textbox", "combobox", "checkbox")]
        seen, unique = set(), []
        for row in rows:
            if row in seen:
                continue
            seen.add(row)
            unique.append(row)
        head = f"URL: {self.url}\n"
        body = "\n".join(unique[:limit]) or "(no named accessible controls)"
        return head + body

    def locate(self, role: str | None, name: str | None, selector: str | None) -> int:
        """Resolve one element, or say precisely why it could not."""
        if selector:
            document = self.cdp.send("DOM.getDocument", {"depth": 0, "pierce": True},
                                     self.session).get("root", {})
            found = self.cdp.send("DOM.querySelector",
                                  {"nodeId": document.get("nodeId"), "selector": selector},
                                  self.session)
            node_id = found.get("nodeId")
            if not node_id:
                raise ToolError(f"E2E_SELECTOR_MISMATCH: no element matches selector "
                                f"{selector!r}. Repair owner: the journey locator, unless the "
                                "UI contract itself is missing.")
            described = self.cdp.send("DOM.describeNode", {"nodeId": node_id}, self.session)
            return described["node"]["backendNodeId"]

        role = (role or "").lower()
        matches = [n for n in self.a11y() if n["role"] == role and n["backendDOMNodeId"]]
        if name is None:
            if len(matches) == 1:
                return matches[0]["backendDOMNodeId"]
            if not matches:
                raise ToolError(f"E2E_UI_TARGET_MISSING: no accessible {role} exists on this page. "
                                "Repair owner: the product UI, route or state.")
            raise ToolError(f"E2E_SELECTOR_AMBIGUOUS: {len(matches)} accessible {role} controls "
                            "were found. Repair owner: the journey locator - give a name or a "
                            "stable CSS selector.")

        if not matches:
            raise ToolError(f"E2E_UI_TARGET_MISSING: no accessible {role} exists while the journey "
                            f"expected {name!r}. Repair owner: the product UI, route or state.")

        wanted = _normalise(name)
        for candidates, label in (
            ([n for n in matches if n["name"] == name], "exact"),
            ([n for n in matches if _normalise(n["name"]) == wanted], "normalised"),
            ([n for n in matches if wanted and wanted in _normalise(n["name"])], "containing"),
        ):
            if len(candidates) == 1:
                return candidates[0]["backendDOMNodeId"]
            if len(candidates) > 1:
                names = " | ".join(c["name"][:80] for c in candidates[:5])
                raise ToolError(f"E2E_SELECTOR_AMBIGUOUS: {label} match for {name!r} on role "
                                f"{role} hits {len(candidates)} controls ({names}). Repair owner: "
                                "the journey locator - use a more specific name or a CSS selector.")

        observed = " | ".join(n["name"][:60] for n in matches[:8] if n["name"])
        raise ToolError(f"E2E_SELECTOR_MISMATCH: no accessible {role} named {name!r}."
                        + (f" Observed {role} names: {observed}." if observed else "")
                        + " Repair owner: the journey locator if one of those is the intended "
                          "target; otherwise the product UI, route or state.")

    # -- interaction -----------------------------------------------------
    def _box(self, backend_id: int) -> tuple[float, float]:
        model = self.cdp.send("DOM.getBoxModel", {"backendNodeId": backend_id}, self.session)
        quad = model["model"]["content"]
        return ((quad[0] + quad[2] + quad[4] + quad[6]) / 4,
                (quad[1] + quad[3] + quad[5] + quad[7]) / 4)

    def click(self, backend_id: int) -> None:
        self.cdp.send("DOM.scrollIntoViewIfNeeded", {"backendNodeId": backend_id}, self.session)
        x, y = self._box(backend_id)
        for kind in ("mousePressed", "mouseReleased"):
            self.cdp.send("Input.dispatchMouseEvent",
                          {"type": kind, "x": x, "y": y, "button": "left", "clickCount": 1},
                          self.session)
        time.sleep(0.25)

    def fill(self, backend_id: int, text: str) -> None:
        self.click(backend_id)
        self.cdp.send("Input.dispatchKeyEvent",
                      {"type": "keyDown", "key": "a", "code": "KeyA",
                       "modifiers": 8 if os.sys.platform == "darwin" else 2}, self.session)
        self.cdp.send("Input.dispatchKeyEvent",
                      {"type": "keyUp", "key": "a", "code": "KeyA",
                       "modifiers": 8 if os.sys.platform == "darwin" else 2}, self.session)
        self.cdp.send("Input.insertText", {"text": str(text)}, self.session)
        time.sleep(0.1)

    def press(self, key: str) -> None:
        table = {"Enter": (13, "Enter"), "Tab": (9, "Tab"), "Escape": (27, "Escape"),
                 "ArrowDown": (40, "ArrowDown"), "ArrowUp": (38, "ArrowUp"),
                 "Backspace": (8, "Backspace")}
        code, name = table.get(key, (0, key))
        for kind in ("keyDown", "keyUp"):
            self.cdp.send("Input.dispatchKeyEvent",
                          {"type": kind, "key": name, "code": name,
                           "windowsVirtualKeyCode": code, "nativeVirtualKeyCode": code},
                          self.session)
        time.sleep(0.2)

    def screenshot(self, path: Path, width: int = 1280, height: int = 800) -> Path:
        self.cdp.send("Emulation.setDeviceMetricsOverride",
                      {"width": width, "height": height, "deviceScaleFactor": 1,
                       "mobile": width <= 600}, self.session)
        time.sleep(0.4)
        data = self.cdp.send("Page.captureScreenshot", {"format": "png"}, self.session,
                             timeout=45).get("data", "")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(data))
        self.cdp.send("Emulation.clearDeviceMetricsOverride", {}, self.session)
        return path


# ---------------------------------------------------------------------------
# The browser instance
# ---------------------------------------------------------------------------
class Browser:
    def __init__(self, events=None) -> None:
        self.events = events
        self.cdp: Cdp | None = None
        self.process: subprocess.Popen | None = None
        self.profile: str | None = None
        self.pages: dict[str, Page] = {}
        self.active: str | None = None
        self.captures: dict[str, dict] = {}
        # A suite that has failed this many times without the project changing
        # is not going to pass on the next identical retry.
        self.attempts: dict[str, dict] = {}

    @property
    def running(self) -> bool:
        return self.cdp is not None and not self.cdp.closed

    def launch(self) -> None:
        if self.running:
            return
        executable = discover_browser()
        if not executable:
            raise ToolError("No Chrome, Edge or Chromium was found. Install one, or set "
                            "AGENT_BROWSER_EXECUTABLE. Browser journeys use direct CDP.")
        self.profile = tempfile.mkdtemp(prefix="builder-agent-cdp-")
        args = [executable, "--headless=new", "--remote-debugging-port=0",
                f"--user-data-dir={self.profile}", "--no-first-run",
                "--no-default-browser-check", "--disable-background-networking",
                "--disable-component-update", "--disable-sync", "--disable-extensions",
                "--disable-features=Translate,MediaRouter", "--disable-popup-blocking",
                "--window-size=1280,800", "about:blank"]
        if os.name != "nt" and hasattr(os, "geteuid") and os.geteuid() == 0:
            args.insert(2, "--no-sandbox")
        self.process = subprocess.Popen(args, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL)

        port_file = Path(self.profile) / "DevToolsActivePort"
        deadline = time.time() + 20
        endpoint = None
        while time.time() < deadline:
            if self.process.poll() is not None:
                break
            try:
                lines = port_file.read_text(encoding="utf-8").strip().splitlines()
                if len(lines) >= 2 and lines[0].isdigit():
                    endpoint = f"ws://127.0.0.1:{lines[0]}{lines[1]}"
                    break
            except OSError:
                pass
            time.sleep(0.05)
        if not endpoint:
            self.close()
            raise ToolError("The browser started but never exposed a debugging endpoint.")
        self.cdp = Cdp(endpoint).connect()
        try:
            self.cdp.send("Browser.setDownloadBehavior", {"behavior": "deny"})
        except ToolError:
            pass

    def page(self, tab_id: str | None = None) -> Page:
        self.launch()
        tab_id = tab_id or self.active
        if tab_id and tab_id in self.pages:
            return self.pages[tab_id]
        return self.open_tab()

    def open_tab(self, url: str = "about:blank") -> Page:
        self.launch()
        target = self.cdp.send("Target.createTarget", {"url": url})["targetId"]
        session = self.cdp.send("Target.attachToTarget",
                                {"targetId": target, "flatten": True})["sessionId"]
        page = Page(self.cdp, target, session)
        self.pages[target] = page
        self.active = target
        return page

    def fresh_session(self) -> None:
        """Start from a clean auth/storage state, as a real first visit would."""
        if not self.running:
            return
        for page in self.pages.values():
            try:
                self.cdp.send("Network.clearBrowserCookies", {}, page.session)
                page.evaluate("try{localStorage.clear();sessionStorage.clear()}catch(e){}")
            except ToolError:
                pass

    def mark_project_changed(self) -> None:
        """A repair happened; a previously blocked suite may retry."""
        self.attempts.clear()

    def close(self) -> None:
        if self.cdp:
            self.cdp.close()
        self.cdp = None
        self.pages.clear()
        self.active = None
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    self.process.kill()
                except OSError:
                    pass
        self.process = None
        if self.profile:
            shutil.rmtree(self.profile, ignore_errors=True)
            self.profile = None
