---
name: notifications
description: Send email with Resend and SMS with Twilio — which credentials to ask for, why sending never happens in the request that triggered it, and how to test without posting to a real person.
---

# Email and SMS

Use this skill when the product tells somebody something outside itself: an
order confirmation, a booking reminder, a password reset, a receipt, an OTP, an
alert to staff.

## What was already settled

An email account cannot be read out of a repository, so the user was asked
before the plan was written: which provider, and whether anything really
leaves the machine. That answer is in the plan under "already settled". Do not
ask again, and do not build a switch that supports all of them - build the one
that was chosen, and read its file and no other.

- **Test** - nothing is sent. Every message is written as a record and logged,
  so the whole flow can be exercised without reaching a real person. There is
  no provider file to read: write the record, log it, and make the app say
  plainly that it is not sending.
- **Resend** - `readSkill("notifications", "resend.md")`
- **SendGrid** - `readSkill("notifications", "sendgrid.md")`
- **Mailgun** - `readSkill("notifications", "mailgun.md")`
- **Twilio (SMS)** - `readSkill("notifications", "twilio.md")`

The settings arrive either from the question or from a plugin the user ticked; both land in the same place and mean the same thing, and whichever provider's names are present in the environment is the one that was chosen.

Their keys are already in `.env.local` under the names the question used. Read
them from `process.env` and never write one into source: a key in a file goes
into git, into a screenshot, and into whatever the repository is copied into,
and a leaked one has to be rotated in the provider's dashboard rather than
edited out. If nobody answered, the names are in `.env.example` - build against
`process.env` anyway and fail with a message naming the missing variable rather
than silently sending nothing.

## What has to be true

**Sending is not part of the request.** A checkout that waits on an email API
is a checkout that fails when that API is slow. Write the message as a record
first — recipient, template, payload, `status: 'pending'` — return to the user,
and send from that record. If the send fails, the record is still there to
retry.

**The same event does not send twice.** Key the record on what caused it (the
order id and the template name), so a retried request or a replayed webhook
finds the message already sent. People notice two confirmation emails; they
notice two OTPs more.

**A failure is recorded, not swallowed.** Store the provider's error on the
record and let it be visible. `catch {}` around a send is a feature that is
silently off.

**Never put a secret or a token in the body.** A password-reset link carries a
single-use, expiring token, not a password. An OTP is short-lived and rate
limited per recipient, or the SMS bill is somebody else's to run up.

**Nothing goes to a real person from a test.** In test mode, and in every
automated test, the send goes to the record and the log and no further.

## Verifying it

Unit tests own the sending boundary with the provider stubbed: the record is
written before the send, the same event twice sends once, a provider failure
leaves the record retryable rather than lost, and a rejected recipient is
recorded as rejected rather than as sent.

An E2E journey completes the action that triggers the message and asserts what
the user can actually see — "a confirmation has been sent to a@b.com" — plus
the pending record. Do not assert on a real inbox.

The provider's own file carries its references, its error shapes and its test
addresses.
