"""Deterministic high-confidence E2E diagnosis rules.

These rules handle facts that should not consume an LLM round: HTTP request/body
format mismatches, explicit auth failures and exact API route ownership.  The
agentic debugger remains responsible for ambiguous product/UI reasoning.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse


def _route_source(route: str, files: dict[str, str]) -> str:
    route = str(route or "").split("?", 1)[0].rstrip("/") or "/"
    if not route.startswith("/api/"):
        return ""
    segs = [s for s in route[len("/api/"):].split("/") if s]
    exact = "app/api/" + "/".join(segs) + "/route.js"
    if exact in files:
        return exact
    candidates = []
    for rel in files:
        if not rel.startswith("app/api/") or not rel.endswith("/route.js"):
            continue
        middle = rel[len("app/api/"):-len("/route.js")]
        parts = middle.split("/") if middle else []
        if len(parts) != len(segs):
            continue
        if all(a == b or (a.startswith("[") and a.endswith("]"))
               for a, b in zip(parts, segs)):
            candidates.append(rel)
    return sorted(candidates)[0] if candidates else ""


def _failed_api_rows(packet: str) -> list[dict]:
    rows = []
    for line in str(packet or "").splitlines():
        if "/api/" not in line:
            continue
        m = re.search(r"HTTP\s+([45]\d\d)\s+(GET|POST|PUT|PATCH|DELETE)\s+(https?://\S+)", line, re.I)
        if not m:
            continue
        url = m.group(3).rstrip(".,;)")
        try:
            route = urlparse(url).path
        except Exception:
            route = re.sub(r"^https?://[^/]+", "", url).split("?", 1)[0]
        ct = ""
        cm = re.search(r"content-type=([^|—]+)", line, re.I)
        if cm:
            ct = cm.group(1).strip().lower()
        body = ""
        bm = re.search(r"request-body=(.*?)(?:\s+[—|]\s+response=|\s+—\s+response=|$)", line, re.I)
        if bm:
            body = bm.group(1).strip()
        response = ""
        rm = re.search(r"response=(.*)$", line, re.I)
        if rm:
            response = rm.group(1).strip()
        rows.append({
            "status": int(m.group(1)), "method": m.group(2).upper(),
            "route": route, "content_type": ct, "body": body,
            "response": response, "line": line,
        })
    return rows


def _target_references_api(arch, failures, route: str) -> bool:
    """Whether the failing page/component actually talks to this API family."""
    files = getattr(arch, "files", None) or {}
    route = str(route or "").split("?", 1)[0]
    parts = [p for p in route.split("/") if p]
    needles = [route]
    if len(parts) >= 2:
        needles.append("/" + "/".join(parts[:2]))

    candidates = []
    for failure in failures or []:
        rel = str(getattr(failure, "target", "") or "").strip()
        if rel in files and rel not in candidates:
            candidates.append(rel)
    for rel in list(candidates):
        body = str(files.get(rel) or "")
        for kind, name in re.findall(
                r"from\s+['\"]@/(components|lib)/([\w./-]+)['\"]", body):
            base = f"{kind}/{name}"
            for ext in (".jsx", ".js", ".tsx", ".ts", ""):
                child = base + ext
                if child in files and child not in candidates:
                    candidates.append(child)
                    break
    hay = "\n".join(str(files.get(rel) or "") for rel in candidates[:8])
    return any(n and n in hay for n in needles)


_BUSINESS_PRECONDITION_RE = re.compile(
    r"\b(?:already\s+(?:exists|used|submitted|reviewed|completed|cancelled|claimed)|"
    r"only\s+(?:be\s+)?(?:allowed|available|submitted|created|updated|deleted|cancelled|"
    r"reviewed|left|performed)?\s*(?:after|before|when|if)|"
    r"cannot\s+[^.;]{0,100}\s+(?:until|while|after|before|because)|"
    r"not\s+(?:eligible|available|allowed|complete|completed|active)|"
    r"requires?\s+[^.;]{0,80}\s+(?:state|status)|"
    r"must\s+be\s+(?:active|inactive|complete|completed|checked|checked[_ -]?out|"
    r"confirmed|approved|eligible)|overlap(?:ping)?|conflict)\b", re.I)


def _business_precondition(response: str) -> bool:
    """Whether a 4xx describes valid domain state, not a broken payload."""
    return bool(_BUSINESS_PRECONDITION_RE.search(str(response or "")))


def diagnose_api_http_error(agent, arch, failures, packet: str) -> dict | None:
    """Promote a relevant API 4xx/5xx above a downstream UI symptom.

    A missing button or text often appears *after* the page's data request was
    rejected. Fixing the selector in that situation only teaches the test to
    ignore the real defect. Prefer errors emitted by the exact failing step;
    otherwise require source ownership before using older journey traffic.
    """
    try:
        ev = dict(getattr(agent, "_last_run_evidence", {}) or {})
    except Exception:
        ev = {}
    step_blob = "\n".join(str(x) for x in (ev.get("step_network_errors") or []))
    step_rows = _failed_api_rows(step_blob)
    rows = step_rows or _failed_api_rows(packet)
    if not rows:
        return None
    files = getattr(arch, "files", None) or {}

    for row in reversed(rows):
        status = int(row.get("status") or 0)
        route = str(row.get("route") or "")
        if not route.startswith("/api/"):
            continue
        auth_route = route.startswith("/api/auth/")
        relevant = bool(step_rows) or auth_route or status >= 500 or \
            _target_references_api(arch, failures, route)
        if not relevant:
            continue

        target = str(getattr((failures or [None])[0], "target", "") or "")
        api_source = _route_source(route, files)
        repair_files = []
        if api_source:
            repair_files.append(api_source)
        if target in files and target not in repair_files:
            repair_files.append(target)
        response = str(row.get("response") or "").strip()
        suffix = f" Response: {response[:220]}" if response else ""

        if status in (401, 403):
            return {
                "verdict": "AUTH_FIX",
                "root": f"{route} returned HTTP {status} during the required browser journey; the protected request lost/failed authorization.{suffix}",
                "files": repair_files[:4], "test_step": "", "test_patch": "",
                "hypothesis": "the authenticated browser and protected API disagree on session/role state",
                "next": "inspect the session/role check and the calling page together, repair the auth boundary, then resume the same journey",
                "confidence": "high", "privileged": [],
                "evidence_rule": "relevant-api-auth-error",
            }

        if status == 404:
            if api_source and re.search(r"not\s+found|missing|does not exist", response, re.I):
                return {
                    "verdict": "DATA_PREREQUISITE",
                    "root": f"{route} exists but returned HTTP 404 for the record/state this journey expected.{suffix}",
                    "files": repair_files[:4], "test_step": "", "test_patch": "",
                    "hypothesis": "the journey reached a real handler but its required record was not established",
                    "next": "establish the prerequisite through the real workflow, then rerun without inventing markup or test data",
                    "confidence": "high", "privileged": [],
                    "evidence_rule": "relevant-api-record-404",
                }
            return {
                "verdict": "ROUTE_FIX",
                "root": f"{route} returned HTTP 404 while the failing page depends on it; the client/API route contract is broken.{suffix}",
                "files": repair_files[:4], "test_step": "", "test_patch": "",
                "hypothesis": "the UI calls an endpoint that is missing or mapped to the wrong route",
                "next": "align the caller with the real API route (or implement the required route) and rerun the browser checkpoint",
                "confidence": "high", "privileged": [],
                "evidence_rule": "relevant-api-404",
            }

        if status in (400, 409, 422) and _business_precondition(response):
            return {
                "verdict": "DATA_PREREQUISITE",
                "root": (f"{route} correctly rejected the journey's current record/state "
                         f"with HTTP {status}.{suffix}"),
                "files": repair_files[:4], "test_step": "", "test_patch": "",
                "hypothesis": ("the scenario selected or created data that does not satisfy "
                               "the business action's documented precondition"),
                "next": ("use the real workflow to create/select a record whose state satisfies "
                         "the response, then retry the action without weakening the API rule"),
                "confidence": "high", "privileged": [],
                "evidence_rule": "relevant-api-business-precondition",
            }

        if status >= 500 or status in (400, 409, 422):
            return {
                "verdict": "APP_FIX",
                "root": f"{route} returned HTTP {status} during the required journey; repair the client/API data contract before changing downstream UI selectors.{suffix}",
                "files": repair_files[:4], "test_step": "", "test_patch": "",
                "hypothesis": "the page and API disagree on request/query/data state, so the UI never receives the business data it needs",
                "next": "inspect the captured request/response and handler contract, repair the smallest client/API owner set, then resume the journey",
                "confidence": "high", "privileged": [],
                "evidence_rule": "relevant-api-http-error",
            }
    return None


def diagnose_post_mutation_proof(agent, arch, failures, scenario) -> dict | None:
    """Classify a failed proof after a business action as production behavior.

    Checkpoint resumes used to reset the runner's business-state flag. A price
    update could succeed, then a missing guessed price assertion was treated
    as a pre-action test typo and consumed several TEST_FIX rounds. The runner
    now restores that state; this rule turns the resulting BEHAVIOR failure
    into an immediate evidence-scoped application diagnosis.
    """
    if not failures or scenario is None:
        return None
    if not all(str(getattr(f, "kind", "") or "").upper() == "BEHAVIOR"
               for f in failures):
        return None
    try:
        ev = dict(getattr(agent, "_last_run_evidence", {}) or {})
        idx = int(ev.get("failed_index", -1))
    except Exception:
        return None
    if idx < 0 or idx >= len(getattr(scenario, "steps", []) or []):
        return None
    try:
        prior_business = any(agent._is_business_step(st)
                             for st in scenario.steps[:idx])
    except Exception:
        prior_business = False
    if not prior_business:
        return None
    step = scenario.steps[idx]
    if str(getattr(step, "verb", "") or "") not in {
            "EXPECT_TEXT", "EXPECT_VALUE", "EXPECT_URL", "EXPECT_MUTATION",
            "WAIT_FOR"}:
        return None
    files = getattr(arch, "files", None) or {}
    target = str(getattr(failures[0], "target", "") or "")
    repair_files = [target] if target in files else []
    try:
        before = str(ev.get("route_before") or "")
        producer = agent._page_for(before)
        if producer in files and producer not in repair_files:
            repair_files.append(producer)
    except Exception:
        pass
    return {
        "verdict": "APP_FIX",
        "root": "the journey already completed a business action, but its required downstream state/route proof did not appear",
        "files": repair_files[:4], "test_step": "", "test_patch": "",
        "hypothesis": "the mutation/refresh/navigation path completed incompletely, leaving the expected business state unobservable",
        "next": "inspect the action producer and destination state refresh together, repair production code, then resume this checkpoint",
        "confidence": "high", "privileged": [],
        "evidence_rule": "post-mutation-behavior-proof",
    }


def diagnose_request_contract(agent, arch, failures, packet: str) -> dict | None:
    """Return a deterministic diagnosis when request/handler formats conflict."""
    files = getattr(arch, "files", None) or {}
    for row in reversed(_failed_api_rows(packet)):
        rel = _route_source(row["route"], files)
        if not rel:
            continue
        source = str(files.get(rel) or "")
        ct = row["content_type"]
        body = row["body"]

        json_only = bool(re.search(r"\brequest\s*\.\s*json\s*\(", source))
        form_reader = bool(re.search(r"\brequest\s*\.\s*formData\s*\(", source))
        form_request = "application/x-www-form-urlencoded" in ct or "multipart/form-data" in ct
        json_request = "application/json" in ct

        if json_only and form_request and not form_reader:
            target = str(getattr(failures[0], "target", "") or "") if failures else ""
            repair_files = [rel]
            if target.startswith(("app/", "components/", "lib/")) and target not in repair_files:
                repair_files.append(target)
            return {
                "verdict": "APP_FIX",
                "root": (
                    f"{row['route']} parses request.json(), but the browser submitted "
                    f"{ct or 'form data'}; the client/server request-body contract is incompatible"
                ),
                "files": repair_files[:2],
                "test_step": "", "test_patch": "",
                "hypothesis": "aligning the request encoding and route parser will remove the API failure",
                "next": (
                    "inspect the submitting form/fetch and the route together; use one canonical payload "
                    "shape instead of teaching the test to bypass the real UI"
                ),
                "confidence": "high", "privileged": [],
                "evidence_rule": "request-content-type-vs-request.json",
            }

        if form_reader and json_request and not json_only:
            target = str(getattr(failures[0], "target", "") or "") if failures else ""
            repair_files = [rel]
            if target.startswith(("app/", "components/", "lib/")) and target not in repair_files:
                repair_files.append(target)
            return {
                "verdict": "APP_FIX",
                "root": (
                    f"{row['route']} parses request.formData(), but the browser sent application/json; "
                    "the client/server request-body contract is incompatible"
                ),
                "files": repair_files[:2],
                "test_step": "", "test_patch": "",
                "hypothesis": "using the same payload encoding on both sides will remove the API failure",
                "next": "align the submitting client and route parser around one canonical payload shape",
                "confidence": "high", "privileged": [],
                "evidence_rule": "request-content-type-vs-formData",
            }

        if row["status"] == 400 and body and re.search(
            r"missing|required|invalid|must provide|expected", row["response"], re.I
        ):
            target = str(getattr(failures[0], "target", "") or "") if failures else ""
            repair_files = [rel]
            if target.startswith(("app/", "components/", "lib/")) and target not in repair_files:
                repair_files.append(target)
            return {
                "verdict": "APP_FIX",
                "root": (
                    f"{row['route']} rejected the real browser payload with HTTP 400; "
                    "the submitted field schema does not satisfy the route contract"
                ),
                "files": repair_files[:2],
                "test_step": "", "test_patch": "",
                "hypothesis": "the UI and route disagree on required field names/shape",
                "next": "compare the captured request-body with the route's required fields and make both sides use the same schema",
                "confidence": "high", "privileged": [],
                "evidence_rule": "http400-request-schema",
            }
    return None



def diagnose_page_health(agent, arch, failures, packet: str) -> dict | None:
    """Prioritize a real page 5xx over downstream selector symptoms."""
    files = getattr(arch, "files", None) or {}
    rows = []
    for line in str(packet or "").splitlines():
        m = re.search(r"HTTP\s+(5\d\d)\s+GET\s+(https?://\S+)", line, re.I)
        if not m:
            continue
        url = m.group(2).rstrip(".,;)")
        try:
            route = urlparse(url).path or "/"
        except Exception:
            route = re.sub(r"^https?://[^/]+", "", url).split("?", 1)[0] or "/"
        if route.startswith("/api/"):
            continue
        rows.append((int(m.group(1)), route, line))
    if not rows:
        return None

    status, route, line = rows[-1]
    target = ""
    try:
        target = str(agent._page_for(route) or "").strip()
    except Exception:
        target = ""
    repair_files = []
    if target in files:
        repair_files.append(target)
    for failure in failures or []:
        rel = str(getattr(failure, "target", "") or "").strip()
        if rel in files and rel not in repair_files:
            repair_files.append(rel)
    return {
        "verdict": "APP_FIX",
        "root": f"the journey page {route} returned HTTP {status}; repair the page/runtime path before changing its E2E locator",
        "files": repair_files[:4],
        "test_step": "", "test_patch": "",
        "hypothesis": f"the HTTP {status} page failure at {route} causes the downstream E2E symptom",
        "next": "inspect the page and its direct imports/data calls, repair the runtime failure, then resume this same journey checkpoint",
        "confidence": "high", "privileged": [],
        "evidence_rule": "page-http-5xx",
        "evidence": line[:1200],
    }

def diagnose_navigation_loop(agent, arch, failures, packet: str) -> dict | None:
    """Turn a runaway same-page refresh burst into one scoped APP_FIX."""
    blob = "\n".join([str(packet or "")] +
                     [str(getattr(f, "message", "") or "") for f in (failures or [])])
    m = re.search(r"NAVIGATION_LOOP:\s*([^\s]+)", blob, re.I)
    if not m:
        return None
    route = m.group(1).split("?", 1)[0].rstrip("/") or "/"
    files = getattr(arch, "files", None) or {}
    target = str(getattr((failures or [None])[0], "target", "") or "")
    candidates = []
    if target in files:
        candidates.append(target)

    try:
        page_rel = agent._page_for(route)
    except Exception:
        page_rel = ""
    if page_rel in files and page_rel not in candidates:
        candidates.append(page_rel)
    roots = list(candidates)
    for rel in roots:
        body = str(files.get(rel) or "")
        for kind, name in re.findall(r'from\s+[\'"]@/(components|lib)/([\w./-]+)[\'"]', body):
            base = f"{kind}/{name}"
            for ext in (".jsx", ".js", ""):
                child = base + ext
                if child in files:
                    src = str(files.get(child) or "")
                    if re.search(r"router\.(?:refresh|replace|push)\s*\(|location\.(?:reload|replace)\s*\(|window\.location", src):
                        if child not in candidates:
                            candidates.append(child)
                    break
    if not candidates:
        for rel, body in files.items():
            if rel.startswith(("app/", "components/")) and re.search(
                    r"router\.(?:refresh|replace|push)\s*\(|location\.(?:reload|replace)\s*\(",
                    str(body or "")):
                candidates.append(rel)
                if len(candidates) >= 4:
                    break

    return {
        "verdict": "APP_FIX",
        "root": f"{route} is trapped in a client-side same-page navigation/refresh loop; the browser circuit breaker observed a request burst",
        "files": candidates[:6],
        "test_step": "", "test_patch": "",
        "hypothesis": "a render/effect/state transition repeatedly calls router.refresh/replace/push or reloads the current route",
        "next": "inspect the page and its directly rendered client components; remove the self-triggering refresh/redirect cycle while preserving the intended one-time navigation",
        "confidence": "high", "privileged": [],
        "evidence_rule": "same-page-request-burst",
    }


def diagnose_checkpoint_auth(agent, arch, failures, packet: str) -> dict | None:
    """Treat failed checkpoint identity restoration as auth, not a UI miss."""
    try:
        ev = dict(getattr(agent, "_last_run_evidence", {}) or {})
    except Exception:
        ev = {}
    reason = str(ev.get("resume_auth_error") or "").strip()
    if not reason:
        return None
    files = getattr(arch, "files", None) or {}
    target = str(getattr((failures or [None])[0], "target", "") or "")
    repair = [p for p in (target, "lib/auth.js", "lib/auth-client.js",
                          "app/api/auth/[...all]/route.js") if p in files]
    return {
        "verdict": "AUTH_FIX",
        "root": reason,
        "files": repair[:4], "test_step": "", "test_patch": "",
        "hypothesis": "the focused checkpoint lost the expected demo identity after a production repair",
        "next": "repair the session/role boundary without replaying completed business steps, then resume the same checkpoint",
        "confidence": "high", "privileged": [],
        "evidence_rule": "checkpoint-auth-restore",
    }
