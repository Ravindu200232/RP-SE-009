"""A separate UI/UX agent context with access only to handoffs and its drawing."""
from pathlib import Path

from .agent import BuilderAgent
from .loop import Outcome
from .prototype_check import repair_prompt as prototype_repair_prompt
from .prototype_check import validate_all as validate_prototype_all
from .sandbox import Sandbox




class DesignerAgent(BuilderAgent):
    def __init__(self, config, **kwargs):
        config.extra = {**config.extra, "agent_role": "designer"}
        config.unit_tests = config.e2e_tests = False
        super().__init__(config, **kwargs)
        self.sandbox = Sandbox(config.workspace, role="designer")
        self.registry = self.registry.subset(("readFile", "readFiles", "writeFile", "patchFile", "editFile",
                                             "deleteFile", "listDir", "globFiles", "grepSearch", "search"))

    def run(self, task: str) -> Outcome:
        root = Path(self.config.workspace) / ".agentforge" / "prototype"
        root.mkdir(parents=True, exist_ok=True)
        self.events.emit("phase", phase="prototype", title="Designing the prototype", status="active")

        # Antigravity-style direct context pre-load for handoff documents
        handoff_dir = Path(self.config.workspace) / ".agentforge" / "handoff"
        handoff_docs = []
        if "=== PRE-LOADED SPECIFICATION" not in task and handoff_dir.is_dir():
            for hname in ("app.md", "sitemap.md", "prototype.md", "builder.md"):
                hpath = handoff_dir / hname
                if hpath.is_file():
                    try:
                        content = hpath.read_text(encoding="utf-8", errors="replace").strip()
                        if content:
                            handoff_docs.append(f"--- .agentforge/handoff/{hname} ---\n{content}")
                    except Exception:
                        pass

        if handoff_docs:
            preloaded = (
                "=== PRE-LOADED SPECIFICATION & HANDOFF DOCUMENTS ===\n"
                "The following specification handoff documents are already pre-loaded into your context:\n\n"
                + "\n\n".join(handoff_docs)
                + "\n\n=== END PRE-LOADED SPECIFICATION ===\n\n"
                "The approved specification is already in your context above. "
                "Do NOT spend tool calls running readFile on .agentforge/handoff/*.md files. "
                "Continue the existing prototype if there is one. Write only inside .agentforge/prototype/. "
                "Use HTML, CSS and JavaScript to implement the specified interface and interactions. "
                "Batch operations to write or update multiple files in one turn where possible (e.g. use readFiles to inspect multiple files). "
                "When rewriting or updating a page, use writeFile with overwrite: true directly. "
                "For localized edits, use editFile or patchFile with exact matches. "
                "Finish promptly and summarize what changed.\n\n" + task
            )
        else:
            preloaded = (
                "Read the shared .agentforge/handoff/app.md, sitemap.md, prototype.md and builder.md. "
                "Continue the existing prototype if there is one. Write only inside .agentforge/prototype/. "
                "Use HTML, CSS and JavaScript to implement the specified interface and interactions. "
                "Batch operations to write or update multiple files in one turn where possible (e.g. use readFiles to inspect multiple files). "
                "When rewriting or updating a page, use writeFile with overwrite: true directly. "
                "For localized edits, use editFile or patchFile with exact matches. "
                "Finish promptly and summarize what changed.\n\n" + task
            )

        outcome = self._loop(self.registry, prototype=True, verification_kinds=[]).run(preloaded)
        if outcome.status == "completed" and not (root / "index.html").is_file():
            outcome = Outcome(status="incomplete", result="The designer did not produce index.html. Continue this design to finish it.")
        if outcome.status == "completed":
            if not any(root.rglob('*.html')):
                return Outcome(status='incomplete', result='No HTML pages were generated. The conversation is saved.')
            # Static syntax/style checks and the bounded page-open pass are
            # collected together before the model is asked to touch anything.
            # There is exactly one automatic grouped repair request for this
            # generated version, followed by one verification pass.
            findings = validate_prototype_all(root)
            real_findings = [row for row in findings
                             if row.get("kind") != "browser unavailable"]
            browser_unavailable = any(row.get("kind") == "browser unavailable"
                                      for row in findings)
            if browser_unavailable and not real_findings:
                outcome = Outcome(status='incomplete', result='Prototype browser validation was unavailable. Files are saved; retry when the browser is available.')
            elif real_findings:
                detail = "; ".join(f"{row.get('page')}: {row.get('text')}"
                                   for row in real_findings[:6])
                self.events.emit("notice", level="warn",
                                 message=f"Prototype validation found {detail[:760]}")
                outcome = self._loop(self.registry, prototype=True,
                                     verification_kinds=[],
                                     max_iterations=self.MAX_PROTOTYPE_REPAIR_ITERATIONS).run(
                                         prototype_repair_prompt(real_findings))
                # A repair that ran out of turns is judged the same way as one
                # that said it finished: by re-opening the pages. "It used its
                # turns" is not a verdict on the drawing, and reporting it as a
                # failed run hid a prototype that was already correct.
                if outcome.status in ("completed", "max_iterations"):
                    remaining = validate_prototype_all(root)
                    remaining_real = remaining
                    if remaining_real:
                        detail = "; ".join(
                            f"{row.get('page')}: {row.get('text')}"
                            for row in remaining_real[:6])
                        outcome = Outcome(
                            status="incomplete",
                            result="Prototype validation still has errors after the "
                                   "single grouped repair pass: " + detail,
                        )
                    else:
                        self.events.emit(
                            "notice", level="success",
                            message=f"Prototype page-open check passed for "
                                    f"{len(list(root.rglob('*.html')))} page(s); "
                                    "grouped repair verified with no console or runtime errors.",
                        )
        self.events.emit("prototype", path=str(root), pages=[{"file": p.name} for p in sorted(root.glob("*.html"))])
        self.events.emit("phase", phase="prototype", title="Designing the prototype",
                         status="done" if outcome.status == "completed" else "error")
        return outcome
