# RULE — Reusable feature component

Generate exactly one complete production-safe TSX file. Output code only. First line exactly `'use client'`.

## Authoritative contract

- FULL PRODUCT CONTEXT contains the exact product request, design, roles, routes, APIs, entities, fields,
  components, and installed shadcn primitives. The TASK narrows that context to this component.
- Use the exact file path, export name, signature, props, resource, API base, field names, and functions supplied.
- Never add fields, endpoints, routes, roles, props, packages, components, or business behaviour that is absent.
- If required CRUD metadata is absent, render a useful read-only surface instead of guessing.

## Component boundary

- A feature component renders only its declared block: form, list, table, board, filters, summary, or action panel.
- It never owns global navigation, a page shell, authentication, another role's workspace, or unrelated features.
- If props are supplied, they are the entire interface. Declare them exactly and do not fetch the data they carry.
- Without props, fetch only the declared endpoint and implement loading, empty, error, and success states.
- Exactly one named default export. No extra exported helpers or locally redefined entity DTO.

## shadcn/Tailwind contract

- Import primitives only from names in `availableShadcnComponents`, via `@/components/ui/<name>`.
- The installed list is exhaustive: no `typography`, `clipboard-copy`, UI barrel, or font-named
  component exists. Use `font-heading`/`font-sans` and `navigator.clipboard` where applicable.
- Import real Lucide icons from `lucide-react`; import only icons actually rendered.
- Use Tailwind with semantic tokens: `bg-card`, `bg-background`, `text-foreground`,
  `text-muted-foreground`, `bg-primary`, `text-primary-foreground`, `border-border`,
  `bg-muted`, `text-destructive`, and `ring-ring`.
- Never hard-code hex colours or fixed Tailwind families such as `white`, `red-*`, `green-*`,
  `slate-*`, or `gray-*`; the Architect palette already exists as semantic CSS variables. Never import MUI, Emotion, Material icons,
  react-icons, Chakra, Ant, axios, chart libraries, or any package not declared by the project.
- Preserve the Architect's visual signature, typography, radius, spacing, shadow, and motion choices.

## Product-quality states

- Add useful hierarchy and domain copy; never render an unlabelled form/table or generic “No data”.
- Loading uses Skeleton/Progress with context. Empty explains the next action. Error uses Alert plus Retry.
- One main action is visually primary; destructive actions require confirmation and destructive styling.
- Forms have visible labels, controlled values, inline validation, server messages, and disabled submitting state.
- Format dates/currency/status meaningfully. Do not invent business metrics. Domain-accurate reference
  examples are allowed only when the raw input explicitly requests a fixed public guide/comparison inventory.
- Responsive from 375px through desktop, with accessible focus states and at least 44px touch targets.
- Stateful filter/toggle buttons use `type="button"` and `aria-pressed`; icon-only controls have aria-labels.

## TypeScript and React safety

- Import entity records from `@/types` and use only fields in the contract. Persisted IDs are `_id`.
- No `any`, `as any`, suppression comments, index-signature escape hatches, or Mongoose imports in client code.
- Hooks are unconditional and declared before early returns. Effects clean up when needed.
- `useTransition()` returns `[isPending, startTransition]`; never call its second member with a
  boolean. For a manual async submit/loading flag, use `useState(false)` and its boolean setter.
- Use the documented `{ success, data, error }` API envelope and relative fetch URLs only.
- Reference selects load their exact endpoint, submit `_id`, and display the supplied label field.
- Every import resolves, every identifier is declared, and every JSX tag/brace is closed.

## Final gate

Silently confirm the exact signature, complete functionality, semantic shadcn styling, responsive/accessibility
states, and absence of invented fields/routes/imports before returning the single complete TSX file.
