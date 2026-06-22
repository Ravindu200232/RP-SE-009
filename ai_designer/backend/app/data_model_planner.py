"""Requirement-aware data model planner.

Turns a free-text app prompt (or SRS) into a concrete, relationship-aware data
model: entities, typed fields, enums, unique constraints, indexes, references
with cardinality + ownership, roles/access, workflow rules, and relationship
side effects (e.g. "creating an invoice decreases stock and writes a stock
movement"). The output (`app_data_model.json`) drives the Mongo schema, API,
service, and CRUD-UI generators.

Design rules:
* No app names are hardcoded. Domain RELATIONSHIP templates are data, not app
  identities, and they only activate when the domain is detected.
* Unknown domains are handled by a generic entity/relationship extractor, so the
  planner never falls back to a single Item/User CRUD when the prompt implies a
  richer model.
"""
from __future__ import annotations

import copy
import json
import os
import re


# --------------------------------------------------------------------------- #
# Domain detection
# --------------------------------------------------------------------------- #

# Ordered, most-specific first. POS/ERP is checked before generic ecommerce.
DOMAIN_KEYWORDS = {
    "healthcare": ["hospital", "clinic", "patient", "doctor", "appointment", "lab report",
                   "department", "provider", "medical", "prescription", "billing", "health"],
    "real-estate": ["real estate", "property", "properties", "listing", "neighborhood",
                    "agent", "tour", "buyer", "seller", "realty", "mortgage"],
    "fitness": ["fitness", "gym", "trainer", "coach", "workout", "class schedule", "program",
                "member", "wellness", "session"],
    "restaurant": ["restaurant", "menu", "reservation", "table", "dining", "chef", "cafe",
                   "kitchen", "food ordering"],
    "education": ["course", "learning", "lesson", "student", "instructor", "enrollment",
                  "curriculum", "lms", "module", "academy"],
    "vehicle": ["vehicle", "car dealership", "dealership", "automotive", "test drive",
                "showroom", "financing", "motors"],
    "pos-erp": ["pos", "erp", "inventory", "stock", "grn", "goods receipt", "supplier",
                "warehouse", "branch", "invoice", "sku", "stock movement", "tyre shop", "purchase order"],
    "travel": ["travel", "tour package", "destination", "itinerary", "trip", "tourism", "guide"],
    "ecommerce": ["ecommerce", "online store", "shop", "product catalog", "cart", "checkout", "marketplace"],
    "ai-devtools": ["api", "developer tool", "devtool", "sdk", "automation", "deployment", "ai platform"],
    "fintech": ["fintech", "payment", "wallet", "transaction", "ledger", "banking", "invoice"],
    "saas": ["saas", "workspace", "productivity", "project management", "team", "workflow tool"],
    "community": ["community", "social network", "forum", "members", "creator", "feed"],
}


def detect_domain(prompt: str) -> str:
    low = " " + str(prompt or "").lower() + " "
    best, best_score = "saas", 0
    for domain, kws in DOMAIN_KEYWORDS.items():
        score = 0
        for kw in kws:
            if kw in low:
                score += 3 if " " in kw else 2
        if score > best_score:
            best, best_score = domain, score
    return best


# --------------------------------------------------------------------------- #
# Field / relationship / side-effect builders
# --------------------------------------------------------------------------- #

def f(name, ftype="text", required=False, enum=None, unique=False, label=None, ref=None):
    field = {"name": name, "type": ftype, "required": bool(required),
             "label": label or _title(name)}
    if enum:
        field["enum"] = list(enum)
    if unique:
        field["unique"] = True
    if ref:
        field["ref"] = ref
    return field


def r(target, cardinality="many-to-one", required=True, field=None, owner=False):
    return {"type": "ref", "target": target,
            "field": field or (_camel(target) + "Id"),
            "cardinality": cardinality, "required": bool(required), "owner": bool(owner)}


def se(on, action, target, field=None, note=""):
    """A relationship side effect, e.g. on create increment Doctor.appointmentCount."""
    return {"on": on, "action": action, "target": target, "field": field, "note": note}


def ent(name, fields=None, refs=None, indexes=None, embeds=None, workflows=None,
        side_effects=None, owner_of_user=False, unique=None, access=None):
    return {
        "name": name,
        "label": _title(name),
        "collection": _collection(name),
        "fields": list(fields or []),
        "relationships": list(refs or []),
        "indexes": list(indexes or []),
        "unique": list(unique or []),
        "embeds": list(embeds or []),
        "workflow_rules": list(workflows or []),
        "side_effects": list(side_effects or []),
        "owner_of_user": bool(owner_of_user),
        "access": dict(access or {}),
        "transactional": bool(side_effects),
    }


# --------------------------------------------------------------------------- #
# Domain relationship libraries (data, not app identities)
# --------------------------------------------------------------------------- #

def _healthcare():
    return {
        "roles": ["Admin", "Doctor", "Patient"],
        "entities": [
            ent("Patient",
                fields=[f("name", required=True), f("email", "email"), f("phone", "phone"),
                        f("dob", "date", label="Date of birth"),
                        f("gender", "enum", enum=["female", "male", "other"])],
                refs=[r("User", "one-to-one", required=False, owner=True)],
                indexes=["userId"]),
            ent("Department",
                fields=[f("name", required=True, unique=True), f("description", "textarea"),
                        f("phone", "phone")]),
            ent("Doctor",
                fields=[f("name", required=True), f("specialty", required=True),
                        f("email", "email"), f("phone", "phone"), f("photo", "image")],
                refs=[r("Department")],
                indexes=["departmentId"]),
            ent("Appointment",
                fields=[f("scheduledAt", "datetime", required=True, label="Scheduled at"),
                        f("status", "enum", required=True,
                          enum=["scheduled", "completed", "cancelled", "no-show"]),
                        f("reason", "textarea")],
                refs=[r("Patient"), r("Doctor"), r("Department", required=False)],
                indexes=["patientId", "doctorId", "departmentId", "scheduledAt"],
                workflows=["Slot must be free for the doctor at scheduledAt",
                           "Only Patient/Admin may create; Doctor/Admin may complete"],
                side_effects=[se("create", "increment", "Doctor", "appointmentCount",
                                 "doctor schedule load grows"),
                              se("create", "append-history", "Patient", "appointmentHistory",
                                 "patient appointment history"),
                              se("cancel", "decrement", "Doctor", "appointmentCount",
                                 "released slot")],
                access={"create": ["Patient", "Admin"], "update": ["Doctor", "Admin"]}),
            ent("LabReport",
                fields=[f("title", required=True), f("result", "textarea"),
                        f("status", "enum", enum=["pending", "ready", "reviewed"])],
                refs=[r("Patient"), r("Appointment", required=False)],
                indexes=["patientId", "appointmentId"]),
            ent("Bill",
                fields=[f("amount", "currency", required=True),
                        f("status", "enum", enum=["unpaid", "paid", "refunded"])],
                refs=[r("Patient"), r("Appointment", required=False)],
                indexes=["patientId"],
                side_effects=[se("pay", "set-status", "Bill", "status", "mark paid")]),
            ent("Prescription",
                fields=[f("medication", required=True), f("dosage"), f("notes", "textarea")],
                refs=[r("Patient"), r("Doctor")],
                indexes=["patientId", "doctorId"]),
        ],
    }


def _real_estate():
    return {
        "roles": ["Admin", "Agent", "Buyer", "Seller"],
        "entities": [
            ent("Agent",
                fields=[f("name", required=True), f("email", "email"), f("phone", "phone"),
                        f("bio", "textarea"), f("photo", "image")],
                refs=[r("User", "one-to-one", required=False, owner=True)]),
            ent("Neighborhood",
                fields=[f("name", required=True, unique=True), f("city"),
                        f("description", "textarea"), f("image", "image")]),
            ent("Property",
                fields=[f("title", required=True), f("price", "currency", required=True),
                        f("beds", "number"), f("baths", "number"), f("area", "number", label="Area (sqft)"),
                        f("address"), f("status", "enum", enum=["for-sale", "pending", "sold"]),
                        f("image", "image")],
                refs=[r("Agent"), r("Neighborhood"), r("User", "many-to-one", required=False, field="sellerId")],
                indexes=["agentId", "neighborhoodId", "status", "price"]),
            ent("TourBooking",
                fields=[f("scheduledAt", "datetime", required=True, label="Scheduled at"),
                        f("status", "enum", enum=["requested", "confirmed", "completed", "cancelled"]),
                        f("notes", "textarea")],
                refs=[r("Property"), r("Agent"), r("User")],
                indexes=["propertyId", "agentId", "userId", "scheduledAt"],
                workflows=["Property must be available", "Notify the assigned agent"],
                side_effects=[se("create", "increment", "Property", "tourCount", "tour interest grows"),
                              se("create", "notify", "Agent", None, "agent receives a lead notification")],
                access={"create": ["Buyer", "Admin"], "update": ["Agent", "Admin"]}),
            ent("Lead",
                fields=[f("name", required=True), f("email", "email"), f("phone", "phone"),
                        f("message", "textarea"),
                        f("status", "enum", enum=["new", "contacted", "qualified", "closed"])],
                refs=[r("Property", required=False), r("Agent")],
                indexes=["agentId", "propertyId"]),
            ent("SavedProperty",
                fields=[],
                refs=[r("User"), r("Property")],
                unique=["userId", "propertyId"], indexes=["userId"]),
        ],
    }


def _fitness():
    return {
        "roles": ["Admin", "Trainer", "Member"],
        "entities": [
            ent("Trainer",
                fields=[f("name", required=True), f("discipline"), f("bio", "textarea"),
                        f("photo", "image")],
                refs=[r("User", "one-to-one", required=False, owner=True)]),
            ent("Program",
                fields=[f("name", required=True),
                        f("level", "enum", enum=["beginner", "intermediate", "advanced"]),
                        f("description", "textarea")],
                refs=[r("Trainer", required=False)],
                indexes=["trainerId"]),
            ent("ClassSession",
                fields=[f("title", required=True), f("startsAt", "datetime", required=True, label="Starts at"),
                        f("capacity", "number", required=True),
                        f("seatsAvailable", "number", label="Seats available")],
                refs=[r("Trainer"), r("Program")],
                indexes=["trainerId", "programId", "startsAt"]),
            ent("Booking",
                fields=[f("status", "enum", enum=["booked", "attended", "cancelled"])],
                refs=[r("User", field="memberId"), r("ClassSession")],
                indexes=["memberId", "classSessionId"],
                workflows=["Class must have an available seat"],
                side_effects=[se("create", "decrement", "ClassSession", "seatsAvailable", "reserve a seat"),
                              se("create", "append-history", "User", "schedule", "member schedule"),
                              se("cancel", "increment", "ClassSession", "seatsAvailable", "release seat")],
                access={"create": ["Member", "Admin"]}),
            ent("MemberProgress",
                fields=[f("metric", required=True), f("value", "number", required=True),
                        f("recordedAt", "date", label="Recorded at")],
                refs=[r("User", field="memberId"), r("Program", required=False)],
                indexes=["memberId", "programId"]),
            ent("Payment",
                fields=[f("amount", "currency", required=True),
                        f("status", "enum", enum=["pending", "paid", "refunded"])],
                refs=[r("User", field="memberId"), r("Booking", required=False)],
                indexes=["memberId"]),
        ],
    }


def _restaurant():
    return {
        "roles": ["Admin", "Staff", "Customer"],
        "entities": [
            ent("Category", fields=[f("name", required=True, unique=True)]),
            ent("MenuItem",
                fields=[f("name", required=True), f("price", "currency", required=True),
                        f("description", "textarea"), f("image", "image"),
                        f("available", "boolean")],
                refs=[r("Category")],
                indexes=["categoryId"]),
            ent("RestaurantTable",
                fields=[f("number", "number", required=True, unique=True, label="Table number"),
                        f("seats", "number"), f("status", "enum", enum=["free", "reserved", "occupied"])]),
            ent("Reservation",
                fields=[f("dateTime", "datetime", required=True, label="Date & time"),
                        f("partySize", "number", required=True, label="Party size"),
                        f("status", "enum", enum=["requested", "confirmed", "seated", "cancelled"])],
                refs=[r("User", field="customerId"), r("RestaurantTable")],
                indexes=["customerId", "restaurantTableId", "dateTime"],
                workflows=["Table must be free at the requested time"],
                side_effects=[se("create", "set-status", "RestaurantTable", "status", "table becomes reserved")],
                access={"create": ["Customer", "Admin"]}),
            ent("Order",
                fields=[f("status", "enum", enum=["open", "preparing", "served", "paid"]),
                        f("total", "currency")],
                refs=[r("User", field="customerId", required=False), r("RestaurantTable", required=False)],
                embeds=[{"name": "items", "of": "MenuItem", "fields": ["menuItemId", "qty", "price"]}],
                indexes=["customerId"],
                side_effects=[se("create", "create-children", "OrderItem", None, "order line items"),
                              se("create", "set-status", "RestaurantTable", "status", "table becomes occupied")]),
        ],
    }


def _education():
    return {
        "roles": ["Admin", "Instructor", "Student"],
        "entities": [
            ent("Instructor",
                fields=[f("name", required=True), f("bio", "textarea"), f("photo", "image")],
                refs=[r("User", "one-to-one", required=False, owner=True)]),
            ent("Course",
                fields=[f("title", required=True), f("level", "enum",
                        enum=["beginner", "intermediate", "advanced"]),
                        f("description", "textarea"), f("image", "image")],
                refs=[r("Instructor", owner=True)],
                indexes=["instructorId"]),
            ent("Module",
                fields=[f("title", required=True), f("order", "number")],
                refs=[r("Course")], indexes=["courseId"]),
            ent("Lesson",
                fields=[f("title", required=True), f("content", "textarea"),
                        f("durationMin", "number", label="Duration (min)")],
                refs=[r("Module")], indexes=["moduleId"]),
            ent("Enrollment",
                fields=[f("status", "enum", enum=["active", "completed", "dropped"])],
                refs=[r("User", field="studentId"), r("Course")],
                indexes=["studentId", "courseId"],
                workflows=["Student may enroll once per course"],
                side_effects=[se("create", "create-children", "Progress", None,
                                 "create a progress record per lesson")],
                unique=["studentId", "courseId"],
                access={"create": ["Student", "Admin"]}),
            ent("Progress",
                fields=[f("completed", "boolean"), f("score", "number")],
                refs=[r("Enrollment"), r("Lesson")],
                indexes=["enrollmentId", "lessonId"]),
        ],
    }


def _vehicle():
    return {
        "roles": ["Admin", "Sales", "Buyer"],
        "entities": [
            ent("Brand", fields=[f("name", required=True, unique=True)]),
            ent("VehicleCategory", fields=[f("name", required=True, unique=True, label="Category")]),
            ent("Vehicle",
                fields=[f("name", required=True), f("price", "currency", required=True),
                        f("year", "number"), f("mileage", "number"),
                        f("fuel", "enum", enum=["petrol", "diesel", "electric", "hybrid"]),
                        f("status", "enum", enum=["available", "reserved", "sold"]), f("image", "image")],
                refs=[r("Brand"), r("VehicleCategory")],
                indexes=["brandId", "vehicleCategoryId", "status", "price"]),
            ent("TestDrive",
                fields=[f("scheduledAt", "datetime", required=True, label="Scheduled at"),
                        f("status", "enum", enum=["requested", "confirmed", "completed", "cancelled"])],
                refs=[r("Vehicle"), r("User", field="customerId"),
                      r("User", required=False, field="salespersonId")],
                indexes=["vehicleId", "customerId", "scheduledAt"],
                side_effects=[se("create", "increment", "Vehicle", "testDriveCount", "interest grows")],
                access={"create": ["Buyer", "Admin"]}),
            ent("Sale",
                fields=[f("price", "currency", required=True), f("date", "date")],
                refs=[r("Vehicle"), r("User", field="customerId"), r("User", field="salespersonId")],
                indexes=["vehicleId", "customerId"],
                side_effects=[se("create", "set-status", "Vehicle", "status", "vehicle becomes sold")]),
            ent("FinanceApplication",
                fields=[f("amount", "currency", required=True), f("term", "number", label="Term (months)"),
                        f("status", "enum", enum=["submitted", "approved", "rejected"])],
                refs=[r("User", field="customerId"), r("Vehicle")],
                indexes=["customerId", "vehicleId"]),
        ],
    }


def _pos_erp():
    return {
        "roles": ["Admin", "Manager", "Cashier", "Warehouse"],
        "entities": [
            ent("Brand", fields=[f("name", required=True, unique=True)]),
            ent("Category", fields=[f("name", required=True, unique=True)]),
            ent("Supplier", fields=[f("name", required=True), f("email", "email"), f("phone", "phone")]),
            ent("Branch", fields=[f("name", required=True, unique=True), f("address")]),
            ent("Product",
                fields=[f("name", required=True), f("sku", required=True, unique=True, label="SKU"),
                        f("price", "currency", required=True), f("cost", "currency")],
                refs=[r("Brand"), r("Category"), r("Supplier", required=False)],
                indexes=["brandId", "categoryId", "supplierId", "sku"]),
            ent("Stock",
                fields=[f("quantity", "number", required=True), f("batch")],
                refs=[r("Product"), r("Branch")],
                indexes=["productId", "branchId"], unique=["productId", "branchId", "batch"]),
            ent("GRN",
                fields=[f("reference", required=True, label="GRN reference"), f("receivedAt", "date")],
                refs=[r("Supplier"), r("Branch")],
                embeds=[{"name": "items", "of": "Product", "fields": ["productId", "qty", "cost"]}],
                workflows=["A GRN adds received quantities into Stock"],
                side_effects=[se("create", "increment", "Stock", "quantity", "received goods raise stock"),
                              se("create", "create-children", "StockMovement", None, "movement type=in")]),
            ent("Invoice",
                fields=[f("number", required=True, unique=True, label="Invoice number"),
                        f("total", "currency"),
                        f("status", "enum", enum=["draft", "issued", "paid", "void"])],
                refs=[r("User", field="customerId", required=False), r("Branch")],
                embeds=[{"name": "items", "of": "Product", "fields": ["productId", "qty", "price"]}],
                indexes=["customerId", "branchId", "number"],
                workflows=["Issuing an invoice reduces stock and records a stock movement"],
                side_effects=[se("create", "create-children", "InvoiceItem", None, "line items"),
                              se("create", "decrement", "Stock", "quantity", "sold goods reduce stock"),
                              se("create", "create-children", "StockMovement", None, "movement type=out")]),
            ent("InvoiceItem",
                fields=[f("qty", "number", required=True), f("price", "currency", required=True)],
                refs=[r("Invoice"), r("Product")],
                indexes=["invoiceId", "productId"]),
            ent("Payment",
                fields=[f("amount", "currency", required=True),
                        f("method", "enum", enum=["cash", "card", "transfer"])],
                refs=[r("Invoice")], indexes=["invoiceId"],
                side_effects=[se("create", "set-status", "Invoice", "status", "invoice marked paid")]),
            ent("StockMovement",
                fields=[f("type", "enum", required=True, enum=["in", "out", "adjust"]),
                        f("qty", "number", required=True)],
                refs=[r("Product"), r("Branch"), r("GRN", required=False), r("Invoice", required=False)],
                indexes=["productId", "branchId"]),
            ent("Customer", fields=[f("name", required=True), f("email", "email"), f("phone", "phone")]),
            ent("Employee",
                fields=[f("name", required=True), f("role", "enum", enum=["manager", "cashier", "warehouse"])],
                refs=[r("Branch", required=False)]),
        ],
    }


_DOMAIN_LIBRARY = {
    "healthcare": _healthcare,
    "real-estate": _real_estate,
    "fitness": _fitness,
    "restaurant": _restaurant,
    "education": _education,
    "vehicle": _vehicle,
    "pos-erp": _pos_erp,
}


# --------------------------------------------------------------------------- #
# Generic extraction for unseen / under-specified domains
# --------------------------------------------------------------------------- #

# Words in a prompt that imply a transactional entity (gets refs to a customer
# + the main catalog entity, and a status field).
_TRANSACTION_HINTS = {"booking", "order", "invoice", "tour", "reservation", "appointment",
                      "enrollment", "sale", "lead", "testdrive", "subscription", "ticket",
                      "request", "payment", "shipment", "transaction"}
_CATALOG_HINTS = {"product", "item", "listing", "property", "vehicle", "course", "program",
                  "menu", "service", "destination", "package", "class", "plan"}
_STOPWORDS = {"with", "and", "the", "for", "app", "platform", "website", "system", "create",
              "build", "make", "a", "an", "of", "to", "management", "admin", "real", "estate",
              "online", "data", "page", "pages", "support", "login", "register", "dashboard"}


def _singular(word):
    w = word.lower()
    if w.endswith("ies"):
        return w[:-3] + "y"
    if w.endswith("sses") or w.endswith("ches") or w.endswith("shes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _candidate_entities_from_prompt(prompt):
    tokens = re.findall(r"[A-Za-z][A-Za-z-]+", str(prompt or ""))
    seen, out = set(), []
    for tok in tokens:
        base = _singular(tok)
        if base in _STOPWORDS or len(base) < 3:
            continue
        name = _title(base).replace(" ", "")
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        out.append(name)
    return out


def _generic_model(prompt, domain):
    """Build a model when no curated domain library matches. Infers a catalog
    entity, transactional entities, and User relationships from the prompt."""
    words = set(_singular(w) for w in re.findall(r"[A-Za-z]+", str(prompt or "").lower()))
    entities, names = [], []

    catalog = next((c for c in _CATALOG_HINTS if c in words), "item")
    catalog_name = _title(catalog)
    entities.append(ent(catalog_name,
                        fields=[f("name", required=True), f("description", "textarea"),
                                f("price", "currency"), f("status", "enum",
                                enum=["active", "inactive"]), f("image", "image")]))
    names.append(catalog_name)

    transactions = [t for t in _TRANSACTION_HINTS if t in words]
    for t in transactions[:4]:
        tn = _title(t).replace(" ", "")
        if tn in names:
            continue
        entities.append(ent(tn,
                            fields=[f("status", "enum", enum=["new", "in-progress", "done", "cancelled"]),
                                    f("amount", "currency")],
                            refs=[r("User", field="customerId"), r(catalog_name, required=False)],
                            indexes=["customerId", _camel(catalog_name) + "Id"],
                            side_effects=[se("create", "append-history", "User", "history",
                                             "linked to the acting user")]))
        names.append(tn)

    if len(entities) < 2:  # ensure at least a second related entity
        entities.append(ent("Category", fields=[f("name", required=True, unique=True)]))
        entities[0]["relationships"].append(r("Category", required=False))
        names.append("Category")
    return {"roles": ["Admin", "User"], "entities": entities}


# --------------------------------------------------------------------------- #
# Role / auth inference
# --------------------------------------------------------------------------- #

_ROLE_HINTS = {
    "patient": "Patient", "provider": "Provider", "doctor": "Doctor", "nurse": "Nurse",
    "agent": "Agent", "buyer": "Buyer", "seller": "Seller", "landlord": "Landlord",
    "trainer": "Trainer", "coach": "Coach", "member": "Member",
    "customer": "Customer", "staff": "Staff", "host": "Host", "guest": "Guest",
    "student": "Student", "instructor": "Instructor", "teacher": "Teacher",
    "manager": "Manager", "cashier": "Cashier", "warehouse": "Warehouse",
    "sales": "Sales", "developer": "Developer", "operator": "Operator", "admin": "Admin",
}


def infer_roles(prompt, domain, library_roles):
    low = str(prompt or "").lower()
    roles = list(library_roles or [])
    for kw, role in _ROLE_HINTS.items():
        if kw in low and role not in roles:
            roles.append(role)
    if "Admin" not in roles:
        roles.insert(0, "Admin")
    # de-dup preserving order
    out, seen = [], set()
    for role in roles:
        if role not in seen:
            seen.add(role)
            out.append(role)
    return out[:6]


def auth_required(prompt, entities):
    low = str(prompt or "").lower()
    if any(w in low for w in ("login", "auth", "account", "role", "portal", "admin", "sign in", "sign up")):
        return True
    # Transactional / owned entities imply authenticated users.
    return any(e.get("transactional") or any(rel.get("target") == "User" for rel in e["relationships"])
               for e in entities)


# --------------------------------------------------------------------------- #
# Assembly + validation
# --------------------------------------------------------------------------- #

def _user_entity(roles):
    return ent("User",
               fields=[f("name", required=True), f("email", "email", required=True, unique=True),
                       f("password", "password", required=True),
                       f("role", "enum", required=True, enum=[role for role in roles]),
                       f("phone", "phone")],
               indexes=["email", "role"])


# --------------------------------------------------------------------------- #
# SRS-authoritative model construction (when a rich SRS - real fields/
# relationships, not just bare entity names - is provided, it REPLACES the
# domain-library/generic guess entirely rather than just padding it).
# --------------------------------------------------------------------------- #

# Duplicated from srs.py deliberately (not imported) - the two modules have
# stayed independent of each other by design; this is a 5-item set literal,
# not worth a cross-module coupling for.
_AUTH_TABLE_NAMES = {"user", "role", "permission", "rolepermission", "auditlog", "session"}

_SRS_CARDINALITY_MAP = {
    "many_to_one": "many-to-one", "one_to_many": "one-to-many",
    "many_to_many": "many-to-many", "one_to_one": "one-to-one",
}


def _map_cardinality(t):
    return _SRS_CARDINALITY_MAP.get(str(t or "").strip().lower(), str(t or "many-to-one").replace("_", "-"))


def _fields_from_srs(norm_fields):
    """Adapter from srs.py's already-normalized field shape (name/label/type/
    options/required) into this module's f(...) builder. srs.py emits the type
    string "select" for the same concept this module calls "enum"."""
    out = []
    for nf in norm_fields or []:
        ftype = "enum" if nf.get("type") == "select" else nf.get("type", "text")
        out.append(f(nf["name"], ftype, required=bool(nf.get("required")),
                     enum=nf.get("options"), label=nf.get("label")))
    return out


def _entities_from_srs(srs: dict):
    """Build the COMPLETE entity list straight from a rich SRS (real fields and/or
    relationships - not the bare {"name": ...} shape some callers still pass).
    Returns None when the SRS isn't rich enough, so callers fall through to the
    domain-library/generic-model path unchanged."""
    if not isinstance(srs, dict):
        return None
    raw = srs.get("entities") or []
    if not (raw and any(len(e.get("fields") or []) >= 2 for e in raw)):
        return None

    by_table, by_name = {}, {}
    for e in raw:
        built = ent(e["name"], fields=_fields_from_srs(e.get("fields")))
        table_key = e.get("_table") or e["name"].lower()
        by_table[table_key] = built
        by_name[e["name"]] = built

    for rel in srs.get("relationships") or []:
        src_e = by_table.get(rel.get("from_table"))
        if not src_e:
            continue
        to_table = rel.get("to_table") or ""
        if to_table in _AUTH_TABLE_NAMES or to_table.rstrip("s") in _AUTH_TABLE_NAMES:
            tgt_name = "User"          # FK into users/roles/etc -> the auto-built User entity
        else:
            tgt_e = by_table.get(to_table)
            tgt_name = tgt_e["name"] if tgt_e else None
        if not tgt_name or tgt_name == src_e["name"]:
            continue
        cardinality = _map_cardinality(rel.get("type"))
        field_name = _camel(rel["from_field"]) if rel.get("from_field") else _camel(tgt_name) + "Id"
        src_e["relationships"].append(r(tgt_name, cardinality, field=field_name))

    access_map = srs.get("entity_access") or {}
    for nm, access in access_map.items():
        if nm in by_name:
            by_name[nm]["access"] = access

    # Wire SRS business_workflows to the most-relevant entity's workflow_rules.
    # Matching is keyword-based: a workflow whose name/steps mention an entity's
    # name tokens gets its step list appended to that entity's workflow_rules.
    _stop = {"the", "and", "for", "with", "from", "into", "that", "this", "then",
             "each", "user", "admin", "system", "page", "open", "click", "print"}
    for wf in (srs.get("business_workflows") or []):
        if not isinstance(wf, dict):
            continue
        steps = [str(s) for s in (wf.get("steps") or [])]
        wf_text = (wf.get("name") or "") + " " + " ".join(steps)
        wf_low = re.sub(r"[^a-z0-9 ]", " ", wf_text.lower())
        best_e, best_score = None, 0
        for nm, e in by_name.items():
            toks = {t for t in re.findall(r"[a-z]{4,}", nm.lower()) if t not in _stop}
            toks |= {t for t in re.findall(r"[a-z]{4,}", e.get("label", "").lower()) if t not in _stop}
            score = sum(1 for t in toks if re.search(r"\b" + re.escape(t), wf_low))
            if score > best_score:
                best_e, best_score = e, score
        if best_e is not None and best_score >= 1:
            best_e.setdefault("workflow_rules", [])
            best_e["workflow_rules"].extend(steps[:8])

    return {"roles": srs.get("roles") or [], "entities": list(by_name.values()),
            "srs_workflows": srs.get("business_workflows") or [],
            "srs_notifications": srs.get("notification_requirements") or [],
            "srs_reports": srs.get("reporting_requirements") or [],
            "srs_security": srs.get("security_requirements") or [],
            "srs_ui_ux": srs.get("ui_ux_requirements") or {},
            "srs_acceptance": srs.get("acceptance_criteria") or [],
            "srs_future": srs.get("future_enhancements") or [],
            "srs_validation": srs.get("validation_rules") or [],
            "srs_auth": srs.get("authentication_requirement") or {},
            "srs_modules": srs.get("main_modules") or [],
            "srs_system_category": srs.get("system_category") or "",
            }


def plan_data_model(prompt: str, app_name: str = None, srs: dict = None) -> dict:
    """Plan a relationship-aware data model from a prompt (and optional SRS)."""
    prompt = str(prompt or "")
    domain = detect_domain(prompt)               # cosmetic when SRS is authoritative
                                                   # (dashboard title lookup only) - does
                                                   # NOT gate which entities get built below.

    srs_base = _entities_from_srs(srs)
    if srs_base is not None:
        base = srs_base
        roles = list(srs_base["roles"]) or ["Admin", "User"]
    else:
        builder = _DOMAIN_LIBRARY.get(domain)
        base = builder() if builder else _generic_model(prompt, domain)
        roles = infer_roles(prompt, domain, base.get("roles"))

    entities = copy.deepcopy(base["entities"])
    # Extra SRS-derived metadata keys (passed through from _entities_from_srs)
    _srs_extra = {k: base.get(k, base.get(k[4:], [])) for k in (
        "srs_workflows", "srs_notifications", "srs_reports", "srs_security",
        "srs_ui_ux", "srs_acceptance", "srs_future", "srs_validation",
        "srs_auth", "srs_modules", "srs_system_category",
    )} if srs_base is not None else {}

    # SRS entity overrides/additions (generic, optional) - only when the SRS
    # WASN'T rich enough to be authoritative above (bare {"name": ...} shape).
    if srs_base is None and isinstance(srs, dict) and isinstance(srs.get("entities"), list):
        existing = {e["name"].lower() for e in entities}
        for se_ in srs["entities"]:
            nm = _title(str(se_.get("name") or "")).replace(" ", "")
            if nm and nm.lower() not in existing:
                entities.append(ent(nm, fields=[f("name", required=True),
                                                f("status", "enum", enum=["active", "inactive"])]))
                existing.add(nm.lower())

    needs_auth = auth_required(prompt, entities) or bool(srs_base)   # an SRS with explicit
                                                                       # roles always implies login
    if needs_auth:
        entities.insert(0, _user_entity(roles))

    entities = _validate_and_link(entities)
    model = {
        "app_name": app_name or _infer_app_name(prompt, domain),
        "domain": domain,
        "auth_required": needs_auth,
        "roles": roles,
        "entity_count": len(entities),
        "entities": entities,
        "relationships_summary": _relationship_summary(entities),
        "workflows": _workflow_summary(entities),
        "generated_by": "data_model_planner",
        **_srs_extra,   # propagate all SRS coverage sections (workflows, notifications, reports, etc.)
    }
    return model


def _validate_and_link(entities):
    """Drop refs whose target isn't in the model; compute derived fields and
    referenced-by back-links; mark embedded child collections."""
    names = {e["name"] for e in entities}
    for e in entities:
        e["relationships"] = [rel for rel in e["relationships"]
                              if rel["target"] in names or rel["target"] == "User"]
        # ensure every ref field is an index for query performance
        for rel in e["relationships"]:
            if rel["field"] not in e["indexes"]:
                e["indexes"].append(rel["field"])
        # derived fields used by side effects (counters)
        for eff in e["side_effects"]:
            if eff["action"] in ("increment", "decrement") and eff.get("field"):
                _ensure_counter(entities, eff["target"], eff["field"])
    # referenced_by back-links
    ref_map = {}
    for e in entities:
        for rel in e["relationships"]:
            ref_map.setdefault(rel["target"], []).append({"entity": e["name"], "field": rel["field"]})
    for e in entities:
        e["referenced_by"] = ref_map.get(e["name"], [])
    return entities


def _ensure_counter(entities, target_name, field):
    for e in entities:
        if e["name"] == target_name:
            if not any(fl["name"] == field for fl in e["fields"]):
                e["fields"].append(f(field, "number", label=_title(field)))
            return


def _relationship_summary(entities):
    out = []
    for e in entities:
        for rel in e["relationships"]:
            out.append(f"{e['name']} -> {rel['target']} ({rel['cardinality']}, {rel['field']})")
    return out


def _workflow_summary(entities):
    out = []
    for e in entities:
        for eff in e["side_effects"]:
            tgt = f"{eff['target']}.{eff['field']}" if eff.get("field") else eff["target"]
            out.append(f"on {eff['on']} {e['name']}: {eff['action']} {tgt}"
                       + (f" — {eff['note']}" if eff.get("note") else ""))
    return out


def _infer_app_name(prompt, domain):
    # Neutral, non-branded working title derived from the domain (never a real brand).
    return _title(domain.replace("-", " ")) + " Platform"


def write_data_model(out_dir: str, model: dict, filename: str = "app_data_model.json") -> str:
    path = os.path.join(out_dir, filename)
    try:
        os.makedirs(out_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(model, fh, indent=2)
    except OSError:
        pass
    return path


# --------------------------------------------------------------------------- #
# small text helpers
# --------------------------------------------------------------------------- #

def _title(name):
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(name or ""))
    s = re.sub(r"[_-]+", " ", s).strip()
    return " ".join(w[:1].upper() + w[1:] for w in s.split()) or "Item"


def _camel(name):
    parts = re.split(r"[\s_-]+", str(name or ""))
    if not parts:
        return "item"
    head = parts[0]
    head = head[:1].lower() + head[1:]
    return head + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def _collection(name):
    base = _camel(name)
    if base.endswith("y") and base[-2:-1] not in "aeiou":
        return base[:-1] + "ies"
    if base.endswith(("s", "x", "z", "ch", "sh")):
        return base + "es"
    return base + "s"
