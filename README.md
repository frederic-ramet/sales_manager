# Dashboard Pipeline CFO

Synchronisation automatique Asana → Google Sheets pour le pilotage financier du pipeline commercial.

## Fonctionnalités

- Extraction des deals depuis un projet Asana
- Calcul des métriques financières (revenue pondéré, marge, scénarios)
- Synchronisation vers Google Sheets (4 onglets)
- Interface Streamlit pour déclencher la sync

## Installation

```bash
# Cloner le repo
git clone <repo-url>
cd sales_manager

# Créer un environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Installer les dépendances
pip install -r requirements.txt
```

## Configuration

### 1. Copier le fichier d'environnement

```bash
cp .env.example .env
```

### 2. Configuration Asana

1. Créez un **Personal Access Token** sur https://app.asana.com/0/my-apps
2. Copiez le token dans `.env` → `ASANA_ACCESS_TOKEN`
3. Récupérez le GID du projet Sales Pipeline (visible dans l'URL Asana)
4. Copiez-le dans `.env` → `ASANA_PROJECT_GID`

### 3. Configuration Google Sheets

1. Créez un **Service Account** sur Google Cloud Console
2. Activez l'API Google Sheets
3. Téléchargez le fichier JSON des credentials
4. Placez-le à la racine du projet (ex: `credentials.json`)
5. Mettez à jour `.env` → `GOOGLE_CREDENTIALS_PATH`
6. Créez un Google Sheet et partagez-le avec l'email du Service Account
7. Copiez l'URL du Sheet dans `.env` → `GOOGLE_SPREADSHEET_URL`

### 4. Custom Fields Asana

Le projet Asana doit avoir ces custom fields :

| Field | Type | Description |
|-------|------|-------------|
| Client | Text | Nom du client |
| Projet | Text | Nom du projet |
| Estimated value | Number | Budget en € |
| Marge/Bénéfice | Number | Marge en € |
| Mois de facturation prévu | Date | Date de facturation prévue |
| Confidence Score | Number (1-5) | Niveau de confiance |

## Utilisation

```bash
# Lancer l'interface Streamlit
streamlit run app.py
```

L'interface s'ouvre sur http://localhost:8501

### Workflow

1. Vérifiez la configuration dans la sidebar
2. Testez les connexions Asana et Google Sheets
3. Cliquez sur "Synchroniser maintenant"
4. Vérifiez les résultats dans le Google Sheet

## Onglets Google Sheets

| Onglet | Description |
|--------|-------------|
| Pipeline complet | Tous les deals avec métriques |
| Scénario conservateur | Deals avec confidence ≥ 4 (70%+) |
| Scénario probable | Deals avec confidence ≥ 3 (50%+) |
| Config | Métadonnées et résumé de la sync |

## Calculs

### Mapping Confidence → Probabilité

| Confidence | Probabilité |
|------------|-------------|
| 5 | 90% |
| 4 | 70% |
| 3 | 50% |
| 2 | 25% |
| 1 | 10% |

### Métriques calculées

- **Revenue pondéré** = Budget × Probabilité
- **Marge %** = Marge / Budget × 100
- **Marge pondérée** = Marge × Probabilité

## Tests

```bash
# Lancer les tests
pytest tests/ -v

# Avec couverture
pytest tests/ --cov=core
```

## Structure du projet

```
sales_manager/
├── app.py                 # Interface Streamlit
├── config.py              # Configuration centralisée
├── core/
│   ├── asana_client.py    # Client API Asana
│   ├── pipeline.py        # Logique métier et calculs
│   └── sheets_sync.py     # Sync Google Sheets
├── tests/
│   ├── test_asana_client.py
│   └── test_pipeline.py
├── .env.example
├── requirements.txt
└── README.md
```

## Troubleshooting

### Erreur "Spreadsheet not found"
- Vérifiez que le Service Account a accès au Sheet (partage avec l'email du SA)

### Erreur "Rate limit"
- L'API Asana limite à 1500 req/min. Le client gère automatiquement les retries.

### Custom fields non récupérés
- Vérifiez les noms exacts des custom fields dans Asana
- Les alias supportés sont listés dans `core/pipeline.py`

## Licence

Propriétaire - Genie Factory
