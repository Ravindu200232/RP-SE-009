"""Data model planner tests — relationship-aware models per domain + unseen apps."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import data_model_planner as dmp
from app import data_model_quality_gate as dmg

RESULTS = []


def rec(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""), flush=True)


def names(model):
    return {e["name"] for e in model["entities"]}


def refs_of(model, entity):
    e = next((x for x in model["entities"] if x["name"] == entity), None)
    return {r["target"] for r in (e["relationships"] if e else [])}


def side_effects_of(model, entity):
    e = next((x for x in model["entities"] if x["name"] == entity), None)
    return [s["action"] for s in (e["side_effects"] if e else [])]


def main():
    print("=" * 72)
    print("DATA MODEL PLANNER")
    print("=" * 72)

    hosp = dmp.plan_data_model("Create a hospital platform with appointment booking, doctor search, departments, patient portal, provider portal, clinic management, lab reports, billing, compliance and security.")
    rec("1. hospital -> Patient/Doctor/Appointment/Department/LabReport/Bill + User/Role",
        {"User", "Patient", "Doctor", "Appointment", "Department", "LabReport", "Bill"}.issubset(names(hosp))
        and len(hosp["roles"]) >= 3,
        {"entities": sorted(names(hosp)), "roles": hosp["roles"]})
    rec("1b. Appointment references Patient + Doctor + Department; LabReport/Bill reference Patient",
        {"Patient", "Doctor", "Department"}.issubset(refs_of(hosp, "Appointment"))
        and "Patient" in refs_of(hosp, "LabReport") and "Patient" in refs_of(hosp, "Bill"),
        {"appt": sorted(refs_of(hosp, "Appointment"))})

    re_ = dmp.plan_data_model("Create a real estate platform with listings, neighborhoods, agents, property tours, buyer leads, saved properties, and admin management.")
    rec("2. real estate -> Property/Agent/Neighborhood/TourBooking/Lead",
        {"Property", "Agent", "Neighborhood", "TourBooking", "Lead"}.issubset(names(re_)),
        {"entities": sorted(names(re_))})
    rec("2b. TourBooking references Property + Agent + User",
        {"Property", "Agent", "User"}.issubset(refs_of(re_, "TourBooking")),
        {"tour": sorted(refs_of(re_, "TourBooking"))})

    fit = dmp.plan_data_model("Create a fitness coaching platform with programs, trainers, class schedule, member bookings, progress tracking, payments, and admin management.")
    rec("3. fitness -> Trainer/Program/ClassSession/Booking/MemberProgress",
        {"Trainer", "Program", "ClassSession", "Booking", "MemberProgress"}.issubset(names(fit)),
        {"entities": sorted(names(fit))})
    rec("3b. Booking references Member(User) + ClassSession; decrements seats",
        {"User", "ClassSession"}.issubset(refs_of(fit, "Booking")) and "decrement" in side_effects_of(fit, "Booking"),
        {"booking_refs": sorted(refs_of(fit, "Booking")), "effects": side_effects_of(fit, "Booking")})

    pos = dmp.plan_data_model("Create a POS and inventory ERP for a tyre shop with products, brands, categories, branches, suppliers, stock, GRN, invoices, invoice items, payments, customers, employees, and stock movements.")
    rec("4. POS/ERP -> Product/Stock/Branch/Invoice/InvoiceItem/StockMovement",
        {"Product", "Stock", "Branch", "Invoice", "InvoiceItem", "StockMovement"}.issubset(names(pos)),
        {"entities": sorted(names(pos))})
    rec("4b. Invoice decrements Stock + creates InvoiceItem + StockMovement; GRN increments Stock",
        "decrement" in side_effects_of(pos, "Invoice") and "create-children" in side_effects_of(pos, "Invoice")
        and "increment" in side_effects_of(pos, "GRN"),
        {"invoice": side_effects_of(pos, "Invoice"), "grn": side_effects_of(pos, "GRN")})
    rec("4c. Product references Brand/Category/Supplier",
        {"Brand", "Category", "Supplier"}.issubset(refs_of(pos, "Product")), {"product": sorted(refs_of(pos, "Product"))})

    # indexes / validation / referenced_by guards
    rec("5. every model has refs + indexes + required-field validation + unique constraints",
        all(dmg.evaluate(m)["ok"] for m in (hosp, re_, fit, pos)),
        {"hosp": dmg.evaluate(hosp)["issues"], "pos": dmg.evaluate(pos)["issues"]})
    appt = next(e for e in hosp["entities"] if e["name"] == "Appointment")
    rec("6. relationship fields are indexed + delete guard exists (referenced_by back-links)",
        "patientId" in appt["indexes"] and "doctorId" in appt["indexes"]
        and any(e.get("referenced_by") for e in hosp["entities"]),
        {"appt_indexes": appt["indexes"]})

    # unseen domain still produces relationships (not generic Item/User only)
    unseen = dmp.plan_data_model("Build a pet grooming studio app with pets, owners, grooming appointments, services, and staff.")
    g = dmg.evaluate(unseen)
    rec("7. unseen domain infers related entities (never only generic Item/User CRUD)",
        g["entity_count"] >= 2 and g["relationship_count"] >= 1 and "only generic" not in " ".join(g["issues"]),
        {"entities": sorted(names(unseen)), "rels": g["relationship_count"]})

    # writes app_data_model.json
    import json
    import tempfile
    d = tempfile.mkdtemp()
    path = dmp.write_data_model(d, hosp)
    written = json.load(open(path, encoding="utf-8"))
    rec("8. writes app_data_model.json with entities + relationships_summary + workflows",
        os.path.exists(path) and written.get("entities") and written.get("relationships_summary") and written.get("workflows"),
        {"workflows": written.get("workflows", [])[:2]})

    print("=" * 72)
    ok = all(RESULTS)
    print(f"DATA MODEL PLANNER GREEN ({sum(RESULTS)}/{len(RESULTS)})" if ok else f"FAILURES ({sum(RESULTS)}/{len(RESULTS)} passed)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
