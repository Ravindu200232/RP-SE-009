# Builder, Bug Fixer and Image Generator

Writes the application. The architect plans the files, the builder generates them, the analyzer and bug fixer repair what the build reports, and the image generator produces the assets the pages ask for.

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

- `agents/`

Because the shared runtime — `server.py`, the studio shell, the launchers —
lives on `main`, this branch is for reading and reviewing this component in
isolation, not for running it. Run the application from `main`.

Other components: srs-agent, qa-agent, deployment-agent.

**Author:** Ravindu B. Subasinghe, Sri Lanka Institute of Information Technology
