# Projet_stage - BioData Explorer

BioData Explorer est une application web de recherche biodiversite. Elle interroge plusieurs sources d'occurrences biologiques, harmonise les resultats, enrichit les especes avec le statut IUCN, affiche un apercu dans le navigateur et permet l'export CSV.

L'application est composee de :

- un backend FastAPI dans `Backend/`
- un frontend HTML/CSS/JavaScript dans `Frontend/`
- une base SQLite locale dans `Backend/data/app.db`

## Fonctionnalites principales

- Recherche par source :
  - GBIF
  - Silene Expert
  - iNaturalist
  - STELI
  - recherche combinee GBIF + Silene Expert + iNaturalist + STELI
- Filtres :
  - pays
  - famille
  - genre
  - espece
  - date de debut
  - date de fin
  - type de donnee iNaturalist : `research`, `needs_id`, `casual`
- Export CSV standardise.
- Enrichissement IUCN via l'API IUCN v4 si `IUCN_TOKEN` est configure.
- Comptes utilisateurs avec validation admin.
- Interface admin pour valider, invalider et supprimer des comptes.
- Nettoyage admin :
  - supprimer l'historique des recherches
  - supprimer les comptes non valides
- Historique personnel des recherches par utilisateur.

## Structure du projet

```text
Backend/
  app/
    main.py
    routes/
      admin.py
      auth.py
      combined.py
      history.py
      inaturalist.py
      search.py
      silene.py
      silene_expert.py
      steli.py
    services/
      combined_service.py
      gbif_service.py
      inaturalist_service.py
      iucn_service.py
      silene_expert_service.py
      silene_service.py
      steli_service.py
    utils/
      auth.py
      csv_export.py
      database.py
      history.py
      row_normalization.py
  data/
    app.db

Frontend/
  admin.html
  dashboard.html
  exports.html
  login.html
  search.html
  *.js
  *.css
```

## Prerequis

- Python 3.11+
- Un environnement virtuel Python
- Acces internet pour GBIF, iNaturalist, Silene Expert et IUCN

Installation :

```powershell
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt
```

## Configuration `.env`

Le backend charge automatiquement le fichier `.env` place a la racine du projet.

Exemple :

```env
APP_SECRET_KEY=change-this-long-random-secret
ADMIN_EMAIL=noelline.tsafack@imbe.fr

IUCN_TOKEN=

# Option 1 : token/cookie Silene Expert manuel
SILENE_EXPERT_TOKEN=

# Option 2 : connexion automatique Silene Expert
SILENE_EXPERT_LOGIN=
SILENE_EXPERT_PASSWORD=
SILENE_EXPERT_APP_ID=3

# Serveur avec proxy/certificats systeme, souvent necessaire en universite
SILENE_TRUST_ENV=true
```

Notes importantes :

- `APP_SECRET_KEY` signe les sessions utilisateur. En production, utiliser une valeur longue et secrete.
- `ADMIN_EMAIL` definit le compte administrateur initial. Pour Noelline : `noelline.tsafack@imbe.fr`.
- `IUCN_TOKEN` est necessaire pour remplir la colonne `status` avec le statut Red List.
- `SILENE_EXPERT_TOKEN` reste supporte.
- Si `SILENE_EXPERT_LOGIN` et `SILENE_EXPERT_PASSWORD` sont renseignes, le backend peut obtenir et rafraichir le token Silene automatiquement.
- Sur un serveur universitaire qui passe par un proxy, ajouter `SILENE_TRUST_ENV=true`.
- Ne jamais committer `.env`.

## Lancer en local

Backend :

```powershell
.\venv\Scripts\python.exe -m uvicorn Backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

ou :

```powershell
.\start_backend.ps1
```

Frontend :

```powershell
python -m http.server 8081 --bind 127.0.0.1 -d Frontend
```

ou :

```powershell
.\start_frontend.ps1
```

Pages utiles :

```text
http://127.0.0.1:8081/login.html
http://127.0.0.1:8081/dashboard.html
http://127.0.0.1:8081/search.html
http://127.0.0.1:8081/exports.html
http://127.0.0.1:8081/admin.html
```

## Comptes utilisateurs et administration

Les comptes sont stockes dans `Backend/data/app.db`.

Workflow :

- Un utilisateur cree un compte avec nom, prenom, email et mot de passe.
- Si son email ne correspond pas a `ADMIN_EMAIL`, le compte est cree en `non valide`.
- Un compte `non valide` ne peut pas se connecter.
- L'administrateur ouvre `admin.html`.
- L'administrateur peut :
  - valider un compte
  - invalider un compte
  - regenerer un mot de passe temporaire pour un compte non administrateur
  - supprimer un compte non administrateur
  - supprimer tous les comptes non valides
  - nettoyer tout l'historique des recherches

Pour definir Noelline comme administratrice :

```env
ADMIN_EMAIL=noelline.tsafack@imbe.fr
```

Puis redemarrer le backend. Au demarrage, le backend marque ce compte comme admin et valide s'il existe dans la base.

Si l'email du compte Noelline change dans la base locale, il faut soit :

- modifier la ligne dans la base SQLite
- ou recreer le compte avec le bon email

## Securite

Points deja en place :

- Les mots de passe sont haches avec PBKDF2 SHA-256 et un sel aleatoire.
- Les tokens de session sont signes avec `APP_SECRET_KEY`.
- Les routes admin exigent un utilisateur connecte avec `is_admin = 1`.
- Les comptes non valides sont bloques a la connexion.
- `.env` est ignore par Git.
- `Backend/data/` est ignore par Git.

Points d'attention :

- Configurer `APP_SECRET_KEY` sur chaque serveur.
- Configurer `ADMIN_EMAIL` sur chaque serveur.
- La base `Backend/data/app.db` est locale a chaque machine. Elle n'est pas poussee sur GitHub.
- Un compte cree sur le PC local n'existe pas automatiquement sur le serveur.
- Apres modification de `.env`, redemarrer le backend.
- Ne jamais mettre les mots de passe Silene, tokens IUCN ou secrets dans GitHub.

## Base SQLite

La base est creee automatiquement au demarrage du backend par `Backend/app/utils/database.py`.

Tables principales :

- `users`
- `search_history`

La table `users` contient notamment :

- `email`
- `first_name`
- `last_name`
- `password_hash`
- `is_validated`
- `is_admin`
- `validated_at`
- `validated_by`
- `last_login_at`
- `last_activity_at`
- `created_at`

Nettoyage disponible dans l'admin :

- `Nettoyer historique` supprime les lignes de `search_history`.
- `Supprimer comptes non valides` supprime les comptes avec `is_validated = 0` et `is_admin = 0`.

## Configuration frontend

Le frontend utilise `Frontend/config.js`.

- En local (`localhost`, `127.0.0.1`, `file://`), l'API pointe vers `http://127.0.0.1:8000`.
- En production, l'API pointe vers `/api`.
- Les fichiers JS/CSS locaux sont charges avec cache busting par `Frontend/asset-loader.js`.

Les scripts frontend doivent utiliser :

```javascript
const API_URL = window.API_URL;
```

## Colonnes CSV standardisees

Colonnes principales :

```text
source_bdd
country
coordinates
eventDate
basisOfRecord
datasetName
family
genus
species
status
```

Pour iNaturalist, une colonne supplementaire est ajoutee :

```text
quality_grade
```

Valeurs possibles :

- `research`
- `needs_id`
- `casual`

## Endpoints principaux

Authentification :

```text
POST /auth/register
POST /auth/login
GET /auth/me
```

Admin :

```text
GET /admin/users
PATCH /admin/users/{user_id}/validate
PATCH /admin/users/{user_id}/invalidate
PATCH /admin/users/{user_id}/password
DELETE /admin/users/{user_id}
DELETE /admin/users/unvalidated
DELETE /admin/history
```

Historique :

```text
GET /history?limit=10
```

Recherche JSON :

```text
GET /search
GET /silene-expert/search
GET /inaturalist/search
GET /steli/search
GET /combined/search
```

Export CSV :

```text
GET /search/csv
GET /silene-expert/search/csv
GET /inaturalist/search/csv
GET /steli/search/csv
GET /combined/search/csv
```

## Ajouter une nouvelle base de donnees

Pour ajouter une nouvelle source, suivre toujours les memes etapes.

### 1. Creer un service backend

Ajouter un fichier dans :

```text
Backend/app/services/
```

Exemple :

```text
Backend/app/services/nouvelle_source_service.py
```

Le service doit :

- appeler l'API externe
- appliquer les filtres utiles (`country`, `family`, `genus`, `species`, dates, etc.)
- transformer les resultats en lignes Python
- retourner des lignes compatibles avec les colonnes standardisees

Chaque ligne doit autant que possible contenir :

```python
{
    "source_bdd": "NOUVELLE_SOURCE",
    "country": "...",
    "coordinates": "...",
    "eventDate": "...",
    "basisOfRecord": "...",
    "datasetName": "...",
    "family": "...",
    "genus": "...",
    "species": "...",
    "status": "...",
}
```

Utiliser les helpers existants quand possible :

- `Backend/app/utils/date_filters.py`
- `Backend/app/utils/row_normalization.py`
- `Backend/app/utils/csv_export.py`

### 2. Creer une route backend

Ajouter un fichier dans :

```text
Backend/app/routes/
```

Exemple :

```text
Backend/app/routes/nouvelle_source.py
```

La route doit exposer :

```text
GET /nouvelle-source/search
GET /nouvelle-source/search/csv
```

S'inspirer de :

- `Backend/app/routes/steli.py`
- `Backend/app/routes/inaturalist.py`
- `Backend/app/routes/search.py`

### 3. Brancher la route dans FastAPI

Modifier :

```text
Backend/app/main.py
```

Ajouter l'import :

```python
from Backend.app.routes.nouvelle_source import router as nouvelle_source_router
```

Puis :

```python
app.include_router(nouvelle_source_router)
```

### 4. Integrer la source dans le frontend

Modifier :

```text
Frontend/search.html
Frontend/search.js
```

Ajouter la source dans le select et les boutons de source.

Dans `search.js`, ajouter le cas qui construit l'URL API :

```javascript
`${API_URL}/nouvelle-source/search?...`
```

### 5. Ajouter l'export CSV

Si la source doit exporter en CSV :

- creer ou reutiliser la route `/search/csv`
- verifier les colonnes exportees
- tester avec un petit `limit` et `max_pages`

### 6. Ajouter la source combinee si necessaire

Si la source doit apparaitre dans la recherche combinee :

- modifier `Backend/app/services/combined_service.py`
- appeler le nouveau service
- fusionner les resultats avec les autres sources
- gerer les erreurs sans bloquer toutes les sources

### 7. Ajouter des tests

Ajouter un test dans :

```text
Backend/test_..._unittest.py
```

Tester au minimum :

- construction des parametres
- normalisation d'une ligne
- export CSV si disponible
- gestion d'une reponse vide ou erreur API

## Performance

Les gros exports peuvent prendre du temps car ils interrogent plusieurs API externes et enrichissent les especes avec IUCN.

Optimisations deja en place :

- GBIF, Silene Expert, iNaturalist et STELI sont lances en parallele pour la recherche combinee.
- Les statuts IUCN sont recuperes en parallele et caches.
- iNaturalist precharge les lieux/pays par groupe.

Conseils :

- Pour un test rapide : `limit=50`, `max_pages=5`.
- Par defaut, les exports utilisent `limit=300` et `max_pages=67`, soit environ 20 000 resultats maximum par source.
- Pour un export large : augmenter progressivement `max_pages`.
- Ajouter un filtre precis (`species` ou `genus`) reduit fortement le temps.
- `quality_grade=research` est souvent plus strict et plus rapide.

## Tests

Lancer toute la suite :

```powershell
.\venv\Scripts\python.exe -m unittest discover Backend -p "test_*_unittest.py"
```

Lancer seulement auth/admin/historique :

```powershell
.\venv\Scripts\python.exe -m unittest Backend.test_auth_history_unittest
```

## Deploiement

Le depot doit rester identique entre le poste local et le serveur.

Sur le serveur :

- configurer `.env`
- verifier `ADMIN_EMAIL=noelline.tsafack@imbe.fr`
- verifier `APP_SECRET_KEY`
- ne pas modifier manuellement les fichiers frontend apres un `git pull`

Procedure :

```bash
git pull origin main
systemctl restart bioexplorer
systemctl reload nginx
```

Notes :

- `systemctl restart bioexplorer` est necessaire si Python, `.env` ou le backend changent.
- `systemctl reload nginx` est necessaire si la configuration Nginx change.
- Pour une modification uniquement frontend, le cache busting aide le navigateur a recuperer les nouveaux fichiers.

## Depannage

Erreur `Not Found` dans l'admin :

- Le backend lance n'est probablement pas la derniere version.
- Redemarrer le backend.
- Verifier `/docs` ou `/openapi.json`.

Compte admin impossible a connecter :

- Verifier que l'email existe dans `Backend/data/app.db`.
- Verifier que `ADMIN_EMAIL` dans `.env` correspond exactement.
- Redemarrer le backend.
- Attention : la base locale et la base serveur sont differentes.

Erreur API externe :

- Verifier la connexion internet.
- Verifier les tokens dans `.env`.
- Pour Silene Expert, verifier `GET /silene-expert/status`.

## Remarques

- Les fichiers dans `Backend/exports/` sont generes localement.
- Les CSV deja telecharges ne sont pas modifies automatiquement apres une correction du code.
- Redemarrer le backend apres chaque changement Python.
