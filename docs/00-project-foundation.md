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
- `pyproject.toml` este configurat pentru fundația backend-ului
- aplicația FastAPI pornește local
- endpoint-ul `/health` funcționează
- configurația aplicației este citită din `.env`
- PostgreSQL local rulează prin Docker Compose
- conexiunea reală la baza de date este validată
- modelul `User` este definit și mapat în tabela `users`
- tabela `users` a fost creată și verificată în PostgreSQL
- schemele Pydantic pentru user sunt definite
- hashing-ul si verificarea parolei sunt implementate
- endpoint-ul `POST /auth/register` este funcțional
- endpoint-ul `POST /auth/login` este functional
- generarea JWT este functionala
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

Pasul imediat dupa aceasta fundatie este continuarea Sprintului 1 prin:

- configurarea conexiunii la baza de date
- definirea modelului User
- pregatirea pentru register / login

Acestea vor fi facute etapizat, nu toate deodata.

---

# Ce e bun in documentul asta

Fixeaza:

- ce este proiectul
- ce nu este proiectul
- de ce ai ales monorepo
- ce intra in MVP
- ce nu intra in MVP
- unde esti acum
- care e ordinea corecta

Adica reduce haosul.
