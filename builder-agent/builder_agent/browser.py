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

# Network errors that mean "this request was called off", not "this app is
# broken". Route prefetches, an aborted fetch on navigation and a client-side
# block all land here, and none of them is a defect in the product.
CANCELLED_ERRORS = frozenset({
    "net::ERR_ABORTED",
    "net::ERR_BLOCKED_BY_CLIENT",
    "net::ERR_CACHE_MISS",
})


def request_outcome(params: dict) -> str:
    """Was this request called off, or did it genuinely fail?

    CDP answers it directly with `canceled`; the error text is the backstop
    for the cases where it does not set the flag.
    """
    if params.get("canceled") or str(params.get("errorText", "")) in CANCELLED_ERRORS:
        return "request cancelled"
    return "request failed"


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
        self._id_lock = threading.Lock()
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

    def _next_id(self) -> int:
        with self._id_lock:
            self._id += 1
            return self._id

    def post(self, method: str, params: dict | None = None,
             session: str | None = None) -> None:
        """Send a message and do not wait for its reply.

        Event handlers run on the reader's own thread, so a handler that calls
        `send` blocks the loop that has to read the answer it is waiting for -
        a deadlock that only ends when the call times out, with the whole
        connection stalled until it does.

        Screencast acknowledgements are the case that matters: one per frame,
        and Chrome stops sending frames until each is answered. Nothing here
        needs the reply, so nothing waits for it.
        """
        if self.closed or self._ws is None:
            return
        message = {"id": self._next_id(), "method": method, "params": params or {}}
        if session:
            message["sessionId"] = session
        payload = json.dumps(message)

        async def _send():
            try:
                await self._ws.send(payload)
            except Exception:  # noqa: BLE001 - a dropped ack is not a failed run
                pass

        try:
            asyncio.run_coroutine_threadsafe(_send(), self._loop)
        except RuntimeError:                 # the loop is closing; so is the run
            pass

    def send(self, method: str, params: dict | None = None, session: str | None = None,
             timeout: float = CALL_TIMEOUT) -> dict:
        if self.closed or self._ws is None:
            raise ToolError("Browser debugging connection is not open.")
        message = {"id": self._next_id(), "method": method, "params": params or {}}
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
        # Last known address, updated on navigation. A screencast frame arrives
        # on the socket thread, and asking the page for its URL from there
        # would block that thread on a reply it is itself responsible for
        # reading.
        self.url_cached = ""
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
            # A cancelled request is not a broken one. A framework that
            # prefetches routes cancels those prefetches on every navigation,
            # so counting them as defects fails every journey on every app and
            # the repair loop can never converge. CDP says so itself with
            # `canceled`; the error text is the backstop for the cases where
            # it does not.
            self._note(request_outcome(params), str(params.get("errorText", "")),
                       params.get("url", ""))

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

    # -- watching --------------------------------------------------------
    def start_screencast(self, on_frame, quality: int = 55, width: int = 900) -> None:
        """Stream what this tab is showing, frame by frame.

        The journeys run headless, so without this a browser stage is a
        progress bar and a log line: you cannot see the page the assertion
        failed on. Every frame must be acknowledged or Chrome stops sending
        them after the first.
        """
        def frame(params, session):
            if session != self.session:
                return
            # This runs on the socket's own thread. The acknowledgement is
            # posted, never sent: waiting for its reply here would block the
            # reader that has to deliver it.
            self.cdp.post("Page.screencastFrameAck",
                          {"sessionId": params.get("sessionId")}, self.session)
            data = params.get("data") or ""
            if data:
                on_frame("data:image/jpeg;base64," + data)

        if getattr(self, "_casting", False):
            return                      # already streaming; one cast per tab
        self.cdp.on("Page.screencastFrame", frame)
        try:
            self.cdp.send("Page.startScreencast",
                          {"format": "jpeg", "quality": quality, "maxWidth": width,
                           "maxHeight": int(width * 0.75), "everyNthFrame": 2},
                          self.session)
            self._casting = True
        except ToolError:
            self._casting = False       # watching is a convenience, never a gate

    def stop_screencast(self) -> None:
        if not getattr(self, "_casting", False):
            return
        self._casting = False
        try:
            self.cdp.send("Page.stopScreencast", {}, self.session, timeout=5)
        except ToolError:
            pass

    def _note(self, kind: str, text: str, url: str = "") -> None:
        # Bounded: a page in a redirect loop can emit thousands of these, and
        # the useful ones are always the first few.
        if len(self.diagnostics) < 60:
            self.diagnostics.append({"kind": kind, "text": str(text)[:400], "url": str(url)[:300]})

    def reset_diagnostics(self) -> None:
        self.diagnostics = []

    # -- navigation ------------------------------------------------------
    def navigate(self, url: str, timeout: float = 30) -> None:
        self.url_cached = str(url)
        self.cdp.send("Page.navigate", {"url": url}, self.session, timeout=timeout)
        self.wait_ready(timeout)
        self.url_cached = self.url or self.url_cached

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

    def locate(self, role: str | None, name: str | None, selector: str | None,
               index: int | None = None) -> int:
        """Resolve one element, or say precisely why it could not.

        `index` picks from an ordered set of equal matches. A list page renders
        the same control once per row - "View & Book" on every room card - and
        that is correct product UI, not a defect. Without a way to say "the
        first one" no list page could ever be tested, which made ambiguity a
        dead end rather than something the journey could resolve.
        """
        if selector:
            document = self.cdp.send("DOM.getDocument", {"depth": 0, "pierce": True},
                                     self.session).get("root", {})
            found = self.cdp.send("DOM.querySelectorAll",
                                  {"nodeId": document.get("nodeId"), "selector": selector},
                                  self.session)
            node_ids = found.get("nodeIds") or []
            if not node_ids:
                raise ToolError(f"E2E_SELECTOR_MISMATCH: no element matches selector "
                                f"{selector!r}. Repair owner: the journey locator, unless the "
                                "UI contract itself is missing.")
            node_id = self._pick(node_ids, index, f"selector {selector!r}")
            described = self.cdp.send("DOM.describeNode", {"nodeId": node_id}, self.session)
            return described["node"]["backendNodeId"]

        # A missing role means "any role". Requiring one made an omitted role
        # match nothing at all and report "no accessible  exists".
        role = (role or "").lower().strip()
        nodes = [n for n in self.a11y() if n["backendDOMNodeId"]]
        matches = [n for n in nodes if n["role"] == role] if role else nodes
        described_role = role or "control"

        if name is None:
            if not matches:
                raise ToolError(f"E2E_UI_TARGET_MISSING: no accessible {described_role} exists on "
                                "this page. Repair owner: the product UI, route or state.")
            return self._pick([n["backendDOMNodeId"] for n in matches], index,
                              f"role {described_role}")

        if not matches:
            raise ToolError(f"E2E_UI_TARGET_MISSING: no accessible {described_role} exists while "
                            f"the journey expected {name!r}. Repair owner: the product UI, route "
                            "or state.")

        wanted = _normalise(name)
        for candidates, label in (
            ([n for n in matches if n["name"] == name], "exact"),
            ([n for n in matches if _normalise(n["name"]) == wanted], "normalised"),
            ([n for n in matches if wanted and wanted in _normalise(n["name"])], "containing"),
        ):
            if candidates:
                return self._pick([n["backendDOMNodeId"] for n in candidates], index,
                                  f"{label} match for {name!r} on role {described_role}")

        observed = " | ".join(n["name"][:60] for n in matches[:8] if n["name"])
        raise ToolError(f"E2E_SELECTOR_MISMATCH: no accessible {described_role} named {name!r}."
                        + (f" Observed names: {observed}." if observed else "")
                        + " Repair owner: the journey locator if one of those is the intended "
                          "target; otherwise the product UI, route or state.")

    @staticmethod
    def _pick(node_ids: list, index: int | None, what: str) -> int:
        """One node from an ordered set, or an error that says how to choose."""
        if index is not None:
            position = int(index)
            if not -len(node_ids) <= position < len(node_ids):
                raise ToolError(f"E2E_SELECTOR_MISMATCH: index {position} is out of range for "
                                f"{what}, which matched {len(node_ids)} element(s). Repair owner: "
                                "the journey locator.")
            return node_ids[position]
        if len(node_ids) == 1:
            return node_ids[0]
        raise ToolError(f"E2E_SELECTOR_AMBIGUOUS: {what} hits {len(node_ids)} controls. Repair "
                        "owner: the journey locator - add index:0 for the first of them (or any "
                        "position, -1 for the last), or use a more specific name or CSS selector. "
                        "Repeated controls on a list page are normal and are not a product defect.")

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
        # A tab created at a URL never goes through `navigate`, so this is the
        # only place its address is recorded — and the address is what the
        # studio labels the stream with.
        page.url_cached = "" if url == "about:blank" else str(url)
        self.pages[target] = page
        self.active = target
        self._watch(page)
        return page

    def _watch(self, page: Page) -> None:
        """Show what this tab is looking at, for as long as it is open.

        The browser runs headless, so anything it does is invisible unless it
        is streamed. Starting only inside a journey meant a build that opened a
        page and photographed it — which is most of the visual review — showed
        nothing at all.
        """
        if not self.events:
            return
        page.start_screencast(
            lambda frame: self.events.emit("browser", state="frame", frame=frame,
                                           url=page.url_cached))

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
        # Say so, or the last frame sits over the preview until it goes stale.
        if self.events:
            self.events.emit("browser", state="closed", frame="", url="")
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
