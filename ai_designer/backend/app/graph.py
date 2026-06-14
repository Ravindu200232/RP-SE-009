import json
import os
import re
from langgraph.graph import StateGraph, START, END
from app.state import GraphState
from app.agents import (
    plan_design_agent,
    update_prototype_agent,
    get_llm,
    extract_json,
    ensure_ollama,
)
from langchain_core.prompts import ChatPromptTemplate
from app.themes import pick_theme, fonts_url
from app import component_bank, design_library, fooocus_images, knowledge, landing_copy, nextgen, planner, research, srs

_GENERIC_STATUS = ["Active", "Pending", "Completed", "Cancelled"]
_PARADIGM_HISTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_paradigm_history.json")


def _guess_field(fname: str) -> dict:
    """Infer a form field's type from its name (blueprint entities ship only
    field names; the planner-derived ones already carry rich types)."""
    n = str(fname).lower()
    label = str(fname).replace("_", " ").strip().title()
    if n == "status" or n.endswith("_status") or n in ("state", "stage", "priority"):
        return {"name": fname, "label": label, "type": "select", "options": _GENERIC_STATUS, "required": False, "form": True}
    if any(k in n for k in ("date", "_at", "deadline", "dob", "_on")):
        return {"name": fname, "label": label, "type": "date", "options": None, "required": False, "form": True}
    if any(k in n for k in ("price", "amount", "total", "cost", "salary", "fee", "qty", "quantity",
                            "count", "stock", "rate", "number", "age", "score", "hours", "weight", "balance")):
        return {"name": fname, "label": label, "type": "number", "options": None, "required": False, "form": True}
    if "email" in n:
        return {"name": fname, "label": label, "type": "email", "options": None, "required": False, "form": True}
    if any(k in n for k in ("description", "notes", "bio", "summary", "details", "message", "address", "comment")):
        return {"name": fname, "label": label, "type": "textarea", "options": None, "required": False, "form": True}
    return {"name": fname, "label": label, "type": "text", "options": None, "required": False, "form": True}


def _merge_blueprint(state: GraphState, plan: dict, bp: dict) -> None:
    """Fold the Deep Research blueprint into the plan: per-entity CRUD layout,
    domain-specific marketing pages, theme paradigm, utility-tool isolation."""
    roles = plan.get("roles") or ["Admin", "User"]
    entities = plan.get("entities") or []
    app_name = plan.get("app_name") or "App"

    # roles: planner default is generic; prefer the research-grounded roles then.
    if bp.get("roles") and (not roles or [r.lower() for r in roles] == ["admin", "user"]):
        roles = bp["roles"]

    # entities: keep the planner's rich field types; just stamp each with the
    # crud_layout the researcher chose for the closest-named blueprint entity.
    bp_ents = {re.sub(r"[^a-z0-9]", "", e["name"].lower()): e for e in bp.get("entities", [])}
    have = {re.sub(r"[^a-z0-9]", "", str(e.get("name", "")).lower()) for e in entities}
    if entities:
        for e in entities:
            key = re.sub(r"[^a-z0-9]", "", str(e.get("name", "")).lower())
            match = bp_ents.get(key) or next((v for k, v in bp_ents.items() if k and (k in key or key in k)), None)
            e["crud_layout"] = (match or {}).get("crud_layout", "table")
        # add research entities the planner missed (richer domain coverage)
        for k, be in bp_ents.items():
            if k and k not in have and len(entities) < 5:
                entities.append({
                    "name": be["name"], "label": planner.label_from(be["name"]),
                    "storage_key": be["name"],
                    "fields": [_guess_field(f) for f in (be.get("fields") or ["name"])][:7],
                    "crud_layout": be.get("crud_layout", "table"),
                })
    elif bp_ents:
        entities = [{
            "name": be["name"], "label": planner.label_from(be["name"]), "storage_key": be["name"],
            "fields": [_guess_field(f) for f in (be.get("fields") or ["name"])][:7],
            "crud_layout": be.get("crud_layout", "table"),
        } for be in bp_ents.values()][:5]

    if bp.get("app_name") and app_name in ("App", "Prototype App", ""):
        app_name = bp["app_name"]

    state["roles"] = roles
    state["entities"] = entities
    state["app_name"] = app_name
    state["marketing_pages"] = bp.get("marketing_pages") or []
    state["theme_style"] = bp.get("theme_style", "minimal")
    state["is_utility_tool"] = bool(bp.get("is_utility_tool", False))
    state["blueprint"] = bp


def _pick_paradigm(style: str) -> str:
    """Honor the researcher's paradigm, but never repeat the immediately
    previous run's look - guarantees the design family rotates app to app."""
    order = ["minimal", "neo-brutalism", "glassmorphism", "cyberpunk"]
    style = style if style in order else "minimal"
    try:
        hist = json.load(open(_PARADIGM_HISTORY, encoding="utf-8"))[-3:]
    except Exception:
        hist = []
    # avoid the last 3 paradigms so all four cycle before any repeats
    recent = hist[-3:]
    if style in recent:
        style = next((s for s in order if s not in recent),
                     next((s for s in order if not hist or s != hist[-1]), style))
    hist.append(style)
    try:
        json.dump(hist[-4:], open(_PARADIGM_HISTORY, "w", encoding="utf-8"))
    except OSError:
        pass
    return style


def _default_fields(name: str) -> list:
    return [_guess_field(f) for f in ("name", "status", "notes", "created_at")]


def _apply_intake(state: GraphState) -> None:
    """Override the plan with the user's interview answers (app type, pages +
    per-page sections, auth, roles, data records + CRUD layout, theme). The
    interview is the user's explicit intent, so it wins over research guesses."""
    intake = state.get("intake") or {}
    if not intake.get("active"):
        return
    app_type = intake.get("app_type", "hybrid")
    pages = intake.get("pages") or []
    if app_type == "internal":
        state["marketing_pages"] = []          # login-first: no public marketing tier
        state["is_utility_tool"] = True
    elif pages:
        state["marketing_pages"] = [
            {"name": p.get("name", "Page"), "slug": p.get("slug", "page"),
             "template": p.get("template", "content"), "sections": p.get("sections", [])}
            for p in pages
        ]
    if intake.get("roles"):
        state["roles"] = intake["roles"]
    if intake.get("theme_style"):
        state["theme_style"] = intake["theme_style"]

    # Data records: honor exactly what the user picked, reusing the planner's
    # richer field types when an entity name matches; otherwise synthesize.
    chosen = intake.get("entities") or []
    if chosen:
        existing = {re.sub(r"[^a-z0-9]", "", str(e.get("name", "")).lower()): e for e in state.get("entities", [])}
        rebuilt = []
        for ce in chosen:
            key = re.sub(r"[^a-z0-9]", "", str(ce.get("name", "")).lower())
            base = existing.get(key) or next((v for k, v in existing.items() if k and (k in key or key in k)), None)
            if base:
                base["crud_layout"] = ce.get("layout", "table")
                rebuilt.append(base)
            else:
                rebuilt.append({"name": ce["name"], "label": ce.get("label") or planner.label_from(ce["name"]),
                                "storage_key": ce["name"], "fields": _default_fields(ce["name"]),
                                "crud_layout": ce.get("layout", "table")})
        state["entities"] = rebuilt
    else:
        layouts = intake.get("entity_layouts") or {}
        for e in state.get("entities", []):
            key = re.sub(r"[^A-Za-z0-9]", "", str(e.get("name", "")))
            if key in layouts:
                e["crud_layout"] = layouts[key]

    req = intake.get("requirements")
    if req:
        state["prompt"] = (str(state.get("prompt", "")) + "  Extra requirements: " + req)[:1400]
    state["logs"].append(
        f"--- [AGENT: Requirements] app_type={app_type}, {len(pages)} pages, "
        f"auth={intake.get('auth')}, theme={intake.get('theme_style') or 'auto'} ---"
    )

def planning_node(state: GraphState):
    state["logs"] = state.get("logs", [])
    state["logs"].append("--- [PHASE 1: PLANNING USER INTERFACE & ROLES] ---")
    if not ensure_ollama():
        state["logs"].append("WARNING: local LLM runtime could not be started - using generic fallbacks.")

    # --- [AGENT: SRS Ingest] if the input is an SRS JSON, IT is the source of
    # truth: every entity, role and public module must be fulfilled. We still
    # run light research on the derived domain for theme + imagery only.
    parsed = None
    try:
        parsed = srs.parse_srs_input(state.get("prompt", ""))
    except Exception as e:
        state["logs"].append(f"SRS parse skipped ({str(e)[:80]}).")
    if parsed:
        state["logs"].append(
            f"--- [AGENT: SRS Ingest] Parsed SRS for '{parsed['app_name']}': "
            f"{len(parsed['entities'])} entities, {len(parsed['roles'])} roles, "
            f"{len(parsed['marketing_pages'])} public pages ---"
        )
        bp = None
        try:
            bp = research.deep_research(parsed["query"])
        except Exception:
            bp = None
        state["srs"] = {"app_name": parsed["app_name"], "roles": parsed["roles"]}
        state["app_name"] = parsed["app_name"]
        state["roles"] = parsed["roles"]
        state["entities"] = parsed["entities"]
        state["marketing_pages"] = parsed["marketing_pages"]
        state["theme_style"] = (bp or {}).get("theme_style", "minimal")
        state["is_utility_tool"] = False
        state["blueprint"] = {
            **(bp or {}),
            "domain": parsed["domain"],
            "key_features": parsed["key_features"] or (bp or {}).get("key_features", []),
            "terminology": parsed["terminology"] or (bp or {}).get("terminology", []),
            "entities": [{"name": e["name"]} for e in parsed["entities"]],
        }
        state["pages"] = []
        state["status"] = "SRS ingested."
        state["logs"].append("Entities: " + ", ".join(f"{e['name']}[{e['crud_layout']}]" for e in parsed["entities"]))
        state["logs"].append("Roles: " + ", ".join(parsed["roles"]))
        state["logs"].append("Public pages: " + ", ".join(p["name"] for p in parsed["marketing_pages"]))
        _apply_intake(state)
        return state

    # --- [AGENT: Deep Research] internet-grounded Domain Blueprint (runs FIRST) ---
    # ddgs reads REAL sites in this domain; Gemma synthesizes the page set,
    # entities + per-entity CRUD layout, theme paradigm and roles. This is what
    # makes a school produce Admissions/Curriculum (not Home/Features/About).
    state["logs"].append("--- [AGENT: Deep Research] Browsing real sites for this domain ---")
    bp = None
    try:
        bp = research.deep_research(state.get("prompt", ""))
    except Exception as e:
        state["logs"].append(f"Deep Research unavailable ({str(e)[:80]}); using planner only.")
    if bp:
        state["logs"].append(
            f"Blueprint: domain '{bp.get('domain','?')}', theme '{bp.get('theme_style','?')}', "
            f"utility={bp.get('is_utility_tool')}, pages [{', '.join(p['name'] for p in bp.get('marketing_pages', []))}] "
            f"({bp.get('engine','?')})"
        )

    plan = plan_design_agent(state)
    if bp:
        _merge_blueprint(state, plan, bp)
    else:
        state["roles"] = plan["roles"]
        state["entities"] = plan.get("entities", [])
        state["app_name"] = plan.get("app_name", "App")
        state["marketing_pages"] = []
        state["theme_style"] = "minimal"
        state["is_utility_tool"] = False
    state["pages"] = plan["pages"]
    state["status"] = plan["status"]
    state["logs"].append(f"Planner complete. Roles: {', '.join(state['roles'])}")
    state["logs"].append(
        "Entities: " + ", ".join(f"{e.get('name','?')}[{e.get('crud_layout','table')}]" for e in state["entities"])
    )
    if state.get("marketing_pages"):
        state["logs"].append("Public pages: " + ", ".join(p["name"] for p in state["marketing_pages"]))
    _apply_intake(state)
    return state

_SIDEBAR_ICONS = ["Users", "ClipboardList", "CalendarDays", "Package", "Star", "Layers"]

def _entities_meta(state: GraphState):
    out = []
    for i, e in enumerate(state.get("entities", [])):
        name = e.get("name", "Item")
        out.append({
            "name": name,
            "label": planner.label_from(name) if hasattr(planner, "label_from") else name,
            "slug": planner.slug_of(name),
            "icon": _SIDEBAR_ICONS[i % len(_SIDEBAR_ICONS)],
            "crud_layout": e.get("crud_layout", "table"),
            "fields": [
                {"name": f.get("name", "name"),
                 "label": str(f.get("label") or f.get("name", "name")).replace("_", " ").title(),
                 "type": f.get("type", "text"),
                 **({"options": f.get("options")} if f.get("options") else {})}
                for f in e.get("fields", [])
            ] or [{"name": "name", "label": "Name", "type": "text"}],
        })
    return out


def _role_slug(role: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(role).lower()).strip("-") or "user"


# Marketing-page slugs that would collide with the app's real routes (the app
# tier owns /dashboard, /login, /e/*, /workspace/*, etc.) or with the landing.
_RESERVED_SLUGS = {
    "", "home", "index", "dashboard", "login", "register", "logout", "e", "entity",
    "workspace", "notifications", "profile", "settings", "api", "assets", "auth", "admin",
}


def _safe_marketing_pages(pages):
    """Sanitize public pages so `next build` never sees a route collision:
    normalize each slug, drop reserved/home/empty slugs and duplicates."""
    out, seen = [], set()
    for p in pages or []:
        slug = re.sub(r"[^a-z0-9-]+", "-", str(p.get("slug") or p.get("name", "")).lower()).strip("-")[:32]
        if not slug or slug in _RESERVED_SLUGS or slug in seen:
            continue
        seen.add(slug)
        out.append({**p, "slug": slug})
    return out


def code_generation_node(state: GraphState):
    """V2: produce a COMPLETE Next.js app (frontend + API + local DB), with the
    user-facing phases planning -> pages -> images -> qa -> building -> done.
    The preview stays hidden until phase == done."""
    state["logs"] = state.get("logs", [])
    output_dir = os.path.join("output", state["project_id"])
    app_name = state.get("app_name", "App")

    # --- [AGENT: Knowledge] match the request against every page of the user's
    # own past projects; close matches guide structure + design selection.
    kb = knowledge.match(state.get("prompt", ""))
    if kb:
        state["logs"].append(
            "--- [AGENT: Knowledge] similar pages from your projects: "
            + ", ".join(f"{e['project']}/{os.path.basename(e['file'])}" for e in kb[:3]) + " ---"
        )

    # --- [AGENT: Component Bank] one variant per design family (hero, navbar,
    # footer, dashboard, list), matched to the input's domain tags with
    # anti-repeat history - the COMPLETE design rotates app to app.
    comps = component_bank.pick_components(state.get("prompt", ""))
    state["logs"].append(
        "--- [AGENT: Component Bank] " +
        ", ".join(f"{fam}={e['name']}" for fam, e in comps.items()) + " ---"
    )

    # --- [AGENT: Color Planner] variety engine: landing x accent x fonts is
    # picked randomly with the last two runs' choices excluded, so generating
    # the SAME app twice always yields a different design.
    design = design_library.pick_design((state.get("prompt", "") + " " + knowledge.bias_tags(kb)).strip())
    accent = design["accent"]
    theme = {"font_display": design["font_display"], "font_body": design["font_body"], "accent": f"text-{accent}-500"}
    state["theme"] = theme
    state["logs"].append(
        f"--- [AGENT: Color Planner] accent '{accent}', fonts {design['font_display']}/{design['font_body']}, "
        f"landing '{design['landing']['name']}' (anti-repeat on) ---"
    )

    # --- scaffold ------------------------------------------------------------
    state["logs"].append("--- [SCAFFOLD] Creating Next.js app (npm deps shared from cache) ---")
    nextgen.create_project(output_dir)
    nextgen.write_status(output_dir, "pages", "Generating application pages")

    # Persist the build plan derived from the interview answers (traceable, and
    # the user asked nothing be edited after - this is exactly what gets built).
    if (state.get("intake") or {}).get("active"):
        try:
            plan = {
                "app_name": app_name, "app_type": state["intake"].get("app_type"),
                "language": state["intake"].get("language"), "auth": state["intake"].get("auth"),
                "theme_style": state.get("theme_style"), "roles": state.get("roles"),
                "marketing_pages": state.get("marketing_pages"),
                "entities": [{"name": e.get("name"), "layout": e.get("crud_layout"),
                              "fields": [f.get("name") for f in e.get("fields", [])]} for e in state.get("entities", [])],
                "requirements": state["intake"].get("requirements"),
            }
            with open(os.path.join(output_dir, "_plan.json"), "w", encoding="utf-8") as f:
                json.dump(plan, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    ents = _entities_meta(state)
    roles = state.get("roles", ["Admin", "User"])
    # Public nav comes from the Deep Research blueprint (domain-specific, variable
    # in number). A utility tool has no marketing tier at all - just the workspace.
    utility = state.get("is_utility_tool", False)
    mk_pages = [] if utility else (state.get("marketing_pages") or [
        {"name": "Features", "slug": "features", "template": "features"},
        {"name": "About", "slug": "about", "template": "about"},
        {"name": "Contact", "slug": "contact", "template": "contact"},
    ])
    mk_pages = _safe_marketing_pages(mk_pages)   # drop reserved routes (dashboard/login/...), home, dupes
    marketing_links = [{"label": "Home", "href": "/"}] + [
        {"label": p["name"], "href": "/" + p["slug"]} for p in mk_pages
    ]
    # Role-based access: each link lists the roles allowed to SEE it (no
    # "roles" key = everyone). The Sidebar filters by the logged-in user's
    # role, so e.g. a Nurse never sees the Doctor Workspace or admin Settings.
    primary = roles[0] if roles else "Admin"
    sidebar_links = [{"label": "Dashboard", "href": "/dashboard", "icon": "LayoutDashboard"}]
    sidebar_links += [{"label": e["label"], "href": f"/e/{e['slug']}", "icon": e["icon"]} for e in ents]
    sidebar_links += [
        {"label": f"{r} Workspace", "href": f"/workspace/{_role_slug(r)}", "icon": "BriefcaseBusiness",
         "roles": [r, primary]}
        for r in roles[1:3]
    ]
    sidebar_links += [
        {"label": "Notifications", "href": "/notifications", "icon": "Bell"},
        {"label": "Profile", "href": "/profile", "icon": "User"},
        {"label": "Settings", "href": "/settings", "icon": "Settings", "roles": [primary]},
    ]

    # --- copywriter (one small JSON call) + site/theme/layout ---------------
    state["logs"].append("--- [AGENT: Copywriter] Writing the marketing copy ---")
    copy = {}
    try:
        chain = ChatPromptTemplate.from_messages([
            ("system", landing_copy._COPY_PROMPT),
            ("user", "Write the landing copy for {app_name} now."),
        ]) | get_llm(temperature=0.4, num_predict=3072)
        ent_names = ", ".join(e["label"] for e in ents) or "records"
        ctx = f"{app_name} manages {ent_names}. {state.get('prompt', '')[:200]}"
        hint = knowledge.reference_hint(kb)
        if hint:
            ctx += " " + hint[:400]
        copy = extract_json(chain.invoke({
            "app_name": app_name,
            "app_context": ctx,
        }).content)
    except Exception:
        copy = {}
    tagline = (copy.get("subline") or f"The modern way to run {app_name}.")[:120]

    # --- [AGENT: Theme & UX Architect] one of 4 visual paradigms (neo-brutalism /
    # glassmorphism / minimal / cyberpunk), anti-repeated so the WHOLE design
    # changes app to app - layered over the accent/font the Color Planner picked.
    intake = state.get("intake") or {}
    if intake.get("active") and intake.get("theme_style"):
        paradigm = intake["theme_style"]   # user picked it explicitly - honor verbatim
    else:
        paradigm = _pick_paradigm(state.get("theme_style", "minimal"))
    state["theme_style"] = paradigm
    state["logs"].append(
        f"--- [AGENT: Theme & UX Architect] paradigm '{paradigm}' x accent '{accent}' "
        f"x {theme['font_display']} ---"
    )

    auth_enabled = intake.get("auth", True) if intake.get("active") else True
    styles = {fam: e["name"] for fam, e in comps.items() if fam in ("nav", "footer", "dash", "list")}
    styles.update({k: v for k, v in (intake.get("styles") or {}).items() if v})  # user-picked navbar/dash/list designs win
    nextgen.write_site(output_dir, app_name, tagline, marketing_links, sidebar_links, ents, roles, styles, auth_enabled)
    nextgen.write_theme(output_dir, accent, theme["font_display"], theme["font_body"], paradigm)
    nextgen.write_layout_meta(output_dir, app_name, tagline, fonts_url(theme), paradigm)

    # --- [AGENT: Database Seeder] -------------------------------------------
    state["logs"].append("--- [AGENT: Database Seeder] Seeding the database ---")
    db = nextgen.generate_seeds(state)
    nextgen.write_db(output_dir, db)
    state["logs"].append(
        "Seed data ready: users " + str(len(db.get("users", []))) + ", " +
        ", ".join(f"{e['name']} {len(db.get(e['name'], []))}" for e in ents)
    )
    if nextgen.write_env(output_dir, state["project_id"]):
        # Seeding must VERIFIABLY succeed: a connected-but-empty Mongo app would
        # render blank lists and a login that rejects everyone. Retry transient
        # failures; if Mongo still won't take the seeds, drop .env.local so the
        # app runs fully on its local JSON database instead.
        import time as _t
        seed_log = ""
        for attempt in range(3):
            seed_log = nextgen.run_seed(output_dir)
            if "SEED: ok" in seed_log:
                break
            _t.sleep(5)
        if "SEED: ok" in seed_log:
            state["logs"].append(f"MongoDB: database '{state['project_id']}' - {seed_log[:160]}")
        else:
            try:
                os.remove(os.path.join(output_dir, ".env.local"))
            except OSError:
                pass
            state["logs"].append(f"MongoDB seeding failed ({seed_log[:100]}); app uses its local JSON database instead.")
    else:
        state["logs"].append("MongoDB not configured - app uses its local JSON database.")

    # --- marketing pages from the design library -----------------------------
    landing = design["landing"]
    detail, landing_src = design_library.load_landing(landing, theme, hero_file=comps["hero"].get("file"))
    state["logs"].append(f"--- [AGENT: Design Library] Landing '{landing['name']}' ({detail}) ---")
    pages_written = []
    src = landing_copy.apply(landing["name"], landing_src, copy, app_name)
    pages_written.append(nextgen.write_page(output_dir, "(marketing)", src))
    # Domain-specific secondary pages from the blueprint (e.g. a school's
    # Admissions / Curriculum / Faculty) - deterministic + build-safe.
    if mk_pages:
        bp_full = dict(state.get("blueprint") or {})
        bp_full.setdefault("entities", [{"name": e["label"]} for e in ents])
        mk_paths = nextgen.write_marketing_pages(output_dir, mk_pages, app_name, bp_full, state.get("ai_sections"))
        pages_written.extend(mk_paths)
        state["logs"].append("Marketing pages written: Home, " + ", ".join(p["name"] for p in mk_pages) + ".")
    else:
        state["logs"].append("Utility tool: no marketing tier - users land directly in the workspace.")

    # --- images run AFTER the build (see end) so the preview is NEVER gated
    # behind a slow or hung image step; they pop into public/assets on reload. --
    state["logs"].append("--- [AGENT: Image Studio] Images generate in the background after build ---")

    # --- hidden QA / bug-fixing agent ----------------------------------------
    nextgen.write_status(output_dir, "qa", "Quality check")
    state["logs"].append("--- [AGENT: QA] Auditing the build against the plan ---")
    qa_notes = []
    anchors = ("Headline part", "accent words", "Feature one", "Question one?", "Full Name", "Tagline category", "App Name")
    for path in pages_written:
        try:
            with open(path, encoding="utf-8") as f:
                src = f.read()
        except OSError:
            qa_notes.append(f"missing page file {path}")
            continue
        left = [a for a in anchors if a in src]
        if left:
            with open(path, "w", encoding="utf-8") as f:
                f.write(landing_copy.apply("qa-fix", src, {}, app_name))
            qa_notes.append(f"{os.path.basename(os.path.dirname(path))}: filled leftover copy {left}")
        imgs = re.findall(r"/assets/(\w+\.jpg)", src)
        dups = {i for i in imgs if imgs.count(i) > 1}
        if dups:
            qa_notes.append(f"{os.path.basename(os.path.dirname(path))}: duplicate images {sorted(dups)}")
    if qa_notes:
        state["logs"].append("QA fixed/flagged: " + "; ".join(qa_notes[:6]))
    else:
        state["logs"].append("QA: plan and build match; no duplicate images; copy complete.")

    # --- guarantee every image slot has an image (placeholder now, AI photo
    # overwrites in the background) so the preview never shows an empty card ----
    nph = nextgen.seed_placeholder_images(output_dir)
    state["logs"].append(f"--- [AGENT: Image Studio] Seeded {nph} image placeholders; real photos generate in background ---")

    # --- build (the ultimate guard: nothing broken can reach the preview) ----
    nextgen.write_status(output_dir, "building", "Building the app")
    state["logs"].append("--- [BUILD] next build ---")
    ok, out = nextgen.run_build(output_dir)
    if not ok:
        bad = nextgen.failing_page(out)
        state["logs"].append(f"Build failed{f' at {bad}' if bad else ''}; retrying once after re-applying safe copy.")
        if bad and os.path.exists(bad):
            with open(bad, encoding="utf-8") as f:
                src = f.read()
            with open(bad, "w", encoding="utf-8") as f:
                f.write(landing_copy.apply("qa-fix", src, {}, app_name))
        ok, out = nextgen.run_build(output_dir)
    if not ok:
        nextgen.write_status(output_dir, "error", "Build failed")
        state["logs"].append("BUILD ERROR (tail): " + out[-600:])
        state["status"] = "Generation failed at build."
        return state

    nextgen.write_status(output_dir, "done", "Ready")
    state["logs"].append("--- [DONE] Next.js app built successfully - preview is ready ---")
    state["status"] = "Generation completed."

    # Fire image generation in the BACKGROUND now that the app is built + shown.
    # Images land in public/assets as they finish (the user reloads to see them);
    # a hung/slow Fooocus can never block the preview again.
    import threading
    pr = state.get("prompt", "")

    def _bg_images():
        try:
            n = fooocus_images.generate_all_bg(output_dir, app_name, pr)
            nextgen.write_status(output_dir, "done", f"Ready - {n} images")
        except Exception:
            pass
    threading.Thread(target=_bg_images, daemon=True).start()
    return state

def update_node(state: GraphState):
    state["logs"] = state.get("logs", [])
    state["logs"].append(f"--- [PHASE 1: REFACTORING PROTOTYPE FOR ID: {state['project_id']}] ---")
    state["logs"].append(f"Instruction received: {state['prompt']}")
    
    # Run the iterative refactoring agent
    res = update_prototype_agent(state)
    state["files"] = res["files"]
    state["status"] = res["status"]
    
    # Write updated files back to disk
    state["logs"].append("--- [PHASE 2: SAVING MODIFICATIONS TO DISK] ---")
    output_dir = os.path.join("output", state["project_id"])
    for filepath, content in state["files"].items():
        full_path = os.path.join(output_dir, filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
            
    state["logs"].append("Modified files compiled and saved.")
    return state

# ----------------- ROUTING LOGIC -----------------
# We compile two sub-graphs: one for creation, one for updates.
creation_workflow = StateGraph(GraphState)
creation_workflow.add_node("planning", planning_node)
creation_workflow.add_node("code_generation", code_generation_node)
creation_workflow.add_edge(START, "planning")
creation_workflow.add_edge("planning", "code_generation")
creation_workflow.add_edge("code_generation", END)
creation_app = creation_workflow.compile()

update_workflow = StateGraph(GraphState)
update_workflow.add_node("updating", update_node)
update_workflow.add_edge(START, "updating")
update_workflow.add_edge("updating", END)
update_app = update_workflow.compile()
