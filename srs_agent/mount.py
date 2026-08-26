"""
Run the SRS API inside AgentForge's process.

AgentForge's own HTTP server is a `ThreadingHTTPServer` and its websocket server
owns the main thread's asyncio loop. Uvicorn's `Server.run()` calls
`asyncio.run()`, so it brings its own loop and needs its own thread — the two
share nothing, and `emit()` already marshals onto the websocket loop with
`run_coroutine_threadsafe` for anything that crosses.

Nothing in here may raise into the caller. A broken SRS import is a missing tab,
never an AgentForge that will not start; `server.py` reports the reason through
/api/srs-status instead.
"""
from __future__ import annotations

import logging
import time

from .bridge import SRS_PORT

log = logging.getLogger("srs")


STORE_CHECK_EVERY_S = 5.0


def serve(port: int = SRS_PORT, host: str = "127.0.0.1") -> None:
    """Block on uvicorn. Intended as a daemon thread's target."""
    import uvicorn

    from . import jobs
    from .app.db import ensure_store
    from .app.main import app

    jobs.attach(app)

    last_checked = [0.0]

    @app.middleware("http")
    async def keep_the_store_alive(request, call_next):
        """
        Give the store a chance to heal before the request needs it.

        AgentForge starts mongod in a thread at the same moment this app starts
        connecting to it, so the very first connection can lose the race and
        fall back to memory permanently. And mongod can go away later. Both
        are silent failures without this — an interview that reports success
        and is gone on restart.
        """
        now = time.monotonic()
        if now - last_checked[0] > STORE_CHECK_EVERY_S:
            last_checked[0] = now
            try:
                await ensure_store()
            except Exception as e:                          # noqa: BLE001
                log.warning(f"store check failed: {type(e).__name__}: {e}")
        return await call_next(request)

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,

        timeout_keep_alive=300,
    )
    uvicorn.Server(config).run()
