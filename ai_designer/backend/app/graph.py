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
from app import app_taxonomy, design_planes
from app import data_model_planner, data_model_quality_gate, app_shell_generator, crud_generator, auth_page_generator
from app import srs_page_generator

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
        state["_roles_explicit"] = True   # the user picked these in the interview
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


def _run_data_model_planner(state: GraphState) -> None:
    """PART 5: relationship-aware data model (entities w/ typed refs, per-entity
    role access, workflows, side effects) - drives CRUD/API/dashboard generation
    downstream. Runs LAST in planning (after intake) so it sees the final
    prompt/app_name/roles. Its OWN domain-grounded roles win UNLESS the user
    explicitly chose roles (SRS or the interview set state["_roles_explicit"]) -
    a generic LLM/heuristic role guess from the legacy planner is not "explicit"
    just because it happens to differ from the ["Admin","User"] literal default,
    so checking for that one literal value isn't enough (caught live: a generic
    planner guess of ["Admin","Staff","Customer"] for a campus prompt silently
    beat the data model's correctly-detected ["Admin","Instructor","Student"])."""
    try:
        dm = data_model_planner.plan_data_model(
            state.get("prompt", ""), app_name=state.get("app_name"), srs=state.get("srs"))
        state["data_model"] = dm
        if not state.get("_roles_explicit"):
            state["roles"] = dm["roles"]
        state["logs"].append(
            f"--- [AGENT: Data Model Planner] domain={dm['domain']} "
            f"entities={[e['name'] for e in dm['entities']]} roles={dm['roles']} ---")
        issues = data_model_quality_gate.evaluate(dm).get("issues", [])
        if issues:
            state["logs"].append(f"--- [AGENT: Data Model QA] {'; '.join(issues[:5])} ---")
    except Exception as _de:
        state["logs"].append(f"--- [AGENT: Data Model Planner] skipped ({str(_de)[:80]}) ---")
        state["data_model"] = None


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
        state["srs"] = parsed   # the WHOLE parsed structure - data_model_planner needs the
                                 # rich fields/relationships/entity_access, not just app_name/roles
        state["app_name"] = parsed["app_name"]
        state["roles"] = parsed["roles"]
        state["_roles_explicit"] = True   # SRS is user-provided - data model planner must not override
        state["entities"] = parsed["entities"]
        state["marketing_pages"] = parsed["marketing_pages"]
        state["theme_style"] = (bp or {}).get("theme_style", "minimal")
        state["is_utility_tool"] = False
        state["blueprint"] = {
            **(bp or {}),
            "domain": parsed["domain"],
            "system_category": parsed.get("system_category", ""),
            "key_features": parsed["key_features"] or (bp or {}).get("key_features", []),
            "terminology": parsed["terminology"] or (bp or {}).get("terminology", []),
            "entities": [{"name": e["name"]} for e in parsed["entities"]],
            "main_modules": parsed.get("main_modules", []),
            "auth_requirements": parsed.get("authentication_requirement", {}),
            "reporting": parsed.get("reporting_requirements", []),
            "notifications": parsed.get("notification_requirements", []),
            "ui_ux": parsed.get("ui_ux_requirements", {}),
            "acceptance_criteria": parsed.get("acceptance_criteria", []),
            "future_enhancements": parsed.get("future_enhancements", []),
        }
        state["pages"] = []
        state["status"] = "SRS ingested."
        state["logs"].append("Entities: " + ", ".join(f"{e['name']}[{e['crud_layout']}]" for e in parsed["entities"]))
        state["logs"].append("Roles: " + ", ".join(parsed["roles"]))
        state["logs"].append("Public pages: " + ", ".join(p["name"] for p in parsed["marketing_pages"]))
        if parsed.get("main_modules"):
            state["logs"].append("Modules: " + ", ".join(parsed["main_modules"][:8]))
        if parsed.get("business_workflows"):
            state["logs"].append("Workflows: " + ", ".join(
                w["name"] for w in parsed["business_workflows"][:6] if w.get("name")))
        if parsed.get("reporting_requirements"):
            state["logs"].append("Reports: " + ", ".join(
                r.get("name", "") for r in parsed["reporting_requirements"][:6] if r.get("name")))
        if parsed.get("relationships"):
            state["logs"].append("Relationships: " + ", ".join(
                f"{r.get('from_table','?')}->{r.get('to_table','?')}({r.get('type','?')})"
                for r in parsed["relationships"][:8]))
        _apply_intake(state)
        _run_data_model_planner(state)
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

    # --- [AGENT: Domain Modeler] universal fallback: if research + planner produced no
    # data model (offline / unknown domain), infer entities/roles/workflows from the
    # prompt's own nouns + verbs so EVERY app ships a meaningful, domain-shaped model.
    if not state.get("entities"):
        try:
            from app import design_genome
            dm = design_genome.infer_domain_model(state.get("prompt", ""))
            state["entities"] = dm["entities"]
            if not state.get("roles") or [r.lower() for r in state["roles"]] == ["admin", "user"]:
                state["roles"] = dm["roles"]
            state["logs"].append("--- [AGENT: Domain Modeler] inferred entities "
                                 + ", ".join(e["name"] for e in dm["entities"])
                                 + " | workflows " + ", ".join(dm["workflows"]) + " ---")
        except Exception:
            pass

    # --- [AGENT: App Classifier + Design Plane] classify the prompt into one of
    # 20 categories / 300+ app types, then load the world-class design plane that
    # specifies which 12-16 premium sections to assemble for this category.
    try:
        cls = app_taxonomy.classify(state.get("prompt", ""))
        plane = design_planes.get_plane(cls["category_id"], cls.get("app_type"))
        state["app_classification"] = {
            "category_id": cls["category_id"],
            "category_name": cls["category_name"],
            "app_type": cls["app_type"],
            "design_family": cls["design_family"],
            "visual_style": plane["visual_style"],
            "landing_template": plane["landing_template"],
            "hero_variant": plane["hero_variant"],
            "nav_style": plane["nav_style"],
        }
        state["design_plane"] = {
            "section_sequence": plane["section_sequence"],
            "section_pools": plane["section_pools"],
            "min_sections": plane["min_sections"],
            "footer_style": plane["footer_style"],
            "hero_variant": plane["hero_variant"],  # passed to compose_landing → _pick_hero
            "landing_template": plane["landing_template"],
        }
        # Apply landing template from design plane to override generic selection
        if not state.get("blueprint"):
            state["blueprint"] = {}
        state["blueprint"]["landing_template"] = plane["landing_template"]
        state["blueprint"]["visual_style"] = plane["visual_style"]
        state["blueprint"]["design_family"] = cls["design_family"]
        state["logs"].append(
            f"--- [AGENT: App Classifier] {cls['category_name']} → {cls['app_type']} "
            f"| template={plane['landing_template']} visual={plane['visual_style']} "
            f"sections={plane['min_sections']}+ ---"
        )
    except Exception as _ce:
        state["logs"].append(f"--- [AGENT: App Classifier] skipped: {_ce} ---")

    _apply_intake(state)
    _run_data_model_planner(state)
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


# Marketing-page slugs that would collide with the app's real routes (the app
# tier owns /dashboard, /login, /manage/*, /e/*, etc.) or with the landing.
# /e/* and /workspace are legacy/retired routes, kept reserved defensively in
# case an old project or stray link still points at them.
_RESERVED_SLUGS = {
    "", "home", "index", "dashboard", "login", "register", "logout", "e", "entity",
    "manage", "workspace", "notifications", "profile", "settings", "api", "assets", "auth", "admin",
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
    nextgen.write_status(output_dir, "planning", "Planning complete")

    # --- [AGENT: Data Model + CRUD] Part 5: relationship-aware Mongo schema,
    # API/service layer, descriptor-driven CRUD UI, domain-aware auth pages, and
    # role-access metadata (lib/access.js) - all driven by state["data_model"].
    # shell_bundle["sidebar"] (role-aware /manage links) replaces the legacy
    # generic per-entity sidebar links below.
    shell_bundle = {"sidebar": [], "written": []}
    dm = state.get("data_model")
    parsed_srs = state.get("srs") or {}
    if dm:
        try:
            # Attach SRS app_pages to data model so app_shell_generator can
            # build the SRS-route sidebar and generate page-level access rules.
            if parsed_srs.get("app_pages"):
                dm["srs_app_pages"] = parsed_srs["app_pages"]

            data_model_planner.write_data_model(output_dir, dm)
            crud_bundle = crud_generator.write_crud(output_dir, dm)
            auth_page_generator.write_auth_pages(output_dir, dm["domain"], genome or {})
            shell_bundle = app_shell_generator.write_app_shell(output_dir, dm)
            state["logs"].append(
                f"--- [AGENT: Data Model + CRUD] wrote {len(crud_bundle['written'])} CRUD files, "
                f"{len(shell_bundle['written'])} app-shell files for "
                f"{len(dm['entities'])} entities ({dm['domain']}) ---")

            # ── SRS-specific pages (POS, reports, admin sections, customer portal) ──
            if parsed_srs.get("app_pages"):
                try:
                    srs_bundle = srs_page_generator.write_srs_pages(output_dir, parsed_srs, dm)
                    # Merge SRS-page sidebar entries BEFORE the standard ones (they
                    # supersede entity-collection links when an SRS is present).
                    shell_bundle["sidebar"] = (
                        srs_bundle.get("sidebar_extras") or []
                    ) + shell_bundle["sidebar"]
                    # Deduplicate by href (first-seen wins; srs_extras take priority)
                    _seen_hrefs, _deduped = set(), []
                    for _se in shell_bundle["sidebar"]:
                        _h = _se.get("href", "")
                        if _h and _h not in _seen_hrefs:
                            _seen_hrefs.add(_h)
                            _deduped.append(_se)
                    shell_bundle["sidebar"] = _deduped
                    state["logs"].append(
                        f"--- [AGENT: SRS Pages] wrote {len(srs_bundle['written'])} SRS-specific files "
                        f"({len(srs_bundle.get('sidebar_extras', []))} sidebar entries) ---")
                except Exception as _spe:
                    state["logs"].append(f"--- [AGENT: SRS Pages] skipped ({str(_spe)[:120]}) ---")

        except Exception as _pe:
            state["logs"].append(f"--- [AGENT: Data Model + CRUD] skipped ({str(_pe)[:80]}) ---")
            # Safety net: even if CRUD gen failed, ensure access.js has canAccessPage.
            # The scaffold stub lacks it; writing a permissive fallback prevents runtime TypeError.
            try:
                _access_path = os.path.join(output_dir, "src", "lib", "access.js")
                if os.path.exists(_access_path):
                    _src = open(_access_path, encoding="utf-8").read()
                    if "canAccessPage" not in _src:
                        with open(_access_path, "a", encoding="utf-8") as _af:
                            _af.write("\nexport function canAccessPage(role, pathname) { return true; }\n")
            except Exception:
                pass
    else:
        state["logs"].append("--- [AGENT: Data Model + CRUD] skipped (no data model from planning) ---")

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

    # --- [AGENT: Design Genome] make the genome NOW (was post-build) so it actually
    # DRIVES structure: per-entity CRUD layout (real kanban/timeline/split-pane/table
    # components), nav/dashboard/list presets, app-shell orientation and marketing
    # section order. Seeded + anti-similar vs recent runs => same prompt twice differs.
    from app import design_genome
    nextgen.write_status(output_dir, "genome", "Choosing composition")
    genome, genome_styles = {}, {}        # safe defaults: a genome error must never break generation
    try:
        genome = design_genome.make_genome(state.get("prompt", ""), history=design_genome.load_history("output"))
        state["genome"] = genome
        genome_styles = design_genome.genome_to_styles(genome)
        # CRUD layouts come from the genome UNLESS the interview pinned the app explicitly
        # (the interview is the user's own intent and stays authoritative).
        if not (state.get("intake") or {}).get("active"):
            for e, lay in zip(ents, design_genome.genome_crud_layouts(genome, len(ents))):
                e["crud_layout"] = lay
        genome["structure_signature"] = design_genome.structure_signature(
            genome, genome_styles, [e["crud_layout"] for e in ents])
        genome["visual_structure_signature"] = design_genome.visual_structure_signature(
            genome, genome_styles, [e["crud_layout"] for e in ents])
        genome["first_screen_skeleton"] = design_genome.first_screen_skeleton(genome)
        state["logs"].append(
            f"--- [AGENT: Design Genome] {genome.get('app_category')} | layout={genome.get('layout_family')} "
            f"shell={genome_styles.get('appNav')} dash={genome_styles.get('dashLayout')} nav={genome_styles.get('nav')} "
            f"crud={[e['crud_layout'] for e in ents]} sections={genome.get('section_strategy')} "
            f"hero={genome.get('hero_variant')} cards={genome.get('card_style')} images={genome.get('image_strategy')} "
            f"inspiration={genome.get('inspiration_family')} ---")
        if genome.get("dna_profile_ids"):
            state["logs"].append(
                f"--- [AGENT: Design DNA] ids={genome.get('dna_profile_ids', [])[:5]} "
                f"families={genome.get('dna_families', [])[:5]} palette={genome.get('color_palette_family')} "
                f"typography={genome.get('typography_style')} rhythm={genome.get('layout_rhythm')} ---")
        if genome.get("art_director_enabled"):
            before = (genome.get("design_quality_before") or {}).get("score", "?")
            after = (genome.get("design_quality_after") or {}).get("score", "?")
            state["logs"].append(
                f"--- [AGENT: Art Director] preset={genome.get('premium_preset_id')} "
                f"quality={before}->{after} hero={((genome.get('hero_recipe') or {}).get('id') or '')[:60]} "
                f"image_roles={list((genome.get('image_roles') or {}).keys())[:6]} ---")
    except Exception as _ge:
        state["logs"].append(f"--- [AGENT: Design Genome] skipped ({str(_ge)[:80]}); using default styles ---")

    try:
        insp_theme = design_genome.inspiration_theme(genome)
        if insp_theme:
            accent = insp_theme.get("accent", accent)
            theme["accent"] = f"text-{accent}-500"
            theme["font_display"] = insp_theme.get("font_display", theme["font_display"])
            theme["font_body"] = insp_theme.get("font_body", theme["font_body"])
            intake_theme = (state.get("intake") or {}).get("theme_style") if (state.get("intake") or {}).get("active") else None
            if insp_theme.get("theme_style") and not intake_theme:
                state["theme_style"] = insp_theme["theme_style"]
            state["logs"].append(
                f"--- [AGENT: Inspiration] family={genome.get('inspiration_family')} "
                f"palette={genome.get('color_palette_family')} typography={genome.get('typography_style')} "
                f"accent={accent} fonts={theme['font_display']}/{theme['font_body']} ---")
            research = genome.get("online_research") or {}
            queries = "; ".join(str(q) for q in (research.get("queries") or []))[:320] or "none"
            refs = ", ".join(str(r.get("url", "")) for r in (research.get("references") or [])[:4] if isinstance(r, dict) and r.get("url"))[:320] or "none"
            fallback = "" if research.get("ok") else f" fallback={research.get('reason', 'curated-only')}"
            state["logs"].append(
                f"--- [AGENT: Design Research] enabled={research.get('enabled', False)} "
                f"mode={genome.get('inspiration_mode', research.get('mode', 'curated'))} "
                f"provider={research.get('provider', 'local')} queries={queries} "
                f"found={research.get('result_count', 0)}{fallback} refs={refs} ---")
    except Exception as _ie:
        state["logs"].append(f"--- [AGENT: Inspiration] theme skipped ({str(_ie)[:80]}) ---")

    # --- [AGENT: Design Agent] Visual identity blueprint + similarity check ----
    # Runs after the genome so it can use genome hints as inspiration. Creates
    # design_blueprint.json in the project dir and updates the shared
    # output/design_history.json so future runs avoid repeating this visual sig.
    _design_history_path = os.path.join("output", "design_history.json")
    _design_blueprint: dict = {}
    _sim_result: dict = {"similarity": 0.0, "too_similar": False, "recommendation": ""}
    try:
        from app import design_agent as _da_mod, visual_similarity_checker as _vsc
        _design_blueprint = _da_mod.create_design_blueprint(
            parsed_srs, genome, output_dir, _design_history_path, app_name)
        state["design_blueprint"] = _design_blueprint
        _sim_result = _vsc.check_similarity(_design_blueprint, _design_history_path, exclude_app_name=app_name)
        state["logs"].append(
            f"--- [AGENT: Design Agent] mood={_design_blueprint.get('domain_mood')} "
            f"hero={_design_blueprint.get('hero_composition')} "
            f"navbar={_design_blueprint.get('navbar_style')} "
            f"similarity={_sim_result.get('similarity', 0):.2f} "
            f"| {_sim_result.get('recommendation', '')[:70]} ---"
        )
    except Exception as _dae:
        state["logs"].append(f"--- [AGENT: Design Agent] skipped ({str(_dae)[:80]}) ---")

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
    marketing_links = nextgen.build_marketing_links(mk_pages)
    # Role-based access: each link lists the roles allowed to SEE it (no
    # "roles" key = everyone). The Sidebar filters by the logged-in user's
    # role, so e.g. a Student never sees an Admin-only manage link or Settings.
    # Entity links come from shell_bundle["sidebar"] (Part 5: role-aware
    # /manage/<collection> links built from the data model's per-entity access).
    primary = roles[0] if roles else "Admin"
    sidebar_links = [{"label": "Dashboard", "href": "/dashboard", "icon": "LayoutDashboard"}]
    sidebar_links += shell_bundle["sidebar"]
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
    styles.update(genome_styles)   # GENOME drives nav/dash/dashLayout/list/appNav (real structure, anti-repeat)
    styles.update({k: v for k, v in (intake.get("styles") or {}).items() if v})  # explicit user picks still win
    # Force sidebar only when genome didn't explicitly choose topnav AND the app is
    # very wide (>9 modules). Smaller overrides let genome variety through.
    _genome_nav = genome_styles.get("appNav", "sidebar")
    if _genome_nav != "topnav" and len(sidebar_links) > 9:
        styles["appNav"] = "sidebar"
    nextgen.write_status(output_dir, "scaffold", "Writing generated app files")
    nextgen.write_site(output_dir, app_name, tagline, marketing_links, sidebar_links, ents, roles, styles, auth_enabled)
    nextgen.write_theme(output_dir, accent, theme["font_display"], theme["font_body"], paradigm)
    nextgen.write_layout_meta(output_dir, app_name, tagline, fonts_url(theme), paradigm)
    try:
        nextgen.materialize_genome_structure(output_dir, genome, styles, ents)
        state["logs"].append(
            f"--- [AGENT: Design Genome] materialized source shell={styles.get('appNav')} "
            f"dash={styles.get('dashLayout')} crud={[e['crud_layout'] for e in ents]} ---")
    except Exception as _me:
        state["logs"].append(f"--- [AGENT: Design Genome] source materialization skipped ({str(_me)[:80]}) ---")

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

    # --- marketing pages from the design library / genome composer -----------
    pages_written = []
    bp_full = dict(state.get("blueprint") or {})
    bp_full.setdefault("entities", [{"name": e["label"]} for e in ents])
    bp_full.setdefault("domain", app_name)
    genome_sections = design_genome.genome_section_order(genome, [])
    genome_visual = design_genome.genome_visual_composition(genome)
    # PRIMARY: use design_planes + section_bank for a world-class 12-16 section
    # landing page. The genome-based page_sections path is kept as a fallback.
    _cls = state.get("app_classification") or {}
    _cat_id = _cls.get("category_id", "")
    _design_plane = state.get("design_plane")

    _home_used_families: set = set()
    if _design_plane:
        # World-class path: classification + design plane → 12-16 curated sections
        # with category-specific headings and hero matched to the plane's hero_variant.
        _compose_entry = {"compose": True, "name": "remix-sections", "file": None}
        detail, landing_src, _home_used_families = design_library.load_landing(
            _compose_entry, theme,
            hero_file=comps["hero"].get("file"),
            prompt_text=state.get("prompt", ""),
            design_plane=_design_plane,
            category_id=_cat_id,
        )
        src = landing_copy.apply("remix-sections", landing_src, copy, app_name)
        state["logs"].append(
            f"--- [AGENT: Design Planes] Landing: {_cat_id} / {_cls.get('app_type','')} "
            f"| template={_cls.get('landing_template', _design_plane.get('landing_template',''))} "
            f"| hero={_cls.get('hero_variant','')} | {detail[:60]} ---"
        )
    else:
        # Fallback: genome-based section composer (secondary pages also use this)
        try:
            from app import page_sections
            src = page_sections.compose_marketing_page(
                {"name": "Home", "slug": "home", "template": "content", "purpose": tagline},
                bp_full, 0, app_name, state.get("ai_sections"), genome_sections, genome_visual)
            state["logs"].append(
                f"--- [AGENT: Design Genome] Home sections {genome.get('section_strategy')} -> "
                f"{', '.join(genome_sections or ['default'])}; hero={genome_visual.get('hero_variant')} "
                f"cards={genome_visual.get('card_style')} image={genome_visual.get('image_strategy')} ---")
        except Exception:
            landing = design["landing"]
            detail, landing_src, _home_used_families = design_library.load_landing(
                landing, theme, hero_file=comps["hero"].get("file"),
                prompt_text=state.get("prompt", ""),
                design_plane=None,
                category_id=_cat_id,
            )
            state["logs"].append(f"--- [AGENT: Design Library] Landing '{landing['name']}' ({detail}) ---")
            src = landing_copy.apply(landing["name"], landing_src, copy, app_name)
    pages_written.append(nextgen.write_page(output_dir, "(marketing)", src))
    # Domain-specific secondary pages from the blueprint (e.g. a school's
    # Admissions / Curriculum / Faculty) - deterministic + build-safe.
    if mk_pages:
        # Pass home-page used_families so sub-pages never repeat the same section families.
        mk_paths = nextgen.write_marketing_pages(output_dir, mk_pages, app_name, bp_full,
                                                 state.get("ai_sections"), genome_sections, genome_visual,
                                                 exclude_families=_home_used_families)
        pages_written.extend(mk_paths)
        state["logs"].append("Marketing pages written: Home, " + ", ".join(p["name"] for p in mk_pages) + ".")
    else:
        state["logs"].append("Utility tool: no marketing tier - users land directly in the workspace.")

    # ── SRS-exact public pages (overwrite generic marketing pages) ────────────
    # When the SRS has public_landing_website.pages with section specs, we
    # overwrite the generic template pages with pharmacy/domain-correct JSX.
    if parsed_srs.get("srs_public_pages"):
        try:
            from app import srs_public_page_generator
            _design_blueprint = state.get("design_blueprint") or {}
            pub_result = srs_public_page_generator.write_srs_public_pages(
                output_dir, parsed_srs, dm, blueprint=_design_blueprint
            )
            pages_written.extend(pub_result["written"])
            state["logs"].append(
                f"--- [AGENT: SRS Public Pages] overwrote {len(pub_result['written'])} "
                f"public pages with SRS-exact pharmacy content ---"
            )
        except Exception as _ppe:
            state["logs"].append(
                f"--- [AGENT: SRS Public Pages] failed ({str(_ppe)[:120]}) ---"
            )

    # --- [AGENT: LLM UI Generator] Augment public pages with blueprint JSX ----
    # Template pages are on disk as a safe baseline. This overwrites each page
    # only when the LLM output passes JSX validation. On failure the template
    # stays intact — no build breakage. Skipped in fast mode.
    if parsed_srs.get("srs_public_pages") and not os.getenv("AI_DESIGNER_FAST"):
        try:
            from app import llm_ui_generator as _llm_ui
            _llm_augmented = _llm_ui.augment_public_pages(
                output_dir, parsed_srs, _design_blueprint, app_name,
                state.get("roles", ["Admin", "User"]), state["logs"],
                fast=False,
            )
            if _llm_augmented > 0:
                state["logs"].append(
                    f"--- [AGENT: LLM UI] {_llm_augmented} public page(s) upgraded with blueprint-guided JSX ---"
                )
        except Exception as _lui:
            state["logs"].append(f"--- [AGENT: LLM UI] skipped ({str(_lui)[:80]}) ---")

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

    # --- Fooocus images FIRST, then one single build ----------------------------
    # Seed fallback placeholders so any slot Fooocus can't fill has a valid file.
    # When AI_DESIGNER_FAST is off, integrate_generated_images() calls
    # ensure_fooocus() and generate_one() per slot before touching the scaffold.
    # The build runs only ONCE, after every real image is on disk, so the very
    # first preview the user sees already has all generated domain images.
    nph = nextgen.seed_placeholder_images(output_dir)
    state["logs"].append(f"--- [AGENT: Image Studio] Seeded {nph} fallback image slots ---")

    from app import image_pipeline
    nextgen.write_status(output_dir, "image_generating", "Generating images")
    asset_plan = image_pipeline.build_asset_plan(output_dir, app_name, state.get("prompt", ""))
    image_pipeline.write_asset_plan(output_dir, asset_plan)
    state["logs"].append(f"--- [AGENT: Image Studio] Asset plan: {len(asset_plan)} JSX image reference(s) -> public/generated ---")
    img_result = image_pipeline.integrate_generated_images(
        output_dir, app_name, state.get("prompt", ""), plan=asset_plan)
    if not img_result.get("ok"):
        nextgen.write_status(output_dir, "error", "Image integration failed")
        state["logs"].append("IMAGE ERROR: " + str(img_result.get("error") or img_result.get("missing") or "unknown"))
        state["status"] = "Generation failed during image integration."
        return state
    if img_result.get("fallback"):
        state["logs"].append(
            f"--- [AGENT: Image Studio] Integrated {img_result.get('integrated', 0)} generated image ref(s); "
            f"{len(img_result.get('fallback', []))} used fallback seeded images ({', '.join(img_result.get('fallback', [])[:5])}) ---")
    else:
        state["logs"].append(
            f"--- [AGENT: Image Studio] Integrated {img_result.get('integrated', 0)} generated image ref(s): "
            f"{', '.join(img_result.get('refs', [])[:6])} ---")

    # --- fast per-file JSX/TS validation BEFORE the build --------------------
    nextgen.write_status(output_dir, "validating", "Validating generated app")
    v_ok, v_bad = image_pipeline.validate_all_pages(output_dir)
    state["logs"].append("--- [VALIDATE] all pages pass JSX validation ---" if v_ok
                         else f"--- [VALIDATE] {len(v_bad)} page(s) flagged: {', '.join(p for p, _ in v_bad[:3])} (build will guard) ---")

    # --- build after image refs are integrated - the guard that nothing broken ships ----
    nextgen.write_status(output_dir, "building", "Building the app")
    state["logs"].append("--- [BUILD] next build (generated images integrated) ---")
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

    state["status"] = "Generation completed."

    # --- [AGENT: Design Critic] QA + visual critique + optional fix rebuild ----
    # Skipped in fast mode. Runs static JSX analysis by default; add
    # AI_DESIGNER_SCREENSHOT_QA=1 for Playwright screenshot capture.
    # Fix loop: regenerate failing pages + one rebuild. Originals are backed up
    # before any overwrite; if the fix rebuild fails the originals are restored.
    if not os.getenv("AI_DESIGNER_FAST"):
        try:
            from app import screenshot_qa as _sqa, design_critic as _dc, llm_ui_generator as _llm_ui
            _qa_results = _sqa.run_qa(output_dir, parsed_srs)
            state["logs"].append(
                f"--- [AGENT: Screenshot QA] {_sqa.summarize(_qa_results)[:160]} ---"
            )
            _critique = _dc.critique_design(
                _qa_results, _design_blueprint, parsed_srs, _sim_result)
            _critic_status = "PASS" if _critique.get("overall_passed") else "FAIL"
            state["logs"].append(
                f"--- [AGENT: Design Critic] {_critic_status} "
                f"score={_critique.get('score', 0)} | {_critique.get('summary', '')[:80]} ---"
            )

            # Fix loop (max 1 rebuild cycle, only when critic found fixable pages)
            if not _critique.get("overall_passed"):
                _fix_pages = _dc.pages_needing_regeneration(_critique, max_pages=3)
                if _fix_pages:
                    _originals: dict = {}
                    _doc_srs = (parsed_srs.get("srs_document") or parsed_srs) or {}
                    _pub_pages = (_doc_srs.get("public_landing_website") or {}).get("pages", [])
                    from app.srs_public_page_generator import _slug_for_page

                    for _fp in _fix_pages:
                        _fp_name = _fp.get("name", "")
                        # Match by slug comparison (page dirs are named via _slug_for_page)
                        _page_data = next(
                            (p for p in _pub_pages
                             if _slug_for_page(p.get("page_name", ""), p.get("route", ""))
                             == _fp_name),
                            {"page_name": _fp_name,
                             "route": f"/{_fp_name}", "sections": []},
                        )
                        _slug = _slug_for_page(
                            _page_data.get("page_name", _fp_name),
                            _page_data.get("route", f"/{_fp_name}"),
                        )
                        _dest = os.path.join(
                            output_dir, "src", "app", "(marketing)", _slug, "page.jsx")
                        if not os.path.exists(_dest):
                            continue
                        try:
                            with open(_dest, encoding="utf-8") as _bf:
                                _originals[_dest] = _bf.read()
                        except Exception:
                            continue
                        _aug_bp = dict(_design_blueprint)
                        _aug_bp["_critic_fix"] = _fp.get("fix_instructions", "")
                        _new_code = _llm_ui.generate_page(
                            _page_data, parsed_srs, _aug_bp,
                            app_name, state.get("roles", ["Admin", "User"]),
                            page_type="home" if _page_data.get("route") in ("/", "") else "listing",
                        )
                        if _new_code:
                            try:
                                with open(_dest, "w", encoding="utf-8") as _wf:
                                    _wf.write(_new_code)
                                state["logs"].append(
                                    f"--- [AGENT: Design Critic] rewrote '{_fp_name}': "
                                    f"{_fp.get('fix_instructions', '')[:60]} ---"
                                )
                            except Exception:
                                _originals.pop(_dest, None)

                    if _originals:
                        state["logs"].append(
                            "--- [AGENT: Design Critic] fix rebuild starting ---"
                        )
                        _fix_ok, _ = nextgen.run_build(output_dir)
                        if _fix_ok:
                            state["logs"].append(
                                "--- [AGENT: Design Critic] fix rebuild succeeded ---"
                            )
                        else:
                            # Restore originals; the prior .next is now stale so rebuild it
                            for _rpath, _rcontent in _originals.items():
                                try:
                                    with open(_rpath, "w", encoding="utf-8") as _rf:
                                        _rf.write(_rcontent)
                                except Exception:
                                    pass
                            nextgen.run_build(output_dir)
                            state["logs"].append(
                                "--- [AGENT: Design Critic] fix build failed; reverted to templates ---"
                            )
        except Exception as _dce:
            state["logs"].append(
                f"--- [AGENT: Design Critic] skipped ({str(_dce)[:80]}) ---"
            )

    # Write the component registry (inert JSON in the project root; never affects the
    # build) so the studio can resolve editable components via a validated manifest.
    try:
        from app import component_registry
        reg = component_registry.write_registry(output_dir)
        v_ok, v_issues = component_registry.validate_registry(output_dir, reg)
        state["logs"].append(f"--- [AGENT: Registry] {len(reg)} editable components mapped"
                             + (" + validated ---" if v_ok else f"; {len(v_issues)} issue(s) ---"))
    except Exception:
        pass

    # Persist the SAME genome that drove this build (incl. its structure signature) and
    # append it to the shared history, so the next run is anti-similar to this real structure.
    try:
        design_genome.write_genome(output_dir, state.get("prompt", ""), genome=state.get("genome"))
        state["logs"].append(f"--- [AGENT: Design Genome] stored structure "
                             f"'{(state.get('genome') or {}).get('structure_signature', '')}' ---")
    except Exception:
        pass

    nextgen.write_status(output_dir, "done", "Preview ready — all domain images generated and built")
    state["logs"].append("--- [DONE] Next.js app built successfully — all Fooocus images integrated, preview is ready ---")
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
