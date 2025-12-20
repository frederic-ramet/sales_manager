# Tasks - Module Lead Scraper (Migration)

## Phase 1 : Setup & Core Modules

### T2.1.1 - Setup structure
**Durée** : 1h
**Priorité** : 🔴 Bloquant

- [ ] Créer `modules/lead_scraper/`
- [ ] Créer `modules/lead_scraper/__init__.py`
- [ ] Créer `data/` pour SQLite et exports
- [ ] Merger requirements.txt (ajouter httpx, anthropic, plotly)
- [ ] Ajouter variables .env (PAPPERS_API_KEY, HUBSPOT_API_KEY, ANTHROPIC_API_KEY)

**Fichiers sources** : `.specify/_to_migrate_leadscraper/requirements.txt`, `config.py`
**Dépend de** : Rien

---

### T2.1.2 - Migrer SIRENE Client
**Durée** : 2h
**Priorité** : 🔴 Bloquant

- [ ] Copier `sirene_client_v2.py` → `modules/lead_scraper/sirene_client.py`
- [ ] Adapter imports (config, etc.)
- [ ] Copier `data/codes_ape.json` et `data/departements.json`
- [ ] Test connexion API SIRENE
- [ ] Test recherche basique

**Fichiers sources** : `core/sirene_client_v2.py`
**Dépend de** : T2.1.1

---

### T2.1.3 - Migrer Pappers Client
**Durée** : 1h
**Priorité** : 🟠 Haute

- [ ] Copier `pappers_client.py` → `modules/lead_scraper/`
- [ ] Adapter imports
- [ ] Test connexion API Pappers
- [ ] Vérifier gestion quotas

**Fichiers sources** : `core/pappers_client.py`
**Dépend de** : T2.1.1

---

### T2.1.4 - Migrer Lead Tracker (Dédup SQLite)
**Durée** : 1h
**Priorité** : 🟠 Haute

- [ ] Copier `lead_tracker.py` → `modules/lead_scraper/`
- [ ] Adapter chemin DB (`data/leads.db`)
- [ ] Test création DB
- [ ] Test déduplication

**Fichiers sources** : `core/lead_tracker.py`
**Dépend de** : T2.1.1

---

### T2.1.5 - Migrer Enricher
**Durée** : 2h
**Priorité** : 🟠 Haute

- [ ] Copier `enricher.py` → `modules/lead_scraper/`
- [ ] Adapter imports (sirene, pappers, lead_tracker)
- [ ] Test enrichissement batch
- [ ] Test triple déduplication

**Fichiers sources** : `core/enricher.py`
**Dépend de** : T2.1.2, T2.1.3, T2.1.4

---

## Phase 2 : Modules Avancés

### T2.2.1 - Migrer HubSpot Client
**Durée** : 2h
**Priorité** : 🟠 Haute

- [ ] Copier `hubspot_client.py` → `modules/lead_scraper/`
- [ ] Adapter imports
- [ ] Test connexion API HubSpot
- [ ] Test sync contacts
- [ ] Test déduplication SIREN

**Fichiers sources** : `core/hubspot_client.py`
**Dépend de** : T2.1.1

---

### T2.2.2 - Migrer Query Parser (Claude)
**Durée** : 1h
**Priorité** : 🟡 Moyenne

- [ ] Copier `query_parser.py` → `modules/lead_scraper/`
- [ ] Adapter imports
- [ ] Test parsing requêtes

**Fichiers sources** : `core/query_parser.py`
**Dépend de** : T2.1.1

---

### T2.2.3 - Migrer Lookalike Engine
**Durée** : 2h
**Priorité** : 🟡 Moyenne

- [ ] Copier `lookalike.py` → `modules/lead_scraper/`
- [ ] Adapter imports
- [ ] Test analyse profil
- [ ] Test expansion régionale

**Fichiers sources** : `core/lookalike.py`
**Dépend de** : T2.1.2

---

### T2.2.4 - Migrer Scoring
**Durée** : 1h
**Priorité** : 🟡 Moyenne

- [ ] Copier `scoring.py` → `modules/lead_scraper/`
- [ ] Adapter pour score 1-5 (compatible Asana Confidence Score)
- [ ] Test scoring

**Fichiers sources** : `core/scoring.py`
**Dépend de** : T2.1.1

---

### T2.2.5 - Migrer Exporter
**Durée** : 2h
**Priorité** : 🟠 Haute

- [ ] Copier `exporter.py` → `modules/lead_scraper/`
- [ ] Intégrer avec `core/sheets_sync.py` existant (éviter duplication)
- [ ] Test export CSV
- [ ] Test export Google Sheets
- [ ] Test push HubSpot

**Fichiers sources** : `core/exporter.py`
**Dépend de** : T2.2.1

---

## Phase 3 : Pages Streamlit

### T2.3.1 - Page principale Lead Scraper
**Durée** : 3h
**Priorité** : 🟠 Haute

- [ ] Créer `pages/2_Lead_Scraper.py`
- [ ] Recherche en langage naturel (si Claude configuré)
- [ ] Filtres manuels (APE, département, effectif)
- [ ] Tableau résultats
- [ ] Boutons export (CSV, Sheets, HubSpot)

**Fichiers sources** : `app.py`
**Dépend de** : T2.1.5, T2.2.5

---

### T2.3.2 - Page Mes Leads HubSpot
**Durée** : 2h
**Priorité** : 🟡 Moyenne

- [ ] Créer `pages/2a_Leads_HubSpot.py`
- [ ] Sync HubSpot → local
- [ ] Tableau contacts avec filtres
- [ ] Sélection pour lookalike

**Fichiers sources** : `pages/3_📋_Mes_Leads_HubSpot.py`
**Dépend de** : T2.2.1

---

### T2.3.3 - Page Lookalike
**Durée** : 2h
**Priorité** : 🟡 Moyenne

- [ ] Créer `pages/2b_Lookalike.py`
- [ ] Affichage profil détecté
- [ ] Options élargissement
- [ ] Lancement recherche
- [ ] Export résultats

**Fichiers sources** : `pages/4_🔍_Lookalike.py`
**Dépend de** : T2.2.3

---

### T2.3.4 - Page Historique
**Durée** : 1h
**Priorité** : 🟢 Basse

- [ ] Créer `pages/2c_Historique.py`
- [ ] Liste extractions (SQLite)
- [ ] Filtres date/campagne
- [ ] Stats doublons filtrés

**Fichiers sources** : `pages/2_📊_Historique.py`
**Dépend de** : T2.1.4

---

## Phase 4 : Intégration

### T2.4.1 - Push vers Asana
**Durée** : 2h
**Priorité** : 🟠 Haute

- [ ] Créer `modules/lead_scraper/asana_push.py`
- [ ] Réutiliser `core/asana_client.py` existant
- [ ] Mapping lead → task Asana
- [ ] Vérification doublons (SIREN)
- [ ] Bouton "Push vers Asana" dans UI

**Fichiers** : `modules/lead_scraper/asana_push.py`
**Dépend de** : T2.3.1

---

### T2.4.2 - Config unifiée
**Durée** : 1h
**Priorité** : 🟡 Moyenne

- [ ] Fusionner config dans page Admin globale (Epic 003)
- [ ] Test toutes les connexions API
- [ ] Validation .env complet

**Dépend de** : T2.3.1, Epic 003

---

## Temps Total Estimé

| Phase | Tâches | Temps |
|-------|--------|-------|
| Phase 1 - Core | T2.1.1 → T2.1.5 | 7h |
| Phase 2 - Avancé | T2.2.1 → T2.2.5 | 8h |
| Phase 3 - Pages | T2.3.1 → T2.3.4 | 8h |
| Phase 4 - Intégration | T2.4.1 → T2.4.2 | 3h |
| **TOTAL** | | **26h** |

---

## Fichiers à Migrer (Checklist)

### Core Modules
- [ ] `sirene_client_v2.py` → `modules/lead_scraper/sirene_client.py`
- [ ] `pappers_client.py` → `modules/lead_scraper/pappers_client.py`
- [ ] `hubspot_client.py` → `modules/lead_scraper/hubspot_client.py`
- [ ] `enricher.py` → `modules/lead_scraper/enricher.py`
- [ ] `lead_tracker.py` → `modules/lead_scraper/lead_tracker.py`
- [ ] `lookalike.py` → `modules/lead_scraper/lookalike.py`
- [ ] `query_parser.py` → `modules/lead_scraper/query_parser.py`
- [ ] `scoring.py` → `modules/lead_scraper/scoring.py`
- [ ] `exporter.py` → `modules/lead_scraper/exporter.py`

### Data Files
- [ ] `data/codes_ape.json`
- [ ] `data/departements.json`

### Non migrés (v1)
- ❌ `auto_enricher.py` (hors scope)
- ❌ `company_resolver.py` (hors scope)
- ❌ `google_maps_client.py` (hors scope)
- ❌ `phone_enricher.py` (hors scope)
- ❌ `websearch_enricher.py` (hors scope)

---

## Notes

1. **Réutiliser le code existant** - pas de réécriture, juste adaptation imports
2. **Garder sirene_client_v2** (plus récent) plutôt que v1
3. **Exporter doit utiliser sheets_sync.py** existant pour Google Sheets
4. **HubSpot peut être partagé** avec Dashboard CFO si besoin
5. **Push Asana** réutilise `core/asana_client.py` existant
