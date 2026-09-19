# PayPal

Read this only when PayPal was chosen. SKILL.md still governs that the browser
never sets a price and that a redirect is not a payment; this is PayPal's own
part.

`PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` and `PAYPAL_ENVIRONMENT` are in
`.env.local`. The environment decides the host, and the same code must read it
rather than hard-coding either:

```js
const base = process.env.PAYPAL_ENVIRONMENT === 'live'
  ? 'https://api-m.paypal.com'
  : 'https://api-m.sandbox.paypal.com'
```

Sandbox and live credentials are not interchangeable. Live keys against the
sandbox host — and the reverse — fail as `invalid_client`, which reads like a
wrong secret and is a wrong host.

## Two calls, and the second one is the payment

Create the order on your server, with the amount your server calculated:

```js
POST {base}/v2/checkout/orders
{ "intent": "CAPTURE",
  "purchase_units": [{ "amount": { "currency_code": "USD", "value": "42.00" } }] }
```

Approval in the browser is **not** money. The payment happens when your server
captures it:

```js
POST {base}/v2/checkout/orders/{id}/capture
```

An order that is approved and never captured expires and pays nothing. Treat
the capture's response as the only proof, and read
`purchase_units[0].payments.captures[0].status` — `COMPLETED` is paid;
`PENDING` is not yet and may still fail.

## Amounts are strings, and the decimals matter

`value` is a string — `"42.00"`, not `42`. Sending a number, or `"42.5"` where
the currency takes two decimals, is refused. Currencies without decimals
(JPY among them) must have none at all, and `9.99` in one of those is refused
outright. Format from your own minor-unit integer; never let a float reach it.

## Do not capture the same order twice

Send `PayPal-Request-Id` on the capture with a value derived from the order.
Without it, a retried request can capture twice. A capture on an
already-captured order answers 422 with
`ORDER_ALREADY_CAPTURED` — treat that as success for an order you have already
recorded, not as a failure to retry.

## Webhooks

The webhook is what makes a refund, a dispute or a delayed capture reach your
records. Verify it with `POST /v1/notifications/verify-webhook-signature`
against your webhook id — the headers alone prove nothing, and an unverified
webhook endpoint is an endpoint anyone can post a "payment" to.

## Testing it

Use a sandbox business and personal account. Stub the SDK in unit tests and
assert: the amount comes from the server, an approved-but-uncaptured order
marks nothing paid, `ORDER_ALREADY_CAPTURED` does not double-record, and a
zero-decimal currency is formatted without decimals. If live credentials were
chosen, do not run a journey that moves real money.

- https://developer.paypal.com/docs/api/orders/v2/
- https://developer.paypal.com/api/rest/webhooks/
