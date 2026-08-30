# Response Helpers: one clear HTTP responsibility.
class ResponseHelpersMixin:
    """Keep response helpers behavior together."""

    # Purpose: Prepare this object with the state it needs.
    def __init__(self, *a, **k):
        self._no_cache = False

        super().__init__(*a, directory=str(BASE_DIR), **k)

    # Purpose: Handle log message for this focused step.
    def log_message(self, *a): pass

    # Purpose: Handle end headers for this focused step.
    def end_headers(self):

        if self._no_cache:
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self._no_cache = False
        super().end_headers()

    # Purpose: Handle do OPTIONS for this focused step.
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", "0")
        self.end_headers()

    # Purpose: Handle JSON for this focused step.
    def _json(self, payload, code=200):
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    # Purpose: (is_ours, path_without_the_prefix). See AGENTFORGE_PREFIX.
    def _split(self):
        """(is_ours, path_without_the_prefix). See AGENTFORGE_PREFIX."""
        path = urlsplit(self.path).path
        if path == AGENTFORGE_PREFIX or path.startswith(AGENTFORGE_PREFIX + "/"):
            return True, path[len(AGENTFORGE_PREFIX):] or "/"
        return False, path

    # Purpose: Handle is websocket for this focused step.
    def _is_websocket(self) -> bool:
        return ("upgrade" in self.headers.get("Connection", "").lower()
                and self.headers.get("Upgrade", "").lower() == "websocket")

    # Purpose: There is no UI on this port any more — say so, and point at the one.
    def _serve_ui(self, path):
        """There is no UI on this port any more — say so, and point at the one.

        This used to serve a single-file HTML app out of `ui/`, which the
        Electron shell loaded. Both are gone: the studio is the UI, it runs on
        its own port, and it reaches this server only for `/__agentforge/api/*`.

        A bare 404 here would be technically correct and completely unhelpful —
        the address still looks like the application's, so anyone who lands on
        it deserves to be told where the application went.
        """
        del path
        body = (
            "<!doctype html><meta charset=utf-8>"
            "<title>AgentForge</title>"
            "<body style=\"font:14px/1.6 system-ui;max-width:34rem;margin:12vh auto;"
            "padding:0 1.5rem;color:#e6e6e6;background:#111\">"
            "<h1 style=\"font-size:1.1rem\">AgentForge is not served on this port</h1>"
            f"<p>This is the backend API on :{UI_PORT}. The studio runs separately —"
            " <a style=\"color:#22d3ee\" href=\"http://localhost:3000/__agentforge\">"
            "http://localhost:3000/__agentforge</a></p>"
            "<p style=\"color:#888\">Start both with <code>start.bat</code>.</p>"
        ).encode()
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # Purpose: Handle plain for this focused step.
    def _plain(self, code, body: bytes, ctype="text/plain; charset=utf-8",
               extra=()):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    # Purpose: The dev server is not up. Documents get a page; assets fail fast.
    def _preview_unavailable(self):
        """The dev server is not up. Documents get a page; assets fail fast."""
        dest = self.headers.get("Sec-Fetch-Dest", "")
        wants_page = (dest in ("document", "iframe")
                      or "text/html" in self.headers.get("Accept", ""))
        if not wants_page:

            return self._plain(502, b"")
        page = (b"<!doctype html><meta charset=utf-8>"
                b"<title>Preview not running</title>"
                b"<style>body{font:14px system-ui;background:#0b0d10;color:#8b949e;"
                b"display:grid;place-items:center;height:100vh;margin:0}"
                b"b{color:#e6edf3;font-weight:600}</style>"
                b"<div style=text-align:center><p><b>Preview not running</b>"
                b"<p>Waiting for the dev server\xe2\x80\xa6"
                b"<p><button onclick=location.reload() style=\"font:inherit;"
                b"padding:6px 14px;border-radius:6px;border:1px solid #30363d;"
                b"background:#161b22;color:#e6edf3;cursor:pointer\">Retry</button>"
                b"</div><script>setTimeout(()=>location.reload(),2000)</script>")
        self._plain(503, page, "text/html; charset=utf-8",
                    extra=(("Retry-After", "2"), ("Cache-Control", "no-store")))
