"""An owned tree outlives its shell, but must not outlive preview shutdown."""
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from server_modules.services.process_tree import spawn_owned, stop_owned


class ProcessTreeTests(unittest.TestCase):
    def test_cleanup_after_parent_exit_releases_child_port(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'port.txt'
            child = ("import socket,time,pathlib; s=socket.socket(); "
                     "s.bind(('127.0.0.1',0)); s.listen(); "
                     f"pathlib.Path({str(marker)!r}).write_text(str(s.getsockname()[1])); time.sleep(30)")
            parent = f"import subprocess,sys; subprocess.Popen([sys.executable,'-c',{child!r}])"
            process = spawn_owned([sys.executable, '-c', parent],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.addCleanup(stop_owned, process)
            process.wait(timeout=10)
            deadline = time.monotonic() + 10
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(.05)
            self.assertTrue(marker.exists(), 'Child did not bind its port')
            port = int(marker.read_text())
            with socket.create_connection(('127.0.0.1', port), timeout=1):
                pass
            stop_owned(process)
            # Windows may finish releasing sockets just after the last job
            # process exits. Require the port to be reusable within two seconds.
            deadline = time.monotonic() + 2
            while True:
                with socket.socket() as listener:
                    try:
                        listener.bind(('127.0.0.1', port))
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise
                time.sleep(.05)
