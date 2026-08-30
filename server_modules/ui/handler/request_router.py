# Request Router: one clear HTTP responsibility.
class RequestRouterMixin:
    """Keep request router behavior together."""

    # Purpose: Handle do GET for this focused step.
    def do_GET(self):
        ours, path = self._split()
        if not ours:
            if self._is_websocket():
                return self._proxy_websocket()

            if path == "/" and self.headers.get("Sec-Fetch-Dest") == "document":
                self.send_response(302)
                self.send_header("Location", AGENTFORGE_PREFIX + "/")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            return self._proxy("GET")
        if path.startswith("/api/"):
            return self._guarded(self._api_get, path[4:])
        return self._serve_ui(path)

    # Purpose: Handle do HEAD for this focused step.
    def do_HEAD(self):
        ours, path = self._split()
        if not ours:
            return self._proxy("HEAD")

        del path
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", "0")
        self.end_headers()

    # Purpose: Handle do PUT for this focused step.
    def do_PUT(self):     self._proxy_or_405("PUT")

    # Purpose: Handle do PATCH for this focused step.
    def do_PATCH(self):   self._proxy_or_405("PATCH")

    # Purpose: Handle do DELETE for this focused step.
    def do_DELETE(self):  self._proxy_or_405("DELETE")

    # Purpose: Handle proxy or 405 for this focused step.
    def _proxy_or_405(self, method):
        ours, _ = self._split()
        if ours:
            return self._json({"error": "method not allowed"}, 405)
        self._proxy(method)

    # Purpose: Handle do POST for this focused step.
    def do_POST(self):
        ours, path = self._split()
        if not ours:
            return self._proxy("POST")

        length = int(self.headers.get("Content-Length", 0) or 0)
        self._raw = self.rfile.read(length) if length else b""
        if not path.startswith("/api/"):
            return self._json({"error": "not found"}, 404)
        self._guarded(self._api_post, path[4:])

    # Purpose: Run an API branch and turn a crash into an answer.
    def _guarded(self, fn, path):
        """
        Run an API branch and turn a crash into an answer.

        Without this, an exception anywhere in a handler unwinds into
        `BaseHTTPRequestHandler`, which sends a 500 with an EMPTY body. The
        browser shows "HTTP 500" and that is the entire diagnosis available to
        anybody — measured on the logo panel, where a failed draw said exactly
        that and nothing else, on a machine where the image host had been up
        thirty seconds earlier.

        The traceback goes to the log and the message goes to the caller. An
        API that falls over should still be able to say what it fell over.
        """
        try:
            fn(path)
        except Exception as e:
            log.exception(f"api {path}")
            elog("WARN", f"   ⚠ {path} failed: {type(e).__name__}: {e}")
            try:
                self._json({"error": f"{type(e).__name__}: {e}"}, 500)
            except Exception:
                pass

    # Purpose: Handle body for this focused step.
    def _body(self) -> dict:
        if not self._raw:
            return {}
        try:
            return json.loads(self._raw)
        except Exception:
            return {}
