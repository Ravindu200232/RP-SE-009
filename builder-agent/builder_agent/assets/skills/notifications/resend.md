# Resend

Read this only when Resend was chosen. SKILL.md still governs when a message is
written and when it is sent; this is Resend's own part.

`RESEND_API_KEY` and `EMAIL_FROM` are in `.env.local`.

```js
import { Resend } from 'resend'

const resend = new Resend(process.env.RESEND_API_KEY)

const { data, error } = await resend.emails.send({
  from: process.env.EMAIL_FROM,
  to: customer.email,
  subject: `Order ${order.reference} confirmed`,
  html: renderOrderEmail(order),
})
```

The key is read from the environment. A key written into source goes into git,
into a screenshot, and into whatever the repository is copied into — and a
leaked one has to be rotated in the dashboard, not edited out of a file.

`data.id` is the message id. Store it on the record: it is how a delivery
question is answered later, and it is what makes a resend detectable as a
duplicate rather than a second message.

## What it refuses, and what it says

These are the answers the API actually gives, so handle them as themselves
rather than as a generic failure:

**A sending domain that is not verified** — HTTP 403:

```json
{"statusCode":403,"name":"validation_error",
 "message":"The example.com domain is not verified. Please, add and verify your domain on https://resend.com/domains"}
```

Nothing in the code fixes this. Surface it as configuration: the domain in
`EMAIL_FROM` has to be added and verified at resend.com/domains first.

**`onboarding@resend.dev`** is Resend's own sandbox sender. It needs no domain
setup and works immediately, which is what makes it right while building — and
it is limited to the account's own address, which is what makes it useless in
production. If `EMAIL_FROM` is that address, the app is in sandbox: say so on
screen rather than letting someone ship it.

**A recipient at `example.com`** — HTTP 422:

```json
{"statusCode":422,"name":"validation_error",
 "message":"Invalid `to` field. Please use our testing email address instead of domains like `example.com`."}
```

Resend blocks the example domains outright, so a fixture using
`user@example.com` fails on a real send. Resend's own test mailboxes are
`delivered@resend.dev` and `bounced@resend.dev`, and both are accepted — use
those when a test really has to reach the API.

**A key restricted to sending** answers 401 on anything else:

```json
{"statusCode":401,"name":"restricted_api_key",
 "message":"This API key is restricted to only send emails"}
```

That is the right kind of key for an application. Do not ask for a full-access
one, and do not build a feature that lists domains or manages keys.

## Errors do not throw

`resend.emails.send` resolves with `{ data, error }`; it does not reject on an
API error. Code that only wraps it in `try/catch` treats every failure as a
success:

```js
if (error) {
  await Messages.updateOne({ _id: message._id },
    { $set: { status: 'failed', error: error.message } })
  return
}
```

## Testing it

Stub the client. Assert that the record is written before the send, that an
`error` in the response marks the record failed and retryable rather than sent,
and that the same event twice sends once. Nothing in a test reaches a real
inbox.

- https://resend.com/docs/send-with-nodejs
- https://resend.com/docs/dashboard/domains/introduction
