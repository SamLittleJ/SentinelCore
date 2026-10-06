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
