# Routes AgentForge UI and API requests.

# Everything else here comes from the runtime parts executed before this one;
# only real modules are imported.
from server_modules.services.shots import capture_drawing, capture_element, port_for
from server_modules.builder.theme_preview import read_preview as read_theme_preview
from server_modules.builder.theme_preview import render_preview as render_theme_preview
from urllib.parse import parse_qs, unquote


class UIHandler(PreviewHTTPMixin, SimpleHTTPRequestHandler):

    protocol_version = "HTTP/1.1"

    def __init__(self, *a, **k):
        self._no_cache = False

        super().__init__(*a, directory=str(BASE_DIR), **k)

    def log_message(self, *a): pass

    def end_headers(self):

        if self._no_cache:
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self._no_cache = False
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _json(self, payload, code=200, extra=()):
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _split(self):
        """(is_ours, path_without_the_prefix). See AGENTFORGE_PREFIX."""
        path = urlsplit(self.path).path
        if path == AGENTFORGE_PREFIX or path.startswith(AGENTFORGE_PREFIX + "/"):
            return True, path[len(AGENTFORGE_PREFIX):] or "/"
        return False, path

    def _is_websocket(self) -> bool:
        return ("upgrade" in self.headers.get("Connection", "").lower()
                and self.headers.get("Upgrade", "").lower() == "websocket")

    def do_GET(self):
        # One connection carries many requests: a POST's body is not this GET's.
        self._raw = b""
        if self._on_preview_host():
            return self._preview_request("GET")
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
            return self._guarded(self._api, path[4:])
        return self._serve_ui(path)

    def do_HEAD(self):
        if self._on_preview_host():
            return self._preview_request("HEAD")
        ours, path = self._split()
        if not ours:
            return self._proxy("HEAD")

        del path
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_PUT(self):     self._proxy_or_405("PUT")
    def do_PATCH(self):   self._proxy_or_405("PATCH")
    def do_DELETE(self):  self._proxy_or_405("DELETE")

    def _proxy_or_405(self, method):
        if self._on_preview_host():
            return self._preview_request(method)
        ours, _ = self._split()
        if ours:
            return self._json({"error": "method not allowed"}, 405)
        self._proxy(method)

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

    def _api(self, path):
        """Every API request is signed in, and checked before it is answered (access.py)."""
        if path.startswith("/auth/"):
            return self._auth(path[5:])
        user = request_user(self.headers)
        if user is None:
            return self._json({"error": "sign in to continue", "auth": "required"}, 401)
        _, from_cookie = session_token(self.headers)
        if from_cookie and self.command != "GET" and not trusted(self.headers):
            return self._json({"error": "that request did not come from the studio"}, 403)
        kind, key = access_rule(self.command, path, self._body())
        if not may(user, kind, key):
            if kind == "run" and self.command == "GET":
                return self._json({"pending": []})   # someone else's build asks them nothing
            # Someone else's things are not there, as far as anyone else can tell.
            hidden = kind in ("project", "srs", "job", "srs-job", "deploy-run", "deploy-job",
                              "project-path", "run")
            return self._json({"error": "not found" if hidden else "only the admin can do that"},
                              404 if hidden else 403)
        act_as(user)
        try:
            return (self._api_get if self.command == "GET" else self._api_post)(path)
        finally:
            act_as(None)

    def _studio_origin(self) -> str:
        """The address the studio itself was opened at, as this request arrived."""
        host = studio_host(self.headers)
        return f"{'https' if self._https() else 'http'}://{host}" if host else ""

    def _https(self) -> bool:
        """Did the browser reach the studio over HTTPS? Behind a proxy, it says so."""
        return (str(self.headers.get("X-Forwarded-Proto", ""))
                .split(",")[0].strip().lower() == "https")

    def _auth(self, path):
        """Sign up, sign in, sign out, and who is signed in."""
        secure = self._https()
        token, _ = session_token(self.headers)
        if path == "/me" and self.command == "GET":
            user = auth_db.get_user_by_token(token)
            if user is None:
                return self._json({"error": "sign in to continue", "auth": "required"}, 401)
            # Signed in by the header alone, the frames and the socket still need the cookie.
            return self._json({"ok": True, "user": user},
                              extra=(("Set-Cookie", session_cookie(token, secure=secure)),))
        if self.command != "POST":
            return self._json({"error": "method not allowed"}, 405)
        if not trusted(self.headers):
            return self._json({"error": "that request did not come from the studio"}, 403)
        body = self._body()
        if path == "/logout":
            auth_db.logout_user(token)
            return self._json({"ok": True},
                              extra=(("Set-Cookie", session_cookie("", secure=secure)),))
        if path == "/signup":
            result = auth_db.signup_user(username=body.get("username", ""),
                                         email=body.get("email", ""),
                                         password=body.get("password", ""),
                                         name=body.get("name", ""))
        elif path == "/login":
            result = auth_db.login_user(
                login=body.get("login") or body.get("email") or body.get("username", ""),
                password=body.get("password", ""))
        else:
            return self._json({"error": f"unknown endpoint /auth{path}"}, 404)
        if result.get("error"):
            return self._json(result, 400)
        return self._json(result, extra=(
            ("Set-Cookie", session_cookie(result["token"], secure=secure)),))

    def _api_get(self, path):
        if path.startswith("/runtime/"):
            try:
                return self._json(RUNTIMES.snapshot(runtime_for(unquote(path[9:]))))
            except ValueError as error:
                return self._json({"error": str(error)}, 404)

        if path.startswith("/srs/"):
            return self._proxy_srs("GET", path[4:])
        if path == "/srs-status":
            return self._json(srs_status())

        if path.startswith("/jobs/"):
            return self._json(job_poll(path[len("/jobs/"):]))

        if path.startswith("/deploy/jobs/"):
            try:
                return self._json(deploy_job_poll(path[13:].strip("/")))
            except KeyError as e:
                return self._json({"error": str(e)}, 404)
        if path.startswith("/deploy/"):
            return self._deploy_for_user("GET", "/api" + path[7:])
        if path == "/deploy-status":
            return self._json(deploy_status())
        if path.startswith("/deploy-results/"):
            return self._json(read_deploy_results(path[16:].strip("/")))
        if path == "/projects":
            # Only this person's. Nothing is handed to anyone for having none yet.
            return self._json([p for p in list_projects() if visible_project(p["name"])])
        elif path == "/image-check":

            agent = image_agent()
            host = agent.base_url()
            launcher = _fooocus_launcher()

            import socket
            lan = ""
            if load_settings().get("lan_access"):
                try:
                    lan = f"http://{socket.gethostbyname(socket.gethostname())}:{UI_PORT}"
                except OSError:
                    lan = ""
            self._json({"enabled": agent.enabled, "available": bool(host),
                        "host": host or "", "lan_url": lan,
                        "launcher": launcher,
                        "can_start": bool(launcher and not host),
                        "lan_access": bool(load_settings().get("lan_access"))})
        elif path == "/models":

            self._json(ollama.catalog())
        elif path == "/settings":
            s = load_settings()
            key = ollama.api_key
            uri = str(s.get("mongodb_uri", "")).strip()
            self._json(shared_settings({
                "ollama_host": ollama.host,
                "cloud_enabled": ollama.cloud_ready(),
                "cloud_via": ("api-key" if key
                              else "signed-in" if ollama.signed_in() else "none"),
                "ollama_ready": ollama.daemon_ready(),

                "api_key_hint": (f"…{key[-4:]}" if key else ""),
                "local_num_ctx": s.get("local_num_ctx", max_context("llama3.1:8b")),
                "agent_model": s.get("agent_model", default_agent_model()),
                "agent_think": bool(s.get("agent_think", True)),
                **_image_settings(),
                "mongodb_uri_set": bool(uri),
                "mongodb_uri_hint": _redact_uri(uri),
                "mongo": MONGO.status(),

                "deploy": {},
            }))
        elif path == "/mongo":
            self._json(MONGO.status())
        elif path.startswith("/files/"):
            role = parse_qs(urlsplit(self.path).query).get("agent", ["developer"])[0]
            self._json(get_project_files(path[7:].strip("/"), role))
        elif path.startswith("/workflow/"):
            _, project_dir, error = _owned_dir(PROD_DIR, path[10:].strip("/"), "project name", "project")
            self._json({"error": error}, 404) if error else self._json({**ProjectState(project_dir).snapshot(), "build_available": build_available(project_dir)})
        elif path.startswith("/stream/"):
            self._json({"stream": read_stream(path[8:].strip("/"))})
        elif path.startswith("/session/"):
            self._json({"stats": session_stats(path[9:].strip("/"))})
        elif path == "/plugins":
            # Returns plugin catalog, category groups, and masked credentials summary for current user.
            from server_modules.builder.plugins import catalog, groups, summary_for
            user = acting() or {}
            self._json({"plugins": catalog(), "groups": groups(),
                        "saved": summary_for(user.get("id", "")) if user else []})
        elif path.startswith("/plugins/project/"):
            from server_modules.builder.plugins import enabled_for
            _, project_dir, error = _owned_dir(PROD_DIR, path[17:].strip("/"),
                                               "project name", "project")
            self._json({"error": error}, 404) if error else \
                self._json({"enabled": enabled_for(project_dir)})
        elif path == "/decisions":
            self._json({"pending": pending_decisions()})
        elif path.startswith("/qa-screenshot/"):
            query = parse_qs(urlsplit(self.path).query)
            try:
                data, kind = read_qa_screenshot(unquote(path[15:].strip("/")),
                                                query.get("path", [""])[0])
                self._plain(200, data, kind, extra=(("Cache-Control", "no-cache"),))
            except (OSError, ValueError):
                self._json({"error": "Screenshot not found"}, 404)
        elif path.startswith("/site-image/"):
            proj, _, name = unquote(path[12:].strip("/")).partition("/")
            try:
                data, kind = read_site_image(proj, name)
                self._plain(200, data, kind, extra=(("Cache-Control", "no-cache"),))
            except ValueError as error:
                self._json({"error": str(error)}, 400)
            except (FileNotFoundError, OSError):
                self._json({"error": "No such image"}, 404)
        elif path.startswith("/project-wireframes/"):
            # A built project reads its adopted copy. The SRS agent serves the
            # staged one by specification id; this serves the same file for a
            # project that now has a name of its own.
            self._json(read_project_wireframes(unquote(path[20:].strip("/"))))
        elif path.startswith("/change-requests/"):
            project = unquote(path[17:].strip("/"))
            _, project_dir, error = _owned_dir(PROD_DIR, project, "project name", "project")
            if error:
                self._json({"error": error}, 404)
            else:
                from server_modules.services.change_requests import list_for
                self._json({"requests": list_for(project_dir)})
        elif path.startswith("/site-images/"):
            self._json(site_image_list(unquote(path[13:].strip("/"))))
        elif path.startswith("/design-theme-preview/"):
            try:
                self._plain(200, read_theme_preview(path[22:].strip("/")), "text/html; charset=utf-8",
                            extra=(("Cache-Control", "no-cache"),))
            except ValueError as error:
                self._json({"error": str(error)}, 400)
            except (FileNotFoundError, OSError):
                self._json({"error": "not drawn yet", "drawn": False}, 404)
        elif path.startswith("/prototype/"):
            proj, _, rel = path[11:].strip("/").partition("/")
            try:
                body, kind = read_prototype(proj, rel)
                self._plain(200, body, kind, extra=(("Cache-Control", "no-cache"),))
            except ValueError as error:
                self._json({"error": str(error)}, 400)
            except (FileNotFoundError, OSError) as error:
                rel_clean = (rel or "index.html").strip("/")
                if rel_clean == "index.html" or rel_clean.endswith(".html"):
                    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="2">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Generating Prototype · AgentForge</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: radial-gradient(circle at 50% 20%, #171c2e 0%, #0c0f17 60%, #07090f 100%);
      color: #f8fafc;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      padding: 24px;
      overflow: hidden;
    }}
    .glow {{
      width: 64px; height: 64px;
      border-radius: 18px;
      background: rgba(168, 85, 247, 0.12);
      border: 1px solid rgba(168, 85, 247, 0.25);
      box-shadow: 0 0 40px rgba(168, 85, 247, 0.25);
      display: flex; align-items: center; justify-content: center;
      margin-bottom: 20px;
      position: relative;
    }}
    .spinner {{
      width: 32px; height: 32px;
      border: 3px solid rgba(168, 85, 247, 0.2);
      border-top-color: #a855f7;
      border-radius: 50%;
      animation: spin 0.9s linear infinite;
    }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    h2 {{ font-size: 18px; font-weight: 700; letter-spacing: -0.01em; margin-bottom: 8px; color: #fff; }}
    p {{ font-size: 13px; color: #94a3b8; max-width: 360px; line-height: 1.5; }}
    .badge {{
      margin-top: 18px;
      display: inline-flex; align-items: center; gap: 8px;
      padding: 6px 14px;
      border-radius: 9999px;
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid rgba(255, 255, 255, 0.1);
      font-family: monospace; font-size: 12px; color: #cbd5e1;
    }}
    .dot {{
      width: 7px; height: 7px; border-radius: 50%; background: #a855f7;
      animation: pulse 1.5s ease-in-out infinite;
    }}
    @keyframes pulse {{ 0%, 100% {{ opacity: 1; transform: scale(1); }} 50% {{ opacity: 0.4; transform: scale(0.85); }} }}
  </style>
</head>
<body>
  <div class="glow">
    <div class="spinner"></div>
  </div>
  <h2>Generating HTML Prototype…</h2>
  <p>Designing interactive wireframes, layouts, and responsive components.</p>
  <div class="badge">
    <span class="dot"></span>
    <span>{proj}</span>
  </div>
</body>
</html>"""
                    self._plain(200, html.encode("utf-8"), "text/html; charset=utf-8", extra=(("Cache-Control", "no-cache"),))
                else:
                    self._json({"error": str(error)}, 404)
        elif path.startswith("/qa/"):
            self._json(read_qa_results(path[4:].strip("/")))
        elif path.startswith("/srs-results/"):
            self._json(read_srs_results(path[13:].strip("/")))
        elif path.startswith("/qa-pdf/"):

            proj = path[8:].strip("/")
            qa = read_qa_results(proj)
            if qa.get("error"):
                return self._json(qa, 404)
            try:
                out = (PROD_DIR / proj / ".agentforge" / "qa"
                       / "Test_Report.pdf")
                build_qa_pdf(qa, out, project=proj)
                self._plain(200, out.read_bytes(), "application/pdf",
                            extra=(("Content-Disposition",
                                    f'attachment; filename="{proj}-test-report.pdf"'),))
            except Exception as e:                              # noqa: BLE001
                log.exception("qa pdf")
                self._json({"error": f"the test report could not be built: {e}"}, 500)
        elif path.startswith("/srs-pdf/"):

            pdf = (PROD_DIR / path[9:].strip("/") / ".agentforge" / "srs"
                   / "SRS_latest.pdf")
            if pdf.is_file():
                self._plain(200, pdf.read_bytes(), "application/pdf",
                            extra=(("Content-Disposition",
                                    'inline; filename="SRS.pdf"'),))
            else:
                self._json({"error": "no SRS PDF for this project"}, 404)
        else:
            self._json({"error": f"unknown endpoint {path}"}, 404)

    def do_POST(self):
        if self._on_preview_host():
            return self._preview_request("POST")
        ours, path = self._split()
        if not ours:
            return self._proxy("POST")

        length = int(self.headers.get("Content-Length", 0) or 0)
        self._raw = self.rfile.read(length) if length else b""
        if not path.startswith("/api/"):
            return self._json({"error": "not found"}, 404)
        self._guarded(self._api, path[4:])

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
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError) as e:
            # The caller navigated away or reloaded while we were answering.
            # Nothing failed, there is nobody left to tell, and putting it in
            # the chat stream reads like the run broke.
            log.debug(f"api {path}: caller hung up ({e})")
        except Exception as e:
            log.exception(f"api {path}")
            elog("WARN", f"   ⚠ {path} failed: {type(e).__name__}: {e}")
            try:
                self._json({"error": f"{type(e).__name__}: {e}"}, 500)
            except Exception:
                pass

    _raw = b""

    def _body(self) -> dict:
        if not self._raw:
            return {}
        try:
            return json.loads(self._raw)
        except Exception:
            return {}

    def _api_post(self, path):
        if path == "/design-theme-preview":
            body = self._body()
            try:
                render_theme_preview(body.get("slug", ""), body.get("model", ""))
                return self._json({"ok": True, "slug": body.get("slug", "")})
            except (ValueError, FileNotFoundError) as error:
                return self._json({"error": str(error)}, 400)
            except Exception as error:  # noqa: BLE001 - a draw that fails is an answer
                return self._json({"error": f"The preview could not be drawn: {error}"}, 502)
        if path.startswith("/runtime/") and path.endswith("/activity"):
            try:
                runtime = runtime_for(unquote(path[9:-9]))
                return self._json({"ok": RUNTIMES.activity(runtime, self._body().get("runtimeId"))})
            except ValueError as error:
                return self._json({"error": str(error)}, 404)

        if path.startswith("/srs/"):
            return self._proxy_srs("POST", path[4:])

        if path == "/jobs":
            body = self._body()
            try:
                return self._json(job_start(
                    str(body.get("method", "POST")).upper(),
                    str(body.get("path", "")),
                    body.get("body") or {},
                    headers=self._forward_auth()))
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
        if path == "/deploy/jobs":
            return self._deploy_job_for_user(self._body())
        if path.startswith("/deploy/"):
            return self._deploy_for_user("POST", "/api" + path[7:])
        if path == "/deploy-start":
            body = self._body()
            try:
                return self._json(start_deployment(
                    str(body.get("project", "")).strip(),
                    str(body.get("target", "vercel")).strip(),
                    body))
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
        if path == "/discard-srs":
            sid = str(self._body().get("srs_id", "")).strip()
            out = discard_srs(sid)
            return self._json(out, 400 if out.get("error") else 200)
        if path == "/keep-srs":
            sid = str(self._body().get("srs_id", "")).strip()
            out = keep_srs(sid)
            return self._json(out, 400 if out.get("error") else 200)
        if path == "/decision":
            body = self._body()
            out = resolve_decision(str(body.get("id", "")), body)
            return self._json(out, 404 if out.get("error") else 200)
        if path == "/build/cancel":
            # Their own run, or their place in the line - never someone else's build.
            body = self._body()
            return self._json(*cancel_mine(str(body.get("project") or ""), str(body.get("agent") or "")))
        if path == "/sync/retry":
            result = retry_project_sync(str(self._body().get("project") or ""))
            return self._json(result, 400 if result.get("error") else 200)
        if path == "/change-requests/draft":
            body = self._body()
            project = str(body.get("project", "")).strip()
            _, directory, error = _owned_dir(PROD_DIR, project, "project name", "project")
            if error:
                return self._json({"error": error}, 404)
            try:
                from server_modules.services.change_requests import create
                record = create(directory, prompt=body.get("prompt", ""), kind=body.get("kind", "srs"),
                                targets=body.get("targets") or (), srs_version=body.get("srs_version"),
                                design_spec_version=body.get("design_spec_version"),
                                summary=body.get("summary") or (),
                                owner=(acting() or {}).get("id", ""))
                return self._json({"request": record})
            except ValueError as error:
                return self._json({"error": str(error)}, 400)
        if path.startswith("/change-requests/") and path.endswith("/approve"):
            body = self._body()
            project = str(body.get("project", "")).strip()
            request_id = path[17:-8].strip("/")
            _, directory, error = _owned_dir(PROD_DIR, project, "project name", "project")
            if error:
                return self._json({"error": error}, 404)
            try:
                from server_modules.services.change_requests import approve, read
                record = read(directory, request_id)
                wanted = [str(role) for role in (body.get("targets") or [])
                          if str(role) in ("designer", "developer")]
                if any(role not in set(record.get("requested_targets") or ()) for role in wanted):
                    return self._json({"error": "That deliverable was not part of this change request"}, 400)
                missing = [role for role in wanted if not artifact_exists(directory, role)]
                if missing:
                    return self._json({"error": f"This project has no {' or '.join(missing)} artifact to update"}, 400)
                approved = approve(directory, request_id, wanted)
                start_run(run_spec_change, (project, approved["prompt"], wanted, request_id), project=project)
                return self._json({"ok": True, "request": approved})
            except ValueError as error:
                return self._json({"error": str(error)}, 400)
        if path == "/resume":
            body = {**self._body(), "type": "agent_resume"}
            job = _message_job(body)
            if not job:
                return self._json({"error": "A valid project and request are required"}, 400)
            denied = job_denied(body, acting())
            if denied:
                return self._json({"error": denied}, 403)
            start_run(job[0], job[1])
            self._json({"ok": True})
        elif path == "/delete-project":
            body = self._body()
            out = delete_project(str(body.get("project", "")))
            self._json(out, 400 if out.get("error") else 200)
        elif path == "/save-file":
            body = self._body()
            out = save_project_file(str(body.get("project", "")),
                                    str(body.get("path", "")),
                                    str(body.get("content", "")),
                                    change_summary=str(body.get("change_summary", "")))
            self._json(out, 400 if out.get("error") else 200)
        elif path == "/image-start":

            why = start_fooocus()
            if why:
                return self._json({"error": why}, 503)
            self._json({"ok": True, "launcher": _fooocus_launcher()})
        elif path == "/logo-prompt":

            body = self._body()
            idea = str(body.get("prompt", "")).strip()
            if not idea:
                return self._json({"error": "prompt is required"}, 400)
            model = (body.get("model") or default_agent_model()).strip()
            try:
                r = ollama.chat(model, [
                    {"role": "system", "content": LOGO_PROMPT_SYSTEM},
                    {"role": "user", "content": idea[:1200]},
                ], options={"temperature": 0.7}, timeout=120)
                text = ((r.get("message") or {}).get("content") or "").strip()

                text = text.splitlines()[-1].strip().strip('"').strip("'")
            except Exception as e:
                log.debug(f"logo prompt: {e}")
                text = ""
            self._json({"ok": True, "prompt": text})
        elif path == "/tune":

            body = self._body()
            text = str(body.get("prompt", "")).strip()
            if not text:
                return self._json({"error": "prompt is required"}, 400)
            model = (body.get("model") or default_agent_model()).strip()
            element = body.get("element") or {}
            route = str(body.get("route") or element.get("route") or "/")
            tuned = tune_instruction(text, element, route, model)
            self._json({"ok": True, "prompt": tuned,
                        "changed": tuned.strip() != text.strip()})
        elif path == "/image":

            body = self._body()
            prompt = str(body.get("prompt", "")).strip()
            if not prompt:
                return self._json({"error": "prompt is required"}, 400)
            agent = image_agent()
            if not agent.enabled:
                return self._json({"error": "image generation is switched off"}, 409)
            if not agent.available():
                return self._json(
                    {"error": "no Fooocus is answering — start it, or set "
                              "image_host to the machine that runs it"}, 503)
            name = str(body.get("name", "")) or agent.slug(prompt)
            proj = str(body.get("project", "")).strip()
            out = ((PROD_DIR / proj / "public" / "generated") if proj
                   else (LOGS_DIR / "images")) / f"{name}.png"
            ok = agent.generate(prompt, out,
                                aspect=str(body.get("aspect", "landscape")),
                                seed=int(body.get("seed", 0) or 0),
                                force=bool(body.get("force")))
            if not ok:
                return self._json({"error": "generation failed"}, 502)

            self._json({"ok": True, "file": str(out), "name": name,
                        "data_uri": preview_uri(out),
                        "url": (f"/generated/{name}.png" if proj else "")})
        elif path == "/image-upload":

            body = self._body()
            name = _safe_stem(body.get("name") or body.get("filename"), "upload")
            proj = _safe_stem(body.get("project", ""), "")
            out = ((PROD_DIR / proj / "public" / "generated") if proj
                   else (LOGS_DIR / "images")) / f"{name}.png"

            why = save_uploaded_image(body.get("data_base64", ""), out)
            if why:
                return self._json({"error": why}, 400)

            self._json({"ok": True, "file": str(out), "name": name,
                        "data_uri": preview_uri(out),
                        "url": (f"/generated/{name}.png" if proj else "")})
        elif path == "/site-image-save":
            body = self._body()
            out = site_image_save(body.get("project", ""), body.get("filename", ""),
                                  body.get("data_base64", ""), str(body.get("purpose", "")))
            self._json(out, 400 if out.get("error") else 200)
        elif path == "/site-image-describe":
            body = self._body()
            out = site_image_describe(body.get("project", ""), body.get("file", ""),
                                      str(body.get("purpose", "")))
            self._json(out, 400 if out.get("error") else 200)
        elif path == "/site-image-drop":
            body = self._body()
            out = site_image_drop(body.get("project", ""), body.get("file", ""))
            self._json(out, 400 if out.get("error") else 200)
        elif path == "/agent-build":
            body = {**self._body(), "type": "agent_build"}
            job = _message_job(body)
            if not job:
                return self._json({"error": "A valid project and request are required"}, 400)
            denied = job_denied(body, acting())
            if denied:
                return self._json({"error": denied}, 403)
            start_run(job[0], job[1])
            self._json({"ok": True})
        elif path == "/element-edit":
            body = self._body()
            run_thread(
                target=run_element_edit,
                args=(body.get("project", ""), body.get("prompt", ""),
                      body.get("elements") or body.get("element") or {},
                      body.get("model") or default_agent_model(),
                      _think_flag(body), _browser_console(body),
                      body.get("shots") or [], (body.get("route") or "").strip()),
                daemon=True
            ).start()
            self._json({"ok": True})
        elif path == "/stream":
            body = self._body()
            self._json(write_stream(str(body.get("project") or ""),
                                    body.get("logs"), body.get("chat")))
        elif path == "/shot":
            # A picture of what they just clicked or drew on, for the message
            # they are about to send. Answered inline: the chip waits on it.
            body = self._body()
            strokes = body.get("strokes") or []
            route = str(body.get("route") or "/")
            if not route.startswith("/") or route.startswith("//"):
                return self._json({"error": "Invalid preview route"}, 400)
            try:
                runtime = runtime_for(body.get("project"))
            except ValueError as error:
                return self._json({"error": str(error)}, 404)
            prototype = route.startswith(AGENTFORGE_PREFIX + "/api/prototype/")
            if not prototype and (runtime.runtime_id != body.get("runtimeId") or runtime.status != "running"):
                return self._json({"error": "This preview has stopped or restarted"}, 409)
            port = port_for(route, app_port=runtime.port, studio_port=UI_PORT,
                            prefix=AGENTFORGE_PREFIX)
            if strokes:
                image = capture_drawing(route, viewport=body.get("viewport") or {},
                                        strokes=strokes, port=port)
            else:
                image = capture_element(route,
                                        viewport=body.get("viewport") or {},
                                        scroll=body.get("scroll") or {},
                                        rect=body.get("rect") or {},
                                        port=port)
            self._json({"ok": bool(image),
                        "image": f"data:image/jpeg;base64,{image}" if image else "",
                        "b64": image})
        elif path == "/attach":

            body = self._body()
            proj = _safe_stem(body.get("project", ""), "")
            proj_dir = (PROD_DIR / proj) if proj and (PROD_DIR / proj).is_dir() else None
            got = read_attachment(str(body.get("filename", "")),
                                  body.get("data_base64", ""), proj_dir)
            text = got["text"][:ATTACH_TEXT_CAP]
            if len(got["text"]) > ATTACH_TEXT_CAP:
                text += "\n… (the rest was left out to keep the prompt workable)"
            got["text"] = text
            self._json({"ok": True, **got})
        elif path == "/build-attach":

            body = self._body()
            out = stage_attachment(str(body.get("token", "")),
                                   str(body.get("filename", "")),
                                   body.get("data_base64", ""),
                                   str(body.get("purpose", "")))
            self._json(out, 400 if out.get("error") else 200)
        elif path == "/undo":
            body = self._body()
            self._json(restore_snapshot(body.get("project", ""),
                                        body.get("id", "")))
        elif path == "/feature":
            body = self._body()
            run_thread(
                target=run_feature,
                args=(body.get("project", ""),
                      body.get("prompt", ""),
                      body.get("model") or default_agent_model(),
                      _think_flag(body),
                      (body.get("qa_model") or "").strip(),
                      (body.get("route") or "").strip(),
                      _browser_console(body)),
                daemon=True
            ).start()
            self._json({"ok": True})
        elif path == "/spec-change":
            body = self._body()
            project = str(body.get("project", "")).strip()
            prompt = str(body.get("prompt", "")).strip()
            wanted = [str(role) for role in (body.get("targets") or [])
                      if str(role) in ("designer", "developer")]
            _, directory, error = _owned_dir(PROD_DIR, project, "project name", "project")
            if error or not prompt or not wanted:
                return self._json({"error": error or "A project, a change and something to "
                                                     "update are all required"}, 400)
            # Re-checked here rather than trusted from the browser: the studio
            # listed what existed when the page loaded, which may be a while ago.
            missing = [role for role in wanted if not artifact_exists(directory, role)]
            if missing:
                return self._json({"error": f"This project has no {' or '.join(missing)} "
                                            "artifact to update"}, 400)
            start_run(run_spec_change, (project, prompt, wanted), project=project)
            self._json({"ok": True})
        elif path == "/agent-update":
            body = {**self._body(), "type": "agent_update"}
            job = _message_job(body)
            if not job:
                return self._json({"error": "A valid project and request are required"}, 400)
            denied = job_denied(body, acting())
            if denied:
                return self._json({"error": denied}, 403)
            start_run(job[0], job[1])
            self._json({"ok": True})
        elif path == "/preview-link":
            # Give this project's app an address of its own, for a studio that
            # is not on this machine (preview_link.py).
            body = self._body()
            try:
                self._json(publish_preview(str(body.get("project", "")).strip(),
                                           self._studio_origin()))
            except ValueError as error:
                self._json({"error": str(error)}, 503)
        elif path.startswith("/open/"):
            try:
                self._json({"ok": True, **_open_project(unquote(path[6:].strip("/")))})
            except ValueError as error:
                self._json({"error": str(error)}, 404)
        elif path == "/projects/assign":
            # A new project is its builder's the moment it is made (pipeline.py).
            # This only confirms that - it never moves one.
            self._json({"ok": True})
        elif path == "/mongo/prefetch":
            threading.Thread(target=MONGO.prefetch, daemon=True).start()
            self._json({"ok": True})
        elif path in ("/cli-signin/start", "/cli-signin/poll", "/cli-signin/cancel"):
            # Vercel, Netlify and Azure have no device flow, so their own
            # `login` command drives the browser and this reads the credential
            # it leaves behind. `save_deploy_settings` is already in scope.
            from server_modules.deploy.cli_signin import SIGNINS
            body = self._body()
            user = acting() or {}
            if not user:
                return self._json({"error": "sign in to continue", "auth": "required"}, 401)
            try:
                if path.endswith("/start"):
                    self._json(SIGNINS.start(str(body.get("provider", ""))))
                elif path.endswith("/cancel"):
                    self._json(SIGNINS.cancel(str(body.get("flow_id", ""))))
                else:
                    answer = SIGNINS.poll(str(body.get("flow_id", "")))
                    if answer.get("status") == "ready":
                        patch = {answer.pop("setting"): answer.pop("value")}
                        answer["deploy"] = save_deploy_settings(user, patch)
                    self._json(answer)
            except ValueError as error:
                self._json({"error": str(error)}, 400)
        elif path == "/cli-signin/available":
            from server_modules.deploy.cli_signin import SIGNINS
            self._json({"providers": SIGNINS.available()})
        elif path in ("/plugins/save", "/plugins/forget"):
            # Saves or forgets user-level plugin credentials and returns a masked summary.
            from server_modules.builder.plugins import forget, save
            body = self._body()
            user = acting() or {}
            if not user:
                return self._json({"error": "sign in to continue", "auth": "required"}, 401)
            try:
                if path.endswith("/forget"):
                    saved = forget(user["id"], str(body.get("plugin", "")))
                else:
                    saved = save(user["id"], str(body.get("plugin", "")),
                                 str(body.get("mode", "")), body.get("values") or {})
                self._json({"saved": saved})
            except ValueError as error:
                self._json({"error": str(error)}, 400)
        elif path == "/plugins/project":
            # Which plugins one app uses. Writing this is the whole opt-in: the
            # next run merges their settings into that project's .env.local and
            # the model is given their skill pages to read.
            from server_modules.builder.plugins import set_enabled
            body = self._body()
            _, project_dir, error = _owned_dir(PROD_DIR, str(body.get("project", "")),
                                               "project name", "project")
            if error:
                return self._json({"error": error}, 404)
            enabled = set_enabled(project_dir, body.get("enabled") or [])
            _write_plugin_env(project_dir)
            self._json({"enabled": enabled})
        elif path in ("/github/device/start", "/github/device/poll"):
            # Initiates or polls GitHub device authorization flow and persists resulting credentials.
            from server_modules.deploy.github_device import FLOWS
            body = self._body()
            user = acting() or {}
            if not user:
                return self._json({"error": "sign in to continue", "auth": "required"}, 401)
            try:
                if path.endswith("/start"):
                    client_id = (str(body.get("client_id") or "").strip()
                                 or str(deploy_settings_for(user).get("github_client_id") or ""))
                    self._json(FLOWS.start(client_id))
                else:
                    answer = FLOWS.poll(str(body.get("flow_id", "")))
                    if answer.get("status") == "ready":
                        deploy = save_deploy_settings(user, {"github_token": answer.pop("token")})
                        answer["deploy"] = deploy
                    self._json(answer)
            except ValueError as error:
                self._json({"error": str(error)}, 400)
        elif path == "/settings":
            body = self._body()
            user = acting() or {}
            server_keys = ("ollama_api_key", "mongodb_uri", "ollama_host", "lan_access",
                           "image_enabled", "image_host", "image_config", "image_launcher",
                           "local_num_ctx", "agent_model", "agent_think")
            if any(key in body for key in server_keys) and not user.get("admin"):
                return self._json({"error": "only the admin can change AgentForge's own settings "
                                            "- your deployment accounts are under Deploy"}, 403)
            try:
                # Each person's deployment accounts are their own (deploy_tenancy.py).
                deploy = save_deploy_settings(user, body)
            except ValueError as error:
                return self._json({"error": str(error)}, 400)
            patch = {}
            if "ollama_api_key" in body:
                patch["ollama_api_key"] = str(body["ollama_api_key"]).strip()
            if "mongodb_uri" in body:
                patch["mongodb_uri"] = str(body["mongodb_uri"]).strip()
            if body.get("ollama_host"):
                patch["ollama_host"] = str(body["ollama_host"]).strip()
            if "lan_access" in body:
                patch["lan_access"] = bool(body["lan_access"])
            if "image_enabled" in body:
                patch["image_enabled"] = bool(body["image_enabled"])
            if "image_host" in body:
                patch["image_host"] = str(body["image_host"]).strip()
            if "image_config" in body:
                patch["image_config"] = str(body["image_config"]).strip()
            if "image_launcher" in body:
                patch["image_launcher"] = str(body["image_launcher"]).strip()
            if body.get("local_num_ctx"):
                try:
                    patch["local_num_ctx"] = max(4096, int(body["local_num_ctx"]))
                except (TypeError, ValueError):
                    pass
            if body.get("agent_model"):
                patch["agent_model"] = str(body["agent_model"]).strip()
            # One switch for the build's reasoning, saved rather than carried on
            # each request, so a run started from anywhere uses the same answer.
            if "agent_think" in body:
                patch["agent_think"] = bool(body["agent_think"])
            # agent_model is inherited across all agents (build, SRS, and deployment).
            # SRS keeps thinking off, while deployment connects to agent_think.
            ok = save_settings(patch) if patch else True
            if patch.get("ollama_host"):
                ollama.host = patch["ollama_host"].rstrip("/")
            self._json({"ok": ok, "deploy": deploy, "cloud_enabled": ollama.cloud_ready(),
                        "cloud_reachable": ollama.cloud_reachable()
                        if ollama.api_key else ollama.signed_in()})
        elif path == "/upload-project":
            body = self._body()
            name = body.get("name", "imported")
            files = body.get("files", {})

            pname = re.sub(r"[^a-z0-9]", "", name.lower())[:20] or "imported"
            # Never written into someone else's project for having the same name.
            if (PROD_DIR / pname).exists() and not visible_project(pname):
                pname = project_name_for(pname)
            if not claim_project(pname):
                return self._json({"error": "that name was taken a moment ago - try again"}, 409)
            proj_dir = PROD_DIR / pname
            proj_dir.mkdir(parents=True, exist_ok=True)

            for rel_path, content in files.items():
                fp = proj_dir / rel_path
                fp.parent.mkdir(parents=True, exist_ok=True)
                try:
                    fp.write_text(content, encoding="utf-8")
                except Exception as e:
                    log.error(f"Failed to write {rel_path}: {e}")

            self._json({"ok": True, "project": pname})
        else:
            self._json({"error": f"unknown endpoint {path}"}, 404)

    def _proxy(self, method: str):
        # Legacy root requests have no project identity. Never guess an app
        # from a global port or a different browser tab's last selection.
        return self._plain(503, b"Open a project from AgentForge to view its preview")

    def _proxy_srs(self, method: str, path: str):
        """
        Hand this request to the SRS agent on SRS_PORT.

        A near-copy of _proxy rather than a flag on it, because the two differ
        in the one place that decides whether this works at all: _proxy reads
        with a 300s timeout, and both an SRS generation and the event stream
        outlive that. A read timeout here does not slow anything down — it cuts
        the interview off mid-answer.

        `path` arrives with the /api and /srs prefixes already stripped, and
        without its query string: _split() drops it, so it is put back here.
        """
        if SRS_API["state"] in ("off", "import-failed"):
            return self._json({"error": "the SRS agent is not running",
                               "srs": srs_status()}, 503)

        if path == "/jobs" or path.startswith("/jobs/") or (path == "/projects" and method == "GET"):
            return self._proxy_srs_json(method, path)

        query = urlsplit(self.path).query
        url = f"http://127.0.0.1:{SRS_PORT}{path}" + (f"?{query}" if query else "")

        body = self._raw or None
        headers = {k: v for k, v in self.headers.items()
                   if k.lower() not in HOP_BY_HOP}
        headers["Accept-Encoding"] = "identity"

        try:
            r = requests.request(method, url, headers=headers, data=body,
                                 stream=True, allow_redirects=False,

                                 timeout=(2, None))
        except requests.RequestException as e:
            return self._json({"error": f"SRS agent unreachable: {e}",
                               "srs": srs_status()}, 502)

        self.send_response(r.status_code)
        upstream_length = None
        for k, v in r.raw.headers.items():
            kl = k.lower()
            if kl in HOP_BY_HOP or kl == "content-encoding":
                continue
            if kl == "content-length":
                upstream_length = v
            self.send_header(k, v)

        self.send_header("Access-Control-Allow-Origin", "*")
        if upstream_length is None:

            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()

        try:
            for chunk in r.raw.stream(65536, decode_content=False):
                self.wfile.write(chunk)
        except Exception:
            self.close_connection = True

    def _forward_auth(self) -> dict:
        """The caller's sign-in, for a request this server makes to itself for them."""
        return {key: self.headers[key] for key in ("Authorization", "Cookie")
                if self.headers.get(key)}

    def _proxy_srs_json(self, method: str, path: str):
        """An SRS job, or the list of specifications, read whole: who started a
        job, what it created, and whose specifications a list may show."""
        query = urlsplit(self.path).query
        try:
            r = requests.request(method, f"http://127.0.0.1:{SRS_PORT}{path}"
                                 + (f"?{query}" if query else ""),
                                 data=(self._raw or None) if method == "POST" else None,
                                 headers={"Content-Type": "application/json"},
                                 timeout=(2, 60))
            answer = r.json()
        except (requests.RequestException, ValueError) as e:
            return self._json({"error": f"SRS agent unreachable: {e}",
                               "srs": srs_status()}, 502)
        user = acting()
        if path == "/projects":
            answer = visible_srs_list(answer, user)
        elif method == "POST":
            body = self._body()
            # Differentiates specification creation requests from project listing operations.
            inner_path = str(body.get("path") or "").split("?")[0]
            inner_method = str(body.get("method") or "POST").upper()
            srs_job_started(
                str((answer or {}).get("job_id") or ""), user,
                create=access_rule("POST", "/srs/jobs", body)[0] == "srs-create",
                listing=inner_method == "GET" and inner_path == "/projects")
        else:
            answer = srs_job_answered(path[len("/jobs/"):].strip("/"), answer, user)
        return self._json(answer, r.status_code)

    def _deploy_for_user(self, method: str, path: str):
        """A request to the deployment agent, made for the person asking (deploy_tenancy.py)."""
        user = acting()
        try:
            path, body, answer = deploy_request_for(user, method, path, self._body())
        except ValueError as error:
            return self._json({"error": str(error)}, 400)
        if answer is not None:
            return self._json(answer)
        route = path.split("?")[0]
        if method == "GET" and route in ("/api/onboarding/status", "/api/runs"):
            try:
                data = _deploy_call("GET", path, timeout=(2, 120))
            except Exception as error:                                   # noqa: BLE001
                return self._json({"error": str(error)}, 502)
            return self._json(visible_onboarding(user, data)
                              if route == "/api/onboarding/status" else visible_runs(user, data))
        if method == "POST":
            self._raw = json.dumps(body).encode()
        return self._proxy_deploy(method, path)

    def _deploy_job_for_user(self, body: dict):
        """A deployment-agent job, rewritten for its starter and kept theirs."""
        user = acting()
        method = str(body.get("method", "POST")).upper()
        try:
            path, inner, answer = deploy_request_for(
                user, method, "/api" + str(body.get("path", "")), body.get("body") or {})
            if answer is not None:
                started = deploy_job_done(answer)
            else:
                route = path.split("?")[0]
                shown = ((lambda data: visible_onboarding(user, data))
                         if method == "GET" and route == "/api/onboarding/status"
                         else (lambda data: visible_runs(user, data))
                         if method == "GET" and route == "/api/runs" else None)
                started = deploy_job_start(method, path, inner, transform=shown)
        except ValueError as error:
            return self._json({"error": str(error)}, 400)
        DEPLOY_JOB_OWNERS[started["job_id"]] = user["id"]
        return self._json(started)

    def _proxy_deploy(self, method: str, path: str):
        """
        Hand this request to the deployment agent on DEPLOY_PORT.

        `path` arrives as the studio wrote it, with `/deploy` stripped — every
        route on that agent lives under `/api/`, so `/deploy/runs` becomes
        `/api/runs` here rather than making the studio say `/deploy/api/runs`.

        Same read timeout as _proxy_srs, and for the same reason: a read
        deadline here would not slow anything down, it would cut off a
        deployment mid-flight.
        """
        if DEPLOY_API["state"] in ("off", "import-failed"):
            return self._json({"error": "the deployment agent is not running",
                               "deploy": deploy_status()}, 503)

        query = urlsplit(self.path).query
        url = (f"http://127.0.0.1:{DEPLOY_PORT}{path}"
               + (f"?{query}" if query else ""))

        body = self._raw or None
        # The agent is given the request, not the caller's sign-in - and the
        # body's length as it now is, since it may have been rewritten.
        headers = {k: v for k, v in self.headers.items()
                   if k.lower() not in HOP_BY_HOP
                   and k.lower() not in ("content-length", "cookie", "authorization")}
        headers["Accept-Encoding"] = "identity"

        try:
            r = requests.request(method, url, headers=headers, data=body,
                                 stream=True, allow_redirects=False,
                                 timeout=(2, None))
        except requests.RequestException as e:
            return self._json({"error": f"deployment agent unreachable: {e}",
                               "deploy": deploy_status()}, 502)

        self.send_response(r.status_code)
        upstream_length = None
        for k, v in r.raw.headers.items():
            kl = k.lower()
            if kl in HOP_BY_HOP or kl == "content-encoding":
                continue
            if kl == "content-length":
                upstream_length = v
            self.send_header(k, v)
        if upstream_length is None:
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()

        if method == "HEAD":
            return
        try:
            for chunk in r.raw.stream(65536, decode_content=False):
                self.wfile.write(chunk)
        except Exception:
            self.close_connection = True

    def _plain(self, code, body: bytes, ctype="text/plain; charset=utf-8",
               extra=()):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _proxy_websocket(self, runtime=None):
        """
        Relay the HMR socket byte for byte.

        Dropping it would force a full iframe reload after every edit,
        throwing away scroll position, form state and the logged-in view —
        exactly the state someone is pointing at when they ask for a change.
        """
        try:
            if runtime is None or not runtime.port or runtime.status != "running":
                return self._plain(503, b"Preview is stopped")
            up = socket.create_connection(("127.0.0.1", runtime.port), timeout=5)
        except OSError:
            self.close_connection = True
            try:
                self.wfile.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            except Exception:
                pass
            return

        self.close_connection = True
        try:
            head = f"{self.command} {self.path} HTTP/1.1\r\n".encode()
            for k, v in self.headers.items():
                head += f"{k}: {v}\r\n".encode()
            up.sendall(head + b"\r\n")

            self.connection.settimeout(None)
            up.settimeout(None)

            def pump_down():
                try:
                    while True:
                        data = up.recv(65536)
                        if not data:
                            break
                        self.wfile.write(data)
                        self.wfile.flush()
                except Exception:
                    pass
                finally:
                    try:
                        self.connection.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass

            t = threading.Thread(target=pump_down, daemon=True)
            t.start()
            while True:

                data = self.rfile.read1(65536)
                if not data:
                    break
                up.sendall(data)
        except Exception:
            pass
        finally:
            try:
                up.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            up.close()
