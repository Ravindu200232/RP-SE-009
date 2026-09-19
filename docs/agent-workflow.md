# SRS and agent workflow

The interview includes email, payment and image-upload provider choices. Credential values are posted directly to the interview integration endpoint and saved in the specification's `.env.local`. Only provider choices and credential names enter prompts. Adoption copies the environment into the application and ignores it in Git.

The approved product plan feeds SRS generation. That same generation job writes `app.md`, `sitemap.md`, `prototype.md` and `builder.md` before SRS approval becomes available. There is no second product-planning pass after SRS approval. Design customization precedes the HTML/CSS/JavaScript prototype; the Developer + QA agent implements the selected stack from the approved SRS and prototype.

## Context and UI ownership

Each application stores independent Designer and Developer conversations, usage and events under `.agentforge/agents/<role>/`. The Designer has file tools for its prototype and read access to the shared handoffs. The Developer has application file tools and read access to the prototype and handoffs. Handoffs are written by the SRS service. Credential files and the other agent's context are excluded from file-tool access.

The prototype and design tabs show Designer history. The build preview and testing tabs show Developer history. There is no combined chat. Drafts, selections, screenshots, console evidence, progress and QA results are scoped to their project and agent. Late preview responses update the owning context. A project remembers its last selected tab. Browser history caches are bounded; completed tool checkpoints and context compaction are retained on disk.

The first build requires a completed prototype. Completing a prototype or synchronizing documents does not navigate. **Build App Now** explicitly starts/resumes the developer and switches to the build preview. Runtime ports and service ports continue to come from the per-project runtime registry described in [generated-previews.md](generated-previews.md).

## Durable synchronization

Agent requests are journaled before execution. SRS generation/customization checkpoints completed stages; model conversations checkpoint completed tool observations. Backend restart replays pending requests with the saved context. A single server queue serializes generation and document updates while other projects remain browsable. Cancellation is scoped to the selected project and agent.

After a child agent completes, the server sends its short result to the parent SRS for comparison. The SRS service updates affected requirements, its current plan projection, diagrams, PDF and all four handoffs. If the other artifact exists, its agent applies the change in its own context and verifies it. That completed result goes back to the SRS once. A sibling run cannot enqueue another synchronization cycle. A first prototype never starts a first build through synchronization.

The transaction records `source_completed`, `srs_updated`, `sibling_completed` and `complete`. Stable change IDs and receipts prevent duplicate document versions after interrupted exports. A failed synchronization retains its checkpoint and exposes Retry; it does not restart a completed source generation or repeatedly retry without a user action.

## Validation and limits

Run `python test/run_suite.py`, `npm run build` from `studio`, and `python test/browser_workflow.py` against a running Studio on port 3157 (or set `STUDIO_TEST_URL`). The browser test mocks model/backend transport and exercises both role histories, drafts, console evidence, project switching, reload, synchronization events and the explicit Build Now transition. Backend tests cover context recovery, handoff timing, parent document retries, credential handling, runtime ports and project boundaries.

Recovery starts at the last durable checkpoint; a model response interrupted before that checkpoint may be requested again. Third-party side effects still need provider-level idempotency. Developer shell processes and generated applications run with the host user's privileges: file-tool scope is not an OS/container sandbox. Static prototypes namespace localStorage and sessionStorage on the Studio origin; this is separate application state, not isolation of hostile JavaScript. Live model generation, provider integrations and deployment need testing with configured services.
