# Razorpay

Read this only when Razorpay was chosen. SKILL.md still governs that the
browser never sets a price and that a redirect is not a payment; this is
Razorpay's own part.

`RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` and `RAZORPAY_WEBHOOK_SECRET` are in
`.env.local`. The key id starts with `rzp_test_` or `rzp_live_` and belongs in
the page; the secret never leaves the server.

## Amounts are in paise

`amount: 500` is five rupees, not five hundred. Everything is the minor unit,
as an integer. This is the bug that ships.

```js
const order = await razorpay.orders.create({
  amount: Math.round(rupees * 100),   // paise, integer
  currency: 'INR',
  receipt: booking.reference,
})
```

## The handler's answer proves nothing until it is signed

The checkout's success handler hands the browser
`razorpay_order_id`, `razorpay_payment_id` and `razorpay_signature`. The first
two are just strings anybody can post to your server. The signature is the
proof, and it is verified on the server with your secret:

```js
const expected = crypto
  .createHmac('sha256', process.env.RAZORPAY_KEY_SECRET)
  .update(`${razorpay_order_id}|${razorpay_payment_id}`)
  .digest('hex')

if (!crypto.timingSafeEqual(Buffer.from(expected),
                            Buffer.from(razorpay_signature))) throw new Error('unverified')
```

The body is `order_id|payment_id`, joined by a pipe, in that order. Compare
with a timing-safe comparison, not `===`.

Marking an order paid because the handler fired is the whole vulnerability:
the handler runs in the browser.

## The webhook is a different secret and a different body

`RAZORPAY_WEBHOOK_SECRET` is set when you create the webhook and is not the key
secret. The signature is over the **raw request body**, so the route must read
the body before any JSON parser has touched it — a re-serialised body produces
a different digest and every webhook fails verification.

Webhooks arrive more than once. Key your record on `payment_id` so a replay
finds the payment already recorded.

## Testing it

Stub the SDK. Assert that the amount reaching Razorpay is paise as an integer,
that a wrong signature is refused, that the signed body is
`order_id|payment_id`, and that the same webhook twice records one payment. If
live keys were chosen, do not run a journey that moves real money.

- https://razorpay.com/docs/payments/server-integration/nodejs/
- https://razorpay.com/docs/webhooks/validate-test/
