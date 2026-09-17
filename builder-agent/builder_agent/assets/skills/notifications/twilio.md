# Twilio SMS

Read this only when Twilio was chosen. SKILL.md still governs when a message is
written and when it is sent; this is Twilio's own part.

`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` and `TWILIO_FROM_NUMBER` are in
`.env.local`.

```js
import twilio from 'twilio'

const client = twilio(process.env.TWILIO_ACCOUNT_SID, process.env.TWILIO_AUTH_TOKEN)

const sent = await client.messages.create({
  from: process.env.TWILIO_FROM_NUMBER,
  to: customer.phone,                 // E.164, always
  body: `Your booking on ${date} is confirmed.`,
})
```

Store `sent.sid` on the record. It is how a delivery question is answered
later, and it is what makes a resend detectable as a duplicate.

## Numbers

Twilio takes E.164 and nothing else: `+94771234567`. A Sri Lankan number typed
as `0771234567` is rejected, so normalise on the way in — when the number is
captured — rather than at the point of sending. Store the normalised form; a
database with both shapes in it cannot be deduplicated or matched.

The error for a malformed number is `21211` (invalid `To` number). `21608` means
the number is not verified, which on a trial account is every number you did not
add yourself.

## Trial accounts

A trial account can only message numbers verified in the console, and it puts a
"Sent from your Twilio trial account" prefix on every message. Neither is a bug
to work around. If the app is on a trial account, say so on screen rather than
letting somebody demonstrate it to a number that will never receive anything.

`+15005550006` is Twilio's magic test number: it always succeeds and sends
nothing. Their other magic numbers produce specific failures on demand —
`+15005550001` is invalid, `+15005550009` cannot receive SMS — which is how the
failure paths get tested without a real handset.

## Cost is a real constraint

Every message costs money and there is no undo. A loop that sends per row, a
retry without a ceiling, or an OTP endpoint without rate limiting per recipient
is somebody's bill. Rate limit by recipient and by account, cap retries, and
never send from a test.

## Testing it

Stub the client. Assert that a number is normalised to E.164 before it reaches
the client, that a rejected number marks the record failed rather than throwing
past the caller, that the same event twice sends once, and that the OTP path
refuses a fourth request in a minute.

- https://www.twilio.com/docs/messaging/quickstart/node
- https://www.twilio.com/docs/iam/test-credentials
