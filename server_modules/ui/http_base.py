# HTTP server basics shared by the UI handler.
HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate",
              "proxy-authorization", "te", "trailer", "trailers",
              "transfer-encoding", "upgrade"}


AGENTFORGE_PREFIX = "/__agentforge"


class _UIServer(ThreadingHTTPServer):
    """
    ThreadingHTTPServer that does not shout when a browser hangs up.

    Every verification stops the dev server, builds, and starts it again. The
    UI's iframe keeps requesting through the proxy the whole time, and each
    request that is cut off mid-write raises WinError 10053/10054 out of
    `wfile.write`. The default `handle_error` prints a full traceback per
    request: one measured feature run produced 424 of them, which buried the
    build's own output and is the reason a log had to be grepped to find out
    what happened.

    A dropped client connection is not an error anyone can act on, so it is
    logged at debug. Anything else still gets the traceback it deserves.
    """

    daemon_threads = True

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionAbortedError, ConnectionResetError,
                            BrokenPipeError, TimeoutError)):
            log.debug(f"client went away: {type(exc).__name__}")
            return
        super().handle_error(request, client_address)
