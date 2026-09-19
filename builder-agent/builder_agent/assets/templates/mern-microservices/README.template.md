# Scaffolded from the verified MERN + microservices template

Everything here was installed, unit-tested, built and served on one port
before it was made a template. Build the application on top of it.

    npm install
    npm run dev      # every service + the gateway, one public port
    npm test         # every workspace that has tests
    npm run build    # the client bundle the gateway serves

## Adding a service

Copy `scaffold/service` to `packages/<name>` and follow the README inside it:
rename the two `.tpl` files, rename `Item`/`items` to the resource the service
owns, and route it at the gateway.

`scripts/dev-all.mjs` finds it on its own — it looks for
`packages/*/src/server.js` and needs no edit.

## What is yours to write

Models, routes, pages, components, each service's own `src/server.js`, and the
real stylesheet. The placeholder page/component and the starter stylesheet are
here only so the scaffold builds and renders before any feature exists.

## Test layout

Each workspace owns its runner config, and `vitest.workspace.js` at the root
ties them together, so `npm test` and a bare `vitest run` both do the right
thing. Shared helpers live in `packages/testing`:

    import { connectTestDb, clearCollections, closeTestDb, request } from 'testing';
