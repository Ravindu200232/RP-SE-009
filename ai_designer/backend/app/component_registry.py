"""Per-project Component Registry (smallest safe layer).

A registry is a list of editable-component descriptors written to
`output/<project>/_component_registry.json`:

    {"component_id": "home", "route": "/", "source_file": "src/app/(marketing)/page.jsx",
     "type": "marketing", "editable": ["text","className","image"],
     "image_refs": ["/assets/hero.jpg"], "text_refs": []}

It is OPTIONAL and ADDITIVE: `editor.resolve_component_file` checks the registry
FIRST, then the route resolver, then the legacy _STATIC_MAP. Projects WITHOUT a
registry keep working exactly as before (backward compatible). The registry's
value is a validated, project-specific manifest + precise overrides.
"""
import json
import os
import re

REGISTRY_FILE = "_component_registry.json"
_EDITABLE = ["text", "className", "image"]
_IMG_RE = re.compile(r"/(?:assets|generated)/[A-Za-z0-9_.-]+")


def _scan_image_refs(abs_path: str) -> list:
    try:
        with open(abs_path, encoding="utf-8") as f:
            src = f.read()
    except OSError:
        return []
    return sorted(set(_IMG_RE.findall(src)))


def build_registry(out_dir: str) -> list:
    """Enumerate the project's editable page/component files into registry entries.
    Smallest-safe: one entry per known route/component that actually exists on disk,
    with image_refs scanned from the file. Keyed by the SAME ids the inspector sends."""
    entries, seen = [], set()

    def add(cid, route, rel, ctype):
        if cid in seen:
            return
        abs_path = os.path.join(out_dir, *rel.split("/"))
        if not os.path.exists(abs_path):
            return
        seen.add(cid)
        entries.append({
            "component_id": cid, "route": route, "source_file": rel, "type": ctype,
            "editable": list(_EDITABLE), "image_refs": _scan_image_refs(abs_path), "text_refs": [],
        })

    add("navbar", None, "src/components/shell/Navbar.jsx", "navbar")
    add("sidebar", None, "src/components/shell/Sidebar.jsx", "sidebar")
    add("home", "/", "src/app/(marketing)/page.jsx", "marketing")
    for name in ("dashboard", "profile", "settings", "notifications"):
        add(name, "/" + name, f"src/app/(app)/{name}/page.jsx", "app")
    mkt = os.path.join(out_dir, "src", "app", "(marketing)")
    if os.path.isdir(mkt):
        for d in sorted(os.listdir(mkt)):
            if os.path.isfile(os.path.join(mkt, d, "page.jsx")):
                add("page-" + d, "/" + d, f"src/app/(marketing)/{d}/page.jsx", "marketing")
    add("crud-list", "/e/[entity]", "src/app/(app)/e/[entity]/page.jsx", "crud-list")
    add("crud-detail", "/e/[entity]/[id]", "src/app/(app)/e/[entity]/[id]/page.jsx", "crud-detail")
    add("crud-new", "/e/[entity]/new", "src/app/(app)/e/[entity]/new/page.jsx", "crud-new")
    add("crud-edit", "/e/[entity]/[id]/edit", "src/app/(app)/e/[entity]/[id]/edit/page.jsx", "crud-edit")
    return entries


def write_registry(out_dir: str) -> list:
    """Build + persist the registry. Safe to call post-build (inert JSON in project
    root - never affects the Next build). Returns the registry."""
    reg = build_registry(out_dir)
    try:
        with open(os.path.join(out_dir, REGISTRY_FILE), "w", encoding="utf-8") as f:
            json.dump(reg, f, indent=2)
    except OSError:
        pass
    return reg


def load_registry(out_dir: str):
    p = os.path.join(out_dir, REGISTRY_FILE)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else None
    except (OSError, ValueError):
        return None


def resolve(out_dir: str, component_id: str):
    """Registry lookup: component_id -> (source_file_rel, abs_path), or (None, None)
    if there's no registry or no matching entry (so the caller falls back)."""
    reg = load_registry(out_dir)
    if not reg:
        return None, None
    cid = str(component_id or "").strip()
    for e in reg:
        if e.get("component_id") == cid:
            rel = e.get("source_file", "")
            abs_path = os.path.join(out_dir, *rel.split("/")) if rel else ""
            return (rel, abs_path) if rel and os.path.exists(abs_path) else (rel or None, None)
    return None, None


def validate_registry(out_dir: str, registry=None):
    """Validators -> (ok, issues[]). Checks: no duplicate component_id; every
    source_file exists; every image_ref exists OR is an allowed placeholder slot
    (a seeded V2_NAMES name or a cache-busted img_*). Readable string issues."""
    try:
        from app.fooocus_images import V2_NAMES
    except Exception:
        V2_NAMES = ()
    reg = registry if registry is not None else (load_registry(out_dir) or build_registry(out_dir))
    issues, seen = [], set()
    assets = os.path.join(out_dir, "public", "assets")
    generated = os.path.join(out_dir, "public", "generated")
    for e in reg:
        cid = e.get("component_id")
        if not cid:
            issues.append("entry with empty component_id")
            continue
        if cid in seen:
            issues.append(f"duplicate component_id: {cid}")
        seen.add(cid)
        rel = e.get("source_file", "")
        if not rel or not os.path.exists(os.path.join(out_dir, *rel.split("/"))):
            issues.append(f"missing source_file for '{cid}': {rel}")
        for ref in e.get("image_refs", []):
            base = os.path.basename(str(ref).split("?")[0])
            is_generated = str(ref).startswith("/generated/")
            root = generated if is_generated else assets
            exists = bool(base) and os.path.exists(os.path.join(root, base))
            placeholder_ok = (not is_generated) and (base in V2_NAMES or base.startswith("img_") or base == "placeholder.jpg")
            if not exists and not placeholder_ok:
                issues.append(f"image_ref unresolved + not a placeholder slot: {ref} ('{cid}')")
    return (len(issues) == 0, issues)
