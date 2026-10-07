# SentinelCore - Project Foundation

## 1. Project Overview

**SentinelCore** este o platforma **API-first, web-first, mobile-ready** pentru:

- Identity and Access Management (IAM)
- Security Event Monitoring (SIEM-Light)
- Audit Logging
- Observability
- DevSecOps learning si demonstratie practica

Proiectul este construit ca **modular monolith**, nu ca microservicii.

Scopul lui nu este doar sa fie "o aplicatie care merge", ci sa demonstreze in mod clar competente reale de:

- backend engineering
- securitate aplicationala
- observability
- DevOps
- organizare arhitecturala
- documentare tehnica

---

## 2. Main Objective

Obiectivul principal al SentinelCore este sa devina un proiect real, serios, peste nivel de disertatie, care sa arate capacitatea de a proiecta, construi, rula, documenta si evolua o platforma moderna orientata spre securitate si operatiuni.

Acest proieect trebuie sa demonstreze:

- design coerent
- separare clara a responsabilitatilor
- auditabilitate
- securitate de baza implementata corect
- monitorizare si observabilitate gandite din timp
- baza solida pentru extindere ulterioara

---

## 3. Arhitecture Direction

SentinelCore urmeaza urmatoarele princii arhitecturale:

### API-first
Backend-ul este sursa adevarului. Toata logica critica, validarea, securitatea si modelarea datelor pornesc din API.

### Web-first
Clientul principal in MVP este aplicatia web.

### Mobile-ready
Nu se dezvolta aplicatie mobila in MVP, dar backend-ul si contractele API trebuie gandite astfel incat sa nu blocheze un client mobil in viitor.

### Modular Monolith
Aplicatia va fi construita ca monolit modular. Nu se folosesc microservicii in aceasta etapa deoarece ar introduce complexitate inutila si ar incetini invatarea si executia.

### RBAC from the start
Rolurile si permisiunile sunt parte din fundatia aplicatiei, nu ceva adaugat mai tarziu.

### Audit-first
Evenimentele si audit log-urile sunt centrale in produs, nu simple detalii tehnice.

### Observability-first
Metricile, logging-ul si monitorizarea trebuie gandite inca din fazele timpurii.

---

## 4. User Roles

Sistemul va porni cu urmatoarele roluri principale:

### User
Utilizator standard al platformei, cu accces la datele si activitatea proprie.

### Admin
Gestioneaza utilizatori, roluri si acces administrativ de baza.

### Security Analist
Analizeaza evenimentele de securitate, activitatea suspecta si timeline-ul incidentelor.

### DevOps / Owner
Monitorizeaza sanatatea sistemului, deployment-ul, metricile si starea operationala generala.

---

## 5.MVP Scope

## Backend
MVP-ul backend trebuie sa includa:

- register
- login
- JWT authentication
- model User
- roluri de baza
- users/me
- audit logs
- security events de baza
- PostgreSQL
- health endpoint
- structura backend modulara si clara

## Frontend
MVP-ul frontend trebuie sa includa:

- login page
- register page
- user dashboard
- admin panel basic
- security dashboard basic

## DevOps / Infra
MVP-ul DevOps trebuie sa includa:

- Docker local
- PostgreSQL in mediu local
- Prometheus local
- Grafana local
- baza pentru CI mai tarziu

---

## 6. Explicit Non-Goals for MVP

Lucrurile de mai jos **nu intra in MVP**:

- aplicatia mobila nativa
- machine learning real
- Kafka sau event streaming complex
- SOAR complex
- multi-tenant enterprise
- zero-trust complet
- integratii mutiple externe
- arhitectura pe microservicii
- Kubernetes

Acestea pot exista mai tarziu, dar nu fac parte din fundatia initiala.

---

## 7. Initial Tehincal Stack

### Backend
- Python
- FastAPI
- Uvicorn
- SQLAlchemy
- PostgreSQL
- Alembic
- JWT-based auth

### Frontend
- React
- TypeScript
- Vite

### DevOps / Infra
- Docker
- Docker Compose
- Prometheus
- Grafana

### Documentation
- Markdown in repo
- Documentare incrementala pe etape

---

## 8. Repository Strategy

Proiectul foloseste un **single repository (monorepo)** cu separare clara pe directoare.

Strucutra de baza:

```text
sentinelcore/
├── backend/
├── frontend/
├── infra/
├── docs/
├── .github/
├── .gitignore
├── docker-compose.yml
└── README.md
```

### Motivation

Aceasta abordarea a fost aleasa pentru:

- overhead mai mic la inceput
- coordonare mai simpla intre backend si frontend
- documentatie intr-un singur loc
- CI/CD mai usor de introdus gradual
- schimbari atomice intre UI, API si infrastructura

---

## 9. Backend Structure Direction

Backend-ul va urma directia unui monolit modular.

Strucutra tinta:

```backend/app/
├── api/
├── core/
├── models/
├── schemas/
├── services/
```

### Meaning of each layer
- api/ - endpoints si routere
- core/ - configurari, security utilities, infrastructura interna
- models/ - modele ORM
- schemas/ - validare input/output cu Pydantic
- services/ - logica de business si orchestration

---

## 10. Current Project Status

La acest moment:

- repo-ul și structura de bază sunt create
- frontend-ul pornește corect
- backend-ul are virtual environment propriu
- aplicația FastAPI pornește local
- endpoint-ul `/health` funcționează
- configurația aplicației este citită din `.env`
- PostgreSQL local rulează prin Docker Compose
- conexiunea reală la baza de date este validată
- schema bazei de date este gestionată prin Alembic
- migrația inițială Alembic a fost generată și aplicată
- tabela `alembic_version` confirmă versiunea curentă a schemei DB
- modelul `User` este definit și mapat în tabela `users`
- modelul `AuditLog` este definit și mapat în tabela `audit_logs`
- modelul `SecurityEvent` este definit și mapat în tabela `security_events`
- tabelele `users`, `audit_logs` și `security_events` sunt create prin migrații
- schemele Pydantic pentru user, audit logs și security events sunt definite
- hashing-ul și verificarea parolei sunt implementate
- endpoint-ul `POST /auth/register` este funcțional
- endpoint-ul `POST /auth/login` este funcțional
- generarea și decodarea JWT sunt funcționale
- endpoint-ul `GET /users/me` este funcțional și testat automat
- fundația RBAC este implementată prin roluri pe modelul `User`
- controlul de acces pe rol este validat manual și automat
- endpoint-ul `GET /users/admin-only` este testat pentru user normal și admin
- audit logging-ul este funcțional pentru register, login success, login failed și acces admin
- audit logs pot fi consultate prin API folosind `GET /admin/audit-logs`
- endpoint-ul `GET /admin/audit-logs` este testat automat cu user admin
- security events sunt funcționale pentru register, login success, login failed și admin access
- security events pot fi consultate prin API folosind `GET /security/events`
- endpoint-ul `GET /security/events` este testat automat cu user admin
- testele automate backend sunt introduse prin `pytest`
- testele folosesc baza separată `sentinelcore_test`
- dependența `get_db` este suprascrisă în teste
- backend-ul are 11 teste automate validate
- SentinelCore are acum fundație funcțională pentru IAM, RBAC, Audit Logging, Security Events, migrații DB prin Alembic și teste automate inițiale pentru fluxurile principale
- backend-ul are workflow CI în GitHub Actions 
- workflow-ul CI rulează automat la modificări relevante în `backend/**` 
- workflow-ul poate fi rulat manual prin `workflow_dispatch` 
- CI-ul pornește PostgreSQL ca serviciu în GitHub Actions 
- CI-ul folosește baza de date `sentinelcore_test` 
- CI-ul instalează automat dependențele backend 
- CI-ul rulează testele backend cu `pytest` 
- cele 11 teste backend trec în GitHub Actions 
- acțiunile GitHub au fost actualizate la versiuni compatibile cu Node 24 
- dependențele backend includ suport explicit pentru `pydantic[email]` 
- pipeline-ul backend este verde
- Ruff este introdus pentru linting și verificarea formatării codului Python 
- Ruff este configurat în `backend/pyproject.toml` 
- backend-ul trece local `ruff check .` 
- backend-ul trece local `ruff format --check .` 
- dependency injection-ul FastAPI a fost modernizat cu `Annotated` 
- enum-urile principale au fost modernizate la `StrEnum` 
- workflow-ul Backend CI rulează Ruff înainte de testele pytest 
- pipeline-ul backend este verde pentru Ruff și pytest
- Bandit este introdus pentru scanarea de securitate a codului Python 
- Bandit rulează local și în GitHub Actions 
- Gitleaks este introdus pentru scanarea secretelor în repository 
- Gitleaks rulează local prin Docker și în CI prin Docker 
- Gitleaks scanează istoricul Git prin `fetch-depth: 0` 
- false positive-ul Bandit pentru `token_type="bearer"` a fost tratat punctual cu `# nosec B106` 
- pipeline-ul backend validează Ruff, Bandit, Gitleaks și pytest 
- pipeline-ul backend este verde și fără warning-uri relevante
- modulul Admin User Management a fost început 
- endpoint-ul `GET /admin/users` este implementat 
- lista utilizatorilor poate fi accesată de rolurile `admin` și `owner` 
- userii normali primesc `403 Forbidden` pentru `GET /admin/users` 
- listarea utilizatorilor generează audit log 
- listarea utilizatorilor generează security event 
- endpoint-ul `GET /admin/users` este testat automat 
- backend-ul are 13 teste automate validate 
- implementarea a fost livrată prin branch separat și Pull Request
- endpoint-ul `GET /admin/users/{user_id}` este implementat 
- un admin sau owner poate consulta detaliile unui utilizator individual 
- userii normali primesc `403 Forbidden` pentru `GET /admin/users/{user_id}` 
- userii inexistenți returnează `404 Not Found` 
- vizualizarea detaliilor unui user generează audit log 
- vizualizarea detaliilor unui user generează security event 
- endpoint-ul `GET /admin/users/{user_id}` este testat automat 
- backend-ul are 16 teste automate validate
- Admin User Management Phase 3 is implemented locally on `feat/admin-user-role-phase-3`.
- `PATCH /admin/users/{user_id}/role` allows only an owner to change a non-owner user's role.
- Self-modification, modifying an owner, and assigning the owner role are forbidden.
- The role change, audit log, and security event are committed in one transaction.
- The backend has 29 tests passing locally against the separate PostgreSQL test database.
- Ruff lint and formatting checks pass; Bandit reports no security findings, with warnings about an existing `nosec` comment.
- Phase 3 transaction-failure testing and CI validation remain pending.
- Alembic vede din nou toate modelele; `alembic check` confirmă că modelele și schema DB sunt sincronizate
- utilizatorii inactivi sunt blocați la login și pe endpoint-urile autentificate
- login-ul are timp de răspuns egal pentru email existent și inexistent
- register-ul tratează duplicatele simultane cu `400`, nu `500`
- uneltele de dezvoltare sunt separate în extra-ul `dev`, iar dependențele au versiuni minime
- repository-ul are `README.md` și `backend/README.md`
- backend-ul are 21 de teste automate validate
- Admin User Management Phase 4 este implementat local pe `feat/admin-user-status-phase-4`
- `PATCH /admin/users/{user_id}/status` permite activarea și dezactivarea conturilor, ierarhic pentru `admin` și `owner`
- schimbările de rol și de status au tipuri dedicate de audit și security events
- prima migrație Alembic după schema inițială adaugă noile tipuri de evenimente
- testul de eșec al tranzacției, rămas din Phase 3, este implementat
- backend-ul are 55 de teste automate validate
- input-ul de register și login este validat: lungimi și caractere pentru username, parolă de 12-128 caractere
- emailurile și username-urile sunt tratate fără diferență între litere mari și mici
- backend-ul are 74 de teste automate validate
- prima detecție SIEM-light este implementată: login-urile eșuate repetate pe același email generează un incident `BRUTE_FORCE_DETECTED` și blochează temporar login-ul
- audit logs și security events înregistrează adresa IP a clientului
- backend-ul are 86 de teste automate validate
- audit logs și security events au paginare prin cursor și filtre după tip, severitate, user, email, IP și interval de timp
- consultarea logurilor este auditată
- backend-ul are 107 teste automate validate
- backend-ul expune metrici Prometheus pentru HTTP și security events la `/metrics`
- logurile sunt structurate și au request id pe fiecare cerere
- `/health/ready` verifică disponibilitatea bazei de date
- Prometheus și Grafana rulează local prin Docker Compose, cu dashboard-ul `SentinelCore Overview` provizionat automat
- backend-ul are 132 de teste automate validate
- token-ul JWT identifică userul prin id și sesiunea prin `jti`, cu `iss`, `aud` și `iat` verificate
- sesiunile de login sunt stocate și pot fi revocate: logout, logout de pe toate dispozitivele, revocarea unei sesiuni proprii
- dezactivarea unui cont îi revocă toate sesiunile
- butonul Authorize din Swagger funcționează prin `POST /auth/token`
- backend-ul are 164 de teste automate validate
- sesiunile vechi sunt șterse periodic, după o perioadă de retenție configurabilă
- adminii pot deconecta un user de pe toate dispozitivele fără să-i dezactiveze contul
- backend-ul trece verificarea de tipuri Pyright fără erori
- backend-ul are 184 de teste automate validate
- frontend-ul se va autentifica prin cookie httpOnly, cu protecție CSRF legată de sesiune
- backend-ul are 205 teste automate validate
- frontend-ul are fundația construită: direcția vizuală "consolă de operațiuni" cu paleta "Electric", Tailwind CSS și shadcn/ui, React Router, TanStack Query, română și engleză
- frontend-ul are login prin cookie httpOnly, protecția rutelor, cele două perspective (Contul meu / Organizația), temă și limbă configurabile
- frontend-ul are 49 de teste automate și workflow CI propriu
- jurnalul frontend-ului este în `docs/03-frontend-foundation.md`
- utilizatorii își văd propriul istoric de securitate și se pot deconecta de pe celelalte dispozitive
- perspectiva "Contul meu" are paginile Prezentare (cu rezumat de securitate și alerte recente), Sesiunile mele și Activitatea mea
- backend-ul are 223 de teste automate validate, iar frontend-ul 83
---

## 11. Current Sprint

### Sprint 1 - Backend Foundation

Obiectivul Sprintului 1 este sa construiasca fundatia corecta a backend-ului.

Ordine de lucru planificata:

1. health endpoint si structura minima FastaPI
2. configurare database
3. model User
4. creare tabele / migratii
5. register
6. login
7. users/me
8. roluri de baza
9. audit log de baza
10. security events de baza

---

## 12. Working Method

Proiectul se construieste prin **project-driven learning.**

Reguli de lucru:

- nu se cer bucati mari de cod complet fara intelegere
- nu se sare peste fundatie
- se invata doar ce este necesar pentru pasul curent
- fiecare etapa trebuie implementata, inteleasa si documentata
- problemele trebuie rezolvate concret, nu ocolite
- complexitatea se introduce treptat, nu decorativ

---

## 13. Main Risks

Riscul principal al proiectului nu este complexitatea tehnica, ci:

- constructia fara intelegere reala
- saritul peste baza
- adaugarea de tehnologii doar pentru impresie
- umflarea arhitecturii inainte de validarea fundatiei
- documentatie facuta prea tarziu sau deloc

---

## 14. Project Standard

SentinelCore trebuie sa fie tratat ca un produs serios, nu ca o aplicatie de laborator.

Standardul urmarit:

- structura clara
- decizii argumentate
- implementare incrementala
- documentatie continua
- naming curat
- separare logica a componentelor
- baza solida pentru audit, securitate si observabilitate

---

## 15. Immediate Next Step

Pasul imediat este finalizarea modulului Admin User Management prin Phase 3:

- schimbarea rolului unui utilizator, permisa doar pentru `owner`
- audit log si security event pentru schimbarea de rol
- validare prin CI si Pull Request
