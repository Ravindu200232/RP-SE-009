"""Bounded browser smoke checks for generated HTML prototypes.

Prototype pages are static files, so they do not need a project server just to
prove that their scripts parse and their first render does not throw.  This
module opens every page in an isolated browser and returns the
diagnostics that would otherwise only be discovered after the drawing was
approved.  It deliberately reuses the same CDP diagnostic rules as the E2E
journey tool without running a journey or clicking controls.
"""
from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .browser import Browser
from .errors import ToolError
from .journeys import _is_ignorable_diagnostic


MAX_PAGES = 40
PAGE_TIMEOUT = 15.0
MAX_SCRIPTS = 80
MAX_SCRIPT_BYTES = 250_000
LOCAL_REFERENCE = re.compile(r"\b(?:href|src)=[\"']([^\"']+)[\"']", re.I)


def _prototype(root: Path) -> Path:
    """Resolve either a workspace root or its prototype directory."""
    folder = Path(root) / ".agentforge" / "prototype"
    return folder if folder.is_dir() else Path(root)


def _critical(diagnostic: dict) -> bool:
    kind = str(diagnostic.get("kind") or "")
    return (kind in ("page error", "console error", "request failed")
            or kind.startswith("HTTP 5")) and not _is_ignorable_diagnostic(diagnostic)


def _script_error(path: Path) -> str:
    """Return the first Node syntax error for a generated script, if any."""
    if not path.is_file():
        return ""
    try:
        result = subprocess.run(
            ["node", "--check", str(path)],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        # A missing checker must not prevent the browser pass from running.
        return ""
    if result.returncode == 0:
        return ""
    for line in (result.stderr or "").splitlines():
        if "SyntaxError" in line:
            return line.strip()[:240]
    return "it does not parse"


_SCRIPT_OPEN = re.compile(r"<script\b[^>]*>", re.I)
_SCRIPT_CLOSE = re.compile(r"</script\s*>", re.I)


_INLINE = re.compile(r"<script\b(?![^>]*\bsrc=)[^>]*>(.*?)</script\s*>", re.I | re.S)


def _inline_scripts_parse(text: str) -> bool:
    """Does every inline script on this page parse as JavaScript?"""
    import os
    import tempfile
    for block in _INLINE.findall(text):
        if not block.strip():
            continue
        handle = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                             encoding="utf-8")
        try:
            handle.write(block)
            handle.close()
            if _script_error(Path(handle.name)):
                return False
        finally:
            try:
                os.unlink(handle.name)
            except OSError:
                pass
    return True


def repair_script_tags(path: Path) -> str:
    """Remove a stray <script> tag, but only when doing so is proved to help.

    Two shapes turn up, both from an edit that rewrote a block and kept the
    wrapper: an opening tag written twice in a row, and a closing tag inserted
    before the code it was meant to follow. The page stops parsing at that
    point, so `Unexpected token '<'` or `Unexpected end of input` is all the
    browser can say about it.

    Which tag is the stray one cannot be decided by position - the surplus
    closing tag was in the middle of the block, not at its end, and removing the
    last one merged two scripts and broke a page that had only one fault. So
    each candidate is tried and kept only if every inline script on the page
    then parses. A page that cannot be fixed this way is left exactly as it is
    and reported, because a half-repair is worse than an honest finding.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    if _inline_scripts_parse(text):
        return ""

    found = _without_stray_tags(text)
    if found is None:
        return ""
    fixed, notes = found
    try:
        path.write_text(fixed, encoding="utf-8")
    except OSError:
        return ""
    return "; ".join(sorted(set(notes)))


_ANY_TAG = re.compile(r"<script\b([^>]*)>|</script\s*>", re.I)


def _strays(text: str):
    """The tags that cannot be where they are, with what each one was.

    Found by pairing the tags in order rather than by looking for a shape: an
    opening tag while one is already open is illegal wherever it sits, and a
    closing tag with nothing open is stray wherever it sits.

    A `<script src=...></script>` is a matched pair and is never offered. It
    was, once, and deleting its closing tag let the include swallow the rest of
    the page - which then "parsed", because an external script's body is not
    checked. Repairing a page by silently dropping a file it loads is worse
    than leaving the page broken.
    """
    tags = list(_ANY_TAG.finditer(text))
    depth = 0
    for index, hit in enumerate(tags):
        attributes = hit.group(1)
        if attributes is None:                       # a closing tag
            depth = max(0, depth - 1)
            # Offer closing tag candidates for repair while preserving script include tag integrity.
            before = tags[index - 1] if index else None
            if before is not None and before.group(1) and "src=" in before.group(1).lower():
                continue
            yield ("a stray </script> closed a block early",
                   text[:hit.start()] + text[hit.end():])
            continue
        # Scripts cannot nest, so an opening tag while one is open is stray.
        if depth:
            yield ("a <script> tag was opened while one was already open",
                   text[:hit.start()] + text[hit.end():])
        depth += 1


def _without_stray_tags(text: str, depth: int = 3):
    """(page, notes) once every inline script parses, or None if never.

    Searched rather than counted. A page carrying both faults gets *more*
    unbalanced when the duplicate opening tag goes - closings then outnumber
    openings - so any measure of "closer to balanced" rejects the very move
    that leads to the fix. Whether the scripts parse is the only test that
    holds, so it is the only one used.
    """
    if _inline_scripts_parse(text):
        return text, []
    if depth <= 0:
        return None
    for note, attempt in _strays(text):
        deeper = _without_stray_tags(attempt, depth - 1)
        if deeper is not None:
            return deeper[0], [note] + deeper[1]
    return None


def repair_all_script_tags(root: Path) -> list[dict]:
    """Balance every page's script tags before anything tries to parse them."""
    folder = _prototype(Path(root).resolve())
    if not folder.is_dir():
        return []
    repaired = []
    for path in sorted(folder.rglob("*.html"))[:MAX_PAGES]:
        note = repair_script_tags(path)
        if note:
            repaired.append({"page": path.name, "kind": "markup repaired", "text": note})
    return repaired


def static_validate(root: Path) -> list[dict]:
    """Run deterministic checks for every generated page before browser I/O.

    Static findings are deliberately collected in one pass.  The caller can
    combine this list with browser diagnostics and send the affected files to
    one repair request, instead of repairing one class of problem per round.
    """
    root = Path(root).resolve()
    folder = _prototype(root)
    if not folder.is_dir():
        return []

    findings: list[dict] = []
    scripts = []
    for path in sorted(folder.rglob("*.js")):
        # Skip bundled third-party vendor libraries during script syntax verification.
        parts = {part.lower() for part in path.relative_to(folder).parts}
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if "node_modules" in parts or ("assets" in parts and "static" in parts):
            continue
        if size > MAX_SCRIPT_BYTES:
            continue
        scripts.append(path)
        if len(scripts) >= MAX_SCRIPTS:
            break
    for path in scripts:
        error = _script_error(path)
        if error:
            findings.append({
                "page": path.relative_to(folder).as_posix(),
                "kind": "JavaScript syntax error",
                "text": error,
            })

    # This check is file-only here.  Browser style inspection would navigate
    # the same pages a second time before the runtime diagnostics pass.
    try:
        from . import styles
        bare = styles.unstyled(folder)
    except (OSError, ImportError):
        bare = []
    for name in bare:
        findings.append({
            "page": str(name),
            "kind": "unstyled page",
            "text": "The page has no usable linked stylesheet.",
        })

    # Validate local prototype file link targets statically before launching browser checks.
    pages = sorted(folder.rglob("*.html"))[:MAX_PAGES]
    known = {path.resolve() for path in folder.rglob("*") if path.is_file()}
    for page in pages:
        try:
            text = page.read_text("utf-8")
        except OSError:
            continue
        for reference in LOCAL_REFERENCE.findall(text):
            value = reference.strip()
            if (not value or value.startswith(("#", "//", "/", "http:", "https:",
                                                "mailto:", "tel:", "javascript:", "data:",
                                                "${", "{{", "<%"))
                    or "{" in value or "}" in value):
                continue
            target_path = unquote(urlsplit(value).path)
            if not target_path:
                continue
            target = (page.parent / target_path).resolve()
            if target not in known:
                findings.append({
                    "page": page.relative_to(folder).as_posix(),
                    "kind": "broken local link",
                    "text": f"{value} does not resolve to a generated file.",
                })
    return findings


def validate(root: Path, browser: Browser | None = None) -> list[dict]:
    """Return browser diagnostics for the HTML files under ``root``.

    The check is intentionally bounded and deterministic: at most forty pages
    are visited, one tab is reused, and a missing browser is reported as a
    warning-shaped finding instead of crashing the designer process.  The
    caller can feed findings back to the model for one repair pass.
    """
    root = Path(root).resolve()
    folder = _prototype(root)
    pages = sorted(folder.rglob("*.html"))[:MAX_PAGES] if folder.is_dir() else []
    if not pages:
        return []

    owned = browser is None
    engine = browser or Browser()
    findings: list[dict] = []
    try:
        try:
            page = engine.open_tab("about:blank")
        except (OSError, ToolError) as error:
            return [{"page": "", "kind": "browser unavailable", "text": str(error)[:400]}]

        for path in pages:
            page.reset_diagnostics()
            try:
                page.navigate(path.as_uri(), timeout=PAGE_TIMEOUT)
                # A static page can finish navigation before a deferred script
                # has run.  Keep this short so a broken drawing cannot loop.
                time.sleep(0.15)
            except ToolError as error:
                findings.append({"page": path.relative_to(folder).as_posix(), "kind": "navigation error",
                                 "text": str(error)[:400]})
                continue
            for diagnostic in page.diagnostics:
                if _critical(diagnostic):
                    findings.append({
                        "page": path.relative_to(folder).as_posix(),
                        "kind": diagnostic.get("kind", "browser diagnostic"),
                        "text": str(diagnostic.get("text") or "")[:400],
                        "url": str(diagnostic.get("url") or "")[:300],
                    })
    finally:
        if owned:
            engine.close()
    return findings


def validate_all(root: Path, browser: Browser | None = None) -> list[dict]:
    """Collect static and browser findings in one bounded validation pass.

    Unbalanced script tags are repaired first. They have one correct fix and
    they hide everything after them: a page whose first script stops parsing
    reports one syntax error and nothing about the page itself, so validating
    before repairing them wastes the pass.
    """
    repair_all_script_tags(root)
    findings = static_validate(root)
    findings.extend(validate(root, browser=browser))
    return findings


def repair_prompt(findings: list[dict]) -> str:
    """Turn bounded browser findings into a concise model repair instruction."""
    rows = []
    # Consolidate issues across all inspected pages into a single grouped repair request.
    for finding in findings[:MAX_PAGES]:
        page = finding.get("page") or "prototype"
        kind = finding.get("kind") or "browser diagnostic"
        text = finding.get("text") or ""
        rows.append(f"- {page}: {kind}: {text}")
    return ("Repair every listed prototype file/page in one pass. Fix deterministic syntax "
            "and asset/style findings first, then fix the browser diagnostics. "
            "Use readFiles to inspect multiple affected files in a single turn before patching them. "
            "Keep the approved layout and interactions unchanged. After the repair, reload every "
            "affected page and confirm there are no console, page-error, failed-request or "
            "HTTP 5xx diagnostics. Do not reread or rewrite unaffected pages.\n"
            + "\n".join(rows))
