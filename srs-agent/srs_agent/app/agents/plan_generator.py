"""PlanGeneratorAgent — the plan the customer approves before anything is written.

The SRS is this repo's deliverable, so the plan's job is *confirmation*, not
specification: one page of plain English saying who uses the thing, what screens
exist, what it keeps track of and what it does — in words a non-technical owner
can actually check.

Same shape as the SRS generator: a deterministic skeleton composed from the
interview answers first, then an LLM pass that rewrites it in this customer's
own terms. Any failure keeps the skeleton, so the plan screen always has
something to approve.
"""
from __future__ import annotations

import json
import logging
import re

from ..knowledge import app_types as catalog
from ..knowledge import topics
from ..llm import LLMRepairFailed, LLMUnavailable, get_llm
from ..services.events import bus
from .customer_context import customer_context

log = logging.getLogger("agentforge.plan")

_SYS = """You are a product architect writing a plan for a NON-TECHNICAL \
customer to approve. You are given everything one customer asked for, and you \
produce one complete plan of the application that answers it.

Model what people are trying to DO before you decide what screens exist. A \
workflow is a whole job, start to finish: who starts it, what they see, what \
they change, and where they end up. Screens are then whatever those workflows \
need — nothing more.

This matters because the usual failure is to reach for the shape of the \
category. A shop gets a storefront, a cart and an admin table; a business tool \
gets a dashboard, a list and a form. Those are not requirements, they are \
habits, and an app built from them fits nobody.

This plan is a CEILING, not a summary. Everything written afterwards is derived \
from it and nothing may exceed it: the specification's tables come from your \
`records` and nothing else, its roles from your `users`, its pages from your \
`screens`, and every one of its requirements from your `users`, `features` and \
`workflows`. A record you leave out cannot be added later; a screen you forget \
is a screen the finished app does not have. Say the whole thing here.

Rules:
- Every screen carries a `purpose` naming the job it exists for. If the only \
honest purpose is "applications like this usually have one", do not create it.
- Every record lists at least two things it `keeps`. A record with no fields \
becomes an empty table. Write plain labels — "Price", not "Price (money)" — \
because these become field names literally.
- At least one `workflow` runs a whole job start to finish, in three steps or \
more: who starts it, what they see, what they change, where they end up.
- Where people sign in, each of them gets at least two `can_do` lines.
- Ask an open question rather than inventing an answer. Mark it required when \
the app cannot be specified without it.
- Use only the records, roles and actions the answers support. Do not add a \
record because the domain usually has one.
- Plain language throughout. No jargon: say "records" not "entities", "log in" \
not "authentication", "pages" not "routes".

Return ONLY a JSON object:
{
  "product_intent": "one paragraph: what this is and who it is for",
  "users": [{"role": "Cashier", "can_do": ["short sentence", ...]}],
  "screens": [{"name": "Sale Terminal", "purpose": "why it exists", "who": ["Cashier"]}],
  "records": [{"name": "Product", "keeps": ["Name", "Price", ...]}],
  "workflows": [{"name": "Taking a sale", "steps": ["...", "..."]}],
  "features": ["short sentence describing ONE thing the software does", ...],
  "look_and_feel": "one or two sentences on theme, colour and devices",
  "assumptions": ["something we decided for them, stated plainly"],
  "open_questions": [{"question": "...", "required": true}]
}"""

_REVISION_TAIL = (
    "Return the complete revised plan. Change what they asked for and leave the "
    "rest as it is — a revision is not a re-plan."
)


def _plan_validator(pack: dict | None = None):
    """A depth floor, sized to the kind of app this is.

    The old floor asked for a non-empty intent, one named screen and three
    features — which a plan with `records: [{"name": "Product", "keeps": []}]`
    and no workflows passes cleanly. That matters because the plan is not a
    summary of the SRS, it is a CEILING on it: `_plan_scope_guard` rejects any
    table the plan did not name, and roles, pages and every functional
    requirement come from the plan alone. A thin plan cannot be recovered from
    later, so the repair loop should fire here rather than let it through.

    Only ever used as the LLM's validator. `build_offline_plan` does not pass
    through it, so raising the floor cannot make the deterministic fallback
    raise — the worst case is another repair attempt and then the skeleton.

    Sized to the archetype, because a single-page site legitimately has no
    records and no workflows and should not be failed for it.
    """
    pack = pack or {}
    archetype = str(pack.get("archetype") or "")
    thin = archetype in ("landing-single-page", "single-tool", "marketing")
    wants_auth = str(pack.get("auth_policy") or "") == "required"

    def validate(d: dict) -> None:
        if not isinstance(d, dict):
            raise ValueError("plan must be a JSON object")

        intent = str(d.get("product_intent") or "").strip()
        if len(intent) < 120:
            raise ValueError(
                "'product_intent' must be a full paragraph saying what this is "
                "and who it is for — one line is not enough for someone to "
                "approve")

        screens = [s for s in (d.get("screens") or [])
                   if isinstance(s, dict) and str(s.get("name") or "").strip()]
        if not screens:
            raise ValueError("provide at least one screen, each with a 'name' "
                             "and a 'purpose'")

        blank = [s["name"] for s in screens if not str(s.get("purpose") or "").strip()]
        if blank:
            raise ValueError(
                f"every screen needs a 'purpose' naming the job it exists for; "
                f"missing on: {', '.join(str(b) for b in blank[:5])}")

        feats = [f for f in (d.get("features") or []) if str(f).strip()]
        if len(feats) < 5:
            raise ValueError("provide at least 5 'features', each one plain "
                             "sentence describing ONE thing the software does")

        if thin:
            return

        records = [r for r in (d.get("records") or [])
                   if isinstance(r, dict) and str(r.get("name") or "").strip()]
        if len(records) < 2:
            raise ValueError("provide at least 2 'records' — this app keeps "
                             "track of things, so say what they are")
        empty = [r["name"] for r in records
                 if not [k for k in (r.get("keeps") or []) if str(k).strip()]]
        if empty:
            raise ValueError(
                f"every record needs at least 2 things it 'keeps'; empty on: "
                f"{', '.join(str(e) for e in empty[:5])}")
        shallow = [r["name"] for r in records
                   if len([k for k in (r.get("keeps") or []) if str(k).strip()]) < 2]
        if shallow:
            raise ValueError(
                f"these records keep only one thing, which is not a record: "
                f"{', '.join(str(s) for s in shallow[:5])}")

        flows = [w for w in (d.get("workflows") or [])
                 if isinstance(w, dict)
                 and len([s for s in (w.get("steps") or []) if str(s).strip()]) >= 2]
        if not flows:
            raise ValueError("provide at least one 'workflow' with 2 or more "
                             "steps — a whole job from start to finish")

        if wants_auth:
            able = [u for u in (d.get("users") or [])
                    if isinstance(u, dict)
                    and len([c for c in (u.get("can_do") or []) if str(c).strip()]) >= 2]
            if not able:
                raise ValueError("this app has people who sign in, so at least "
                                 "one entry in 'users' needs 2 or more 'can_do' "
                                 "lines")

    return validate


def _ans(session: dict, key: str, default=None):
    return topics.ans(session, key, default)


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    return [text] if text else []


def _title(text: str) -> str:
    text = str(text or "").replace("_", " ").strip()
    return text[:1].upper() + text[1:] if text else text


_PAGE_PURPOSE = {
    "dashboard": "The first thing staff see, with the day's figures",
    "entity_crud": "Where these records are listed, added and edited",
    "report": "Where the numbers are pulled together for printing or export",
    "settings": "Where the app is configured",
    "marketing": "The public page a visitor lands on",
    "auth": "Where people sign in",
    "catalog": "A browsable list",
    "detail": "The full view of one item",
    "custom": "The main working screen",
}


def build_offline_plan(*, project: dict, session: dict, brief: str = "") -> dict:
    """A complete plan from the interview answers alone. Always succeeds."""
    pack = session.get("pack") or catalog.build_pack(
        session.get("app_type") or catalog.DEFAULT_APP_TYPE,
        brief or project.get("raw_idea", ""),
    )
    answers = session.get("answers") or {}
    app_name = str(_ans(session, "app_name") or project.get("title") or "The app").strip()
    domain_label = str(pack.get("domain_label") or "").strip()

    idea = str(project.get("raw_idea") or "").strip()[:400]
    opening = f"{app_name} is a {pack.get('app_label', 'web application')}"

    if domain_label and pack.get("domain_confidence", 0) >= 0.6:
        opening += f" for {domain_label.lower()}"
    intent = f"{opening}. {idea}".strip()

    users: list[dict] = []
    for role in topics.roles_list(session):
        can_do = _as_list(_ans(session, f"role_functions:{role}"))
        users.append({"role": _title(role), "can_do": can_do})
    if not users:
        page_funcs = _as_list(_ans(session, "page_functions"))
        users.append({"role": "Visitor",
                      "can_do": page_funcs or ["Browse the site", "Get in touch"]})

    screens: list[dict] = []
    for page in pack.get("pages") or []:
        screens.append({
            "name": page.get("name", "Page"),
            "purpose": _PAGE_PURPOSE.get(str(page.get("type", "")),
                                         "A screen in the app")
                       + f" ({page.get('route', '/')}).",
            "who": [u["role"] for u in users],
        })
    for section in _as_list(_ans(session, "sections")):
        screens.append({"name": _title(section),
                        "purpose": "A section of the single page.",
                        "who": ["Visitor"]})

    records: list[dict] = []
    for table in topics.tables_list(session):
        keeps = [_title(f) for f in _as_list(_ans(session, f"table_entities:{table}"))]
        records.append({"name": _title(table), "keeps": keeps})
    for field_group in ("lead_fields", "tool_inputs"):
        fields = _as_list(_ans(session, field_group))
        if fields:
            records.append({"name": "Enquiry" if field_group == "lead_fields" else "Entry",
                            "keeps": [_title(f) for f in fields]})

    by_name = {str(t.get("table_name") or "").lower(): t
               for t in (pack.get("domain_tables") or []) if isinstance(t, dict)}
    for record in records:
        if record["keeps"]:
            continue
        known = by_name.get(record["name"].lower().replace(" ", "_"))
        fields = [f.get("name") if isinstance(f, dict) else str(f)
                  for f in ((known or {}).get("fields") or [])]
        record["keeps"] = [_title(f) for f in fields
                           if f and f not in ("id", "created_at", "updated_at")][:8]

    workflows = [
        {"name": w.get("workflow_name", "Workflow"), "steps": list(w.get("steps") or [])}
        for w in (pack.get("domain_workflows") or [])
    ]

    feature_topics = (
        "role_functions", "page_functions", "offerings", "pos_payments",
        "pos_receipt", "pos_stock_rules", "saas_plans", "store_payments",
        "store_fulfilment", "dash_metrics", "dash_exports", "blog_workflow",
        "blog_organisation", "blog_engagement", "tool_outputs",
        "contact_channels", "social_proof",
    )
    features: list[str] = []
    for key, entry in answers.items():
        if key.split(":", 1)[0] not in feature_topics:
            continue
        for item in _as_list(entry.get("value")):
            label = _title(item)
            if label not in features:
                features.append(label)
    for feat in pack.get("features") or []:
        if len(features) >= 8:
            break
        if feat not in features:
            features.append(feat)

    theme = _ans(session, "theme_type") or "light"
    palette = _ans(session, "color_palette") or pack.get("palette_name", "indigo")
    devices = _as_list(_ans(session, "responsive_pwa")) or ["responsive"]
    look = (f"A {theme} theme on a {str(palette).replace('_', ' ')} palette, "
            f"built for {', '.join(devices)}.")

    assumptions: list[str] = []
    if pack.get("auth_policy") == "required" and not topics.roles_list(session):
        assumptions.append("People will need to log in, with a single admin role.")
    if pack.get("auth_policy") == "disabled":
        assumptions.append("There is no login — everything on the site is public.")
    if not records:
        assumptions.append("Nothing is stored between visits beyond enquiries.")

    notes = customer_notes(session)
    for item in split_notes(notes):
        if item not in features:
            features.append(item)

    return {

        "app_name": app_name,
        "product_intent": intent,
        "users": users,
        "screens": screens,
        "records": records,
        "workflows": workflows,
        "features": features,
        "look_and_feel": look,
        "assumptions": assumptions,
        "open_questions": [],
        "customer_notes": notes,
    }


def customer_notes(session: dict) -> str:
    """Whatever they wrote in the free-text box at the end of the interview."""
    entry = (session.get("answers") or {}).get("extra_notes") or {}
    for field in ("custom_text", "value", "text"):
        text = entry.get(field)
        if isinstance(text, list):
            text = " ".join(str(t) for t in text)
        text = str(text or "").strip()
        if text:
            return text
    return ""


def split_notes(notes: str) -> list[str]:
    """One free-text paragraph as separate things to build.

    Split on sentence ends and on the list commas people actually write
    ("opening hours, a photo gallery and reviews"). Deliberately conservative:
    a fragment that reads as half a thought is worse than one long feature.
    """
    if not notes.strip():
        return []
    out: list[str] = []
    for sentence in re.split(r"(?<=[.!?;])\s+|\n+", notes):
        for part in re.split(r",\s*(?:and\s+)?|\s+and\s+(?=[a-z])", sentence):
            item = _title(part.strip(" .;,"))
            if len(item) > 3 and item not in out:
                out.append(item)
    return out[:12]


def _answers_digest(session: dict) -> str:
    """What they were asked, and what they said back.

    This used to emit the raw topic key — `- pos_payments: ['cash', 'card']` —
    which is the storage key, not a sentence. The SRS generator has always done
    the better thing two modules over (`srs_generator._answers_digest`): it
    joins each answer to the question that produced it, so the model reads
    `- How can a customer pay at the counter? → cash, card`. The join is direct,
    because `question["id"]` IS the answers dict's key.

    That difference matters more here than anywhere else. The plan is a hard
    ceiling on the SRS — `_plan_scope_guard` rejects any table the plan did not
    name, and roles, pages and every functional requirement are derived from
    the plan alone — so whatever the planner cannot understand is not merely
    missing from the plan, it is missing from the finished app.

    Attachments come along too, the way `interview._answers_digest` carries
    them: a customer who photographed their price list has answered more fully
    than the chips did, and that half was invisible here.
    """
    by_key = {q.get("id"): q for q in (session.get("questions") or [])
              if isinstance(q, dict) and q.get("id")}
    lines = []
    for key, entry in (session.get("answers") or {}).items():
        if not isinstance(entry, dict):
            continue
        value = entry.get("value")
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        elif isinstance(value, dict):
            value = json.dumps(value, ensure_ascii=False)

        question = (by_key.get(key) or {}).get("question") or key
        lines.append(f"- {question} → {value}")

        typed = str(entry.get("custom_text") or entry.get("text") or "").strip()
        if typed and typed not in str(value):
            lines.append(f"    they typed: {typed}")
        for att in (entry.get("attachments") or []):
            text = str((att or {}).get("text") or "").strip()
            if text:
                name = str((att or {}).get("filename") or "a file")
                lines.append(f"    they attached {name}: {text[:600]}")

        why = str((by_key.get(key) or {}).get("why_needed") or "").strip()
        if why and not typed:
            lines.append(f"    (asked because: {why[:140]})")
    return "\n".join(lines) or "(nothing recorded)"


def _what_nobody_asked(coverage: dict | None) -> str:
    """The areas the interview never covered, named rather than scored.

    `compute_coverage` runs one step before this, in `orchestrator.generate_plan`
    — and only its integer `score` was ever kept. The interesting half is the
    list: these are the parts of the app nobody was asked about, which is
    exactly the set the model would otherwise quietly invent an answer for.
    """
    if not isinstance(coverage, dict):
        return ""
    critical = [str(a) for a in (coverage.get("critical_missing") or [])]
    optional = [str(a) for a in (coverage.get("optional_missing") or [])]
    other = [str(a) for a in (coverage.get("missing") or [])
             if a not in critical and a not in optional]
    if not (critical or optional or other):
        return ""

    parts = ["NOBODY ASKED ABOUT THESE — the interview never covered them:"]
    if critical:
        parts.append("  important: " + ", ".join(critical))
    if optional or other:
        parts.append("  minor: " + ", ".join(optional + other))
    parts.append(
        "For each one, either state plainly in `assumptions` what you decided "
        "on their behalf, or raise it in `open_questions`. Do not leave it "
        "silently settled — an assumption nobody can see is one nobody can "
        "correct.")
    return "\n".join(parts)


def _what_we_worked_out(project: dict) -> str:
    """What the classifier already decided, which the planner never saw."""
    cls = project.get("classification") or {}
    complexity = project.get("complexity") or {}
    stack = project.get("suggested_stack") or {}
    rows = []
    if project.get("detected_domain") or cls.get("detected_domain"):
        rows.append(f"  domain: {project.get('detected_domain') or cls.get('detected_domain')}")
    if cls.get("app_type"):
        rows.append(f"  kind of app: {cls['app_type']}")
    if cls.get("reasoning"):
        rows.append(f"  why we think so: {str(cls['reasoning'])[:300]}")
    if complexity.get("overall"):
        rows.append(f"  complexity: {complexity['overall']}")
    if stack:
        rows.append("  stack already fixed: "
                    + ", ".join(f"{k}={v}" for k, v in stack.items()
                                if k != "locked" and v))
    if not rows:
        return ""
    return "WHAT WE HAVE ALREADY WORKED OUT ABOUT THIS BUSINESS:\n" + "\n".join(rows)


def _domain_library(pack: dict) -> str:
    """What apps in this domain usually hold — offered, never imposed.

    The knowledge pack carries 26 keys and the plan prompt used three. The rest
    is a domain library with real field lists, and a planner that cannot see it
    invents `Product(name, price)` where the library already says what a product
    record in this trade actually keeps.
    """
    rows = []

    thin = str(pack.get("archetype") or "") in ("landing-single-page", "single-tool")

    tables = [] if thin else [t for t in (pack.get("domain_tables") or [])
                              if isinstance(t, dict)]
    if tables:
        shaped = []
        for t in tables[:14]:
            name = t.get("table_name") or t.get("name")
            fields = [f.get("name") if isinstance(f, dict) else str(f)
                      for f in (t.get("fields") or [])]
            fields = [f for f in fields if f][:10]
            if name:
                shaped.append(f"  {name}: {', '.join(fields) or '—'}")
        if shaped:
            rows.append("Records this trade usually keeps:\n" + "\n".join(shaped))

    offered = (("Modules", "domain_modules"),) if thin else (
        ("Roles", "roles"), ("Modules", "domain_modules"),
        ("Integrations", "domain_integrations"),
        ("Things it usually does", "operations"))
    for label, key in offered:
        items = pack.get(key) or []
        flat = []
        for item in items[:14]:
            if isinstance(item, dict):
                flat.append(str(item.get("role_name") or item.get("name")
                                or item.get("label") or ""))
            else:
                flat.append(str(item))
        flat = [f for f in flat if f.strip()]
        if flat:
            rows.append(f"{label}: {', '.join(flat)}")

    required = [str(p) for p in (pack.get("required_pages") or [])]
    if required:
        rows.append("Pages this kind of app cannot do without: "
                    + ", ".join(required))
    banned = [str(p) for p in (pack.get("prohibited_page_types") or [])]
    if banned:
        rows.append("Pages this kind of app must NOT have: " + ", ".join(banned))

    if not rows:
        return ""
    return ("WHAT APPS IN THIS TRADE USUALLY HAVE — a menu, not a checklist. "
            "Use an item only where the answers above support it; the rule "
            "against adding a record because the domain usually has one still "
            "holds.\n" + "\n\n".join(rows))


async def generate_plan(*, project: dict, session: dict, brief: str = "",
                        previous: dict | None = None, revision: str = "",
                        coverage: dict | None = None) -> dict:
    """Build the plan. Returns the enriched plan, or the skeleton on any failure."""
    pid = project.get("id", "")
    skeleton = build_offline_plan(project=project, session=session, brief=brief)

    pack = session.get("pack") or {}

    parts = [
        customer_context(brief=brief, session=session, project=project)
        or f"THE CUSTOMER'S IDEA:\n{(brief or project.get('raw_idea', ''))[:3000]}",
        "",
        f"APP TYPE: {pack.get('app_label', 'unknown')} ({pack.get('archetype', '')})",
        f"BUSINESS DOMAIN: {pack.get('domain_label', 'general')}",
    ]
    if project.get("language"):

        parts.append(f"WRITE THE PLAN IN: {project['language']}")
    parts.append("")

    for block in (_what_we_worked_out(project), _domain_library(pack)):
        if block:
            parts += [block, ""]

    parts += [f"WHAT THEY ANSWERED:\n{_answers_digest(session)}", ""]

    gaps = _what_nobody_asked(coverage)
    if gaps:
        parts += [gaps, ""]

    notes = customer_notes(session)
    if notes:

        parts += [
            "IN THE CUSTOMER'S OWN WORDS — they wrote this at the end, unprompted, "
            "when asked what else the site should show:",
            f'"""{notes[:2000]}"""',
            "",
            "Everything they named there must appear in the plan — as a screen, a "
            "section, a record or a feature, whichever it actually is. Do not "
            "summarise it away, and do not drop the parts you have no question for.",
            "",
        ]

    parts += [
        "A PLAN ASSEMBLED FROM THOSE ANSWERS (rewrite it in their terms; keep "
        "anything that is already right):",
        "```json",
        json.dumps(skeleton, ensure_ascii=False)[:12000],
        "```",
    ]
    if previous is not None:
        parts += [
            "",
            "## The plan as it stands",
            "```json",
            json.dumps(previous, ensure_ascii=False)[:12000],
            "```",
            "",
            "## What the customer wants changed",
            revision or "(no change requested)",
            "",
            _REVISION_TAIL,
        ]

    try:
        await bus.emit(pid, "PlanGeneratorAgent",
                       "Turning the answers into a plan…", progress=30)
        plan = await get_llm().complete_json(
            system=_SYS, user="\n".join(parts), validator=_plan_validator(pack),
            label="plan_generate",
            trace_sink=(lambda p: bus.trace(pid, p)) if pid else None,
        )
        merged = _merge(skeleton, plan)
        await bus.emit(pid, "PlanGeneratorAgent",
                       f"Plan ready: {len(merged['screens'])} screens, "
                       f"{len(merged['records'])} record types, "
                       f"{len(merged['features'])} features.",
                       level="success", progress=90)
        return merged
    except LLMUnavailable as exc:
        await bus.emit(pid, "PlanGeneratorAgent",
                       f"LLM not used ({str(exc)[:140]}) — using the plan built "
                       "from your answers.", level="warn", progress=90)
    except LLMRepairFailed as exc:
        await bus.error(pid, "PlanGeneratorAgent",
                        f"LLM plan didn't validate after retries; kept the plan "
                        f"built from your answers. ({exc.label})")
    except Exception as exc:  # noqa: BLE001
        await bus.error(pid, "PlanGeneratorAgent",
                        f"Plan generation error: {exc}; kept the plan built from "
                        "your answers.")

    if previous is not None and revision:

        skeleton = {**previous,
                    "open_questions": list(previous.get("open_questions") or [])}
        skeleton.setdefault("assumptions", []).append(
            f"Requested change not applied automatically: {revision[:200]}")
    return skeleton


def _merge(skeleton: dict, plan: dict) -> dict:
    """The model's plan, with the skeleton filling anything it left empty."""
    out = dict(skeleton)
    for key in ("product_intent", "look_and_feel"):
        value = str(plan.get(key) or "").strip()
        if value:
            out[key] = value
    for key in ("users", "screens", "records", "workflows", "features",
                "assumptions", "open_questions"):
        value = plan.get(key)
        if isinstance(value, list) and value:
            out[key] = value
    out["open_questions"] = [
        {"question": str(q.get("question") if isinstance(q, dict) else q).strip(),
         "required": bool(q.get("required")) if isinstance(q, dict) else False}
        for q in (out.get("open_questions") or [])
        if str(q.get("question") if isinstance(q, dict) else q).strip()
    ]

    out["customer_notes"] = str(skeleton.get("customer_notes") or "")
    return out


def render_plan_markdown(plan: dict, *, app_name: str = "") -> str:
    """The plan as Markdown, for the review screen."""
    out: list[str] = []
    if app_name:
        out += [f"# {app_name}", ""]
    out += [str(plan.get("product_intent") or "").strip(), ""]

    notes = str(plan.get("customer_notes") or "").strip()
    if notes:
        out += ["## In your own words", ""]
        out += [line for line in notes.splitlines() if line.strip()]
        out.append("")

    users = plan.get("users") or []
    if users:
        out.append("## Who uses it")
        out.append("")
        for u in users:
            out.append(f"**{u.get('role', 'User')}**")
            for item in u.get("can_do") or []:
                out.append(f"- {item}")
            out.append("")

    screens = plan.get("screens") or []
    if screens:
        out += ["## Screens", "", "| Screen | What it is for | Who sees it |",
                "| --- | --- | --- |"]
        for s in screens:
            who = ", ".join(s.get("who") or []) or "Everyone"
            out.append(f"| {s.get('name', '')} | {s.get('purpose', '')} | {who} |")
        out.append("")

    records = plan.get("records") or []
    if records:
        out += ["## What it keeps track of", ""]
        for r in records:
            keeps = ", ".join(r.get("keeps") or []) or "—"
            out.append(f"- **{r.get('name', '')}** — {keeps}")
        out.append("")

    workflows = plan.get("workflows") or []
    if workflows:
        out += ["## How the work flows", ""]
        for w in workflows:
            out.append(f"**{w.get('name', 'Workflow')}**")
            for i, step in enumerate(w.get("steps") or [], start=1):
                out.append(f"{i}. {step}")
            out.append("")

    features = plan.get("features") or []
    if features:
        out += ["## What it does", ""]
        out += [f"- {f}" for f in features]
        out.append("")

    if plan.get("look_and_feel"):
        out += ["## Look and feel", "", str(plan["look_and_feel"]), ""]

    assumptions = plan.get("assumptions") or []
    if assumptions:
        out += ["## Things we assumed", ""]
        out += [f"- {a}" for a in assumptions]
        out.append("")

    open_qs = plan.get("open_questions") or []
    if open_qs:
        out += ["## Still to settle", ""]
        for q in open_qs:
            mark = " **(needed before we can write the SRS)**" if q.get("required") else ""
            out.append(f"- {q.get('question', '')}{mark}")
        out.append("")

    return "\n".join(out).strip() + "\n"
