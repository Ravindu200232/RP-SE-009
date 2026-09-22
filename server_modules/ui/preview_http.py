"""Stable project origins and the local preview bridge (shared namespace)."""
PREVIEW_PATH = "/__agentforge/preview"


def studio_origins():
    """The pages a preview may be framed by and talk to.

    This machine's studio addresses, and the address a studio was opened at
    when it asked for this preview to be published (core/preview_runtime.py).
    """
    return [f"http://{host}:{port}" for host in ("localhost", "127.0.0.1")
            for port in (3000, UI_PORT)] + sorted(STUDIO_ORIGINS)


def preview_origins(runtime):
    """The addresses this preview itself answers on."""
    state = RUNTIMES.snapshot(runtime)
    return [url.rstrip("/") for url in (state["previewUrl"], state.get("publicUrl")) if url]


class PreviewHTTPMixin:
    def _on_preview_host(self):
        host = self.headers.get("Host", "").split(":", 1)[0].lower()
        return host.startswith("p-") and host.endswith(".localhost")

    def _preview_request(self, method):
        runtime = runtime_from_host(self.headers.get("Host", ""))
        if runtime is None:
            return self._plain(404, b"No such project")
        path = urlsplit(self.path).path
        if path == PREVIEW_PATH + "/status" and method == "GET":
            return self._json(RUNTIMES.snapshot(runtime))
        if path == PREVIEW_PATH + "/bridge.js" and method == "GET":
            return self._preview_bridge(runtime)
        if path in (PREVIEW_PATH + "/activity", PREVIEW_PATH + "/start") and method == "POST":
            if self.headers.get("Origin") not in preview_origins(runtime):
                return self._plain(403, b"Invalid preview origin")
            length = int(self.headers.get("Content-Length", 0) or 0)
            self._raw = self.rfile.read(length) if length else b""
            body = self._body()
            if path.endswith("/activity"):
                return self._json({"ok": RUNTIMES.activity(runtime, body.get("runtimeId"))})
            return self._json(_open_project(runtime.project))
        # Generated origins never expose Studio's project/edit/delete API.
        if path.startswith(AGENTFORGE_PREFIX + "/"):
            return self._plain(404, b"Unknown preview endpoint")
        if self._is_websocket():
            return self._proxy_websocket(runtime)
        navigation = method == "GET" and self.headers.get("Sec-Fetch-Mode") == "navigate"
        user_navigation = navigation and self.headers.get("Sec-Fetch-User") == "?1"
        if user_navigation:
            _open_project(runtime.project)
        if runtime.status != "running":
            if navigation:
                return self._preview_waiting(runtime)
            return self._plain(503, b"Preview is stopped", extra=(("Cache-Control", "no-store"),))
        return self._forward_preview(method, runtime)

    def _preview_bridge(self, runtime):
        query = parse_qs(urlsplit(self.path).query)
        if query.get("runtimeId", [""])[0] != runtime.runtime_id:
            return self._plain(410, b"", "text/javascript")
        config = {"project": runtime.project, "runtimeId": runtime.runtime_id,
                  "parents": studio_origins(), "path": PREVIEW_PATH}
        pieces = ["(() => {", "const config = " + json.dumps(config) + ";"]
        # Share the existing picker and console implementations with the
        # injected frame code, rather than maintaining two serializers.
        for relative in ("studio/lib/picker.js", "studio/lib/console-capture.js",
                         "server_modules/ui/preview_bridge.js"):
            source = (BASE_DIR / relative).read_text("utf-8")
            pieces.append(source.replace("export function ", "function "))
        pieces.append("})();")
        self._plain(200, "\n".join(pieces).encode(), "text/javascript; charset=utf-8",
                    extra=(("Cache-Control", "no-store"),))

    def _preview_waiting(self, runtime):
        state = RUNTIMES.snapshot(runtime)
        # Status polling only observes: it must never extend the idle lease or
        # restart a failed process. The retry button is an explicit user action.
        body = ("<!doctype html><html><head><meta charset=utf-8><title>App preview</title>"
                "<style>body{font:15px system-ui;background:#f5f7fb;color:#243047;display:grid;"
                "place-items:center;min-height:100vh;margin:0}main{max-width:34rem;padding:2rem;text-align:center}"
                "button{font:inherit;padding:.7rem 1.4rem;cursor:pointer}p{line-height:1.6}</style>"
                "</head><body><main><h1 id=title>Starting app…</h1><p id=detail></p>"
                "<button id=retry hidden>Start app</button></main><script>"
                f"const initial={json.dumps(state).replace('<', chr(92) + 'u003c')};"
                f"const endpoint={json.dumps(PREVIEW_PATH)};"
                "const title=document.getElementById('title'),detail=document.getElementById('detail'),"
                "retry=document.getElementById('retry');"
                "function show(s){if(s.status==='running'){location.replace(location.href);return}"
                "title.textContent=s.working?'Build in progress':s.status==='starting'?'Starting app…':"
                "s.status==='failed'?'App could not start':'App stopped';"
                "detail.textContent=s.error||(s.reason==='idle'?'Stopped after 10 minutes without activity.':"
                "s.working?'The preview will open when the build is ready.':'');"
                "retry.hidden=s.status==='starting'||s.working;"
                "if(s.status==='starting'||s.working)setTimeout(poll,700)}"
                "async function poll(){try{show(await(await fetch(endpoint+'/status',{cache:'no-store'})).json())}"
                "catch{title.textContent='AgentForge is unavailable';retry.hidden=false}}"
                "retry.onclick=async()=>{retry.hidden=true;try{show(await(await fetch(endpoint+'/start',"
                "{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})).json())}"
                "catch{title.textContent='Could not start app';retry.hidden=false}};show(initial);"
                "</script></body></html>").encode()
        self._plain(200, body, "text/html; charset=utf-8", extra=(("Cache-Control", "no-store"),))

    def _forward_preview(self, method, runtime):
        with runtime.lock:
            if not runtime.port or runtime.status != "running":
                return self._plain(503, b"Preview is stopped")
            port, runtime_id = runtime.port, runtime.runtime_id
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length and self.headers.get("Transfer-Encoding"):
            return self._plain(411, b"chunked request bodies are not proxied")
        body = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP}
        headers.update({"X-Forwarded-Host": self.headers.get("Host", ""),
                        "X-Forwarded-Proto": "http", "X-Forwarded-For": "127.0.0.1",
                        "Accept-Encoding": "identity"})
        response = None
        try:
            response = requests.request(method, f"http://127.0.0.1:{port}{self.path}",
                                        headers=headers, data=body, stream=True,
                                        allow_redirects=False, timeout=(2, 300))
        except requests.RequestException:
            try:
                response = requests.request(method, f"http://localhost:{port}{self.path}",
                                            headers=headers, data=body, stream=True,
                                            allow_redirects=False, timeout=(2, 300))
            except requests.RequestException:
                return self._plain(503, b"Preview is unavailable")
        is_html = "text/html" in response.headers.get("Content-Type", "").lower()
        nonce = uuid.uuid4().hex
        self.send_response(response.status_code)
        for key, value in response.raw.headers.items():
            lower = key.lower()
            if lower in HOP_BY_HOP or lower in {"content-encoding", "content-length"}:
                continue
            if lower in {"etag", "content-md5", "x-frame-options"}:
                continue
            if lower == "content-security-policy" and is_html:
                directives = []
                seen = set()
                for part in value.split(";"):
                    words = part.strip().split()
                    if not words:
                        continue
                    seen.add(words[0])
                    if words[0] in ("script-src", "script-src-elem"):
                        words = [word for word in words if word != "'none'"] + [f"'nonce-{nonce}'"]
                    if words[0] == "frame-ancestors":
                        words = [word for word in words if word != "'none'"] + studio_origins()
                    directives.append(" ".join(words))
                if "script-src" not in seen:
                    directives.append(f"script-src 'self' 'nonce-{nonce}'")
                value = "; ".join(directives)
            if lower == "set-cookie":
                # Use partitioned cookies to maintain session authentication across Studio preview iframes.
                value = re.sub(r";\s*(?:SameSite|Domain)=[^;]*", "", value, flags=re.I)
                if not re.search(r";\s*Secure(?:;|$)", value, re.I):
                    value += "; Secure"
                if not re.search(r";\s*Partitioned(?:;|$)", value, re.I):
                    value += "; Partitioned"
                value += "; SameSite=None"
            if lower == "location":
                value = re.sub(rf"^http://(?:localhost|127\.0\.0\.1):{port}(?=/|$)",
                               RUNTIMES.snapshot(runtime)["previewUrl"].rstrip("/"), value)
            self.send_header(key, value)
        self.send_header("Connection", "close")
        if is_html:
            self.send_header("Cache-Control", "no-store")
        self.close_connection = True
        self.end_headers()
        try:
            if method == "HEAD":
                return
            script = (f'<script nonce="{nonce}" src="{PREVIEW_PATH}/bridge.js?runtimeId={runtime_id}"></script>').encode()
            buffer, inserted = b"", not is_html
            for chunk in response.raw.stream(65536, decode_content=True):
                if not inserted:
                    buffer += chunk
                    head = re.search(br"<head(?:\s[^>]*)?>", buffer, re.I)
                    if head:
                        chunk = buffer[:head.end()] + script + buffer[head.end():]
                    elif len(buffer) < 262144:
                        continue
                    else:
                        chunk = buffer + script
                    buffer, inserted = b"", True
                self.wfile.write(chunk)
                self.wfile.flush()
            if buffer:
                self.wfile.write(buffer + script)
        except (OSError, requests.RequestException):
            pass
        finally:
            response.close()
