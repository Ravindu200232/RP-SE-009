# Sign in with Facebook

Read this only when Facebook was chosen. SKILL.md still governs verification,
joining and the session; this is Facebook's own part.

`FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET` and optionally
`FACEBOOK_REDIRECT_URI` are in `.env.local`.

## The token has to be inspected, not decoded

Exchange the `code` for an access token, then ask Facebook whether that token
is really yours:

```js
const check = await fetch('https://graph.facebook.com/debug_token?' + new URLSearchParams({
  input_token: userToken,
  access_token: `${process.env.FACEBOOK_APP_ID}|${process.env.FACEBOOK_APP_SECRET}`,
}).toString()).then(r => r.json())
```

`check.data.app_id` must equal your app id and `check.data.is_valid` must be
true. Without this, a token issued to a *different* app is accepted by yours —
that is the whole attack, and skipping `debug_token` is how it lands.

## Ask for the fields you want

The Graph API returns almost nothing unless asked:

```js
const me = await fetch(
  `https://graph.facebook.com/me?fields=id,name,email&access_token=${userToken}`)
```

Without `fields`, you get `id` and `name` and wonder where the email went.

**The email may still be missing.** A person can sign up with a phone number,
can refuse the email permission on the consent screen, or can have an address
Facebook could not confirm. `email` is simply absent from the response — not
null, absent. Plan for an account with no address rather than crashing on one.

`id` is the stable account id, and note that it is **app-scoped**: the same
person has a different id in a different app of yours. That is fine for joining
within one product and wrong for joining across two.

## App review

Until the app passes review it is in development mode, and only people listed
as developers, testers or admins can sign in at all. Everyone else gets a
generic error. If sign-in works for you and for nobody else, this is why — say
so in your report rather than debugging the code.

`email` is one of the permissions that requires review before the public may
grant it.

## Testing it

Stub both calls. Assert that a token whose `app_id` is another app's is
refused, that `is_valid: false` is refused, that a response with no `email`
creates an account rather than throwing, and that the same `id` twice is one
user.

- https://developers.facebook.com/docs/facebook-login/guides/access-tokens/debugging
- https://developers.facebook.com/docs/graph-api/overview
