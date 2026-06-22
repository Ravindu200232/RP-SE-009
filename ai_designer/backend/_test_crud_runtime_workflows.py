"""Runtime CRUD workflow tests — execute the generated services against the
JSON-fallback database (no Mongo required) via node ESM and assert the real
relationship side effects fire: stock decreases, counters/history update, seats
release on cancel, refs validate, related-record delete is guarded.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import data_model_planner as dmp
from app import crud_generator as cg

RESULTS = []


def rec(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""), flush=True)


def _rewrite_service(content):
    content = content.replace("from '@/lib/orm'", "from '../orm.js'")
    content = re.sub(r"from '@/lib/models/([A-Za-z]+)'", r"from '../models/\1.js'", content)
    content = content.replace("from '@/lib/models'", "from '../models/index.js'")
    return content


def _materialize(model):
    """Write orm + models + services to a temp dir as runnable node ESM."""
    files = cg.generate_crud(model)["files"]
    tmp = tempfile.mkdtemp()
    os.makedirs(os.path.join(tmp, "models"), exist_ok=True)
    os.makedirs(os.path.join(tmp, "services"), exist_ok=True)
    with open(os.path.join(tmp, "package.json"), "w") as f:
        f.write('{"type":"module"}')
    with open(os.path.join(tmp, "orm.js"), "w", encoding="utf-8") as f:
        f.write(files["src/lib/orm.js"])
    for rel, content in files.items():
        if rel.startswith("src/lib/models/") and rel.endswith(".js"):
            name = rel.rsplit("/", 1)[1]
            if name == "index.js":
                content = re.sub(r"from '\./([A-Za-z]+)'", r"from './\1.js'", content)
            with open(os.path.join(tmp, "models", name), "w", encoding="utf-8") as f:
                f.write(content)
        elif rel.startswith("src/lib/services/") and rel.endswith(".js"):
            name = rel.rsplit("/", 1)[1]
            with open(os.path.join(tmp, "services", name), "w", encoding="utf-8") as f:
                f.write(_rewrite_service(content))
    return tmp


def _run(tmp, script):
    path = os.path.join(tmp, "run.mjs")
    with open(path, "w", encoding="utf-8") as f:
        f.write(script)
    env = dict(os.environ)
    env.pop("MONGODB_URI", None)  # force JSON backend
    r = subprocess.run(["node", "run.mjs"], cwd=tmp, capture_output=True, text=True, env=env, timeout=60)
    m = re.search(r"RESULT(\{.*\})", (r.stdout or "") + (r.stderr or ""))
    if not m:
        return None, (r.stdout or "") + (r.stderr or "")
    return json.loads(m.group(1)), ""


POS_SCRIPT = """
import { createDoc, getDoc, listDocs } from './orm.js';
import { createInvoice } from './services/InvoiceService.js';
import { deleteProduct } from './services/ProductService.js';
const out = {};
const brand = await createDoc('brands', { name: 'Acme' });
const cat = await createDoc('categories', { name: 'Tyres' });
const branch = await createDoc('branches', { name: 'Main' });
const product = await createDoc('products', { name: 'Tyre X', sku: 'TX1', price: 100, brandId: brand.id, categoryId: cat.id, supplierId: null });
const stock = await createDoc('stocks', { productId: product.id, branchId: branch.id, quantity: 100 });
const invoice = await createInvoice({ number: 'INV-1', branchId: branch.id, customerId: null, items: [{ productId: product.id, qty: 5, price: 100 }] });
out.stockAfter = (await getDoc('stocks', stock.id)).quantity;
const moves = (await listDocs('stockMovements', {})).rows;
out.movements = moves.length;
out.moveType = moves[0] && moves[0].type;
out.invoiceItems = (await listDocs('invoiceItems', {})).rows.length;
try { await deleteProduct(product.id); out.deleteBlocked = false; } catch (e) { out.deleteBlocked = true; }
console.log('RESULT' + JSON.stringify(out));
"""

HEALTH_SCRIPT = """
import { createDoc, getDoc } from './orm.js';
import { createAppointment, cancelAppointment } from './services/AppointmentService.js';
const out = {};
const dept = await createDoc('departments', { name: 'Cardiology' });
const doctor = await createDoc('doctors', { name: 'Dr X', specialty: 'Cardio', departmentId: dept.id });
const patient = await createDoc('patients', { name: 'Pat' });
const appt = await createAppointment({ scheduledAt: '2026-01-01T09:00', status: 'scheduled', patientId: patient.id, doctorId: doctor.id, departmentId: dept.id });
out.docCount = (await getDoc('doctors', doctor.id)).appointmentCount;
out.history = ((await getDoc('patients', patient.id)).appointmentHistory || []).length;
await cancelAppointment(appt.id);
out.docCountAfterCancel = (await getDoc('doctors', doctor.id)).appointmentCount;
try { await createAppointment({ scheduledAt: 'x', status: 'scheduled', patientId: patient.id, doctorId: 'missing-id' }); out.refValidated = false; } catch (e) { out.refValidated = true; }
console.log('RESULT' + JSON.stringify(out));
"""

FITNESS_SCRIPT = """
import { createDoc, getDoc } from './orm.js';
import { createBooking, cancelBooking } from './services/BookingService.js';
const out = {};
const trainer = await createDoc('trainers', { name: 'T' });
const program = await createDoc('programs', { name: 'P', trainerId: trainer.id });
const cls = await createDoc('classSessions', { title: 'C', startsAt: 'x', capacity: 10, seatsAvailable: 10, trainerId: trainer.id, programId: program.id });
const user = await createDoc('users', { name: 'M', email: 'm@x', role: 'Member' });
const booking = await createBooking({ status: 'booked', memberId: user.id, classSessionId: cls.id });
out.seatsAfter = (await getDoc('classSessions', cls.id)).seatsAvailable;
await cancelBooking(booking.id);
out.seatsAfterCancel = (await getDoc('classSessions', cls.id)).seatsAvailable;
console.log('RESULT' + JSON.stringify(out));
"""


def main():
    print("=" * 72)
    print("RUNTIME CRUD WORKFLOWS (services executed against JSON DB)")
    print("=" * 72)

    pos = dmp.plan_data_model("POS inventory ERP with products, brands, categories, branches, suppliers, stock, GRN, invoices, invoice items, payments, stock movements")
    tmp = _materialize(pos)
    res, err = _run(tmp, POS_SCRIPT)
    shutil.rmtree(tmp, ignore_errors=True)
    rec("1. POS: creating an invoice decreases stock (100 -> 95)", res and res.get("stockAfter") == 95, res or err[-300:])
    rec("2. POS: invoice creates StockMovement(out) + InvoiceItem child records",
        res and res.get("movements", 0) >= 1 and res.get("moveType") == "out" and res.get("invoiceItems") == 1, res)
    rec("3. POS: deleting a product referenced by stock/items is blocked", res and res.get("deleteBlocked") is True, res)

    hosp = dmp.plan_data_model("hospital platform with appointments, doctors, departments, patients, lab reports, billing")
    tmp = _materialize(hosp)
    res, err = _run(tmp, HEALTH_SCRIPT)
    shutil.rmtree(tmp, ignore_errors=True)
    rec("4. Healthcare: appointment validates refs + increments doctor count + patient history",
        res and res.get("docCount") == 1 and res.get("history") == 1 and res.get("refValidated") is True, res or err[-300:])
    rec("5. Healthcare: cancelling an appointment decrements the doctor's count",
        res and res.get("docCountAfterCancel") == 0, res)

    fit = dmp.plan_data_model("fitness platform with programs, trainers, class schedule, member bookings, progress, payments")
    tmp = _materialize(fit)
    res, err = _run(tmp, FITNESS_SCRIPT)
    shutil.rmtree(tmp, ignore_errors=True)
    rec("6. Fitness: booking a class decreases seatsAvailable (10 -> 9)", res and res.get("seatsAfter") == 9, res or err[-300:])
    rec("7. Fitness: cancelling a booking releases the seat (9 -> 10)", res and res.get("seatsAfterCancel") == 10, res)

    print("=" * 72)
    ok = all(RESULTS)
    print(f"RUNTIME CRUD WORKFLOWS GREEN ({sum(RESULTS)}/{len(RESULTS)})" if ok else f"FAILURES ({sum(RESULTS)}/{len(RESULTS)} passed)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
