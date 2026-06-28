"""Part of the `interview` package (auto-split, verbatim). See interview/__init__.py."""
import json
import os
import re
from app import srs
from ._config import _APP_TYPE_VALUES, _COV_LABEL, _DEFAULT_LABELS, _DESIGN_STEPS, _LABEL_BY_VALUE, _LAYOUTS, _PARADIGMS, _VALID_THEMES, _norm_layout, _page_template, _slug
from ._plan import sections_for_page

def assemble_intake(answers: dict) -> dict:
    """Normalize the studio's collected answers into the generation spec."""
    answers = answers or {}
    app_type = answers.get("app_type") if answers.get("app_type") in _APP_TYPE_VALUES else "hybrid"
    raw_pages = answers.get("pages") or []
    comp_map = answers.get("components") or {}
    pages = []
    for p in raw_pages:
        if isinstance(p, str):
            name, slug, template = p, _slug(p), _page_template(p)
        else:
            name = p.get("label") or p.get("name") or "Page"
            slug = _slug(p.get("value") or p.get("slug") or name)
            template = p.get("template") or _page_template(name)
        secs = [s for s in (comp_map.get(slug) or comp_map.get(name) or []) if s]
        pages.append({"name": str(name)[:28], "slug": slug, "template": template, "sections": secs})

    roles = [str(r).strip()[:24] for r in (answers.get("roles") or []) if str(r).strip()]
    entities = []
    for e in (answers.get("entities") or []):
        if isinstance(e, dict) and e.get("name"):
            entities.append({"name": re.sub(r"[^A-Za-z0-9]", "", str(e["name"])),
                             "label": str(e.get("label") or e["name"])[:30], "layout": _norm_layout(e.get("layout", "table"))})
    # extra + coverage answers -> a requirements note appended to the build prompt
    notes = []
    cov = answers.get("coverage") or {}
    for k, v in cov.items():
        name = _COV_LABEL.get(k, k.replace("_", " "))
        if v is True:
            notes.append(f"{name} yes")
        elif v is False:
            continue
        elif isinstance(v, list) and v:
            notes.append(f"{name} {', '.join(map(str, v))}")
        elif isinstance(v, str) and v.strip():
            notes.append(f"{name} {v.strip()}")
    extras = answers.get("extras") or {}
    for k, v in extras.items():
        if isinstance(v, list) and v:
            notes.append(f"{k.replace('_', ' ')}: {', '.join(map(str, v))}")
        elif isinstance(v, str) and v.strip():
            notes.append(f"{k.replace('_', ' ')}: {v.strip()}")

    auth = bool(answers.get("auth", app_type != "public")) and app_type != "public"
    theme = str(answers.get("theme", "")).lower().strip()
    return {
        "active": True, "app_type": app_type, "language": answers.get("language", "en"),
        "pages": pages if app_type != "internal" else [],   # internal apps skip the public tier
        "auth": auth, "roles": roles,
        "entities": entities, "entity_layouts": {e["name"]: e["layout"] for e in entities},
        "theme_style": theme if theme in _VALID_THEMES else "",
        "styles": {k: v for k, v in (answers.get("design") or {}).items() if v},   # navbar/dash/list presets
        "coverage": cov,
        "requirements": "; ".join(notes)[:1200],
    }
def _q(qid, kind, label, plan, **kw):
    return {"question": {"id": qid, "kind": kind, "label": label, **kw}, "plan": plan}
def _answered_count(plan, answers):
    n = 0
    comps = answers.get("components") or {}
    if answers.get("pages") is not None:
        n += 1 + sum(1 for p in (answers.get("pages") or []) if isinstance(p, dict) and (p.get("value") or p.get("slug")) in comps)
    for k in ("auth", "roles", "entities", "theme"):
        if k in answers:
            n += 1
    n += len(answers.get("coverage") or {})
    n += len(answers.get("extras") or {})
    return n
def next_step(plan: dict, answers: dict) -> dict:
    """Return the next question, or {done, answers} when the interview is over."""
    plan = plan or {}
    answers = answers or {}
    app_type = plan.get("app_type", "hybrid")
    lang = plan.get("language", "en")
    L = plan.get("labels", _DEFAULT_LABELS)
    total = (1 + max(len(answers.get("pages") or []), len(plan.get("pages") or []))
             + (1 if app_type != "public" else 0) + (2 if app_type != "public" else 0)
             + len(plan.get("coverage") or []) + len(plan.get("extra_questions") or []) + 1)
    prog = {"index": _answered_count(plan, answers), "total": total}

    def out(res):
        res["progress"] = prog
        return res

    # 1) pages
    if answers.get("pages") is None:
        opts = [{"value": p["slug"], "label": p["label"], "template": p["template"]} for p in plan.get("pages", [])]
        return out(_q("pages", "multi", L.get("pages", "Which pages do you want?"), plan,
                      options=opts, default=[o["value"] for o in opts], allow_custom=True, hint=L.get("subtitle")))

    # 2) sections for each chosen page, in order. Options are SPECIFIC to that
    # page (from the plan; custom pages get them from the LLM on the spot).
    comp = answers.get("components") or {}
    for p in (answers.get("pages") or []):
        slug = (p.get("value") or p.get("slug")) if isinstance(p, dict) else str(p)
        if slug and slug not in comp:
            known = next((pp for pp in plan.get("pages", []) if pp["slug"] == slug), None)
            if known:
                opts = known.get("sections") or [{"value": v, "label": _LABEL_BY_VALUE.get(v, v)} for v in (known.get("section_values") or ["hero", "features", "cta"])]
                default = known.get("section_values") or [o["value"] for o in opts]
            else:
                r = sections_for_page(plan.get("description", ""), lang, p.get("label", slug))
                opts, default = r["options"], r["default"]
            return out(_q("sections:" + slug, "multi",
                          (L.get("sections", "What sections on this page?")) + " — " + str(p.get("label", slug)),
                          plan, options=opts, default=default, allow_custom=True))

    # 3) auth (skip for public)
    if app_type != "public" and "auth" not in answers:
        return out(_q("auth", "toggle", L.get("auth", "Do you need user login?"), plan,
                      default=plan.get("auth_default", True), yes=L.get("auth_yes", "Yes"), no=L.get("auth_no", "No")))
    auth_on = bool(answers.get("auth")) if app_type != "public" else False

    # 4) roles
    if auth_on and "roles" not in answers:
        opts = [{"value": r, "label": r} for r in plan.get("roles", [])]
        return out(_q("roles", "multi", L.get("roles", "Who are the users?"), plan,
                      options=opts, default=[o["value"] for o in opts], allow_custom=True))

    # 5) data records + layout
    if auth_on and "entities" not in answers:
        items = [{"name": e["name"], "label": e["label"], "layout": e["layout"]} for e in plan.get("entities", [])]
        return out(_q("entities", "entity_layouts", L.get("data", "What information will it manage?"), plan,
                      items=items, layout_options=_LAYOUTS, default=items, allow_custom=True))

    # 5.5) coverage areas - the rule: comprehensive, non-technical, one at a time,
    # skipping the ones that don't apply (auth / app type / depends-on a prior yes).
    cov = answers.get("coverage") or {}
    for area in plan.get("coverage", []):
        if area["id"] in cov:
            continue
        if area.get("needs_auth") and not auth_on:
            continue
        dep = area.get("depends")
        if dep:
            prev = cov.get(dep["id"])
            ok = bool(prev) if dep.get("truthy") else ((isinstance(prev, list) and dep.get("value") in prev) or prev == dep.get("value"))
            if not ok:
                continue
        kind = area["kind"]
        opts = [{"value": o, "label": o} for o in area.get("options", [])]
        if kind == "toggle":
            default = False
        elif kind == "text":
            default = ""
        elif kind == "single" and area.get("options"):
            default = area["options"][0]
        else:
            default = []
        return out(_q("cov:" + area["id"], kind, area["label"], plan,
                      options=opts, default=default, allow_custom=(kind not in ("toggle", "text"))))

    # 6) extra domain questions, one at a time
    extras = answers.get("extras") or {}
    for eq in plan.get("extra_questions", []):
        if eq["id"] not in extras:
            kind = "toggle" if eq["type"] == "toggle" else ("single" if eq["type"] == "single" else "multi")
            return out(_q("extra:" + eq["id"], kind, eq["label"], plan,
                          options=[{"value": o, "label": o} for o in eq.get("options", [])],
                          default=(False if kind == "toggle" else []), allow_custom=eq.get("allow_custom", True)))

    # 7) theme
    if "theme" not in answers:
        return out(_q("theme", "single", L.get("style", "Pick a visual style"), plan,
                      options=_PARADIGMS, default=plan.get("theme_default", "minimal")))

    # 8) design presets - navbar (always), dashboard + list (login apps only)
    design = answers.get("design") or {}
    for did, label, opts in _DESIGN_STEPS:
        if did in ("dash", "list") and not auth_on:
            continue
        if did not in design:
            return out(_q("design:" + did, "single", label, plan, options=opts, default=opts[0]["value"]))

    # done
    return {"done": True, "answers": {**answers, "app_type": app_type, "language": lang}, "plan": plan, "progress": prog}
