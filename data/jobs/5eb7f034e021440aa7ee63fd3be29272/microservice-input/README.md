# Microservice_input

Packaged by Agent 4 as a deployment-ready microservice project.

## Architecture

- Declared architecture: `not provided`
- Scanned architecture: `microservices`
- Final architecture: `microservices`
- Confidence: `0.88`
- Deployment profile: `docker-compose + github-actions`

## Services

- `restaurant-service` -> `server/Restaurant-service` on port `3002`
- `deliver-service` -> `server/deliver-service` on port `3005`
- `notification-service` -> `server/notification-server` on port `3006`
- `order-service` -> `server/order-service` on port `3003`
- `payment-service` -> `server/payment-service` on port `3004`
- `user-service` -> `server/user-service` on port `3000`
- `frontend` -> `client` on port `5173`

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
