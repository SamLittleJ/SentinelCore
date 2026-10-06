# SentinelCore Frontend

Aplicația web SentinelCore: React 19, TypeScript, Vite, Tailwind CSS și componente shadcn/ui.

## Pornire

Backend-ul trebuie să ruleze local pe portul 8000 (vezi [backend/README.md](../backend/README.md)).

```bash
npm install
npm run dev
```

Aplicația rulează la `http://localhost:5173`. Vite trimite cererile `/api/*` către backend, astfel încât frontend-ul și API-ul sunt pe aceeași origine: nu e nevoie de CORS, iar cookie-urile de sesiune funcționează.

## Comenzi

| Comandă | Ce face |
| --- | --- |
| `npm run dev` | server de dezvoltare cu reîncărcare automată |
| `npm run lint` | ESLint |
| `npm run typecheck` | verificarea tipurilor TypeScript |
| `npm test` | testele Vitest |
| `npm run test:watch` | testele, rerulate la fiecare modificare |
| `npm run build` | build de producție în `dist/` |

## Structura

```text
src/
├── components/
│   ├── layout/      # structura aplicației: bara laterală, meniul contului
│   └── ui/          # componente shadcn/ui (generate, apoi ajustate)
├── features/
│   ├── auth/        # client API pentru autentificare, hook-uri, protecția rutelor
│   └── theme/       # tema întunecată / luminoasă
├── i18n/            # traduceri în română și engleză
├── lib/             # clientul API, configurarea TanStack Query, utilitare
├── pages/           # paginile aplicației
├── test/            # configurarea testelor și serverul API simulat (MSW)
├── routes.tsx       # rutele, folosite și în teste
└── main.tsx         # punctul de intrare
```

## Autentificare

Login-ul folosește `POST /api/auth/session`. Backend-ul pune token-ul într-un cookie httpOnly, pe care codul frontend nu îl poate citi. Pentru cererile care modifică date, clientul API (`src/lib/api.ts`) citește cookie-ul `sentinelcore_csrf` și îl trimite în header-ul `X-CSRF-Token`.

## Temă și traduceri

- Tema implicită este cea întunecată; utilizatorul poate alege luminoasă sau „ca sistemul” din meniul contului. Culorile sunt definite ca variabile CSS în `src/index.css`.
- Limba implicită este româna. Textele sunt în `src/i18n/locales/`; fișierul englez este tipat după cel românesc, deci o cheie lipsă oprește verificarea de tipuri.
