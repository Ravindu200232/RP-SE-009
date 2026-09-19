# Google Maps

Read this only when Google Maps was chosen. SKILL.md still governs what is
stored and what is public; this is Google's own part.

`GOOGLE_MAPS_BROWSER_KEY`, `GOOGLE_MAPS_SERVER_KEY` and optionally
`GOOGLE_MAPS_MAP_ID` are in `.env.local`.

## Two keys, and why

The browser key is in the page. It has to be — a map draws client-side, and
anyone can read it out of the network tab. That is not the problem; an
unrestricted key is. In the Cloud console, restrict it to the product's own
HTTP referrers and to the Maps JavaScript API alone.

The server key never leaves the server. Geocoding runs there, against a key
restricted by IP address and to the Geocoding API. Reusing the browser key for
geocoding puts a server-scoped quota into a public page.

Say both restrictions in your final report. They are done in the console, not
in code, and nobody does them if nobody says so.

## Drawing a map

Load the library once, not per component. A second `<script>` for the same API
raises `You have included the Google Maps JavaScript API multiple times` and
the map that loads second is the one that breaks.

```js
// Loaded once, at the app's edge.
const loader = new Loader({
  apiKey: process.env.NEXT_PUBLIC_GOOGLE_MAPS_BROWSER_KEY,
  version: 'weekly',
  libraries: ['places'],
})
```

Only the browser key may be exposed to the client, and in Next.js that means
it has to carry the `NEXT_PUBLIC_` prefix to reach the browser at all. Copy it
under that name at the app's edge; never prefix the server key.

`AdvancedMarkerElement` needs `GOOGLE_MAPS_MAP_ID`. Without a map id it throws
at render rather than falling back, so if there is no map id, use the classic
`Marker`.

## Geocoding, on the server

```js
const url = new URL('https://maps.googleapis.com/maps/api/geocode/json')
url.searchParams.set('address', address)
url.searchParams.set('key', process.env.GOOGLE_MAPS_SERVER_KEY)
const body = await fetch(url).then(r => r.json())
```

The HTTP status is 200 even when the lookup failed. The answer is in
`body.status`, and these are the ones that matter:

- `OK` — `body.results[0].geometry.location` has `lat` and `lng`.
- `ZERO_RESULTS` — the address does not resolve. Record it as unresolved.
  **Never store `0,0`**: that is a real place in the Gulf of Guinea, and it
  will show up on the map as one.
- `OVER_QUERY_LIMIT` — billing or quota. Back off; do not retry in a loop.
- `REQUEST_DENIED` — the key is wrong, restricted to the wrong API, or billing
  is not enabled on the project. `body.error_message` says which.

Also store `results[0].place_id`. It is stable when the formatted address is
not, and it is what lets you re-resolve later without guessing.

## What costs money

Every Places autocomplete keystroke is a request. Use a session token so a
whole typing session bills as one autocomplete plus one details call, and
debounce on top of it:

```js
const token = new google.maps.places.AutocompleteSessionToken()
```

Cache what you resolve. An address resolves to the same coordinates tomorrow,
and Google's terms allow caching a place id indefinitely.

## Testing it

Stub `fetch`. Assert that `ZERO_RESULTS` stores no coordinates, that
`REQUEST_DENIED` surfaces as configuration rather than as a lost record, and
that the same address twice makes one request. Nothing in a test calls Google.

- https://developers.google.com/maps/documentation/javascript/overview
- https://developers.google.com/maps/documentation/geocoding/requests-geocoding
- https://developers.google.com/maps/documentation/javascript/places-autocomplete#session_tokens
