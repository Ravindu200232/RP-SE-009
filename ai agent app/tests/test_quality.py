from pathlib import Path

from agents.quality import build_contract, scan_source, static_scan, validate_spec
from agents import srs_adapter


def _spec():
    return srs_adapter.adapt({
        "project_name": "quality-fixture",
        "app_summary": {"app_name": "Quality Fixture", "short_description": "fixture"},
        "roles": [{"role_key": "admin"}, {"role_key": "staff"}],
        "pages": [
            {"route": "/", "page_name": "Home", "page_type": "public", "allowed_roles": ["guest"]},
            {"route": "/items", "page_name": "Items", "page_type": "staff_crud", "allowed_roles": ["all_staff"]},
        ],
        "database_design": {"collections": [{"name": "items", "fields": {"title": "string required"}}]},
    })


def test_contract_has_exact_route_and_api_manifest():
    spec = _spec()
    contract = build_contract(spec)
    assert "/items" in contract["routes"]
    assert "/api/items" in contract["api"]
    assert validate_spec(spec, contract) == []


def test_known_runtime_regressions_are_blocked(tmp_path: Path):
    comp = tmp_path / "components"
    comp.mkdir()
    (comp / "Broken.tsx").write_text(
        "export default function Broken(){ return <a href='/contact'>x</a> }\n"
        "const ameniments = []; const items = rows.map(row => row.id); const key = row._id\n",
        encoding="utf-8",
    )
    findings = static_scan(tmp_path, build_contract(_spec()))
    signatures = {f["signature"] for f in findings}
    assert "undefined-field-typo:ameniments" in signatures
    assert "records-use-_id" in signatures
    assert "undeclared-route:/contact" in signatures


def test_string_filter_options_are_not_confused_with_input_target_value():
    source = """const regions = ['Asia', 'Europe']
const onChange = (e: React.ChangeEvent<HTMLInputElement>) => search(e.target.value)
const buttons = regions.map((region) => <button key={region}>{region}</button>)
"""
    findings = scan_source("components/features/Filter.tsx", source, {
        "routes": ["/"], "api": {}, "design": {"navStyle": "none"},
    })
    assert not any(item["signature"] == "malformed-form-options" for item in findings)


def test_string_filter_options_used_as_objects_are_rejected():
    source = """const regions = ['Asia', 'Europe']
const buttons = regions.map((region) => <button key={region.value}>{region.label}</button>)
"""
    findings = scan_source("components/features/Filter.tsx", source, {
        "routes": ["/"], "api": {}, "design": {"navStyle": "none"},
    })
    assert any(item["signature"] == "malformed-form-options" for item in findings)


def test_external_background_image_is_rejected_when_raw_input_forbids_it():
    source = """export default function Artwork() {
  return <div style={{ backgroundImage: 'url(https://example.com/texture.png)' }} />
}
"""
    findings = scan_source("components/features/gradient-artwork.tsx", source, {
        "routes": ["/"], "api": {}, "design": {"navStyle": "topnav"},
        "raw_input": "Create layered CSS-gradient artwork with no external image dependency.",
    })
    assert any(item["signature"] == "forbidden-external-image" for item in findings)


def test_literal_rgba_in_generated_ui_is_rejected_as_nonsemantic():
    findings = scan_source("components/features/artwork.tsx", """
export default function Art() {
  return <div style={{ background: 'rgba(212, 175, 55, 0.1)' }} />
}
""", {"routes": ["/"], "api": {}, "design": {"navStyle": "none"}})
    assert any(item["signature"] == "nonsemantic-functional-color" for item in findings)
