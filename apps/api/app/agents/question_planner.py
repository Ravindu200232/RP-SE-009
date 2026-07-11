"""QuestionPlannerAgent — generate dynamic, plain-language questions.

The LLM (Ollama) is the PRIMARY generator: it writes unique, idea-specific
questions tailored to the detected domain and the missing coverage areas, in a
strict JSON schema validated through the repair loop. If Ollama is unreachable
or returns an unusable set, a domain-tailored deterministic bank is used as a
fallback so the flow always works offline.

Question count depends on how much the brief already covers (5–20). Critical
coverage areas always get asked; optional areas only when not already implied
by the idea.
"""
from __future__ import annotations

import re

from ..knowledge.domains import get_domain
from ..llm import LLMRepairFailed, LLMUnavailable, get_llm
from ..schemas.questions import ANSWER_TYPES, COVERAGE_AREAS, CRITICAL_AREAS
from ..services.events import bus
from .state import AgentState


# Words in the idea that indicate the user already told us the kind of
# business/app — so we should NOT ask "what kind of business is this?".
_BUSINESS_INDICATORS = (
    "service", "services", "shop", "store", "website", "web site", "platform",
    "app", "application", "system", "portal", "software", "tool", "marketplace",
    "business", "company", "agency", "startup", "cleaning", "booking", "rental",
    "delivery", "management", "ecommerce", "e-commerce", "hotel", "school",
    "clinic", "hospital", "restaurant", "cafe", "gym", "fitness", "salon",
    "repair", "tutoring", "consulting", "real estate", "pharmacy", "retail",
    "pos", "vehicle", "car", "food", "grocery", "event", "blog", "social",
)


def _covered(area: str, brief: str) -> bool:
    b = brief.lower()
    table = {
        "business_type": list(_BUSINESS_INDICATORS),
        "main_goal": ["goal", "so that", "in order to", "helps", "manage", "allow", "let", "enable",
                      "doing", "provide", "offer", "where", "can"],
        "users_roles": ["admin", "user", "customer", "staff", "role", "guest", "manager", "owner",
                        "client", "member", "employee", "people", "team"],
        "auth": ["login", "register", "sign in", "sign up", "account", "password", "auth"],
        "public_pages": ["landing", "website", "web site", "public", "home page", "marketing", "site"],
        "features_modules": ["feature", "module", "manage", "track", "report", "booking", "order",
                             "cleaning", "schedule", "inventory", "payment"],
        "data_entities": ["table", "record", "data", "inventory", "product", "booking", "order",
                          "customer", "room", "service", "schedule"],
        "payments_billing": ["pay", "payment", "billing", "invoice", "checkout", "price", "subscription"],
        "reports": ["report", "analytics", "dashboard", "kpi", "revenue", "insight"],
        "notifications": ["notify", "notification", "email", "sms", "alert", "reminder", "whatsapp"],
        "file_uploads": ["upload", "file", "document", "image", "photo", "attachment", "gallery"],
        "integrations": ["integrate", "integration", "api", "third party", "gateway", "sync", "maps", "stripe"],
        "security_privacy": ["secure", "security", "privacy", "gdpr", "permission", "encrypt", "sensitive"],
        "performance": ["fast", "performance", "scale", "concurrent", "load", "users at once"],
        "devices_mobile": ["mobile", "phone", "pwa", "responsive", "tablet", "android", "ios"],
        "languages": ["language", "multilingual", "sinhala", "tamil", "english", "bilingual"],
        "deployment_stack": ["deploy", "cloud", "aws", "azure", "docker", "stack", "react", "node", "on-premise"],
        "special_rules": ["approval", "workflow", "rule", "policy", "approve"],
        "app_surfaces": ["portal", "dashboard", "pos", "admin", "app", "mobile"],
    }
    return any(k in b for k in table.get(area, []))


def _business_known(brief: str, classification: dict) -> bool:
    """True if the idea already tells us the business/domain — don't re-ask it."""
    if float((classification or {}).get("confidence", 0)) >= 0.5:
        return True
    detected = str((classification or {}).get("detected_domain", "")).strip().lower()
    if detected and detected not in ("custom", "custom saas", ""):
        return True
    b = brief.lower()
    words = len(re.findall(r"[a-z]{3,}", b))
    return words >= 5 and any(ind in b for ind in _BUSINESS_INDICATORS)


def _covered_areas(brief: str, classification: dict) -> set[str]:
    """Areas already answered by the idea itself (so we skip those questions)."""
    covered: set[str] = set()
    for area in COVERAGE_AREAS:
        if area == "business_type":
            if _business_known(brief, classification):
                covered.add(area)
        elif _covered(area, brief):
            covered.add(area)
    return covered


def _bank(domain_key: str) -> dict[str, dict]:
    dom = get_domain(domain_key)
    features = dom["feature_options"]
    return {
        "business_type": dict(
            question="What kind of business is your project for?",
            why_needed="Determines the domain model, modules, and database tables.",
            answer_type="single_choice",
            suggested_options=["Hotel / Hospitality", "Online Store / E-commerce", "Healthcare / Clinic",
                               "Education / School", "Vehicle / Automotive", "Other"],
            maps_to_srs_fields=["system_category", "app_type"],
        ),
        "main_goal": dict(
            question="In one sentence, what is the main thing this app should help people do?",
            why_needed="Defines the core business goal and primary workflows.",
            answer_type="free_text", suggested_options=[],
            maps_to_srs_fields=["app_summary.business_goal"],
        ),
        "users_roles": dict(
            question="Who will use the app? Pick all that apply.",
            why_needed="Determines roles and the role access matrix.",
            answer_type="multi_choice",
            suggested_options=[r["role_name"] for r in dom["roles"] if r["role_key"] != "guest"] + ["Other"],
            maps_to_srs_fields=["roles", "role_access_matrix"],
        ),
        "auth": dict(
            question="Should users create accounts and log in?",
            why_needed="Determines authentication requirements.",
            answer_type="single_choice",
            suggested_options=["Yes, accounts with login", "No, mostly public", "Both public + private areas"],
            maps_to_srs_fields=["authentication_requirement"],
        ),
        "public_pages": dict(
            question="Do you need a public marketing website (home, about, contact)?",
            why_needed="Determines whether public landing pages are in scope.",
            answer_type="yes_no", suggested_options=["Yes", "No"],
            maps_to_srs_fields=["public_pages"],
        ),
        "app_surfaces": dict(
            question="Which of these do you need?",
            why_needed="Determines app surfaces (portal, admin, POS, mobile).",
            answer_type="multi_choice",
            suggested_options=["Admin dashboard", "Customer portal", "Point of Sale (POS)", "Mobile-friendly app (PWA)", "Other"],
            maps_to_srs_fields=["app_type", "protected_pages"],
        ),
        "features_modules": dict(
            question="Which features matter most? Pick all that apply.",
            why_needed="Selects the main modules and functional requirements.",
            answer_type="multi_choice",
            suggested_options=features + ["Other"],
            maps_to_srs_fields=["main_modules", "functional_requirements"],
        ),
        "data_entities": dict(
            question="What are the main things the app keeps track of? (e.g. products, bookings, students)",
            why_needed="Drives the database tables and relationships.",
            answer_type="free_text", suggested_options=[],
            maps_to_srs_fields=["database_design.tables"],
        ),
        "payments_billing": dict(
            question="Do you need to take payments or send invoices?",
            why_needed="Determines payment and billing requirements.",
            answer_type="single_choice",
            suggested_options=["Yes, online payments", "Yes, invoices only", "No payments"],
            maps_to_srs_fields=["integration_requirements", "functional_requirements"],
        ),
        "reports": dict(
            question="Do you need reports or analytics dashboards?",
            why_needed="Determines reporting requirements.",
            answer_type="yes_no", suggested_options=["Yes", "No"],
            maps_to_srs_fields=["reporting_requirements"],
        ),
        "notifications": dict(
            question="Should the app send notifications (email / SMS / in-app)?",
            why_needed="Determines notification rules.",
            answer_type="multi_choice",
            suggested_options=["Email", "SMS", "In-app only", "No notifications"],
            maps_to_srs_fields=["notification_rules"],
        ),
        "file_uploads": dict(
            question="Will users upload files or images?",
            why_needed="Determines file storage requirements.",
            answer_type="yes_no", suggested_options=["Yes", "No"],
            maps_to_srs_fields=["functional_requirements"],
        ),
        "integrations": dict(
            question="Any other systems to connect with? (payment, maps, messaging…)",
            why_needed="Determines integration requirements.",
            answer_type="free_text", suggested_options=[],
            maps_to_srs_fields=["integration_requirements"],
        ),
        "security_privacy": dict(
            question="Is any of the data sensitive or private (personal, medical, financial)?",
            why_needed="Determines security and privacy requirements.",
            answer_type="single_choice",
            suggested_options=["Yes, very sensitive", "Somewhat", "Not really"],
            maps_to_srs_fields=["security_requirements", "non_functional_requirements"],
        ),
        "performance": dict(
            question="Roughly how many people will use it at the same time?",
            why_needed="Sizes performance and scalability NFRs.",
            answer_type="single_choice",
            suggested_options=["A handful", "Tens to hundreds", "Thousands+", "Not sure"],
            maps_to_srs_fields=["non_functional_requirements"],
        ),
        "devices_mobile": dict(
            question="Should it work well on phones?",
            why_needed="Determines mobile / PWA support.",
            answer_type="single_choice",
            suggested_options=["Yes, mobile-first", "Desktop mainly", "Both equally"],
            maps_to_srs_fields=["ui_ux_requirements"],
        ),
        "languages": dict(
            question="How many languages should the app support?",
            why_needed="Determines localization requirements.",
            answer_type="single_choice",
            suggested_options=["One language", "Two languages", "Three or more", "Not sure"],
            maps_to_srs_fields=["ui_ux_requirements"],
        ),
        "deployment_stack": dict(
            question="Any preference for where it runs or the technology? (optional)",
            why_needed="Captures deployment / stack preferences.",
            answer_type="single_choice",
            suggested_options=["No preference", "Cloud (AWS/Azure/GCP)", "On-premise", "Specific stack (I'll type it)"],
            maps_to_srs_fields=["app_type.example_stack", "constraints"],
        ),
        "special_rules": dict(
            question="Any special rules, approvals, or workflows we should know about?",
            why_needed="Captures business workflows and validation rules.",
            answer_type="free_text", suggested_options=[],
            maps_to_srs_fields=["business_workflows", "validation_rules"],
        ),
    }


# Order questions sensibly; critical first.
_ORDER = [
    "business_type", "main_goal", "users_roles", "auth", "app_surfaces",
    "features_modules", "data_entities", "payments_billing", "public_pages",
    "reports", "notifications", "file_uploads", "security_privacy",
    "performance", "devices_mobile", "languages", "integrations",
    "deployment_stack", "special_rules",
]


def _deterministic_questions(brief: str, domain_key: str, confidence: float,
                             classification: dict | None = None) -> list[dict]:
    """Domain-tailored fallback. Asks ONLY for areas the idea doesn't already cover."""
    bank = _bank(domain_key)
    covered = _covered_areas(brief, classification or {"confidence": confidence})

    # Ask only the gaps (in priority order).
    chosen = [area for area in _ORDER if area not in covered]

    # Guarantee a useful minimum: if the idea covered almost everything, still
    # confirm a few high-value specifics rather than asking nothing.
    _MIN = 5
    if len(chosen) < _MIN:
        for area in ("features_modules", "data_entities", "payments_billing",
                     "users_roles", "reports", "notifications", "special_rules"):
            if area not in chosen:
                chosen.append(area)
            if len(chosen) >= _MIN:
                break
    chosen = chosen[:20]

    questions = []
    for i, area in enumerate(chosen, start=1):
        q = bank[area]
        questions.append({
            "id": f"Q{i}",
            "question": q["question"],
            "why_needed": q["why_needed"],
            "answer_type": q["answer_type"],
            "suggested_options": q["suggested_options"],
            "maps_to_srs_fields": q["maps_to_srs_fields"],
            "coverage_areas": [area],
            "required": area in CRITICAL_AREAS,
        })
    return questions


def _normalize_questions(data) -> list[dict]:
    """Validate + clean an LLM question payload. Raises ValueError if unusable."""
    raw = data.get("questions") if isinstance(data, dict) else data
    if not isinstance(raw, list) or len(raw) < 5:
        raise ValueError("expected a JSON list of at least 5 questions under 'questions'")

    out: list[dict] = []
    seen: set[str] = set()
    for q in raw[:20]:
        if not isinstance(q, dict):
            continue
        text = str(q.get("question") or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue  # drop blanks + duplicates (uniqueness)
        seen.add(key)
        at = str(q.get("answer_type") or "single_choice").strip()
        if at not in ANSWER_TYPES:
            at = "free_text"
        opts = q.get("suggested_options")
        opts = [str(o) for o in opts][:6] if isinstance(opts, list) else []
        cov = q.get("coverage_areas")
        cov = [str(c) for c in cov if c in COVERAGE_AREAS] if isinstance(cov, list) else []
        maps = q.get("maps_to_srs_fields")
        maps = [str(m) for m in maps][:6] if isinstance(maps, list) else []
        out.append({
            "id": f"Q{len(out) + 1}",
            "question": text,
            "why_needed": str(q.get("why_needed") or "").strip(),
            "answer_type": at,
            "suggested_options": opts,
            "maps_to_srs_fields": maps,
            "coverage_areas": cov or ["features_modules"],
            "required": bool(q.get("required", False)),
        })
    if len(out) < 5:
        raise ValueError("fewer than 5 usable questions after cleaning")
    return out


def _reconcile_business(questions: list[dict], domain_key: str, brief: str,
                        classification: dict) -> list[dict]:
    """If the idea already states the business, DROP the 'what business?' question.
    If it's genuinely unknown, make sure a business question leads."""
    known = _business_known(brief, classification)
    if known:
        kept = [q for q in questions if "business_type" not in (q.get("coverage_areas") or [])]
        questions = kept or questions
    else:
        has_business = any("business_type" in (q.get("coverage_areas") or []) for q in questions)
        if not has_business:
            lead = dict(_bank(domain_key)["business_type"])
            questions = [{
                "question": lead["question"], "why_needed": lead["why_needed"],
                "answer_type": lead["answer_type"], "suggested_options": lead["suggested_options"],
                "maps_to_srs_fields": lead["maps_to_srs_fields"], "coverage_areas": ["business_type"],
                "required": True,
            }] + questions
    for i, q in enumerate(questions, start=1):
        q["id"] = f"Q{i}"
    return questions


_FUNC_REQ_SYSTEM = (
    "You generate a plain-English feature checklist for a NON-TECHNICAL business owner. "
    "They will tick which features they want in their software. "
    "Write 15–25 short, simple sentences — each describing ONE thing the software does. "
    "Rules:\n"
    "- No technical jargon, no database words, no developer language.\n"
    "- Write from the end-user perspective: 'Guests can book a room online', "
    "'Staff can see today\\'s arrivals', 'The system sends a confirmation email'.\n"
    "- Cover: what different user types can do, what the system tracks/manages, "
    "what notifications get sent, what reports/summaries exist, and any payment/billing features.\n"
    "- Each option must be under 12 words.\n"
    "Return ONLY JSON (no markdown):\n"
    "{\"question\": \"Which of these should your system be able to do? Select all that apply.\", "
    "\"options\": [\"Feature one\", \"Feature two\", ...]}\n"
    "The LAST option must always be exactly: \"Something else — I will describe it myself\""
)


async def _llm_functional_req_question(
    pid: str, brief: str, domain_key: str, classification: dict,
) -> dict | None:
    """Use LLM to generate a rich, non-technical functional requirements question.

    Returns a single Question dict ready to be injected into the question list,
    or None if the LLM is unavailable or returns an unusable response.
    """
    dom = get_domain(domain_key)
    detected = (classification or {}).get("detected_domain", dom["label"])
    role_names = [r["role_name"] for r in dom.get("roles", []) if r.get("role_key") != "guest"]
    module_names = dom.get("modules", [])

    user_msg = (
        f"DOMAIN: {detected}\n"
        f"USER IDEA: {brief[:1500]}\n"
        f"TYPICAL USER ROLES IN THIS DOMAIN: {', '.join(role_names)}\n"
        f"TYPICAL MODULES IN THIS DOMAIN: {', '.join(module_names)}\n\n"
        "Generate 15–25 plain-English features for this type of system that a "
        "non-technical business owner would recognise and tick. Each item should "
        "describe ONE concrete thing the software does. Keep every item under 12 words."
    )

    try:
        llm = get_llm()
        data = await llm.complete_json(
            system=_FUNC_REQ_SYSTEM,
            user=user_msg,
            label="func_req_question",
            trace_sink=lambda p: bus.trace(pid, p),
        )
        question_text = str(data.get("question") or "").strip()
        options = data.get("options")
        if not question_text or not isinstance(options, list) or len(options) < 10:
            return None
        options = [str(o).strip() for o in options if str(o).strip()]
        # Drop any "something else" the LLM put mid-list; we add a canonical one at the end
        options = [o for o in options if "something else" not in o.lower()]
        options.append("Something else — I will describe it myself")
        return {
            "id": "FUNC_REQ",  # renumbered when injected
            "question": question_text,
            "why_needed": "Determines the functional requirements and main modules of the SRS.",
            "answer_type": "multi_choice",
            "suggested_options": options[:26],  # max 25 real options + "something else"
            "maps_to_srs_fields": ["functional_requirements", "main_modules"],
            "coverage_areas": ["features_modules"],
            "required": True,
        }
    except Exception:  # noqa: BLE001
        return None


async def _llm_questions(pid: str, brief: str, domain_key: str, classification: dict) -> list[dict]:
    """Generate unique, idea-specific questions with the LLM (raises on failure)."""
    dom = get_domain(domain_key)
    confidence = float((classification or {}).get("confidence", 0.5))
    detected = (classification or {}).get("detected_domain", dom["label"])
    covered = sorted(_covered_areas(brief, classification))
    missing = [a for a in COVERAGE_AREAS if a not in covered]
    business_known = _business_known(brief, classification)
    n_lo, n_hi = (10, 16) if len(missing) > 10 else (5, 10)

    # Build domain-specific context so the LLM can ask targeted, relevant questions
    role_names = [r["role_name"] for r in dom.get("roles", []) if r.get("role_key") != "guest"]
    module_names = dom.get("modules", [])
    entity_names = [t["table_name"] for t in dom.get("tables", [])]
    nfr_focus = dom.get("nfr_focus", [])

    system = (
        "You are a friendly product analyst interviewing a NON-TECHNICAL user about "
        "the app they want to build. FIRST read their idea and extract everything it "
        "already tells you. THEN write SIMPLE, plain-language questions — no tech "
        "jargon — ONLY for the information still MISSING that you need to write a "
        "software requirements specification. Never ask about anything the idea already "
        "states, and never ask the same thing twice. Tailor wording and answer options "
        "to THIS specific domain — use domain-specific terminology and realistic options.\n"
        f"Ask between {n_lo} and {n_hi} questions. Return ONLY JSON of the form "
        '{"questions": [{"id": "Q1", "question": "...", "why_needed": "...", '
        '"answer_type": "single_choice|multi_choice|yes_no|free_text|number", '
        '"suggested_options": ["..."], "maps_to_srs_fields": ["..."], '
        '"coverage_areas": ["..."], "required": true}]}. '
        "suggested_options must be [] for free_text/number. "
        f"coverage_areas values must come from this list: {', '.join(COVERAGE_AREAS)}."
    )
    user = (
        f"USER IDEA / BRIEF:\n{brief[:2500]}\n\n"
        f"DETECTED BUSINESS/DOMAIN: {detected} (confidence {confidence:.0%})\n"
        f"TYPICAL ROLES FOR THIS DOMAIN: {', '.join(role_names)}\n"
        f"TYPICAL MODULES FOR THIS DOMAIN: {', '.join(module_names)}\n"
        f"TYPICAL DATA ENTITIES FOR THIS DOMAIN: {', '.join(entity_names)}\n"
        + (f"KEY NON-FUNCTIONAL CONCERNS: {'; '.join(nfr_focus)}\n" if nfr_focus else "")
        + f"FEATURE OPTIONS TO OFFER: {', '.join(dom['feature_options'])}\n\n"
        f"ALREADY KNOWN FROM THE IDEA — do NOT ask about these: {', '.join(covered) or 'little so far'}\n"
        f"STILL MISSING — ask about ONLY these areas: {', '.join(missing) or 'mostly complete; confirm key specifics'}\n\n"
        + ("The business/domain is ALREADY CLEAR from the idea — do NOT ask 'what kind of "
           "business is this?'. Jump straight to clarifying domain-specific details.\n"
           if business_known else
           "The business/domain is unclear — your FIRST question should ask what kind of "
           "business/app this is.\n")
    )

    llm = get_llm()
    data = await llm.complete_json(
        system=system, user=user,
        validator=lambda d: _normalize_questions(d),
        label="question_plan",
        trace_sink=lambda p: bus.trace(pid, p),
    )
    return _normalize_questions(data)


async def plan_questions_node(state: AgentState) -> AgentState:
    pid = state["project_id"]
    brief = state.get("brief", "")
    classification = state.get("classification", {}) or {}
    domain_key = classification.get("domain_key", "custom")
    confidence = float(classification.get("confidence", 0.5))

    await bus.log(pid, "QuestionPlannerAgent", "Planning the right questions…", progress=70)

    questions: list[dict] | None = None
    try:
        await bus.emit(pid, "QuestionPlannerAgent",
                       "Reading the idea and asking only about missing details…", progress=76)
        questions = await _llm_questions(pid, brief, domain_key, classification)
        questions = _reconcile_business(questions, domain_key, brief, classification)
        await bus.emit(pid, "QuestionPlannerAgent",
                       f"LLM generated {len(questions)} gap-filling questions.", level="success", progress=85)
    except LLMUnavailable as exc:
        await bus.emit(pid, "QuestionPlannerAgent",
                       f"LLM not used ({str(exc)[:160]}) — using the domain question bank.",
                       level="warn", progress=82)
    except (LLMRepairFailed, ValueError) as exc:
        await bus.emit(pid, "QuestionPlannerAgent",
                       f"LLM questions unusable ({exc}); using the domain bank.", level="warn", progress=82)
    except Exception as exc:  # noqa: BLE001
        await bus.error(pid, "QuestionPlannerAgent", f"Question planning error: {exc}; using the domain bank.")

    if not questions:
        questions = _deterministic_questions(brief, domain_key, confidence, classification)
        await bus.emit(pid, "QuestionPlannerAgent",
                       f"Prepared {len(questions)} plain-language questions (skipping what the idea already covers).",
                       level="success", progress=85, data={"count": len(questions)})

    # Replace the generic features_modules question with a rich, non-technical LLM checklist.
    # This is a best-effort upgrade — if the LLM fails we keep whatever is already there.
    await bus.emit(pid, "QuestionPlannerAgent",
                   "Building functional requirements checklist…", progress=87)
    func_req_q = await _llm_functional_req_question(pid, brief, domain_key, classification)
    if func_req_q:
        # Remove any existing features_modules question(s) generated earlier
        other_qs = [q for q in questions
                    if "features_modules" not in (q.get("coverage_areas") or [])]
        # Insert the rich question right after the first question (roles/auth typically lead)
        insert_at = min(2, len(other_qs))
        questions = other_qs[:insert_at] + [func_req_q] + other_qs[insert_at:]
        # Renumber sequentially
        for i, q in enumerate(questions, start=1):
            q["id"] = f"Q{i}"
        await bus.emit(pid, "QuestionPlannerAgent",
                       f"Functional requirements checklist ready ({len(func_req_q['suggested_options'])} options).",
                       level="success", progress=89)

    return {**state, "questions": questions}
