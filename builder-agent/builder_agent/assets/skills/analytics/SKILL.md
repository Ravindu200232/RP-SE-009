---
name: analytics
description: Counting what people do in the product — which credentials to ask for, why a page view is not consent, and how to record an event that still means something in six months.
---

# Analytics

Use this skill when the product needs to know what people actually do in it:
which pages are read, where a sign-up is abandoned, whether a feature is used.

## What was already settled

The account cannot be read out of a repository, so it was asked for before the
build started, or ticked as a plugin. Build the one that was chosen and read
its file and no other.

- **Google Analytics** — `readSkill("analytics", "google-analytics.md")`
- **PostHog** — `readSkill("analytics", "posthog.md")`
- **Plausible** — `readSkill("analytics", "plausible.md")`

Whichever provider's names are present in the environment is the one that was
chosen. If none are, build the product without analytics rather than inventing
a provider, and say so.

## What has to be true

**Asking is part of the feature, not a later ticket.** Where consent is
required, nothing loads until it is given: no script, no cookie, no beacon. A
banner that appears after the tracker has already fired is not consent, it is
a notice. Build the refusal path first and make "no" actually mean no.

**Send no more about a person than the product needs.** An event carries what
happened and an opaque id, never an email address, a name, a full URL with a
token in its query string, or anything typed into a form. A leak through an
analytics payload is still a leak, and it is one nobody looks for.

**An event is named once and never renamed.** `checkout_completed` recorded
under three spellings is three features nobody can measure. Decide the names
with the properties they carry, write them down in the project, and use them
exactly. Past data cannot be renamed.

**Count what the product wants to know, not everything it can see.** Page views
are free and almost never the question. The events worth writing are the ones
attached to the outcome in the request: the booking made, the basket
abandoned, the search that returned nothing.

**Never block the page on it.** Load the client after the content, send events
without awaiting them, and make every call safe to fail. A product that is slow
because it is measuring itself has traded the thing for the measurement.

**It does not run in tests.** An automated run must not appear in the numbers.
Key it off the environment, and prove that in a unit test.

## Verifying it

Unit tests own the boundary with the client stubbed: no event is sent before
consent, an event carries the agreed name and no personal field, a provider
failure does not raise into the request, and nothing is sent in the test
environment.

An E2E journey asserts what the user can see — the consent banner, and that
declining leaves the page working — not that a third party received anything.
