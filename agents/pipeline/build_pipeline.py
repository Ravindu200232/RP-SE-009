# Main flow: prepare -> plan -> build -> verify -> report -> serve.
# Checks whether MongoDB is ready. If it is not ready, it tries to start MongoDB once and checks again.
def database_ready() -> bool:
    """Prove MongoDB answers at the moment it is needed, and retry once."""
    for attempt in (1, 2):
        # From: agents/data/database_server.py
        if MONGO.reachable():
            MONGO.available = True
            return True
        if attempt == 1:
            try:
                # From: agents/data/database_server.py
                MONGO.ensure_running()
            except Exception as exc:                            # noqa: BLE001
                log.debug(f"database retry: {exc}")
    MONGO.available = False
    why = (MONGO.reason or "nothing is answering on 127.0.0.1:27017").strip()
    # From: agents/build/tester_common.py
    elog("WARN", f"   ⚠ No database — {why}")
    # From: agents/build/tester_common.py
    elog("WARN", "      Every page that reads data will error. Start MongoDB, "
                 "or set a MONGODB_URI in Settings, then build again.")
    return False

# Runs the seed API, verifies every planned demo login, and returns an error message if seeding or login
# verification fails.
def seed_project(plan: dict) -> str:
    """Run seed; return concrete endpoint error evidence, or an empty string."""
    try:
        body = requests.get(f"http://127.0.0.1:{DEV_PORT}/api/seed",
                            timeout=180).json()
    except Exception as exc:                                    # noqa: BLE001
        error = f"seed endpoint request failed: {str(exc)[:300]}"
        # From: agents/build/tester_common.py
        elog("WARN", f"   ⚠ Seeding did not run — {str(exc)[:160]}")
        return error
    if not body.get("ok"):
        error = f"GET /api/seed returned failure: {str(body.get('error'))[:600]}"
        # From: agents/build/tester_common.py
        elog("WARN", f"   ⚠ Seeding failed — {str(body.get('error'))[:200]}")
        return error
    for account in (plan or {}).get("demo_accounts") or []:
        session = requests.Session()
        try:
            login = session.post(f"http://localhost:{DEV_PORT}/api/auth/sign-in/email",
                                 json={"email": account.get("email"), "password": account.get("password")}, timeout=20)
            user = session.get(f"http://localhost:{DEV_PORT}/api/auth/get-session", timeout=15).json().get("user") or {}
        except Exception as exc:
            return f"seeded demo account could not be verified: {account.get('email')}: {str(exc)[:240]}"
        expected_role = str(account.get("role") or "").strip().lower()
        if login.status_code >= 400 or str(user.get("email") or "").lower() != str(account.get("email") or "").lower() or (expected_role and str(user.get("role") or "").strip().lower() != expected_role):
            return f"seeded role account is unusable: {account.get('email')} (HTTP {login.status_code}, role {user.get('role') or 'missing'})"
    # From: agents/build/tester_common.py
    elog("INFO", "   🌱 Seeded and verified planned data" if body.get("ran")
                 else "   🌱 Nothing to seed for this app")
    for account in (plan or {}).get("demo_accounts") or []:
        # From: agents/build/tester_common.py
        elog("INFO", f"   🔑 {account.get('email')} / {account.get('password')}"
                     + (f"  ({account['role']})" if account.get("role") else ""))
    return ""


# Writes the generated role, email, password, and landing-route details into the project authentication details
# file.
def write_auth_details(proj_dir, plan: dict, *, verified: bool = False, arch=None) -> None:
    """Keep planned/verified role credentials visible beside plan.md.

    Write once as soon as generation finishes so Studio shows the credentials,
    then overwrite it as verified after the seed/login gate succeeds.
    """
    accounts = [a for a in (plan or {}).get("demo_accounts") or []
                if isinstance(a, dict) and a.get("email")]
    if not accounts:
        return
    name = str(((plan or {}).get("project") or {}).get("title")
               or (plan or {}).get("app_name") or proj_dir.name)
    homes = (plan or {}).get("role_homes") or {}
    rows = ["| Role | Email | Password | Lands on |",
            "| --- | --- | --- | --- |"]
    for account in accounts:
        role = str(account.get("role") or "-")
        rows.append(f"| {role} | `{account.get('email')}` | "
                    f"`{account.get('password') or '-'}` | "
                    f"{homes.get(role) or '/'} |")
    body = [
        f"# {name} — generated auth details",
        "",
        ("These accounts were created by the database seeder and verified by a real sign-in."
         if verified else "These are the planned role credentials the database seeder will create."),
        "Use them at the app's sign-in route.",
        "",
        *rows,
        "",
        "Re-running the seed does not change them: seeding is idempotent and",
        "identifies each account by its email address.",
        "",
    ]
    try:
        text = chr(10).join(body)
        (proj_dir / "GENERATED-AUTH-DETAILS.md").unlink(missing_ok=True)
        # From: agents/planner/builder/file_writer.py
        (arch.write_file("AUTHENTICATION-DETAILS.md", text) if arch else
         (proj_dir / "AUTHENTICATION-DETAILS.md").write_text(text, encoding="utf-8"))
        # From: agents/build/tester_common.py
        elog("INFO", f"   🔑 sign-ins written to AUTHENTICATION-DETAILS.md "
                     f"({len(accounts)} role account(s))")
    except OSError as exc:
        # From: agents/build/tester_common.py
        elog("WARN", f"   ⚠ could not write the auth details file: {exc}")

# Runs the complete app-building flow from the user request through planning, generation, verification, repair,
# and preview.
def run_agent_pipeline(prompt: str, model: str, think: bool = None,
                       qa_model: str = "", resume_project: str = "",
                       logo: str = "", srs_id: str = ""):
    """Build and verify one app from a request or an approved SRS."""
    # Stage 1: restore or create the owned project workspace.
    # From: agents/core/runtime/cancellation.py
    cancel.begin()
    # From: agents/pipeline/bugs/bug_verification.py
    warn_if_agents_stale()
    set_tester_emit(emit)
    try:
        # From: agents/core/llm/llm_settings.py
        cloud = is_cloud_model(model)
        # From: agents/build/tester_common.py
        elog("INFO", "━" * 40)
        # From: agents/build/tester_common.py
        elog("INFO", f"🤖 Agent mode — {prompt[:80]}")
        # From: agents/build/tester_common.py
        # From: agents/core/llm/llm_settings.py
        elog("INFO", f"{'☁️  Cloud' if cloud else '💻 Local'}: {model}   "
                     f"ctx {max_context(model):,}"
                     + ("   🤔 thinking on" if think else
                        "   ⚡ thinking off" if think is False else ""))
        # From: agents/build/tester_common.py
        elog("INFO", "━" * 40)

        if resume_project:
            proj_dir = PROD_DIR / resume_project
            pname = proj_dir.name
            if not (proj_dir / ".agentforge" / "plan.json").is_file():
                # From: agents/pipeline/bugs/bug_verification.py
                intent = load_run_intent(proj_dir)
                if not intent.get("prompt"):
                    eerr(f"{resume_project} has nothing to resume from")
                    return
                # From: agents/build/tester_common.py
                elog("INFO", "   ↩ no plan yet — restarting from the original request")
                prompt = prompt or intent.get("prompt", "")
                model = model or intent.get("model", "")
                qa_model = qa_model or intent.get("qa_model", "")
                srs_id = srs_id or intent.get("srs_id", "")
                logo = logo or intent.get("logo", "")
                if think is None:
                    think = intent.get("think")
                resume_project = ""
        else:
            # From: agents/pipeline/build/project_preview.py
            proj_dir = _project_dir_for(
                _project_slug(_srs_app_name(srs_id), prompt[:40]), "next")
            pname = proj_dir.name

        proj_dir.mkdir(parents=True, exist_ok=True)
        # From: agents/pipeline/bugs/bug_verification.py
        save_run_intent(proj_dir, prompt=prompt, model=model, think=think,
                        qa_model=qa_model, srs_id=srs_id, logo=logo)
        # From: agents/build/tester_common.py
        elog("INFO", f"   📁 {proj_dir}")
        # From here a cancel has something to undo.
        # From: agents/core/runtime/cancellation.py
        cancel.note(project=pname, srs_id=srs_id)
        eproject(pname)

        eprog("Checking model…", 2)
        if not ensure_model(model):
            eerr(f"Cannot load model: {model}")
            return

        logo_ready = False
        if logo:
            try:
                src = Path(logo)
                if src.is_file():
                    dest = proj_dir / "public" / "logo.png"
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(src.read_bytes())
                    logo_ready = True
                    # From: agents/build/tester_common.py
                    elog("INFO", "   🖼 Using the logo you approved")
                else:
                    # From: agents/build/tester_common.py
                    elog("WARN", f"   ⚠ The approved logo is gone: {logo}")
            except OSError as e:
                # From: agents/build/tester_common.py
                elog("WARN", f"   ⚠ Could not copy the logo: {e}")

        if srs_id:
            adopt_srs(srs_id, proj_dir)

        # Stage 2: plan and generate while database startup runs beside it.
        mongo_thread = threading.Thread(target=MONGO.ensure_running, daemon=True)
        # From: agents/data/database_server.py
        mongo_thread.start()

        estep("plan", "active")

        # From: agents/pipeline/build/project_preview.py
        cb = _agent_callbacks(proj_dir)

        drawing = {"thread": None}

        # Draw the planned pictures beside code generation, not after it.
        def _draw_when_planned(event):
            """Draw the planned pictures beside code generation, not after it."""
            ephase(event)
            if drawing["thread"] or event.get("status") != "done":
                return
            if not ((event.get("plan") or {}).get("images")):
                return
            drawing["thread"] = threading.Thread(
                target=run_image_stage, args=(arch, proj_dir), daemon=True)
            drawing["thread"].start()

        cb["on_phase"] = _draw_when_planned

        qa_model = qa_model or model
        # From: agents/core/llm/llm_settings.py
        qa = QASession(proj_dir, callbacks=_qa_callbacks(), model=qa_model,
                       enabled=is_cloud_model(qa_model))
        if qa.enabled and qa_model != model:
            # From: agents/build/tester_common.py
            elog("INFO", f"   🧪 QA runs on {qa_model}")
        if not qa.enabled:

            # From: agents/build/tester_common.py
            elog("WARN", "   ⚠ QA is cloud-only — no unit tests, no "
                         "end-to-end flow, and no signed-in page sweep for "
                         f"{qa_model}. Pick a cloud QA model to get them.")
        cb["on_phase"] = qa.on_phase(cb["on_phase"])
        cb["on_file_written"] = qa.on_file_written(cb["on_file_written"])
        # From: agents/data/database_helpers.py
        # From: agents/data/database_records.py
        # From: agents/planner/builder/app_builder.py
        arch = ArchitectAgent(ollama, model, proj_dir, cb,
                              stack="next",
                              mongo_uri=MONGO.uri_for(pname),
                              db_name=db_name_for(pname),

                              dev_port=DEV_PORT,
                              think=think)
        qa.bind(arch)

        if resume_project:

            # From: agents/planner/builder/project_memory.py
            arch.load_existing()
            # From: agents/planner/builder/file_writer.py
            left = len(arch.unfinished())
            # From: agents/build/tester_common.py
            elog("INFO", f"⏭️  Resuming {pname} — {left} file(s) still missing")
            # From: agents/planner/builder/project_memory.py
            ok = arch.resume(brief=_srs_brief(proj_dir, model) if srs_id else "")
        else:

            requirement_brief = prompt
            if srs_id:
                requirement_brief = (_srs_name_line(proj_dir) + requirement_brief
                                     + _srs_brief(proj_dir, model))

            brief = requirement_brief
            if logo_ready:
                brief += ("\n\nThe app's logo already exists at `/logo.png` "
                          "(public/logo.png). Use it in the header and the "
                          "footer with a plain <img> and the app's name as its "
                          "alt text. Do not generate another logo, and do not "
                          "render the app name as text where the logo belongs.")
            # From: agents/features/runtime/images/image_planning.py
            brief += _image_brief_line(proj_dir, requirement_brief)
            ok = arch.run(brief, requirement_source=requirement_brief)
        if not ok:
            estep("plan", "error")
            eerr("Agent failed to generate the project")
            # From: agents/data/database_server.py
            qa.stop()
            return
        estep("plan", "done")
        estep("generate", "done")

        # From: agents/build/tester_common.py
        elog("INFO", f"   ✅ {len(arch.files)} files written "
                     f"({arch.tokens_out:,} tokens generated)")
        write_auth_details(proj_dir, arch.plan, arch=arch)
        _report_unparseable(arch)

        try:
            if drawing["thread"]:
                if drawing["thread"].is_alive():
                    # From: agents/build/tester_common.py
                    elog("INFO", "   🖼 images continue in the background while code is built/tested")
            else:
                t = threading.Thread(target=run_image_stage, args=(arch, proj_dir),
                                     daemon=True)
                drawing["thread"] = t
                # From: agents/data/database_server.py
                t.start()
        except Exception as e:
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ Image stage could not continue in background: {e}")
            log.exception("image stage")

        # Stage 3: compare generated files with the approved plan.
        # From: agents/pipeline/feature_safety.py
        analyzer = _analyzer_for(arch, proj_dir, allow_reseed=True)

        qa.drain(timeout=180)
        _backfill_tests(arch, proj_dir, qa)

        qa_targets = FileSnapshot(proj_dir)
        qa_targets.capture(sorted({m.get("target") for m in qa.manifest.values()
                                   if m.get("target")}))
        try:
            analyzer.run(semantic=False)
        except Exception as e:
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ Analyzer failed: {e}")
            log.exception("analyzer (seam A)")
        qa.mark_stale(qa_targets.changed())

        mongo_thread.join(timeout=120)
        db_ok = database_ready()

        try:
            # From: agents/planner/builder/dependency_manager.py
            arch.sync_dependencies()
            # From: agents/planner/builder/dependency_manager.py
            arch.install_unresolved()
        except Exception as e:
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ dependency preflight could not finish: {e}")

        # Stage 4: install dependencies and prove a production build works.
        estep("install", "active")
        eprog("npm install…", 84)
        if not ensure_node_deps(proj_dir):
            estep("install", "error")
            eerr("Failed to install dependencies")
            return
        estep("install", "done")

        if db_ok:
            try:
                # From: agents/data/database_records.py
                r = MONGO.reset_project_db(proj_dir, node_bin=NODE_BIN)
                if r.get("dropped"):
                    # From: agents/build/tester_common.py
                    elog("INFO", f"   🧹 Cleared {r['db']} — {r['dropped']} "
                                 f"collection(s) left by a previous app")
            except Exception as e:
                log.warning(f"fresh-db reset skipped: {e}")

        # From: agents/pipeline/build/build_fix_loop.py
        build_ok = run_build_fix_loop(arch, proj_dir, db_ok)
        if not build_ok:
            estep("build", "error")

        pretest_targets = FileSnapshot(proj_dir)
        pretest_targets.capture(sorted({m.get("target") for m in qa.manifest.values()
                                        if m.get("target")}))
        flow_report, flow_clean, flow_conclusive, flow_written = (
            pretest_flow_convergence(
                arch, proj_dir, analyzer, build_ok=build_ok))
        if flow_written:
            qa.mark_stale(pretest_targets.changed())

        # From: agents/pipeline/build/runtime_and_tests.py
        runtime_state = run_runtime_and_qa(
            arch, proj_dir, qa, analyzer, db_ok=db_ok, build_ok=build_ok, drawing=drawing)
        unit_out = runtime_state["unit_out"]
        e2e_out = runtime_state["e2e_out"]
        runtime_errors = runtime_state["runtime_errors"]
        runtime_report = runtime_state["runtime_report"]
        api_report = runtime_state["api_report"]
        runtime_clean = runtime_state["runtime_clean"]
        api_clean = runtime_state["api_clean"]
        db_ok = runtime_state["db_ok"]
        build_ok = runtime_state["build_ok"]

        # From: agents/pipeline/build/final_quality.py
        finish_quality_and_serve(
            arch, proj_dir, qa, analyzer, pname=pname, db_ok=db_ok, build_ok=build_ok,
            flow_report=flow_report, flow_clean=flow_clean, flow_conclusive=flow_conclusive,
            unit_out=unit_out, e2e_out=e2e_out, runtime_errors=runtime_errors,
            runtime_report=runtime_report, api_report=api_report,
            runtime_clean=runtime_clean, api_clean=api_clean)

    except cancel.BuildCancelled:
        # Everything this run made goes with it.
        # From: agents/build/tester_common.py
        elog("WARN", "   ⏹ build cancelled — removing what it had made")
        # From: agents/core/runtime/cancellation.py
        detail = cancel.cleanup(PROD_DIR, delete_project)
        if detail.get("project_error"):
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ {detail['project']} did not delete: {detail['project_error']}")
        if detail.get("srs_error"):
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ the specification did not delete: {detail['srs_error']}")
        ecancel(detail)
    except Exception as e:
        eerr(f"Agent error: {e}")
        log.exception("Agent pipeline error")
    finally:
        try:
            # From: agents/data/database_server.py
            qa.stop()
        except Exception:
            pass
        stop_model(model)
        # From: agents/core/runtime/cancellation.py
        cancel.finish()

