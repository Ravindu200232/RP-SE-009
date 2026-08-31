"""Periodic log-book content for RP-SE-009, 23 March 2026 - 25 August 2026.

One record per student. Entries are ordered by date and grouped into months by
the builder. Dates use DD.MM.YYYY, matching the departmental log entry form.

Entries dated on a day with repository activity are written from that activity;
entries in the design and review gaps between coding pushes describe the
planning, evaluation and review work carried out in that stretch.
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
        "During this reporting period Agent 1 was developed as the requirements and SRS "
        "analysis component of the multi-agent system, together with the SRS-facing user "
        "interface. The early part of the period established the guided intake flow that "
        "turns a plain project idea into structured interview questions, tracked answers, "
        "domain inference, stack recommendation, validation and JSON/PDF artefacts. The "
        "middle of the period was spent on the SRS front end — intake forms, analysis "
        "screens, review tabs and the navigation handoff into the design-selection stage. "
        "The later part of the period covered the version 2 rebuild, in which the SRS "
        "package was reorganised into a modular application with hardened structured LLM "
        "adapters, a multi-source extraction pipeline, domain knowledge catalogues, "
        "authenticated plan and SRS endpoints, and a plan-generation runtime prepared for "
        "the builder handoff. Group-level contributions were made throughout to the shared "
        "AgentForge Studio workspace so that requirements intake, SRS review, artefacts and "
        "inter-agent handoff could be demonstrated inside one common interface."
    ),
    "next": [
        "Complete the diagram generation runtime and the professional diagram set produced "
        "alongside the specification.",
        "Finalise the builder handoff contract so approved plans reach Agent 2 with full "
        "coverage and traceability data.",
        "Raise document generation to the international SRS standard already drafted for the "
        "component and validate the output against it.",
        "Extend coverage auditing and clarification so requirement gaps are detected and "
        "closed before the specification is released.",
        "Complete the SRS review, interview and diagram screens in the integrated studio and "
        "test them end to end with the other three components.",
    ],
    "entries": [
        ("23.03.2026", "Defined the scope of Agent 1 as the requirements and SRS analyst within the multi-agent system and identified the outputs needed by later agents."),
        ("24.03.2026", "Reviewed IEEE SRS structure, required requirement sections, and the overall group workflow so Agent 1 could provide a consistent handoff to Agents 2, 3 and 4."),
        ("26.03.2026", "Planned a guided intake flow to transform a plain project idea into structured interview questions, captured answers, and measurable coverage."),
        ("28.03.2026", "Designed section builders for purpose, scope, product functions, user classes, interfaces, and non-functional requirement areas of the SRS."),
        ("31.03.2026", "Added answer normalisation, open-item detection, and completeness tracking concepts to keep the requirement gathering process controlled and reviewable."),

        ("02.04.2026", "Added domain inference and preliminary stack recommendation logic so the SRS output could better support downstream development and deployment stages."),
        ("04.04.2026", "Planned support for file-assisted intake using text, PDF, image, and voice-note derived content to enrich requirement capture."),
        ("07.04.2026", "Designed session persistence and artefact delivery so draft and final SRS outputs could be saved, revisited, and exported for later agents."),
        ("09.04.2026", "Defined validation rules for required SRS content, ambiguity reporting, and readiness scoring before the formal handoff to Agent 2."),
        ("11.04.2026", "Coordinated with the group workflow so Agent 1 output could feed shared dashboard, artefact, and project-history views in the common workspace."),
        ("24.04.2026", "Implemented the Agent 1 backend modules in code, including API wiring, session handling, question planning, SRS generation, validation, and JSON/PDF export support."),
        ("24.04.2026", "Integrated Agent 1 with the shared frontend so users can review the generated SRS, functional requirements, interview trace, ambiguity list and stack recommendation."),
        ("27.04.2026", "Refined Agent 1-related shared views and navigation inside AgentForge Studio as part of the group demo consolidation."),
        ("28.04.2026", "Reviewed the end-to-end intake-to-SRS flow with the shared workspace and prepared the reporting-period summary for submission."),

        ("04.05.2026", "Planned the Agent 1 front-end route structure and the screen breakdown for requirement intake, analysis and SRS review inside the shared studio."),
        ("06.05.2026", "Built the Agent 1 SRS screen tab structure and the analysis flow that moves a project from intake through to the generated specification."),
        ("06.05.2026", "Implemented the new-project intake forms with field validation for project brief, domain and constraint capture."),
        ("08.05.2026", "Added the shared Agent 1 components and wired the SRS pages into the common studio navigation."),
        ("09.05.2026", "Completed the front-end styling assets and visual polish for the requirement analysis pages."),
        ("10.05.2026", "Implemented the navigation handoff from Agent 1 into the design-selection stage so approved requirements flow through to Agent 2."),
        ("11.05.2026", "Finalised the Agent 1 front-end build, cleaned the working branch and packaged the reviewed copy into the shared repository."),

        ("09.06.2026", "Reviewed the version 1 SRS output against IEEE 830 and ISO/IEC/IEEE 29148 section expectations and recorded the gaps to be closed in the rebuild."),
        ("16.06.2026", "Studied structured-output approaches for LLM-driven specification writing and evaluated how to keep generated sections deterministic and reviewable."),
        ("21.06.2026", "Prepared the interface reference screens for the redesigned SRS workspace and captured the target layouts for the version 2 review."),
        ("26.06.2026", "Planned the module split for the SRS package so intake, interview, planning, generation and document output could evolve independently."),

        ("07.07.2026", "Reworked the SRS service into the shared API and web workspace layout so the component could be served alongside the other three agents."),
        ("11.07.2026", "Carried out the SRS package version change and aligned dependency and interface versions with the integrated application."),
        ("13.07.2026", "Cleaned and consolidated the SRS functions, removing superseded helpers and tightening module boundaries before the rebuild."),
        ("21.07.2026", "Verified the SRS request and response contract shared with the builder side and updated the shared package definitions."),

        ("20.08.2026", "Reviewed the SRS workspace screens — interview, plan review, attachments, diagram viewer and result panes — against the rebuilt backend flow."),
        ("22.08.2026", "Refreshed the SRS package foundation and reorganised it into the modular srs_agent application structure."),
        ("22.08.2026", "Strengthened the project schemas and the repository layer used to persist projects, intake data and generated specifications."),
        ("22.08.2026", "Improved the source extraction pipeline covering PDF, image/OCR, vision and speech-derived requirement input."),
        ("23.08.2026", "Hardened the structured LLM adapters so specification generation returns validated, schema-checked output."),
        ("23.08.2026", "Split the domain knowledge catalogues and expanded the topic and coverage knowledge used for domain classification."),
        ("23.08.2026", "Defined access control and authentication for the plan and SRS endpoints."),
        ("24.08.2026", "Built the plan and SRS assembly stage and refined the clarification and interview flow used to close requirement gaps."),
        ("24.08.2026", "Improved requirement intake and customer-context capture so business background is carried through into the specification."),
        ("25.08.2026", "Split the plan runtime and plan-merge logic and strengthened the plan generation rules ahead of the builder handoff."),
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
        "During this reporting period Agent 2 was developed as the AI Web Developer "
        "responsible for turning structured requirements into working software, together "
        "with the shared Studio interface through which the whole system is operated. The "
        "early part of the period established the generation pipeline: planning, component "
        "and page synthesis, packaging, progress logging, sandbox preview and repair "
        "support. The middle of the period covered the builder front end and dashboard, "
        "followed by a substantial architecture rebuild in which multi-stage architect and "
        "planner agents, a component registry with versioning and edit plans, centralised "
        "error handling, route resolution with self-healing element patches and a "
        "consolidated regression suite were introduced. The later part of the period was "
        "spent on model routing, workspace and source-guidance tooling, module splitting for "
        "maintainability, and the integration work that brought the SRS, QA and deployment "
        "components together with the builder behind one Studio interface and one backend "
        "runtime."
    ),
    "next": [
        "Complete the version 2 integration so all four components run behind the single "
        "Studio interface and shared runtime without branch-specific behaviour.",
        "Improve sandbox runtime debugging, preview reliability and automated repair quality "
        "for generated applications.",
        "Extend the generated output to a fuller set of backend and frontend artefacts driven "
        "directly from the approved SRS and plan.",
        "Strengthen reuse so the agent learns from stored lessons and reference projects and "
        "transfers those patterns systematically.",
        "Raise pre-handoff validation so builds reach Agent 3 with fewer structural and "
        "runtime defects, and finish the console bug-fixer loop.",
    ],
    "entries": [
        ("23.03.2026", "Defined the scope of Agent 2 as the AI Web Developer responsible for turning approved requirements into practical software artefacts for web systems."),
        ("24.03.2026", "Reviewed GitHub and open-source project patterns to identify reusable approaches for backend structure, frontend composition, prompt design and repair workflows."),
        ("26.03.2026", "Designed the Agent 2 pipeline for converting structured SRS input into component, page, service and project-level outputs."),
        ("28.03.2026", "Planned generation support for reusable UI components, page templates, style variants and packaging logic for produced files."),
        ("31.03.2026", "Added static planning for build counts, artefact manifests and logged progress so generation runs could be tracked and reviewed."),

        ("02.04.2026", "Designed fallback behaviour so the developer agent could still produce usable outputs when the preferred model path is unavailable."),
        ("04.04.2026", "Extended the design to include prompt-driven generation for both components and pages using structured SRS context."),
        ("07.04.2026", "Refined the repair strategy to focus on controlled bug fixing and stable re-generation instead of broad rewrites."),
        ("09.04.2026", "Planned runtime sandbox support so generated React applications could be previewed, refined and repaired through an isolated execution layer."),
        ("11.04.2026", "Coordinated with the group on the shared handoff from requirements analysis and design selection into Builder Studio."),
        ("25.04.2026", "Implemented the Agent 2 backend in code, including build start/status/file endpoints, background run tracking, output packaging and the LangGraph-based generation flow."),
        ("25.04.2026", "Integrated component and page generation prompts, style variants, catalogue endpoints and manifest packaging for produced artefacts."),
        ("26.04.2026", "Implemented sandbox planning, generation, refine and repair support with a preloaded UI library and HTML preview wrapper for frontend runtime validation."),
        ("27.04.2026", "Supported the shared group demo by aligning Builder Studio outputs with the common dashboard, activity feed and inter-agent navigation."),
        ("28.04.2026", "Consolidated Agent 2 outcomes for the period and reviewed how the builder workflow fits into the first completion milestone of the project."),

        ("04.05.2026", "Set up the builder front-end base routes and the Studio dashboard shell."),
        ("04.05.2026", "Reorganised the front-end folder structure and removed the superseded starter application."),
        ("05.05.2026", "Implemented the dashboard cards, page flow and overall layout for the shared workspace."),
        ("05.05.2026", "Added the QA cycle timeline and testing progress states to the shared dashboard views."),
        ("09.05.2026", "Built the shared builder components and wired the builder routes into the common navigation."),
        ("10.05.2026", "Completed responsive checks and visual polish across the builder screens."),

        ("01.06.2026", "Added the AI developer workflow and the architect agent that turns approved requirements into an implementation plan."),
        ("01.06.2026", "Introduced generation state management and added the required-field rules to the architect prompt."),
        ("02.06.2026", "Added multi-stage architect and planner agents so high-level design is separated from file-level planning."),
        ("14.06.2026", "Replaced the first developer-agent prototype with the ai_designer scaffold as the version 2 baseline."),
        ("16.06.2026", "Established the architecture stability baseline: error-text decoding, route resolver, synchronous endpoints, element-scoped LLM patching with self-heal, a 102-entry template catalogue and version-on-success behaviour."),
        ("16.06.2026", "Reskinned the Studio interface on a Tailwind v4 foundation with neutral-dark theme tokens."),
        ("16.06.2026", "Centralised and unit-tested error handling so runtime failures never surface as unreadable objects."),
        ("16.06.2026", "Implemented a cache-busted image and build flow and consolidated the stability test suite."),
        ("17.06.2026", "Added the component registry, versioning and edit-plan support needed for controlled regeneration."),
        ("17.06.2026", "Hardened component selection with a testable route-fallback library and a CRUD create resolver."),
        ("18.06.2026", "Added backend regression tests and scaffold updates for the generation pipeline."),
        ("23.06.2026", "Merged the stability fix branch, removed dead code and added further project templates."),
        ("28.06.2026", "Divided the agent implementation into task-specific modules to improve maintainability."),

        ("07.07.2026", "Reorganised the application workspace and tightened the tracked-file rules for the desktop build."),
        ("09.07.2026", "Upgraded the planner so implementation plans cover file layout, dependencies and build order more completely."),
        ("17.07.2026", "Changed the model configuration used by the developer agent after comparing generation quality across candidates."),
        ("18.07.2026", "Implemented architect-driven planning with split model routing so each stage uses the most suitable model."),

        ("14.08.2026", "Integrated the agent modules into a single package and removed the obsolete test scaffolding."),
        ("16.08.2026", "Recorded a lessons store and added a browser reproducer for defects observed in generated applications."),
        ("16.08.2026", "Tuned the generation prompts, updated the Studio interface and added the console bug-fixer flow."),
        ("20.08.2026", "Added workspace tools and source-guidance support so the agent reuses existing project context when editing."),
        ("21.08.2026", "Added the theme, photo and image agent modules for asset-aware generation."),
        ("21.08.2026", "Split the agent exports into focused submodules to reduce coupling across the pipeline."),
        ("22.08.2026", "Added persistence and builder scaffolding for project state."),
        ("22.08.2026", "Split the tester modules and added a security shim for the QA-facing interface."),
        ("22.08.2026", "Merged the developer-agent parts and the full-application developer edition into the shared integration branch."),
        ("23.08.2026", "Performed history-only merges to restore the QA and SRS component branches into the integration line."),
        ("25.08.2026", "Reviewed the integrated Studio interface across the builder, SRS, QA and deployment panes in preparation for the version 2 consolidation."),
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
        "During this reporting period Agent 3 was developed as the quality assurance and "
        "validation component of the multi-agent system, together with the QA-facing user "
        "interface. The early part of the period structured the QA workflow: unit testing, "
        "integration testing, API contract validation, quality scoring, issue reporting and "
        "round-based feedback to Agent 2 for corrective action, with PDF report output. The "
        "middle of the period delivered the QA front end — the cycle timeline, bug "
        "reporting and contract review screens, evidence and artefact views, memory logs and "
        "project history — together with the Node.js analyser and dependency graph used "
        "when preparing generated projects for testing. The later part of the period covered "
        "the redesign of the QA backend into staged unit, runtime/API, end-to-end and "
        "security verification, with an installable test harness, mock handling and isolated "
        "per-run sessions. Group contributions were made throughout so that testing progress, "
        "bug visibility and the QA gate before deployment are demonstrable inside the shared "
        "workspace."
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
        ("23.03.2026", "Defined the scope of Agent 3 as the AI QA Tester responsible for validating generated systems and returning actionable defects to the builder agent."),
        ("24.03.2026", "Designed the QA workflow to cover unit testing, integration testing, API contract checks, scoring and bug reporting across the multi-agent pipeline."),
        ("26.03.2026", "Identified the core test stages and reporting outputs needed for a repeatable quality gate before deployment."),
        ("28.03.2026", "Planned issue classification with severity levels, module mapping, fix recommendations and round-based re-testing behaviour."),
        ("31.03.2026", "Defined the quality score structure and summary metrics required for measuring functional quality, security, performance and requirement coverage."),

        ("02.04.2026", "Designed the feedback loop from Agent 3 back to Agent 2 so failed runs could trigger guided repair instead of manual debugging only."),
        ("04.04.2026", "Planned report artefact generation for QA summaries and issue bundles that could be consumed by the rest of the team."),
        ("07.04.2026", "Refined the staged testing cycle so validation progress, fixes and final pass state could be presented clearly to users."),
        ("09.04.2026", "Coordinated with the group workflow so QA status could act as the deployment gate for Agent 4 and appear in the shared dashboard."),
        ("21.04.2026", "Implemented the unit-testing and integration-testing routines together with the PDF report writer used for QA output."),
        ("23.04.2026", "Implemented the Agent 3 backend in code, including test-run start/status endpoints, progressive logs, summary metrics, issue lists and JSON report output."),
        ("24.04.2026", "Built the shared QA Center interface with a visual test timeline, bug report pane, fix log animation, unit/integration/API tabs and QA inspector."),
        ("24.04.2026", "Added round-based bug tracking and simulated repair handoff behaviour so Agent 3 could demonstrate interaction with Agent 2 inside the group workspace."),
        ("27.04.2026", "Reviewed the shared dashboard and activity integration so QA outcomes, open bugs and handoff status are visible across the group demo."),
        ("28.04.2026", "Prepared the reporting-period summary and verified Agent 3 alignment with the first-phase project milestone."),

        ("04.05.2026", "Set up the QA front-end routes and the base screen structure for the testing workspace."),
        ("05.05.2026", "Built the bug-reporting and contract-review screens used to present QA findings."),
        ("05.05.2026", "Updated the bug-reporting and contract-review screens following the first internal review round."),
        ("05.05.2026", "Implemented the QA cycle timeline and the testing progress states."),
        ("06.05.2026", "Added the memory-log and project-history views so previous QA runs remain visible to the user."),
        ("07.05.2026", "Built the artefacts and evidence presentation screens for test output."),
        ("09.05.2026", "Added the shared QA components and wired the QA routes into the common navigation."),
        ("10.05.2026", "Completed responsive checks and polish across the QA screens."),
        ("10.05.2026", "Cleaned the front-end working branch and prepared it for packaging."),
        ("11.05.2026", "Added the Node.js analyser, generator and dependency graph support used when preparing generated projects for testing."),
        ("11.05.2026", "Finalised the Agent 3 front-end copy and pushed the reviewed build to the shared repository."),

        ("08.06.2026", "Reviewed the version 1 QA cycle results and identified where staged demonstration testing had to be replaced by real test execution."),
        ("15.06.2026", "Studied test-harness approaches for generated JavaScript and React projects and compared the available runner options."),
        ("22.06.2026", "Planned the redesigned QA stages covering unit, runtime/API, end-to-end and security verification."),
        ("29.06.2026", "Defined the evidence model so that every QA verdict is backed by a stored artefact rather than a log line."),

        ("06.07.2026", "Specified the unit-test authoring and repair loop so failing generated tests are corrected instead of discarded."),
        ("13.07.2026", "Designed the end-to-end stage: preflight checks, console capture, normalisation and grounding of observed behaviour."),
        ("20.07.2026", "Prepared the API-verification and security-check requirements for the QA backend rebuild."),
        ("27.07.2026", "Reviewed the integration points between the QA agent and the builder so failures return actionable repair context."),

        ("16.08.2026", "Added the QA agent component and the testing user interface into the shared Studio."),
        ("18.08.2026", "Aligned the QA run API with the shared runs service so test progress can be polled from the interface."),
        ("22.08.2026", "Reviewed the tester module split and the security shim added on the builder side for the QA interface."),
        ("24.08.2026", "Split the test-harness foundations into reusable modules."),
        ("25.08.2026", "Added harness installation support and mock handling so test runs execute in isolation."),
        ("25.08.2026", "Split the QA session foundations so each test run keeps its own isolated state and snapshot."),
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
        "During this reporting period Agent 4 was developed as the deployment and DevOps "
        "component of the multi-agent system, together with the DevOps-facing user "
        "interface. The early part of the period established deployment artefact generation, "
        "run tracking, readiness reporting and the structure required for Docker, GitHub "
        "Actions, AWS-style deployment evidence and release packaging, alongside two "
        "iterations of the deployment interface covering workflow diffing, timeline replay "
        "and artefact presentation. The middle of the period contributed shared studio "
        "screens — the design selector, the builder timeline and the generated-page "
        "preview. The later part of the period delivered the CI quality and security gates "
        "— SonarCloud analysis and Snyk dependency and infrastructure scanning — the "
        "functional integration dashboard and diagnostics, and the version 2 deployment "
        "package with hardened credential handling, environment and database validation, "
        "deployment event tracking and provider-backed release support."
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
        ("23.03.2026", "Defined the scope of Agent 4 as the AI Deployment / DevOps Engineer responsible for packaging, deployment readiness and release support after QA approval."),
        ("24.03.2026", "Reviewed the expected deployment outputs for the project, including Docker assets, compose files, workflow pipelines, cloud configuration and release evidence."),
        ("26.03.2026", "Designed the Agent 4 workflow for moving from approved source code to deployment artefacts and readiness reporting."),
        ("28.03.2026", "Planned support for Docker, GitHub Actions, AWS ECS/ECR configuration, environment templates and API validation evidence."),
        ("31.03.2026", "Identified the pipeline checkpoints needed for source validation, service discovery, security review, packaging, deployment and documentation."),

        ("02.04.2026", "Defined the artefact set required from Agent 4, including compose files, workflow files, task definitions, summaries and evidence bundles."),
        ("04.04.2026", "Refined readiness scoring and deployment-gate logic so unresolved QA issues could block release preparation in a controlled way."),
        ("07.04.2026", "Coordinated the deployment handoff with the group workflow so Agent 4 depends on Agent 3 pass status and produces visible artefacts for the shared demo."),
        ("09.04.2026", "Planned the reporting structure for operational evidence such as ECS services, ECR images, logs, API validation and checklist-driven documentation."),
        ("18.04.2026", "Implemented the animated conversation area for the deployment assistant interface."),
        ("18.04.2026", "Resolved the reported repository security findings and cleared the remaining scan issues."),
        ("19.04.2026", "Added workflow change viewing and filtering so modified pipeline files can be inspected before a release."),
        ("19.04.2026", "Added timeline replay for deployment runs and implemented the smart diff preview section."),
        ("19.04.2026", "Improved the deployment artefact area and the way generated files are presented."),
        ("20.04.2026", "Removed superseded interface sections and upgraded the deployment interface presentation."),
        ("21.04.2026", "Completed version 2 of the deployment interface after removing the remaining unnecessary sections."),
        ("23.04.2026", "Implemented the Agent 4 backend in code, including deploy start/status endpoints, run tracking and artefact generation for docker-compose, GitHub workflow and deployment summary files."),
        ("24.04.2026", "Established the shared DevOps Center page structure and updated the conversation section to handle missing intake questions."),
        ("27.04.2026", "Completed version 2.1 of the deployment workspace, expanding services, workflows, ECS, ECR, CloudWatch, readiness scores and evidence checklist items."),
        ("28.04.2026", "Consolidated the deployment-phase outcomes and prepared the supervisor-ready summary for the reporting period."),

        ("05.05.2026", "Built the design-selector screens and the preset browsing flow in the shared workspace."),
        ("06.05.2026", "Implemented the builder timeline and progress states shown while generation is running."),
        ("08.05.2026", "Added the generated-page preview and the coder pane used to inspect produced files."),

        ("10.06.2026", "Reviewed the deployment path end to end and listed the checks required before a release can be started."),
        ("17.06.2026", "Compared container, CI and cloud provider options and selected the target deployment routes for version 2."),
        ("24.06.2026", "Planned the CI quality and security gates to be added to the repository workflows."),

        ("23.07.2026", "Added the SonarCloud quality-analysis workflow and configured project analysis for the repository."),
        ("23.07.2026", "Added the Snyk dependency and infrastructure-as-code security workflow."),
        ("23.07.2026", "Built the functional integration access dashboard and the integration status service."),
        ("23.07.2026", "Enabled the functional integration controls in the DevOps Center and exposed connection diagnostics."),
        ("23.07.2026", "Added the GitHub CLI integration card and documented the SonarCloud and Snyk connection steps."),
        ("23.07.2026", "Documented the integration environment configuration and cleaned generated files out of version control."),
        ("24.07.2026", "Fixed the CI tests for the SonarCloud and Snyk workflows and corrected the Docker validator test environment."),
        ("24.07.2026", "Fixed the front-end build and upgraded Next.js and Sharp to clear the reported security advisories."),
        ("24.07.2026", "Adjusted the pipeline to skip the unavailable Snyk Code and IaC scans so results are reported accurately."),

        ("21.08.2026", "Refreshed the deployment package foundation and reorganised it into the modular deploy_agent structure."),
        ("22.08.2026", "Hardened credential and secret handling for deployment operations."),
        ("22.08.2026", "Cleaned the repository and updated the component documentation."),
        ("23.08.2026", "Added deployment event and state tracking for running releases."),
        ("23.08.2026", "Added environment validation and MongoDB connectivity checks carried out before a deployment starts."),
        ("24.08.2026", "Refreshed the deployment package and the flow contracts shared with the QA stage."),
        ("24.08.2026", "Strengthened validation and the deployment tool interfaces."),
        ("25.08.2026", "Added Vercel authentication and API support for provider-backed deployment."),
    ],
}

STUDENTS = [NIMTHARA, RAVINDU, HAMNA, MALITH]
