from __future__ import annotations

import unittest

from test import _support  # noqa: F401
from srs_agent.app.generators.builder_prompt import render_prompt
from srs_agent.app.generators.builder_utils import (
    _api_file,
    _entity,
    _field_spec,
    _kind_for,
    _normal_route_pattern,
    _normal_type,
    _page_file,
)


class BuilderHandoffTests(unittest.TestCase):
    def test_route_parameters_are_converted_to_next_dynamic_segments(self):
        self.assertEqual(
            _normal_route_pattern("/rooms/{room_id}?tab=availability"),
            "/rooms/[room_id]",
        )

    def test_page_and_api_paths_follow_next_app_router_layout(self):
        self.assertEqual(_page_file("/rooms/{room_id}"), "app/rooms/[room_id]/page.jsx")
        self.assertEqual(
            _api_file("/api/rooms/{room_id}"),
            "app/api/rooms/[room_id]/route.js",
        )

    def test_reference_field_preserves_object_id_semantics(self):
        spec = _field_spec({
            "name": "guest_id",
            "type": "string",
            "references": "users.id",
            "nullable": False,
            "unique": True,
        })

        self.assertEqual(spec["type"], "ObjectId")
        self.assertEqual(spec["references"], "users.id")
        self.assertTrue(spec["required"])
        self.assertTrue(spec["unique"])

    def test_srs_types_are_normalized_for_builder_storage(self):
        self.assertEqual(_normal_type("decimal"), "Number")
        self.assertEqual(_normal_type("datetime"), "Date")
        self.assertEqual(_normal_type("boolean"), "Boolean")
        self.assertEqual(_normal_type("array of strings"), "Array")

    def test_entity_hint_singularizes_plain_plural_names(self):
        self.assertEqual(_entity("sale items"), "SaleItem")
        self.assertEqual(_entity("categories"), "Category")

    def test_requirement_language_maps_to_the_expected_capability_kind(self):
        self.assertEqual(_kind_for("Create a new reservation"), "create")
        self.assertEqual(_kind_for("Approve a pending request"), "edit")
        self.assertEqual(_kind_for("Cancel an existing booking"), "delete")
        self.assertEqual(_kind_for("Search the booking history"), "list")
        self.assertEqual(_kind_for("Generate a printable summary"), "feature")

    def test_builder_prompt_is_a_natural_srs_handoff(self):
        handoff = {
            "app_name": "SportNova", "appType": "Sports e-commerce web application",
            "product_intent": "Customers browse products and admins manage the store",
            "roles": [{"name": "Customer"}, {"name": "Admin"}],
            "access": [
                {"role": "Customer", "allowed_functions": ["Browse products", "Complete checkout"]},
                {"role": "Admin", "allowed_functions": ["Manage products", "Manage orders"]},
            ],
            "feature_contracts": [
                {"module": "Product Discovery", "requirement": "Search and filter products", "routes": ["/products"], "roles": ["Customer"]},
                {"module": "Shopping Cart", "requirement": "Update cart quantities", "routes": ["/cart"], "roles": ["Customer"]},
            ],
            "models": [{"name": "Product", "field_specs": [{"name": "name", "required": True}, {"name": "brand_id", "references": "brands.id"}]}],
            "relationships": [{"from": "brands.id", "to": "products.brand_id", "type": "one_to-many"}],
            "pages": [{"route": "/products", "public": True}, {"route": "/cart", "public": False, "allowed_roles": ["Customer"]}],
            "workflows": [{"name": "Purchase Journey", "routes": ["/products", "/cart"], "steps": ["Browse a product", "Add it to cart"]}],
            "auth_contract": {"enabled": True, "sign_in_route": "/sign-in", "identity_fields": ["email", "password"], "self_registration": False},
            "invariants": ["Every mutation persists"],
        }
        prompt = render_prompt(handoff, {"look_and_feel": "Use a bold modern sports-retail visual style"})
        self.assertTrue(prompt.startswith("Build a complete production-quality"))
        self.assertIn("## Main User Roles", prompt)
        self.assertIn("## Product Discovery", prompt)
        self.assertIn("Create `/products`.", prompt)
        self.assertIn("## Main Data Models", prompt)
        self.assertIn("## Required Routes", prompt)
        self.assertIn("## Required End-to-End Journeys", prompt)
        self.assertNotIn("FEATURE LEDGER", prompt)
        self.assertNotIn("TRACEABILITY —", prompt)


if __name__ == "__main__":
    unittest.main()
