# Spec - Module Lead Scraper

## Vision

Module de génération et d'enrichissement de leads B2B français, exploitant les données SIRENE et enrichies via Pappers, avec synchronisation HubSpot.

## Contexte

### Code existant à migrer
Application complète dans `.specify/_to_migrate_leadscraper/` :
- 12 modules core
- 10 pages Streamlit
- Intégrations : SIRENE, Pappers, HubSpot, Google Sheets, Claude API

### Objectif
Migrer et intégrer proprement dans le portail Sales Ops unifié.

---

## Fonctionnalités à Migrer

### F2.1 : Recherche SIRENE
**Sources :** `core/sirene_client.py`, `core/sirene_client_v2.py`

- API gouvernementale gratuite (recherche-entreprises.api.gouv.fr)
- Filtres : codes APE, départements, effectifs, date création
- Rate limiting automatique (400 req/min)
- Pagination gérée

### F2.2 : Recherche en Langage Naturel
**Sources :** `core/query_parser.py`

- Intégration Claude API (Anthropic)
- Parse des requêtes type "PME dans la publicité à Paris"
- Conversion en filtres SIRENE

### F2.3 : Enrichissement Pappers
**Sources :** `core/pappers_client.py`, `core/enricher.py`

- Dirigeants (nom, prénom, fonction)
- Coordonnées (email, téléphone, site web)
- Données financières (CA, effectif)
- Gestion quotas (100 crédits/mois gratuit)

### F2.4 : Moteur Lookalike
**Sources :** `core/lookalike.py`

- Analyse profil depuis contacts existants
- Détection : secteurs, région, taille
- Élargissement : codes APE similaires, région entière

### F2.5 : Synchronisation HubSpot
**Sources :** `core/hubspot_client.py`

- Sync bidirectionnelle (HubSpot ↔ App)
- Push nouveaux leads → HubSpot
- Déduplication par SIREN
- Mapping champs personnalisés

### F2.6 : Déduplication Triple
**Sources :** `core/lead_tracker.py`, `core/enricher.py`

1. Interne (même session)
2. SQLite (historique local)
3. HubSpot (CRM)

### F2.7 : Export Multi-Canal
**Sources :** `core/exporter.py`

- CSV (téléchargement direct)
- Google Sheets (via Service Account)
- HubSpot CRM (création contacts)

### F2.8 : Scoring Leads
**Sources :** `core/scoring.py`

- Algorithme configurable
- Critères : taille, secteur, localisation
- Score 1-5 compatible Asana

---

## Pages Streamlit Existantes

| # | Page | Fonction |
|---|------|----------|
| 1 | Admin | Configuration APIs |
| 2 | Historique | Extractions passées (SQLite) |
| 3 | Mes Leads HubSpot | Contacts CRM |
| 4 | Lookalike | Recherche similaires |
| 5 | Enrichir SIRENE | Enrichissement données légales |
| 6 | Enrichir Pappers | Enrichissement complet |
| 7 | Analytics | Statistiques |
| 8 | Workflow Auto | Automatisation |
| 9 | Import CSV | Import fichiers |
| 10 | Templates Export | Modèles d'export |

---

## Architecture Cible (Post-Migration)

```
modules/
  lead_scraper/
    __init__.py

    # Clients API
    sirene_client.py          # API SIRENE v2
    pappers_client.py         # API Pappers
    hubspot_client.py         # API HubSpot

    # Logique métier
    enricher.py               # Orchestration enrichissement
    lookalike.py              # Moteur lookalike
    query_parser.py           # Parser langage naturel
    scoring.py                # Scoring leads
    lead_tracker.py           # Déduplication SQLite

    # Export
    exporter.py               # Export multi-canal

pages/
    2_Lead_Scraper.py         # Page principale (recherche)
    2a_Leads_HubSpot.py       # Mes leads HubSpot
    2b_Lookalike.py           # Recherche lookalike
    2c_Historique.py          # Historique extractions
```

---

## Dépendances Externes

| Service | Usage | Clé requise | Coût |
|---------|-------|-------------|------|
| SIRENE API | Données légales | Non | Gratuit |
| Pappers | Enrichissement | Oui | Freemium (100/mois) |
| HubSpot | CRM sync | Oui (Private App) | Gratuit |
| Anthropic | Langage naturel | Oui | Payant |
| Google Sheets | Export | Oui (Service Account) | Gratuit |

---

## Stratégie de Migration

### Phase 1 : Core Modules
1. Copier les modules `core/` vers `modules/lead_scraper/`
2. Adapter les imports
3. Unifier la config avec `.env` existant
4. Réutiliser `core/sheets_sync.py` existant pour export Sheets

### Phase 2 : Pages Streamlit
1. Convertir en pages multi-page Streamlit
2. Intégrer dans la navigation unifiée (Epic 003)
3. Simplifier (fusionner certaines pages)

### Phase 3 : Intégration
1. Connexion avec module Dashboard CFO (partage HubSpot client)
2. Push vers Asana (réutiliser `core/asana_client.py`)
3. Tests d'intégration

---

## Hors Scope (v1)

- Google Maps enrichment (phone_enricher.py)
- WebSearch enrichment (websearch_enricher.py)
- Company resolver avancé
- Auto-enricher batch
- Migration base SQLite existante
