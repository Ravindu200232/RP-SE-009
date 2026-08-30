# Feature QA handoff: author focused tests -> run them -> return the QA session.
def _feature_tests(arch, proj_dir: Path, spec, model: str, qa_model: str, *,
                   build_ok: bool):
    """Author and run scoped unit tests when build and cloud QA are ready."""
    qa_model = qa_model or model
    qa = QASession(proj_dir, callbacks=_qa_callbacks(), model=qa_model,
                   enabled=is_cloud_model(qa_model))
    if not qa.enabled:
        elog("WARN", "   ⚠ QA is cloud-only — the feature ships untested. "
                     "Pick a cloud QA model to have tests written for it.")
        return qa
    if not build_ok:
        elog("WARN", "   ⚠ Skipping the feature's tests — the build is not green")
        return qa
    qa.bind(arch)

    targets = select_targets(spec.written, qa.read_source,
                             already=len(qa.manifest))
    if not targets:
        elog("INFO", "   🧪 Nothing in this feature is worth a unit test")
    else:
        elog("INFO", f"   🧪 Writing tests for {len(targets)} new file(s)")
        author = UnitTestAuthor(arch, proj_dir, callbacks=_qa_callbacks(),
                                session=qa)
        written = author.write_for(targets)
        elog("INFO", f"   🧪 {len(written)} test file(s) written")

    if not qa.has_tests():
        return qa
    ephase({"phase": -15, "title": "Running unit tests", "status": "active"})
    harness = TestHarness(proj_dir, callbacks=_qa_callbacks(), cmd=qa.cmd)
    harness.materialise()
    if not harness.install():
        _qa_skip(qa, "the test runner could not be installed")
        ephase({"phase": -15, "title": "Running unit tests", "status": "done"})
        return qa
    try:
        run_qa_unit_stage(arch, proj_dir, qa, build_ok=True,
                          scope=spec.written)
    except Exception as e:
        elog("WARN", f"   ⚠ Unit test stage failed: {e}")
        log.exception("feature unit tests")
    ephase({"phase": -15, "title": "Running unit tests", "status": "done"})
    return qa

