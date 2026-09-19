# PostHog

Read this only when PostHog was chosen. SKILL.md still governs consent, event
names and what may travel in a payload; this is PostHog's own part.

`POSTHOG_PUBLIC_KEY` and optionally `POSTHOG_HOST` are in `.env.local`. The
project key starts with `phc_` and is public — it goes in the page.

## The host is not optional if your data must stay in the EU

The client defaults to PostHog's US cloud. An EU project's key sent to the US
host silently records nothing, and data sent to the wrong region cannot be
moved afterwards:

```js
posthog.init(process.env.NEXT_PUBLIC_POSTHOG_PUBLIC_KEY, {
  api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST || 'https://us.i.posthog.com',
})
```

## Consent, and the two things that capture by default

`capture_pageview` and `autocapture` are both on unless turned off, and
autocapture records clicks, inputs and form submissions across the product
without anyone naming them. That is useful and it is also the fastest way to
send something you did not mean to.

Where consent is required, start opted out and opt in on the answer:

```js
posthog.init(key, { api_host: host, opt_out_capturing_by_default: true })
// on consent:
posthog.opt_in_capturing()
```

`posthog.opt_out_capturing()` is the refusal, and it persists.

Mask anything sensitive before it is autocaptured. Inputs are masked by
default; an element you want left out entirely gets the `ph-no-capture` class.

## Identifying a person

`posthog.identify(id, properties)` ties the anonymous history to a user. Call
it once, at sign-in, with **your own opaque id** — not an email address. Call
`posthog.reset()` at sign-out, or the next person on that browser inherits the
previous one's identity.

Do not call `identify` on every render: each call is a request, and a changing
id is a new person every time.

## Session replay

If replay is on, it records the screen. Confirm that is wanted, and mask every
field that carries anything personal before it is. A replay of a checkout with
an unmasked address field is a data breach with a play button.

## Testing it

Stub the client. Assert that nothing is captured before opt-in, that `reset` is
called at sign-out, that `identify` is not called with an email address, and
that nothing is sent in the test environment.

- https://posthog.com/docs/libraries/js
- https://posthog.com/docs/privacy/gdpr-compliance
