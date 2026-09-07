---
name: security-review
description: Review a generated application for the vulnerabilities that actually appear in it — broken access control, injection through user-supplied query shapes, unsafe session handling, secret and data leakage — and verify each finding against the running app rather than by reading alone.
---

# Security review

This is a review discipline, not a library. It never adds a scanner, a monitoring
stack or a security framework to the project. It reads the code that already
exists and proves each finding against the running application.

Run it as part of the final audit, and again whenever auth, roles, or a data
boundary change.

## Broken access control — check this first

It is the most common real defect in a generated app and the one that matters
most, because every other control assumes it works.

- **Authorization is enforced where the data lives, not only in the UI.** A
  hidden admin link is not a control. Call the protected route directly, signed
  out and signed in as the wrong role, and assert the status.
- **Signed out must redirect; wrong role must be refused.** Those are different
  outcomes and both need a test. A wrong-role request that returns 500 instead
  of 403 is a bug, not a refusal — it means the guard threw instead of deciding.
- **Every object lookup is scoped to its owner.** `GET /orders/:id` must not
  return another user's order because the id was guessable. Check every route
  that takes an id from the URL or body.
- **Server-side mutations re-check the role.** A client that hides the delete
  button proves nothing about the route behind it.

## Injection through the shapes users control

- **Never build a query filter out of raw request data.** A body or query
  parameter that reaches a Mongo filter can carry an operator object and turn
  `{ email }` into `{ email: { $ne: null } }`. Pick fields explicitly and cast
  them to the type you expect.
- **Cast ids before querying** and treat a malformed id as a 400, not a crash.
- **Validate at the first trusted server boundary**, before any domain or
  database call, and reject unknown fields rather than passing them through to a
  model.
- **Any path derived from user input stays inside its intended directory.**

## Sessions and credentials

- Passwords are hashed with a slow, salted algorithm the project already
  depends on. Never a plain hash, never a homemade one.
- Session cookies are `httpOnly`, `sameSite`, and `secure` in production. A
  token readable from JavaScript is a token an injected script can take.
- Sign-out invalidates the session on the server, not just in the browser.
- Login failures are indistinguishable between "no such user" and "wrong
  password", and are rate limited.

## What leaks

- **Responses return intentional fields.** Serialising a database document
  directly is how password hashes, internal flags and other users' data escape.
  Check what the route actually returns, not what you meant it to return.
- **Errors say what the caller needs and nothing more.** Stack traces, driver
  messages and query fragments stay in the log.
- **Secrets come from the environment** and are never committed, logged, or sent
  to the browser bundle.

## Verify, do not assert

A finding is not confirmed by reading code. For each one, exercise the real
boundary through the running app — the wrong-role request, the guessed id, the
operator-shaped filter — and record the status and body you actually got. Fix
the smallest owning layer, then re-exercise the same request.

Report honestly: what you checked, what you found, what you fixed, and what you
could not verify in this environment.
