from __future__ import annotations

import unittest
from types import SimpleNamespace

from test import _support  # noqa: F401
from agents.core.imports.import_checker import (
    BrokenImport,
    check_default_imports,
    check_named_imports,
    group_messages,
)
from agents.core.syntax.syntax_checker import syntax_messages
from agents.core.workspace.source_workspace import WorkspaceTools
from agents.core.runtime.command_runner import _uses_package_manager


class ExportContractTests(unittest.TestCase):
    def test_missing_named_export_is_reported_with_available_choices(self):
        files = {
            "lib/money.js": "export const formatMoney = (value) => String(value)",
            "app/page.jsx": (
                "import { formatCurrency } from '@/lib/money'\n"
                "export default function Page() { return null }"
            ),
        }

        broken = check_named_imports(files)

        self.assertEqual(len(broken), 1)
        self.assertEqual(broken[0].name, "formatCurrency")
        self.assertEqual(broken[0].available, ["formatMoney"])

    def test_valid_named_export_is_not_reported(self):
        files = {
            "lib/money.js": "export function formatMoney(value) { return String(value) }",
            "app/page.jsx": (
                "import { formatMoney } from '@/lib/money'\n"
                "export default function Page() { return formatMoney(10) }"
            ),
        }

        self.assertEqual(check_named_imports(files), [])

    def test_missing_default_export_is_reported(self):
        files = {
            "components/Notice.jsx": "export const Notice = () => <p>Ready</p>",
            "app/page.jsx": (
                "import Notice from '@/components/Notice'\n"
                "export default function Page() { return <Notice /> }"
            ),
        }

        broken = check_default_imports(files)

        self.assertEqual(len(broken), 1)
        self.assertEqual(broken[0].module, "components/Notice.jsx")

    def test_close_match_accepts_a_case_only_export_difference(self):
        broken = BrokenImport(
            importer="app/page.jsx",
            line=1,
            name="getsession",
            module="lib/session.js",
            spec="@/lib/session",
            available=["getSession", "createSession"],
        )

        self.assertEqual(broken.close_match(), "getSession")

    def test_grouped_message_keeps_all_missing_names_together(self):
        broken = [
            BrokenImport("app/page.jsx", 2, "one", "lib/a.js", "@/lib/a", ["ok"]),
            BrokenImport("app/page.jsx", 3, "two", "lib/a.js", "@/lib/a", ["ok"]),
        ]

        messages = group_messages(broken)

        self.assertEqual(len(messages), 1)
        self.assertIn("one, two", messages[0])
        self.assertIn("exports only: ok", messages[0])

    def test_a_scaffold_module_is_never_told_to_grow_an_export(self):
        """AgentForge refuses to rewrite lib/mongodb.js, so that repair is a trap.

        Suggesting it burned every repair round on a write that is always
        rejected, and the build ended on the import it started with.
        """
        broken = [BrokenImport("app/api/bookings/route.js", 3, "insertDocument",
                               "@/lib/mongodb", "@/lib/mongodb",
                               ["ObjectId", "getCollection", "getDb", "serialize"])]

        message = group_messages(broken)[0]

        self.assertNotIn("add the missing export", message)
        self.assertIn("cannot gain exports", message)
        self.assertIn("getCollection", message)
        self.assertIn("insertOne", message)

    def test_syntax_message_contains_file_line_and_repair_context(self):
        message = syntax_messages([
            {"path": "components/Card.jsx", "line": 14, "message": "Unexpected }"}
        ])[0]

        self.assertIn("components/Card.jsx:14", message)
        self.assertIn("Unexpected }", message)
        self.assertIn("valid JavaScript", message)


class CommandCoordinationTests(unittest.TestCase):
    def test_windows_package_manager_path_uses_the_shared_install_lock(self):
        self.assertTrue(_uses_package_manager(
            [r"C:\Program Files\nodejs\npm.CMD", "install"]))
        self.assertTrue(_uses_package_manager(["npx", "vitest", "run"]))
        self.assertFalse(_uses_package_manager(["node", "script.js"]))


class WorkspaceToolTests(unittest.TestCase):
    def setUp(self):
        self.arch = SimpleNamespace(
            project_dir=_support.ROOT,
            files={
                "app/api/orders/[id]/route.js": "export async function GET() {}",
                "app/orders/[id]/page.jsx": (
                    "import Card from '@/components/Card'\n"
                    "export default function Page() { return <Card /> }"
                ),
                "components/Card.jsx": "export default function Card() { return <div /> }",
                "lib/format.js": "export const format = String",
            },
        )
        self.tools = WorkspaceTools(self.arch)

    def test_tool_requests_keep_the_order_written_by_the_agent(self):
        reply = (
            '<search_code query="orders"/>\n'
            '<read_file path="components/Card.jsx"/>\n'
            '<route_map prefix="/"/>'
        )

        self.assertEqual(
            self.tools.requests(reply),
            [
                ("search_code", "orders"),
                ("read_file", "components/Card.jsx"),
                ("route_map", "/"),
            ],
        )

    def test_read_file_refuses_parent_directory_escape(self):
        self.assertEqual(self.tools.read_file("../secrets.env"), "refused unsafe path")

    def test_dynamic_page_route_maps_to_its_source(self):
        result = self.tools.route_source("/orders/abc123")

        self.assertIn("app/orders/[id]/page.jsx", result)

    def test_dynamic_api_route_maps_to_its_handler(self):
        result = self.tools.route_source("/api/orders/abc123")

        self.assertIn("app/api/orders/[id]/route.js", result)

    def test_repeated_tool_request_is_served_only_once(self):
        reply = '<read_file path="components/Card.jsx"/>'

        first, first_count = self.tools.serve(reply)
        second, second_count = self.tools.serve(reply)

        self.assertEqual(first_count, 1)
        self.assertIn("COMPLETE", first)
        self.assertEqual(second_count, 0)
        self.assertIn("already served", second)


if __name__ == "__main__":
    unittest.main()
