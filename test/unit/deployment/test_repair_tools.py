import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'deployment-agent' / 'deploy_agent'))
from deployment_agent.repair import DeploymentRepairAgent
from deployment_agent.security import sha256_file
from deployment_agent.state import StateStore
from dfagents.deployer_git import DeploymentGitMixin


class RepairToolsTests(unittest.TestCase):
    def test_local_docker_never_reaches_a_process(self):
        from deployment_agent.tools import run_command
        with patch('deployment_agent.tools.subprocess.run') as process:
            for command in (['docker', 'version'], ['docker-compose', 'up'], ['docker-compose.bat', 'up'], [r'C:\Program Files\Docker\docker.exe', 'build', '.']):
                with self.assertRaisesRegex(ValueError, 'prohibited'):
                    run_command(command)
            process.assert_not_called()

    def test_docker_hidden_in_package_build_is_refused(self):
        from deployment_agent.tools import run_command
        with patch('deployment_agent.tools.subprocess.run') as process:
            for script in ('docker build -t local .', '"C:\\Program Files\\Docker\\docker.exe" build .'):
                (self.staged / 'package.json').write_text(json.dumps({'scripts': {'build': script}}), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'contain Docker'):
                    run_command(['npm', 'run', 'build'], cwd=self.staged)
            process.assert_not_called()

    def test_builder_docker_policy_applies_in_every_mode(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'builder-agent'))
        from builder_agent.policy import classify, BLOCKED
        for command in ('docker --version', 'docker ps', 'Docker.exe build .', 'docker-compose up', 'docker-compose.exe up', 'docker-compose.bat up', '"C:\\Program Files\\Docker\\docker.exe" build .', 'npm run build && docker compose up'):
            self.assertEqual(classify(command)[0], BLOCKED)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.staged = self.root / 'staged'
        self.source = self.root / 'source'
        self.staged.mkdir(); self.source.mkdir()
        self.store = StateStore(self.root / 'state.sqlite')
        self.store.create_run('run', 'source', str(self.source), str(self.staged))
        self.store.update_run('run', plan_json={'target': 'azure'}, spec_json={})

    def test_all_source_conflicts_found_before_any_artifact_is_applied(self):
        records = []
        for name in ('a.js', 'b.js'):
            (self.source / name).write_text('original', encoding='utf-8')
            (self.staged / name).write_text('repair', encoding='utf-8')
            records.append({'path': name, 'sha256': sha256_file(self.staged / name), 'original_exists': True,
                            'original_sha256': sha256_file(self.source / name)})
        (self.source / 'b.js').write_text('user update', encoding='utf-8')
        self.store.set_artifacts('run', records)
        deployer = DeploymentGitMixin()
        deployer.store, deployer.emit = self.store, lambda *args: None
        with self.assertRaisesRegex(RuntimeError, 'changed after review'):
            deployer._apply_reviewed_artifacts('run', self.source, self.staged)
        self.assertEqual((self.source / 'a.js').read_text(), 'original')
        self.assertEqual((self.source / 'b.js').read_text(), 'user update')

    def test_bundled_repair_cannot_write_parent_context_or_escape_staged_copy(self):
        for name in ('a.js', 'b.js'):
            (self.staged / name).write_text('broken', encoding='utf-8')
        rounds = iter([
            {'summary': 'Inspect both errors', 'actions': [{'tool': 'read_file', 'path': name} for name in ('a.js', 'b.js')]},
            {'summary': 'Fix both together', 'actions': [
                {'tool': 'write_file', 'path': '../outside.js', 'content': 'damage'},
                {'tool': 'write_file', 'path': '.agentforge/handoff/srs.md', 'content': 'damage'},
                *[{'tool': 'edit_file', 'path': name, 'old': 'broken', 'new': 'fixed'} for name in ('a.js', 'b.js')],
                {'tool': 'finish'},
            ]},
        ])
        client = type('Client', (), {'chat_json': lambda *args: next(rounds)})()
        agent = DeploymentRepairAgent(self.store, lambda *args: None, client)
        self.assertEqual(agent.repair('run', self.staged, 'two errors'), ['a.js', 'b.js'])
        self.assertFalse((self.root / 'outside.js').exists())
        self.assertFalse((self.staged / '.agentforge').exists())
        self.assertEqual(list(self.source.iterdir()), [])

    def test_repeated_identical_errors_stop_without_infinite_retry(self):
        reply = {'summary': 'Inspect missing file', 'actions': [{'tool': 'read_file', 'path': 'missing.js'}]}
        client = type('Client', (), {'chat_json': lambda *args: reply})()
        agent = DeploymentRepairAgent(self.store, lambda *args: None, client)
        with self.assertRaisesRegex(RuntimeError, 'repeated identical'):
            agent.repair('run', self.staged, 'error')

    def test_question_answer_regenerates_choices_without_touching_source(self):
        from test.unit.deployment.test_mern_workspace import _write
        from dfagents.intake import IntakeAgent
        from dfagents.generator import ArtifactGeneratorAgent
        from dfagents.planner import PlannerAgent
        from deployment_agent.models import DeploymentPlan, DeploymentTarget
        from deployment_agent.repair import submit_answer
        _write(self.source, 'package.json', {'name': 'shop', 'scripts': {'build': 'next build', 'start': 'next start'}, 'dependencies': {'next': '16.0.0'}})
        _write(self.source, 'package-lock.json', {'lockfileVersion': 3, 'packages': {}})
        spec = IntakeAgent().stage_and_analyze('run', self.source, self.staged)
        plan = DeploymentPlan(project_slug='shop', primary_service=spec.services[0].name, model_used=True)
        PlannerAgent._apply_deterministic_generation(plan, spec.services[0])
        records = ArtifactGeneratorAgent().generate('run', spec, plan, self.staged, target=DeploymentTarget.NETLIFY)
        self.store.update_run('run', plan_json=plan.to_dict(), spec_json=spec.to_dict())
        self.store.set_artifacts('run', [record.to_dict() for record in records])
        def emit(run_id, kind, *args):
            if kind == 'question':
                submit_answer(self.store, run_id, self.store.get_question(run_id)['id'], 'shop-renamed')
        agent = DeploymentRepairAgent(self.store, emit, object())
        result = agent._execute('run', self.staged, self.store.get_run('run'), {
            'tool': 'ask_user', 'setting': 'project_name', 'question': 'Choose another site name'})
        self.assertEqual(result['answer'], 'shop-renamed')
        self.assertEqual(self.store.get_run('run')['plan']['project_slug'], 'shop-renamed')
        self.assertIn('deployment-manifest.json', agent.changed)
        self.assertFalse((self.source / 'deployment-manifest.json').exists())
        self.assertIsNone(self.store.get_question('run'))

    def test_user_choice_cannot_retarget_a_provisioned_cloud_application(self):
        self.store.update_run('run', repo_json={'azure_app_name': 'recorded-app'})
        agent = DeploymentRepairAgent(self.store, lambda *args: None, object())
        with self.assertRaisesRegex(ValueError, 'cannot change'):
            agent._apply_choice('run', self.staged, 'project_name', 'another-app')
        self.assertFalse(agent.changed)


if __name__ == '__main__':
    unittest.main()
