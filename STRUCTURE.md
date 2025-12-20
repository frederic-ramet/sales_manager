# 📦 Structure Complète du Projet

```
sales-ops-portal/
│
├── 📋 Documentation & Organisation
│   ├── .specify/                          # spec-kit
│   │   ├── README.md                      # Guide spec-kit
│   │   ├── memory/
│   │   │   └── constitution.md            # ⭐ Principes du projet (LIRE EN PREMIER)
│   │   └── specs/
│   │       └── 001-dashboard-pipeline-cfo/
│   │           ├── spec.md                # User Stories
│   │           ├── plan.md                # Architecture technique
│   │           ├── tasks.md               # 📝 Tâches à faire
│   │           └── research.md            # Notes API/technique
│   │
│   ├── PROJECT_README.md                  # README principal du projet
│   ├── GUIDE_SPECKIT.md                   # 📖 Comment utiliser spec-kit
│   └── specs_sales_pipeline_sync.md       # (ancien doc, peut être archivé)
│
├── ⚙️ Configuration
│   ├── .env.example                       # Template configuration
│   ├── .env                               # Vos secrets (git-ignored)
│   ├── .gitignore
│   └── requirements.txt
│
├── 💻 Code (à créer - Phase 1)
│   ├── app.py                             # Interface Streamlit
│   │
│   ├── core/                              # Logique métier
│   │   ├── __init__.py
│   │   ├── asana_client.py                # Client API Asana
│   │   ├── pipeline.py                    # Calculs financiers
│   │   └── sheets_sync.py                 # Sync Google Sheets
│   │
│   ├── tests/
│   │   ├── test_asana_client.py
│   │   ├── test_pipeline.py
│   │   └── test_sheets_sync.py
│   │
│   └── config/
│       └── google_service_account.json    # Credentials Google (git-ignored)
│
└── 📊 Data (généré automatiquement)
    └── pipeline_cache.json                # Cache Asana (optionnel)
```

## 🎯 Workflow recommandé

### Avant de coder
1. Lire `.specify/memory/constitution.md` 
2. Lire `.specify/specs/001-dashboard-pipeline-cfo/spec.md`
3. Lire `.specify/specs/001-dashboard-pipeline-cfo/plan.md`

### Pendant le dev
1. Suivre les tâches dans `.specify/specs/001-dashboard-pipeline-cfo/tasks.md`
2. Cocher les tâches au fur et à mesure
3. Mettre à jour `research.md` si besoin

### Utilisation quotidienne
```bash
# Voir les tâches à faire
cat .specify/specs/001-dashboard-pipeline-cfo/tasks.md | grep "^\- \[ \]"

# Lancer l'app
streamlit run app.py
```

## 📚 Fichiers Clés

| Fichier | Rôle | Fréquence lecture |
|---------|------|------------------|
| `.specify/memory/constitution.md` | Principes du projet | Au début, puis au besoin |
| `.specify/specs/.../spec.md` | QUOI construire | Avant chaque feature |
| `.specify/specs/.../plan.md` | COMMENT construire | Pendant l'archi |
| `.specify/specs/.../tasks.md` | Progression | Tous les jours |
| `GUIDE_SPECKIT.md` | Aide spec-kit | Si perdu |

## 🚀 Prochaines Étapes

Voir `.specify/specs/001-dashboard-pipeline-cfo/tasks.md` pour la liste complète.

Phase 1 (17h estimées) :
- T1.1 : Setup projet ✅ (FAIT - structure créée)
- T1.2 : Client Asana
- T1.3 : Pipeline & calculs
- T1.4 : Sync Sheets
- T1.5 : UI Streamlit
- T1.6 : Tests
- T1.7 : Documentation
