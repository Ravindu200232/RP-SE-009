# PayHere

Read this only when PayHere was the gateway chosen. The rules in SKILL.md still
apply; this is the part that is PayHere's own.

`PAYHERE_MERCHANT_ID`, `PAYHERE_MERCHANT_SECRET` and `PAYHERE_SANDBOX` are in
`.env.local`. The endpoint follows the sandbox flag and nothing else:

```js
const base = process.env.PAYHERE_SANDBOX === 'true'
  ? 'https://sandbox.payhere.lk/pay/checkout'
  : 'https://www.payhere.lk/pay/checkout'
```

Amounts are LKR with exactly two decimals — `1500.00`, not `1500` and not
`1,500.00`. Format them once, on the server, and use the same string in the
hash and in the form.

## Starting a payment

PayHere takes a form post, and the form carries a hash that proves the amount
came from you and not from whoever has the page open. Build it on the server:

```js
import crypto from 'node:crypto'

const md5 = (value) => crypto.createHash('md5').update(value).digest('hex').toUpperCase()

const amount = order.totalLkr.toFixed(2)
const hash = md5(
  process.env.PAYHERE_MERCHANT_ID +
  order.id +
  amount +
  'LKR' +
  md5(process.env.PAYHERE_MERCHANT_SECRET)
)
```

The inner hash of the secret is not optional and not decoration: it is what the
formula is defined as, and getting it wrong produces a checkout that opens and
then rejects the payment with an unhelpful message.

Send `merchant_id`, `order_id`, `items`, `currency`, `amount`, `hash`,
`return_url`, `cancel_url`, `notify_url`, and the customer's name, email,
phone, address, city and country. `notify_url` must be an address PayHere can
reach from the internet — `localhost` never receives a notification, so while
building either tunnel it or drive the handler directly in tests.

## The notification is the only thing that marks an order paid

`return_url` is the customer's browser and proves nothing. PayHere posts to
`notify_url` as form-encoded fields, and every one of them is unverified until
the signature matches:

```js
const local = md5(
  fields.merchant_id +
  fields.order_id +
  fields.payhere_amount +
  fields.payhere_currency +
  fields.status_code +
  md5(process.env.PAYHERE_MERCHANT_SECRET)
)
if (local !== String(fields.md5sig).toUpperCase()) {
  return new Response('bad signature', { status: 400 })
}
```

Note the order: merchant id, order id, **the amount PayHere reports**, the
currency, the status code, then the hashed secret. Hashing your own expected
amount instead of `payhere_amount` produces a check that passes for a payment
of the wrong size.

`status_code` is `2` for success, `0` pending, `-1` cancelled, `-2` failed, `-3`
chargeback. Only `2` is paid. Compare the reported amount and currency against
the order before marking it paid, and make the whole thing idempotent on
`payment_id` — the notification can arrive more than once.

Reply 200 with no body. PayHere retries anything else.

## Testing it

Sandbox test cards are on PayHere's support site; `4916217501611292` with any
future expiry and any CVV is the usual Visa one.

Everything here is your own code — the hash, the form, the handler — so none
of it needs PayHere to be running, and no unit test should reach it.

The notification cannot reach a local machine, so the test posts it: build the
form fields, compute a valid `md5sig` with the sandbox secret, and post them to
your own handler. Then assert the order is paid, post the same fields again and
assert nothing changed, and post a set with a tampered `payhere_amount` and
assert it is rejected.

- https://support.payhere.lk/api-&-mobile-sdk/checkout-api
- https://support.payhere.lk/api-&-mobile-sdk/payhere-notification
- https://support.payhere.lk/faq/sandbox-test-cards
