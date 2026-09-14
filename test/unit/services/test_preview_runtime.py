"""The public client and every declared service must answer before preview."""
import tempfile
import json
import io
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import server_runtime as server


class PreviewReadinessTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / '.env.local').write_text('PORT=4000\nAUTH_PORT=4101\n', encoding='utf-8')
        self.runtime = server.RUNTIMES.get(self.root, 'mern-microservices')
        self.runtime.ports = {'PORT': 5173, 'AUTH_PORT': 4101}
        self.runtime.proc = SimpleNamespace(poll=lambda: None)
        self.addCleanup(lambda: setattr(self.runtime, 'proc', None))

    def wait(self, **kwargs):
        return server.wait_for_dev('mern-microservices', runtime=self.runtime, **kwargs)

    def test_a_missing_client_bundle_cannot_be_reported_ready(self):
        with patch.object(server.requests, 'get', return_value=SimpleNamespace(status_code=503, close=lambda: None)):
            self.assertFalse(self.wait(timeout=0.02))

    def test_a_failed_internal_service_cannot_be_hidden_by_the_gateway(self):
        def probe(url, **kwargs):
            return SimpleNamespace(status_code=503 if ':4101/' in url else 200, close=lambda: None)
        with patch.object(server.requests, 'get', side_effect=probe):
            self.assertFalse(self.wait(timeout=0.02))

    def test_client_and_all_allocated_services_are_probed(self):
        self.runtime.ports = {'PORT': 50100, 'AUTH_PORT': 50101}
        with patch.object(server.requests, 'get', return_value=SimpleNamespace(status_code=200, close=lambda: None)) as probe:
            self.assertTrue(self.wait(timeout=1))
        urls = [call.args[0] for call in probe.call_args_list]
        self.assertEqual(urls, ['http://127.0.0.1:50100/', 'http://127.0.0.1:50101/health'])

    def test_old_startup_cannot_claim_a_replacement_response(self):
        def replace(url, **kwargs):
            self.runtime.generation += 1
            return SimpleNamespace(status_code=200, close=lambda: None)
        with patch.object(server.requests, 'get', side_effect=replace):
            self.assertFalse(self.wait(timeout=1))

    def test_root_supervisor_receives_project_environment_and_allocated_ports(self):
        (self.root / '.env.local').write_text('PORT=4000\nAUTH_PORT=4101\nAPP_NAME="Shop"\n', encoding='utf-8')
        process = SimpleNamespace(pid=999, stdout=io.StringIO(''), stderr=io.StringIO(''))
        with patch.object(server.threading, 'Thread'), patch.object(server, 'spawn_owned', return_value=process) as spawn:
            self.assertTrue(server._spawn_preview(self.runtime, self.runtime.generation))
        self.assertEqual(spawn.call_args.args[0], [server.NPM_BIN, 'run', 'dev'])
        self.assertEqual(spawn.call_args.kwargs['env']['PORT'], '5173')
        self.assertEqual(spawn.call_args.kwargs['env']['AUTH_PORT'], '4101')
        self.assertEqual(spawn.call_args.kwargs['env']['APP_NAME'], 'Shop')

    def test_local_port_override_does_not_wait_for_the_example_port(self):
        (self.root / '.env.example').write_text('AUTH_PORT=4201\n', encoding='utf-8')
        self.assertEqual(server.declared_ports(self.root), [4000, 4101])

    def test_runtime_info_allocates_before_the_first_agent_command(self):
        self.runtime.ports.clear()
        self.addCleanup(server.RUNTIMES.release_ports, self.runtime)
        info = server.agent_runtime_info(self.runtime)
        self.assertGreater(info['ports']['PORT'], 0)
        self.assertEqual(info['environment']['AUTH_PORT'], str(info['ports']['AUTH_PORT']))
        self.assertNotIn('MONGODB_URI', info['environment'])

    def test_bind_races_retry_only_owned_startups_at_most_three_times(self):
        (self.root / "package.json").write_text("{}", encoding="utf-8")
        for failures in (1, 3):
            with self.subTest(failures=failures):
                processes = []
                self.runtime.logs = []
                self.runtime.error = ''
                self.runtime.proc = None
                def spawn(runtime, generation):
                    process = SimpleNamespace(poll=lambda: 1)
                    processes.append(process)
                    runtime.proc = process
                    runtime.logs = ['EADDRINUSE'] if len(processes) <= failures else []
                    return True
                with patch.object(server, 'working_on'), patch.object(server.MONGO, 'ensure_running'), \
                        patch.object(server, 'stack_of', return_value='mern-microservices'), \
                        patch.object(server, 'ensure_node_deps', return_value=True), \
                        patch.object(server, '_ensure_client_bundle', return_value=True), \
                        patch.object(server, '_spawn_preview', side_effect=spawn), \
                        patch.object(server, 'wait_for_dev', side_effect=lambda *a, **k: len(processes) > failures), \
                        patch.object(server.RUNTIMES, 'stop_process') as stop:
                    self.assertEqual(server.launch_runtime(self.runtime, self.runtime.generation), failures == 1)
                self.assertEqual(len(processes), min(failures + 1, 3))
                self.assertEqual([call.args[0] for call in stop.call_args_list], processes[:failures])

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
