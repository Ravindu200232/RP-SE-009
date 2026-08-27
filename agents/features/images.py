"""
Generated images, from a Fooocus running on this machine or another one.

AgentForge writes apps that want pictures — a hero banner, seeded product photos, a
poster on a marketing page — and until now it wrote `<img src="/placeholder">`
and hoped. This module turns "the app needs an image of X" into a real PNG in
the project's `public/` folder.

**Why it drives Fooocus's Gradio endpoint rather than importing it.** Fooocus
ships no REST API and no `api_name` on any handler, so there is nothing to call
by name. What it does expose, because Gradio always does, is `/run/predict`
with a function index — and the generate handler takes 153 positional
arguments. Building that by hand would be unreadable and would break on every
Fooocus release.

So the argument list is read from Fooocus's own `fooocus_config.json`, which
records the default value of every component in the UI. AgentForge takes those
defaults verbatim and overrides four of them: the prompt, the aspect ratio, how
many images, and the seed. That is the whole integration, and it survives a
Fooocus upgrade as long as the config still describes the UI — which is the
file Fooocus writes to describe the UI.

**Why the host is configurable.** The workstation with the GPU is not always
the workstation running AgentForge. Point `image_host` at the other machine (start
Fooocus there with `--listen`) and everything else is unchanged.
"""
import base64
import json
import logging
import random
import re
import time
from pathlib import Path

import requests

log = logging.getLogger("images")


class _NoQueue(Exception):
    """This Gradio has no WebSocket queue — try the newer HTTP protocol."""


DEFAULT_HOSTS = ("http://127.0.0.1:7865", "http://127.0.0.1:7860")


PROMPT_LABEL = None
NEGATIVE_LABEL = "Negative Prompt"
ASPECT_LABEL = "Aspect Ratios"
COUNT_LABEL = "Image Number"
SEED_LABEL = "Seed"


SAFE_RE = re.compile(r"[^a-z0-9]+")

GENERATE_TIMEOUT = 600


class ImageAgent:
    """
    One Fooocus, wherever it is running.

    Every method degrades to "no image" rather than raising: an app that could
    not get a picture still has to build, and a missing banner is a smaller
    problem than a failed generation.
    """

    def __init__(self, host: str = "", config_path: str = "",
                 callbacks: dict = None, enabled: bool = True):
        self.host = (host or "").rstrip("/")
        self.config_path = config_path or ""
        self.cb = callbacks or {}
        self.enabled = enabled
        self._payload = None
        self._fn_index = None
        self._gallery_index = None
        self._checked = None

    def _fire(self, name, *a):
        fn = self.cb.get(name)
        if fn:
            try:
                fn(*a)
            except Exception as e:
                log.warning(f"callback {name} failed: {e}")

    def _log(self, lvl, txt):
        self._fire("on_log", lvl, txt)
        log.info(txt)

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

    def available(self) -> bool:
        return bool(self.enabled and self.base_url())

    def _load_template(self) -> bool:
        """
        Read Fooocus's UI description and keep the defaults for every input.

        Preferred over the file on disk: `/config` is what the *running*
        Fooocus is actually using, and a stale `fooocus_config.json` from an
        older version would build an argument list the server rejects.
        """
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

    def _slot(self, label: str, fallback: int) -> int:
        return getattr(self, "_labels", {}).get(label, fallback)

    ASPECTS = {
        "banner":   "1664*576",
        "wide":     "1344*768",
        "landscape": "1152*896",
        "square":   "1024*1024",
        "portrait": "896*1152",
        "poster":   "832*1216",
    }

    def generate(self, prompt: str, out_path: Path, *, aspect: str = "landscape",
                 seed: int = 0, force: bool = False) -> bool:
        """
        Make one image and write it to `out_path`. False when it could not.

        Already-existing files are left alone: image generation is the slowest
        thing in a build by an order of magnitude, and a rebuild that reuses
        what is already on disk is the difference between seconds and minutes.

        `force` is for the caller who is asking for a DIFFERENT picture rather
        than for this picture to exist — the logo panel, where "try another"
        means exactly that. Without it the panel wrote every attempt to
        `logo.png`, found it already there, and handed back the first image
        every time: a regenerate button that could not regenerate.

        `seed = 0` means "any picture", and is answered with a RANDOM seed.
        Passing the literal 0 through made it a fixed seed instead, so the same
        prompt drew the same image forever: measured, three "try another"
        presses returned byte-identical files after 31 seconds of GPU each —
        `force` was defeating the file cache and the seed was putting the same
        picture back. Pass a non-zero seed to reproduce one deliberately.
        """
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
        data = self._predict(url, args)
        if data is None:
            return False

        raw = self._first_image(data)
        if not raw:
            self._log("WARN", "   ⚠ Fooocus returned no image")
            return False
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(raw)
        except OSError as e:
            self._log("WARN", f"   ⚠ could not write {out_path.name}: {e}")
            return False
        self._log("INFO", f"   ✅ {out_path.name} in {time.time() - t0:.0f}s")
        return True

    def _predict(self, url: str, args: list):
        """
        Run the generate handler and return its final output list.

        Fooocus's generate is a *generator* behind Gradio's queue: it yields
        progress for a minute, then the images. `/run/predict` answers such a
        function immediately with whatever the first yield held — a progress
        bar — which is why the obvious call returns a clean 200 and no picture.

        Gradio 3.x runs its queue over a WebSocket. The handshake is fixed:
        the server says `send_hash`, we answer with the session; it says
        `send_data`, we answer with the arguments; then it streams progress
        until `process_completed` carries the output. Gradio 4 replaced this
        with SSE at `/queue/join` + `/queue/data`, so both are tried — this one
        first, because it is what is actually running here.
        """
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

    def _predict_ws(self, ws_url: str, session: str, args: list,
                    fn_index: int):
        """The Gradio 3.x queue handshake. Raises `_NoQueue` when unsupported."""
        import asyncio

        try:
            import websockets
        except ImportError:
            raise _NoQueue("websockets is not installed")

        async def go():
            try:
                conn = await asyncio.wait_for(
                    websockets.connect(f"{ws_url}/queue/join",
                                       max_size=None, open_timeout=20),
                    timeout=25)
            except Exception as e:
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

        return asyncio.run(go())

    def _first_image(self, data) -> bytes:
        """
        The bytes of the first image in a Gradio response.

        Gradio answers with either a base64 data URI or a path on the server,
        depending on version and component, so both are handled rather than
        guessed at.
        """
        def walk(node):
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

    def _fetch(self, ref: str) -> bytes:
        """A file Fooocus reported by path — read it, or pull it over HTTP."""
        p = Path(ref)
        if p.is_file():
            try:
                return p.read_bytes()
            except OSError:
                pass
        url = self.base_url()
        if not url:
            return b""
        for path in (f"/file={ref}", f"/file/{ref}", ref):
            try:
                r = requests.get(url + path if path.startswith("/") else path,
                                 timeout=60)
                if r.status_code == 200 and r.content[:4] in (b"\x89PNG", b"\xff\xd8\xff\xe0",
                                                              b"RIFF"):
                    return r.content
            except requests.RequestException:
                continue
        return b""

    @staticmethod
    def slug(text: str, limit: int = 40) -> str:
        """A filename for a prompt, stable across runs so caching works."""
        s = SAFE_RE.sub("-", (text or "image").lower()).strip("-")
        return (s[:limit].rstrip("-") or "image")
