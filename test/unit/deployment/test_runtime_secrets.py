import sys
import unittest
from pathlib import Path
from test import _support  # noqa: F401

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'deployment-agent' / 'deploy_agent'))
sys.path.insert(0, str(ROOT / 'deployment-agent'))
from dfagents.deployer_prepare import DeploymentPrepareMixin
from deployment_agent.environment import EnvironmentContractResolver
from deployment_agent.models import EnvironmentVariable, ServiceSpec


class RuntimeSecretTests(unittest.TestCase):
    def test_session_signing_key_generated_and_retained_on_redeploy(self):
        service = ServiceSpec('api', '', 'express', '', 'npm', 'npm ci', '', 'node server.js',
                              environment=[EnvironmentVariable(name='SESSION_SECRET', secret=True, required=False)])
        contract = EnvironmentContractResolver.discover(service)
        self.assertEqual(contract.entries[0].resolution, 'auto_generate')
        plan = {'environment': contract.to_dict()}
        first = DeploymentPrepareMixin._runtime_secret_values('mongodb://host/app', {}, plan)
        self.assertGreaterEqual(len(first['SESSION_SECRET']), 48)
        second = DeploymentPrepareMixin._runtime_secret_values('mongodb://host/app', {}, plan, first)
        self.assertEqual(first['SESSION_SECRET'], second['SESSION_SECRET'])
