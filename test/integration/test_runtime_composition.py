from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path

from test import _support


ROOT = _support.ROOT


def runtime_parts() -> tuple[str, ...]:
    tree = ast.parse((ROOT / "server_runtime.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "_RUNTIME_PARTS" for target in node.targets):
                return tuple(ast.literal_eval(node.value))
    raise AssertionError("server_runtime.py does not declare _RUNTIME_PARTS")


def integer_constant(source: str, name: str) -> int:
    match = re.search(rf"^\s*(?:const\s+)?{re.escape(name)}\s*=\s*(\d+)", source, re.MULTILINE)
    if not match:
        raise AssertionError(f"missing integer constant: {name}")
    return int(match.group(1))


class SharedRuntimeCompositionTests(unittest.TestCase):
    def test_every_shared_runtime_part_exists_in_the_repository(self):
        missing = [part for part in runtime_parts() if not (ROOT / part).is_file()]

        self.assertEqual(missing, [])

    def test_runtime_parts_are_unique_and_bootstrap_before_consumers(self):
        parts = runtime_parts()

        self.assertEqual(len(parts), len(set(parts)))
        self.assertEqual(parts[0], "server_modules/core/startup/bootstrap.py")
        self.assertLess(parts.index("qa_agent/server/unit_support.py"), parts.index("qa_agent/server/unit_stage.py"))
        self.assertLess(parts.index("server_modules/ui/http_base.py"), parts.index("server_modules/ui/http_handler.py"))
        self.assertEqual(parts[-1], "server_modules/core/endpoints/main.py")

    def test_full_app_runtime_mounts_srs_qa_deployment_builder_and_ui(self):
        parts = set(runtime_parts())
        required = {
            "agents/pipeline/build_pipeline.py",
            "qa_agent/server/unit_stage.py",
            "qa_agent/server/e2e_stage.py",
            "server_modules/srs/srs_runtime.py",
            "server_modules/srs/srs_api.py",
            "server_modules/deploy/deploy_runtime.py",
            "server_modules/deploy/deploy_api.py",
            "server_modules/ui/http_handler.py",
        }

        self.assertEqual(required - parts, set())

    def test_stable_server_entrypoint_delegates_to_shared_runtime(self):
        tree = ast.parse((ROOT / "server.py").read_text(encoding="utf-8"))
        imports = {
            alias.name
            for node in tree.body
            if isinstance(node, ast.Import)
            for alias in node.names
        }

        self.assertIn("server_runtime", imports)


class DesktopProcessContractTests(unittest.TestCase):
    def test_electron_backend_ports_match_the_python_runtime(self):
        bootstrap = (ROOT / "server_modules/core/startup/bootstrap.py").read_text(encoding="utf-8")
        desktop = (ROOT / "desktop/main.js").read_text(encoding="utf-8")
        match = re.search(r"BACKEND_PORTS\s*=\s*\[([^]]+)]", desktop)
        self.assertIsNotNone(match)
        electron_ports = [int(value) for value in re.findall(r"\d+", match.group(1))]
        python_ports = [
            integer_constant(bootstrap, "UI_PORT"),
            integer_constant(bootstrap, "WS_PORT"),
            integer_constant(bootstrap, "SRS_PORT"),
            integer_constant(bootstrap, "DEPLOY_PORT"),
        ]

        self.assertEqual(electron_ports, python_ports)

    def test_electron_and_studio_agree_on_the_ui_port(self):
        desktop = (ROOT / "desktop/main.js").read_text(encoding="utf-8")
        studio_package = json.loads((ROOT / "studio/package.json").read_text(encoding="utf-8"))
        port = integer_constant(desktop, "STUDIO_PORT")

        self.assertIn(f"--port {port}", studio_package["scripts"]["dev"])
        self.assertIn(f"--port {port}", studio_package["scripts"]["start"])

    def test_electron_package_points_to_the_real_desktop_entrypoint(self):
        package = json.loads((ROOT / "desktop/package.json").read_text(encoding="utf-8"))

        self.assertEqual(package["main"], "main.js")
        self.assertEqual(package["scripts"]["start"], "electron .")
        self.assertTrue((ROOT / "desktop" / package["main"]).is_file())


class StudioStartupResilienceTests(unittest.TestCase):
    def test_ui_handler_keeps_the_real_http_handler_base(self):
        source = (ROOT / "server_modules/ui/http_handler.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        handler = next(node for node in tree.body
                       if isinstance(node, ast.ClassDef) and node.name == "UIHandler")
        bases = {base.id for base in handler.bases if isinstance(base, ast.Name)}
        self.assertIn("SimpleHTTPRequestHandler", bases)

    def test_desktop_waits_for_backend_before_opening_the_studio(self):
        source = (ROOT / "desktop/main.js").read_text(encoding="utf-8")
        self.assertIn("waitForPort(BACKEND_PORTS[0])", source)
        self.assertIn("waitForPort(STUDIO_PORT)", source)

    def test_studio_retries_projects_and_models_and_keeps_cloud_fallbacks(self):
        page = (ROOT / "studio/app/page.jsx").read_text(encoding="utf-8")
        models = (ROOT / "studio/lib/models.js").read_text(encoding="utf-8")
        self.assertIn("retry(() => api.projects(), 6, 500)", page)
        self.assertIn("retry(() => api.models(), 6, 500)", page)
        self.assertIn("CLOUD_FALLBACK", models)

    def test_mongo_install_uses_the_current_platform_executable_helper(self):
        source = (ROOT / "agents/data/database_install.py").read_text(encoding="utf-8")
        self.assertNotIn('_exe("mongod")', source)
        self.assertIn('_platform_executable("mongod")', source)


if __name__ == "__main__":
    unittest.main()
