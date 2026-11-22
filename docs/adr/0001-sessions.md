# 0001. Browser sessions: a token bound to a revocable session, in an httpOnly cookie

- **Status:** Accepted
- **Date:** 2026-10-06

## Context and problem

The console signs people in and must survive a stolen token and cross-site requests. A JWT alone cannot be revoked before it expires, and a token readable by JavaScript is lost to any XSS.

## Considered options

- A JWT in `localStorage`, sent as a Bearer header: no CSRF, but any script on the page can read and send it, and it cannot be revoked.
- Server-side sessions with an opaque cookie: revocable, but every request needs a session lookup and the API's Bearer clients need a second mechanism.
- A JWT whose `jti` is a row in `user_sessions`, sent in an httpOnly cookie, with a signed double-submit CSRF header (chosen).

## Decision

Every sign-in creates a session row whose id is the token's `jti`; the token is checked and its session must still be live. The console gets the token only as an httpOnly, `Secure`, `SameSite=Strict` cookie; every state-changing request by cookie must carry `X-CSRF-Token`, an HMAC of the session id. Bearer requests need no CSRF token.

## Consequences

- Good: Logout, logout everywhere, deactivation and suspension revoke sessions at once.
- Good: JavaScript never sees the token; a forged cross-site request lacks the CSRF header.
- Bad: One database read per request to check the session.
- Bad: Two ways to authenticate (cookie and Bearer) to keep equal.

## More information

Written in November 2026 from the decisions log: [JWT and sessions](../02-decisions-log.md#jwt-and-sessions), [Browser authentication](../02-decisions-log.md#browser-authentication).
