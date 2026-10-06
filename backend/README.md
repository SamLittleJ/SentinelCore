# SentinelCore Backend

API FastAPI cu SQLAlchemy 2, PostgreSQL, Alembic și autentificare JWT.

## Structura

```text
app/
├── api/        # routere și dependențe (sesiune DB, utilizator curent, RBAC)
├── core/       # configurare, conexiune DB, hashing parole și JWT
├── models/     # modele ORM
├── schemas/    # scheme Pydantic pentru input și output
├── services/   # logica de business
└── main.py     # punctul de intrare al aplicației
migrations/     # migrații Alembic
tests/          # teste pytest
```

## Setup local

Comenzile se rulează din directorul `backend/`, cu PostgreSQL pornit prin `docker compose up -d` din rădăcina repository-ului.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

`.[dev]` instalează și uneltele de dezvoltare: pytest, httpx, Ruff și Bandit. Pentru rularea aplicației este suficient `python -m pip install -e .`.

## Protecție la brute-force

Login-urile eșuate repetate pentru același email blochează temporar login-ul pe acel email. Pragurile sunt configurabile în `.env`:

```env
LOGIN_MAX_FAILED_ATTEMPTS=5
LOGIN_FAILURE_WINDOW_MINUTES=15
LOGIN_LOCKOUT_MINUTES=15
```

În spatele unui reverse proxy, pornește uvicorn cu `--proxy-headers --forwarded-allow-ips=<IP-ul proxy-ului>`, altfel toate evenimentele vor înregistra IP-ul proxy-ului.

## Observabilitate

- `GET /health`: procesul rulează
- `GET /health/ready`: aplicația poate servi trafic; răspunde `503` dacă baza de date nu e disponibilă
- `GET /metrics`: metrici Prometheus; dacă `METRICS_TOKEN` e setat, cere `Authorization: Bearer <token>`
- fiecare răspuns conține `X-Request-ID`, prezent și în toate logurile cererii

Logurile se configurează în `.env`:

```env
LOG_LEVEL=INFO
LOG_FORMAT=text   # json pentru colectoare de loguri
```

## Sesiuni

Fiecare login creează o sesiune, revocabilă prin `/auth/logout`, `/auth/logout-all`, `DELETE /users/me/sessions/{id}` sau, de către un admin, prin `DELETE /admin/users/{id}/sessions`.

Sesiunile expirate sau revocate de mai mult de `SESSION_RETENTION_DAYS` zile sunt șterse automat de API, la fiecare `SESSION_CLEANUP_INTERVAL_MINUTES` minute. Curățarea poate fi rulată și manual sau din cron:

```bash
python -m app.cli cleanup-sessions
```

## Verificare de tipuri

Pylance verifică doar fișierele deschise în editor. Pentru tot backend-ul, cu același motor (Pyright):

```bash
npx --yes pyright@1 --pythonpath .venv/bin/python app tests migrations
```

## Migrații

```bash
python -m alembic revision --autogenerate -m "descriere modificare"
python -m alembic upgrade head
python -m alembic check    # verifică dacă modelele și schema DB sunt sincronizate
```

Migrațiile generate automat trebuie verificate manual înainte de aplicare.

## Teste

Testele rulează pe baza de date separată `sentinelcore_test`, niciodată pe baza de development. Creare, o singură dată:

```bash
docker exec sentinelcore-postgres createdb -U sentinelcore sentinelcore_test
```

Rulare:

```bash
python -m pytest -v
```

Adresa bazei de test poate fi schimbată prin variabila `TEST_DATABASE_URL`; numele ei trebuie să conțină `sentinelcore_test`.

## Verificări rulate și în CI

```bash
python -m ruff check .
python -m ruff format --check .
python -m bandit -r app -c pyproject.toml
python -m pytest -v
```

Scanarea de secrete cu Gitleaks se rulează din rădăcina repository-ului. Pe Fedora, opțiunea `:Z` este necesară din cauza SELinux:

```bash
docker run --rm -v "$(pwd):/repo:Z" -w /repo zricethezav/gitleaks:latest detect --source=/repo --verbose
```
