from pathlib import Path

from agents.quality import build_contract, static_scan, validate_spec
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
