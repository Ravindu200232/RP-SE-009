"""The shared router observes background traffic and wakes only user opens."""
import http.client
import json
import tempfile
import threading
import subprocess
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import server_runtime as server
from server_modules.services.preview_runtime import RuntimeRegistry, project_host


class Upstream(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(b'<html><head><title>Project</title></head><body>Ready</body></html>')

    def do_POST(self):
        body = self.rfile.read(int(self.headers['Content-Length']))
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Set-Cookie', 'session=ok; HttpOnly; SameSite=Lax')
        self.end_headers()
        self.wfile.write(body)


class PreviewHTTPTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        (self.root / 'shop').mkdir()
        (self.root / 'shop' / 'package.json').write_text('{}', encoding='utf-8')
        self.now = 0
        self.registry = RuntimeRegistry(stop_process=lambda proc: None, clock=lambda: self.now)
        self.addCleanup(self.registry.close)
        self.runtime = self.registry.get(self.root / 'shop')
        self.started = threading.Event()
        self.launches = 0
        self.upstream = self.serve(Upstream)
        self.backend = self.serve(server.UIHandler)
        self.registry.ui_port = self.backend.server_port
        self.host = f'{project_host("shop")}:{self.backend.server_port}'
        for name, value in {'RUNTIMES': self.registry, 'PROD_DIR': self.root,
                            'launch_runtime': self.launch, '_spec_only': lambda root: False}.items():
            patcher = patch.object(server, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def serve(self, handler):
        httpd = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        return httpd

    def launch(self, runtime, generation):
        self.launches += 1
        runtime.ports = {'PORT': self.upstream.server_port}
        runtime.proc = SimpleNamespace(poll=lambda: None)
        self.started.set()
        return True

    def request(self, path='/', method='GET', body=None, **headers):
        conn = http.client.HTTPConnection('127.0.0.1', self.backend.server_port, timeout=5)
        try:
            conn.request(method, path, body=body, headers={'Host': self.host, **headers})
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def test_stopped_background_requests_and_status_never_start_app(self):
        for path in ('/', '/api/poll', '/_next/webpack-hmr'):
            self.assertEqual(self.request(path)[0], 503)
        self.assertEqual(self.request(server.PREVIEW_PATH + '/status')[0], 200)
        self.assertEqual(self.launches, 0)
        self.assertEqual(self.runtime.status, 'stopped')

    def test_browser_refresh_starts_stopped_app_and_reuses_running_app(self):
        headers = {'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-User': '?1'}
        self.assertEqual(self.request(**headers)[0], 200)
        self.assertTrue(self.started.wait(2))
        with self.runtime.lock:
            self.assertEqual(self.runtime.status, 'running')
        self.now = 500
        self.request(**headers)
        self.assertEqual(self.launches, 1)
        self.assertEqual(self.runtime.last_activity, 500)

    def test_activity_requires_current_runtime_and_matching_origin(self):
        self.registry.open(self.runtime, self.launch, background=False)
        self.now = 400
        path = server.PREVIEW_PATH + '/activity'
        body = json.dumps({'runtimeId': self.runtime.runtime_id})
        self.assertEqual(self.request(path, 'POST', body, Origin='http://evil.localhost')[0], 403)
        stale = self.request(path, 'POST', '{"runtimeId":"old"}', Origin='http://' + self.host)
        self.assertFalse(json.loads(stale[2])['ok'])
        self.assertEqual(self.runtime.last_activity, 0)
        current = self.request(path, 'POST', body, Origin='http://' + self.host)
        self.assertTrue(json.loads(current[2])['ok'])
        self.assertEqual(self.runtime.last_activity, 400)

    def test_proxy_injects_bridge_preserves_body_and_does_not_touch_activity(self):
        self.registry.open(self.runtime, self.launch, background=False)
        self.now = 599
        status, headers, body = self.request()
        self.assertEqual(status, 200)
        self.assertIn(self.runtime.runtime_id.encode(), body)
        self.assertIn(b'<head><script nonce=', body)
        self.assertIn("'nonce-", headers['Content-Security-Policy'])
        self.assertNotIn("frame-ancestors 'none'", headers['Content-Security-Policy'])
        payload = '{"item":"hello"}'
        status, headers, body = self.request('/api/example', 'POST', payload)
        self.assertEqual(body.decode(), payload)
        self.assertIn('Partitioned', headers['Set-Cookie'])
        self.assertEqual(self.runtime.last_activity, 0)
        self.now = 600
        self.registry.reap()
        self.assertEqual(self.runtime.reason, 'idle')

    def test_generated_origin_cannot_access_management_api_or_old_bridge(self):
        self.assertEqual(self.request('/__agentforge/api/projects')[0], 404)
        self.assertEqual(self.request(server.PREVIEW_PATH + '/bridge.js?runtimeId=old')[0], 410)

    def test_injected_bridge_is_a_standalone_classic_script(self):
        status, _, body = self.request(server.PREVIEW_PATH + '/bridge.js?runtimeId=' + self.runtime.runtime_id)
        self.assertEqual(status, 200)
        target = self.root / 'bridge.js'; target.write_bytes(body)
        result = subprocess.run(['node','--check',str(target)],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('useStore', body.decode())
