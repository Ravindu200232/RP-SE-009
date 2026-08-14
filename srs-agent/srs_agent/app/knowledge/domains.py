"""Domain knowledge library.

This is a *template library*, not hard-coded output. Each domain contributes
genuinely different roles / modules / tables / workflows. The classifier picks
a domain from the brief, and the generator composes a full SRS from the domain
template + universal sections + feature flags derived from the user's answers.

Adding a domain = adding one entry here. Nothing about any single domain is
baked into the agents or the API.
"""
from __future__ import annotations

import re
from typing import Any

GENERIC_KEY = "custom"


def pk() -> dict:
    return {"name": "id", "type": "uuid", "primary_key": True, "nullable": False}


def fk(name: str, ref: str, nullable: bool = False) -> dict:
    return {"name": name, "type": "foreign_key", "references": ref, "nullable": nullable}


def f(name: str, type_: str, **kw: Any) -> dict:
    return {"name": name, "type": type_, **kw}


def timestamps() -> list[dict]:
    return [
        f("created_at", "datetime", nullable=False),
        f("updated_at", "datetime", nullable=False),
    ]


def status(values: list[str], default: str) -> dict:
    return f("status", "enum", values=values, default=default)


def universal_tables() -> list[dict]:
    return [
        {
            "table_name": "users",
            "description": "Login accounts for all system users.",
            "fields": [
                pk(),
                f("full_name", "string", nullable=False),
                f("email", "string", unique=True, nullable=False),
                f("phone", "string", nullable=True),
                f("password_hash", "string", nullable=False),
                fk("role_id", "roles.id"),
                status(["active", "inactive", "blocked"], "active"),
                f("last_login_at", "datetime", nullable=True),
                *timestamps(),
            ],
        },
        {
            "table_name": "roles",
            "description": "System roles for RBAC.",
            "fields": [pk(), f("role_key", "string", unique=True), f("role_name", "string"),
                       f("description", "text", nullable=True)],
        },
        {
            "table_name": "permissions",
            "description": "Granular permissions assigned to roles.",
            "fields": [pk(), f("permission_key", "string", unique=True), f("module", "string"),
                       f("action", "enum", values=["view", "create", "edit", "delete", "approve", "export"])],
        },
        {
            "table_name": "audit_logs",
            "description": "Security audit trail of critical actions.",
            "fields": [
                pk(), fk("user_id", "users.id", nullable=True), f("action", "string"),
                f("module", "string"), f("record_id", "string", nullable=True),
                f("old_values", "json", nullable=True), f("new_values", "json", nullable=True),
                f("ip_address", "string", nullable=True), f("created_at", "datetime"),
            ],
        },
        {
            "table_name": "notifications",
            "description": "In-app + outbound notifications.",
            "fields": [
                pk(), fk("user_id", "users.id"), f("title", "string"), f("body", "text"),
                f("channel", "enum", values=["in_app", "email", "sms"]),
                f("read", "boolean", default=False), f("created_at", "datetime"),
            ],
        },
    ]


GUEST_ROLE = {"role_key": "guest", "role_name": "Public Guest",
              "description": "Browses public pages and submits inquiries without login."}
SUPER_ADMIN = {"role_key": "super_admin", "role_name": "Super Admin",
               "description": "Full system owner with access to all settings, users, and audit logs."}


DOMAIN_LIBRARY: dict[str, dict[str, Any]] = {
    "hotel": {
        "label": "Hospitality SaaS",
        "system_category": "Hotel Management and Booking Web Application",
        "app_type_primary": "Hotel Management System with Booking Portal and Admin Dashboard",
        "keywords": ["hotel", "room", "booking", "guest", "reservation", "hospitality",
                     "check-in", "checkout", "stay", "resort", "lodge", "suite", "occupancy"],
        "roles": [SUPER_ADMIN,
                  {"role_key": "admin", "role_name": "Hotel Admin", "description": "Manages property, rooms, rates, staff, and settings."},
                  {"role_key": "front_desk", "role_name": "Front Desk", "description": "Handles check-in, check-out, walk-ins, and guest requests."},
                  {"role_key": "housekeeping", "role_name": "Housekeeping", "description": "Updates room cleaning status and maintenance flags."},
                  {"role_key": "guest_user", "role_name": "Guest", "description": "Searches rooms, books stays, pays online, and manages reservations."},
                  GUEST_ROLE],
        "modules": ["Public Website", "Authentication", "Room & Inventory Management",
                    "Booking Engine", "Front Desk Operations", "Housekeeping",
                    "Payments & Invoicing", "Guest Management", "Reviews & Ratings",
                    "Reports & Analytics", "Notifications", "Settings"],
        "tables": [
            {"table_name": "room_types", "description": "Categories of rooms with base rate and capacity.",
             "fields": [pk(), f("name", "string", nullable=False), f("description", "text", nullable=True),
                        f("base_rate", "decimal", nullable=False), f("max_occupancy", "integer", default=2),
                        f("amenities", "json", nullable=True), status(["active", "inactive"], "active")]},
            {"table_name": "rooms", "description": "Physical rooms belonging to a room type.",
             "fields": [pk(), fk("room_type_id", "room_types.id"), f("room_number", "string", unique=True),
                        f("floor", "integer", nullable=True),
                        f("housekeeping_status", "enum", values=["clean", "dirty", "inspected", "out_of_service"], default="clean"),
                        status(["available", "occupied", "maintenance"], "available")]},
            {"table_name": "bookings", "description": "Guest reservations across stay dates.",
             "fields": [pk(), f("booking_reference", "string", unique=True), fk("guest_id", "users.id", nullable=True),
                        fk("room_id", "rooms.id", nullable=True), fk("room_type_id", "room_types.id"),
                        f("check_in", "date", nullable=False), f("check_out", "date", nullable=False),
                        f("adults", "integer", default=1), f("children", "integer", default=0),
                        f("total_amount", "decimal"), f("source", "enum", values=["website", "walk_in", "phone", "ota"], default="website"),
                        status(["pending", "confirmed", "checked_in", "checked_out", "cancelled", "no_show"], "pending")]},
            {"table_name": "rate_plans", "description": "Seasonal / promotional pricing for room types.",
             "fields": [pk(), fk("room_type_id", "room_types.id"), f("name", "string"),
                        f("price", "decimal"), f("start_date", "date"), f("end_date", "date"),
                        f("min_nights", "integer", default=1)]},
            {"table_name": "payments", "description": "Payments and refunds against bookings.",
             "fields": [pk(), fk("booking_id", "bookings.id"), f("amount", "decimal"),
                        f("method", "enum", values=["card", "cash", "bank_transfer", "online_gateway"]),
                        f("transaction_reference", "string", nullable=True),
                        status(["pending", "paid", "failed", "refunded"], "pending"), f("paid_at", "datetime", nullable=True)]},
            {"table_name": "reviews", "description": "Guest reviews after checkout.",
             "fields": [pk(), fk("booking_id", "bookings.id"), fk("guest_id", "users.id"),
                        f("rating", "integer"), f("comment", "text", nullable=True), f("created_at", "datetime")]},
        ],
        "relationships": [
            {"from": "room_types.id", "to": "rooms.room_type_id", "type": "one_to_many", "description": "A room type has many rooms."},
            {"from": "rooms.id", "to": "bookings.room_id", "type": "one_to_many", "description": "A room can have many bookings over time."},
            {"from": "bookings.id", "to": "payments.booking_id", "type": "one_to_many", "description": "A booking can have many payments/refunds."},
            {"from": "bookings.id", "to": "reviews.booking_id", "type": "one_to_one", "description": "A completed booking can have one review."},
        ],
        "public_pages": [
            {"page_name": "Home", "route": "/", "sections": ["Hero with search (dates, guests)", "Featured room types", "Amenities", "Gallery", "Guest reviews", "Location map", "Footer"]},
            {"page_name": "Rooms", "route": "/rooms", "sections": ["Room type list", "Filters (price, occupancy, amenities)", "Availability calendar"]},
            {"page_name": "Room Details", "route": "/rooms/[id]", "sections": ["Photos", "Amenities", "Rate plans", "Book now"]},
            {"page_name": "Contact", "route": "/contact", "sections": ["Inquiry form", "Map", "Phone/email"]},
        ],
        "protected_pages": [
            {"page_name": "Guest Dashboard", "route": "/account", "page_type": "portal", "allowed_roles": ["guest_user"], "functions": ["View bookings", "Modify/cancel booking", "Download invoice", "Leave review"]},
            {"page_name": "Front Desk", "route": "/desk", "page_type": "dashboard", "allowed_roles": ["front_desk", "admin", "super_admin"], "functions": ["Check-in", "Check-out", "Create walk-in booking", "Assign room", "Take payment"]},
            {"page_name": "Housekeeping Board", "route": "/housekeeping", "page_type": "dashboard", "allowed_roles": ["housekeeping", "admin"], "functions": ["View room status", "Mark clean/dirty", "Flag maintenance"]},
            {"page_name": "Rooms & Rates", "route": "/admin/rooms", "page_type": "dashboard", "allowed_roles": ["admin", "super_admin"], "functions": ["Manage room types", "Manage rooms", "Manage rate plans"]},
            {"page_name": "Reports", "route": "/admin/reports", "page_type": "dashboard", "allowed_roles": ["admin", "super_admin"], "functions": ["Occupancy", "Revenue (ADR/RevPAR)", "Booking source mix"]},
        ],
        "workflows": [
            {"workflow_name": "Online Booking Workflow", "steps": ["Guest searches by dates and occupancy", "System shows available room types and rates", "Guest selects room type and rate plan", "Guest enters details and pays online", "System creates confirmed booking", "System emails confirmation and invoice", "Front desk sees upcoming arrival"]},
            {"workflow_name": "Check-in / Check-out Workflow", "steps": ["Front desk opens arrival", "Front desk verifies ID and assigns room", "System marks booking checked_in and room occupied", "On departure front desk records charges", "System marks checked_out and room dirty", "Housekeeping is notified to clean room"]},
        ],
        "notifications": [
            {"event": "Booking Confirmed", "recipients": ["guest_user"], "channels": ["email", "in_app"]},
            {"event": "Upcoming Arrival", "recipients": ["front_desk"], "channels": ["in_app", "email"]},
            {"event": "Payment Received", "recipients": ["guest_user", "admin"], "channels": ["email", "in_app"]},
            {"event": "Room Needs Cleaning", "recipients": ["housekeeping"], "channels": ["in_app"]},
        ],
        "reports": [
            {"report_name": "Occupancy Report", "filters": ["date range", "room type"], "exports": ["PDF", "Excel"]},
            {"report_name": "Revenue Report", "filters": ["date range", "source", "room type"], "exports": ["PDF", "Excel"]},
        ],
        "integrations": [
            {"name": "Payment Gateway", "type": "payment", "description": "Online card payments for bookings.", "required": False},
            {"name": "Channel Manager / OTA", "type": "distribution", "description": "Sync availability with OTAs (Booking.com, Expedia).", "required": False},
        ],
        "feature_options": ["Online booking & payments", "Front desk check-in/out", "Housekeeping board",
                            "Channel manager / OTA sync", "Loyalty programme", "Reviews & ratings",
                            "Multi-property support", "Dynamic / seasonal pricing"],
        "nfr_focus": ["Prevent double-booking of the same room/date (concurrency control)",
                      "Online payments must be PCI-DSS compliant via a hosted gateway"],
        "risks": [
            {"area": "Bookings", "risk": "Concurrent Bookings", "severity": "Medium", "reason": "Race conditions on the same room/date.", "mitigation": "Optimistic locking + idempotent reservation creation."},
            {"area": "Payments", "risk": "Payment Processing", "severity": "High", "reason": "PCI-DSS compliance complexity.", "mitigation": "Use a hosted checkout (Stripe/PayHere) to reduce scope."},
        ],
    },

    "retail": {
        "label": "Retail / POS",
        "system_category": "Retail POS, Inventory and E-commerce Web Application",
        "app_type_primary": "Retail POS with Inventory, E-commerce and Admin Dashboard",
        "keywords": ["retail", "pos", "point of sale", "inventory", "stock", "product", "sku",
                     "cashier", "store", "warehouse", "supplier", "barcode", "ecommerce", "shop", "cart", "checkout"],
        "roles": [SUPER_ADMIN,
                  {"role_key": "store_manager", "role_name": "Store Manager", "description": "Manages store inventory, pricing, staff, and reports."},
                  {"role_key": "cashier", "role_name": "Cashier", "description": "Operates the POS, scans products, and takes payments."},
                  {"role_key": "inventory_clerk", "role_name": "Inventory Clerk", "description": "Receives stock, adjusts quantities, and manages suppliers."},
                  {"role_key": "customer", "role_name": "Customer", "description": "Browses the online store, places orders, and tracks delivery."},
                  GUEST_ROLE],
        "modules": ["Public Storefront", "Authentication", "Product Catalog", "Inventory Management",
                    "Point of Sale (POS)", "Orders & Cart", "Suppliers & Purchasing",
                    "Payments", "Customers & Loyalty", "Reports & Analytics", "Notifications", "Settings"],
        "tables": [
            {"table_name": "categories", "description": "Product categories / departments.",
             "fields": [pk(), f("name", "string"), fk("parent_id", "categories.id", nullable=True), status(["active", "inactive"], "active")]},
            {"table_name": "products", "description": "Sellable products / SKUs.",
             "fields": [pk(), f("sku", "string", unique=True), f("name", "string", nullable=False),
                        fk("category_id", "categories.id", nullable=True), f("barcode", "string", nullable=True),
                        f("cost_price", "decimal"), f("sell_price", "decimal"), f("tax_rate", "decimal", default=0),
                        f("reorder_level", "integer", default=5), status(["active", "discontinued"], "active")]},
            {"table_name": "inventory", "description": "Per-warehouse stock levels.",
             "fields": [pk(), fk("product_id", "products.id"), fk("warehouse_id", "warehouses.id"),
                        f("quantity_on_hand", "integer", default=0), f("quantity_reserved", "integer", default=0)]},
            {"table_name": "warehouses", "description": "Stores / stock locations.",
             "fields": [pk(), f("name", "string"), f("location", "string", nullable=True), status(["active", "inactive"], "active")]},
            {"table_name": "sales_orders", "description": "POS + online sales transactions.",
             "fields": [pk(), f("order_number", "string", unique=True), fk("customer_id", "users.id", nullable=True),
                        fk("cashier_id", "users.id", nullable=True), f("channel", "enum", values=["pos", "online"], default="pos"),
                        f("subtotal", "decimal"), f("tax_total", "decimal", default=0), f("discount_total", "decimal", default=0),
                        f("grand_total", "decimal"), status(["draft", "paid", "fulfilled", "refunded", "cancelled"], "draft"), f("created_at", "datetime")]},
            {"table_name": "sales_order_items", "description": "Line items of a sale.",
             "fields": [pk(), fk("sales_order_id", "sales_orders.id"), fk("product_id", "products.id"),
                        f("quantity", "integer"), f("unit_price", "decimal"), f("line_total", "decimal")]},
            {"table_name": "suppliers", "description": "Vendors for purchasing stock.",
             "fields": [pk(), f("name", "string"), f("email", "string", nullable=True), f("phone", "string", nullable=True), status(["active", "inactive"], "active")]},
            {"table_name": "purchase_orders", "description": "Restock orders to suppliers.",
             "fields": [pk(), f("po_number", "string", unique=True), fk("supplier_id", "suppliers.id"),
                        f("total_amount", "decimal"), status(["draft", "ordered", "received", "cancelled"], "draft"), f("created_at", "datetime")]},
        ],
        "relationships": [
            {"from": "categories.id", "to": "products.category_id", "type": "one_to_many", "description": "A category has many products."},
            {"from": "products.id", "to": "inventory.product_id", "type": "one_to_many", "description": "A product has stock across warehouses."},
            {"from": "sales_orders.id", "to": "sales_order_items.sales_order_id", "type": "one_to_many", "description": "A sale has many line items."},
            {"from": "suppliers.id", "to": "purchase_orders.supplier_id", "type": "one_to_many", "description": "A supplier receives many purchase orders."},
        ],
        "public_pages": [
            {"page_name": "Storefront Home", "route": "/", "sections": ["Hero", "Featured products", "Categories", "Promotions", "Footer"]},
            {"page_name": "Shop", "route": "/shop", "sections": ["Product grid", "Filters (category, price)", "Search", "Add to cart"]},
            {"page_name": "Product Details", "route": "/product/[sku]", "sections": ["Gallery", "Price/stock", "Add to cart", "Related products"]},
            {"page_name": "Cart & Checkout", "route": "/checkout", "sections": ["Cart summary", "Address", "Payment", "Place order"]},
        ],
        "protected_pages": [
            {"page_name": "POS Terminal", "route": "/pos", "page_type": "pos", "allowed_roles": ["cashier", "store_manager", "super_admin"], "functions": ["Scan/search product", "Add to ticket", "Apply discount", "Take payment", "Print receipt", "Open/close till"]},
            {"page_name": "Inventory", "route": "/admin/inventory", "page_type": "dashboard", "allowed_roles": ["inventory_clerk", "store_manager", "super_admin"], "functions": ["Receive stock", "Stock adjustments", "Low-stock alerts", "Stock transfer"]},
            {"page_name": "Products", "route": "/admin/products", "page_type": "dashboard", "allowed_roles": ["store_manager", "super_admin"], "functions": ["Create/edit product", "Manage categories", "Manage pricing & tax"]},
            {"page_name": "Purchasing", "route": "/admin/purchasing", "page_type": "dashboard", "allowed_roles": ["store_manager", "super_admin"], "functions": ["Manage suppliers", "Create purchase orders", "Receive PO"]},
            {"page_name": "Reports", "route": "/admin/reports", "page_type": "dashboard", "allowed_roles": ["store_manager", "super_admin"], "functions": ["Sales by day/product", "Inventory valuation", "Profit margin"]},
        ],
        "workflows": [
            {"workflow_name": "POS Sale Workflow", "steps": ["Cashier scans products into a ticket", "System prices items and applies tax/discounts", "Cashier selects payment method", "Customer pays (cash/card)", "System decrements inventory", "System prints receipt and records the sale"]},
            {"workflow_name": "Stock Replenishment Workflow", "steps": ["System flags products below reorder level", "Manager creates a purchase order to a supplier", "Supplier ships goods", "Clerk receives stock against the PO", "System increases quantity on hand", "Low-stock alert clears"]},
        ],
        "notifications": [
            {"event": "Low Stock", "recipients": ["inventory_clerk", "store_manager"], "channels": ["in_app", "email"]},
            {"event": "Order Placed (Online)", "recipients": ["customer", "store_manager"], "channels": ["email", "in_app"]},
            {"event": "Refund Issued", "recipients": ["customer", "store_manager"], "channels": ["email"]},
        ],
        "reports": [
            {"report_name": "Sales Report", "filters": ["date range", "channel", "cashier", "product"], "exports": ["PDF", "Excel"]},
            {"report_name": "Inventory Valuation", "filters": ["warehouse", "category"], "exports": ["PDF", "Excel"]},
        ],
        "integrations": [
            {"name": "Payment Gateway", "type": "payment", "description": "Card payments for POS and online checkout.", "required": False},
            {"name": "Barcode Scanner", "type": "hardware", "description": "USB/Bluetooth barcode scanning at POS.", "required": False},
            {"name": "Receipt Printer", "type": "hardware", "description": "Thermal receipt printing.", "required": False},
        ],
        "feature_options": ["In-store POS", "Online storefront", "Barcode scanning", "Multi-warehouse stock",
                            "Supplier purchase orders", "Loyalty points", "Discounts & promotions", "Tax management"],
        "nfr_focus": ["POS must keep working briefly offline and sync when reconnected",
                      "Inventory decrements must be atomic to avoid overselling"],
        "risks": [
            {"area": "Inventory", "risk": "Overselling", "severity": "High", "reason": "Concurrent POS + online sales of last unit.", "mitigation": "Atomic stock decrement with reservation + transaction."},
            {"area": "POS", "risk": "Offline Resilience", "severity": "Medium", "reason": "Network drops at the till stop sales.", "mitigation": "Local queue with sync on reconnect."},
        ],
    },

    "school": {
        "label": "Education / LMS",
        "system_category": "School Management, LMS, Fees and Transport Web Application",
        "app_type_primary": "School Management System and LMS with Parent Portal and Admin Dashboard",
        "keywords": ["school", "student", "class", "teacher", "lms", "education", "exam", "attendance",
                     "parent", "fees", "tuition", "course", "lesson", "grade", "academic", "transport", "library"],
        "roles": [SUPER_ADMIN,
                  {"role_key": "admin", "role_name": "School Admin", "description": "Manages school setup, users, classes, fees, and configuration."},
                  {"role_key": "teacher", "role_name": "Teacher", "description": "Manages lessons, attendance, assignments, and marks."},
                  {"role_key": "student", "role_name": "Student", "description": "Views lessons, submits assignments, and views results."},
                  {"role_key": "parent", "role_name": "Parent", "description": "Views child attendance, marks, fees, and pays online."},
                  {"role_key": "accountant", "role_name": "Accountant", "description": "Manages fee invoices, payments, and financial reports."},
                  GUEST_ROLE],
        "modules": ["Public Website", "Authentication", "Admission Management", "Student Management",
                    "Class & Subject Management", "Attendance", "LMS (Lessons & Assignments)",
                    "Exams & Grading", "Fee Management", "Transport Management", "Parent Portal",
                    "Reports & Analytics", "Notifications", "Settings"],
        "tables": [
            {"table_name": "classes", "description": "Grades / classes such as Grade 6.",
             "fields": [pk(), f("class_name", "string"), f("class_level", "integer", nullable=True), status(["active", "inactive"], "active")]},
            {"table_name": "sections", "description": "Sections within a class (6-A, 6-B).",
             "fields": [pk(), fk("class_id", "classes.id"), f("section_name", "string"), fk("class_teacher_id", "users.id", nullable=True), f("capacity", "integer", nullable=True)]},
            {"table_name": "subjects", "description": "Subjects taught at the school.",
             "fields": [pk(), f("subject_code", "string", unique=True), f("subject_name", "string"), status(["active", "inactive"], "active")]},
            {"table_name": "students", "description": "Student profiles.",
             "fields": [pk(), fk("user_id", "users.id", nullable=True), f("admission_number", "string", unique=True),
                        f("full_name", "string"), f("date_of_birth", "date", nullable=True), fk("class_id", "classes.id"),
                        fk("section_id", "sections.id"), status(["active", "graduated", "transferred"], "active")]},
            {"table_name": "attendance_records", "description": "Daily attendance.",
             "fields": [pk(), fk("student_id", "students.id"), f("attendance_date", "date"),
                        f("status", "enum", values=["present", "absent", "late", "excused"]), fk("marked_by", "users.id")]},
            {"table_name": "assignments", "description": "LMS assignments.",
             "fields": [pk(), f("title", "string"), fk("subject_id", "subjects.id"), fk("teacher_id", "users.id"),
                        f("due_date", "datetime"), f("total_marks", "decimal", default=100), status(["draft", "published", "closed"], "draft")]},
            {"table_name": "exam_results", "description": "Student marks per subject.",
             "fields": [pk(), fk("student_id", "students.id"), fk("subject_id", "subjects.id"),
                        f("marks_obtained", "decimal"), f("total_marks", "decimal", default=100), f("grade", "string", nullable=True)]},
            {"table_name": "fee_invoices", "description": "Student fee invoices.",
             "fields": [pk(), f("invoice_number", "string", unique=True), fk("student_id", "students.id"),
                        f("fee_type", "enum", values=["admission", "tuition", "exam", "transport", "other"]),
                        f("grand_total", "decimal"), f("paid_amount", "decimal", default=0),
                        f("payment_status", "enum", values=["unpaid", "partial", "paid"], default="unpaid"), f("due_date", "date")]},
            {"table_name": "transport_routes", "description": "School bus routes.",
             "fields": [pk(), f("route_name", "string"), f("monthly_fee", "decimal", default=0), status(["active", "inactive"], "active")]},
        ],
        "relationships": [
            {"from": "classes.id", "to": "sections.class_id", "type": "one_to_many", "description": "A class has many sections."},
            {"from": "sections.id", "to": "students.section_id", "type": "one_to_many", "description": "A section has many students."},
            {"from": "students.id", "to": "attendance_records.student_id", "type": "one_to_many", "description": "A student has many attendance records."},
            {"from": "students.id", "to": "fee_invoices.student_id", "type": "one_to_many", "description": "A student has many fee invoices."},
        ],
        "public_pages": [
            {"page_name": "Home", "route": "/", "sections": ["Hero + admission CTA", "Programs", "Why choose us", "Notices", "Footer"]},
            {"page_name": "Admissions", "route": "/admissions", "sections": ["Process", "Required documents", "Inquiry form", "FAQ"]},
            {"page_name": "Academics", "route": "/academics", "sections": ["Curriculum", "Streams", "Calendar"]},
            {"page_name": "Contact", "route": "/contact", "sections": ["Form", "Map", "Phone/email"]},
        ],
        "protected_pages": [
            {"page_name": "Student Dashboard", "route": "/student", "page_type": "portal", "allowed_roles": ["student"], "functions": ["View timetable", "View lessons", "Submit assignments", "View results", "View fees"]},
            {"page_name": "Parent Dashboard", "route": "/parent", "page_type": "portal", "allowed_roles": ["parent"], "functions": ["View child attendance/marks", "View & pay fees", "View notices", "Contact teacher"]},
            {"page_name": "Teacher Dashboard", "route": "/teacher", "page_type": "dashboard", "allowed_roles": ["teacher"], "functions": ["Mark attendance", "Create lessons/assignments", "Grade submissions", "Enter exam marks"]},
            {"page_name": "Fee Management", "route": "/admin/fees", "page_type": "dashboard", "allowed_roles": ["accountant", "admin", "super_admin"], "functions": ["Generate invoices", "Record payments", "Print receipts", "Fee reports"]},
            {"page_name": "Admin Dashboard", "route": "/admin", "page_type": "dashboard", "allowed_roles": ["admin", "super_admin"], "functions": ["Manage students/teachers", "Manage classes/subjects", "Manage transport", "Reports"]},
        ],
        "workflows": [
            {"workflow_name": "Daily Attendance Workflow", "steps": ["Teacher selects class/section", "System lists students", "Teacher marks present/absent/late", "System saves records", "System notifies parents of absentees", "Attendance report updates"]},
            {"workflow_name": "Fee Payment Workflow", "steps": ["Accountant generates invoice", "Parent views invoice in portal", "Parent pays online or school records manual payment", "System updates payment status", "System generates receipt", "Fee report updates"]},
        ],
        "notifications": [
            {"event": "Student Absent", "recipients": ["parent"], "channels": ["sms", "email", "in_app"]},
            {"event": "Exam Result Published", "recipients": ["student", "parent"], "channels": ["email", "in_app"]},
            {"event": "Fee Invoice Created", "recipients": ["parent"], "channels": ["email", "in_app"]},
        ],
        "reports": [
            {"report_name": "Attendance Report", "filters": ["date range", "class", "section"], "exports": ["PDF", "Excel"]},
            {"report_name": "Fee Collection Report", "filters": ["date range", "class", "status"], "exports": ["PDF", "Excel"]},
            {"report_name": "Exam Result Report", "filters": ["exam", "class", "subject"], "exports": ["PDF", "Excel"]},
        ],
        "integrations": [
            {"name": "Payment Gateway", "type": "payment", "description": "Online fee payments for parents.", "required": False},
            {"name": "SMS Gateway", "type": "messaging", "description": "Absence + result SMS alerts.", "required": False},
        ],
        "feature_options": ["Online admissions", "Attendance", "LMS lessons & assignments", "Exams & grading",
                            "Fee management & online payment", "Transport management", "Parent portal", "Library"],
        "nfr_focus": ["Students/parents must only access their own records",
                      "Marks and fee changes must be recorded in audit logs"],
        "risks": [
            {"area": "Privacy", "risk": "Cross-student data leakage", "severity": "High", "reason": "A parent could view another child's data.", "mitigation": "Strict row-level authorization on every query."},
            {"area": "Fees", "risk": "Payment reconciliation", "severity": "Medium", "reason": "Online + manual payments can desync.", "mitigation": "Idempotent webhooks + daily reconciliation report."},
        ],
    },

    "vehicle": {
        "label": "Automotive Platform",
        "system_category": "Vehicle Sales, Rental, Service and Spare Parts Web Application",
        "app_type_primary": "Vehicle Sales / Rental / Service Center with Admin Dashboard",
        "keywords": ["vehicle", "car", "auto", "automobile", "dealership", "rental", "service center",
                     "spare parts", "garage", "mechanic", "fleet", "test drive", "motorbike", "showroom"],
        "roles": [SUPER_ADMIN,
                  {"role_key": "admin", "role_name": "Dealership Admin", "description": "Manages inventory, staff, pricing, and settings."},
                  {"role_key": "sales_agent", "role_name": "Sales Agent", "description": "Handles leads, test drives, quotes, and sales."},
                  {"role_key": "service_advisor", "role_name": "Service Advisor", "description": "Manages service bookings, jobs, and parts."},
                  {"role_key": "customer", "role_name": "Customer", "description": "Browses vehicles, books test drives/service, and rents vehicles."},
                  GUEST_ROLE],
        "modules": ["Public Website", "Authentication", "Vehicle Inventory", "Sales & Leads",
                    "Rental Management", "Service & Workshop", "Spare Parts (POS)", "Payments",
                    "Customers", "Reports & Analytics", "Notifications", "Settings"],
        "tables": [
            {"table_name": "vehicles", "description": "Vehicles for sale or rent.",
             "fields": [pk(), f("vin", "string", unique=True), f("make", "string"), f("model", "string"),
                        f("year", "integer"), f("mileage", "integer", nullable=True), f("price", "decimal"),
                        f("listing_type", "enum", values=["sale", "rental", "both"], default="sale"),
                        status(["available", "reserved", "sold", "rented", "in_service"], "available")]},
            {"table_name": "leads", "description": "Sales leads and inquiries.",
             "fields": [pk(), fk("vehicle_id", "vehicles.id", nullable=True), fk("customer_id", "users.id", nullable=True),
                        f("source", "enum", values=["website", "walk_in", "phone", "referral"], default="website"),
                        status(["new", "contacted", "test_drive", "negotiating", "won", "lost"], "new"), f("created_at", "datetime")]},
            {"table_name": "sales_orders", "description": "Vehicle sales transactions.",
             "fields": [pk(), f("order_number", "string", unique=True), fk("vehicle_id", "vehicles.id"),
                        fk("customer_id", "users.id"), fk("sales_agent_id", "users.id"), f("sale_price", "decimal"),
                        status(["quoted", "deposit_paid", "completed", "cancelled"], "quoted"), f("created_at", "datetime")]},
            {"table_name": "rentals", "description": "Vehicle rental agreements.",
             "fields": [pk(), fk("vehicle_id", "vehicles.id"), fk("customer_id", "users.id"),
                        f("start_date", "date"), f("end_date", "date"), f("daily_rate", "decimal"),
                        f("total_amount", "decimal"), status(["booked", "active", "returned", "cancelled"], "booked")]},
            {"table_name": "service_jobs", "description": "Workshop service jobs.",
             "fields": [pk(), f("job_number", "string", unique=True), fk("vehicle_id", "vehicles.id", nullable=True),
                        fk("customer_id", "users.id"), fk("service_advisor_id", "users.id", nullable=True),
                        f("description", "text"), f("scheduled_at", "datetime", nullable=True),
                        f("total_cost", "decimal", default=0), status(["booked", "in_progress", "ready", "completed", "cancelled"], "booked")]},
            {"table_name": "parts", "description": "Spare parts inventory.",
             "fields": [pk(), f("part_number", "string", unique=True), f("name", "string"),
                        f("price", "decimal"), f("quantity_on_hand", "integer", default=0), f("reorder_level", "integer", default=3)]},
        ],
        "relationships": [
            {"from": "vehicles.id", "to": "leads.vehicle_id", "type": "one_to_many", "description": "A vehicle attracts many leads."},
            {"from": "vehicles.id", "to": "sales_orders.vehicle_id", "type": "one_to_one", "description": "A vehicle is sold once."},
            {"from": "vehicles.id", "to": "rentals.vehicle_id", "type": "one_to_many", "description": "A vehicle can be rented many times."},
            {"from": "service_jobs.id", "to": "parts.id", "type": "many_to_many", "via": "service_job_parts", "description": "Service jobs consume parts."},
        ],
        "public_pages": [
            {"page_name": "Home", "route": "/", "sections": ["Hero search", "Featured vehicles", "Sell/Rent/Service tabs", "Why us", "Footer"]},
            {"page_name": "Inventory", "route": "/vehicles", "sections": ["Vehicle grid", "Filters (make, model, year, price)", "Compare"]},
            {"page_name": "Vehicle Details", "route": "/vehicles/[id]", "sections": ["Gallery", "Specs", "Book test drive", "Enquire / Finance"]},
            {"page_name": "Book Service", "route": "/service", "sections": ["Service types", "Booking form", "Locations"]},
        ],
        "protected_pages": [
            {"page_name": "Customer Account", "route": "/account", "page_type": "portal", "allowed_roles": ["customer"], "functions": ["My enquiries", "My rentals", "My service jobs", "Invoices"]},
            {"page_name": "Sales CRM", "route": "/admin/sales", "page_type": "dashboard", "allowed_roles": ["sales_agent", "admin", "super_admin"], "functions": ["Manage leads", "Schedule test drives", "Create quotes", "Close sale"]},
            {"page_name": "Workshop", "route": "/admin/service", "page_type": "dashboard", "allowed_roles": ["service_advisor", "admin", "super_admin"], "functions": ["Manage service jobs", "Assign mechanics", "Add parts/labour", "Invoice"]},
            {"page_name": "Inventory", "route": "/admin/vehicles", "page_type": "dashboard", "allowed_roles": ["admin", "super_admin"], "functions": ["Add/edit vehicles", "Manage rental fleet", "Pricing"]},
            {"page_name": "Reports", "route": "/admin/reports", "page_type": "dashboard", "allowed_roles": ["admin", "super_admin"], "functions": ["Sales pipeline", "Rental utilization", "Service revenue"]},
        ],
        "workflows": [
            {"workflow_name": "Vehicle Sales Workflow", "steps": ["Customer enquires on a vehicle", "Sales agent contacts and books a test drive", "Agent prepares a quote", "Customer pays deposit", "Paperwork and financing completed", "Vehicle marked sold and invoice issued"]},
            {"workflow_name": "Service Booking Workflow", "steps": ["Customer books a service slot", "Service advisor creates a job card", "Mechanic performs work and adds parts/labour", "Advisor reviews and prices the job", "Customer pays and collects the vehicle", "Job marked completed"]},
        ],
        "notifications": [
            {"event": "New Lead", "recipients": ["sales_agent"], "channels": ["in_app", "email"]},
            {"event": "Test Drive Scheduled", "recipients": ["customer", "sales_agent"], "channels": ["email", "in_app"]},
            {"event": "Service Ready for Pickup", "recipients": ["customer"], "channels": ["sms", "email"]},
        ],
        "reports": [
            {"report_name": "Sales Pipeline", "filters": ["date range", "agent", "status"], "exports": ["PDF", "Excel"]},
            {"report_name": "Service Revenue", "filters": ["date range", "advisor"], "exports": ["PDF", "Excel"]},
        ],
        "integrations": [
            {"name": "Payment Gateway", "type": "payment", "description": "Deposits and service payments.", "required": False},
            {"name": "Finance / Leasing API", "type": "finance", "description": "Vehicle financing quotes.", "required": False},
        ],
        "feature_options": ["Vehicle sales CRM", "Rental management", "Service workshop", "Spare parts POS",
                            "Test drive booking", "Online enquiries", "Financing quotes", "Fleet tracking"],
        "nfr_focus": ["A vehicle must not be double-sold or double-booked across sales/rental/service"],
        "risks": [
            {"area": "Inventory", "risk": "Double allocation", "severity": "High", "reason": "Same vehicle sold and rented simultaneously.", "mitigation": "Single source-of-truth status with locking."},
        ],
    },

    "hospital": {
        "label": "Healthcare / Clinic",
        "system_category": "Hospital / Clinic Management Web Application",
        "app_type_primary": "Clinic Management with Appointments, EMR and Admin Dashboard",
        "keywords": ["hospital", "clinic", "patient", "doctor", "appointment", "healthcare", "medical",
                     "pharmacy", "diagnosis", "prescription", "emr", "nurse", "ward", "lab", "treatment"],
        "roles": [SUPER_ADMIN,
                  {"role_key": "admin", "role_name": "Clinic Admin", "description": "Manages staff, schedules, billing, and settings."},
                  {"role_key": "doctor", "role_name": "Doctor", "description": "Manages appointments, consultations, and prescriptions."},
                  {"role_key": "nurse", "role_name": "Nurse", "description": "Records vitals and assists consultations."},
                  {"role_key": "receptionist", "role_name": "Receptionist", "description": "Registers patients and books appointments."},
                  {"role_key": "patient", "role_name": "Patient", "description": "Books appointments and views records/prescriptions."},
                  GUEST_ROLE],
        "modules": ["Public Website", "Authentication", "Patient Management", "Appointments",
                    "Consultations / EMR", "Prescriptions", "Pharmacy & Billing", "Lab Tests",
                    "Reports & Analytics", "Notifications", "Settings"],
        "tables": [
            {"table_name": "patients", "description": "Patient demographic and medical profile.",
             "fields": [pk(), fk("user_id", "users.id", nullable=True), f("mrn", "string", unique=True),
                        f("full_name", "string"), f("date_of_birth", "date", nullable=True),
                        f("gender", "enum", values=["male", "female", "other"], nullable=True),
                        f("blood_group", "string", nullable=True), status(["active", "inactive"], "active")]},
            {"table_name": "doctors", "description": "Doctor profiles and specialties.",
             "fields": [pk(), fk("user_id", "users.id"), f("specialty", "string"), f("license_number", "string", unique=True),
                        f("consultation_fee", "decimal", default=0)]},
            {"table_name": "appointments", "description": "Patient appointments with doctors.",
             "fields": [pk(), fk("patient_id", "patients.id"), fk("doctor_id", "doctors.id"),
                        f("scheduled_at", "datetime"), f("reason", "text", nullable=True),
                        status(["booked", "confirmed", "in_consultation", "completed", "cancelled", "no_show"], "booked")]},
            {"table_name": "consultations", "description": "EMR consultation notes.",
             "fields": [pk(), fk("appointment_id", "appointments.id"), fk("patient_id", "patients.id"),
                        f("symptoms", "text", nullable=True), f("diagnosis", "text", nullable=True),
                        f("notes", "text", nullable=True), f("created_at", "datetime")]},
            {"table_name": "prescriptions", "description": "Medications prescribed during a consultation.",
             "fields": [pk(), fk("consultation_id", "consultations.id"), f("medication", "string"),
                        f("dosage", "string"), f("frequency", "string"), f("duration", "string")]},
            {"table_name": "invoices", "description": "Patient billing.",
             "fields": [pk(), f("invoice_number", "string", unique=True), fk("patient_id", "patients.id"),
                        f("total_amount", "decimal"), f("paid_amount", "decimal", default=0),
                        f("payment_status", "enum", values=["unpaid", "partial", "paid"], default="unpaid")]},
        ],
        "relationships": [
            {"from": "patients.id", "to": "appointments.patient_id", "type": "one_to_many", "description": "A patient has many appointments."},
            {"from": "doctors.id", "to": "appointments.doctor_id", "type": "one_to_many", "description": "A doctor has many appointments."},
            {"from": "appointments.id", "to": "consultations.appointment_id", "type": "one_to_one", "description": "An appointment yields one consultation."},
            {"from": "consultations.id", "to": "prescriptions.consultation_id", "type": "one_to_many", "description": "A consultation has many prescriptions."},
        ],
        "public_pages": [
            {"page_name": "Home", "route": "/", "sections": ["Hero + book appointment", "Specialties", "Doctors", "Footer"]},
            {"page_name": "Doctors", "route": "/doctors", "sections": ["Doctor list", "Filter by specialty", "Availability"]},
            {"page_name": "Book Appointment", "route": "/book", "sections": ["Select doctor/slot", "Patient details", "Confirm"]},
        ],
        "protected_pages": [
            {"page_name": "Patient Portal", "route": "/patient", "page_type": "portal", "allowed_roles": ["patient"], "functions": ["Book/cancel appointment", "View prescriptions", "View invoices", "Download records"]},
            {"page_name": "Doctor Console", "route": "/doctor", "page_type": "dashboard", "allowed_roles": ["doctor"], "functions": ["View schedule", "Start consultation", "Write diagnosis", "Prescribe"]},
            {"page_name": "Reception", "route": "/reception", "page_type": "dashboard", "allowed_roles": ["receptionist", "admin"], "functions": ["Register patient", "Book appointment", "Take payment"]},
            {"page_name": "Admin Dashboard", "route": "/admin", "page_type": "dashboard", "allowed_roles": ["admin", "super_admin"], "functions": ["Manage staff", "Schedules", "Billing", "Reports"]},
        ],
        "workflows": [
            {"workflow_name": "Appointment & Consultation Workflow", "steps": ["Patient books an appointment", "Receptionist confirms and collects details", "Nurse records vitals", "Doctor consults and records diagnosis", "Doctor issues prescription", "System bills the patient and updates records"]},
        ],
        "notifications": [
            {"event": "Appointment Confirmed", "recipients": ["patient"], "channels": ["email", "sms", "in_app"]},
            {"event": "Appointment Reminder", "recipients": ["patient"], "channels": ["sms", "in_app"]},
        ],
        "reports": [
            {"report_name": "Appointments Report", "filters": ["date range", "doctor", "status"], "exports": ["PDF", "Excel"]},
            {"report_name": "Revenue Report", "filters": ["date range", "doctor"], "exports": ["PDF", "Excel"]},
        ],
        "integrations": [
            {"name": "Payment Gateway", "type": "payment", "description": "Consultation/billing payments.", "required": False},
            {"name": "SMS Reminders", "type": "messaging", "description": "Appointment reminders.", "required": False},
        ],
        "feature_options": ["Online appointment booking", "Doctor consultation / EMR", "Prescriptions",
                            "Billing & invoices", "Lab tests", "Pharmacy", "Patient portal"],
        "nfr_focus": ["Patient medical records are sensitive and must be access-controlled and encrypted at rest",
                      "All record access must be audit-logged for compliance"],
        "risks": [
            {"area": "Compliance", "risk": "PHI exposure", "severity": "High", "reason": "Medical data is highly sensitive.", "mitigation": "Encryption at rest, strict RBAC, full audit trail."},
        ],
    },

    "restaurant": {
        "label": "Food & Restaurant",
        "system_category": "Online Food Ordering and Restaurant Management Web Application",
        "app_type_primary": "Food Ordering & Restaurant Management with Kitchen and Admin Dashboard",
        "keywords": ["restaurant", "food", "menu", "dish", "meal", "cuisine", "cafe", "kitchen",
                     "order", "ordering", "delivery", "takeaway", "dine", "dine-in", "table",
                     "reservation", "recipe", "pizza", "burger", "bakery", "catering", "waiter", "chef"],
        "roles": [SUPER_ADMIN,
                  {"role_key": "admin", "role_name": "Restaurant Admin", "description": "Manages menu, branches, staff, pricing, and settings."},
                  {"role_key": "manager", "role_name": "Manager", "description": "Oversees daily orders, staff, promotions, and views sales reports."},
                  {"role_key": "kitchen_staff", "role_name": "Kitchen Staff", "description": "Sees incoming orders on a live board and updates cooking status."},
                  {"role_key": "cashier", "role_name": "Cashier / Counter", "description": "Takes counter orders and processes payments."},
                  {"role_key": "delivery_driver", "role_name": "Delivery Driver", "description": "Receives assigned deliveries and updates delivery status."},
                  {"role_key": "customer", "role_name": "Customer", "description": "Browses the menu, orders (QR/online), pays, and tracks the order."},
                  GUEST_ROLE],
        "modules": ["Public Website", "Authentication", "Menu Management", "Online Ordering & Cart",
                    "Table QR Ordering", "Kitchen Display (KDS)", "Order Management", "Payments",
                    "Delivery Management", "Reservations", "Promotions & Loyalty",
                    "Reports & Analytics", "Notifications", "Settings"],
        "tables": [
            {"table_name": "menu_categories", "description": "Groups of menu items (Starters, Mains, Drinks).",
             "fields": [pk(), f("name", "string", nullable=False), f("display_order", "integer", default=0), status(["active", "inactive"], "active")]},
            {"table_name": "menu_items", "description": "Individual dishes/products on the menu.",
             "fields": [pk(), fk("category_id", "menu_categories.id"), f("name", "string", nullable=False),
                        f("description", "text", nullable=True), f("price", "decimal", nullable=False),
                        f("image_url", "string", nullable=True), f("is_veg", "boolean", default=False),
                        f("spice_level", "enum", values=["none", "mild", "medium", "hot"], default="none"),
                        f("prep_minutes", "integer", default=15), status(["available", "sold_out", "hidden"], "available")]},
            {"table_name": "item_modifiers", "description": "Add-ons / options for an item (extra cheese, size).",
             "fields": [pk(), fk("menu_item_id", "menu_items.id"), f("name", "string"), f("price_delta", "decimal", default=0),
                        f("group", "string", nullable=True), f("required", "boolean", default=False)]},
            {"table_name": "dining_tables", "description": "Physical tables with QR codes for in-restaurant ordering.",
             "fields": [pk(), f("table_number", "string", unique=True), f("seats", "integer", default=4),
                        f("qr_code", "string", unique=True), status(["free", "occupied", "reserved"], "free")]},
            {"table_name": "orders", "description": "Customer orders across channels.",
             "fields": [pk(), f("order_number", "string", unique=True), fk("customer_id", "users.id", nullable=True),
                        fk("dining_table_id", "dining_tables.id", nullable=True),
                        f("channel", "enum", values=["dine_in_qr", "online_delivery", "online_pickup", "counter"], default="online_delivery"),
                        f("subtotal", "decimal"), f("delivery_fee", "decimal", default=0), f("tax_total", "decimal", default=0),
                        f("tip", "decimal", default=0), f("grand_total", "decimal"), f("notes", "text", nullable=True),
                        f("status", "enum", values=["placed", "accepted", "preparing", "ready", "out_for_delivery", "completed", "cancelled"], default="placed"),
                        f("created_at", "datetime")]},
            {"table_name": "order_items", "description": "Line items within an order.",
             "fields": [pk(), fk("order_id", "orders.id"), fk("menu_item_id", "menu_items.id"),
                        f("quantity", "integer", default=1), f("unit_price", "decimal"),
                        f("selected_modifiers", "json", nullable=True), f("line_total", "decimal"), f("notes", "string", nullable=True)]},
            {"table_name": "payments", "description": "Payments against orders.",
             "fields": [pk(), fk("order_id", "orders.id"), f("amount", "decimal"),
                        f("method", "enum", values=["card", "cash", "online_gateway", "wallet"]),
                        f("transaction_reference", "string", nullable=True),
                        status(["pending", "paid", "failed", "refunded"], "pending"), f("paid_at", "datetime", nullable=True)]},
            {"table_name": "deliveries", "description": "Delivery assignments and tracking.",
             "fields": [pk(), fk("order_id", "orders.id"), fk("driver_id", "users.id", nullable=True),
                        f("address", "text"), f("lat", "decimal", nullable=True), f("lng", "decimal", nullable=True),
                        f("status", "enum", values=["assigned", "picked_up", "delivered", "failed"], default="assigned"),
                        f("eta_minutes", "integer", nullable=True)]},
            {"table_name": "reservations", "description": "Table reservations.",
             "fields": [pk(), fk("customer_id", "users.id", nullable=True), fk("dining_table_id", "dining_tables.id", nullable=True),
                        f("party_size", "integer"), f("reserved_at", "datetime"),
                        status(["booked", "seated", "completed", "cancelled", "no_show"], "booked")]},
            {"table_name": "promotions", "description": "Discounts, coupons, and loyalty offers.",
             "fields": [pk(), f("code", "string", unique=True), f("description", "string"),
                        f("discount_type", "enum", values=["percent", "amount", "free_item"]),
                        f("value", "decimal"), f("starts_at", "date", nullable=True), f("ends_at", "date", nullable=True),
                        status(["active", "expired", "disabled"], "active")]},
        ],
        "relationships": [
            {"from": "menu_categories.id", "to": "menu_items.category_id", "type": "one_to_many", "description": "A category has many menu items."},
            {"from": "menu_items.id", "to": "item_modifiers.menu_item_id", "type": "one_to_many", "description": "An item has many modifiers."},
            {"from": "orders.id", "to": "order_items.order_id", "type": "one_to_many", "description": "An order has many line items."},
            {"from": "menu_items.id", "to": "order_items.menu_item_id", "type": "one_to_many", "description": "A menu item appears in many order lines."},
            {"from": "orders.id", "to": "payments.order_id", "type": "one_to_many", "description": "An order can have payments/refunds."},
            {"from": "orders.id", "to": "deliveries.order_id", "type": "one_to_one", "description": "A delivery order has one delivery record."},
            {"from": "dining_tables.id", "to": "orders.dining_table_id", "type": "one_to_many", "description": "A table can have many QR orders over time."},
        ],
        "public_pages": [
            {"page_name": "Home", "route": "/", "sections": ["Hero with order CTA", "Featured dishes", "How it works", "Offers", "Reviews", "Location & hours", "Footer"]},
            {"page_name": "Menu", "route": "/menu", "sections": ["Category tabs", "Dish cards with photo/price", "Add to cart", "Search & filters (veg, spicy)"]},
            {"page_name": "Cart & Checkout", "route": "/checkout", "sections": ["Cart summary", "Delivery/pickup choice", "Address & time", "Payment", "Place order"]},
            {"page_name": "Track Order", "route": "/track/[order]", "sections": ["Live status timeline", "ETA", "Driver location"]},
            {"page_name": "Reserve a Table", "route": "/reserve", "sections": ["Date/time/party size", "Confirm reservation"]},
        ],
        "protected_pages": [
            {"page_name": "Customer Account", "route": "/account", "page_type": "portal", "allowed_roles": ["customer"], "functions": ["Order history", "Reorder", "Saved addresses", "Loyalty points", "My reservations"]},
            {"page_name": "Kitchen Display", "route": "/kds", "page_type": "dashboard", "allowed_roles": ["kitchen_staff", "manager", "admin"], "functions": ["See new orders live", "Accept order", "Mark preparing/ready", "Bump completed tickets"]},
            {"page_name": "Order Management", "route": "/admin/orders", "page_type": "dashboard", "allowed_roles": ["manager", "cashier", "admin", "super_admin"], "functions": ["View all orders", "Refund/cancel", "Assign driver", "Reprint receipt"]},
            {"page_name": "Menu Management", "route": "/admin/menu", "page_type": "dashboard", "allowed_roles": ["manager", "admin", "super_admin"], "functions": ["Create/edit items", "Manage categories & modifiers", "Set availability/sold-out", "Pricing"]},
            {"page_name": "Delivery Board", "route": "/admin/delivery", "page_type": "dashboard", "allowed_roles": ["manager", "delivery_driver", "admin"], "functions": ["Assign deliveries", "Update status", "Driver view of route"]},
            {"page_name": "Reports", "route": "/admin/reports", "page_type": "dashboard", "allowed_roles": ["manager", "admin", "super_admin"], "functions": ["Sales by day/item/channel", "Peak hours", "Average order value", "Top dishes"]},
        ],
        "workflows": [
            {"workflow_name": "Online Order Workflow", "steps": ["Customer browses the menu and adds items + modifiers to cart", "Customer chooses delivery or pickup and a time", "Customer pays online", "System creates the order and shows it on the Kitchen Display", "Kitchen accepts and marks preparing → ready", "Driver is assigned (for delivery) and delivers", "Customer is notified at each step and the order is completed"]},
            {"workflow_name": "Table QR Ordering Workflow", "steps": ["Guest scans the QR code on their table", "System opens the menu for that table", "Guest adds items and places the order", "Order appears on the Kitchen Display tagged with the table", "Kitchen prepares and serves to the table", "Guest pays at the table or counter", "Table is marked free"]},
        ],
        "notifications": [
            {"event": "Order Placed", "recipients": ["customer", "kitchen_staff"], "channels": ["in_app", "email", "sms"]},
            {"event": "Order Ready / Out for Delivery", "recipients": ["customer", "delivery_driver"], "channels": ["sms", "in_app"]},
            {"event": "New Order (Kitchen)", "recipients": ["kitchen_staff"], "channels": ["in_app"]},
            {"event": "Daily Sales Summary", "recipients": ["manager"], "channels": ["email"]},
        ],
        "reports": [
            {"report_name": "Sales Report", "filters": ["date range", "channel", "item", "branch"], "exports": ["PDF", "Excel"]},
            {"report_name": "Top Items Report", "filters": ["date range", "category"], "exports": ["PDF", "Excel"]},
            {"report_name": "Delivery Performance", "filters": ["date range", "driver"], "exports": ["PDF", "Excel"]},
        ],
        "integrations": [
            {"name": "Payment Gateway", "type": "payment", "description": "Online card/wallet payments at checkout.", "required": False},
            {"name": "Google Maps", "type": "maps", "description": "Address autocomplete + delivery distance/ETA.", "required": False},
            {"name": "SMS / WhatsApp", "type": "messaging", "description": "Order status updates to customers.", "required": False},
            {"name": "Third-party Delivery (Uber Eats/Deliveroo)", "type": "delivery", "description": "Push orders to aggregator couriers.", "required": False},
        ],
        "feature_options": ["Online ordering (delivery/pickup)", "Table QR ordering", "Kitchen display board",
                            "Menu & modifier management", "Online payments", "Own delivery / driver app",
                            "Table reservations", "Loyalty & promotions", "Live order tracking", "Ingredient stock alerts"],
        "nfr_focus": ["The kitchen display must update in near real-time (websockets) so new orders appear within ~2 seconds",
                      "Online payments must use a PCI-DSS compliant hosted gateway"],
        "risks": [
            {"area": "Realtime", "risk": "Kitchen board lag", "severity": "Medium", "reason": "Orders that don't appear promptly delay food.", "mitigation": "WebSocket push + audible alert + auto-retry polling."},
            {"area": "Payments", "risk": "Payment Processing", "severity": "High", "reason": "Card handling carries PCI-DSS obligations.", "mitigation": "Use a hosted/tokenised gateway; never store card data."},
        ],
    },
}


GENERIC_DOMAIN: dict[str, Any] = {
    "label": "Custom SaaS",
    "system_category": "Custom Web Application with Admin Dashboard",
    "app_type_primary": "Custom SaaS Web Application",
    "keywords": [],
    "roles": [SUPER_ADMIN,
              {"role_key": "admin", "role_name": "Administrator", "description": "Manages users, records, and settings."},
              {"role_key": "staff", "role_name": "Staff", "description": "Performs day-to-day operations on records."},
              {"role_key": "member", "role_name": "Member", "description": "Self-service access to their own data."},
              GUEST_ROLE],
    "modules": ["Public Website", "Authentication", "User Management", "Core Records",
                "Dashboard & Reports", "Notifications", "Settings"],
    "tables": [
        {"table_name": "records", "description": "Primary domain records managed by the app.",
         "fields": [pk(), f("title", "string"), f("description", "text", nullable=True),
                    fk("owner_id", "users.id", nullable=True), status(["draft", "active", "archived"], "active"), *timestamps()]},
        {"table_name": "categories", "description": "Categorisation for records.",
         "fields": [pk(), f("name", "string"), status(["active", "inactive"], "active")]},
        {"table_name": "comments", "description": "Comments / activity on records.",
         "fields": [pk(), fk("record_id", "records.id"), fk("user_id", "users.id"), f("body", "text"), f("created_at", "datetime")]},
    ],
    "relationships": [
        {"from": "categories.id", "to": "records.category_id", "type": "one_to_many", "description": "A category groups many records."},
        {"from": "records.id", "to": "comments.record_id", "type": "one_to_many", "description": "A record has many comments."},
    ],
    "public_pages": [
        {"page_name": "Home", "route": "/", "sections": ["Hero", "Features", "How it works", "Pricing", "Footer"]},
        {"page_name": "Contact", "route": "/contact", "sections": ["Form", "Details"]},
    ],
    "protected_pages": [
        {"page_name": "Member Dashboard", "route": "/app", "page_type": "portal", "allowed_roles": ["member"], "functions": ["View/manage own records", "Profile"]},
        {"page_name": "Admin Dashboard", "route": "/admin", "page_type": "dashboard", "allowed_roles": ["admin", "super_admin", "staff"], "functions": ["Manage records", "Manage users", "Reports", "Settings"]},
    ],
    "workflows": [
        {"workflow_name": "Core Record Lifecycle", "steps": ["User creates a record", "Staff reviews/updates it", "Record moves through statuses", "System notifies stakeholders", "Record is archived when done"]},
    ],
    "notifications": [
        {"event": "Record Created", "recipients": ["admin", "staff"], "channels": ["in_app", "email"]},
        {"event": "Record Updated", "recipients": ["member"], "channels": ["in_app"]},
    ],
    "reports": [
        {"report_name": "Activity Report", "filters": ["date range", "status"], "exports": ["PDF", "Excel"]},
    ],
    "integrations": [
        {"name": "Email Provider", "type": "messaging", "description": "Transactional email.", "required": False},
    ],
    "feature_options": ["User accounts & roles", "Core record management", "Dashboard & reports",
                        "Notifications", "File uploads", "Public landing site", "Online payments"],
    "nfr_focus": ["Role-based access control on all protected endpoints"],
    "risks": [
        {"area": "Scope", "risk": "Under-specified domain", "severity": "Medium", "reason": "Idea is generic, so the model is a sensible default.", "mitigation": "Refine via the requirement questions and prompt customization."},
    ],
}


def get_domain(domain_key: str) -> dict[str, Any]:
    return DOMAIN_LIBRARY.get(domain_key, GENERIC_DOMAIN)


_WORD_RE = re.compile(r"[a-z0-9]+")


def classify_domain(text: str) -> tuple[str, float, str]:
    """Keyword-score the brief against the library.

    Returns ``(domain_key, confidence 0..1, human_label)``. Used as a fast,
    deterministic classifier and as a prior the LLM classifier can override.
    """
    tokens = set(_WORD_RE.findall((text or "").lower()))
    if not tokens:
        return GENERIC_KEY, 0.0, GENERIC_DOMAIN["label"]

    scores: dict[str, int] = {}
    for key, dom in DOMAIN_LIBRARY.items():
        hits = 0
        for kw in dom["keywords"]:
            parts = kw.split()
            if len(parts) == 1:
                if kw in tokens:
                    hits += 1
            elif kw in (text or "").lower():
                hits += 2
        scores[key] = hits

    best_key = max(scores, key=scores.get)
    best = scores[best_key]
    if best == 0:
        return GENERIC_KEY, 0.0, GENERIC_DOMAIN["label"]

    total = sum(scores.values()) or 1

    confidence = min(0.97, 0.45 + 0.5 * (best / total) + min(best, 4) * 0.05)
    return best_key, round(confidence, 2), DOMAIN_LIBRARY[best_key]["label"]
