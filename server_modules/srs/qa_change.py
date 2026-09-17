"""What QA proved, in a form the parent SRS can record.

The SRS is supposed to be the document that says what the product must do and
what has been shown to work. The first half was always there; the second was
not. QA evidence stopped at `.agentforge/qa/results.json`, so the specification
could carry thirty requirements with nothing anywhere saying which of them a
test had ever touched.

This turns the evidence ledger into a report the parent-sync transaction can
hand to the model. Two things about its shape matter more than the wording:

  * It states failures as failures. A digest that only lists passes teaches the
    document to claim verification it does not have, which is worse than saying
    nothing.
  * It carries each requirement's description beside its id. Scope ids are
    chosen by the build and normalised (`evidence._requirement_id`), so they are
    not guaranteed to be the handoff's `FR-003`; the description is what lets
    the model match a verified behaviour to the requirement that describes it.
"""
from __future__ import annotations

import json
from pathlib import Path

CHANGE_FILE = "srs-change.json"
MAX_ROWS = 60


def change_path(project_dir: Path | str) -> Path:
    return Path(project_dir) / ".agentforge" / "qa" / CHANGE_FILE


def _passed_suites(evidence: dict) -> list[dict]:
    return [s for s in (evidence.get("suites") or []) if s.get("status") == "passed"]


def _rows(evidence: dict) -> list[dict]:
    """One row per requirement in scope, with whatever proved it."""
    scope = (evidence.get("scope") or {}).get("requirements") or []
    passed = _passed_suites(evidence)
    rows = []
    for requirement in scope[:MAX_ROWS]:
        rid = str(requirement.get("id") or "").strip()
        wanted = list(requirement.get("evidence") or [])
        proofs = {}
        for kind in wanted:
            names = [s.get("suite") or s.get("command") or kind
                     for s in passed
                     if s.get("kind") == kind and rid in (s.get("covers") or [])]
            if names:
                proofs[kind] = sorted({str(n)[:80] for n in names})
        rows.append({
            "id": rid,
            "description": str(requirement.get("description") or "").strip(),
            "expected": wanted,
            "proved_by": proofs,
            "verified": bool(wanted) and all(kind in proofs for kind in wanted),
        })
    return rows


def traceability_digest(evidence: dict, record: dict | None = None) -> dict:
    """The machine-readable half. `summary_text` is what the model reads."""
    rows = _rows(evidence)
    coverage = evidence.get("coverage") or {}
    unit = (coverage.get("unit") or {}).get("requirementCoverage") or {}
    e2e = coverage.get("e2e") or {}
    digest = {
        "revision": evidence.get("revision"),
        "ready": bool(evidence.get("ready")),
        "unit": {"covered": unit.get("covered", 0), "total": unit.get("total", 0),
                 "percent": unit.get("percent", 0)},
        "e2e": {"covered": e2e.get("covered", 0), "total": e2e.get("total", 0),
                "percent": e2e.get("percent", 0), "target": e2e.get("target"),
                "status": e2e.get("status")},
        "missing": list(evidence.get("missingRequirements") or [])[:MAX_ROWS],
        "limitations": dict(evidence.get("limitations") or {}),
        "requirements": rows,
        "complete": bool((record or {}).get("complete")),
    }
    digest["summary_text"] = summary_text(digest)
    return digest


def summary_text(digest: dict) -> str:
    """The report the compare step reads.

    The instruction comes first and is unambiguous about scope, because the same
    LLM call is used for designer and developer changes, where adding a
    requirement is exactly the right response. Here it never is.
    """
    e2e, unit = digest["e2e"], digest["unit"]
    lines = [
        "QA VERIFICATION REPORT - TRACEABILITY ONLY. No new capability was built.",
        "",
        "Update ONLY requirement_traceability_matrix entries and acceptance criteria status.",
        # Phrased without removal verbs on purpose. This text is also read as an
        # edit instruction, and a "do not remove" sentence matched the removal
        # keywords, which turned the merge into a wholesale replace.
        "Every functional requirement, table, role, page and workflow stays exactly as it is.",
        "Keep every row already in the matrix; a row this report does not mention keeps its "
        "current status.",
        "Match each line below to an existing requirement by its description when its id is not "
        "one of the document's own ids.",
        "",
        f"Build revision: {digest.get('revision')}   Verification ready: "
        f"{str(digest.get('ready')).lower()}",
        f"Unit requirement coverage: {unit.get('covered', 0)}/{unit.get('total', 0)} "
        f"({unit.get('percent', 0)}%)",
        f"E2E requirement coverage: {e2e.get('covered', 0)}/{e2e.get('total', 0)} "
        f"({e2e.get('percent', 0)}%)"
        + (f", target {e2e.get('target')} - {str(e2e.get('status') or '').upper()}"
           if e2e.get("target") is not None else ""),
    ]

    verified = [r for r in digest["requirements"] if r["verified"]]
    unverified = [r for r in digest["requirements"] if not r["verified"]]

    if verified:
        lines += ["", "VERIFIED"]
        for row in verified:
            proof = "; ".join(f"{kind} {', '.join(names)}"
                              for kind, names in sorted(row["proved_by"].items()))
            lines.append(f'- {row["id"]} "{row["description"]}" -> {proof}')
    if unverified:
        lines += ["", "NOT VERIFIED"]
        for row in unverified:
            absent = [k for k in row["expected"] if k not in row["proved_by"]]
            why = f"no {', '.join(absent)} evidence covers it" if absent else "no evidence recorded"
            lines.append(f'- {row["id"]} "{row["description"]}" -> {why}')
    if digest["missing"]:
        lines += ["", "REQUIREMENTS WITH NO EVIDENCE AT ALL",
                  *(f"- {item}" for item in digest["missing"])]
    if digest["limitations"]:
        lines += ["", "RECORDED LIMITATIONS",
                  *(f"- {kind}: {reason}" for kind, reason in digest["limitations"].items())]
    if not verified and not unverified:
        lines += ["", "No verification scope was defined for this build."]
    return "\n".join(lines)


def write_change(project_dir: Path | str, evidence: dict, record: dict | None = None) -> Path:
    """Leave the digest for the sync transaction to pick up after the build."""
    path = change_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = traceability_digest(evidence, record)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def clear_change(project_dir: Path | str) -> None:
    """Forget a digest once it has been recorded.

    The file is written by a build that ran tests and read by the transaction
    that follows it. Left in place, the next change - a prototype edit, say,
    that runs no tests at all - would post the same evidence again under its own
    change id, and the document would carry verification attributed to work that
    was never verified.
    """
    try:
        change_path(project_dir).unlink(missing_ok=True)
    except OSError:
        pass


def read_change(project_dir: Path | str) -> dict:
    path = change_path(project_dir)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
