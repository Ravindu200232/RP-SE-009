# Runs QA after Builder has produced a preview.
"""QA handoff for finished Builder work.

Builder owns implementation and the preview lifecycle. This module owns every
verification stage and the artefacts that make it visible to the studio and
the SRS: unit evidence, direct-CDP browser journeys, UI sweep, security scan
and the durable QA change digest.
"""
from qa_agent import QAAgent


QA_PHASES = ("unit", "e2e", "ui", "security")


def run_qa_verification(*, proj_dir, project: str, model: str, qa_model: str = "",
                        think=False, host: str = "", cancel=None, memory=None,
                        preview_url: str = ""):
    """Run and publish the independent QA pass for a live project preview."""
    events = Events()
    StudioBridge(events, kind="test", phases=list(QA_PHASES), think=bool(think))
    qa = QAAgent(project=project, project_dir=proj_dir,
                 model=(qa_model or model or default_agent_model()), host=host,
                 events=events, think=bool(think), cancel=cancel,
                 memory=memory, preview_url=preview_url)
    try:
        outcome = qa.run()
        evidence = qa.agent.memory.evidence.summary()
        try:
            from server_modules.srs.qa_change import write_change
            write_change(proj_dir, evidence, outcome.record)
        except Exception as error:  # noqa: BLE001 - a lost digest must not hide test evidence
            emit({"type": "notice", "level": "warn", "project": project,
                  "message": f"QA traceability digest not written: {error}"})
        emit({"type": "test_report", "project": project,
              "stages": outcome.record.get("stages", []),
              "complete": outcome.record.get("complete", False)})
        return outcome
    finally:
        qa.dispose()
