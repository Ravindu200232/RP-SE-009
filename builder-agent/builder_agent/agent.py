"""One build, start to finish.

The session owns the durable pieces - workspace, memory, model, processes,
browser - across the passes a build is made of:

    plan  ->  design  ->  build  ->  verify

There is no approval between them. The engine used to stop twice: once for the
plan and once for a design questionnaire, each waiting on a human who, in a
studio build, is not there. Both are now decided and applied automatically, and
what the user gets instead of two dialogs is a plan and a design contract
written into the project where they can read and edit them.

What is deliberately kept is the refusal to *finish* without evidence. Skipping
an approval prompt is a convenience; skipping verification would be a lie.
"""
from __future__ import annotations

import re
import subprocess
import uuid
from pathlib import Path

from .approvals import Approvals
from .browser import Browser
from .config import Config
from .design import apply_answer as apply_design_answer
from .design import choose as choose_design
from .design import design_contract_message, form_payload, write_design_skill
from .design import tokens as design_tokens
from .errors import AbortError, ConfigError
from .events import Events
from .llm import OllamaClient, Router
from .loop import Loop, Outcome
from .memory import Memory
from .processes import Processes
from .prompts import task_message
from .setup import ASK_TIMEOUT, apply_answer, questions_for
from . import sitemap as sitemap_of
from . import styles as styles_of
from .skills import read_manifest
from .skills import select as select_skills
from .sandbox import Sandbox
from .tools import build_registry, review_registry

# How many times a rejected plan may be sent back before the build proceeds
# anyway. A plan nobody accepts after this many tries is not going to be
# accepted, and the alternative is a build that never starts.
MAX_PLAN_REVISIONS = 3

# What the drawing is asked at. The build stays at the config's own setting,
# which is low on purpose: code is judged by whether it runs. A drawing is
# judged by whether anyone likes looking at it, and two drawings of the same
# product should not be the same drawing.
DRAWING_TEMPERATURE = 0.8

# Work that genuinely has no user interface. A design contract for a cron job
# is noise, and this is the only case where it is.
NON_UI_TERMS = ("cli", "command line", "cron job", "cron", "worker", "daemon",
                "library", "migration", "seed script", "api only", "api-only",
                "backend only", "headless", "batch job")


# A plan that files a .jsx or a page is building a user interface, whatever the
# request happened to call it.
_UI_FILES = re.compile(r"\.(?:jsx|tsx|css|scss|html)\b|/page\.|components?/")


def wants_design(task: str, plan: str = "") -> bool:
    """Does this piece of work put something on a screen?

    Yes, unless the request says otherwise. Both supported stacks *are* web
    applications - that is the builder contract - so a UI is the default case,
    not the exception.

    This used to require a literal "app", "page" or "site" in the request, and
    nobody writes those words: "a plant nursery where a visitor browses plants
    on /plants and adds one to a basket" is obviously a user interface and
    matched none of them, so every real request silently lost its design.

    The plan is better evidence than the request, which is why it is offered
    here: a plan that files components has settled the question.
    """
    text = f" {re.sub(r'[^a-z0-9/ ]+', ' ', str(task or '').lower())} "
    if any(f" {term} " in text for term in NON_UI_TERMS):
        # Unless the plan it produced is full of pages and components anyway.
        return bool(plan) and bool(_UI_FILES.search(str(plan)))
    return True



def _script_error(path: Path) -> str:
    """The first syntax error in a drawing's script, or "" if it parses.

    Node is what the stack already requires, so this costs nothing and is
    exact. If it is somehow absent the drawing proceeds - a missing checker is
    not a reason to fail a pass.
    """
    if not path.is_file():
        return ""
    try:
        done = subprocess.run(["node", "--check", str(path)], capture_output=True,
                              text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return ""
    if done.returncode == 0:
        return ""
    for line in (done.stderr or "").splitlines():
        if "SyntaxError" in line:
            return line.strip()[:160]
    return "it does not parse"


def _page_file(route: str) -> str:
    """`/admin/orders` -> `admin-orders.html`; `/` -> `index.html`."""
    parts = [part.strip("[]:") for part in str(route or "").strip("/").split("/") if part]
    stem = "-".join(re.sub(r"[^a-z0-9]+", "-", part.lower()).strip("-") for part in parts)
    return f"{stem or 'index'}.html"


def _title_of(name: str) -> str:
    stem = str(name or "").rsplit(".", 1)[0].replace("-", " ").replace("_", " ")
    return (stem[:1].upper() + stem[1:]) if stem else "Page"


class BuilderAgent:
    """The builder agent: plans, designs, builds and proves one application."""

    def __init__(self, config: Config, *, client=None, events: Events | None = None,
                 cancel=None, memory: Memory | None = None) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.config = config
        self.events = events or Events()
        self.cancel = cancel or (lambda: False)
        # Only a surface that can actually answer turns these on; everywhere
        # else they resolve to the default immediately.
        self.approvals = Approvals(self.events, enabled=bool(config.extra.get("gates")),
                                   timeout=float(config.extra.get("gate_timeout", 300)))
        self.sandbox = Sandbox(config.workspace)
        self.memory = memory if memory is not None else Memory(budget_tokens=config.context_tokens)
        self.memory.budget_tokens = config.context_tokens
        self.processes = Processes(events=self.events)
        self.browser = Browser(events=self.events)
        self.client = client or OllamaClient(config.host or None)
        self.router = Router(self.client, config.model, config=config, events=self.events)
        self.registry = build_registry()
        self.plan_text = ""
        self.plan_approval = True
        self.design: dict | None = None
        # The screens the design step agreed, and the drawing made of them.
        self.screens: list[dict] = []
        self.prototype_dir: Path | None = None
        # Which screens exist and what reaches what. Built from the plan, folded
        # onto what the drawing actually wrote, handed to both passes. Never
        # shown to the user - they approved a plan and will look at a drawing.
        self.sitemap: list[dict] = []
        # What the user settled before planning: which provider, which mode,
        # which names are configured. Never the values themselves.
        self.setup_notes: list[str] = []

        detected = self.router.context_window()
        if detected:
            self.config.context_tokens = detected
            self.memory.budget_tokens = detected

    def retarget(self, model: str = "", think: bool | None = None) -> bool:
        """Answer the rest of this conversation with a different model.

        Changing the model does not make what was already said untrue, so it
        must not throw the conversation away: the transcript, the evidence and
        the context all belong to the project, not to whichever model happened
        to be answering. Only the window can differ, and that is re-measured
        here so a smaller model is not handed a transcript it cannot hold.
        """
        changed = False
        if model and model != self.config.model:
            self.config.model = model
            self.router.model = model
            changed = True
        if think is not None and bool(think) != bool(self.config.think):
            self.config.think = bool(think)
            changed = True
        if changed:
            detected = self.router.context_window()
            if detected:
                self.config.context_tokens = detected
                self.memory.budget_tokens = detected
        return changed

    # -- passes ----------------------------------------------------------
    def settings(self, task: str, plan: str = "") -> list[str]:
        """Ask for the accounts the agreed plan needs, before anything is designed.

        A Stripe secret or a Cloudinary cloud name cannot be read out of a
        repository, so it has to be asked for. The request is too early to know
        which of them this product will want - "a shop for my bakery" does not
        say whether it takes cards, sends receipts or lets anyone upload a
        photograph - and asking then means questions about providers the
        product will never have, and none about the ones the plan invents.

        The approved plan does say. So the questions are read off it, after the
        user has agreed it and before the design is customised, which is the
        last moment they still cost nothing: the design, the drawing and the
        build all follow from here.

        Nothing is enumerated in code. The skills the plan selects are what
        decide the questions, and a skill declares its own - so a plan that
        never mentions money is never asked about Stripe, and a new integration
        is a new skill directory rather than a branch here.
        """
        try:
            selected = select_skills(read_manifest(), plan, task, self.config.stack)
            questions = questions_for(selected)
        except Exception as error:                                   # noqa: BLE001
            self.events.emit("notice", level="warn",
                             message=f"Setup questions could not be prepared: {error}")
            return []

        notes = []
        for question in questions:
            if question.get("error"):
                self.events.emit("notice", level="warn",
                                 message=f"The {question['skill']} skill's setup declaration "
                                         f"is unusable: {question['error']}")
                continue
            answer = self.approvals.ask(
                "setup",
                {key: question[key] for key in ("purpose", "question", "choices", "fields")},
                default={"decision": "later"}, timeout=ASK_TIMEOUT, cancel=self.cancel)
            applied = apply_answer(self.sandbox.root, question, answer)
            # Names only. A value that reaches an event reaches the log, the
            # saved stream and the transcript, which is every place a secret
            # must not be.
            self.events.emit("setup", purpose=question["purpose"], choice=applied["label"],
                             saved=applied["saved"], missing=applied["missing"])
            notes.append(applied["note"])
        self.setup_notes = notes
        return notes

    def plan(self, task: str) -> Outcome:
        """Investigate the project, then write the plan the build executes.

        The plan is offered for review before anything is built. Nobody has to
        answer: the gate expires into "accept", because a plan is cheap to
        change now and the alternative is a build that never starts.
        """
        self.events.emit("phase", phase="plan", title="Planning", status="active")
        request = self._with_settings(task)

        for revision in range(MAX_PLAN_REVISIONS + 1):
            loop = self._loop(self.registry.subset(
                [name for name, tool in self.registry.tools.items()
                 if tool.review_safe or name in ("executeTerminal",)]),
                plan_only=True)
            outcome = loop.run(request)
            self.plan_text = loop.state.get("plan") or outcome.result

            if not getattr(self, "plan_approval", True):
                break

            answer = self.approvals.ask(
                "plan", {"plan": self.plan_text, "goal": task[:400],
                         "revision": revision, "maxRevisions": MAX_PLAN_REVISIONS},
                default={"decision": "accept"}, cancel=self.cancel)
            if answer.get("decision") != "revise" or revision >= MAX_PLAN_REVISIONS:
                break

            feedback = str(answer.get("feedback") or "").strip()
            self.events.emit("notice", level="info",
                             message=f"Revising the plan (round {revision + 2})"
                                     + (f": {feedback[:160]}" if feedback else "."))
            request = "\n".join([
                f"Revise the plan for this request:\n\n{task}", "",
                "The previous plan was sent back. What was asked for:",
                feedback or "(nothing specific - reconsider the approach yourself)", "",
                "Previous plan:", self.plan_text[:6000], "",
                "Produce a new plan that addresses this. Do not simply restate the old one.",
            ])

        self.events.emit("phase", phase="plan", title="Planning", status="done")
        return outcome

    def apply_design(self, task: str, plan: str = "") -> dict | None:
        """Decide the look, offer it for adjustment, and write it as a contract."""
        if not wants_design(task, plan):
            return None
        # The plan names the screens and the domain far more precisely than the
        # request does, so it is part of what the design is chosen from.
        # The task sets the mood; the plan names the screens. They are read
        # separately because only one of them has been approved.
        form = form_payload(f"{task}\n{plan}"[:8000], plan=plan)
        answer = self.approvals.ask(
            "design", form, default={"decision": "apply"}, cancel=self.cancel)
        if answer.get("decision") == "skip":
            self.events.emit("notice", level="info",
                             message="Design contract skipped; the build will choose its own look.")
            return None

        selection = apply_design_answer(form["chosen"], answer.get("selection"))
        chosen = set(selection.get("pages") or [])
        self.screens = [page for page in (form.get("pages") or [])
                        if page.get("id") in chosen]
        self.sitemap = sitemap_of.from_screens(self.screens)
        sitemap_of.save(self.sandbox.root, self.sitemap)
        written = write_design_skill(
            self.sandbox.root, selection, goal=task[:300], stack=self.config.stack)
        if written.get("blockInstallError"):
            self.events.emit(
                "notice", level="warn",
                message=f"Selected UI blocks could not be installed: "
                        f"{written['blockInstallError'][:300]}")
        self.design = written
        self.events.emit("phase", phase="design", title="Design system", status="done",
                         palette=selection["paletteName"], theme=selection["themeMode"])
        self.events.emit("design", **{
            "palette": selection["paletteName"], "mood": selection["mood"],
            "theme": selection["themeMode"], "font": selection["font"],
            "radius": selection["radius"], "density": selection["density"],
            "typeScale": selection["typeScale"], "path": written["path"],
            "tokens": design_tokens(selection["palette"], selection["themeMode"]),
            "summary": (f"{selection['paletteName']} - {selection['mood']} "
                        f"Default theme {selection['themeMode']}; {selection['font']} type, "
                        f"{selection['radius']} corners, {selection['density']} spacing."),
        })
        return written


    # The tools a drawing needs: read the project, read the skill, write files.
    # Nothing that installs, serves, tests or drives a browser - a prototype is
    # HTML on disk, and a pass that can run npm will find a reason to.
    PROTOTYPE_TOOLS = ("readFile", "writeFile", "patchFile", "editFile", "listDir",
                       "globFiles", "grepSearch", "readSkill", "listSkills",
                       "inspectProject")

    # How many times the user may send the drawing back before the build starts
    # anyway. Each round is a re-render, which is cheap; an unbounded loop with
    # nobody answering is not.
    MAX_PROTOTYPE_ROUNDS = 8

    def prototype(self, task: str, plan: str = "") -> dict | None:
        """Draw the application in HTML, and change it until they are happy.

        The cheapest place in the pipeline to be wrong. A layout that is wrong
        here costs a re-render; the same layout wrong after the build costs the
        build, its tests and its browser journeys.

        No new agent: this is the builder, with the tools that write files and
        none of the ones that install or serve anything, pointed at a skill that
        says what a prototype is. What comes back is plain HTML and one
        stylesheet, which is what makes "make the buttons blue" a one-property
        change rather than a re-render of five components.
        """
        if not self.design or not self.screens:
            return None

        root = Path(self.sandbox.root) / ".agentforge" / "prototype"
        root.mkdir(parents=True, exist_ok=True)
        self.prototype_dir = root
        self.events.emit("phase", phase="prototype", title="Drawing it", status="active")

        registry = self.registry.subset(self.PROTOTYPE_TOOLS)
        instruction = self._prototype_task(task, plan)
        feedback = ""

        for round_number in range(self.MAX_PROTOTYPE_ROUNDS):
            request = instruction if not feedback else "\n".join([
                "Change the prototype you already wrote in .agentforge/prototype/.",
                "", "What they asked for:", feedback, "",
                "Change what they asked for and leave the rest alone. A colour or a "
                "size that is a token changes in the token block, once, so every "
                "page follows. Rewrite only the files that actually change.",
            ])
            outcome = self._loop(registry, prototype=True).run(request)
            if outcome.status == "cancelled":
                return None

            drawn = self._drawn_pages(root)
            # A redraw adds pages, removes them and re-points the navigation, so
            # the map is folded again after every round rather than once at the
            # end. The build reads it, and reads it after the last change.
            self.sitemap = sitemap_of.from_drawing(root, self.sitemap)
            sitemap_of.save(self.sandbox.root, self.sitemap)
            self.events.emit("prototype", pages=drawn, round=round_number + 1,
                             path=str(root))
            if not drawn:
                self.events.emit("notice", level="warn",
                                 message="The prototype pass wrote no pages; building "
                                         "from the design contract alone.")
                break

            # A script that does not parse takes the whole flow with it, and the
            # page still looks finished, so nobody finds out until they click.
            # Every drawing of a twenty-screen product broke this way - the model
            # patches demo.js repeatedly and leaves a duplicated tail behind.
            broken = _script_error(root / "demo.js")
            if broken and round_number + 1 < self.MAX_PROTOTYPE_ROUNDS:
                self.events.emit("notice", level="warn",
                                 message=f"demo.js does not parse ({broken}); fixing it "
                                         "before showing the drawing.")
                feedback = ("`demo.js` has a syntax error and none of the flow runs: "
                            f"{broken}. Read the file around that line and repair it - "
                            "the usual cause is a block that was closed and then had its "
                            "last few lines repeated after the closing brace. Change "
                            "nothing else.")
                continue

            # The one way a drawing of plain CSS can still be shown bare: the
            # stylesheet was never really written, or the pages never link it.
            bare = styles_of.unstyled(root, styles_of.browser_check(self.browser))
            if bare and round_number + 1 < self.MAX_PROTOTYPE_ROUNDS:
                self.events.emit("notice", level="warn",
                                 message=f"{len(bare)} page(s) have no styling on them; "
                                         "writing it before showing the drawing.")
                feedback = (
                    "These pages render with no styling at all: " + ", ".join(bare[:8])
                    + ". Everything is in `styles.css` - the design contract's tokens on "
                    "`:root`, then the shell, the components, the layout and the motion - "
                    "and every page links it with "
                    "`<link rel=\"stylesheet\" href=\"styles.css\">` in its head. There is "
                    "no CSS framework to fall back on: a class only does something if a "
                    "rule in `styles.css` says what it does. Write that stylesheet, point "
                    "the pages at it, and leave the markup alone otherwise.")
                continue

            # Parallel flow verification, screenshot capture, and living SRS update
            try:
                from server_modules.srs.srs_sync import sync_from_prototype_async
                sync_from_prototype_async(Path(root), drawn)
            except Exception:
                pass

            answer = self.approvals.ask(
                "prototype",
                {"pages": drawn, "goal": task[:300], "round": round_number + 1,
                 "maxRounds": self.MAX_PROTOTYPE_ROUNDS},
                default={"decision": "stop"}, cancel=self.cancel)
            if answer.get("decision") in ("stop", "prototype_only", "keep"):
                self._stop_at_prototype = True
                break
            if answer.get("decision") != "revise":
                break
            feedback = str(answer.get("feedback") or "").strip()
            if not feedback:
                break
            self.events.emit("notice", level="info",
                             message=f"Redrawing: {feedback[:160]}")

        self.events.emit("phase", phase="prototype", title="Drawing it", status="done")
        return {"path": str(root), "pages": self._drawn_pages(root)}

    def _drawn_pages(self, root: Path) -> list[dict]:
        """The files the drawing pass actually produced, in the plan's order."""
        if not root.is_dir():
            return []
        on_disk = {path.name for path in root.glob("*.html")}
        pages, seen = [], set()
        for screen in self.screens:
            name = _page_file(screen.get("route", ""))
            if name in on_disk:
                pages.append({"file": name, "route": screen.get("route", ""),
                              "label": screen.get("label", name), "what": screen.get("what", "")})
                seen.add(name)
        # Anything it drew that the plan did not name is still shown, because a
        # page nobody can see is a page nobody can ask to remove.
        for name in sorted(on_disk - seen):
            pages.append({"file": name, "route": "", "label": _title_of(name), "what": ""})
        return pages

    def _prototype_task(self, task: str, plan: str = "") -> str:
        """What to draw, and what was already settled. How to draw it is the skill's.

        Every rule in `html-prototype` used to be written into this instruction
        as well - the page counts, the shell, the pictures, the styling, the
        motion, all of it twice. When the two disagreed the instruction won
        silently: the skill was changed to say a drawing writes its own CSS
        while this still dictated a Tailwind head, and drawings kept coming
        back with the framework in them. One document says how; this one says
        what, and points at it.
        """
        screens = "\n".join(
            f"- {page.get('label', '')} ({page.get('route', '')}) -> "
            f"{_page_file(page.get('route', ''))}"
            + (f" - {page['what']}" if page.get("what") else "")
            for page in self.screens)
        contract = (design_contract_message(self.design["selection"], drawing=True)
                    if self.design and self.design.get("selection") else "")
        return "\n".join([
            "THE WHOLE APPLICATION, NOT HALF OF IT. Every screen on the list, finished, "
            "and every link on every one of them landing on a page that exists. No stub, "
            "no placeholder, nothing left for later.",
            "",
            "Draw this whole application as static HTML, before any of it is built for "
            "real. This is the finished thing on paper, not a sketch of it.",
            "",
            "READ THE `html-prototype` SKILL IN FULL BEFORE YOU WRITE ANYTHING, and "
            "follow it to the letter. It is the contract for this pass: which files to "
            "write and in what order, how a page is shaped, how it is styled, how it "
            "moves, what its pictures are, what it must never say, and the counts every "
            "page has to meet. None of that is repeated here, so a drawing made without "
            "reading it will be wrong in ways nothing below mentions.",
            "",
            "GOAL:", task[:2000], "",
            "SCREENS TO DRAW - a separate file for each, in .agentforge/prototype/. "
            "This is a multi-page application, not one page with sections and not one "
            "file with tabs:", screens, "",
            (sitemap_of.render(self.sitemap)
             + "\nEvery one of those is a file you write, and every one of them\n"
               "is reachable from the navigation on every other one.\n"
             if self.sitemap else ""),
            "COVER EVERYTHING THAT WAS AGREED. Two things were settled before this and "
            "both are binding:",
            "",
            "1. The plan below. Every requirement it enumerates has to be visible "
            "somewhere in these pages - if the plan says a seller edits their own "
            "listings, there is a screen where that is on the page. Work through the "
            "plan's requirements one at a time and place each one. A requirement nobody "
            "can see was not drawn.",
            "2. The design contract below. Every dimension it settles - palette, type, "
            "scale, corners, spacing, borders, depth, width, voice - is expressed in "
            "styles.css and used on every page. Do not re-decide any of it.",
            "",
            "BEFORE YOU STOP, the four that have actually been shipped. The skill says "
            "what each one should be; this is the list to check yourself against:",
            "- A thin page. The pages that come back short are the ones nobody argues "
            "with, and they are what the build is then made to match.",
            "- A sketch's shell: a header of five links and a footer of one line, when "
            "the real product's header and footer carry thirty between them.",
            "- A page that admits what it is - 'prototype', 'demo', 'coming soon', an "
            "explanation of what is missing, or lorem ipsum anywhere.",
            "- A drawing nobody can click through, because the flow keeps its state in "
            "a variable instead of localStorage, or the content is built by the script "
            "rather than written in the HTML.",
            "",
            "Write the files and stop. Do not install anything, do not start a server, "
            "and do not write tests.",
        ] + (["", "THE DESIGN CONTRACT:", contract] if contract else [])
          + (["", "THE APPROVED PLAN - every requirement in it belongs on a page:",
              plan[:6000]] if plan else []))

    def build(self, task: str, *, plan: str = "", verification_kinds=None) -> Outcome:
        """Implement the plan and prove it works."""
        if not self.config.unit_tests and not self.config.e2e_tests and verification_kinds is None:
            verification_kinds = []
        phase = verification_kinds[0] if verification_kinds and len(verification_kinds) == 1 else "build"
        title = {"unit": "Unit tests", "e2e": "End-to-end"}.get(phase, "Building")
        self.events.emit("phase", phase=phase, title=title, status="active")
        instruction = self._with_settings(task)
        instruction = self._with_prototype(instruction)
        if self.design:
            instruction = design_contract_message(self.design["selection"]) + "\n\n" + instruction
        loop = self._loop(self.registry, verification_kinds=verification_kinds)
        outcome = loop.run(instruction, plan=plan)
        self.events.emit("phase", phase=phase, title=title,
                         status="done" if outcome.status == "completed" else "error")
        return outcome

    def review(self, focus: str = "Review the current change set.") -> Outcome:
        """A read-only pass that reports defects and changes nothing."""
        loop = self._loop(review_registry(self.registry), review=True)
        return loop.run(focus)

    def run(self, task: str) -> Outcome:
        """The whole build: settle, plan, design, implement, verify."""
        if not str(task or "").strip():
            raise ConfigError("A task description is required.")
        try:
            plan_outcome = self.plan(task)
            if plan_outcome.status not in ("completed",):
                # A planning pass that could not finish is not fatal: the build
                # can still proceed from the request itself, and saying so is
                # more useful than refusing to start.
                self.events.emit("notice", level="warn",
                                 message="Planning did not complete; building from the request "
                                         "directly.")
                self.plan_text = ""
            # What the agreed plan needs an account for - a card processor, a
            # mail service, somewhere to put an upload - asked between the plan
            # and the design, because the plan is what says which of them the
            # product actually has.
            self.settings(task, plan=self.plan_text)
            self.apply_design(task, plan=self.plan_text)
            # Drawn, changed until they are happy with it, and only then built.
            self.prototype(task, plan=self.plan_text)
            if getattr(self, "_stop_at_prototype", False) or getattr(self.config, "prototype_only", False):
                self.events.emit("notice", level="success",
                                 message="HTML Prototype finished and saved.")
                return Outcome(status="completed", result="Prototype finished.")
            return self.build(task, plan=self.plan_text)
        finally:
            self._finish()

    def _with_prototype(self, instruction: str) -> str:
        """The build's job is to make the real thing look like what was agreed.

        The user looked at the drawing and said yes to it, so it is not a
        reference or an inspiration: it is the settled appearance of the
        product, and it outranks whatever the model would otherwise reach for.
        """
        if not self.prototype_dir or not self.prototype_dir.is_dir():
            return instruction
        pages = sorted(path.name for path in self.prototype_dir.glob("*.html"))
        if not pages:
            return instruction
        return "\n".join([
            "THE WHOLE APPLICATION, NOT HALF OF IT. Every screen in the drawing, built, "
            "and every route it links to answering. No stub, no placeholder, nothing "
            "left for later.",
            "THE APPROVED PROTOTYPE - this is what the product looks like.",
            f"`.agentforge/prototype/` holds the HTML the user approved: "
            f"{', '.join(pages)} and `styles.css`.",
            "Read them before writing the first component, and build the real "
            "application to match: the same layout, the same structure, the same shell "
            "and navigation, the same words, the same tokens. Where the prototype and "
            "your own taste disagree the prototype wins - they have already seen it "
            "and agreed to it.",
            "ONE DRAWN PAGE IS ONE SCREEN'S CHECKLIST. Open the drawn page for the "
            "screen you are about to write, at the moment you write it, and work down "
            "it section by section: every section it has below the header, the built "
            "screen has. None dropped, none merged into another, none reduced to a "
            "heading. Count them against each other before you call the screen done - "
            "the section that goes missing is the one below the fold, the summary "
            "under the table, the empty state, the panel explaining what the screen "
            "is for. This is the whole measure of whether a screen is finished; there "
            "is no separate list of what a screen of this kind ought to contain, "
            "because the drawing already is that list, for this product.",
            "The shell is the exception, and only the shell: the drawing repeats its "
            "header, navigation and footer into every file because it has no layout to "
            "put them in. You do, so they are written once there and every page "
            "inherits them - with everything in them, the whole navigation and the "
            "whole footer, not a reduced version.",
            "The built screen will be smaller than the drawn one in characters, and "
            "that is right: the drawing writes nine room cards out by hand where you "
            "write one and map over the data. Judge it by sections and by what is in "
            "them, never by length - hand-writing rows to match a drawing's size would "
            "be a worse application, not a fuller one.",
            "Where a screen is split into a page and its components, the two together "
            "are the drawn page. Writing the table into a component does not finish "
            "the screen the table sits on; the rest of that drawn page still has to "
            "be somewhere.",
            "It is a drawing, so it has no data layer. Replace its written-in content "
            "with the real thing from the database and keep everything else it settled.",
            "THE PICTURES ARE PART OF WHAT WAS APPROVED. Every image address in the "
            "drawing carries over exactly as written - the same seed, so the same "
            "photograph. Do not re-derive one from a field that happens to be nearby: "
            "seeding a bakery's picture from `product.slug` gives country-sourdough "
            "where the drawing had sourdough-country, which is a different photograph, "
            "and seeding it from a database id gives a different one again every time "
            "the data is re-seeded. Where the drawing shows a picture for a thing that "
            "now comes from the database, put that drawn address on the record in the "
            "seed and render the stored value, so the built page shows the picture they "
            "said yes to and keeps showing it.",
            (sitemap_of.render(self.sitemap, drawn=True)
             + "\nThat is the whole product. Every screen on it is a route in the"
               " built application, and every link on it still works when the"
               " build is done."
             if self.sitemap else ""),
            "", instruction,
        ])

    def _with_settings(self, task: str) -> str:
        """The request, plus the accounts the user settled once the plan was agreed."""
        if not self.setup_notes:
            return task
        return "\n".join([
            task, "",
            "ALREADY SETTLED WITH THE USER (build for these, do not ask again):",
            *(f"- {note}" for note in self.setup_notes), "",
            "Every value above is already in this project's .env.local. Read each one from "
            "process.env at run time. Never write one into source, a test, a fixture or a "
            "message, and never invent a value for a name that was not supplied.",
            "A capability whose keys were not supplied is not built as though they were. "
            "A checkout with no payment provider configured does not collect a card "
            "number, an expiry and a CVC into plain inputs and tell the reader their "
            "details are processed securely - it took a real card, charged nothing and "
            "threw it away, which is a worse thing to ship than an unfinished page. Build "
            "the step it can honestly do: take the order, say how payment will be taken, "
            "and leave the card to the provider's own form when there is one.",
        ])

    # -- plumbing --------------------------------------------------------
    def _loop(self, registry, *, plan_only: bool = False, review: bool = False,
              prototype: bool = False, verification_kinds=None) -> Loop:
        config = self.config
        if plan_only or review or prototype:
            from dataclasses import replace
            # A drawing writes files and proves nothing, so the verification
            # contract is off for it. It is not a review either: it changes the
            # workspace, and the file tools have to be on the table.
            #
            # It is also the one pass where the safest next word is the wrong
            # one. A build wants 0.2 - the same function, spelled the same way,
            # every time - but a drawing asked at 0.2 returns the same page
            # anyone else would have got, and "the design is flat" is what came
            # back. Nothing here has to compile, so it is allowed to reach.
            config = replace(config, plan_only=plan_only, review=review,
                             temperature=DRAWING_TEMPERATURE if prototype else config.temperature,
                             unit_tests=config.unit_tests and not prototype,
                             e2e_tests=config.e2e_tests and not prototype)
        return Loop(config=config, registry=registry, router=self.router, memory=self.memory,
                    sandbox=self.sandbox, events=self.events, processes=self.processes,
                    browser=self.browser, cancel=self.cancel, approvals=self.approvals,
                    verification_kinds=verification_kinds)

    def _finish(self) -> None:
        """Leave services running for the preview; take everything else down."""
        self.approvals.cancel_all()
        self.memory.close_pending_tools(
            "The run ended before this tool reported a result. Verify the current state before "
            "retrying it.")
        self.processes.release_services()
        self.processes.stop_all(keep_services=True)
        self.browser.close()

    def dispose(self) -> None:
        self.processes.stop_all()
        self.browser.close()

    def snapshot(self) -> dict:
        return {
            "id": self.id, "model": self.router.label, "workspace": str(self.sandbox.root),
            "stack": self.config.stack, "quality": self.config.quality.name,
            "messages": len(self.memory), "compactions": self.memory.compactions,
            "usage": self.router.usage,
            "processes": [job.summary() for job in self.processes.list()],
            "evidence": self.memory.evidence.summary(),
            "plan": self.plan_text, "design": self.design,
        }
