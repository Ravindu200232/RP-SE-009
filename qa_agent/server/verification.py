# Security, API, runtime and performance checks.
def run_security_stage(arch, proj_dir: Path, analyzer) -> tuple:
    """
    Ask whether the app is safe to put in front of people, and fix what is not.

    Every other gate asks whether it WORKS. This one is the only thing between
    a generated app and an open `PATCH /api/orders/[id]` that lets a stranger
    mark anybody's order collected — which compiles, renders, passes its tests
    and answers its route probe.

    Blockers and majors go to `analyzer.repair`, the same call the route-error
    path uses, because a described flaw and a fixed one are not the same
    deliverable. Minors are reported and left.
    """
    from qa_agent.verification.security import SecurityAgent

    ephase({"phase": -22, "title": "Security check", "status": "active"})
    agent = SecurityAgent(proj_dir, callbacks=_analyzer_callbacks(),
                          cmd=getattr(arch, "cmd", None))
    findings, counts = agent.run()

    if counts:
        worst = ", ".join(f"{n} {sev}" for sev, n in counts.items())
        bad = counts.get("critical", 0) + counts.get("high", 0)
        elog("WARN" if bad else "INFO",
             f"   🔐 npm audit: {worst}")
        emit({"type": "test_result",
              "status": "fail" if bad else "warn",
              "msg": "Dependencies", "detail": worst})
    else:
        emit({"type": "test_result", "status": "pass",
              "msg": "Dependencies", "detail": "no known advisories"})

    for dupe in check_seed_duplicates(proj_dir):
        elog("WARN", f"   🌱 {dupe}")
        emit({"type": "test_result", "status": "warn", "msg": "Seed data",
              "detail": dupe[:160]})

    if not findings:
        elog("INFO", "   🔐 No security problems found in the generated code")
        emit({"type": "test_result", "status": "pass", "msg": "Security",
              "detail": "nothing found"})
        ephase({"phase": -22, "title": "Security check", "status": "done"})

        return [], counts

    for f in findings:
        elog("WARN", f"   🔐 [{f.severity}] {f.path}: {f.message[:110]}")
        emit({"type": "test_result", "status": "fail", "msg": f"Security: {f.code}",
              "detail": f"{f.path} — {f.message[:160]}"})

    serious = [f for f in findings if f.severity in ("blocker", "major")]
    written = 0
    if serious:
        elog("INFO", f"   🔧 Repairing {len(serious)} security finding(s)")

        snap = FileSnapshot(proj_dir)
        snap.capture([p for p in arch.files
                      if p.startswith(("app/", "components/", "lib/"))])
        report = AnalyzerReport()
        report.findings = serious
        report.missing = []
        try:
            written = analyzer.repair(report) or 0
        except Exception as e:
            elog("WARN", f"   ⚠ Security repair failed: {e}")
            log.exception("security repair")
        if written:

            _stop_dev_proc()

            arch.repair_missing_imports()
            if not run_build_fix_loop(arch, proj_dir, MONGO.available,
                                      max_rounds=1):

                elog("WARN", "   ↩ the security fix broke the build — "
                             "reverting it, and the finding stands")
                snap.restore()
                written = 0
                run_build_fix_loop(arch, proj_dir, MONGO.available,
                                   max_rounds=1)
            start_next(proj_dir)
            wait_for_next()
            still, _ = agent.run(audit=False)
            gone = len(findings) - len(still)
            elog("INFO" if gone else "WARN",
                 f"   🔐 {gone} of {len(findings)} finding(s) closed")

            findings = still

    ephase({"phase": -22, "title": "Security check", "status": "done",
            "written": written})
    return findings, counts


def repair_findings(arch, proj_dir: Path, analyzer, report, db_ok: bool,
                    *, restart_dev: bool = True, server_log: str = "",
                    validate_build: bool = True) -> int:
    """Fix what the verification pass found, instead of only counting it.

    `analyzer.run_runtime` walks the running app and finds real, specific
    defects — a link to a page nobody wrote (DEAD_LINK: the 404s), a fetch to
    a route handler that does not exist, a form posting nowhere — and it used
    to end by logging one line: `🔍 Verification — 5 major`. Then the pipeline
    moved on to the security scan. Nothing read those findings, so every one
    of them shipped, and "every app has a 404 in it" is exactly what that
    looks like from the outside.

    The security stage a few lines below has always repaired its own findings
    this way; this is the same loop, on the findings the browser produced:
    snapshot, repair, rebuild, and put it all back if the repair broke the
    build — a dead link is better than a project that will not compile.
    """
    serious = [f for f in (getattr(report, "findings", None) or [])
               if getattr(f, "severity", "") in ("blocker", "major")]
    if not serious:
        return 0

    for f in serious[:8]:
        elog("WARN", f"   🔍 [{f.severity}] {getattr(f, 'code', '')}: "
                     f"{f.message[:110]}")
    elog("INFO", f"   🔧 Repairing {len(serious)} verification finding(s)")
    ephase({"phase": -21, "title": "Fixing what the check found",
            "status": "active"})

    snap = FileSnapshot(proj_dir)
    snapshot_paths = [p for p in arch.files
                      if p.startswith(("app/", "components/", "lib/"))]
    for finding in serious:
        for rel in list(getattr(finding, "extra", None) or []):
            rel = str(rel or "").strip().replace("\\", "/").lstrip("./")
            if rel.startswith(("app/", "components/", "lib/")):
                snapshot_paths.append(rel)
    snap.capture(dict.fromkeys(snapshot_paths))
    fix_report = AnalyzerReport()
    fix_report.findings = serious
    fix_report.missing = list(getattr(report, "missing", None) or [])
    written = 0
    try:
        written = analyzer.repair(fix_report, server_log=server_log) or 0
    except Exception as e:
        elog("WARN", f"   ⚠ Verification repair failed: {e}")
        log.exception("verification repair")

    if written:
        arch.repair_missing_imports()
        if validate_build:
            was_serving = _dev_alive(1.0)
            _stop_dev_proc()
            if not run_build_fix_loop(arch, proj_dir, db_ok, max_rounds=1):
                elog("WARN", "   ↩ the fix broke the build — reverting it, and "
                             "the findings stand")
                snap.restore()
                written = 0
                run_build_fix_loop(arch, proj_dir, db_ok, max_rounds=1)
            if restart_dev or was_serving:
                start_next(proj_dir)
                if restart_dev:
                    wait_for_next()
        else:
            changed = [p for p in snap.changed() if p in (getattr(arch, "files", {}) or {})]
            problems, _ = check_syntax(
                proj_dir, {p: arch.files.get(p, "") for p in changed})
            if problems:
                elog("WARN", "   ↩ the candidate repair does not parse — reverting it")
                snap.restore()
                written = 0

    ephase({"phase": -21, "title": "Fixing what the check found",
            "status": "done", "written": written})
    return written


def _serious_findings(report) -> list:
    """Blockers/majors, de-duplicated without throwing away their evidence."""
    out, seen = [], set()
    for f in (getattr(report, "findings", None) or []):
        if getattr(f, "severity", "") not in ("blocker", "major"):
            continue
        key = (getattr(f, "code", ""), getattr(f, "path", ""),
               getattr(f, "message", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def _merge_analyzer_reports(*reports):
    """One report for the final gate; preserve the strongest evidence only once."""
    merged = AnalyzerReport()
    seen = set()
    for report in reports:
        if report is None:
            continue
        if not getattr(merged, "planned", None):
            merged.planned = list(getattr(report, "planned", None) or [])
        if not getattr(merged, "routes", None):
            merged.routes = dict(getattr(report, "routes", None) or {})
        merged.missing = list(dict.fromkeys(
            list(getattr(merged, "missing", None) or [])
            + list(getattr(report, "missing", None) or [])))
        for f in (getattr(report, "findings", None) or []):
            key = (getattr(f, "severity", ""), getattr(f, "code", ""),
                   getattr(f, "path", ""), getattr(f, "message", ""))
            if key in seen:
                continue
            seen.add(key)
            merged.findings.append(f)
    return merged


def _write_final_flow_receipt(proj_dir: Path, report, *, clean: bool,
                              conclusive: bool, db_ok: bool, build_ok: bool):
    """Persist what 'Done' meant so a green badge is auditable after restart."""
    serious = _serious_findings(report)
    payload = {
        "clean": bool(clean),
        "conclusive": bool(conclusive),
        "build_ok": bool(build_ok),
        "database_ok": bool(db_ok),
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "serious": [{
            "severity": getattr(f, "severity", ""),
            "code": getattr(f, "code", ""),
            "path": getattr(f, "path", ""),
            "message": getattr(f, "message", ""),
        } for f in serious[:30]],
    }
    try:
        d = proj_dir / ".agentforge"
        d.mkdir(parents=True, exist_ok=True)
        (d / "final-flow.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        log.debug(f"final-flow receipt: {e}")
    emit({"type": "quality_gate", **payload})


def pretest_flow_convergence(arch, proj_dir: Path, analyzer, *, build_ok: bool):
    """Close plan/capability gaps ONCE after build, before any tests run.

    V16 waited until every browser/security stage had finished, then ran the
    semantic UNBUILT_PROMISE audit and rewrote ten files at the very end.  That
    invalidated the tests that had just run and forced more builds/probes.  The
    architecture proof belongs here: generated -> build green -> close planned
    flows -> unit/runtime/API/E2E/security/performance.
    """
    ephase({"phase": -24, "title": "Closing planned flows", "status": "active"})
    eprog("Closing planned capabilities before testing…", 87)

    def collect(semantic=True):
        reports = []
        try:
            reports.append(analyzer.scan())
        except Exception as e:
            elog("WARN", f"   ⚠ pre-test static flow scan failed: {e}")
        if build_ok and semantic:
            try:
                promises = analyzer.unbuilt_promises(max_reads=8)
                if promises:
                    sem = AnalyzerReport(); sem.findings = promises
                    reports.append(sem)
            except Exception as e:
                elog("WARN", f"   ⚠ pre-test semantic flow scan failed: {e}")
        return _merge_analyzer_reports(*reports)

    def _key(f):
        return (getattr(f, "code", ""), getattr(f, "path", ""),
                re.sub(r"\b[0-9a-f]{24}\b", "<id>",
                       str(getattr(f, "message", "") or ""))[:200])

    report = collect()
    serious = _serious_findings(report)
    written = 0
    parked = {}
    convergence_round = 0

    # The whole loop shares one snapshot and one build. Rebuilding after
    # every round cost three green builds on one run; the repairs are
    # syntax-checked per round and the batch is compiled once at the end,
    # reverted whole if that compile fails.
    loop_snap = FileSnapshot(proj_dir)
    loop_snap.capture([p for p in arch.files
                       if p.startswith(("app/", "components/", "lib/"))])

    while build_ok and serious and convergence_round < 2:
        # A finding that survived a repair of its own file gets parked, not
        # chased. The old same-state breaker never fired because the model
        # audit jittered a finding in and out each round.
        active = [f for f in serious if parked.get(_key(f), 0) < 1]
        if not active:
            elog("WARN", "   ↔ every remaining flow finding already survived "
                         "its own repair — parking them for the report")
            break
        convergence_round += 1
        elog("INFO", f"   🔗 pre-test flow analysis found {len(active)} "
                     f"disconnected promise(s) — evidence repair round "
                     f"{convergence_round}")
        focus = AnalyzerReport()
        focus.findings = active
        focus.missing = list(getattr(report, "missing", None) or [])
        n = repair_findings(arch, proj_dir, analyzer, focus, True,
                            restart_dev=False, validate_build=False)
        written += n
        if not n:
            elog("WARN", "   ↔ no files changed for the remaining planned-flow "
                         "evidence; leaving it explicitly unresolved")
            break
        for f in active:
            parked[_key(f)] = parked.get(_key(f), 0) + 1
        # Deterministic rescan only: the model promise audit jitters, and a
        # convergence loop keyed on jitter never converges.
        report = collect(semantic=False)
        next_serious = _serious_findings(report)
        for f in next_serious:
            parked.setdefault(_key(f), parked.get(_key(f), 0))
        closed = {_key(f) for f in serious} - {_key(f) for f in next_serious}
        for k in closed:
            parked.pop(k, None)
        serious = next_serious

    if written and build_ok:
        elog("INFO", "   🔨 flow repairs settled — one production build")
        if not run_build_fix_loop(arch, proj_dir, MONGO.available,
                                  max_rounds=1):
            elog("WARN", "   ↩ the flow repair batch broke the build — "
                         "restoring the pre-loop source")
            loop_snap.restore()
            try:
                arch.load_existing()
            except Exception:
                pass
            written = 0
            run_build_fix_loop(arch, proj_dir, MONGO.available, max_rounds=1)
            report = collect(semantic=False)
            serious = _serious_findings(report)

    clean = bool(build_ok and not serious)
    conclusive = bool(build_ok)
    if clean:
        elog("INFO", "   ✅ planned pages/capabilities/flows are connected before testing")
    elif serious:
        elog("WARN", f"   ⚠ {len(serious)} planned flow issue(s) remain before testing")
    else:
        elog("WARN", "   ⚠ pre-test flow proof was inconclusive")

    try:
        d = proj_dir / ".agentforge"; d.mkdir(parents=True, exist_ok=True)
        (d / "pretest-flow.json").write_text(json.dumps({
            "clean": clean, "conclusive": conclusive, "written": written,
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "serious": [{"severity": getattr(f,"severity",""),
                         "code": getattr(f,"code",""),
                         "path": getattr(f,"path",""),
                         "message": getattr(f,"message","")}
                        for f in serious[:30]],
        }, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    ephase({"phase": -24, "title": "Closing planned flows", "status": "done",
            "clean": clean, "issues": len(serious), "written": written})
    return report, clean, conclusive, written


def _runtime_route_source(route: str, arch=None, analyzer=None) -> str:
    """Best source file for a runtime GET route, including dynamic routes."""
    route = (route or "/").split("?", 1)[0].rstrip("/") or "/"
    try:
        routes = analyzer.enumerate_routes() if analyzer is not None else {}
    except Exception:
        routes = {}
    meta = routes.get(route) or routes.get(route.rstrip("/")) or {}
    rel = str(meta.get("file") or "").strip()
    if rel:
        return rel
    for pattern, info in routes.items():
        if not info.get("dynamic"):
            continue
        rx = re.escape(pattern.rstrip("/") or "/")
        rx = re.sub(r"\\\[\\\.\\\.\\\.[^\\\]]+\\\]", r".+", rx)
        rx = re.sub(r"\\\[[^\\\]]+\\\]", r"[^/]+", rx)
        if re.fullmatch(rx, route):
            rel = str(info.get("file") or "").strip()
            if rel:
                return rel

    files = getattr(arch, "files", None) or {}
    if route == "/":
        for rel in ("app/page.jsx", "app/page.js"):
            if rel in files:
                return rel
    direct = "app" + route + "/page"
    for ext in (".jsx", ".js", ".tsx", ".ts"):
        if direct + ext in files:
            return direct + ext
    return ""


def _nearby_runtime_route(trace: str, fault: str, arch=None, analyzer=None) -> tuple:
    """Route/source nearest a terminal fault in the ordered Next dev log.

    React/Next often prints the exception before the request's final ``GET``
    timing line, while browser console errors usually print just after it.  Use
    the nearest request on either side within a small window; this is evidence
    for repair focus, not a substitute for the fresh post-repair re-probe.
    """
    lines = str(trace or "").splitlines()
    if not lines or not fault:
        return "", ""
    idx = next((i for i, line in enumerate(lines) if fault in line), -1)
    if idx < 0:
        key = re.sub(r"^.*?(?:\[next\]\s*)?", "", fault).strip()
        idx = next((i for i, line in enumerate(lines) if key and key in line), -1)
    if idx < 0:
        return "", ""

    candidates = []
    get_re = re.compile(r"\bGET\s+(/[^\s?]*(?:\?[^\s]*)?)\s+\d{3}\b")
    for j in range(max(0, idx - 10), min(len(lines), idx + 11)):
        m = get_re.search(lines[j])
        if not m:
            continue
        route = m.group(1)
        distance = abs(j - idx)
        after_bias = 0 if j >= idx else 1
        candidates.append((distance, after_bias, route))
    for _distance, _bias, route in sorted(candidates):
        rel = _runtime_route_source(route, arch, analyzer)
        if rel:
            return route, rel
    return "", ""


def _runtime_fault_findings(trace: str, arch=None, analyzer=None) -> list:
    """Turn Next/browser terminal faults into source-located findings.

    A stack frame such as `components/Foo.jsx:84:21` is stronger evidence than
    the eventual selector/HTTP symptom.  Preserve that location so the fixer
    opens the exact line instead of asking the LLM to guess which page caused
    the exception.  Generic terminal faults are kept only when no exact project
    frame was available for that message.
    """
    blob = str(trace or "")
    norm = blob.replace("\\", "/")
    out, seen = [], set()

    files = (getattr(arch, "files", None) or {}) if arch is not None else {}
    for rel in files:
        rel = str(rel or "").replace("\\", "/").lstrip("./")
        if not rel.startswith(("app/", "components/", "lib/")):
            continue
        if not rel.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs")):
            continue
        rx = re.compile(re.escape(rel) + r":(\d+)(?::(\d+))?", re.I)
        for m in rx.finditer(norm):
            line = int(m.group(1) or 0)
            col = int(m.group(2) or 0)
            around = norm[max(0, m.start()-900):min(len(norm), m.end()+900)]
            if not re.search(
                r"(?:ReferenceError|TypeError|RangeError|SyntaxError|Error:|"
                r"Unhandled|Failed to compile|cannot be passed|is not defined|"
                r"module not found|runtime error|\b500\b)", around, re.I):
                continue
            key = (rel, line, col)
            if key in seen:
                continue
            seen.add(key)
            location = f"{rel}:{line}" + (f":{col}" if col else "")
            msg = " ".join(around.split())[:700]
            out.append(Finding(
                "blocker", "RUNTIME_EXCEPTION",
                f"Runtime stack points to {location}: {msg}",
                path=rel,
                fix=(f"open {location}, inspect the surrounding source and make "
                     "the smallest repair at that production frame"),
                extra=[location]))
            if len(out) >= 12:
                return out

    # Keep terminal errors that did not include a project source.
    for fault in terminal_faults(blob):
        if len(out) >= 12:
            break
        if re.search(r"destination stream closed early|Fast Refresh had to perform a full reload",
                     fault, re.I):
            continue
        m = re.search(r"((?:app|components|lib)[\\/][A-Za-z0-9_./\\\[\]-]+\.(?:jsx?|tsx?|mjs))(?::(\d+))?(?::(\d+))?", fault)
        rel = m.group(1).replace("\\", "/") if m else ""
        route = ""
        if not rel and ("[browser]" in fault or
                        "Only plain objects can be passed" in fault or
                        "Classes or other objects with methods are not supported" in fault):
            route, rel = _nearby_runtime_route(blob, fault, arch, analyzer)
        loc = ""
        if m and m.group(2):
            loc = f":{m.group(2)}" + (f":{m.group(3)}" if m.group(3) else "")
        key = (rel, int(m.group(2)) if m and m.group(2) else 0,
               int(m.group(3)) if m and m.group(3) else 0)
        if rel and key in seen:
            continue
        out.append(Finding(
            "blocker", "RUNTIME_EXCEPTION",
            f"Next/browser runtime exception at {rel + loc if rel else 'runtime'}"
            + (f" while serving {route}" if route else "") + f": {fault[:700]}",
            path=rel,
            fix=("repair the source-located Server/Client/runtime boundary and "
                 "re-probe the same route while capturing fresh terminal faults"),
            extra=([rel + loc, route] if rel and route else [rel + loc] if rel else [])))

    def _fault_family(finding):
        text = getattr(finding, "message", "") or ""
        for signal in _TERMINAL_SIGNALS:
            if signal in text:
                return signal
        return ""

    located_families = {_fault_family(f) for f in out if getattr(f, "path", "")}
    out = [f for f in out
           if getattr(f, "path", "") or not _fault_family(f)
           or _fault_family(f) not in located_families]
    return out[:12]


RUNTIME_REPAIR_ROUNDS = 2


def _runtime_confirmation_targets(findings, report, analyzer) -> list:
    """Concrete URLs that can prove a source-located runtime repair."""
    examples = getattr(report, "runtime_examples", None) or {}
    out, seen = [], set()
    for finding in findings or []:
        rel = str(getattr(finding, "path", "") or "").strip()
        candidates = []
        for item in list(getattr(finding, "extra", None) or []):
            item = str(item or "").strip()
            if item.startswith("/"):
                candidates.append(item)
        msg = str(getattr(finding, "message", "") or "")
        for m in re.finditer(r"while serving\s+(/[^\s,;]+)", msg, re.I):
            candidates.append(m.group(1))
        candidates.extend(list(examples.get(rel) or []))

        route = _route_for_page_source(rel)
        if route and "[" not in route:
            candidates.append(route)
        if getattr(finding, "code", "") == "ROUTE_ERROR":
            m = re.search(r"\b(/[^\s]+)\s+returns\s+HTTP", msg)
            if m:
                candidates.append(m.group(1))

        for url in candidates:
            url = str(url or "").strip()
            if not url.startswith("/") or url.startswith("/api/"):
                continue
            source = rel or _runtime_route_source(url, None, analyzer)
            key = (url, source)
            if key in seen:
                continue
            seen.add(key)
            out.append(key)
    return out


def run_runtime_verification_stage(arch, proj_dir: Path, analyzer, *, db_ok: bool,
                                   build_ok: bool, allow_repair: bool = True):
    """Verify pages, optionally repair faults, then re-probe affected URLs."""
    ephase({"phase": -25, "title": "Runtime verification", "status": "active"})
    stage_snap = FileSnapshot(proj_dir)
    stage_snap.capture([p for p in arch.files
                        if p.startswith(("app/", "components/", "lib/"))])
    mark = dev_log_mark()
    try:
        report = analyzer.run_runtime(
            mongo=MONGO, node_bin=NODE_BIN, use_model=bool(build_ok and allow_repair), probe_apis=False,
            skip_root=True,
            dev_log=lambda: _filter_db_noise(dev_log_since(mark), db_ok))
    except Exception as e:
        elog("WARN", f"   ⚠ Runtime verification failed: {e}")
        report = AnalyzerReport()
    trace = _filter_db_noise(dev_log_since(mark), db_ok)
    report.findings.extend(_runtime_fault_findings(trace, arch, analyzer))
    serious = _serious_findings(report)

    self_repaired = int(getattr(report, "written", 0) or 0)
    written = self_repaired
    if allow_repair and build_ok and self_repaired and not serious:
        _stop_dev_proc()
        if not run_build_fix_loop(arch, proj_dir, db_ok, max_rounds=1):
            report.findings.append(Finding(
                "blocker", "RUNTIME_REPAIR_BUILD",
                "runtime self-repair did not compile", path="",
                fix="repair the runtime change so production build is green"))
            serious = _serious_findings(report)
        start_next(proj_dir)
        wait_for_next()

    current_trace = trace
    seen_findings = set()
    round_no = 0
    while allow_repair and build_ok and serious and round_no < RUNTIME_REPAIR_ROUNDS:
        round_no += 1
        finding_state = tuple(sorted(
            (getattr(f, "code", ""), getattr(f, "path", ""),
             re.sub(r"\b[0-9a-f]{24}\b", "<id>",
                    str(getattr(f, "message", "") or ""))[:260])
            for f in serious))
        if finding_state in seen_findings:
            elog("WARN", "   ↔ the same runtime finding survived the previous repair — stopping instead of rewriting it again")
            break
        seen_findings.add(finding_state)

        for finding in serious:
            stage_snap.capture([str(rel or "").strip().replace("\\", "/").lstrip("./")
                                for rel in (getattr(finding, "extra", None) or [])
                                if str(rel or "").strip().startswith(("app/", "components/", "lib/"))])
        targets = _runtime_confirmation_targets(serious, report, analyzer)
        elog("INFO", f"   🩺 runtime repair {round_no}/{RUNTIME_REPAIR_ROUNDS}"
                     + (f" — will re-check {len(targets)} affected page(s)" if targets else ""))
        repaired = repair_findings(
            arch, proj_dir, analyzer, report, db_ok, restart_dev=False,
            server_log=current_trace, validate_build=False)
        written += repaired
        if not repaired:
            break

        check = analyzer.scan()
        check.runtime_examples = dict(getattr(report, "runtime_examples", None) or {})
        confirm_mark = dev_log_mark()
        probed_paths = set()
        for url, rel in targets:
            source = rel or _runtime_route_source(url, arch, analyzer)
            if source:
                probed_paths.add(source)
                bucket = check.runtime_examples.setdefault(source, [])
                if url not in bucket:
                    bucket.append(url)
            status = analyzer._get_status(analyzer.base_url + url)
            if status is None or status >= 400:
                check.findings.append(Finding(
                    "blocker", "ROUTE_ERROR",
                    f"{url} returns HTTP {status}", path=source,
                    fix=f"fix {source or url} so {url} responds"))
        if targets:
            time.sleep(0.2)
        current_trace = _filter_db_noise(dev_log_since(confirm_mark), db_ok)
        check.findings.extend(_runtime_fault_findings(current_trace, arch, analyzer))

        unprovable = {"RUNTIME_EXCEPTION", "RUNTIME_REPAIR_BUILD"}
        carried = [f for f in serious
                   if getattr(f, "code", "") in unprovable
                   and getattr(f, "path", "") not in probed_paths]
        if carried:
            check.findings.extend(carried)
            elog("INFO", f"   ↁ {len(carried)} runtime finding(s) still lack a concrete confirmation route")

        report = check
        serious = _serious_findings(report)
        if not serious:
            elog("INFO", "   ✅ affected runtime pages are clean after repair")
            break

    if written and allow_repair and build_ok and hasattr(arch, "packages_named_in"):
        elog("INFO", "   🔨 runtime repairs settled — one production build")
        _stop_dev_proc()
        if not run_build_fix_loop(arch, proj_dir, db_ok, max_rounds=1):
            elog("WARN", "   ↩ runtime repair batch broke the build — restoring the pre-stage source")
            stage_snap.restore()
            try:
                arch.load_existing()
            except Exception:
                pass
            report.findings.append(Finding(
                "blocker", "RUNTIME_REPAIR_BUILD",
                "runtime repair batch did not compile", path="",
                fix="repair the runtime change so production build is green"))
            serious = _serious_findings(report)
            written = 0
        start_next(proj_dir)
        wait_for_next()

    clean = bool(build_ok and not serious)
    ephase({"phase": -25, "title": "Runtime verification", "status": "done",
            "clean": clean, "issues": len(serious), "written": written})
    return report, clean, written

def run_api_verification_stage(arch, proj_dir: Path, analyzer, *, db_ok: bool,
                               build_ok: bool, allow_repair: bool = True):
    """Probe non-mutating API routes and optionally repair their faults."""
    ephase({"phase": -26, "title": "API verification", "status": "active"})
    report = analyzer.scan()
    mark = dev_log_mark()
    try:
        from qa_agent.verification.api_verification import probe_non_mutating_apis
        probe_non_mutating_apis(analyzer, report, skip_health=True)
    except Exception as e:
        elog("WARN", f"   ⚠ API verification failed: {e}")
    api_trace = _filter_db_noise(dev_log_since(mark), db_ok)
    report.findings.extend(_runtime_fault_findings(api_trace, arch, analyzer))
    serious = _serious_findings(report)
    written = 0
    if allow_repair and build_ok and serious:
        written = repair_findings(arch, proj_dir, analyzer, report, db_ok,
                                   restart_dev=True, server_log=api_trace)
        if written:
            check = analyzer.scan()
            affected = {getattr(f, "path", "") for f in serious if getattr(f, "path", "")}
            from qa_agent.verification.api_verification import reprobe_affected_gets
            reprobe_affected_gets(analyzer, check, affected, Finding)
            report = check
            serious = _serious_findings(report)
    clean = bool(build_ok and not serious)
    if clean:
        elog("INFO", "   ✅ API verification clean — protected 401/403 responses are accepted")
    ephase({"phase": -26, "title": "API verification", "status": "done",
            "clean": clean, "issues": len(serious), "written": written})
    return report, clean, written


_E2E_HARD_UPSTREAM_CODES = {"RUNTIME_STAGE_FAILED", "API_STAGE_FAILED",
                            "RUNTIME_REPAIR_BUILD"}


def _e2e_hard_upstream_blockers(runtime_report, api_report) -> list:
    """Infrastructure failures that make a browser journey unsafe to start."""
    out = []
    for stage, report in (("runtime", runtime_report), ("api", api_report)):
        for finding in _serious_findings(report):
            if getattr(finding, "code", "") in _E2E_HARD_UPSTREAM_CODES:
                out.append((stage, finding))
    return out


IMAGE_PROMPT_SYSTEM = """\
Turn the requested web visual into one production-ready image-generation prompt.
Reply with the prompt only: one line, concise but specific.

Use the app context to make the image belong to the actual product/domain instead
of looking like generic stock photography. Preserve details the user did not ask
to change. Describe, in this order: main subject, environment/background,
composition for its UI placement, lighting, materials/colour mood, visual style.

Prefer believable commercial/editorial photography, clear focal hierarchy,
intentional negative space where UI will overlay, and a crop that matches the
requested banner/card/background use. Avoid unrelated decorative objects,
clutter, crowds, watermarks, fake UI screenshots and generic AI-art buzzwords.

Normally use no text, logos, signage or lettering. The only exception is when
the user explicitly asks to redraw an advertisement/banner/poster with text;
then request only the exact short wording supplied by the user, clearly readable.
"""

LOGO_PROMPT_SYSTEM = """\
Turn the app/SRS brief into one production-ready logo-generation prompt. Reply
with the prompt only: one line, no explanation.

First identify the exact application/brand name stated in the brief. The logo
MUST include that exact name as clear, correctly spelled, readable text. Design
one memorable domain-relevant symbol in a clean circular badge/emblem plus a
clean wordmark; keep the symbol visibly round and do not invent or shorten the name.

Describe: symbol concept, exact wordmark text in quotes, typography character,
1-2 brand colours, simple background and flat vector treatment. Keep the mark
legible at small sizes, centred, balanced, with generous spacing. Prefer a
professional modern identity appropriate to the app's actual industry.

Avoid scenes, people, hands, storefronts, photographs, gradients unless the
brief specifically needs one, mockup boards, multiple logo variations, slogans,
extra letters, watermarks or unrelated icons. The application name is the only
required text unless the SRS explicitly provides a tagline.
"""


LIGHTHOUSE = "lighthouse@12"


def run_perf_stage(proj_dir: Path) -> dict:
    """
    Lighthouse against the running app, reported and never blocking.

    A slow page is a judgement call, not a defect. A build that refuses to
    finish over a performance score would be a build that refuses to finish
    over a hero image somebody may well have wanted, so this stage says what it
    measured and gets out of the way.

    Driven through the Chromium Playwright has already downloaded — the tester
    and the e2e pass both use it — so there is no second browser to install.
    """
    ephase({"phase": -23, "title": "Performance", "status": "active"})
    chrome = _playwright_chromium()
    if not chrome:
        elog("INFO", "   ⚡ No Chromium available — the performance check is "
                     "skipped")
        ephase({"phase": -23, "title": "Performance", "status": "done"})
        return {}

    out = proj_dir / ".agentforge" / "lighthouse.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = CommandRunner(proj_dir, npm_bin=NPM_BIN, node_bin=NODE_BIN,
                        on_log=lambda lvl, txt: elog(lvl, txt), max_calls=6)
    env_was = os.environ.get("CHROME_PATH")
    os.environ["CHROME_PATH"] = chrome
    try:

        rel = out.relative_to(proj_dir).as_posix()

        res = cmd.run(
            f"npx --yes {LIGHTHOUSE} http://127.0.0.1:{DEV_PORT} "
            f"--output=json --output-path={rel} --quiet "
            f'--chrome-flags="--headless=new --no-sandbox"',
            timeout=300)
    finally:
        if env_was is None:
            os.environ.pop("CHROME_PATH", None)
        else:
            os.environ["CHROME_PATH"] = env_was

    if not out.is_file():
        elog("WARN", "   ⚠ Lighthouse produced no report — the performance "
                     "check is skipped")
        log.debug(f"lighthouse: {(res.output or '')[-400:]}")
        ephase({"phase": -23, "title": "Performance", "status": "done"})
        return {}

    try:
        data = json.loads(out.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        elog("WARN", f"   ⚠ Could not read the Lighthouse report: {e}")
        ephase({"phase": -23, "title": "Performance", "status": "done"})
        return {}

    err = data.get("runtimeError") or {}
    if err.get("code"):
        elog("WARN", f"   ⚠ Lighthouse could not measure the app: "
                     f"{err.get('code')} — "
                     f"{str(err.get('message', ''))[:120]}")
        ephase({"phase": -23, "title": "Performance", "status": "done"})
        return {}

    scores, cats = {}, data.get("categories") or {}
    for key in ("performance", "accessibility", "best-practices", "seo"):
        raw = (cats.get(key) or {}).get("score")
        if raw is None:
            continue
        pct = int(round(raw * 100))
        scores[key] = pct
        emit({"type": "test_result",
              "status": "pass" if pct >= 90 else ("warn" if pct >= 50 else "fail"),
              "msg": f"Lighthouse: {key.replace('-', ' ')}", "detail": f"{pct}/100"})

    audits = data.get("audits") or {}
    metrics = " · ".join(
        f"{name} {(audits.get(key) or {}).get('displayValue', '?')}"
        for name, key in (("LCP", "largest-contentful-paint"),
                          ("CLS", "cumulative-layout-shift"),
                          ("TBT", "total-blocking-time"))
        if audits.get(key))
    elog("INFO", "   ⚡ " + " · ".join(f"{k.replace('-', ' ')} {v}"
                                       for k, v in scores.items()))
    if metrics:
        elog("INFO", f"   ⚡ {metrics}")

    scores["measured_on"] = "next dev — not a production build"
    elog("INFO", "   ⚡ measured against `next dev`: routes compile on first "
                 "request and the JavaScript is unminified, so these are not "
                 "the numbers the built app would give")

    ephase({"phase": -23, "title": "Performance", "status": "done"})
    return scores


def _playwright_chromium() -> str:
    """The Chromium Playwright installed, or "" — Lighthouse needs a browser."""
    root = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    if not root.is_dir():
        return ""

    for d in sorted(root.glob("chromium-*"), reverse=True):
        for sub, exe in (("chrome-win64", "chrome.exe"),
                         ("chrome-win", "chrome.exe"),
                         ("chrome-linux", "chrome"),
                         ("chrome-mac", "Chromium.app/Contents/MacOS/Chromium")):
            p = d / sub / exe
            if p.is_file():
                return str(p)
    return ""


def run_delivery_stabilization(arch, proj_dir: Path, analyzer, *, db_ok: bool,
                               build_ok: bool, rounds: int = 3):
    """Final delivery gate: repair served behavior even when QA tests stay red."""
    ephase({"phase": -27, "title": "Final self-healing", "status": "active"})
    total_written, report, serious = 0, AnalyzerReport(), []
    for rnd in range(1, max(1, rounds) + 1):
        elog("INFO", f"   🛡 delivery stabilization {rnd}/{rounds}")
        db_ok = db_ok or database_ready()
        if not build_ok:
            _stop_dev_proc()
            build_ok = bool(run_build_fix_loop(arch, proj_dir, db_ok, max_rounds=2))
        if not _dev_alive():
            start_next(proj_dir); wait_for_next()
        seed_error = ""
        if db_ok:
            try: seed_error = seed_project(getattr(arch, "plan", None) or {}) or ""
            except Exception as e: seed_error = f"seed endpoint failed: {e}"

        mark = dev_log_mark()
        try:
            report = analyzer.run_runtime(mongo=MONGO, node_bin=NODE_BIN,
                                          use_model=False, probe_apis=True,
                                          skip_root=False)
        except Exception as e:
            elog("WARN", f"   ⚠ final runtime sweep failed: {e}")
            report = analyzer.scan()
        if build_ok:
            try:
                promises = analyzer.unbuilt_promises(max_reads=8)
                report.findings.extend(promises)
            except Exception as e:
                elog("WARN", f"   ⚠ final journey audit failed: {e}")
        trace = _filter_db_noise(dev_log_since(mark), db_ok)
        report.findings.extend(_runtime_fault_findings(trace, arch, analyzer))
        if seed_error:
            report.findings.append(Finding("blocker", "SEED_RUNTIME", seed_error,
                                           "lib/seed.js" if "lib/seed.js" in arch.files else "app/api/seed/route.js",
                                           "persist every planned seed row and role account; never return success after an early abort", ["lib/auth.js"]))
        serious = _serious_findings(report)
        if not serious and _dev_alive():
            elog("INFO", "   ✅ final served routes, data contracts and journeys are clean")
            break

        before = total_written
        total_written += repair_findings(
            arch, proj_dir, analyzer, report, db_ok, restart_dev=True,
            server_log=trace, validate_build=bool(build_ok))
        if total_written == before:
            elog("WARN", "   ↔ final self-heal found no additional evidence-backed write")
            break
        if not build_ok:
            _stop_dev_proc(); start_next(proj_dir); wait_for_next()

    if total_written and not build_ok:
        _stop_dev_proc()
        build_ok = bool(run_build_fix_loop(arch, proj_dir, db_ok, max_rounds=2))
        start_next(proj_dir); wait_for_next()

    # A repair/build pass may have changed source after the last verdict. Never
    # ship a stale green receipt: probe the exact bytes that remain on disk.
    if not _dev_alive():
        start_next(proj_dir); wait_for_next()
    mark = dev_log_mark()
    try:
        final_runtime = analyzer.run_runtime(
            mongo=MONGO, node_bin=NODE_BIN, use_model=False, probe_apis=True,
            skip_root=False)
    except Exception as e:
        final_runtime = AnalyzerReport()
        final_runtime.findings.append(Finding(
            "blocker", "FINAL_RUNTIME_FAILED", f"final runtime probe failed: {e}"))
    final_reports = [final_runtime]
    if build_ok:
        try:
            semantic = AnalyzerReport()
            semantic.findings.extend(analyzer.unbuilt_promises(max_reads=8))
            final_reports.append(semantic)
        except Exception as e:
            semantic = AnalyzerReport()
            semantic.findings.append(Finding(
                "major", "FINAL_JOURNEY_AUDIT_FAILED",
                f"final journey audit failed: {e}"))
            final_reports.append(semantic)
    trace = _filter_db_noise(dev_log_since(mark), db_ok)
    faults = AnalyzerReport()
    faults.findings.extend(_runtime_fault_findings(trace, arch, analyzer))
    final_reports.append(faults)
    report = _merge_analyzer_reports(*final_reports)
    serious = _serious_findings(report)
    serving = bool(_dev_alive())
    clean = bool(serving and not serious)
    ephase({"phase": -27, "title": "Final self-healing", "status": "done",
            "clean": clean, "issues": len(serious), "written": total_written})
    return build_ok, db_ok, report, clean, serving, total_written
