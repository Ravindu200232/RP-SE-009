"""A photograph of the thing the user is pointing at.

When someone clicks an element in the preview, or draws a red ring around a
corner of it, the words they type are only half the request; the other half is
what it currently looks like. "Make this tighter" means nothing without the
picture, and a description of a picture is not the picture.

So both gestures produce a screenshot that travels with the message: the
element on its own for a click, the page with the drawing still on it for a
stroke. Both are taken with the engine's own Chrome - the same browser that
runs the journeys, not a second automation stack beside it - and one browser is
kept warm between them, because launching Chrome per click turns a two-element
selection into a ten-second wait.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import threading
import time

log = logging.getLogger("shots")

PAD = 14                    # a little room around the element, for context
INK_PAD = 24                # a drawing means the area around it too
MIN_W, MIN_H = 120, 60
INK_MIN_W, INK_MIN_H = 260, 190
MAX_W, MAX_H = 1600, 1600
IDLE_CLOSE = 180            # seconds of quiet before Chrome is released
MAX_B64 = 400_000


class _Warm:
    """One Chrome, shared by every capture, closed when nobody is clicking."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.browser = None
        self.page = None
        self.timer: threading.Timer | None = None

    def page_for(self, url: str):
        from builder_agent.browser import Browser

        if self.browser is None or not self.browser.running:
            self.browser = Browser()          # no event bus: nothing to stream
            self.browser.launch()
            self.page = self.browser.open_tab("about:blank")
        self.page.navigate(url)
        return self.page

    def touch(self) -> None:
        if self.timer:
            self.timer.cancel()
        self.timer = threading.Timer(IDLE_CLOSE, self.close)
        self.timer.daemon = True
        self.timer.start()

    def close(self) -> None:
        with self.lock:
            browser, self.browser, self.page = self.browser, None, None
        try:
            if browser:
                browser.close()
        except Exception as error:                               # noqa: BLE001
            log.debug(f"closing the capture browser: {error}")


_WARM = _Warm()


# The drawing is replayed onto the real page before the photograph, so what the
# model sees is the annotation over the live layout rather than a canvas the
# studio composited on top of an iframe it cannot read.
_INK_JS = """
(strokes) => {
  const old = document.getElementById('__af_ink'); if (old) old.remove();
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.id = '__af_ink';
  const w = Math.max(document.documentElement.scrollWidth, window.innerWidth);
  const h = Math.max(document.documentElement.scrollHeight, window.innerHeight);
  svg.setAttribute('width', w); svg.setAttribute('height', h);
  Object.assign(svg.style, {
    position: 'absolute', left: '0', top: '0', width: w + 'px',
    height: h + 'px', pointerEvents: 'none', zIndex: '2147483647'
  });
  for (const stroke of strokes) {
    if (!stroke || stroke.length < 2) continue;
    const line = document.createElementNS(ns, 'polyline');
    line.setAttribute('points', stroke.map(p => p.x + ',' + p.y).join(' '));
    line.setAttribute('fill', 'none');
    line.setAttribute('stroke', '#ff2d55');
    line.setAttribute('stroke-width', '3');
    line.setAttribute('stroke-opacity', '0.85');
    line.setAttribute('stroke-linecap', 'round');
    line.setAttribute('stroke-linejoin', 'round');
    svg.appendChild(line);
  }
  document.body.appendChild(svg);
  return JSON.stringify({ w: w, h: h });
}
"""


def ink_bounds(strokes) -> dict:
    """The page box the drawing covers, with room around it."""
    points = [point for stroke in (strokes or []) for point in stroke
              if isinstance(point, dict)]
    if not points:
        return {}
    xs = [float(p.get("x") or 0) for p in points]
    ys = [float(p.get("y") or 0) for p in points]
    x0, y0 = min(xs) - INK_PAD, min(ys) - INK_PAD
    x1, y1 = max(xs) + INK_PAD, max(ys) + INK_PAD
    return {"x": max(0.0, x0), "y": max(0.0, y0),
            "width": min(max(x1 - x0, INK_MIN_W), MAX_W),
            "height": min(max(y1 - y0, INK_MIN_H), MAX_H),
            "scale": 1}


def _clip(rect: dict, scroll: dict) -> dict:
    """The element's box in page coordinates, with a margin."""
    x = float((rect or {}).get("x") or 0) + float((scroll or {}).get("x") or 0)
    y = float((rect or {}).get("y") or 0) + float((scroll or {}).get("y") or 0)
    w = max(float((rect or {}).get("w") or 0), MIN_W)
    h = max(float((rect or {}).get("h") or 0), MIN_H)
    return {"x": max(0.0, x - PAD), "y": max(0.0, y - PAD),
            "width": min(w + PAD * 2, MAX_W), "height": min(h + PAD * 2, MAX_H),
            "scale": 1}


def _shrink(png: bytes) -> str:
    """A chat attachment, not a print. Small enough to travel in a message."""
    encoded = base64.b64encode(png).decode()
    try:
        from PIL import Image

        image = Image.open(io.BytesIO(png)).convert("RGB")
        for bounds, quality in (((900, 700), 80), ((520, 400), 68)):
            image.thumbnail(bounds)
            out = io.BytesIO()
            image.save(out, "JPEG", quality=quality, optimize=True)
            encoded = base64.b64encode(out.getvalue()).decode()
            if len(encoded) <= MAX_B64:
                return encoded
    except Exception as error:                                   # noqa: BLE001
        log.debug(f"screenshot resize failed: {error}")
    return encoded


def capture_element(route: str, *, viewport: dict, scroll: dict, rect: dict,
                    port: int = 5173) -> str:
    """Base64 JPEG of one element on the running preview, or "" if it failed."""
    return _shoot(route, viewport=viewport, port=port,
                  clip=_clip(rect, scroll), strokes=None, what="element")


def capture_drawing(route: str, *, viewport: dict, strokes: list,
                    port: int = 5173) -> str:
    """Base64 JPEG of the page with the user's red drawing still on it."""
    clip = ink_bounds(strokes)
    if not clip:
        return ""
    return _shoot(route, viewport=viewport, port=port,
                  clip=clip, strokes=strokes, what="drawing")


def _shoot(route: str, *, viewport: dict, port: int, clip: dict,
           strokes, what: str) -> str:
    width = int((viewport or {}).get("w") or 1280)
    height = int((viewport or {}).get("h") or 800)
    url = f"http://127.0.0.1:{port}{route or '/'}"

    with _WARM.lock:
        try:
            page = _WARM.page_for(url)
            page.cdp.send("Emulation.setDeviceMetricsOverride",
                          {"width": width, "height": height,
                           "deviceScaleFactor": 1, "mobile": width <= 600},
                          page.session)
            # Give the page a moment to lay itself out at that width, or the
            # box measured in the studio's iframe lands on the wrong thing.
            time.sleep(0.6)
            if strokes:
                page.evaluate(f"({_INK_JS})({json.dumps(strokes)})")
                time.sleep(0.2)
            data = page.cdp.send(
                "Page.captureScreenshot",
                {"format": "png", "clip": clip, "captureBeyondViewport": True},
                page.session, timeout=45).get("data", "")
            page.cdp.send("Emulation.clearDeviceMetricsOverride", {}, page.session)
        except Exception as error:                               # noqa: BLE001
            log.warning(f"{what} capture: {error}")
            _WARM.close()
            return ""
    _WARM.touch()
    return _shrink(base64.b64decode(data)) if data else ""
