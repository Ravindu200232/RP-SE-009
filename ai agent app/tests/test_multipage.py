import tempfile
import unittest
from pathlib import Path

from agents.builder import BuilderAgent, _multipage_navbar
from agents import scaffold


SPEC = {
    "app_kind": "multipage-app",
    "auth": {"enabled": True, "signup": True},
    "title": "Test Market",
    "roles": [
        {"name": "owner", "label": "Owner", "home": "/owner", "selfSignup": True},
        {"name": "admin", "label": "Admin", "home": "/admin", "selfSignup": False},
    ],
    "data_model": [{
        "name": "Listing",
        "ownedBy": "User",
        "fields": [{"name": "title", "type": "String", "required": True}],
    }],
    "pages": [
        {"path": "/", "title": "Home", "kind": "landing", "access": "public"},
        {"path": "/listings", "title": "Listings", "kind": "list", "access": "public", "resource": "Listing"},
        {"path": "/listings/[id]", "title": "Listing", "kind": "detail", "access": "public", "resource": "Listing"},
        {"path": "/owner", "title": "Owner", "kind": "dashboard", "access": "role:owner"},
        {"path": "/admin", "title": "Admin", "kind": "dashboard", "access": "role:admin"},
    ],
}


class NoModelBuilder(BuilderAgent):
    def _gen(self, *args, **kwargs):
        return ""


class MultipageRegressionTests(unittest.TestCase):
    def test_contract_documents_auth_mine_and_ownership(self):
        contract = scaffold.api_contract(SPEC)
        self.assertIn("/api/listings/mine", contract)
        self.assertIn("owner or admin only", contract)
        self.assertIn("/api/auth/register", contract)

    def test_pascalcase_link_is_not_treated_as_void_html(self):
        with tempfile.TemporaryDirectory() as temp:
            builder = BuilderAgent(project_dir=Path(temp))
            source = _multipage_navbar(SPEC)
            cleaned = builder._sanitize_jsx(source, "components/AppNavbar.tsx")
            self.assertIn("<Link href='/'", cleaned)
            self.assertNotIn("<Link href='/' className='font-black text-xl gradient-text' />", cleaned)

    def test_extractor_preserves_constants_and_adds_icon_imports(self):
        with tempfile.TemporaryDirectory() as temp:
            builder = BuilderAgent(project_dir=Path(temp))
            source = """'use client'
import { FiHome } from 'react-icons/fi'
const PROPERTY_TYPES = [
  'Apartment',
  'House',
]
export default function Demo() {
  return <div><FiSettings />{PROPERTY_TYPES.join(', ')}</div>
}
"""
            extracted = builder._extract_valid_component(source, "Demo")
            cleaned = builder._sanitize_jsx(extracted, "components/Demo.tsx")
            self.assertIn("const PROPERTY_TYPES", cleaned)
            self.assertRegex(cleaned, r"import \{[^\n]*FiSettings[^\n]*\} from 'react-icons/fi'")

    def test_no_model_fallback_builds_declared_route_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            builder = NoModelBuilder(project_dir=root)
            builder.write_base(SPEC)
            for rel, content in scaffold.auth_files(SPEC).items():
                builder._write_one(rel, content)
            builder.build_frontend(SPEC)
            self.assertTrue((root / "app/listings/page.tsx").exists())
            self.assertTrue((root / "app/listings/[id]/page.tsx").exists())
            self.assertTrue((root / "app/owner/page.tsx").exists())
            self.assertIn("findById", (root / "app/listings/[id]/page.tsx").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
