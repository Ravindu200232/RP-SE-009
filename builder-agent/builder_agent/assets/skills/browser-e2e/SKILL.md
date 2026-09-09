---
name: browser-e2e
description: Verify real Next.js user journeys with AgentX's isolated direct-CDP browser and no project-level E2E framework.
---

# AgentX Browser E2E

Use AgentX `browserRunJourney` as the only E2E harness. It drives an isolated installed Chrome/Edge/Chromium browser through Chrome DevTools Protocol and records executed assertions in the durable E2E ledger. Do not add E2E framework packages, config files, generated spec files, browser downloads, or framework-owned web-server orchestration to the generated project.

## Discover the real journey

- Start from the real public route and real task-owned/seeded data.
- Prefer a stable `startUrl` for each suite. If omitted, AgentX reuses the active tab automatically.
- Each suite starts with a fresh browser auth/storage session by default; do not manually log out/login between suites just to reset state. Set `freshSession:false` only when the requirement explicitly needs one continuous browser session across that suite boundary.
- Use browserSnapshot once to observe actual role/name controls when the flow is uncertain.
- Accessible-name resolution is tolerant but deterministic: exact -> normalized exact -> one unique containing name. Prefer a short unique accessible name such as the visible entity title; do not copy a whole card's concatenated accessibility text.
- If more than one control matches, use a more specific accessible name or one stable CSS selector derived from the current UI.
- An `index` selects within the locator's matched candidates, starting at zero; it is not the control's position among every button or tab on the page. If a short label matches both itself and a longer label, use the exact observed accessible name or a stable selector instead of guessing an index. Counts in accessible names can change after a journey action.
- Do not query the database merely to discover a UI link/ID after a selector miss when the public UI itself should expose the target.

## Assertions and state

- Assert the outcome after each material action: URL, visible text/control, value, business-state result and `noDiagnostics` where appropriate.
- Keep journey diagnostics across steps so a snapshot cannot erase an earlier page, console, request, or HTTP failure.
- Cover each sealed E2E requirement only when the journey truly crosses its public browser boundary.
- Use isolated test/demo data; browser session isolation does not reset persistent database state.
- Prepare fixtures once before verification, and have each journey create and clean up its own records. Do not repeatedly clear or reseed the whole database between passing checks. Keep stable suite IDs and requirement coverage so the final summary can reuse the evidence. After a passing journey, move to the next missing requirement or completion; rerun only after a relevant repair or when the ledger identifies stale evidence.
- Prefer one short journey per critical public flow rather than one giant scenario that makes failures ambiguous.

## Passing on the first run

Nearly every journey that fails on its first attempt fails for the same reason:
it asserted what the author imagined the page renders instead of what it
actually renders. That costs a full repair cycle each time and, worse, it sends
the repair loop hunting a product defect that does not exist.

### HTTP 200 is not a rendered page

Measured on a real build. The gateway returned **200** for `/`, `/ready`
returned **200**, every API returned **200**, and the gateway's own 27 unit
tests passed — and the page was **blank**. The bundle loaded and then threw
`Cannot read properties of undefined (reading 'toFixed')`, which emptied the
React tree.

A status-only probe calls that healthy. So:

- **The first step after `open` asserts real content** — a heading, a product
  name, a row count — never just the URL. A journey that opens a page and goes
  straight to clicking will report a locator failure when the truth is that
  nothing rendered at all.
- **Put `noDiagnostics` in every journey.** It is the only assertion that
  catches an uncaught exception, a failed request or a console error that leaves
  a page technically served and actually empty.
- **When a locator "is not found", read the returned page text first.** If the
  page text is empty or shell-only, the locator is fine and the app crashed.
  Fixing the selector is then the wrong repair, twice over.

### Where separately built packages first meet

The same build: `catalog-service` passed 116 of its own tests, the client passed
its own, and together they produced the blank page above — because the product
response omitted the `price` field the client rendered with `.toFixed()`. Each
side tested against its own idea of the shape; neither test could see the other.

The browser journey is the first place those two ideas are compared for real, so
it is the only place that mismatch can be caught:

- Assert a **value that crossed the boundary**, not merely that a list has rows.
  A price, a name, a total — something the other package actually produced.
- Cover one journey per cross-service flow, and assert the field the consumer
  depends on. "Twelve cards rendered" passes happily while every price is blank.
- A field that is present in the model and absent from the response is a
  serializer or projection defect. Fix the producer, not the consumer, and never
  by making the consumer tolerate `undefined`.

**Take one `browserSnapshot` of the page in the state you are about to assert,
and copy the real roles, names and text out of it.** Then write the journey.
These are the mistakes that snapshot prevents:

- **A number input is a `spinbutton`, not a `textbox`.** `type="number"`,
  `range`, `checkbox`, `radio`, `date` and `file` all have their own roles.
  Copy the role from the snapshot rather than assuming every field is a textbox.
- **Assert the DOM text, not the rendered appearance.** `text-transform:
  uppercase` makes a badge *look* like `PLACED` while the text node is still
  `placed`. Casing you see on screen is not necessarily casing you can match.
- **Assert a substring the page really contains.** A cart that computes a line
  total renders `$94.95`; it does not render `5 × $18.99` just because that is
  how you would describe it. Prices, dates, plurals and separators are all
  formatted by the code, so take the exact string from the snapshot.
- **Never review a screenshot you did not capture.** `browserReviewScreenshot`
  reads a file that a `screenshot` step must have written first, at that exact
  path, in this run.
- **The visible label is not always the accessible name.** A field showing
  `Search` above it can expose `Search products`, because a placeholder or
  `aria-label` wins over the nearby text. Read the name from the snapshot, not
  from the screenshot.
- **Narrow the page before locating a repeated control.** A catalogue renders
  one `Add to cart` per product — twelve identical names. Apply the search or
  filter first so exactly one remains, then locate by name; that also asserts
  the filter works. Reaching for a longer name string instead just moves the
  ambiguity.
- **Locate by one stable thing.** When two controls share an accessible name —
  a results-count link and an empty-state link both saying "Clear filters" —
  use a CSS selector instead of a more elaborate name guess.

When a journey does fail, read the returned page text before changing anything.
If the required content is in that text under a different form, the journey is
wrong and the product is fine: fix the assertion and rerun that suite once.
Editing production code to satisfy a mistaken locator is the most expensive
possible wrong turn.

## Capture visual evidence inside the journey

- A journey step may be `{"type":"screenshot","filePath":"...","view":"...","covers":["VIS-..."],"width":...,"height":...}`. Use it. Place it immediately after the assertion that proves the screen is in the state you want photographed.
- The journey has already navigated, signed in, seeded the state and asserted it. A separate capture pass afterwards repeats every one of those steps to reach the same screens, which is the single most expensive thing the visual phase can do — and it photographs a state you have not re-asserted.
- Cover both widths in the same journey where a view carries a responsive visual requirement: one screenshot step at desktop width, one at narrow width, each with its own `filePath` and `view`.
- A capture still records no evidence on its own. Review each one with `browserReviewScreenshot` before capturing further views; at most two unreviewed captures may exist at a time and a third is refused.
- This does not change what a journey asserts. Screenshots are additional evidence for the sealed visual requirements, never a substitute for the functional assertions around them.

## Failure and anti-loop rule

On failure, use the bounded failure URL/diagnostics/page text already returned by `browserRunJourney`. Do not take another snapshot unless that evidence says the page changed after the failure. Route the repair by owner: `E2E_SELECTOR_*` = journey/harness locator only; `E2E_UI_TARGET_MISSING` = product UI/route/state; assertion/console/network/HTTP 5xx failures = production behavior/runtime. State one falsifiable hypothesis and patch only that owner.

Do not manually churn browser state, guess multiple selector names, repeatedly logout/login, or rerun the same full journey after every observation. Correct a locator in the journey definition and retry with the same suite ID; this is a repair even though no product file changed. Do not rename the suite or edit working application code to escape a failed result. A passing retry replaces that suite's failed evidence.

After the repair, rerun only the affected journey once. If it passes, do not rerun unrelated E2E journeys until the final regression checkpoint. Never weaken assertions or fabricate success. Journey actions are intentionally lightweight; avoid manual `browserSnapshot` polling after every click, because the harness settles actions internally and captures bounded evidence only on failure. That is about accessibility-tree reads for debugging — it is not a reason to leave out `screenshot` steps, which are the visual evidence the sealed scope requires and belong inside the journey.
