# Stripe

Read this only when Stripe was the gateway chosen. The rules in SKILL.md still
apply; this is the part that is Stripe's own.

`STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY` and `STRIPE_WEBHOOK_SECRET` are in
`.env.local`. Read them from `process.env`. A `sk_test_`/`pk_test_` pair is test
mode and a `sk_live_`/`pk_live_` pair is real money; the code is the same either
way, so never branch on which one is present.

## Checkout

Hosted Checkout is the right default: Stripe hosts the card form, so no card
detail ever touches your origin and PCI scope stays with them. Build the session
on the server from prices you looked up yourself.

```js
import Stripe from 'stripe'

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY)

// The client sends ids. The server decides what they cost.
const items = await loadCartItems(cartId)
const session = await stripe.checkout.sessions.create({
  mode: 'payment',
  line_items: items.map(item => ({
    quantity: item.quantity,
    price_data: {
      currency: 'usd',
      unit_amount: item.priceInCents,        // integer, from your database
      product_data: { name: item.name },
    },
  })),
  success_url: `${origin}/orders/${order.id}?checkout=done`,
  cancel_url: `${origin}/cart`,
  client_reference_id: order.id,             // how the webhook finds the order
  metadata: { orderId: order.id },
})
```

Redirect the browser to `session.url`. `client_reference_id` and `metadata` are
how the notification later identifies which order was paid — without one of
them you are matching on amount and time, which is guesswork.

## The webhook is the only thing that marks an order paid

`success_url` is the customer's browser. It can be opened directly, bookmarked,
or never reached because they closed the tab after paying. Show "we are
confirming your payment" there, and let the webhook do the work.

```js
export async function POST(request) {
  const signature = request.headers.get('stripe-signature')
  const raw = await request.text()            // the raw body, not parsed JSON

  let event
  try {
    event = stripe.webhooks.constructEvent(
      raw, signature, process.env.STRIPE_WEBHOOK_SECRET)
  } catch {
    return new Response('bad signature', { status: 400 })
  }

  if (event.type === 'checkout.session.completed') {
    const session = event.data.object
    await markPaidOnce(session.client_reference_id, {
      provider: 'stripe',
      paymentId: session.payment_intent,
      amount: session.amount_total,
      currency: session.currency,
      eventId: event.id,
    })
  }
  return new Response('ok')
}
```

Two things this depends on:

**The raw body.** `constructEvent` recomputes the signature over the exact bytes
Stripe sent. A framework that parses JSON first has already changed them, and
verification then fails on every legitimate request. In Next.js App Router
`request.text()` gives you the raw body; in Express this one route needs
`express.raw({ type: 'application/json' })` rather than `express.json()`.

**Idempotency.** Stripe retries until it gets a 2xx, and it can deliver the same
event more than once. Store `event.id` and make `markPaidOnce` a no-op the
second time it sees one.

Return 200 quickly. Long work inside the handler causes Stripe to time out and
retry, which is how one payment becomes three emails.

## Testing it

`4242 4242 4242 4242`, any future expiry, any CVC — succeeds.
`4000 0000 0000 9995` — declined, which is the case that gets left untested.

There is no browser flow for the webhook, so deliver the event yourself in the
test: build the payload your handler expects, sign it with the test secret using
`stripe.webhooks.generateTestHeaderString`, and post it. Assert the order is
paid, then post the identical event again and assert nothing changed.

- https://docs.stripe.com/checkout/quickstart
- https://docs.stripe.com/webhooks/signature
- https://docs.stripe.com/testing
