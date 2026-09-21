"""Exercise the engine's real CDP error-path assertion against a local fixture."""
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "builder-agent"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "qa-agent"))
from qa_agent.browser import Browser
from qa_agent.evidence import Evidence
from qa_agent.journeys import run_journey
from builder_agent.sandbox import Sandbox


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        body = b'''<!doctype html><title>Expected response fixture</title>
<button onclick="fetch('/duplicate',{method:'POST'}).then(async r=>{
document.querySelector('p').textContent=await r.text()})">Duplicate signup</button><p></p>'''
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self.send_response(409)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"An account with this email already exists")


server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
threading.Thread(target=server.serve_forever, daemon=True).start()
browser = Browser()
try:
    with tempfile.TemporaryDirectory() as directory:
        browser.open_tab()
        evidence = Evidence()
        result = run_journey(browser, Sandbox(directory), evidence,
            suite="duplicate-signup", covers=[], start_url=f"http://127.0.0.1:{server.server_port}", steps=[
                {"action": "click", "role": "button", "name": "Duplicate signup"},
                {"type": "httpStatus", "url": "/duplicate", "expected": 409},
                {"type": "textIncludes", "expected": "already exists"},
                {"type": "noDiagnostics"},
            ])
        print(result["content"])
        assert evidence.suites[-1]["status"] == "passed"
        assert any(d.get("source") == "network" and d["kind"] == "console error"
                   for d in browser.page().diagnostics), "Fixture must reproduce Chromium's 409 network error"
        print("PASS: real HTTP 409, visible validation, and final diagnostics all verified")
finally:
    browser.close()
    server.shutdown()
    server.server_close()
