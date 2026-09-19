# Mailgun

Read this only when Mailgun was chosen. SKILL.md still governs when a message
is written and when it is sent; this is Mailgun's own part.

`MAILGUN_API_KEY`, `MAILGUN_DOMAIN`, `MAILGUN_REGION` and `EMAIL_FROM` are in
`.env.local`.

## The region is a different host

Mailgun runs separate EU and US infrastructure, and an account in one is
invisible to the other. The client defaults to the US host, so an EU account
authenticates against it and fails with 401 — which reads as a wrong key and is
a wrong host.

```js
const mailgun = new Mailgun(FormData)
const mg = mailgun.client({
  username: 'api',
  key: process.env.MAILGUN_API_KEY,
  url: process.env.MAILGUN_REGION === 'eu'
    ? 'https://api.eu.mailgun.net'
    : 'https://api.mailgun.net',
})
```

## The sending domain is not your website

`MAILGUN_DOMAIN` is the domain added and verified in Mailgun — usually a
subdomain such as `mg.example.com`, kept separate so a sending-reputation
problem never touches the main domain's mail. `EMAIL_FROM` has to be an address
on it; a `from` on any other domain is refused.

```js
await mg.messages.create(process.env.MAILGUN_DOMAIN, {
  from: process.env.EMAIL_FROM,
  to: [customer.email],
  subject: `Booking ${booking.reference} confirmed`,
  html: renderBookingEmail(booking),
})
```

`to` is an array. A bare string works for one recipient and behaves differently
for several.

The response carries `id`, the message id, in angle brackets. Store it on the
record.

## A sandbox domain only mails its authorised recipients

A new account gets `sandboxXXXX.mailgun.org`, which sends only to addresses
explicitly authorised in the dashboard. Everything else is accepted and
dropped. If mail "sends" and nothing arrives, check this before the code.

## Errors

A failure rejects with `error.status` and `error.details`. 401 is the key or
the region; 400 with a message about the domain is the `from` address. Record
the detail on the message rather than a generic string.

## Testing it

Stub the client. Assert that the EU region produces the EU host, that the
record is written before the send, that a 401 is recorded as configuration, and
that the same event twice sends once.

- https://documentation.mailgun.com/docs/mailgun/user-manual/sending-messages/
- https://documentation.mailgun.com/docs/mailgun/user-manual/domains/
