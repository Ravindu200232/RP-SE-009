---
name: payments
description: Take payments with Stripe or PayHere, including which one to use, test against live credentials, the redirect and webhook boundaries, and what must never be trusted from the browser.
---

# Payments

Use this skill when the product takes money: a checkout, a subscription, a
deposit, a top-up, a paid booking, a donation. Do not use it for a price that is
only displayed.

## What was already settled

You cannot read a merchant account out of a repository, so the user was asked
before the plan was written — which gateway, and test credentials or real ones.
That answer is in the plan under "already settled", and it is not yours to
revisit. Do not ask again, do not offer the other gateway, and do not write a
switch that supports both: build the one that was chosen.

If a setting turns out to be missing while you work, `askForSetup` asks for it
without stopping the build.

Read the file for the gateway that was chosen, and no other:

- **Stripe** → `readSkill("payments", "stripe.md")`. International cards, hosted
  Checkout, subscriptions.
- **PayHere** → `readSkill("payments", "payhere.md")`. Sri Lanka: LKR, local
  cards, eZ Cash, mCash and bank options.

Their keys are already in `.env.local` under the names the question used. Read
them from `process.env` and never write one into source. If nobody answered,
the names are in `.env.example`: build against `process.env` anyway, and fail
loudly at the point of use with a message naming the missing variable rather
than pretending a payment succeeded.

## What is true whichever provider is chosen

**The browser never decides what anything costs.** Take a cart, a plan id or a
booking id from the client; read the price from your own database on the server
and build the charge from that. A client-supplied amount is a price the customer
chose.

**The order is not paid because the browser came back.** A redirect to a success
page is the customer's browser, and it can be opened directly, closed early or
replayed. The record is marked paid by the server, from a verified notification,
and by nothing else. Show "we are confirming your payment" until that has
happened.

**Every notification is verified before it is believed.** Stripe: read the raw,
unparsed request body and check the signature header with the webhook secret. A
route that parses JSON first cannot verify anything, so the framework's body
parsing must be off for that one path. PayHere: recompute the `md5sig` from the
merchant id, order id, amount, currency, status code and the hashed merchant
secret, and compare. Reject anything that does not match, with a 400 and no
detail.

**Notifications arrive more than once, and out of order.** Key every payment
record on the provider's own id and make applying one idempotent, so the same
notification twice does not ship two orders or credit an account twice.

**Store what happened, not the instrument.** A card number, a CVV or a raw
token never reaches your database, your logs, your test fixtures or a
screenshot. Keep the provider's payment id, the amount, the currency, the
status, and your own order id.

**Money is an integer.** Stripe charges in the smallest unit (cents), PayHere
takes an amount with two decimals — either way, hold minor units in the
database and format only for display. Currency is stored beside every amount,
never assumed.

## Verifying it

An E2E journey drives the real test-mode flow: the customer reaches checkout,
is redirected to the provider's sandbox, pays with the provider's test card,
and returns to a page that is honest about the order still being unconfirmed.
Then deliver the notification your own webhook handler expects and assert the
order becomes paid exactly once.

Unit tests own the parts that must not be reachable from a browser at all:
a tampered amount is rejected, a bad signature is rejected, a replayed
notification changes nothing the second time, and a currency mismatch is
refused.

Never weaken a check to make a test pass. If live credentials were chosen, do
not run a journey that moves real money — build it, and say plainly that it was
verified in sandbox only.

Current references:

- https://docs.stripe.com/checkout/quickstart
- https://docs.stripe.com/webhooks/signature
- https://support.payhere.lk/api-&-mobile-sdk/checkout-api
- https://support.payhere.lk/api-&-mobile-sdk/payhere-notification
