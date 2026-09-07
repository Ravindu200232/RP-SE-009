# Serves the QA record to the studio.
"""Reading back what the QA agent proved.

The record is written once by the QA agent, in the shape the Testing tab
renders. Nothing is re-derived here: a second summary computed at read time is
a second thing that can disagree with the evidence.
"""

from qa_agent import build_pdf as _build_pdf
from qa_agent import read_results as _read_results


def read_qa_results(proj_name: str) -> dict:
    name = str(proj_name or "").strip()
    proj_dir = PROD_DIR / name
    if not name or not proj_dir.is_dir():
        return {"error": "no such project", "project": name}
    return _read_results(proj_dir, name)


def build_qa_pdf(qa: dict, out, project: str = ""):
    return _build_pdf(qa, out, project)


def qa_evidence(proj_name: str) -> dict:
    """The verification ledger on its own, for the evidence panel."""
    record = read_qa_results(proj_name)
    return (record.get("report") or {}).get("evidence") or {}
