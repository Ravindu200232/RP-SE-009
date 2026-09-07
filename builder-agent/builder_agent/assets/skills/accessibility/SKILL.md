---
name: accessibility
description: Build and audit accessible web interfaces using semantic HTML, keyboard operation, visible focus, correct names/labels, usable dialogs/forms, contrast, and reduced-motion support.
compatibility: AgentX React/Next.js UI quality and E2E verification.
---

# Accessibility

Accessibility is part of functional correctness.

- Prefer native semantic controls and landmarks before adding ARIA.
- Every interactive element needs an accessible name that matches its purpose.
- All functionality must be keyboard reachable with logical focus order and visible focus state.
- Dialogs/menus/popovers must manage focus correctly and expose their state/relationship.
- Associate form labels, descriptions, validation messages, and required state programmatically.
- Do not communicate status or error only by color; use text/icon semantics too.
- Maintain readable contrast and scalable text; avoid clipping at zoom/narrow viewports.
- Respect `prefers-reduced-motion` for nonessential animation.
- Images that convey information need meaningful alternative text; decorative images should not add noise.
- Dynamic updates that matter to task completion should be announced appropriately without flooding assistive tech.

Test critical journeys with role/name locators; locator failures often expose real accessibility problems. Do not add fake labels only to satisfy tests—make the UI genuinely understandable.
