"""Project folders and editable-file operations used by the Studio."""

# Project flow: validate ownership -> read or change -> notify the Studio.
SRC_ROOTS = ("app", "components", "lib", "src", "pages")
SKIP_DIRS = {"node_modules", ".next", ".git", "dist", "out", ".vite", ".turbo",
             ".agentforge"}
SRC_EXT = {".js", ".jsx", ".css"}


# Every source file in a project, whatever layout it uses.
def _iter_source(proj_dir: Path):
    """Every source file in a project, whatever layout it uses."""
    for root in SRC_ROOTS:
        base = proj_dir / root
        if not base.is_dir():
            continue
        for fp in base.rglob("*"):
            if not fp.is_file() or fp.suffix not in SRC_EXT:
                continue
            if any(s in fp.parts for s in SKIP_DIRS):
                continue
            yield fp


# Resolves one HTTP-supplied directory name inside its owned root.
def _owned_dir(root: Path, raw: str, label: str,
               missing_label: str) -> tuple:
    """Resolve one HTTP-supplied directory name inside its owned root."""
    name = str(raw or "").strip().replace("\\", "/")
    if not name or "/" in name or name in (".", "..") or name.startswith("."):
        return name, None, f"{raw!r} is not a {label}"
    try:
        resolved = (root / name).resolve()
        # From: agents/features/element_selector.py
        resolved.relative_to(root.resolve())
    except (ValueError, OSError):
        return name, None, f"{name} is outside {root.name}"
    if not resolved.is_dir():
        return name, None, f"no such {missing_label}: {name}"
    return name, resolved, ""




# Remove a fenced project, then its generated database, in background.
def delete_project(proj_name: str) -> dict:
    """Remove a fenced project, then its generated database, in background."""
    name, resolved, error = _owned_dir(
        PROD_DIR, proj_name, "project name", "project")
    if error:
        return {"error": error}

    if active_vite.get("dir") == str(resolved):
        # From: agents/build/tester_common.py
        elog("INFO", f"   ⏹ Stopping the dev server before deleting {name}")
        _stop_dev_proc()
        _kill_port(DEV_PORT)
        active_vite["dir"] = None

    trash = PROD_DIR / f".trash-{name}-{int(time.time())}"
    try:
        resolved.rename(trash)
    except OSError as e:
        return {"error": f"could not delete {name}: {e}"}

    DEPLOY_RUNS.pop(name, None)

    # Finishes the project-delete job by removing its database when possible, logging the result, and cleaning the
    # temporary trash folder.
    def _finish():
        """Prepare the finish value or state used by this focused pipeline step."""
        dropped, why = "", ""
        try:
            # From: agents/data/database_records.py
            r = MONGO.reset_project_db(trash, node_bin=NODE_BIN)
            dropped = r.get("db", "") if r.get("ok") else ""
            why = "" if dropped else str(r.get("error", "") or "")
        except Exception as e:                                   # noqa: BLE001
            why = f"{type(e).__name__}: {e}"
        # From: agents/build/tester_common.py
        elog("INFO", f"   🗑 Deleted {name}"
                     + (f" and its database {dropped}" if dropped else
                        f" — its database was left ({why or 'no reason given'})"))
        try:
            shutil.rmtree(trash, ignore_errors=True)
        except Exception as e:                                   # noqa: BLE001
            log.debug(f"emptying {trash.name}: {e}")
        for old in PROD_DIR.glob(".trash-*"):
            if old != trash:
                shutil.rmtree(old, ignore_errors=True)

    threading.Thread(target=_finish, daemon=True).start()
    return {"ok": True, "project": name}


# Returns all projects in production-ready/ with metadata.
def list_projects() -> list:
    """Return all projects in production-ready/ with metadata."""
    projects = []
    if not PROD_DIR.exists():
        return projects
    try:
        folders = sorted(PROD_DIR.iterdir(),
                         key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return projects
    for d in folders:
        try:
            if not d.is_dir() or d.name.startswith("."):
                continue
            pkg = d / "package.json"
            title = d.name
            if pkg.exists():
                try:
                    data = json.loads(pkg.read_text())
                    title = data.get("name", d.name)
                except (OSError, ValueError, TypeError):
                    pass
            projects.append({
                "name": d.name, "title": title,
                "mtime": int(d.stat().st_mtime),
                "file_count": sum(1 for _ in _iter_source(d)),
                "stack": detect_stack(d),
                "unfinished": _unfinished_count(d),
                "deployed": _deploy_marker(d),
            })
        except OSError as e:
            log.debug(f"skipping unreadable project {d}: {e}")
    return projects


# Count planned files absent on disk without walking dependencies.
def _unfinished_count(proj_dir: Path) -> int:
    """Count planned files absent on disk without walking dependencies."""
    try:
        fp = proj_dir / ".agentforge" / "plan.json"
        if not fp.is_file():
            return 0
        plan = json.loads(fp.read_text(encoding="utf-8"))
        planned = [f.get("path", "") for ph in (plan.get("phases") or [])
                   for f in (ph.get("files") or []) if f.get("path")]
        missing = 0
        for rel in planned:
            rel = rel.lstrip("./")
            stem = re.sub(r"\.jsx?$", "", rel)
            if any((proj_dir / c).is_file()
                   for c in (rel, stem + ".js", stem + ".jsx")):
                continue
            missing += 1
        return missing
    except Exception as e:
        log.debug(f"unfinished count for {proj_dir.name}: {e}")
        return 0


FILE_PRIORITY = [
    "app/page.js", "app/page.jsx", "app/layout.js", "lib/mongodb.js",
    "app/globals.css", "next.config.mjs", "jsconfig.json",
    "package.json", "tailwind.config.js", "plan.md", "AUTHENTICATION-DETAILS.md",
]
MAX_LISTED_FILES = 120
MAX_FILE_BYTES = 256_000


# Writes one manually edited file, fenced inside its project.
def save_project_file(proj_name: str, rel: str, content: str) -> dict:
    """Write one manually edited file, fenced inside its project."""
    # From: agents/features/runtime/images/image_service.py
    proj_dir = PROD_DIR / _safe_stem(proj_name, "")
    if not proj_dir.is_dir():
        return {"error": f"no such project: {proj_name}"}

    rel = str(rel or "").replace("\\", "/").strip().lstrip("/")
    if not rel:
        return {"error": "no path given"}
    try:
        target = (proj_dir / rel).resolve()
        # From: agents/features/element_selector.py
        target.relative_to(proj_dir.resolve())
    except (ValueError, OSError):
        return {"error": f"{rel} is outside the project"}

    if target.suffix not in SRC_EXT | {".json", ".md", ".mjs", ".cjs", ".txt"}:
        return {"error": f"{target.suffix or 'that kind of file'} is not editable here"}
    if len(content) > MAX_FILE_BYTES:
        return {"error": f"{len(content):,} characters is past the "
                         f"{MAX_FILE_BYTES:,} limit"}

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="")
    except OSError as e:
        return {"error": f"could not write {rel}: {e}"}

    size = (f"{len(content)/1024:.1f}KB" if len(content) >= 1024
            else f"{len(content)}B")
    # From: agents/build/tester_common.py
    elog("INFO", f"   💾 {rel} saved by hand ({size})")

    efile(rel, size, content)
    return {"ok": True, "path": rel, "size": size}


# Read all source files from a project directory, return as {path: content}.
def get_project_files(proj_name: str) -> dict:
    """Read all source files from a project directory, return as {path: content}."""
    proj_dir = PROD_DIR / proj_name
    if not proj_dir.exists():
        return {}

    # Add one item to this local collection only when it is valid and not already present.
    def add_project_file(files: dict, rel: str, fp: Path):
        """Add one item to this local collection only when it is valid and not already present."""
        try:
            if fp.stat().st_size > MAX_FILE_BYTES:
                return
            content = fp.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return
        sz = (f"{len(content)/1024:.1f}KB" if len(content) >= 1024
              else f"{len(content)}B")
        files[rel] = {"content": content, "size": sz}

    files = {}
    for rel in FILE_PRIORITY:
        fp = proj_dir / rel
        if fp.exists() and rel not in files:
            add_project_file(files, rel, fp)

    for fp in sorted(_iter_source(proj_dir)):
        if len(files) >= MAX_LISTED_FILES:
            break
        rel = str(fp.relative_to(proj_dir)).replace("\\", "/")
        if rel not in files:
            add_project_file(files, rel, fp)

    for sub in ("tests/unit", "tests/e2e"):
        base = proj_dir / sub
        if not base.is_dir():
            continue
        for fp in sorted(base.rglob("*")):
            if len(files) >= MAX_LISTED_FILES:
                break
            if fp.is_file() and fp.suffix in SRC_EXT:
                rel = str(fp.relative_to(proj_dir)).replace("\\", "/")
                if rel not in files:
                    add_project_file(files, rel, fp)
    return files


