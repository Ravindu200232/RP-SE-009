"""Direct edits use their project and the durable designer/SRS transaction."""
import ast
import re
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from test import _support  # noqa: F401
from server_modules.services.project_state import ProjectState

ROOT = Path(__file__).resolve().parents[3]
def load(source, name, namespace):
    tree = ast.parse((ROOT / source).read_text(encoding='utf-8'))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), source, 'exec'), namespace)
    return namespace[name]

class ManualPrototypeSyncTests(unittest.TestCase):
    def test_save_queues_only_prototype_summary_with_explicit_project_and_role(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/'alpha').mkdir()
            emit, queue, target = Mock(), Mock(), Mock()
            namespace = {'Path':Path, 'PROD_DIR':root, 're':re, 'SRC_EXT':{'.html','.js'},
                         'MAX_FILE_BYTES':256000, 'MAX_PROTOTYPE_CHARACTERS':4000000, '_safe_stem':lambda value,_:value,
                         'elog':Mock(), 'emit':emit, 'start_run':queue, 'run_manual_prototype_change':target}
            save = load('server_modules/builder/projects.py', 'save_project_file', namespace)
            save('alpha', '.agentforge/prototype/index.html', '<h1>Hello</h1>', change_summary='Heading changed')
            self.assertEqual(emit.call_args.args[0]['project'], 'alpha')
            self.assertEqual(emit.call_args.args[0]['agent'], 'designer')
            queue.assert_called_once_with(target, ('alpha','Heading changed'), project='alpha')
            save('alpha','main.js','const a = 1',change_summary='Builder')
            self.assertEqual(queue.call_count, 1)
            self.assertTrue(save('alpha','.agentforge/prototype/image.html','x'*300000)['ok'])
            self.assertIn('error', save('alpha','main.js','x'*300000))

    def test_valid_direct_edit_does_not_invoke_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/'alpha').mkdir()
            namespace = {'PROD_DIR':root, 'ProjectState':ProjectState, 'time':time, 'emit':Mock(),
                         '_run_agent':Mock(), 'default_agent_model':lambda:'test'}
            run = load('server_modules/srs/parent_sync.py','run_manual_prototype_change',namespace)
            with patch('builder_agent.prototype_check.validate_all',return_value=[]), patch('builder_agent.browser.Browser'):
                run('alpha','Heading changed')
            namespace['_run_agent'].assert_not_called()
            self.assertEqual(ProjectState(root/'alpha').read()['agents']['designer']['summary'],'Heading changed')

    def test_invalid_pages_are_repaired_in_one_request(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/'alpha').mkdir()
            namespace = {'PROD_DIR':root, 'ProjectState':ProjectState, 'time':time, 'emit':Mock(),
                         '_run_agent':Mock(return_value=(Mock(),SimpleNamespace(status='completed',result='fixed'))),
                         'default_agent_model':lambda:'test'}
            run = load('server_modules/srs/parent_sync.py','run_manual_prototype_change',namespace)
            findings = [{'page':'a.html','kind':'page error','text':'broken A'}, {'page':'b.html','kind':'page error','text':'broken B'}]
            with patch('builder_agent.prototype_check.validate_all',return_value=findings), patch('builder_agent.browser.Browser'):
                run('alpha','Heading changed')
            namespace['_run_agent'].assert_called_once()
            self.assertIn('a.html', namespace['_run_agent'].call_args.args[1])
            self.assertIn('b.html', namespace['_run_agent'].call_args.args[1])

    def test_missing_browser_is_not_reported_as_verified(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/'alpha').mkdir()
            namespace = {'PROD_DIR':root, 'ProjectState':ProjectState, 'time':time, 'emit':Mock(), '_run_agent':Mock()}
            run = load('server_modules/srs/parent_sync.py','run_manual_prototype_change',namespace)
            with patch('builder_agent.prototype_check.validate_all',return_value=[{'kind':'browser unavailable'}]), patch('builder_agent.browser.Browser'):
                with self.assertRaisesRegex(RuntimeError,'unavailable'): run('alpha','Heading changed')
            self.assertEqual(ProjectState(root/'alpha').read()['agents']['designer']['status'],'error')
