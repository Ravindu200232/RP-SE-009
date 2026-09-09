"""Follow-up features must receive the preceding build's actual transcript."""
import tempfile
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import server_runtime as server
from builder_agent.agent import BuilderAgent
from builder_agent.llm import Router


class ConversationContinuityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.project = self.root / "shop"
        self.project.mkdir()
        self.start_patch(patch.object(server, "PROD_DIR", self.root))
        self.start_patch(patch.object(server, "_SESSIONS", {}))
        self.start_patch(patch.object(Router, "context_window", return_value=128_000))
        self.start_patch(patch.object(server, "StudioBridge"))
        self.start_patch(patch.object(server.qa_report, "LiveReport"))
        self.start_patch(patch.object(BuilderAgent, "run", autospec=True, side_effect=self.reply))
        self.start_patch(patch.object(BuilderAgent, "build", autospec=True, side_effect=self.reply))
        self.inputs = []

    def start_patch(self, patcher):
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def reply(self, agent, prompt):
        agent.memory.set_task(prompt)
        self.inputs.append(agent.memory.build())
        agent.memory.add_assistant("Implemented the existing account page in client/src/Account.jsx.")
        return SimpleNamespace(status="completed",
                               result="Implemented the existing account page in client/src/Account.jsx.")

    def run_request(self, prompt, *, plan=False):
        return server._run_agent(self.project, prompt, "test-model", False,
            kind="build" if plan else "edit", phases=server.EDIT_PHASES,
            plan=plan, stack="mern-microservices")[0]

    def assert_remembers(self):
        text = str(self.inputs[-1])
        self.assertIn("Build a shop with customer accounts", text)
        self.assertIn("client/src/Account.jsx", text)
        self.assertIn("Add a signup link to that page", text)

    def test_first_feature_keeps_the_build_transcript(self):
        self.run_request("Build a shop with customer accounts", plan=True)
        self.run_request("Add a signup link to that page")
        self.assert_remembers()

    def test_completed_reply_reaches_the_project_chat(self):
        with patch.object(server, "emit") as emit:
            self.run_request("Add a signup link to that page")
        replies = [call.args[0] for call in emit.call_args_list
                   if call.args[0].get("type") == "agent_msg"]
        self.assertIn({"type": "agent_msg", "text":
                       "Implemented the existing account page in client/src/Account.jsx."}, replies)

    def test_backend_restart_restores_the_actual_transcript(self):
        self.run_request("Build a shop with customer accounts")
        server._SESSIONS.clear()  # A new backend has no live agent objects.
        self.run_request("Add a signup link to that page")
        self.assert_remembers()

    def test_older_projects_recover_saved_chat_without_inventing_tool_evidence(self):
        path = self.project / server.STREAM_FILE
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'chat': [
            {'role': 'user', 'text': 'Build a shop with customer accounts'},
            {'role': 'assistant', 'text': 'Implemented client/src/Account.jsx.'},
        ]}), encoding='utf-8')
        agent = self.run_request('Add a signup link to that page')
        self.assert_remembers()
        self.assertIn('partial history', str(self.inputs[-1]))
        self.assertEqual(agent.memory.evidence.suites, [])

    def test_opening_the_preview_keeps_the_conversation(self):
        self.run_request("Build a shop with customer accounts")
        with patch.object(server, "working_on"), patch.object(server, "free_declared_ports", return_value=[]), \
                patch.object(server.MONGO, "ensure_running"), \
                patch.object(server, "ensure_node_deps", return_value=True), \
                patch.object(server, "start_dev_server"), patch.object(server, "wait_for_dev", return_value=True), \
                patch.object(server, "edone"):
            server._open_project("shop")
        self.run_request("Add a signup link to that page")
        self.assert_remembers()

    def test_switching_projects_restores_the_right_history(self):
        self.run_request("Build a shop with customer accounts")
        server.release_other_sessions("another-project")
        self.run_request("Add a signup link to that page")
        self.assert_remembers()

    def test_explicit_new_build_starts_its_own_conversation(self):
        self.run_request("Build a shop with customer accounts")
        self.run_request("Start a different full build", plan=True)
        self.assertNotIn("Build a shop with customer accounts", str(self.inputs[-1]))

    def test_restart_preserves_compaction_design_and_usage(self):
        agent = self.run_request("Build a shop with customer accounts")
        agent.memory.replace_history("Account page is in client/src/Account.jsx")
        agent.memory.archive = "Older detailed observations"
        agent.design = {"selection": {"palette": "orange"}}
        agent.router.usage.update({"requests": 12, "prompt": 12345, "completion": 678})
        server.save_conversation(self.project, agent)
        server._SESSIONS.clear()
        restored = self.run_request("Add a signup link to that page")
        self.assertEqual(restored.memory.compactions, 1)
        self.assertEqual(restored.memory.archive, "Older detailed observations")
        self.assertEqual(restored.design, agent.design)
        self.assertEqual(restored.router.usage, agent.router.usage)
        self.assert_remembers()

    def test_failed_save_leaves_the_previous_transcript_intact(self):
        agent = self.run_request("Build a shop with customer accounts")
        path = self.project / server.CONVERSATION_FILE
        original = path.read_text(encoding="utf-8")
        agent.memory.add_user("newer request")
        with patch.object(Path, "replace", side_effect=OSError("disk busy")), patch.object(server, "elog"):
            server.save_conversation(self.project, agent)
        self.assertEqual(path.read_text(encoding="utf-8"), original)
        self.assertEqual(list(path.parent.glob("conversation-*.tmp")), [])

    def test_saved_conversation_cannot_cross_project_boundaries(self):
        self.run_request("Build a shop with customer accounts")
        path = self.project / server.CONVERSATION_FILE
        saved = json.loads(path.read_text(encoding="utf-8"))
        saved["workspace"] = str(self.root / "another-project")
        path.write_text(json.dumps(saved), encoding="utf-8")
        server._SESSIONS.clear()
        self.run_request("Add a signup link to that page")
        self.assertNotIn("Build a shop with customer accounts", str(self.inputs[-1]))
