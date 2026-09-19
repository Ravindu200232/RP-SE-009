"""Exercise the runtime's Deploy response without starting servers or cloud clients."""
import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'builder-agent'))


def load_functions(namespace, source, names):
    parsed = ast.parse((ROOT / source).read_text(encoding='utf-8'))
    functions = [node for node in parsed.body if isinstance(node, ast.FunctionDef) and node.name in names]
    exec(compile(ast.Module(body=functions, type_ignores=[]), source, 'exec'), namespace)


class AccountStatusTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / 'shop').mkdir()
        self.user = {'id': 'u0123456789abcdef012345'}
        self.settings = {
            'aws_profile': 'af-cdef012345-agentforge-console', 'aws_region': 'ap-south-1',
            'github_token': 'test-user-gh', 'github_login': 'owner',
            'vercel_token': 'test-user-vercel', 'netlify_token': 'test-user-netlify',
            'azure_credentials': 'test-user-azure',
        }
        self.namespace = {
            'Path': Path, 'json': json, 'PROD_DIR': self.root, 'DEPLOY_RUNS': {},
            'acting': lambda: self.user,
            'auth_db': SimpleNamespace(user_settings=Mock(side_effect=lambda _: self.settings)),
            'load_settings': Mock(return_value={'aws_profile': 'agentforge-console', 'aws_region': 'us-east-1'}),
            'deploy_status': lambda: {'listening': True}, '_redact_uri': lambda value: '',
        }
        load_functions(self.namespace, 'server_modules/deploy/deploy_runtime.py',
                       {'_deploy_mongo_uri', 'deploy_settings_summary', 'read_deploy_results'})
        load_functions(self.namespace, 'server_modules/deploy/deploy_tenancy.py', {'deploy_summary_for'})

    def test_deploy_tab_uses_the_same_profile_and_accounts_as_settings(self):
        expected = self.namespace['deploy_summary_for'](self.user)
        result = self.namespace['read_deploy_results']('shop')
        self.assertEqual(result['settings'], expected)
        self.assertEqual(result['settings']['aws_profile'], self.settings['aws_profile'])
        self.namespace['load_settings'].assert_not_called()

    def test_switching_accounts_does_not_reuse_the_first_users_profile(self):
        for owner, profile in [('u0123456789abcdef012345', 'af-cdef012345-console'),
                               ('u543210fedcba9876543210', 'af-9876543210-console')]:
            self.user = {'id': owner}
            self.settings = {'aws_profile': profile, 'aws_region': 'ap-south-1'}
            result = self.namespace['read_deploy_results']('shop')
            self.assertEqual(result['settings']['aws_profile'], profile)
        self.namespace['load_settings'].assert_not_called()

    def test_no_request_owner_never_exposes_machine_deployment_accounts(self):
        self.user = None
        result = self.namespace['read_deploy_results']('shop')
        self.assertEqual(result['settings'], {})
        self.namespace['load_settings'].assert_not_called()


if __name__ == '__main__':
    unittest.main()
