"""Focused contracts for the compact server action helpers."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
