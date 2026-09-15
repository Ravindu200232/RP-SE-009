import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'deployment-agent' / 'deploy_agent'))
sys.path.insert(0, str(ROOT / 'deployment-agent'))
from deployment_agent.events import EventBus
from deployment_agent.models import ArtifactRecord, DeploymentPlan, DeploymentTarget, ProjectSpec, RepositorySpec, ServiceSpec
from deployment_agent.orchestrator import Orchestrator
from deployment_agent.state import StateStore


class SecurityRepairTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.source, self.staged = self.root / 'source', self.root / 'staged'
        self.source.mkdir(); self.staged.mkdir()
        (self.staged / 'readiness-score.json').write_text(json.dumps({'categories': {'security': 0, 'build': 0}, 'score': 0}))
        self.store = StateStore(self.root / 'state.sqlite')
        self.store.create_run('run', 'app', str(self.source), str(self.staged))
        self.orchestrator = Orchestrator(self.store, EventBus(self.store))
        self.spec = ProjectSpec('app', str(self.source), str(self.staged),
                                [ServiceSpec('app', '', 'node', '', 'npm', 'npm ci', 'npm run build', 'npm start')], RepositorySpec(False))
        self.plan = DeploymentPlan('app', 'app', model_used=True)
        self.records = [ArtifactRecord('package.json', 'source-patch', 'test-hash', 10, True, 'original-hash')]
        self.agent = Mock(changed={'package.json'})

    def analyze(self, validations, builds):
        with patch.dict(os.environ, {'DEPLOYMENT_AGENT_SKIP_BUILD_VALIDATION': '0'}), \
             patch('deployment_agent.orchestrator.IntakeAgent') as intake, \
             patch('deployment_agent.orchestrator.PlannerAgent') as planner, \
             patch('deploy_agent.bridge.ollama_client', return_value=Mock()), \
             patch('deployment_agent.orchestrator.ArtifactGeneratorAgent') as generator, \
             patch('deployment_agent.orchestrator.SecurityValidatorAgent') as validator, \
             patch('deployment_agent.repair.DeploymentRepairAgent', return_value=self.agent), \
             patch('deployment_agent.repair_records.record_repairs', return_value=[record.to_dict() for record in self.records]), \
             patch.object(self.orchestrator, '_validate_build', side_effect=builds) as build:
            intake.return_value.stage_and_analyze.return_value = self.spec
            planner.return_value.plan.return_value = self.plan
            generator.return_value.generate.return_value = self.records
            generator.return_value.finalize_review.side_effect = lambda spec, plan, staged, readiness, records: records
            validator.return_value.validate.side_effect = validations
            self.orchestrator._analyze('run', self.source, self.staged, True)
        return self.store.get_run('run'), build

    @staticmethod
    def validation(passed=True):
        return {'passed': passed, 'errors': [] if passed else ['OIDC subject restriction is missing'], 'warnings': []}

    @staticmethod
    def build(total=0):
        return {'attempted': True, 'passed': True, 'output': 'production build passed',
                'dependency_findings': {'total': total, 'high': 2 if total else 0, 'critical': 1 if total else 0}}

    def test_successful_build_with_vulnerabilities_is_sent_to_llm_and_revalidated(self):
        run, build = self.analyze([self.validation(), self.validation()], [self.build(7), self.build()])
        self.agent.repair.assert_called_once()
        self.assertIn('7', self.agent.repair.call_args.args[2])
        self.assertEqual(build.call_count, 2)
        self.assertTrue(run['readiness']['gates']['security_validation'])

    def test_artifact_security_failure_is_repaired_before_build(self):
        run, build = self.analyze([self.validation(False), self.validation()], [self.build()])
        self.agent.repair.assert_called_once()
        self.assertIn('OIDC subject restriction', self.agent.repair.call_args.args[2])
        self.assertEqual(build.call_count, 1)
        self.assertEqual(run['state'], 'REVIEW_READY')

    def test_remaining_vulnerabilities_stop_after_bounded_repairs(self):
        run, _ = self.analyze([self.validation()] * 3, [self.build(7)] * 3)
        self.assertEqual(self.agent.repair.call_count, 2)
        self.assertFalse(run['readiness']['gates']['security_validation'])
        self.assertEqual(run['state'], 'FAILED')

    def test_informational_security_warnings_do_not_start_repair(self):
        validation = self.validation()
        validation['warnings'] = ['Provider credential is stored in GitHub Actions secrets']
        run, _ = self.analyze([validation], [self.build()])
        self.agent.repair.assert_not_called()
        self.assertTrue(run['readiness']['gates']['security_validation'])


if __name__ == '__main__':
    unittest.main()
