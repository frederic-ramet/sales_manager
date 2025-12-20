# Portail Sales Ops - Genie Factory

## Vue d'ensemble

Portail modulaire pour l'équipe Sales & Finance de Genie Factory.

## Modules

| # | Module | Description | Statut |
|---|--------|-------------|--------|
| 001 | **Dashboard Pipeline CFO** | Sync Asana → Google Sheets + scheduler | ✅ Done |
| 002 | **Lead Scraper** | Extraction SIRENE/Pappers + enrichissement | ✅ Done |
| 003 | **UI Navigation** | Interface multi-page Streamlit | ✅ Done |
| 004 | **GetSales Sync** | Sync leads LinkedIn → HubSpot | ✅ Done |
| 005 | **Leads Hub** | Base centralisée + enrichissement bidirectionnel | ⏸️ Suspendu |
| 006 | **Unified Data Model** | Refonte modèle données unifié | 🆕 Prioritaire |

---

## Structure

```
.specify/
├── memory/
│   └── constitution.md           # Principes directeurs
├── specs/
│   ├── 001-dashboard-pipeline-cfo/
│   │   ├── spec.md               # User Stories
│   │   ├── plan.md               # Architecture
│   │   ├── tasks.md              # Tâches détaillées
│   │   └── research.md           # Recherche API
│   ├── 002-lead-scraper/
│   │   ├── spec.md
│   │   └── tasks.md
│   ├── 003-ui-navigation/
│   │   ├── spec.md
│   │   └── tasks.md
│   ├── 004-getsales-sync/
│   │   ├── spec.md
│   │   └── tasks.md
│   ├── 005-leads-hub/
│   │   └── spec.md
│   └── 006-unified-data-model/
│       └── spec.md
└── _to_migrate_leadscraper/      # Code legacy (migré)
```

---

## Roadmap

### Phase 1 : Dashboard CFO (Module 001) ✅
- [x] Client Asana SDK v5
- [x] Sync Google Sheets
- [x] Interface Streamlit
- [x] Détection changements (Modified timestamp)
- [x] Sync automatique (APScheduler)

### Phase 2 : Lead Scraper (Module 002) ✅
- [x] Migration modules core (9 modules)
- [x] Client SIRENE (gratuit)
- [x] Client Pappers (enrichissement)
- [x] Client HubSpot (sync CRM)
- [x] Déduplication SQLite
- [x] Query Parser (Claude API)
- [x] Pages Streamlit (Recherche + Historique)

### Phase 3 : UI Navigation (Module 003) ✅
- [x] Restructuration multi-page
- [x] Page d'accueil avec statuts
- [x] Navigation emoji-numérotée

### Phase 4 : GetSales Sync (Module 004) ✅
- [x] Client API GetSales (rate limiting, retry)
- [x] Modèles SQLite (PendingLead, SyncLog, LeadInteraction)
- [x] Déduplication LinkedIn/Email
- [x] Validation manuelle leads (create/merge/reject)
- [x] Formulaire merge champ par champ
- [x] Sync interactions → base locale

### Phase 5 : Leads Hub (Module 005) ⏸️ Suspendu
> Suspendu en faveur de Epic 006 qui refonde le modèle de données.

- [x] Migration BDD : colonnes source, hubspot_id, enriched_at (partiel)
- [x] Page Base de Leads (vue unifiée multi-sources) - UI prête
- [x] Min leads = 1
- [ ] ~~Import HubSpot → base locale~~ → Epic 006
- [ ] ~~Enrichissement leads existants~~ → Epic 006
- [ ] ~~Push enrichis vers HubSpot~~ → Epic 006
- [ ] ~~Intégration GetSales → Base de Leads~~ → Epic 006

### Phase 6 : Unified Data Model (Module 006) 🆕 Prioritaire
> Refonte complète du modèle de données (Option B - clean slate)

- [ ] Créer `ContactManager` avec table `unified_contacts`
- [ ] Supprimer ancien `LeadTracker` / `leads_history`
- [ ] Adapter page Recherche Leads → `import_from_sirene()`
- [ ] Adapter page Base de Leads → `ContactManager`
- [ ] Intégration GetSales validés → `unified_contacts`
- [ ] Import HubSpot → `unified_contacts`
- [ ] Export/Sync vers HubSpot
- [ ] Enrichissement Pappers avec traçabilité
- [ ] Déduplication cross-sources (email, SIREN, LinkedIn)

---

## Temps estimés

| Module | Estimé | Réel |
|--------|--------|------|
| 001 - Dashboard CFO | ~9h | ✅ |
| 002 - Lead Scraper | ~22h | ✅ |
| 003 - UI Navigation | ~11h | ✅ |
| 004 - GetSales Sync | ~9 jours | ✅ |
| 005 - Leads Hub | ~14h | ⏸️ Partiel |
| 006 - Unified Data Model | ~16h | - |

---

## Quick Start

```bash
# Installation
pip install -r requirements.txt

# Configuration
cp .env.example .env
# Éditer .env avec vos credentials

# Lancement
streamlit run app.py
```

---

## Variables d'environnement

```bash
# Dashboard CFO (001)
ASANA_ACCESS_TOKEN=xxx
ASANA_PROJECT_GID=xxx
GOOGLE_CREDENTIALS_PATH=credentials/service-account.json
GOOGLE_SPREADSHEET_URL=xxx

# Lead Scraper (002)
PAPPERS_API_KEY=xxx
HUBSPOT_API_KEY=xxx
ANTHROPIC_API_KEY=xxx

# GetSales Sync (004)
GETSALES_API_KEY=xxx
```

---

## Workflow de développement

1. **Lire la spec** du module (`specs/XXX/spec.md`)
2. **Consulter les tâches** (`specs/XXX/tasks.md`)
3. **Implémenter** en suivant l'ordre des tâches
4. **Cocher** les items complétés dans tasks.md
5. **Commiter** régulièrement
