---
name: html-prototype
description: Draw the whole application as static HTML before any of it is built — every planned screen, the chosen design tokens, realistic content, styled by one stylesheet of your own CSS, no framework, no build step and no backend — so the look can be agreed before the expensive part starts.
---

# The HTML prototype

Draw the application before it is built. One static HTML file per screen the
plan named, styled by the design contract just agreed, filled with content that
belongs to this product. The user looks at it, asks for changes, and only then
does the real build start — from what they approved.

This is the cheapest place in the pipeline to be wrong: a layout wrong here
costs a re-render, the same layout wrong after the build costs the build.

## What it is

- **Plain HTML, one stylesheet of your own CSS, and a little JavaScript.** No
  React, no bundler, no npm install, no build step, no CSS framework. A file
  opens in a browser and works, offline, first time.
- **A multi-page application.** A file per screen, reached through the
  navigation — Not one page with sections, not one file with tabs. The
  user opens `menu.html`, clicks through to `checkout.html`, and sees what that
  is like.
- **It works.** Somebody clicks through it. See "Make the flow work".
- **No backend.** No fetch, no API, no database, no server. Every piece of
  state lives in the page.

It is not a wireframe of grey boxes, not a component library, not a style guide
page, and not a place for lorem ipsum.

## The files you write

```
.agentforge/prototype/styles.css    the whole look, written first
.agentforge/prototype/index.html    the first screen the plan named
.agentforge/prototype/<screen>.html one per remaining screen, named after its route
.agentforge/prototype/demo.js       the script that makes the flow work
```

Create the folder with `writeFile`. There is nothing in it to read, and nothing
to look up first: the screens are in the request, the tokens in
`design-system.md`.

**`styles.css` first, and finished.** It is where the product gets its
character, and writing it first is what makes twelve pages look like one
product. Pages written before their stylesheet carry their design in their
markup, and then the look cannot be changed in one place.

**Every rule lives in it**: no `<style>` block in a page, no `style="…"` on an
element. A rule written into one file drifts from the other eleven.

## The design contract owns the look

The palette, type, radius, spacing, border weight, shadow depth and container
width are already decided, in `design-system.md`. Put its tokens at the top of
`styles.css` as custom properties and reference them everywhere:

```css
:root {
  --primary: #EA580C;
  --surface: #FFFFFF;
  --radius:  12px;      /* … the rest, from the contract */
}
```

**Never write a hex value anywhere but that block.** One property changes and
the whole prototype follows — that is the point, and a hard-coded `#EA580C` in
a button rule breaks it.

## The head of every page

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Overview | Workspace</title>
  <link rel="stylesheet" href="styles.css">
</head>
```

**No CSS framework.** No Tailwind, no Bootstrap, no `<script src="…cdn…">`
that styles the page, no `@apply`. A drawing that compiles its stylesheet in
the browser is one unknown class away from rendering as bare HTML — a single
`hover:shadow-overlay` once left every page of a seven-page drawing unstyled.
Your own CSS cannot fail that way: an unknown rule is skipped and the rest of
the page keeps its styling.

`demo.js` goes once, at the end of `<body>`.

## The stylesheet

`styles.css` is the whole look, in this order: the tokens; a short reset
(`box-sizing`, margins off, body type and colour, `img { max-width: 100% }`);
the shell; the components; the layout helpers you actually use; the motion;
then the tablet and phone blocks.

Ordinary CSS a person can read:

```css
.button-primary {
  display: inline-flex; align-items: center; gap: .5rem;
  padding: .8rem 1.5rem; border: 0; border-radius: var(--radius);
  background: var(--primary); color: #fff; font-weight: 600; cursor: pointer;
  transition: transform .15s ease, box-shadow .15s ease, background .15s ease;
}
.button-primary:hover  { background: var(--primary-hover); transform: translateY(-1px); }
.button-primary:active { transform: translateY(0) scale(.98); }
```

**A class says what the thing is, not what it looks like.** `.metric-card`,
`.item-row`, `.price`, `.status-badge` — never `.mt-12` or `.text-sm`. Forty
buttons carrying look-alike classes is forty places to edit when the user says
"make the buttons bigger", and the fortieth will be missed.

Use what CSS gives you: `grid-template-columns: repeat(auto-fill, minmax(16rem,
1fr))`, `flex`, `gap`, `clamp()`, `:hover`, `:focus-visible`, `:disabled`,
`[data-state="paid"]`, `:nth-child`.

## Motion

The build copies what it sees here, so decide it here.

- **Everything interactive transitions** on the property that changes. Nothing
  jumps.
- **The page arrives** — a short fade-and-rise on the sections, staggered:

  ```css
  @keyframes rise { from { opacity: 0; transform: translateY(12px); } }
  .section { animation: rise .5s ease both; }
  .section:nth-child(2) { animation-delay: .06s; }
  ```
- **State changes are animated, not swapped**: a row marked paid, a basket
  count going up, an error appearing, a panel opening.
- **Loading looks like loading** — a skeleton shimmer or a spinner in CSS.
- **End with the setting honoured:**

  ```css
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration: .01ms !important;
                             transition-duration: .01ms !important; }
  }
  ```

150ms to 500ms, a few pixels. Motion that has to be waited for is worse than
none.

## Make it good, not only complete

A page can pass every count below and still look like a form someone filled
in. Asked for one page in a single sitting this same model writes 127 CSS
rules; drawing twelve screens against a checklist it wrote 44. The checklist
takes the attention the design should have had — so spend it here, on the
stylesheet, where it is reused twelve times.

- **The opening decides the product — and what the opening *is* depends on who
  opens it.** Something sold to the public opens on a hero: a real photograph
  with something over it, a gradient scrim, a vignette, a wash from the
  palette, the title in the display face at `clamp()` size. Something worked in
  opens on the work: today's figures across the top, then the queue, at
  density. Both are designed. Only one of them is a hero, and a till given a
  hero was designed for the wrong reader. A heading on a white band is the
  clearest sign nobody designed either.
- **Depth in the palette's own colours**: a shadow tinted with the primary
  rather than black, a border one shade off the surface, a section on
  `--surface-alt`. Flat grey on white is the default nobody chose.
- **A rhythm, not a list**: for a public page, full-bleed photograph, contained
  text, a grid, a quiet band; for a working screen, the figures, a dense table,
  a narrower panel beside it. Same padding everywhere reads as a template
  either way.
- **One thing that is yours** — a card that lifts and shows its price, a number
  that counts up, a nav that condenses, a photograph that zooms inside its
  frame, a hand-drawn underline in SVG. One is enough, and it is what they
  remember.
- **Type does the work**: two faces from the contract, display large and tight,
  body at a comfortable measure, sizes from a scale.
- **Detail at the edges**: focus rings in the brand colour, a selection colour,
  a hover state on everything interactive, an empty state with a drawing in it.

## The shell

An authentic navigation shell on every page, designed for the product's actual archetype:
- **Public products and storefronts**: A top navigation bar with brand, primary sections, search/actions, and a structured multi-column sitemap footer with secondary links and copyright.
- **Applications, dashboards, and tools**: A real application shell — sidebar navigation with active route highlights, top workspace bar with breadcrumbs, search, user menu, and status bar.

The product's name links to `index.html` and the current page is clearly marked as active.

**Every link is a real `<a href="…">` in the markup**, including into detail
pages: a list of items is a list of written-out anchors, one per item. A page
reachable only because a script built its link is a page nobody finds by
reading the file. An admin or settings screen's link is in the markup too — let the script
hide or disable it when appropriate, rather than generating anchors out of thin air.

## Make the flow work

A demo that cannot be clicked tells the user almost nothing.

- **The thing the product is for works end to end**: add to a basket and the
  count goes up and the item is on the basket page; book a slot and it shows as
  booked; mark an order collected and the row changes state.
- **Forms respond**: an empty field shows that field's error, a good one shows
  the success state. Nothing is posted anywhere.
- **Controls do their job**: a filter filters, a search narrows, a tab
  switches, a sort reorders.
- **State survives the walk.** One `localStorage` key, one `load()`, one
  `save()`, called on every change — so what was added on one page is still
  there on the next and after a reload. State in a plain variable is gone at
  the first click, which makes the demo a slideshow. No `localStorage` in
  `demo.js` means the flow does not work, whatever one page looks like.
- **Signing in works without checking anything**: any password is accepted, it
  sets a name and a role, and the navigation changes to match. The page never
  says so.

### The script never supplies the content

Every card, row, link and word is written in the HTML. The script only
*changes* what is already there — filters the rows, marks one booked, updates a
count, shows an error. An empty `<div id="grid"></div>` the script fills is a
page with nothing in it and nothing linking anywhere. **Delete `demo.js` and
the drawing must still be the whole application, just inert.**

Keep it small: one file, plain functions, no framework, no `fetch`.

## Full size, not a sketch

A thin page gets approved — there is nothing in it to disagree with — and then
the build is made to match it. Every screen is the whole page: the full shell appropriate to the archetype, complete functional views, no stubs. A sign-in page is a full page too.

**Substantial, archetype-native composition.** Generate a professional app with
long quality and comprehensive depth. Do not impose fixed section lists,
arbitrary counts, or artificial templates — what is needed for the product,
the LLM naturally selects. What goes on the screen depends on what the product genuinely is:

- **Sold to the public**: the hero, then what it is, then the proof or the
  detail, then a call to action, then the footer.
- **Worked in** — a counter, a console, a back office, a dashboard, or a tool: opens directly on the work. Today's figures, what
  needs doing now, the queue, or the interactive canvas. No "how it works"
  explainer, no marketing hero banner, and no promotional call to action. A till that greets its own cashier with a landing page was built for the wrong reader.

A working screen opens directly on the work: current metrics, controls, data views, and row actions. Density is what a working screen is for; it has no hero photograph. Include the **empty state**, drawn rather than described.

Then: lists look like lists (eight or ten rows, not two), tables have their
columns and statuses and actions, dashboards have their figures, forms have
every field with labels and help text, detail pages have the whole record.
Every requirement the plan enumerated is visible on some page — work through
them one at a time and place each. A requirement nobody can see was not drawn.

Only the screens the plan names. A product with no admin area has no admin
page, and inventing one is worse than drawing a thin one.

## The content

What this product would actually hold: realistic domain items with names, prices,
and descriptions; books with titles and authors; bookings with dates,
guests, and states. Not "Item 1". Not lorem ipsum. Prices with the right
currency, dates in a real format, statuses from the real set.

Invented but plausible content is what lets someone say "that is not what I
meant". Grey placeholder boxes tell them nothing.

## Pictures

A product with catalog items, portfolios, courses, or people uses photographs where appropriate, and a
drawing of it with none is a wireframe.

```html
<img src="https://loremflickr.com/800/600/bedroom,garden,hotel/any?lock=12"
     width="800" height="600" alt="The Willow room, looking onto the garden">
```

- **A photograph of the thing.** The tags name the subject and nothing else —
  two or three, most specific first.
- **`/any` after the tags, always.** Without it the service wants one
  photograph carrying every tag at once and errors when there is none.
- **`?lock=<n>`, a different number per picture.** Without it the same address
  returns a different photograph on every request and the page reshuffles as
  you scroll.
- **A source whose addresses always resolve.** Tags and a lock are all
  `loremflickr.com/<w>/<h>/<tags>` needs. Never a source whose ids have to be
  looked up.
- **Always `width` and `height`** matching the ratio, so the layout does not
  jump, and **real `alt`** describing that subject.
- Never a grey box, never a coloured rectangle, never an `<img>` with no `src`.

A dashboard of numbers genuinely has no pictures; do not invent them there.

## Every state that matters

Draw them where they belong, not on a separate page: an empty list with the
line that says what would be here and the action that creates it, a form with
an error on one field, a row in each status the product defines.

## Three widths, all three finished

- **Phone, ~390px.** One column, the navigation collapsed to a button, touch
  targets at least 44px, tables scrolling inside their own box. The page never
  scrolls sideways.
- **Tablet, ~820px.** Two columns where three do not fit, the navigation back
  on the page.
- **Desktop.** The full layout, held to the contract's container width and
  centred, not stretched edge to edge.

Two `@media` blocks, and fluid sizes (`clamp()`, `minmax()`, `auto-fit`) for
the rest. Check every page at all three.

## Changing it

The user asks in their own words: "make the buttons blue", "this heading is too
big". Apply it where it belongs — a token in `styles.css` for a colour or a
radius, that component's own rule for the look of one kind of thing — and
re-render only the files that changed. A change made by editing markup across
nine files will be half-applied. If they point at one element, change that one:
a class used once, never an inline style.

## Never say it is a drawing

Nothing on any page says prototype, mockup, demo, coming soon or not
implemented, and nothing explains what is missing. Two places invite it and
both have produced one:

- **The sign-in page.** Any password works, but the page reads exactly as the
  real one: the fields, "forgot your password", the link to register.
- **The payment step.** No card is taken, but it shows the card fields, the
  order summary and the total.

The one thing this cannot do is store data on a server, and that is invisible.
There is nothing to apologise for.

## Before you show it

| | Every page |
| --- | --- |
| links in the header | **12 or more** — on public sites (or complete app navigation for tools) |
| links in the footer | **12 or more** — sitemap columns (or status bar for tools) |
| the two together | **30 or more** — all planned routes linked across the shell |
| depth & quality | professional app with long quality — the LLM naturally selects all panels and views |
| rows in a list or table | **8 or more** |
| pictures, where the product shows them | enough that the page is of something (none on raw dashboards) |
| `localStorage` in `demo.js` | present |
| text saying "demo", "prototype" or "coming soon" | none |

| | `styles.css` |
| --- | --- |
| rules | **120 or more** |
| `transition:` | **12 or more** |
| `@keyframes` | **3 or more** |
| `:hover`, `:focus-visible`, `:disabled`, empty and error states | all present |
| `@media` | the phone and the tablet, both |

A page is as long as what it has to say — write the authentic views this product
actually has and stop when you run out of true things, rather than padding to
reach a size. A page with thin stubs is empty whatever it weighs.

- Does every screen the plan named exist, as a full page rather than a stub?
- Can you click the main flow from beginning to end and see it respond?
- With `demo.js` deleted, is every page still whole, with every link working?
- Can you point at where each of the plan's requirements is?
- Is every colour a token reference — no hex outside `styles.css`?
- Is `styles.css` the only stylesheet: no framework, no CDN, no `<style>` in a
  page?
- Does it move, and is `prefers-reduced-motion` honoured?
- Is the content this product's own, with no placeholder text?
- Does every place the real product shows a picture show a real photograph?
- Does it hold at all three widths, none of them scrolling sideways?
- Would the person who wrote the request recognise their product?
