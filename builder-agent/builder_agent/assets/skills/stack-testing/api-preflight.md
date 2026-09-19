---
name: "API Contract Tests Before Browser Journeys"
description: "Cover every API route with fast in-process contract tests - status codes and the role matrix - as part of the unit run, before any browser journey. Apply after routes exist and before browserRunJourney, and whenever a journey fails for a reason a browser cannot show you."
allowed-tools: Read, Write, Edit, Bash
version: 2.0.0
compatibility: Claude Opus 4.6, Sonnet 4.6, Claude Code v2.1.x
updated: 2026-09-16
---

# API contract tests, before browser journeys

A browser journey is the slowest way to learn that a route forgot its role
check, the seed is empty, or sign-in is broken. Prove the HTTP contract in the
unit run. The browser is then left doing the only job it is uniquely good at:
rendering, navigation and form interaction.

## Why this comes first

Measured on a real multi-role app build: the browser E2E phase
took **29.6 minutes**, of which the journeys themselves ran for **73 seconds**.
The rest went on re-establishing basics by hand — `npm run seed` ten times,
twenty-one sign-in probes, sixteen runtime checks — and on driving the browser
click by click to find out *why* a journey failed. Of the five real fixes it
produced, three were a backend route and its seed data. An in-process HTTP test
finds those in milliseconds.

So: **when a journey fails, first ask whether a browser was needed to find it.**
If the answer is no, you are debugging in the wrong tool.

## A passing unit run is not a tested API

Unit totals like "37 passing, 0 failing, 3 files" say nothing about routes. The
route inventory links a route to a test **only when a test file imports that
route module**. A single big suite that imports `createApp()` and drives
everything through it exercises the routes but links to none of them, so every
route reads as `no linked test record` and nobody can tell which endpoints are
actually covered.

**Write one test file per route module, and import that module in it.**

```
packages/core/src/routes/orders.routes.js
packages/core/test/orders.routes.test.js   <- imports ../src/routes/orders.routes.js
```

That gives real per-route coverage and makes the inventory tell the truth. The
same rule applies to every `*.routes.js` you create: a route without its own
test file is an untested route, whatever the totals say.

## Fast means in-process — but the database is real

These are the calls you would make in Postman, with no UI and no server to
start: a real HTTP request, through the real middleware, to the real database.

**Do not mock the data layer.** Mocking the model is what makes a route test
pass while the route is broken: the filter that forgets the tenant, the unique
index that is missing, the populate that returns nothing, the cascade that
leaves orphans — none of them exist against a mock. Connect to the test
database, clear it between tests, insert the rows the case needs, and assert on
what comes back.

What you skip is the browser and the server process, not the stack underneath.
Mount the router on a bare Express app inside the test and call it with
supertest: each request is a function call, so a whole route module is tens of
milliseconds while still touching the database.

```js
// packages/core/test/orders.routes.test.js
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest'
import express from 'express'
import request from 'supertest'
import orders from '../src/routes/orders.routes.js'   // <- the link
import { connectTestDb, clearCollections, closeTestDb } from 'testing'
import { signFor } from './helpers/auth.js'

const app = express().use(express.json()).use('/api/orders', orders)

beforeAll(connectTestDb)
beforeEach(clearCollections)
afterAll(closeTestDb)

describe('GET /api/orders', () => {
  it('refuses an unauthenticated request', async () => {
    const answer = await request(app).get('/api/orders')
    expect([401, 403]).toContain(answer.status)
  })

  it('refuses a role the route does not allow', async () => {
    const answer = await request(app).get('/api/orders')
      .set('Authorization', `Bearer ${signFor('member')}`)
    expect(answer.status).toBe(403)
  })

  it('serves an allowed role', async () => {
    const answer = await request(app).get('/api/orders')
      .set('Authorization', `Bearer ${signFor('staff')}`)
    expect(answer.status).toBe(200)
  })
})
```

## What every route must assert

For each route in the handoff's API table:

| Request | Expected |
|---|---|
| No credentials | 401 or 403 — never 200, and never the data |
| Signed in as a role **not** in `allowed_roles` | 403 |
| Signed in as an allowed role | 2xx |
| Another tenant's / another user's record by id | 403 or 404 — never the record |

The first and fourth rows are the ones a browser structurally cannot check,
because a browser only issues the requests the UI issues. A route that returns
data to either one is a data leak that passes every journey ever written.

## Before the first journey

Once the route tests are green, confirm the stack the journeys will actually
run against: the server answers, the seed ran and the rows exist, and every demo
role can sign in and gets a token. A broken sign-in makes every journey fail at
once, which reads as a far larger problem than it is.

## Write checks in Node, not shell pipelines

`executeTerminal` runs the platform shell — `cmd.exe` on Windows — where POSIX
syntax fails instantly and the failure looks like a wrong command rather than a
wrong shell:

- `VAR=$(...)` — command substitution does not exist
- `... | tail -20`, `| head`, `| grep` — those programs do not exist
- `curl -w "%{http_code}"` — `cmd` eats `%{...}` before curl sees it

If you need a one-off probe, put it in a `.mjs` file and run
`node scripts/probe.mjs`. Node gives you `fetch`, JSON and a real exit code on
every platform with no quoting problems. Better still, make it a test instead,
so the next run keeps the check.

## After it is green

Only then run `browserRunJourney`. Spend journeys on what a browser is for —
does the page render, does the link go somewhere, does the form submit, does the
right thing appear afterwards. Do not re-check authorization the contract tests
already proved; you will pay twenty seconds a step to learn something HTTP told
you in milliseconds.

If a journey still fails, re-run the route tests before touching the UI. A
backend change made while fixing something else is a more common cause than the
page, and the tests tell you which half to look in.
