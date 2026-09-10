---
name: planning
description: Turn a request into a plan that covers all of it — how to enumerate what was asked for before deciding how to build it, what counts as a requirement, and what is never allowed to go missing.
---

# Planning a build

The plan is the only place the whole request is held at once. Everything after
it works from the plan, so anything the plan does not mention is not built —
and nobody finds out until the app is finished and the thing they asked for is
not in it.

The failure is never "the plan was wrong". It is "the plan was about most of
it". A request names eleven things; the plan describes eight beautifully, and
the three it skipped were skipped silently.

## First, list what was asked for

Before any thought about structure, read the request again and write down every
distinct thing it asks for. Work through it phrase by phrase rather than
summarising it — a summary is exactly where a requirement goes missing.

Take one requirement from each of these when the request contains it:

- **Every role or kind of person named**, and what each one can do. "A manager
  sees the money" is a role, a screen and an authorisation rule.
- **Every screen, page or view**, named or implied. "Book a bench" implies
  something that lists benches and something that confirms.
- **Every action** somebody performs: browse, filter, book, cancel, pay, mark
  done, export, approve.
- **Every piece of data** that has to exist for those actions to be possible,
  and what relates to what.
- **Every rule** — a booking cannot overlap, only the owner can cancel, stock
  cannot go below zero, a price is fixed at the time of order.
- **Every integration**: payment, email, SMS, upload, map, calendar, export.
  These carry credentials and belong in the plan as their own work.
- **Everything about state that is not the happy path**: empty, loading, error,
  unauthorised, not found, and what a first-time user sees before there is any
  data.
- **Everything said about seeding**: demo users, sample data, "enough that
  every screen has something on it".
- **Everything said in passing.** "…and it should work on a phone" is a
  requirement. So is "in Sinhala", "no login", "with photos".

Constraints are requirements too, including the negative ones. "No payments"
means the plan says payments are out of scope — not that payments are absent
from the plan.

## Then check the list against the request

Go back over the request one more time with the list beside it, and ask of each
sentence: which item covers this? A sentence that no item covers is a
requirement you have just missed. Add it.

This second pass is the whole method. Skipping it is how eight-of-eleven
happens.

## Only then decide how to build it

Group the requirements into ordered phases where each phase leaves the app in a
working state, and give each one a done condition that can be checked rather
than believed. Order execution as implementation, production build, runtime
readiness, unit and integration evidence, E2E evidence, done.

Each requirement has to appear in exactly one phase, and every requirement on
the list has to appear in some phase. A requirement that survived the listing
and then fell out of the phases is no better off than one that was never
listed.

## Name the screens, with their routes

Give the plan a **Screens** section that lists every screen the product has,
one per line, each with its route and one line saying what it is for:

```
## Screens
- `/` — Home: today's soups and what is left.
- `/menu` — Menu: the whole menu with prices and allergens.
- `/admin/orders` — Admin orders: every order, and marking one collected.
```

This section is read directly: it is what the design step offers the user to
confirm, and what the drawing of the application is made from. A plan that
describes its screens only inside prose — "a rooms page with filters", "a
dashboard of KPIs" — leaves both of those steps guessing, and a six-screen
product has been shown to the user as a single page because of it.

Every screen, including the ones that are obvious: the home page, the sign-in
page, the empty state someone lands on first. If a screen has no route yet
because the stack decides it, say so rather than leaving it out.

## What the plan must contain

- The goal in one sentence, and what must stay true whatever else changes.
- **The requirements, enumerated and numbered**, so they can be counted and
  pointed at. This is the part that gets skipped; it is the part that matters.
- **The screens**, as above, each with its route.
- What is deliberately out of scope, and why — usually because the request
  ruled it out.
- What the project already has, from `inspectProject`, and what that changes.
- The phases, in order, each naming which numbered requirements it satisfies
  and how you will know it is done.
- What proves the whole thing: which journeys, which boundaries.
- Real limitations: what cannot be verified here, and what will be assumed.

## Honesty

Do not quietly narrow the request because part of it is hard. If something
cannot be done in this stack, the plan says so, in that requirement's own
words, and the rest is still built.

Do not pad the plan with work nobody asked for. A requirement that is not in
the request and not needed to make one that is work is scope you invented.

Do not implement anything during planning: no installs, no generators, no
seeding, no servers, no tests. Read what you need, list what was asked, and
submit one complete plan.
