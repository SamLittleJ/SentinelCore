# 03 - Frontend Foundation

## Scop

Acest document descrie fundatia aplicatiei web SentinelCore: directia vizuala, baza tehnica si primele ecrane functionale.

---

## Etapa 1: Fundatia frontend-ului

### 1. Directia vizuala

Au fost comparate trei directii vizuale, aplicate pe acelasi ecran de evenimente de securitate. A fost aleasa **directia A, "consola de operatiuni"**:
- tema intunecata implicita, cu varianta luminoasa completa
- interfata densa, potrivita pentru analisti care urmaresc evenimente mult timp
- `IBM Plex Sans` pentru interfata si `IBM Plex Mono` pentru date tehnice: ore, IP-uri, tipuri de evenimente, nume de utilizator

Paleta initiala a fost considerata prea stearsa. Din trei palete mai vii a fost aleasa **"Electric"**: albastru electric pe bleumarin.

Principiile paletei:
- culorile au fost generate in spatiul OKLCH, unde luminozitatea perceputa este controlabila direct
- pe tema intunecata, fundalul nu este negru, iar textul nu este alb pur (contrast in jur de 14:1), pentru a reduce oboseala ochilor
- toate perechile text/fundal trec de pragul WCAG AA
- cele cinci culori de grafic au trecut validatorul de palete pe ambele teme, inclusiv separarea pentru daltonism; ordinea lor este fixa
- culorile de severitate (info, avertizare, incident, succes) sunt separate de culoarea de brand si apar mereu cu text si forma, nu doar prin culoare

### 2. Doua perspective: Contul meu si Organizatia

SentinelCore este gandit ca un hub de monitorizare cu doua perspective:
- **Contul meu**: orice utilizator isi urmareste propriul cont (sesiuni, activitate, alerte)
- **Organizatia**: administratorii si analistii de securitate urmaresc toate conturile

Comutatorul dintre perspective apare doar pentru rolurile `admin`, `owner` si `security_analyst`. Ruta `/org` este protejata si in frontend, dar autorizarea reala ramane in API: frontend-ul doar evita afisarea unor pagini ale caror cereri ar fi oricum refuzate.

### 3. Baza tehnica

| Zona | Alegere |
| --- | --- |
| Framework | React 19, TypeScript, Vite |
| Stiluri | Tailwind CSS 4, variabile CSS pentru tema |
| Componente | shadcn/ui (pe primitive Radix), copiate in `src/components/ui` |
| Rutare | React Router 8 |
| Date de la server | TanStack Query |
| Traduceri | i18next, romana implicit, engleza disponibila |
| Fonturi | `@fontsource`, servite din aplicatie |
| Teste | Vitest, Testing Library, MSW pentru API simulat |

Fonturile sunt incluse in build in loc sa fie incarcate de la Google Fonts: browserul nu face cereri catre terti, iar o politica CSP stricta ramane posibila. Subsetul `latin-ext` acopera `ă`, `ș` si `ț`.

### 4. Problema intalnita: shadcn si pachetul `cn`

Initializarea interactiva `shadcn init` s-a blocat asteptand o alegere, asa ca `components.json` a fost scris manual. La adaugarea componentelor, CLI-ul nu a rezolvat aliasul `@/lib/utils`: a generat `import { cn } from "cn"` si a instalat un pachet npm fara legatura cu proiectul, numit `cn`.

Pachetul a fost dezinstalat, iar importurile corectate catre `@/lib/utils`. Componentele importa acum doar pachete cunoscute: `radix-ui`, `lucide-react`, `class-variance-authority` si React.

Lectia: comenzile care modifica dependentele trebuie verificate in `package.json` dupa rulare, chiar si cand vin de la unelte cunoscute.

### 5. Autentificarea in browser

Frontend-ul foloseste autentificarea prin cookie introdusa in backend:
- login prin `POST /api/auth/session`; token-ul ajunge intr-un cookie `httpOnly`, pe care codul frontend nu il poate citi
- clientul API (`src/lib/api.ts`) trimite automat header-ul `X-CSRF-Token`, cu valoarea cookie-ului `sentinelcore_csrf`, la orice cerere `POST`, `PUT`, `PATCH` sau `DELETE`
- erorile backend-ului devin `ApiError`, cu `status`, `detail` si `Retry-After`

In development, Vite trimite cererile `/api/*` catre backend (`localhost:8000`). Frontend-ul si API-ul sunt astfel pe aceeasi origine: nu este nevoie de CORS, iar cookie-urile `SameSite=Strict` sunt trimise normal.

### 6. Sesiunea si protectia rutelor

- utilizatorul curent este citit din `/users/me` prin TanStack Query
- `RequireAuth` trimite vizitatorii fara sesiune la `/login?next=<pagina>`, iar dupa login ii readuce pe pagina ceruta
- parametrul `next` accepta doar cai interne ale aplicatiei; o adresa ca `/login?next=https://evil.example` duce la `/me` (protectie impotriva open redirect)
- un cont dezactivat ajunge la pagina de login, cu explicatie
- orice raspuns `401` primit in timpul folosirii (sesiune expirata sau revocata) declanseaza reverificarea utilizatorului si trimiterea la login
- erorile de retea sunt reincercate de doua ori, iar apoi este afisat un ecran cu buton de reincercare
- logout-ul goleste toate datele din cache, pentru ca urmatorul utilizator sa nu vada nimic din sesiunea anterioara

Mesajele de eroare de la login sunt specifice: credentiale gresite, cont dezactivat, date invalide, server indisponibil si blocare brute-force, cu numarul de minute calculat din `Retry-After`.

### 7. Tema si limba

- tema implicita este cea intunecata; din meniul contului se poate alege luminoasa sau "ca sistemul", iar alegerea este pastrata
- limba implicita este romana; engleza se alege din acelasi meniu, iar atributul `lang` al paginii este actualizat
- fisierul de traduceri in engleza este tipat dupa cel in romana, deci o cheie lipsa sau in plus opreste verificarea de tipuri
- formele de plural romanesti sunt tratate corect: "1 minut", "2 minute", "20 de minute"

### 8. Ecrane in aceasta etapa

- pagina de login
- structura aplicatiei: bara laterala cu comutatorul de perspectiva, navigarea si meniul contului
- **Contul meu / Prezentare**: profilul utilizatorului
- pagini de rezerva pentru sectiunile din etapele urmatoare: sesiuni, activitate, evenimente de securitate, jurnal de audit, utilizatori

### 9. Securitatea dependentelor

`npm audit` a gasit 10 vulnerabilitati (7 de severitate mare) in lockfile-ul mostenit din template, aproape toate in unelte de build si dezvoltare. Toate aveau versiuni corectate compatibile si au fost rezolvate prin `npm audit fix`, fara schimbari de versiune majora. Vite a urcat la 8.3.3.

CI-ul ruleaza `npm audit --audit-level=high` la fiecare Pull Request.

### 10. CI pentru frontend

Workflow-ul `.github/workflows/frontend-ci.yml` ruleaza la Pull Request-uri catre `main` si la push pe `main` cu modificari in `frontend/`:
- `npm ci`
- `npm audit --audit-level=high`
- `npm run lint`
- `npm run typecheck`
- `npm test`
- `npm run build`

### 11. Validarea locala

- eslint -> fara probleme
- tsc -> fara erori
- vitest -> 49 passed
- build -> reusit
- npm audit -> 0 vulnerabilitati

Testele acopera: clientul API (CSRF doar pe cereri care modifica date, erori, `Retry-After`, raspunsuri `204`), filtrarea parametrului `next`, login-ul cu toate tipurile de eroare, redirectionarea dupa login, protectia rutelor si a perspectivei de organizatie, tema, limba, logout-ul cu token CSRF si iesirea din aplicatie cand sesiunea se termina.

Verificare inversa: fiecare dintre urmatoarele modificari face cel putin un test sa pice: parametrul `next` nefiltrat, lipsa header-ului CSRF, lipsa verificarii rolului pentru `/org`, ignorarea unui `401` primit in timpul folosirii.

Verificare end-to-end, cu backend-ul real pe o baza temporara si Vite pornit:
- prin proxy: login `204` cu cookie `httpOnly`, `/users/me` autentificat prin cookie, logout fara CSRF `403`, cu CSRF `204`, apoi `401`
- capturi reale in Firefox ale paginii de login si ale celor doua perspective, pentru un utilizator cu rol de analist

### 12. Ce urmeaza

Etapa 2 este descrisa mai jos. Urmeaza:
- **Etapa 3, Organizatia**: evenimente de securitate si jurnal de audit, cu filtrele si paginarea existente, plus administrarea utilizatorilor
- **Etapa 4**: dashboard-uri cu carduri si grafice

## Etapa 2: Contul meu

### 13. Ce a fost construit

Backend-ul a primit doua endpoint-uri (detalii in `docs/01-backend-foundation.md`, sectiunea "My Account API - Phase 1"):
- `GET /users/me/activity`: evenimentele de securitate despre propriul cont
- `DELETE /users/me/sessions`: deconectarea celorlalte dispozitive

Frontend-ul are trei pagini reale in perspectiva "Contul meu".

### 14. Prezentare

Deasupra profilului apare un rezumat de securitate:
- **Sesiuni active**, cu link catre gestionarea lor
- **Autentificarea anterioara**: cand si de pe ce IP. Cea mai noua autentificare este chiar sesiunea curenta, asa ca este afisata cea dinaintea ei: daca utilizatorul nu o recunoaste, contul poate fi compromis
- **Alerte din ultimele 30 de zile**: avertismentele si incidentele. Se citeste o singura pagina de 50; daca exista mai multe, numarul apare ca "50+"

Sub rezumat sunt ultimele 5 alerte si un link catre activitate, filtrata pe alerte. Daca una dintre cereri esueaza, doar cifra respectiva apare ca "Indisponibil"; restul paginii functioneaza.

### 15. Sesiunile mele

- sesiunea din acest browser apare prima, marcata "Aceasta sesiune", cu butonul "Deconecteaza-te"
- fiecare sesiune arata dispozitivul, IP-ul, cand a inceput si cand expira
- celelalte sesiuni pot fi inchise individual sau toate odata; ambele actiuni cer confirmare in pagina, fara dialoguri
- daca o sesiune era deja inchisa (`404`), pagina explica asta si reincarca lista

Dispozitivul este dedus din `User-Agent` (de exemplu "Firefox pe Linux", "Chrome pe Android"). Header-ul este trimis de client si poate fi falsificat, deci este doar un indiciu; textul complet apare la trecerea mouse-ului peste nume. Clientii necunoscuti, de exemplu scripturile, apar ca "Dispozitiv necunoscut".

Butoanele "Inchide sesiunea" se repeta pe fiecare rand, asa ca fiecare este legat prin `aria-describedby` de numele dispozitivului, pentru cititoarele de ecran.

### 16. Activitatea mea

- tabel cu evenimentul, severitatea, IP-ul si data; data relativa apare la trecerea mouse-ului
- filtru "Tot" / "Doar alerte", pastrat in adresa (`/me/activity?filter=alerts`), deci linkul din Prezentare deschide direct alertele; o valoare necunoscuta este ignorata
- paginile mai vechi se incarca la cerere, cu cursorul primit de la API

Evenimentele sunt descrise dupa tip, in limba interfetei. Severitatea apare mereu ca icon si cuvant, nu doar prin culoare.

### 17. Componente noi

- `SeverityBadge`: severitatea cu icon, text si culorile de severitate ale temei; va fi refolosita in perspectiva Organizatia
- `ActivityTable`: tabelul de evenimente, folosit in Prezentare si in Activitate
- `lib/format.ts`: date absolute si relative ("acum 5 minute", "peste 25 de minute"), in limba interfetei; dupa 30 de zile se afiseaza data exacta

### 18. Validarea locala

- eslint -> fara probleme
- tsc -> fara erori
- vitest -> 83 passed
- build -> reusit

Testele noi acopera: recunoasterea dispozitivelor, formatarea datelor relative, ordinea si continutul sesiunilor, inchiderea unei sesiuni cu confirmare si anulare, sesiunea deja inchisa, eroarea la inchidere, inchiderea celorlalte sesiuni, deconectarea din pagina, descrierea evenimentelor, filtrul de alerte si pastrarea lui in adresa, paginarea, starile goale, rezumatul din Prezentare si comportamentul cand o cerere esueaza.

Verificare inversa: fiecare dintre urmatoarele modificari face cel putin un test sa pice: sesiunea curenta neadusa prima, paginarea fara cursor, lipsa semnului "+" pentru mai mult de o pagina de alerte, filtrul de alerte fara severitati, afisarea sesiunii curente ca "autentificare anterioara".

Verificare end-to-end, cu backend-ul real pe o baza temporara si Vite pornit:
- prin proxy: istoricul propriu contine autentificarile reusite si esuate, `user_id` ca parametru primeste `422`, deconectarea celorlalte dispozitive fara CSRF `403`, cu CSRF `200`, cu sesiunea curenta pastrata si audit log `OTHER_SESSIONS_REVOKED`
- capturi reale in Firefox ale celor trei pagini, in tema intunecata, si ale paginii de sesiuni in tema luminoasa; dupa ele, tabelul de alerte din Prezentare a fost intins pe toata latimea, ca sa se alinieze cu rezumatul

Optiunea `baseUrl` a fost scoasa din `tsconfig.json` si `tsconfig.app.json`: TypeScript 6, folosit de VS Code, o marca drept depreciata (eroare), iar din TypeScript 4.1 alias-ul `@/*` din `paths` functioneaza si fara ea. Proiectul a fost verificat atat cu TypeScript 5.9, cat si cu TypeScript 6.

Bundle-ul JavaScript are aproximativ 564 KB. Impartirea lui pe pagini ramane pentru etapa 3, cand vor exista paginile perspectivei Organizatia.

### 19. Ajustare de layout: continut centrat

Pe monitoare late, continutul statea lipit de bara laterala, iar jumatatea dreapta a ecranului ramanea goala. Acum toate paginile sunt intr-o singura coloana de cel mult 1024 px (`max-w-5xl`), centrata in spatiul de langa bara laterala. Latimea este aceeasi pe toate paginile, ca titlul sa nu-si schimbe pozitia la navigare; paginile nu mai au latimi proprii.

Spatiul de deasupra continutului a crescut la 48 px pe ecrane mari (32 px pe telefon), iar cel de jos la 48 px.

## Organizatia - PR 1 (backend)

### 20. Actiunile primite in Activitatea mea

Backend-ul inregistreaza acum tinta actiunilor de administrare, iar istoricul propriu include si actiunile facute asupra contului, marcate cu `as_target: true`. Fara o schimbare in frontend, utilizatorul afectat ar fi vazut textul actorului ("Ai schimbat rolul unui utilizator").

`ActivityTable` foloseste pentru aceste elemente textele noi din `eventsAsTarget`:
- "Rolul tau a fost schimbat"
- "Contul tau a fost reactivat" / "Contul tau a fost dezactivat"
- "Un administrator ti-a inchis sesiunile"

Tipurile care pot fi primite sunt listate in `ACCOUNT_ACTION_TYPES` (`features/account/api.ts`). Adresa IP a acestor elemente vine `null` de la API (este a operatorului), deci coloana arata "—".

Validare: eslint, tsc, vitest (84 passed), build. Verificare inversa: ignorarea campului `as_target` face testul nou sa pice.

## Izolarea conturilor (backend)

### 21. Contul blocat

Backend-ul poate bloca temporar un cont. Frontend-ul trateaza doua situatii noi:
- la login, `403` cu `detail` `Account temporarily locked` afiseaza "Contul este blocat temporar din motive de securitate. Contacteaza un administrator.", separat de mesajul pentru cont dezactivat; ambele raspunsuri au acelasi status, deci diferenta se face dupa `detail` (`isAccountLockedError()` in `features/auth/api.ts`)
- o sesiune refuzata cu acelasi raspuns duce la `/login?reason=locked`, cu acelasi mesaj

In Activitatea mea apar tipurile noi: "Contul tau a fost blocat temporar" / "Contul tau a fost deblocat" pentru contul afectat si "Ai blocat temporar un cont" / "Ai deblocat un cont" pentru operator. `User` are campul `locked_until`.

Validare: eslint, tsc, vitest (86 passed), build, `npm audit`. Verificare inversa: ignorarea `detail` la `403` face testele noi sa pice. Capturi reale in Firefox, in ambele teme, ale paginii de login pentru cont blocat si ale paginii Activitatea mea dupa blocare si deblocare.

## Etapa 3: Organizatia - Evenimente si Audit

### 22. Ce a fost construit

Primele doua pagini ale perspectivei Organizatia, pentru `admin`, `owner` si `security_analyst`:
- Evenimente de securitate (`/org/events`), pe `GET /security/events`
- Jurnal de audit (`/org/audit`), pe `GET /admin/audit-logs`

Ambele folosesc aceleasi componente: bara de filtre, tabelul si panoul de detalii.

### 23. Filtrele

- **Interval**: ultima ora, 24 de ore, 7 zile (implicit), 30 de zile, tot. Inceputul intervalului se calculeaza cand se incarca prima pagina; paginile urmatoare il pastreaza, ca "Incarca mai multe" sa nu mute fereastra.
- **Severitate** (doar la evenimente): butoane care se pot combina.
- **Tipuri**: un meniu cu casute, care ramane deschis cat timp se aleg mai multe tipuri.
- **Cautare**: email sau adresa IP exacta, intr-un singur camp. O adresa IPv4 sau orice valoare cu `:` (IPv6) merge la filtrul `ip_address`, restul la `email`. Cautarea porneste la Enter sau la butonul de cautare, nu la fiecare tasta.
- **Cont / Tinta**: `user_id` si `target_user_id`, afisate ca etichete care se pot elimina; vin din link-uri sau din panoul de detalii.

Toate filtrele sunt pastrate in adresa (`range`, `type`, `severity`, `q`, `user`, `target`), deci o vedere filtrata poate fi trimisa ca link. Valorile invalide din adresa sunt ignorate; valorile implicite nu apar in adresa. Un filtru respins de API (`422`, de exemplu o adresa IP gresita) are mesajul sau.

### 24. Tabelul si detaliile

Coloanele: data, eveniment, severitate (doar la evenimente), cont, adresa IP. Evenimentele sunt descrise neutru ("Rol schimbat", "Cont blocat temporar"), nu la persoana a doua ca in Activitatea mea; textele sunt in `orgEvents.types` si `audit.types`.

Un clic oriunde pe rand deschide detaliile; de la tastatura, descrierea evenimentului este un buton. Detaliile sunt intr-un panou lateral (Radix Dialog: focusul ramane in panou, Escape il inchide, focusul revine pe rand). Panoul arata contul (email si id), tinta, adresa IP, sursa, mesajul pentru operatori si actiuni care restrang lista: "Doar acest cont", "Doar aceasta tinta", "Doar aceasta adresa IP". O incercare esuata care numeste doar un email restrange dupa email.

### 25. Reincarcarea si auditul

Fiecare incarcare a acestor pagini este auditata de backend. De aceea, listele nu se reincarca singure cand fereastra revine in focus (`refetchOnWindowFocus: false`); pagina are un buton "Reimprospateaza", care revine la prima pagina, cu intervalul masurat din acel moment. Pagina de audit spune explicit ca si consultarea ei este inregistrata.

### 26. Componente comune noi

- `PagedResults`: starile de incarcare, eroare (cu reincercare) si lista goala, plus "Incarca mai multe", pentru orice lista citita cu cursor; folosita si de Activitatea mea
- `SegmentedControl`: butoane exclusive, folosite pentru interval si pentru filtrul din Activitatea mea; pe ecrane inguste trec pe randul urmator
- `ui/sheet.tsx`: panoul lateral, pe Radix Dialog
- `features/org`: clientul API, filtrele din adresa, hook-urile, bara de filtre, tabelul si detaliile

Textele "Incarca mai multe", "Se incarca" si "Ai ajuns la inceputul istoricului" au trecut din `activity` in `paging`.

### 27. Impartirea bundle-ului

Paginile organizatiei se incarca la cerere (`React.lazy` in `pages/lazy.ts`, cu un `Suspense` in `AppShell`). Codul lor (aproximativ 21 KB) nu mai ajunge la utilizatorii obisnuiti, iar avertismentul Vite pentru chunk-uri peste 500 KB a disparut: aplicatia are acum un chunk principal (~311 KB) si unul cu bibliotecile comune (~262 KB). Incarcarea initiala totala ramane aproape aceeasi, pentru ca bibliotecile (React, Radix, i18next) domina.

### 28. Validarea locala

- eslint -> fara probleme
- tsc (5.9 si 6.0) -> fara erori
- vitest -> 111 passed
- build -> reusit, fara avertismentul de dimensiune
- npm audit -> 0 vulnerabilitati

Testele noi acopera: descrierile neutre, intervalul implicit si "Tot", severitatea si tipurile (cu adresa actualizata), citirea filtrelor dintr-un link, cautarea dupa email si IPv6 cu focusul pastrat, eliminarea etichetelor si resetarea, panoul de detalii si actiunile lui, deschiderea cu mouse-ul si inchiderea cu Escape, paginarea cu acelasi interval, reimprospatarea, filtrul invalid, cele doua stari goale, jurnalul de audit (fara severitate, mesaj lipsa, filtrul de tinta) si functiile de filtrare.

Verificare inversa: fiecare dintre urmatoarele modificari face cel putin un test sa pice: intervalul recalculat la fiecare pagina, IP-ul cautat ca email, actiunea de tinta care filtreaza actorul, tipuri necunoscute acceptate din adresa, intervalul implicit scris in adresa, meniul de tipuri inchis la prima alegere, mesajul pentru filtrul invalid ignorat, campul de cautare care nu urmareste schimbarile din afara, randurile care nu se deschid, textul pentru lista goala care ignora filtrele.

Un test a prins o problema reala: campul de cautare era remontat la fiecare cautare (prin `key`) si pierdea focusul dupa Enter. Acum isi sincronizeaza valoarea in timpul randarii, fara remontare.

Verificare end-to-end, cu backend-ul real pe o baza temporara si Vite pornit: date create prin API (login-uri reusite si esuate, brute force, schimbare de rol, blocare si deblocare, inchiderea sesiunilor, dezactivare) si cateva login-uri esuate inserate direct, cu adrese diferite. Capturi reale in Firefox, ca analist, in ambele teme: evenimentele, jurnalul de audit, panoul de detalii deschis, filtre active si lungimea de telefon (390 px). Dupa capturi: antetele "Cont" si "Adresa IP" nu mai folosesc fontul monospace, iar butoanele de interval trec pe randul urmator pe telefon, in loc sa iasa din ecran.

Observatie: listele erau ordonate dupa `id` (ordinea inregistrarii), nu dupa `created_at`, iar evenimentele inserate cu o data din trecut apareau deasupra celor mai noi. Rezolvat in backend (Event Ordering - Phase 1, `docs/01`): listele sunt ordonate dupa moment, iar frontend-ul nu s-a schimbat.

### 29. Barele de derulare

Pe telefon, sub meniul orizontal al barei laterale aparea o bara de derulare alba, si in tema intunecata. `color-scheme` era deja setat, dar unele browsere (printre ele Firefox fara interfata, folosit pentru capturi) il ignora pentru barele de derulare. Acum `:root` are `scrollbar-color` din culorile temei (`--muted-foreground` la 45%, pe fundal transparent), iar meniul orizontal are bara subtire (`scrollbar-width: thin`). Capturile la 390 px, in ambele teme, arata o bara discreta in culorile temei.
