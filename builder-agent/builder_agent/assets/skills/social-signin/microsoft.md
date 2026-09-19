# Sign in with Microsoft

Read this only when Microsoft was chosen. SKILL.md still governs verification,
joining and the session; this is Microsoft's own part.

`MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `MICROSOFT_TENANT_ID` and
optionally `MICROSOFT_REDIRECT_URI` are in `.env.local`.

## The tenant decides who may sign in

The authority is `https://login.microsoftonline.com/{tenant}/v2.0`, and the
tenant is the access rule:

- a tenant **GUID** — only that one organisation
- **`organizations`** — any work or school account, from any tenant
- **`consumers`** — personal Microsoft accounts only
- **`common`** — both

Choosing `common` for a product meant for one company lets every Microsoft
account in the world reach the sign-in. Choose deliberately, and say which in
your report.

## Verifying the token

Validate against the published keys for the authority you used, and check:

- **`aud`** equals your client id.
- **`iss`** matches the authority. With `common` or `organizations` the issuer
  contains the signing-in tenant's own id, so it is *not* a fixed string — the
  check is that the issuer's tenant matches the `tid` claim, not that it equals
  a constant. Hard-coding the issuer is what breaks multi-tenant sign-in a week
  after it ships.
- **`tid`** — when the product is for one organisation, this must be that
  tenant. This is the real check; a `tenant` in the URL is not enforcement on
  its own.

## Which claim is the account

**`oid`** is the person's object id, stable within a tenant. **`sub`** is
stable but is scoped per application. Use `oid` together with `tid`: the pair
identifies a person in an organisation, and either one alone does not.

Do not join on `email`, `preferred_username` or `upn`. All three are mutable,
`preferred_username` is explicitly documented as unsuitable for
authorisation decisions, and a personal account may have no `email` claim at
all.

## The secret expires

A client secret has a maximum lifetime and is commonly created with a short
one. When it lapses, sign-in stops for everyone with
`AADSTS7000222: The provided client secret keys for app … are expired`. Say
the expiry date in your report; nothing in the code can prevent it.

## Scopes

`openid profile email` is an identity. `offline_access` is only needed if the
product calls Microsoft APIs later on the person's behalf — a sign-in does not.

## Testing it

Stub the key endpoint. Assert that a wrong `aud` is refused, that a token from
another `tid` is refused when the product is single-tenant, that the join key
is `oid`+`tid` rather than an address, and that an expired-secret error
surfaces as configuration rather than as a failed login.

- https://learn.microsoft.com/entra/identity-platform/id-tokens
- https://learn.microsoft.com/entra/identity-platform/access-tokens#validate-tokens
