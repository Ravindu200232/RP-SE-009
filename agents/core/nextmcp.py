"""
The Next.js dev server's own MCP endpoint, read for the fix prompt.

From 16.2 the dev server serves `/_next/mcp`, and among its tools is
`get_errors`, which returns what Next itself knows went wrong — not the
terminal text AgentForge has to parse, but structured JSON, per URL, with
source-mapped frames:

    {"configErrors": [],
     "sessionErrors": [{"url": "/boom", "buildError": null,
       "runtimeErrors": [{"errorName": "Error", "message": "…",
         "stack": [{"file": "app\\\\boom\\\\page.js", "methodName": "Boom",
                    "line": 2, "column": 39}]}]}]}

That is strictly better than reading the log: no keyword guessing, no
continuation-line problem, and the failing URL is attached to its own trace.

Two constraints, both measured rather than assumed:

* **`get_errors` needs a browser session.** Without one it answers "No browser
  sessions connected." AgentForge's route probe speaks plain HTTP, so the only
  moment this works is while `agents/build/tester.py` has Playwright open — which is
  exactly where it is called from.
* **The endpoint only exists on Next 16.2+.** Projects generated before the
  migration pin 15.5.22 and have no such route, so every call here degrades to
  silence.

`get_project_metadata`, `get_routes` and `get_logs` do work without a browser,
but AgentForge already enumerates routes from disk (uncapped) and captures the dev
server's stream directly, so they add nothing today.
"""
import json
import logging
import urllib.error
import urllib.request

log = logging.getLogger("nextmcp")

TIMEOUT = 15


_HEADERS = {"Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"}


def call(base_url: str, tool: str, arguments: dict = None) -> dict:
    """Invoke one MCP tool. Returns {} on any failure — never raises."""
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": tool, "arguments": arguments or {}},
    }).encode()
    try:
        req = urllib.request.Request(
            base_url.rstrip("/") + "/_next/mcp", data=payload, headers=_HEADERS)
        body = urllib.request.urlopen(req, timeout=TIMEOUT) \
                             .read().decode("utf-8", "replace")
    except Exception as e:
        log.debug(f"mcp {tool}: {e}")
        return {}

    for line in body.splitlines():
        line = line.strip()
        if line.startswith("data: "):
            line = line[6:]
        if not line.startswith("{"):
            continue
        try:
            result = json.loads(line).get("result", {})
        except json.JSONDecodeError:
            continue
        text = " ".join(c.get("text", "") for c in result.get("content", []))
        if not text.strip():
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"text": text}
    return {}


def available(base_url: str) -> bool:
    """True when this dev server serves an MCP endpoint at all."""
    return bool(call(base_url, "get_project_metadata"))


def _frame(fr: dict) -> str:
    f = str(fr.get("file", "")).replace("\\", "/")
    where = f"{f}:{fr.get('line', '?')}:{fr.get('column', '?')}"
    fn = fr.get("methodName")
    return f"    at {fn} ({where})" if fn else f"    at {where}"


def errors(base_url: str, limit: int = 8) -> str:
    """
    Next's own error state, formatted for a fix prompt. "" when there is none.

    Requires a live browser session on the dev server — call it while the
    tester's Playwright page is still open.
    """
    d = call(base_url, "get_errors")
    if not d or "error" in d and len(d) == 1:

        return ""

    out = []
    for c in (d.get("configErrors") or [])[:2]:
        msg = str(c.get("message", "")).strip()
        if msg:
            out.append(f"next.config: {msg}")

    for s in (d.get("sessionErrors") or []):
        url = s.get("url", "?")
        build = s.get("buildError")
        if build:
            msg = build if isinstance(build, str) else build.get("message", "")
            out.append(f"{url} — build error: {str(msg).strip()[:600]}")
        for e in (s.get("runtimeErrors") or []):
            name = e.get("errorName") or e.get("type") or "Error"
            head = f"{url} — {name}: {str(e.get('message', '')).strip()[:300]}"
            frames = [_frame(f) for f in (e.get("stack") or [])[:4]

                      if "node_modules" not in str(f.get("file", ""))]
            out.append("\n".join([head] + frames))
        if len(out) >= limit:
            break

    if not out:
        return ""
    return ("## What Next.js itself reports is broken\n"
            "Source-mapped, straight from the dev server — the file and line "
            "are exact.\n\n```\n" + "\n".join(out[:limit]) + "\n```")
