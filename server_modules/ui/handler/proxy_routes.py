# Proxy Routes: one clear HTTP responsibility.
class ProxyRoutesMixin:
    """Keep proxy routes behavior together."""

    # Purpose: Handle proxy for this focused step.
    def _proxy(self, method: str):
        url = f"http://127.0.0.1:{DEV_PORT}{self.path}"
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length and self.headers.get("Transfer-Encoding"):
            return self._plain(411, b"chunked request bodies are not proxied")
        body = self.rfile.read(length) if length else None

        headers = {k: v for k, v in self.headers.items()
                   if k.lower() not in HOP_BY_HOP}

        headers["X-Forwarded-Host"] = self.headers.get("Host", "")
        headers["X-Forwarded-Proto"] = "http"
        headers["X-Forwarded-For"] = "127.0.0.1"
        headers["Accept-Encoding"] = "identity"

        try:
            r = requests.request(method, url, headers=headers, data=body,
                                 stream=True, allow_redirects=False,
                                 timeout=(2, 300))
        except requests.RequestException:
            return self._preview_unavailable()

        self.send_response(r.status_code)
        upstream_length = None

        for k, v in r.raw.headers.items():
            kl = k.lower()
            if kl in HOP_BY_HOP or kl == "content-encoding":
                continue
            if kl == "content-length":
                upstream_length = v
            if kl == "set-cookie":
                v = re.sub(r";\s*Secure", "", v, flags=re.I)
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

    # Purpose: Hand this request to the SRS agent on SRS_PORT.
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

    # Purpose: Hand this request to the deployment agent on DEPLOY_PORT.
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
        headers = {k: v for k, v in self.headers.items()
                   if k.lower() not in HOP_BY_HOP}
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

    # Purpose: Relay the HMR socket byte for byte.
    def _proxy_websocket(self):
        """
        Relay the HMR socket byte for byte.

        Dropping it would force a full iframe reload after every element or
        pencil edit, throwing away scroll position, form state and the
        logged-in view — exactly the state those tools operate on.
        """
        try:
            up = socket.create_connection(("127.0.0.1", DEV_PORT), timeout=5)
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

            # Purpose: Handle pump down for this focused step.
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
