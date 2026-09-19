---
name: scoped-change-tests
description: "How much to test when changing an app that already works: prove the change and everything that reads it, not the whole product again. Covers deciding the blast radius honestly, which unit files to write and run, which browser journeys to re-run and which to reuse, and the rule that no existing test may be weakened to make a change land."
---

# Testing a change, not the whole product

This is a change to an application that already exists and already passes. The
suite that proves the rest of it passed before you started and will pass after,
unless you broke something — so running all of it proves almost nothing about
what you did, and costs the time that should have gone into proving the part
that is actually new.

Prove the change. Prove what reads the change. Leave the rest alone.

## Decide the blast radius before writing a test

Ask what *else* would be wrong if your edit were wrong. That set is the radius,
and it is the only thing that decides how much to test.

- **A page, a component, a route handler, one endpoint** — the radius is that
  file and whatever imports it. Usually two or three modules.
- **A shared thing** — a utility, a layout, a schema, a database model, an auth
  helper, a design token. The radius is every caller. `search` for the symbol
  before deciding; the number of hits is the answer, not a guess.
- **A data shape** — a field added, renamed or removed. The radius is everything
  that reads or writes that field, on both sides of the wire.

Say which one it is in your summary, and say how you established it. "I changed
the invoice table's columns, and `search` found four files reading
`invoice.total`" is a radius. "I tested the affected parts" is not.

Widening the radius when the change is shared is not over-testing. Narrowing it
when the change is local is not under-testing. Getting it wrong in either
direction is.

## Unit tests

Write or extend tests for the code you actually wrote, and for the callers your
radius named. Nothing else.

- A new module gets its own test file. Every exported function, every branch
  that can fail, and the failure itself — not only the happy path.
- An edited module keeps its existing test file and gains cases for what
  changed. Do not rewrite the file; add to it.
- A caller you changed because of the edit gets a case proving it still works
  with the new shape.

Run only what you touched:

```
executeTerminal("npx vitest run <the files in your radius>")
```

A full `vitest run` is the right command in exactly two situations: your radius
is genuinely the whole app, or the targeted run passed and you want one final
confirmation before reporting. It is never the first thing to run, and its
output is never a substitute for having tested the change itself.

## Browser journeys

The engine reuses a passing journey whose steps and revision have not changed,
so you do not have to re-run everything by hand — but you do have to decide
which ones the change can reach.

- **Re-run every journey that visits a route you changed.** If you edited the
  bookings list, every journey that opens it runs again, not just one.
- **Add a journey only when the change added a path a user can take.** A new
  page, a new action, a new outcome. A changed label on an existing page needs
  an assertion in the existing journey, not a journey of its own.
- **Leave untouched journeys alone.** Re-running a journey over a page you did
  not change tells you what it told you last time.
- The new or changed assertion must be about *the change*. Adding a column and
  asserting the page still loads proves nothing — assert the column's header
  and one row's value.

## Two rules that are not negotiable

**Never weaken a test to make a change pass.** If an existing test now fails,
one of two things is true: the change broke something, or the test encoded
behaviour the change deliberately replaced. Say which. If it is the first, fix
the code. If it is the second, update the test *and say in your summary that you
changed it and why*. Deleting an assertion, loosening a matcher, or marking a
test skipped so a change can land is a silent regression and will be read as
one.

**Never report a scope you did not run.** If you ran four unit files and two
journeys, say that. Do not say "all tests pass" when what you mean is "the
tests I ran pass" — those are different claims, and only one of them is yours
to make.

## What to say when you are done

- What changed, in one line.
- The radius, and how you established it.
- Which unit files you wrote or extended, and which you ran.
- Which journeys you re-ran or added, and what they now assert about the change.
- Anything in the radius you chose *not* to test, and why.
