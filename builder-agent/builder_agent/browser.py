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

# Harmless aborted or cancelled network request codes that do not represent application errors.
CANCELLED_ERRORS = frozenset({
    "net::ERR_ABORTED",
    "net::ERR_BLOCKED_BY_CLIENT",
    "net::ERR_CACHE_MISS",
})

# Roles whose value is the point of them: a snapshot that omits it cannot say
# whether a form was filled.
VALUE_ROLES = frozenset({
    "textbox", "combobox", "searchbox", "checkbox", "radio", "slider",
    "spinbutton", "switch",
})

# Read back one control after typing into it. `this` is the element.
READ_CONTROL = """function () {
  const opaque = ['checkbox', 'radio', 'file', 'range', 'color', 'submit',
                  'button', 'reset', 'image', 'hidden'];
  const tag = this.tagName.toLowerCase();
  const type = (this.type || '').toLowerCase();
  const editable = this.isContentEditable === true;
  return {
    fillable: editable || tag === 'textarea' ||
              (tag === 'input' && opaque.indexOf(type) === -1),
    value: String((editable ? this.textContent : this.value) || ''),
    focused: document.activeElement === this,
    tag: tag,
    type: type,
    label: this.id || this.name || this.getAttribute('placeholder') ||
           this.getAttribute('aria-label') || ''
  };
}"""


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

    def ask(self, method: str, params: dict | None = None, session: str | None = None,
            then=None) -> None:
        """Send a call and hand its reply to `then`, without waiting for it.

        `post` sends and forgets, which is no use when the reply is the point;
        `send` blocks the caller for a whole round trip. This is the third
        case: a call whose result matters but whose latency must not be on
        anybody's critical path - a screenshot after every journey step, where
        a measured 60 ms per capture is 29% of a twelve-step journey if the
        journey waits for it.

        Ordering is not luck. Chrome processes commands on a session in the
        order they arrive, so a capture queued here is taken before the next
        step's input events, and the frame is genuinely of the page as the step
        left it. `then` runs on the socket thread, so it must be short and it
        must not raise.
        """
        if self.closed or self._ws is None:
            return
        message = {"id": self._next_id(), "method": method, "params": params or {}}
        if session:
            message["sessionId"] = session

        async def _call():
            future = self._loop.create_future()
            self._pending[message["id"]] = future
            try:
                await self._ws.send(json.dumps(message))
                reply = await asyncio.wait_for(future, CALL_TIMEOUT)
            except Exception:  # noqa: BLE001 - a lost frame is not a failed run
                self._pending.pop(message["id"], None)
                return
            if then and not reply.get("error"):
                try:
                    then(reply.get("result") or {})
                except Exception:  # noqa: BLE001
                    pass

        try:
            asyncio.run_coroutine_threadsafe(_call(), self._loop)
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
        # Cache active URL on navigation events to avoid deadlocking the socket reader thread.
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
                self._note("console error", entry.get("text", ""), entry.get("url", ""),
                           source=entry.get("source"), requestId=entry.get("networkRequestId"))

        def exception(params, session):
            if session != self.session:
                return
            detail = params.get("exceptionDetails") or {}
            text = (detail.get("exception") or {}).get("description") or detail.get("text") or ""
            self._note("page error", text, detail.get("url", ""))

        def failed(params, session):
            if session != self.session:
                return
            # Ignore cancelled prefetch requests so navigation changes are not misidentified as defects.
            self._note(request_outcome(params), str(params.get("errorText", "")),
                       params.get("url", ""))

        def response(params, session):
            if session != self.session:
                return
            info = params.get("response") or {}
            status = int(info.get("status") or 0)
            if status >= 400:
                self._note(f"HTTP {status}", info.get("statusText", ""), info.get("url", ""),
                           source="network", requestId=params.get("requestId"), status=status)

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
            # Asynchronously post screencast frame acknowledgements to avoid blocking socket reception.
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

    def _note(self, kind: str, text: str, url: str = "", **metadata) -> None:
        # Bounded: a page in a redirect loop can emit thousands of these, and
        # the useful ones are always the first few.
        if len(self.diagnostics) < 60:
            self.diagnostics.append({"kind": kind, "text": str(text)[:400], "url": str(url)[:300], **metadata})

    def reset_diagnostics(self) -> None:
        self.diagnostics = []
        self.asserted_http_responses = []

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
                # Client-side rendering still has to paint before anything is
                # worth asserting against; wait for the frame, not for 350ms.
                self.settle(cap=0.35)
                return
            time.sleep(0.05)

    def settle(self, cap: float = 0.25, frames: int = 2) -> None:
        """Wait until the page has painted, instead of for a fixed delay.

        Every caller below used to sleep 100-400ms on the chance the browser had
        caught up: a click cost 0.25s, a screenshot 0.4s, a page load 0.35s, and
        a journey of eighty steps paid all of it whether or not anything was
        still happening. A frame callback answers the same question in the time
        it actually takes - usually one or two frames - and `cap` keeps this no
        slower than the sleep it replaces when the page cannot answer at all.
        """
        try:
            self.evaluate(
                "new Promise(done => {"
                f"  let left = {max(1, int(frames))};"
                "  const tick = () => (--left <= 0 ? done(1) : requestAnimationFrame(tick));"
                "  requestAnimationFrame(tick);"
                "})", timeout=cap)
        except Exception:                                            # noqa: BLE001
            # A page too busy or too broken to paint is not a reason to fail the
            # step; fall back to the delay this replaced.
            time.sleep(cap)

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
        """The page's controls, and what they are holding.

        The value was always collected - `a11y` reads it off the same node -
        and was dropped one line later, so this read the same whether a field
        held an address or nothing at all. That is the one question worth
        asking when a form did not submit, and it was the only question this
        could not answer.
        """
        rows = []
        for node in self.a11y():
            if not (node["name"] or node["role"] in VALUE_ROLES):
                continue
            row = f"{node['role']}: {node['name']}"
            if node["role"] in VALUE_ROLES:
                held = str(node["value"] or "")
                row += f" = {held[:80]!r}" if held else " = (empty)"
            rows.append(row)
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
        self.settle(cap=0.25)

    def fill(self, backend_id: int, text: str) -> None:
        """Type into a control, and prove the text arrived.

        `Input.insertText` goes to whatever holds focus. When the click before
        it misses - something covering the control, an element still moving
        under an animation, a control that cannot take focus - the text goes
        nowhere, and every signal the journey has still says the step passed.
        The failure surfaces several steps later as an assertion about a URL,
        with an empty form behind it that nothing in the report mentions.

        That is not hypothetical: four journeys failed on `urlIncludes` after a
        login whose fields were never filled, and the run spent forty minutes
        looking for the defect in the product, then edited the product to match
        the broken test. So the control is read back here, and a `type` that
        did not type fails at the step where it happened.
        """
        self.click(backend_id)
        self.cdp.send("Input.dispatchKeyEvent",
                      {"type": "keyDown", "key": "a", "code": "KeyA",
                       "windowsVirtualKeyCode": 65, "nativeVirtualKeyCode": 65,
                       "modifiers": 8 if os.sys.platform == "darwin" else 2}, self.session)
        self.cdp.send("Input.dispatchKeyEvent",
                      {"type": "keyUp", "key": "a", "code": "KeyA",
                       "windowsVirtualKeyCode": 65, "nativeVirtualKeyCode": 65,
                       "modifiers": 8 if os.sys.platform == "darwin" else 2}, self.session)
        self.cdp.send("Input.insertText", {"text": str(text)}, self.session)
        self.settle(cap=0.1, frames=1)
        self._verify_filled(backend_id, str(text))

    def control(self, backend_id: int) -> dict | None:
        """What one control holds and whether it has focus, read from the DOM.

        `None` when the element is not something a person types into, since
        there is then nothing to read back and nothing to verify.
        """
        try:
            node = self.cdp.send("DOM.resolveNode", {"backendNodeId": backend_id},
                                 self.session)
            object_id = (node.get("object") or {}).get("objectId")
            if not object_id:
                return None
            reply = self.cdp.send("Runtime.callFunctionOn",
                                  {"objectId": object_id, "returnByValue": True,
                                   "functionDeclaration": READ_CONTROL}, self.session)
            state = (reply.get("result") or {}).get("value")
        except ToolError:
            return None                 # a read-back that cannot run proves nothing
        return state if isinstance(state, dict) and state.get("fillable") else None

    def _verify_filled(self, backend_id: int, text: str) -> None:
        """Fail the step here if the text did not land in the control.

        Deliberately conservative. An empty control after a non-empty fill, or
        a control that never took focus, is a failure nobody can argue with. A
        value that differs in some other way is not: a field that formats a
        phone number or a date as it is typed has done its job, and failing
        that would make every masked input untestable.
        """
        state = self.control(backend_id)
        if state is None or not text:
            return
        held, focused = str(state.get("value") or ""), bool(state.get("focused"))
        if held and focused:
            return
        where = state.get("label") or state.get("tag") or "that control"
        why = ("The control never took focus, so the keystrokes went nowhere - "
               "something is covering it, or it moved between the click and the text."
               if not focused else
               "The control has focus but kept nothing, which is what a controlled "
               "input that rejects its own change event does.")
        raise ToolError(
            f"E2E_FILL_FAILED: typing into {where!r} left it holding {held[:80]!r}, "
            f"not {text[:80]!r}. {why} Repair owner: the page or the journey's "
            "locator - not the assertion that would have failed later.")

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
        self.settle(cap=0.2)

    def frame(self, path: Path, quality: int = 55, scale: float = 0.5) -> None:
        """Photograph the page without making anybody wait for it.

        For a timeline: one after every step of a journey, looked at in a strip
        rather than reviewed. So it is half size, it sets no device-metrics
        override, and it waits for nothing - the step it follows has already
        settled, and the reply is written on the socket thread when it arrives.
        Measured at 60 ms of browser time per capture, none of which the
        journey now spends.
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        def keep(result):
            data = result.get("data") or ""
            if data:
                path.write_bytes(base64.b64decode(data))

        self.cdp.ask("Page.captureScreenshot",
                     {"format": "jpeg", "quality": int(quality),
                      "captureBeyondViewport": False,
                      "optimizeForSpeed": True,
                      **({"clip": {**self._viewport(), "scale": scale}} if scale != 1 else {})},
                     self.session, then=keep)

    def _viewport(self) -> dict:
        """The visible area, for a clip that scales it. Cheap and cached."""
        if not getattr(self, "_view", None):
            metrics = self.cdp.send("Page.getLayoutMetrics", {}, self.session) or {}
            box = metrics.get("cssVisualViewport") or metrics.get("layoutViewport") or {}
            self._view = {"x": 0, "y": 0,
                          "width": int(box.get("clientWidth") or box.get("width") or 1280),
                          "height": int(box.get("clientHeight") or box.get("height") or 800)}
        return dict(self._view)

    def screenshot(self, path: Path, width: int = 1280, height: int = 800,
                   fmt: str = "png", quality: int = 0, settle: bool = True,
                   resize: bool = True) -> Path:
        """One picture of the page.

        The arguments exist for the difference between evidence and a record of
        what happened. Evidence is a full PNG at a named width, and it pays for
        a device-metrics override and a reflow to get that width honestly.

        A frame taken after every step of a journey is not that. It is a
        timeline, its only job is to show what the page looked like when the
        step finished, and it is taken at whatever size the page already is -
        so it sets no override and waits for nothing, because the step it
        follows has already settled. `resize=False, settle=False, fmt="jpeg"`
        is what makes one affordable per step instead of per journey.
        """
        if resize:
            self.cdp.send("Emulation.setDeviceMetricsOverride",
                          {"width": width, "height": height, "deviceScaleFactor": 1,
                           "mobile": width <= 600}, self.session)
        # The resize has to reflow and paint before the capture is of anything.
        if settle:
            self.settle(cap=0.4)
        shot = {"format": fmt}
        if fmt == "jpeg" and quality:
            shot["quality"] = int(quality)
        data = self.cdp.send("Page.captureScreenshot", shot, self.session,
                             timeout=45).get("data", "")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(data))
        if resize:
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
        # Record initial page URL when creating a new browser tab.
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
