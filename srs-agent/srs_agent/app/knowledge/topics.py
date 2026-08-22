"""The interview backbone.

An ordered list of topics, each with a condition. `app_type` is always first
because every later topic reads from it — the queue is re-evaluated after every
answer, so answering "no auth" genuinely removes the role questions rather than
skipping past them.

Each Topic carries `fallback_options`. If the model returns nothing usable the
UI still gets a real question, so a bad LLM response degrades the wording, never
the flow.

`srs_fields` and `coverage` are what let each emitted question satisfy the
existing `Question` contract, so the CoverageAuditor and the SRS mapping keep
working without knowing this module exists.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from . import app_types as catalog


KINDS = ("single", "multi", "yes_no", "number", "text", "upload")


@dataclass
class Topic:
    key: str
    kind: str
    label: str
    intent: str
    applies_to: Callable[[dict], bool] = lambda s: True

    options_from: Callable[[dict, dict], list] | None = None
    fallback_options: list = field(default_factory=list)

    options_locked: bool = False

    repeats_over: Callable[[dict], list] | None = None
    placeholder: str = ""

    profiles: tuple[str, ...] = ()

    srs_fields: tuple[str, ...] = ()
    coverage: tuple[str, ...] = ()

    fixed: str = ""

    optional: bool = False

    multiline: bool = False


def ans(s: dict, key: str, default=None):
    entry = s.get("answers", {}).get(key)
    return default if entry is None else entry.get("value", default)


def has_auth(s: dict) -> bool:
    v = ans(s, "auth")
    if v is None:
        return bool(_pack(s).get("auth_default", True))
    return v in (True, "yes", "true", 1)


def wants_images(s: dict) -> bool:
    v = ans(s, "images")
    return v in (True, "yes", "true", 1)


def roles_list(s: dict) -> list[str]:
    v = ans(s, "auth_roles") or []
    if isinstance(v, str):
        v = [v]
    return [str(x) for x in v]


def tables_list(s: dict) -> list[str]:
    v = ans(s, "data_tables") or []
    if isinstance(v, str):
        v = [v]
    return [str(x) for x in v]


def _pack(s: dict) -> dict:
    return s.get("pack") or {}


def _yes_no() -> list:
    return [{"label": "Yes", "value": True}, {"label": "No", "value": False}]


CRUD = "fullstack-crud"
LANDING = "landing-single-page"
TOOL = "single-tool"


def archetype(s: dict) -> str:
    return str(_pack(s).get("archetype") or CRUD)


def question_set(s: dict) -> str:
    """Which profile's questions this session asks."""
    pack = _pack(s)
    return str(pack.get("question_set") or pack.get("app_type") or "saas")


RECORD_PROFILES = ("pos", "saas", "ecommerce", "dashboard", "blog", "other")


def only_for(*kinds: str) -> Any:
    """Gate a topic to the archetypes it actually makes sense for."""
    return lambda s: archetype(s) in kinds


def _and(*conditions) -> Any:
    return lambda s: all(cond(s) for cond in conditions)


def wants_leads(s: dict) -> bool:
    v = ans(s, "lead_capture")
    if v is None:
        return True
    return v in (True, "yes", "true", 1)


def _sections_options(s: dict, item: dict | None = None) -> list:
    """The bands this kind of page is built from, per the app type's own plan."""
    pages = _pack(s).get("pages") or []
    sections: list[str] = []
    for page in pages:
        for name in page.get("sections") or []:
            if name not in sections:
                sections.append(name)
    if not sections:
        sections = ["Hero", "Services", "About", "Testimonials", "Contact"]
    return [{"label": name, "value": _snake_value(name)} for name in sections[:12]]


def _offering_options(s: dict, item: dict | None = None) -> list:
    """Deliberately empty, so the model reads the customer's own idea.

    The domain library is a *schema* library — for a cleaning company that
    matched the hospitality domain it would suggest "Room Type" and "Rate Plan"
    as services to sell. There is no deterministic source for what a business
    offers, and the per-question call already conditions its options on the raw
    idea, which is the only place that answer actually lives.
    """
    return []


def _snake_value(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_") or "item"


def _palette_options(s: dict) -> list:
    preferred = _pack(s).get("palette_name")
    labels = {
        "business": "Corporate blue",
        "mint": "Fresh mint",
        "navy": "Deep navy & gold",
        "gold": "Black & gold",
        "indigo": "Modern indigo",
    }
    opts = [
        {"label": labels[k], "value": k, "hint": v["primary"]}
        for k, v in catalog.PALETTES.items()
    ]

    opts.sort(key=lambda o: o["value"] != preferred)
    return opts


def _domain_tables(s: dict) -> list[dict]:
    return _pack(s).get("domain_tables") or []


_ES_PLURAL = ("sses", "xes", "zes", "ches", "shes")


def _norm(name: str) -> str:
    """Loose singular key, so 'Sales Orders' and 'sales_order' compare equal."""
    key = re.sub(r"[^a-z0-9]+", "", str(name).lower())
    if key.endswith("ies"):
        return key[:-3] + "y"
    if key.endswith(_ES_PLURAL):
        return key[:-2]
    if key.endswith("s") and not key.endswith("ss"):
        return key[:-1]
    return key


def _match_domain_table(subject: str, s: dict) -> dict | None:
    want = _norm(subject)
    if not want:
        return None
    tables = _domain_tables(s)
    for t in tables:
        if _norm(t.get("table_name", "")) == want:
            return t

    if len(want) >= 5:
        for t in tables:
            other = _norm(t.get("table_name", ""))
            if other and (want in other or other in want):
                return t
    return None


_BORING_FIELDS = {"id", "created_at", "updated_at", "deleted_at",
                  "password_hash", "old_values", "new_values", "ip_address"}


def _field_options(s: dict, item: dict) -> list:
    """Real fields for THIS record type, drawn from the matched domain table."""
    table = _match_domain_table((item or {}).get("subject") or "", s)
    if not table:
        return []

    out = []
    for fld in table.get("fields") or []:
        name = str(fld.get("name") or "")
        if not name or name in _BORING_FIELDS or fld.get("primary_key"):
            continue
        label = re.sub(r"_(id|at)$", "", name).replace("_", " ").strip().title()
        opt = {"label": label or name, "value": name}
        if fld.get("type") == "foreign_key":
            opt["hint"] = "links to another record"
        elif fld.get("values"):
            opt["hint"] = " / ".join(str(v) for v in fld["values"][:3])
        out.append(opt)
    return out[:14]


_WHAT_HAPPENS = {
    "pos": "The app IS the till — ring up what someone is buying and take "
           "payment at the counter",
    "ecommerce": "Customers order and pay on the site themselves, and "
                 "something gets shipped or collected",
    "saas": "Customers sign up for their own account and use it on their own, "
            "usually paying a subscription",
    "dashboard": "Your own people keep the records — bookings, jobs, members, "
                 "stock — and work from them all day",
    "blog": "Writing is the point: pieces get published and readers come to "
            "read them",
    "landing": "One page that explains one thing and collects sign-ups",
    "portfolio": "Finished work put on show — there is nothing to run or "
                 "keep track of",
    "utility": "One small job done on the spot, and nothing is kept afterwards",
    "other": "None of these describe it — tell us what happens in it",
}


def _mark_auth(options: list) -> list:
    """
    Say which categories mean "no login", because three of them do.

    `landing`, `portfolio` and `utility` carry `auth_policy: "disabled"`, and
    that is not a hint — `_auth_on` in plan_srs.py short-circuits on it, the
    SRS then describes no roles and no protected pages, and the handoff prompt
    tells the builder in as many words: "There are no user accounts and no
    login. Every page is public." So this question decides authentication for
    the whole app while appearing to ask only what kind of thing it is, and
    nothing on the screen said so. Answering it wrongly is not a mislabel; it
    silently removes the login.
    """
    out = []
    for opt in options:
        opt = dict(opt)
        key = opt.get("value")
        spec = catalog.APP_TYPES.get(key) or {}
        opt["hint"] = _WHAT_HAPPENS.get(key) or opt.get("hint") or ""
        if str(spec.get("auth_policy")) == "disabled":
            hint = str(opt.get("hint") or "").rstrip(" .")
            opt["hint"] = f"{hint} — nobody logs in" if hint else "Nobody logs in"
        out.append(opt)
    return out


def _app_type_options(s: dict) -> list:
    """
    The nine build categories, best guess first.

    This used to be `catalog.app_type_options()` with the session ignored, so
    every idea ever typed was offered "POS / Retail" as option one — that is
    simply the first key in the APP_TYPES dict. A school library and a dental
    clinic both came out of the interview classified as POS / Retail, and the
    whole spec, the requirement pack and the generated project's folder name
    followed from it.

    The order is all that changes. Every category is still offered, still in
    one list, and the customer still picks — a wrong guess costs them one
    extra glance, not a wrong app. What it must never do is look confident
    when it is not, so the hint says which way the suggestion came:

      * the model read the idea      -> "Suggested — <its reason>"
      * only keywords matched        -> "Closest match to what you wrote"
      * nothing matched at all       -> no marker, plain dict order

    A guess is never pre-selected. Ordering invites; a filled-in radio button
    decides, and this is the customer's decision to make.
    """
    options = _mark_auth(catalog.app_type_options())
    guess = str((s or {}).get("guessed_app_type") or "").strip()
    if not guess:
        return options

    try:
        confidence = float((s or {}).get("guessed_app_type_confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0

    if confidence < 0.4:
        return options

    why = str((s or {}).get("guessed_app_type_why") or "").strip()
    ordered, chosen = [], None
    for opt in options:
        if opt.get("value") == guess and chosen is None:
            chosen = dict(opt)
        else:
            ordered.append(opt)
    if chosen is None:
        return options

    reason = f"Suggested — {why}" if why else "Closest match to what you wrote"

    if str((catalog.APP_TYPES.get(guess) or {}).get("auth_policy")) == "disabled":
        reason += " · nobody logs in"
    chosen["hint"] = reason
    chosen["suggested"] = True
    return [chosen] + ordered


TOPICS: list[Topic] = [
    Topic(
        key="app_type", kind="single", label="App type",
        intent="What kind of application this is. Drives every later question.",
        options_from=lambda s, item: _app_type_options(s),
        fallback_options=catalog.app_type_options(),

        options_locked=True,
        srs_fields=("system_category", "app_type"),
        coverage=("business_type", "app_surfaces"),
    ),
    Topic(
        key="app_name", kind="text", label="Name",
        intent="The product name shown in the header, title bar and login page.",
        placeholder="e.g. FreshMart POS",
        srs_fields=("project_name", "app_summary.app_name"),
    ),
    Topic(
        key="logo", kind="upload", label="Logo",
        intent="Whether they have a logo to upload, or want one generated.",
        fallback_options=[
            {"label": "Generate one for me", "value": "generate"},
            {"label": "Upload my logo", "value": "upload"},
            {"label": "No logo — just the name", "value": "none"},
        ],
        srs_fields=("ui_ux_requirements",),
        coverage=("file_uploads",),
    ),
    Topic(
        key="auth_roles", profiles=RECORD_PROFILES, kind="multi", label="Roles",
        intent="Which kinds of user exist, in the customer's own words. "
               "Each option must be exactly ONE role — never bundle roles "
               "together ('Manager', not 'Manager + Cashier'), because the "
               "customer picks several and each becomes its own permission set.",
        applies_to=_and(only_for(CRUD), has_auth),
        options_from=lambda s, item: [
            {"label": r.replace("_", " ").title(), "value": r}
            for r in (_pack(s).get("roles") or ["admin", "user"])
        ],
        fallback_options=[
            {"label": "Admin", "value": "admin"},
            {"label": "Staff", "value": "staff"},
            {"label": "Customer", "value": "customer"},
        ],
        srs_fields=("roles", "role_access_matrix"),
        coverage=("users_roles", "auth"),
    ),
    Topic(
        key="auth_identity", profiles=RECORD_PROFILES, kind="multi", label="Login fields",
        intent="What a user signs in and registers with.",
        applies_to=_and(only_for(CRUD), has_auth),
        fallback_options=[
            {"label": "Email + password", "value": "email"},
            {"label": "Username + password", "value": "username"},
            {"label": "Phone number", "value": "phone"},
            {"label": "Full name (on register)", "value": "full_name"},
        ],
        srs_fields=("authentication_requirement",),
        coverage=("auth",),
    ),
    Topic(
        key="role_functions", profiles=RECORD_PROFILES, kind="multi", label="Role duties",
        intent="What this specific role is allowed to do. Ask once per role.",
        applies_to=_and(only_for(CRUD), has_auth),
        repeats_over=roles_list,
        options_from=lambda s, item: [
            {"label": f, "value": f} for f in (_pack(s).get("features") or [])[:8]
        ],
        fallback_options=[
            {"label": "View records", "value": "view"},
            {"label": "Create and edit records", "value": "edit"},
            {"label": "Delete records", "value": "delete"},
            {"label": "View reports", "value": "reports"},
            {"label": "Manage users", "value": "manage_users"},
        ],
        srs_fields=("functional_requirements", "main_modules", "role_access_matrix"),
        coverage=("features_modules", "users_roles"),
    ),
    Topic(
        key="page_functions", profiles=RECORD_PROFILES, kind="multi", label="Page features",
        intent="What each page should let a visitor do, since there are no roles.",
        applies_to=_and(only_for(CRUD), lambda s: not has_auth(s)),
        options_from=lambda s, item: [
            {"label": f, "value": f} for f in (_pack(s).get("features") or [])[:8]
        ],
        fallback_options=[
            {"label": "Show information", "value": "info"},
            {"label": "Collect an enquiry", "value": "enquiry"},
            {"label": "Show a gallery", "value": "gallery"},
        ],
        srs_fields=("functional_requirements", "main_modules", "public_pages"),
        coverage=("features_modules", "public_pages"),
    ),

    Topic(
        key="data_tables", profiles=RECORD_PROFILES, kind="multi", label="Data",
        intent="What kinds of records the system stores. The customer can pick "
               "several and type any you did not think of.",
        applies_to=only_for(CRUD),
        options_from=lambda s, item: [
            {"label": e, "value": e} for e in (_pack(s).get("entities") or [])
        ],
        fallback_options=[
            {"label": "Users", "value": "User"},
            {"label": "Records", "value": "Record"},
        ],
        placeholder="e.g. Purchase Order",
        srs_fields=("database_design.tables",),
        coverage=("data_entities",),
    ),
    Topic(
        key="table_entities", profiles=RECORD_PROFILES, kind="multi", label="Fields",
        intent="Which individual details are stored for this record type. Each "
               "option must be ONE field a person would fill in — 'Price', "
               "'Barcode', 'Expiry date' — never a bundle or a preset like "
               "'Basic details'. Offer fields that genuinely belong to THIS "
               "record and nothing else.",
        applies_to=only_for(CRUD),
        repeats_over=tables_list,
        options_from=_field_options,
        fallback_options=[
            {"label": "Name", "value": "name"},
            {"label": "Description", "value": "description"},
            {"label": "Status", "value": "status"},
            {"label": "Created date", "value": "created_at"},
        ],
        placeholder="e.g. Reorder level",
        srs_fields=("database_design.tables",),
        coverage=("data_entities",),
    ),

    Topic(
        key="pos_payments", kind="multi", label="Payments",
        intent="How a customer can pay at the counter. Each option is ONE way "
               "of paying.",
        profiles=("pos",),
        fallback_options=[
            {"label": "Cash", "value": "cash"},
            {"label": "Card", "value": "card"},
            {"label": "Bank transfer", "value": "transfer"},
            {"label": "Mobile wallet", "value": "wallet"},
            {"label": "On account / credit", "value": "credit"},
        ],
        placeholder="e.g. Gift voucher",
        srs_fields=("integration_requirements", "functional_requirements"),
        coverage=("payments_billing",),
    ),
    Topic(
        key="pos_receipt", kind="multi", label="Receipt",
        intent="What happens at the end of a sale.",
        profiles=("pos",),
        fallback_options=[
            {"label": "Print a receipt", "value": "print"},
            {"label": "Email the receipt", "value": "email"},
            {"label": "No receipt", "value": "none"},
        ],
        srs_fields=("notification_rules", "functional_requirements"),
        coverage=("notifications",),
    ),
    Topic(
        key="pos_stock_rules", kind="multi", label="Stock",
        intent="How stock behaves as things are sold and received.",
        profiles=("pos",),
        fallback_options=[
            {"label": "Reduce stock on every sale", "value": "decrement"},
            {"label": "Warn when stock runs low", "value": "low_stock_alert"},
            {"label": "Record stock coming in", "value": "receiving"},
            {"label": "Allow selling below zero", "value": "allow_negative"},
        ],
        srs_fields=("business_workflows", "validation_rules"),
        coverage=("special_rules",),
    ),

    Topic(
        key="saas_plans", kind="multi", label="Plans",
        intent="The subscription tiers customers can be on.",
        profiles=("saas",),
        fallback_options=[
            {"label": "Free tier", "value": "free"},
            {"label": "Starter", "value": "starter"},
            {"label": "Pro", "value": "pro"},
            {"label": "Enterprise", "value": "enterprise"},
        ],
        placeholder="e.g. Education plan",
        srs_fields=("functional_requirements",),
        coverage=("payments_billing",),
    ),
    Topic(
        key="saas_signup", kind="single", label="Sign-up",
        intent="Whether anyone can create an account or the team invites them.",
        profiles=("saas",),
        fallback_options=[
            {"label": "Anyone can sign up", "value": "open"},
            {"label": "Invite only", "value": "invite"},
            {"label": "Request access, then approve", "value": "request"},
        ],
        srs_fields=("authentication_requirement", "functional_requirements"),
        coverage=("auth",),
    ),
    Topic(
        key="saas_workspace", kind="single", label="Accounts",
        intent="Whether people work alone or share a workspace with colleagues.",
        profiles=("saas",),
        fallback_options=[
            {"label": "Each person works alone", "value": "solo"},
            {"label": "Teams share a workspace", "value": "team"},
        ],
        srs_fields=("roles", "functional_requirements"),
        coverage=("users_roles",),
    ),

    Topic(
        key="store_checkout", kind="single", label="Checkout",
        intent="Whether a shopper must have an account to buy.",
        profiles=("ecommerce",),
        fallback_options=[
            {"label": "Guest checkout allowed", "value": "guest"},
            {"label": "Account required", "value": "account"},
            {"label": "Either, shopper chooses", "value": "either"},
        ],
        srs_fields=("functional_requirements", "authentication_requirement"),
        coverage=("auth",),
    ),
    Topic(
        key="store_payments", kind="multi", label="Payments",
        intent="How a shopper pays.",
        profiles=("ecommerce",),
        fallback_options=[
            {"label": "Card online", "value": "card"},
            {"label": "Cash on delivery", "value": "cod"},
            {"label": "Bank transfer", "value": "transfer"},
            {"label": "Mobile wallet", "value": "wallet"},
        ],
        srs_fields=("integration_requirements", "functional_requirements"),
        coverage=("payments_billing",),
    ),
    Topic(
        key="store_fulfilment", kind="multi", label="Delivery",
        intent="How an order reaches the customer.",
        profiles=("ecommerce",),
        fallback_options=[
            {"label": "Delivery", "value": "delivery"},
            {"label": "Collect in store", "value": "pickup"},
            {"label": "Digital download", "value": "digital"},
        ],
        srs_fields=("business_workflows",),
        coverage=("special_rules",),
    ),

    Topic(
        key="dash_metrics", kind="multi", label="Headline figures",
        intent="The numbers someone opens this tool to check first.",
        profiles=("dashboard",),
        options_from=lambda s, item: [
            {"label": f, "value": _snake_value(f)}
            for f in (_pack(s).get("features") or [])[:8]
        ],
        fallback_options=[
            {"label": "Total records", "value": "total_records"},
            {"label": "Added this week", "value": "recent"},
            {"label": "Outstanding items", "value": "outstanding"},
        ],
        placeholder="e.g. Overdue invoices",
        srs_fields=("reporting_requirements",),
        coverage=("reports",),
    ),
    Topic(
        key="dash_exports", kind="multi", label="Exports",
        intent="How the data leaves the tool.",
        profiles=("dashboard",),
        fallback_options=[
            {"label": "CSV download", "value": "csv"},
            {"label": "Printable view", "value": "print"},
            {"label": "No export", "value": "none"},
        ],
        srs_fields=("reporting_requirements",),
        coverage=("reports",),
    ),

    Topic(
        key="blog_workflow", kind="multi", label="Publishing",
        intent="The steps a post goes through before readers see it.",
        profiles=("blog",),
        fallback_options=[
            {"label": "Draft then publish", "value": "draft_publish"},
            {"label": "Schedule for later", "value": "scheduled"},
            {"label": "Needs approval first", "value": "review"},
            {"label": "Publish immediately", "value": "immediate"},
        ],
        srs_fields=("business_workflows",),
        coverage=("special_rules",),
    ),
    Topic(
        key="blog_organisation", kind="multi", label="Organising",
        intent="How readers find their way around the posts.",
        profiles=("blog",),
        fallback_options=[
            {"label": "Categories", "value": "categories"},
            {"label": "Tags", "value": "tags"},
            {"label": "Search", "value": "search"},
            {"label": "Featured posts", "value": "featured"},
        ],
        srs_fields=("main_modules", "functional_requirements"),
        coverage=("features_modules",),
    ),
    Topic(
        key="blog_engagement", kind="multi", label="Readers",
        intent="What readers can do besides read.",
        profiles=("blog",),
        fallback_options=[
            {"label": "Leave comments", "value": "comments"},
            {"label": "Subscribe by email", "value": "subscribe"},
            {"label": "Share to social", "value": "share"},
            {"label": "Nothing — read only", "value": "none"},
        ],
        srs_fields=("functional_requirements",),
        coverage=("features_modules",),
    ),

    Topic(
        key="sections", profiles=("landing", "portfolio"), kind="multi", label="Sections",
        intent="Which bands the page is built from, top to bottom. These become "
               "the actual sections of the single page, so name what a visitor "
               "scrolls past — not app features.",
        applies_to=only_for(LANDING),
        options_from=_sections_options,
        fallback_options=[
            {"label": "Hero", "value": "hero"},
            {"label": "Services", "value": "services"},
            {"label": "About", "value": "about"},
            {"label": "Testimonials", "value": "testimonials"},
            {"label": "Pricing", "value": "pricing"},
            {"label": "Contact", "value": "contact"},
        ],
        placeholder="e.g. Before & after gallery",
        srs_fields=("public_pages",),
        coverage=("public_pages",),
    ),
    Topic(
        key="offerings", profiles=("landing", "portfolio"), kind="multi", label="What you offer",
        intent="The specific services, packages or pieces of work to show off. "
               "Each option is ONE thing a visitor could buy or book.",
        applies_to=only_for(LANDING),
        options_from=_offering_options,
        fallback_options=[
            {"label": "Standard service", "value": "standard"},
            {"label": "Premium service", "value": "premium"},
            {"label": "One-off job", "value": "one_off"},
        ],
        placeholder="e.g. Deep clean, End-of-tenancy",
        srs_fields=("main_modules", "functional_requirements"),
        coverage=("features_modules",),
    ),
    Topic(
        key="cta", profiles=("landing", "portfolio"), kind="single", label="Main action",
        intent="The one thing the page is trying to get a visitor to do. Every "
               "button on the page points at this.",
        applies_to=only_for(LANDING),
        fallback_options=[
            {"label": "Book now", "value": "book"},
            {"label": "Get a quote", "value": "quote"},
            {"label": "Contact us", "value": "contact"},
            {"label": "Buy now", "value": "buy"},
        ],
        srs_fields=("app_summary.business_goal",),
        coverage=("main_goal",),
    ),
    Topic(
        key="lead_capture", profiles=("landing", "portfolio"), kind="yes_no", label="Enquiries",
        intent="Whether the page collects enquiries the owner can read later, "
               "rather than only listing a phone number.",
        applies_to=only_for(LANDING),
        fallback_options=_yes_no(),
        srs_fields=("functional_requirements",),
        coverage=("features_modules",),
    ),
    Topic(
        key="lead_fields", profiles=("landing", "portfolio"), kind="multi", label="Enquiry form",
        intent="What the enquiry form asks for. Each option is ONE field a "
               "visitor fills in — keep it short, every extra field loses "
               "enquiries.",
        applies_to=_and(only_for(LANDING), wants_leads),
        fallback_options=[
            {"label": "Name", "value": "name"},
            {"label": "Phone", "value": "phone"},
            {"label": "Email", "value": "email"},
            {"label": "Service wanted", "value": "service"},
            {"label": "Preferred date", "value": "preferred_date"},
            {"label": "Message", "value": "message"},
        ],
        placeholder="e.g. Postcode",
        srs_fields=("database_design.tables", "validation_rules"),
        coverage=("data_entities",),
    ),
    Topic(
        key="contact_channels", profiles=("landing", "portfolio"), kind="multi", label="Contact",
        intent="How a visitor can reach the business besides the form.",
        applies_to=only_for(LANDING),
        fallback_options=[
            {"label": "Phone number", "value": "phone"},
            {"label": "Email address", "value": "email"},
            {"label": "WhatsApp", "value": "whatsapp"},
            {"label": "Map / address", "value": "map"},
            {"label": "Opening hours", "value": "hours"},
        ],
        srs_fields=("integration_requirements",),
        coverage=("integrations",),
    ),
    Topic(
        key="social_proof", profiles=("landing", "portfolio"), kind="multi", label="Trust",
        intent="What convinces a visitor this business is real and good.",
        applies_to=only_for(LANDING),
        fallback_options=[
            {"label": "Customer testimonials", "value": "testimonials"},
            {"label": "Client logos", "value": "logos"},
            {"label": "Numbers (jobs done, years)", "value": "stats"},
            {"label": "Photo gallery", "value": "gallery"},
            {"label": "Certifications", "value": "certifications"},
        ],
        srs_fields=("public_pages",),
        coverage=("public_pages",),
    ),

    Topic(
        key="tool_job", profiles=("utility",), kind="text", label="The job",
        intent="In one sentence, what the tool does for someone — the thing "
               "they open it to get done.",
        applies_to=only_for(TOOL),
        placeholder="e.g. Work out a loan repayment",
        srs_fields=("app_summary.business_goal",),
        coverage=("main_goal",),
    ),
    Topic(
        key="tool_inputs", profiles=("utility",), kind="multi", label="Inputs",
        intent="What the person types in. Each option is ONE input.",
        applies_to=only_for(TOOL),
        fallback_options=[
            {"label": "A number", "value": "number"},
            {"label": "A date", "value": "date"},
            {"label": "Some text", "value": "text"},
            {"label": "A choice from a list", "value": "choice"},
            {"label": "A file", "value": "file"},
        ],
        placeholder="e.g. Loan amount",
        srs_fields=("functional_requirements", "validation_rules"),
        coverage=("data_entities",),
    ),
    Topic(
        key="tool_outputs", profiles=("utility",), kind="multi", label="Results",
        intent="What the tool shows back. Each option is ONE result.",
        applies_to=only_for(TOOL),
        fallback_options=[
            {"label": "A single figure", "value": "figure"},
            {"label": "A breakdown table", "value": "table"},
            {"label": "A converted value", "value": "converted"},
            {"label": "A downloadable file", "value": "download"},
        ],
        placeholder="e.g. Monthly repayment",
        srs_fields=("functional_requirements",),
        coverage=("features_modules",),
    ),
    Topic(
        key="save_history", profiles=("utility",), kind="yes_no", label="History",
        intent="Whether past results are kept so the person can come back to "
               "them, or the tool forgets everything on refresh.",
        applies_to=only_for(TOOL),
        fallback_options=_yes_no(),
        srs_fields=("database_design.tables",),
        coverage=("data_entities",),
    ),

    Topic(
        key="images", kind="yes_no", label="Images",
        intent="Whether the app needs generated artwork.",
        fallback_options=_yes_no(),
        srs_fields=("ui_ux_requirements",),
        coverage=("file_uploads",),
    ),
    Topic(
        key="image_kinds", kind="multi", label="Artwork",
        intent="Which images are needed.",
        applies_to=wants_images,
        fallback_options=[
            {"label": "Hero banner", "value": "banner"},
            {"label": "Logo mark", "value": "logo"},
            {"label": "Avatar placeholders", "value": "avatar"},
            {"label": "Empty-state art", "value": "empty"},
            {"label": "Social share card", "value": "og"},
        ],
        srs_fields=("ui_ux_requirements",),
        coverage=("file_uploads",),
    ),

    Topic(
        key="responsive_pwa", kind="multi", label="Devices",
        intent="Which devices matter and whether it should install as an app.",
        fallback_options=[
            {"label": "Works on mobile", "value": "responsive"},
            {"label": "Installable (PWA)", "value": "pwa"},
            {"label": "Desktop only", "value": "desktop"},
        ],
        srs_fields=("ui_ux_requirements",),
        coverage=("devices_mobile",),
    ),

    Topic(
        key="extra_notes", kind="text", label="Anything else",
        intent="Anything the customer wants that no question covered — "
               "especially what they want the site to show.",
        fixed="Last one — is there anything else? Tell me what the site should "
              "show, or anything we have not covered. Write as much as you like.",
        placeholder="e.g. show our opening hours, a photo gallery of past work, "
                    "customer reviews, and the team's phone numbers",
        optional=True,
        multiline=True,
        srs_fields=("app_summary.short_description", "functional_requirements"),
        coverage=("special_rules",),
    ),
]

TOPICS_BY_KEY = {t.key: t for t in TOPICS}


MAX_VISIBLE_QUESTIONS = 25
_ASSUMED_REPEATS = 4


def topics_for(profile: str) -> list[Topic]:
    """The question set a given app profile asks, before conditions apply."""
    return [t for t in TOPICS if not t.profiles or profile in t.profiles]


def question_budget(profile: str) -> int:
    """Worst-case visible questions for a profile.

    Conditions (`applies_to`) only ever remove questions, so this is an upper
    bound: if it fits, no real interview can overflow.
    """
    total = 0
    for topic in topics_for(profile):
        total += _ASSUMED_REPEATS if topic.repeats_over else 1
    return total


def validate_question_budget() -> dict[str, int]:
    """Raise if any profile could ask more than the maximum. Returns the counts."""
    counts = {}
    over = []
    for profile in sorted({t for topic in TOPICS for t in topic.profiles}
                          | {"landing", "utility", "saas"}):
        counts[profile] = question_budget(profile)
        if counts[profile] > MAX_VISIBLE_QUESTIONS:
            over.append(f"{profile}={counts[profile]}")
    if over:
        raise ValueError(
            "question sets exceed the "
            f"{MAX_VISIBLE_QUESTIONS}-question budget: {', '.join(over)}"
        )
    return counts


def build_queue(session: dict) -> list[dict]:
    """Every question still to ask, in order.

    Recomputed after each answer, so answering "no auth" drops the role
    questions and adding a table adds a field question for it.
    """
    queue: list[dict] = []
    answers = session.get("answers", {})
    profile = question_set(session)

    for topic in TOPICS:
        if topic.profiles and profile not in topic.profiles:
            continue
        if not topic.applies_to(session):
            continue

        if topic.repeats_over:
            for item in topic.repeats_over(session):
                key = f"{topic.key}:{item}"
                if key not in answers:
                    queue.append({"topic": topic.key, "key": key, "subject": item})
        else:
            if topic.key not in answers:
                queue.append({"topic": topic.key, "key": topic.key, "subject": None})

    return queue


def total_estimate(session: dict) -> int:
    """Asked so far + still queued. Repeating topics make this move as the
    interview goes, which is honest — the count is an estimate, not a promise.

    Clarification turns are excluded. Being asked "what did you mean by that?"
    is not another interview question, and counting it would make the rail grow
    as a punishment for writing something in your own words.
    """
    asked = [k for k in session.get("asked", []) if not is_clarification(k)]
    return len(asked) + len(build_queue(session))


def is_clarification(key: str) -> bool:
    """Follow-up turns live outside the question budget."""
    return str(key or "").startswith(("clarify:", "adaptive:", "schema:"))
