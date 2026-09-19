"""Parent documents follow completed changes and survive interrupted publication."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from test import _support
from srs_agent.app import db
from srs_agent.app.config import settings
from srs_agent.app.models import repositories as repo
from srs_agent.app.schemas.srs import validate_srs
from srs_agent.app.services import orchestrator, parent_sync, storage, integrations
from srs_agent.app.generators.agent_handoff import FILES


def specification():
    return validate_srs({"srs_document": {
        "project_name": "Observatory", "system_category": "Custom",
        "app_summary": {"app_name": "Observatory", "short_description": "Record observations", "business_goal": "Preserve research"},
        "app_type": {"primary_type": "Web app"}, "database_design": {},
        "roles": [{"role_key": "researcher", "role_name": "Researcher", "description": "Record observations"}],
        "functional_requirements": [{"id": f"FR-{i}", "module": "Observations", "requirement": text} for i, text in enumerate(
            ["Create observations", "Read observations", "Edit observations"], 1)],
        "non_functional_requirements": [{"id": f"NFR-{i}", "category": "Quality", "requirement": text} for i, text in enumerate(
            ["Keyboard access", "Save records durably", "Responsive screens"], 1)],
        "public_pages": [{"page_name": "Observations", "route": "/observations"}],
        "approved_plan": {"features": ["OLD feature"], "look_and_feel": "OLD design"},
    }}).model_dump()


class ParentDocumentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for patcher in (patch.object(settings, "storage_dir", str(self.root)), patch.object(db, "_store", db.MemoryStore())):
            patcher.start()
            self.addCleanup(patcher.stop)
        await repo.create_project({"id": "spec", "title": "Observatory", "stack": "mern-microservices", "status": "approved",
            "raw_idea": "Record observations", "integrations": [{"id": "notifications", "provider": "smtp", "configured": ["SMTP_PASSWORD"]}]})

    async def seed_version(self):
        await repo.save_version({"id": "v1", "project_id": "spec", "version": "1.0.0", "created_at": "2000-01-01", "srs": specification()})

    async def test_generation_publishes_four_handoffs_before_srs_approval(self):
        async def generate(state):
            self.assertIn("SMTP_PASSWORD", state["brief"])
            self.assertIn("mern-microservices", state["brief"])
            return {"srs": specification()}
        with patch.object(orchestrator, "run_generation", side_effect=generate), patch.object(orchestrator.plan_approval, "approved_plan", new=AsyncMock(return_value={"plan": {}})):
            result = await orchestrator.generate_srs("spec")
        self.assertEqual(result["project"]["status"], "generated")
        self.assertEqual(set(FILES), {p.name for p in (self.root / "spec/handoff").glob("*.md")})
        self.assertIn("Express microservices", (self.root / "spec/handoff/builder.md").read_text(encoding="utf-8"))

    async def test_child_change_updates_all_documents_once_and_resumes_after_pdf_failure(self):
        await self.seed_version()
        async def compare(**kwargs):
            result = {"srs_document": {"public_pages": [{"page_name": "Observations", "route": "/observations"}, {"page_name": "Search", "route": "/search"}],
                "ui_ux_requirements": {"theme": "blue"}}, "diff_summary": ["Added search with blue styling"]}
            kwargs["validator"](result)
            return result
        llm = Mock(complete_json=AsyncMock(side_effect=compare))
        async def diagrams(label, state, nodes):
            return state
        with patch.object(parent_sync, "get_llm", return_value=llm), patch("srs_agent.app.graph.workflow._checkpointed", side_effect=diagrams), patch.object(parent_sync, "generate_pdf", new=AsyncMock(side_effect=[OSError("disk busy"), None])) as pdf:
            with self.assertRaisesRegex(OSError, "disk busy"):
                await parent_sync.synchronize("spec", "change1", "designer", "Added search with blue styling")
            result = await parent_sync.synchronize("spec", "change1", "designer", "Added search with blue styling")
            again = await parent_sync.synchronize("spec", "change1", "designer", "Added search with blue styling")
        self.assertEqual(result, again)
        self.assertEqual(llm.complete_json.await_count, 1)
        self.assertEqual(pdf.await_count, 2)
        self.assertEqual(len(await repo.list_versions("spec")), 2)
        latest = await repo.latest_version("spec")
        self.assertEqual(latest["version"], "1.1.0")
        self.assertNotIn("OLD", json.dumps(latest["srs"]))
        for name in ("app.md", "sitemap.md"):
            self.assertIn("/search", (self.root / "spec/handoff" / name).read_text(encoding="utf-8"))
        self.assertIn("blue", (self.root / "spec/handoff/prototype.md").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((self.root / "spec/srs_latest.json").read_text(encoding="utf-8")), latest["srs"])

    async def test_interview_credentials_stay_out_of_metadata_and_prompts(self):
        catalog = [{"id": kind, "choices": [{"id": "yes", "label": "Enabled", "fields": [{"key": f"TEST_SECRET_{i}"}]}]}
                   for i, kind in enumerate(integrations.KINDS)]
        with patch.object(integrations, "questions", return_value=catalog):
            answers = [{"id": item["id"], "choice": "yes", "values": {f"TEST_SECRET_{i}": "secret#value"}} for i, item in enumerate(catalog)]
            metadata = integrations.save("spec", answers)
            restored = integrations.save("spec", [{**a, "values": {}} for a in answers])
        self.assertEqual(metadata, restored)
        self.assertNotIn("secret#value", json.dumps(metadata))
        self.assertIn('"secret#value"', (self.root / "spec/.env.local").read_text(encoding="utf-8"))
        await repo.update_project("spec", {"integrations": metadata})
        self.assertNotIn("secret#value", await orchestrator._brief_for(await repo.get_project("spec")))

    async def test_no_requirement_change_keeps_one_version_and_consistent_projections(self):
        await self.seed_version()
        llm = Mock(complete_json=AsyncMock(return_value={"srs_document": {}, "diff_summary": []}))
        with patch.object(parent_sync, "get_llm", return_value=llm), patch.object(parent_sync, "generate_pdf", new=AsyncMock()):
            result = await parent_sync.synchronize('spec', 'nochange', 'developer', 'Verified the existing implementation')
        self.assertEqual(result['version'], '1.0.0')
        self.assertEqual(result['diff_summary'], [])
        self.assertEqual(len(await repo.list_versions('spec')), 1)
        latest = await repo.latest_version('spec')
        self.assertEqual(json.loads((self.root / 'spec/srs_latest.json').read_text(encoding='utf-8')), latest['srs'])
        self.assertNotIn('OLD', json.dumps(latest['srs']))


class RevisionLabelTests(unittest.IsolatedAsyncioTestCase):
    """What a revision row says it was.

    "developer update" named who reported the change and nothing about the
    change, and the model had already written a usable sentence and a list of
    the actual edits - both saved, neither shown. So the label is the sentence,
    the bullets are rendered under it, and the old wording survives only for a
    revision the model described in neither form.
    """

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for patcher in (patch.object(settings, "storage_dir", str(self.root)),
                        patch.object(db, "_store", db.MemoryStore())):
            patcher.start()
            self.addCleanup(patcher.stop)
        await repo.create_project({"id": "spec", "title": "Observatory",
                                   "stack": "mern-microservices", "status": "approved",
                                   "raw_idea": "Record observations"})
        await repo.save_version({"id": "v1", "project_id": "spec", "version": "1.0.0",
                                 "created_at": "2000-01-01", "srs": specification()})

    async def label_for(self, answer, change_id):
        async def compare(**kwargs):
            kwargs["validator"](answer)
            return answer
        llm = Mock(complete_json=AsyncMock(side_effect=compare))

        async def diagrams(label, state, nodes):
            return state
        with patch.object(parent_sync, "get_llm", return_value=llm), \
             patch("srs_agent.app.graph.workflow._checkpointed", side_effect=diagrams), \
             patch.object(parent_sync, "generate_pdf", new=AsyncMock()):
            await parent_sync.synchronize("spec", change_id, "developer", "did a thing")
        return (await repo.latest_version("spec"))

    CHANGE = {"public_pages": [{"page_name": "Observations", "route": "/observations"},
                               {"page_name": "Search", "route": "/search"}]}

    async def test_the_label_is_what_the_model_said_happened(self):
        row = await self.label_for(
            {"srs_document": self.CHANGE, "diff_summary": ["Added a search page"],
             "headline": "Observations can now be searched"}, "c1")
        self.assertEqual(row["label"], "Observations can now be searched")
        self.assertEqual(row["diff_summary"], ["Added a search page"])
        self.assertEqual(row["source"], "developer")

    async def test_without_a_headline_the_first_real_change_is_the_label(self):
        row = await self.label_for(
            {"srs_document": self.CHANGE, "diff_summary": ["Added a search page"]}, "c2")
        self.assertEqual(row["label"], "Added a search page")

    async def test_a_revision_described_in_neither_form_still_says_something(self):
        row = await self.label_for({"srs_document": self.CHANGE}, "c3")
        self.assertEqual(row["label"], "developer update")

    async def test_a_headline_is_one_line_however_it_arrives(self):
        """A paragraph in a list row is a paragraph nobody reads."""
        row = await self.label_for(
            {"srs_document": self.CHANGE, "diff_summary": ["x"],
             "headline": "  Observations\ncan now\tbe searched  " + "y" * 200}, "c4")
        self.assertNotIn("\n", row["label"])
        self.assertLessEqual(len(row["label"]), 90)
        self.assertTrue(row["label"].startswith("Observations can now be searched"))
