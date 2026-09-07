---
name: frontend-design
description: Design and build visually excellent React pages and the components they are made of — component inventory, content-heavy layouts, vertical rhythm, typographic hierarchy, restraint, and the craft that separates competent from world class — applied while writing the code, not as a later repaint.
---

# Frontend design

Use this **while writing pages and components**, not as a repaint afterwards.
Layout decisions made in the markup are the design; a styling pass bolted on at
the end can only tidy what the structure already got wrong.

It never replaces working architecture, and it never invents colour, type or
spacing values: those come from the approved token sheet. If there is a
`design-system` skill in this project, read it first — it wins over every
preference here.

## A page is a sequence of sections

A large page is not one canvas. It is 4–8 sections, each with exactly one job,
in an order that answers the visitor's questions as they arise.

- Give every section a single purpose you can name in three words. Two purposes
  means two sections.
- Vary the shape between neighbours. Full-bleed, then contained. Two columns,
  then one. A wall of identical cards is the clearest signal that nobody made a
  decision.
- Let one thing dominate per screenful. If three elements compete for first
  read, the reader picks none.
- End sections at a natural stop, not wherever the content ran out.

## Build it as components, not as one long file

A page written as one file is a page nobody can change. Decide the component
inventory before writing markup, and derive it from the page rather than from a
library's list of parts.

- **Extract when a thing repeats, owns state, or is long enough to hide the page
  structure.** A section you can read in one screen and that appears once can
  stay inline; a card rendered in a loop cannot.
- **A page component composes; it does not style.** Its job is order, data and
  layout. Anything that draws a thing belongs in its own component, so the page
  file reads as the outline of the page.
- **Keep state where it is used.** Filters live with the list they filter; a
  modal owns whether it is open. State lifted higher than its readers turns
  every unrelated change into a re-render and every component into a prop relay.
- **Props describe intent, not appearance.** `variant="danger"` and
  `size="compact"` survive a redesign; `color="#b3261e"` and `padding={12}` do
  not, and they leak the token sheet into call sites.
- **One component, one decision.** A component that takes a boolean to become a
  different component is two components. Splitting them removes the branch from
  both.
- **Name for the domain, not the shape.** `BookingSummary` still makes sense
  after it stops being a card; `WhiteBox` never did.
- Build the shared primitives the page actually needs — button, field, card,
  empty state, skeleton — once, from the tokens, and use them everywhere. Two
  slightly different buttons is the first crack in a design system.
- A component that renders a list also renders that list's empty, loading and
  error states. Leaving them to the caller is how one screen gets them and the
  others do not.

## Pages that carry a lot of content

A long page is not a short page scrolled further. Past roughly two screenfuls
the reader stops reading and starts scanning, and the design has to serve
scanning.

- **Give a long page its own navigation.** A sticky in-page index, a sidebar of
  sections, or a breadcrumb with the current section — something that answers
  "where am I and how much is left". Anchor targets need scroll padding so a
  sticky header does not cover the heading it jumped to.
- **Headings are the interface.** At length, the heading hierarchy is what the
  reader uses instead of reading. Every section gets a real heading that says
  what is in it; "Overview" and "Details" say nothing.
- **Chunk to a scannable unit.** Three to six paragraphs, or eight to twelve
  rows, then a heading, a divider, a table or an image. Unbroken text past a
  screenful is skipped whole.
- **Front-load each chunk.** The first sentence of a section and the first
  column of a row carry the meaning; the reader may never reach the rest.
- **Progressive disclosure for depth, not for volume.** Collapse the detail a
  minority needs — specifications, history, raw payloads. Do not collapse the
  main content to make a page look shorter; a page of closed accordions is a
  page with no content.
- **Long lists need a spine.** Sticky table headers, a pinned first column,
  zebra or hairline row separation, and a visible count. Decide pagination
  versus infinite scroll from whether the reader needs to reach a known place
  again — infinite scroll destroys "page 4" and breaks the back button.
- **Filters state their result.** Show the active filters as removable chips and
  the resulting count next to them. A filtered empty state says which filter
  emptied it and offers to clear it.
- **Render long lists lazily once they are genuinely long.** Thousands of rows
  need windowing; forty do not, and adding it early only costs correctness.
- **Density is a decision, not an accident.** A dashboard and an article want
  different densities. Pick one per surface and hold it; mixed density inside
  one page reads as unfinished.
- Keep the primary action reachable while scrolling — a sticky footer bar on
  narrow screens, a sticky aside on wide ones — so a decision made at the bottom
  does not require a trip back to the top.

## Vertical rhythm is what makes it look designed

The single biggest difference between a generated page and a designed one is
spacing discipline, not colour.

- **Section padding is much larger than component padding** — roughly 4–6× on
  desktop. Cramped sections read as a template; generous ones read as intent.
- Space belongs *between* groups, not sprinkled evenly. Related things sit
  close; unrelated things get real distance. Proximity is the cheapest grouping
  device and the most ignored.
- Use only the spacing ramp from the tokens. A one-off `margin-top: 37px` is how
  a page stops lining up.
- Halve section spacing on narrow screens; keep component spacing roughly
  constant. Mobile needs less air between blocks, not less air inside them.

## Typography carries the hierarchy

- Three levels of text on a screen is usually right: what this is, what it says,
  what to do. A fourth is normally a section that should have been split.
- **Contrast weight and colour before size.** A semibold 16px label against 16px
  muted body reads as hierarchy without another type size.
- Long-form measure is 60–80 characters. Full-width paragraphs on a wide screen
  are unreadable no matter how good the font is.
- Line height falls as size rises: 1.5–1.65 for body, 1.15–1.25 for headings.
- Numbers in tables and prices are tabular and right-aligned; ragged decimals
  look broken even when correct.
- One accent voice. A heading that is bold *and* coloured *and* larger *and*
  uppercase is shouting four times.

## The hero earns the rest of the page

Choose the pattern from the product, not from habit:

- **Centred** — one clear proposition, one action. Best when the offer is simple
  and the audience is broad.
- **Split** — copy against a product shot or live UI. Best when seeing the thing
  is the argument.
- **Editorial** — a strong headline with supporting type and generous space.
  Best for content, brand and considered purchases.

Whichever it is: one headline that says what this actually does, one primary
action, and at most one secondary. A hero with three equal buttons has no
primary action.

## Restraint

Most generated interfaces fail by addition. Before adding an effect, remove
something instead.

- **One primary colour on a screen.** The accent is for emphasis, badges and
  charts — never a second CTA.
- Shadows come from the elevation scale, and only where something genuinely
  floats. Shadowed cards inside a shadowed card inside a shadowed section is
  noise.
- Gradients, glass and blur are seasoning. If removing an effect does not make
  the page worse, it was not doing anything.
- Borders or shadows, rarely both, for the same separation.
- Icons support labels; they rarely replace them. An icon-only control needs a
  name for a screen reader anyway, so write the label.

### The generated-page tells to avoid

Three equal feature cards each with a circular icon. A purple-to-blue gradient
hero. Every surface a rounded card with the same shadow. Emoji as iconography.
Lorem-flavoured filler like "Seamlessly empower your workflow". Centred text in
long paragraphs. A dashboard that is six identical stat tiles and nothing else.

## Build every state, not just the full one

An empty state is a designed screen, not a grey sentence. Say what belongs here,
why it is empty, and give the action that fills it.

- **Loading** — skeletons matching the real layout, so nothing jumps when data
  lands. Never a bare centred spinner on a page that will have structure.
- **Empty** — different copy for "nothing yet" and "nothing matched your
  filters". The second offers a way to clear them.
- **Error** — what failed, whether it is retryable, and the retry control.
- **Partial** — one section failing does not blank the page.

## Responsive is a reflow, not a shrink

- Design the narrow layout as its own composition. Decide what leads on a phone;
  it is often not what leads on a desktop.
- Tables become stacked records or a horizontally scrolling region with a pinned
  first column — never a squeezed grid.
- Touch targets are at least 44×44, including icon-only controls.
- Nothing scrolls the page horizontally at 390px. Long words, code and URLs need
  explicit wrapping.

## Interaction states are part of the component

Write them as you write the component, not afterwards:
`:hover`, `:focus-visible`, `:active`, `:disabled`, and the loading state of any
control that triggers work. A focus ring must be visible on every background it
can land on. Motion is for orientation and feedback only, and always honours
`prefers-reduced-motion`.

## What separates good from world class

Everything above gets a page to competent. The distance from competent to
memorable is a small number of decisions that generated interfaces almost never
make.

- **A type scale, not a set of sizes.** Pick a ratio and generate the ramp from
  the body size. Sizes chosen one at a time never sit together, and the gap
  between a heading and its body is what reads as confidence.
- **One idea per screen, executed further than feels necessary.** A hero with
  one sentence set very large beats a hero with three balanced blocks. Most
  designs fail by being three-quarters committed to two ideas.
- **Optical alignment beats measured alignment.** Round shapes, punctuation and
  icons need to overhang slightly to look aligned. If it measures right and
  looks wrong, the eye is right.
- **Give the content real air at the edges.** A wide screen wants a container
  and margin, not edge-to-edge text. The empty space is doing the work.
- **Treat images as content, not decoration.** Fixed aspect ratios so nothing
  reflows on load, a considered crop, and `object-fit` rather than a stretched
  box. One strong photograph beats four stock ones.
- **Alignment is a grid, and the grid does not bend.** Everything that can share
  an edge, shares it — across sections, not only inside one. A single column
  that starts eight pixels off is visible even when nobody can name it.
- **Write the interface copy.** Button verbs, empty states, error sentences and
  headings are design surface. "Save changes" and "No bookings yet — your first
  one will appear here" carry more polish than any shadow.
- **Motion under 200ms, and only where something moved.** Entrances, state
  changes and the thing the user just did. Anything longer is felt as lag; a
  page that animates on scroll for its own sake reads as a template.
- **Dark mode is a second palette, not an inversion.** Surfaces lighten with
  elevation instead of casting shadows, and pure black with pure white is
  harsher than any real product ships.
- **Details at the end of the flow.** Focus order, the caret in a form, what the
  page looks like at 1600px, what a two-line product name does to a card row —
  these are what people notice without knowing why.

## The craft pass, once it works

With real content in place, walk the page and look for: things that nearly line
up, cards of uneven height in one row, inconsistent radii, text that wraps to a
single orphan word, spacing that differs between similar sections, a sticky
header covering an anchor target, and hover states that shift layout.

Then look at it at 390px and 1280px and ask the only question that matters:
**can a stranger tell what this page is for in three seconds?**
