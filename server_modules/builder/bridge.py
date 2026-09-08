# Translates engine events into the messages the studio already speaks.
"""The one place the engine and the studio meet.

The engine publishes what happened; the studio renders a specific vocabulary.
Rather than teaching either about the other, this subscribes to the event bus
and re-emits. Nothing in the engine knows a studio exists, and nothing in the
studio knows what an agent loop is.

Progress numbers are honest ranges, not a countdown. The engine cannot know how
many steps a build will take - that is the point of an agent - so a phase
occupies a band and the studio's own model creeps within it.
"""

# Where each phase sits on the single progress bar the studio paints.
PHASE_BAND = {
    "plan": (4, 20),
    "design": (20, 24),
    "build": (24, 74),
    "unit": (74, 86),
    "e2e": (86, 95),
    "security": (95, 97),
}

# Tools worth a line in the activity feed, and how to say them in English.
TOOL_WORDS = {
    "writeFile": "Writing", "patchFile": "Editing", "editFile": "Editing",
    "patchJson": "Editing", "deleteFile": "Removing", "readFile": "Reading",
    "search": "Searching", "grepSearch": "Searching", "globFiles": "Searching",
    "executeTerminal": "Running", "runTests": "Testing",
    "browserRunJourney": "Checking in the browser", "browserOpen": "Opening",
    "browserScreenshot": "Photographing", "readSkill": "Reading",
    "defineVerificationScope": "Deciding what to prove",
    "inspectProject": "Looking at the project", "inspectError": "Reading the failure",
}

QUIET_TOOLS = {"testingStatus", "backgroundProcess", "listSkills",
               "recallKnowledge", "recallCompactedContext"}


class StudioBridge:
    """Subscribes to one run and speaks studio."""

    def __init__(self, events, *, kind: str = "build", phases=("build",)):
        self.events = events
        self.kind = kind
        self.phases = list(phases)
        self.phase = self.phases[0] if self.phases else "build"
        self.streaming_file = ""
        self.tests_started = False
        # What the console shows about the run itself, kept here so every
        # update carries the whole picture rather than one changed field.
        self.stats = {"model": "", "iterations": 0, "tools": 0, "files": 0,
                      "tokens": 0, "limit": 0, "percent": 0, "phase": self.phase,
                      "requests": 0, "sent": 0, "received": 0}
        self.files_seen = set()
        self.attach()

    # -- wiring ----------------------------------------------------------
    def attach(self):
        bus = self.events
        bus.on("agent:start", self.on_start)
        bus.on("notice", self.on_notice)
        bus.on("phase", self.on_phase)
        bus.on("iteration", self.on_iteration)
        bus.on("tool:start", self.on_tool_start)
        bus.on("tool:end", self.on_tool_end)
        bus.on("file", self.on_file)
        bus.on("test", self.on_test)
        bus.on("e2e", self.on_e2e)
        bus.on("context", self.on_context)
        bus.on("plan", self.on_plan)
        bus.on("design", self.on_design)
        bus.on("approval", self.on_approval)
        bus.on("approval:resolved", self.on_approval_resolved)
        bus.on("agent:error", self.on_error)

    def _band(self, fraction: float) -> int:
        low, high = PHASE_BAND.get(self.phase, (24, 74))
        return int(low + (high - low) * max(0.0, min(1.0, fraction)))

    # -- handlers --------------------------------------------------------
    def _stats(self, **patch):
        self.stats.update(patch, phase=self.phase)
        ememory(dict(self.stats))

    def on_start(self, p):
        elog("INFO", f"   {p.get('model')} · {p.get('stack')} · {p.get('quality')} profile")
        self._stats(model=str(p.get("model") or ""), stack=str(p.get("stack") or ""),
                    quality=str(p.get("quality") or ""))
        eprog(_phase_label(self.phase), self._band(0.05))

    def on_notice(self, p):
        elog({"warn": "WARN", "error": "ERROR"}.get(p.get("level"), "INFO"),
             f"   {p.get('message', '')}")

    def on_phase(self, p):
        phase = str(p.get("phase") or "")
        if phase in PHASE_BAND:
            self.phase = phase
        title = p.get("title") or phase
        status = p.get("status") or "active"
        ephase({"phase": self.phases.index(phase) + 1 if phase in self.phases else 0,
                "title": title, "status": status})
        if status == "active":
            eprog(title, self._band(0.02))
        estep(_step_for(phase), "active" if status == "active" else
              "done" if status == "done" else "error")

    def on_iteration(self, p):
        # The bar has to move while a long phase runs, but the engine has no
        # step count to divide by. A settling curve is honest about that: it
        # approaches the top of the band without ever claiming to reach it.
        step = int(p.get("iteration") or 1)
        self._stats(iterations=step)
        # The model is composing its next move. Between here and the tool call
        # that follows there is nothing to log, and an empty feed reads as a
        # stall rather than as thinking.
        emit({"type": "agent_state", "state": "thinking", "iteration": step})
        eprog(_phase_label(self.phase), self._band(1 - 0.94 ** step))

    def on_tool_start(self, p):
        self.stats["tools"] += 1
        tool = p.get("tool", "")
        emit({"type": "agent_state", "state": "working", "tool": tool})
        if tool in QUIET_TOOLS:
            return
        word = TOOL_WORDS.get(tool, tool)
        summary = str(p.get("summary") or "")[:90]
        elog("INFO", f"   {word} {summary}".rstrip())

    def on_tool_end(self, p):
        if p.get("ok") or p.get("tool") in QUIET_TOOLS:
            return
        detail = str(p.get("detail") or "").strip().splitlines()
        elog("WARN", f"   ⚠ {p.get('tool')}: {detail[0][:220] if detail else 'failed'}")

    def on_file(self, p):
        name = p.get("name", "")
        content = p.get("content") or ""
        note = p.get("note", "written")
        if note == "deleted":
            efile(name, 0, "")
            elog("INFO", f"   removed {name}")
            return
        # The studio's code pane follows a file as it lands. The engine writes
        # a file at once rather than a token at a time, so the stream is opened
        # and closed around the finished text: the pane still jumps to the file
        # being worked on, which is the part anyone actually watches.
        estream_start(name)
        estream_end(name, content)
        efile(name, len(content), content)
        self.files_seen.add(name)
        self._stats(files=len(self.files_seen))
        elog("INFO", f"   {note} {name} ({len(content.splitlines())} lines)")

    def on_test(self, p):
        state = p.get("state")
        if state == "scope":
            elog("INFO", f"   scope: {p.get('requirements')} requirement(s)"
                         + ("" if p.get("sealed") else ", still open"))
        elif state == "run":
            if not self.tests_started:
                emit({"type": "test_start"})
                self.tests_started = True
            emit({"type": "test_run", "attempt": 1})
            elog("INFO", f"   running {p.get('kind')}/{p.get('suite')}")
        elif state == "result":
            emit({"type": "test_result", "status": p.get("status"),
                  "msg": f"{p.get('kind')}/{p.get('suite')}",
                  "detail": str(p.get("detail") or "")[:400]})
        elif state == "visual":
            elog("INFO", f"   captured {p.get('view')} at {p.get('width')}px")

    def on_e2e(self, p):
        emit({"type": "e2e_event", **{k: v for k, v in p.items() if k != "type"}})

    def on_context(self, p):
        self._stats(tokens=int(p.get("tokens") or 0), limit=int(p.get("limit") or 0),
                    percent=int(p.get("percent") or 0),
                    requests=int(p.get("used_requests") or 0),
                    sent=int(p.get("used_prompt") or 0),
                    received=int(p.get("used_completion") or 0))

    def on_plan(self, p):
        """The plan is the thing the build is about to do. Show it in full."""
        plan = str(p.get("plan") or "")
        if plan:
            emit({"type": "agent_msg", "kind": "plan", "title": "The plan",
                  "text": plan[:8000]})

    def on_error(self, p):
        elog("ERROR", f"   {p.get('message', 'the run failed')}")

    def on_approval(self, payload) -> None:
        """A question the run is waiting on. The studio answers it or it expires."""
        emit({"type": "approval", **payload})
        elog("INFO", f"   waiting for a decision: {payload.get('kind')}")

    def on_approval_resolved(self, payload) -> None:
        emit({"type": "approval_resolved", **payload})
        elog("INFO", f"   {payload.get('kind')}: {payload.get('decision')}")

    def on_design(self, payload) -> None:
        """The design customiser's answer, shown rather than only written."""
        emit({"type": "agent_msg", "kind": "design", "title": "Design system",
              "text": payload.get("summary", ""), "design": payload})


def _phase_label(phase: str) -> str:
    return {"plan": "Planning…", "design": "Choosing the design…",
            "build": "Building…", "unit": "Unit tests…",
            "e2e": "Browser journeys…", "security": "Security review…"}.get(phase, "Working…")


def _step_for(phase: str) -> str:
    # The studio's step rail has four lanes; the engine has more phases.
    return {"plan": "plan", "design": "plan", "build": "build",
            "unit": "test", "e2e": "test", "security": "verify"}.get(phase, "build")
