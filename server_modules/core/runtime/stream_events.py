# Stream Events: one focused part of the development-server lifecycle.
# Development server lifecycle and shared runtime I/O.
# Purpose: The page a picker-driven edit was made on, for the preview reload.
def _route_of(payload: dict) -> str:
    """The page a picker-driven edit was made on, for the preview reload."""
    route = (payload or {}).get("route") or "/"
    route = str(route).strip()

    return route if route.startswith("/") and "//" not in route else "/"
# Purpose: Send one error message to the log and Studio.
def eerr(txt):

    log.error(txt)
    emit({"type": "error", "text": txt})


_STREAM_SEND_LOCK = threading.Lock()
_STREAM_SEND_FILE = ""
_STREAM_SEND_TEXT = ""
_STREAM_SEND_TIMER = None
_STREAM_SEND_DELAY = 0.03
_STREAM_SEND_MAX = 8192


# Purpose: Handle take stream payload locked for this focused step.
def _take_stream_payload_locked():
    global _STREAM_SEND_FILE, _STREAM_SEND_TEXT, _STREAM_SEND_TIMER
    if not _STREAM_SEND_TEXT:
        _STREAM_SEND_TIMER = None
        return None
    payload = {"type": "stream", "file": _STREAM_SEND_FILE, "token": _STREAM_SEND_TEXT}
    _STREAM_SEND_FILE = ""
    _STREAM_SEND_TEXT = ""
    _STREAM_SEND_TIMER = None
    return payload


# Purpose: Handle flush stream send for this focused step.
def _flush_stream_send():
    with _STREAM_SEND_LOCK:
        payload = _take_stream_payload_locked()
    if payload:
        emit(payload)


# Purpose: Handle cancel stream timer locked for this focused step.
def _cancel_stream_timer_locked():
    global _STREAM_SEND_TIMER
    timer = _STREAM_SEND_TIMER
    _STREAM_SEND_TIMER = None
    if timer:
        timer.cancel()


# Purpose: Handle estream start for this focused step.
def estream_start(fname):
    _flush_stream_send()
    emit({"type": "stream_start", "file": fname})


# Purpose: Handle estream for this focused step.
def estream(fname, tok):
    global _STREAM_SEND_FILE, _STREAM_SEND_TEXT, _STREAM_SEND_TIMER
    token = str(tok or "")
    if not token:
        return

    pending = None
    send_now = None
    timer_to_start = None
    with _STREAM_SEND_LOCK:
        if _STREAM_SEND_TEXT and _STREAM_SEND_FILE != fname:
            _cancel_stream_timer_locked()
            pending = _take_stream_payload_locked()

        _STREAM_SEND_FILE = fname
        _STREAM_SEND_TEXT += token
        if len(_STREAM_SEND_TEXT) >= _STREAM_SEND_MAX:
            _cancel_stream_timer_locked()
            send_now = _take_stream_payload_locked()
        elif _STREAM_SEND_TIMER is None:
            timer_to_start = threading.Timer(_STREAM_SEND_DELAY, _flush_stream_send)
            timer_to_start.daemon = True
            _STREAM_SEND_TIMER = timer_to_start

    if pending:
        emit(pending)
    if send_now:
        emit(send_now)
    if timer_to_start:
        timer_to_start.start()


# Purpose: Handle estream end for this focused step.
def estream_end(f, c):
    _flush_stream_send()
    emit({"type": "stream_end", "file": f, "content": c})

# Purpose: Send one pipeline phase update to the Studio.
def ephase(payload):      emit({**payload, "type":"phase"})
# Purpose: Send one agent message to the Studio.
def echat(text):          emit({"type":"agent_msg",    "text":text})
# Purpose: Send current memory usage information to the Studio.
def ememory(stats):       emit({"type":"memory",       **stats})
# Purpose: Send one MongoDB status update to the Studio.
def emongo(payload):      emit({**payload, "type":"mongo"})
# Purpose: Send one command status update to the Studio.
def ecommand(payload):    emit({**payload, "type":"command"})


# Purpose: Send generated demo account details to the Studio developer view.
def ecreds(accounts, source="plan", verified=None):
    """
    The generated app's demo accounts, for AgentForge's own UI.

    Generated apps used to print these on their own login page — a "Demo
    Accounts" card above the sign-in form listing five addresses and a shared
    password. The prompts now forbid that, so the accounts have to reach the
    developer some other way, and this is it.
    """
    emit({"type": "demo_accounts", "accounts": accounts,
          "source": source, "verified": verified})


_cur_stream = {"name": None, "buf": ""}

# Purpose: Convert streamed model tokens into Studio file-stream events.
def on_token(token: str):
    if token.startswith("\x00START:"):
        fname = token[7:]
        _cur_stream["name"] = fname
        _cur_stream["buf"]  = ""
        estream_start(fname)
    elif token == "\x00END":
        fname = _cur_stream["name"]
        content = _cur_stream["buf"]
        estream_end(fname, content)
        _cur_stream["name"] = None
        _cur_stream["buf"]  = ""
    else:
        _cur_stream["buf"] += token
        estream(_cur_stream["name"] or "generating…", token)


