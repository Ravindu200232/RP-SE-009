# Feature safety flow: open -> snapshot -> observe -> stabilize -> rollback if needed.
# Common preamble for every tool that edits an existing project.
def _open_for_edit(proj_name: str, model: str, think: bool = None):
    """Common preamble for every tool that edits an existing project."""
    t0 = time.time()
    proj_dir = PROD_DIR / proj_name
    if not proj_dir.exists():
        eerr(f"Project not found: {proj_name}")
        return None, None, None
    if not ensure_model(model):
        eerr(f"Cannot load model: {model}")
        return None, None, None
    stack = detect_stack(proj_dir)
    if stack == "next":
        # From: agents/data/database_server.py
        MONGO.ensure_running()
    # From: agents/data/database_helpers.py
    # From: agents/data/database_records.py
    # From: agents/pipeline/build/project_preview.py
    # From: agents/planner/builder/app_builder.py
    arch = ArchitectAgent(ollama, model, proj_dir, _agent_callbacks(proj_dir),
                          stack=stack,
                          mongo_uri=MONGO.uri_for(proj_name) if stack == "next" else "",
                          db_name=db_name_for(proj_name) if stack == "next" else "",
                          dev_port=DEV_PORT, think=think)
    # From: agents/planner/builder/project_memory.py
    arch.load_existing()
    # From: agents/build/tester_common.py
    elog("INFO", f"   ⏱ open {time.time() - t0:.1f}s")
    return proj_dir, arch, arch.stack

# Creates the shared analyzer configuration used by server actions.
def _analyzer_for(arch, proj_dir: Path, *, runtime: bool = True, **options):
    """Create the shared analyzer configuration used by server actions."""
    # From: agents/pipeline/build/project_preview.py
    options.setdefault("callbacks", _analyzer_callbacks())
    if runtime:
        options.setdefault("base_url", f"http://localhost:{DEV_PORT}")
    # From: agents/analysis/analyzer.py
    return AnalyzerAgent(arch, proj_dir, **options)

_FEATURE_TX_EXCLUDED_DIRS = {"node_modules", ".next", ".git"}
_FEATURE_SOAK_SECONDS = 8.0
_FEATURE_STABILIZE_ROUNDS = 3

# Files whose bytes belong to a feature transaction baseline. The generated app can be small or large, so the
# transaction is not capped by file count. Build artefacts and dependencies are excluded; source, tests, assets,
# package metadata and the saved conversation are included. This makes rollback total: a failed feature cannot
# leave a new page, route, component or test behind after the old app is restored.
def _feature_tx_paths(proj_dir: Path) -> set:
    """Files whose bytes belong to a feature transaction baseline.

    The generated app can be small or large, so the transaction is not capped
    by file count. Build artefacts and dependencies are excluded; source,
    tests, assets, package metadata and the saved conversation are included.
    This makes rollback total: a failed feature cannot leave a new page, route,
    component or test behind after the old app is restored.
    """
    root = Path(proj_dir)
    out = set()
    if not root.is_dir():
        return out
    for fp in root.rglob("*"):
        if not fp.is_file():
            continue
        try:
            rel = fp.relative_to(root).as_posix()
        except ValueError:
            continue
        parts = rel.split("/")
        if any(part in _FEATURE_TX_EXCLUDED_DIRS for part in parts):
            continue
        if parts and parts[0] == ".agentforge" and rel != ".agentforge/convo.json":
            continue
        out.add(rel)
    return out

# Captures feature transaction so the next step can work from real evidence.
def _capture_feature_transaction(arch, proj_dir: Path) -> dict:
    """Capture feature transaction so the next step can work from real evidence."""
    paths = _feature_tx_paths(proj_dir)
    snap = FileSnapshot(proj_dir)
    snap.capture(paths)
    return {
        "snapshot": snap,
        "paths": paths,
        "files": dict(getattr(arch, "files", {}) or {}),
        "plan_md": getattr(arch, "plan_md", ""),
        "convo": copy.deepcopy(getattr(arch, "convo", []) or []),
    }

# Restore the app to exactly the state before the feature started.
def _restore_feature_transaction(arch, proj_dir: Path, tx: dict) -> list:
    """Restore the app to exactly the state before the feature started."""
    snap = tx.get("snapshot")
    restored = snap.restore() if snap is not None else []
    before_paths = set(tx.get("paths") or ())
    for rel in sorted(_feature_tx_paths(proj_dir) - before_paths, reverse=True):
        fp = Path(proj_dir) / rel
        try:
            if fp.is_file():
                fp.unlink()
                restored.append(rel)
        except OSError as e:
            log.warning(f"feature rollback: cannot remove {rel}: {e}")
    arch.files = dict(tx.get("files") or {})
    arch.plan_md = tx.get("plan_md", "")
    arch.convo = copy.deepcopy(tx.get("convo") or [])
    return sorted(set(restored))

# Builds a stable key for comparing one feature-runtime finding across checks.
def _feature_finding_key(f) -> tuple:
    """Build a stable key for comparing one feature-runtime finding across checks."""
    text = str(getattr(f, "message", "") or "").lower()
    text = re.sub(r"\b[0-9a-f]{24}\b", "<id>", text)
    text = re.sub(r"\b\d+\b", "#", text)
    text = re.sub(r"\s+", " ", text).strip()[:260]
    return (str(getattr(f, "code", "") or ""),
            str(getattr(f, "path", "") or "").replace("\\", "/"), text)

# Returns finding keys that were already present before the feature change.
def _feature_baseline_keys(report) -> set:
    """Return finding keys that were already present before the feature change."""
    return {_feature_finding_key(f) for f in _serious_findings(report)}

# Returns source paths changed by the current feature transaction.
def _feature_changed_paths(before_files: dict, arch) -> set:
    """Return source paths changed by the current feature transaction."""
    now = dict(getattr(arch, "files", {}) or {})
    keys = set(before_files) | set(now)
    return {p for p in keys if before_files.get(p) != now.get(p)}

# Serious findings introduced by this feature, not pre-existing debt.
def _feature_related_findings(report, baseline_keys: set, changed_paths: set) -> list:
    """Serious findings introduced by this feature, not pre-existing debt."""
    out = []
    shared_changed = (
        any(p in changed_paths for p in ("middleware.js", "middleware.ts",
                                        "app/layout.js", "app/layout.jsx",
                                        "app/layout.ts", "app/layout.tsx"))
        or any(p.startswith("app/layout") for p in changed_paths)
    )
    for f in _serious_findings(report):
        key = _feature_finding_key(f)
        if key in baseline_keys:
            continue
        code = str(getattr(f, "code", "") or "")
        path = str(getattr(f, "path", "") or "").replace("\\", "/")
        msg = str(getattr(f, "message", "") or "")
        if code in {"RUNTIME_EXCEPTION", "ROUTE_ERROR", "BAD_CREDENTIALS"}:
            mentions_changed = any(p and p in msg for p in changed_paths)
            if path not in changed_paths and not mentions_changed and not shared_changed:
                continue
        out.append(f)
    return out

# Choose the short runtime observation window used after a feature change.
def _feature_soak_seconds() -> float:
    """Choose the short runtime observation window used after a feature change."""
    raw = os.environ.get("AGENTFORGE_FEATURE_SOAK_SECONDS", "").strip()
    try:
        return max(1.0, min(float(raw), 30.0)) if raw else _FEATURE_SOAK_SECONDS
    except ValueError:
        return _FEATURE_SOAK_SECONDS

# Open only the feature-owned routes and watch their Next/browser output.
def _observe_feature_upgrade(arch, proj_dir: Path, analyzer, *, db_ok: bool,
                             changed_paths=None, declared_routes=None, route_hint=""):
    """Open only the feature-owned routes and watch their Next/browser output."""
    if not _dev_alive():
        start_next(proj_dir)
        wait_for_next()

    try:
        # From: agents/analysis/checks/scan_state.py
        report = analyzer.scan()
    except Exception as e:
        # From: agents/build/tester_common.py
        elog("WARN", f"   ⚠ post-feature static scan failed: {e}")
        # From: agents/analysis/analysis_shared.py
        report = AnalyzerReport()

    # From: agents/pipeline/bugs/bug_request.py
    pages, apis = _feature_focus_scope(
        arch, changed_paths or [], declared_routes=declared_routes, route_hint=route_hint)
    page_msg = ", ".join(pages) if pages else "none"
    api_msg = ", ".join(apis) if apis else "none"
    # From: agents/build/tester_common.py
    elog("INFO", f"   🎯 Feature check scope — pages: {page_msg}; APIs: {api_msg}")

    mark = dev_log_mark()
    for route in pages:
        # From: agents/pipeline/bugs/bug_request.py
        seen = _reproduce_complaint(proj_dir, route, "", analyzer)
        src = _runtime_route_source(route, arch, analyzer)
        for err in list(getattr(seen, "page_errors", []) or []) + list(getattr(seen, "console", []) or []):
            if any(sig in str(err) for sig in _TERMINAL_SIGNALS):
                # From: agents/analysis/analysis_shared.py
                report.findings.append(Finding(
                    "blocker", "RUNTIME_EXCEPTION",
                    f"post-feature browser exception on {route}: {str(err)[:500]}",
                    path=src, fix=f"repair {src or route} and re-open {route}"))
        for net in list(getattr(seen, "network", []) or []):
            m = re.match(r"HTTP\s+(\d{3})\s+(\w+)\s+(\S+)", str(net))
            if not m:
                continue
            status = int(m.group(1))
            url = m.group(3)
            if status == 404 or status >= 500:
                # From: agents/analysis/analysis_shared.py
                report.findings.append(Finding(
                    "blocker", "ROUTE_ERROR",
                    f"post-feature request failed on {route}: HTTP {status} {m.group(2)} {url}",
                    path=src, fix=f"repair the feature flow serving {route} and re-probe the failed request"))

    route_meta = getattr(report, "routes", None) or {}
    for api in apis:
        meta = route_meta.get(api) or {}
        methods = set(meta.get("methods") or [])
        if methods and "GET" not in methods:
            continue
        try:
            # From: agents/analysis/runtime/runtime_probe.py
            status = analyzer._get_status(analyzer.base_url + api)
        except Exception:
            status = None
        if status is None or status == 404 or status >= 500:
            # From: agents/analysis/analysis_shared.py
            report.findings.append(Finding(
                "blocker", "ROUTE_ERROR", f"feature API {api} returns HTTP {status}",
                path=meta.get("file", ""), fix=f"repair {api} and re-probe only this API"))

    seconds = _feature_soak_seconds()
    # From: agents/build/tester_common.py
    elog("INFO", f"   👀 Watching these feature routes for {seconds:.0f}s")
    deadline = time.time() + seconds
    while time.time() < deadline:
        time.sleep(min(0.5, max(0.05, deadline - time.time())))
    # From: agents/pipeline/build/runtime_faults.py
    trace = _filter_db_noise(dev_log_since(mark, limit=220), db_ok)
    report.findings.extend(_runtime_fault_findings(trace, arch, analyzer))
    return report, trace

# Observe → repair → rebuild → observe until the feature is quiet. A feature may be large; the loop is bounded by
# convergence, not by file count. If the same obstruction survives a repair or no evidence-backed write is
# possible, the caller rolls the whole feature back instead of shipping a degraded application.
def _stabilize_feature_upgrade(arch, proj_dir: Path, analyzer, *,
                               baseline_keys: set, before_files: dict,
                               db_ok: bool, declared_routes=None, route_hint="") -> tuple:
    """Observe → repair → rebuild → observe until the feature is quiet.

    A feature may be large; the loop is bounded by convergence, not by file
    count. If the same obstruction survives a repair or no evidence-backed
    write is possible, the caller rolls the whole feature back instead of
    shipping a degraded application.
    """
    last_sig = None
    total_written = 0
    # From: agents/analysis/analysis_shared.py
    last_report = AnalyzerReport()
    for rnd in range(1, _FEATURE_STABILIZE_ROUNDS + 1):
        # From: agents/build/tester_common.py
        elog("INFO", f"   🩺 Post-feature stabilization {rnd}/{_FEATURE_STABILIZE_ROUNDS}")
        changed = _feature_changed_paths(before_files, arch)
        # From: agents/pipeline/bugs/bug_request.py
        focus_pages, _focus_apis = _feature_focus_scope(
            arch, changed, declared_routes=declared_routes, route_hint=route_hint)
        related_paths = set(changed)
        for route in focus_pages:
            src = _runtime_route_source(route, arch, analyzer)
            if src:
                related_paths.add(src)
        report, _trace = _observe_feature_upgrade(
            arch, proj_dir, analyzer, db_ok=db_ok, changed_paths=changed,
            declared_routes=declared_routes, route_hint=route_hint)
        last_report = report
        serious = _feature_related_findings(report, baseline_keys, related_paths)
        if not serious:
            # From: agents/build/tester_common.py
            elog("INFO", "   ✅ Feature stayed clean during the live Next.js watch")
            return True, total_written, report

        sig = tuple(sorted(_feature_finding_key(f) for f in serious))
        # From: agents/build/tester_common.py
        elog("WARN", f"   ⚠ {len(serious)} new feature regression(s) appeared live")
        for f in serious[:5]:
            # From: agents/build/tester_common.py
            elog("WARN", f"      [{getattr(f,'code','')}] {getattr(f,'message','')[:140]}")
        if sig == last_sig:
            # From: agents/build/tester_common.py
            elog("WARN", "   ↔ the same feature regression survived the last repair")
            break
        last_sig = sig

        # From: agents/analysis/analysis_shared.py
        fix = AnalyzerReport()
        fix.findings = serious
        fix.missing = list(getattr(report, "missing", None) or [])
        written = repair_findings(arch, proj_dir, analyzer, fix, db_ok,
                                  restart_dev=True)
        total_written += written
        if not written:
            # From: agents/build/tester_common.py
            elog("WARN", "   ↔ no evidence-backed repair was possible")
            break
    return False, total_written, last_report
