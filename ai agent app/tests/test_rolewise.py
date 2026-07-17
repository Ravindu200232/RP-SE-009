import json
from pathlib import Path

import pytest

from agents.component_pages import compile_component_pages
from agents.component_registry import registry_files, validate_registry_files
from agents.planner import write_artifacts
from agents.quality import build_contract, validate_spec
from agents.srs_adapter import adapt, is_srs
from agents.auth_scaffold import auth_files


FIXTURES = Path(__file__).parent / "fixtures"
EXPECTED = {
    "01_educore_school_role_wise.json": {"roles": 4, "pages": 16, "tables": 11, "relationships": 12, "used_components": 55},
    "02_grandstay_hotel_role_wise.json": {"roles": 4, "pages": 14, "tables": 12, "relationships": 12, "used_components": 48},
    "03_dineflow_restaurant_role_wise.json": {"roles": 5, "pages": 16, "tables": 14, "relationships": 12, "used_components": 57},
}


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name,expected", EXPECTED.items())
def test_rolewise_fixtures_compile_without_inventory_loss(name, expected):
    source = load(name)
    assert is_srs(source)
    spec = adapt(source)
    assert spec["input_schema"] == "role-wise-srs/v1"
    for key, value in expected.items():
        assert spec["analysis"]["counts"][key] == value
    assert spec["analysis"]["errors"] == []
    assert validate_spec(spec) == []


@pytest.mark.parametrize("name", EXPECTED)
def test_planner_emits_complete_artifact_bundle(name, tmp_path):
    spec = adapt(load(name))
    result = write_artifacts(tmp_path, spec, build_contract(spec))
    assert result["coverage"]["complete"] is True
    assert all(item["percent"] == 100 for item in result["coverage"]["dimensions"].values())
    for artifact in ("normalized-spec.json", "analysis.json", "plan.json", "TASKS.md", "contract.json", "coverage.json"):
        assert (tmp_path / ".locode" / artifact).exists()
    tasks = result["plan"]["tasks"]
    assert any(t["kind"] == "component" for t in tasks)
    assert any("/_components/" in t["target"] for t in tasks if t["kind"] == "section")


def test_component_compiler_splits_pages_sections_and_features():
    spec = adapt(load("01_educore_school_role_wise.json"))
    files = compile_component_pages(spec)
    assert "app/teacher/attendance/page.tsx" in files
    assert "app/teacher/attendance/_components/SelectionSection.tsx" in files
    assert any(path.startswith("components/features/") and path.endswith("/AttendanceGrid.tsx") for path in files)
    page = files["app/teacher/attendance/page.tsx"]
    assert "SelectionSection" in page
    assert "MarkAttendanceSection" in page
    assert "getSession" in page
    assert "redirect('/login')" in page


def test_local_component_registry_is_dependency_ready():
    files = registry_files({})
    assert validate_registry_files(files) == []
    manifest = json.loads(files[".locode/shadcn-registry.json"])
    assert manifest["mode"] == "offline-pinned"
    assert "button" in manifest["installed"]
    assert "dialog" in manifest["catalog"]
    assert "@radix-ui/react-slot" in files["components/ui/button.tsx"]


def test_single_pipeline_and_prevention_gates_wired():
    # The dead duplicate template pipeline (`_run_pipeline_once` + its quality-round loop) is removed —
    # only the v2 `run_pipeline` remains, so there is exactly one repair system.
    server_src = (Path(__file__).parents[1] / "server.py").read_text(encoding="utf-8")
    assert "def _run_pipeline_once(" not in server_src
    assert "def run_pipeline(" in server_src
    # The P2 prevention gates are wired into the orchestrator.
    orch = (Path(__file__).parents[1] / "agents" / "orchestrator.py").read_text(encoding="utf-8")
    assert "module_gate.repair_imports" in orch      # module-existence gate (one-shot module-not-found cure)
    assert "build_registry" in orch                  # canonical contract registry → typed DTOs
    assert "contract_scan.scan_project" in orch       # contract-usage scanner (field-name drift)


def test_disabled_signup_never_emits_a_dead_signup_link():
    spec = adapt(load("01_educore_school_role_wise.json"))
    files = auth_files(spec)
    assert "app/signup/page.tsx" not in files
    assert "href='/signup'" not in files["app/login/page.tsx"]
    assert "min-h-[calc(100vh-4rem)]" in files["app/login/page.tsx"]
    assert "hidden w-64" in files["components/Sidebar.tsx"]
    assert "Open role navigation" in files["components/Sidebar.tsx"]


def test_generated_forms_import_only_controls_they_render():
    spec = adapt(load("01_educore_school_role_wise.json"))
    files = compile_component_pages(spec)
    sources = [source for path, source in files.items() if path.endswith("Form.tsx")]
    assert sources
    for source in sources:
        if "<Select " not in source:
            assert "import { Select }" not in source
        if "<Input " not in source:
            assert "import { Input }" not in source
        if "<Label " not in source:
            assert "import { Label }" not in source
        if "update('" not in source:
            assert "const update =" not in source


def test_rolewise_resource_inference_and_api_permissions_are_explicit():
    spec = adapt(load("01_educore_school_role_wise.json"))
    pages = {page["path"]: page for page in spec["pages"]}
    assert {"StudentFee", "FeePayment"}.issubset(pages["/parent/fees"]["resources"])
    assert {"StudentFee", "FeePayment"}.issubset(pages["/accountant/payments/create"]["resources"])
    fee = next(model for model in spec["data_model"] if model["name"] == "StudentFee")
    assert fee["permissions"]["parent"] == ["read"]
    assert set(fee["permissions"]["admin"]) == {"read", "create", "update", "delete"}
