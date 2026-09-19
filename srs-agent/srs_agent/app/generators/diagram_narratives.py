"""Diagram Narratives — Plain-English system flow explanations for non-technical stakeholders."""
from __future__ import annotations

import re


def _clean(val: str | None, default: str = "") -> str:
    return " ".join(str(val or default).split()).strip()


def _roles_str(doc: dict) -> str:
    roles = [r.get("role_name") or r.get("name") for r in (doc.get("roles") or []) if isinstance(r, dict)]
    roles = [r for r in roles if r]
    return ", ".join(roles) if roles else "Users and Administrators"


def _tables_str(doc: dict) -> str:
    tables = [t.get("table_name") or t.get("name") for t in ((doc.get("database_design") or {}).get("tables") or []) if isinstance(t, dict)]
    tables = [t.replace("_", " ") for t in tables if t]
    return ", ".join(tables[:4]) if tables else "core business records"


def _app_title(doc: dict) -> str:
    summary = doc.get("app_summary")
    name = (summary.get("app_name") if isinstance(summary, dict) else "") or doc.get("project_name") or "Application"
    return _clean(name, "Application")


def generate_business_summary(kind: str, doc: dict) -> str:
    app = _app_title(doc)
    roles = _roles_str(doc)
    tables = _tables_str(doc)

    summaries = {
        "system_context": f"A high-level map of {app} showing how {roles} interact with the software, and how it safely connects to data stores and third-party services.",
        "component": f"An architectural blueprint of {app} illustrating how user screens connect through secure API controllers to manage {tables}.",
        "deployment": f"A structural overview of where {app} runs, including the client browser interface, the application runtime, and the secure production database.",
        "use_case": f"A clear inventory of goals that {roles} can achieve when using {app}, defining permissions and capabilities without technical jargon.",
        "sequence": f"A chronological step-by-step walkthrough showing the exact conversation between a user, the application interface, security checks, and database updates.",
        "erd": f"The business data blueprint showing the records {app} remembers ({tables}), their relationships, and how customer data remains organized and accurate.",
        "activity": f"The complete workflow path from when a user begins an action to its successful completion or error handling.",
        "class_object": f"A structural overview of the primary information models and objects that power the business logic inside {app}.",
        "state_machine": f"The lifecycle states a primary business record moves through (e.g. Draft, Active, Completed), ensuring no invalid status changes occur.",
        "dfd": f"A data flow map tracking where customer input enters {app}, how it is verified, and where it is permanently stored.",
        "bpmn": f"The standard business process flow detailing participant responsibilities, trigger events, decision branches, and expected outcomes.",
    }
    return summaries.get(kind, f"Visual system flow model for {app}.")


def generate_flow_explanation(kind: str, doc: dict) -> list[str]:
    app = _app_title(doc)
    roles = _roles_str(doc)
    tables = _tables_str(doc)

    flows = {
        "system_context": [
            f"1. Primary Users ({roles}) access {app} securely via desktop or mobile web browsers.",
            "2. User requests pass through authenticated gateway boundaries, preventing unauthorized access.",
            f"3. Validated requests interact with application domain services to manage {tables}.",
            "4. External services (e.g., notifications, email, payment gateways) are called asynchronously without blocking the user.",
            "5. Safe response data is returned to the user's screen with instantaneous visual feedback."
        ],
        "component": [
            "1. Presentation Layer: Users interact with responsive screens (navigation, dashboards, forms, and cards).",
            "2. Gateway & API Layer: Client button clicks and inputs trigger structured HTTP/JSON or WebSocket API calls.",
            "3. Security & Validation: Every request checks role permissions and validates inputs before executing business logic.",
            f"4. Persistence Layer: Approved operations read or write persistent records in {tables}.",
            "5. The system refreshes the client interface in real-time to reflect updated status."
        ],
        "deployment": [
            "1. Client Environment: The web application is served to the user's browser with pre-compiled assets and responsive styling.",
            "2. Application Server: Next.js and API services process server components, route handlers, and API endpoints.",
            "3. Database Host: A managed MongoDB cluster stores operational documents with isolated access credentials.",
            "4. Communication Security: All communication travels over encrypted HTTPS and WSS connections."
        ],
        "use_case": [
            f"1. Role Identification: The system identifies the user's role ({roles}).",
            "2. Permitted Actions: The user is presented only with capabilities allowed for their specific role.",
            "3. Goal Execution: The user initiates actions (e.g. creating bookings, updating records, reviewing reports).",
            "4. Completion: The system completes the requested use case and logs necessary audit events."
        ],
        "sequence": [
            "1. User Action: A user enters information into a form and clicks submit.",
            "2. Client Validation: The browser performs instant validation to ensure required fields are filled.",
            "3. API Request: An authorized POST/PUT request is dispatched to the backend service.",
            "4. Database Mutation: The server executes atomic database updates and receives confirmation.",
            "5. Response: The server returns an affirmative status, and the UI displays a success confirmation."
        ],
        "erd": [
            f"1. Entity Modeling: Core business objects are represented as collections: {tables}.",
            "2. Relational Integrity: Each record has a unique ID, and related records connect via explicit foreign keys.",
            "3. Cardinality: One-to-many and one-to-one connections ensure parent records properly organize children.",
            "4. Data Consistency: Required fields and data types prevent malformed records from entering the database."
        ],
        "activity": [
            "1. Start Node: The workflow begins when the user triggers an action.",
            "2. Decision Gateway: The system checks pre-conditions (e.g. authentication, quota, valid inputs).",
            "3. Branch Handling: If checks fail, an informative error guidance message is displayed.",
            "4. Processing: If checks pass, background tasks and data persistence complete.",
            "5. End Node: The workflow terminates in an approved, saved state."
        ],
        "state_machine": [
            "1. Initial State: A new record is created in a 'Draft' or 'Pending' state.",
            "2. Transition Trigger: A user action or system event triggers an authorized state transition.",
            "3. Guard Conditions: Pre-requisites are verified before moving to the next state.",
            "4. Terminal State: The record reaches its final state (e.g. 'Completed', 'Approved', 'Archived')."
        ],
    }

    return flows.get(kind, [
        f"1. User initiates interaction with {app}.",
        "2. The system validates the request and security permissions.",
        "3. Business logic processes the action and updates data records.",
        "4. The system delivers a clear response and updates the screen."
    ])


def generate_key_takeaways(kind: str, doc: dict) -> list[str]:
    takeaways = {
        "system_context": [
            "External boundaries strictly separate what users see from how data is stored.",
            "Third-party integrations run as isolated services that cannot compromise core application data."
        ],
        "component": [
            "Modular architecture ensures changes to the user interface do not break backend database logic.",
            "Every database query passes through server-side permission checks."
        ],
        "deployment": [
            "Zero client-side secrets: API keys and connection credentials stay secure on the server.",
            "Fully encrypted transport across browser, server, and database."
        ],
        "erd": [
            "Every data entity has explicit ownership and field validation.",
            "Relationships are structured to prevent orphaned or disconnected records."
        ]
    }
    return takeaways.get(kind, [
        "Structured for clear maintainability and security.",
        "Designed to provide a fast, predictable experience for all users."
    ])
