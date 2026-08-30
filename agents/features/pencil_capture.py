"""Capture an annotated preview region with Playwright at the iframe viewport."""
from __future__ import annotations

import base64
import io
import logging
from dataclasses import dataclass, field

# Source: feature_prompts.py — imported helper(s) come from this file.
from agents.features.feature_prompts import feature_prompt

log = logging.getLogger("capture")

PAD = 24
MIN_W, MIN_H = 240, 180


MAX_B64 = 900_000


@dataclass
class CaptureResult:
    png_b64: str = ""
    page_b64: str = ""
    crop: dict = field(default_factory=dict)
    page_size: dict = field(default_factory=dict)
    logged_in: bool = False
    error: str = ""

    # Checks whether this captured visual result contains usable image data.
    def ok(self) -> bool:
        """Return whether this captured visual result contains usable image data."""
        return bool(self.png_b64)

    # Returns the image payloads that should be shown to the vision model.
    def vision_images(self) -> list[str]:
        """Return the image payloads that should be shown to the vision model."""
        return [image for image in (self.png_b64, self.page_b64) if image]


# Keep a vision screenshot clear without sending full-size pixels.
def _small_screenshot(png: bytes, size: tuple[int, int]) -> str:
    """Keep a vision screenshot clear without sending full-size pixels."""
    encoded = base64.b64encode(png).decode()
    try:
        from PIL import Image

        image = Image.open(io.BytesIO(png)).convert("RGB")
        for bounds, quality in ((size, 82),
                                ((size[0] // 2, size[1] // 2), 72)):
            image.thumbnail(bounds)
            out = io.BytesIO()
            image.save(out, "JPEG", quality=quality, optimize=True)
            encoded = base64.b64encode(out.getvalue()).decode()
            if len(encoded) <= MAX_B64:
                break
    except Exception as e:                                  # pragma: no cover
        log.debug(f"screenshot resize failed: {e}")
    return encoded


# Calculates the smallest rectangular area that contains all captured pencil strokes.
def strokes_bounds(strokes, pad: int = PAD) -> dict:
    """Prepare the strokes bounds value or state used by this focused pipeline step."""
    pts = [p for s in (strokes or []) for p in s if isinstance(p, dict)]
    if not pts:
        return {}
    xs = [p.get("x", 0) for p in pts]
    ys = [p.get("y", 0) for p in pts]
    x0, y0 = min(xs) - pad, min(ys) - pad
    x1, y1 = max(xs) + pad, max(ys) + pad
    return {"x": x0, "y": y0, "width": max(x1 - x0, MIN_W),
            "height": max(y1 - y0, MIN_H)}


_OVERLAY_JS = """
(strokes) => {
  const old = document.getElementById('__lc_ink'); if (old) old.remove();
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.id = '__lc_ink';
  const w = Math.max(document.documentElement.scrollWidth, window.innerWidth);
  const h = Math.max(document.documentElement.scrollHeight, window.innerHeight);
  svg.setAttribute('width', w); svg.setAttribute('height', h);
  Object.assign(svg.style, {
    position: 'absolute', left: '0', top: '0', width: w + 'px',
    height: h + 'px', pointerEvents: 'none', zIndex: '2147483647'
  });
  for (const stroke of strokes) {
    if (!stroke || stroke.length < 2) continue;
    const pl = document.createElementNS(ns, 'polyline');
    pl.setAttribute('points', stroke.map(p => p.x + ',' + p.y).join(' '));
    pl.setAttribute('fill', 'none');
    pl.setAttribute('stroke', '#ff2d55');
    pl.setAttribute('stroke-width', '3');
    pl.setAttribute('stroke-opacity', '0.75');
    pl.setAttribute('stroke-linecap', 'round');
    pl.setAttribute('stroke-linejoin', 'round');
    svg.appendChild(pl);
  }
  document.body.appendChild(svg);
  return { w: w, h: h };
}
"""


# Captures region so the next step can work from real evidence.
def capture_region(route: str, *, viewport: dict, scroll: dict, strokes: list,
                   port: int = 5173, login: tuple = None,
                   login_endpoint: str = "", timeout: int = 45_000
                   ) -> CaptureResult:
    """Capture region so the next step can work from real evidence."""
    crop = strokes_bounds(strokes)
    if not crop:
        return CaptureResult(error="nothing was drawn")

    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:                                  # pragma: no cover
        return CaptureResult(error=f"Playwright is unavailable: {e}", crop=crop)

    vw = int((viewport or {}).get("w") or 1280)
    vh = int((viewport or {}).get("h") or 800)
    base = f"http://127.0.0.1:{port}"
    res = CaptureResult(crop=crop)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(viewport={"width": vw, "height": vh},
                                      device_scale_factor=1)
            try:
                if login and login_endpoint:
                    email, password = login
                    try:
                        r = ctx.request.post(
                            base + login_endpoint,
                            data={"email": email, "password": password},
                            timeout=20_000)
                        res.logged_in = r.status < 400
                    except Exception as e:
                        log.info(f"pre-login failed: {e}")

                page = ctx.new_page()
                page.goto(base + (route or "/"), wait_until="load",
                          timeout=timeout)

                try:
                    page.wait_for_load_state("networkidle", timeout=8_000)
                except Exception:
                    pass
                page.wait_for_timeout(700)
                sx = int((scroll or {}).get("x") or 0)
                sy = int((scroll or {}).get("y") or 0)
                if sx or sy:
                    page.evaluate(f"window.scrollTo({sx}, {sy})")
                    page.wait_for_timeout(300)

                size = page.evaluate(_OVERLAY_JS, strokes)
                res.page_size = size

                clip = dict(crop)
                clip["x"] = max(0, min(clip["x"], size["w"] - 10))
                clip["y"] = max(0, min(clip["y"], size["h"] - 10))
                clip["width"] = max(10, min(clip["width"], size["w"] - clip["x"]))
                clip["height"] = max(10, min(clip["height"], size["h"] - clip["y"]))
                res.crop = clip

                crop_png = page.screenshot(clip=clip, type="png", full_page=True)
                page_png = page.screenshot(type="png", full_page=True)
                res.png_b64 = _small_screenshot(crop_png, (960, 720))
                res.page_b64 = _small_screenshot(page_png, (1200, 1600))
            finally:
                # From: agents/planner/builder/write_stream.py
                ctx.close()
                # From: agents/planner/builder/write_stream.py
                browser.close()
    except Exception as e:
        res.error = str(e)[:200]
        log.warning(f"capture failed: {e}")
    return res


# From: agents/features/feature_prompts.py
PENCIL_SYSTEM = feature_prompt("PENCIL", foundation=True)
