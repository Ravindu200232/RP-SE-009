"""Long builds must checkpoint safely and avoid rerunning unchanged suites."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from test import _support  # noqa: F401
from builder_agent.compactor import Compactor
from builder_agent.context import ContextBudget
from builder_agent.events import Events
from builder_agent.llm import Reply
from builder_agent.memory import Memory
from qa_agent.evidence import Evidence
from qa_agent.journeys import run_journey, run_journeys
from builder_agent.sandbox import Sandbox
from qa_agent.tools.verify import run_tests


class BoundedVerificationTests(unittest.TestCase):
    def test_failed_summary_still_preserves_task_and_archives_history(self):
        memory = Memory(); memory.set_system('developer'); memory.set_task('preserve the project')
        memory.add_assistant('large previous turn ' * 30000)
        budget = ContextBudget(8192, 2048)
        router = Mock(); router.ask.side_effect = RuntimeError('context too long')
        self.assertTrue(Compactor(memory, budget, router, Events()).compact(force=True)['compacted'])
        self.assertIn('preserve the project', str(memory.build()))
        self.assertIn('large previous turn', memory.archive)
        self.assertFalse(budget.measure(memory.build()).should_compact)

    def test_browser_batch_continues_after_failure_and_reuses_identical_pass(self):
        page = Mock(); page.url = 'http://localhost/'; page.diagnostics = []
        page.text.return_value = 'Ready'
        driver = SimpleNamespace(page=lambda _: page, fresh_session=Mock())
        evidence = Evidence()
        specs = [{'suite':'failed','steps':[{'type':'textIncludes','expected':'Missing','timeoutMs':100}]},
                 {'suite':'passed','steps':[{'type':'textIncludes','expected':'Ready'}]}]
        result = run_journeys(driver, None, evidence, suites=specs)
        self.assertFalse(result['ok']); self.assertIn('1 passed, 1 failed', result['content'])
        before = driver.fresh_session.call_count
        run_journey(driver, None, evidence, suite='passed', covers=[], steps=specs[1]['steps'])
        self.assertEqual(driver.fresh_session.call_count, before)
        evidence.changed()
        run_journey(driver, None, evidence, suite='passed', covers=[], steps=specs[1]['steps'])
        self.assertEqual(driver.fresh_session.call_count, before + 1)

    def test_screenshot_does_not_inherit_non_visual_requirement(self):
        with tempfile.TemporaryDirectory() as folder:
            evidence = Evidence()
            evidence.define_scope('web', 'mern', [{'id':'booking','description':'booking','evidence':['e2e']}])
            page = Mock(); page.url = 'http://localhost/'; page.diagnostics = []
            driver = SimpleNamespace(page=lambda _: page, fresh_session=Mock())
            self.assertTrue(run_journey(driver, Sandbox(Path(folder)), evidence, suite='booking', covers=['booking'],
                                        steps=[{'action':'screenshot','view':'booking'}])['ok'])
            self.assertEqual(evidence.visuals[0]['covers'], [])

    def test_oversized_history_is_not_sent_to_summary_provider(self):
        memory = Memory()
        memory.set_system('developer')
        memory.set_task('finish the existing build')
        memory.add_assistant('error details ' * 15000)
        budget = ContextBudget(8192, 2048)
        router = Mock()
        def ask(messages, **kwargs):
            self.assertLess(budget.measure(messages).prompt_tokens, budget.limit // 2)
            return Reply(content='Continue repairing the existing build.')
        router.ask.side_effect = ask
        self.assertTrue(Compactor(memory, budget, router, Events()).compact(force=True)['compacted'])

    def test_passing_shell_suite_reused_until_source_revision_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            memory = Memory(evidence=Evidence())
            memory.evidence.define_scope('web', 'mern', [
                {'id': 'booking', 'description': 'booking', 'evidence': ['unit']}])
            processes = Mock()
            processes.run.return_value = {'exitCode': 0, 'elapsed': 0.01}
            ctx = SimpleNamespace(memory=memory, sandbox=Sandbox(Path(folder)),
                                  events=Events(), processes=processes)
            args = {'kind': 'unit', 'suite': 'client', 'command': 'npm test', 'covers': ['booking']}
            self.assertTrue(run_tests(args, ctx)['ok'])
            self.assertTrue(run_tests(args, ctx)['ok'])
            self.assertEqual(processes.run.call_count, 1)
            memory.evidence.changed()
            run_tests(args, ctx)
            self.assertEqual(processes.run.call_count, 2)
