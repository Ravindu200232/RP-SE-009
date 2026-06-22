"""Data model quality gate.

Fails a planned data model when it is too shallow for a real app: only generic
Item/User CRUD, missing relationships when the prompt implies them, no indexes,
no validation, no role model under auth, or no workflow side effects for
transactional entities (booking / order / invoice / enrollment / appointment).
"""
from __future__ import annotations


_TRANSACTION_WORDS = ("Booking", "Order", "Invoice", "Appointment", "Enrollment",
                      "Reservation", "Tour", "Sale", "TestDrive", "GRN", "Payment", "Lead")


def evaluate(model: dict) -> dict:
    issues = []
    entities = model.get("entities", [])
    names = [e["name"] for e in entities]
    non_user = [e for e in entities if e["name"] != "User"]

    if len(non_user) <= 1 and any(n in ("Item", "Record", "Thing") for n in names):
        issues.append("only generic Item/User CRUD generated for a richer prompt")

    total_refs = sum(len(e.get("relationships", [])) for e in entities)
    if len(non_user) > 1 and total_refs == 0:
        issues.append("no relationships between entities")

    if not any(e.get("indexes") for e in entities):
        issues.append("no indexes on any entity")

    if not any(any(f.get("required") for f in e.get("fields", [])) for e in entities):
        issues.append("no required-field validation")
    if not any(e.get("unique") or any(f.get("unique") for f in e.get("fields", [])) for e in entities):
        issues.append("no unique constraints")

    if model.get("auth_required") and len(model.get("roles", [])) < 2:
        issues.append("auth required but no role model")

    txn = [e for e in entities if any(w in e["name"] for w in _TRANSACTION_WORDS)]
    for e in txn:
        if not e.get("side_effects") and not e.get("relationships"):
            issues.append(f"{e['name']} is transactional but has no relationships or side effects")
    # at least one entity must carry real workflow side effects
    if txn and not any(e.get("side_effects") for e in txn):
        issues.append("no workflow side effects for any transactional entity")

    return {
        "ok": not issues,
        "issues": issues,
        "entity_count": len(entities),
        "relationship_count": total_refs,
        "transactional_entities": [e["name"] for e in txn],
        "side_effect_count": sum(len(e.get("side_effects", [])) for e in entities),
    }
