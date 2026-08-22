"""
Run the deployment agent inside AgentForge's process.

Simpler than the SRS's mount, and for one reason: this agent's HTTP server is a
`ThreadingHTTPServer`, so it already gets a thread per request. The SRS ran on
uvicorn, where a single synchronous call — ReportLab, in the bug that produced
that module's comments — stalls every other request on the loop. Here the long
work (boto3, `gh`, `npm ci`, Playwright) blocks only its own request's thread.

That is why the copy keeps its own server rather than being re-hosted as ASGI
routes: rewriting thirty-five handlers onto AgentForge's websocket loop would put
every one of those blocking calls back on a loop.

Nothing in here may raise into the caller. A broken deployment agent is a tab
that explains itself, never an AgentForge that will not start; `server.py` reports
the reason through /api/deploy-status instead.
"""
from __future__ import annotations

import logging
import os

from .bridge import DEPLOY_PORT

log = logging.getLogger("deploy")


def serve(port: int = DEPLOY_PORT, host: str = "127.0.0.1") -> None:
    """Block on the HTTP server. Intended as a daemon thread's target."""

    from .bridge import DEPLOY_DATA
    DEPLOY_DATA.mkdir(parents=True, exist_ok=True)
    os.environ["DEPLOYMENT_AGENT_DATA_DIR"] = str(DEPLOY_DATA)

    os.environ["DEPLOYMENT_AGENT_NO_BROWSER"] = "1"

    import dfserver

    try:
        dfserver.start_reconciliation()
    except Exception as e:                                      # noqa: BLE001
        log.warning(f"reconciliation skipped: {type(e).__name__}: {e}")

    dfserver.start_http(port=port, host=host)
