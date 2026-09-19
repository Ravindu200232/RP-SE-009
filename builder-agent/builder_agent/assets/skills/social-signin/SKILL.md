---
name: social-signin
description: Signing in with Google, GitHub, Facebook or Microsoft — which credentials to ask for, why the token is verified on the server and never trusted from the browser, and how the account it returns is joined to a user you already have.
---

# Signing in with somebody else's account

Use this skill when a person signs in with an account they already have
instead of a password the product stores. It replaces nothing else about
authorisation: who they are is the provider's answer, what they may do is
still yours.

## What was already settled

A client id and secret cannot be read out of a repository, so they were asked
for before the build started, or ticked as a plugin. That answer is in the plan
under "already settled". Build the one sign-in that was chosen; do not add a
second provider nobody asked for, and do not build a switch between them.

- **Google** — `readSkill("social-signin", "google.md")`
- **GitHub** — `readSkill("social-signin", "github.md")`
- **Facebook** — `readSkill("social-signin", "facebook.md")`
- **Microsoft** — `readSkill("social-signin", "microsoft.md")`

Whichever provider's names are present in the environment is the one that was
chosen. Read them from `process.env` and never write one into source: a secret
in a file goes into git, into a screenshot, and into whatever the repository is
copied into, and a leaked one has to be rotated in the provider's console
rather than edited out. Where a name is in `.env.example` but not in the
environment, build against `process.env` anyway and fail at the point of use
with a message naming the missing variable, rather than rendering a button that
cannot work.

The redirect URI is not a credential and it is not guesswork: it is the route
you actually serve the callback on, and the same string has to be registered
with the provider or the sign-in is refused. Say in your final report which URI
the app expects, because that is the one thing the user has to go and paste.

## What has to be true

**The browser never decides who it is.** A token that arrives from the client
is a claim. Verify it on the server — signature against the provider's
published keys, issuer, audience equal to your client id, and expiry — or
exchange the code for it server-side, before it becomes a session. A
decoded-but-unverified JWT is a text field anybody can type into.

**The account is joined on the provider's stable id, not on the email.** Every
one of these has an id that does not change; an email address can be changed
and reassigned inside a workspace or an organisation. Store the id, and treat
the email as a display detail that may move.

**An unverified email is not an identity.** If the provider says the address is
unverified — or, as GitHub does, simply declines to give you one — the account
is not proven and must not be merged into an existing user with that address.
That is exactly how one account is taken over by another.

**Signing in is not signing up, unless you say so.** Decide, once, whether an
account with no matching user creates one. Both answers are reasonable; what is
not reasonable is that it depends on which route they arrived through.

**The session is yours.** The provider's part ends when the token is verified.
Set your own session with the same rules as the rest of the product —
httpOnly, secure, sameSite, and an expiry — rather than keeping the provider's
token around to re-present.

**State is checked on the way back.** The callback carries a `state` you
generated and stored; if it does not match, the request is not a sign-in and is
refused. Without it the callback is an open door for a forged login.

**Ask for the narrowest scope that works.** The default scope is an identity,
not a mailbox and not a repository list. Every extra scope is a consent screen
that loses people and a breach that is worse when it comes.

## Verifying it

Unit tests own the verification boundary with the provider's endpoints stubbed:
a token signed by the wrong key is refused, an expired one is refused, one
whose audience is another client id is refused, a mismatched `state` is
refused, an unverified email does not merge into an existing account, and a
valid sign-in produces exactly one user on two attempts.

An E2E journey cannot drive somebody else's consent screen and must not try.
Stub the verification at the server boundary, then assert what the user can
see: the button exists on the signed-out page, a signed-in session reaches the
page it was meant to reach, and a refused token lands on an error they can read.
