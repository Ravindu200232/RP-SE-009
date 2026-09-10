---
name: html-prototype
description: Draw the whole application as static HTML before any of it is built — every planned screen, the chosen design tokens, realistic content, no framework and no backend — so the look can be agreed before the expensive part starts.
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

- **Plain HTML and CSS.** No React, no build step, no bundler, no npm install.
  A file opens in a browser and looks right.
- **No backend.** No fetch, no API, no database. The content is written into
  the markup.
- **Every screen the plan named**, one file each, plus the shared stylesheet.
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

## The files

```
.agentforge/prototype/
  index.html        the first screen the plan named
  <screen>.html     one per remaining screen, named after its route
  styles.css        every token and every rule, shared by all of them
```

One stylesheet, linked from every page. A page with its own `<style>` block is
a page that will drift from the others, and a colour change the user asks for
then has to be made five times instead of once.

## The design contract owns the look

The palette, type, radius, spacing, border weight, shadow depth and container
width were chosen and written to `design-system.md` and its token block. Put
those tokens at the top of `styles.css` as custom properties and reference them
everywhere:

```css
:root { --primary: #EA580C; --surface: #FFFFFF; /* … from the contract */ }
.button-primary { background: var(--primary); border-radius: var(--radius); }
```

**Never write a hex value anywhere but the token block.** When the user asks
for a different colour, one property changes and the whole prototype follows.
That is the point of the exercise, and a hard-coded `#EA580C` in a button rule
breaks it.

Every interactive thing gets a class, not an inline style: `.button-primary`,
`.button-secondary`, `.card`, `.field`, `.nav-link`. A request to change "the
buttons" has to have something to change.

## The shell

Every page carries the same header, navigation and footer, written into each
file. The product's name links to `index.html`, the navigation lists the
screens this visitor can reach, and the current page is marked. A prototype
where one screen cannot be reached from another has not shown the user their
application.

## Full size, not a sketch

The most expensive mistake here is a thin page. A thin page gets approved,
because there is nothing in it to disagree with, and then the real build is
made to match it.

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
change everywhere it belongs, in the stylesheet where it is a token or a class,
and re-render only the files that changed.

If they point at one element and ask for a change to that alone, change that
one — a class used once, or a modifier on it, never a new inline style.

## Before you show it

- Does every screen the plan named exist as a file?
- Can you point at where each of the plan's requirements is on a page?
- Is every dimension the design contract settled actually expressed?
- Can you reach every screen from every screen?
- Is every colour a token reference, with no hex outside the token block?
- Is the content this product's content, with no placeholder text left?
- Does any page look thin — a list of two, a table with no statuses, a form
  missing half its fields?
- Does it hold together at 360px?
- Would the person who wrote the request recognise their product?
