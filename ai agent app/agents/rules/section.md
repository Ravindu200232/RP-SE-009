# RULE — Page body (`components/pages/<Component>.tsx`)

Generate exactly one complete Next.js client TSX file. Output code only. First line exactly `'use client'`.

## Source of truth

- The FULL PRODUCT CONTEXT is authoritative for the user request, routes, roles, pages, resources,
  fields, API methods, design tokens, sections, functions, and available shadcn primitives.
- Implement the current TASK's route, page job, primary action, declared functions, layout, archetype,
  and visual signature. Never replace it with a generic dashboard, KPI row, or CRUD table.
- Use only declared routes, endpoints, fields, enum values, roles, and installed components.
- Records use `_id`. Import entity DTOs from `@/types`; never import Mongoose models into client code.
- Never invent metrics, testimonials, customer logos, ratings, awards, endpoints, or placeholder content.

## Design bar

- The page must feel production-ready and specific to this product at 375px and 1440px.
- Preserve the Architect's preset, mode, typography, navigation, spacing, motion, palette, page layout,
  and visual signature. Use the semantic theme instead of fixed colours.
- Establish a clear title, useful subtitle, visual hierarchy, 8px rhythm, purposeful depth, and one
  obvious primary action. Render every declared section with real domain copy.
- Give interactive surfaces hover, focus-visible, active, disabled, and useful transition states.
- Loading uses Skeleton/Progress with context. Empty state uses an icon, useful explanation, and the
  appropriate next action. Errors use Alert plus Retry. Success provides visible feedback.
- Forms use visible labels, inline validation, server errors, accessible descriptions, and 44px touch targets.
- Tables/lists format dates and currency, expose useful filters/search when requested, and remain usable on mobile.
- Motion is purposeful, honours `prefers-reduced-motion`, and follows the Architect's motion level.
- No lorem ipsum, TODO, ellipses standing for code, fake statistics, or incomplete JSX.

## UI stack — shadcn + Tailwind only

- Import UI primitives only from the exact `availableShadcnComponents` list in PRODUCT CONTEXT, using
  `@/components/ui/<name>`. Import only exports that really exist in that primitive.
- The exact installed list is exhaustive. Never invent `typography`, `clipboard-copy`, a barrel
  `@/components/ui`, or a font-named component. Apply fonts with `font-heading`/`font-sans`; implement
  copy actions with `navigator.clipboard`, Button, and a Lucide icon.
- Use Lucide icons from `lucide-react`. Import real PascalCase icon names and render every imported icon.
- Style layout and composition with Tailwind. Prefer semantic classes:
  `bg-background`, `bg-card`, `text-foreground`, `text-muted-foreground`, `bg-primary`,
  `text-primary-foreground`, `border-border`, `bg-muted`, and `text-destructive`.
- Never use fixed Tailwind colour families (`white`, `black`, `slate-*`, `gray-*`, `red-*`,
  `green-*`, etc.), inline hex colours, MUI, Emotion,
  `sx`, Material icons, react-icons, Chakra, Ant, or an unlisted package.
- Use responsive Tailwind prefixes (`sm:`, `md:`, `lg:`), CSS grid/flex, `max-w-*`, and semantic HTML.
- Use `cn` from `@/lib/utils` only when conditional class composition is needed.

## Boundary and file shape

- Render only this page body. Global role navigation is owned by the route layout. Do not add a second
  sidebar/topbar unless this TASK is the public `/` page and the Architect explicitly puts navigation there.
- Exactly one named default export whose name matches the requested component.
- Keep all hooks unconditional and before early returns. Include every import and close every tag/brace.
- Give object-shaped local state an explicit interface/type. For nullable results use
  `useState<Result | null>(null)`, never an untyped `useState(null)` that narrows to `never`.
- Do not use `any`, suppression comments, split components, dynamically created files, or external packages.
- Existing composed child components must be imported exactly as supplied and wired to their real signatures.
- When this is the public `/` page and Architect navigation is `topnav`, render one accessible semantic
  `<nav aria-label="Primary">` with valid route or in-page section links.

## Data and actions

- Use relative `fetch('/api/...')` and the documented `{ success, data, error }` envelope.
- Check `res.ok` and `success` before using `data`; display the server's `error` message.
- Fetch only endpoints in the contract. Mutations use the documented POST/PUT/DELETE method and refresh state.
- Reference fields use the supplied reference endpoint, `_id` as value, and the exact label field.
- Detail/edit bodies use the exact `initialItem` prop declared by the TASK and do not re-fetch it.
- Links may target only VALID ROUTES. Per-record API actions are not page links.
- A public no-account guide that explicitly requests a fixed number of reference examples must display
  exactly that many domain-accurate examples on first load, even when its optional API collection is empty.

## Final gate

Before returning, silently verify: complete TSX; exact export; no invented imports/routes/fields; every declared
function works; all states are designed; Tailwind is semantic and responsive; no MUI or fixed theme colours.
