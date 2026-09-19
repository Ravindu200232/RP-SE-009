---
name: stack-remix
description: "The skills for Remix v2 + MongoDB. Read this index first, then read only the entries the task actually needs with readSkill resourcePath."
---

# Remix + MongoDB

Everything here is read with `readSkill` and a `resourcePath`, for example
`readSkill(name="stack-remix", resourcePath="remix-routing.md")`.

Read the entry that matches what you are about to write, not all of them.

- **`remix-routing.md`** — The route file convention, nested routes, `Outlet`, dynamic and splat segments, and which file serves which URL.
- **`remix-data.md`** — `loader` and `action`, `useLoaderData`, `Form` and `useFetcher`, redirects, and where the database belongs.
- **`remix-errors.md`** — `ErrorBoundary`, `useRouteError`, thrown responses, and the difference between an expected 404 and a crash.

## What is true of every file in this project

**This is Remix v2 on Vite.** There is no `remix.config.js`; the framework's
options are the `remix()` plugin's in `vite.config.js`. A file of that name is
ignored, and writing one is the most common way to spend an hour on a setting
that never took effect.

**Your training data has three different Remixes in it.** Remix v1 (its own
compiler, `remix.config.js`), Remix v2 (the Vite plugin, `@remix-run/*`, which
is this), and the successor released as React Router 7 and later, where the
same APIs live under `react-router` and `@react-router/*`. Check
`package.json` before you import: in this project every framework import is
`@remix-run/node` or `@remix-run/react`, and an import from `react-router`
that is not `react-router`'s own is the wrong generation.

**The server/client split is the architecture, not a detail.** A `loader` and
an `action` run only on the server, and Remix removes them from the browser
bundle along with everything only they import. That is what lets
`lib/db.js` be imported from a route at all. Import it into a component and
Mongoose is bundled for the browser, which fails at build time with a message
about Node built-ins and reads as a bundler problem.

**Data is not fetched in a `useEffect`.** A route gets its data from its own
`loader` before it renders. Fetching the app's own data from the client gives
up server rendering, the framework's revalidation, and the loading states the
router already handles.

**Progressive enhancement is the default and is worth keeping.** A `<Form>`
works with JavaScript disabled because the `action` is a real form post. Do
not replace it with an `onSubmit` that calls `fetch` unless something actually
requires it.

## Running it

- `npm run dev` — the Vite dev server.
- `npm run build` — `remix vite:build`. It writes `build/client` and
  `build/server`, and it type-checks nothing, so a route that throws at render
  still builds. Open the page.
- `npm start` — `remix-serve` against the build. This is the production shape.
- `npm test` — Vitest.

`vitest.config.js` deliberately does **not** load the Remix plugin. It rewrites
route modules for the framework's loader/action split and expects a Remix
request in flight; under the runner there is none, so including it turns every
component test into an error about a missing route context.
