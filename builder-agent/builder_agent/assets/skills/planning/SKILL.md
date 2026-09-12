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

### 100% Requirements coverage & traceability

Enumerate requirements as numbered identifiers `[REQ-01]`, `[REQ-02]`, etc. Every requirement must directly trace to:
1. **The Route/Screen** where the user interacts with it.
2. **The Data & Actions**: required schema fields and API endpoints.
3. **The Non-happy States**: empty state, loading skeleton, validation errors, and unauthorized access.

Extract both explicit and implicit requirements:
- **Every role or kind of person named**, and what each one can do. "A manager sees the money" is a role, a screen and an authorisation rule.
- **Every screen, page or view**, named or implied. "Book a room" implies room browsing, availability filtering, conflict check, and confirmation receipt.
- **Every action** somebody performs: browse, filter, search, book, cancel, pay, mark done, export, approve.
- **Every piece of data** that has to exist for those actions to be possible, and what relates to what.
- **Every rule** — bookings cannot overlap, only owners can cancel, stock cannot go below zero, prices fix on checkout.
- **Every integration**: payment, email, SMS, upload, map, calendar, export.
- **Non-happy states**: empty state with guidance, loading skeletons, error toasts, 404, unauthorized.
- **Seeding & sample data**: realistic domain seed data so every screen displays populated state on first boot.
- **Passing details**: "mobile responsive", "dark mode", "language switch", "Sinhala", "no password".

Constraints are requirements too. "No payments" means the plan explicitly rules payments out of scope.

## Then check the list against the request

Go back over the request one more time with the list beside it, and ask of each
sentence: which item covers this? A sentence that no item covers is a
requirement you have just missed. Add it. Zero requirements may be dropped.

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

Every screen, including the ones that are obvious: whatever answers at `/`,
the sign-in page, the empty state someone lands on first. What `/` is belongs
to the product — a shop front for something being sold, the day's figures and
what needs doing for something people work in — so say which it is rather than
writing "home" and leaving it to be guessed. If a screen has no route yet
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
