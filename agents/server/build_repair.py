# Build failure analysis and repair flow.


def _npm_build_errors(proj_dir: Path, stack: str = "vite"):
    """
    `npm run build` surfaces real compile errors the dev server hides.

    Returns ``(error_text, conclusive)``. The second value matters: a timed-out
    `next build` used to return "" here, which the fix loop then read as "no
    errors" and shipped a broken app. An inconclusive check must never look
    like a clean one.
    """
    timeout = NEXT_BUILD_TIMEOUT if stack == "next" else 120
    env = {**os.environ, "CI": "true", "NEXT_TELEMETRY_DISABLED": "1",
           "NO_COLOR": "1", "FORCE_COLOR": "0"}
    try:
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


def _redact_uri(uri: str) -> str:
    """`mongodb+srv://user:pass@host/db` → `mongodb+srv://user:***@host` —
    safe to show in the UI."""
    if not uri:
        return ""
    shown = re.sub(r"://([^:/@]+):[^@]*@", r"://\1:***@", uri)
    return shown[:60] + ("…" if len(shown) > 60 else "")


def _open_project(proj_name: str):
    """Boot an existing project so the preview iframe has something to show.

    Every exit says so, because the studio holds its preview behind the build
    overlay from the click until this answers — `done` or `error`, and nothing
    else clears it. `wait_for_dev` returning False used to fall out of the
    bottom silently, which left the overlay up over a project that was never
    going to appear, with no way to tell that from one still starting.
    """
    try:
        proj_dir = PROD_DIR / proj_name
        if not proj_dir.exists():
            eerr(f"Project not found: {proj_name}")
            return
        stack = detect_stack(proj_dir)
        elog("INFO", f"📂 Opening {proj_name} ({stack})")
        if stack == "next":
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


def _announce_project_credentials(proj_dir: Path):
    """
    Show an existing project's demo accounts when it is opened.

    Generated apps no longer print these on their own login page, so without
    this there is no way to sign in to an app you built last week.
    """
    try:
        arch = ArchitectAgent(ollama, DEFAULT_BUILD, proj_dir, stack="next")
        arch.load_existing()
        AnalyzerAgent(arch, proj_dir,
                      base_url=f"http://localhost:{DEV_PORT}",
                      callbacks=_analyzer_callbacks())._announce_credentials()
    except Exception as e:
        log.warning(f"could not read demo accounts: {e}")


NOT_A_NAME = {
    "yes", "y", "yeah", "yep", "yup", "ok", "okay", "sure", "fine", "correct",
    "right", "true", "confirm", "confirmed", "no", "n", "nope", "nah", "false",
    "none", "na", "null", "undefined", "app", "application", "webapp",
    "web app", "website", "site", "project", "untitled", "test",
}


def _is_a_name(text: str, limit: int = 60) -> bool:
    """False for a confirmation, a placeholder, or nothing at all."""
    name = " ".join(str(text or "").split())
    return bool(name) and len(name) <= limit and name.lower() not in NOT_A_NAME


def _slug(text: str, fallback: str = "app") -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    s = re.sub(r"-+", "-", s)[:28].strip("-")
    return s or fallback


def _project_slug(*candidates: str, fallback: str = "app") -> str:
    """
    The first candidate that reads like a name, as a folder name.

    The name reaches three places that outlive the build — the directory under
    `production-ready`, the Mongo database `db_name_for` derives from it, and
    the suffixing in `_project_dir_for` — so a word that is not a name is not
    a small mistake. `_slug("yes")` is a perfectly good slug, which is how two
    tire shops came to live in `production-ready/yes` and `yes-2`; falling
    through to the prompt gives a duller name and the right one.
    """
    for text in candidates:
        s = _slug(text, "")
        if s and s.replace("-", " ") not in NOT_A_NAME and s not in NOT_A_NAME:
            return s
    return fallback


def _has_app(d: Path) -> bool:
    """True when a directory already holds someone's application code.

    Only the scaffold's own placeholders don't count — those are what an
    interrupted build leaves behind, and stepping back into one is fine.
    """
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


def bundler_flag(proj_dir: Path) -> list:
    """
    `['--webpack']` on Next 16+, `[]` before it.

    Next 16 made Turbopack the default, and Turbopack words its diagnostics
    differently from the `Failed to compile` / `Module not found` /
    `Can't resolve` strings that `run_build_fix_loop`, `next_stderr` and
    `agents/build/tester.py` all match on. Pinning the bundler pins that vocabulary.

    It must be conditional, not unconditional: **Next 15.5.22 has no
    `--webpack` flag at all** — verified, its `dev --help` lists only `--turbo`
    and `--turbopack` — and `next dev` exits immediately on an unknown
    argument. Passing it to the eleven projects already on disk would kill
    every one of their dev servers.
    """
    return ["--webpack"] if next_major(proj_dir) >= 16 else []


def _project_dir_for(pname: str, stack: str) -> Path:
    """
    Where a new build should write.

    A NEW build never writes into a directory that already holds an app.

    This used to return `base` whenever `detect_stack(base) == stack`, which
    made "a Next.js app is already here" the *condition for reuse* rather than
    for avoidance — the suffixing loop below was unreachable for same-stack
    collisions. Since `_slug(prompt[:40])` keys a project on the first forty
    characters of the prompt, three prompts sharing an SRS preamble landed in
    one folder. Nothing ever empties a directory and `write_file` only
    overwrites, so a POS app, a school app and a car dealership ended up
    superimposed: 66 route URLs on disk against a 31-file plan.

    The build itself never noticed — `arch.files` starts empty. The analyzer
    did, because it reads from disk by design: every leftover
    `fetch('/api/attendance')` became a DEAD_ENDPOINT blocker, and the repair
    pass wrote nine route handlers for two dead applications. Because
    `db_name_for` also follows the directory name, the new app inherited the old
    one's `users` collection and its own seed never ran.

    Editing an existing project is unaffected — that path goes through
    `_open_for_edit`, not here.
    """
    base = PROD_DIR / pname
    if not base.exists() or not any(base.iterdir()):
        return base
    if not _has_app(base) and detect_stack(base) == stack:
        return base
    for i in range(2, 100):
        alt = PROD_DIR / f"{pname}-{i}"
        if not alt.exists() or not any(alt.iterdir()):
            elog("INFO", f"   📁 {pname} already holds a "
                         f"{detect_stack(base)} project — using {alt.name}")
            return alt
    return base


def _agent_callbacks(proj_dir: Path) -> dict:
    """Bridge ArchitectAgent events onto the existing WebSocket protocol."""
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


MONGO.set_callbacks({
    "on_log":    lambda lvl, txt: elog(lvl, txt),
    "on_status": lambda s: emongo(s),
})


def _analyzer_callbacks() -> dict:
    """The analyzer speaks the same WS protocol as everything else."""
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


_DB_ERROR_MARKERS = ("MongoServerSelectionError", "MongoNetworkError",
                     "ECONNREFUSED", "MONGODB_URI", "/api/health",
                     "connect ETIMEDOUT")


def _filter_db_noise(text: str, db_ok: bool) -> str:
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


def _transient_terminal_fault(line: str) -> bool:
    """Next dev navigation noise that is not evidence of an app defect."""
    return bool(_TRANSIENT_TERMINAL_RE.search(str(line or "")))


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


def align_tailwind(arch, proj_dir: Path) -> bool:
    """Make the Tailwind config match the Tailwind that is installed.

    Tailwind 4 moved the PostCSS plugin into `@tailwindcss/postcss` and
    replaced the three `@tailwind` directives with one `@import`. A project
    carrying version 3's shape and version 4's package does not compile, and
    the error — "trying to use `tailwindcss` directly as a PostCSS plugin" —
    is not something the model can fix by rewriting a page, so every build
    round spends itself and the app never starts. Measured on a gym build:
    six rounds, no green build, the end-to-end stage skipped for it.

    The pin in package.json is what stops the versions drifting apart; this
    is the second line, for when something installs Tailwind 4 anyway. It
    reads the version actually in `node_modules` and writes the config that
    version needs. Deterministic, a few milliseconds, and it runs before
    every build.
    """
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
            elog("WARN", f"   ⚠ could not install @tailwindcss/postcss: {e}")

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


def _toolchain_break(proj_dir: Path, errors: str = "") -> str:
    """Why the INSTALL is broken, or "" when the app itself is at fault.

    Two independent witnesses, and either is enough:

    the disk -- a package whose declared entry files are missing is broken
    however plausible its `package.json` looks; and

    the error text -- a relative or node_modules-internal `Cannot find module`
    was raised by a package about its own contents, and no file the builder
    writes appears anywhere in that sentence.
    """
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


def _repair_toolchain(proj_dir: Path, why: str) -> bool:
    """Reinstall the broken packages. Returns True when something was done."""
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
        elog("INFO", "   🗑 removed the half-installed "
                     + ", ".join(dropped) + " so npm reinstalls it")
    elif not nm.is_dir():
        pass
    else:
        elog("INFO", "   📦 reinstalling to reconcile the error with the disk")
        try:
            (proj_dir / "node_modules" / ".package-lock.json").unlink()
        except Exception:
            pass
    ok = ensure_node_deps(proj_dir)
    elog("INFO" if ok else "WARN",
         "   ✅ the toolchain is installed again" if ok else
         "   ⚠ the reinstall did not succeed")
    return ok


def run_build_fix_loop(arch, proj_dir: Path, db_ok: bool,
                       max_rounds: int = MAX_BUILD_FIX) -> bool:
    """
    Compile the app and let the model repair whatever `next build` rejects.

    This runs BEFORE the dev server starts, which matters twice over: `next
    build` and `next dev` share `.next/`, so building first avoids clobbering a
    running server; and a compile error is a far cheaper, far more precise
    signal than waiting for Playwright to notice a blank page.

    The model fixes with its own tools — `write_file` for code, `run_command`
    for a missing package — so `Module not found: Can't resolve 'bcryptjs'` is
    something it can actually resolve instead of merely rewriting around.

    Returns True when the build is clean.
    """
    align_tailwind(arch, proj_dir)
    for rnd in range(1, max_rounds + 1):
        estep("build", "active")
        eprog(f"Compiling (round {rnd})…", min(84 + rnd * 2, 92))
        ephase({"phase": -3, "title": f"Build check {rnd}/{max_rounds}",
                "status": "active"})
        elog("INFO", f"🔨 npm run build (round {rnd}/{max_rounds})…")

        try:
            arch.sync_dependencies()
            missing_deps = arch.unresolved_packages()
            if missing_deps:
                arch.install_packages(missing_deps)
            ensure_node_deps(proj_dir)
        except Exception as e:
            elog("WARN", f"   ⚠ dependency reconciliation could not finish: {e}")

        errors, conclusive = _npm_build_errors(proj_dir, "next")

        if not conclusive:
            elog("WARN", "   ⚠ Build check timed out — could not verify")
            ephase({"phase": -3, "title": f"Build check {rnd}/{max_rounds}",
                    "status": "done"})
            return False
        if not errors:
            elog("INFO", "   ✅ Build clean")
            estep("build", "done")
            ephase({"phase": -3, "title": "Build clean", "status": "done"})
            return True

        lines = [ln.rstrip() for ln in errors.strip().splitlines() if ln.strip()]
        first = lines[0][:120] if lines else "?"
        elog("WARN", f"   ❌ Build failed: {first}")

        for ln in lines[1:9]:
            elog("WARN", f"      {ln[:160]}")
        emit({"type": "test_fixing", "attempt": rnd,
              "errors": errors.splitlines()[:5]})

        broken = _toolchain_break(proj_dir, errors)
        if broken and _repair_toolchain(proj_dir, broken):
            errors, conclusive = _npm_build_errors(proj_dir, "next")
            if conclusive and not errors:
                elog("INFO", "   ✅ Build clean once the toolchain was repaired "
                             "— no application file was touched")
                estep("build", "done")
                ephase({"phase": -3, "title": "Build clean", "status": "done"})
                return True
            lines = [ln.rstrip() for ln in (errors or "").strip().splitlines()
                     if ln.strip()]
            elog("WARN", "   ❌ Still failing after the reinstall: "
                         + (lines[0][:120] if lines else "?"))
            if not conclusive:
                ephase({"phase": -3, "title": f"Build check {rnd}/{max_rounds}",
                        "status": "done"})
                return False

        wanted = arch.packages_named_in(errors)
        if wanted and arch.install_packages(wanted):
            errors, conclusive = _npm_build_errors(proj_dir, "next")
            if conclusive and not errors:
                elog("INFO", "   ✅ Build clean once the packages were in")
                estep("build", "done")
                ephase({"phase": -3, "title": "Build clean", "status": "done"})
                return True
            if not conclusive:
                elog("WARN", "   ⚠ Build check timed out — could not verify")
                ephase({"phase": -3, "title": f"Build check {rnd}/{max_rounds}",
                        "status": "done"})
                return False
            lines = [ln.rstrip() for ln in errors.strip().splitlines()
                     if ln.strip()]
            elog("WARN", f"   ❌ Still failing: "
                         f"{(lines[0][:120] if lines else '?')}")

        if rnd == max_rounds:
            elog("WARN", f"   ⚠ Still failing after {max_rounds} rounds — "
                         f"serving anyway so you can see it")
            ephase({"phase": -3, "title": f"Build check {rnd}/{max_rounds}",
                    "status": "done"})
            return False

        guidance = nextdocs.guidance_for(errors)
        if guidance:
            elog("INFO", f"   📖 {', '.join(nextdocs.slugs_in(errors)[:2])} "
                         f"— attached Next.js's own fix guide")

        arch.update(textwrap.dedent(f"""\
            `npm run build` failed. Fix every error below.

            Any package the compiler named has already been installed for
            you, and anything npm could not supply does not exist — so an
            unresolved import that is still here is a name to correct, not one
            to install. Rewrite the affected file completely.

            ```
            {_filter_db_noise(errors, db_ok)[:4000]}
            ```
            """) + _failing_sources(arch, errors)
            + ("\n" + guidance if guidance else ""))

        ensure_node_deps(proj_dir)
        ephase({"phase": -3, "title": f"Build check {rnd}/{max_rounds}",
                "status": "done"})

    return False


_ERR_FILE_RE = re.compile(r"^\s*\.?/?((?:app|components|lib)/[\w./\[\]@-]+"
                          r"\.(?:jsx?|mjs))\s*$", re.M)
FAIL_SRC_BUDGET = 26_000


def _failing_sources(arch, errors: str) -> str:
    """The current source of every file the compiler complained about.

    The repair turn was the error text and nothing else. `arch.update` puts it
    into the running conversation, where the model sees a fixed snapshot that
    on a forty-file project regularly does not contain the file the error
    names — so it was being asked to rewrite a file it could not read, and
    guessed at the rest of it. That is why a build takes three rounds to go
    green when the error was specific from the first one.

    Next prints the path above each error, so the list is free. Nothing is
    inferred and nothing is fetched: these are files the compiler itself
    named, read from what is already in memory.
    """
    seen, blocks, used = set(), [], 0
    for rel in _ERR_FILE_RE.findall(errors or ""):
        rel = rel.replace("\\", "/")
        if rel in seen:
            continue
        seen.add(rel)
        body = (getattr(arch, "files", None) or {}).get(rel)
        if not body:
            continue
        block = f"--- {rel} ---\n{body[:9000]}"
        if used + len(block) > FAIL_SRC_BUDGET and blocks:
            break
        blocks.append(block)
        used += len(block)
    if not blocks:
        return ""
    return ("\n\nThis is what those files contain right now. Rewrite each one "
            "COMPLETE, keeping everything about it that already works — the "
            "error is the only thing to change.\n\n```jsx\n"
            + "\n\n".join(blocks) + "\n```\n")


# Four rounds are always attempted.
