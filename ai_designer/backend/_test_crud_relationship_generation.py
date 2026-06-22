"""Relationship-aware CRUD generation tests (schema/api/service/ui + node --check)."""
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import data_model_planner as dmp
from app import crud_generator as cg
from app import data_model_quality_gate as dmg

RESULTS = []


def rec(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""), flush=True)


def main():
    print("=" * 72)
    print("RELATIONSHIP-AWARE CRUD GENERATION")
    print("=" * 72)

    hosp = dmp.plan_data_model("hospital platform with appointments, doctors, departments, patients, lab reports, billing")
    pos = dmp.plan_data_model("POS inventory ERP with products, brands, categories, branches, suppliers, stock, GRN, invoices, invoice items, payments, stock movements")

    h = cg.generate_crud(hosp)["files"]
    p = cg.generate_crud(pos)["files"]

    # 1. per-entity model descriptors with refs + indexes + enums
    appt_model = h["src/lib/models/Appointment.js"]
    rec("1. model descriptor has typed refs + indexes + enums",
        '"patientId"' in appt_model and '"doctorId"' in appt_model and "scheduledAt" in appt_model
        and '"enums"' in appt_model and '"collection": "patients"' in appt_model,
        {})

    # 2. service validates refs + runs relationship side effects (appointment)
    appt_svc = h["src/lib/services/AppointmentService.js"]
    rec("2. createAppointment validates refs + increments doctor + appends patient history",
        "validateRefs" in appt_svc and "incField('doctors'" in appt_svc and "pushField('patients'" in appt_svc,
        {})

    # 3. invoice service: decrement stock + create invoice items + stock movements
    inv_svc = p["src/lib/services/InvoiceService.js"]
    rec("3. createInvoice decrements stock + creates invoiceItems + stockMovements",
        "incField('stocks'" in inv_svc and "createDoc('invoiceItems'" in inv_svc and "createDoc('stockMovements'" in inv_svc,
        {})

    # 4. GRN service increments stock
    grn_svc = p["src/lib/services/GRNService.js"]
    rec("4. createGRN increments stock + records stock movements (type in)",
        "incField('stocks'" in grn_svc and "type: 'in'" in grn_svc, {})

    # 5. delete guards related records
    rec("5. delete<Entity> guards referencing records (countReferencing)",
        "countReferencing" in h["src/lib/services/DoctorService.js"]
        and "Cannot delete" in h["src/lib/services/DoctorService.js"], {})

    # 6. cancel workflow releases capacity (fitness booking)
    fit = dmp.plan_data_model("fitness platform with programs, trainers, class schedule, member bookings, progress, payments")
    booking_svc = cg.generate_crud(fit)["files"]["src/lib/services/BookingService.js"]
    rec("6. cancelBooking releases a class seat (workflow method)",
        "cancelBooking" in booking_svc and "incField('classSessions'" in booking_svc, {})

    # 7. API routes per entity (collection + item) delegate to services
    rec("7. API routes generated per entity (list+create / read+update+delete)",
        "src/app/api/appointments/route.js" in h and "src/app/api/appointments/[id]/route.js" in h
        and "createAppointment" in h["src/app/api/appointments/route.js"]
        and "populateMany" in h["src/app/api/appointments/route.js"], {})

    # 8. CRUD UI includes relation selectors + related lists
    form = h["src/components/CrudForm.jsx"]
    detail = h["src/app/(app)/manage/[collection]/[id]/page.jsx"]
    rec("8. CRUD UI has relation selectors + related-record lists + loading/empty/error states",
        "model.refs.map" in form and "<select" in form and "referencedBy" in detail
        and "Loading" in h["src/app/(app)/manage/[collection]/page.jsx"]
        and "No " in h["src/app/(app)/manage/[collection]/page.jsx"], {})

    # 9. models index has no duplicate model names + imports every entity
    idx = p["src/lib/models/index.js"]
    coll_names = pos["entity_count"]
    import_count = idx.count("import {")
    rec("9. model registry imports every entity once (no duplicate model names)",
        import_count == coll_names and "byCollection" in idx, {"imports": import_count, "entities": coll_names})

    # 10. node --check every generated .js (syntax + no obvious broken structure)
    tmp = tempfile.mkdtemp()
    bad = []
    js_count = 0
    for rel, content in {**h, **p}.items():
        if not rel.endswith(".js"):
            continue
        js_count += 1
        path = os.path.join(tmp, rel.replace("/", "_"))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
        if r.returncode != 0:
            bad.append((rel, (r.stderr or "")[:120]))
    shutil.rmtree(tmp, ignore_errors=True)
    rec("10. every generated .js passes node --check (API routes + schemas + services compile)",
        not bad, {"checked": js_count, "bad": bad[:3]})

    # 11. data model quality gate enforces relationships/side-effects
    rec("11. data model quality gate passes for relationship-rich apps",
        dmg.evaluate(hosp)["ok"] and dmg.evaluate(pos)["ok"] and dmg.evaluate(fit)["ok"], {})

    print("=" * 72)
    ok = all(RESULTS)
    print(f"CRUD RELATIONSHIP GENERATION GREEN ({sum(RESULTS)}/{len(RESULTS)})" if ok else f"FAILURES ({sum(RESULTS)}/{len(RESULTS)} passed)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
