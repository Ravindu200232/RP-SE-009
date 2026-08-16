# QA Agent

Tests what was built. Writes Vitest unit tests and Playwright end-to-end flows against the generated application, runs them, and reports what failed rather than only that something did.

---

This branch carries **only this component**. It is one of four cut from `main`,
which holds the whole application:

| branch | component |
|---|---|
| `srs-agent` | SRS Agent |
| `builder-agent` | Builder, Bug Fixer and Image Generator |
| `qa-agent` | QA Agent |
| `deployment-agent` | Deployment Agent |

Paths on this branch:

- `qa_agent/`
- `studio/components/testing/`

Because the shared runtime — `server.py`, the studio shell, the launchers —
lives on `main`, this branch is for reading and reviewing this component in
isolation, not for running it. Run the application from `main`.

Other components: srs-agent, builder-agent, deployment-agent.

**Author:** Ravindu B. Subasinghe, Sri Lanka Institute of Information Technology
