"""Focused contracts for the compact server action helpers."""
from __future__ import annotations

import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import server_runtime as server


class PipelineLifecycleTests(unittest.TestCase):
    def tearDown(self):
        server.cancel.finish()

    def test_completed_e2e_finishes_without_starting_a_second_qa_agent(self):
        from builder_agent.memory import Memory

        memory = Memory()
        memory.evidence.define_scope("web", "nextjs", [
            {"id": "booking", "description": "Book a room",
             "evidence": ["unit", "runtime", "e2e"]}
        ])
        unit = memory.evidence.start("unit", "all", "vitest run", [], ["booking"])
        memory.evidence.observe(unit, {"exitCode": 0,
            "stdout": "Test Files 2 passed (2)\nTests 8 passed (8)"})
        for kind in ("runtime", "e2e"):
            memory.evidence.record_external(kind=kind, suite=kind, source="runner",
                status="passed", covers=["booking"],
                output="1. navigate -> /\n2. assert textIncludes -> Booked")
        builder = SimpleNamespace(memory=memory)
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(server, "_prepare_workspace", return_value=Path(directory)), \
                patch.object(server.MONGO, "ensure_running"), \
                patch.object(server, "_brief", return_value="hotel"), \
                patch.object(server, "_run_agent", return_value=(
                    builder, SimpleNamespace(status="completed"))), \
                patch.object(server, "fill_missing_images"), \
                patch.object(server, "_serve", return_value="http://localhost"), \
                patch.object(server, "QAAgent") as qa, \
                patch.object(server, "edone") as done, \
                patch.object(server, "eerr") as error:
            qa.return_value.run.return_value = SimpleNamespace(ok=True)
            server.run_agent_pipeline("hotel", "model")
            saved = server.qa_report.read(Path(directory))
            self.assertEqual(saved["vitest"]["numPassedTests"], 8)
            self.assertEqual(saved["report"]["e2e"]["stage_passed"], 2)
            done.assert_called_once_with("http://localhost", Path(directory).name)

        error.assert_not_called()
        qa.assert_not_called()

    def test_cancel_adapter_returns_the_requested_state(self):
        server.cancel.begin()
        self.assertFalse(server._cancelled())
        self.assertTrue(server.cancel.request()["ok"])
        self.assertTrue(server._cancelled())

    def test_build_registers_and_releases_cancellation(self):
        def stop_run(*args, **kwargs):
            self.assertEqual(server.cancel.request(),
                             {"ok": True, "project": "demo", "srs_id": "spec"})
            return None, SimpleNamespace(status="cancelled")

        with patch.object(server, "_prepare_workspace", return_value=Path("demo")), \
                patch.object(server.MONGO, "ensure_running"), \
                patch.object(server, "_brief", return_value="build"), \
                patch.object(server, "_run_agent", side_effect=stop_run) as run, \
                patch.object(server, "ecancel") as stopped, \
                patch.object(server, "eerr") as error:
            server.run_agent_pipeline("build", "model", srs_id="spec")
        run.assert_called_once()
        stopped.assert_called_once_with({"project": "demo"})
        error.assert_not_called()
        self.assertFalse(server.cancel.request()["ok"])

    def test_done_requires_completed_build_and_passing_qa(self):
        for status, qa_ok, url in (("unverified", True, "http://localhost"),
                                   ("completed", False, "http://localhost"),
                                   ("completed", True, "")):
            with self.subTest(status=status, qa_ok=qa_ok, url=url), \
                    patch.object(server, "edone") as done, \
                    patch.object(server, "eerr") as error:
                result = server._finish("demo", url,
                                        SimpleNamespace(status=status, result="incomplete"),
                                        SimpleNamespace(ok=qa_ok, reason="checks failed"))
                self.assertFalse(result)
                done.assert_not_called()
                error.assert_called_once()

        with patch.object(server, "edone") as done:
            self.assertTrue(server._finish("demo", "http://localhost",
                                           SimpleNamespace(status="completed"),
                                           SimpleNamespace(ok=True)))
            done.assert_called_once_with("http://localhost", "demo")


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
    def test_chat_can_add_features_without_calling_every_request_a_bug(self):
        with patch.object(server, "_edit_run") as run:
            server.run_chat("demo", "Add room search", "model", "/rooms")
        brief = run.call_args.kwargs["brief"]
        self.assertIn("Add room search", brief)
        self.assertNotIn("The user reports this problem", brief)
        self.assertIn("new feature", brief)
        self.assertIn("/rooms", brief)

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
            ("build", "model", False, "qa", "", "logo.png", "spec", ""))

    def test_a_stack_chosen_in_the_studio_reaches_the_run(self):
        """Reading it out of the wording of the brief is the fallback, not the rule."""
        _, args = self.job("agent_build", prompt="a shop",
                           stack=" mern-microservices ")
        self.assertEqual(args[-1], "mern-microservices")

        _, args = self.job("agent_build", prompt="a shop")
        self.assertEqual(args[-1], "")

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
            ("element_edit", server.run_element_edit,
             ("demo", "change", element, "model", None, "log", [], "/rooms")),
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
                target, args = self.job(kind, **message)
                self.assertIs(target, expected_target)
                self.assertEqual(args, expected_args)

    def test_a_selection_of_several_elements_travels_whole(self):
        """Clicking three things has to send three things, with their pictures."""
        elements = [{"tag": "button"}, {"tag": "h1"}, {"tag": "img"}]
        shots = [{"kind": "element", "image": "AAAA"},
                 {"kind": "drawing", "image": "BBBB"}]
        target, args = self.job(
            "element_edit", project="demo", prompt="tidy these",
            route="/plants", elements=elements, shots=shots)
        self.assertIs(target, server.run_element_edit)
        self.assertEqual(args,
                         ("demo", "tidy these", elements, "model", None, "",
                          shots, "/plants"))

    def test_the_removed_editing_actions_are_gone(self):
        """The pencil and the picture tool are one selection surface now."""
        for kind in ("pencil_edit", "image_edit"):
            with self.subTest(kind=kind):
                self.assertIsNone(self.job(
                    kind, project="demo", prompt="change",
                    element={"tag": "button"}))

    def test_invalid_or_incomplete_action_is_ignored(self):
        self.assertIsNone(server._message_job({"type": "unknown"}))
        self.assertIsNone(self.job("feature", project="demo"))


class ChatSessionTests(unittest.TestCase):
    """A second message continues the first conversation, not a new one."""

    def setUp(self):
        server._SESSIONS.clear()
        self.addCleanup(server._SESSIONS.clear)

    def test_the_same_project_keeps_one_conversation(self):
        key = server._session_key("deepseek", False, "nextjs-mongo")
        self.assertEqual(key, server._session_key("deepseek", False, "nextjs-mongo"))

    def test_changing_the_model_is_a_different_conversation(self):
        """A transcript written under one model cannot be handed to another."""
        base = server._session_key("deepseek", False, "nextjs-mongo")
        self.assertNotEqual(base, server._session_key("qwen", False, "nextjs-mongo"))
        self.assertNotEqual(base, server._session_key("deepseek", True, "nextjs-mongo"))
        self.assertNotEqual(base, server._session_key("deepseek", False, "mern-microservices"))

    def test_forgetting_a_project_disposes_its_agent(self):
        disposed = []
        server._SESSIONS["demo"] = {
            "agent": types.SimpleNamespace(dispose=lambda: disposed.append(True)),
            "key": server._session_key("m", False, "s")}

        server.forget_session("demo")

        self.assertEqual(disposed, [True])
        self.assertNotIn("demo", server._SESSIONS)

    def test_forgetting_survives_an_agent_that_cannot_be_disposed(self):
        """A session that will not close must still be let go of."""
        def boom():
            raise RuntimeError("browser already gone")

        server._SESSIONS["demo"] = {"agent": types.SimpleNamespace(dispose=boom),
                                    "key": server._session_key("m", False, "s")}
        server.forget_session("demo")
        self.assertNotIn("demo", server._SESSIONS)

    def test_forgetting_a_project_nobody_was_talking_about_is_fine(self):
        server.forget_session("never-opened")
        self.assertEqual(server._SESSIONS, {})



if __name__ == "__main__":
    unittest.main()
