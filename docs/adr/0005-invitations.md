# 0005. Accounts join by invitation, not by public sign-up

- **Status:** Accepted
- **Date:** 2026-10-09

## Context and problem

An organization's accounts should not be open to anyone who reaches the API, and the public sign-up endpoint also told anyone whether an email had an account.

## Considered options

- Public sign-up behind a setting: nothing to forget to turn off is better than a switch.
- Operators set temporary passwords: the operator would know them and could act as that person.
- Invitations with a one-time token, accepted by the person invited (chosen).

## Decision

`POST /auth/register` is removed. An admin (or the owner, for admins) invites an email with a role; the token is built like an API key, lasts 72 hours, works once and travels only in request bodies. Who may grant the role is checked again on acceptance. The first owner comes from the command line.

## Consequences

- Good: No open door to the platform; no account enumeration through sign-up.
- Good: Granting a privileged role by invitation raises the same alert as a role change.
- Bad: An invitation link must reach the person outside the platform (no email is sent).
- Bad: Invalid invitation tokens are not rate limited.

## More information

Written in November 2026 from the decisions log: [Invitations instead of public sign-up](../02-decisions-log.md#invitations-instead-of-public-sign-up), [Invitations interface](../02-decisions-log.md#invitations-interface).
