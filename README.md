# Projet_stage - Plateforme de recherche biodiversite

Application locale pour rechercher des occurrences biologiques dans plusieurs bases, afficher un apercu harmonise, enrichir les especes avec le statut IUCN, puis exporter un CSV propre.

## Fonctionnalites

- Backend FastAPI avec API JSON et exports CSV.
- Frontend HTML/CSS/JS pour lancer les recherches et telecharger les resultats.
- Sources supportees :
  - GBIF
  - Silene Expert
  - iNaturalist
  - STELI
  - Recherche combinee GBIF + Silene Expert + iNaturalist + STELI
- Filtres :
  - pays
  - famille
  - genre
  - espece
  - date de debut et date de fin
  - type de donnee iNaturalist : research, needs_id, casual
- Export CSV avec colonnes standardisees.
- Enrichissement IUCN via l'API IUCN v4 si `IUCN_TOKEN` est configure.

## Structure

```text
Backend/
  app/
    main.py
    routes/
    services/
    utils/
  exports/
Frontend/
  search.html
  search.css
  search.js
```

## Prerequis

- Python 3.11+
- Un environnement virtuel Python
- Acces internet pour GBIF, iNaturalist, Silene Expert et IUCN

Installation des dependances :

```powershell
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt
```

## Configuration `.env`

Le backend charge automatiquement le fichier `.env` place a la racine du projet.

Exemple :

```env
IUCN_TOKEN=

# Option 1 : token/cookie Silene Expert manuel
SILENE_EXPERT_TOKEN=

# Option 2 : connexion automatique Silene Expert
SILENE_EXPERT_LOGIN=
SILENE_EXPERT_PASSWORD=
SILENE_EXPERT_APP_ID=3
```

Notes :

- `IUCN_TOKEN` est necessaire pour remplir la colonne `status` avec le statut Red List.
- `SILENE_EXPERT_TOKEN` reste supporte.
- Si `SILENE_EXPERT_LOGIN` et `SILENE_EXPERT_PASSWORD` sont renseignes, le backend peut obtenir et rafraichir le token Silene automatiquement.
- Ne jamais committer le fichier `.env`.

## Lancer le backend

Depuis la racine du repo :

```powershell
.\venv\Scripts\python.exe -m uvicorn Backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Ou simplement :

```powershell
.\start_backend.ps1
```

## Lancer le frontend

Depuis `Frontend/` :

```powershell
python -m http.server 8081 --bind 127.0.0.1
```

Puis ouvrir :

```text
http://127.0.0.1:8081/search.html
```

Ou depuis la racine du repo :

```powershell
.\start_frontend.ps1
```

## Colonnes CSV standardisees

Les exports utilisent les colonnes principales suivantes :

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

## Endpoints JSON

GBIF :

```text
GET /search?family=...&genus=...&species=...&country=...&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&limit=100&page=1
```

Silene Expert :

```text
GET /silene-expert/search?family=...&genus=...&species=...&country=...&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&limit=100&page=1
```

iNaturalist :

```text
GET /inaturalist/search?family=...&genus=...&species=...&country=...&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&quality_grade=research,needs_id,casual&limit=100&page=1
```

Combine :

```text
GET /combined/search?family=...&genus=...&species=...&country=...&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&quality_grade=research,needs_id&limit=100&page=1
```

STELI :

```text
GET /steli/search?family=...&genus=...&species=...&country=...&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&limit=100&page=1
```

## Endpoints CSV

GBIF :

```text
GET /search/csv?species=Panthera leo&limit=300&max_pages=50
```

Silene Expert :

```text
GET /silene-expert/search/csv?species=Testudo hermanni&limit=200&max_pages=50
```

iNaturalist :

```text
GET /inaturalist/search/csv?species=Testudo hermanni&quality_grade=research,needs_id&limit=200&max_pages=50
```

Combine :

```text
GET /combined/search/csv?species=Testudo hermanni&quality_grade=research,needs_id&limit=200&max_pages=50
```

STELI :

```text
GET /steli/search/csv?species=Orthetrum cancellatum&limit=200&max_pages=50
```

## Performance

Les gros exports peuvent prendre du temps car ils interrogent plusieurs API externes et enrichissent les especes avec IUCN.

Optimisations deja en place :

- GBIF, Silene Expert et iNaturalist sont lances en parallele pour la recherche combinee.
- Les statuts IUCN sont recuperes en parallele et caches.
- iNaturalist precharge les lieux/pays par groupe pour eviter un appel reseau par observation.
- Le frontend permet de regler :
  - `Resultats par page` (`limit`)
  - `Pages export max` (`max_pages`)

Conseils :

- Pour un test rapide, utiliser `limit=50` et `max_pages=5`.
- Pour un export large, augmenter progressivement `max_pages`.
- Ajouter un filtre taxonomique precis (`species` ou `genus`) reduit fortement le temps.
- Le filtre `quality_grade=research` est plus strict et souvent plus rapide que `research,needs_id,casual`.

## Sources

GBIF :

- API publique d'occurrences.
- Bonne source globale.
- Donnees deja standardisees, avec pays et dates souvent bien structures.

Silene Expert :

- Source orientee donnees expertes.
- Necessite une authentification.
- Le backend gere le token manuel ou la connexion automatique par login/password.

iNaturalist :

- Source d'observations naturalistes communautaires.
- Le champ `quality_grade` permet de choisir le niveau de validation.
- Le pays est reconstruit depuis les `place_ids` iNaturalist quand disponible.

IUCN :

- Utilise pour enrichir la colonne `status`.
- Si une espece n'est pas trouvee ou si le token manque, `status` vaut `Non renseigne`.

## Tests

Lancer les tests principaux :

```powershell
.\venv\Scripts\python.exe -m unittest Backend.test_inaturalist_service_unittest Backend.test_csv_export_routes_unittest Backend.test_combined_export_unittest Backend.test_silene_expert_service_unittest Backend.test_iucn_service_unittest
```

## Remarques

- Les fichiers dans `Backend/exports/` sont des fichiers generes localement.
- Les CSV telecharges precedemment ne sont pas modifies automatiquement apres une correction du code.
- Redemarrer le backend apres chaque changement Python.
