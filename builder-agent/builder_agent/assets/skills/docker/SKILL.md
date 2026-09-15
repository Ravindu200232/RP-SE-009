---
name: docker
description: Generate and audit production-oriented Dockerfiles and Docker Compose for AgentX applications while keeping MERN local development and E2E independent of Docker.
---

# Docker and Compose

Generate deployment artifacts for MERN microservices, or for Next.js when requested.

Never use Docker on the local PC, even if installed: no Docker CLI probes, Docker Desktop, daemon, containers, Docker Compose or local Docker builds. Dockerfiles and Compose files are deployment artifacts; generate and inspect them statically. Image builds and pushes run only on a configured cloud CI runner. Local development, unit tests, page/console checks and runtime verification use plain Node/package manager tools.

## Dockerfile rules
- Use multi-stage builds where they materially reduce runtime size or dev dependencies.
- Copy lockfiles before source to preserve dependency layer caching.
- Use the repository's package manager and reproducible install command.
- Run as a non-root runtime user when practical.
- Do not bake secrets into image layers or build args that become image history.
- Add only files needed by each independently deployable unit; use `.dockerignore`.
- Define production startup and health behavior explicitly.

## Compose rules
- Model gateway, domain services, and optional local Mongo only when the product contract asks for it.
- Use service DNS names inside the Compose network rather than localhost.
- Add healthchecks and dependency conditions where startup truly needs service readiness.
- Keep environment names aligned with the Docker-free runtime contract.
- Expose the public gateway port; avoid publishing every internal service port by default.

Always validate these files statically and verify the app with the Docker-free runner on the local PC.

Official reference:
- https://docs.docker.com/compose/how-tos/startup-order/
