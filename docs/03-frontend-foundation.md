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

