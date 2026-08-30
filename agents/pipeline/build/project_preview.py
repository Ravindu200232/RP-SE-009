# Repair flow: build -> collect evidence -> patch owned files -> rebuild.


# Returns build errors and whether the check reached a conclusion.
def _npm_build_errors(proj_dir: Path, stack: str = "next"):
    """Return build errors and whether the check reached a conclusion."""
    timeout = NEXT_BUILD_TIMEOUT if stack == "next" else 120
    env = {**os.environ, "CI": "true", "NEXT_TELEMETRY_DISABLED": "1",
           "NO_COLOR": "1", "FORCE_COLOR": "0"}
    try:
        # From: agents/core/runtime/cancellation.py
        r = cancel.run([NPM_BIN, "run", "build"], cwd=proj_dir,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        log.warning("build check timed out")
        return "", False
    except Exception as e:
        log.warning(f"build check failed: {e}")
        return "", False

    txt = _strip_ansi((r.stdout or "") + "\n" + (r.stderr or ""))

    if r.returncode == 0:

        bad = [ln.strip() for ln in txt.splitlines()
               if "Attempted import error" in ln]
        if bad:
            return ("The build compiled, but these imports do not resolve and "
                    "the pages that make them will throw as soon as they are "
                    "opened:\n" + "\n".join(dict.fromkeys(bad))[:2000]), True
        return "", True

    i = txt.find("Failed to compile")
    if i >= 0:
        txt = txt[i:]
    return txt.strip()[:2500], True


# `mongodb+srv://user:pass@host/db` → `mongodb+srv://user:***@host` — safe to show in the UI.
def _redact_uri(uri: str) -> str:
    """`mongodb+srv://user:pass@host/db` → `mongodb+srv://user:***@host` —
    safe to show in the UI."""
    if not uri:
        return ""
    shown = re.sub(r"://([^:/@]+):[^@]*@", r"://\1:***@", uri)
    return shown[:60] + ("…" if len(shown) > 60 else "")


# Boot an existing project's preview and always report the outcome.
def _open_project(proj_name: str):
    """Boot an existing project's preview and always report the outcome."""
    try:
        proj_dir = PROD_DIR / proj_name
        if not proj_dir.exists():
            eerr(f"Project not found: {proj_name}")
            return
        stack = detect_stack(proj_dir)
        # From: agents/build/tester_common.py
        elog("INFO", f"📂 Opening {proj_name} ({stack})")
        if stack == "next":
            # From: agents/data/database_server.py
            MONGO.ensure_running()
        if not ensure_node_deps(proj_dir):
            eerr("Failed to install dependencies")
            return
        start_dev_server(proj_dir, stack)
        if wait_for_dev(stack):
            edone(f"http://localhost:{DEV_PORT}", proj_name)
        else:
            why = (dev_stderr(stack) or "").strip().splitlines()
            eerr(f"{proj_name} did not start"
                 + (f" — {why[-1][:200]}" if why else
                    ". Its dev server never answered."))
            return
        if stack == "next":
            _announce_project_credentials(proj_dir)
    except Exception as e:
        eerr(f"Could not open {proj_name}: {e}")
        log.exception("open project failed")


# Show an existing project's demo accounts when it is opened.
def _announce_project_credentials(proj_dir: Path):
    """Show an existing project's demo accounts when it is opened."""
    try:
        # From: agents/planner/builder/app_builder.py
        arch = ArchitectAgent(ollama, DEFAULT_BUILD, proj_dir, stack="next")
        # From: agents/planner/builder/project_memory.py
        arch.load_existing()
        # From: agents/pipeline/feature_safety.py
        _analyzer_for(arch, proj_dir)._announce_credentials()
    except Exception as e:
        log.warning(f"could not read demo accounts: {e}")


NOT_A_NAME = {
    "yes", "y", "yeah", "yep", "yup", "ok", "okay", "sure", "fine", "correct",
    "right", "true", "confirm", "confirmed", "no", "n", "nope", "nah", "false",
    "none", "na", "null", "undefined", "app", "application", "webapp",
    "web app", "website", "site", "project", "untitled", "test",
}


# False for a confirmation, a placeholder, or nothing at all.
def _is_a_name(text: str, limit: int = 60) -> bool:
    """False for a confirmation, a placeholder, or nothing at all."""
    name = " ".join(str(text or "").split())
    return bool(name) and len(name) <= limit and name.lower() not in NOT_A_NAME


# Converts a label into a safe URL/file slug.
def _slug(text: str, fallback: str = "app") -> str:
    """Convert a label into a safe URL/file slug."""
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    s = re.sub(r"-+", "-", s)[:28].strip("-")
    return s or fallback


# Returns the first candidate that reads like a durable project name.
def _project_slug(*candidates: str, fallback: str = "app") -> str:
    """Return the first candidate that reads like a durable project name."""
    for text in candidates:
        s = _slug(text, "")
        if s and s.replace("-", " ") not in NOT_A_NAME and s not in NOT_A_NAME:
            return s
    return fallback


# Checks whether a directory contains code beyond owned scaffolding.
def _has_app(d: Path) -> bool:
    """Return whether a directory contains code beyond owned scaffolding."""
    for root in ("app", "components", "lib", "src", "pages"):
        base = d / root
        if not base.is_dir():
            continue
        for fp in base.rglob("*"):
            if fp.is_file() and fp.suffix in {".js", ".jsx", ".mjs"}:
                rel = str(fp.relative_to(d)).replace("\\", "/")
                if rel not in ArchitectAgent.NEXT_SCAFFOLD:
                    return True
    return False


# The installed Next.js major version, or 0 when it cannot be read.
def next_major(proj_dir: Path) -> int:
    """The installed Next.js major version, or 0 when it cannot be read."""
    try:
        pj = proj_dir / "node_modules" / "next" / "package.json"
        if not pj.is_file():
            pj = proj_dir / "package.json"
            v = json.loads(pj.read_text(encoding="utf-8")) \
                    .get("dependencies", {}).get("next", "")
        else:
            v = json.loads(pj.read_text(encoding="utf-8")).get("version", "")
        m = re.search(r"(\d+)", v or "")
        return int(m.group(1)) if m else 0
    except Exception:
        return 0


# Use Webpack where Next 16 otherwise changes diagnostic vocabulary.
def bundler_flag(proj_dir: Path) -> list:
    """Use Webpack where Next 16 otherwise changes diagnostic vocabulary."""
    return ["--webpack"] if next_major(proj_dir) >= 16 else []


# Choose an empty/scaffold directory without overlaying another app.
def _project_dir_for(pname: str, stack: str) -> Path:
    """Choose an empty/scaffold directory without overlaying another app."""
    base = PROD_DIR / pname
    if not base.exists() or not any(base.iterdir()):
        return base
    if not _has_app(base) and detect_stack(base) == stack:
        return base
    for i in range(2, 100):
        alt = PROD_DIR / f"{pname}-{i}"
        if not alt.exists() or not any(alt.iterdir()):
            # From: agents/build/tester_common.py
            elog("INFO", f"   📁 {pname} already holds a "
                         f"{detect_stack(base)} project — using {alt.name}")
            return alt
    return base


# Bridge ArchitectAgent events onto the existing WebSocket protocol.
def _agent_callbacks(proj_dir: Path) -> dict:
    """Bridge ArchitectAgent events onto the existing WebSocket protocol."""
    # From: agents/build/tester_common.py
    return {
        "on_log":      lambda lvl, txt: elog(lvl, txt),
        "on_chat":     lambda text: echat(text),
        "on_progress": lambda label, pct: eprog(label, pct),
        "on_memory":   lambda stats: ememory(stats),
        "on_phase":    lambda p: ephase(p),
        "on_file_start":   lambda path: estream_start(path),
        "on_file_token":   lambda path, tok: estream(path, tok),
        "on_file_end":     lambda path, content: estream_end(path, content),
        "on_file_written": lambda path, size, content: efile(path, size, content),
        "on_command":  lambda ev: ecommand(ev),

        "npm_bin": NPM_BIN,
        "node_bin": NODE_BIN,
    }


# From: agents/build/tester_common.py
# From: agents/data/database_helpers.py
MONGO.set_callbacks({
    "on_log":    lambda lvl, txt: elog(lvl, txt),
    "on_status": lambda s: emongo(s),
})


# The analyzer speaks the same WS protocol as everything else.
def _analyzer_callbacks() -> dict:
    """The analyzer speaks the same WS protocol as everything else."""
    # From: agents/build/tester_common.py
    return {
        "on_log":     lambda lvl, txt: elog(lvl, txt),
        "on_phase":   lambda p: ephase(p),
        "on_command": lambda ev: ecommand(ev),
        "on_mongo":   lambda ev: emongo(ev),
        "on_test":    lambda status, msg, detail="": emit(
            {"type": "test_result", "status": status, "msg": msg,
             "detail": detail}),
        "on_file_start": lambda path: estream_start(path),
        "on_file_end":   lambda path, content: estream_end(path, content),
        "on_creds":      lambda accounts, source, verified: ecreds(
            accounts, source, verified),
        "on_feature_plan": lambda payload: emit({**payload,
                                                 "type": "feature_plan"}),
        "npm_bin": NPM_BIN,
        "node_bin": NODE_BIN,
    }
