# Runs and reports the SRS sidecar API.
SRS_API = {"state": "off", "port": SRS_PORT, "error": ""}


# Purpose: Run the SRS agent's FastAPI app. Intended as a daemon thread's target.
def start_srs_api():
    """
    Run the SRS agent's FastAPI app. Intended as a daemon thread's target.

    Two separate try blocks on purpose: an import failure and a runtime failure
    are different problems with different fixes, and one combined handler loses
    which of them happened — which is the only thing the report is for.

    Nothing here may propagate. A broken SRS is a tab that explains itself,
    never an AgentForge that will not start.
    """
    try:
        from srs_agent import mount
    except Exception as e:
        SRS_API.update(state="import-failed", error=f"{type(e).__name__}: {e}")
        print(f"⚠️  SRS agent unavailable — {SRS_API['error']}")
        return

    SRS_API.update(state="starting", error="")
    try:
        mount.serve(port=SRS_PORT)
        SRS_API.update(state="stopped")
    except Exception as e:
        SRS_API.update(state="crashed", error=f"{type(e).__name__}: {e}")
        print(f"⚠️  SRS agent stopped — {SRS_API['error']}")


# Purpose: Is the SRS agent actually there?.
def srs_status() -> dict:
    """
    Is the SRS agent actually there?

    `state` is what the thread believes; `listening` is measured. They disagree
    exactly when it matters — during the second or two of startup, and after a
    crash inside uvicorn that never reached the exception handler.
    """
    import socket
    listening = False
    try:
        with socket.create_connection(("127.0.0.1", SRS_PORT), timeout=0.5):
            listening = True
    except OSError:
        pass
    return {**SRS_API, "listening": listening}


DEPLOY_API = {"state": "off", "port": DEPLOY_PORT, "error": ""}
