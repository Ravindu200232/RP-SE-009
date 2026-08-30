"""Generate cached project images through a local or remote Fooocus Gradio UI."""
import base64
import json
import logging
import random
import re
import time
from pathlib import Path
import requests
# Source: image_settings.py — imported helper(s) come from this file.
from agents.features.image_settings import *

log = logging.getLogger("images")

class ImageAgent:
    """Version-tolerant Fooocus client that degrades to ``False`` on failure."""

    # Prepares ImageAgent with the services and starting state it needs before it begins work.
    def __init__(self, host: str = "", config_path: str = "",
                 callbacks: dict = None, enabled: bool = True):
        """Prepare this helper with the state it needs."""
        self.host = (host or "").rstrip("/")
        self.config_path = config_path or ""
        self.cb = callbacks or {}
        self.enabled = enabled
        self._fetch_error = ""
        self._payload = None
        self._fn_index = None
        self._gallery_index = None
        self._checked = None

    # Sends one progress event to the UI callback when a callback exists.
    def _fire(self, name, *a):
        """Send one progress event to the UI callback when a callback exists."""
        fn = self.cb.get(name)
        if fn:
            try:
                fn(*a)
            except Exception as e:
                log.warning(f"callback {name} failed: {e}")

    # Writes one readable status message through the configured logger.
    def _log(self, lvl, txt):
        """Write one readable status message through the configured logger."""
        self._fire("on_log", lvl, txt)
        log.info(txt)

    # The Fooocus that answers, or '' when none does. Cached per run.
    def base_url(self) -> str:
        """The Fooocus that answers, or '' when none does. Cached per run."""
        if self._checked is not None:
            return self._checked
        candidates = [self.host] if self.host else list(DEFAULT_HOSTS)
        for url in candidates:
            try:
                r = requests.get(f"{url}/config", timeout=4)
                if r.status_code == 200 and "components" in r.text[:400]:
                    self._checked = url
                    return url
            except requests.RequestException:
                continue
        self._checked = ""
        return ""

    # Checks whether the external image service is ready to accept work.
    def available(self) -> bool:
        """Return whether the external image service is ready to accept work."""
        return bool(self.enabled and self.base_url())

    # Discover the live generate function and its version-specific defaults.
    def _load_template(self) -> bool:
        """Discover the live generate function and its version-specific defaults."""
        if self._payload is not None:
            return True
        cfg = None
        url = self.base_url()
        if url:
            try:
                cfg = requests.get(f"{url}/config", timeout=10).json()
            except Exception as e:
                log.debug(f"live config: {e}")
        if cfg is None and self.config_path:
            try:
                cfg = json.loads(Path(self.config_path).read_text(encoding="utf-8"))
            except Exception as e:
                log.debug(f"config file: {e}")
        if not cfg:
            return False

        comps = {c["id"]: c for c in cfg.get("components", [])}
        deps = cfg.get("dependencies", [])

        idx = max(range(len(deps)),
                  key=lambda i: len(deps[i].get("inputs") or []),
                  default=None)
        if idx is None or len(deps[idx].get("inputs") or []) < 50:
            return False

        values, labels = [], {}
        for pos, cid in enumerate(deps[idx]["inputs"]):
            props = (comps.get(cid) or {}).get("props") or {}
            values.append(props.get("value"))
            label = props.get("label")
            if label and label not in labels:
                labels[label] = pos

        self._payload, self._fn_index, self._labels = values, idx, labels

        gallery = {cid for cid, c in comps.items() if c.get("type") == "gallery"}
        self._gallery_index = next(
            (i for i, d in enumerate(deps)
             if d.get("trigger_after") == idx
             and any(o in gallery for o in (d.get("outputs") or []))),
            None)

        chain, seen, at = [], set(), idx
        while at is not None and at not in seen:
            seen.add(at)
            prev = deps[at].get("trigger_after")
            if prev is None or not isinstance(prev, int) or prev >= len(deps):
                break
            chain.append(prev)
            at = prev

        self._prelude = []
        for i in reversed(chain):
            d = deps[i]
            self._prelude.append((i, [
                ((comps.get(cid) or {}).get("props") or {}).get("value")
                for cid in (d.get("inputs") or [])
            ]))
        return True

    # Finds the requested image slot in the current image plan and return the matching slot data.
    def _slot(self, label: str, fallback: int) -> int:
        """Prepare the slot value or state used by this focused pipeline step."""
        return getattr(self, "_labels", {}).get(label, fallback)

    ASPECTS = {
        "banner":   "1664*576",
        "wide":     "1344*768",
        "landscape": "1152*896",
        "square":   "1024*1024",
        "portrait": "896*1152",
        "poster":   "832*1216",
    }

    # Generate one image; cache unless forced and randomize a zero seed.
    def generate(self, prompt: str, out_path: Path, *, aspect: str = "landscape",
                 seed: int = 0, force: bool = False) -> bool:
        """Generate one image; cache unless forced and randomize a zero seed."""
        out_path = Path(out_path)
        if not force and out_path.is_file() and out_path.stat().st_size > 1024:
            return True
        if not self.available():
            return False
        if not self._load_template():
            self._log("WARN", "   ⚠ could not read the Fooocus UI description")
            return False

        args = list(self._payload)
        args[2] = prompt
        i = self._slot(ASPECT_LABEL, 6)

        want = self.ASPECTS.get(aspect, self.ASPECTS["landscape"])
        cur = args[i]
        if isinstance(cur, str):
            args[i] = re.sub(r"^\d+[*×]\d+", want.replace("*", "×"), cur) \
                if re.match(r"^\d+[*×]\d+", cur) else cur
        args[self._slot(COUNT_LABEL, 7)] = 1
        args[self._slot(SEED_LABEL, 9)] = str(
            seed if seed else random.randint(1, 2 ** 31 - 1))

        url = self.base_url()
        self._log("INFO", f"   🎨 {out_path.name} — {prompt[:60]}")
        t0 = time.time()
        self._fetch_error = ""
        data = self._predict(url, args)
        if data is None:
            # _predict already named the queue/timeout reason; say which image
            # it cost, or the log shows a generation start with no outcome.
            self._log("WARN", f"   ⚠ {out_path.name} was not generated "
                              f"after {time.time() - t0:.0f}s")
            return False

        raw = self._first_image(data)
        if not raw:
            # Three different faults used to land here as one sentence: a
            # response shape we could not read, a file that never became
            # readable, and a failed download all said "returned no image".
            why = self._fetch_error or "no image field in the Fooocus response"
            self._log("WARN", f"   ⚠ {out_path.name} — {why}")
            return False
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(raw)
        except OSError as e:
            self._log("WARN", f"   ⚠ could not write {out_path.name}: {e}")
            return False
        self._log("INFO", f"   ✅ {out_path.name} in {time.time() - t0:.0f}s")
        return True

    # Runs the queued generator via Gradio 3 WebSocket or Gradio 4 SSE.
    def _predict(self, url: str, args: list):
        """Run the queued generator via Gradio 3 WebSocket or Gradio 4 SSE."""
        ws_url = url.replace("http://", "ws://").replace("https://", "wss://")
        session = "agentforge-" + str(int(time.time() * 1000))
        try:

            for fn, defaults in getattr(self, "_prelude", []):
                self._predict_ws(ws_url, session, list(defaults), fn)

            task = self._predict_ws(ws_url, session, args, self._fn_index)
            if task is None:
                return None
            if self._gallery_index is None:
                return task
            return self._predict_ws(ws_url, session, list(task),
                                    self._gallery_index)
        except _NoQueue:
            pass
        except Exception as e:
            self._log("WARN", f"   ⚠ Fooocus queue failed: {e}")
            return None

        payload = {"fn_index": self._fn_index, "data": args,
                   "session_hash": session}
        try:
            join = requests.post(f"{url}/queue/join", json=payload, timeout=30)
            if not join.ok:
                self._log("WARN", f"   ⚠ Fooocus {join.status_code}: "
                                  f"{join.text[:140]}")
                return None
            stream = requests.get(f"{url}/queue/data",
                                  params={"session_hash": session},
                                  stream=True, timeout=GENERATE_TIMEOUT)
            for line in stream.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                ev = json.loads(line[5:].strip())
                if ev.get("msg") == "process_completed":
                    out = ev.get("output") or {}
                    return None if out.get("error") else (out.get("data") or [])
        except Exception as e:
            self._log("WARN", f"   ⚠ Fooocus did not answer: {e}")
        return None

    # The Gradio 3.x queue handshake. Raises `_NoQueue` when unsupported.
    def _predict_ws(self, ws_url: str, session: str, args: list,
                    fn_index: int):
        """The Gradio 3.x queue handshake. Raises `_NoQueue` when unsupported."""
        import asyncio

        try:
            import websockets
        except ImportError:
            # From: agents/features/image_settings.py
            raise _NoQueue("websockets is not installed")

        # Runs the Fooocus WebSocket queue handshake until an image result or timeout is observed.
        async def run_websocket_queue():
            """Run the Fooocus WebSocket queue handshake until an image result or timeout is observed."""
            try:
                conn = await asyncio.wait_for(
                    websockets.connect(f"{ws_url}/queue/join",
                                       max_size=None, open_timeout=20),
                    timeout=25)
            except Exception as e:
                # From: agents/features/image_settings.py
                raise _NoQueue(str(e))
            async with conn as ws:
                deadline = time.time() + GENERATE_TIMEOUT
                last = -1
                while time.time() < deadline:
                    raw = await asyncio.wait_for(ws.recv(),
                                                 timeout=GENERATE_TIMEOUT)
                    ev = json.loads(raw)
                    msg = ev.get("msg")
                    if msg == "send_hash":
                        await ws.send(json.dumps({"session_hash": session,
                                                  "fn_index": fn_index}))
                    elif msg == "send_data":
                        await ws.send(json.dumps({
                            "fn_index": fn_index, "data": args,
                            "session_hash": session}))
                    elif msg == "process_completed":
                        out = ev.get("output") or {}
                        if out.get("error"):
                            self._log("WARN", f"   ⚠ Fooocus: "
                                              f"{str(out['error'])[:140]}")
                            return None
                        return out.get("data") or []
                    elif msg in ("process_generating", "progress"):
                        pd = (ev.get("progress_data") or [{}])[0]
                        pct = int(pd.get("index") or 0)
                        if pct and pct != last and pct % 10 == 0:
                            last = pct
                            self._fire("on_progress", f"Image {pct}%", 78)
                self._log("WARN", "   ⚠ Fooocus took too long")
                return None

        return asyncio.run(run_websocket_queue())

    # Extracts the first base64 or file-backed image from nested output.
    def _first_image(self, data) -> bytes:
        """Extract the first base64 or file-backed image from nested output."""
        # Walk through nested response data and yield each item that can contain a generated image.
        def walk(node):
            """Prepare the walk value or state used by this focused pipeline step."""
            if isinstance(node, str):
                if node.startswith("data:image"):
                    try:
                        return base64.b64decode(node.split(",", 1)[1])
                    except Exception:
                        return None
                if node.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    return self._fetch(node)
                return None
            if isinstance(node, dict):

                for key in ("value", "name", "path", "url", "data"):
                    if key not in node:
                        continue
                    got = walk(node[key])
                    if got:
                        return got
                return None
            if isinstance(node, (list, tuple)):
                for item in node:
                    got = walk(item)
                    if got:
                        return got
            return None

        return walk(data)

    # A file Fooocus reported by path — read it, or pull it over HTTP. Fooocus names the file in its gallery result
    # before that file is readable, so a single immediate attempt loses images that were in fact generated: the first
    # few succeed while it is idle, then every later one reports nothing. Poll for a short while instead of giving up
    # at once, and keep the last reason so the caller can say what went wrong.
    def _fetch(self, ref: str) -> bytes:
        """A file Fooocus reported by path — read it, or pull it over HTTP.

        Fooocus names the file in its gallery result before that file is
        readable, so a single immediate attempt loses images that were in fact
        generated: the first few succeed while it is idle, then every later one
        reports nothing. Poll for a short while instead of giving up at once,
        and keep the last reason so the caller can say what went wrong.
        """
        self._fetch_error = ""
        url = self.base_url()
        deadline = time.time() + FETCH_TIMEOUT
        attempt = 0
        while True:
            attempt += 1
            p = Path(ref)
            if p.is_file():
                try:
                    body = p.read_bytes()
                    if body[:4] in IMAGE_MAGIC:
                        return body
                    self._fetch_error = f"{p.name} is not image data yet"
                except OSError as e:
                    self._fetch_error = f"cannot read {p.name}: {e}"
            elif not url:
                self._fetch_error = "no Fooocus address, and the file is not on disk"

            if url:
                for path in (f"/file={ref}", f"/file/{ref}", ref):
                    target = url + path if path.startswith("/") else path
                    try:
                        r = requests.get(target, timeout=60)
                    except requests.RequestException as e:
                        self._fetch_error = f"{type(e).__name__} on {path}"
                        continue
                    if r.status_code != 200:
                        self._fetch_error = f"HTTP {r.status_code} on {path}"
                    elif r.content[:4] not in IMAGE_MAGIC:
                        self._fetch_error = f"{path} returned {len(r.content)}B of non-image data"
                    else:
                        return r.content

            if time.time() >= deadline:
                self._fetch_error = (f"{self._fetch_error or 'not readable'} "
                                     f"after {attempt} attempt(s) over "
                                     f"{FETCH_TIMEOUT}s")
                return b""
            time.sleep(FETCH_POLL)

    # A filename for a prompt, stable across runs so caching works.
    @staticmethod
    def slug(text: str, limit: int = 40) -> str:
        """A filename for a prompt, stable across runs so caching works."""
        s = SAFE_RE.sub("-", (text or "image").lower()).strip("-")
        return (s[:limit].rstrip("-") or "image")
