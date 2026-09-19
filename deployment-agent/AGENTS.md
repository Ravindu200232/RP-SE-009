# Deployment agent rules

- Never install, start, probe, build with, or otherwise use Docker on the local PC. Do not start Docker Desktop, a local Docker daemon, local containers or Docker Compose.
- Validate locally with the application's Node/package manager tools. Dockerfiles may be generated as source for AWS ECS; Docker builds and pushes run only on the GitHub Actions cloud runner.
- Repair only the selected project's isolated deployment worktree. Read the project's handoff documents as context; never edit parent SRS/prototype state, other projects, credentials or `.git` internals.
- Collect all available failure diagnostics before a bundled repair. Respect the bounded tool/retry budget and stop when identical failures repeat without progress.
- Preserve recorded repository and cloud application identities during repair/redeploy. Never delete shared accounts, resource groups, networks or service plans.
- Keep provider credentials in owner-scoped encrypted settings and provider/GitHub secret storage. Never put secret values in prompts, source files, event streams or commits.
