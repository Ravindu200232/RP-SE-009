# Mapbox

Read this only when Mapbox was chosen. SKILL.md still governs what is stored
and what is public; this is Mapbox's own part.

`MAPBOX_PUBLIC_TOKEN`, `MAPBOX_SECRET_TOKEN` and optionally `MAPBOX_STYLE_URL`
are in `.env.local`.

## Two tokens, told apart by their prefix

`pk.` is public and belongs in the page. Restrict it by URL in the account
dashboard so it only works from the product's own domains.

`sk.` is secret, carries the geocoding scope, and must never reach the browser.
Mapbox scans public repositories for tokens and revokes what it finds, so a
committed `sk.` token stops working — which is the good outcome; the bad one is
the bill before it is noticed. In Next.js, only the public token may carry the
`NEXT_PUBLIC_` prefix.

## Drawing a map

```js
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css'

mapboxgl.accessToken = process.env.NEXT_PUBLIC_MAPBOX_PUBLIC_TOKEN
```

Two things break maps that otherwise look right:

- **The stylesheet is not optional.** Without `mapbox-gl.css` the map renders
  as a broken stack of tiles with the controls scattered across the page. It
  looks like a layout bug and it is a missing import.
- **The container must have a height.** A `div` with no height gives a map of
  zero pixels and no error. Set it in CSS, not by waiting for a resize.

Call `map.remove()` when the component unmounts. Mapbox holds a WebGL context
per map, browsers cap how many may exist, and a page that mounts maps without
removing them eventually renders nothing at all.

## Geocoding, on the server

```js
const url = new URL(
  `https://api.mapbox.com/search/geocode/v6/forward`)
url.searchParams.set('q', address)
url.searchParams.set('access_token', process.env.MAPBOX_SECRET_TOKEN)
const body = await fetch(url).then(r => r.json())
```

The answer is GeoJSON: `body.features` is an array, empty when nothing
resolved. **Coordinates are `[longitude, latitude]`, in that order** —
longitude first, which is the opposite of how everyone says it and the single
most common bug against this API. Name the variables when you unpack them.

An empty `features` array is "not found", and it is recorded as unresolved.
Never store `0,0`.

`features[0].properties.mapbox_id` is the stable handle; keep it beside the
coordinates.

## Testing it

Stub `fetch`. Assert that an empty `features` array stores no coordinates, that
the pair is unpacked longitude-first, and that a provider failure leaves the
record the user was saving intact.

- https://docs.mapbox.com/mapbox-gl-js/guides/
- https://docs.mapbox.com/api/search/geocoding/
