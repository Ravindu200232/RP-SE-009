"""What a run is allowed to build, how hard it verifies, and where.

Two deliberate simplifications relative to the JavaScript engine this is
ported from:

* **There are no interaction modes.** The old engine had planner/acceptable/
  auto gates, so the same build behaved differently depending on which one was
  selected and half the code existed to reconcile them. A studio build is
  unattended by definition, so the engine plans, designs and builds in one
  pass. The permanent command denylist in `policy.py` still refuses
  destructive work; unattended never meant unguarded.
* **There is one build quality, and ultra belongs to verification.** Quality
  used to be a four-way picker whose top setting also doubled as a reasoning
  level, so choosing it applied the same audit gates twice. Building now runs
  at one profile, and the deep profile is spent where deep actually pays: the
  unit and end-to-end suites, which are the evidence anyone reads.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from pathlib import Path


# --------------------------------------------------------------------------
# Builder stacks
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Stack:
    """The fixed application contract a build works inside.

    The stack is product-owned, not a model decision: a run must never spend
    turns debating a framework, and must never migrate an existing project to
    another one.
    """

    id: str
    product: str
    tech: str
    language: str
    unit_tool: str
    e2e_tool: str
    rules: tuple[str, ...]
    # Skills this stack always needs, whatever the request happens to mention.
    skills: tuple[str, ...] = ()
    # Not part of the stack's contract, so a request can ask for them and a
    # request can rule them out.
    extras: tuple[str, ...] = ()
    parallel_units: bool = False


NEXT_MONGO = Stack(
    id="nextjs-mongo",
    product="A full-stack Next.js web application backed by MongoDB.",
    tech="Next.js (App Router) + React + MongoDB/Mongoose",
    language="JavaScript (ESM)",
    unit_tool="Vitest",
    e2e_tool="AgentX browser journeys (direct CDP)",
    rules=(
        "One Next.js application written in JavaScript. API work belongs in route handlers, not a second server.",
        "Persist through the project's Mongoose data layer; no other application database.",
        "Use Vitest for project unit and integration tests.",
        "Use the engine's direct-CDP browser journeys for E2E; do not add a project E2E framework. "
        "Check the routes themselves with curl first - a page that refuses to render records is not "
        "a route that refuses to return them.",
        "Detect the installed versions, router shape, package manager and code style from the project itself.",
        "Never migrate the generated application to another framework, database or distributed architecture.",
    ),
    skills=("html-prototype", "stack-nextjs", "stack-testing", "stack-debug",
            "stack-security"),
)

MERN_MICRO = Stack(
    id="mern-microservices",
    product="A MERN application split into Express microservices behind one gateway.",
    tech="React (Vite) + Express microservices + MongoDB/Mongoose + API gateway",
    language="JavaScript (ESM)",
    unit_tool="Vitest",
    e2e_tool="AgentX browser journeys (direct CDP)",
    rules=(
        "React plus Express/Node microservices, written in JavaScript.",
        "Each service owns its own collections through its own Mongoose layer and never reaches into another service's data.",
        "Use Vitest in every service and in the client.",
        "Use the engine's direct-CDP browser journeys for E2E; do not add a project E2E framework. "
        "Check the routes themselves with curl first - a page that refuses to render records is not "
        "a route that refuses to return them.",
        "Every service must run locally with plain Node and no container runtime. Docker is a deliverable, never a requirement for running or verifying the app.",
        "Expose the whole application through ONE public port: a gateway serves the built client and proxies each service under its own path prefix.",
        "Generate a Dockerfile (and a compose file when there is more than one service) as build output, but never verify through it.",
        "Never collapse the services back into one server, and never migrate off this architecture.",
    ),
    skills=("html-prototype", "stack-mern", "stack-testing", "stack-debug",
            "stack-security"),
    parallel_units=True,
)

STACKS = {s.id: s for s in (NEXT_MONGO, MERN_MICRO)}
DEFAULT_STACK = NEXT_MONGO.id


def stack_for(value: str | None) -> Stack:
    return STACKS.get(str(value or "").strip(), STACKS[DEFAULT_STACK])


def stack_of(workspace) -> str:
    """Which stack a project on disk was built as, from its own manifest.

    Reading the request instead is fine when there is no project yet, and
    wrong the moment there is one: an edit whose words happen not to mention
    microservices was handed the single-application contract for a repository
    full of services, and - because the stack is part of what makes a
    conversation the same conversation - was given a new agent and a context
    window starting again from nothing.

    Nothing is guessed from a directory listing. A workspaces manifest is a
    multi-package repository because npm says so; `next` among the root
    dependencies is a Next application for the same reason.
    """
    try:
        manifest = json.loads(
            (Path(workspace) / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    if not isinstance(manifest, dict):
        return ""
    if manifest.get("workspaces"):
        return MERN_MICRO.id
    dependencies = {**(manifest.get("dependencies") or {}),
                    **(manifest.get("devDependencies") or {})}
    return NEXT_MONGO.id if "next" in dependencies else ""


def detect_stack(prompt: str) -> str:
    """Pick a stack from what the user asked for, defaulting to Next.js.

    Only an explicit ask moves the build off the default: a passing mention of
    "service" in a sentence about a booking service is not an architecture.
    """
    text = str(prompt or "").lower()
    signals = ("microservice", "micro service", "micro-service", "mern",
               "api gateway", "separate services")
    return MERN_MICRO.id if any(s in text for s in signals) else DEFAULT_STACK


# --------------------------------------------------------------------------
# Quality
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Quality:
    """How much evidence a stage must produce before it may call itself done."""

    name: str
    reasoning: str
    unit_floor: int
    e2e_floor: int
    max_heal: int
    read_depth: str
    final_audit: bool
    summary: str


# Building. Deep enough to trace a change into its callers and prove it runs.
BUILD_QUALITY = Quality(
    name="default",
    reasoning="medium",
    unit_floor=0,
    e2e_floor=80,
    max_heal=3,
    read_depth="callers-and-contracts",
    final_audit=False,
    summary=("Balanced build verification: trace changed code into its direct "
             "callers and consumers, cover meaningful boundary and error states, "
             "and prove the app actually runs."),
)

# Verification. The unit and E2E suites are the evidence anyone reads, so this
# is the one place the deep profile earns its cost.
VERIFY_QUALITY = Quality(
    name="ultra",
    reasoning="max",
    unit_floor=0,
    e2e_floor=100,
    max_heal=5,
    read_depth="deep-cross-layer",
    final_audit=True,
    summary=("Deep evidence-first verification: exhaustive critical-flow coverage, "
             "source-context repair packets, and an independent audit of the "
             "finished suite before it is reported as passing."),
)


def quality_prompt(q: Quality) -> str:
    lines = [
        f"QUALITY PROFILE: {q.name.upper()} - {q.summary}",
        "- Unit/source coverage is optional diagnostic information, not a completion requirement. Do not add or rerun tests solely to raise a percentage.",
        f"- Critical E2E requirement coverage floor: {q.e2e_floor}%.",
        "- Runtime evidence must exercise the real public boundary; a build, a PID, a screenshot or one HTTP status is not enough.",
        "- Prove the requested behaviours. Never weaken an assertion, skip a required flow or fabricate evidence.",
    ]
    if q.final_audit:
        lines.append(
            "- Before reporting a pass, re-read the highest-risk changed code and its "
            "callers, challenge the happy path, and repair anything the suite did not catch.")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Run configuration
# --------------------------------------------------------------------------
DEFAULT_CONTEXT_TOKENS = 24_000


@dataclass
class Config:
    """Everything one run needs, resolved before the loop starts."""

    workspace: Path
    model: str = ""
    host: str = ""
    stack: str = DEFAULT_STACK
    quality: Quality = BUILD_QUALITY
    think: bool = False
    context_tokens: int = DEFAULT_CONTEXT_TOKENS
    max_iterations: int = 0            # 0 = no fixed cap; checkpoints renew room
    temperature: float = 0.2
    # One turn stays bounded however large the window, which is for useful input
    # rather than a licence to run for half an hour.
    max_response_tokens: int = 16_384
    response_timeout: int = 240
    stream_stall_timeout: int = 60
    command_timeout: int = 1_800
    unit_tests: bool = True
    e2e_tests: bool = True
    review: bool = False               # read-only inspection pass
    plan_only: bool = False
    prototype_only: bool = False
    state_root: Path | None = None     # cross-project learned lessons
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.workspace = Path(self.workspace).resolve()
        if self.state_root is None:
            self.state_root = Path(
                os.environ.get("AGENTX_STATE") or Path.home() / ".agentx")

    @property
    def stack_contract(self) -> Stack:
        return stack_for(self.stack)

    def for_verification(self) -> "Config":
        """The same run, at the profile the test stages are held to."""
        return replace(self, quality=VERIFY_QUALITY)
