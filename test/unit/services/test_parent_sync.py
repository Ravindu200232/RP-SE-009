import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

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
