# Sign in with GitHub

Read this only when GitHub was chosen. SKILL.md still governs verification,
joining and the session; this is GitHub's own part.

`GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` and optionally `GITHUB_REDIRECT_URI`
are in `.env.local`.

## There is no id token

GitHub's OAuth is not OpenID Connect. There is no JWT to verify — the callback
brings a `code`, you exchange it on the server for an access token, and then
you ask the API who it belongs to. The access token is the credential; it never
reaches the browser.

```js
const token = await fetch('https://github.com/login/oauth/access_token', {
  method: 'POST',
  headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
  body: JSON.stringify({
    client_id: process.env.GITHUB_CLIENT_ID,
    client_secret: process.env.GITHUB_CLIENT_SECRET,
    code,
  }),
}).then(r => r.json())
```

**Send `Accept: application/json` or the answer comes back as
`access_token=gho_…&scope=&token_type=bearer`** — a form-encoded string, not
JSON. Parsing that with `JSON.parse` is the first thing that goes wrong here.

An error is returned with HTTP 200 and an `error` field:
`{"error":"bad_verification_code"}`. Check the field, not the status.

## The email may not be there

`GET /user` returns the profile. Its `email` is the *public* one, and most
accounts do not set it — so `user.email` is very often `null`. This is the
thing that breaks a sign-in built against Google's shape.

If the product needs an address, request the `user:email` scope and ask
separately:

```js
const emails = await gh('/user/emails')       // needs the user:email scope
const primary = emails.find(e => e.primary && e.verified)
```

Only a `verified` address may be joined to an existing account. If none is
verified, the identity is not proven for merging.

`user.id` is the stable account id. `user.login` is a username and **can be
changed by its owner**, so joining on it hands one person's account to whoever
takes the name next.

## Scopes

An empty scope already gives `GET /user` and public data, which is all a
sign-in needs. Add `user:email` only if you need the address. Never ask for
`repo`: it is read and write access to every private repository the person has.

## Testing it

Stub both calls. Assert that a form-encoded error answer is not treated as a
token, that a `null` email does not become the join key, that an unverified
address does not merge, and that a changed `login` still resolves to the same
user.

- https://docs.github.com/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps
- https://docs.github.com/rest/users/emails
