# RULE — Route page wrapper (`app/<path>/page.tsx`)

You generate the Next.js App Router page file for one route. Output **only** TypeScript/TSX,
no markdown, no prose.

## Placement & layout context
- The file path is derived from the route (`/dashboard/students` → `app/dashboard/students/page.tsx`,
  `/rooms/[id]` → `app/rooms/[id]/page.tsx`).
- Routes under `/dashboard/**` are ALREADY wrapped by a fixed `app/dashboard/layout.tsx` (sidebar +
  role nav + sign-out). Do NOT re-render a sidebar or nav — render only this page's content.
- Public routes (e.g. `/`, `/rooms`) have only the root layout — they own their full page chrome.
- Route protection is handled by fixed middleware — do NOT implement auth redirects in the page.

## Structure
- The page is a thin wrapper that renders the page BODY component (generated separately) at
  `@/components/pages/<Component>`. Keep the wrapper minimal.
**The route decides the shape. Read it exactly — the body component is generated against the same
rule, so an invented prop name or an unexpected prop is a guaranteed type error.**

- **List / dashboard / static / landing / NEW-form** pages — every route WITHOUT `[id]`: render the
  body client component directly, passing NOTHING.
  ```tsx
  import <Component> from '@/components/pages/<Component>'
  export default function Page() {
    return <<Component> />
  }
  ```
- **Detail and EDIT** pages — every route WITH `[id]` (`.../[id]`, `.../[id]/edit`): fetch the record
  server-side and pass it in as `initialItem`. The prop is named **`initialItem`** — never `item`,
  never the entity's name (`recipe`, `order`). MUST set `export const dynamic = 'force-dynamic'`.
  ```tsx
  import { notFound } from 'next/navigation'
  import dbConnect from '@/lib/mongodb'
  import <Model> from '@/models/<Model>'
  import type { <Entity> } from '@/types'
  import <Component> from '@/components/pages/<Component>'
  export const dynamic = 'force-dynamic'
  export default async function Page({ params }: { params: Promise<{ id: string }> }) {
    const { id } = await params
    await dbConnect()
    const raw = await <Model>.findById(id).lean()
    if (!raw) notFound()
    const initialItem = JSON.parse(JSON.stringify(raw)) as <Entity>
    return <<Component> initialItem={initialItem} />
  }
  ```
  **Cast to the ENTITY type, never `Record<string, unknown>`.** The body declares its own prop type —
  you are shown its real signature above. `Record<string, unknown>` is not assignable to `Entity`
  ("missing the following properties from type 'Entity': _id, …"), while `Entity` is assignable to
  `Record<string, any>`. Casting to the entity therefore works whichever shape the body declares.
- Never put `'use client'` in a page that does server data fetching. Body components are the client parts.
