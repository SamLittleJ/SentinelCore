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

```sql
SELECT 1
```

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
```python
Base.metadata.create_all(bind=engine)
```
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

## Extinderea fundatiei backend: login si JWT

### 22. Extinderea securitatii pentru verificarea parolei
Fisierul `app/core/security.py` a fost extins cu functia `verify_password()`

Scop:
- compararea unei parole introduse de utilizator cu valoarea hash-uita stocata in baza de date
- separarea logicii de verificare a parolei de endpoint-uri si servicii
- pastrarea responsabilitatilor de securitate intr-un singur modul dedicat
Aceasta functie completeaza `hash_password()` si permite implementarea fluxului de autentificare

### 23. Introducerea schemei de login
Fisierul `app/schemas/user.py` a fost extins cu schema `UserLogin`

Aceasta defineste datele necesare pentru autentificare:
- `email`
- `password`

Scop:
- separarea clara intre contractul de register si contractul de login
- validarea input-ului de autentificare prin Pydantic

### 24. Introducerea schemei de token
Fisierul `app/schemas/user.py` a fost extins si cu schema `Token`.
Aceasta defineste raspunsul endpoint-ului de login:
- `access_token`
- `token_type`

Scop:
- standardizarea raspunsului de autentificare
- pregatirea folosirii token-ului JWT in endpoint-uri protejate ulterior

### 25. Extinderea configuratiei aplicatiei pentru JWT
Fisierele `.env.example` si `.env` au fost extinse cu setari pentru JWT:
- `SECRET_KEY`
- `ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_TIME`
Fisierul `app/core/config.py` a fost actualizat pentru a citi aceste valori

Scop:
- configurarea centralizata a mecanismului de emitere token
- evitarea hardcodarii valorilor de securitate in cod

### 26. Generarea token-ului JWT
Fisierul `app/core/security.py` a fost extins cu functia `create_access_token()`

Aceasta:
- construieste payload-ul token-ului
- include claim-ul de `sub`
- include claim-ul de `exp`
- semneaza token-ul folosind configuratia din `Settings`

Scop:
- emiterea unui token JWT valid dupa autentificare reusita
- pregatirea bazei pentru endpoint-uri protejate

### 27. Introducerea autentificarii in stratul de servicii
Fisierul `app/services/user_service.py` a fost extins cu functia `authenticate_user()`

Aceasta:
- cauta utilizatorul dupa email
- verifica parola folosind `verify_password()`
- returneaza utilizatorul daca autentificarea este valida
- returneaza `None` daca autentificarea esueaza

Scop:
- separarea logicii de autentificare de endpoint
- reutilizarea logicii intr-un mod clar si testabil

### 28. Implementarea endpoint-ului de login
Fisierul `app/api/routes/auth.py` a fost extins cu endpoint-ul:
```http
POST /auth/login
```
Acesta:
- primeste imput de tip `UserLogin`
- foloseste sesiunea DB prin `get_db()`
- valideaza credentialele prin `authenticate_user()`
- emite un JWT prin `create_access_token()`
- returneaza raspunsul de tip `Token`

### 29. Validarea fluxului de login
Fluxul de autentificare a fost testat prin Swagger UI (`/docs`)

Rezultate confirmate:
- login valid -> `200 OK`
- login cu parola gresita -> `401 Unauthorized`
Raspunsul pentru login valid include:
- `access_token`
- `token_type = "bearer"`
Aceasta confirma functionarea completa a fluxului de autentificare:
- validare input
- verificare user in DB
- verificare parola hash-uita
- generare JWT
- raspuns standardizat pentru client

### 30. Stare actuala a backend-ului
In acest moment backend-ul are:
- aplicatie FastAPI functionala
- endpoint `/health`
- endpoint `POST /auth/register`
- endpoint `POST /auth/login`
- configurare prin `.env`
- conexiune PostgreSQL functionala
- model ORM `User`
- tabela `users` creata si validata
- hashing si verificare de parola
- generare JWT
- strat `schemas`
- strat `services`
- flux complet de register
- flux complet de login

### Observație practică
În această etapă, token-ul JWT folosește email-ul utilizatorului ca `subject` (`sub`). Această alegere este suficientă pentru MVP, urmând ca identificatorul principal din token să poată fi revizuit ulterior dacă va fi nevoie de o strategie mai strictă.

## Extinderea fundatiei backend: current user si RBAC(Role-base Access Control)

### 31. Decodarea token-ului JWT
Fisierul `app/core/security.py` a fost extins cu functia `decode_access_token()`.

Aceasta:
- decodeaza token-ul JWT
- valideaza semnatura token-ului
- valideaza expirarea token-ului
- returneaza payload-ul daca token-ul este valid

Scop:
- consumarea reala a token-ului emis la login
- pregatirea endpoint-urilor protejate
- separarea logicii JWT de restul aplicatiei

### 32. Introducerea dependentei pentru utilizatorul curent
Fisierul `app/api/deps.py` a fost extins cu:
- `oauth2_scheme`
- `get_current_user()`

Rolul acestora:
- extragerea token-ului Bearer din request
- validarea token-ului
- extragerea identitatii utilizatorului din claim-ul `sub`
- cautarea utilizatorului real in baza de date
- returnarea utlizatorului curent daca autentificarea este valida

In aceasta etapa, claim-ul `sub` contine email-ul utilizatorului.

### 33. Introducerea primului endpoint protejat.
A fost creat fisierul `app/api/routes/users.py`

A fost introdus endpoint-ul:
```http
GET /users/me
```
Acesta:
- necesita token JWT valid
- foloseste `get_current_user()`
- returneaza utilizatorul autentificat prin schema `UserRead`
Scop:
- validarea consumului real al token-ului
- confirmarea faptului ca autentificarea functioneaza nu doar la emitere, ci si la utilizare

### 34. Introducerea fundatiei RBAC
Modelul `User` a fost extins cu un camp `role`.
Rolurile au fost definite prin enum-ul `UserRole`, cu valorile:
- `user`
- `admin`
- `security_analyst`
- `owner`
Scop:
- introducerea controlului de acces bazat pe rol
- separarea clara a tipurilor de utilizatori inca din MVP
- pregatirea sistemului pentru endpoint-uri diferentiate pe roluri

### 35. Reset local al bazei de date pentru schimbarea schemei
Pentru a introduce coloana `role` in tabela `users`, baza de date locala a fost resetata.
A fost folosit un reset local prin Docker Compose, deoarece proiectul nu foloseste inca migratii gestionate prin Alembic pentru schimbarile de schema.
Aceasta abordare este acceptabila in aceasta etapa deoarece datele locale nu au inca valoare operationala.

### 36. Rol implicit pentru utilizatori noi
La crearea unui utilizator nou prin fluxul de register, rolul este setat implicit la:
```
user
```
Aceasta alegere defineste comportamentul standard pentru utilizatorii obisnuiti si evita atribuirea accidentala a unor privilegii ridicate.

### 37. Expunerea rolului in schema de output
Schema `UserRead` a fost extinsa cu campul `role`.

Scop:
- vizibilitate asupra rolului utilizatorului in raspunsurile API
- validarea corecta a comportamentului RBAC
- pregatirea interfetei pentru afisarea rolului in frontend mai tarziu

### 38. Introducerea autorizarii pe rol
Fisierul `app/api/deps.py` a fost extins cu functia `require_role()`

Aceasta:
- primeste unul sau mai multe roluri permise
- verifica rolul utilizatorului autentificat
- returneaza `403 Forbidden` daca utilizatorul nu are acces
- permite continuarea request-ului daca rolul este acceptat

Scop:
- separarea autentificarii de autorizare
- definirea unui mecanism reutilizabil pentru protejarea endpoint-urilor

### 39. Implementarea unui endpoint admin-only
Fisierul `app/api/routes/users.py` a fost extins cu endpoint-ul:
```http
GET /users/admin-only
```
Acesta:
- necesita utilizator autentificat
- permite acces doar pentru rolurile autorizate(`admin`, respectiv `owner` in implementarea curenta)
- returneaza raspuns valid doar daca utilizatorul are permisiunea neceasra

### 40. Validarea comportamentului RBAC
Comportamentul RBAC a fost testat prin request-uri autentificate.
Rezultate confirmate:
- utilizatorul cu rol `user` -> `403 Forbidden`
- utilizatoru cu rol `admin` -> `200 OK`

Aceasta confirma:
- functionarea corecta a dependentei `get_current_user()`
- functionarea corecta a dependentei `require_role()`
- diferentierea clara dintre autentificare si autorizare

### 41. Stare actuala a backend-ului
In acest moment backend-ul are:
- aplicatie FastAPI functionala
- endpoint `/health`
- endpoint `POST /auth/register`
- endpoint `POST /auth/login`
- endpoint `GET /users/me`
- endpoint `GET /users/admin-only`
- configurare prin `.env`
- conexiune PostgreSQL functionala
- model ORM `User`
- tabela `users` creata si validata
- hashing si verificare de parola
- generare si decodare JWT
- strat `schemas`
- strat `services`
- flux complet de register
- flux complet de login
- identificarea utilizatorului curent din token
- fundatie RBAC functionala

### Observație practică privind testarea endpoint-urilor protejate
În implementarea actuală, endpoint-ul de login folosește input JSON, nu formular OAuth2 standard. Din acest motiv, mecanismul `Authorize` din Swagger UI nu este aliniat complet cu fluxul de login și testarea endpoint-urilor protejate a fost făcută prin request-uri manuale (`curl`).

Aceasta este o limitare de integrare a documentației interactive, nu o problemă a backend-ului.

## Extinderea fundatiei backend: Audit Logging

### 42. Introducerea modelului `AuditLog`
A fost creat modelul ORM `AuditLog` in fisierul:

```text
app/models/audit_log.py
```
Acest model reprezinta baza mecanismului de audit al aplicatiei SentinelCore.

Scopul auditului este inregistrarea actiunilor importante din sistem, in special cele legate de autentificare, acces si evenimente relevante pentru securitate.

Modelul `AuditLog` contine urmatoarele campuri:
- `id`
- `event_type`
- `user_id`
- `email`
- `message`
- `created_at`

### 43. Introducerea tipurilor de evenimente de audit

A fost definit enum-ul `AuditEventType`.

Evenimentele initiale definite sunt:

- `USER_REGISTERED`
- `LOGIN_SUCCESS`
- `LOGIN_FAILED`
- `ADMIN_ENDPOINT_ACCESSED`

Scop:

- evitarea valorilor scrise manual in mai multe locuri
- reducerea riscului de typo-uri
- difinirea controlata a tipurilor de evenimente de audit

Observatie:

In etapa actuala, valorile enum-ului sunt salvate in baza de date cu numele membrilor enum, de exemplu `USER_REGISTERED`, nu cu forma lowercase `user_registered`. Acest comportament este acceptabil pentru MVP.

### 44. Crearea tabelei `audit_logs`

Tabela `audit_logs` a fost creata in PostgreSQL folosind mecanismul temporar:

```
Base.metadata.create_all(bind=engine)
```

Pentru ca SQLAlchemy sa detecteze modelul, `AuditLog` a fost importat in `app/main.py`.

Tabela a fost verificata in PostgreSQL cu:

```
\dt
\d audit_logs
```

Rezultatul a confirmat existenta tabelei `audit_logs` si a relatiei foregin key catre tabela `users`.

### 45. Structura tabelei `audit_logs`

Tabela `audit_logs` contine:

- `id` - identificator unic al evenimentului
- `event_type` - tipul evenimentului de audit
- `user_id` - referinta optionala catre utilizator
- `email` - email asociat evenimentului, util mai ales la login esuat
- `message` - descriere umana a evenimentului
- `created_at` - momentul producerii evenimentului

Campul `user_id` este optional deoarece anumite evenimente, precum login esua cu email inexistent sau parola gresita, pot exista fara un utilizator autentificat valid.

### 46. Introducerea serviciului de audit

A fost creat fisierul:

```
app/services/audit_service.py
```

Aceasta contine functia:

```
create_audit_log()
```

Scopul serviciului este centralizarea logicii de creare a evenimentelor de audit.

Aceasta abordare evita duplicarea codului de tip:

- creare obiect `AuditLog`
- `db.add(...)`
- `db.commit()`
- `db.refresh(...)`

in mai multe endpoint-uri.

### 47. Integrarea auditului in fluxul de register

Endpoint-ul:
```
POST /auth/register
```
a fost extins astfel incat, dupa crearea cu succesa unui utilizator, sa creeze un eveniment de audit de tip: ```USER_REGISTERED```

Acest eveniment confirma ca inregistrarea utilizatorului este urmarita in sistem.

### 48. Integrarea auditului in fluxul de login reusit

Endpoint-ul:
```
POST /auth/login
```
creeaza un eveniment de audit de tip: ```LOGIN_SUCCESS``` atunci cand autentificarea este valida.

Acest eveniment confirma ca autentificarile reusite sunt urmarite in sistem.

### 49. Integrarea auditului in fluxul de login esuat

Endpoint-ul:
```
POST /auth/login
```
creeaza un eveniment de audit de tip: ```LOGIN_FAILED``` atunci cand autentificarea esueaza.

Acest caz este important deoarece tentativele de loing esuate pot deveni ulterior baza pentru detectii de securitate, cum ar fi brute-force sau activitate suspecte.

In acest caz, audit log-ul poate contine email-ul incercat chiar daca nu exista un utilizator autentificat valid.

### 50. Integrarea auditului in endpoint-ul admin-only

Endpoint-ul:
```
GET /users/admin-only
```
creeaza un eveniment de audit de tip: ```ADMIN_ENDPOINT_ACCESSED``` atunci cand un utilizator cu rol permis acceseaza endpoint-ul.

In etapa actuala, este auditat accesul permis. Accesul refuzat prin `403 Forbidden` nu este inca auditat.

### 51. Validarea auditului in baza de date

Auditul a fost validat in PostgreSQL prin query-ul:
```
SELECT id, event_type, user_id, email, message, created_at
FROM audit_logs
ORDER BY id;
```

Au fost confirmate urmatoarele evenimente:
- `USER_REGISTERED`
- `LOGIN_SUCCESS`
- `LOGIN_FAILED`
- `ADMIN_ENDPOINT_ACCESSED`

Aceasta confirma ca auditul functioneaza pentru fluxuri reale ale aplicatiei.

### 52. Stare actuala dupa Audit Logging

In acest moment backend-ul are:
- aplicatie FastAPI functionala
- endpoint `/health`
- endpoint `POST /auth/register`
- endpoint `POST /auth/login`
- endpoint `GET /users/me`
- endpoint `GET /users/admin-only`
- configurare prin `.env`
- PostgreSQL local prin Docker Compose
- model ORM `User`
- model ORM `AuditLog`
- tabela `users`
- tabela `audit_logs`
- hashing si verificare de parola
- generare si decodare JWT
- identificarea utilizatorului curent din token
- fundatie RBAC functionala
- audit logging functional pentru register, login si acces admin

## Extinderea fundatiei backend: Audit Logs API

### 53. Introducerea schemei `AuditLogRead`

A fost creat fisierul:

```text
app/schemas/audit_log.py
```

Acesta defineste schema `AuditLogRead`, folosita pentru raspunsurile API care expun evenimentele de audit.

Scop:

- separarea modelului ORM `AuditLog` de contractul API
- controlarea campurilor returnate catre clinet
- pregatirea audit logs pentru afisare in dashboard-uri viitoare

### 54. Listarea audit logs prin service

Fisierul `app/services/audit_service.py` a fost extins cu functia:

```
list_audit_logs()
```

Aceasta:

- citeste evenimentele de audit din baza de date
- le ordoneaza descrescator dupa `created_at`
- aplica o limita pentru a evita returnarea intregii tabele

### 55. Introducerea endpoint-ului pentru audit logs

A fost creat fisierul:

```
app/api/routes/audit.py
```

A fost introdus endpoint-ul:

```
GET /admin/audit-logs
```
Acesta permite consultarea evenimentelor de audit prin API.

Endpoint-ul accepta paramentrul: ```limit``` pentru controlarea numarului de rezultate returnate.

### 56. Protejarea endpoint-ului de audit prin RBAC

Endpoint-ul `GET /admin/audit-logs` este protejat prin `require_role(...)`.

Rolurile permise sunt:

- `admin`
- `owner`
- `security_analyst`

Un utilizator standard cu rol `user` nu poate accesa acest endpoint.

### 57. Validarea endpoint-ului de audit

Endpoint-ul a fost testat prin `curl`.

Rezultate confirmate:

- utlizator cu rol `admin` -> `200 OK`
- utilizator cu rol `user` -> `403 Forbidden`

Aceasta confirma:

- listarea audit logs prin API
- protectia endpoint-ului prin RBAC
- separarea corecta intre utilizator obisnuit si roluri privilegiate

### 58. Stare actuala dupa Audit Logs API

In acest moment backend-ul are:

- audit logs salvate in PostgreSQL
- audit logs consultabile prin API
- endpoint `GET /admin/audit-logs`
- protectie RBAC pentru acces la audit logs
- validare functionala pentru admin si user normal

## Extinderea fundatiei backend: Security Events

### 59. Introducerea modelului `SecurityEvent`

A fost creat modelul ORM `SecurityEvent` in fisierul: `app/models/security_event.py`.

Acest model reprezinta primul strat de evenimente de securitate al platformei SentinelCore.

Spre deosebire de `AuditLog`, care inregistreaza factual actiuni din sistem, `SecurityEvent` reprezinta evenimentele relevante pentru zona de securitate si SIEM-light.

Modelul `SecurityEvent` contine urmatoarele campuri:

- `id`
- `event_type`
- `severity`
- `user_id`
- `email`
- `source`
- `message`
- `created_at`

### 60. Diferenta dintre Audit Logs si Security Events

In SentinelCore, cele doua concepte sunt separate:

**Audit Logs**
Audit logs raspund la intrebarea:

```
Ce s-a intamplat in sistem?
```

Exemple:
- utilizator creat
- login reusit
- login esuat
- endpoint admin accesat

**Security Events**
Security events raspund la intrebarea:

```
Ce evenimente sunt relevante pentru securitate?
```

Exemple:
- login esuat cu severitate `warn`
- login reusit cu severitate `info`
- acces admin cu severitate `info`

Aceasta separare este importanta deoarece auditul este jurnalul brut, iar security events reprezinta stratul de interpretare pentru zona SIEM-light.

### 61. Introducerea tipurilor de security events

A fost definit enum-ul `SecurityEventType`.

Evenimentele initale definite sunt:
- `USER_REGISTERED`
- `LOGIN_SUCCESS`
- `LOGIN_FAILED`
- `ADMIN_ACCESS`

Acestea acopera primele fluxuri reale deja existente in backend:
- register
- login reusit
- login esuat
- acces admin

### 62. Introducerea severitatilor de securitate

A fost definit enum-ul `SecuritySeverity`

Severitatile initiale sunt:
- `INFO`
- `WARN`
- `INCIDENT`

In etapa actuala au fost folosite:
- `INFO` pentru evenimente normale, dar relevante
- `WARN` pentru login esuat

Severitatea `INCIDENT` este pregatita pentru evenimente viitoare mai grave, cum ar fi detectii de tip brute-force sau comportament suspect.

### 63. Crearea tabelei `security_events`

Tabela `security_events` a fost create in PostgreSQL prin mecanismul temporar:

```
Base.metadata.create_all(bind=engine)
```

Pentru ca SQLAlchemy sa detecteze modelul, `SecurityEvent` a fost importat in `app.main.py`.

Tabela a fost verificata in PostgreSQL cu:

```
\dt
\d security_events
```

### 64. Introducerea serviciului pentru security events

A fost creat fisierul:

```
app/services/security_event_service.py
```

Acesta contine functiile:

```
create_security_event()
list_security_events()
```

Scopul serviciului este centralizarea logicii de creare si citire a evenimentelor de securitate.

Functia `create_security_event()` permite salvarea unui eveniment cu:
- tip eveniment
- severitate
- user asociat optional
- email asociat optional
- sursa
- mesaj descriptiv

Functia `list_security_events()` permite citirea evenimentelor de securitate in ordine descrescatoare dupa momentul producerii.

### 65. Introducerea schemei `SecurityEventRead`

A fost creat fisierul: ```app/schemas/security_event.py```.

Acesta defineste schema `SecurityEventRead`.

Scop:
- separarea modelului ORM de respons-ul API
- controlarea campurilor returnate catre client
- pregatirea datelor pentru dashboard-uri viitoare de securitate

### 66. Introducerea endpoint-ului pentru security events

A fost creat fisierul: ```app/api/routes/security.py```.

A fost introdus endpoint-ul: ```GET /security/events```.

Acesta permite consultarea evenimentelor de securitate prin API.

Endpoint-ul accepta parametrul: ```limit``` pentru limitarea numarului de evenimente returnate.

### 67. Protejarea endpoint-ului de security events prin RBAC

Endpoint-ul `GET /security/events` este protejat prin `require_role(...)`.

Rolurile permise sunt:
- `admin`
- `owner`
- `security_analyst`

Un utilizator standard cu rol `user` nu are acces la acest endpoint.

### 68. Integrarea security events in fluxurile existente

Security events au fost integrate in urmatoarele fluxuri:

**Register**
La crearea unui utilizator nou se creeaza evenimentul: ```USER_REGISTERED``` cu severitate: ```INFO```.

**Login reusit**
La autentificare reusita se creeaza evenimentul ```LOGIN_SUCCESS``` cu severitate: ```INFO```.

**Login esuat**
La autentificare esuata se creeaza evenimentul ```LOGIN_FAILED``` cu severitate: ```WARN```.
Acest eveniment este important deoarece poate deveni ulterior baza pentru detectii de tip brute-force.

**Acces admin**
La accesarea endpoint-ului admin-only se creeaza evenimentul: ```ADMIN_ACCESS``` cu severitate: ```INFO```.

### 69. Validarea endpoint-ului `GET /security/events`

Endpoint-ul a fost testat prin `curl`.

Rezultate confirmate:
- utilizator cu rol permis -> `200 OK`
- raspunsul contine security events reale
- evenimentele sunt returnate in format JSON
- severitatile apar corect ca `info` si `warn`

Evenimente confirmate in raspuns:
- `user_registered`
- `login_success`
- `login_failed`
- `admin_access`

### 70. Stare actuala dupa Security Events Foundation

In acest moment backend-ul are:

- aplicație FastAPI funcțională
- endpoint `/health`
- endpoint `POST /auth/register`
- endpoint `POST /auth/login`
- endpoint `GET /users/me`
- endpoint `GET /users/admin-only`
- endpoint `GET /admin/audit-logs`
- endpoint `GET /security/events`
- configurare prin `.env`
- PostgreSQL local prin Docker Compose
- model ORM `User`
- model ORM `AuditLog`
- model ORM `SecurityEvent`
- tabelă `users`
- tabelă `audit_logs`
- tabelă `security_events`
- hashing și verificare de parolă
- generare și decodare JWT
- identificarea utilizatorului curent din token
- fundație RBAC funcțională
- audit logging funcțional
- security events funcționale
- prim strat SIEM-light funcțional

## Extinderea fundatiei backend: Alembic Migrations

### 71. Trecerea de la `create_all()` la migratii

Pana in aceasta etapa, schema bazei de date a fost creata temporar prin: ```Base.metadata.create_all(bind=engine)```.

Acest mecanism a fost util pentru validarea initiala a modelelor si pentru intelegerea legaturii dintre SQLAlchemy si PostgreSQL.

Dupa introducerea modelelor principale (`User`, `AuditLog`, `SecurityEvent`), acest mecanism a fost eliminat din `app/main.py`.

De acum inainte, schema bazei de date este gestionata prin Alembic.

### 72. Motivul introducerii Alembic

Alembic a fost introdus pentru:
- versionarea schemei bazei de date
- evitarea resetarilor locale repetate
- gestionarea modificarilor viitoare de modele prin migratii
- apropierea proiectului de un workflow real de dezvoltare backend
- separarea responsabilitatii dintre aplicatie si schema DB

Aplicatia FastAPI nu mai trebuie sa creeze tabele la pornire.

### 73. Initializarea Alembic

Alembic a fost initalizat in backend.

Au fost create: 
- `alembic.ini`
- directorul `migrations/`
- directorul `migrations/versions/`
- fisierul `migrations/env.py`
- template-ul pentru migratii

### 74. Configurarea conexiunii Alembic la baza de date

In `alembic.ini`, conexiunea catre PostgreSQL local a fost configurata prin:

```
sqlalchemy.url = postgresql+psycopg://sentinelcore:sentinelcore@localhost:5432/sentinelcore
```

Aceasta configurare permite Alembic sa se conecteze la baza de date locala pentru generarea si aplicarea migratiilor.

### 75. Conectarea Alembic la modelele SQLAlchemy

In `migrations/env.py`, Alembic a fost conectat la metadata SQLAlchemy.

A fost importat `Base`: ```from app.core.database import Base``` si au fost importate modulele cu modelele principale:

```python
from app.models import audit_log, security_event, user  # noqa: F401
```

Importul este necesar chiar daca modulele nu sunt folosite direct: doar importate, modelele se inregistreaza in `Base.metadata`. Fara el, `--autogenerate` vede o schema goala si ar propune stergerea tuturor tabelelor. Comentariul `# noqa: F401` impiedica Ruff sa elimine importul ca nefolosit.

Apoi `target_metadata` a fost setat la: ```target_metadata = Base.metadata```.

Aceasta configurare permite comenzii ` --autogenerate` sa compare modelele SQLAlchemy cu schmea reala din baza de date.

### 76. Reset local al bazei de date pentru migratia initiala

Pentru ca mediul este inca local si datele nu au valoare operationala, baza de date a fost resetata inainte de migratia initiala.

Comenzile folosite:
```
docker compose down -v
docker compose up -d
```

Aceasta resetare a permis pornirea de la o baza PostgreSQL goala, astfel incat schmea initiala sa fie creata exclusiv prin Alembic.

### 77. Generarea migratiei initiale

Migratia initala a fost generata cu:

```
python -m alembic revision --autogenerate -m "initial schema"
```

Alembic a detectat modelele si a generat un fisier de migratie in: ```migrations/versions```.

Migratia initiala contine schema pentru:
- `users`
- `audit_logs`
- `security_events`
- tipurile enum asociate
- indexurile definite pe modele
- foreign key-urile dintre tabele

### 78. Aplicarea migratiei initiale

Migratia initiala a fost aplicata cu: ```python -m alembic upgrade head```.

Dupa aplicare, Alembic a creat si tabela: ```alembic_version```.

Aceasta stocheaza versiunea curenta a schemei bazei de date.

### 79. Verificarea rezultatului in PostgreSQL

Schema bazei de date a fost verificata in PostgreSQL cu: ```SELECT * FROM alembic_version;```.

Rezultatul a confirmat ca baza de date este la versiunea migratiei initiale.

### 80. Workflow standard pentru modificari viitoare de schema

De acum inainte, orice modificare a modelelor SQLAlchemy trebuie gestionata prin Alembic.

Workflow-ul standard este:

```
python -m alembic reivison --autogenerate -m "descriere modificare"
python -m alembic upgrade head
```

Migratiile generate trebuie verificate manual inainte de aplicare.

`--autogenerate` ajuta, dar nu inlocuieste verificarea logica a dezvoltatorului.

### 81. Stare actuala dupa Alembic

În acest moment backend-ul are:

- aplicație FastAPI funcțională
- PostgreSQL local prin Docker Compose
- schema bazei de date gestionată prin Alembic
- `create_all()` eliminat din `main.py`
- migrație inițială generată și aplicată
- tabela `alembic_version` creată
- tabelele `users`, `audit_logs` și `security_events` create prin migrație
- workflow matur pentru modificări viitoare ale schemei DB

## Extinderea fundatiei backend: Tests Foundation

### 82. Introducerea testelor automate

A fost introdusa prima fundatie de teste automate pentru backend-ul SentinelCore.

Scopul acestei etape este trecerea de la testare manuala prin `curl` / Swagger la validarea automata a fluxurilor principale.

Au fost adaugate dependentele:
- `pytest`
- `httpx`

Acestea permit rularea testelor automate si folosirea `TestClient` pentru testarea aplicatiei FastAPI.

### 83. Configurarea `pyproject.toml` pentru teste

Fisierul `pyproject.toml` a fost actualizat pentru testare.

A fost adaugata configuratia:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

Scop:
- testele sunt cautate in directorul `tests`
- importurile absolute de forma `from app...` funtioneaza corect in timpul testarii

De asemenea, a fost configurata descoperirea explicita a pachetului Python:
```toml
[tool.setuptools.packages.find]
include = ["app*"]
exclude = ["migrations*", "tests*"]
```

Aceasta configurare a fost necesara deoarece dupa introducerea Alembic, `setuptools` detecta atat `app`, cat si `migrations` ca pachete top-level.

### 84. Introducerea bazei de date separate pentru teste

A fost create o baza de date separata pentru teste: ```sentinelcore_test```.

Scop:
- testele nu modifica baza de date de development
- datele de test sunt izolate
- testele pot crea si sterge date fara risc pentru mediul local principal

A fost adaugata variabila:
```env
TEST_DATABASE_URL=postgresql+psycopg://sentinelcore:sentinelcore@localhost:5432/sentinelcore_test
```
in configuratia locala si in `.env.example`.

### 85. Introducerea fisierului `tests/conftest.py`

A fost creat fisierul: ```tests/conftest.py`.

Acesta defineste fixture-uri reutilizabile pentru teste

Elementele principale:
- `test_engine`
- `TestingSessionLocal`
- fixture `db_session`
- fixture `client`

Scop:
- conectarea testelor la baza de date `sentinelcore_test`
- crearea tabelelor inainte de test
- stergerea tabelelor dupa test
- suprascrierea dependentei `get_db`
- rularea requesturilor prin `TestClient`

### 86. Override pentru `get_db`

In teste, dependenta reala: ``` get_db()``` este suprascrisa cu o sesiune de test.

Scop:
- endpoint-urile folosesc baza de date de test
- logica aplicatiei este testata aproape real
- testele nu ating baza de date principala

Aceasta abordare permite testarea endpoint-urilor FastAPI fara a porni un server HTTP separat.

### 87. Test pentru endpoint-ul `/health`

A fost creat testul: ```/tests/test_health```.

Acesta verifica endpoint-ul:
```http
GET /health
```

Rezultatul asteptat:
```JSON
{"status": "ok"}
```
Acest test confirma ca aplicatia FastAPI se importa corect si ca routerul de health este functional.

### 88. Teste pentru register

A fost creat fisierul: ```tests/test_auth.py```.

Au fost validate urmatoarele scenarii:

**Register valid**
Endpoint testat:
```http
POST /auth/register
```

Rezultatul asteptat:
- status `201 Created`
- user creat cu `username` si `email`
- `hashed_password` nu este returnat in response

**Register cu email duplicat**

Rezultat asteptat:
- status `400 Bad Request`
- mesaj: `Email already registered`

### 89. Teste pentru login

Au fost validate urmatorele scenarii

**Login valid**

Endpoint testat:
```http
POST /auth/login
```

Rezultat asteptat:
- status `200 ok`
- response contine `access_token`
- `token_type` este `bearer`

**Login cu parola gresita**

Rezultat asteptat:
- status `401 Unauthorized`
- mesaj: `Invalid email or password`

### 90. Validarea testelor

Testele au fost rulate cu:
```bash
python -m pytest
```

Rezultatul confirmat:
``` 5 passed```

Aceasta confirma ca prima etapa de teste automate functioneaza corect.

### 91. Stare actuala dupa Tests Foundation Phase 1

In acest moment backend-ul are:
- test automat pentru `/health`
- teste automate pentru register
- teste automate pentru login
- baza de date separata pentru teste
- fixture pentru sesiune DB de test
- override pentru `get_db`
- `TestClient` functional
- rulare automata prin `pytest`

Aceasta marcheaza trecerea de la testare manuala la o prima plasa de siguranta automata pentru backend.

## Extinderea testelor backend: Tests Foundation Phase 2

### 92. Scopul fazei 2 de testare

Dupa validarea endpoint-urilor de baza (`/health`, register si login), testele au fost extinse catre rutele protejate ale aplicatiei.

Scopul acestei faze este validarea automata a:
- autentificarii prin JWT
- accesului la endpoint-uri protejate
- comportamentului fara token
- controlului de acces pe roluri
- accesului admin la audit logs
- accesului admin la security logs

Aceasta etapa confirma ca mecanismele IAM si RBAC functioneaza nu doar manual, ci si automat prin teste.

### 93. Fisier nou pentru rute protejate

A fost creat fisierul:
```text
tests/test_protected_routes.py
```

Acesta contine teste pentru endpoint-urile care necesita autentificare sau roluri speciale.

### 94. Helper functions pentru teste

In `test_protected_routes.py` au fost introduse functii helper pentru reducerea duplicarii codului:

```python
register_user()
login_user()
auth_headers()
promote_user_to_admin()
```

Scopul acestor functii este:
- crearea rapida a unui user de test
- autentificarea userului si obtinerea tokenului JWT
- construirea headerului `Authorization`
- promovarea unui user la rolul `Admin` direct in baza de date de test

### 95. Testarea endpoint-ului `/users/me`

A fost testat endpoint-ul:

```http
GET /users/me
```

Scenarii validate:

**Cu token valid**
Rezultatul asteptat:
- status `200 OK`
- response-ul contine datele userului autentificat
- `hashed_password` nu este returnat in response

**Fara token**
Rezultatul asteptat:
- status `401 Unauthorized`

Acest test confirma ca endpoint-ul este protejat corect si nu permite acces anonim.

### 96. Testarea endpoint-ului `/users/admin-only`

A fost testat endpoint-ul:
```http
GET /users/admin-only
```

Scenarii valide:

**User normal**
Rezultat asteptat:
- status `403 Forbidden`

Acest test confirma ca un user autentificat, dar fara rol potrivit, nu poate accesa ruta de admin.

**User admin**
Rezultat asteptat:
- status `200 OK`
- response-ul confirma userul admin
- rolul returnat este `admin`

Acest test valideaza fundatia RBAC

### 97. Promovarea userului la admin in test

Pentru ca aplicatia nu are inca un endpoint dedicat pentru schimbarea rolului unui user, promovarea la admin este facuta direct in baza de date de test:

```python
user.role = UserRole.ADMIN
db_session.commit()
```

Aceasta abordare este acceptabila in teste deoarece reprezinta doar setup de test, nu logica de productie.

In aplicatia reala, schimbarea rolurilor va trebui facuta ulterior prin endpoint-uri administrative controlate si auditate.

### 98. Testarea endpoint-ului de audit logs

A fost testat endpoint-ul

```http
GET /admin/audit-logs?limit=20
```

Scenariu validat:
- user admin autentificat
- status `200 OK`
- response-ul este o lista

Acest test confirma ca audit logs pot fi accesate prin API de catre rolurile autorizate.

### 99. Testarea endpoint-ului de security events

A fost testat endpoint-ul:

```http
GET /security/events?limit=20
```

Scenariu validat:
- user admin autentificat
- status `200 OK`
- response-ul este o lista

Acest test confirma ca security events pot fi consultate prin API de catre rolurile autorizate.

### 100. Teste validate in Phase 2

In aceasta faza au fost validate urmatoarele scenarii:
```
/users/me with token            -> 200
/users/me without token         -> 401
/users/admin-only regular user  -> 403
/users/admin-only admin         -> 200
/admin/audit-logs admin         -> 200
/security/events admin          -> 200
```

Impreuna cu testele din Phase 1, backend-ul are acum teste automate pentru:
```
/health                         -> 200
/auth/register                  -> 201
/auth/register duplicate email  -> 400
/auth/login                     -> 200 + token
/auth/login wrong password      -> 401
/users/me with token            -> 200
/users/me without token         -> 401
/users/admin-only regular user  -> 403
/users/admin-only admin         -> 200
/admin/audit-logs admin         -> 200
/security/events admin          -> 200
```

### 101. Rezultatul testelor

Testele au fost rulate cu:
```bash
python -m pytest -v
```

Rezultatul confirmat:

```
11 passed
```

Aceasta confirma ca fundatia de autentificare, autorizare si acces la endpoint-uri protejate este validata automat.

### 102. Stare actuala dupa Tests Foundation Phase 2

In acest moment backend-ul are:
- teste automate pentru health check
- teste automate pentru register
- teste automate pentru login
- teste automate pentru endpoint-uri protejate
- teste automate pentru JWT access
- teste automate pentru acces fara token
- teste automate pentru RBAC user/admin
- teste automate pentru audit logs endpoint
- teste automate pentru security events endpoint
- baza de date separata pentru teste
- override pentru `get_db`
- setup de test prin `conftest.py`
- 11 teste automate validate

Aceasta etapa marcheaza trecerea backend-ului SentinelCore de la testare manuala la verificare automata pentru fluxurile IAM/RBAC principale.

## Backend CI Pipeline - Phase 1

### 103. Introducerea CI pentru backend

A fost introdus primul workflow de Continuous Integration pentru backend-ul SentinelCore.

Scopul acestei etape este ca testele backend sa ruleze automat in GitHub Actions la modificari relevante ale codului.

Pana in aceasta etapa, testele erau rulate local cu:

```bash
python -m pytest -v
```

Dupa introducerea CI, testele sunt rulate si automat in GitHub, ceea ce ofera o verificare reproductibila a backend-ului.

### 104. Fisierul workflow

A fost creat fisierul:

```
.github/workflows/backend-ci.yml
```

Acesta defineste pipeline-ul pentru testarea backend-ului.

Workflow-ul se numeste:

```yml
name: Backend CI
```

### 105. Trigger-ele workflow-ului

Workflow-ul ruleaza automat la:

- `push` pe branch-ul `main`
- `pull_request` catre branch-ul `main`

Triggerul este limitat prin `paths`, astfel incat pipeline-ul sa ruleze doar cand sunt modificate fisiere relevante pentru backend sau workflow-ul CI.

Configuratia folosita:

```yml
on:
  workflow_dispatch:

  push:
    branches:
      - main
    paths:
      - "backend/**"
      - ".github/workflows/backend-ci.yml"

  pull_request:
    branches:
      - main
```

Initial, filtrul `paths` exista si pe `pull_request`. Ulterior a fost eliminat, astfel incat orice Pull Request catre `main` ruleaza CI-ul.

A fost postrat si `workflow_dispatch`, pentru a permite rularea manuala a workflow-ului din interfata GitHub Actions.

### 106. PostgreSQL ca serviciu in GitHub Actions

Pentru ca testele backend folosesc baza de date, workflow-ul porneste automat un serviciu PostgreSQL.

Serviciul foloseste imaginea:

```yml
postgres:16
```

Ulterior, imaginea a fost aliniata la `postgres:17`, aceeasi versiune folosita local in Docker Compose.

Configuratia principala:

```yml
POSTGRES_USER: sentinelcore 
POSTGRES_PASSWORD: sentinelcore 
POSTGRES_DB: sentinelcore_test
```

Baza de date folosita in CI este:

```
sentinelcore_test
```

Aceasta pastreaza aceeasi strategie folosita local: testele nu ruleaza pe baza de date de development.

### 107. Health check pentru PostgreSQL

In workflow a fost configurat un health check pentru PostgreSQL:

```yml
--health-cmd="pg_isready -U sentinelcore -d sentinelcore_test" 
--health-interval=10s 
--health-timeout=5s 
--health-retries=5
```

Scopul acestuia este ca job-ul sa astepte pana cand PostgreSQL este pregatit inainte de rularea testelor.

### 108. Variabile de mediu pentru CI

Workflow-ul defineste variabilele necesare pentru rularea aplicatiei si testelor:

```yml
TEST_DATABASE_URL: postgresql+psycopg://sentinelcore:sentinelcore@localhost:5432/sentinelcore_test 
DATABASE_URL: postgresql+psycopg://sentinelcore:sentinelcore@localhost:5432/sentinelcore_test 
SECRET_KEY: ci-test-secret-key-for-sentinelcore-minimum-32-bytes 
ALGORITHM: HS256 
ACCESS_TOKEN_EXPIRE_MINUTES: 30
```

`TEST_DATABASE_URL` este folosit pentru testele automate.
`DATABASE_URL` este setat pentru ca aplicatia sa poata fi importata corect in mediul CI.
`SECRET_KEY` a fost setat la o valoare suficient de lunga pentru a evita warning-urile legate de lungimea minima recomandata pentru HMAC SHA256.

### 109. Pasii workflow-ului

Workflow-ul executa urmatorii pasii:

1. checkout repository
2. setup Python
3. instalare dependente backend
4. rulare teste backend

Pasii principali:

```yml
- name: Checkout repository 
  uses: actions/checkout@v5 

- name: Set up Python 
  uses: actions/setup-python@v6 
  with: python-version: "3.12" 
  
- name: Install backend dependencies 
  working-directory: backend 
  run: | 
    python -m pip install --upgrade pip 
    python -m pip install -e . 
    
- name: Run backend tests 
  working-directory: backend 
  run: |
    python -m pytest -v
```

### 110. Problema intalnita: lipsa `pydantic[email]`

La prima rulare in CI, workflow-ul a esuat deoarece mediul GitHub Actions nu avea instalat suportul necesar pentru validarea campurilor de tip email in Pydantic.

Problema a aratat ca mediul local avea dependente disponibile, dar proiectul nu declara complet cerintele in `pyproject.toml`.

Aceasta dependenta a fost adaugata in `backend/pyproject.toml`.

Lectia acestei etape:
- CI-ul trebuie sa poata reproduce mediul proiectului doar din fisierele versionate
- Dependentele folosite de aplicatie trebuie declarate explicit
- Nu ne bazam pe ce este instalat accidental in mediul local

### 111. Warning JWT rezolvat

In timpul rularii testelor, PyJWT a afisat un warning legat de lungimea prea mica a cheii HMAC folosite pentru `HS256`.

Problema era produsă de:

```yml
SECRET_KEY: test-secret-key-for-ci
```

Rezolvare:

```yml
SECRET_KEY: ci-test-secret-key-for-sentinelcore-minimum-32-bytes
```

După această modificare, warning-urile legate de JWT au fost eliminate.

### 112. Rezultatul final al workflow-ului

Dupa corectii, workflow-ul ruleaza corect in GitHub Actions.

Rezultat confirmat:

```
11 passed
```

Testele validate in CI:

```
/health -> 200 
/auth/register -> 201 
/auth/register duplicate email -> 400 
/auth/login -> 200 + token 
/auth/login wrong password -> 401 
/users/me with token -> 200 
/users/me without token -> 401 
/users/admin-only regular user -> 403 
/users/admin-only admin -> 200 
/admin/audit-logs admin -> 200 
/security/events admin -> 200
```

### 113. Stare actuala dupa Backend CI Phase 1

In acest moment SentinelCore are:
- workflow GitHub Actions pentru backend
- PostgreSQL pornit ca serviciu in CI
- baza de date de test `sentinelcore_test`
- instalare automata a dependentelor backend
- rulare automata a testelor cu `pytest`
- 11 teste validate in CI
- trigger limitat prin `paths`
- posibilitate de rulare manuala prin `workflow_dispatch`
- actiuni GitHub actualizate la versiuni compatibile cu Node 24
- warning JWT rezolvat prin `SECRET_KEY` mai puternic
- pipeline verde in GitHub Actions

Aceasta etapa marcheaza trecerea backend-ului de la testare locala la validare automata in pipeline CI.

## Backend Code Quality CI - Ruff Phase 1

### 114. Introducerea Ruff pentru calitatea codului

A fost introdus `Ruff` pentru verificarea calitatii codului Python si pentru verificarea formatarii.

Scopul acestei etape este ca backend-ul SentinelCore sa nu fie verificat doar functional prin teste, ci si stilistic si structural.

Pana in aceasta etapa, CI-ul valida:

```
pytest -> testele backend
```

Dupa introducerea Ruff, CI-ul valideaza si:

```bash
ruff check .
ruff format --check .
```

Aceasta marcheaza trecerea de la simpla rulare a testelor la un prim standard automat de calitate a codului.

### 115. Configurarea Ruff in `pyproject.toml`

In `backend/pyproject.toml` a fost adaugata dependenta:

```toml
"ruff",
```

A fost adaugata si configuratia Ruff:

```
[tool.ruff] 
line-length = 88 
target-version = "py312" 

[tool.ruff.lint] 
select = [
  "E",
  "F",
  "I",
  "B",
  "UP",
  ] 
ignore = [] 

[tool.ruff.format] 
quote-style = "double" 
indent-style = "space" 
line-ending = "auto"
```

Regulile selectate au urmatorul rol:
- E -> reguli de stil Python
- F -> erori de tip Pyflakes, iumporturi sau variabile nefolosite
- I -> ordine importuri
- B -> posibile bug-uri comune detectate de flake8-bugbear
- UP -> modernizare cod Python pentru versiuni mai noi

### 116. Verificari Ruff rulate local

Inainte de integrarea in CI, Ruff a fost rulat local:

```bash
python -m ruff check .
python -m ruff format --check .
```

Initial, Ruff a gasit mai multe probleme, desi testele treceau.

Acest lucru a confirmat diferenta dintre:

- teste functionale -> aplicatia merge
- linting -> codul respecta standardul de calitate

Testele treceau, dar Ruff a indentificat probleme de stil, modernizare si bune practici.

### 117. Probleme identificate de Ruff

Ruff a identificat urmatoarele categorii principale de probleme:
- B008 -> apeluri Depends(...) in argumente default
- B904 -> ridicare de exceptii in except fara `from`
- UP042 -> enum-uri definite ca str + enum.Enum in loc de StrEnum

Aceste probleme nu stricau functionalitatea aplicatiei, dar indicau zone unde codul putea fi modernizat si clarificat.

### 118. Modernizarea dependecy injection cu `Annotated`

Pentru a rezolva regulile `B008`, endpoint-urile FastAPI au fost modernizate folosind `typing.Annotated`.

In locul stilului clasic:

```python
def read_current_user(current_user: User = Depends(get_current_user)) -> return current_user
```

a fost folosit stilul modern:

```python
def read_current_user(
  current_user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
  return current_user
```

Aceasta schimbare a fost aplicata in:
- app/api/deps.py
- app/api/routes/auth.py
- app/api/routes/users.py
- app/api/routes/audit.py
- app/api/routes/security.py

Avantaje:
- cod mai compatibil cu stilul modern FastAPI
- eliminarea warning-urilor Ruff `B008`
- separarea mai clara intre tipul datelor si mecanismul de dependency injection
- cod mai usor de verificat static

### 119. Rezolvarea regulii `B904`

In `app/api/deps.py`, Ruff a semnalat ca o exceptie ridicata in interiorul unui bloc `except` trebuie sa pastreze cauza initiala.

In loc de:

```python
except InvalidTokenError:
  raise credentials_exception
```

s-a folosit:

```python
except InvalidTokenError as exc:
  raise credentials_exception from exc
```

Aceasta modificare face mai clar lantul cazual al erorilor si ajuta debugging-ul.

### 120. Modificarea enum-urilor cu `StrEnum`

Pentru regula `UP042`, enum-urile definite prin combinatia:

```python
class UserRole(str, enumEnum):
  ...
```

au fost modernizate folosind:

```python
from enum import StrEnum
```

si:

```python
class UserRole(StrEnum):
  ...
```

Aceasta schimbare a fost aplicata pentru:
- UserRole
- AuditEventType
- SecurityEventType
- SecuritySeverity

Fisiere afectate:
- app/models/user.py
- app/models/audit_log.py
- app/models/security_event.py

Aceasta modernizare este potrivita deoarece backend-ul foloseste Python 3.12.

### 121. Ruff format

Ruff format a fost folosit pentru verificarea formatarii codului:

```bash
python -m ruff format --check .
```

Rezultatul local a confirmat ca fisierele sunt formatate corect:

```bash
32 files already formatted
```

Aceasta inseamna ca standardul de formatare este consistent in backend.

### 122. Validarea finala locala

Dupa corectarea problemelor, au fost rulate local:

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -v
```

Rezultatul final:
- ruff check -> All checks passed
- ruff format --check -> passed
- pytest -> 11 passed

Aceasta confirma ca backend-ul respecta atat testele functionale, cat si regulile de calitate a codului.

### 123. Integrarea Ruff in GitHub Actions

Dupa validarea locala, Ruff a fost integrat in workflow-ul GitHub Actions

In `.github/workflows/backend-ci.yml`, dupa instalarea dependentelor si inainte de rularea testelor, au fost adaugati pasii:

```yml
- name: Run Ruff lint 
  working-directory: backend 
  run: | 
    python -m ruff check . 
    
- name: Run Ruff format check 
  working-directory: backend 
  run: | 
    python -m ruff format --check .
```

Ordinea actuala a pipeline-ului backend este:
- install dependencies
- ruff check
- ruff format --check
- pytest

Aceasta ordine este intentionata: codul trebuie sa respecte standardul de calitate inainte ca testele sa fie rulate.

### 124. Rezultatul in CI

Workflow-ul GitHub Actions a fost rulat dupa integrarea Ruff.

Rezultat confirmat:

- Ruff lint -> passed
- Ruff format check -> passed
- pytest -> 11 passed

Pipeline-ul backend este verde.

### 125. Stare actuala dupa Ruff Phase 1

In acest moment backend-ul SentinelCore are:
- teste automate locale
- teste automate in GitHub Actions
- PostgreSQL ca serviciu in CI
- 11 teste validate in CI
- Ruff instalat si configurat
- linting automat prin `ruff check`
- verificare automata a formatarii prin `ruff format --check`
- cod modernizat cu `Annotated`
- enum-uri modernizate cu `StrEnum`
- regula `B904` rezolvata corect
- pipeline CI verde pentru teste si calitatea codului

Aceasta etapa marcheaza introducerea primului strat real de code quality automation in SentinelCore.

## Backend Security Checks - Phase 1

### 126. Introducerea verificarilor de securitate in backend

A fost introdus primul strat de verificari automate de securitate pentru backend-ul SentinelCore.

Pana in aceasta etapa, pipeline-ul valida:

```bash
ruff check .
ruff format --check .
pytest
```

Dupa aceasta etapa, pipeline-ul valideaza si:

```bash
bandit
gitleaks
```

Scopul acestei faze este ca proiectul sa nu fie verificat doar functional si stilistic, ci si din perspectiva securitatii de baza.

### 127. Introducerea Bandit

A fost introdus `Bandit` pentru scanarea codului Python.

Bandit este folosit pentru detectarea unor probleme comune de securitate in codul sursa Python.

In `backend/pyproject.toml` a fost adaugata dependenta:

```toml
"bandit[toml]",
```

S-a folosit varianta `[toml]` pentru ca Bandit sa poata fi configurat prin `pyproject.toml`.

### 128. Configurarea Bandit

In `backend/pyproject.toml` a fost adaugata configuratia:

```toml
[tool.bandit]
exclude_dirs = ["tests", ".venv", "migrations"]
skips = []
```

Au fost excluse:
- tests -> testele pot contine parole sau valori hardcodate de test
- .venv -> mediul virtual nu trebuie scanat
- migrations -> migratiile Alembic nu reprezinta logica aplicatiei

Pentru inceput, scanarea Bandit se concentreaza pe codul aplicatiei din: `app/`

### 129. Rularea locala Bandit

Bandit a fost rulat local din directorul `backend` cu:

```bash
python -m bandit -r app -c pyproject.toml
```

Initial, Bandit a raportat un issue de severitate mica:

```
B106: hardcoded_password_funcarg
Possible hardcoded password: 'bearer'
```

Locatia raportata era in endpoint-ul de login, la raspunsul:

```python
return Token(access_token=access_token, token_type="bearer")
```

### 130. Tratarea false positive-ului Bandit B106

Raportarea `B106` a fost analizata si clasificata ca false positive.

Valoarea: `bearer` nu este o parola, token real sau secret. Este valoarea standard OAuth2 pentru tipul token-ului returnat clientului.

Rezolvarea a fost facuta punctual, prin adaugarea comentariului:

```python
return Token(
  access_token = access_token,
  # OAuth2 token type, not a password or secret.
  token_type="bearer",  # nosec B106
)
```

Decizia importanta:
- regula `B106` nu a fost dezactivata global
- exceptia a fost aplicata doar pe linia analizata
- regula ramane activa pentru a detecta eventuale parole reale hardcodate in viitor

Aceasta este abordatea corecta deoarece evita suprimarea unei reguli utile la nivelul intregului proiect.

### 131. Validarea Bandit dupa corectie

Dupa tratarea false positive-ului, au fost rulate din nou:
- python -m ruff check .
- python -m ruff format --check .
- python -m bandit -r app -c pyproject.toml
- python -m pytest -v

Rezultatul local:
- ruff check -> All checks passed
- ruff format --check -> passed
- bandit -> No issues identified
- pytest -> 11 passed

Aceasta confirma ca backend-ul trece atat verificarile functionale, cat si verificarile de calitate si securitate Python.

### 132. Introducerea Gitleaks

A fost introdus `Gitleaks` pentru scanarea secretelor in repository.

Gitleaks este folosit pentru detectarea de:
- parole
- token-uri
- API keys
- private key
- secrete hardcodate
- credentiale expuse accidental

Aceasta verificare este importanta mai ales deoarece SentinelCore urmeaza sa poata fi facut public dupa ce repo-ul este considerat sigur.

### 133. Problema locala intalnita cu Docker pe Fedora

La prima rulare locala cu Docker, Gitleaks nu a scanat repository-ul real.

Rezultatul gresit arata:
- 0 commits scanned
- scanned ~0 bytes
- fatal: not a git repository

Aceasta iesire nu a fost acceptata ca valida, deoarece `no leaks found` nu are valoare daca au fost scanate `0` commit-uri.

Problema a fost investigata prin rularea unui container Alpine:

```bash
docker run --rm -v "$(pwd):/repo" -w /repo alpine:latest ls -la
```

Rezultatul a indicat:

```
Permission denied
```

Cauza a fost legata de permisiunile Docker/SELinux pe Fedora.

### 134. Rezolvarea problemei SELinuz cu `:Z`.

Pe Fedora, problema de mount Docker a fost rezolvata prin folosirea optiunii `:Z`:

```bash
docker run --rm -v "$(pwd):/repo:Z" -w /repo alpine:latest ls -la
```

Dupa aceasta modificare, containerul a putut vedea corect repository-ul:
- .git
- .github
- backend
- frontend
- docs

Comanda locala corecta pentru Gitleaks pe Fedora devine:

```bash
docker run --rm -v "$(pwd):/repo:Z" -w /repo zricethezav/gitleaks:latest
```

### 135. Validarea locala Gitleaks

Dupa rezolvarea problemei de mount, Gitleaks a scanat corect repository-ul.

Rezultat confirmat:

```
23 commits scanned
scanned ~280700 bytes
no leaks found
```

Aceasta confirma ca Gitleaks a scanat istoricul Git disponibil si nu doar un director gol.

### 136. Integrarea Bandit in GitHub Actions

Dupa validarea locala, Bandit a fost integrat in workflow-ul backend.

In `.github/workflows/backend-ci.yml`, Bandit ruleaza dupa Ruff si inainte de pytest:

```yml
  - name: Run Bandit security scan 
    working-directory: backend 
    run: | 
      python -m bandit -r app -c pyproject.toml
```

Ordinea actuala jobului backend devine:
- install dependencies
- ruff check
- ruff format --check
- badit
- pytest

Aceasta ordine este intentionata:
- mai intai se valideaza calitatea codului
- apoi se ruleaza scanarea de securitate Python
- apoi se ruleaza testele functionale

### 137. Integrarea Gitleaks in GitHub Actions

Gitleaks a fost integrat in workflow ca job separat.

Initial a fost testata varianta cu:

```yml
uses: gitleaks/gitleaks-action@v2
```

Aceasta functiona, dar producea un warning de infrastructura legat de Node.js 20.

Pentru a elimina warning-ul, Gitleaks a fost schimbat sa ruleze prin Docker in CI:

```yml
gitleaks:
  name: Run Gitleaks secret scan 
  runs-on: ubuntu-latest 
  
  steps: 
    - name: Checkout repository 
      uses: actions/checkout@v5 
      with: 
        fetch-depth: 0 
    
    - name: Run Gitleaks with Docker 
      run: | 
        docker run --rm -v "$PWD:/repo" -w /repo zricethezav/gitleaks:latest detect --source=/repo --verbose
```

In CI nu este necesara optinuea `:Z`, deoarece aceasta a fost specifica mediului local Fedora/SELinux.

### 138. Scanarea istoricului Git

Pentru jobul Gitleaks, checkout-ul foloseste: `fetch-depth: 0`.

Aceasta setare descarca istoricul complet al repository-ului in runner.

Motiv:
- Gitleaks trebuie sa poata scana si istoricul Git, nu doar ultimul snapshot
- Daca un secret a fost comis in trecut, el poate fi detectat chiar daca fisierul curent a fost curatat.

Aceasta abordare este importanta pentru pregatirea repository-ului in vederea publicarii ulterioare.

### 139. Rezultatul final in CI

Dupa integrarea Bandit si Gitleaks, workflow-ul GitHub Actions a fost rulat cu success.

Rezultat confirmat:

```
Ruff lint -> passed
Ruff format check -> passed
Bandit security scan -> passed
Gitleaks secret scan -> passed
pytest -> 11 passed
```

Pipeline-ul este verde si fara warning-uri relevante.

### 140. Starea actuala dupa Security Checks Phase 1

In acest moment backend-ul SentinelCore are:
- teste automate locale
- teste automate in GitHub Actions
- PostgreSQL ca serviciu in CI
- Ruff pentru linting si format check
- Bandit pentru scanare de securitate Python
- Gitleaks pentru scanare de secrete
- Gitleaks rulat local prin Docker cu `:Z` pe Fedora
- Gitleaks rulat in CI prin Docker
- scanare Git history prin `fetch-depth:0`
- false positive Bandit tratat punctual cu `# nosec B106`
- 11 teste validate
- pipeline CI verde
- pipeline fara warning-uri relevante

Aceasta etapa marcheaza introducerea primului strat real de DevSecOps in SentinelCore.

## Admin User Management - Phase 1

### 141. Introducerea administarii utilizatorilor

A fost introdusa prima etapa din zona de administrare a utilizatorilor.

Scopul acestei faze este ca utilizatorii cu rol administrativ sa poata consulta lista utilizatorilor existenti in sistem.

Endpoint introdus:

```
GET /admin/users
```

Aceasta etapa marcheaza inceputul zonei de Admin User Management din SentinelCore.

### 142. Scopul endpoint-ului `GET /admin/users`

Endpoint-ul permite listarea utilizatorilor existenti in aplicatie.

Accesul este permis doar pentru rolurile administrative:
- admin
- owner

Un utilizator normal nu poate accesa aceasta ruta.

Aceasta separare este importanta pentru fundatia IAM/RBAC, deoarece datele despre utilizatori nu trebuie expuse tuturor conturilor autentificate.

### 143. Service pentru listarea utilizatorilor

In `app/services/user_service.py` a fost adaugata functia:

```python
def list_users(
    db: Session,
    limit: int = 50,
    offset: int = 0,
) -> list[User]:
    statement = select(User).order_by(User.id).offset(offset).limit(limit) 
    return list(db.scalars(statement).all())
```

Aceasta functie separa logica de acces la baza de date de logica rutei API.

Scop:
- pastrarea rutelor cat mai curate
- reutilizarea logicii de listare in alte zone ale aplicatiei
- pregatirea pentru paginare mai avansata in viitor

### 144. Ruta noua pentru administrarea utilizatorilor

A fost creat fisierul:

```
app/api/routes/admin_users.py
```

Routerul foloseste prefixul:

```python
router = APIRouter(prefix="/admin/users", tags=["admin-users"])
```

Endpoint-ul principal introdus:

```python
@router.get("", response_model=list[UserRead])
def read_users(...)
```

Acesta returneaza lista utilizatorilor folosind schema publica `UserRead`.

### 145. Protectia endpoint-ului prin RBAC

Endpoint-ul este protejat cu dependency-ul:

```python
Depends(require_role(UserRole.ADMIN, UserRole.OWNER))
```

Aceasta inseamna ca doar utilizatorii cu rolurile de `ADMIN` sau `OWNER` pot accesa lista utilizatorilor.

Un user normal primeste: `403 Forbidden`.

Aceasta verificare confirma ca RBAC-ul este aplicat si pe noile endpoint-uri administrative, nu doar pe endpoint-ul de test `/users/admin-only`.

### 146. Folosirea `Annotated` pentru dependecy injection

Endpoint-ul a fost scris folosind stilul modern FastAPI cu `typing.Annotated`.

Aceasta abordare pastreaza codul compatibil cu standardele introduse in etapa Ruff si evita problam `B008`.

### 147. Parametri de paginare de baza

Endpoint-ul accepta parametri de baza:

```
limit
offset
```

Configuratie:

```
limit: Annotated[int, Query(ge=1, le=200)] =50
offset: Annotated[int, Query(ge=0)] = 0
```

Aceasta implementare ofera o fundatie simpla pentru paginare.

Limitarea la maximum `200` previne cereri prea mari catre API.

### 148. Audit log pentru listarea utilizatorilor

Cand un admin acceseaza lista utilizatorilor, aplicatia creeaza un audit log.

Eveniment folosit:

```
AuditEventType.ADMIN_ENDPOINT_ACCESSED
```

Mesaj:

```
Admin listed users
```

Aceasta decizie este importanta deoarece accesul la lista de utilizatori este o actiune administrativa si trebuie urmarita.

In SentinelCore, actiunile administrative trebuie sa fie vizibile in audit trail.

### 149. Security event pentru listarea utilizatorilor

Pe langa audit, endpoint-ul creeaza si un security event.

Eveniment folosit: `SecurityEventType.ADMIN_ACCESS`

Severitate: `SecuritySeverity.INFO`

Mesaj: `Admin listed users`

Aceasta clasificare marcheaza actiunea ca eveniment de securitate informativ.

Nu este incident, dar este o actiune relevanta pentru vizibilitatea administrativa.

### 150. Inregistrarea routerului in aplicatie

Routerul `admin_users` a fost inclus in `app/main.py`.

A fost adaugat importul: `from app.api.routes import admin_users` si routerul a fost inregistrat in aplicatia FastAPI: `app.include_router(admin_users.router)

Astfel endpoint-ul devine disponibil in aplicatie sub ruta: `GET /admin/users`

### 151. Teste automate pentru `GET /admin/users`

Au fost adugate teste in: `tests/test_protected_routes.py`

Scenarii validate:
- user normal -> 403 Forbidden
- admin user -> 200 OK + lista utilizatori

Primul test confirma ca un utilizator fara rol administrativ nu poate accesa endpoint-ul.

Al doilea test confirma ca un admin poate accesa lista utilizatorilor si ca raspunsul nu expune `hashed_password`.

### 152. Test pentru user normal

Scenariu:
1. se creeaza un user normal
2. userul face login
3. userul incearca sa acceseze GET /admin/users
4. API-ul raspunde cu 403

Rezultat asteptat: `403 Forbidden`

Acest test valideaza protectia RBAC.

### 153. Test pentru user admin

Scenariu:
1. se creeaza un user
2. userul este promovat la admin in baza de date de test
3. userul face login
4. acceseaza GET /admin/users
5. API-ul raspunde cu lista de utilizatori

Rezultatul asteptat: `200 OK`

Validari suplimentare:
- response-ul este lista
- lista contine userul creat
- email-ul este corect
- username-ul este corect
- hashed_password nu este expus

Aceasta verificare este importanta pentru securitatea raspunsului API.

### 154. Validarea locala

Dupa implementare au fost rulate local:

```bash
python -m ruff check .
python -m ruff format --check .
python -m bandit -r app -c pyproject.toml
python -m pytest -v
```

Rezultat confirmat:
- ruff check -> passed
- ruff format --check -> passed
- bandit -> passed
- pytest -> passed

Dupa adaugarea celor doua teste noi, numarul total de teste backend a crescut de la `11` la `13`.

### 155. Validarea prin Pull Request

Implementarea a fost facuta pe branch separat, nu direct pe `main`.

Flux folosit:
- feature branch
- push
- Pull Request catre main
- CI verde
- merge
- stergere branch

Aceasta etapa confirma noua disciplina de lucru a proiectului: fiecare task nou se dezvolta pe branch separat si intra in `main` doar dupa verificare prin CI.

### 156. Stare actuala dupa Admin User Management Phase 1

In acest moment backend-ul SentinelCore are:
- endpoint administrativ `GET /admin/users`
- listare utilizatori prin service dedicat
- acces permis doar pentru `admin` si `owner`
- raspuns prin schema publica `UserRead`
- protectie impotriva expunerii `hashed_password`
- audit log pentru listarea utilizatorilor
- security event pentru listarea utilizatorilor
- parametri de baza `limit` si `offset`
- teste pentru acces interzis user normal
- teste pentru acces permis admin
- 13 teste backend validate
- CI verde dupa Pull Request

Aceasta etapa marcheaza inceputul modulului real de administrare a utilizatorilor in SentinelCore.

## Admin User Management - Phase 2

### 157. Introducerea endpoint-urilor pentru detalii utilizator

A fost introdusa a doua etapa din zona de Admin User Management.

Dupa implementarea endpoint-ului pentru listarea utilizatorilor: `GET /admin/users` a fost adaugat endpoint-ul pentru consultarea unui utilizator individual: `GET /admin/users/{user_id}`.

Scopul acestui endpoint este ca un utilizator cu rol administrativ sa poata vedea detaliile unui user specific.

### 158. Scopul endpoint-ului `GET /admin/users/{user_id}`

Endpoint-ul permite obtinerea informatiilor publice despre un utilizator, pe baza ID-ului intern.

Accesul este permis doar pentru rolurile:
- admin
- owner

Un utilizator normal nu poate accesa aceasta ruta si primeste: `403 Forbidden`.

Daca utilizatorul cerut nu exista, API-ul raspunde cu: `404 Not Found` si mesajul `{"detail": "User not found"}

### 159. Service pentru citirea unui user dupa ID

In `app/services/user_service.py` a fost adaugata functia:

```python
def get_user_by_id(db: Session, user_id: int) -> User | None:
   statement = select(User).where(User.id == user_id) 
   return db.scalar(statement)
```

Aceasta functie separa logica de acces la baza de date de logica endpoint-ului API.

Scop:
- ruta API mai curata
- logica reutilizabila
- pregatire pentru viitoare endpoint-uri administrative
- tratarea clara a cazului in care userul nu exista

### 160. Extinderea routerului `admin_users`

Endpoint-ul a fost adaugat fisierul:

```
app/api/routes/admin_users.py
```

Ruta introdusa:

```python
@router.get("/{user_id}", response_model=UserRead)
def read_user_by_id(...)
```

Endpoint-ul returneaza un obiect de tip `UserRead`, nu modelul complet intern.

Aceasta decizie previne expunerea campurilor sensibile, cum ar fi:
- hashed_password

### 161. Protectia prin RBAC

Endpoint-ul este protejat cu: `Depends(require_role(UserRole.ADMIN, UserRole.OWNER))`

Aceasta inseamna ca doar utilizatorii cu rol administrativ pot consulta detaliile altor utilizatori.

Scenarii:
- user normal -> 403 Forbidden
- admin -> 200 OK
- owner -> 200 OK

Aceasta protectie este esentiala deoarece detaliile utilizatorilor nu trebuie sa fie accesibile public sau pentru orice user autentificat.

### 162. Tratarea userului inexistent

Daca `get_user_by_id()` nu gaseste userul cerut, endpoint-ul returneaza:

```python
raise HTTPException(
  status_code=status.HTTP_404_NOT_FOUND,
  detail="User not found",
)
```

Aceasta tratare este importanta pentru claritatea API-ului.
Nu returnam `None`, nu returnam lista goala si nu ascundem eroarea.

### 163. Audit log pentru vizualizarea detaliilor unui user

Cand un admin sau owner consulta detaliile unui user, aplicatia creeaza un audit log.

Eveniment folosit: `AuditEventType.ADMIN_ENDPOINT_ACCESSED`

Mesaj: `Admin viewed user details for user_id={target_user.id}`

Aceasta decizie este importanta deoarece vizualizarea datelor unui user este o actiune administrativa si trebuie urmarita.

In SentinelCore, actiunile administrative trebuie sa fie vizibile in audit trail.

### 164. Security event pentru vizualizarea detaliilor unui user

Pe langa audit log, endpoint-ul creeaza si un security event.

Eveniment folosit: `SecurityEventType.ADMIN_ACCESS`

Severitate: `SecuritySeverity.INFO`

Mesaj : `Admin viewed user details for user_id={target_user.id}`

Acest eveniment nu este incident, dar reprezinta o actiune administrativa relevanta pentru vizibilitatea de securitate.

### 165. Teste automate pentru `GET /admin/users/{user_id}`

Au fost adaugate teste in: `tests/test_protected_routes.py`

Scenarii validate:
- user normal -> 403 Forbidden
- admin user -> 200 OK + detalii user
- user inexistent -> 404 Not Found

Aceste teste extind acoperirea pentru zona de administrare a utilizatorilor.

### 166. Test pentru user normal

Scenariu:
1. se creeaza un user normal
2. se obtine ID-ul userului din baza de date de test
3. userul face login
4. userul incearca sa acceseze `GET /admin/users/{user_id}`
5. API-ul raspunde cu 403

Rezultatul asteptat: `403 Forbidden`

Acest test confirma ca un user normal nu poate consulta detalii administrative despre utilizatori.

### 167. Test pentru user admin

Scenariu:
1. se creeaza un user
2. se obtine ID-ul userului din baza de date de test
3. userul este promovat la admin in baza de date de test
4. userul face login
5. adminul acceseaza `GET /admin/users/{user_id}`
6. API-ul returneaza detaliile userului

Rezultatul asteptat: `200 OK`

Validari suplimentare:
- id-ul este corect
- email-ul este corect
- username-ul este corect
- hashed_password nbu este expus

### 168. Test pentru user inexistent

Scenariu:
1. se creeaze un user
2. userul este promovat la admin
3. adminul face login
4. adminul acceseaza `GET /admin/users/999999`
5. API-ul raspunde cu 404

Rezultat asteptat: `404 Not Found`

Mesaj validat: `{"detail": "User not found"}`

Acest test confirma ca API-ul trateaza explicit cazul in care userul cerut nu exista.

### 169. Validarea locala

Dupa implementare au fost rulate local:

```bash
python -m ruff check .
python -m ruff format --check .
python -m bandit -r app -c pyproject.toml
python -m pytest -v
```

Rezultat confirmat:
- ruff check -> passed
- ruff format --check -> passed
- bandit -> passed
- pytest -> passed

Dupa adaugarea celor trei teste noi, numarul total de teste backend a crescut de la `13` la `16`.

### 170. Validarea prin Pull Request

Implementarea a fost facuta pe branch separat, nu direct pe `main`.

Flux folosit:
- feature branch
- push
- Pull Request catre main
- CI verde
- merge
- stergere branch

Aceasta etapa continua disciplina introdusa anterior: fiecare task nou este lucrat pe branch separat si intra in main doar dupa validare prin CI.

### 171. Stare actuala dupa Admin User Management Phase 2

In acest moment backend-ul SentinelCore are:
- endpoint administrativ `GET /admin/users`
- endpoint administrativ `GET /admin/users/{user_id}`
- listare utilizatori
- citire detalii utilizator individual
- acces permis doar pentru `admin` si `owner`
- raspuns prin schema publica `UserRead`
- protectie impotriva expunerii `hashed_password`
- tratare explicita `404 User not found`
- audit log pentru vizualizarea detaliilor unui user
- security event pentru vizualizarea detaliilor unui user
- teste pentru acces interzis user normal
- teste pentru acces permis admin
- teste pentru user inexistent
- 16 teste backend validate
- CI verde dupa Pull Request

Aceasta etapa consolideaza modulul Admin User Management si pregateste terenul pentru actiuni administrative mai sensibile, precum schimbarea rolurilor.

## Admin User Management - Phase 3 (local implementation)

### 172. Role update endpoint and policy

`PATCH /admin/users/{user_id}/role` accepts a body such as `{"role": "admin"}`
and returns `UserRead`, excluding `hashed_password`.

Only an authenticated owner may change a target user's role. Allowed destination
roles are `user`, `admin`, and `security_analyst`. The endpoint rejects
self-modification, modifying an existing owner, and assigning the owner role.

| Situation | Response |
| --- | --- |
| Missing token | 401 |
| Actor is not an owner | 403, `Insufficient permissions` |
| Target does not exist | 404, `User not found` |
| Owner targets their own account | 403, `Owners cannot change their own role` |
| Owner targets another owner | 403, `Cannot change the role of an owner` |
| Owner tries to assign owner | 403, `Cannot promote a user to owner` |
| Unknown role such as `manager` | 422 |
| Allowed change | 200 |
| Existing role requested for an allowed target | 200, no change events |

`UserRoleUpdate` validates the role using `UserRole`. The value `owner` is valid
input for the enum but is rejected by the endpoint's business rules.

### 173. Actor, target, and transaction behavior

The actor is the authenticated owner; the target is the user identified by the
route's `user_id`. Audit and security event `user_id` and `email` fields identify
the actor. The message records the target ID and the previous and new roles:

`Owner changed role for user_id={target_id} from {old_role} to {new_role}`

`update_user_role()` stages the role change, an `AuditLog`, and a `SecurityEvent`
before committing once. It rolls back and re-raises if the commit fails.
It constructs event objects directly because the existing event creation helpers
commit independently. No new enum values or database migration are required.

The events reuse `ADMIN_ENDPOINT_ACCESSED` and `ADMIN_ACCESS`, with security
severity `INFO` and source `backend`. Requests rejected by the endpoint and
requests that leave the role unchanged create no successful-change events.
Self-modification and owner restrictions are checked before the unchanged-role
shortcut.

### 174. Local verification on 2026-10-06

- Ruff lint and formatting checks passed for the backend.
- Bandit reported no security findings; it emitted warnings while parsing the
  existing OAuth2 `nosec` comment in `auth.py`.
- All 29 tests passed in 4.64 seconds against the separate PostgreSQL database
  `sentinelcore_test`, using `backend/.venv`.
- Successful-change tests verify the role read back from the database and the
  actor and message in both event records.
- Additional tests cover an unknown target, an invalid role, and an unchanged
  role, including the absence of successful-change events.

The PostgreSQL connection failed inside the sandbox; the successful test run was
performed outside it. A transaction-failure test remains to be added. Phase 3
CI validation remains pending.

## Project Cleanup

### 175. Scopul etapei

Inainte de continuarea dezvoltarii, proiectul a fost verificat integral si au fost corectate problemele gasite. Lucrul a fost facut pe branch separat, `chore/project-cleanup`, creat din `main`.

### 176. Alembic vedea o schema goala

`migrations/env.py` importa doar `Base`, nu si modulele cu modele. Un model se inregistreaza in `Base.metadata` doar cand modulul lui este importat, asa ca la rularea Alembic `Base.metadata.tables` era gol. Urmatorul `alembic revision --autogenerate` ar fi propus stergerea tuturor tabelelor.

Cauza probabila: importurile au fost eliminate de Ruff ca nefolosite (`F401`).

Rezolvare:

```python
from app.models import audit_log, security_event, user  # noqa: F401
```

Verificare: `python -m alembic check` -> `No new upgrade operations detected.`

Testele nu puteau prinde problema, deoarece creeaza schema prin `create_all()`, nu prin migratii. `alembic check` a fost adaugat in `backend/README.md` ca verificare manuala.

### 177. Utilizatori inactivi

Campul `is_active` exista in model, dar nu era verificat nicaieri.

Comportament nou:
- login cu parola corecta pentru un user inactiv -> `403 Forbidden`, `Inactive user`
- tentativa genereaza audit log si security event `LOGIN_FAILED`, severitate `WARN`
- un token emis inainte de dezactivare este refuzat de `get_current_user()` cu `403 Inactive user`

Mesajul `Inactive user` apare doar dupa verificarea parolei, deci nu dezvaluie starea contului cuiva care nu cunoaste parola.

Momentan nu exista un endpoint pentru dezactivare; in teste, `is_active` este setat direct in baza de date de test.

### 178. Timp de raspuns egal la login

Pentru un email inexistent, `authenticate_user()` returna imediat, fara verificarea hash-ului. Pentru un email existent se calcula hash-ul Argon2, ceea ce dureaza vizibil mai mult. Diferenta de timp permitea aflarea emailurilor inregistrate.

Rezolvare: in `app/core/security.py` este generat la pornire `DUMMY_PASSWORD_HASH`, dintr-o valoare aleatoare. Pentru un email inexistent, parola este verificata contra acestui hash, deci ambele cazuri costa la fel.

Observatie: `POST /auth/register` raspunde in continuare cu `Email already registered`, deci existenta unui email poate fi aflata prin register. Aceasta este o limitare acceptata in etapa actuala.

### 179. Inregistrari simultane

Register verifica duplicatele inainte de insert. Doua request-uri simultane cu acelasi email puteau trece ambele de verificare, iar al doilea primea `500 Internal Server Error` de la indexul unic din PostgreSQL.

Rezolvare:
- `create_user()` face `rollback` daca `commit` esueaza
- endpoint-ul prinde `IntegrityError` de tip `UniqueViolation` si raspunde cu `400`
- mesajul este ales dupa indexul incalcat: `ix_users_email` -> `Email already registered`, `ix_users_username` -> `Username already taken`

Testul simuleaza cursa dezactivand verificarile prealabile prin `monkeypatch`, astfel incat doar indexurile unice pot respinge duplicatul.

### 180. Dependente si alte corecturi

- uneltele de dezvoltare (`pytest`, `httpx`, `ruff`, `bandit`) au fost mutate in `[project.optional-dependencies] dev`
- instalarea pentru dezvoltare si CI devine `python -m pip install -e ".[dev]"`
- dependentele au limite minime egale cu versiunile validate local
- `ruff` este fixat exact (`ruff==0.15.17`), deoarece versiunile noi pot schimba formatarea sau adauga reguli si ar putea pica CI-ul fara modificari de cod
- dependenta duplicata `pwdlib` / `pwdlib[argon2]` a fost redusa la `pwdlib[argon2]`
- CI-ul foloseste `postgres:17`, aceeasi versiune ca Docker Compose
- explicatia pentru `# nosec B106` a fost mutata pe randul anterior; Bandit interpreta textul de dupa `nosec` ca ID-uri de reguli si emitea warning-uri
- `AuditLogRead.message` accepta `None`, la fel ca coloana din baza de date
- adnotarile `Mapped[DateTime]` au devenit `Mapped[datetime]`
- typo-uri corectate in `.env.example` (`postgresql+psycopg://`) si `.gitignore` (`__pycache__/`)
- documentatia a fost aliniata cu codul (`require_role()`, rute, configuratia CI)
- au fost scrise `README.md` si `backend/README.md`

### 181. Validarea locala

- ruff check -> passed
- ruff format --check -> passed
- bandit -> No issues identified, fara warning-uri
- alembic check -> No new upgrade operations detected
- pytest -> 21 passed

Testele noi au fost verificate si invers: cu reparatiile dezactivate temporar, toate cele 5 teste noi pica.

## Admin User Management - Phase 4

### 182. Activarea si dezactivarea conturilor

A fost introdus endpoint-ul:

```http
PATCH /admin/users/{user_id}/status
```

Body:

```json
{"is_active": false}
```

Raspunsul foloseste schema `UserRead`, deci `hashed_password` nu este expus.

Endpoint-ul foloseste verificarea `is_active` introdusa in etapa de cleanup: un cont dezactivat nu se mai poate autentifica, iar token-urile emise anterior sunt refuzate imediat, deoarece `get_current_user()` citeste userul din baza de date la fiecare request.

### 183. Reguli de permisiune

Accesul este ierarhic:
- `admin` poate activa sau dezactiva conturi `user` si `security_analyst`
- `owner` poate activa sau dezactiva si conturi `admin`
- nimeni nu isi poate schimba propriul status
- statusul unui `owner` nu poate fi schimbat

| Situatie | Raspuns |
| --- | --- |
| Fara token | 401 |
| Actorul nu este `admin` sau `owner` | 403, `Insufficient permissions` |
| User inexistent | 404, `User not found` |
| Actorul isi schimba propriul status | 403, `Users cannot change their own status` |
| Tinta este `owner` | 403, `Cannot change the status of an owner` |
| `admin` schimba statusul altui `admin` | 403, `Only an owner can change the status of an admin` |
| `is_active` nu este boolean (`"false"`, `0`, `null`) | 422 |
| Schimbare permisa | 200 |
| Statusul cerut este deja cel actual | 200, fara evenimente |

`UserStatusUpdate` foloseste `StrictBool`, astfel incat valori precum `"false"` sau `0` sunt respinse, nu convertite implicit.

### 184. Tipuri dedicate de evenimente

Pana acum, actiunile administrative refoloseau `ADMIN_ENDPOINT_ACCESSED` si `ADMIN_ACCESS`, iar schimbarile se distingeau doar prin mesaj.

Au fost adaugate tipuri noi, atat in `AuditEventType`, cat si in `SecurityEventType`:
- `USER_ROLE_CHANGED`
- `USER_ACTIVATED`
- `USER_DEACTIVATED`

Schimbarea de rol din Phase 3 foloseste acum `USER_ROLE_CHANGED`.

Mesajele inregistrate:
- `Admin deactivated user_id={id}` / `Owner activated user_id={id}`
- `Owner changed role for user_id={id} from {old} to {new}`

Campurile `user_id` si `email` ale evenimentelor identifica actorul; tinta apare in mesaj. Severitatea este `INFO`.

### 185. Prima migratie Alembic dupa schema initiala

Valorile noi au fost adaugate in tipurile enum PostgreSQL prin migratia `02a6be0e0ec8_add_user_management_event_types.py`.

Migratia a fost scrisa manual, deoarece `--autogenerate` nu detecteaza valori noi intr-un enum existent. Din acelasi motiv, `alembic check` nu poate confirma ca enum-urile din baza de date sunt la zi.

Upgrade:

```sql
ALTER TYPE audit_event_types ADD VALUE IF NOT EXISTS 'USER_ROLE_CHANGED';
```

Valorile sunt scrise cu majuscule, deoarece SQLAlchemy salveaza numele membrilor enum.

PostgreSQL nu permite stergerea unei valori dintr-un enum. Downgrade-ul:
- remapeaza randurile cu tipurile noi la `ADMIN_ENDPOINT_ACCESSED` / `ADMIN_ACCESS`
- redenumeste tipul enum existent
- creeaza tipul cu valorile vechi
- converteste coloana `event_type` la tipul nou
- sterge tipul vechi

Migratia a fost verificata pe o baza temporara prin `upgrade -> downgrade -> upgrade`, cu randuri care foloseau valorile noi. Downgrade-ul a remapat randurile si a pastrat indexul `ix_security_events_event_type`.

Aplicare locala:

```bash
python -m alembic upgrade head
```

### 186. Tranzactie comuna pentru schimbari si evenimente

Logica de commit din `update_user_role()` a fost extrasa in `_commit_user_change()`, folosita acum si de `update_user_status()`.

Functia adauga audit log-ul si security event-ul in aceeasi sesiune cu modificarea userului si face un singur `commit`. Daca acesta esueaza, se face `rollback` si exceptia este propagata.

A fost adaugat testul de esec al tranzactiei, ramas in asteptare din Phase 3, pentru ambele operatii. Commit-ul simulat face mai intai `flush`, astfel incat modificarea si evenimentele ajung in tranzactia deschisa; doar un `rollback` real le anuleaza. Testul a fost verificat invers: fara `rollback`, pica.

### 187. Validarea locala

- ruff check -> passed
- ruff format --check -> passed
- bandit -> No issues identified
- pytest -> 55 passed

Testele noi acopera: lipsa token-ului, roluri fara drept de acces, matricea de schimbari permise, toate restrictiile, user inexistent, valori non-boolean, status neschimbat, esecul tranzactiei si pierderea imediata a accesului pentru un cont dezactivat.

## Input Validation - Phase 1

### 188. Problema

Schemele de input acceptau orice string:
- un username mai lung de 50 de caractere ajungea in PostgreSQL, depasea coloana `String(50)` si producea `500 Internal Server Error`
- username-ul si parola goale erau acceptate cu `201 Created`
- `Test@x.com` si `test@x.com` puteau fi conturi diferite, la fel `Admin` si `admin`

### 189. Reguli introduse

Regulile sunt definite in `app/schemas/user.py`, ca tipuri reutilizabile cu `Annotated`.

**Username** (`Username`):
- 3-50 caractere; 50 corespunde coloanei `users.username`
- doar litere ASCII, cifre, `_`, `.` si `-`
- transformat in litere mici, astfel incat `Admin` si `admin` nu pot coexista

**Email** (`NormalizedEmail`):
- validat de `EmailStr`
- transformat in litere mici, la register si la login

**Parola la register** (`NewPassword`):
- minimum 12 caractere
- maximum 128 caractere, pentru a limita costul hashing-ului Argon2 pe request
- fara reguli de compozitie (majuscule, simboluri), conform recomandarilor NIST si OWASP

**Parola la login** (`LoginPassword`):
- doar maximum 128 caractere
- fara minimum, pentru ca un cont creat inainte de politica noua sa se poata autentifica

Input-ul invalid este respins cu `422`, inainte de orice acces la baza de date.

Observatie: in Pydantic, `pattern` este verificat pe valoarea primita, inainte de `to_lower`. De aceea pattern-ul accepta si majuscule (`^[A-Za-z0-9_.-]+$`), iar valoarea salvata este oricum lowercase.

### 190. Migratia pentru datele existente

Dupa normalizarea input-ului, un cont existent salvat ca `Test@x.com` nu ar mai fi fost gasit la login, deoarece cautarea se face dupa `test@x.com`.

Migratia `7242f1f7b69b_lowercase_user_emails_and_usernames.py` transforma `users.email` si `users.username` in litere mici.

Daca doua conturi ar deveni identice, de exemplu `Dup@x.com` si `dup@x.com`, migratia se opreste cu un mesaj care listeaza valorile in conflict. Tranzactia este anulata, datele raman neatinse, iar baza ramane la versiunea anterioara. Conflictele trebuie rezolvate manual, deoarece unirea automata a doua conturi nu este sigura.

Downgrade-ul nu modifica datele: forma originala nu este salvata, iar valorile lowercase raman valide si in revizia anterioara.

Username-urile existente care nu respecta noile reguli nu sunt modificate. Login-ul se face dupa email, deci aceste conturi raman utilizabile.

Migratia a fost verificata pe o baza temporara: date mixed-case, `downgrade -> upgrade` si cazul de conflict.

Aplicare locala:

```bash
python -m alembic upgrade head
```

### 191. Validarea locala

- ruff check -> passed
- ruff format --check -> passed
- bandit -> No issues identified
- pytest -> 74 passed

Testele noi acopera: fiecare regula respinsa cu `422`, valorile-limita acceptate, salvarea lowercase, duplicatele care difera doar prin litere mari/mici, login case-insensitive, parola prea lunga la login si login-ul unui cont cu parola mai scurta decat politica noua.

Verificare inversa: cu schemele anterioare, 12 din cele 19 teste noi pica. Celelalte 7 confirma ca regulile nu sunt prea stricte si trec in ambele variante.

## Brute-Force Detection - Phase 1

### 192. Scopul etapei

Pana acum, login-urile esuate erau inregistrate ca `LOGIN_FAILED` cu severitate `WARN`, dar nimic nu reactiona la ele. Un atacator putea incerca parole nelimitat.

Aceasta etapa introduce prima detectie reala din zona SIEM-light: prea multe esecuri pentru acelasi email genereaza un incident si blocheaza temporar login-ul. Este prima utilizare a severitatii `INCIDENT`.

### 193. Reguli

Valorile implicite, configurabile din `.env`:

```env
LOGIN_MAX_FAILED_ATTEMPTS=5
LOGIN_FAILURE_WINDOW_MINUTES=15
LOGIN_LOCKOUT_MINUTES=15
```

- la al 5-lea esec in 15 minute pentru acelasi email, login-ul pe acel email este blocat 15 minute
- incercarea care atinge pragul primeste deja `429 Too Many Requests`
- in timpul blocarii, orice incercare primeste `429`, chiar si cu parola corecta
- raspunsul contine header-ul `Retry-After` cu secundele ramase
- in timpul blocarii, parola nu este verificata deloc, astfel incat incercarile nu ofera nicio informatie
- un login reusit reseteaza numaratoarea
- dupa expirarea unei blocari, esecurile anterioare ei nu mai sunt numarate
- emailurile inexistente sunt blocate identic, deci blocarea nu dezvaluie existenta unui cont
- login-urile esuate ale unui cont inactiv sunt numarate la fel

Dezavantaj cunoscut: un atacator poate bloca temporar contul unei victime trimitand parole gresite. Blocarea este temporara, iar varianta pe email a fost aleasa constient, in locul blocarii pe email + IP, care ar fi fost ocolita de un atacator cu mai multe IP-uri.

### 194. Starea este derivata din security events

Nu exista tabela sau coloana separata pentru numararea esecurilor. Serviciul `app/services/login_protection_service.py` foloseste evenimentele deja inregistrate:
- numarul de esecuri = `LOGIN_FAILED` pentru email, dupa cel mai recent dintre: inceputul ferestrei, ultimul `LOGIN_SUCCESS`, ultimul `BRUTE_FORCE_DETECTED`
- blocarea este activa daca ultimul `BRUTE_FORCE_DETECTED` este mai recent decat durata de blocare

Timpul este citit din baza de date (`SELECT now()`), acelasi ceas care completeaza `created_at`, astfel incat comparatiile nu amesteca ceasul aplicatiei cu cel al bazei de date.

Pentru aceste interogari a fost adaugat indexul compus `ix_security_events_email_type_created` pe `(email, event_type, created_at)`.

### 195. Evenimente noi

| Situatie | Audit log | Security event | Severitate |
| --- | --- | --- | --- |
| Pragul este atins | `LOGIN_LOCKED` | `BRUTE_FORCE_DETECTED` | `INCIDENT` |
| Incercare in timpul blocarii | `LOGIN_BLOCKED` | `LOGIN_BLOCKED` | `WARN` |

Denumirile urmeaza separarea existenta: audit log-ul descrie faptul (login blocat), iar security event-ul interpretarea (atac brute-force detectat).

Incidentul este legat de contul atacat prin `user_id` atunci cand contul exista, chiar daca incercarile nu l-au autentificat.

### 196. Adresa IP in evenimente

Tabelele `audit_logs` si `security_events` au acum coloana `ip_address` (`String(45)`, suficient pentru IPv6). Toate evenimentele inregistreaza IP-ul clientului: register, login, endpoint-urile administrative si schimbarile de rol/status.

IP-ul este obtinut prin dependenta `get_client_ip()` din `app/api/deps.py`, din `request.client.host`. Valorile care nu sunt adrese IP valide sunt salvate ca `NULL` (de exemplu `testclient` in teste).

Header-ul `X-Forwarded-For` nu este citit direct, deoarece poate fi falsificat de client. Daca aplicatia ruleaza in spatele unui reverse proxy, uvicorn trebuie pornit cu `--proxy-headers` si `--forwarded-allow-ips`, iar `request.client` va contine IP-ul real.

`AuditLogRead` si `SecurityEventRead` expun campul `ip_address`.

IP-ul pregateste o detectie viitoare: multe emailuri diferite incercate de pe acelasi IP (password spraying).

### 197. Migratia

Migratia `449c22b3652c_add_login_protection_events_and_ip_.py`:
- adauga valorile noi in `audit_event_types` si `security_event_types`
- adauga coloana `ip_address` in ambele tabele
- creeaza indexul compus

Downgrade-ul sterge indexul si coloanele, remapeaza randurile cu tipurile noi la `LOGIN_FAILED` si recreeaza tipurile enum fara valorile noi.

Verificare pe baza temporara: `upgrade`, `alembic check`, randuri cu valorile noi, `downgrade`, din nou `upgrade` si `alembic check`.

### 198. Problema intalnita in teste: prepared statements

Dupa adaugarea noilor interogari, doua teste picau intermitent cu:

```
cache lookup failed for type ...
```

Cauza: psycopg pregateste pe server (prepared statement) o interogare executata de cel putin 5 ori pe aceeasi conexiune. Interogarea ramane legata de identificatorul intern (OID) al tipului enum. Fixture-ul de test recreeaza schema la fiecare test, deci tipurile enum primesc OID-uri noi, iar conexiunile refolosite din pool pastrau interogari legate de tipuri sterse.

Rezolvare: in `tests/conftest.py`, dupa recrearea schemei, este apelat `test_engine.dispose()`, astfel incat fiecare test porneste pe conexiuni noi.

Problema apare doar in teste, deoarece aplicatia reala nu recreeaza tipurile enum in timp ce ruleaza.

### 199. Validarea locala

- ruff check -> passed
- ruff format --check -> passed
- bandit -> No issues identified
- pytest -> 86 passed

Testele noi (`tests/test_login_protection.py`) acopera: atingerea pragului si incidentul, refuzul parolei corecte in timpul blocarii fara verificarea ei, blocarea emailurilor inexistente, expirarea blocarii, fereastra de timp, resetarea dupa login reusit, ignorarea esecurilor dinaintea unei blocari expirate, izolarea pe email, pragurile din configurare, inregistrarea IP-ului (IPv4 si IPv6) si expunerea lui prin API.

Timpul scurs este simulat prin mutarea `created_at` al evenimentelor in trecut.

Verificare inversa: fara verificarea blocarii pica 3 teste, fara prag pica 6, iar fara resetarea dupa login reusit / blocare pica 2.

## Log Filtering - Phase 1

### 200. Scopul etapei

Endpoint-urile `GET /admin/audit-logs` si `GET /security/events` returnau doar ultimele `limit` evenimente, fara filtre si fara posibilitatea de a ajunge la evenimente mai vechi. Aceasta etapa le pregateste pentru dashboard-ul de securitate din frontend.

### 201. Raspuns paginat prin cursor

Raspunsul nu mai este o lista, ci un obiect (envelope):

```json
{
  "items": [...],
  "next_cursor": 123
}
```

Pagina urmatoare se obtine cu `?before_id=123`. Cand nu mai exista rezultate, `next_cursor` este `null`.

Evenimentele sunt ordonate dupa `id` descrescator, adica cele mai noi primele. Ordinea dupa `id` (si nu dupa `created_at`) este necesara pentru ca:
- `id` este unic, deci nu exista egalitati intre evenimente
- cursorul este tot un `id`, deci ordinea si cursorul folosesc aceeasi cheie
- `created_at` este momentul de inceput al tranzactiei, deci un eveniment inserat mai tarziu poate avea un timestamp mai vechi

Avantaje fata de `offset`:
- paginile nu se decaleaza cand apar evenimente noi in timp ce analistul rasfoieste
- interogarea ramane rapida si pe tabele mari, deoarece nu parcurge randurile sarite

Pentru a sti daca exista o pagina urmatoare, se citeste un rand in plus fata de `limit`.

Schimbarea formei raspunsului este o modificare de contract API. A fost facuta acum deoarece nu exista inca niciun client al acestor endpoint-uri.

Schema generica `Page[ItemT]` din `app/schemas/pagination.py` foloseste sintaxa de generice din Python 3.12.

### 202. Filtre

Filtre comune (`app/schemas/event_filters.py`):

| Parametru | Comportament |
| --- | --- |
| `user_id` | egalitate |
| `email` | egalitate, fara diferenta intre litere mari si mici |
| `ip_address` | IPv4 sau IPv6 valid; forma IPv6 este normalizata, deci `2001:DB8:0:0::1` gaseste `2001:db8::1` |
| `since` | `created_at >= since` |
| `until` | `created_at < until` |
| `before_id` | cursorul de paginare |
| `limit` | 1-200, implicit 50 |

Filtre specifice:
- audit logs: `event_type`, cu una sau mai multe valori (`?event_type=login_failed&event_type=login_locked`)
- security events: `event_type` si `severity`, fiecare cu una sau mai multe valori

Mai multe valori pentru acelasi parametru se combina cu `OR`; parametri diferiti se combina cu `AND`.

Intervalul de timp este semi-deschis (`since <= created_at < until`), astfel incat intervale consecutive nu numara de doua ori acelasi eveniment.

### 203. Validarea filtrelor

Filtrele sunt definite ca modele Pydantic folosite pentru query parameters (`Annotated[AuditLogFilters, Query()]`). Raspund cu `422`:
- `since` mai mare sau egal cu `until`
- date fara fus orar (`AwareDatetime`), pentru a evita interpretari ambigue
- valori invalide pentru `event_type`, `severity`, `ip_address`, `limit` sau `before_id`
- parametri necunoscuti, prin `extra="forbid"`

Ultima regula este importanta pentru securitate: un filtru scris gresit, de exemplu `?event_typ=login_failed`, ar fi fost altfel ignorat, iar analistul ar fi vazut rezultate nefiltrate crezand ca sunt filtrate.

### 204. Auditarea consultarii logurilor

Consultarea logurilor este acum auditata, cu tipuri noi in `AuditEventType`:
- `AUDIT_LOGS_VIEWED`
- `SECURITY_EVENTS_VIEWED`

Mesajul contine filtrele folosite, de exemplu:

```
Viewed audit logs with event_type=['login_failed'], limit=10
```

Decizii:
- evenimentul este inregistrat dupa interogare, deci raspunsul nu contine niciodata propria consultare
- se creeaza doar audit log, nu si security event: consultarea este un fapt de audit, nu un semnal de securitate, si nu trebuie sa umple fluxul SIEM

Valorile noi au fost adaugate prin migratia `1ff3830ec505_add_log_view_audit_event_types.py`. Downgrade-ul remapeaza randurile la `ADMIN_ENDPOINT_ACCESSED` si recreeaza tipul enum.

### 205. Logica de interogare comuna

Filtrele comune, ordonarea si paginarea sunt implementate o singura data, in `fetch_event_page()` din `app/services/event_query.py`, folosita de ambele servicii. Fiecare serviciu adauga doar filtrele specifice (`event_type`, `severity`).

`fetch_event_page()` este o functie generica cu `EventT: AuditLog | SecurityEvent`. Varianta initiala, cu constrangeri `(AuditLog, SecurityEvent)`, era rezolvata gresit de Pylance pentru apelul cu `AuditLog`.

### 206. Validarea locala

- ruff check -> passed
- ruff format --check -> passed
- bandit -> No issues identified
- pytest -> 107 passed
- migratia: `upgrade -> alembic check -> downgrade -> upgrade -> alembic check` pe baza temporara

Testele noi (`tests/test_event_logs_api.py`) acopera: acces interzis pentru user normal, ordinea, parcurgerea completa prin cursor, stabilitatea paginilor la evenimente noi, ordinea dupa insertie chiar daca timestamp-urile sunt inverse, fiecare filtru si combinarea lor, intervalul semi-deschis, query-urile invalide si auditarea consultarii.

Verificare inversa: fiecare dintre urmatoarele modificari face cel putin un test sa pice: eliminarea `extra="forbid"`, eliminarea normalizarii emailului, cursor inclusiv, interval inchis, ordonare dupa `created_at`.

Cele 3 teste existente care asteptau o lista au fost actualizate pentru noua forma a raspunsului.

## Observability - Phase 1

### 207. Scopul etapei

"Observability-first" este unul dintre principiile proiectului, iar Prometheus si Grafana fac parte din MVP-ul DevOps. Pana acum, backend-ul nu expunea metrici, scria loguri nestructurate, iar `/health` raspundea `ok` chiar daca PostgreSQL era oprit.

Aceasta etapa introduce:
- metrici Prometheus pentru HTTP si pentru security events
- loguri structurate, cu un request id pe fiecare cerere
- un health check care verifica baza de date
- Prometheus si Grafana in Docker Compose, cu dashboard provizionat automat

### 208. Metrici

Metricile sunt definite in `app/core/metrics.py` si expuse la `GET /metrics`, in formatul text Prometheus.

| Metrica | Tip | Etichete |
| --- | --- | --- |
| `sentinelcore_http_requests_total` | Counter | `method`, `route`, `status_code` |
| `sentinelcore_http_request_duration_seconds` | Histogram | `method`, `route` |
| `sentinelcore_security_events_total` | Counter | `event_type`, `severity` |

Fiecare combinatie distincta de etichete devine o serie separata in Prometheus. De aceea etichetele provin din multimi mici si fixe:
- `route` este sablonul rutei (`/admin/users/{user_id}`), nu calea concreta (`/admin/users/42`)
- caile care nu corespund niciunei rute primesc `route="unmatched"`
- metodele HTTP necunoscute primesc `method="OTHER"`

Altfel, oricine ar putea crea un numar nelimitat de serii trimitand cereri catre cai sau metode inventate.

`sentinelcore_security_events_total` este incrementat dupa commit-ul fiecarui security event, in cele trei locuri care le creeaza: `create_security_event()`, `_commit_user_change()` si `lock_login()`. O singura metrica acopera login-uri reusite si esuate, blocari, incidente brute-force si schimbari administrative.

Metricile sunt pastrate in memoria procesului si pornesc de la zero la fiecare restart; functiile `rate()` si `increase()` din Prometheus trateaza aceste resetari. Configuratia presupune un singur proces uvicorn; mai multi workeri ar necesita modul multiprocess din `prometheus_client`.

### 209. Protectia `/metrics`

Daca `METRICS_TOKEN` este setat in `.env`, `/metrics` cere `Authorization: Bearer <token>` si raspunde altfel cu `401`. Daca este gol sau lipseste, endpoint-ul este deschis, ceea ce este potrivit pentru dezvoltare locala.

Token-ul este comparat cu `hmac.compare_digest`, in timp constant, astfel incat timpul de raspuns nu dezvaluie cat de mult din token a fost ghicit.

`/metrics` nu apare in documentatia OpenAPI.

### 210. Request id si loguri structurate

Middleware-ul `observe_requests` din `app/api/middleware.py`:
- refoloseste header-ul `X-Request-ID` primit, daca are maximum 64 de caractere din `A-Z a-z 0-9 . _ -`, altfel genereaza unul nou
- intoarce request id-ul in header-ul `X-Request-ID` al raspunsului
- il pastreaza intr-un `ContextVar`, astfel incat orice log scris in timpul cererii il contine
- scrie un singur log pe cerere, cu `method`, `route`, `path`, `status_code`, `duration_ms` si `client_ip`
- inregistreaza metricile HTTP

Validarea request id-ului primit impiedica injectarea de text arbitrar, de exemplu linii noi, in loguri si header-e.

Formatul logurilor se alege din `.env`:

```env
LOG_LEVEL=INFO
LOG_FORMAT=json
```

- `json`: un obiect JSON pe linie, pentru colectoare de loguri
- `text`: linii lizibile in terminal, cu aceleasi campuri

Exemplu JSON:

```json
{"timestamp": "2026-10-06T16:00:03.871220+00:00", "level": "INFO", "logger": "sentinelcore.request", "message": "Request completed", "request_id": "demo-trace-1", "method": "GET", "route": "/health", "path": "/health", "status_code": 200, "duration_ms": 0.22, "client_ip": "127.0.0.1"}
```

Logurile uvicorn trec prin acelasi format. Access log-ul propriu al uvicorn este dezactivat, deoarece ar dubla logul scris de middleware.

### 211. Health checks

- `GET /health`: liveness, adica procesul ruleaza si raspunde; nu depinde de baza de date
- `GET /health/ready`: readiness, adica aplicatia poate servi trafic; executa `SELECT 1` si raspunde `503` cu `{"status": "unavailable", "database": "unavailable"}` daca PostgreSQL nu este disponibil

Separarea permite unui orchestrator sa nu reporneasca procesul cand doar baza de date este temporar indisponibila, dar sa nu-i trimita trafic pana cand aceasta revine.

### 212. Prometheus si Grafana

`docker-compose.yml` contine acum serviciile `prometheus` (`prom/prometheus:v3.15.0`) si `grafana` (`grafana/grafana:13.2.3`). Configuratia este in `infra/`:

```text
infra/
├── prometheus/
│   └── prometheus.yml
└── grafana/
    ├── provisioning/
    │   ├── datasources/prometheus.yml
    │   └── dashboards/sentinelcore.yml
    └── dashboards/
        └── sentinelcore-overview.json
```

Ambele servicii folosesc `network_mode: host` si asculta doar pe `127.0.0.1`:
- Prometheus colecteaza backend-ul pornit local pe `localhost:8000`, fara ca uvicorn sa fie pornit pe `0.0.0.0`
- nimic nu este expus in reteaua locala

Host networking este suportat complet pe Linux.

Fisierele de configurare sunt montate cu `:ro,z`. Optiunea `z` reeticheteaza fisierele pentru SELinux, necesara pe Fedora, la fel ca la Gitleaks; pe sisteme fara SELinux este ignorata.

Dashboard-ul `SentinelCore Overview` este provizionat automat si contine:
- Security: incidente brute-force, incercari blocate, login-uri esuate, dezactivari de conturi, security events pe minut dupa tip si dupa severitate
- HTTP: request-uri pe secunda dupa ruta, raspunsuri dupa status code, latenta p95 dupa ruta, procentul de erori 5xx

Pornire:

```bash
docker compose up -d prometheus grafana
```

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`, user `admin`, parola `sentinelcore` (doar local)

### 213. Validarea locala

- ruff check -> passed
- ruff format --check -> passed
- bandit -> No issues identified
- pytest -> 132 passed

Testele noi (`tests/test_observability.py`) acopera: generarea, refolosirea si respingerea request id-urilor, logul per cerere, propagarea request id-ului in logurile scrise in timpul cererii, ambele formate de log, etichetele bazate pe sabloane, gruparea cailor si metodelor necunoscute, histograma de durata, numararea security events, protectia `/metrics` si readiness-ul cu baza de date disponibila si indisponibila.

Verificare inversa: fiecare dintre urmatoarele modificari face cel putin un test sa pice: cale concreta in loc de sablon, request id nevalidat, request id nepropagat in loguri, token nevalidat, incident nenumarat.

Verificare end-to-end, pe o baza temporara migrata:
- backend pornit cu loguri JSON, Prometheus si Grafana pornite prin Docker Compose
- un atac brute-force simulat: 4 raspunsuri `401`, apoi `429` cu `Retry-After: 900`
- Prometheus colecteaza backend-ul (`health: up`) si raporteaza exact evenimentele generate
- Grafana provizioneaza datasource-ul si dashboard-ul, iar toate cele 12 panouri returneaza date

Verificarea a gasit o problema: panoul pentru erorile 5xx nu afisa nimic cand nu existau erori, deoarece impartirea unei serii goale nu produce rezultat. Expresia foloseste acum `or vector(0)`, astfel incat afiseaza `0`.
