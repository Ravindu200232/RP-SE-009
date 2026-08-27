"""International standards profile for generated requirements documents."""
from __future__ import annotations

import re
from datetime import date
from typing import Any

SRS_STANDARD = "ISO/IEC/IEEE 29148:2018"
SRS_STANDARD_TITLE = "Systems and software engineering — Life cycle processes — Requirements engineering"
UML_STANDARD = "OMG UML 2.5.1"
BPMN_STANDARD = "OMG BPMN 2.0.2"
ERD_NOTATION = "Crow's Foot ERD"
DFD_NOTATION = "Yourdon/DeMarco-style DFD"

# Concise, reader-facing guidance derived from the named standards and the
# diagramming conventions used by professional modelling tools.  This is also
# a generation contract: a diagram must begin with these elements and must not
# invent relationships that the approved SRS does not support.
DIAGRAM_GUIDANCE = {
    "use_case": {
        "question": "What is a Use Case Diagram?",
        "definition": (
            "A UML use case diagram shows the system boundary, the external actors that use "
            "the system, and the observable goals they expect the system to fulfil."
        ),
        "drawing_rules": [
            "Start with actors outside one named system boundary and place actor goals inside it.",
            "Connect actors only to goals supported by the approved roles and capabilities.",
            "Add «include», «extend», or generalization only when that relationship is explicit in the SRS.",
        ],
    },
    "sequence": {
        "question": "What is a Sequence Diagram?",
        "definition": (
            "A UML sequence diagram shows how an actor and system participants exchange messages "
            "for one scenario, with time progressing from top to bottom."
        ),
        "drawing_rules": [
            "Start with the initiating actor, application participants, and their lifelines.",
            "Draw requests in execution order and show the corresponding return messages.",
            "Use alt, opt, loop, or parallel fragments only when the SRS states those conditions.",
        ],
    },
    "erd": {
        "question": "What is an Entity-Relationship Diagram?",
        "definition": (
            "An ER diagram is a database blueprint showing persistent entities, their attributes, "
            "keys, relationships, and supported cardinalities."
        ),
        "drawing_rules": [
            "Start from the approved persistent entities and list their typed PK and FK attributes.",
            "Connect only explicit relationships or resolvable foreign-key references.",
            "Show one, many, and optionality with Crow's Foot markers only when supported by the schema.",
        ],
    },
    "activity": {
        "question": "What is an Activity Diagram?",
        "definition": (
            "A UML activity diagram models a workflow as actions connected by control flow, including "
            "supported choices, loops, and concurrent work."
        ),
        "drawing_rules": [
            "Start at one initial node, follow the ordered SRS workflow, and finish at a final node.",
            "Use a decision and merge only for an explicit guarded alternative.",
            "Use fork and join bars only when the requirements explicitly allow parallel activities.",
        ],
    },
    "class_object": {
        "question": "What is a Class & Object Diagram?",
        "definition": (
            "A UML class diagram describes static types, their attributes, operations, and relationships; "
            "an object view shows an illustrative runtime instance of one of those classes."
        ),
        "drawing_rules": [
            "Start with one compartmented class box per supported domain type.",
            "List typed attributes and operations only when they are present in the SRS model.",
            "Add association multiplicity, aggregation, composition, or inheritance only with supporting evidence.",
        ],
    },
    "state_machine": {
        "question": "What is a State Machine Diagram?",
        "definition": (
            "A UML state machine shows the legal states in one object's lifecycle and the events or "
            "conditions that permit each transition."
        ),
        "drawing_rules": [
            "Start from an initial pseudo-state and one explicitly modelled lifecycle field.",
            "Draw only legal from-state to to-state transitions stated by the requirements.",
            "If no transitions are specified, explain the missing evidence instead of inventing a lifecycle.",
        ],
    },
    "dfd": {
        "question": "What is a Data Flow Diagram?",
        "definition": (
            "A data flow diagram shows how named information enters the system, is transformed by "
            "processes, is stored, and leaves for external entities."
        ),
        "drawing_rules": [
            "Start with external entities, numbered verb–noun processes, and approved data stores.",
            "Label every arrow with the actual data being moved rather than a control-flow action.",
            "Never connect entity-to-entity or entity-to-store directly, and avoid black-hole or miracle processes.",
        ],
    },
    "bpmn": {
        "question": "What is a BPMN Process Diagram?",
        "definition": (
            "A BPMN process diagram models a business process with events, tasks, gateways, and "
            "participant lanes that make responsibility and hand-offs explicit."
        ),
        "drawing_rules": [
            "Start with a named pool, horizontal responsibility lanes, and one start event.",
            "Place each task in the lane of the participant responsible for it and follow sequence flow.",
            "Use gateways only for explicit branch semantics and finish with an end event.",
        ],
    },
    "system_context": {
        "question": "What is a System Context Diagram?",
        "definition": (
            "A system context diagram defines the software boundary and its externally visible "
            "relationships with people, external systems, and persistent data."
        ),
        "drawing_rules": [
            "Start with one central system boundary and keep implementation detail inside it minimal.",
            "Place human actors and external systems outside the boundary.",
            "Label every supported interaction or data relationship and omit unsupported integrations.",
        ],
    },
    "component": {
        "question": "What is a Component Diagram?",
        "definition": (
            "A UML component diagram shows modular software parts, the interfaces or ports through "
            "which they collaborate, and the dependencies required to assemble the system."
        ),
        "drawing_rules": [
            "Start with presentation, application/domain, and data/external component groups.",
            "Give each component one clear responsibility and connect every displayed dependency through a port.",
            "Show provided or required interfaces only when the SRS identifies that service boundary.",
        ],
    },
    "deployment": {
        "question": "What is a Deployment Diagram?",
        "definition": (
            "A UML deployment diagram shows runtime nodes, the software artifacts hosted on them, "
            "and the communication paths that form the physical execution topology."
        ),
        "drawing_rules": [
            "Start with client, application host, and data host nodes required by the approved stack.",
            "Nest deployed software artifacts inside the node on which they execute.",
            "Label communication protocols and add external service nodes only when required by the SRS.",
        ],
    },
}

_VAGUE = re.compile(r"\b(user[- ]?friendly|easy|fast|quickly|appropriate|adequate|etc\.?|and so on|as needed|normally|usually)\b", re.I)
_COMPOUND = re.compile(r"\b(and|or)\b", re.I)
_TESTABLE = re.compile(r"\b(within|less than|more than|at least|at most|%|seconds?|minutes?|milliseconds?|must|shall|will)\b", re.I)


def _verification_method(text: str, category: str = "") -> str:
    low = f"{category} {text}".lower()
    if any(k in low for k in ("performance", "latency", "response time", "throughput", "load", "concurrent")):
        return "Test / Measurement"
    if any(k in low for k in ("security", "permission", "role", "encrypt", "authentication", "authorization", "privacy")):
        return "Test / Inspection"
    if any(k in low for k in ("availability", "uptime", "recovery", "backup")):
        return "Test / Analysis"
    if any(k in low for k in ("ui", "screen", "display", "show", "render", "accessible", "wcag")):
        return "Demonstration / Inspection"
    return "Functional Test"


def _quality_flags(text: str) -> list[str]:
    """Conservative requirement-quality warnings, not a certification score."""
    s = " ".join(str(text or "").split())
    flags: list[str] = []
    if not s:
        return ["empty"]
    if _VAGUE.search(s):
        flags.append("potentially ambiguous wording")
    if len(_COMPOUND.findall(s)) >= 3:
        flags.append("possibly compound requirement")
    if not _TESTABLE.search(s) and not re.search(r"\bshall\b", s, re.I):
        flags.append("verification criterion should be made explicit")
    return flags


def _source_map(doc: dict) -> dict[str, str]:
    """Best-effort provenance from approved plan features / screens."""
    plan = doc.get("effective_plan") or doc.get("approved_plan") or {}
    sources: dict[str, str] = {}
    for i, feature in enumerate(plan.get("features") or [], 1):
        text = str(feature or "").strip()
        if text:
            sources[text.casefold()] = f"Approved Plan Feature {i}"
    return sources


def apply_international_profile(srs: dict) -> dict:
    """Enrich an SRS in place with ISO/IEC/IEEE-29148-oriented metadata."""
    doc = srs.get("srs_document", srs)
    if not isinstance(doc, dict):
        return srs

    doc["standards_profile"] = {
        "requirements_standard": SRS_STANDARD,
        "requirements_standard_title": SRS_STANDARD_TITLE,
        "uml_standard": UML_STANDARD,
        "bpmn_standard": BPMN_STANDARD,
        "erd_notation": ERD_NOTATION,
        "dfd_notation": DFD_NOTATION,
        "conformance_note": (
            "Structure and notation are aligned to the named standards. Formal conformance or "
            "certification requires project-specific review and approval by the responsible organisation."
        ),
    }
    doc.setdefault("document_control", {})
    dc = doc["document_control"]
    dc.setdefault("document_id", f"SRS-{re.sub(r'[^A-Z0-9]+', '-', str(doc.get('project_name', 'PROJECT')).upper()).strip('-')[:32] or 'PROJECT'}")
    dc.setdefault("version", doc.get("version", "1.0.0"))
    dc.setdefault("status", "Draft")
    dc.setdefault("prepared_date", date.today().isoformat())
    dc.setdefault("standard", SRS_STANDARD)
    dc.setdefault("document_owner", "Project Stakeholders")
    doc.setdefault("revision_history", [{
        "version": dc.get("version", doc.get("version", "1.0.0")),
        "date": dc.get("prepared_date", date.today().isoformat()),
        "description": "Generated requirements baseline",
    }])
    doc.setdefault("approval_record", [])

    source_map = _source_map(doc)
    review: list[dict[str, Any]] = []

    for fr in doc.get("functional_requirements") or []:
        if not isinstance(fr, dict):
            continue
        text = str(fr.get("requirement") or "").strip()
        fr.setdefault("source", source_map.get(text.casefold(), "Approved SRS / stakeholder input"))
        fr.setdefault("verification_method", _verification_method(text, "functional"))
        fr.setdefault("rationale", "Required to satisfy the approved product capability represented by this requirement.")
        flags = _quality_flags(text)
        fr["quality_review"] = {"status": "review" if flags else "pass", "warnings": flags}
        if flags:
            review.append({"requirement_id": fr.get("id"), "warnings": flags})

    for nfr in doc.get("non_functional_requirements") or []:
        if not isinstance(nfr, dict):
            continue
        text = str(nfr.get("requirement") or "").strip()
        nfr.setdefault("source", "Approved SRS / stakeholder quality expectation")
        nfr.setdefault("verification_method", _verification_method(text, str(nfr.get("category") or "")))
        flags = _quality_flags(text)
        nfr["quality_review"] = {"status": "review" if flags else "pass", "warnings": flags}
        if flags:
            review.append({"requirement_id": nfr.get("id"), "warnings": flags})

    fr_by_id = {str(r.get("id")): r for r in doc.get("functional_requirements") or [] if isinstance(r, dict)}
    for row in doc.get("requirement_traceability_matrix") or []:
        if not isinstance(row, dict):
            continue
        fr = fr_by_id.get(str(row.get("requirement_id"))) or {}
        row.setdefault("source", fr.get("source", "Approved SRS"))
        row.setdefault("verification_method", fr.get("verification_method", "Functional Test"))
        if not row.get("test_case"):
            rid = str(row.get("requirement_id") or "REQ")
            row["test_case"] = f"TC-{rid.replace('FR-', '').replace('NFR-', '')}"

    doc["requirements_quality_review"] = {
        "profile": SRS_STANDARD,
        "items_needing_human_review": review,
        "note": "Warnings are conservative lint findings, not proof that a requirement is invalid.",
    }
    return srs

DIAGRAM_NOTATION = {
    "use_case": [
        "Stick figure — actor (person or external system)",
        "Oval — use case (actor goal / system behavior)",
        "System boundary — scope of the subject system",
        "Solid line — actor/use-case association",
        "Dashed «include» / «extend» relationships appear only when explicitly specified",
    ],
    "sequence": [
        "Participant box + dashed vertical line — lifeline",
        "Thin rectangle on lifeline — activation / execution occurrence",
        "Solid arrow — synchronous call/request",
        "Dashed open arrow — return/response",
        "Time progresses from top to bottom",
    ],
    "erd": [
        "Entity rectangle — entity/table with attributes",
        "PK / FK — primary and foreign keys",
        "Single bar — one; crow's foot — many",
        "Optionality markers are shown only when the SRS provides enough information",
    ],
    "activity": [
        "Solid black circle — initial node",
        "Rounded rectangle — action",
        "Diamond — decision/merge only for explicit guarded alternatives",
        "Arrow — control flow",
        "Circle-in-circle — final node",
    ],
    "class_object": [
        "Compartmented rectangle — class name and attributes",
        "+ / - — public/private visibility convention",
        "Multiplicity at association ends — 1, 0..*, etc.",
        "Underlined instance-name : Class — object diagram instance",
    ],
    "state_machine": [
        "Rounded rectangle — state",
        "Solid black circle — initial pseudo-state",
        "Circle-in-circle — final pseudo-state",
        "Labeled arrow — transition/event",
        "No transition is invented when the SRS does not state a legal lifecycle",
    ],
    "dfd": [
        "Rectangle — external entity",
        "Circle/rounded process — process that transforms data",
        "Open-ended data-store symbol — persistent data store",
        "Labeled arrow — data flow (not control flow)",
    ],
    "bpmn": [
        "Thin circle / thick circle — start/end event",
        "Rounded rectangle — task/activity",
        "Diamond — gateway only for explicit branching semantics",
        "Pool/lane — participant/responsibility boundary",
        "Solid arrow — sequence flow; message flow is not used inside one pool",
    ],
    "system_context": [
        "Central system boundary — the software system in scope",
        "Person/role box — human actor using the system",
        "External-system box — third-party dependency or integration",
        "Database cylinder — persistent application data",
        "Labeled arrow — externally visible relationship",
    ],
    "component": [
        "Component rectangle with UML component glyph — deployable/logical component",
        "Horizontal bands — presentation, application/domain, and data/external interfaces",
        "Dependency arrow — one component depends on another supported SRS element",
    ],
    "deployment": [
        "3-D node box — device or execution environment",
        "Nested text — software artifacts hosted on the node",
        "Communication path — protocol/connection between nodes",
        "External service box — separately deployed integration",
    ],
}
