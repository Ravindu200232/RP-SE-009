---
name: html-prototype
description: Draw the whole application as static HTML before any of it is built — every planned screen, the chosen design tokens, realistic content, styled by one stylesheet of your own CSS, no framework, no build step and no backend — so the look can be agreed before the expensive part starts.
---

# The HTML prototype

Before the real application is built, draw it. One static HTML file per screen
the plan named, styled with the design contract that was just agreed, filled
with content that belongs to this product. It is shown to the user, changed
until they are happy with it, and only then does the real build start — from
what they approved.

This is the cheapest place in the whole pipeline to be wrong. A layout that is
wrong here costs a re-render; the same layout wrong after the build costs the
build.

## What it is

- **Plain HTML, one stylesheet of your own CSS, and a little JavaScript.** No
  React, no bundler, no npm install, no build step, and no CSS framework —
  nothing is compiled in the browser. A file opens in a browser and works,
  offline, first time.
- **It works.** This is a demo somebody clicks through, not a picture of one.
  See "Make the flow work" below.
- **No backend.** No fetch, no API, no database, no server. Every piece of
  state lives in the page.
- **Every screen the plan named**, one file each, plus the shared stylesheet
  and one small `demo.js`.
- **A real navigation between them**: the files link to each other with plain
  `<a href="menu.html">`, so the user can walk the whole application.

## What it is not

- **Not one page.** It is a multi-page application: a separate file per screen,
  reached through the navigation. Not one long page with sections, not one file
  with tabs, not one document with anchors. The user has to be able to open
  `menu.html`, click through to `checkout.html`, and see what that is like.
- Not a wireframe of grey boxes. It is what the product will look like, in
  colour, with its type and spacing and its own words.
- Not a component library, a style guide page or a token dump.
- Not a place for lorem ipsum. See below.

## The files you write

`.agentforge/prototype/` is a folder in the project. You **create** it with
`writeFile`. It is not part of this skill and there is nothing in it to read —
this skill is one file, `SKILL.md`, and you have it in front of you. Do not
call `readSkill` for anything under `.agentforge/`.

Write these, with `writeFile`, using the paths exactly as shown:

```
.agentforge/prototype/index.html    the first screen the plan named
.agentforge/prototype/<screen>.html one per remaining screen, named after its route
.agentforge/prototype/styles.css    the design tokens, linked by all of them
.agentforge/prototype/demo.js       the small amount of script that makes the flow work
```

Start writing. There is nothing to look up first: the screens are listed in the
request, and the tokens are in `design-system.md`, which is the one other file
worth reading.

**One `styles.css`, linked from every page, and every rule lives in it.** No
`<style>` block in a page, no `style="…"` on an element. A rule written into
one file is a rule that will drift from the other eleven, and a colour change
the user asks for then has to be made five times instead of once.

## The design contract owns the look

The palette, type, radius, spacing, border weight, shadow depth and container
width were chosen and written to `design-system.md` and its token block. Put
those tokens at the top of `styles.css` as custom properties and reference them
everywhere:

```css
:root {
  --primary: #EA580C;
  --surface: #FFFFFF;
  --radius:  12px;      /* … the rest, from the contract */
}
```

**Never write a hex value anywhere but that block.** When the user asks for a
different colour, one property changes and the whole prototype follows. That is
the point of the exercise, and a hard-coded `#EA580C` in a button rule breaks
it.

## The head of every page

The same five lines in all twelve files. Nothing is fetched from the internet
and nothing is compiled in the browser:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Rooms & Suites | Royal Azure</title>
  <link rel="stylesheet" href="styles.css">
</head>
```

**No CSS framework.** No Tailwind, no Bootstrap, no `<script src="…cdn…">`
that styles the page, no `@apply`, no `<style>` block in the page. A drawing
that compiles its stylesheet in the browser is one unknown class away from
rendering as bare HTML — which is exactly what happened to a hotel drawing of
seven pages, where a single `hover:shadow-overlay` in a `.card` rule left every
page unstyled. Your own CSS cannot fail that way: a rule the browser does not
understand is skipped, and the rest of the page still has its styling.

`demo.js` goes at the end of `<body>`, once, with `<script src="demo.js"></script>`.

## The stylesheet

`styles.css` is the whole look of the product, in this order:

1. **The tokens** from the design contract, as custom properties on `:root`.
2. **A short reset** — `box-sizing`, margins off, `body` type and colour,
   `img { max-width: 100% }`.
3. **The shell**: the header, the navigation, the footer, the page container.
4. **The components**, each named for what it is: `.button-primary`,
   `.button-secondary`, `.card`, `.field`, `.nav-link`, `.badge`, `.table`,
   `.stat`, `.empty`.
5. **The layout helpers** you actually use — a `.grid-3`, a `.row`, a
   `.stack` — written once, not a utility library.
6. **Motion**, below.
7. **The phone**, in one `@media (max-width: 720px)` block at the end.

Write it as ordinary CSS a person can read:

```css
.button-primary {
  display: inline-flex;
  align-items: center;
  gap: .5rem;
  padding: .8rem 1.5rem;
  border: 0;
  border-radius: var(--radius);
  background: var(--primary);
  color: #fff;
  font-weight: 600;
  cursor: pointer;
  transition: transform .15s ease, box-shadow .15s ease, background .15s ease;
}
.button-primary:hover  { background: var(--primary-hover); transform: translateY(-1px); }
.button-primary:active { transform: translateY(0) scale(.98); }

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.5rem;
  transition: box-shadow .2s ease, transform .2s ease;
}
.card:hover { box-shadow: 0 10px 30px rgb(0 0 0 / .12); transform: translateY(-2px); }
```

**A class says what the thing is, not what it looks like.** `.room-card`,
`.booking-row`, `.price`, `.status-paid` — never `.mt-12`, `.text-sm`,
`.flex-row-gap-6`. Forty buttons each carrying a handful of look-alike classes
is forty places to edit when the user says "make the buttons bigger", and the
fortieth will be missed. A request to change "the buttons" has to have one
thing to change.

Use what CSS already gives you rather than inventing scaffolding: `display:
grid` with `grid-template-columns: repeat(auto-fill, minmax(16rem, 1fr))`,
`flex`, `gap`, `clamp()` for type that scales, `:hover`, `:focus-visible`,
`:disabled`, `[data-state="paid"]`, `:nth-child`.

## Motion

The product should feel alive when it is clicked, and this is where that is
decided — the build copies what it sees here.

- **Every interactive thing transitions.** Buttons, cards, rows, links, fields:
  `transition: … .15s ease` on the property that changes. Nothing jumps.
- **The page arrives.** A short fade-and-rise on the main sections, staggered
  by a few tens of milliseconds, is enough:

  ```css
  @keyframes rise { from { opacity: 0; transform: translateY(12px); } }
  .section { animation: rise .5s ease both; }
  .section:nth-child(2) { animation-delay: .06s; }
  ```
- **State changes are animated, not swapped.** A row marked paid, a basket
  count going up, an error appearing, a panel opening: give it a keyframe —
  a pulse, a slide, a tick that draws itself.
- **Loading looks like loading.** A skeleton shimmer or a spinner drawn in CSS,
  where the real product would wait for data.
- **Respect the setting.** End the motion section with:

  ```css
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration: .01ms !important;
                             transition-duration: .01ms !important; }
  }
  ```

Keep it quick and small — 150ms to 500ms, a few pixels, never a bounce that
holds the page up. Motion that has to be waited for is worse than none.

## The shell

Every page carries the same header, navigation and footer, written into each
file. The product's name links to `index.html`, the navigation lists the
screens this visitor can reach, and the current page is marked.

**The shell is most of the links on the page.** In a real site the header and
footer together carry thirty to forty links, and they are identical on every
page. That is what makes a set of files feel like one product rather than ten
documents. Specifically:

- **The header** lists every section of the product, not a shortlist of four.
  Where a section has parts — rooms by type, a menu by service, reports by
  period — they hang off it as a dropdown whose items are real anchors too.
  Twelve to twenty links.
- **The footer** is a sitemap: three or four columns of links, each with a
  heading, plus the small print row and the social links. It repeats the main
  navigation and adds what does not belong at the top — contact, terms,
  careers, help. Twelve to eighteen links.

A page whose header is one row of five links and whose footer is a copyright
line is the single clearest sign the drawing is a sketch. Count them: if the
header and footer together are under thirty links, the shell is not finished.

**Every link is a real `<a href="…">` in the markup**, including the ones into
a detail page: a list of rooms is a list of `<a href="rooms-id.html">`, written
out, one per room. A page you can only reach because the script built its link
is a page nobody can reach by reading the file, and the drawing is read as
often as it is clicked.

Nothing is hidden behind a role at first sight either. If an admin screen
exists, its link is in the markup — let the script hide it when the demo is
signed in as a guest, not the other way round.

A prototype where one screen cannot be reached from another has not shown the
user their application.

## Make the flow work

A demo that cannot be clicked through tells the user almost nothing. They ask
"what happens when I add one?" and a picture cannot answer.

So write a small `demo.js`, linked from every page, and make the product's main
flow actually run in the browser:

- **The thing the product is for works end to end.** Add to a basket and the
  basket count goes up and the item appears on the basket page. Book a slot and
  it shows as booked. Mark an order collected and the row changes state.
- **Forms respond.** Submitting with a field empty shows that field's error;
  submitting a good one shows the success state the real app will show. Nothing
  is posted anywhere.
- **Controls do their job.** A filter filters the rows on the page, a search box
  narrows them, a tab switches the panel, a sort reorders.
- **State survives the walk.** This is not optional and it is the thing most
  often skipped. Read and write one `localStorage` key — `const KEY = "…"`, one
  `load()`, one `save()`, called on every change — so adding something on the
  menu page is still there on the basket page, and still there after a reload.
  State held in a plain variable is gone at the first link click, which makes
  the demo a slideshow. If `demo.js` contains no `localStorage`, the flow does
  not work, whatever it looks like on one page.
- **Signing in works without checking anything.** Any password is accepted; it
  sets a name and a role in that same state and the navigation changes to
  match. Never a real check, never a real credential — and the page never says
  so. It reads as the product's own sign-in page.

### The script never supplies the content

This is the trap. Told to make it work, it is tempting to write
`<div id="roomGrid"></div>` and have the script fill it — and then the page is
four empty sections, nothing links anywhere, and the drawing shows nothing at
all with scripting off.

**Every card, row, link and word is written in the HTML.** The script *changes*
what is already on the page: it filters the rows that are there, marks one
booked, updates a count, shows an error, switches a panel. If you delete
`demo.js` the drawing must still be the whole application, just inert.

Keep it small and readable — one file, plain functions, no framework, no
`fetch`. It is there to make the flow real, not to be the application.

## Full size, not a sketch

The most expensive mistake here is a thin page. A thin page gets approved,
because there is nothing in it to disagree with, and then the real build is
made to match it.

**Every screen is a full page.** No stubs. A sign-in page still has the
product's header, its own layout, the form with its fields and its error state,
and the footer — a 3KB page in a set of 12KB pages is the one the user will
point at.

**A page is several sections, not one block.** A home page is a hero, then the
thing the product does, then the proof or the detail, then a call to action,
then the footer — **six to ten distinct sections** that each do something the
one above it does not. One long column of cards is not a page.

Six is the floor, not the aim. A landing page for a product with anything to
say runs to ten or twelve: the hero, what it is, the categories, the featured
items, how it works, the proof, the numbers, who it is for, the questions
people ask, the call to action. Write the ones this product actually has, and
stop when you run out of true things to say rather than when you reach a count.

**This applies to every screen the product has, not only the ones that sell
it.** A screen somebody works in — a dashboard, a console, a table of orders,
a queue of arrivals, a form, a settings page — is the one this gets wrong: it
comes back as a heading and the thing itself, three sections against the home
page's nine, and it is the screen the people who use the product every day
spend their day in.

Give a working screen its own six, and check each one is actually on the page:

1. What this screen is, and what the person is looking at right now.
2. **The numbers across the top** — the counts, totals or figures that say how
   today is going. A table with no figures above it is the commonest miss.
3. **The controls** — the date it is showing, the filters, the search, the
   tabs. A table nobody can narrow is a report, not a screen.
4. The thing itself, with its columns, its statuses and its row actions.
5. **What it looks like with nothing in it** — drawn on the page, not
   described. The first day of use is the empty state.
6. The next thing the person needs: the related queue, the recent activity,
   what to do when a row is wrong.

Numbers, controls and the empty state are the three that keep going missing,
and a screen without them is the thin one. It has no hero photograph and
should not have one; density is what it is for.

Only for the screens the plan actually names. A product with no admin area has
no admin page, and inventing one is worse than drawing a thin one.

So each file is the whole page:

- **Lists look like lists.** Eight or ten rows, not two. Enough that the
  spacing, the density and the scroll are real decisions someone can react to.
- **Tables have their columns**, their statuses, their row actions, their
  header, and a total or a count if the product has one.
- **Dashboards have their figures** — real-looking numbers, the comparison or
  the trend beside them, and the panels arranged as they will be.
- **Forms have every field** the product needs, with labels, help text, and the
  buttons in their real order.
- **Detail pages have the whole record**, not a title and a paragraph.

Every requirement the plan enumerated is visible on some page. Work through
them one at a time and place each one. If the plan says a seller edits only
their own listings, there is a screen where that is on the page — the edit
control on their rows and not on others'. A requirement nobody can see was not
drawn.

## The content

Write what this product would actually hold. Six soups with names, prices and
descriptions. Eight books with titles and authors. Three bookings with dates
and guests and states.

Not "Item 1, Item 2". Not lorem ipsum. Not "Lorem ipsum dolor sit amet" in a
paragraph that will be a product description. Invented but plausible content is
what lets someone look at a screen and say "that is not what I meant" — grey
placeholder boxes tell them nothing.

Numbers should look like real numbers: prices with the right currency and
decimals, dates in a real format, statuses from the real set.

## Pictures

A product with rooms, dishes, courses or people is mostly photographs, and a
drawing of it with none is not a drawing of it. A hotel mock with a gallery
page and not one `<img>` tells the user nothing about their product.

So wherever the real application shows a picture, show a real photograph:

```html
<img src="https://loremflickr.com/800/600/bedroom,garden,hotel?lock=12"
     width="800" height="600" alt="The Willow room, looking onto the garden">
```

- **A photograph of the thing, not a photograph.** The address carries the
  subject as tags — `bedroom,garden,hotel`, `sourdough,bread`,
  `ferrari,supercar` — and what comes back is of that. Two or three tags,
  most specific first.

  This is the whole point and it is easy to get wrong. A seeded picture from a
  random-photo service is stable and pretty and has nothing to do with the
  product: a bakery's Country Sourdough card came back as a pine forest, and a
  supercar page as a black-and-white photograph of somebody's arm. The page
  looks finished in a thumbnail and absurd the moment anyone reads it.
- **`?lock=<n>` on every one**, a different number per picture. Without it the
  same address returns a different photograph on every request, so the page
  reshuffles itself as you scroll and again on the next redraw. With it, the
  same address is the same photograph every time — verified: three fetches of
  `?lock=7`, three identical files.
- **A public source that needs no account and no key, where any address you
  write resolves.** Tags and a lock are all `loremflickr.com/<w>/<h>/<tags>`
  needs, and both are yours to make up.

  **Not a source whose addresses have to be looked up.** A photograph on
  Unsplash lives at `photo-1566665797739-1674de7a4279`, and there is no way to
  know from here which of those identifiers exist — so they get invented, and
  an invented one is a grey rectangle where the hero should be. This is not
  hypothetical: a drawing shipped with three of those, one of which 404s, and
  it is the first thing on the home page. If a source needs a real identifier
  you cannot verify, it is the wrong source for a drawing.
- **Always `width` and `height`**, matching the ratio you asked for, so the
  layout does not jump as the pictures land.
- **Real `alt` text** describing that specific subject, not "image" or the
  product's name.
- A hero, a gallery, a card grid, an avatar, a logo strip: all of them get
  real pictures.
- Never a grey box, never a coloured rectangle standing in for a photograph,
  never an `<img>` with no `src`.

If the product genuinely has no pictures — a dashboard of numbers, an admin
table — do not invent them. Everywhere else, the absence is what makes a mock
look like a wireframe.

## Every state that matters

A screen that only shows the happy path hides the decisions. Where the product
has them, draw them — an empty list with the line that says what would be here
and the action that creates it, a form with an error on one field, a row in
each status the product defines. Put them on the page they belong to, not on a
separate "states" page.

## Responsive

It has to hold together on a phone. One column, larger touch targets, the
navigation collapsed to something usable. Check it at about 360px as well as
wide — the user will.

## Changing it

The user will ask for changes, in their own words: "make the buttons blue",
"this heading is too big", "put the price above the description". Apply the
change everywhere it belongs — a token in `styles.css` where it is a colour or
a radius, that component's own rule where it is the look of one kind of thing —
and re-render only the files that changed. A change made by editing markup
across nine files is a change that will be half-applied.

If they point at one element and ask for a change to that alone, change that
one — a class used once, or a modifier on it, never a new inline style.

## Never say it is a drawing

Nothing on any page tells the reader that this is not the real product. No
"prototype", no "mockup", no "demo only", no "coming soon", no "not
implemented", no "this is a demo", no note explaining what is missing or what
would happen in the real app. No `lorem ipsum` either — every word is this
product's own.

Two places invite this note, and both have produced one:

- **The sign-in page.** Any password works, but the page does not say so.
  It reads exactly as the real sign-in: the fields, the "forgot your
  password", the link to register. Not "this is a demo — any email works".
- **The payment step.** No card is taken, but the page does not say so. It
  shows the card fields, the order summary and the total, like the real one.
  Not "no payment is taken and no card is stored".

Write the page the real product would have. The one thing this cannot do is
store data on a server, and that is invisible — the demo keeps its state in the
browser and behaves exactly as the real thing would within one visit. There is
nothing to apologise for, so do not.

## Before you show it

Count these before you stop. They are the difference between a page and a
sketch of a page, and each one has been the fault at least once:

| | Every page |
| --- | --- |
| header + footer links | **30 or more**, and identical on every page |
| sections *between* the header and the footer | **6 or more** — the header, the nav and the footer are not three of the six, and counting them is how a page with three real sections passes this line |
| bytes | **9,000 or more**; a landing page **15,000 or more** |
| words of real content | **150 or more**; a landing page **400 or more** |
| pictures, where the product shows them | **6 or more** on a page that shows things |
| rows in a list or table | **8 or more** |
| `localStorage` in `demo.js` | **present** |
| `@keyframes` in `styles.css` | **3 or more**, and a `transition` on everything that responds |
| text that says "demo", "prototype" or "coming soon" | **none** |

A page under those is not finished — go back to it and add what is actually
missing, rather than padding what is already there.

- Does every screen the plan named exist as a file, and is each one a full
  page rather than a stub?
- Can you click the product's main flow from beginning to end and see it
  respond?
- With `demo.js` deleted, is every page still the whole page, with every link
  still working?
- Can you point at where each of the plan's requirements is on a page?
- Is every dimension the design contract settled actually expressed?
- Can you reach every screen from every screen?
- Is every colour a token reference — no hex outside `styles.css`?
- Is `styles.css` the only stylesheet: no framework, no CDN, no `<style>` block
  in a page, no `style="…"` on an element?
- Does it move — a transition on everything that responds, the sections
  arriving, the state changes animated, and `prefers-reduced-motion` honoured?
- Is the content this product's content, with no placeholder text left?
- Does any page look thin — a list of two, a table with no statuses, a form
  missing half its fields?
- Does every place the real product shows a picture show a real photograph?
- Does it hold together at 360px?
- Would the person who wrote the request recognise their product?
