# Portail Sales Ops - Genie Factory

## Vue d'ensemble

Portail modulaire pour l'équipe Sales & Finance de Genie Factory.

## Modules

| # | Module | Description | Statut |
|---|--------|-------------|--------|
| 001 | **Dashboard Pipeline CFO** | Sync Asana → Google Sheets pour suivi financier | En cours |
| 002 | **Lead Scraper** | Récupération et enrichissement de leads | À faire |
| 003 | **UI Navigation** | Interface unifiée entre modules | À faire |

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
│   └── 003-ui-navigation/
│       ├── spec.md
│       └── tasks.md
└── _to_migrate/                  # Code legacy à migrer
```

---

## Roadmap

### Phase 1 : Dashboard CFO (Module 001) ✅
- [x] Client Asana
- [x] Sync Google Sheets
- [x] Interface Streamlit
- [x] Détection changements + Log
- [ ] **Sync automatique (quotidien/hebdo)**

### Phase 2 : Lead Scraper (Module 002)
- [ ] Migration code existant
- [ ] Scraping leads
- [ ] Enrichissement SIRENE/Pappers
- [ ] Push vers Asana

### Phase 3 : UI Navigation (Module 003)
- [ ] Restructuration multi-page
- [ ] Page d'accueil
- [ ] Composants communs
- [ ] Intégration modules

---

## Temps estimés

| Module | Temps |
|--------|-------|
| 001 - Dashboard CFO (Phase 2) | ~9h |
| 002 - Lead Scraper | ~22h |
| 003 - UI Navigation | ~11h |
| **TOTAL** | **~42h** |

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

## Workflow de développement

1. **Lire la spec** du module (`specs/XXX/spec.md`)
2. **Consulter les tâches** (`specs/XXX/tasks.md`)
3. **Implémenter** en suivant l'ordre des tâches
4. **Cocher** les items complétés dans tasks.md
5. **Commiter** régulièrement
