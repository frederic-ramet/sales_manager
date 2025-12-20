# 📊 Portail Sales Ops - Genie Factory

Portail modulaire pour l'équipe Sales & Finance.

## Module Actuel : Dashboard Pipeline CFO

Synchronisation automatique Asana → Google Sheets pour le pilotage financier.

### Fonctionnalités
- ✅ Extraction des deals depuis Asana
- ✅ Calculs financiers (revenue pondéré, scénarios trésorerie)
- ✅ Synchronisation vers Google Sheets (4 onglets)
- ✅ Interface Streamlit pour admin

## Quick Start

### 1. Installation
```bash
pip install -r requirements.txt
```

### 2. Configuration
```bash
cp .env.example .env
# Éditer .env avec vos credentials
```

### 3. Setup Asana
1. Aller dans Asana → Settings → Apps → Personal Access Tokens
2. Créer un token et le copier dans `.env`
3. Récupérer le GID du projet "Sales pipeline" (dans l'URL)
4. Créer les custom fields requis (voir [Custom Fields](#custom-fields-requis))

### 4. Setup Google Sheets
1. Créer un Service Account dans Google Cloud Console
2. Télécharger le JSON credentials
3. Partager votre Google Sheet avec l'email du service account
4. Copier l'URL du Sheet dans `.env`

### 5. Lancement
```bash
streamlit run app.py
```

## Custom Fields Requis dans Asana

Créer ces champs dans le projet "Sales pipeline" :

| Nom | Type | Description |
|-----|------|-------------|
| Client | Text | Nom du client/prospect |
| Projet | Text | Nom du projet |
| Marge/Bénéfice | Number | Marge en € |
| Mois de facturation prévu | Date | Mois de facturation |

Le champ "Estimated value" (Budget) existe déjà.  
Le champ "Confidence Score" (1-5) existe déjà.

## Structure du Projet

```
.
├── app.py                  # Interface Streamlit
├── core/                   # Logique métier
│   ├── asana_client.py
│   ├── pipeline.py
│   └── sheets_sync.py
├── tests/                  # Tests unitaires
└── .specify/               # Documentation spec-kit
    ├── memory/
    │   └── constitution.md
    └── specs/
        └── 001-dashboard-pipeline-cfo/
```

## Documentation

Voir `.specify/README.md` pour comprendre l'organisation du projet avec spec-kit.

Les specs complètes sont dans `.specify/specs/001-dashboard-pipeline-cfo/`:
- `spec.md` : User Stories
- `plan.md` : Architecture technique
- `tasks.md` : Découpage en tâches
- `research.md` : Notes techniques

## Modules Futurs

- Module 2 : Prospection & Enrichissement
- Module 3 : Sync HubSpot

## Support

Pour toute question, consulter :
1. `.specify/memory/constitution.md` (principes du projet)
2. Les specs dans `.specify/specs/`
3. `GUIDE_SPECKIT.md` (comment utiliser spec-kit)

## Licence

Propriétaire - Genie Factory
