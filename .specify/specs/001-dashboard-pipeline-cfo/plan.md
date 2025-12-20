# Plan d'Implémentation - Module Dashboard Pipeline CFO

## Architecture Cible (Phase 1)

```
sales-ops-portal/
├── app.py                      # Point d'entrée Streamlit (page admin/config)
├── config.py                   # Configuration centralisée
├── .env                        # Secrets (gitignored)
│
├── core/                       # Logique métier
│   ├── __init__.py
│   ├── asana_client.py         # API Asana
│   ├── pipeline.py             # Logique pipeline & calculs financiers
│   └── sheets_sync.py          # Sync Google Sheets
│
├── data/
│   └── pipeline_cache.json     # Cache Asana (optionnel)
│
├── tests/
│   ├── test_asana_client.py
│   ├── test_pipeline.py
│   └── test_sheets_sync.py
│
└── .specify/                   # Specs projet (spec-kit)
    ├── memory/
    │   └── constitution.md
    └── specs/
        └── 001-dashboard-pipeline-cfo/
            ├── spec.md
            ├── plan.md
            ├── tasks.md
            └── research.md
```

---

## Stack Technique

| Composant | Technologie | Justification |
|-----------|-------------|---------------|
| Frontend | Streamlit 1.28+ | Simple, rapide, Python-first |
| Backend | Python 3.11+ | Déjà utilisé |
| Cache | JSON files | Pas besoin de base de données pour Phase 1 |
| APIs | requests + asana SDK | Client officiel Asana + wrapper custom |

---

## Composants à Développer

### 1. `core/asana_client.py`

```python
from asana import Client
from typing import List, Dict

class AsanaClient:
    """Client API Asana pour récupérer les deals du pipeline"""
    
    def __init__(self, access_token: str):
        self.client = Client.access_token(access_token)
        
    def get_project_tasks(self, project_gid: str) -> List[Dict]:
        """
        Récupère toutes les tasks d'un projet avec leurs custom fields
        
        Returns:
            List de dicts avec : gid, name, custom_fields, assignee, 
            due_on, memberships (section), etc.
        """
        tasks = self.client.tasks.find_by_project(
            project_gid,
            opt_fields=[
                'name',
                'custom_fields',
                'custom_fields.display_value',
                'custom_fields.number_value',
                'assignee.name',
                'due_on',
                'memberships.section.name'
            ]
        )
        return list(tasks)
    
    def get_custom_field_gids(self, project_gid: str) -> Dict[str, str]:
        """
        Récupère les GIDs des custom fields du projet
        Utile pour validation et mapping
        """
        project = self.client.projects.find_by_id(
            project_gid,
            opt_fields=['custom_field_settings.custom_field']
        )
        # Parser et retourner mapping {nom: gid}
```

### 2. `core/pipeline.py`

```python
import pandas as pd
from typing import Dict, List
from datetime import datetime

class PipelineCalculator:
    """Calculs financiers sur le pipeline"""
    
    # Mapping Confidence Score → Probabilité
    CONFIDENCE_TO_PROBA = {
        5: 90,
        4: 70,
        3: 50,
        2: 25,
        1: 10,
    }
    
    def __init__(self, asana_tasks: List[Dict]):
        self.tasks = asana_tasks
        self.df = None
        
    def parse_tasks_to_dataframe(self) -> pd.DataFrame:
        """
        Transforme les tasks Asana en DataFrame standardisé
        """
        rows = []
        for task in self.tasks:
            custom_fields = self._parse_custom_fields(task['custom_fields'])
            
            rows.append({
                'asana_gid': task['gid'],
                'titre': task['name'],
                'client': custom_fields.get('Client'),
                'projet': custom_fields.get('Projet'),
                'budget': custom_fields.get('Estimated value'),  # ou 'Budget'
                'marge': custom_fields.get('Marge/Bénéfice'),
                'mois_facturation': custom_fields.get('Mois de facturation prévu'),
                'confidence_score': custom_fields.get('Confidence Score'),
                'section': self._get_section(task),
                'owner': task.get('assignee', {}).get('name'),
                'due_date': task.get('due_on'),
                # Plus de champs selon besoins
            })
            
        self.df = pd.DataFrame(rows)
        return self.df
    
    def calculate_metrics(self) -> pd.DataFrame:
        """
        Ajoute toutes les métriques calculées au DataFrame
        """
        df = self.df.copy()
        
        # Probabilité
        df['probabilite_pct'] = df['confidence_score'].map(self.CONFIDENCE_TO_PROBA)
        
        # Revenue pondéré
        df['revenue_pondere'] = (df['budget'] * df['probabilite_pct'] / 100).fillna(0)
        
        # Marge %
        df['marge_pct'] = ((df['marge'] / df['budget']) * 100).fillna(0)
        
        # Dimensions temporelles
        df['mois_facturation'] = pd.to_datetime(df['mois_facturation'], errors='coerce')
        df['annee'] = df['mois_facturation'].dt.year
        df['trimestre'] = 'Q' + df['mois_facturation'].dt.quarter.astype(str)
        df['mois'] = df['mois_facturation'].dt.strftime('%B %Y')
        
        # Scénarios
        df['scenario_conservateur'] = df['confidence_score'] >= 4
        df['scenario_probable'] = df['confidence_score'] >= 3
        
        self.df = df
        return df
    
    def _parse_custom_fields(self, custom_fields: List[Dict]) -> Dict:
        """Parse custom fields Asana en dict {nom: valeur}"""
        result = {}
        for cf in custom_fields:
            name = cf.get('name')
            # Prendre display_value ou number_value selon type
            value = cf.get('display_value') or cf.get('number_value')
            result[name] = value
        return result
    
    def _get_section(self, task: Dict) -> str:
        """Extrait le nom de la section (colonne board Kanban)"""
        memberships = task.get('memberships', [])
        if memberships:
            return memberships[0].get('section', {}).get('name')
        return None
```

### 3. `core/sheets_sync.py`

```python
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

class GoogleSheetsSync:
    """Synchronisation Pipeline → Google Sheets"""
    
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    def __init__(self, credentials_path: str, spreadsheet_url: str):
        creds = Credentials.from_service_account_file(
            credentials_path, 
            scopes=self.SCOPES
        )
        self.gc = gspread.authorize(creds)
        self.spreadsheet = self.gc.open_by_url(spreadsheet_url)
        
    def sync_pipeline(self, df: pd.DataFrame):
        """
        Sync complet du pipeline vers Google Sheets
        Crée/update les onglets : Pipeline complet, Scénarios, Config
        """
        # Ajouter timestamp
        df['derniere_maj'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Onglet 1 : Pipeline complet
        self._write_to_sheet(df, "Pipeline complet")
        
        # Onglet 2 : Scénario conservateur
        df_conservateur = df[df['scenario_conservateur'] == True]
        self._write_to_sheet(df_conservateur, "Scénario conservateur")
        
        # Onglet 3 : Scénario probable
        df_probable = df[df['scenario_probable'] == True]
        self._write_to_sheet(df_probable, "Scénario probable")
        
        # Onglet 4 : Config/Logs
        config_df = pd.DataFrame([{
            'derniere_sync': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'nb_deals': len(df),
            'statut': 'SUCCESS'
        }])
        self._write_to_sheet(config_df, "Config")
        
    def _write_to_sheet(self, df: pd.DataFrame, sheet_name: str):
        """Écrit un DataFrame dans un onglet (replace mode)"""
        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            worksheet = self.spreadsheet.add_worksheet(
                title=sheet_name, 
                rows=1000, 
                cols=30
            )
        
        # Clear et write
        worksheet.clear()
        data = [df.columns.tolist()] + df.fillna('').values.tolist()
        worksheet.update('A1', data)
```

### 4. `app.py` (Interface Streamlit)

```python
import streamlit as st
from core.asana_client import AsanaClient
from core.pipeline import PipelineCalculator
from core.sheets_sync import GoogleSheetsSync
import os
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Dashboard Pipeline CFO",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Dashboard Pipeline CFO")

# Sidebar - Configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    asana_token = st.text_input(
        "Asana PAT", 
        value=os.getenv('ASANA_ACCESS_TOKEN', ''),
        type="password"
    )
    asana_project_gid = st.text_input(
        "Project GID",
        value=os.getenv('ASANA_PROJECT_GID', '')
    )
    
    gsheet_url = st.text_input(
        "Google Sheet URL",
        value=os.getenv('GSHEET_URL', '')
    )
    
    st.markdown("---")
    
    # Test connexions
    if st.button("🔗 Test Asana"):
        try:
            client = AsanaClient(asana_token)
            st.success("✅ Connexion Asana OK")
        except Exception as e:
            st.error(f"❌ Erreur : {e}")

# Main - Sync
st.header("Synchronisation")

if st.button("🔄 Sync maintenant", type="primary"):
    with st.spinner("Récupération des deals Asana..."):
        try:
            # 1. Extract
            asana_client = AsanaClient(asana_token)
            tasks = asana_client.get_project_tasks(asana_project_gid)
            
            # 2. Transform
            calculator = PipelineCalculator(tasks)
            df = calculator.parse_tasks_to_dataframe()
            df = calculator.calculate_metrics()
            
            st.success(f"✅ {len(df)} deals récupérés")
            
            # 3. Load
            syncer = GoogleSheetsSync(
                credentials_path=os.getenv('GOOGLE_CREDS_PATH'),
                spreadsheet_url=gsheet_url
            )
            syncer.sync_pipeline(df)
            
            st.success("✅ Synchronisation terminée !")
            
            # Preview
            st.dataframe(df)
            
        except Exception as e:
            st.error(f"❌ Erreur : {e}")
```

---

## Configuration Requise

### `.env`
```bash
ASANA_ACCESS_TOKEN=your_pat_here
ASANA_PROJECT_GID=1234567890123456
GSHEET_URL=https://docs.google.com/spreadsheets/d/XXX
GOOGLE_CREDS_PATH=./config/google_service_account.json
```

### Custom Fields Asana
À créer manuellement dans le projet avant dev :
- Client (Text)
- Projet (Text)
- Marge/Bénéfice (Number)
- Mois de facturation prévu (Date)

---

## Dépendances Python

```txt
streamlit>=1.28.0
asana>=5.0.0
gspread>=5.12.0
google-auth>=2.23.0
pandas>=2.1.0
python-dotenv>=1.0.0
```

---

## Roadmap

### Phase 1 (Actuel) - MVP Dashboard CFO
- ✅ Extraction Asana
- ✅ Calculs financiers
- ✅ Sync Google Sheets
- ✅ Interface admin Streamlit

### Phase 2 - Modules additionnels
- Module Prospection & Enrichissement
- Module Sync HubSpot

### Phase 3 - Améliorations
- Webhooks Asana (sync temps réel)
- Historisation des syncs
- Alertes automatiques
