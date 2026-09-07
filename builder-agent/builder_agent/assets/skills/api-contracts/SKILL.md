---
name: api-contracts
description: Define and preserve explicit HTTP/API contracts between frontend, gateway, services, and persistence with validation, consistent errors, idempotency where needed, and contract-focused tests.
compatibility: AgentX Next.js route handlers and MERN gateway/service APIs.
---

# API contracts

Treat every externally consumed route as a versioned behavior contract even when no formal OpenAPI file exists.

- Define method + path, auth requirement, path/query/body schema, success status/body, expected errors, and side effects.
- Validate untrusted input at the first trusted server boundary.
- Keep response DTOs intentional; do not serialize raw database documents by accident.
- **Pin every response field name in the contract, not just the route.** Packages built separately agree on `GET /api/catalog/products` and still disagree on whether an item carries `price`. Measured: a model that defined `price`, a client that rendered `price.toFixed()`, a response that omitted it, and a blank page — with both packages' own tests passing.
- Test the serializer against the contract's field list, so a projection or `select()` that drops a field fails at the producer instead of surfacing as `undefined` in a consumer.
- Use consistent error shapes with machine-readable code plus safe human message.
- Preserve semantic HTTP status codes; distinguish validation, auth, forbidden, not found, conflict, rate limit, upstream unavailable, and internal failure.
- Make retries safe: use idempotency keys or naturally idempotent operations where duplicate submission is a product risk.
- For microservices, maintain gateway-to-service contract tests and prevent clients from depending on internal service URLs.
- When changing a contract, update producer, all consumers, fixtures/tests, and migration/backward-compatibility plan together.

Verification should include valid request, each meaningful invalid boundary, auth/ownership, duplicate/retry behavior where relevant, and serialization safety.
