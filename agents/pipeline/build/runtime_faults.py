

_DB_ERROR_MARKERS = ("MongoServerSelectionError", "MongoNetworkError",
                     "ECONNREFUSED", "MONGODB_URI", "/api/health",
                     "connect ETIMEDOUT")

# Only the faults that mean "the database is not answering". `/api/health` and
# `MONGODB_URI` are deliberately absent: a health route can fail for its own
# reasons, and naming a variable is not a connection failure.
_DB_DOWN_MARKERS = ("MongoServerSelectionError", "MongoNetworkError",
                    "ECONNREFUSED", "connect ETIMEDOUT")


# True when what failed is the database connection, not the app.
def database_fault(errors) -> bool:
    """True when what failed is the database connection, not the app."""
    text = "\n".join(str(e) for e in (errors or ()))
    return any(marker in text for marker in _DB_DOWN_MARKERS)


# Bring MongoDB back mid-run and report whether it answers now. A build outlives its database sometimes — mongod
# is killed, crashes, or was a child of a process that went away. The runtime loop used to hand `ECONNREFUSED
# 127.0.0.1:27017` to the repair agent as if the generated app had a bug, which spends a repair round rewriting
# correct code and ends with the same error. Restarting the server is the only repair that can work.
def recover_database() -> bool:
    """Bring MongoDB back mid-run and report whether it answers now.

    A build outlives its database sometimes — mongod is killed, crashes, or
    was a child of a process that went away. The runtime loop used to hand
    `ECONNREFUSED 127.0.0.1:27017` to the repair agent as if the generated app
    had a bug, which spends a repair round rewriting correct code and ends with
    the same error. Restarting the server is the only repair that can work.
    """
    try:
        MONGO.available = False
        # From: agents/data/database_server.py
        ok = bool(MONGO.ensure_running())
    except Exception as e:                                       # noqa: BLE001
        # From: agents/build/tester_common.py
        elog("WARN", f"   ⚠ could not restart MongoDB: {e}")
        return False
    # From: agents/build/tester_common.py
    elog("INFO" if ok else "WARN",
         "   🍃 MongoDB is answering again" if ok else
         "   ⚠ MongoDB is still down — database pages will keep failing")
    return ok


# Remove database connection noise when the current build failure has another proven owner.
def _filter_db_noise(text: str, db_ok: bool) -> str:
    """Remove database connection noise when the current build failure has another proven owner."""
    if db_ok or not text:
        return text
    keep = [ln for ln in text.splitlines()
            if not any(m in ln for m in _DB_ERROR_MARKERS)]
    return "\n".join(keep)


_TERMINAL_SIGNALS = (
    "Only plain objects can be passed",
    "Functions cannot be passed directly",
    "Event handlers cannot be passed",
    "cannot be passed directly to Client Components",
    "Classes or other objects with methods are not supported",
    "Objects are not valid as a React child",
    "Maximum update depth exceeded",
    "Hydration failed",
    "Text content does not match",
    "only works in a Client Component",
    "Unhandled Runtime Error",
    "Unhandled Rejection",
    "Module not found",
    "is not exported from",
    "is not a function",
    "is not defined",
    "Cannot read properties",
    "ReferenceError",
    "SyntaxError",
    "⨯",
)


_TRANSIENT_TERMINAL_RE = re.compile(
    r"destination stream closed early|Fast Refresh had to perform a full reload|"
    r"\bERR_ABORTED\b", re.I)


# Next dev navigation noise that is not evidence of an app defect.
def _transient_terminal_fault(line: str) -> bool:
    """Next dev navigation noise that is not evidence of an app defect."""
    return bool(_TRANSIENT_TERMINAL_RE.search(str(line or "")))


# The dev server's distinct actionable runtime complaints.
def terminal_faults(text: str, limit: int = 6) -> list:
    """The dev server's distinct actionable runtime complaints."""
    if not text:
        return []
    seen, out = set(), []
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 12 or _transient_terminal_fault(line):
            continue
        if not any(s in line for s in _TERMINAL_SIGNALS):
            continue

        key = re.sub(r"[{<].*", "", line)[:90]
        if key in seen:
            continue
        seen.add(key)
        out.append(line[:400])
        if len(out) >= limit:
            break
    return out


MAX_BUILD_FIX = 3


_TW_DIRECTIVES = re.compile(r"^[ \t]*@tailwind\s+(base|components|utilities)\s*;\s*$",
                            re.M)


# Align PostCSS and CSS directives with installed Tailwind 4.
def align_tailwind(arch, proj_dir: Path) -> bool:
    """Align PostCSS and CSS directives with installed Tailwind 4."""
    try:
        meta = proj_dir / "node_modules" / "tailwindcss" / "package.json"
        if not meta.is_file():
            return False
        major = int(str(json.loads(meta.read_text(encoding="utf-8"))
                        .get("version", "0")).split(".")[0] or 0)
    except Exception:
        return False
    if major < 4:
        return False

    changed = []
    for name in ("postcss.config.js", "postcss.config.cjs", "postcss.config.mjs"):
        fp = proj_dir / name
        if fp.is_file():
            try:
                fp.unlink()
                arch.files.pop(name, None)
            except OSError:
                pass
    was = getattr(arch, "_scaffolding", False)
    arch._scaffolding = True
    try:
        # From: agents/planner/builder/file_writer.py
        if arch.write_file("postcss.config.mjs",
                           "const config = { plugins: { '@tailwindcss/postcss': {} } }\n"
                           "export default config\n"):
            changed.append("postcss.config.mjs")

        css = proj_dir / "app" / "globals.css"
        try:
            body = css.read_text(encoding="utf-8") if css.is_file() else ""
        except OSError:
            body = ""
        if body and _TW_DIRECTIVES.search(body):
            body = _TW_DIRECTIVES.sub("", body, count=3).lstrip("\n")
            # From: agents/planner/builder/file_writer.py
            if arch.write_file("app/globals.css",
                               '@import "tailwindcss";\n\n' + body):
                changed.append("app/globals.css")
    finally:
        arch._scaffolding = was

    if not (proj_dir / "node_modules" / "@tailwindcss" / "postcss").is_dir():
        try:
            arch.cmd.run("npm install -D @tailwindcss/postcss")
            changed.append("@tailwindcss/postcss")
        except Exception as e:
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ could not install @tailwindcss/postcss: {e}")

    # From: agents/build/tester_common.py
    elog("INFO", f"   🎨 Tailwind {major} is installed — "
                 f"{', '.join(changed)} written to match it")
    return True


_INSTALL_WITNESS = {
    "next": ("package.json", "dist/build/output/log.js", "dist/bin/next"),
    "react": ("package.json", "index.js"),
    "react-dom": ("package.json", "index.js"),
}

_PKG_INTERNAL_RE = re.compile(
    r"Cannot find module ['\"](\.\.?/[^'\"]+)['\"]"
    r"|Cannot find module ['\"]([^'\"]*[\\/]node_modules[\\/][^'\"]+)['\"]",
    re.I)


# Returns evidence of an incomplete install, or ``""`` for app faults.
def _toolchain_break(proj_dir: Path, errors: str = "") -> str:
    """Return evidence of an incomplete install, or ``""`` for app faults."""
    nm = proj_dir / "node_modules"
    if not nm.is_dir():
        return "node_modules is missing"

    for name, witnesses in _INSTALL_WITNESS.items():
        if not (nm / name).is_dir():
            continue  # not installed is _deps_ready's job
        for rel in witnesses:
            if not (nm / name / rel).exists():
                return f"node_modules/{name} is incomplete — {rel} is missing"

    m = _PKG_INTERNAL_RE.search(errors or "")
    if m:
        spec = m.group(1) or m.group(2) or ""
        return (f"a package asked for {spec!r}, which is inside an installed "
                f"package and not anything this app wrote")
    return ""


# Reinstall the broken packages. Returns True when something was done.
def _repair_toolchain(proj_dir: Path, why: str) -> bool:
    """Reinstall the broken packages. Returns True when something was done."""
    # From: agents/build/tester_common.py
    elog("WARN", f"   🔧 the toolchain is what is broken, not the app: {why}")
    nm = proj_dir / "node_modules"
    dropped = []
    for name, witnesses in _INSTALL_WITNESS.items():
        d = nm / name
        if not d.is_dir():
            continue
        if all((d / rel).exists() for rel in witnesses):
            continue
        try:
            shutil.rmtree(d, ignore_errors=True)
            dropped.append(name)
        except Exception as e:
            log.debug(f"removing {d}: {e}")
    if dropped:
        # From: agents/build/tester_common.py
        elog("INFO", "   🗑 removed the half-installed "
                     + ", ".join(dropped) + " so npm reinstalls it")
    elif not nm.is_dir():
        pass
    else:
        # From: agents/build/tester_common.py
        elog("INFO", "   📦 reinstalling to reconcile the error with the disk")
        try:
            (proj_dir / "node_modules" / ".package-lock.json").unlink()
        except Exception:
            pass
    ok = ensure_node_deps(proj_dir)
    # From: agents/build/tester_common.py
    elog("INFO" if ok else "WARN",
         "   ✅ the toolchain is installed again" if ok else
         "   ⚠ the reinstall did not succeed")
    return ok
