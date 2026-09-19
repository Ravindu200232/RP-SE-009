# SendGrid

Read this only when SendGrid was chosen. SKILL.md still governs when a message
is written and when it is sent; this is SendGrid's own part.

`SENDGRID_API_KEY` and `EMAIL_FROM` are in `.env.local`.

```js
import sgMail from '@sendgrid/mail'
sgMail.setApiKey(process.env.SENDGRID_API_KEY)

const [response] = await sgMail.send({
  to: customer.email,
  from: process.env.EMAIL_FROM,
  subject: `Booking ${booking.reference} confirmed`,
  html: renderBookingEmail(booking),
})
```

## A 202 means accepted, not delivered

SendGrid answers `202 Accepted` with an empty body. That is the queue accepting
the message; it says nothing about whether it arrived. The message id is in the
`x-message-id` response header — store it, because it is the only handle you
have when somebody asks later what happened to an email.

```js
const messageId = response.headers['x-message-id']
```

Delivery, bounce and spam-report outcomes arrive at an Event Webhook, if one is
configured. Without it, "sent" is the furthest the product can honestly say.

## The from address is the thing that fails

A `from` that is not a Verified Sender, or not on an authenticated domain, is
refused with HTTP 403 and a body naming the sender identity. Nothing in the
code fixes that; it is done under Settings, Sender Authentication. Surface it
as configuration and say so in your report.

Domain authentication also decides whether mail lands in an inbox. An
unauthenticated domain sends, and goes to spam.

## Errors are nested, and the useful part is inside

`@sendgrid/mail` rejects on an API error, and the message on the thrown error
is generic. What actually went wrong is in `error.response.body.errors`, an
array of `{ message, field, help }`. Record that array on the message, not
`error.message`, or every failure reads the same.

## Sandbox mode

`mailSettings: { sandboxMode: { enable: true } }` validates the request and
sends nothing. It is the right thing for an automated run: it exercises the
whole path, including a 403 for a bad sender, without reaching anyone.

## Testing it

Stub the client. Assert that the record is written before the send, that a 403
is recorded as configuration rather than as a retryable failure, that the
message id is stored, and that the same event twice sends once. Nothing in a
test reaches a real inbox.

- https://www.twilio.com/docs/sendgrid/for-developers/sending-email/quickstart-nodejs
- https://www.twilio.com/docs/sendgrid/ui/sending-email/sender-verification
