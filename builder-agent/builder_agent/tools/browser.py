"""Looking at the running app, and proving it works.

`browserRunJourney` is the one that produces evidence; the rest exist so the
model can find out why a journey failed without guessing. A snapshot is the
accessibility tree, not pixels, because that is what a locator resolves
against - showing the model a picture and asking it to write a selector is how
journeys end up clicking the wrong control.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..errors import ToolError
from ..journeys import diagnostics_report, run_journey
from ..policy import MODERATE, SAFE
from .base import Tool


def browser_open(args, ctx):
    page = ctx.browser.open_tab()
    page.navigate(str(args["url"]))
    return {"ok": True, "content": f"Opened {page.url}\n\n{page.snapshot(60)}"}


def browser_snapshot(args, ctx):
    page = ctx.browser.page(args.get("tabId"))
    return {"ok": True, "content": page.snapshot(int(args.get("limit") or 120))
                                   + "\n\n" + diagnostics_report(page)}


def browser_action(args, ctx):
    page = ctx.browser.page(args.get("tabId"))
    action = str(args["action"])
    if action == "navigate":
        page.navigate(str(args["url"]))
    elif action == "click":
        page.click(page.locate(args.get("role", "button"), args.get("name"), args.get("selector")))
        page.wait_ready(6)
    elif action in ("type", "fill"):
        page.fill(page.locate(args.get("role", "textbox"), args.get("name"), args.get("selector")),
                  str(args.get("text", "")))
    elif action == "press":
        page.press(str(args.get("key", "Enter")))
    else:
        raise ToolError(f"Unsupported browser action {action!r}.")
    return {"ok": True, "content": f"{action} done. URL: {page.url}\n\n{page.snapshot(50)}"}


def browser_run_journey(args, ctx):
    return run_journey(
        ctx.browser, ctx.sandbox, ctx.memory.evidence,
        suite=str(args["suite"]), covers=args.get("covers") or [],
        steps=args["steps"], start_url=args.get("startUrl"),
        fresh_session=bool(args.get("freshSession", True)),
        tab_id=args.get("tabId"), events=ctx.events)


def browser_screenshot(args, ctx):
    page = ctx.browser.page(args.get("tabId"))
    view = str(args["view"])
    width = int(args.get("width") or 1280)
    height = int(args.get("height") or 800)
    name = re.sub(r"[^a-z0-9]+", "-", view.lower()).strip("-") or "view"
    target = Path(ctx.sandbox.state_dir("screenshots")) / f"{name}-{width}.png"
    page.screenshot(target, width=width, height=height)
    record = ctx.memory.evidence.capture_visual({
        "view": view, "width": width, "height": height,
        "filePath": ctx.sandbox.relative(target), "covers": args.get("covers") or []})
    ctx.events.emit("test", state="visual", view=view, width=width,
                    path=record["filePath"])
    return {"ok": True, "content":
            f"Captured {view} at {width}x{height} -> {record['filePath']}. A capture is not "
            "evidence on its own; review it with browserReviewScreenshot."}


def browser_review_screenshot(args, ctx):
    record = ctx.memory.evidence.review_visual(
        view=str(args["view"]), width=int(args["width"]),
        status="passed" if str(args["verdict"]).lower() == "pass" else "failed",
        findings=str(args["findings"]), model=ctx.config.model)
    return {"ok": record["status"] == "passed",
            "content": f"Recorded a {record['status']} visual review of {args['view']}."}


def browser_close(args, ctx):
    ctx.browser.close()
    return {"ok": True, "content": "Closed the browser and discarded its profile."}


def register(registry):
    registry.add(Tool(
        name="browserRunJourney", risk=MODERATE, handler=browser_run_journey,
        description="Run a bounded browser journey in the engine's isolated browser and record "
                    "it as end-to-end evidence. Steps are actions and assertions; a diagnostics "
                    "check runs at the end, so console errors and 5xx responses fail the journey.",
        parameters={"type": "object", "required": ["suite", "steps"], "properties": {
            "suite": {"type": "string", "description": "Stable name for this journey."},
            "covers": {"type": "array", "description": "Requirement ids this journey proves."},
            "startUrl": {"type": "string"},
            "freshSession": {"type": "boolean", "default": True,
                             "description": "Clear cookies and storage first."},
            "tabId": {"type": "string"},
            "steps": {"type": "array", "description":
                      'Actions: {action:"navigate",url}, {action:"click",role,name|selector}, '
                      '{action:"type",role,name|selector,text}, {action:"press",key}, '
                      '{action:"wait",ms}, {action:"screenshot",view,width}. '
                      'Assertions: {type:"textIncludes",expected}, {type:"urlIncludes",expected}, '
                      '{type:"visible",role,name}, {type:"count",selector,expected}, '
                      '{type:"noDiagnostics"}.'},
        }},
        summarize=lambda a: a.get("suite", "journey")))

    registry.add(Tool(
        name="browserOpen", risk=MODERATE, handler=browser_open,
        description="Open a URL in the engine's isolated browser and show its accessible controls.",
        parameters={"type": "object", "required": ["url"],
                    "properties": {"url": {"type": "string"}}},
        summarize=lambda a: a.get("url", "")))

    registry.add(Tool(
        name="browserSnapshot", risk=SAFE, handler=browser_snapshot,
        description="Read the current page's accessibility tree and any diagnostics it produced. "
                    "This is what a locator resolves against.",
        parameters={"type": "object", "properties": {
            "tabId": {"type": "string"}, "limit": {"type": "integer"}}},
        summarize=lambda a: "snapshot"))

    registry.add(Tool(
        name="browserAction", risk=MODERATE, handler=browser_action,
        description="One interaction on the current page, for investigating a failure.",
        parameters={"type": "object", "required": ["action"], "properties": {
            "action": {"type": "string", "enum": ["navigate", "click", "type", "fill", "press"]},
            "url": {"type": "string"}, "role": {"type": "string"}, "name": {"type": "string"},
            "selector": {"type": "string"}, "text": {"type": "string"},
            "key": {"type": "string"}, "tabId": {"type": "string"},
        }},
        summarize=lambda a: f"{a.get('action')} {a.get('name') or a.get('url') or ''}"))

    registry.add(Tool(
        name="browserScreenshot", risk=MODERATE, handler=browser_screenshot,
        description="Capture one view as a PNG. A capture is not evidence until it is reviewed.",
        parameters={"type": "object", "required": ["view"], "properties": {
            "view": {"type": "string"}, "width": {"type": "integer", "default": 1280},
            "height": {"type": "integer", "default": 800},
            "covers": {"type": "array"}, "tabId": {"type": "string"},
        }},
        summarize=lambda a: a.get("view", "")))

    registry.add(Tool(
        name="browserReviewScreenshot", risk=SAFE, handler=browser_review_screenshot,
        description="Record your review of a captured screenshot: what you saw and whether the "
                    "screen is acceptable.",
        parameters={"type": "object",
                    "required": ["view", "width", "verdict", "findings"], "properties": {
                        "view": {"type": "string"}, "width": {"type": "integer"},
                        "verdict": {"type": "string", "enum": ["pass", "fail"]},
                        "findings": {"type": "string"},
                    }},
        summarize=lambda a: f"review {a.get('view')}"))

    registry.add(Tool(
        name="browserClose", risk=SAFE, handler=browser_close,
        description="Close the engine's browser and discard its throwaway profile.",
        parameters={"type": "object", "properties": {}},
        summarize=lambda a: "close browser"))
