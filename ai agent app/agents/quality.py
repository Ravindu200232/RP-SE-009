"""Strict quality contracts and source-level regression checks.

This module is intentionally dependency-free.  It runs before the generated app
is served and turns the normalized Locode spec into a machine-checkable contract.
The contract is also written into every successful project's verification bundle so
the tester and the UI use the same source of truth.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


QUALITY_VERSION = 1


def _norm_path(value: str) -> str:
    value = str(value or "/").strip()
    if not value.startswith("/"):
        value = "/" + value
    value = re.sub(r"/{2,}", "/", value)
    if len(value) > 1:
        value = value.rstrip("/")
    return value


def build_contract(spec: dict) -> dict:
    """Build the exact route/API/link contract used by strict verification."""
    from agents.scaffold import auth_enabled, route_name

    pages = []
    # `/login` exists only where the auth scaffold emits it. Seeding it unconditionally told the
    # undeclared-route check that a "Login" button is always fine — so a no-auth app shipped a nav
    # with a dead Login link and this scan reported clean.
    routes = {"/login"} if auth_enabled(spec) else set()
    for page in spec.get("pages") or []:
        if not isinstance(page, dict) or not page.get("path"):
            continue
        path = _norm_path(page["path"])
        access = str(page.get("access") or "public")
        entry = {
            "path": path,
            "access": access,
            "kind": str(page.get("kind") or "static"),
            "resource": str(page.get("resource") or ""),
            "title": str(page.get("title") or path),
        }
        pages.append(entry)
        routes.add(path)
    auth = spec.get("auth") or {}
    if auth.get("signup", True):
        routes.add("/signup")
    # Only shared-dashboard SRS apps expose /dashboard. Role-wise inputs use exact
    # per-role homes such as /teacher/dashboard and /front-desk/dashboard.
    role_homes = {str(r.get("home") or "") for r in (spec.get("roles") or []) if isinstance(r, dict)}
    if "/dashboard" in role_homes or any(p.get("path") == "/dashboard" for p in pages):
        routes.add("/dashboard")

    api = {
        "/api/auth/register": ["POST"],
        "/api/auth/login": ["POST"],
        "/api/auth/logout": ["POST"],
        "/api/auth/me": ["GET"],
    }
    if spec.get("app_kind") == "multipage-app":
        api.update({"/api/admin/users": ["GET"], "/api/admin/users/[id]/role": ["PUT"]})
    kits = set(spec.get("kits") or [])
    if "inventory" in kits:
        api["/api/stock/adjust"] = ["POST"]
    if "invoicing" in kits:
        api["/api/invoices/[id]/payments"] = ["POST"]
    if "pos" in kits:
        api["/api/pos/checkout"] = ["POST"]
    # `/api/reports` is emitted by core.core_files for EVERY app that has a non-User model (see
    # scaffold.reports_route), and the dashboard rule tells the model to fetch it. Declaring it only
    # for `kits` apps made the dashboard's own required call look undeclared.
    if "reports" in kits or any(str(m.get("name", "")).lower() not in ("", "user")
                                for m in (spec.get("data_model") or [])):
        api["/api/reports"] = ["GET"]
    collections = []
    for model in spec.get("data_model") or []:
        name = str(model.get("name") or "Item")
        seg = route_name(name)
        base = f"/api/{seg}"
        endpoints = {base: ["GET", "POST"], f"{base}/[id]": ["GET", "PUT", "DELETE"]}
        if model.get("ownedBy") == "User":
            endpoints[f"{base}/mine"] = ["GET"]
        api.update(endpoints)
        collections.append({
            "name": name,
            "segment": seg,
            "owned": model.get("ownedBy") == "User",
            "fields": model.get("fields") or [],
        })

    allowed_links = sorted(routes | {p["path"].replace("[id]", "__id__") for p in pages})
    return {
        "version": QUALITY_VERSION,
        "strict": True,
        "max_pages": 19,
        "routes": sorted(routes),
        "pages": pages,
        "source_pages": spec.get("pages") or [],
        "api": api,
        "collections": collections,
        "roles": spec.get("roles") or [],
        "components": spec.get("component_contracts") or [],
        "actions": spec.get("actions") or [],
        "relationships": spec.get("relationships") or [],
        "input_schema": spec.get("input_schema"),
        "input_hash": spec.get("input_hash"),
        "allowed_links": allowed_links,
        "rules": [
            "no-invented-routes", "no-invented-api", "records-use-_id",
            "no-hardcoded-business-metrics", "functional-pages-deterministic",
        ],
    }


def _page_component_name(page: dict) -> str:
    """Mirror of agents.orchestrator.component_name (route path → body-component name), used here to
    detect specs where two DISTINCT routes would collapse to the same components/pages/<Comp>.tsx."""
    from agents.scaffold import pascal
    path = str(page.get("path") or "/")
    tokens: list[str] = []
    for seg in path.strip("/").split("/"):
        if not seg:
            continue
        if seg.startswith("["):
            param = seg.strip("[].")
            tokens.append("By" + pascal(param) if param else "Dyn")
        else:
            tokens.append(pascal(seg))
    base = "".join(tokens) if tokens else "Home"
    if str(page.get("kind")) == "detail":
        base += "Detail"
    return base + "Page"


def validate_spec(spec: dict, contract: dict | None = None) -> list[str]:
    """Validate normalized spec invariants before any files are generated."""
    errors: list[str] = []
    contract = contract or build_contract(spec)
    errors.extend(str(x) for x in ((spec.get("analysis") or {}).get("errors") or []))
    pages = contract.get("pages") or []
    if len(pages) > int(contract.get("max_pages", 19)):
        errors.append(f"page-count-exceeds-{contract['max_pages']}")
    paths = [p["path"] for p in pages]
    duplicates = sorted({p for p in paths if paths.count(p) > 1})
    if duplicates:
        errors.append("duplicate-routes:" + ",".join(duplicates))
    # Two DISTINCT routes that resolve to the SAME page-body component name would overwrite each
    # other's components/pages/<Comp>.tsx (the 'same file generated twice' bug). The generator now
    # auto-suffixes to stay safe, but a spec-level clash is worth surfacing.
    comp_map: dict[str, set] = {}
    for p in pages:
        comp_map.setdefault(_page_component_name(p), set()).add(p["path"])
    clashes = sorted(f"{c}({'/'.join(sorted(ps))})" for c, ps in comp_map.items() if len(ps) > 1)
    if clashes:
        errors.append("component-name-collision:" + ",".join(clashes))
    roles = {str(r.get("name")) for r in contract.get("roles") or [] if isinstance(r, dict)}
    for p in pages:
        access = str(p.get("access") or "public")
        if access.startswith("role:"):
            unknown = [x for x in access[5:].split("|") if x and x not in roles]
            if unknown:
                errors.append(f"unknown-role:{p['path']}:{','.join(unknown)}")
    for coll in contract.get("collections") or []:
        names = [str(f.get("name")) for f in coll.get("fields") or [] if isinstance(f, dict)]
        if len(names) != len(set(names)):
            errors.append(f"duplicate-fields:{coll['name']}")
        for field in coll.get("fields") or []:
            if not isinstance(field, dict) or not field.get("ref"):
                continue
            known_models = {c.get("name") for c in contract.get("collections") or []} | {"User"}
            if field.get("ref") not in known_models:
                errors.append(f"unknown-reference:{coll['name']}.{field.get('name')}:{field.get('ref')}")
    # Every section-level component and action must have a canonical contract.
    known_components = {c.get("name") for c in contract.get("components") or [] if isinstance(c, dict)}
    for page in spec.get("pages") or []:
        for section in page.get("sections") or []:
            # A section is either {'section_name', 'components'} (role-wise SRS) or a plain string
            # label (single-page specs). SectionAgent has always accepted both; this never ran, so it
            # never learned to.
            if not isinstance(section, dict):
                continue
            for name in section.get("components") or []:
                if name not in known_components:
                    errors.append(f"missing-component-contract:{page.get('path')}:{name}")
    if any(str(a.get("kind")) == "unresolved" for a in contract.get("actions") or [] if isinstance(a, dict)):
        errors.append("unresolved-actions")
    return errors


def _source_files(project_dir: Path):
    for root in (project_dir / "app", project_dir / "components", project_dir / "lib", project_dir / "models"):
        if not root.exists():
            continue
        yield from (p for p in root.rglob("*") if p.suffix in {".ts", ".tsx", ".js", ".jsx"})


def _component_feature_path(contract: dict) -> str:
    allowed = contract.get("allowed_resources") or ["shared"]
    feature = re.sub(r"[^a-z0-9]+", "-", str(allowed[0]).lower()).strip("-") or "shared"
    return f"components/features/{feature}/{contract.get('name')}.tsx"


def _section_component_name(value: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", str(value or "Section"))
    return "".join(x[:1].upper() + x[1:] for x in parts) + "Section"


def component_graph_scan(project_dir: Path, contract: dict) -> list[dict]:
    """Ensure every canonical component/section exists and participates in imports."""
    if contract.get("input_schema") != "role-wise-srs/v1":
        return []
    findings = []
    sources = {}
    for path in _source_files(project_dir):
        try:
            sources[path.relative_to(project_dir).as_posix()] = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
    all_text = "\n".join(sources.values())
    for component in contract.get("components") or []:
        rel = _component_feature_path(component)
        name = str(component.get("name") or "")
        if rel not in sources:
            findings.append({"signature": f"missing-component-file:{name}", "file": rel,
                             "message": f"declared component {name} has no generated file"})
            continue
        import_pattern = re.compile(rf"import\s+{re.escape(name)}\s+from\s+['\"][^'\"]+['\"]")
        imported_elsewhere = any(import_pattern.search(text) for path, text in sources.items() if path != rel)
        if not imported_elsewhere:
            findings.append({"signature": f"unused-component:{name}", "file": rel,
                             "message": f"generated component {name} is never imported"})
    for page in contract.get("pages") or []:
        clean = str(page.get("path") or "/").strip("/")
        page_dir = f"app/{clean}" if clean else "app"
        page_rel = f"{page_dir}/page.tsx"
        page_text = sources.get(page_rel, "")
        if not page_text:
            findings.append({"signature": f"missing-page-file:{page.get('path')}", "file": page_rel,
                             "message": "declared route has no page.tsx"})
            continue
        # Locate source section metadata from the canonical page stored alongside contract.
        source_page = next((p for p in (contract.get("source_pages") or []) if p.get("path") == page.get("path")), None)
        for section in (source_page or {}).get("sections") or []:
            component = _section_component_name(section.get("section_name"))
            section_rel = f"{page_dir}/_components/{component}.tsx"
            if section_rel not in sources:
                findings.append({"signature": f"missing-section-file:{page.get('path')}:{component}",
                                 "file": section_rel, "message": "declared section has no component file"})
            elif not re.search(rf"import\s+{re.escape(component)}\s+from\s+['\"]\./_components/", page_text):
                findings.append({"signature": f"section-not-imported:{page.get('path')}:{component}",
                                 "file": page_rel, "message": "page does not import its section component"})
    # Registry integrity is a separate signature family so repair points at the source registry.
    for required in ("components.json", "lib/utils.ts", "components/ui/button.tsx", "components/ui/card.tsx"):
        if required not in sources and not (project_dir / required).exists():
            findings.append({"signature": f"missing-registry-file:{required}", "file": required,
                             "message": "local component registry file is missing"})
    return findings


def static_scan(project_dir: Path, contract: dict) -> list[dict]:
    """Catch runtime-only defects that TypeScript/Next can miss, across the whole project."""
    unique: dict = {}
    for path in _source_files(project_dir):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for item in scan_source(path.relative_to(project_dir).as_posix(), text, contract):
            unique[(item["signature"], item["file"])] = item
    # Cross-file checks can only run once every file exists.
    for item in component_graph_scan(project_dir, contract):
        unique[(item["signature"], item["file"])] = item
    return list(unique.values())


def scan_source(rel: str, text: str, contract: dict) -> list[dict]:
    """The same checks against ONE candidate file, before it is written.

    A green build says nothing about a "Login" button in an app that has no login page — the compiler
    cannot see it, so it has to be checked here, in the same loop that regenerates the file, while the
    prompt that produced it is still at hand."""
    findings: list[dict] = []
    allowed = set(contract.get("allowed_links") or [])
    route_literals = set(contract.get("routes") or [])
    api_literals = set(contract.get("api", {}).keys())

    # Known recurrent runtime defects and their general forms.
    for bad, rule in [("ameniments", "undefined-field-typo"), ("/owner/dashboard", "invalid-redirect")]:
        if bad in text:
            findings.append({"signature": f"{rule}:{bad}", "file": rel, "message": f"forbidden token {bad}"})
    if re.search(r"\bitem\.id\b|\brow\.id\b", text) and "_id" in text:
        findings.append({"signature": "records-use-_id", "file": rel, "message": "mixed id/_id record contract"})
    if re.search(r"Active Users\s*[:=]\s*['\"]?\d", text, re.I):
        findings.append({"signature": "hardcoded-business-metric", "file": rel, "message": "metric is not API/report backed"})
    if re.search(r"const\s+Link\s*=|type\s+Link\s*=", text) and re.search(r"import\s+Link\s+from\s+['\"]next/link", text):
        findings.append({"signature": "duplicate-link-identifier", "file": rel, "message": "Link import/type collision"})
    imported = []
    for im in re.finditer(r"import\s+(?:\{([^}]+)\}|([A-Za-z_$][\w$]*))\s+from\s+['\"]", text):
        if im.group(2):
            imported.append(im.group(2))
        if im.group(1):
            imported.extend(re.sub(r"\bas\b", " ", x).strip().split()[0]
                            for x in im.group(1).split(",") if x.strip())
    duplicates = sorted({x for x in imported if imported.count(x) > 1})
    if duplicates:
        findings.append({"signature": "duplicate-imports:" + ",".join(duplicates), "file": rel, "message": "identifier imported more than once"})
    if re.search(r"const\s+\w+\s*=\s*\[[^\]]*['\"][^\]]*['\"]\s*\]", text) and re.search(r"\b\w+\.(?:value|label)\b", text):
        findings.append({"signature": "malformed-form-options", "file": rel, "message": "string option array used as object options"})

    # Literal internal links must target a declared route. Dynamic [id] links
    # are checked against the route shape and accepted with __id__.
    for match in re.finditer(r"(?:href|router\.push|redirect)\s*=?\s*[({]?\s*['\"](/[^'\"]*)", text):
        href = _norm_path(match.group(1))
        if href.startswith("/api/"):
            continue
        # `/` always exists. `/login` and `/signup` do NOT: they are emitted by the auth scaffold
        # only. Exempting them unconditionally is why an app with no accounts could ship a nav
        # with a dead "Login" button and still scan clean — let the contract decide.
        if href == "/":
            continue
        if href not in route_literals and href not in allowed:
            # Ignore hash anchors and external/static asset paths.
            if not href.startswith("/#") and not href.startswith("/_next"):
                findings.append({"signature": f"undeclared-route:{href}", "file": rel, "message": f"link/redirect {href} is not declared"})

    # Fetch calls may only target declared APIs.
    for match in re.finditer(r"fetch\(\s*['\"](/api/[^'\"]+)", text):
        endpoint = match.group(1)
        # A query string is not part of the route: `/api/reports?type=summary` IS `/api/reports`, and
        # comparing the whole literal flagged the one call the dashboard rule mandates.
        endpoint = endpoint.split("?")[0].rstrip("/")
        normalized = re.sub(r"/[A-Za-z0-9_-]{8,24}(?=['\"`])", "/[id]", endpoint)
        if endpoint not in api_literals and normalized not in api_literals:
            findings.append({"signature": f"undeclared-api:{endpoint}", "file": rel, "message": f"API {endpoint} is not in contract"})

    # Deduplicate repeated evidence from the same file.
    unique = {}
    for item in findings:
        unique[(item["signature"], item["file"])] = item
    return list(unique.values())


def write_manifest(project_dir: Path, spec: dict, contract: dict, report: dict | None = None):
    out = project_dir / "verification"
    out.mkdir(parents=True, exist_ok=True)
    (out / "contract.json").write_text(json.dumps(contract, indent=2), encoding="utf-8")
    if report is not None:
        (out / "report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")


def bug_signatures(errors: list[str] | list[dict]) -> list[str]:
    result = []
    for error in errors:
        text = error.get("message", "") if isinstance(error, dict) else str(error)
        sig = error.get("signature") if isinstance(error, dict) else None
        sig = sig or re.sub(r"\s+", " ", text.strip())[:180]
        if sig and sig not in result:
            result.append(sig)
    return result
