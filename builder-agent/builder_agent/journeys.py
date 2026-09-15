"""Declarative browser journeys, executed by the engine.

A journey is a list of steps the model writes and this module runs. It is not a
test file: nothing is generated into the project, nothing has to be installed,
and the result is an exit status the evidence ledger records directly.

Every journey ends with an implicit diagnostics check. A page that renders the
right text while throwing in the console, failing a fetch or answering 500 has
not passed, and that is the failure a screenshot would have missed.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin

from .errors import ToolError

MAX_STEPS = 80
STEP_TIMEOUT = 15.0
MAX_SUITES = 12
ACTION_READY_TIMEOUT = 2.0
NAVIGATION_TIMEOUT = 8.0


def _clip(value, limit: int = 400) -> str:
    return str(value if value is not None else "")[:limit]


def _assert(page, step: dict) -> tuple[bool, str]:
    kind = str(step.get("type") or step.get("assert") or "").strip()
    expected = step.get("expected")
    if kind in ("textIncludes", "urlIncludes") and not str(expected or "").strip():
        raise ToolError(f'{kind} needs a non-empty "expected" string. An empty value matches '
                        "every page, so the assertion could never fail.")

    if kind == "textIncludes":
        body = page.text()
        hit = str(expected).lower() in body.lower()
        return hit, (f"page text contains {expected!r}" if hit else
                     f"page text does not contain {expected!r}. Visible text starts: "
                     f"{_clip(body, 300)!r}")
    if kind == "urlIncludes":
        url = page.url
        hit = str(expected).lower() in url.lower()
        return hit, f"URL {url!r} {'contains' if hit else 'does not contain'} {expected!r}"
    if kind == "visible":
        try:
            page.locate(step.get("role"), step.get("name"), step.get("selector"),
                        step.get("index"))
            return True, f"{step.get('name') or step.get('role') or step.get('selector')} is present"
        except ToolError as error:
            return False, str(error)
    if kind == "count":
        selector = step.get("selector")
        if not selector:
            raise ToolError("count needs a CSS selector.")
        found = int(page.evaluate(f"document.querySelectorAll({selector!r}).length") or 0)
        want = int(expected or 0)
        return found == want, f"{selector} matched {found} element(s), expected {want}"
    if kind == "httpStatus":
        url = str(step.get("url") or "").strip()
        status = int(expected or 0)
        if not url or not 400 <= status < 500:
            raise ToolError('httpStatus needs an exact URL and an expected 4xx status for an error-path assertion.')
        url = urljoin(page.url, url)
        observed = [d for d in page.diagnostics
                    if d.get("source") == "network" and d.get("status") == status and d.get("url") == url]
        if not observed:
            return False, f"No observed HTTP {status} response from {url}"
        confirmed = getattr(page, "asserted_http_responses", [])
        for response in observed:
            if response not in confirmed:
                confirmed.append(response)
        page.asserted_http_responses = confirmed
        return True, f"observed expected HTTP {status} from {url}"
    if kind == "noDiagnostics":
        # "request cancelled" is deliberately absent: see CANCELLED_ERRORS.
        critical = [d for d in page.diagnostics
                    if (d["kind"] in ("page error", "console error", "request failed")
                        or d["kind"].startswith("HTTP 5"))
                    and not _asserted_http_diagnostic(page, d)
                    and not _is_ignorable_diagnostic(d)]
        if not critical:
            return True, "no critical browser diagnostics"
        detail = "; ".join(f"{d['kind']}: {_clip(d['text'], 160)}" for d in critical[:5])
        return False, f"{len(critical)} critical browser diagnostic(s): {detail}"
    raise ToolError(f"Unsupported assertion type: {kind!r}. Use textIncludes, urlIncludes, "
                    "visible, count, httpStatus or noDiagnostics.")


def _is_ignorable_diagnostic(diagnostic):
    text = diagnostic.get("text", "")
    url = diagnostic.get("url", "")
    # Ignore benign external asset or ORB/connectivity diagnostics in headless browser
    if any(ign in text for ign in ("ERR_BLOCKED_BY_ORB", "ERR_NAME_NOT_RESOLVED", "ERR_INTERNET_DISCONNECTED")):
        return True
    if "favicon.ico" in url or "favicon.ico" in text:
        return True
    return False


def _asserted_http_diagnostic(page, diagnostic):
    """Only a browser network message for an already asserted 4xx is expected."""
    if _is_ignorable_diagnostic(diagnostic):
        return True
    if diagnostic.get("source") != "network" or diagnostic.get("kind") != "console error":
        return False
    match = re.search(r"Failed to load resource:.*?status of (4\d\d)\b", diagnostic.get("text", ""))
    if not match:
        return False
    for response in getattr(page, "asserted_http_responses", []):
        if response.get("status") != int(match.group(1)) or response.get("url") != diagnostic.get("url"):
            continue
        if diagnostic.get("requestId") and response.get("requestId") != diagnostic["requestId"]:
            continue
        return True
    return False


def _retry_assert(page, step: dict) -> tuple[bool, str]:
    """Poll an assertion until its timeout.

    Client-side rendering means the state a step asserts often arrives a beat
    after the action that caused it. Polling is the difference between a real
    failure and a race.
    """
    budget = max(0.1, min(STEP_TIMEOUT, float(step.get("timeoutMs", 5000)) / 1000))
    deadline = time.time() + budget
    passed, detail = _assert(page, step)
    while not passed and time.time() < deadline:
        time.sleep(0.25)
        passed, detail = _assert(page, step)
    return passed, detail


def diagnostics_report(page) -> str:
    if not page.diagnostics:
        return "No browser diagnostics were recorded."
    rows = [f"- {d['kind']}: {_clip(d['text'], 200)}"
            + (f" [{d['url']}]" if d["url"] else "") for d in page.diagnostics[:12]]
    return "Browser diagnostics during this journey:\n" + "\n".join(rows)


def run_journey(browser, sandbox, evidence, *, suite: str, covers, steps,
                start_url: str | None = None, fresh_session: bool = True,
                tab_id: str | None = None, events=None) -> dict:
    """Execute one journey and record it as end-to-end evidence."""
    if not isinstance(steps, list) or not steps or len(steps) > MAX_STEPS:
        raise ToolError(f"Provide 1-{MAX_STEPS} journey steps.")

    covered = evidence.validate_covers("e2e", covers or [])
    fingerprint = hashlib.sha256(json.dumps(
        {"steps": steps, "startUrl": start_url, "freshSession": fresh_session, "covers": sorted(covered)},
        sort_keys=True, default=str).encode()).hexdigest()
    previous = next((r for r in evidence.suites if r["kind"] == "e2e" and r["suite"] == suite), {})
    if (previous.get("status") == "passed" and previous.get("revision") == evidence.revision
            and previous.get("journeyFingerprint") == fingerprint):
        return {"ok": True, "content": f"{suite}: passed (reused at unchanged revision)."}
    page = browser.page(tab_id)
    if fresh_session:
        browser.fresh_session()
    page.reset_diagnostics()

    if start_url:
        try:
            page.navigate(start_url, timeout=NAVIGATION_TIMEOUT)
        except ToolError as error:
            evidence.record_external(kind="e2e", suite=suite, source="direct-CDP journey",
                                     covers=covered, status="failed", reason=str(error), output=str(error))
            raise

    if events:
        events.emit("e2e", state="journey_start", suite=suite, title=suite,
                    steps=len(steps), total=len(steps), url=start_url or page.url)

    trace, failed = [], None
    for index, step in enumerate(steps, 1):
        step = step if isinstance(step, dict) else {}
        action = str(step.get("action") or step.get("type") or "").strip()
        label = f"{index}. {action or 'assert'}"
        if events:
            events.emit("e2e", state="step", suite=suite, index=index, total=len(steps),
                        verb=_verb(action, step), label=_label(step),
                        value=str(step.get("url") or step.get("text") or
                                  step.get("expected") or ""))
        try:
            if action == "navigate":
                page.navigate(str(step["url"]), timeout=NAVIGATION_TIMEOUT)
                trace.append(f"{label} -> {page.url}")
            elif action == "click":
                page.click(page.locate(step.get("role"), step.get("name"),
                                       step.get("selector"), step.get("index")))
                page.wait_ready(ACTION_READY_TIMEOUT)
                trace.append(f"{label} {step.get('name') or step.get('selector')}")
            elif action in ("type", "fill"):
                page.fill(page.locate(step.get("role", "textbox"), step.get("name"),
                                      step.get("selector"), step.get("index")),
                          str(step.get("text", "")))
                trace.append(f"{label} {step.get('name') or step.get('selector')}")
            elif action == "press":
                page.press(str(step.get("key", "Enter")))
                page.wait_ready(ACTION_READY_TIMEOUT)
                trace.append(f"{label} {step.get('key')}")
            elif action == "wait":
                time.sleep(min(10.0, float(step.get("ms", 500)) / 1000))
                trace.append(label)
            elif action == "screenshot":
                view = str(step.get("view") or f"step-{index}")
                width = int(step.get("width") or 1280)
                target = Path(sandbox.state_dir("screenshots")) / f"{re.sub(r'[^a-z0-9]+', '-', view.lower())}-{width}.png"
                page.screenshot(target, width=width, height=int(step.get("height") or 800))
                record = evidence.capture_visual({
                    "view": view, "width": width, "height": int(step.get("height") or 800),
                    "filePath": sandbox.relative(target), "covers": step.get("covers") if "covers" in step else
                    [r["id"] for r in (evidence.scope or {}).get("requirements", [])
                     if r["id"] in covered and "visual" in r.get("evidence", [])]})
                trace.append(f"{label} {record['filePath']}")
            else:
                passed, detail = _retry_assert(page, step)
                trace.append(f"{label} {step.get('type')}: {detail}")
                if not passed:
                    failed = f"Step {index} failed: {detail}"
                    break
        except ToolError as error:
            failed = f"Step {index} failed: {error}"
            trace.append(f"{label} -> {error}")
            break

    if not failed:
        passed, detail = _assert(page, {"type": "noDiagnostics"})
        trace.append(f"{len(steps) + 1}. assert noDiagnostics: {detail}")
        if not passed:
            failed = f"The journey completed but the page reported problems: {detail}"

    if events:
        events.emit("e2e", state="journey_done", suite=suite, title=suite,
                    status="failed" if failed else "passed", url=page.url,
                    message=failed or "")

    body = "\n".join(trace)
    if failed:
        # Preserve the diagnostics with the durable E2E record, rather than
        # only in the tool error sent to the agent. This lets Testing retain
        # console, network and page-error evidence after a reload.
        diagnostics = diagnostics_report(page)
        evidence.record_external(kind="e2e", suite=suite, source="direct-CDP journey",
                                 covers=covered, status="failed",
                                 output=f"{body}\n\n{diagnostics}", reason=failed)
        raise ToolError(
            f"{failed}\n\nURL: {page.url}\n{body}\n\n{diagnostics}\n"
            f"Page text: {_clip(page.text(), 800)}\n\n"
            "Recorded as a failed E2E suite. Repair the owner named in the failure, "
            "then rerun only this suite. Do not take another snapshot of an unchanged page.")

    record = evidence.record_external(kind="e2e", suite=suite, source="direct-CDP journey",
                                      covers=covered, status="passed", output=body)
    record["journeyFingerprint"] = fingerprint
    return {"ok": True,
            "content": (f"E2E journey passed.\nSuite: {suite}\n"
                        f"Covered: {', '.join(covered) or 'no scoped ids'}\n{body}")}


def run_journeys(browser, sandbox, evidence, *, suites, events=None) -> dict:
    """Run several independent journeys in one deterministic browser pass.

    The journeys remain isolated (each suite controls ``freshSession``), but
    the model pays for one tool turn instead of a turn between every suite.
    A failure is recorded and the batch continues so one broken flow cannot
    hide failures in the other critical flows.
    """
    if not isinstance(suites, list) or not suites or len(suites) > MAX_SUITES:
        raise ToolError(f"Provide 1-{MAX_SUITES} journey suites.")

    results = []
    for index, spec in enumerate(suites, 1):
        if not isinstance(spec, dict):
            results.append({"suite": f"suite-{index}", "status": "failed",
                            "detail": "Each suite must be an object."})
            continue
        suite = str(spec.get("suite") or f"suite-{index}")
        try:
            result = run_journey(
                browser, sandbox, evidence,
                suite=suite,
                covers=spec.get("covers") or [],
                steps=spec.get("steps"),
                start_url=spec.get("startUrl"),
                fresh_session=bool(spec.get("freshSession", True)),
                tab_id=spec.get("tabId"),
                events=events,
            )
            results.append({"suite": suite, "status": "passed",
                            "detail": result.get("content", "")})
        except ToolError as error:
            # run_journey already persisted the detailed failure evidence.
            # Keep the batch alive and return a compact combined report to the
            # model so it can repair all owners in one pass.
            results.append({"suite": suite, "status": "failed",
                            "detail": str(error)[:1200]})

    failed = [row for row in results if row["status"] == "failed"]
    summary = [f"E2E batch completed: {len(results) - len(failed)} passed, "
               f"{len(failed)} failed."]
    for row in results:
        summary.append(f"- {row['suite']}: {row['status']}")
        if row["status"] == "failed":
            summary.append(f"  {row['detail']}")
    return {"ok": not failed, "content": "\n".join(summary)}


_VERBS = {"navigate": "GOTO", "click": "CLICK", "type": "FILL", "fill": "FILL",
          "press": "PRESS", "wait": "WAIT", "screenshot": "SHOT"}


def _verb(action: str, step: dict) -> str:
    """What this step is doing, in the vocabulary the studio already renders."""
    if action in _VERBS:
        return _VERBS[action]
    return "CHECK"


def _label(step: dict) -> str:
    return str(step.get("name") or step.get("selector") or step.get("url")
               or step.get("expected") or step.get("type") or "")[:80]


def journey_fingerprint(suite: str, failure: str) -> str:
    return hashlib.sha256(f"{suite}\0{failure}".encode()).hexdigest()[:16]
