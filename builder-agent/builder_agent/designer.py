"""A separate UI/UX agent context with access only to handoffs and its drawing."""
from pathlib import Path

from .agent import BuilderAgent, _script_error
from .loop import Outcome
from .sandbox import Sandbox


class DesignerAgent(BuilderAgent):
    def __init__(self, config, **kwargs):
        config.extra = {**config.extra, "agent_role": "designer"}
        config.unit_tests = config.e2e_tests = False
        super().__init__(config, **kwargs)
        self.sandbox = Sandbox(config.workspace, role="designer")
        self.registry = self.registry.subset(("readFile", "writeFile", "patchFile", "editFile",
                                             "deleteFile", "listDir", "globFiles", "grepSearch", "search"))

    def run(self, task: str) -> Outcome:
        root = Path(self.config.workspace) / ".agentforge" / "prototype"
        root.mkdir(parents=True, exist_ok=True)
        self.events.emit("phase", phase="prototype", title="Designing the prototype", status="active")
        outcome = self._loop(self.registry, prototype=True, verification_kinds=[]).run(
            "Read the shared .agentforge/handoff/app.md, sitemap.md, prototype.md and builder.md. "
            "Continue the existing prototype if there is one. Write only inside .agentforge/prototype/. "
            "Use HTML, CSS and JavaScript to implement the specified interface and interactions. "
            "Batch operations to write or update multiple files in one turn where possible. "
            "When rewriting or updating a page, use writeFile with overwrite: true directly. "
            "For localized edits, use editFile or patchFile with exact matches. "
            "Finish promptly and summarize what changed.\n\n" + task)
        if outcome.status == "completed" and not (root / "index.html").is_file():
            outcome = Outcome(status="incomplete", result="The designer did not produce index.html. Continue this design to finish it.")
        if outcome.status == "completed":
            errors = [(str(path.relative_to(root)), _script_error(path)) for path in root.rglob("*.js")]
            errors = [(name, error) for name, error in errors if error]
            if errors:
                outcome = Outcome(status="incomplete", result="Prototype JavaScript validation failed: " +
                                  "; ".join(f"{name}: {error}" for name, error in errors))
        self.events.emit("prototype", path=str(root), pages=[{"file": p.name} for p in sorted(root.glob("*.html"))])
        self.events.emit("phase", phase="prototype", title="Designing the prototype",
                         status="done" if outcome.status == "completed" else "error")
        return outcome
