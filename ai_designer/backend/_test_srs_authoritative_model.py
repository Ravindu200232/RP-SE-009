"""SRS-authoritative data model regression test.

Proves a rich SRS JSON (real fields/relationships/role_access_matrix - not just
bare entity names) becomes the AUTHORITATIVE source for plan_data_model(),
instead of being reduced to name-only padding on a domain-guessed model.
Uses a real-world hotel-management SRS (the exact shape a user provided) as
the fixture: srs_document wrapper, roles as {role_key,role_name} objects,
database_design.tables with typed/FK fields, public_landing_website.pages,
application_pages, and role_access_matrix.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import srs
from app import data_model_planner as dmp

RESULTS = []


def rec(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""), flush=True)


HOTEL_SRS = r"""
{
  "srs_document": {
    "project_name": "GrandVista Hotel Management Platform",
    "app_summary": {"app_name": "GrandVista Hotel Management Platform"},
    "roles": [
      {"role_key": "super_admin", "role_name": "Super Admin"},
      {"role_key": "admin", "role_name": "Hotel Admin"},
      {"role_key": "manager", "role_name": "Hotel Manager"},
      {"role_key": "receptionist", "role_name": "Receptionist"},
      {"role_key": "cashier", "role_name": "Cashier / POS Operator"},
      {"role_key": "housekeeping", "role_name": "Housekeeping Staff"},
      {"role_key": "inventory_manager", "role_name": "Inventory Manager"},
      {"role_key": "accountant", "role_name": "Accountant"},
      {"role_key": "customer", "role_name": "Registered Customer"},
      {"role_key": "guest", "role_name": "Public Guest"}
    ],
    "database_design": {
      "tables": [
        {"table_name": "users", "fields": [{"name":"id","type":"uuid","primary_key":true},{"name":"full_name","type":"string"},{"name":"role_id","type":"foreign_key","references":"roles.id"}]},
        {"table_name": "roles", "fields": [{"name":"id","type":"uuid","primary_key":true},{"name":"role_name","type":"string"}]},
        {"table_name": "permissions", "fields": [{"name":"id","type":"uuid","primary_key":true}]},
        {"table_name": "role_permissions", "fields": [{"name":"role_id","type":"foreign_key","references":"roles.id"},{"name":"permission_id","type":"foreign_key","references":"permissions.id"}]},
        {"table_name": "hotels", "fields": [{"name":"id","type":"uuid","primary_key":true},{"name":"hotel_name","type":"string","nullable":false},{"name":"status","type":"enum","values":["active","inactive"]}]},
        {"table_name": "room_types", "fields": [{"name":"id","type":"uuid","primary_key":true},{"name":"hotel_id","type":"foreign_key","references":"hotels.id"},{"name":"type_name","type":"string","nullable":false},{"name":"base_price_per_night","type":"decimal","nullable":false}]},
        {"table_name": "rooms", "fields": [{"name":"id","type":"uuid","primary_key":true},{"name":"hotel_id","type":"foreign_key","references":"hotels.id"},{"name":"room_type_id","type":"foreign_key","references":"room_types.id"},{"name":"room_number","type":"string","unique":true},{"name":"status","type":"enum","values":["available","occupied","reserved","cleaning","maintenance","inactive"]}]},
        {"table_name": "guests", "fields": [{"name":"id","type":"uuid","primary_key":true},{"name":"user_id","type":"foreign_key","references":"users.id","nullable":true},{"name":"full_name","type":"string"}]},
        {"table_name": "reservations", "fields": [{"name":"id","type":"uuid","primary_key":true},{"name":"guest_id","type":"foreign_key","references":"guests.id"},{"name":"room_type_id","type":"foreign_key","references":"room_types.id"},{"name":"room_id","type":"foreign_key","references":"rooms.id","nullable":true},{"name":"status","type":"enum","values":["pending","confirmed","checked_in","checked_out","cancelled","no_show"]}]},
        {"table_name": "payments", "fields": [{"name":"id","type":"uuid","primary_key":true},{"name":"reservation_id","type":"foreign_key","references":"reservations.id","nullable":true},{"name":"invoice_id","type":"foreign_key","references":"invoices.id","nullable":true},{"name":"amount","type":"decimal"}]},
        {"table_name": "invoices", "fields": [{"name":"id","type":"uuid","primary_key":true},{"name":"guest_id","type":"foreign_key","references":"guests.id","nullable":true},{"name":"reservation_id","type":"foreign_key","references":"reservations.id","nullable":true},{"name":"grand_total","type":"decimal"}]},
        {"table_name": "pos_orders", "fields": [{"name":"id","type":"uuid","primary_key":true},{"name":"guest_id","type":"foreign_key","references":"guests.id","nullable":true},{"name":"reservation_id","type":"foreign_key","references":"reservations.id","nullable":true},{"name":"total_amount","type":"decimal"}]},
        {"table_name": "pos_order_items", "fields": [{"name":"id","type":"uuid","primary_key":true},{"name":"pos_order_id","type":"foreign_key","references":"pos_orders.id"},{"name":"menu_item_id","type":"foreign_key","references":"menu_items.id"},{"name":"quantity","type":"integer"}]},
        {"table_name": "menu_items", "fields": [{"name":"id","type":"uuid","primary_key":true},{"name":"item_name","type":"string"},{"name":"price","type":"decimal"}]},
        {"table_name": "housekeeping_tasks", "fields": [{"name":"id","type":"uuid","primary_key":true},{"name":"room_id","type":"foreign_key","references":"rooms.id"},{"name":"assigned_to","type":"foreign_key","references":"users.id"},{"name":"status","type":"enum","values":["pending","in_progress","completed","cancelled"]}]},
        {"table_name": "inventory_items", "fields": [{"name":"id","type":"uuid","primary_key":true},{"name":"item_name","type":"string"},{"name":"current_stock","type":"decimal"}]},
        {"table_name": "suppliers", "fields": [{"name":"id","type":"uuid","primary_key":true},{"name":"supplier_name","type":"string"}]},
        {"table_name": "stock_movements", "fields": [{"name":"id","type":"uuid","primary_key":true},{"name":"inventory_item_id","type":"foreign_key","references":"inventory_items.id"},{"name":"created_by","type":"foreign_key","references":"users.id"},{"name":"quantity","type":"decimal"}]},
        {"table_name": "staff_profiles", "fields": [{"name":"id","type":"uuid","primary_key":true},{"name":"user_id","type":"foreign_key","references":"users.id"},{"name":"job_title","type":"string"}]},
        {"table_name": "audit_logs", "fields": [{"name":"id","type":"uuid","primary_key":true},{"name":"user_id","type":"foreign_key","references":"users.id","nullable":true},{"name":"action","type":"string"}]}
      ],
      "relationships": [
        {"from": "users.role_id", "to": "roles.id", "type": "many_to_one"},
        {"from": "hotels.id", "to": "room_types.hotel_id", "type": "one_to_many"},
        {"from": "room_types.id", "to": "rooms.room_type_id", "type": "one_to_many"}
      ]
    },
    "public_landing_website": {"pages": [
      {"page_name": "Home Page", "route": "/"}, {"page_name": "Rooms Page", "route": "/rooms"},
      {"page_name": "Facilities Page", "route": "/facilities"}, {"page_name": "About Page", "route": "/about"},
      {"page_name": "Contact Page", "route": "/contact"}
    ]},
    "application_pages": [
      {"page_name": "Room Management", "route": "/admin/rooms", "allowed_roles": ["super_admin", "admin", "manager"], "functions": ["Create room type", "Create room", "Edit room", "Change room status"]},
      {"page_name": "Reservation Management", "route": "/admin/reservations", "allowed_roles": ["super_admin", "admin", "manager", "receptionist"], "functions": ["Create reservation", "Assign room", "Check-in guest", "Check-out guest"]},
      {"page_name": "POS System", "route": "/pos", "allowed_roles": ["super_admin", "admin", "manager", "cashier"], "functions": ["Create restaurant order", "Accept cash/card payment"]},
      {"page_name": "Housekeeping Board", "route": "/admin/housekeeping", "allowed_roles": ["super_admin", "admin", "manager", "housekeeping"], "functions": ["Update cleaning status", "Mark room cleaned"]},
      {"page_name": "Inventory Management", "route": "/admin/inventory", "allowed_roles": ["super_admin", "admin", "manager", "inventory_manager"], "functions": ["Create inventory item", "Update stock", "Manage suppliers"]},
      {"page_name": "Billing and Finance", "route": "/admin/billing", "allowed_roles": ["super_admin", "admin", "manager", "accountant"], "functions": ["View invoices", "Record payment", "Process refund"]}
    ],
    "role_access_matrix": [
      {"role": "receptionist", "allowed_functions": ["Create reservation", "Assign room", "Check-in guest", "Check-out guest"], "restricted_functions": []},
      {"role": "manager", "allowed_functions": ["Manage reservations", "Manage daily operations"], "restricted_functions": []},
      {"role": "admin", "allowed_functions": ["Manage hotel setup", "Manage rooms", "Manage reservations"], "restricted_functions": []},
      {"role": "super_admin", "allowed_functions": ["Full system access"], "restricted_functions": []}
    ],
    "functional_requirements": [
      {"id": "FR-001", "module": "Public Website", "requirement": "Public hotel website with home, rooms, facilities, about, contact."}
    ]
  }
}
"""


def main():
    print("=" * 72)
    print("SRS-AUTHORITATIVE DATA MODEL")
    print("=" * 72)

    parsed = srs.parse_srs_input(HOTEL_SRS)
    rec("1. parse_srs_input recognizes the srs_document schema", parsed is not None)
    if parsed is None:
        print("ABORT: parsing failed, cannot continue")
        sys.exit(1)

    rec("2. app_name resolved from project_name/app_summary", parsed["app_name"] == "GrandVista Hotel Management Platform")

    non_guest_roles = [r for r in parsed["roles"] if r.lower() != "public guest"]
    rec("3. all 9 non-guest roles present (no [:6] cap)", len(non_guest_roles) == 9, {"roles": parsed["roles"]})

    ent_names = {e["name"] for e in parsed["entities"]}
    rec("4. 15 business entities extracted (not 20 - auth tables excluded)",
        len(parsed["entities"]) == 15, {"count": len(parsed["entities"])})
    rec("5. auth/RBAC tables are NOT separate entities",
        not ({"User", "Role", "Permission", "RolePermission", "AuditLog"} & ent_names), {"entities": sorted(ent_names)})
    rec("6. entity names are singular (Hotel not Hotels - avoids double-pluralized collections)",
        "Hotel" in ent_names and "Hotels" not in ent_names and "Room" in ent_names and "Rooms" not in ent_names)

    model = dmp.plan_data_model("hotel management system", app_name=parsed["app_name"], srs=parsed)
    model_ents = {e["name"]: e for e in model["entities"]}
    business_ents = {n: e for n, e in model_ents.items() if n != "User"}

    rec("7. plan_data_model used the SRS as authoritative (same entity count, not collapsed to generic fallback)",
        len(business_ents) == 15, {"count": len(business_ents)})
    rec("8. all 9 non-guest roles flow into the model", all(r in model["roles"] for r in non_guest_roles))

    def has_ref(entity_name, target_name):
        e = model_ents.get(entity_name)
        return bool(e) and any(rel["target"] == target_name for rel in e["relationships"])

    rec("9. Reservation -> Guest relationship resolves", has_ref("Reservation", "Guest"))
    rec("10. Reservation -> RoomType relationship resolves", has_ref("Reservation", "RoomType"))
    rec("11. PosOrderItem -> PosOrder relationship resolves", has_ref("PosOrderItem", "PosOrder"))
    rec("12. PosOrderItem -> MenuItem relationship resolves", has_ref("PosOrderItem", "MenuItem"))
    rec("13. HousekeepingTask -> User relationship resolves (FK into an excluded auth table -> User, not dropped)",
        has_ref("HousekeepingTask", "User"))

    room_access = model_ents.get("Room", {}).get("access") or {}
    room_roles = set(room_access.get("create", []) + room_access.get("update", []))
    rec("14. Room access includes a manager-equivalent role (Hotel Manager)", "Hotel Manager" in room_roles, room_roles)

    resv_access = model_ents.get("Reservation", {}).get("access") or {}
    resv_roles = set(sum(resv_access.values(), []))
    rec("15. Reservation access includes Receptionist", "Receptionist" in resv_roles, resv_roles)

    pos_access = model_ents.get("PosOrder", {}).get("access") or {}
    pos_roles = set(sum(pos_access.values(), []))
    rec("16. PosOrder access includes Cashier / POS Operator", "Cashier / POS Operator" in pos_roles, pos_roles)

    print("=" * 72)
    ok = all(RESULTS)
    print(f"SRS-AUTHORITATIVE MODEL GREEN ({sum(RESULTS)}/{len(RESULTS)})" if ok else f"FAILURES ({sum(RESULTS)}/{len(RESULTS)} passed)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
