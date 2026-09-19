"""Workspace roots with no own dependencies must reuse their existing install."""
import json
import tempfile
import unittest
from pathlib import Path
from test import _support  # noqa: F401
import server_runtime as server


class DependencyReadinessTests(unittest.TestCase):
    def put(self, root, name, payload):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_hoisted_workspace_dependencies_are_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.put(root, "package.json", {"workspaces": ["packages/*", "client"]})
            self.put(root, "client/package.json", {"dependencies": {"react": "^19"}})
            self.put(root, "packages/api/package.json", {"dependencies": {"express": "^5"}})
            self.put(root, "node_modules/react/package.json", {"name": "react"})
            self.put(root, "node_modules/express/package.json", {"name": "express"})
            self.assertTrue(server._deps_ready(root))
            self.put(root, "client/package.json", {"dependencies": {"react": "^19", "new-package": "1"}})
            self.assertFalse(server._deps_ready(root))

    def test_nested_workspace_install_is_resolved_before_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.put(root, "package.json", {"workspaces": ["client"]})
            self.put(root, "client/package.json", {"devDependencies": {"vite": "^7"}})
            self.put(root, "client/node_modules/vite/package.json", {"name": "vite"})
            (root / "node_modules").mkdir()
            self.assertTrue(server._deps_ready(root))
