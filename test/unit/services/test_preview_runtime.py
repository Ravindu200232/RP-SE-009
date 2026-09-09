"""The public client and every declared service must answer before preview."""
import tempfile
import json
import io
import os
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import server_runtime as server


class Response:
    status = 200
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


class PreviewReadinessTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / '.env.local').write_text('PORT=4000\nAUTH_PORT=4101\n', encoding='utf-8')
        patcher = patch.object(server, 'active_vite', {'dir': str(self.root), 'ready': True,
            'proc': SimpleNamespace(poll=lambda: None)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_missing_client_bundle_cannot_be_reported_ready(self):
        error = urllib.error.HTTPError('http://127.0.0.1:5173/', 503, 'client not built', {}, None)
        with patch('urllib.request.urlopen', side_effect=error), patch.object(server.time, 'sleep'), \
                patch.object(server, 'elog'):
            self.assertFalse(server.wait_for_dev('mern-microservices', timeout=0.02))

    def test_a_failed_internal_service_cannot_be_hidden_by_the_gateway(self):
        def probe(url, **kwargs):
            if ':4101/' in url:
                raise urllib.error.HTTPError(url, 503, 'DB not ready', {}, None)
            return Response()
        with patch('urllib.request.urlopen', side_effect=probe), patch.object(server.time, 'sleep'), \
                patch.object(server, 'elog'):
            self.assertFalse(server.wait_for_dev('mern-microservices', timeout=0.02))

    def test_client_and_all_declared_services_are_probed(self):
        with patch('urllib.request.urlopen', return_value=Response()) as probe:
            self.assertTrue(server.wait_for_dev('mern-microservices', timeout=1))
        urls = [call.args[0] for call in probe.call_args_list]
        self.assertIn('http://127.0.0.1:5173/', urls)
        self.assertIn('http://127.0.0.1:4101/health', urls)
        self.assertNotIn('http://127.0.0.1:4000/health', urls)

    def test_old_startup_cannot_claim_the_next_projects_ready_response(self):
        def switch_project(url, **kwargs):
            server.active_vite['proc'] = SimpleNamespace(poll=lambda: None)
            server.active_vite['dir'] = str(self.root / 'new-project')
            return Response()
        with patch('urllib.request.urlopen', side_effect=switch_project):
            self.assertFalse(server.wait_for_dev('mern-microservices', timeout=1))

    def test_replaced_open_never_stops_or_completes_the_new_project(self):
        def replace_while_waiting(stack):
            server.active_vite['request'] = 'newer-open-request'
            return False
        with patch.object(server, 'PROD_DIR', self.root.parent), \
                patch.object(server, 'working_on'), patch.object(server, 'release_other_sessions'), \
                patch.object(server, 'free_declared_ports', return_value=[]), \
                patch.object(server.MONGO, 'ensure_running'), \
                patch.object(server, 'ensure_node_deps', return_value=True), \
                patch.object(server, 'start_dev_server', return_value=True), \
                patch.object(server, 'wait_for_dev', side_effect=replace_while_waiting), \
                patch.object(server, '_stop_dev_proc') as stop, \
                patch.object(server, 'edone') as done, patch.object(server, 'eerr') as error:
            server._open_project(self.root.name)
        self.assertEqual(stop.call_count, 1)
        done.assert_not_called()
        error.assert_not_called()

    def test_root_supervisor_receives_project_environment_and_public_port(self):
        (self.root / '.env.local').write_text('PORT=4000\nAUTH_PORT=4101\nAPP_NAME="Shop"\n', encoding='utf-8')
        process = SimpleNamespace(pid=999, stdout=io.StringIO(''), stderr=io.StringIO(''))
        with patch.object(server, '_stop_dev_proc'), patch.object(server, '_kill_port'), \
                patch.object(server.threading, 'Thread'), \
                patch.object(server.subprocess, 'Popen', return_value=process) as spawn:
            self.assertTrue(server.start_next(self.root, stack='mern-microservices'))
        self.assertEqual(spawn.call_args.args[0], [server.NPM_BIN, 'run', 'dev'])
        self.assertEqual(spawn.call_args.kwargs['env']['PORT'], str(server.DEV_PORT))
        self.assertEqual(spawn.call_args.kwargs['env']['AUTH_PORT'], '4101')
        self.assertEqual(spawn.call_args.kwargs['env']['APP_NAME'], 'Shop')

    def test_local_port_override_does_not_wait_for_the_example_port(self):
        (self.root / '.env.example').write_text('AUTH_PORT=4201\n', encoding='utf-8')
        self.assertEqual(server.declared_ports(self.root), [4000, 4101])

    def test_only_a_missing_or_changed_client_bundle_is_built(self):
        client = self.root / 'client'
        client.mkdir()
        (self.root / 'package.json').write_text(json.dumps({'scripts': {'build': 'build-client'}}), encoding='utf-8')
        manifest = client / 'package.json'
        manifest.write_text('{}', encoding='utf-8')
        with patch.object(server.cancel, 'run', return_value=SimpleNamespace(returncode=0)) as build:
            self.assertTrue(server._ensure_client_bundle(self.root))
            self.assertEqual(build.call_count, 1)
            (client / 'dist').mkdir()
            index = client / 'dist/index.html'
            index.write_text('<html>Shop</html>', encoding='utf-8')
            os.utime(manifest, (10, 10))
            self.assertTrue(server._ensure_client_bundle(self.root))
            self.assertEqual(build.call_count, 1)
            os.utime(manifest, (index.stat().st_mtime + 10, index.stat().st_mtime + 10))
            self.assertTrue(server._ensure_client_bundle(self.root))
            self.assertEqual(build.call_count, 2)
