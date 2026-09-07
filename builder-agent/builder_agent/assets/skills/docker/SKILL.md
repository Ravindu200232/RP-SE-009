---
name: docker
description: Generate and audit production-oriented Dockerfiles and Docker Compose for AgentX applications while keeping MERN local development and E2E independent of Docker.
compatibility: AgentX deployment artifacts; required for MERN microservices output, optional for Next.js when requested.
---

# Docker and Compose

Docker is a deployment artifact in AgentX MERN mode. Never require Docker to run local development, unit tests, runtime smoke, or browser E2E.

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

If Docker is unavailable, validate files statically and verify the same app contract with the Docker-free runner.

Official reference:
- https://docs.docker.com/compose/how-tos/startup-order/
