# SentinelCore Frontend

The SentinelCore web app: React 19, TypeScript, Vite, Tailwind CSS and shadcn/ui components.

## Getting started

The backend must be running locally on port 8000 (see [backend/README.md](../backend/README.md)).

```bash
npm install
npm run dev
```

The app runs at `http://localhost:5173`. Vite forwards `/api/*` requests to the backend, so the frontend and the API share an origin: no CORS is needed and the session cookies work.

## Commands

| Command | What it does |
| --- | --- |
| `npm run dev` | development server with hot reload |
| `npm run lint` | ESLint |
| `npm run typecheck` | TypeScript type check |
| `npm test` | the Vitest tests |
| `npm run test:watch` | the tests, rerun on every change |
| `npm run build` | production build into `dist/` |
| `npm run preview` | serves the build from `dist/` with the production security headers, forwarding `/api` like the dev server |

## Structure

```text
src/
├── components/
│   ├── brand/       # the logomark and the "SENTINEL core" wordmark
│   ├── layout/      # app structure: sidebar, page headers, command palette (Ctrl+K), account menu, the frame of the public pages
│   └── ui/          # shadcn/ui components (generated, then adjusted)
├── features/
│   ├── account/     # the "My account" scope: sessions, activity
│   ├── auth/        # authentication API client, hooks, route protection, invitation links
│   ├── org/         # the "Organization" scope ("Platform" for the owner): overview, logs, users, invitations, API keys, organizations and the owner's organization picker, MITRE ATT&CK, filters, actions
│   └── theme/       # dark / light theme
├── i18n/            # Romanian and English translations
├── lib/             # API client, TanStack Query setup, utilities
├── pages/           # app pages; the organization pages load on demand (pages/lazy.ts)
├── test/            # test setup and the mocked API server (MSW)
├── routes.tsx       # the routes, also used by the tests
└── main.tsx         # entry point
security-headers.ts  # the headers the dev server and the build's preview send
```

## Authentication

Login uses `POST /api/auth/session`. The backend puts the token in an httpOnly cookie that frontend code cannot read. For requests that change data, the API client (`src/lib/api.ts`) reads the `sentinelcore_csrf` cookie and sends it in the `X-CSRF-Token` header.

New accounts come from invitations. An admin or the owner creates one on the Users page and gets a link of the form `/invite#sci_…`, shown once. The token sits in the fragment, which the browser never sends to a server; the public `/invite` page reads it, clears it from the address bar, and sends it to the API in a request body. After the account is created, the page opens `/login` with the email filled in.

## Security headers

`security-headers.ts` holds the headers the console is served with; `vite.config.ts` sends them from both servers.

- **Production** (`npm run preview`): a Content Security Policy that runs only the bundle's own scripts (`script-src 'self'`) and lets no other site frame the console (`frame-ancestors 'none'`, plus `X-Frame-Options: DENY`), with `nosniff`, `Referrer-Policy: no-referrer`, a `Permissions-Policy` and `Cross-Origin-Opener-Policy`. Inline styles stay allowed, because Radix dialogs and menus add `<style>` elements while they are open. Fonts stay files rather than inlined `data:` URIs, so `font-src 'self'` covers them.
- **Development** (`npm run dev`): the same, except for the inline React Refresh script and the hot reload websocket, which Vite's dev server needs.

The console's image (`Dockerfile`) serves the build with nginx and sends the same production headers: `scripts/nginx-headers.ts` writes them as nginx directives at build time, from `security-headers.ts`, so the two cannot drift apart. Its nginx configuration (`nginx/`) passes `/api` to the backend, replaces the client's `X-Forwarded-For`, keeps `/api/metrics` inside and limits ingestion requests per address.

## Theme and translations

- Type: Public Sans, bundled with the app through Fontsource; no font is loaded from a CDN. Emails, addresses and ids use the system's monospace font. The console is being redesigned as a sober monitoring tool; pages not redesigned yet still use `font-display` and `label-mono`, which go with them.
- `Ctrl+K` (`Cmd+K` on a Mac), or the search button in the sidebar, opens the command palette: jump to a page, open the user list or the event log filtered by what was typed, change the theme or the language, sign out. The palette itself makes no API requests.
- The theme follows the system until the user picks light or dark from the account menu. Colors are defined as CSS variables in `src/index.css`; colour beyond the one blue accent marks severity only.
- The default language is Romanian. Strings live in `src/i18n/locales/`; the English file is typed after the Romanian one, so a missing key fails the type check.
