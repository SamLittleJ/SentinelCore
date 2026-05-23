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
Fisierul `app/api/deps.py` a fost extins cu functia `require_roles()`

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
GET /user/admin-only
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
- functionarea corecta a dependentei `require_roles()`
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
Base.metadata.create_alll(bind=engine)
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

Endpoint-ul `GET /admin/aduit-logs` este protejat prin `require_role(...)`.

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
- endpoint `GET /admin/aduit-logs`
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

Endpoint-ul `GET /security/events` este protejat prin `require_roles(...)`.

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