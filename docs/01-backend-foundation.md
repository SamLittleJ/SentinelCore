# 01 - Backend Foundation

## Scop
Acest document descrie fundatia initiala a backend-ului SentinelCore si primele decizii tehnice luate pentru a porni proiectul corect.

---

## Ce a fost realizat

### 1. Structura initiala a backend-ului
A fost creat directorul `backend/`, separat de frontend, pentru a pastra clar delimitata partea de API si logica server-side.

Structura actuala relevanta:

```text
backend/
├── .venv/
├── app/
│   ├── api/
│   │   └── routes/
│   │       └── health.py
│   └── main.py
├── tests/
├── .env.example
├── pyproject.toml
└── README.md
```

---

### 2. Virtual environment dedicat backend-ului
A fost folosit un mediu virtual Python separat in `backend/.venv`.

Motiv:
- izolarea dependentelor backend-ului
- evitarea conflictelor cu Python-ul global din sistem
- control mai bun aspura pachetelor instalate

---

### 3. Configurarea proiectului Python prin **pyproject.toml**
Backend-ul a fost initializat ca proiect Python modern folosind **pyproject.toml**.

In acest fisier au fost definite:
- build system-ul
- numele proiectului
- versiunea
- versiunea minima Python
- dependentele minime initiale

Dependente instalate in aceasta etapa:
- fastapi
- uvicorn[standard]

---

### 4. Instalarea backend-ului in mod editable
A fost rulat:
- `pip install -e .`
- `python -m pip install -e`

Scop:
- instalarea proiectului local in mediul virtual
- posibilitatea de a lucra iterativ fara reinstalari complete la fiecare modificare

---

### 5. Prima aplicatie FastAPI functionala
A fost creat fisierul `app/main.py` si aplicatia FastAPI minima.

Initial, endpoint-ul `/health` a fost definit direct in `main.py`, apoi a fost mutat intr-un router separat pentru a mentine o structura mai curata.

---

### 6. Separarea rutelor
A fost introdusa o structura minima pentru routere:
- `app/main.py` - punct de intrat al aplicatiei
- `app/api/routes/health.py` - router dedicat pentru health check

Aceasta separare pregateste proiectul pentru extinderea viitoare fara aglomerarea fisierului principal.

---

### 7. Health endpoint functional
A fost implementat endpoint-ul:
- GET /health
Raspunsul returnat:
- {"status": "ok"}

Acest endpoint confirma ca:
- aplicatia porneste
- serverul raspunde corect
- structura minima a backend-ului este functionala

---

### 8. Pornirea locala a backend-ului
Backend-ul a fost pornit local cu comanda:
- python -m uvicorn app.main:app --reload
Aceasta este comanda standard de lucru local folosita in proiect in acest moment.

---

## Probleme intalinte si rezolvari

### Problema 1: **pyproject.toml** invalid
La prima incercare de instalare a proiectului a aparut o eroare de tip TOML parse error.
Cauza:
- sintaxa invalida in `pyproject.toml` din cauza unei ghilimele lipsa
Rezolvare:
- fisierul a fost corectat si validat
- instalarea editable a functionat dupa corectare

---

### Problema 2: **uvicorn** rulat din context gresit
La prima rulare a serverului aparea eroarea `ModuleNotFoundError: No module named 'fastapi'`, desi FastAPI era instalat in virtual environment.
Cauza:
- comanda `uvicorn...` folosea executabilul gresit / contextul gresit din sistem
Rezolvare:
- rularea a fost facuta cu: `python -m uvicorn app.main:app --reload`
- astfel s-a folosit interpreterul Python din `.venv`

---

## Ce a fost inteles in aceasta etapa
In aceasta etapa au fost clarificate urmatoarele concepte:
- rolul fisierului `pyproject.toml`
- diferenta dintre Python global si Python din virtual environment
- importanta rularii tool-urilor Python prin `python -m...`
- separarea dintre punctul de intrare al aplicatiei si routerele dedicate
- rolul unui endpoint de health check in validarea fundatiei backend-ului

---

## Stare la finalul etapei
La finalul acestei etape, backend-ul SentinelCore are:
- proiect Python configurat
- dependente minime instalate
- mediu virtual functional
- aplicatie FastAPI functionala
- router separat pentru `/health`
- pornire locala validata

---

## Pasul urmator
Pasul urmator dupa aceasta fundatie este configurarea conexiunii la baza de date si definirea primului model real al aplicatiei.

### 9. PostgreSQL local prin Docker Compose
A fost consigurat un serviciu PostgreSQL local folosind Docker Compose.

Scop:
- mediu reproductibil
- rulare locala controlata
- fundatie pentru dezvoltarea backend-ului si testarea modelelor

Baza de date locala a fost pornita si verificata cu succes.

### 10. Test de conexiune reala la baza de date
Conexiunea reala la PostgreSQL a fost validata prin executarea unei interogari simple:

'''sql
SELECT 1
'''

Rezultatul a confirmat:
- server PostgreSQL functional
- URL de conexiune valid
- driver **psycopg** functional
- conectarea corecta prin SQLAlchemy

### 11. Primul model ORM: **User**
A fost introdus primul model real al aplicatiei: **User**

Campuri definite:
- id
- username
- email
- hashed_password
- is_active
- created_at
- updated_at
Constrangeri importante:
- username unic
- email unic
- campuri obligatorii pentru datele esentiale
Acest model reprezinta prima entitate centrala a sistemului SentinelCore

### 12. Crearea primei tabele in baza de date
Tabela **users** a fost creata in PostgreSQL folosind:
'''
Base.metadata.create_all(bind=engine)
'''
Crearea a fost verificate direct in PostgreSQL cu:
- \dt
- \d users
Rezultatul a confirmat existenta tabelei si a coloanelor definite in model.

### 13. Problema intalnita: importuri inconsistente
La prima incercare, tabela **users** nu a fost creata, desi modelul exista.
Cauza:
- proiectul folosea importuri inconsistente:
  - unele pornind din **app...**
  - altele pornind direct din **core...* sau **models...**
Aceasta a dus la incarcarea separata a modulelor si la folosirea unor instante diferite de **Base**, ceea ce a facut ca **create_all()** sa nu vada modelul **User**.
Rezolvare:
- standardizarea importurilor pe varianta absoluta pornind din **app**
- exemplu:
  - from app.core.database import Base
  - from app.models.user import User
Aceasta decizie trebuie pastrata consecvent in tot backend-ul

### 14. Stare actuala a backend-ului
In acest moment backend-ul are:
- aplicatie FastAPI functionala
- health check functional
- configurare prin .env
- conexiune la PostgreSQL functionala
- strat ORM initial
- model User
- tabea users creata si validata

## Extinderea fundatiei backend: schemas, services si primul flux real de autentificare

### 15. Introducerea schemelor Pydantic pentru user
A fost creat directorul `app/schemas/` si fisierul `app/schemas/user.py`.

Au fost definite doua scheme initiale:
- `UserCreate` - pentru input-ul necesar la crearea unui utilizator
- `UserRead` - pentru output-ul trimis catre client

Scopul acestei separari:
- diferentierea clara intre modelul ORM si contractul API
- control asupra datelor acceptate in request
- control asupra datelor returnate in response
- excluderea explicita a campului `hashed_password` din raspunsurile API

### 16. Introducerea dependentei pentru sesiunea DB
A fost creat fisierul `app/api/deps.py`
A fost introdusa functia `hash_password()`, bazata pe `pwdlib`.

Scop:
- parolele nu sunt stocate niciodata in forma raw
- hashing-ul este centralizat intr-un loc dedicat
- logica de securitate nu este imprastiata prin endpoint-uri

### 17. Introducerea stratului de servicii pentru user
A fost creat directorul `app/services` si fisierul `app/services/user_service.py`.

Au fost definite functiile:
- `get_user_by_email()`
- `get_user_by_username()`
- `create_user()`

Scopul stratului `services`:
- mutarea logicii de business in afara endpoint-urilor
- separarea clara dintre ruta, acces DB si reguli de business
- pregatirea arhitecturii pentru extinderea ulterioara

### 18. Implementarea primului endpoint real: register
A fost creat fisierul `app/api/routes/auth.py`.

A fost introdus endpoint-ul:

```http
POST /auth/register
```
Acesta:
- primeste input de tip `UserCreate`
- foloseste `get_db()` pentru sesiunea de baza de date
- verifica existenta unui utilizator cu acelasi email
- verifica existenta unui utilizator cu acelasi username
- creeaza utilizatorul daca datele sunt valide si unice
- returneaza datele utilizatorului prin schema `UserRead`

### 19. Validarea fluxului de register
Fluxul de inregistrare a fost testat prin Swagger UI (`/docs`)
Rezultate confirmate:
- creare user cu succes -> `201 Created`
- incercare de creare user duplicat - > `400 Bad Request`
- endpoint-ul `/health` ramane functional in paralel
Aceasta confirma primul flux complet end-to-end al backend-ului:
- request HTTP
- validare input
- acces DB
- logica de business
- hashing parola
- persistenta in PostgreSQL
- response model controlat

### 20. Structura actuala relevanta a backend-ului
```
backend/app/
├── api/
│   ├── deps.py
│   └── routes/
│       ├── auth.py
│       └── health.py
├── core/
│   ├── config.py
│   ├── database.py
│   └── security.py
├── models/
│   └── user.py
├── schemas/
│   └── user.py
├── services/
│   └── user_service.py
└── main.py
```

### 21. Stare actuala a backend-ului
In acest moment backend-ul are:
- aplicatie FastAPI functionala
- endpoint `/health`
- enpoint `POST /auth/register`
- configurare prin `.env`
- conexiune PostgreSQL functionala
- model ORM `User`
- tabela `users` creata si validata
- hashing de parola
- strat `schemas`
- strat `services`
- prim flux real de creare utilizator validat