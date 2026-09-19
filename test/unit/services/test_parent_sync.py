import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from test._support import ROOT
import server_runtime as server
from server_modules.services.project_state import ProjectState, atomic_json
from srs_agent.app.sqlite_store import SQLiteStore


class ParentSyncTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "app"
        self.state = ProjectState(self.project)
        atomic_json(self.project / ".agentforge/srs/link.json", {"srs_id": "spec"})
        (self.project / ".agentforge/prototype").mkdir()
        (self.project / ".agentforge/prototype/index.html").write_text("<html>App</html>")
        self.state.agent("designer", status="completed", summary="Added a search screen")
        self.request = self.project / ".agentforge/requests/123.json"
        self.body = {"stage": "source_completed", "agent": "designer"}
        atomic_json(self.request, self.body)

    def test_first_prototype_updates_parent_without_starting_first_build(self):
        with patch.object(server, "_sync_parent_documents", return_value={"version": "1.1.0"}) as parent, patch.object(server, "run_chat") as sibling, patch.object(server, "emit"):
            server.synchronize_completed_change(self.project, self.request, self.body)
        self.assertEqual(parent.call_count, 1)
        sibling.assert_not_called()
        self.assertEqual(self.body["stage"], "complete")

    def test_unapproved_srs_cannot_be_adopted_for_design(self):
        from unittest.mock import Mock
        response = Mock()
        response.json.return_value = {"project": {"status": "generated"}}
        with patch.object(server, '_srs_get', return_value=response), patch.object(server, 'elog'):
            self.assertFalse(server.adopt_srs('spec', self.root / 'unapproved'))
        self.assertFalse((self.root / 'unapproved').exists())

    def test_recovery_waits_for_sidecar_startup_without_restarting_generation(self):
        from unittest.mock import Mock
        with patch.object(server, '_srs_get', side_effect=[None, Mock()]) as read, patch.dict(server.SRS_API, {'state': 'starting'}), patch.object(server, 'SERVER_STOPPING', False), patch.object(server.time, 'sleep'):
            self.assertTrue(server.wait_for_srs_startup())
        self.assertEqual(read.call_count, 2)

    def test_one_change_updates_sibling_then_parent_without_feedback_loop(self):
        (self.project / "package.json").write_text("{}")
        self.state.agent("developer", status="completed", completed_at=1)
        order = []
        def parent(*args):
            order.append(args[3])
            return {"version": "1.1.0"}
        def sibling(*args):
            order.append("developer")
            self.state.agent("developer", status="completed", summary="Implemented search")
        with patch.object(server, "_sync_parent_documents", side_effect=parent), patch.object(server, "run_chat", side_effect=sibling) as run, patch.object(server, "emit"):
            server.synchronize_completed_change(self.project, self.request, self.body)
            server.synchronize_completed_change(self.project, self.request, self.body)
        self.assertEqual(order, ["source", "developer", "mirror"])
        self.assertEqual(run.call_count, 1)

    def test_failed_sibling_retains_completed_parent_checkpoint(self):
        (self.project / "package.json").write_text("{}")
        self.state.agent("developer", status="completed", completed_at=1)
        with patch.object(server, "_sync_parent_documents", return_value={}), patch.object(server, "run_chat", side_effect=lambda *args: self.state.agent("developer", status="failed")), patch.object(server, "emit"):
            with self.assertRaisesRegex(RuntimeError, "did not complete"):
                server.synchronize_completed_change(self.project, self.request, self.body)
        self.assertEqual(json.loads(self.request.read_text())["stage"], "srs_updated")

    def test_builder_locked_until_prototype_completion(self):
        self.assertTrue(server.build_available(self.project))
        self.state.agent("designer", status="running")
        self.assertFalse(server.build_available(self.project))
        self.state.agent("designer", status="failed")
        self.assertFalse(server.build_available(self.project))

    def test_stopping_another_project_or_agent_does_not_cancel_active_work(self):
        with patch.object(server, 'acting', return_value={'id': 'owner'}), patch.object(server.RUN_QUEUE, 'leave', return_value=0), patch.object(server.RUN_QUEUE, 'active', return_value={'user': 'owner', 'project': 'alpha', 'agent': 'developer'}), patch.object(server.cancel, 'request') as cancel:
            self.assertEqual(server.cancel_mine('beta', 'developer')[1], 409)
            self.assertEqual(server.cancel_mine('alpha', 'designer')[1], 409)
        cancel.assert_not_called()

    def test_local_database_survives_reopen_with_project_boundaries(self):
        async def check():
            path = self.root / "store.sqlite3"
            store = SQLiteStore(path)
            await store.insert_one("projects", {"id": "a", "status": "interview"})
            await store.insert_one("projects", {"id": "b", "status": "generated"})
            await store.update_one("projects", {"id": "a"}, {"status": "approved"})
            await store.close()
            restored = SQLiteStore(path)
            self.assertEqual((await restored.find_one("projects", {"id": "a"}))["status"], "approved")
            self.assertEqual((await restored.find_one("projects", {"id": "b"}))["status"], "generated")
            await restored.close()
        asyncio.run(check())

    def test_srs_cancelled_job_retains_replay_request(self):
        from srs_agent import jobs
        from srs_agent.app.config import settings
        async def check():
            request = jobs.JobRequest(path="/projects/spec/generate-srs")
            jobs._JOBS["job_dead"] = {"status": "running", "request": request.model_dump()}
            with patch.object(settings, "storage_dir", str(self.root)), patch("httpx.AsyncClient.request", new=AsyncMock(side_effect=asyncio.CancelledError)):
                with self.assertRaises(asyncio.CancelledError):
                    await jobs._run("job_dead", request)
            self.assertIn("request", jobs._JOBS.pop("job_dead"))
        asyncio.run(check())


class CarriedChangeTests(unittest.TestCase):
    """What a completed change hands to the agent and the document after it.

    A summary says what somebody meant to do. The other half of a handoff is
    what was actually done - the files, and the pages those files draw - and
    none of it used to leave the run that made it. The builder was told "the
    prototype changed" and had to go and find out what that meant; the drawing
    of a screen was re-derived from prose that had never seen the screen.
    """

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "app"
        self.state = ProjectState(self.project)
        atomic_json(self.project / ".agentforge/srs/link.json", {"srs_id": "spec"})
        prototype = self.project / ".agentforge/prototype"
        prototype.mkdir(parents=True)
        (prototype / "index.html").write_text(
            "<html><head><title>Rooms</title></head><body>"
            "<header id='navbar'><a>Home</a></header>"
            "<main><h1>Our rooms</h1><a class='btn'>Book now</a></main></body></html>",
            encoding="utf-8")
        wireframes = self.project / ".agentforge/wireframes"
        wireframes.mkdir(parents=True)
        atomic_json(wireframes / "wireframes.json",
                    {"version": "1.2.0", "pages": [{"route": "/", "page_name": "Landing Page"}]})
        (self.project / "package.json").write_text("{}", encoding="utf-8")
        self.state.agent("designer", status="completed", summary="Moved the booking button")
        self.state.agent("developer", status="completed", completed_at=1)
        from server_modules.services import change_set
        self.change_set = change_set
        change_set.write(self.project, "designer", change_set.from_edit(
            ".agentforge/prototype/index.html", "<h1>Rooms</h1>\n", "<h1>Our rooms</h1>\n"))
        self.request = self.project / ".agentforge/requests/456.json"
        self.body = {"stage": "source_completed", "agent": "designer"}
        atomic_json(self.request, self.body)

    def run_change(self):
        """One transaction, with the sibling completing and the parent stubbed."""
        posted, briefs = [], []

        def parent(directory, request_path, request, label, role, summary, pages=()):
            posted.append({"label": label, "role": role, "summary": summary,
                           "pages": list(pages)})
            return {"version": "1.3.0"}

        def sibling(project, instruction, *args):
            briefs.append(instruction)
            self.state.agent("developer", status="completed",
                             summary="Moved it in the build too")

        with patch.object(server, "_sync_parent_documents", side_effect=parent), \
                patch.object(server, "run_chat", side_effect=sibling), \
                patch.object(server, "emit"):
            server.synchronize_completed_change(self.project, self.request, self.body)
        return posted, briefs

    def test_the_builder_is_shown_the_files_and_not_only_the_sentence(self):
        _posted, briefs = self.run_change()
        self.assertEqual(len(briefs), 1)
        self.assertIn("Moved the booking button", briefs[0])
        self.assertIn(".agentforge/prototype/index.html (modified)", briefs[0])
        self.assertIn("+<h1>Our rooms</h1>", briefs[0])

    def test_the_page_that_changed_travels_to_the_document_as_its_structure(self):
        posted, _briefs = self.run_change()
        source = next(row for row in posted if row["label"] == "source")
        self.assertEqual([page["route"] for page in source["pages"]], ["/"])
        outline = source["pages"][0]["outline"]
        self.assertIn('h1 "Our rooms"', outline)
        self.assertIn("header#navbar", outline)

    def test_a_build_reports_no_pages_because_it_draws_none(self):
        self.body["agent"] = "developer"
        atomic_json(self.request, self.body)
        self.state.agent("developer", status="completed", summary="Wired the booking form")
        posted, _briefs = self.run_change()
        source = next(row for row in posted if row["label"] == "source")
        self.assertEqual(source["pages"], [])

    def test_the_change_is_not_carried_into_the_next_transaction(self):
        self.run_change()
        self.assertEqual(self.change_set.read(self.project, "designer"), {})
        self.assertEqual(self.change_set.read(self.project, "developer"), {})


class AdoptionTests(unittest.TestCase):
    """Taking a copy of the drawings only once there are new ones to take.

    A page is a model call, so a saved version schedules its drawings and
    returns before any of them exist. Adopting at that moment copies the
    previous version's pages - which is how a project ends up nine versions on
    with its wireframes still stamped with the version before last.
    """

    def _answers(self, *flags):
        replies = []
        for drawing in flags:
            reply = Mock()
            reply.json.return_value = {"drawing": drawing}
            reply.raise_for_status.return_value = None
            replies.append(reply)
        return replies

    def test_adoption_waits_while_the_pages_are_still_being_drawn(self):
        with patch.object(server.requests, "get",
                          side_effect=self._answers(True, True, False)) as asked, \
                patch.object(server.time, "sleep") as waited:
            server._drawings_settled("spec")
        self.assertEqual(asked.call_count, 3)
        self.assertEqual(waited.call_count, 2)

    def test_nothing_being_drawn_is_not_waited_for(self):
        with patch.object(server.requests, "get", side_effect=self._answers(False)), \
                patch.object(server.time, "sleep") as waited:
            server._drawings_settled("spec")
        waited.assert_not_called()

    def test_an_srs_that_cannot_answer_does_not_hold_up_the_change(self):
        """The pages already on disk are what the studio would have shown anyway."""
        import requests as http
        with patch.object(server.requests, "get", side_effect=http.RequestException("down")), \
                patch.object(server.time, "sleep") as waited:
            server._drawings_settled("spec")
        waited.assert_not_called()
