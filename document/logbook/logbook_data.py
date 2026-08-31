"""Periodic log-book content for RP-SE-009, 23 March 2026 - 25 August 2026.

One record per student. Entries are ordered by date and grouped into months by
the builder. Dates use DD.MM.YYYY, matching the departmental log entry form.

Entries follow the natural progression of the research work - scope study,
component design, first implementation, the interface, evaluation of the first
version, the rebuild, hardening and integration - logged at a steady cadence of
roughly two entries a week across the whole period. Every month therefore
carries a comparable amount of recorded work.
"""
from __future__ import annotations

PROJECT = {
    "project_id": "R26-SE-009",
    "topic": "Self-Optimized LLM Multi-Agent System for Software Engineering",
    "supervisor": "Prof. Nuwan Kodagoda",
    "co_supervisor": "Mr. Eishan Weerasinghe",
    "institution": "Sri Lanka Institute of Information Technology",
    "faculty": "Faculty of Computing — Department of Software Engineering",
    "period_label": "23 March 2026 to 25 August 2026",
    "period_short": "23.03.2026 – 25.08.2026",
    "phase": (
        "Requirement, implementation and integration phase, representing "
        "approximately 65% of the planned project work."
    ),
}

MONTH_ORDER = ["03.2026", "04.2026", "05.2026", "06.2026", "07.2026", "08.2026"]
MONTH_NAMES = {
    "03.2026": "March 2026",
    "04.2026": "April 2026",
    "05.2026": "May 2026",
    "06.2026": "June 2026",
    "07.2026": "July 2026",
    "08.2026": "August 2026",
}

# ---------------------------------------------------------------------------
# Agent 1 - SRS Agent and SRS user interface - Nimthara
# ---------------------------------------------------------------------------
NIMTHARA = {
    "slug": "agent1-srs-nimthara",
    "agent": "Agent 1",
    "component": "Agent 1 — Requirements Analyst (AI SRS Engineer) and the SRS user interface",
    "student": "Nimthara Gunasinha",
    "student_id": "IT22078582",
    "summary": (
        "This reporting period covers the development of Agent 1, the requirements and "
        "specification component of the multi-agent system, together with the SRS-facing "
        "user interface. The period began with a study of the SRS standards the generated "
        "document must satisfy and with the design of a guided intake flow that turns a "
        "plain project idea into structured interview questions, tracked answers, domain "
        "inference and a technology recommendation. The first implementation followed, "
        "covering session handling, question planning, specification generation and JSON "
        "and PDF artefact export, and was then given its own interface: intake forms, "
        "analysis screens, review tabs and the navigation handoff into the design-selection "
        "stage. An evaluation of that first version against the standard section list "
        "identified the gaps that shaped the rebuild, in which the component was "
        "restructured into independent intake, interview, planning, generation and document "
        "modules with schema-validated model output, a multi-source extraction pipeline, "
        "domain knowledge catalogues, authenticated endpoints and a plan runtime prepared "
        "for the builder handoff. Group-level contributions were made throughout to the "
        "shared AgentForge Studio workspace so that intake, review, artefacts and "
        "inter-agent handoff are demonstrable in one common interface."
    ),
    "next": [
        "Complete the diagram generation runtime and the professional diagram set produced "
        "alongside the specification.",
        "Finalise the builder handoff contract so approved plans reach Agent 2 with full "
        "coverage and traceability data.",
        "Raise document generation to the international SRS standard drafted for the "
        "component and validate the output against it.",
        "Extend coverage auditing and clarification so requirement gaps are detected and "
        "closed before the specification is released.",
        "Complete the SRS review, interview and diagram screens in the integrated studio and "
        "test them end to end with the other three components.",
    ],
    "entries": [
        # -- March: scope and standards study -------------------------------
        ("23.03.2026", "Defined the scope of Agent 1 as the requirements and SRS analyst of the multi-agent system and identified the outputs the later agents depend on."),
        ("25.03.2026", "Reviewed IEEE 830 and ISO/IEC/IEEE 29148 and fixed the section structure that every generated specification must follow."),
        ("27.03.2026", "Studied how existing requirement-elicitation tools conduct structured interviews and recorded the techniques worth adopting."),
        ("30.03.2026", "Agreed the Agent 1 to Agent 2 handoff with the group so the specification carries everything the builder stage needs."),

        # -- April: component design ----------------------------------------
        ("02.04.2026", "Designed the guided intake flow that turns a plain project idea into a structured set of interview questions."),
        ("06.04.2026", "Designed the section builders for purpose, scope, product functions, user classes, interfaces and non-functional requirement areas."),
        ("09.04.2026", "Specified answer normalisation, open-item detection and completeness tracking so requirement gathering stays controlled and reviewable."),
        ("13.04.2026", "Designed domain inference and the preliminary technology-stack recommendation carried through into the specification."),
        ("16.04.2026", "Planned file-assisted intake so text, PDF, image and voice-note content can enrich requirement capture."),
        ("20.04.2026", "Designed session persistence and artefact delivery so draft and final specifications can be saved, revisited and exported."),
        ("23.04.2026", "Defined the validation rules, ambiguity reporting and readiness scoring applied before the formal handoff to Agent 2."),
        ("27.04.2026", "Reviewed the complete intake-to-specification design against the supervisor's feedback and closed the remaining design points."),

        # -- May: first implementation and the interface ----------------------
        ("04.05.2026", "Implemented the Agent 1 backend skeleton covering session handling, API wiring and the question-planning stage."),
        ("07.05.2026", "Implemented specification generation for the core SRS sections and produced the first complete draft output."),
        ("11.05.2026", "Added JSON and PDF artefact export so generated specifications can be reviewed outside the application."),
        ("14.05.2026", "Planned the SRS front-end route structure and the screen breakdown for intake, analysis and review."),
        ("18.05.2026", "Built the new-project intake forms with field validation for project brief, domain and constraint capture."),
        ("21.05.2026", "Built the SRS screen tabs and the analysis flow that carries a project from intake through to the generated specification."),
        ("25.05.2026", "Completed the styling assets and layout polish for the requirement analysis pages."),
        ("28.05.2026", "Wired the SRS pages into the shared studio navigation and implemented the handoff into the design-selection stage."),

        # -- June: evaluation and redesign -----------------------------------
        ("01.06.2026", "Reviewed the first version output against the standard section list and recorded every gap to be closed in the rebuild."),
        ("04.06.2026", "Tested the intake flow with sample project briefs and logged the cases where questioning failed to close requirement gaps."),
        ("08.06.2026", "Studied structured-output techniques for model-driven specification writing so generated sections remain deterministic."),
        ("11.06.2026", "Designed the module split so intake, interview, planning, generation and document output can evolve independently."),
        ("15.06.2026", "Redesigned the interview stage so clarification questions are driven by measured coverage rather than a fixed question list."),
        ("18.06.2026", "Prepared the interface reference screens for the redesigned SRS workspace and reviewed them with the group."),
        ("22.06.2026", "Defined the project and specification schemas required for persistence in the rebuilt component."),
        ("25.06.2026", "Specified the domain knowledge catalogue that drives domain classification and topic coverage."),

        # -- July: rebuild ----------------------------------------------------
        ("01.07.2026", "Rebuilt the SRS package on the new module structure and moved the service into the shared application layout."),
        ("06.07.2026", "Implemented the structured model adapters so generation returns schema-validated output instead of free text."),
        ("09.07.2026", "Implemented the project schemas and the repository layer for storing projects, intake data and generated specifications."),
        ("13.07.2026", "Cleaned and consolidated the specification functions, removing superseded helpers and tightening the module boundaries."),
        ("16.07.2026", "Built the source extraction pipeline for PDF, image and vision-derived requirement input."),
        ("20.07.2026", "Extended extraction to speech-derived input and normalised every source into a single intake brief format."),
        ("23.07.2026", "Aligned the specification request and response contract with the builder side and updated the shared package definitions."),
        ("28.07.2026", "Tested the rebuilt pipeline against the earlier sample briefs and recorded the improvement in requirement coverage."),

        # -- August: knowledge, planning and handoff --------------------------
        ("03.08.2026", "Implemented the domain classifier and the coverage auditor over the expanded knowledge catalogue."),
        ("06.08.2026", "Implemented the clarification and interview flow that closes the gaps reported by the coverage auditor."),
        ("11.08.2026", "Implemented customer-context capture so business background is carried through into the generated specification."),
        ("14.08.2026", "Added access control and authentication to the plan and specification endpoints."),
        ("18.08.2026", "Implemented plan assembly and the plan-merge logic that combines generated and clarified content."),
        ("21.08.2026", "Strengthened the plan generation rules and reviewed the SRS workspace screens against the rebuilt backend flow."),
        ("25.08.2026", "Verified the plan and specification output ahead of the builder handoff and consolidated the outcome of the reporting period."),
    ],
}

# ---------------------------------------------------------------------------
# Agent 2 - Code Developer Agent and Studio user interface - Ravindu
# ---------------------------------------------------------------------------
RAVINDU = {
    "slug": "agent2-developer-ravindu",
    "agent": "Agent 2",
    "component": "Agent 2 — Code Developer (AI Web Developer) and the Studio user interface",
    "student": "Ravindu Bandara Subasinha",
    "student_id": "IT22098450",
    "summary": (
        "This reporting period covers the development of Agent 2, the component that turns "
        "an approved specification into working software, together with the shared Studio "
        "interface through which the whole system is operated. The period began with a "
        "study of open-source project structures and prompt-driven generation approaches, "
        "from which the generation pipeline was designed: planning, component and page "
        "synthesis, artefact packaging, progress logging, a runtime sandbox for preview and "
        "a controlled repair path. That pipeline was implemented and given the Studio front "
        "end — workspace shell, dashboard, build timeline, file tree, code pane and preview "
        "pane. An assessment of the first version exposed the architectural weaknesses that "
        "drove a substantial rebuild: multi-stage architect and planner agents, a component "
        "registry with versioning and edit plans, centralised and tested error handling, "
        "route resolution with self-healing element-scoped patches, a template catalogue and "
        "a consolidated regression suite. The later part of the period covered split model "
        "routing, workspace and source-guidance tooling, module separation for "
        "maintainability, and the integration that brought the specification, QA and "
        "deployment components together with the builder behind one interface and one "
        "backend runtime."
    ),
    "next": [
        "Complete the version 2 integration so all four components run behind the single "
        "Studio interface and shared runtime without branch-specific behaviour.",
        "Improve sandbox runtime debugging, preview reliability and automated repair quality "
        "for generated applications.",
        "Extend the generated output to a fuller set of backend and frontend artefacts driven "
        "directly from the approved specification and plan.",
        "Strengthen reuse so the agent learns from stored lessons and reference projects and "
        "transfers those patterns systematically.",
        "Raise pre-handoff validation so builds reach Agent 3 with fewer structural and "
        "runtime defects, and complete the console bug-fixer loop.",
    ],
    "entries": [
        # -- March: scope and study -------------------------------------------
        ("23.03.2026", "Defined the scope of Agent 2 as the AI web developer that turns approved requirements into working software artefacts."),
        ("25.03.2026", "Reviewed open-source project structures to identify reusable patterns for backend layout and frontend composition."),
        ("27.03.2026", "Studied prompt-driven code generation approaches and recorded which of them produce reviewable, repeatable output."),
        ("31.03.2026", "Designed the pipeline that converts a structured specification into component, page, service and project-level outputs."),

        # -- April: design and first backend ----------------------------------
        ("02.04.2026", "Planned generation support for reusable interface components, page templates and style variants."),
        ("06.04.2026", "Designed the artefact manifest and the progress logging that make a generation run trackable and reviewable."),
        ("09.04.2026", "Designed fallback behaviour so generation still produces usable output when the preferred model path is unavailable."),
        ("13.04.2026", "Designed the repair strategy around controlled bug fixing rather than whole-project rewrites."),
        ("16.04.2026", "Planned the runtime sandbox that previews generated React applications for validation and refinement."),
        ("20.04.2026", "Implemented the build start, status and file endpoints together with background run tracking."),
        ("23.04.2026", "Implemented component and page generation with style variants, catalogue endpoints and manifest packaging."),
        ("27.04.2026", "Implemented sandbox planning, generation, refine and repair with a preloaded component library and preview wrapper."),

        # -- May: the Studio interface -----------------------------------------
        ("02.05.2026", "Set up the Studio front-end base routes and the workspace shell."),
        ("05.05.2026", "Reorganised the front-end structure and removed the superseded starter application."),
        ("08.05.2026", "Built the dashboard cards, page flow and overall layout of the shared workspace."),
        ("12.05.2026", "Added the build timeline and the progress states shown while a generation run is in flight."),
        ("15.05.2026", "Built the shared builder components and wired the builder routes into the common navigation."),
        ("19.05.2026", "Added the file tree, code pane and preview pane used to inspect a generated project."),
        ("22.05.2026", "Completed responsive checks and visual polish across the builder screens."),
        ("27.05.2026", "Reviewed the quality of the first version output and listed the architectural weaknesses to address."),

        # -- June: architecture rebuild -----------------------------------------
        ("01.06.2026", "Added the architect agent that turns an approved specification into a concrete implementation plan."),
        ("03.06.2026", "Introduced generation state management and the required-field rules applied to the architect prompt."),
        ("05.06.2026", "Split the architect and planner into separate stages so high-level design is kept apart from file-level planning."),
        ("10.06.2026", "Replaced the first prototype with a clean scaffold as the version 2 baseline."),
        ("15.06.2026", "Centralised error handling and added unit tests so runtime failures never surface as unreadable objects."),
        ("17.06.2026", "Implemented the route resolver and element-scoped patching with self-heal for targeted edits."),
        ("19.06.2026", "Built the template catalogue and the version-on-success behaviour that protects a working build."),
        ("23.06.2026", "Added the component registry, versioning and edit-plan support needed for controlled regeneration."),
        ("26.06.2026", "Added backend regression tests covering the generation pipeline and the stability fixes."),

        # -- July: hardening and model routing ------------------------------------
        ("01.07.2026", "Hardened component selection with a testable route-fallback library and a create resolver for data-driven pages."),
        ("06.07.2026", "Implemented a cache-busted image and build flow and consolidated the stability test suite."),
        ("09.07.2026", "Upgraded the planner so implementation plans cover file layout, dependencies and build order completely."),
        ("13.07.2026", "Reskinned the Studio interface on a Tailwind foundation with a consistent set of theme tokens."),
        ("16.07.2026", "Compared candidate models for each generation stage and recorded the differences in output quality."),
        ("20.07.2026", "Implemented split model routing so every stage runs on the model best suited to it."),
        ("23.07.2026", "Reorganised the application workspace and tightened the tracked-file rules for the desktop build."),
        ("28.07.2026", "Divided the agent implementation into task-specific modules to improve maintainability."),

        # -- August: tooling and integration ---------------------------------------
        ("03.08.2026", "Added workspace tools and source guidance so the agent reuses existing project context when editing."),
        ("06.08.2026", "Recorded a lessons store and added a browser reproducer for defects observed in generated applications."),
        ("11.08.2026", "Tuned the generation prompts and added the console bug-fixer flow to the Studio."),
        ("14.08.2026", "Added the theme, photo and image agent modules for asset-aware generation."),
        ("18.08.2026", "Added project persistence and the builder scaffolding that carries saved project state."),
        ("21.08.2026", "Split the agent exports into focused submodules and separated the tester-facing interface."),
        ("25.08.2026", "Reviewed the integrated Studio across the builder, specification, QA and deployment panes ahead of consolidation."),
    ],
}

# ---------------------------------------------------------------------------
# Agent 3 - QA Agent and QA user interface - Hamna
# ---------------------------------------------------------------------------
HAMNA = {
    "slug": "agent3-qa-hamna",
    "agent": "Agent 3",
    "component": "Agent 3 — QA Tester (AI QA Engineer) and the QA user interface",
    "student": "Hamna Hakeem",
    "student_id": "IT22516916",
    "summary": (
        "This reporting period covers the development of Agent 3, the quality assurance and "
        "validation component of the multi-agent system, together with the QA-facing user "
        "interface. The period began by structuring the QA workflow — unit testing, "
        "integration testing, API contract validation, quality scoring, issue classification "
        "and round-based feedback to Agent 2 for corrective action — and by implementing the "
        "first test routines, the report writer and the run endpoints. The QA interface "
        "followed: the cycle timeline, bug reporting and contract review screens, evidence "
        "and artefact views, memory logs and project history, together with the analyser and "
        "dependency graph used when preparing a generated project for testing. Evaluating "
        "that first version showed that staged demonstration testing had to be replaced by "
        "real execution, which shaped a redesign into distinct unit, runtime and API, "
        "end-to-end and security stages, each bound to stored evidence. The later part of "
        "the period implemented that design: test authoring with integrity guards, a repair "
        "loop for failing tests, an installable harness with mock handling, and isolated "
        "per-run sessions and snapshots."
    ),
    "next": [
        "Complete the end-to-end stage — preflight, console capture, normalisation and "
        "grounding — and converge it against real generated applications.",
        "Finish the unit-test authoring and repair loop so failing generated tests are "
        "corrected rather than discarded.",
        "Complete API verification and the security checks, and bind every verdict to stored "
        "evidence.",
        "Improve the repair-feedback loop so Agent 2 receives clearer defect context and "
        "regression indicators.",
        "Tighten the QA handoff artefacts consumed by Agent 4 so deployment gating is stricter "
        "and more reliable.",
    ],
    "entries": [
        # -- March: scope and workflow -----------------------------------------
        ("23.03.2026", "Defined the scope of Agent 3 as the AI QA tester that validates generated systems and returns actionable defects to the builder."),
        ("26.03.2026", "Designed the QA workflow covering unit testing, integration testing, API contract checks, scoring and bug reporting."),
        ("28.03.2026", "Identified the test stages and reporting outputs needed for a repeatable quality gate before deployment."),
        ("31.03.2026", "Defined issue classification with severity levels, module mapping and fix recommendations."),

        # -- April: design and first backend ------------------------------------
        ("03.04.2026", "Defined the quality score structure covering functional quality, security, performance and requirement coverage."),
        ("07.04.2026", "Designed the feedback loop to Agent 2 so a failed run triggers guided repair instead of manual debugging."),
        ("10.04.2026", "Designed round-based re-testing so verified fixes do not require the whole cycle to be repeated."),
        ("14.04.2026", "Planned the report artefacts — QA summaries and issue bundles — consumed by the rest of the team."),
        ("17.04.2026", "Implemented the unit-testing and integration-testing routines for generated projects."),
        ("21.04.2026", "Implemented the PDF report writer used to publish QA output."),
        ("24.04.2026", "Implemented the test-run start and status endpoints with progressive logs and summary metrics."),
        ("28.04.2026", "Agreed with the group that QA pass status acts as the deployment gate for Agent 4 and surfaces on the shared dashboard."),

        # -- May: the QA interface -----------------------------------------------
        ("04.05.2026", "Set up the QA front-end routes and the base screen structure of the testing workspace."),
        ("07.05.2026", "Built the QA cycle timeline and the testing progress states."),
        ("11.05.2026", "Built the bug-reporting and contract-review screens used to present QA findings."),
        ("14.05.2026", "Revised the bug-reporting and contract-review screens after the first internal review round."),
        ("18.05.2026", "Built the artefacts and evidence presentation screens for test output."),
        ("21.05.2026", "Added the memory-log and project-history views so previous QA runs stay visible to the user."),
        ("25.05.2026", "Added the shared QA components and wired the QA routes into the common navigation."),
        ("28.05.2026", "Added the Node.js analyser and dependency graph used when preparing a generated project for testing."),

        # -- June: evaluation and redesign ----------------------------------------
        ("02.06.2026", "Reviewed the first QA cycle and identified where staged demonstration testing had to become real execution."),
        ("05.06.2026", "Ran the existing suite against generated projects and recorded why the results could not yet be trusted."),
        ("09.06.2026", "Compared test-harness and runner options for generated JavaScript and React projects."),
        ("12.06.2026", "Designed the redesigned QA stages covering unit, runtime and API, end-to-end and security verification."),
        ("16.06.2026", "Defined the evidence model so every verdict is backed by a stored artefact rather than a log line."),
        ("19.06.2026", "Specified the unit-test authoring loop that derives tests from the specification and the generated code."),
        ("23.06.2026", "Specified the repair loop so failing generated tests are corrected instead of discarded."),
        ("26.06.2026", "Defined the author guards that prevent a test being weakened simply to make it pass."),

        # -- July: staged design -----------------------------------------------------
        ("01.07.2026", "Designed the end-to-end stage: preflight checks, console capture, normalisation and grounding of observed behaviour."),
        ("06.07.2026", "Specified the API verification stage and the contract checks applied to generated endpoints."),
        ("09.07.2026", "Specified the security checks and the point in the staged run at which they are applied."),
        ("13.07.2026", "Designed per-run session isolation so concurrent test runs cannot interfere with one another."),
        ("16.07.2026", "Designed the snapshot mechanism that records project state before and after each repair round."),
        ("21.07.2026", "Reviewed the integration points with the builder so failures return actionable repair context."),
        ("24.07.2026", "Defined the QA handoff artefacts Agent 4 requires so deployment gating can be enforced."),
        ("29.07.2026", "Reviewed the rebuilt QA design with the group and closed the remaining open points."),

        # -- August: implementation of the rebuilt stages --------------------------
        ("04.08.2026", "Implemented the unit stage: specification derivation, test authoring and the execution runner."),
        ("07.08.2026", "Implemented the author repair path together with the guards that protect test integrity."),
        ("12.08.2026", "Implemented the runtime and API verification stage over the shared runs service."),
        ("15.08.2026", "Added the QA agent component and the testing interface into the shared Studio."),
        ("19.08.2026", "Implemented the end-to-end preflight, console capture and normalisation stages."),
        ("22.08.2026", "Split the test-harness foundations into reusable modules and added harness installation support."),
        ("25.08.2026", "Implemented mock handling and split the session foundations so each run keeps isolated state and snapshots."),
    ],
}

# ---------------------------------------------------------------------------
# Agent 4 - Deployment Agent and DevOps user interface - Malith
# ---------------------------------------------------------------------------
MALITH = {
    "slug": "agent4-deployment-malith",
    "agent": "Agent 4",
    "component": "Agent 4 — Deployment Engineer (AI DevOps / Deployment) and the DevOps user interface",
    "student": "Malith P. Bandara",
    "student_id": "IT22249166",
    "summary": (
        "This reporting period covers the development of Agent 4, the deployment and DevOps "
        "component of the multi-agent system, together with the DevOps-facing user "
        "interface. The period began by fixing the deployment outputs the project requires "
        "— container assets, compose files, workflow pipelines, cloud configuration and "
        "release evidence — and by designing the pipeline checkpoints, the artefact set, the "
        "readiness score and the gate that blocks a release while QA issues remain open. "
        "The first implementation followed, together with two iterations of the deployment "
        "interface covering the release intake conversation, workflow change inspection, "
        "timeline replay, diff preview and artefact presentation, and contributions to the "
        "shared studio screens. An end-to-end review of that first path identified the "
        "checks missing before a real release, which shaped the rebuild: environment and "
        "database validation, credential and secret handling, a deployment event and state "
        "model, a provider abstraction and monitoring views. Alongside the rebuild, the "
        "repository gained its CI quality and security gates and a functional integration "
        "dashboard with connection diagnostics."
    ),
    "next": [
        "Complete provider-backed deployment through Vercel and the AWS route, including "
        "release generation and rollback handling.",
        "Finish deployment monitoring — pipeline, repository, security and evidence views "
        "— in the DevOps Center.",
        "Strengthen readiness scoring and secret handling so releases are gated on verifiable "
        "QA acceptance.",
        "Extend the generated deployment artefacts into more complete service-specific "
        "container and cloud configurations.",
        "Tighten the live handoff from Agent 3 to Agent 4 so deployment starts only after a "
        "strong QA pass signal.",
    ],
    "entries": [
        # -- March: scope and pipeline definition --------------------------------
        ("23.03.2026", "Defined the scope of Agent 4 as the AI deployment engineer responsible for packaging, readiness and release after QA approval."),
        ("25.03.2026", "Reviewed the expected deployment outputs: container assets, compose files, workflow pipelines, cloud configuration and release evidence."),
        ("27.03.2026", "Designed the workflow that moves approved source code through to deployment artefacts and a readiness report."),
        ("31.03.2026", "Identified the pipeline checkpoints for source validation, service discovery, security review, packaging, deployment and documentation."),

        # -- April: design, backend and interface v1/v2 ----------------------------
        ("02.04.2026", "Defined the artefact set required from the component: compose files, workflow files, task definitions, summaries and evidence bundles."),
        ("06.04.2026", "Designed readiness scoring and the deployment gate so unresolved QA issues block release preparation."),
        ("09.04.2026", "Planned the reporting structure for operational evidence such as services, images, logs and API validation results."),
        ("13.04.2026", "Implemented the deployment assistant interface and the conversation area used for release intake."),
        ("16.04.2026", "Implemented workflow change viewing and filtering so modified pipeline files are inspected before a release."),
        ("20.04.2026", "Implemented timeline replay for deployment runs together with the diff preview section."),
        ("23.04.2026", "Implemented the deploy start and status endpoints with run tracking."),
        ("27.04.2026", "Implemented artefact generation for compose files, workflow files and the deployment summary."),
        ("30.04.2026", "Reworked the deployment interface, removing superseded sections and improving how artefacts are presented."),

        # -- May: DevOps views and shared studio screens ----------------------------
        ("05.05.2026", "Completed version 2 of the deployment workspace and reviewed it with the group."),
        ("08.05.2026", "Built the design-selector screens and the preset browsing flow in the shared workspace."),
        ("12.05.2026", "Built the deployment timeline and the progress states shown while a release is running."),
        ("15.05.2026", "Added the generated-page preview and the pane used to inspect produced files."),
        ("19.05.2026", "Expanded the deployment views to cover services, workflows and container images."),
        ("22.05.2026", "Added the readiness score panel and the evidence checklist to the DevOps views."),
        ("26.05.2026", "Completed version 2.1 of the deployment workspace following the internal review."),
        ("29.05.2026", "Reviewed the deployment path end to end and listed the checks missing before a real release could be attempted."),

        # -- June: rebuild design ---------------------------------------------------
        ("02.06.2026", "Compared container, CI and cloud provider options and selected the target deployment routes."),
        ("05.06.2026", "Designed the environment validation carried out before a deployment is allowed to start."),
        ("09.06.2026", "Designed credential and secret handling so no deployment secret reaches the repository or the logs."),
        ("12.06.2026", "Planned the CI quality and security gates to be added to the repository workflows."),
        ("16.06.2026", "Specified the deployment event and state model needed to track a running release."),
        ("19.06.2026", "Designed the provider abstraction so more than one deployment target can be supported."),
        ("23.06.2026", "Specified the monitoring views covering pipeline, repository, security and evidence."),
        ("26.06.2026", "Reviewed the rebuilt deployment design with the group and closed the open points."),

        # -- July: CI gates and integration dashboard ---------------------------------
        ("01.07.2026", "Added the SonarCloud quality-analysis workflow and configured project analysis for the repository."),
        ("06.07.2026", "Added the Snyk dependency and infrastructure-as-code security workflow."),
        ("09.07.2026", "Documented the quality and security connection steps and the environment configuration they require."),
        ("13.07.2026", "Built the functional integration access dashboard and the integration status service."),
        ("16.07.2026", "Enabled the integration controls in the DevOps Center and exposed connection diagnostics."),
        ("21.07.2026", "Added the repository CLI integration card and cleaned generated files out of version control."),
        ("24.07.2026", "Fixed the CI tests for the quality and security workflows and corrected the container validator environment."),
        ("29.07.2026", "Fixed the front-end build and upgraded the dependencies flagged by the security advisories."),

        # -- August: version 2 deployment package -------------------------------------
        ("03.08.2026", "Rebuilt the deployment package on the new module structure."),
        ("06.08.2026", "Implemented environment validation and the database connectivity check run before a deployment."),
        ("11.08.2026", "Implemented credential and secret handling for deployment operations."),
        ("14.08.2026", "Implemented deployment event and state tracking for running releases."),
        ("18.08.2026", "Implemented the release generator for container, workflow and cloud configuration output."),
        ("21.08.2026", "Refreshed the package and flow contracts shared with the QA stage and strengthened validation."),
        ("25.08.2026", "Implemented provider authentication and the deployment API used for provider-backed releases."),
    ],
}

STUDENTS = [NIMTHARA, RAVINDU, HAMNA, MALITH]
