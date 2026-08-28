"""Focused contracts for the compact server action helpers."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server_runtime as server


class OwnedDirectoryTests(unittest.TestCase):
    def test_owned_dir_accepts_only_existing_direct_child(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            child = root / "project"
            child.mkdir()

            name, resolved, error = server._owned_dir(
                root, "project", "project name", "project")

            self.assertEqual(name, "project")
            self.assertEqual(resolved, child.resolve())
            self.assertEqual(error, "")

    def test_owned_dir_rejects_traversal_hidden_and_missing_names(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            for name in ("../escape", "..\\escape", ".hidden", ""):
                with self.subTest(name=name):
                    _, resolved, error = server._owned_dir(
                        root, name, "project name", "project")
                    self.assertIsNone(resolved)
                    self.assertTrue(error)

            _, resolved, error = server._owned_dir(
                root, "missing", "project name", "project")
            self.assertIsNone(resolved)
            self.assertEqual(error, "no such project: missing")


class MessageDispatchTests(unittest.TestCase):
    def job(self, kind, **values):
        message = {"type": kind, "model": "model", **values}
        return server._message_job(message)

    def test_build_and_resume_contracts(self):
        target, args = self.job(
            "agent_build", prompt=" build ", qa_model="qa",
            think=False, logo=" logo.png ", srs_id=" spec ")
        self.assertIs(target, server.run_agent_pipeline)
        self.assertEqual(
            args,
            ("build", "model", False, "qa", "", "logo.png", "spec"))

        target, args = self.job(
            "agent_resume", project=" demo ", qa_model="qa", think=True)
        self.assertIs(target, server.run_agent_pipeline)
        self.assertEqual(args, ("", "model", True, "qa", "demo"))

    def test_edit_action_contracts(self):
        element = {"tag": "button"}
        cases = (
            ("chat", server.run_chat,
             ("demo", "change", "model", "/rooms", None, "qa", "log")),
            ("agent_update", server.run_chat,
             ("demo", "change", "model", "/rooms", None, "qa", "log")),
            ("pencil_edit", server.run_pencil_edit,
             ("demo", "change", None, "model", None)),
            ("element_edit", server.run_element_edit,
             ("demo", "change", element, "model", None, "log")),
            ("image_edit", server.run_image_edit,
             ("demo", "change", element, "model", None)),
            ("feature", server.run_feature,
             ("demo", "change", "model", None, "qa", "/rooms", "log")),
        )
        for kind, expected_target, expected_args in cases:
            with self.subTest(kind=kind):
                message = {
                    "project": " demo ", "prompt": " change ",
                    "route": " /rooms ", "qa_model": "qa",
                    "console": "log", "element": element,
                    "build_model": "builder",
                }
                if kind == "pencil_edit":
                    expected_args = (
                        "demo", "change",
                        {"type": kind, "model": "model", **message},
                        "model", None)
                target, args = self.job(kind, **message)
                self.assertIs(target, expected_target)
                self.assertEqual(args, expected_args)

    def test_invalid_or_incomplete_action_is_ignored(self):
        self.assertIsNone(server._message_job({"type": "unknown"}))
        self.assertIsNone(self.job("feature", project="demo"))


class AnalyzerFactoryTests(unittest.TestCase):
    def test_runtime_configuration_is_centralized(self):
        with patch.object(server, "AnalyzerAgent", return_value="analyzer") as ctor:
            result = server._analyzer_for("arch", Path("project"))
        self.assertEqual(result, "analyzer")
        self.assertEqual(
            ctor.call_args.kwargs["base_url"],
            f"http://localhost:{server.DEV_PORT}")
        self.assertIn("callbacks", ctor.call_args.kwargs)

    def test_non_runtime_analyzer_omits_base_url(self):
        with patch.object(server, "AnalyzerAgent", return_value="analyzer") as ctor:
            server._analyzer_for("arch", Path("project"), runtime=False)
        self.assertNotIn("base_url", ctor.call_args.kwargs)


class DatabaseFaultTests(unittest.TestCase):
    """A dead database is infrastructure, not a bug in the generated app."""

    def test_only_connection_faults_count_as_the_database_being_down(self):
        self.assertTrue(server.database_fault([
            "DB: /api/health failed → 500 "
            "MongoServerSelectionError: connect ECONNREFUSED 127.0.0.1:27017"]))
        self.assertTrue(server.database_fault(["MongoNetworkError: socket closed"]))

        # An app bug must never be mistaken for the database going away, or the
        # run restarts mongod instead of repairing the fault it actually has.
        self.assertFalse(server.database_fault([
            "TypeError: filteredRooms.map is not a function"]))
        self.assertFalse(server.database_fault(["/api/health returned 500"]))
        self.assertFalse(server.database_fault([]))


if __name__ == "__main__":
    unittest.main()
