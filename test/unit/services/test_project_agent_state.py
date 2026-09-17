import json
import tempfile
import unittest
from pathlib import Path

from server_modules.services.project_state import ProjectState, atomic_json
from test._support import ROOT

import sys
sys.path.insert(0, str(ROOT / 'builder-agent'))
sys.path.insert(0, str(ROOT / 'srs-agent'))
from srs_agent.app.generators.agent_handoff import FILES, write_handoff
from builder_agent.sandbox import Sandbox
from builder_agent.errors import SecurityError


class ProjectAgentStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_restart_detects_interrupted_run_and_keeps_each_context(self):
        a, b = ProjectState(self.root / 'a'), ProjectState(self.root / 'b')
        a.start('designer', {'prompt': 'make the navigation blue'})
        a.start('developer', {'prompt': 'implement search'})
        a.record({'type': 'agent_msg', 'project': 'a', 'agent': 'designer', 'text': 'design context'})
        b.record({'type': 'agent_msg', 'project': 'b', 'agent': 'developer', 'text': 'other project'})
        raw = a.read()
        raw['agents']['designer']['server_id'] = 'previous process'
        atomic_json(a.path, raw)
        restored = ProjectState(self.root / 'a').snapshot()
        self.assertEqual(restored['agents']['designer']['status'], 'interrupted')
        self.assertEqual(restored['agents']['developer']['status'], 'running')
        self.assertEqual(restored['events']['designer'][0]['text'], 'design context')
        self.assertEqual(restored['events']['developer'], [])
        self.assertNotIn('other project', json.dumps(restored))

    def test_scoped_files_refuse_wrong_agent_secrets_and_handoff_writes(self):
        designer = Sandbox(self.root, role='designer')
        developer = Sandbox(self.root, role='developer')
        for role in (designer, developer):
            role.resolve('.agentforge/handoff/app.md')
            with self.assertRaises(SecurityError):
                role.check_access(self.root / '.agentforge/handoff/app.md', write=True)
            with self.assertRaises(SecurityError):
                role.resolve('../outside.md')
            with self.assertRaises(SecurityError):
                role.resolve('.env.local')
        designer.check_access(self.root / '.agentforge/prototype/index.html', write=True)
        developer.check_access(self.root / 'app/page.jsx', write=True)
        with self.assertRaises(SecurityError):
            designer.resolve('app/page.jsx')
        with self.assertRaises(SecurityError):
            developer.check_access(self.root / '.agentforge/prototype/index.html', write=True)
        with self.assertRaises(SecurityError):
            designer.resolve('.agentforge/agents/developer/conversation.json')
        # Skills: designer can read theme/system skills, but cannot write them
        designer.check_access(self.root / '.agents/skills/design-theme/SKILL.md', write=False)
        designer.check_access(self.root / '.agent/skills/design-theme/SKILL.md', write=False)
        with self.assertRaises(SecurityError):
            designer.check_access(self.root / '.agents/skills/design-theme/SKILL.md', write=True)

    def test_queued_run_belongs_to_current_server(self):
        state = ProjectState(self.root)
        state.agent('designer', status='queued')
        self.assertEqual(state.read()['agents']['designer']['status'], 'queued')

    def test_prototype_undo_only_restores_prototype(self):
        import server_runtime as server
        from unittest.mock import patch
        project = self.root / 'app'
        prototype = project / '.agentforge/prototype/index.html'
        prototype.parent.mkdir(parents=True)
        prototype.write_text('<h1>Before</h1>', encoding='utf-8')
        app = project / 'page.jsx'
        app.write_text('Before build', encoding='utf-8')
        with patch.object(server, 'PROD_DIR', self.root), patch.object(server, '_owned_dir', return_value=('app', project, '')), patch.object(server, 'emit'):
            snapshot = server.snapshot_project(project, 'designer')
            prototype.write_text('<h1>After</h1>', encoding='utf-8')
            app.write_text('Changed build', encoding='utf-8')
            server.restore_snapshot('app', snapshot['id'])
        self.assertEqual(prototype.read_text(), '<h1>Before</h1>')
        self.assertEqual(app.read_text(), 'Changed build')

    def test_handoff_keeps_full_srs_and_selected_stack_without_replanning(self):
        spec = self.root / '.agentforge/srs/srs_latest.json'
        atomic_json(spec, {'project_name': 'Observatory', 'screens': [{'route': '/observations', 'purpose': 'Record observations'}],
                           'requirements': [{'id': 'R-200', 'text': 'Retain observations for ten years'}]})
        target = write_handoff(self.root / 'handoff', json.loads(spec.read_text()), stack='mern-microservices')
        self.assertEqual(set(FILES), {p.name for p in target.glob('*.md')})
        self.assertIn('R-200', (target / 'app.md').read_text())
        self.assertIn('/observations', (target / 'sitemap.md').read_text())
        self.assertIn('Express microservices', (target / 'builder.md').read_text())
        self.assertIn('HTML', (target / 'prototype.md').read_text())
        before = (target / 'app.md').stat().st_mtime_ns
        write_handoff(target, json.loads(spec.read_text()), stack='mern-microservices')
        self.assertEqual(before, (target / 'app.md').stat().st_mtime_ns)


if __name__ == '__main__':
    unittest.main()
