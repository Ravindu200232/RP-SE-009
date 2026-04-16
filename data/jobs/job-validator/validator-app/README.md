# Validator App

Packaged by Agent 4 as a deployment-ready microservice project.

## Architecture

- Declared architecture: `microservices`
- Scanned architecture: `microservices`
- Final architecture: `microservices`
- Confidence: `0.95`
- Deployment profile: `docker-compose + github-actions`

## Services

- `order-service` -> `server/order-service` on port `3001`
- `user-service` -> `server/user-service` on port `3000`

## Quick Start

```bash
cp .env.example .env
./setup.sh
```

## CI/CD

- GitHub Actions workflows are generated under `.github/workflows/`.
- Workflows run tests and Docker build checks for each service.
- `GITHUB_TOKEN` is intended only for in-repo workflow tasks.
- Cloud deployment targets are intentionally excluded for now.

## Generated Evidence

- `analysis.json`
- `strategy.json`
- `deployment_evidence.json`
