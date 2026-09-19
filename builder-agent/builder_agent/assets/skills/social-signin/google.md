# Sign in with Google

Read this only when Google was chosen. SKILL.md still governs verification,
joining and the session; this is Google's own part.

`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` and optionally
`GOOGLE_REDIRECT_URI` are in `.env.local`.

## The redirect URI is exact

`http://localhost:3000/api/auth/callback/google` and
`http://localhost:3000/api/auth/callback/google/` are different URIs to Google,
and so are http and https, and so is a different port. A mismatch is refused
with `redirect_uri_mismatch` before your code runs. Register every environment
you will use, and say in your report which string the app expects.

## Verifying the token

Whether the id token arrives from the button or from a code exchange, it is a
claim until it is verified against Google's published keys:

```js
import { OAuth2Client } from 'google-auth-library'

const client = new OAuth2Client(process.env.GOOGLE_CLIENT_ID)
const ticket = await client.verifyIdToken({
  idToken,
  audience: process.env.GOOGLE_CLIENT_ID,
})
const claims = ticket.getPayload()
```

`verifyIdToken` checks the signature, the issuer, the audience and the expiry
together. Decoding the JWT yourself checks none of them — a decoded token is a
text field anybody can type into.

## What the claims mean

- **`sub`** is the account. It never changes. This is what the user record is
  joined on.
- **`email`** can be changed by the person, and inside a Workspace an
  administrator can reassign an address to somebody else. It is a display
  detail.
- **`email_verified`** — if this is false, the address is not proven and must
  not be merged into an existing user with that address. Refuse, or create a
  separate account.
- **`hd`** is the Workspace domain, and it is absent on personal accounts. If
  the product is for one organisation, check `hd` on the server; a `hd`
  parameter on the authorisation URL is a hint to Google's UI, not a
  restriction, and it can simply be removed by the person signing in.

## Scopes

`openid email profile` is an identity and is what this needs. Anything beyond
it — Drive, Calendar, Gmail — turns the consent screen into a decision and
puts the app into Google's verification process. Do not ask for one nobody
requested.

## Testing it

Stub the verification. Assert that a token with the wrong audience is refused,
that an expired one is refused, that `email_verified: false` does not merge
into an existing account, and that signing in twice produces one user.

- https://developers.google.com/identity/gsi/web/guides/verify-google-id-token
- https://developers.google.com/identity/protocols/oauth2/openid-connect
