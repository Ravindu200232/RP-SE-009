---
name: page-composition
description: How to compose a real, substantial page for this product — how much of it there should be, what order it goes in, and the section patterns that make a generated page look generated. Read with frontend-design, which owns how it looks.
license: MIT
---

# Page composition

`design-system` fixes the palette, type, corners, spacing, borders, depth,
motion, voice, contrast and width. `frontend-design` decides the personality
within that. **Do not re-open either here.** This is about what goes on the
page, how much of it, and in what order.

## Make it this product's page

Before composing, answer three questions from the brief and keep the answers
in front of you:

1. **What is this?** Not "a web app" — a clinic booking system, a parts shop,
   a recipe community.
2. **Who opens it, and what have they come to do?** A rider checking their next
   delivery is not a manager reading the day's revenue.
3. **What is this product's one characteristic thing?** The dish photograph,
   the seat map, the diff view, the waveform. That thing earns the most space.

Two products built from this skill should not be recognisable as siblings. If
what you are composing would work just as well for a different product with
the words swapped, it is not finished.

## The tells

These are what a generated page looks like. Do not produce them:

- A centred hero, a centred paragraph and a centred button — on every page
- Row after row of identical cards, icon above title above two lines
- Every section in its own rounded rectangle
- Gradient blobs, glow, and glass used as decoration rather than meaning
- One accented word in a headline; ALL-CAPS eyebrow labels over every section
- The same border radius on every element
- Numbered markers (01 / 02 / 03) on content that is not a sequence
- Charts that display nothing real; metrics invented to look impressive
- Emoji standing in for icons
- Fade-and-slide-up on every section; hover lift on every card
- Buzzword copy: "revolutionise your workflow", "unlock your potential"

## Give it real depth

A page with three sections and a lot of whitespace reads as a demo. Compose
what the product actually needs:

| Page | Sections |
|---|---|
| Marketing or landing | 8–16, when there is enough to say |
| Product or item detail | 5–9 |
| List, catalogue or search | 4–7 including filters and empty state |
| Dashboard or console | 4–8 panels, densest first |
| Form or single task | 2–4, and nothing that distracts from the task |

Every section must earn its place. Never pad to reach a number — a short page
that says something beats a long one that repeats itself.

## Order it as a narrative

A page argues, in this order, skipping what does not apply:

**Orient** what this is and who it is for → **Value** the outcome it produces →
**Proof** why to believe it → **Understand** how it works → **Depth** what makes
it strong → **Fit** who uses it and when → **Reassure** security, reliability,
support → **Decide** pricing, comparison, questions → **Act** one clear next step.

A dashboard argues differently: **what needs attention now** → **the numbers** →
**the detail behind them** → **the actions available**.

## Vary the sections

Consecutive sections must not share a shape. Change at least one of: the
background, the column count, the media/text ratio, the alignment, the density.
Three full-width text-left/image-right sections in a row is the same section
three times.

Keep the variation inside the contract's tokens — vary the composition, not the
palette.

## Compose for the product type

- **SaaS / B2B** — clarity first: what it does, a real screenshot, who trusts
  it, how it fits the work they already do.
- **Commerce** — the product photograph is the interface. Price, availability
  and the next step visible without scrolling.
- **Booking / scheduling** — availability is the hero. Show what is free before
  asking who they are.
- **Dashboard / admin** — density is a feature. Scanning beats decoration;
  the layout must not move as data loads.
- **Editorial / content** — measure, rhythm and reading comfort. The article is
  the design.
- **Portfolio / agency** — the work first, at size, with the story second.

Do not put a landing-page aesthetic on an admin console.

## Tailwind discipline

Tailwind is installed and its theme reads the contract's custom properties.

- Reach for a theme value (`bg-surface`, `text-foreground`, `rounded-xl`)
  before an arbitrary one (`bg-[#1b1f2a]`, `rounded-[13px]`).
- A repeated semantic value belongs in the theme, not copied into forty class
  lists.
- Group utilities in a stable order — layout, spacing, colour, type, state —
  so a long class list stays readable.
- Compose your own components. Do not install a component library on top.
- Do not rewrite a working Tailwind config without a reason, and do not mix
  v4 syntax into a v3 project.

## Write the words

Copy makes a page look templated faster than layout does.

- Name real things: "Add a plant", not "Get started".
- Labels short, microcopy useful, headings specific to this product.
- Seed realistic examples — real dish names, plausible prices, believable
  people. Never lorem ipsum.
- If you do not know a number, leave it out. Do not invent metrics, logos,
  testimonials or press quotes and present them as real.

## Finish every screen

A screen is not done until it holds up when things go wrong:

- **Loading** — skeletons that match the shape of the content, not a spinner
  over a blank page. The layout must not jump when data lands.
- **Empty** — say what would be here and give the action that creates it.
- **Error** — say what failed and what to do next.
- **Success** — confirm what happened, and where it went.

## The pages share a shell

An application with more than one screen has one shell, written once in the
root layout and worn by every page: the product's name, the navigation for
whoever is signed in, and a footer.

Without it each page is an island. A build that composed a good menu page, a
good checkout and a good admin table, and gave none of them a header, produced
an application where the only way from checkout back to the menu was the
browser's back button, and the only way to reach the admin screen was typing
its URL. Every page was defensible on its own and the product was not usable.

- The shell is in `app/layout.jsx` (or the equivalent), not repeated per page.
  A page that draws its own header is a page that will drift from the others.
- **The shell is thirty-odd links, not three.** The header lists every section
  of the product, with sub-items where a section has parts; the footer is a
  sitemap of three or four columns with headings, plus the small print row.
  This is the most-skipped item on the page: builds that composed decent
  screens have shipped a layout with a product name and one link in it, and
  that is a set of documents rather than an application. Count the links in
  the header and footer components — under thirty and the shell is a stub.
- Navigation shows what this visitor can actually reach. A customer does not
  see the admin link; an admin does. Hiding a link is not access control — the
  server still checks — but showing one that 403s is a broken door.
- The current page is marked in the navigation, so someone always knows where
  they are.
- The product's name is a link home from every page.
- Sign in and sign out live in the shell, and the shell says who is signed in.

A single-page tool is the exception, and only when there is genuinely one
screen.

## Responsive

Design the narrow layout as a real layout, not a squeezed one: one column,
larger touch targets, navigation that collapses to something usable, tables
that become cards or scroll deliberately. Check ~360px, ~768px, ~1280px and
one width wider than the content's maximum.

## Before you call a page done

Count these first. They are the section table above, restated where the page is
actually being written, because a count read thirty files ago is not a count:

| | Every screen |
| --- | --- |
| sections | the table above — **6 or more** on a marketing or landing page |
| the shared shell | a header listing every section of the product, and a footer of **three or four columns of links** — thirty-odd links, identical on every page |
| rows in a list or table | **8 or more**, with the empty state written too |
| fields in a form | every field the product needs, with labels and help text |
| words of real content | **400 or more** on a landing page; enough elsewhere to say what the screen is for |

A home page that is a heading, a paragraph and a button is the single most
common failure here, and it passes every qualitative check below. It is not a
page. Neither is a sign-in screen that is two inputs on an empty background:
it carries the shell, the product's name, the reason to sign in, the way to
recover an account and the way to make one.

Then:

- Would this page be recognisable as *this* product with the words removed?
- Does every section do something the one above it does not?
- Do the loading, empty and error states exist for every screen?
- Is every number, logo and quotation either real or clearly a demo?
- Does it hold together at 360px?
- Can you reach every other screen you are allowed to reach, from here?
- Did you avoid every tell in the list above?
