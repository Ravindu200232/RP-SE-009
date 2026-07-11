"""Acceptance tests for the agentic SRS pipeline (offline / deterministic)."""
import pytest

from app.services import orchestrator
from app.schemas.srs import validate_srs, summarize_srs
from app.agents.pdf_generator import generate_pdf
from app.knowledge.offline_srs import build_offline_srs, merge_pack


HOTEL = ("A hotel booking platform where guests can search rooms, make bookings, "
         "pay online, and hotel admins manage inventory and view revenue reports.")
RETAIL = ("An online and in-store retail system with POS, product inventory, "
          "suppliers, barcode scanning, and sales reports.")
SCHOOL = ("A school management platform with student admissions, attendance, exams, "
          "fees, transport, and a parent portal.")
CLINIC = ("A clinic management system with patient records, doctor appointments, "
          "prescriptions, and billing.")


async def _full_run(idea: str, n_answers: int = 6):
    proj = await orchestrator.create_project(idea)
    pid = proj["id"]
    res = await orchestrator.analyze(pid)
    answers = []
    for q in res["questions"][:n_answers]:
        opts = q.get("suggested_options") or []
        answers.append({"question_id": q["id"], "value": opts[0] if opts else "Yes", "raw_text": None})
    await orchestrator.submit_answers(pid, answers)
    gen = await orchestrator.generate_srs(pid)
    return pid, gen


# ── intake / classification ──────────────────────────────────
async def test_text_idea_creates_project():
    proj = await orchestrator.create_project(HOTEL)
    assert proj["id"]
    assert proj["status"] == "intake"
    assert proj["title"]


async def test_nonsense_idea_asks_clarification_no_fake_srs():
    proj = await orchestrator.create_project("asdasdas asd asd qwe zxc")
    res = await orchestrator.analyze(proj["id"])
    assert res["needs_clarification"] is True
    assert res["clarification_reason"]
    # No SRS should exist yet.
    assert await orchestrator.latest_srs(proj["id"]) is None
    # Clarification questions are basic + plain.
    assert len(res["questions"]) >= 1


async def test_question_planner_dynamic_count():
    proj = await orchestrator.create_project(HOTEL)
    res = await orchestrator.analyze(proj["id"])
    n = len(res["questions"])
    assert 5 <= n <= 20


async def test_answers_update_coverage():
    proj = await orchestrator.create_project(HOTEL)
    res = await orchestrator.analyze(proj["id"])
    answers = [{"question_id": q["id"], "value": (q.get("suggested_options") or ["Yes"])[0]}
               for q in res["questions"][:5]]
    out = await orchestrator.submit_answers(proj["id"], answers)
    assert 0 <= out["coverage_score"] <= 100
    assert out["coverage_score"] > 0


# ── domain-specific generation ───────────────────────────────
async def test_hotel_generates_hotel_tables():
    pid, gen = await _full_run(HOTEL)
    tables = [t["table_name"] for t in gen["srs"]["srs_document"]["database_design"]["tables"]]
    assert {"rooms", "bookings"}.issubset(set(tables))
    validate_srs(gen["srs"])


async def test_retail_generates_pos_inventory_tables():
    pid, gen = await _full_run(RETAIL)
    tables = [t["table_name"] for t in gen["srs"]["srs_document"]["database_design"]["tables"]]
    assert {"products", "inventory", "sales_orders"}.issubset(set(tables))


async def test_school_generates_lms_fees_transport_tables():
    pid, gen = await _full_run(SCHOOL)
    doc = gen["srs"]["srs_document"]
    tables = [t["table_name"] for t in doc["database_design"]["tables"]]
    assert {"students", "fee_invoices", "transport_routes"}.issubset(set(tables))
    assert any("LMS" in m or "Assignment" in m or "Lesson" in m for m in doc["main_modules"])


async def test_clinic_generates_patient_tables():
    pid, gen = await _full_run(CLINIC)
    tables = [t["table_name"] for t in gen["srs"]["srs_document"]["database_design"]["tables"]]
    assert {"patients", "appointments"}.issubset(set(tables))


async def test_restaurant_generates_food_tables():
    pid, gen = await _full_run(
        "An online food ordering and restaurant system with menu, table QR ordering, "
        "delivery and a live kitchen board.")
    doc = gen["srs"]["srs_document"]
    tables = [t["table_name"] for t in doc["database_design"]["tables"]]
    assert {"menu_items", "orders", "order_items"}.issubset(set(tables))
    assert gen["project"]["domain_key"] == "restaurant"


def test_merge_pack_assembles_valid_srs():
    """LLM enrichment-pack merge yields a valid SRS: universal + domain tables,
    regenerated API, and FR ids — the core of reliable LLM SRS generation."""
    proj = {"title": "Acme", "raw_idea": "a custom workflow app", "domain_key": "custom",
            "language": "English", "current_version": "1.0.0"}
    skeleton = build_offline_srs(project=proj, answers=[], brief="a custom workflow app")
    pack = {
        "system_category": "Custom Workflow Platform",
        "tables": [
            {"table_name": "widgets", "fields": [{"name": "id", "type": "uuid", "primary_key": True},
                                                 {"name": "title", "type": "string"}]},
            {"table_name": "gizmos", "fields": [{"name": "id", "type": "uuid", "primary_key": True},
                                                {"name": "widget_id", "type": "foreign_key", "references": "widgets.id"}]},
            {"table_name": "gadgets", "fields": [{"name": "id", "type": "uuid", "primary_key": True}]},
            {"table_name": "sprockets", "fields": [{"name": "id", "type": "uuid", "primary_key": True}]},
        ],
        "relationships": [{"from": "widgets.id", "to": "gizmos.widget_id", "type": "one_to_many", "description": "has"}],
        "functional_requirements": [
            {"module": "Widgets", "requirement": f"The system shall manage widget feature {i}.", "priority": "high"}
            for i in range(6)
        ],
        "risk_priority": [{"area": "Ops", "risk": "Downtime", "severity": "Medium", "reason": "x", "mitigation": "y"}],
    }
    merged = merge_pack(skeleton, pack)
    validate_srs(merged)  # must assemble to a valid SRS
    doc = merged["srs_document"]
    names = [t["table_name"] for t in doc["database_design"]["tables"]]
    # universal tables preserved + domain tables added
    assert all(u in names for u in ("users", "roles", "permissions", "audit_logs", "notifications"))
    assert {"widgets", "gizmos", "gadgets", "sprockets"}.issubset(set(names))
    # API regenerated from the new domain tables
    assert any("/api/widgets" in a["path"] for a in doc["api_design"])
    # FR ids assigned sequentially, universal + pack present
    assert doc["functional_requirements"][0]["id"] == "FR-001"
    assert doc["system_category"] == "Custom Workflow Platform"


# ── SRS validity & structure ─────────────────────────────────
async def test_srs_validates_and_is_not_empty():
    pid, gen = await _full_run(HOTEL)
    doc = gen["srs"]["srs_document"]
    assert len(doc["functional_requirements"]) >= 3
    assert len(doc["non_functional_requirements"]) >= 3
    assert len(doc["roles"]) >= 1
    assert len(doc["requirement_traceability_matrix"]) >= 1
    assert doc["acceptance_criteria"]


async def test_diagrams_generated_for_all_kinds():
    pid, gen = await _full_run(HOTEL)
    kinds = {d["kind"] for d in gen["srs"]["srs_document"]["diagrams"]}
    assert kinds == {"use_case", "activity", "sequence", "erd", "system_context", "component", "deployment"}
    # Each has Mermaid source.
    for d in gen["srs"]["srs_document"]["diagrams"]:
        assert d["source"].strip()


async def test_pdf_generated_and_nonempty():
    pid, gen = await _full_run(HOTEL)
    path = await generate_pdf(pid, gen["srs"], status="Draft", version=gen["version"])
    assert path.exists()
    assert path.stat().st_size > 2000


# ── customization & versioning ───────────────────────────────
async def test_customize_preserves_data_and_bumps_version():
    pid, gen = await _full_run(HOTEL)
    before = {t["table_name"] for t in gen["srs"]["srs_document"]["database_design"]["tables"]}
    before_fr = len(gen["srs"]["srs_document"]["functional_requirements"])

    cust = await orchestrator.customize(pid, "Add a loyalty programme to system features")
    after_doc = cust["srs"]["srs_document"]
    after = {t["table_name"] for t in after_doc["database_design"]["tables"]}

    assert before.issubset(after)                       # nothing deleted
    assert "loyalty_accounts" in after                  # new table added
    assert len(after_doc["functional_requirements"]) > before_fr
    assert cust["version"] == "1.1.0"
    assert cust["diff_summary"]


async def test_version_history_preserved():
    pid, gen = await _full_run(HOTEL)
    await orchestrator.customize(pid, "Add multi-currency requirement")
    detail = await orchestrator.project_detail(pid)
    versions = [v["version"] for v in detail["versions"]]
    assert "1.0.0" in versions and "1.1.0" in versions


async def test_customize_stricter_performance():
    pid, gen = await _full_run(HOTEL)
    cust = await orchestrator.customize(pid, "Make the performance target stricter")
    nfrs = cust["srs"]["srs_document"]["non_functional_requirements"]
    perf = [n for n in nfrs if n["category"].lower() == "performance"]
    assert perf and ("1 second" in perf[0]["requirement"] or "P95" in perf[0]["requirement"])


async def test_rename_module_via_prompt():
    pid, gen = await _full_run(HOTEL)
    cust = await orchestrator.customize(pid, "Rename Booking Engine to Reservation Engine")
    blob = str(cust["srs"]["srs_document"]["main_modules"])
    assert "Reservation Engine" in blob


# ── inspector summary ────────────────────────────────────────
async def test_summary_matches_counts():
    pid, gen = await _full_run(HOTEL)
    doc = gen["srs"]["srs_document"]
    summary = summarize_srs(gen["srs"])
    assert summary["functional"] == len(doc["functional_requirements"])
    assert summary["non_functional"] == len(doc["non_functional_requirements"])
    assert summary["tables"] == len(doc["database_design"]["tables"])
    assert summary["diagrams"] == 7
