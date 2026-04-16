# Food Ordering Application

Packaged by Agent 4 as a deployment-ready microservice project.

## Architecture

- Declared architecture: `microservices`
- Scanned architecture: `microservices`
- Final architecture: `microservices`
- Confidence: `0.95`
- Deployment profile: `docker-compose + github-actions + aws-ecs-fargate`

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
- Workflows use OIDC with `aws-actions/configure-aws-credentials@v4`.
- `GITHUB_TOKEN` is intended only for in-repo workflow tasks.

## AWS ECS

- Backend task definitions are generated under `aws/`.
- Replace placeholder AWS account values before deployment.

## Generated Evidence

- `analysis.json`
- `strategy.json`
- `deployment_evidence.json`
