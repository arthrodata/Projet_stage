# Projet_stage — Recherche biodiversité (GBIF / Silene Expert / IUCN)

projet  :
- **Backend** FastAPI (API JSON + export CSV)
- **Frontend** HTML/JS (affiche les 10 premiers résultats, bouton de téléchargement CSV)

## Prérequis

- Python 3.11+ (recommandé)
- Un environnement virtuel (venv) activé

## Configuration (.env)

Le backend charge automatiquement le fichier `.env` à la racine du projet (voir `Backend/app/main.py`).

1) Copier `.env.example` vers `.env`
2) Renseigner les variables :

- `SILENE_EXPERT_TOKEN` : cookie `token=...` de Silene Expert (obligatoire pour la source Silene Expert)
- (Recommande) `SILENE_EXPERT_LOGIN` / `SILENE_EXPERT_PASSWORD` : identifiants Silene Expert. Si fournis, le backend regenere automatiquement le cookie `token` quand il expire.
- `IUCN_TOKEN` : token API IUCN v4 (optionnel ; le CSV n’en a pas besoin, l’API JSON peut enrichir)

## Lancer le backend

Depuis la racine du repo :

```powershell
cd Backend
python -m uvicorn Backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Endpoints principaux :
- JSON GBIF : `GET /search?family=...&genus=...&species=...&country=...`
- JSON Silene Expert (mappé) : `GET /silene-expert/search?...`
- JSON combiné : `GET /combined/search?...`
- CSV (tous les résultats) :
  - `GET /search/csv?...`
  - `GET /silene-expert/search/csv?...`
  - `GET /combined/search/csv?...`

Notes CSV :
- Les routes `*/csv` récupèrent **toutes les pages** côté backend.
- Un paramètre `max_pages` (défaut `50`) évite des exports infinis : `.../csv?...&max_pages=200`.

## Lancer le frontend

Le front est dans `Frontend/` et appelle l’API sur `http://127.0.0.1:8000`.

Option recommandée (serveur statique local) :

```powershell
cd Frontend
python -m http.server 8080
```

Ouvrir ensuite :
- `http://127.0.0.1:8080/search.html`

## Sources utilisées

- **GBIF** : recherche d’occurrences via l’API publique GBIF (occurrence search).
- **Silene Expert** : données “Expert” via l’API Silene (nécessite un token/cookie).
- **IUCN** : enrichissement du statut Red List via l’API IUCN v4 (si `IUCN_TOKEN` est défini).

## Exemple de recherche

1) Démarrer le backend + le frontend
2) Dans la page :
   - Source : `GBIF + Silene Expert`
   - Famille : `Felidae`
   - Genre : `Panthera`
   - Espèce : `Panthera leo`
   - Pays : `FR`
3) Cliquer **Rechercher** (le tableau affiche les 10 premiers)
4) Cliquer **Telecharger CSV** pour obtenir **tous** les résultats en CSV (pagination côté backend)

