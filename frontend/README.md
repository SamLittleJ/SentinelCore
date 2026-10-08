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

## Structure

```text
src/
├── components/
│   ├── layout/      # app structure: sidebar, account menu
│   └── ui/          # shadcn/ui components (generated, then adjusted)
├── features/
│   ├── account/     # the "My account" scope: sessions, activity
│   ├── auth/        # authentication API client, hooks, route protection
│   ├── org/         # the "Organization" scope: overview, logs, users, filters, account actions
│   └── theme/       # dark / light theme
├── i18n/            # Romanian and English translations
├── lib/             # API client, TanStack Query setup, utilities
├── pages/           # app pages; the organization pages load on demand (pages/lazy.ts)
├── test/            # test setup and the mocked API server (MSW)
├── routes.tsx       # the routes, also used by the tests
└── main.tsx         # entry point
```

## Authentication

Login uses `POST /api/auth/session`. The backend puts the token in an httpOnly cookie that frontend code cannot read. For requests that change data, the API client (`src/lib/api.ts`) reads the `sentinelcore_csrf` cookie and sends it in the `X-CSRF-Token` header.

## Theme and translations

- The default theme is dark; users can pick light or "match system" from the account menu. Colors are defined as CSS variables in `src/index.css`.
- The default language is Romanian. Strings live in `src/i18n/locales/`; the English file is typed after the Romanian one, so a missing key fails the type check.
