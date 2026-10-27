# 03 - Frontend Foundation

## Purpose

This document describes the foundation of the SentinelCore web app: its visual direction, its technical base and its first working screens.

---

## Stage 1: The frontend foundation

### 1. Visual direction

Three visual directions were compared, each applied to the same security events screen. **Direction A, "operations console"**, was chosen:
- dark theme by default, with a complete light variant
- a dense interface, suited to analysts who watch events for long stretches
- `IBM Plex Sans` for the interface and `IBM Plex Mono` for technical data: times, IPs, event types, usernames

The initial palette was judged too dull. Out of three more vivid palettes, **"Electric"** was chosen: electric blue on navy.

Palette principles:
- the colors were generated in the OKLCH space, where perceived lightness can be controlled directly
- on the dark theme, the background is not black and the text is not pure white (contrast around 14:1), to reduce eye strain
- every text/background pair passes the WCAG AA threshold
- the five chart colors passed the palette validator on both themes, including the color-blindness separation; their order is fixed
- the severity colors (info, warning, incident, success) are separate from the brand color and always come with text and a shape, never color alone

### 2. Two scopes: My account and Organization

SentinelCore is designed as a monitoring hub with two scopes:
- **My account**: every user watches their own account (sessions, activity, alerts)
- **Organization**: administrators and security analysts watch every account

The scope switcher appears only for the `admin`, `owner` and `security_analyst` roles. The `/org` route is also protected in the frontend, but the real authorization stays in the API: the frontend only avoids showing pages whose requests would be refused anyway.

### 3. Technical base

| Area | Choice |
| --- | --- |
| Framework | React 19, TypeScript, Vite |
| Styles | Tailwind CSS 4, CSS variables for the theme |
| Components | shadcn/ui (on Radix primitives), copied into `src/components/ui` |
| Routing | React Router 8 |
| Server data | TanStack Query |
| Translations | i18next, Romanian by default, English available |
| Fonts | `@fontsource`, served by the app |
| Tests | Vitest, Testing Library, MSW for a mocked API |

The fonts are bundled into the build instead of being loaded from Google Fonts: the browser makes no third-party requests, and a strict CSP remains possible. The `latin-ext` subset covers `ă`, `ș` and `ț`.

### 4. Problem encountered: shadcn and the `cn` package

The interactive `shadcn init` hung waiting for a choice, so `components.json` was written by hand. When components were added, the CLI did not resolve the `@/lib/utils` alias: it generated `import { cn } from "cn"` and installed an unrelated npm package called `cn`.

The package was uninstalled and the imports were pointed back at `@/lib/utils`. The components now import only known packages: `radix-ui`, `lucide-react`, `class-variance-authority` and React.

Lesson: after running a command that changes dependencies, check `package.json`, even when the command comes from a well-known tool.

### 5. Authentication in the browser

The frontend uses the cookie authentication introduced in the backend:
- login through `POST /api/auth/session`; the token goes into an `httpOnly` cookie that frontend code cannot read
- the API client (`src/lib/api.ts`) automatically sends the `X-CSRF-Token` header, with the value of the `sentinelcore_csrf` cookie, on every `POST`, `PUT`, `PATCH` or `DELETE` request
- backend errors become an `ApiError`, with `status`, `detail` and `Retry-After`

In development, Vite forwards `/api/*` requests to the backend (`localhost:8000`). The frontend and the API therefore share an origin: no CORS is needed, and the `SameSite=Strict` cookies are sent normally.

### 6. Session and route protection

- the current user is read from `/users/me` through TanStack Query
- `RequireAuth` sends visitors without a session to `/login?next=<page>`, and brings them back to the requested page after login
- the `next` parameter accepts only internal app paths; an address like `/login?next=https://evil.example` leads to `/me` (open redirect protection)
- a deactivated account lands on the login page, with an explanation
- any `401` received during use (expired or revoked session) triggers a recheck of the user and a redirect to login
- network errors are retried twice, then a screen with a retry button is shown
- logout clears all cached data, so the next user sees nothing from the previous session

The login error messages are specific: wrong credentials, deactivated account, invalid input, server unavailable, and the brute-force block, with the number of minutes computed from `Retry-After`.

### 7. Theme and language

- the default theme is dark; the account menu offers light or "match system", and the choice is remembered
- the default language is Romanian; English is chosen from the same menu, and the page's `lang` attribute is updated
- the English translation file is typed after the Romanian one, so a missing or extra key fails the type check
- Romanian plural forms are handled correctly: "1 minut", "2 minute", "20 de minute"

### 8. Screens at this stage

- the login page
- the app structure: the sidebar with the scope switcher, the navigation and the account menu
- **My account / Overview**: the user's profile
- placeholder pages for the sections of the next stages: sessions, activity, security events, audit log, users

### 9. Dependency security

`npm audit` found 10 vulnerabilities (7 high severity) in the lockfile inherited from the template, almost all in build and development tools. All of them had compatible fixed versions and were resolved with `npm audit fix`, with no major version changes. Vite went up to 8.3.3.

CI runs `npm audit --audit-level=high` on every pull request.

### 10. Frontend CI

The `.github/workflows/frontend-ci.yml` workflow runs on pull requests to `main` and on pushes to `main` that change `frontend/`:
- `npm ci`
- `npm audit --audit-level=high`
- `npm run lint`
- `npm run typecheck`
- `npm test`
- `npm run build`

### 11. Local validation

- eslint -> no problems
- tsc -> no errors
- vitest -> 49 passed
- build -> successful
- npm audit -> 0 vulnerabilities

The tests cover: the API client (CSRF only on requests that change data, errors, `Retry-After`, `204` responses), filtering of the `next` parameter, login with every error type, the redirect after login, protection of the routes and of the organization scope, the theme, the language, logout with the CSRF token, and leaving the app when the session ends.

Reverse check: each of the following changes makes at least one test fail: an unfiltered `next` parameter, a missing CSRF header, a missing role check on `/org`, ignoring a `401` received during use.

End-to-end check, with the real backend on a temporary database and Vite running:
- through the proxy: login `204` with an `httpOnly` cookie, `/users/me` authenticated by cookie, logout without CSRF `403`, with CSRF `204`, then `401`
- real Firefox screenshots of the login page and of both scopes, for a user with the analyst role

### 12. What comes next

Stage 2 is described below. Next up:
- **Stage 3, Organization**: security events and the audit log, with the existing filters and pagination, plus user administration
- **Stage 4**: dashboards with cards and charts

## Stage 2: My account

### 13. What was built

The backend got two endpoints (details in `docs/01-backend-foundation.md`, section "My Account API - Phase 1"):
- `GET /users/me/activity`: the security events about one's own account
- `DELETE /users/me/sessions`: signing out of the other devices

The frontend has three real pages in the "My account" scope.

### 14. Overview

A security summary sits above the profile:
- **Active sessions**, with a link to manage them
- **Previous sign-in**: when and from which IP. The newest sign-in is the current session itself, so the one before it is shown: if the user does not recognize it, the account may be compromised
- **Alerts, last 30 days**: the warnings and incidents. A single page of 50 is read; when there are more, the number shows as "50+"

Below the summary are the latest 5 alerts and a link to the activity page, filtered to alerts. If one of the requests fails, only that figure shows as "Unavailable"; the rest of the page works.

### 15. My sessions

- the session in this browser comes first, marked "This session", with a "Sign out" button
- each session shows the device, the IP, when it started and when it expires
- the other sessions can be ended one by one or all at once; both actions ask for confirmation in the page, without dialogs
- if a session had already ended (`404`), the page says so and reloads the list

The device is inferred from `User-Agent` (for example "Firefox on Linux", "Chrome on Android"). The header is sent by the client and can be forged, so it is only a hint; the full string appears on hover. Unknown clients, such as scripts, show as "Unknown device".

The "End session" buttons repeat on every row, so each one is linked to the device name through `aria-describedby`, for screen readers.

### 16. My activity

- a table with the event, severity, IP and date; the relative date appears on hover
- an "All" / "Alerts only" filter, kept in the address (`/me/activity?filter=alerts`), so the link from Overview opens the alerts directly; an unknown value is ignored
- older pages load on demand, with the cursor returned by the API

Events are described by type, in the interface language. Severity always appears as an icon and a word, never as color alone.

### 17. New components

- `SeverityBadge`: the severity with an icon, text and the theme's severity colors; it will be reused in the Organization scope
- `ActivityTable`: the event table, used in Overview and in Activity
- `lib/format.ts`: absolute and relative dates ("5 minutes ago", "in 25 minutes"), in the interface language; after 30 days the exact date is shown

### 18. Local validation

- eslint -> no problems
- tsc -> no errors
- vitest -> 83 passed
- build -> successful

The new tests cover: device recognition, relative date formatting, the order and content of sessions, ending a session with confirmation and cancellation, a session that had already ended, an error while ending, ending the other sessions, signing out from the page, event descriptions, the alerts filter and keeping it in the address, pagination, empty states, the Overview summary, and the behavior when a request fails.

Reverse check: each of the following changes makes at least one test fail: the current session not brought first, pagination without the cursor, a missing "+" when there is more than one page of alerts, an alerts filter without severities, showing the current session as the "previous sign-in".

End-to-end check, with the real backend on a temporary database and Vite running:
- through the proxy: the personal history contains the successful and failed sign-ins, `user_id` as a parameter gets `422`, signing out of the other devices without CSRF `403`, with CSRF `200`, with the current session kept and an `OTHER_SESSIONS_REVOKED` audit log
- real Firefox screenshots of the three pages in the dark theme, and of the sessions page in the light theme; afterwards, the alerts table in Overview was stretched to full width, to line up with the summary

The `baseUrl` option was removed from `tsconfig.json` and `tsconfig.app.json`: TypeScript 6, used by VS Code, flags it as deprecated (an error), and since TypeScript 4.1 the `@/*` alias in `paths` works without it. The project was checked with both TypeScript 5.9 and TypeScript 6.

The JavaScript bundle is about 564 KB. Splitting it by page is left for stage 3, when the Organization pages exist.

### 19. Layout adjustment: centered content

On wide monitors, the content stuck to the sidebar and the right half of the screen stayed empty. All pages now sit in a single column of at most 1024 px (`max-w-5xl`), centered in the space next to the sidebar. The width is the same on every page, so the title does not move when navigating; pages no longer set their own widths.

The space above the content grew to 48 px on large screens (32 px on phones), and the space below to 48 px.

## Organization - PR 1 (backend)

### 20. Actions received in My activity

The backend now records the target of administrative actions, and the personal history also includes actions taken on the account, marked `as_target: true`. Without a frontend change, the affected user would have seen the actor's text ("You changed a user's role").

`ActivityTable` uses the new `eventsAsTarget` strings for these items:
- "Your role was changed"
- "Your account was reactivated" / "Your account was deactivated"
- "An administrator ended your sessions"

The types that can be received are listed in `ACCOUNT_ACTION_TYPES` (`features/account/api.ts`). The IP address of these items comes back `null` from the API (it is the operator's), so the column shows "—".

Validation: eslint, tsc, vitest (84 passed), build. Reverse check: ignoring the `as_target` field makes the new test fail.

## Account containment (backend)

### 21. The locked account

The backend can lock an account temporarily. The frontend handles two new situations:
- at login, a `403` with the `detail` `Account temporarily locked` shows "This account is temporarily locked for security reasons. Contact an administrator.", separate from the message for a deactivated account; both responses have the same status, so they are told apart by `detail` (`isAccountLockedError()` in `features/auth/api.ts`)
- a session refused with the same response leads to `/login?reason=locked`, with the same message

My activity shows the new types: "Your account was temporarily locked" / "Your account was unlocked" for the affected account, and "You temporarily locked an account" / "You unlocked an account" for the operator. `User` has the `locked_until` field.

Validation: eslint, tsc, vitest (86 passed), build, `npm audit`. Reverse check: ignoring `detail` on a `403` makes the new tests fail. Real Firefox screenshots, in both themes, of the login page for a locked account and of the My activity page after a lock and an unlock.

## Stage 3: Organization - Events and Audit

### 22. What was built

The first two pages of the Organization scope, for `admin`, `owner` and `security_analyst`:
- Security events (`/org/events`), on `GET /security/events`
- Audit log (`/org/audit`), on `GET /admin/audit-logs`

Both use the same components: the filter bar, the table and the details panel.

### 23. The filters

- **Time range**: last hour, 24 hours, 7 days (default), 30 days, all. The start of the range is computed when the first page loads; later pages keep it, so "Load more" does not shift the window.
- **Severity** (events only): buttons that can be combined.
- **Types**: a menu with checkboxes, which stays open while several types are picked.
- **Search**: an exact email or IP address, in a single field. An IPv4 address or any value with `:` (IPv6) goes to the `ip_address` filter, everything else to `email`. The search runs on Enter or on the search button, not on every keystroke.
- **Account / Target**: `user_id` and `target_user_id`, shown as removable chips; they come from links or from the details panel.

Every filter is kept in the address (`range`, `type`, `severity`, `q`, `user`, `target`), so a filtered view can be shared as a link. Invalid values in the address are ignored; default values are left out of the address. A filter the API rejects (`422`, for example a malformed IP address) has its own message.

### 24. The table and the details

The columns: time, event, severity (events only), account, IP address. Events are described neutrally ("Role changed", "Account temporarily locked"), not in the second person as in My activity; the strings are in `orgEvents.types` and `audit.types`.

A click anywhere on a row opens the details; from the keyboard, the event description is a button. The details are in a side panel (Radix Dialog: focus stays in the panel, Escape closes it, focus returns to the row). The panel shows the account (email and id), the target, the IP address, the source, the message for operators, and actions that narrow the list: "Only this account", "Only this target", "Only this IP address". A failed attempt that names only an email narrows by email.

### 25. Reloading and auditing

Every load of these pages is audited by the backend. That is why the lists do not reload on their own when the window regains focus (`refetchOnWindowFocus: false`); the page has a "Refresh" button, which goes back to the first page, with the range measured from that moment. The audit page says explicitly that viewing it is recorded too.

### 26. New shared components

- `PagedResults`: the loading, error (with retry) and empty states, plus "Load more", for any list read with a cursor; also used by My activity
- `SegmentedControl`: mutually exclusive buttons, used for the time range and for the My activity filter; on narrow screens they wrap to the next line
- `ui/sheet.tsx`: the side panel, on Radix Dialog
- `features/org`: the API client, the address filters, the hooks, the filter bar, the table and the details

The "Load more", "Loading…" and "You reached the start of your history." strings moved from `activity` to `paging`.

### 27. Splitting the bundle

The organization pages load on demand (`React.lazy` in `pages/lazy.ts`, with a `Suspense` in `AppShell`). Their code (about 21 KB) no longer reaches regular users, and the Vite warning for chunks over 500 KB is gone: the app now has a main chunk (~311 KB) and one with the shared libraries (~262 KB). The total initial load stays nearly the same, because the libraries (React, Radix, i18next) dominate.

### 28. Local validation

- eslint -> no problems
- tsc (5.9 and 6.0) -> no errors
- vitest -> 111 passed
- build -> successful, without the size warning
- npm audit -> 0 vulnerabilities

The new tests cover: the neutral descriptions, the default range and "All", severity and types (with the address updated), reading the filters from a link, searching by email and by IPv6 with focus kept, removing chips and resetting, the details panel and its actions, opening with the mouse and closing with Escape, pagination with the same range, refreshing, the invalid filter, the two empty states, the audit log (no severity, missing message, the target filter) and the filter functions.

Reverse check: each of the following changes makes at least one test fail: the range recomputed on every page, an IP searched as an email, the target action filtering the actor, unknown types accepted from the address, the default range written into the address, the types menu closing at the first pick, the invalid filter message ignored, a search field that does not follow outside changes, rows that do not open, an empty-list text that ignores the filters.

A test caught a real problem: the search field was remounted on every search (through `key`) and lost focus after Enter. It now syncs its value during render, without remounting.

End-to-end check, with the real backend on a temporary database and Vite running: data created through the API (successful and failed sign-ins, brute force, a role change, a lock and an unlock, closing sessions, a deactivation) and a few failed sign-ins inserted directly, with different addresses. Real Firefox screenshots, as an analyst, in both themes: the events, the audit log, the open details panel, active filters and phone width (390 px). After the screenshots: the "Account" and "IP address" headers no longer use the monospace font, and the time range buttons wrap to the next line on phones instead of overflowing the screen.

Observation: the lists were ordered by `id` (the order of recording), not by `created_at`, so events inserted with a past date appeared above newer ones. Fixed in the backend (Event Ordering - Phase 1, `docs/01`): the lists are ordered by the moment of the event, and the frontend did not change.

### 29. Scrollbars

On phones, a white scrollbar appeared under the sidebar's horizontal menu, even in the dark theme. `color-scheme` was already set, but some browsers (among them headless Firefox, used for the screenshots) ignore it for scrollbars. `:root` now has a `scrollbar-color` from the theme colors (`--muted-foreground` at 45%, on a transparent track), and the horizontal menu has a thin scrollbar (`scrollbar-width: thin`). The screenshots at 390 px, in both themes, show a discreet scrollbar in the theme colors.

## Stage 4: Organization - Users

### 30. What was built

The Users page of the Organization scope, for `admin`, `owner` and `security_analyst`, on the API from Organization API - Phase 1 and Account Containment - Phase 1. No backend change was needed.

- the list (`/org/users`), on `GET /admin/users`
- one page per account (`/org/users/:id`), on `GET /admin/users/{id}` and `GET /admin/users/{id}/activity`, with the actions the signed-in operator may take

Both load on demand, like the other organization pages.

### 31. The list

- **Search**: a substring of the username or email, applied on Enter or on the search button. The search field is now a shared component (`SearchForm`), also used by the logs.
- **Roles**: a menu with checkboxes, like the event types.
- **State**: All, Active, Locked, Deactivated. The API filters `is_active` and `locked` separately; "Active" asks for both `is_active=true` and `locked=false`, so a locked account never shows as active.

The filters are kept in the address (`q`, `role`, `state`), and invalid values are ignored. Each row shows the username, email, role, state and member-since date; a click anywhere on the row opens the account, and from the keyboard the username is a link. On phones, the state moves under the email and the date column is hidden, so what matters stays in view without scrolling the table sideways. The list ends with "That is every account." instead of the history wording, through a new `end` option of `PagedResults`.

### 32. The account page

The page shows the username, the email, the state (with the lock's end time while it is in force), the id, role, member-since date and last change, then the actions and the account's history.

The history is the set the account's owner sees in My activity, with the operator details: the same table and details panel as the logs, with neutral descriptions and the actor's account in its own column. The back link returns to the list as it was filtered, through the router's location state.

An unknown account (`404`) and an address that is not an account id show "Account not found".

### 33. Actions

The page offers only what the operator may do, mirroring the API's rules in `features/org/permissions.ts` (the API still decides):

| Operator | Actions |
| --- | --- |
| `security_analyst` | End sessions, Lock temporarily |
| `admin` | the above, Unlock (while locked), Deactivate / Reactivate (not on another admin) |
| `owner` | everything, including Change the role |

On one's own account or on the owner's, no actions appear, and a sentence explains why. Each action opens a step in the page, not a dialog, that names its effect and asks for confirmation, as the session actions in My account do:
- **End sessions** and **Lock temporarily** ask for a reason, 3-500 characters after trimming, the API's bounds; the confirmation stays off until the reason fits
- **Lock temporarily** offers 1 hour, 24 hours (default) or 7 days
- **Change the role** offers user, security analyst or administrator; choosing the current role keeps the confirmation off

A change the API answers with the account (lock, unlock, status, role) replaces the cached account, so the page updates without reading it again, which would add another audited read. The account's history, the user list and both logs are marked stale. A refused action (`403`, for example a role changed meanwhile by someone else) says so and reads the account again.

### 34. Links from the logs

The details panel of an event or audit record now has "Open the account" and "Open the target", which lead to the account pages. In an account's history, the link to the account already shown is left out. The links sit on their own row, with an arrow, apart from the actions that narrow the list.

### 35. Local validation

- eslint -> no problems
- tsc (5.9 and 6.0) -> no errors
- vitest -> 147 passed
- build -> successful; the two pages are separate chunks (about 5 KB and 10 KB)
- npm audit -> 0 vulnerabilities

The new tests cover: the list's rows and states (locked, deactivated, an expired lock not shown), search with focus kept, roles and states sent to the API and kept in the address, a shared link with invalid values, reset, the empty state, opening an account from a row and going back to the filtered list, pagination; on the account page: the profile and the neutral history, the actions offered to each role (including a locked account for the analyst, an admin on another admin, one's own account and the owner's), locking with a duration and a trimmed reason, ending sessions, cancelling, deactivating and reactivating, unlocking, changing the role, a refused action, an unknown account and an invalid address, and the account links in both the logs and the history; the address filters and the permission rules as units.

Reverse check: each of the following changes makes at least one test fail: an analyst offered Unlock, a lock that ignores the chosen duration, "Active" counting locked accounts, a link to the account already shown (actor or target), a reason without a minimum, an action that reads the account again instead of using the answer, a back link that forgets the filters.

End-to-end check, with the real backend on a temporary database and Vite running: ten accounts, with sessions ended and a lock by the analyst, a deactivation by an admin and a role change by the owner. Through the proxy, the API refused an analyst's unlock, a lock on the owner and an admin deactivating another admin (`403`), the state filters returned the expected accounts, and a cookie action without the CSRF header got `403`, with it `200`. Every list, account and history read appeared in the audit log, with the target for account reads, and no `ADMIN_ACCESS` security event was created. Real Firefox screenshots, in both themes: the list (filtered too), a locked account as an admin, the lock form as an analyst, the event panel with the account links, and phone width (390 px). After the screenshots: the state moved under the email on phones, and the account links got their own row and an arrow.


## Stage 5: Organization - Overview

### 36. What was built

The Overview page of the Organization scope (`/org`), for `admin`, `owner` and `security_analyst`, on `GET /security/summary` from Organization API - Phase 1 and on `GET /security/events`. It replaces the placeholder, loads on demand like the other organization pages, and completes the scope. No backend change was needed.

### 37. The counts

Six tiles, each a link to the records behind it:

| Tile | Headline | Beside it | Opens |
| --- | --- | --- | --- |
| Incidents, Warnings, Informational events | count over 24 hours | count over 7 days | the event log, that severity, 24 hours |
| Failed sign-ins | count over 24 hours | emails locked now by brute-force protection | the event log, failed sign-ins, 24 hours |
| Locked accounts | accounts an operator locked, lock in force | | the user list, Locked |
| Deactivated accounts | count | out of all accounts | the user list, Deactivated |

The 24-hour and 7-day counts are shown together rather than behind a switch: the API gives failed sign-ins and their sources over 24 hours only, so a switch would change half the page. Severity tiles carry the severity icon; the numbers stay in the text color, never the severity color. Numbers are formatted for the interface language through a new `number` formatter in `lib/format.ts`. Links are built with the pages' own address writers (`writeLogFilters`, `writeUserFilters`), so they stay in step with what those pages read.

### 38. Latest incidents and failed sign-in sources

- **Latest incidents:** the 5 newest incidents of the last 7 days, in the log table, with the same details panel and account links as the event log, and a link to every incident. The request asks the API for a page of 5 (`limit`, new in `fetchSecurityEvents`). Showing them is audited, like any read of the event log, and the section says so.
- **Failed sign-in sources:** the up to 5 addresses with the most failed sign-ins over 24 hours, as bars scaled to the largest, in the accent color, with the count written beside each. Each row opens the failed sign-ins from that address.

### 39. Reloading

The counts are not audited, but they reload only with the incidents, on the page's refresh button, never on window focus, so the two always describe the same moment and the audit log gains no automatic entries. The header shows when the counts were computed (`generated_at`, on the database clock). The incidents query sits under the event log's key, so whatever refreshes the log (an account action, the log's own refresh) refreshes it too.

If the counts fail to load, the tiles give way to an error with a retry, the sources say "Unavailable", and the incidents stay; a failed incident list has its own retry.

### 40. Local validation

- eslint -> no problems
- tsc -> no errors
- vitest -> 153 passed
- build -> successful; the page is its own chunk (about 8 KB)
- npm audit -> 0 vulnerabilities

The new tests cover: the six tiles with their 24-hour and 7-day counts, plural texts and links; the latest incidents with the request sent (severity, page size, a 7-day window), the details panel and its account links; the sources ranked with their links and bar widths; the empty states; a failed summary with the incidents kept and a working retry; and the refresh reloading both.

Reverse check: each of the following changes makes at least one test fail: a severity tile linking without its severity, the incident list without a page size, the incident list without its 7-day window, bars not scaled to the largest, and a refresh that reloads only the counts.

End-to-end check, with the real backend on a temporary database and Vite running: seven accounts, a brute-force attack (five failed sign-ins), a lock and a deactivation through the API as the owner, and failed sign-ins from four more addresses (IPv4 and IPv6) and older events added in the database. The page showed the counts the API returned, and each visit added one `security_events_viewed` audit entry with its filters (`limit=5, severity=['incident'], since=...`) and nothing for the counts. Real Firefox screenshots in both themes and at phone width (390 px). After the screenshots, the "Updated" line was aligned to the left on phones, under the refresh button.

## Stage 6: Detection alerts

### 41. The new event types

The backend's detection rules raise three new security event types, which the frontend now names in both languages and offers in the event log's type filter:

| Type | Event log | My activity |
| --- | --- | --- |
| `password_spray_detected` | Password spray detected | (names no account, so it never appears there) |
| `dormant_account_login` | Sign-in to a long-dormant account | Sign-in after a long period of inactivity |
| `privileged_role_granted` | Privileged role granted | You granted a privileged role / You were granted a privileged role |

`privileged_role_granted` joins the account action types, so the account that received the role reads it in the second person, as with a role change. The technique each detection stands for (`mitre_technique`) is shown in a later stage.

### 42. Local validation

- eslint, tsc -> no problems
- vitest -> 153 passed; the My activity test now includes the new alerts, as actor and as target
- build -> successful

### 43. API key events

The backend's ingestion stage adds security events for creating and revoking an API key, and audit entries for those and for listing the keys. The frontend names them in both languages ("API key created", "API key revoked", "API keys viewed"), and the owner reads "You created an API key" in My activity. The page for managing keys comes in a later stage. vitest -> 153 passed.


### 44. Unfamiliar sign-in alert

The backend's new detection rule raises `unfamiliar_sign_in` on the account that signed in. The frontend names it in both languages and offers it in the event log's type filter:

| Type | Event log | My activity |
| --- | --- | --- |
| `unfamiliar_sign_in` | Sign-in from an unfamiliar network and device | Sign-in from a new network on a new device |

The event log text is neutral, as for every organization view; the account's own activity speaks to it. The My activity test now includes the new alert. eslint and tsc report no problems, vitest 153 passed, the build succeeds and `npm audit` finds 0 vulnerabilities.

## Stage 7: API keys and MITRE ATT&CK

### 45. The API keys page

`/org/api-keys` (`OrgApiKeysPage`, loaded on demand like the other organization pages), linked from the organization menu as "API keys":

- Every operator sees the keys: name, prefix (`sck_<prefix>_…`), source, state, expiry and last use. The state is a word with a color, never color alone: active, expired (past `expires_at`) or revoked, computed as the API decides it (`keyState` in `features/org/api-keys.ts`). On phones, source and state move under the name; expiry and last use appear from medium widths.
- Only the owner sees "New key" and the revoke buttons (`canManageApiKeys` in `permissions.ts`); the others read "Only the organization owner creates and revokes keys." The API still decides.
- Listing keys is audited (`API_KEYS_VIEWED`), so the list does not reload on window focus; the page has a refresh button.

### 46. Issuing a key and showing it once

"New key" opens a form in the page, like the account actions: a name (3-100 characters), a source and a lifetime (30 days, 90 days or 1 year, 90 by default). The source is checked as the API checks it, after trimming and lowercasing: 2-50 letters, digits and `_ . -`, starting with a letter or digit, and not `backend` or `detection`, with the reason shown under the field. The API still decides; a refused key (422) is explained and the form stays.

The answer holds the full key. It is shown once, in a panel in the page: the key, a copy button (the Clipboard API, with a fallback message to copy it by hand), how a system sends it (`Authorization: Bearer sck_…`), and the warning that it will not be shown again because only a hash is kept. "I have saved the key" closes the panel.

The key lives only in the page's state. It is never in the address, in browser storage or in the query cache: the creating mutation is reset as soon as it succeeds, with `gcTime: 0`, so TanStack Query drops its answer at once instead of keeping it for five minutes. A test checks all four places.

Revoking asks for confirmation in the page ("Systems that use it will no longer be able to send events. Revoking cannot be undone.") and is offered only on active keys. Creating or revoking refreshes the key list and both logs.

The confirmation form of the account actions moved to `features/org/ActionForm.tsx` (`ActionForm`, `ConfirmForm`, `ActionNotice`), shared by both pages, and the overview's load-failure block to `components/LoadFailed.tsx`.

### 47. MITRE ATT&CK techniques

Security events now carry `mitre_technique` and `occurred_at` from the API.

- In every table of security events (the event log, an account's history, the overview's latest incidents), a detection shows a small badge with its technique id beside its description (`LogTable` gained an `annotate` column slot). The technique's name is in the tooltip, and screen readers hear "MITRE ATT&CK technique T1110.003".
- The details panel shows the technique id and name, and a link to its page on attack.mitre.org, opened in a new tab with `rel="noopener noreferrer"`: the new page cannot reach back to SentinelCore, and MITRE is not told which address it came from. The link is built only from a valid technique id (`T1234` or `T1234.567`, `features/org/mitre.ts`); anything else gives no link.
- For an alert about an event reported late, the panel also shows when the event happened ("Happened at"), beside the time the alert was raised.
- Technique names stay in English in both languages: they are MITRE's proper names.

The fields shared by the three pages' details panels are now built in one place (`securityEventFields` in `features/org/security-event-fields.tsx`).

### 48. Local validation

- eslint -> no problems
- tsc -> no errors
- vitest -> 171 passed
- build -> successful; the API keys page is its own chunk (about 9.5 KB)
- npm audit -> 0 vulnerabilities

The new tests cover: the list for an admin and an analyst (states, last use, no actions); creating a key as the owner, with the request body (trimmed name, lowercased source, lifetime), the key shown once, copied to the clipboard, absent from the address, browser storage, query and mutation caches, and gone once saved; the name and source checks; a refused key; revoking only active keys, after confirmation, with cancel; an empty list; the technique badge in the event log, an account's history and the overview; the details link and its `rel`; the time of a late alert's event; the link built only from valid ids; the menu link.

Reverse check: each of the following changes makes at least one test fail: admins allowed to manage keys, the creating mutation not reset, the mutation kept in the cache, a revoked key counted as active, reserved sources allowed, any value turned into a link, the link sending a referrer, the event time always shown, the badge not rendered, revoke offered on every key, the page letting every operator manage keys, and the source sent as typed (12 of 12).

End-to-end check, with the real backend on a temporary database and Vite running: an owner and an analyst; three keys (one used through ingestion, one revoked, one expired); a password spray and a sign-in from an unfamiliar network and device reported through ingestion, the latter three hours late, and a brute-force attack through the real sign-in. Headless Firefox took eleven screenshots: the keys page as the owner (light, dark, phone width), as the analyst (phone width, dark), a key created through the page's own form and shown once (light; dark at phone width), the event log with its badges (light, dark), an alert's details (light; dark at phone width), and the overview. On each, a check run in the page confirmed the theme, the expected texts, no horizontal scrolling at phone width, the badges `T1110.001`, `T1110.003` and `T1078`, the details' "Happened at", link and `rel`, and a key of the right shape in the creation panel. The audit log recorded both keys created through the page and one `API_KEYS_VIEWED` per load of the list.

## Stage 8: Visual identity

### 49. Purpose of the stage

The shell was shadcn/ui's sidebar as it ships: a square with initials, a plain list, the same type everywhere. Another application built with the same tools looked the same. Four directions were drawn on the real overview; the chosen one combines a threat status band, typography with a logomark, data visuals and a command palette. This stage brings the identity and the palette; the band and the data visuals need new counts from the API and come next.

### 50. Logomark, type and page headers

- `components/brand/Logomark.tsx`: a shield with an eye, drawn in the current text color, and the "SENTINEL core" wordmark (condensed capitals, a mono suffix). The favicon uses the same mark.
- IBM Plex Sans Condensed (`@fontsource/ibm-plex-sans-condensed`, weights 600 and 700) for titles and headline numbers, as the `font-display` token; a `label-mono` utility in `index.css` for the small uppercase captions.
- `PageHeader` gives every page the same title block: where the page sits ("ORGANIZAȚIA / 02 EVENIMENTE DE SECURITATE"), a condensed title, the description and the page's buttons. An account's page sits under Users.
- The pages, their numbers and their scopes are defined once (`components/layout/navigation.ts`) and read by the sidebar, the page headers and the palette.
- The overview's tiles and the personal overview's figures use the condensed numbers and mono captions; section titles use the display face.

### 51. Sidebar

- The wordmark, a search button that opens the palette, the scope switch as two mono tabs, and a numbered navigation (`01 Prezentare`).
- Beside Security events, the number of incidents in the last 24 hours, from the summary counts (not audited), with its full meaning for screen readers. It loads only in the organization scope, so a user's personal pages do not ask for organization counts.
- The sidebar is wider (`w-72`), so the button and the badge fit; long names are truncated instead of scrolling the menu sideways.

### 52. Command palette

`Ctrl+K` (or `Cmd+K`), or the sidebar button, opens `CommandPalette`: a Radix Dialog holding an ARIA combobox. Focus stays in the input; the arrow keys move through the list and wrap at the ends, `aria-activedescendant` tells screen readers which command is highlighted, Enter runs it and Escape closes.

- **Pages:** the user's own pages, and the organization's for operators. Matching ignores case and diacritics, so "activitate" finds "Activitatea mea".
- **Search (operators):** what was typed opens the user list or the event log filtered by it (the event log matches an exact email or IP).
- **Actions:** the three themes, the two languages, signing out.

The palette makes no API request of its own: the page it opens loads, and audits, the records as usual.

### 53. Local validation

- eslint -> no problems
- tsc -> no errors
- vitest -> 181 passed
- build -> successful, no warnings; the condensed font adds about 20 KB per weight in the Latin subset, loaded only when used
- npm audit -> 0 vulnerabilities

The new tests cover: opening the palette with Ctrl+K and from the sidebar, closing it with Escape; matching without diacritics and opening with Enter; the arrow keys and `aria-activedescendant`; a user seeing only their own pages and no organization search; an operator's searches opening the filtered user list and event log without any request while typing; changing the theme and the language; the incident badge and its screen reader text; no badge without incidents and no counts loaded on personal pages; the page headers, an account's page included.

Reverse check: each of the following changes makes at least one test fail: no Ctrl+K listener, diacritics kept in matching, organization search or pages offered to a user, arrows that stop at the ends, no `aria-activedescendant`, the palette left open after a command, Enter doing nothing, the event search dropping the query, the counts loaded on every page, the badge without its screen reader text, an account's page not placed under Users, and unpadded page numbers (13 of 13).

End-to-end check, with the real backend on a temporary database seeded by the attack simulator, the owner created from the command line, and Vite running: headless Firefox took screenshots of the organization overview (dark, light, dark and light at phone width), the event log with the palette open on an IP search, the personal overview (light), the palette at phone width (light), an account's page (dark) and the user list at phone width (light). A check run in each page confirmed the theme, the header's location line, the condensed font loaded, the wordmark, the badge (11 incidents), the palette's commands and no horizontal scrolling at phone width. The first round of screenshots showed the search button and the badge cut off in a 256 px sidebar; the sidebar was widened and the names truncated, and a second round confirmed the fix.

## Stage 9: Security trends

### 54. Threat status band

`ThreatBand` (`features/org/ThreatBand.tsx`) sits above every organization page, under a top edge in the level's color: the level ("Incident activ", "Atenție", "Calm") with a dot, the last 24 hours as 24 cells colored by the most severe event of each hour (the counts in each cell's tooltip), and the latest detection's technique and time, linked to the event log filtered by that technique's types. Screen readers get the 24-hour totals as text; the cells are decorative. It reads the summary, shared with the overview and the sidebar badge, and stays hidden until the counts arrive or when they fail, where the overview offers the retry.

### 55. Trends on the overview

- The three severity tiles show their last 7 days as small bars, scaled to the busiest day; days without events show a short bar in the border color.
- The latest incidents are a timeline: time, a dot on a line, the description with its technique, the account and address. Each entry opens the details panel, as the table rows did.
- "Tehnici detectate" lists the alerts per technique over 7 days as bars, with the technique's MITRE name; each opens the alerts behind it.
- A `time` formatter joins the date formatters.

### 56. Local validation

- eslint -> no problems
- tsc -> no errors
- vitest -> 188 passed
- build -> successful, no warnings
- npm audit -> 0 vulnerabilities

The new tests cover: the band's level, its screen reader totals, the color of each hour and its tooltip, and the latest detection's link; the calm and warning states; no band and no request for the counts on personal pages; the 7-day bars and their scale; the techniques, their order, names, links and bars, and their empty state; the timeline opening the details; no band when the counts fail.

Reverse check: each of the following changes makes at least one test fail: the band shown on personal pages, warnings drawn over incidents, the band's link without the technique's types, the wrong color for a warning, bars not scaled to the busiest day, a technique's link without its types, and timeline entries that open nothing (7 of 7).

End-to-end check, with the real backend on a temporary database seeded by the attack simulator: headless Firefox took the overview (dark and light, desktop and phone width) and the event log (dark, and light at phone width). Checks in the page confirmed the band on both pages (level, 24 cells, the latest detection linked to its alerts), 21 bars on the tiles, four techniques, five timeline entries and no horizontal scrolling at phone width. The light screenshots showed empty cells and days nearly invisible against the background; they now use the border color, and a second round confirmed it.

## Stage 10: Invitations

### 57. Invitations on the Users page

The Users page opens with an "Invitații" section above the accounts, which now have their own "Conturi" heading.

- **Open invitations** are listed in a table: email, token prefix (`sci_<prefix>_…`), role, state and when the invitation expires. The used, revoked and expired ones are folded into a "History" section with their count; an accepted invitation links to the new account.
- **Inviting** follows the API keys page: an in-page form (email and role, as a segmented control), then a panel with the link, shown once, a copy button and "Am trimis link-ul". The link lives in the page's state only. The mutation is reset and kept with `gcTime: 0`, so the token is not left in the address, browser storage or the query and mutation caches.
- **Roles** mirror the API (`features/org/invitations.ts`): an admin offers `user` and `security_analyst`, the owner `admin` too, and an analyst only reads the list. Revoking is offered on open invitations whose role the reader may offer, after a confirmation step.
- States are computed as of the list's last load (`dataUpdatedAt`), so they hold still between renders. The Refresh button reloads both the accounts and the invitations.
- Listing invitations is audited by the API, so the list reloads only on request, like the API keys.

### 58. The public invitation page

`/invite` (`pages/AcceptInvitationPage.tsx`) is public, beside `/login`, and shares its frame (`components/layout/PublicShell.tsx`).

- The link carries the token in the fragment (`/invite#sci_…`, `features/auth/invitation-link.ts`). Browsers never send the fragment to a server. The page reads it once, then replaces the history entry without it, so it leaves the address bar and the back history.
- The token goes to `POST /auth/invitations/preview` in the request body. The query is not keyed by the token and is dropped when the page closes. Every unusable token, missing, wrong, used, revoked or expired, gets the same message.
- The form shows the email, role and expiry, then asks for a username, a password and the password again. The username and password rules mirror the API's (3 to 50 characters from `A-Z a-z 0-9 _ . -`; 12 to 128 characters, counted by code point as Python counts them). A hidden field holds the email with `autocomplete="username"`, so a password manager files the new password under the email used to sign in, not under the username.
- After `POST /auth/invitations/accept`, the page opens `/login` with the email in the router's state, not in the address. The login page shows "Contul a fost creat" and fills in the email. The API does not sign the person in, so the first sign-in goes through the usual checks.
- A taken username asks for another; an invitation that stopped working meanwhile shows the same "not valid" message.

### 59. Event types

The interface now names `invitation_created` and `invitation_revoked` (security events, personal and organization views) and `invitations_viewed` (audit log), added by the backend with invitations.

### 60. Local validation

- eslint -> no problems
- tsc -> no errors
- vitest -> 209 passed
- build -> successful, no warnings
- npm audit -> 0 vulnerabilities

The new tests cover: the invitation states and who may offer and revoke each role; links with the token in the fragment only; the username and password rules, emoji included; an analyst's read-only view with the history folded and the accepted account linked; an admin inviting with a normalized email and an everyday role, the link shown once and kept nowhere else; the owner offered the admin role; an email that already has an account; revoking only what one may offer; a link without a token not reaching the API; the same answer for every invalid token; the token sent in the body and cleared from the address; a short or mismatched password refused; the account created and sign-in opened with the email filled in and the password focused; a taken username; an invitation that stopped working before acceptance.

Reverse check: each of the following changes makes at least one test fail: the token in the link's query string, the mutation not reset, no `gcTime: 0`, an admin offered or revoking the admin role, acceptance ignored when an invitation has also expired, the fragment left in the address, the token in the preview's URL, the repeated password not compared, short passwords allowed, passwords counted in UTF-16 units, the username pattern dropped, a failed acceptance not shown as invalid, the email passed to `/login` in the address, the login page ignoring it, used invitations listed as open, the email not normalized, no message for an existing account, and the invite button shown to analysts (19 of 19).

End-to-end check, with the real backend on a temporary database, the owner created from the command line and invitations created, accepted and revoked through the API: headless Firefox took the Users page with the history open (dark and light, and dark at phone width), the invite form (dark), the link panel after inviting (light), the public page (dark, and light at phone width), an invalid token, the sign-in page after accepting, and the same link opened again. Checks in the page confirmed the theme, the fragment cleared from the address, the "not valid" message for both the invalid and the used token, `/login` with the success message after accepting, and no horizontal scrolling at phone width.

## Stage 11: Organization field

### 61. Choosing the organization

Since the backend gave every account and API key an organization, the owner names one when inviting or creating a key. `OrganizationField` (`features/org/OrganizationField.tsx`) is a native select of the organizations that are not suspended, read from `GET /admin/organizations`; with only one, it is chosen already. It appears in the API key form and, for the owner only, in the invitation form; an admin invites into their own organization and never sees it. Confirming waits for a choice. The organizations page, filters and columns come with the frontend stage of this work.

### 62. Local validation

- eslint -> no problems
- tsc -> no errors
- vitest -> 210 passed
- build -> successful, no warnings
- npm audit -> 0 vulnerabilities

The tests cover the only organization chosen already and sent, the choice among several with suspended ones left out and confirmation waiting for it, the owner's invitation sending the organization, and the admin's form without the field.

Reverse check: each of the following changes makes at least one test fail: no automatic choice, suspended organizations offered, a key form valid without an organization, the owner's invitation or the key request without it, and the field shown to admins (6 of 6).

End-to-end check: on the demo, headless Firefox took the API key form (dark) and the invitation form (light, and dark at phone width) with "Acme" chosen; no horizontal scrolling at phone width.

## Stage 12: Several organizations

### 63. Names of the scope

The organization scope is named after the reader: "Platformă" for the platform owner, the organization's name for a member, read from `GET /users/me` (`scopeName` in `components/layout/navigation.ts`). The name shows in the scope switch, the page headers, the command palette and, beside the role, in the account menu.

### 64. The owner's choice of organization

- One picker in the sidebar, for the owner only, sets the organization of every organization page at once: overview, band, incident badge, both logs, users, invitations and API keys. The queries send it as `organization_id` and keep it in their keys. Members never send it, even with one in the address: the API would answer `403`.
- The address holds the choice (`?org=3`, or `?org=all`), so a link opens the same view and Back restores the previous one. Pages rewrite their address with each filter, and links inside the pages do not carry it, so `OrganizationViewProvider` (`features/org/OrganizationViewProvider.tsx`) also remembers the last choice seen, reads it while the address holds none, and puts it back. Without that, every such step would load every organization's records once in between, and each of those loads is audited in each organization it returns.
- Choosing writes only to the address, never to the remembered value first. Navigation updates the address a moment later, and a choice written first would be overwritten by the old address in between, so "all organizations" could not be chosen after one.
- An address naming an organization that does not exist falls back to all of them.
- The organizations list is audited, so it loads once and then only after a change to an organization or on request (`staleTime: Infinity`), not each time the picker, a form or a column asks for it.

### 65. Organization column

While the owner views every organization, the logs, users, invitations and API keys show which organization each row belongs to, or "Platformă" for the platform's own records (`features/org/organization-column.tsx`). With one organization chosen, and for members, the column would repeat one name and is left out. On phones the name moves under the row's main line, as the role and state do.

### 66. Organizations page

`/org/organizations` (`pages/OrgOrganizationsPage.tsx`), for the owner only: the route is behind `RequireOwner` and the menu entry is shown to the owner alone, last, so the other pages keep their numbers for everyone.

- The list shows each organization's name, slug, state (written out, not by color alone), members and creation date.
- Creating one suggests a slug from the name (diacritics and symbols removed) until the slug is edited by hand. The name and slug rules mirror the API's (`features/org/organizations.ts`), so the form says what is wrong before sending; a taken name or slug gets its own message.
- Renaming keeps the slug and waits for a different, valid name.
- Suspending signs out every member at once, so the owner types the organization's slug before the confirmation becomes available. It uses the page's confirmation step, as every other action does, rather than a modal dialog. Reactivating asks for a plain confirmation.
- After each change, the list, both logs and the summary reload.

### 67. Platform overview

For the owner viewing every organization, the overview is "Prezentarea platformei" and adds "Organizații după nivel": each organization and the platform with its level, written out beside its color, and its incidents and warnings over 24 hours, from the summary's new `organizations` field. A suspended organization is marked. Choosing an organization's name opens its view on every page.

### 68. Event types

The interface now names `organization_created`, `organization_renamed`, `organization_suspended` and `organization_reactivated` (security events, personal and organization views) and `organizations_viewed` (audit log).

### 69. Local validation

- eslint -> no problems
- tsc -> no errors
- vitest -> 237 passed
- build -> successful; the organizations page loads on demand as its own chunk
- npm audit -> 0 vulnerabilities
- Gitleaks on `frontend/src` -> no leaks found

The new tests cover: the slug suggested from a name and the name and slug rules; the list with states and members; creating with a suggested slug, then one edited by hand; a slug refused before sending; a taken name; renaming; suspending only once the slug is typed; reactivating; an admin refused the page without loading the list; the scope named "Platformă" for the owner and "Acme" for a member, and the menu entry for the owner only; the picker's options, suspended ones marked; the column shown for every organization and gone after choosing one, with every request, the band's included, naming it; the choice kept through a filter and a menu link, with no request for every organization in between; an unknown organization falling back to all; the platform overview's ranking and opening one organization from it; a member with the organization's name, no picker, no column and no `organization_id` sent.

Reverse check: each of the following changes makes at least one test fail: the choice not put back in the address, no remembered choice while the address has none, members allowed a choice, the column shown with one organization chosen, the user list or the summary ignoring the choice, an unknown organization kept, suspending without typing the slug, the slug not following the name until edited, no owner guard on the page, the menu entry shown to admins, the scope not named after the organization, diacritics kept in the slug, and renaming to the same name (14 of 14). The column check was missed at first, because the test kept looking at the table shown before the choice; it now looks at whichever table is shown.

End-to-end check: on a temporary database, the API ran as `sentinelcore_app`; the owner created Acme, Globex and Initech through the API, people joined by invitation, a brute force against an Acme account raised an incident, two sign-ins failed on unknown emails, and Initech was suspended. Headless Firefox took the platform overview (dark and light, and dark at phone width), the organizations page with the suspension step and the slug typed (dark, and light at phone width), the event log with the organization column (light), the overview with Acme chosen (dark), and an Acme admin's event log (dark), named "Acme", with no picker and no column. The overview ranked Acme (active incident), Globex (warning), the platform and Initech (suspended, calm).


## Stage 13: Security headers

### 70. The console's policy

`security-headers.ts`, beside `vite.config.ts`, holds the headers. The config sends `productionHeaders` from `vite preview`, which serves the build, and `developmentHeaders` from the dev server. The production Content Security Policy:

- `script-src 'self'`: only the bundle's own files run. An injected `<script>`, `onclick=` or `javascript:` link does not. `index.html` has no inline script, and the build adds none.
- `style-src 'self' 'unsafe-inline'`: Radix dialogs and menus add `<style>` elements while they are open (`react-remove-scroll`, through `react-style-singleton`). A nonce would need a server that writes each page. A style cannot run code, and `style={{…}}` goes through the CSS object model, which the policy does not restrict.
- the other directives:
  - `img-src 'self' data:` and `font-src 'self'`;
  - `connect-src 'self'`, since the API is reached through `/api` on the same origin;
  - `object-src 'none'`, `base-uri 'none'` and `form-action 'self'`;
  - `frame-ancestors 'none'`.

Besides the policy, the console sends `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, a `Permissions-Policy` and `Cross-Origin-Opener-Policy: same-origin`. Whatever serves the build in production (nginx, in phase B) must send the same headers.

### 71. Fonts as files

Vite inlines files under 4 kB into the CSS as `data:` URIs. Four Cyrillic subsets of IBM Plex Sans Condensed (weights 600 and 700) were inlined this way. `font-src 'self'` would have blocked them as soon as a name written in Cyrillic needed them. `build.assetsInlineLimit` now keeps fonts as files, so the policy stays as narrow as it is.

### 72. The dev server

The dev server adds the React Refresh preamble as an inline script and reloads the page over a websocket. Its policy therefore allows `'unsafe-inline'` scripts and `ws:` connections; everything else is the production policy. Firefox reported no violation on the dev server either.

### 73. Local validation

- eslint -> no problems
- tsc -> no errors
- vitest -> 243 passed
- build -> successful, with no inline script and no `data:` font
- npm audit -> 0 vulnerabilities
- Gitleaks on `frontend` -> no leaks found

The new tests cover:
- the production policy running only the bundle's own scripts, and closing `object-src`, `base-uri`, `connect-src` and `form-action`;
- inline styles allowed, with nothing else inline and no `eval`;
- no framing in either policy;
- the dev policy relaxing scripts and connections only;
- the dev server and the preview each sending their headers;
- fonts never inlined.

Reverse check: each of the following changes makes at least one test fail (8 of 8):
- inline scripts in production;
- the console framed by its own origin;
- no `object-src`, or no `X-Frame-Options`;
- the dev policy relaxing another directive;
- either server without its headers;
- fonts inlined again.

End-to-end check, on a temporary database filled by the attack simulator, with `vite preview` serving the build under the production policy:
- **Every page, no violation.** Headless Firefox, driven over WebDriver BiDi, signed in through the login page. It opened every page of both scopes, dark and light, at desktop and phone width: the owner's overview, both logs, the users and one user, API keys, organizations with the creation form, the account menu and the 404 page, plus `/login` and `/invite`. Across 58 checks there was no policy violation and no horizontal overflow.
- **The check itself.** A second run with inline styles forbidden blocked the account menu each time it opened (`style-src-elem`, from `react-remove-scroll`). So the check does see violations, and Radix does need inline styles.
- **Framing.** A page on another origin that framed the console got Firefox's refusal.

## Stage 14: API key volume alert

### 74. The new alert in the console

The backend's new alert, `api_key_volume_spike`, is one more security event type (`SECURITY_EVENT_TYPES` in `features/account/api.ts`), so the type filter offers it with no other change. It is labelled "Unusual volume on an API key" ("Volum neobișnuit pe o cheie API"), and its technique, T1499, is named "Endpoint Denial of Service" in `features/org/mitre.ts`, which gives it the badge, the tooltip and the link to attack.mitre.org. The API keys page is unchanged: the alert is read in Security events, like every detection.

### 75. Local validation

- eslint -> no problems
- tsc -> no errors
- vitest -> 244 passed
- build -> successful
- npm audit -> 0 vulnerabilities

The new test checks the alert's row (badge and technique name), its details (technique, link, sending address, message) and the absence of an account link; `mitre.test.ts` names the new technique. Reverse check (3 of 3): the technique name removed, the label changed, or the type removed from the list (caught by the type check).

End-to-end check: headless Firefox over WebDriver BiDi, on `vite preview` with the production policy, against the temporary database of the server check. Signed in as the owner, it opened Security events filtered to the new type, in both themes, both languages, at desktop and phone width, and opened the alert's details each time: 64 of 64 checks passed (two alerts listed, the T1499 badge and its name, the details and the MITRE link, no account link, the theme, no horizontal overflow, no policy violation). The screenshots were viewed.

## Stage 15: Sign-in limit per address

### 76. The new event in the console

The backend's new `login_address_limited` event is one more security event type (`SECURITY_EVENT_TYPES`) and one more audit type (`AUDIT_EVENT_TYPES` in `features/org/api.ts`). It is labelled "Address limited after too many failed sign-ins" ("Adresă limitată după prea multe autentificări eșuate") in the organization view, "Address limited after failed sign-ins" in the audit log, and "Sign-in attempts limited for an address" in the personal view's list, which the type requires though no account's activity shows it. Its technique, T1110, is named "Brute Force" in `features/org/mitre.ts`. The event belongs to the platform, so only the owner sees it. The login page needs nothing new: a refused address gets the same `429` and `Retry-After` as a locked email, which it already shows with the time to wait.

### 77. Local validation

- eslint -> no problems
- tsc -> no errors
- vitest -> 246 passed
- build -> successful
- npm audit -> 0 vulnerabilities

The new tests check the event's row (badge and technique name) and its details (technique, link, address, no account link) in Security events, and the record in the audit log with its type offered by the filter; `mitre.test.ts` names T1110. Reverse check (4 of 4): the technique name removed, the label changed, the type removed from the security event types (caught by the type check), or removed from the audit types (first missed, now caught by the audit test).

End-to-end check: headless Firefox over WebDriver BiDi, on `vite preview` with the production policy, against the temporary database of the server check. Signed in as the owner, in both themes, both languages, at desktop and phone width, it opened Security events filtered to the new type and the event's details, then the audit log filtered to it: 72 of 72 checks passed (one row, the T1110 badge and its name, the address `::1`, the MITRE link, no account link, the audit record, the theme, no horizontal overflow, no policy violation). Once `127.0.0.1` was over its limit, the sign-in page answered the owner's right password with the lockout's message and the minutes left, and stayed on `/login`: 40 of 40 checks. The screenshots were viewed.

## Stage 16: Sprays across organizations

### 78. The new alert in the console

The backend's new `cross_organization_spray_detected` alert is one more security event type (`SECURITY_EVENT_TYPES`). It is labelled "Password spray across organizations" ("Password spray între organizații") in the organization view and "Password spray across organizations detected" in the personal view's list, which the type requires though no account's activity shows it. Its technique, T1110.003, already had its name in `features/org/mitre.ts`. The alert belongs to the platform, so only the owner sees it, in Security events, the threat band and the overview's technique counts.

### 79. Local validation

- eslint -> no problems
- tsc -> no errors
- vitest -> 247 passed
- build -> successful
- npm audit -> 0 vulnerabilities

The new test checks the alert's row (technique badge) and its details (label, technique name, address, the message's spread, no account link) in Security events. Reverse check (2 of 2): the label changed, or the type removed from the security event types (caught by the type check).

End-to-end check: headless Firefox over WebDriver BiDi, on `vite preview` with the production policy, against the temporary database of the server check. Signed in as the owner, in both themes, both languages, at desktop and phone width, it opened Security events filtered to the new type and an alert's details, then the overview: 75 of 75 checks passed (the label, the T1110.003 badge and its name, the address, the spread, the theme, no horizontal overflow, no policy violation). The screenshots were viewed.

## Stage 17: Sealed audit history

### 80. The new alert in the console

The backend's new `audit_chain_broken` alert is one more security event type (`SECURITY_EVENT_TYPES`). It is labelled "Audit history broken" ("Istoric de audit rupt") in the organization view and "Audit history no longer verifies" ("Istoricul de audit nu mai trece verificarea") in the personal view's list, which the type requires though no account's activity shows it. Its technique, T1070, gets its name in `features/org/mitre.ts`: Indicator Removal. The alert belongs to the platform, so only the owner sees it, in Security events, the threat band and the overview's technique counts. There is no page for the chains themselves: the command line checks them on demand.

### 81. Local validation

- eslint -> no problems
- tsc -> no errors
- vitest -> 248 passed
- build -> successful
- npm audit -> 0 vulnerabilities

The new test checks the alert's row (technique badge and name) and its details (label, technique, the record in the message, the link to attack.mitre.org, no account link) in Security events; the technique test checks the new name. Reverse check (2 of 2): the label changed, or the technique's name removed.

End-to-end check: headless Firefox over WebDriver BiDi, on `vite preview` with the production policy, against the temporary database of the server check, holding a changed record and a truncated chain. Signed in as the owner, in both themes, both languages, at desktop and phone width, it opened Security events filtered to the new type and an alert's details, then the overview: 81 of 81 checks passed (the label, the T1070 badge and its name, the details, the theme, the technique counts once the overview had loaded, no horizontal overflow, no policy violation). The screenshots were viewed. A first run took its overview screenshots while the page was still loading; the check was changed to wait for the technique section itself.

## Stage 18: The console's server (phase B)

### 82. nginx in the console's image

`frontend/Dockerfile` builds the console with Node 22 and serves `dist/` with the unprivileged nginx image (`nginxinc/nginx-unprivileged:stable-alpine`, pinned by digest), as its user 101, on port 8080 (`frontend/nginx/default.conf`):

- **The same headers as `vite preview`.** `scripts/nginx-headers.ts` turns `productionHeaders` from `security-headers.ts` into `add_header … always;` lines at the image build, included in each location that serves the console; it refuses a value nginx would read differently (a quote, `$`, a backslash, a new line). The API's answers keep the backend's own policy.
- **One origin.** `/api/` goes to the backend, reached as `sentinelcore-backend:8000`, as the Vite proxy does. nginx replaces `X-Forwarded-For` with the address it saw (`nginx/proxy.conf`).
- **Kept inside.** `/api/metrics` answers `404` with the API's own body.
- **Ingestion floods.** Each address may send 20 requests a second to `/api/ingest`, with bursts of 100; beyond that nginx answers `429` with a JSON body.
- **Caching.** The console's pages are `no-store`; `/assets/`, whose names carry a content hash, are cached for a year as immutable. Static files are compressed.
- **Probes.** `/nginx-health` answers from nginx itself.

### 83. Local validation

- eslint, tsc, build, npm audit (0) -> passed; vitest -> 255 passed (7 new for the header writer)
- Reverse check (2 of 2): a header left out, or the guard on values removed.
- End-to-end check: headless Firefox over WebDriver BiDi on the console's image at `http://localhost:8080`, against the backend's image: 129 of 129 checks passed (sign-in with the `Secure` cookies, overview, security events, audit log and personal overview, in both themes, both languages, desktop and phone, no policy violation, no horizontal overflow). The screenshots were viewed.

## Stage 19: New advisories

### 84. undici and zod

Two new high-severity advisories made `npm audit --audit-level=high` fail on `main`. Both packages are transitive development dependencies, not part of the console's build: undici 8.11.2 (through jsdom, for the tests; denial of service in the EventSource parser and on excessive content encodings, and a Subresource Integrity bypass) and zod 4.3.6 (through `eslint-plugin-react-hooks`; memory exhaustion on oversized constrained collections). `npm audit fix` moves them to undici 8.12.3 and zod 4.6.7 in `package-lock.json` only; `package.json` is unchanged. undici 8.12.3 is six days old, inside the seven-day cooldown, which security fixes skip as Dependabot's do. This supersedes Dependabot's #59.

### 85. brotli-libs in the console's image

Images CI then failed on the same pull request: Grype found CVE-2026-111497, rated Critical, in the console's brotli-libs 1.2.0-r1, fixed in 1.2.1-r0. The nginx-unprivileged base was already at its newest digest (rebuilt 2026-10-19) and still carried 1.2.0-r1, while Alpine 3.24's repository had the fix. As with zlib in C2, `frontend/Dockerfile` now installs `brotli-libs=1.2.1-r0` next to `zlib=1.3.2-r1`; remove each patch once the base digest includes it.

### 86. Local validation

- `make verify`: 15 of 15 checks (vitest 255 passed, npm audit 0 vulnerabilities, pytest 703 passed).
- `make scan-images`: 0 open; console high 1 (0 fixable), medium 3 (0), unknown 2 (2); backend unchanged. `make deploy-lint`: clean.
- Reverse checks: on `main`, without the changes, `npm audit` fails with the two advisories, and Images CI fails on the brotli-libs finding (pull request #61, first run).

### 87. curl in the console's image

A day later, Grype found CVE-2026-92392, rated High, in the console's curl and libcurl 8.22.0-r0, fixed in 8.23.0-r0. It failed Images CI for the open signing pull request (#60). The nginx-unprivileged base was still at the same digest and carried 8.22.0-r0. `frontend/Dockerfile` now also installs `curl=8.23.0-r0` and `libcurl=8.23.0-r0`, the same patch as for zlib and brotli-libs.

### 88. Local validation

- `make scan-images`: 0 open; console medium 3 (0 fixable), unknown 2 (2); backend unchanged. `make deploy-lint`: clean.
- Reverse check: without the patch, `make scan-images` fails with the two curl findings.

## Stage 20: Audit fixes

### 89. Cached data across accounts

Logging out clears React Query's cache, but a session that expires does not: the 401 only re-checks the current user, and the guard sends the browser to `/login`. Whoever signed in next in the same tab saw the previous account's cached pages, possibly another organization's, until they reloaded. A successful login now removes every cached query (`useLogIn` in `features/auth/hooks.ts`); the guard then loads the new account. The cost is a short loader after login, where the current user used to be fetched before leaving the login page.

### 90. Rename and suspend forms kept the previous organization

The row buttons stay enabled while a form is open. Picking "Rename" on one organization and then on another kept the first one's typed name, now aimed at the second; the suspend form kept the typed slug the same way. Both forms are now keyed by the organization's id, so each pick starts a fresh form.

### 91. Local validation

- `make verify`: 15 of 15 checks (vitest 257 passed, npm audit 0 vulnerabilities, pytest 703 passed).
- Mutations: 4/4 caught (login keeps the cache; rename form without its key; suspend form without its key; the earlier invalidation instead of removal). Removing the current user's query too was not caught, so it is removed with the rest.

### 92. Lean pass after the audit

Removed: the unused shadcn components and exports (`badge.tsx`, `tooltip.tsx` with its provider in `main.tsx` and the test renderer, six `DropdownMenu` parts, `CardDescription`, `CardAction`, `CardFooter`, `AlertTitle`), the `userDetail.profile`, `.email` and `.state` translations and the pass-through `ConfirmForm`, whose callers use `ActionForm` directly. `MySessionsPage` uses `ActionNotice` instead of its own copy, and both `MySessionsPage` and `OrgUserPage` use `LoadFailed` for their retry blocks. The `radix-ui` dependency stays: other components use it. The decisions log has the full list.

### 93. Local validation

- `make verify`: 15 of 15 checks (vitest 257 passed, npm audit 0 vulnerabilities, pytest 711 passed). The removals change no behaviour, so no test was added or changed on the console.

## Stage 21: Dependency updates

### 94. Two Dependabot updates in one pull request

The npm group (#69, ten minor and patch updates: `@tanstack/react-query`, `i18next`, `lucide-react`, `react-i18next`, `react-router`, `eslint`, `typescript-eslint`, `vitest`, `@vitest/coverage-v8`, `jsdom`) and ruff 0.17.1 for the backend (#68) were both behind `main`, which requires a branch to be up to date before merging. They share one branch, so CI runs once instead of after each merge. TypeScript 6 (#70) is a major version and keeps its own pull request, as decided after #52. `make verify`: 15 of 15 checks (vitest 257 passed, npm audit 0 vulnerabilities, pytest 711 passed).

### 95. TypeScript 6

TypeScript moves from 5.9.3 to 6.0.3 (#70), on its own branch because the Dependabot one conflicted with `main` after #72. The range stays `~` (patches only): `typescript-eslint` 8.72 accepts TypeScript below 6.1, so a caret range could let a future 6.1 break the lint step. No `tsconfig` option needed changing. `make verify`: 15 of 15 checks (typecheck and build clean, vitest 257 passed, npm audit 0 vulnerabilities, pytest 711 passed).

## Stage 22: README screenshots

### 96. Four pictures from the demo

`scripts/screenshots.py`, run as `make screenshots` while `make demo` serves the console, signs in through the real form as the owner, Acme's admin and Globex's admin (passwords read from `.demo/`, never printed), opens four pages and captures them over WebDriver BiDi: the platform overview (also the README's first image), Acme's security events filtered to incidents over 30 days, the Acme account locked by an operator (found through `GET /admin/users?locked=true`), and Globex's overview. A preload script sets the dark theme and English before the console starts; a page counts as loaded when its heading shows and no skeleton is left. `make help` now says three organizations. Run three times against the same demo: four pictures, 41 to 45 KB each, Firefox and its temporary profile removed afterwards. The pictures and a README section for them wait for the interface redesign that comes next, so they are not committed yet. `make verify`: 15 of 15 checks (ruff and format now include `scripts/screenshots.py`, vitest 257 passed, pytest 711 passed).

## Stage 23: Redesign, part one

### 97. Tokens, shell and overview

The palette in `src/index.css` is new: white and near-black backgrounds, neutral greys, one blue accent, and severity colours, every text colour at 4.5:1 or more on the page, the sidebar and its own tinted background in both themes (checked with the WCAG formula; the lowest is 4.66:1). Public Sans replaces IBM Plex; `font-display` now points at it until the remaining pages drop it. The theme follows the system by default, and `index.html` no longer forces the dark class, so the page's first paint already matches the system.

The sidebar has one menu in two groups, named after the organization (or "Platform" for the owner) and "My account", without numbers; on a phone each group is one scrolling row. `PageHeader` loses the breadcrumb above the title and shows the owner's organization picker beside the page's actions. The threat band is removed (`ThreatBand.tsx`).

The overview now opens with the level and the latest detection, then the newest incidents as a list, each with an Open button for its details (still recorded in the audit log), then the six counts in one ruled row, a chart of the last 24 hours stacked by severity, and the organizations, techniques and failed sign-in sources below. The band's tests moved to `OrgOverviewStatus.test.tsx`, for the status and the chart; the sidebar, theme and navigation tests describe the new shell.

Local validation: `make verify` 15 of 15 (vitest 258 passed, pytest 711 passed, npm audit 0). Mutations caught 6 of 6: the incident count loaded on personal pages, the chart scaled to incidents only, the default theme back to dark, Open doing nothing, the latest detection's link without its alert types, the picker shown to members. Real Firefox screenshots on `make demo`: the overview, the events page, an account page and Globex's overview, light and dark at 1440×900 and at phone width.

## Stage 24: Redesign, part two

### 98. Table pages

The security events, audit log, users, account, API keys and organizations pages follow the new look. Table cells go from `py-2.5` to `py-2`. `font-mono` is removed from times, dates, counts, emails, the search box and its filter chip, and the account, target, time and message fields of the details sheet; it stays on IP addresses, MITRE codes, prefixes, slugs and sources. `SeverityBadge` shows info in the muted text colour without a background. `MitreBadge` drops its pill and crosshair icon for grey monospace text, keeping the tooltip and the screen-reader label. `OrgUserPage` shows its fields as a plain list with sentence-case labels and drops `font-display` and `label-mono`; `AccountActions` writes the deactivate button in the destructive colour. The organization column uses the table's text size instead of a smaller one. The overview's counts and account line follow the same rules. No behaviour or text changes. The account page test now checks that the role is listed under its label.

Local validation: `make verify` 15 of 15 (vitest 258 passed, pytest 711 passed, npm audit 0). Mutations caught 4 of 4: the MITRE screen-reader label removed, its tooltip removed, the severity word removed, the account page's field labels removed (the last one was first missed and the test was strengthened). Real Firefox screenshots on `make demo` of the six pages, light and dark at 1440×900 and at phone width.

