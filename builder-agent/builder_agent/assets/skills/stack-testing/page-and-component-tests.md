---
name: "A Unit Test For Every Page And Component"
description: "Every page and every component you generate gets its own unit test file - render, the role or state branches, and the empty case. Apply while writing client pages and components, not after."
allowed-tools: Read, Write, Edit, Bash
version: 1.0.0
compatibility: Claude Opus 4.6, Sonnet 4.6, Claude Code v2.1.x
updated: 2026-09-16
---

# A unit test for every page and every component

Every page and every component you generate gets a test file. Not the ones that
look risky, not the ones with logic in them — **all of them**.

Measured on a real build: fifteen generated pages produced three test files, and
the run reported "37 passing, 0 failing, 3 files". That number is true and tells
you nothing: fourteen of the fifteen pages had never been rendered by a test
even once, so any of them could throw on mount and the suite would stay green.

## The rule

```
client/src/pages/ListPage.jsx        ->  client/test/pages/ListPage.test.jsx
client/src/components/StatusBadge.jsx ->  client/test/components/StatusBadge.test.jsx
```

One file beside each. Write it in the same turn you write the page — batching
the page and its test together costs one turn, and coming back later costs a
rediscovery of what the page was supposed to do.

## What each test must cover

**1. It renders.** Mount it inside the providers it really needs (router, auth,
toast) and assert one thing a user would recognise — the heading, not a class
name. This single assertion is what catches a bad import, a missing provider, a
null dereference on mount, and a hook used incorrectly.

**2. Each branch the page chooses between.** Most generated pages branch on
role, on loading, and on whether the request returned anything. Render it once
per branch:

- the role that is allowed sees the action
- a role that is not allowed does not see it — and this is a real assertion,
  `expect(screen.queryByRole('button', { name: 'Delete item' })).toBeNull()`
- while loading, the loading state shows
- when the list is empty, the empty message shows rather than a blank panel

**3. The empty and error case.** An empty list and a failed fetch are the two
states a demo never shows and a marker always tries.

```jsx
// client/test/pages/DashboardPage.test.jsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AuthProvider } from '../../src/auth.jsx'
import { ToastProvider } from '../../src/toast.jsx'
import { DashboardPage } from '../../src/pages/DashboardPage.jsx'

const renderAs = (user, props = {}) => render(
  <AuthProvider value={{ user }}>
    <ToastProvider>
      <MemoryRouter><DashboardPage {...props} /></MemoryRouter>
    </ToastProvider>
  </AuthProvider>,
)

describe('DashboardPage', () => {
  it('renders the signed-in greeting', () => {
    renderAs({ role: 'member', name: 'Ana' })
    expect(screen.getByRole('heading', { name: /Ana/ })).toBeInTheDocument()
  })

  it('shows the empty message when there is nothing to list', () => {
    renderAs({ role: 'member' }, { items: [] })
    expect(screen.getByText(/nothing here yet/i)).toBeInTheDocument()
  })

  it('does not offer an action the role is not allowed', () => {
    renderAs({ role: 'member' }, { items: [{ id: '1', canDelete: false }] })
    expect(screen.queryByRole('link', { name: /delete/i })).toBeNull()
  })
})
```

## Assert what a user sees

Query by role, label and text — `getByRole('button', { name: 'Save changes' })`
— not by class or by test id where a real name exists. A test written against
class names passes after a redesign that broke the page, and fails after a
rename that broke nothing.

Where a control genuinely has no accessible name, fix the control by giving it
one rather than reaching for a test id. The E2E journeys need those names too.

## What this is not

This does not replace the modules that decide things — validation, permissions,
pricing, dates, route handlers — which need their own tests for accepted,
rejected and boundary input. This is the floor beneath them: no page or
component ships without having been rendered by a test at least once.
