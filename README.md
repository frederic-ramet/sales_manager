# Sales Ops Portal - Genie Factory

Portail de gestion commerciale pour l'équipe Sales & Finance.

## Lancement

```bash
# Installation
pip install -r requirements.txt

# Configuration
cp .env.example .env
# Éditer .env avec vos credentials

# Lancement
streamlit run app.py
```

L'application s'ouvre sur http://localhost:8501

---

## Modules disponibles

| Module | Description | Documentation |
|--------|-------------|---------------|
| 📊 Pipeline CFO | Synchronisation Asana → Google Sheets | [Voir doc](docs/pages/pipeline_cfo.md) |
| 🎯 Recherche Leads | Recherche et enrichissement de leads B2B | [Voir doc](docs/pages/recherche_leads.md) |
| 📜 Historique Leads | Consultation des leads exportés | [Voir doc](docs/pages/historique_leads.md) |
| 🔄 GetSales Sync | Sync leads LinkedIn → HubSpot | [Voir doc](docs/pages/getsales_sync.md) |

---

## Configuration requise

### Variables d'environnement (.env)

```bash
# === Pipeline CFO ===
ASANA_ACCESS_TOKEN=xxx          # Token API Asana
ASANA_PROJECT_GID=xxx           # ID du projet Sales Pipeline
GOOGLE_CREDENTIALS_PATH=credentials/service-account.json
GOOGLE_SPREADSHEET_URL=xxx      # URL du Google Sheet

# === Lead Scraper ===
PAPPERS_API_KEY=xxx             # API Pappers (enrichissement)
HUBSPOT_API_KEY=xxx             # API HubSpot (CRM)
ANTHROPIC_API_KEY=xxx           # Claude AI (recherche NL)

# === GetSales Sync ===
GETSALES_API_KEY=xxx            # API GetSales.io
```

### Fichiers credentials

```
credentials/
└── service-account.json    # Service Account Google (pour Sheets)
```

---

## Structure du projet

```
sales_manager/
├── app.py                      # Page d'accueil
├── pages/
│   ├── 1_📊_Pipeline_CFO.py
│   ├── 2_🎯_Recherche_Leads.py
│   ├── 3_📜_Historique_Leads.py
│   └── 4_🔄_GetSales_Sync.py
├── core/                       # Module Dashboard CFO
├── modules/
│   ├── lead_scraper/           # Module Lead Scraper
│   └── getsales/               # Module GetSales Sync
├── docs/pages/                 # Documentation utilisateur
└── .specify/                   # Spécifications techniques
```

---

## Support

- Documentation technique : `.specify/README.md`
- Specs détaillées : `.specify/specs/`

---

Genie Factory - Sales Ops Portal
