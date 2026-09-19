"""Isolation, port ownership, expiry and concurrent project opening."""
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from server_modules.services.preview_runtime import RuntimeRegistry, runtime_environment, project_host


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = 0
        self.stopped = []
        self.events = []
        self.registry = RuntimeRegistry(stop_process=self.stopped.append, emit=self.events.append,
                                        clock=lambda: self.now)
        self.addCleanup(self.registry.close)
        self.a = self.registry.get(Path(self.temp.name) / 'a')
        self.b = self.registry.get(Path(self.temp.name) / 'b')

    def ready(self, runtime, generation):
        runtime.proc = SimpleNamespace(poll=lambda: None)
        return True

    def open(self, runtime):
        return self.registry.open(runtime, self.ready, background=False)

    def test_idle_boundary_and_other_project_activity(self):
        self.open(self.a)
        self.open(self.b)
        first, second = self.a.proc, self.b.proc
        self.now = 599
        self.registry.reap()
        self.assertEqual(self.stopped, [])
        self.registry.activity(self.b, self.b.runtime_id)
        self.now = 600
        self.registry.reap()
        self.assertEqual(self.stopped, [first])
        self.assertIs(self.b.proc, second)
        self.assertEqual(self.a.reason, 'idle')

    def test_activity_extends_deadline_but_status_reads_do_not(self):
        self.open(self.a)
        self.now = 599
        self.assertTrue(self.registry.activity(self.a, self.a.runtime_id))
        for self.now in (600, 900, 1198):
            self.registry.snapshot(self.a)
            self.registry.reap()
            self.assertEqual(self.a.status, 'running')
        self.now = 1199
        self.registry.reap()
        self.assertEqual(self.a.status, 'stopped')

    def test_build_lease_starts_clock_after_completion(self):
        self.open(self.a)
        self.registry.begin_work(self.a)
        self.now = 1800
        self.registry.reap()
        self.assertEqual(self.a.status, 'running')
        self.registry.end_work(self.a)
        self.now = 2399
        self.registry.reap()
        self.assertEqual(self.a.status, 'running')
        self.now = 2400
        self.registry.reap()
        self.assertEqual(self.a.status, 'stopped')

    def test_old_activity_cannot_extend_a_restarted_runtime(self):
        old = self.open(self.a)
        self.registry.stop(self.a, 'idle')
        new = self.open(self.a)
        self.assertNotEqual(old['runtimeId'], new['runtimeId'])
        self.assertEqual(old['previewUrl'], new['previewUrl'])
        self.now = 599
        self.assertFalse(self.registry.activity(self.a, old['runtimeId']))
        self.now = 600
        self.registry.reap()
        self.assertEqual(self.a.status, 'stopped')

    def test_reopen_running_reuses_process(self):
        first = self.open(self.a)
        process = self.a.proc
        self.now = 500
        second = self.open(self.a)
        self.assertEqual(first['runtimeId'], second['runtimeId'])
        self.assertIs(self.a.proc, process)
        self.assertEqual(self.a.last_activity, 500)

    def test_duplicate_open_joins_startup_and_other_project_can_start(self):
        entered, release, done = threading.Event(), threading.Event(), threading.Event()
        calls = []
        def launch(runtime, generation):
            calls.append(runtime.project)
            entered.set()
            release.wait(2)
            self.ready(runtime, generation)
            done.set()
            return True
        first = self.registry.open(self.a, launch)
        self.assertTrue(entered.wait(2))
        second = self.registry.open(self.a, launch)
        self.open(self.b)
        self.assertEqual(first['requestId'], second['requestId'])
        self.assertEqual(calls, ['a'])
        self.assertEqual(self.b.status, 'running')
        release.set()
        self.assertTrue(done.wait(2))

    def test_stale_failure_does_not_stop_replacement(self):
        self.registry._new_start(self.a)
        old_generation = self.a.generation
        self.registry.stop(self.a)
        self.open(self.a)
        replacement = self.a.proc
        def late_failure(runtime, generation):
            raise RuntimeError('old startup')
        self.registry._launch(self.a, old_generation, late_failure)
        self.assertEqual(self.a.status, 'running')
        self.assertIs(self.a.proc, replacement)

    def test_startup_failure_stops_only_owned_tree(self):
        self.open(self.b)
        proc = object()
        def fail(runtime, generation):
            runtime.proc = proc
            self.registry.allocate(runtime, {'PORT': 0})
            raise RuntimeError('missing service')
        result = self.registry.open(self.a, fail, background=False)
        self.assertEqual(result['status'], 'failed')
        self.assertIn('missing service', result['error'])
        self.assertEqual(self.stopped, [proc])
        self.assertEqual(self.a.ports, {})
        self.assertEqual(self.b.status, 'running')

    def test_busy_ports_are_skipped_and_external_listener_survives(self):
        with socket.socket() as external:
            external.bind(('127.0.0.1', 0))
            external.listen()
            port = external.getsockname()[1]
            a = self.registry.allocate(self.a, {'PORT': port, 'AUTH_PORT': port, 'MONGODB_PORT': 27017})
            b = self.registry.allocate(self.b, {'PORT': port, 'AUTH_PORT': port})
            self.assertNotIn(port, [*a.values(), *b.values()])
            self.assertNotIn('MONGODB_PORT', a)
            self.assertEqual(len(set([*a.values(), *b.values()])), 4)
            self.registry.stop(self.a)
            with socket.create_connection(('127.0.0.1', port), timeout=1):
                pass
            self.assertEqual(self.stopped, [])

    def test_concurrent_allocations_are_distinct(self):
        barrier = threading.Barrier(2)
        def allocate(runtime):
            barrier.wait()
            self.registry.allocate(runtime, {'PORT': 5173, 'AUTH_PORT': 4101})
        workers = [threading.Thread(target=allocate, args=(r,)) for r in (self.a, self.b)]
        for worker in workers: worker.start()
        for worker in workers: worker.join(2)
        ports = [*self.a.ports.values(), *self.b.ports.values()]
        self.assertEqual(len(set(ports)), 4)

    def test_local_url_overrides_follow_ports_without_changing_external_dependencies(self):
        env = runtime_environment({'AUTH_URL': 'http://localhost:4101/api',
            'MONGODB_URI': 'mongodb://localhost:27017/shop', 'BILLING_URL': 'https://billing.example/api'},
            {'PORT': 50000, 'AUTH_PORT': 50001, 'BILLING_PORT': 50002})
        self.assertEqual(env['AUTH_URL'], 'http://127.0.0.1:50001/api')
        self.assertEqual(env['MONGODB_URI'], 'mongodb://localhost:27017/shop')
        self.assertEqual(env['BILLING_URL'], 'https://billing.example/api')
        self.assertEqual(env['PUBLIC_APP_URL'], 'http://127.0.0.1:50000')

    def test_host_identity_is_stable_and_distinct(self):
        self.assertEqual(project_host('shop'), project_host('shop'))
        self.assertNotEqual(project_host('shop'), project_host('Shop'))
        self.assertRegex(project_host('spaces and symbols!'), r'^p-[a-f0-9]{24}\.localhost$')


if __name__ == '__main__':
    unittest.main()
