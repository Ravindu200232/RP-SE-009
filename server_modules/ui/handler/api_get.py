# Api Get: one clear HTTP responsibility.
class ApiGetMixin:
    """Keep api get behavior together."""

    # Purpose: Handle API get for this focused step.
    def _api_get(self, path):

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
            return self._proxy_deploy("GET", "/api" + path[7:])
        if path == "/deploy-status":
            return self._json(deploy_status())
        if path.startswith("/deploy-results/"):
            return self._json(read_deploy_results(path[16:].strip("/")))
        if path == "/projects":
            self._json(list_projects())
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
            self._json({
                "ollama_host": ollama.host,
                "cloud_enabled": ollama.cloud_ready(),
                "cloud_via": ("api-key" if key
                              else "signed-in" if ollama.signed_in() else "none"),
                "ollama_ready": ollama.daemon_ready(),

                "api_key_hint": (f"…{key[-4:]}" if key else ""),
                "local_num_ctx": s.get("local_num_ctx", max_context("llama3.1:8b")),
                "agent_model": s.get("agent_model", default_agent_model()),
                **_image_settings(),
                "mongodb_uri_set": bool(uri),
                "mongodb_uri_hint": _redact_uri(uri),
                "mongo": MONGO.status(),

                "deploy": deploy_settings_summary(),
            })
        elif path == "/mongo":
            self._json(MONGO.status())
        elif path.startswith("/files/"):
            self._json(get_project_files(path[7:].strip("/")))
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
                from qa_agent.verification.report_pdf import build_qa_pdf
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
