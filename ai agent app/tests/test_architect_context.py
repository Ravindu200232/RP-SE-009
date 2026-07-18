import json
from copy import deepcopy
from pathlib import Path

import pytest

from agents import core, llm, quality, scaffold
from agents.architect import ARCHITECT_JSON_SCHEMA, ArchitectAgent, normalize_spec, validate_spec
from agents.auth_scaffold import auth_files, normalize_roles
from agents.bugfix_agent import BugFixAgent
from agents.component_registry import registry_files
from agents.design import planner as design_planner
from agents.gen_agents import GenAgent, scrub_jsx
from agents.memory import Memory
from agents.product_context import (
    CONTEXT_VERSION,
    ProductContextError,
    build_product_context,
    load_product_context,
    prompt_block,
    write_product_context,
)


def raw_plan():
    return {
        "project_name": "field-notes",
        "site_type": "editorial tool",
        "title": "Field Notes",
        "tagline": "Capture observations where they happen",
        "description": "A public field journal for recording and browsing observations.",
        "brand_name": "Field Notes",
        "target_audience": "Community researchers",
        "key_features": ["Capture observations", "Browse the field journal"],
        "special_instructions": "Keep the experience calm and editorial.",
        "auth": {"enabled": False, "reason": "The journal is intentionally public", "signup": False},
        "roles": [],
        "design": {
            "preset": "modern",
            "mode": "light",
            "navStyle": "topnav",
            "palette": {
                "primary": "#14532d", "secondary": "#0f766e", "accent": "#d97706",
                "background": "#fffdf5", "surface": "#f7f3e8", "text": "#172016",
                "textSecondary": "#5d665b", "border": "#d9dfd4", "success": "#15803d",
                "warning": "#b45309", "error": "#b91c1c",
            },
            "typography": {"heading": "Lora", "body": "Inter"},
            "radius": "md", "shadow": "sm", "spacing": "relaxed", "motion": "subtle",
            "visualSignature": "Botanical specimen labels and an editorial observation grid",
        },
        "data_model": [{
            "name": "Observation",
            "fields": [
                {"name": "title", "type": "String", "required": True},
                {"name": "notes", "type": "String", "required": True},
                {"name": "observedAt", "type": "Date", "required": True},
            ],
        }],
        "pages": [
            {
                "path": "/", "title": "Journal", "kind": "editorial-landing", "access": "public",
                "purpose": "Introduce and browse the observation journal",
                "userJob": "Understand the project and find recent observations",
                "resource": "Observation", "resources": ["Observation"],
                "sections": ["Intro", "RecentObservations", "Method"],
                "functions": ["Browse recent observations", "Search observation titles"],
                "primaryAction": "Browse observations", "archetype": "editorial-index",
                "layout": "Magazine-style lead story followed by a filterable observation grid",
                "visualSignature": "Oversized serif lead with specimen-label cards",
            },
            {
                "path": "/capture", "title": "Capture", "kind": "focused-form", "access": "public",
                "purpose": "Record a field observation", "userJob": "Save a complete observation",
                "resource": "Observation", "resources": ["Observation"],
                "sections": ["ObservationForm"], "functions": ["Validate and save an observation"],
                "primaryAction": "Save observation", "archetype": "field-notebook-form",
                "layout": "Split notebook form with contextual guidance",
                "visualSignature": "Ruled-paper form rhythm with a specimen preview",
            },
        ],
    }


def spec():
    return normalize_spec(raw_plan(), "Build a public editorial field journal with no accounts.")


def test_planning_and_generation_models_are_independently_pinned():
    assert llm.LOCAL_MODEL == "gemma4:12b"
    assert llm.CLOUD_MODEL == "nemotron-3-super:cloud"
    assert llm.ARCHITECT_MODEL == llm.CLOUD_MODEL
    assert {llm.GEN_MODEL, llm.REPAIR_MODEL, llm.REMAINING_MODEL} == {llm.LOCAL_MODEL}
    assert llm.BASE_OPTS["num_ctx"] == 98304
    assert llm.THINK is False and llm.REMAINING_THINK is False
    assert "num_gpu" not in llm.BASE_OPTS
    assert llm.pinned_model("nemotron-3-super:cloud") == llm.LOCAL_MODEL
    assert llm.pinned_architect_model("gemma4:12b") == llm.CLOUD_MODEL


def test_architect_structured_schema_rejects_invented_object_keys():
    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(ARCHITECT_JSON_SCHEMA)


def test_architect_spec_is_input_driven_and_auth_independent():
    planned = spec()
    assert validate_spec(planned) == []
    assert planned["app_kind"] == "multipage-app"
    assert planned["auth"]["enabled"] is False
    assert len(planned["pages"]) == 2
    assert scaffold.auth_enabled(planned) is False
    contract = quality.build_contract(planned)
    assert "/login" not in contract["routes"]
    assert not any(path.startswith("/api/auth") for path in contract["api"])


def test_explicit_input_constraints_are_normalized_without_forcing_a_preset():
    raw = raw_plan()
    raw["design"]["preset"] = "warm-editorial-tea"
    planned = normalize_spec(
        raw, "Create a one-page public guide with no accounts and top navigation.")
    issues = validate_spec(planned)
    assert [page["path"] for page in planned["pages"]] == ["/"]
    assert planned["auth"]["enabled"] is False and planned["roles"] == []
    assert planned["design"]["navStyle"] == "topnav"
    assert issues == []
    assert not any("preset" in issue for issue in issues)


def test_explicit_user_actions_are_losslessly_retained_in_page_functions():
    planned = normalize_spec(
        raw_plan(), "Visitors must compare observations and copy a selected summary.")
    issues = validate_spec(planned)
    functions = " ".join(function for page in planned["pages"] for function in page["functions"])
    assert "compare observations and copy a selected summary" in functions
    assert not any("explicit user action" in issue for issue in issues)


def test_explicit_entity_type_count_rejects_an_architect_mismatch():
    raw = raw_plan()
    raw["data_model"].append({
        "name": "Tea",
        "fields": [{
            "name": "type", "type": "String", "required": True,
            "enum": ["black", "green", "white", "oolong", "herbal", "pu-erh"],
        }],
    })
    planned = normalize_spec(raw, "Create a guide comparing five tea types.")
    issues = validate_spec(planned)
    assert any("requires exactly 5 tea types" in issue and "declares 6" in issue
               for issue in issues)


def test_persistent_saved_favorites_are_rejected_when_not_requested():
    raw = raw_plan()
    raw["pages"][0]["functions"].append("Save favorite teas")
    planned = normalize_spec(raw, "Build a public guide for browsing observations.")
    issues = validate_spec(planned)
    assert "persistent saved-tea/favorites capability was invented without an input requirement" in issues


def test_explicit_local_bookmark_requirement_authorizes_bookmark_capability():
    raw = raw_plan()
    raw["pages"][0]["functions"].append("Bookmark observations locally")
    planned = normalize_spec(raw, "Let visitors bookmark observations locally.")
    issues = validate_spec(planned)
    assert "persistent saved-tea/favorites capability was invented without an input requirement" not in issues


def test_explicit_page_count_is_validated():
    planned = normalize_spec(raw_plan(), "Create a five-page public journal.")
    issues = validate_spec(planned)
    assert any(issue.startswith("the user explicitly requested 5 pages, but the plan declares ")
               for issue in issues)


def test_explicit_named_route_list_cannot_be_replaced_by_unrelated_pages():
    raw = raw_plan()
    raw["pages"] = [
        {**raw["pages"][0], "path": "/", "title": "Atlas"},
        {**raw["pages"][0], "path": "/explore", "title": "Explore"},
        {**raw["pages"][0], "path": "/story/[slug]", "title": "Story Detail"},
        {**raw["pages"][0], "path": "/create", "title": "Create"},
        {**raw["pages"][0], "path": "/bookmarks", "title": "Bookmarks"},
    ]
    planned = normalize_spec(
        raw,
        "Create a five-page journal with routes: Home, City Stories, one Story Detail, "
        "Field Notes, and About.",
    )
    issues = validate_spec(planned)
    assert "the explicitly named page/route 'city stories' is missing from the plan" in issues
    assert "the explicitly named page/route 'field notes' is missing from the plan" in issues
    assert "the explicitly named page/route 'about' is missing from the plan" in issues


def test_explicit_named_route_list_accepts_semantically_matching_pages():
    raw = raw_plan()
    raw["pages"] = [
        {**raw["pages"][0], "path": "/", "title": "Atlas"},
        {**raw["pages"][0], "path": "/city-stories", "title": "City Stories"},
        {**raw["pages"][0], "path": "/stories/[slug]", "title": "Story Detail"},
        {**raw["pages"][0], "path": "/field-notes", "title": "Field Notes"},
        {**raw["pages"][0], "path": "/about", "title": "About"},
    ]
    planned = normalize_spec(
        raw,
        "Create a five-page journal with routes: Home, City Stories, one Story Detail, "
        "Field Notes, and About.",
    )
    assert not any("explicitly named page/route" in issue for issue in validate_spec(planned))


def test_component_dependency_names_are_losslessly_normalized_to_paths():
    raw = raw_plan()
    raw["generation_plan"] = {
        "components": [
            {"name": "TeaCard", "path": "components/features/TeaCard.tsx", "page": "/",
             "type": "display", "responsibility": "Show tea", "props": "", "state": [],
             "actions": [], "dependencies": [], "allowed_resources": [], "expectedLines": 80},
            {"name": "TeaGrid", "path": "components/features/TeaGrid.tsx", "page": "/",
             "type": "list", "responsibility": "Compose tea cards", "props": "", "state": [],
             "actions": [], "dependencies": ["TeaCard"], "allowed_resources": [],
             "expectedLines": 100},
        ],
        "dependencyWaves": [["components/features/TeaCard.tsx"],
                            ["components/features/TeaGrid.tsx"]],
    }
    planned = normalize_spec(raw, "Build a public field guide.")
    assert planned["generation_plan"]["components"][1]["dependencies"] == [
        "components/features/TeaCard.tsx"]
    assert not any("unknown dependency" in issue for issue in validate_spec(planned))


def test_generation_component_state_cannot_shadow_a_prop_callback():
    planned = normalize_spec(raw_plan(), "Build a public field guide.")
    planned["generation_plan"]["components"][0]["props"] = (
        "story: Story; isBookmarked: (slug: string) => boolean")
    planned["generation_plan"]["components"][0]["state"] = [
        "isBookmarked", "copyStatus: boolean"]
    issues = validate_spec(planned)
    assert any("reuses prop name(s) as local state: isBookmarked" in issue for issue in issues)


def test_architect_retries_validation_errors_without_template_fallback(monkeypatch):
    replies = ["not json", json.dumps(raw_plan())]
    calls = []

    def fake_chat(messages, **kwargs):
        calls.append((messages, kwargs))
        return replies.pop(0)

    monkeypatch.setattr(llm, "chat", fake_chat)
    result = ArchitectAgent("qwen2.5-coder:7b").plan("Build a public field journal with no accounts")
    assert result["pages"][1]["path"] == "/capture"
    assert len(calls) == 2
    assert all(call[1]["model"] == llm.CLOUD_MODEL for call in calls)
    assert all(call[1]["think"] is False for call in calls)
    assert all(call[1]["route"] == "architect" for call in calls)
    assert all("format_schema" not in call[1] for call in calls)
    assert "reply was not a raw JSON object" in calls[1][0][0]["content"]


def test_architect_merges_partial_cloud_corrections(monkeypatch):
    first = raw_plan()
    first["design"]["mode"] = "sepia"
    replies = [json.dumps(first), json.dumps({"design": {"mode": "light"}})]
    monkeypatch.setattr(llm, "chat", lambda *args, **kwargs: replies.pop(0))
    result = ArchitectAgent().plan("Build a public editorial field journal with no accounts.")
    assert result["title"] == "Field Notes"
    assert result["design"]["mode"] == "light"
    assert validate_spec(result) == []


def test_product_context_is_lossless_stable_and_persisted(tmp_path):
    planned = spec()
    context = build_product_context(planned)
    assert context["version"] == CONTEXT_VERSION
    assert context["rawInput"] == planned["_raw_idea"]
    assert context["normalizedSpec"]["pages"] == planned["pages"]
    assert context["normalizedSpec"]["data_model"] == planned["data_model"]
    assert context["routeApiFieldContract"]["api"]["/api/observations"] == ["GET", "POST"]
    block = prompt_block(context)
    assert context["contextHash"] in block
    assert "Botanical specimen labels" in block
    write_product_context(tmp_path, context)
    assert load_product_context(tmp_path) == context

    damaged = deepcopy(context)
    damaged["normalizedSpec"]["title"] = "Tampered"
    (tmp_path / ".locode" / "product-context.json").write_text(json.dumps(damaged), encoding="utf-8")
    with pytest.raises(ProductContextError):
        load_product_context(tmp_path)


def test_generation_and_repair_receive_full_product_context(monkeypatch, tmp_path):
    planned = spec()
    context = build_product_context(planned)
    write_product_context(tmp_path, context)
    memory = Memory(tmp_path, planned)
    memory.set_product_context(context)
    captured = []

    def fake_stream(messages, **kwargs):
        captured.append(messages[0]["content"])
        yield "export default function Demo(){return null}"

    monkeypatch.setattr(llm, "stream_chat", fake_stream)
    agent = GenAgent(tmp_path, memory, model="gemma4:12b")
    agent._gen("demo", "TASK: write Demo", num_predict=1000)
    prompt = captured[0]
    for expected in ("FULL PRODUCT CONTEXT", "rawInput", "designPlan", "roles", "pages",
                     "data_model", "routeApiFieldContract", "contextHash", "TASK: write Demo"):
        assert expected in prompt

    repair_memory = BugFixAgent(tmp_path)._repair_memory()
    assert context["contextHash"] in repair_memory
    assert planned["_raw_idea"] in repair_memory


def test_shadcn_semantic_theme_replaces_mui_and_fixed_dark_styles():
    planned = spec()
    files = scaffold.base_files(planned)
    package = json.loads(files["package.json"])
    dependencies = package["dependencies"]
    assert not any(name.startswith("@mui/") or name.startswith("@emotion/") for name in dependencies)
    assert "lucide-react" in dependencies
    assert dependencies["@radix-ui/react-select"] == "2.2.6"
    assert "app/providers.tsx" not in files
    assert "--background: #fffdf5" in files["app/globals.css"]
    assert "color-scheme: light" in files["app/globals.css"]
    assert "bg-background" in files["app/globals.css"]
    assert "AppRouterCacheProvider" not in files["app/layout.tsx"]
    assert "Lora" in files["app/layout.tsx"]

    registry = registry_files(planned)
    assert {"components/ui/dialog.tsx", "components/ui/progress.tsx",
            "components/ui/switch.tsx"}.issubset(registry)
    joined = "\n".join(registry.values())
    assert "bg-slate" not in joined
    assert "@mui" not in joined


def test_schema_and_crud_contracts_are_deterministic_typed_infrastructure():
    files = core.core_files(spec())
    contract = quality.build_contract(spec())
    assert {"models/Observation.ts", "lib/validators/Observation.ts",
            "app/api/observations/route.ts",
            "app/api/observations/[id]/route.ts"}.issubset(files)
    assert "app/api/reports/route.ts" not in files
    assert "/api/reports" not in contract["api"]
    assert "req: NextRequest" in files["app/api/observations/route.ts"]
    assert "{ params }: Ctx" in files["app/api/observations/[id]/route.ts"]


def test_ui_quality_scan_rejects_literal_colours_and_inaccessible_toggles():
    source = """'use client'
export default function Filter({active}:{active:string}) {
  return <button className={active === 'Low' ? \"bg-[#ffffff] text-green-700\" : ''}>Low</button>
}
"""
    findings = quality.scan_source("components/features/Filter.tsx", source,
                                   quality.build_contract(spec()))
    signatures = {item["signature"] for item in findings}
    assert {"nonsemantic-hex-color", "nonsemantic-tailwind-color",
            "toggle-missing-aria-pressed"}.issubset(signatures)


def test_project_scan_requires_architect_selected_top_navigation(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    page = app / "page.tsx"
    page.write_text("export default function Page(){return <main>Guide</main>}\n", encoding="utf-8")
    contract = quality.build_contract(spec())
    assert any(item["signature"] == "missing-top-navigation"
               for item in quality.static_scan(tmp_path, contract))
    page.write_text(
        "export default function Page(){return <><nav aria-label='Primary'>Guide</nav><main /></>}\n",
        encoding="utf-8")
    assert not any(item["signature"] == "missing-top-navigation"
                   for item in quality.static_scan(tmp_path, contract))


def test_auth_shell_honours_nav_style_and_does_not_invent_admin():
    planned = spec()
    planned["auth"] = {"enabled": True, "reason": "Private submissions", "signup": True}
    planned["roles"] = [{
        "name": "researcher", "label": "Researcher", "home": "/capture",
        "rank": 10, "selfSignup": True, "permissions": ["submit observations"],
    }]
    planned["pages"][1]["access"] = "role:researcher"
    assert [role["name"] for role in normalize_roles(planned)] == ["researcher"]

    files = auth_files(planned)
    assert "components/TopNav.tsx" in files
    assert "<TopNav" in files["app/capture/layout.tsx"]
    assert "app/api/admin/users/route.ts" not in files
    assert "app/signup/page.tsx" in files

    planned["design"]["navStyle"] = "none"
    files = auth_files(planned)
    assert "<Sidebar" not in files["app/capture/layout.tsx"]
    assert "<TopNav" not in files["app/capture/layout.tsx"]


def test_design_planner_serializes_page_layout_without_table_fallback():
    planned = spec()
    contract = design_planner.plan(planned)["by_path"]["/"]
    assert contract["archetype"] == "editorial-index"
    assert contract["pattern"] == planned["pages"][0]["layout"]
    assert contract["archetype"] != "table-crud"


def test_ui_surfaces_read_only_split_model_routing():
    root = Path(__file__).parents[1]
    for rel in ("ui/index.html", "electron/ui/index.html"):
        text = (root / rel).read_text(encoding="utf-8")
        assert "Gemma 4 12B Local · 98K · 100% GPU" in text
        assert "Nemotron 3 Super Cloud · Planning" in text
        assert "let selRefine = 'nemotron-3-super:cloud'" in text
        assert "let selBuild = 'gemma4:12b'" in text
        model_block = text.split("const MODELS = [", 1)[1].split("]", 1)[0]
        assert "gemma4:12b" in model_block.lower()
        assert "nemotron-3-super:cloud" in model_block.lower()
        assert "qwen" not in model_block.lower()


def test_compiler_preserving_scrub_closes_only_a_proven_jsx_ancestor():
    source = """'use client'
export default function Demo() {
  return <Card><CardHeader><CardTitle>Quote</CardHeader><Textarea
    onChange={(event) => update({ value: event.target.value })}
  /></Card>
}
"""
    fixed, count = scrub_jsx("components/Demo.tsx", source)
    assert count == 1
    assert "<CardTitle>Quote</CardTitle></CardHeader>" in fixed
    assert "</Textarea>" not in fixed

    extra_brace = "export default function Demo(){ return <main>Ready</main> }\n}\n"
    fixed, count = scrub_jsx("components/Demo.tsx", extra_brace)
    assert count == 1
    assert fixed.rstrip().endswith("</main> }")
