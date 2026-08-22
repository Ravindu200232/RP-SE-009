# Deployment Agent

Puts the application somewhere. Generates the CloudFormation, the GitHub Actions workflows and the release script, deploys to Vercel, AWS EC2 or AWS ECS Fargate, and monitors the result.

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

- `deployment-agent/`
- `studio/components/deploy/`

Because the shared runtime — `server.py`, the studio shell, the launchers —
lives on `main`, this branch is for reading and reviewing this component in
isolation, not for running it. Run the application from `main`.

Other components: srs-agent, builder-agent, qa-agent.

**Author:** Malith Bandara, Sri Lanka Institute of Information Technology
