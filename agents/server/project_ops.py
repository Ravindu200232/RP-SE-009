# Project flow: validate ownership -> read or change -> notify the Studio.
SRC_ROOTS = ("app", "components", "lib", "src", "pages")
SKIP_DIRS = {"node_modules", ".next", ".git", "dist", "out", ".vite", ".turbo",
             ".agentforge"}
SRC_EXT = {".js", ".jsx", ".css"}


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


def _owned_dir(root: Path, raw: str, label: str,
               missing_label: str) -> tuple:
    """Resolve one HTTP-supplied directory name inside its owned root."""
    name = str(raw or "").strip().replace("\\", "/")
    if not name or "/" in name or name in (".", "..") or name.startswith("."):
        return name, None, f"{raw!r} is not a {label}"
    try:
        resolved = (root / name).resolve()
        resolved.relative_to(root.resolve())
    except (ValueError, OSError):
        return name, None, f"{name} is outside {root.name}"
    if not resolved.is_dir():
        return name, None, f"no such {missing_label}: {name}"
    return name, resolved, ""


def _deploy_marker(project_dir: Path) -> dict | None:
    """Return cheap, disk-only deployment history for project listings."""
    agentforge = project_dir / ".agentforge"
    if (agentforge / "deploy-deleted.json").is_file():
        return {"state": "deleted", "target": ""}
    link = agentforge / "deploy" / "link.json"
    if not link.is_file():
        return None
    try:
        target = str(json.loads(link.read_text(encoding="utf-8")).get("target") or "")
    except Exception:
        target = ""
    return {"state": "deployed", "target": target}


def discard_srs(srs_id: str) -> dict:
    """Remove one staged specification without escaping its owned root."""
    sid, resolved, error = _owned_dir(
        PROD_DIR / ".srs", srs_id, "specification id", "specification")
    if error:
        if "outside" in error:
            error = f"{sid} is outside the specification store"
        return {"error": error}

    shutil.rmtree(resolved, ignore_errors=True)
    if resolved.exists():
        return {"error": f"{sid} could not be removed"}
    elog("INFO", f"   🗑 discarded the specification {sid}")
    return {"ok": True, "srs_id": sid}


def delete_project(proj_name: str) -> dict:
    """Remove a fenced project, then its generated database, in background."""
    name, resolved, error = _owned_dir(
        PROD_DIR, proj_name, "project name", "project")
    if error:
        return {"error": error}

    if active_vite.get("dir") == str(resolved):
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

    def _finish():
        dropped, why = "", ""
        try:
            r = MONGO.reset_project_db(trash, node_bin=NODE_BIN)
            dropped = r.get("db", "") if r.get("ok") else ""
            why = "" if dropped else str(r.get("error", "") or "")
        except Exception as e:                                   # noqa: BLE001
            why = f"{type(e).__name__}: {e}"
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


def list_projects() -> list:
    """Return all projects in production-ready/ with metadata."""
    projects = []
    if not PROD_DIR.exists():
        return projects
    for d in sorted(PROD_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):

        if not d.is_dir() or d.name.startswith("."):
            continue
        pkg = d / "package.json"
        title = d.name
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text())
                title = data.get("name", d.name)
            except: pass
        projects.append({
            "name": d.name,
            "title": title,
            "mtime": int(d.stat().st_mtime),
            "file_count": sum(1 for _ in _iter_source(d)),
            "stack": detect_stack(d),

            "unfinished": _unfinished_count(d),

            "deployed": _deploy_marker(d),
        })
    return projects


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
    "src/App.jsx", "src/main.jsx", "src/index.css", "index.html",
    "vite.config.js", "package.json", "tailwind.config.js", "plan.md",
]
MAX_LISTED_FILES = 120
MAX_FILE_BYTES = 256_000


def save_project_file(proj_name: str, rel: str, content: str) -> dict:
    """Write one manually edited file, fenced inside its project."""
    proj_dir = PROD_DIR / _safe_stem(proj_name, "")
    if not proj_dir.is_dir():
        return {"error": f"no such project: {proj_name}"}

    rel = str(rel or "").replace("\\", "/").strip().lstrip("/")
    if not rel:
        return {"error": "no path given"}
    try:
        target = (proj_dir / rel).resolve()
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
    elog("INFO", f"   💾 {rel} saved by hand ({size})")

    efile(rel, size, content)
    return {"ok": True, "path": rel, "size": size}


def get_project_files(proj_name: str) -> dict:
    """Read all source files from a project directory, return as {path: content}."""
    proj_dir = PROD_DIR / proj_name
    if not proj_dir.exists():
        return {}

    def add(files: dict, rel: str, fp: Path):
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
            add(files, rel, fp)

    for fp in sorted(_iter_source(proj_dir)):
        if len(files) >= MAX_LISTED_FILES:
            break
        rel = str(fp.relative_to(proj_dir)).replace("\\", "/")
        if rel not in files:
            add(files, rel, fp)

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
                    add(files, rel, fp)
    return files


def _decide_targets(update_prompt: str, components: list, codebase_ctx: str,
                    build_model: str) -> list:
    """Ask the LLM for up to three existing or new component names."""
    import requests as req

    comp_list = ", ".join(components) if components else "(none)"
    prompt = (
        f"A React project has these components: {comp_list}\n\n"
        f"The user wants to: {update_prompt}\n\n"
        f"CODEBASE SUMMARY:\n{codebase_ctx[:1200]}\n\n"
        "Which component(s) must be MODIFIED or CREATED to fulfil the request?\n"
        "Reply with ONLY a JSON array of component names, e.g.: [\"Hero\", \"Navbar\"]\n"
        "Rules:\n"
        "- Use existing names exactly as listed above when modifying\n"
        "- Use a new PascalCase name when a new component is needed\n"
        "- Maximum 3 components per update\n"
        "- Reply with ONLY the JSON array. No explanation."
    )
    try:
        r = req.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model":    build_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream":   False,
                "options":  {"temperature": 0.0, "num_predict": 80},
            },
            timeout=45,
        )
        r.raise_for_status()
        raw = r.json()["message"]["content"].strip()

        m = re.search(r'\[([^\]]+)\]', raw)
        if m:
            names = json.loads(f"[{m.group(1)}]")
            return [n.strip() for n in names if isinstance(n, str) and n.strip()]
    except Exception as e:
        log.warning(f"   _decide_targets failed: {e}")
    return []


def _build_update_prompt(component_name: str, existing_code: str,
                         update_request: str, codebase_ctx: str,
                         is_new: bool) -> str:
    """Build the focused prompt passed through the normal generation path."""
    import textwrap as tw
    if is_new:
        return tw.dedent(f"""\
            Add a NEW component called '{component_name}' to an existing React project.

            USER REQUEST: {update_request}

            EXISTING CODEBASE (for context — imports, styles, data patterns):
            {codebase_ctx[:1500]}

            Requirements:
            - Export default function {component_name}()
            - Match the visual style and color scheme of the existing site
            - framer-motion animations, Tailwind CSS, react-icons/fi
            - Real content matching the request — no placeholder text
            - Outermost div MUST have an explicit dark background class
            - Output ONLY the complete JSX starting with imports
            """)
    else:
        return tw.dedent(f"""\
            Modify the existing '{component_name}' React component as requested.

            USER REQUEST: {update_request}

            EXISTING COMPONENT CODE (modify THIS — keep everything not mentioned in the request):
            {existing_code}

            OTHER FILES FOR CONTEXT (imports, shared styles — do NOT modify these):
            {codebase_ctx[:1200]}

            Requirements:
            - Apply ONLY the changes the user requested — preserve all other functionality
            - Keep the same visual design for parts not mentioned in the request
            - Export default function {component_name}()
            - Follow all JSX rules: hoist regex, hoist divisions, no split components
            - Output ONLY the COMPLETE updated component JSX starting with imports
            """)


def run_update_pipeline(proj_name: str, update_prompt: str, build_model: str):
    """Update selected components, then run the normal test/fix loop."""
    set_stream_callback(on_token)
    set_tester_emit(emit)

    proj_dir = PROD_DIR / proj_name
    if not proj_dir.exists():
        eerr(f"Project not found: {proj_name}"); return

    try:
        elog("INFO", "━" * 40)
        elog("INFO", f"✏️  Updating: {proj_name}")
        elog("INFO", f"📝 Request: {update_prompt[:80]}")
        elog("INFO", f"🏗️  Model: {build_model}")
        elog("INFO", "━" * 40)

        estep("refine", "active")
        eprog("Loading project…", 5)

        builder = UIBuilder(OLLAMA_URL, build_model, proj_dir)

        file_data = get_project_files(proj_name)
        for rel, info in file_data.items():
            builder.built_files[rel] = info["content"]

            efile(rel, info["size"], info["content"])

        comp_dir   = proj_dir / "src" / "components"
        components = sorted(f.stem for f in comp_dir.glob("*.jsx")) if comp_dir.exists() else []
        elog("INFO", f"   📂 Loaded {len(file_data)} files | Components: {components}")

        estep("refine", "done")
        eprog("Analysing request…", 15)

        if not ensure_model(build_model):
            eerr(f"Cannot load build model: {build_model}"); return

        codebase_ctx = builder._build_codebase_context()

        estep("build", "active")
        eprog("Deciding targets…", 22)

        targets = _decide_targets(update_prompt, components, codebase_ctx, build_model)
        targets = [t for t in targets if re.match(r"^[A-Z][A-Za-z0-9_]*$", t)]

        if not targets:

            for comp in components:
                if comp.lower() in update_prompt.lower():
                    targets = [comp]
                    break
            if not targets and components:

                targets = [max(
                    components,
                    key=lambda c: len(builder.built_files.get(f"src/components/{c}.jsx", ""))
                )]
                elog("WARN", f"   Could not infer target — defaulting to largest component: {targets}")
            elif not targets:
                eerr("No components found in project"); return

        elog("INFO", f"   🎯 Targets: {targets}")

        updated_count = 0
        pct_per_comp  = max(1, 30 // len(targets))

        for i, comp_name in enumerate(targets):
            fpath    = f"src/components/{comp_name}.jsx"
            is_new   = comp_name not in components
            existing = builder.built_files.get(fpath, "")

            if is_new:
                elog("INFO", f"   ➕ Creating new component: {comp_name}")
            else:
                elog("INFO", f"   ✏️  Updating: {fpath}")

            eprog(f"Generating {comp_name}…", 25 + i * pct_per_comp)

            prompt = _build_update_prompt(
                comp_name, existing, update_prompt, codebase_ctx, is_new
            )

            new_code = builder._gen(comp_name, prompt)

            if not new_code:
                elog("WARN", f"   LLM returned nothing for {comp_name} — skipping")
                continue

            builder._write_one(fpath, new_code)
            updated_count += 1
            elog("INFO", f"   ✓ {fpath} written")

            if is_new:
                _inject_component_into_app(builder, proj_dir, comp_name)

        if updated_count == 0:
            eerr("No components were updated — LLM may have failed to generate valid JSX")
            return

        stop_model(build_model)

        estep("build", "done")
        eprog("Components updated", 58)
        elog("INFO", f"   ✅ {updated_count}/{len(targets)} component(s) updated")

        estep("serve", "active")
        eprog("Restarting Vite…", 65)
        elog("INFO", "🌐 Restarting Vite…")
        if not ensure_node_deps(proj_dir):
            eerr("Dependency install failed")
            return
        start_vite(proj_dir)
        wait_for_vite(35)

        estep("test", "active")
        eprog("Testing…", 75)
        elog("INFO", "🧪 Testing updated build…")
        emit({"type": "test_start"})

        tester = TesterAgent(proj_dir, DEV_PORT)
        npm_errors = ""

        for attempt in range(1, MAX_FIX + 2):
            elog("INFO", f"   🔬 Test run #{attempt}")
            emit({"type": "test_run", "attempt": attempt})

            errors = tester.test()

            if not errors:
                elog("INFO", "   🎉 All tests passed!")
                estep("test", "done")
                break

            if attempt > MAX_FIX:
                elog("WARN", f"   ⚠ Max fix attempts reached — applying safe fallbacks")
                from agents.build.builder_common import _safe_component
                for fpath_s, src in list(builder.built_files.items()):
                    if not (fpath_s.startswith("src/components/") and fpath_s.endswith(".jsx")):
                        continue
                    comp_name_s = fpath_s.split("/")[-1].replace(".jsx", "")
                    if len(src.strip()) < 400 or npm_errors.strip():
                        safe = _safe_component(comp_name_s)
                        (proj_dir / fpath_s).write_text(safe, encoding="utf-8")
                        builder.built_files[fpath_s] = safe
                        elog("WARN", f"   🛟 Safe fallback → {fpath_s}")
                estep("test", "done")
                break

            npm_errors = builder._npm_build_errors()
            vs_errors  = vite_stderr()
            all_errors = "\n".join(errors) + "\n" + npm_errors + "\n" + vs_errors

            elog("INFO", f"   📋 npm build:\n{npm_errors[:250] or '  (none)'}")
            emit({"type": "test_fixing", "attempt": attempt, "errors": errors[:5]})
            elog("INFO", f"   🔧 Fixing attempt {attempt}/{MAX_FIX}…")

            if not ensure_model(build_model):
                elog("WARN", "   Cannot reload build model — skipping fix")
                break

            builder.fix_with_errors(all_errors)
            stop_model(build_model)

            elog("INFO", "   🔄 Restarting Vite after fix…")
            if not ensure_node_deps(proj_dir):
                eerr("Dependency install failed")
                return
            start_vite(proj_dir)
            wait_for_vite(35)

        url = f"http://localhost:{DEV_PORT}"
        estep("serve", "done")
        eprog("Done!", 100)
        elog("INFO", f"🎉 Updated → {url}")
        edone(url, proj_name)

    except Exception as e:
        eerr(f"Update error: {e}")
        log.exception("Update pipeline error")
    finally:
        set_stream_callback(None)


def _inject_component_into_app(builder, proj_dir: Path, comp_name: str):
    """Render a newly generated component from a Vite App.jsx."""
    app_path = proj_dir / "src" / "App.jsx"
    if not app_path.exists():
        return

    app_code = app_path.read_text(encoding="utf-8")

    if f"import {comp_name}" in app_code:
        return

    try:

        last_import = max(
            (i for i, l in enumerate(app_code.splitlines()) if l.strip().startswith("import")),
            default=0
        )
        lines = app_code.splitlines()
        lines.insert(last_import + 1, f"import {comp_name} from './components/{comp_name}'")

        new_app = "\n".join(lines)

        insert_tag = f"      <{comp_name} />\n"
        last_div   = new_app.rfind("</div>")
        if last_div != -1:
            new_app = new_app[:last_div] + insert_tag + new_app[last_div:]

        app_path.write_text(new_app, encoding="utf-8")
        builder.built_files["src/App.jsx"] = new_app
        sz = f"{len(new_app)//1024:.1f}KB" if len(new_app) >= 1024 else f"{len(new_app)}B"
        efile("src/App.jsx", sz, new_app)
        log.info(f"   ✓ Injected {comp_name} into App.jsx")
    except Exception as e:
        log.warning(f"   _inject_component_into_app failed: {e}")


async def ws_handler(websocket, path=None):
    clients.add(websocket)
    log.info(f"WS connected ({len(clients)})")
    try:
        await websocket.send(json.dumps({
            "type": "log", "level": "INFO",
            "text": "✅ AgentForge connected — enter a prompt and click Build"
        }))
        async for raw in websocket:
            try:
                msg = json.loads(raw)
                job = _message_job(msg)
                if job:
                    threading.Thread(
                        target=job[0], args=job[1], daemon=True).start()
            except json.JSONDecodeError:
                pass
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clients.discard(websocket)
        log.info(f"WS disconnected ({len(clients)})")


def _message_job(msg: dict):
    """Translate one WebSocket action into its unchanged worker contract."""
    kind = msg.get("type")
    prompt = str(msg.get("prompt") or "").strip()
    project = str(msg.get("project") or "").strip()

    if kind == "build" and prompt:
        return run_pipeline, (
            prompt, msg.get("refine_model", DEFAULT_REFINE),
            msg.get("build_model", DEFAULT_BUILD))
    if kind == "update" and project and prompt:
        return run_update_pipeline, (
            project, prompt, msg.get("build_model", DEFAULT_BUILD))
    known = {
        "agent_build", "agent_resume", "chat", "agent_update",
        "pencil_edit", "element_edit", "image_edit", "feature",
    }
    if kind not in known:
        return None
    model = msg.get("model") or default_agent_model()
    qa_model = str(msg.get("qa_model") or "").strip()
    route = str(msg.get("route") or "").strip()
    think = _think_flag(msg)

    if kind == "agent_build" and prompt:
        return run_agent_pipeline, (
            prompt, model, think, qa_model, "",
            str(msg.get("logo") or "").strip(),
            str(msg.get("srs_id") or "").strip())
    if kind == "agent_resume" and project:
        return run_agent_pipeline, (
            "", model, think, qa_model, project)
    if kind in ("chat", "agent_update") and project and prompt:
        return run_chat, (
            project, prompt, model, route, think, qa_model,
            _browser_console(msg))
    if kind == "pencil_edit" and project and prompt:
        return run_pencil_edit, (project, prompt, msg, model, think)
    if kind == "element_edit" and project and prompt:
        return run_element_edit, (
            project, prompt, msg.get("element") or {}, model, think,
            _browser_console(msg))
    if kind == "image_edit" and project and prompt:
        return run_image_edit, (
            project, prompt, msg.get("element") or {}, model, think)
    if kind == "feature" and project and prompt:
        return run_feature, (
            project, prompt, model, think, qa_model, route,
            _browser_console(msg))
    return None
