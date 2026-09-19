import json
import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'deployment-agent' / 'deploy_agent'))
from deployment_agent.dependency_audit import audit_dependencies, dependency_command, parse_report
from deployment_agent.models import DeploymentTarget, ProjectSpec, RepositorySpec, ServiceSpec
from deployment_agent.orchestrator import Orchestrator
from deployment_agent.repair import DeploymentRepairAgent
from deployment_agent.security import sha256_file
from deployment_agent.state import StateStore


class DependencyAuditTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'package.json').write_text(json.dumps({'name': 'app', 'packageManager': 'npm@11.0.0'}))

    @staticmethod
    def report(total=7):
        return json.dumps({'metadata': {'vulnerabilities': {'low': 0, 'moderate': 4 if total else 0,
                           'high': 2 if total else 0, 'critical': 1 if total else 0, 'total': total}},
                           'vulnerabilities': {'example': {'severity': 'critical', 'range': '<2.0.1',
                                                         'fixAvailable': {'name': 'example', 'version': '2.0.1'}}} if total else {}})

    def test_build_passes_but_full_audit_findings_are_retained_for_repair(self):
        calls = []
        def command(argv, **kwargs):
            calls.append((argv, kwargs))
            if argv == ['npm', 'audit', '--json']:
                return CompletedProcess(argv, 1, self.report(), '')
            return CompletedProcess(argv, 0, '7 vulnerabilities (4 moderate, 2 high, 1 critical)', '')
        service = ServiceSpec('app', '', 'node', '', 'npm', 'npm ci', 'npm run build', 'npm start')
        spec = ProjectSpec('app', str(self.root), str(self.root), [service], RepositorySpec(False))
        with patch('deployment_agent.orchestrator.command_exists', return_value=True), \
             patch('deployment_agent.orchestrator.run_command', side_effect=command):
            result = Orchestrator(Mock(), Mock())._validate_build('run', spec, self.root, DeploymentTarget.AWS_EC2)
        self.assertTrue(result['passed'])
        self.assertFalse(result['dependency_audit']['passed'])
        self.assertEqual(result['dependency_findings']['total'], 7)
        self.assertIn('2.0.1', result['dependency_audit']['output'])
        self.assertTrue(all(call[1]['authenticated'] is False for call in calls))

    def test_registry_failure_cannot_look_like_a_clean_audit(self):
        runner = Mock(return_value=CompletedProcess([], 1, 'registry unreachable', ''))
        result = audit_dependencies(self.root, 'npm', runner)
        self.assertFalse(result['passed'])

    def test_clean_json_audit_is_verified(self):
        runner = Mock(return_value=CompletedProcess([], 0, self.report(0), ''))
        result = audit_dependencies(self.root, 'npm', runner)
        self.assertTrue(result['passed'])
        self.assertEqual(result['findings']['total'], 0)

    def test_yarn_classic_advisory_stream_summary(self):
        output = '\n'.join(json.dumps(value) for value in [
            {'type': 'auditAdvisory', 'data': {'advisory': {'id': 1, 'module_name': 'dep', 'severity': 'high'}}},
            {'type': 'auditSummary', 'data': {'vulnerabilities': {'info': 0, 'low': 0, 'moderate': 0, 'high': 1, 'critical': 0}}},
        ])
        counts, recognized = parse_report(output)
        self.assertTrue(recognized)
        self.assertEqual(counts['total'], 1)

    def test_package_manager_audit_matches_project(self):
        self.assertEqual(dependency_command(self.root, 'pnpm'), ['pnpm', 'audit', '--json'])
        self.assertEqual(dependency_command(self.root, 'bun'), ['bun', 'audit', '--json'])
        self.assertEqual(dependency_command(self.root, 'yarn'), ['yarn', 'audit', '--json'])
        (self.root / 'package.json').write_text(json.dumps({'packageManager': 'yarn@4.0.0'}))
        self.assertEqual(dependency_command(self.root, 'yarn'), ['yarn', 'npm', 'audit', '--all', '--recursive', '--json'])

    def test_lock_refresh_is_recorded_as_an_owned_repair_with_original_hash(self):
        lock = self.root / 'package-lock.json'
        lock.write_text('{"version": 1}')
        original_hash = sha256_file(lock)
        agent = DeploymentRepairAgent(Mock(), Mock(), client=Mock())
        def command(argv, **kwargs):
            self.assertIn('--ignore-scripts', argv)
            self.assertFalse(kwargs['authenticated'])
            lock.write_text('{"version": 2}')
            return CompletedProcess(argv, 0, '', '')
        run = {'spec': {'services': [{'root': '', 'package_manager': 'npm', 'install_command': 'npm ci'}]}}
        with patch('deployment_agent.repair.run_command', side_effect=command):
            agent._cli(self.root, run, 'refresh_lockfile')
        self.assertEqual(agent.changed, {'package-lock.json'})
        self.assertEqual(agent.baselines['package-lock.json'], original_hash)

    def test_latest_stream_page_keeps_recent_events_and_preserves_cursor_reads(self):
        store = StateStore(self.root / 'events.sqlite')
        store.create_run('run', 'app', str(self.root), str(self.root))
        for value in range(9):
            store.add_event('run', {'message': str(value)})
        self.assertEqual([event['message'] for event in store.get_events('run', limit=3)], ['0', '1', '2'])
        self.assertEqual([event['message'] for event in store.get_events('run', limit=3, latest=True)], ['6', '7', '8'])
        self.assertEqual([event['message'] for event in store.get_events('run', after_id=6)], ['6', '7', '8'])


if __name__ == '__main__':
    unittest.main()
