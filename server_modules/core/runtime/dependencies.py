# Dependencies: one focused part of the development-server lifecycle.
# Purpose: Are node_modules already correct for this package.json?.
def _deps_ready(proj_dir: Path) -> bool:
    """
    Are node_modules already correct for this package.json?

    Stack-agnostic by construction: instead of probing for a specific binary
    (the old code looked for `vite`, which never exists under Next and so made
    `npm install` re-run on every call), check that every dependency
    package.json declares is physically installed.

    That single test also covers the case this needs to catch — when
    `sync_dependencies()` adds a package, its folder is absent and an install
    is triggered — while still recognising installs done by older versions of
    AgentForge, so existing projects are not needlessly reinstalled.
    """
    nm = proj_dir / "node_modules"
    if not nm.is_dir():
        return False
    try:
        pkg = json.loads((proj_dir / "package.json").read_text(encoding="utf-8"))
    except Exception:
        return False
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    if not deps:
        return False

    return all((nm / name / "package.json").exists() for name in deps)


# Purpose: Make sure all Node.js packages are installed before the app runs.
def ensure_node_deps(proj_dir: Path) -> bool:
    if _deps_ready(proj_dir):
        return True

    elog("INFO", "📦 Installing dependencies (180s cap, one retry)…")
    from qa_agent.unit.harness_common import NPM_LOCK
    with NPM_LOCK:
        for attempt in (1, 2):
            try:
                r = cancel.run(
                    [NPM_BIN, "install", "--no-audit", "--no-fund",
                     "--prefer-offline", "--loglevel=error"],
                    cwd=proj_dir, capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=180,
                    env={**os.environ, "CI": "true", "NO_COLOR": "1",
                         "FORCE_COLOR": "0", "NPM_CONFIG_FUND": "false",
                         "NPM_CONFIG_AUDIT": "false"})
                if r.returncode == 0 and _deps_ready(proj_dir):
                    elog("INFO", "   ✅ npm install complete")
                    return True
                elog("ERROR", f"   ❌ npm install failed:\n{((r.stderr or r.stdout) or '')[:300]}")
                if attempt == 1:
                    elog("WARN", "   ↻ npm install exited non-zero — retrying once")
                    continue
                return False
            except subprocess.TimeoutExpired:
                if attempt == 1:
                    elog("WARN", "   ⏱ npm install exceeded 180s — process tree stopped; retrying once")
                    continue
                elog("ERROR", "   ❌ npm install timed out again after retry")
                return False
            except Exception as e:
                elog("ERROR", f"   ❌ npm install crashed: {e}")
                return False
    return False


# Purpose: Which framework a generated project uses. AgentForge only builds Next.
def detect_stack(proj_dir: Path) -> str:
    """Which framework a generated project uses. AgentForge only builds Next."""
    return "next"


