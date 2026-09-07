---
name: authentication
description: Design, implement, audit, and test authentication, sessions, password handling, and authorization without forcing a framework-specific provider.
---

# Authentication and authorization

Use this skill when the product requires identity, login, sessions/tokens, roles, password recovery, OAuth/OIDC, or protected resources. First inspect the selected auth provider/library, deployment trust boundaries, user model, cookie/session storage, middleware, client flow, and existing tests. Do not replace a selected auth solution with a hardcoded library.

Decide explicitly whether the requirement is production authentication or a labelled non-security demo. Never satisfy a secure sign-in requirement with a username-exists check, an ignored password argument, a client-only role switch, a plaintext/fast fake hash, or comments promising that real authentication would be added later. If the required secure boundary cannot be implemented in the selected runtime, keep the requirement incomplete and report it honestly.

- Keep authentication (who), authorization (what), and session lifecycle separate. Enforce resource/action authorization on every server boundary; hiding a UI control is not access control.
- Prefer mature framework/provider primitives. Validate issuer, audience, signature, expiry, nonce/state/PKCE, and redirect destinations as applicable to the chosen protocol.
- Store browser sessions/tokens using the selected solution's secure server-backed or `HttpOnly`, `Secure`, appropriate `SameSite` cookie pattern. Do not persist credentials, session IDs, refresh tokens, or JWTs in web storage.
- Never store plaintext passwords or use fast general-purpose hashes. Use a maintained password-hashing implementation and current parameters, plus rate limiting and non-enumerating login/recovery responses.
- Rotate/invalidate sessions at login, privilege change, password reset, and logout as the threat model requires. Protect state-changing cookie-authenticated requests against CSRF.
- Keep secrets out of source, URLs, client bundles, logs, screenshots, fixtures, and error bodies.

Test successful login plus unknown-user and wrong-password failures, logout/invalidation, expiry, protected-route redirects/API status, direct server/API access without the UI, cross-user and role escalation boundaries, recovery/verification misuse, CSRF/state handling, and safe error disclosure. Assert that secret/hash fields never cross into client-visible session or response data. Use test identities and never real credentials.

Current security references:

- https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
