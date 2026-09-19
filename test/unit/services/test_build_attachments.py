"""What the user attached, and the build that has to read it.

The home screen has always taken a PDF or a picture, and only the
specification agent could read one: pressing Build dropped them, so a request
that said "the menu is in this PDF" was built from a sentence with no menu in
it. These cover the two halves of the fix - the files travel over HTTP rather
than in the build message, and they are read once there is a project to read
them into.
"""
from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path

from test import _support  # noqa: F401
import server_runtime as server


def b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


class StagedAttachmentTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.project = self.root / "menus"
        self.project.mkdir()
        self._saved = server.PROD_DIR
        server.PROD_DIR = self.root

    def tearDown(self):
        server.PROD_DIR = self._saved

    def stage(self, token="tok", name="menu.txt", body="Soup 4.50", purpose=""):
        return server.stage_attachment(token, name, b64(body), purpose)

    def test_a_staged_file_is_read_into_the_brief(self):
        self.assertTrue(self.stage().get("ok"))
        block = server.read_staged_attachments("tok", self.project)
        self.assertIn("menu.txt", block)
        self.assertIn("Soup 4.50", block)
        self.assertIn("attached", block.lower())

    def test_what_the_user_said_it_is_for_travels_with_it(self):
        self.stage(purpose="these are the real prices")
        block = server.read_staged_attachments("tok", self.project)
        self.assertIn("these are the real prices", block)

    def test_the_stage_is_emptied_once_the_build_has_read_it(self):
        self.stage()
        stage = self.root / server.STAGE_ROOT / "tok"
        self.assertTrue(stage.is_dir())
        server.read_staged_attachments("tok", self.project)
        self.assertFalse(stage.exists())

    def test_a_build_with_nothing_staged_gets_nothing_and_does_not_fail(self):
        self.assertEqual(server.read_staged_attachments("", self.project), "")
        self.assertEqual(server.read_staged_attachments("never-used", self.project), "")

    def test_an_empty_or_unreadable_upload_is_refused_rather_than_stored(self):
        self.assertIn("error", server.stage_attachment("tok", "empty.txt", ""))
        self.assertIn("error", server.stage_attachment("tok", "bad.txt", "!!!not base64"))
        self.assertIn("error", server.stage_attachment("", "menu.txt", b64("x")))

    def test_neither_the_token_nor_the_filename_can_leave_the_staging_root(self):
        self.assertTrue(server.stage_attachment(
            "../../evil", "../../../boom.txt", b64("x")).get("ok"))
        inside = self.root / server.STAGE_ROOT
        written = [p for p in inside.rglob("*") if p.is_file()]
        self.assertEqual([p.name for p in written], ["boom.txt"])
        for path in written:
            path.relative_to(inside)          # raises if it escaped

    def test_the_build_message_carries_the_token_and_never_the_bytes(self):
        """A frame this size is refused by the socket, so it must not go there."""
        job = server._message_job({
            "type": "agent_build", "prompt": "a cafe site",
            "attachments": "tok", "model": "m",
        })
        self.assertIsNotNone(job)
        function, arguments = job
        self.assertIs(function, server.run_agent_pipeline)
        self.assertIn("tok", arguments)
        self.assertNotIn(b64("Soup 4.50"), json.dumps(arguments))


class SpecificationOnlyProjectTests(unittest.TestCase):
    """A specification kept without building it, told apart from an app."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self._saved = server.PROD_DIR
        server.PROD_DIR = self.root

    def tearDown(self):
        server.PROD_DIR = self._saved

    def project(self, *, srs=True, manifest=False, source=False) -> Path:
        proj = self.root / "cafe"
        proj.mkdir(exist_ok=True)
        if srs:
            (proj / ".agentforge" / "srs").mkdir(parents=True, exist_ok=True)
            (proj / ".agentforge" / "srs" / "srs_latest.json").write_text("{}", encoding="utf-8")
        if manifest:
            (proj / "package.json").write_text('{"name":"cafe"}', encoding="utf-8")
        if source:
            (proj / "app").mkdir(exist_ok=True)
            (proj / "app" / "page.jsx").write_text("export default () => null", encoding="utf-8")
        return proj

    def test_a_specification_with_nothing_built_is_one(self):
        self.assertTrue(server._spec_only(self.project()))

    def test_a_manifest_means_a_build_happened(self):
        self.assertFalse(server._spec_only(self.project(manifest=True)))

    def test_a_single_source_file_means_a_build_happened(self):
        self.assertFalse(server._spec_only(self.project(source=True)))

    def test_a_project_that_never_had_a_specification_is_not_one(self):
        self.assertFalse(server._spec_only(self.project(srs=False)))

    def test_the_listing_says_which_projects_are_specifications(self):
        self.project()
        rows = {row["name"]: row for row in server.list_projects()}
        self.assertIn("cafe", rows)
        self.assertTrue(rows["cafe"]["spec_only"])
