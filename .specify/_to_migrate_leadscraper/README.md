# 🎯 Lead Gen SIRENE V2

Outil avancé de génération de leads B2B français exploitant les données ouvertes SIRENE, enrichies via Pappers, avec synchronisation HubSpot et moteur de recherche lookalike.

## 📋 Fonctionnalités

### 🔍 Recherche & Extraction
- **Recherche en langage naturel** via Claude API (Anthropic)
  - *"PME dans la publicité à Paris"*
  - *"Agences web en Île-de-France +10 employés"*
- **Recherche avancée** via l'API SIRENE (gratuite, données officielles)
- **Filtres** : secteur d'activité (APE), département, effectif, date de création
- **Moteur Lookalike** : trouvez des entreprises similaires à vos meilleurs clients

### 💎 Enrichissement & Déduplication
- **Enrichissement Pappers** : dirigeants, email, téléphone, CA
- **Triple déduplication** automatique :
  1. Interne (même session de recherche)
  2. SQLite (historique des extractions)
  3. HubSpot (leads déjà dans votre CRM)

### 🔄 Synchronisation HubSpot
- **Bidirectionnelle** : HubSpot ↔ Application
- **Sync automatique** des contacts HubSpot → miroir local
- **Push automatique** nouveaux leads → HubSpot CRM
- **Déduplication SIREN** pour éviter les doublons

### 📊 Export Multi-Canal
- **CSV** : téléchargement direct
- **Google Sheets** : export automatique
- **HubSpot CRM** : intégration native

### 🖥️ Interface Multi-Pages
- **Nouvelle recherche** : extraction classique avec tous les filtres
- **Mes Leads HubSpot** : visualisation et analyse de vos contacts
- **Lookalike** : recherche de profils similaires
- **Admin** : configuration centralisée des APIs
- **Historique** : consultation des extractions passées

## 🏗️ Architecture

```
leadscraper/
├── app.py                          # Page principale (Nouvelle recherche)
├── config.py                       # Configuration centrale
├── requirements.txt                # Dépendances Python
├── .env.example                    # Template variables d'environnement
│
├── pages/                          # Pages Streamlit
│   ├── 1_⚙️_Admin.py              # Configuration APIs
│   ├── 2_📊_Historique.py         # Historique SQLite
│   ├── 3_📋_Mes_Leads_HubSpot.py  # Contacts HubSpot
│   └── 4_🔍_Lookalike.py          # Recherche similaire
│
├── core/                           # Modules métier
│   ├── sirene_client.py            # Client API SIRENE
│   ├── pappers_client.py           # Client API Pappers
│   ├── hubspot_client.py           # Client API HubSpot v3
│   ├── query_parser.py             # Parser langage naturel (Claude)
│   ├── lookalike.py                # Moteur lookalike + expansion régionale
│   ├── enricher.py                 # Orchestration enrichissement + dédup
│   ├── exporter.py                 # Export CSV + Sheets + HubSpot
│   └── lead_tracker.py             # Tracker SQLite (déduplication)
│
├── data/
│   ├── codes_ape.json              # 50 codes APE B2B
│   ├── departements.json           # 101 départements français
│   ├── exports/                    # CSV générés
│   ├── hubspot_mirror.json         # Miroir contacts HubSpot
│   └── leads.db                    # Base SQLite (historique)
│
└── credentials/
    └── gcp_service_account.json    # Credentials Google (à ajouter)
```

## 🚀 Installation

### Prérequis

- **Python 3.11+**
- **Compte [Pappers](https://www.pappers.fr)** (gratuit : 100 crédits/mois)
- **Projet Google Cloud Platform** (pour export Google Sheets)
- **Compte [Anthropic](https://console.anthropic.com)** (pour recherche en langage naturel)
- **Compte [HubSpot](https://www.hubspot.com)** (optionnel, pour CRM sync)

### 📦 Installation Rapide

```bash
git clone <repo>
cd leadscraper
./setup.sh
```

Le script `setup.sh` va :
- ✅ Vérifier les prérequis (Python 3.11+, pip)
- ✅ Créer l'environnement virtuel
- ✅ Installer les dépendances
- ✅ Configurer le fichier `.env` interactivement
- ✅ Valider la configuration
- ✅ Proposer de lancer Streamlit

### 🔑 Configuration des APIs

#### 1. API Pappers (Enrichissement)

1. Créez un compte sur [pappers.fr](https://www.pappers.fr)
2. Accédez à votre [tableau de bord API](https://www.pappers.fr/api)
3. Copiez votre clé API
4. Configurez dans **⚙️ Admin** > **Pappers API**

#### 2. Google Sheets (Export)

1. Créez un projet sur [Google Cloud Console](https://console.cloud.google.com)
2. Activez les APIs :
   - Google Sheets API
   - Google Drive API
3. Créez un Service Account :
   - IAM & Admin > Comptes de service > Créer
   - Téléchargez le JSON des credentials
4. Placez le fichier dans `credentials/gcp_service_account.json`
5. Partagez votre Google Sheet avec l'email du service account
6. Configurez dans **⚙️ Admin** > **Google Sheets**

#### 3. Anthropic API (Recherche Naturelle)

1. Créez un compte sur [console.anthropic.com](https://console.anthropic.com)
2. Générez une clé API
3. Configurez dans **⚙️ Admin** > **Anthropic API**
4. Modèle recommandé : `claude-3-5-haiku-20241022` (rapide et économique)

#### 4. HubSpot CRM (Optionnel)

##### Étape 1 : Créer une Private App

1. Accédez à [HubSpot Settings](https://app.hubspot.com/settings) → Integrations → Private Apps
2. Créez une nouvelle Private App
3. Donnez les permissions suivantes :
   - `crm.objects.contacts.read` (lecture contacts)
   - `crm.objects.contacts.write` (création contacts)
   - `crm.objects.companies.read` (lecture entreprises - pour récupérer secteur/effectif)
4. Générez et copiez le token (format: `pat-na1-...` ou `pat-eu1-...`)
5. Configurez dans **⚙️ Admin** > **HubSpot CRM**

**⚠️ Important :** Utilisez une **Private App** uniquement. Les Personal Access Keys et Developer API Keys ne fonctionnent pas avec l'API CRM.

##### Étape 2 : Créer les propriétés personnalisées (Optionnel mais recommandé)

Pour synchroniser les données SIREN (SIREN, Code APE, Effectif, CA), créez ces propriétés personnalisées :

1. Accédez à [HubSpot Settings](https://app.hubspot.com/settings) → **Properties** → **Contact Properties**
2. Créez les propriétés suivantes (type: **Single-line text**) :

| Nom interne | Label | Type | Description |
|------------|-------|------|-------------|
| `siren` | SIREN | Single-line text | Numéro SIREN de l'entreprise |
| `code_ape` | Code APE | Single-line text | Code APE / NAF de l'activité |
| `effectif` | Effectif | Single-line text | Nombre d'employés |
| `chiffre_affaires` | Chiffre d'affaires | Single-line text | CA annuel |

**Note :** Si ces propriétés n'existent pas, la synchronisation fonctionnera quand même avec les champs standard (nom, email, téléphone, entreprise, etc.). Les données SIREN seront simplement omises.

### 📝 Fichier .env

```env
# API Pappers (enrichissement)
PAPPERS_API_KEY=your_api_key_here

# Google Sheets
GOOGLE_SHEETS_CREDENTIALS_PATH=credentials/gcp_service_account.json
DEFAULT_SHEET_ID=your_sheet_id_here

# Anthropic API (recherche en langage naturel)
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_MODEL=claude-3-5-haiku-20241022

# HubSpot API (CRM et synchronisation) - OPTIONNEL
HUBSPOT_API_KEY=your_hubspot_api_key_here
```

## 🎮 Utilisation

### Lancer l'application

```bash
./run.sh
```

Ou manuellement :
```bash
source venv/bin/activate
streamlit run app.py
```

L'interface s'ouvre sur `http://localhost:8501`

### Workflows

#### 🔍 Workflow 1 : Recherche Classique

1. **Page "Nouvelle recherche"** (app.py)
2. Option A - **Recherche en langage naturel** :
   - Tapez : *"PME dans la publicité à Paris"*
   - Cliquez "Parser"
   - Ajustez les filtres si nécessaire

3. Option B - **Filtres manuels** :
   - Sélectionnez codes APE
   - Sélectionnez départements
   - Configurez effectifs, date de création

4. **Options export** :
   - ☑️ Export Google Sheets
   - ☑️ Export HubSpot (si configuré)

5. **Lancer l'extraction**
   - Déduplication automatique (SQLite + HubSpot)
   - Enrichissement Pappers
   - Export multi-canal

#### 🔄 Workflow 2 : Lookalike Search

1. **Page "📋 Mes Leads HubSpot"**
   - Cliquez "🔄 Synchroniser" (première fois)
   - Filtrez vos meilleurs clients (secteur, ville, etc.)
   - Sélectionnez-les dans le tableau
   - Cliquez "🔍 Trouver des similaires"

2. **Page "🔍 Lookalike"**
   - Consultez le profil détecté
   - Options d'élargissement :
     - ☑️ Élargir aux secteurs proches (APE similaires)
     - ☑️ Élargir à toute la région
     - ☑️ France entière
   - Lancez la recherche
   - Exportez les résultats

#### 📊 Workflow 3 : Gestion Historique

1. **Page "📊 Historique"**
   - Consultez toutes vos extractions passées
   - Filtrez par campagne, date
   - Vérifiez les doublons automatiquement filtrés

## 📊 Données Extraites

| Colonne | Source | Description |
|---------|--------|-------------|
| siren | SIRENE | Numéro unique entreprise (9 chiffres) |
| denomination | SIRENE | Nom de l'entreprise |
| code_ape | SIRENE | Code activité (ex: 62.01Z) |
| activite | SIRENE | Libellé activité |
| adresse | SIRENE | Adresse complète |
| code_postal | SIRENE | Code postal |
| ville | SIRENE | Ville |
| departement | SIRENE | Code département |
| dirigeant_nom | Pappers | Nom du dirigeant |
| dirigeant_prenom | Pappers | Prénom du dirigeant |
| dirigeant_fonction | Pappers | Fonction du dirigeant |
| email | Pappers | Email de l'entreprise |
| telephone | Pappers | Téléphone |
| site_web | Pappers | URL du site web |
| chiffre_affaires | Pappers | Chiffre d'affaires (€) |
| effectif | SIRENE | Tranche d'effectif |
| date_creation | SIRENE | Date de création |
| date_extraction | Auto | Date/heure de l'extraction |

## ⚙️ Configuration Avancée

### Limites et Rate Limiting

Dans `config.py` :

```python
# API SIRENE
SIRENE_RATE_LIMIT = 400           # Requêtes/min
SIRENE_BASE_URL = "https://recherche-entreprises.api.gouv.fr"

# API Pappers
MAX_RESULTS = 500                  # Max leads par campagne
BATCH_SIZE = 25                    # Taille batch enrichissement
REQUEST_TIMEOUT = 30               # Timeout requêtes (secondes)

# HubSpot
HUBSPOT_BASE_URL = "https://api.hubapi.com"
# Rate limiting : 100 req/10sec (géré automatiquement)
```

### HubSpot : Mapping des Champs

Dans `core/hubspot_client.py`, les champs SIRENE/Pappers sont mappés vers HubSpot :

```python
{
    "email": email,
    "firstname": dirigeant_prenom,
    "lastname": dirigeant_nom,
    "company": denomination,
    "phone": telephone,
    "website": site_web,
    "siren": siren,                    # Champ custom
    "ape_code": code_ape,               # Champ custom
    "city": ville,
    "zip": code_postal
}
```

### Lookalike : Régions Françaises

13 régions supportées dans `core/lookalike.py` :
- Île-de-France
- Auvergne-Rhône-Alpes
- Nouvelle-Aquitaine
- Occitanie
- Hauts-de-France
- Provence-Alpes-Côte d'Azur
- Grand Est
- Bretagne
- Pays de la Loire
- Normandie
- Bourgogne-Franche-Comté
- Centre-Val de Loire
- Corse

## 🔧 Utilisation Programmatique

```python
from core.sirene_client import SireneClient
from core.pappers_client import PappersClient
from core.hubspot_client import HubSpotClient
from core.enricher import Enricher
from core.exporter import Exporter
from core.lookalike import LookalikeEngine

# Recherche SIRENE
with SireneClient() as sirene:
    companies = sirene.search_all(
        codes_ape=["62.01Z", "62.02A"],
        departements=["75", "92"],
        max_results=100
    )

# Déduplication HubSpot
hubspot = HubSpotClient(api_key="...")
enricher = Enricher(None, hubspot)
companies, num_dups = enricher.deduplicate_against_hubspot(companies)

# Enrichissement Pappers
with PappersClient() as pappers:
    enricher = Enricher(pappers, hubspot)
    enriched = enricher.enrich_batch(companies)

# Export multi-canal
exporter = Exporter(
    credentials_path="credentials/gcp_service_account.json",
    hubspot_client=hubspot
)
results = exporter.export_all(
    data=enriched,
    csv_filename="mes_leads",
    sheet_id="1A2B3C4D5E6F7G8H9I0J",
    enable_hubspot=True
)

print(f"CSV: {results['csv_path']}")
print(f"Sheet: {results['sheet_url']}")
print(f"HubSpot: {results['hubspot_created']} contacts créés")
```

### Lookalike Programmatique

```python
from core.lookalike import LookalikeEngine
import json

# Charger les codes APE
with open("data/codes_ape.json") as f:
    codes_ape = json.load(f)

# Initialiser le moteur
engine = LookalikeEngine(codes_ape)

# Construire un profil depuis des contacts existants
contacts = [...]  # Vos meilleurs clients
profile = engine.build_profile(contacts)

# Obtenir un résumé
summary = engine.get_profile_summary(profile)
print(summary["interpretation"])
# "Profil détecté : 3 secteurs, région Île-de-France, 10-50 employés"

# Convertir en paramètres de recherche
search_params = engine.to_search_params(profile, {
    "extend_ape": True,       # Élargir aux codes APE similaires
    "extend_region": True,    # Élargir à toute la région
    "france_entiere": False
})

# Lancer la recherche
companies = sirene.search_all(**search_params)
```

## 🐛 Dépannage

### Erreur "PAPPERS_API_KEY non définie"

✅ Solutions :
- Vérifier que `.env` existe à la racine
- Vérifier que `PAPPERS_API_KEY=...` est renseignée
- Redémarrer Streamlit après modification

### Erreur Google Sheets "Permission denied"

✅ Solutions :
- Vérifier le chemin du fichier credentials JSON
- Partager le Google Sheet avec l'email du service account
- Activer Google Sheets API et Google Drive API dans GCP

### Erreur HubSpot "Unauthorized"

✅ Solutions :
- Vérifier que vous utilisez une **Private App** (pas API key legacy)
- Vérifier les permissions : `crm.objects.contacts.read` + `write`
- Tester la connexion dans **⚙️ Admin** > **HubSpot CRM**

### Erreur Claude API "Rate limit exceeded"

✅ Solutions :
- Réduire la fréquence des requêtes
- Utiliser Haiku (plus rapide, moins cher) au lieu de Sonnet/Opus
- Vérifier votre quota sur console.anthropic.com

### Rate limit SIRENE dépassé

Le client gère automatiquement les pauses (400 req/min). Si trop de requêtes :
- Réduire `MAX_RESULTS` dans `config.py`
- Affiner les filtres pour cibler moins d'entreprises

### Quota Pappers dépassé

- Plan gratuit : 100 requêtes/mois
- Le client continue avec les données SIRENE uniquement
- Upgrade vers un plan payant sur pappers.fr

## 📈 Limitations

| Service | Limitation | Gestion |
|---------|------------|---------|
| **API SIRENE** | 400 req/min | Automatique (rate limiting) |
| **API Pappers** | 100 crédits/mois (gratuit) | Graceful degradation |
| **API HubSpot** | 100 req/10sec | Automatique (batching) |
| **Claude API** | Selon plan Anthropic | Retry logic |
| **Extraction max** | 500 leads/campagne | Configurable (`MAX_RESULTS`) |
| **Google Sheets** | 10M cellules/sheet | N/A |

## 🔒 Sécurité

- ✅ Toutes les clés API dans `.env` (gitignored)
- ✅ Credentials Google Cloud dans `credentials/` (gitignored)
- ✅ HubSpot Private App (OAuth recommandé pour production)
- ✅ Rate limiting automatique sur toutes les APIs
- ✅ Timeouts configurables sur toutes les requêtes

## 🆕 Nouveautés V2

### Phase 1 : Core Modules
- ✅ `hubspot_client.py` : Sync bidirectionnelle HubSpot
- ✅ `lookalike.py` : Moteur de recherche lookalike
- ✅ `query_parser.py` : Recherche en langage naturel (Claude)
- ✅ `lead_tracker.py` : Déduplication SQLite

### Phase 2 : Interface Multi-Pages
- ✅ Page Admin : Configuration centralisée
- ✅ Page Historique : Consultation extractions
- ✅ Page Mes Leads HubSpot : Sync et visualisation
- ✅ Page Lookalike : Recherche profils similaires
- ✅ Déduplication triple : Interne + SQLite + HubSpot

### Architecture
- ✅ Navigation multi-pages Streamlit
- ✅ Session state pour partage données entre pages
- ✅ Export multi-canal (CSV + Sheets + HubSpot)
- ✅ Workflow complet : Sync → Analyse → Lookalike → Export

## 🤝 Contribution

Les contributions sont les bienvenues !

1. Fork le projet
2. Créer une branche feature (`git checkout -b feature/amelioration`)
3. Commit les changements (`git commit -m 'feat: Ajout fonctionnalité'`)
4. Push (`git push origin feature/amelioration`)
5. Ouvrir une Pull Request

## 📝 Licence

Ce projet est sous licence MIT.

## 🙏 Crédits

- [API SIRENE](https://recherche-entreprises.api.gouv.fr) - Données entreprises (gouvernement français)
- [Pappers API](https://www.pappers.fr/api) - Enrichissement données
- [HubSpot API](https://developers.hubspot.com) - CRM synchronisation
- [Anthropic Claude](https://www.anthropic.com) - Recherche en langage naturel
- [Streamlit](https://streamlit.io) - Framework UI
- [gspread](https://github.com/burnash/gspread) - Google Sheets Python

## 📧 Support

Pour toute question ou problème, ouvrir une issue sur GitHub.

---

**Made with ❤️ for French B2B lead generation**
