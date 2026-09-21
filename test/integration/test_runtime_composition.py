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
        self.assertEqual(parts[0], "server_modules/core/bootstrap.py")
        # Each part uses what the ones before it defined, so order is a
        # contract rather than a preference.
        self.assertLess(parts.index("server_modules/builder/media.py"),
                        parts.index("server_modules/builder/pipeline.py"))
        self.assertLess(parts.index("server_modules/builder/bridge.py"),
                        parts.index("server_modules/builder/pipeline.py"))
        self.assertLess(parts.index("server_modules/builder/pipeline.py"),
                        parts.index("server_modules/builder/edits.py"))
        self.assertLess(parts.index("server_modules/ui/http_base.py"),
                        parts.index("server_modules/ui/http_handler.py"))
        self.assertEqual(parts[-1], "server_modules/core/main.py")

    def test_full_app_runtime_mounts_srs_qa_deployment_builder_and_ui(self):
        parts = set(runtime_parts())
        required = {
            "server_modules/builder/pipeline.py",
            "server_modules/builder/edits.py",
            "server_modules/qa/artifacts.py",
            "server_modules/qa/runner.py",
            "server_modules/srs/srs_runtime.py",
            "server_modules/srs/srs_api.py",
            "server_modules/deploy/deploy_runtime.py",
            "server_modules/deploy/deploy_api.py",
            "server_modules/ui/http_handler.py",
        }

        self.assertEqual(required - parts, set())

    def test_the_agents_are_importable_packages_beside_the_server(self):
        """The agents are libraries, not runtime parts.

        Executing an agent into the shared namespace would make it unusable
        from the CLI, from a test, and from the other agents.
        """
        for package in ("builder-agent/builder_agent", "qa-agent/qa_agent",
                        "srs-agent/srs_agent", "deployment-agent/deploy_agent"):
            self.assertTrue((ROOT / package / "__init__.py").is_file(), package)
        for part in runtime_parts():
            self.assertFalse(part.startswith(("builder-agent/", "qa-agent/")), part)

    def test_no_runtime_part_imports_a_package_that_no_longer_exists(self):
        """A stale import inside a function fails only when that path runs.

        `from qa_agent.unit.harness_common import NPM_LOCK` sat inside
        `ensure_node_deps`, so it survived every import check and every test,
        and would have failed the first time a real build installed anything.
        """
        gone = ("agents.", "qa_agent.unit", "qa_agent.e2e", "qa_agent.core",
                "qa_agent.server", "qa_agent.verification")
        offenders = []
        for part in runtime_parts():
            source = (ROOT / part).read_text(encoding="utf-8")
            for number, line in enumerate(source.splitlines(), 1):
                text = line.strip()
                if not text.startswith(("import ", "from ")):
                    continue
                if any(f"{prefix}" in text for prefix in gone):
                    offenders.append(f"{part}:{number}: {text}")

        self.assertEqual(offenders, [])

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
        bootstrap = (ROOT / "server_modules/core/bootstrap.py").read_text(encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
