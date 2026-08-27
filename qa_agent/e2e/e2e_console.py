"""Console-first triage for browser journey failures."""
from __future__ import annotations

from qa_agent.e2e.e2e_common import _is_noise

_CONSOLE_KINDS = {"console.error", "pageerror"}


def meaningful_console_events(events) -> list[dict]:
    """Return unique browser errors that are worth repairing."""
    out = []
    seen = set()
    for item in events or []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("event") or "").lower()
        if kind not in _CONSOLE_KINDS:
            continue
        text = str(item.get("text") or "").strip()
        stack = str(item.get("stack") or "").strip()
        if _is_noise(text + "\n" + stack):
            continue
        key = (kind, text[:500], str(item.get("url") or ""),
               int(item.get("line") or 0))
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(item))
    return out


def console_event_summary(events, limit: int = 8) -> str:
    """Compact failure text for the E2E result and repair log."""
    rows = []
    for item in meaningful_console_events(events)[:max(1, int(limit or 1))]:
        pos = str(item.get("url") or "")
        line = int(item.get("line") or 0)
        col = int(item.get("column") or 0)
        if line:
            pos += f":{line}" + (f":{col}" if col else "")
        text = " ".join(str(item.get("text") or "browser runtime error").split())
        rows.append(f"{item.get('event')}: {text[:500]}" +
                    (f" [{pos}]" if pos else ""))
    return "\n".join(rows)


def console_repair_batch(agent, failures=None) -> dict:
    """Build one repair batch from every error captured at the failing action."""
    ev = dict(getattr(agent, "_last_run_evidence", {}) or {})
    raw = ev.get("step_runtime_events") or ev.get("runtime_events") or []
    events = meaningful_console_events(raw)
    if not events:
        return {}

    scoped = dict(ev)
    scoped["runtime_events"] = events
    scoped["console"] = []
    try:
        sites = list(agent.console_bug_sites(scoped) or [])
    except Exception:
        sites = []

    files = []
    for rel, _line, _why in sites:
        rel = str(rel or "").strip()
        if rel and rel not in files:
            files.append(rel)
    target = str(ev.get("target") or "").strip()
    known = getattr(getattr(agent, "arch", None), "files", None) or {}
    if target in known and target not in files:
        files.append(target)

    lines = [
        "CONSOLE-FIRST E2E REPAIR",
        "The browser reported runtime errors during the failing action.",
        "Fix every independent console/pageerror listed below in this single batch.",
        "Do not change the scenario or selector while a production console error remains.",
    ]
    for idx, item in enumerate(events, 1):
        pos = str(item.get("url") or "")
        if item.get("line"):
            pos += f":{item.get('line')}"
            if item.get("column"):
                pos += f":{item.get('column')}"
        lines.append(f"\nERROR {idx}: {item.get('event')} :: {item.get('text')}")
        if pos:
            lines.append("location=" + pos)
        stack = str(item.get("stack") or "").strip()
        if stack:
            lines.append("stack=" + stack[:5000])
    if sites:
        lines.append("\nPROJECT SOURCE LOCATIONS")
        for rel, line, why in sites[:16]:
            lines.append(f"- {rel}" + (f":{line}" if line else "") +
                         f" :: {str(why)[:260]}")
    if files:
        lines.append("\nRepair scope: " + ", ".join(files))
    return {
        "events": events, "sites": sites, "files": files,
        "report": "\n".join(lines)[:30000],
    }
