"""Screenshot QA — captures key pages with Playwright (optional).

Two modes:
  1. Static analysis (default): reads generated JSX files and checks them for
     SRS section coverage, domain relevance, and common anti-patterns. Requires
     no server and no Playwright.
  2. Screenshot mode (AI_DESIGNER_SCREENSHOT_QA=1): starts a temporary `next start`
     server, captures screenshots with Playwright, shuts it down.

Both modes return the same result structure so design_critic.py can consume
either without branching.
"""
import os
import re
import subprocess
import time
from typing import Optional


# ── Static analysis (default mode) ───────────────────────────────────────────

_BAD_PATTERNS = [
    (r"\blorem\b", "Contains lorem ipsum placeholder text"),
    (r"\bplaceholder text\b", "Contains generic placeholder text"),
    (r"PLACEHOLDER|TODO:|FIXME:", "Contains unresolved placeholders"),
    (r"class=(?!Name)", "Uses HTML class= instead of className="),
]


def _read_jsx(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _check_file(path: str, required_sections: list[str]) -> dict:
    """Analyse a single JSX file for quality issues."""
    code = _read_jsx(path)
    if not code:
        return {"status": "missing", "issues": ["File not found"], "sections_found": []}

    issues = []
    for pattern, msg in _BAD_PATTERNS:
        if re.search(pattern, code, re.IGNORECASE):
            issues.append(msg)

    # Check required section keywords appear somewhere in the page
    sections_found = [s for s in required_sections if s.lower() in code.lower()]
    sections_missing = [s for s in required_sections if s.lower() not in code.lower()]
    if sections_missing:
        issues.append(f"Sections possibly missing: {', '.join(sections_missing[:4])}")

    return {
        "status": "ok",
        "issues": issues,
        "sections_found": sections_found,
        "sections_missing": sections_missing,
    }


def analyze_page_files(output_dir: str, srs_data: dict) -> list[dict]:
    """Static analysis of generated public pages — no server needed."""
    doc = (srs_data.get("srs_document") or srs_data) if isinstance(srs_data, dict) else {}
    pub_pages = (doc.get("public_landing_website") or {}).get("pages") or []

    results = []
    marketing_root = os.path.join(output_dir, "src", "app", "(marketing)")

    if not os.path.isdir(marketing_root):
        return [{"name": "all", "route": "/", "status": "skipped",
                 "error": "No marketing pages directory", "issues": []}]

    for entry in os.listdir(marketing_root)[:8]:
        page_dir = os.path.join(marketing_root, entry)
        page_file = os.path.join(page_dir, "page.jsx")
        if not os.path.isfile(page_file):
            continue

        # Find the SRS page that matches this slug
        matching_page = next(
            (p for p in pub_pages if entry in str(p.get("page_name", "")).lower()
             or entry in str(p.get("route", "")).lower()),
            {}
        )
        required = matching_page.get("sections", []) if isinstance(matching_page.get("sections"), list) else []

        analysis = _check_file(page_file, required)
        results.append({
            "name": entry,
            "route": matching_page.get("route", f"/{entry}"),
            "status": analysis["status"],
            "issues": analysis["issues"],
            "sections_found": analysis.get("sections_found", []),
            "sections_missing": analysis.get("sections_missing", []),
            "screenshot_b64": None,
        })

    return results or [{"name": "home", "route": "/", "status": "skipped",
                        "error": "No pages analysed", "issues": []}]


# ── Screenshot mode (requires Playwright + AI_DESIGNER_SCREENSHOT_QA=1) ──────

def _find_free_port(start: int = 4200) -> int:
    import socket
    for port in range(start, start + 100):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    return start


def _wait_for_server(url: str, timeout: float = 30.0) -> bool:
    try:
        import urllib.request
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                urllib.request.urlopen(url, timeout=2)
                return True
            except Exception:
                time.sleep(1)
    except Exception:
        pass
    return False


def capture_screenshots(
    output_dir: str,
    srs_data: dict,
    key_routes: Optional[list[str]] = None,
) -> list[dict]:
    """Capture screenshots using Playwright.

    Starts `next start` on a free port, captures screenshots, kills the server.
    Returns same structure as analyze_page_files.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return [{"name": "all", "route": "/", "status": "skipped",
                 "error": "Playwright not installed — install with: pip install playwright && playwright install chromium",
                 "issues": []}]

    port = _find_free_port(4200)
    url_base = f"http://127.0.0.1:{port}"
    shots_dir = os.path.join(output_dir, "_screenshots")
    os.makedirs(shots_dir, exist_ok=True)

    # Determine routes to capture
    if not key_routes:
        doc = (srs_data.get("srs_document") or srs_data) if isinstance(srs_data, dict) else {}
        pub = (doc.get("public_landing_website") or {}).get("pages", [])
        key_routes = ["/", "/login", "/dashboard"]
        for p in pub[:3]:
            r = p.get("route", "")
            if r and r not in key_routes:
                key_routes.append(r)

    proc: Optional[subprocess.Popen] = None
    results: list[dict] = []

    try:
        proc = subprocess.Popen(
            ["npm", "start", "--", "-p", str(port)],
            cwd=output_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=True,
        )
        if not _wait_for_server(url_base, timeout=40):
            return [{"name": "all", "route": "/", "status": "error",
                     "error": "Server did not start in 40s", "issues": []}]

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(viewport={"width": 1280, "height": 720})

            for route in key_routes:
                name = route.strip("/").replace("/", "_") or "home"
                shot_path = os.path.join(shots_dir, f"{name}.png")
                result: dict = {"name": name, "route": route, "status": "ok",
                                "error": None, "issues": [], "screenshot_b64": None}
                try:
                    pg = ctx.new_page()
                    pg.goto(f"{url_base}{route}", timeout=12000, wait_until="networkidle")
                    time.sleep(0.3)
                    pg.screenshot(path=shot_path, full_page=True)
                    with open(shot_path, "rb") as f:
                        import base64
                        result["screenshot_b64"] = base64.b64encode(f.read()[:51200]).decode()
                    result["screenshot_path"] = shot_path
                    pg.close()
                except Exception as e:
                    result["status"] = "error"
                    result["error"] = str(e)[:120]
                results.append(result)

            browser.close()

    except Exception as e:
        results = [{"name": "all", "route": "/", "status": "error",
                    "error": str(e)[:120], "issues": []}]
    finally:
        if proc:
            try:
                proc.terminate()
            except Exception:
                pass

    return results


def run_qa(
    output_dir: str,
    srs_data: dict,
    key_routes: Optional[list[str]] = None,
) -> list[dict]:
    """Entry point: use screenshot mode if enabled, otherwise static analysis."""
    if os.getenv("AI_DESIGNER_SCREENSHOT_QA") == "1":
        return capture_screenshots(output_dir, srs_data, key_routes)
    return analyze_page_files(output_dir, srs_data)


def summarize(results: list[dict]) -> str:
    """Human-readable summary for log output."""
    ok = sum(1 for r in results if r.get("status") == "ok" and not r.get("issues"))
    warn = sum(1 for r in results if r.get("status") == "ok" and r.get("issues"))
    err = sum(1 for r in results if r.get("status") not in ("ok", "skipped"))
    skip = sum(1 for r in results if r.get("status") == "skipped")
    lines = [f"QA: {ok} clean, {warn} warnings, {err} errors, {skip} skipped"]
    for r in results:
        icon = "✓" if (r["status"] == "ok" and not r.get("issues")) else ("⚠" if r.get("issues") else "✗")
        detail = "; ".join(r.get("issues", [])[:2]) or r.get("error", "")
        lines.append(f"  {icon} {r['name']} ({r.get('route','')}) {detail}")
    return "\n".join(lines)
