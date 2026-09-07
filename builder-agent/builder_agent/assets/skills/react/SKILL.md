# React engineering skill

Use this skill only when React is selected or evidenced by the project.

## Read first
- Inspect `package.json`, lockfile, app entry points, routing approach, state/data layer, styling conventions and existing test setup.
- React is used through the fixed Next.js application contract. Preserve the observed App/Pages Router, server/client component boundaries, styling conventions and state approach; do not migrate the generated app to a standalone React toolchain.

## Build contract
- Model UI from user journeys and domain state, not from a fixed demo layout.
- Keep server/domain decisions out of presentation components. Put side effects behind explicit boundaries.
- Every interactive control must have an accessible name and a real handler; do not render decorative controls for required actions.
- Handle loading, empty, error, success, disabled and retry states where the flow needs them.
- Keep list keys stable, effects bounded and subscriptions/timers cleaned up. Avoid effect loops and derived-state duplication.
- Treat API response shape, auth state and route params as contracts. Validate nullable/optional values at the boundary rather than scattering fallback literals.

## Repair
1. Reproduce the exact failing journey/assertion.
2. Read the owning component plus the direct hook/service/router consumer.
3. Check rendered DOM/accessibility name, state transition and network/request evidence.
4. Fix the smallest coherent owner; do not add test-only controls or hardcoded data.
5. Rerun the affected component/unit check, then the critical E2E flow and runtime smoke evidence.

## Verification
Use the project-selected runner. Test behavior and contracts rather than implementation trivia. For selected visual-risk states, inspect the final rendered pixels at the required viewports after the last edit.
