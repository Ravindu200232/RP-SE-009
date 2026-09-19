# Plausible

Read this only when Plausible was chosen. SKILL.md still governs event names
and what may travel in a payload; this is Plausible's own part.

`PLAUSIBLE_DOMAIN` and optionally `PLAUSIBLE_HOST` are in `.env.local`.

## Why there is no banner

Plausible sets no cookies and stores nothing that identifies a person, so in
most jurisdictions it needs no consent banner. That is the reason to choose it.
Do not add one, and do not add a second tracker beside it that does need one —
that gives the product the banner it was chosen to avoid.

## The domain is a key, not a URL

`data-domain` must be exactly the site as it was added in Plausible: no
`https://`, no `www.` unless that is how it was added, no trailing slash. It is
how the request is matched to a site, and a mismatch records nothing at all
while the script loads perfectly and reports no error. This is the only real
failure mode here.

```html
<script defer data-domain="riverside-dental.lk"
        src="https://plausible.io/js/script.js"></script>
```

## Custom events

Custom events need the `script.tagged-events.js` (or `script.manual.js`)
variant; the plain script counts page views and nothing else.

```js
window.plausible?.('Booking completed', { props: { service: 'cleaning' } })
```

Two constraints that decide how you name things:

- An event has to be **declared as a goal** in the Plausible dashboard before
  it shows in reports. Data arriving for an undeclared goal is not backfilled.
- Properties are **low-cardinality only**. `service: 'cleaning'` is a property;
  a booking id is not, and using one produces a report with one row per record
  that answers no question.

`window.plausible` is undefined when the script is blocked, so always call it
optionally. An ad blocker must not throw inside a checkout.

## Testing it

Stub `window.plausible`. Assert that a blocked script does not throw, that no
event carries a high-cardinality or personal property, and that nothing is sent
in the test environment.

- https://plausible.io/docs/plausible-script
- https://plausible.io/docs/custom-event-goals
