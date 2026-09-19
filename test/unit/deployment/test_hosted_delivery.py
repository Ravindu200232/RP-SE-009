import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'deployment-agent' / 'deploy_agent'))
from deployment_agent.hosted import runtime_values
from deployment_agent.models import DeploymentTarget
from dfagents.monitor import MonitorAgent


class HostedDeliveryTests(unittest.TestCase):
    def test_generated_hosted_workflows_validate_and_pin_release(self):
        from test.unit.deployment.test_mern_workspace import _write
        from dfagents.intake import IntakeAgent
        from dfagents.generator import ArtifactGeneratorAgent
        from dfagents.planner import PlannerAgent
        from dfagents.validator import SecurityValidatorAgent
        from deployment_agent.models import DeploymentPlan
        import yaml
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'shop'
            _write(source, 'package.json', {'name': 'shop', 'scripts': {'build': 'next build', 'start': 'next start'}, 'dependencies': {'next': '16.0.0', 'react': '19.0.0'}})
            _write(source, 'package-lock.json', {'lockfileVersion': 3, 'packages': {}})
            _write(source, 'app/page.js', 'export default function Page() { return null }')
            for target in (DeploymentTarget.NETLIFY, DeploymentTarget.AZURE):
                staged = root / target.value
                spec = IntakeAgent().stage_and_analyze('run', source, staged)
                plan = DeploymentPlan(project_slug='shop', primary_service=spec.services[0].name, model_used=True)
                PlannerAgent._apply_deterministic_generation(plan, spec.services[0])
                records = ArtifactGeneratorAgent().generate('run', spec, plan, staged, target=target)
                result = SecurityValidatorAgent().validate('run', staged, [item.to_dict() for item in records], target=target)
                self.assertEqual(result['errors'], [])
                workflow = (staged / '.github/workflows/deploy.yml').read_text(encoding='utf-8')
                parsed = yaml.safe_load(workflow)
                self.assertIn('deploy', parsed['jobs'])
                self.assertIn('$GITHUB_SHA', workflow)

    def test_redeploy_keeps_required_provider_environment(self):
        plan = {'environment': {'entries': [{'name': 'MAIL_API_KEY', 'resolution': 'user_required', 'required': True}]}}
        self.assertEqual(runtime_values(plan, '', 'https://example.test', {'MAIL_API_KEY': 'saved-provider-value'})['MAIL_API_KEY'], 'saved-provider-value')

    def test_hosted_release_requires_current_commit(self):
        for target, state in [('netlify', {'ready': True, 'commit_sha': 'old'}), ('azure', {'ready': True, 'commit_sha': 'old'})]:
            run = {'plan': {'target': target}, 'repo': {'push': {'head_sha': 'new'}}, 'readiness': {'categories': {'build': 15}}}
            snap = {target: state, 'workflow': {'conclusion': 'success'}, 'api': [{'passed': True}]}
            self.assertEqual(MonitorAgent._readiness(run, snap)['categories']['provider'], 0)
            snap[target]['commit_sha'] = 'new'
            self.assertEqual(MonitorAgent._readiness(run, snap)['categories']['provider'], 25)

    def test_cancel_only_current_deployment_workflow(self):
        from dfagents.deployer_lifecycle import DeploymentLifecycleMixin
        import json
        from subprocess import CompletedProcess
        calls = []
        def command(argv, **kwargs):
            calls.append(argv)
            if argv[1:3] == ['run', 'list']:
                return CompletedProcess(argv, 0, json.dumps([
                    {'databaseId': 1, 'status': 'in_progress', 'headSha': 'another-project'},
                    {'databaseId': 2, 'status': 'in_progress', 'headSha': 'mine'},
                ]), '')
            return CompletedProcess(argv, 0, '', '')
        with patch('dfagents.deployer_lifecycle.command_exists', return_value=True), patch('dfagents.deployer_lifecycle.run_command', side_effect=command):
            result = DeploymentLifecycleMixin()._cancel_workflow_run({'repo': {'repository': 'user/repo', 'push': {'head_sha': 'mine'}}})
        self.assertEqual(result, '2')
        self.assertEqual(calls[-1][3], '2')


if __name__ == '__main__':
    unittest.main()
