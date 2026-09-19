# Google Analytics

Read this only when Google Analytics was chosen. SKILL.md still governs
consent, event names and what may travel in a payload; this is GA's own part.

`GA_MEASUREMENT_ID` is in `.env.local`. It starts with `G-` and is public by
design — it goes in the page.

## Nothing loads before consent

The tag sets cookies the moment it runs, so in the EU and the UK it must not
run until consent is given. Load the script *after* the answer, not before:

```js
if (consented) loadGtag(process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID)
```

Consent Mode — `gtag('consent', 'default', { analytics_storage: 'denied' })`
before the tag, updated on the answer — is the supported alternative and still
sends cookieless pings while denied. Either is defensible; loading the tag and
showing a banner afterwards is not.

## A page view is not automatic in an app router

GA's enhanced measurement listens for History API changes, which is why a
Next.js app router commonly reports either one page view per session or two
per navigation. Send them yourself, once, on the route you actually rendered:

```js
gtag('event', 'page_view', { page_path: pathname })
```

and turn off enhanced measurement's own page-view listener in the data stream
settings so the two do not both fire.

## Events

`gtag('event', name, params)` — names are `snake_case`, and GA4 reserves a set
of its own (`page_view`, `purchase`, `login`, `sign_up` among them) whose
expected parameters are documented. Using a reserved name with your own shape
produces a report that looks right and counts the wrong thing.

Custom parameters do not appear in reports until they are registered as custom
dimensions in the GA admin. Data sent before registration is not backfilled, so
register first and say so in your report.

**Nothing identifying goes in a parameter.** GA's terms forbid sending personal
data, and an account can be suspended for it. Not an email address, not a name,
not a URL with a token in its query string. If a user id is needed, set the
`user_id` field to your own opaque id.

## Testing it

Stub `gtag`. Assert that nothing is sent before consent, that declining leaves
the page working and sends nothing, that no event carries a personal field, and
that nothing fires in the test environment.

- https://developers.google.com/analytics/devguides/collection/ga4
- https://developers.google.com/tag-platform/security/guides/consent
