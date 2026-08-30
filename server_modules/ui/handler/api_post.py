# Api Post: one clear HTTP responsibility.
class ApiPostMixin:
    """Keep api post behavior together."""

    # Purpose: Handle API post for this focused step.
    def _api_post(self, path):

        if path.startswith("/srs/"):
            return self._proxy_srs("POST", path[4:])

        if path == "/jobs":
            body = self._body()
            try:
                return self._json(job_start(
                    str(body.get("method", "POST")).upper(),
                    str(body.get("path", "")),
                    body.get("body") or {}))
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
        if path == "/deploy/jobs":
            body = self._body()
            try:
                return self._json(deploy_job_start(
                    str(body.get("method", "POST")).upper(),
                    "/api" + str(body.get("path", "")),
                    body.get("body") or {}))
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
        if path.startswith("/deploy/"):
            return self._proxy_deploy("POST", "/api" + path[7:])
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
        if path == "/build/cancel":
            out = cancel.request()
            return self._json(out, 200 if out.get("ok") else 409)
        if path == "/resume":
            body = self._body()
            threading.Thread(
                target=run_agent_pipeline,
                args=("", body.get("model") or default_agent_model(),
                      _think_flag(body),
                      (body.get("qa_model") or "").strip(),
                      body.get("project", "").strip()),
                daemon=True
            ).start()
            self._json({"ok": True})
        elif path == "/delete-project":
            body = self._body()
            out = delete_project(str(body.get("project", "")))
            self._json(out, 400 if out.get("error") else 200)
        elif path == "/save-file":
            body = self._body()
            out = save_project_file(str(body.get("project", "")),
                                    str(body.get("path", "")),
                                    str(body.get("content", "")))
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
        elif path == "/agent-build":
            body = self._body()
            threading.Thread(
                target=run_agent_pipeline,
                args=(body.get("prompt", ""),
                      body.get("model") or default_agent_model(),
                      _think_flag(body),
                      (body.get("qa_model") or "").strip(),
                      "", str(body.get("logo", "")).strip(),
                      str(body.get("srs_id", "")).strip()),
                daemon=True
            ).start()
            self._json({"ok": True})
        elif path == "/pencil-edit":
            body = self._body()
            threading.Thread(
                target=run_pencil_edit,
                args=(body.get("project", ""), body.get("prompt", ""), body,
                      body.get("model") or default_agent_model(),
                      _think_flag(body)),
                daemon=True
            ).start()
            self._json({"ok": True})
        elif path == "/element-edit":
            body = self._body()
            threading.Thread(
                target=run_element_edit,
                args=(body.get("project", ""), body.get("prompt", ""),
                      body.get("element") or {},
                      body.get("model") or default_agent_model(),
                      _think_flag(body)),
                daemon=True
            ).start()
            self._json({"ok": True})
        elif path == "/image-edit":

            body = self._body()
            threading.Thread(
                target=run_image_edit,
                args=(body.get("project", ""), body.get("prompt", ""),
                      body.get("element") or {},
                      body.get("model") or default_agent_model(),
                      _think_flag(body)),
                daemon=True
            ).start()
            self._json({"ok": True})
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
        elif path == "/image-swap":

            body = self._body()
            threading.Thread(
                target=run_image_swap,
                args=(body.get("project", ""), body.get("data_base64", ""),
                      body.get("filename", ""), body.get("element") or {}),
                daemon=True
            ).start()
            self._json({"ok": True})
        elif path == "/undo":
            body = self._body()
            self._json(restore_snapshot(body.get("project", ""),
                                        body.get("id", "")))
        elif path == "/feature":
            body = self._body()
            threading.Thread(
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
        elif path == "/agent-update":
            body = self._body()
            threading.Thread(
                target=run_chat,
                args=(body.get("project", ""), body.get("prompt", ""),
                      body.get("model") or default_agent_model(),
                      (body.get("route") or "").strip(), _think_flag(body),
                      (body.get("qa_model") or "").strip(),
                      _browser_console(body)),
                daemon=True
            ).start()
            self._json({"ok": True})
        elif path.startswith("/open/"):
            proj = path[6:].strip("/")
            threading.Thread(target=_open_project, args=(proj,), daemon=True).start()
            self._json({"ok": True})
        elif path == "/mongo/prefetch":
            threading.Thread(target=MONGO.prefetch, daemon=True).start()
            self._json({"ok": True})
        elif path == "/settings":
            body = self._body()
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

            if "srs_model" in body:
                patch["srs_model"] = str(body["srs_model"]).strip()

            if "deploy_model" in body:
                patch["deploy_model"] = str(body["deploy_model"]).strip()
            for key in ("aws_profile", "aws_region", "aws_start_url",
                        "aws_sso_region"):
                if key in body:
                    patch[key] = str(body[key]).strip()
            if "vercel_token" in body:
                v = str(body["vercel_token"]).strip()
                patch["vercel_token"] = "" if v == "-" else v
            if "deploy_mongodb_uri" in body:
                v = str(body["deploy_mongodb_uri"]).strip()
                patch["deploy_mongodb_uri"] = "" if v == "-" else v
            ok = save_settings(patch)
            if patch.get("ollama_host"):
                ollama.host = patch["ollama_host"].rstrip("/")
            self._json({"ok": ok, "cloud_enabled": ollama.cloud_ready(),
                        "cloud_reachable": ollama.cloud_reachable()
                        if ollama.api_key else ollama.signed_in()})
        elif path == "/upload-project":
            body = self._body()
            name = body.get("name", "imported")
            files = body.get("files", {})

            pname = re.sub(r"[^a-z0-9]", "", name.lower())[:20] or "imported"
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
