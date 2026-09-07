---
name: nextjs
description: Plan, build, debug, and verify a Next.js application using the installed version and the project's selected App Router or Pages Router conventions.
---

# Next.js application work

Use this skill only when Next.js is selected or detected. Treat the lockfile and installed package versions as authoritative. When version behavior is uncertain, read the matching current official documentation instead of relying on model memory.

## Inspect before planning

Read `package.json`, the lockfile, Next configuration, TypeScript/JavaScript config, environment examples, source layout, route tree, middleware/proxy files, and nearby tests. Determine whether the project uses App Router, Pages Router, `src/`, server actions, route handlers, a custom server, or a deployment adapter. Do not mix router conventions or introduce an alternative architecture without a concrete requirement.

For greenfield generation, inspect the intended root before running `create-next-app`. AgentX metadata such as `.agent/` or `.agents/` can make the root non-empty even though no app exists. If the installed generator refuses that root, inspect its current help and scaffold into a clean child staging directory, using its supported no-install option when available. Promote an explicit inventory of application source, public assets, configuration, and manifests; never use an unfiltered recursive staging-tree transfer. Leave the staging `.git`, `node_modules`, `.next`, caches, coverage, screenshots, and test artifacts behind. Install once in the intended root and remove staging only after verifying the inventory. If dependencies were already installed in staging, do not copy them—install from the transferred manifest and lockfile in the intended root.

## Implement coherently

- Preserve Server and Client Component boundaries. Add `use client` only where browser state, effects, or event handlers require it; never expose server secrets in client bundles.
- Keep filesystem routes, links, redirects, dynamic parameters, API contracts, loading/error/not-found states, metadata, and authorization redirects mutually consistent.
- Choose caching, revalidation, static/dynamic rendering, and mutation behavior from the product contract and installed Next.js semantics. Do not copy obsolete cache advice.
- Validate untrusted input at server boundaries and return intentional status/error shapes. Keep database and secret-bearing modules server-only.
- Use the selected styling, data, auth, testing, and package-manager choices verbatim when compatible. Do not silently substitute a preferred library.

## Mistakes that fail the first run

Observed in real builds. Each cost a full repair cycle and none of them are
subtle once named.

- **`forbidden()` and `unauthorized()` need `authInterrupts` enabled.** Without
  the flag in `next.config`, calling them throws at render and surfaces as a
  minified React error and an HTTP 500 — which reads like a broken auth guard
  when the guard is fine. Enable the flag, or return an explicit response
  instead. Check the installed version's own docs before choosing.
- **Navigate with `<Link>`, not `<a>`.** An internal `<a href="/x">` is a lint
  error in this project and a full page reload for the user. Reserve `<a>` for
  external URLs.
- **A `use client` component cannot be `async` and cannot read server-only
  modules.** Fetch on the server and pass the data down, or move the boundary.
- **`params` and `searchParams` follow the installed version's contract.**
  Recent versions hand them over as promises; awaiting one that is not a promise
  (or failing to await one that is) breaks the route. Read the version you have
  rather than recalling an older shape.
- **Server-only stays server-only.** A database or secret-bearing module
  imported anywhere reachable from a client component ends up in the browser
  bundle. Keep the import boundary explicit.
- **A route handler must return a `Response`.** Returning a bare object yields
  an empty body and a confusing client-side parse failure.

## Verify

Run the project's finite lint/typecheck/unit commands, then a production build. Start the built app on a task-owned available port and probe important routes and assets. Use E2E for async Server Components and critical browser journeys when unit tooling cannot exercise them accurately. Inspect browser console, failed requests, hydration, redirects, and responsive UI before completion.

Current official references:

- https://nextjs.org/docs/app/getting-started
- https://nextjs.org/docs/app/guides
- https://nextjs.org/docs/app/guides/testing
