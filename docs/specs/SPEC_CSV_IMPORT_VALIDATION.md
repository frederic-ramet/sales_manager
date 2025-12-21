# Spec: Import & Validation CSV avec Review Manuelle

**Date:** 2025-12-21
**Version:** 1.0
**Statut:** DRAFT - À implémenter

---

## 🎯 Objectif

Créer une page dédiée pour l'import CSV avec workflow de validation similaire à GetSales:
- File de validation avec review manuelle
- Détection doublons HubSpot + Base locale
- Édition des données avant import
- Gestion des entreprises (companies)
- Synchronisation HubSpot optionnelle
- Contrôle qualité maximum avant import massif

---

## 📋 Contexte

Actuellement, l'import CSV est dans un onglet de "Base de Leads" avec:
- ❌ Import direct sans validation manuelle
- ❌ Pas de détection doublons HubSpot
- ❌ Pas de gestion des entreprises
- ❌ Pas de sync HubSpot automatique

**Problème:** Risque d'importer des doublons ou données de mauvaise qualité dans HubSpot.

**Solution:** Page dédiée avec workflow en 3 étapes (comme GetSales).

---

## 🏗️ Architecture

### 1. Base de données

**Nouvelle table: `csv_pending_imports`**

```sql
CREATE TABLE csv_pending_imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL UNIQUE,

    -- Métadonnées fichier
    filename TEXT NOT NULL,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_rows INTEGER NOT NULL,
    batch_id TEXT NOT NULL,  -- Identifiant unique du fichier uploadé

    -- Données du contact (JSON)
    csv_data TEXT NOT NULL,  -- JSON des données mappées
    row_number INTEGER NOT NULL,  -- Numéro de ligne dans le CSV

    -- Statut validation
    validation_status TEXT DEFAULT 'pending',  -- pending, approved, rejected, duplicate_skipped
    validated_at TIMESTAMP,
    validated_by TEXT,  -- Utilisateur (futur)

    -- Détection doublons
    hubspot_matches TEXT,  -- JSON: [{"hubspot_contact_id": ..., "confidence": ...}]
    local_matches TEXT,    -- JSON: [{"contact_uuid": ..., "confidence": ...}]
    company_matches TEXT,  -- JSON: [{"hubspot_company_id": ..., "match_type": ...}]
    local_company_matches TEXT,  -- JSON: [{"company_id": ..., "match_type": ...}]

    -- Décision utilisateur
    merge_decision TEXT,  -- JSON: choix utilisateur (create_new, merge, link, etc.)
    rejection_reason TEXT,

    -- Résultat sync
    contact_uuid TEXT,  -- UUID du contact créé/lié
    company_id INTEGER,  -- ID de l'entreprise créée/liée
    hubspot_contact_id TEXT,  -- ID HubSpot créé
    hubspot_company_id TEXT,  -- ID HubSpot company créé
    sync_status TEXT,  -- not_synced, synced, failed
    sync_error TEXT,

    -- Indexes
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE INDEX idx_csv_pending_batch ON csv_pending_imports(batch_id);
CREATE INDEX idx_csv_pending_status ON csv_pending_imports(validation_status);
CREATE INDEX idx_csv_pending_upload_date ON csv_pending_imports(upload_date DESC);
```

**Table de métadonnées: `csv_import_batches`**

```sql
CREATE TABLE csv_import_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL UNIQUE,
    filename TEXT NOT NULL,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uploaded_by TEXT,

    -- Stats
    total_rows INTEGER NOT NULL,
    total_columns INTEGER NOT NULL,
    mapping TEXT,  -- JSON du mapping utilisé

    -- Configuration import
    source_name TEXT DEFAULT 'csv_import',
    campaign_id TEXT,
    sync_to_hubspot INTEGER DEFAULT 0,  -- 0 ou 1

    -- Résultats
    status TEXT DEFAULT 'pending',  -- pending, processing, completed, failed
    pending_count INTEGER DEFAULT 0,
    approved_count INTEGER DEFAULT 0,
    rejected_count INTEGER DEFAULT 0,
    duplicate_count INTEGER DEFAULT 0,
    synced_count INTEGER DEFAULT 0,

    completed_at TIMESTAMP,

    -- Métadonnées
    encoding TEXT,
    separator TEXT,
    notes TEXT
);
```

---

## 🎨 Interface Utilisateur

### Page: `5_📤_Import_CSV.py`

Structure en 3 sections:

```
┌─────────────────────────────────────────────────────┐
│ 📤 Import & Validation CSV                          │
├─────────────────────────────────────────────────────┤
│                                                      │
│ [Tab: 📥 Upload]  [Tab: ⏳ File validation]  [Tab: 📊 Historique]  [Tab: 📖 Doc]
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

### **Section 1: Upload CSV**

#### Étape 1.1: Upload fichier
```
┌─────────────────────────────────────────┐
│ 📥 Glissez votre fichier CSV ici        │
│                                          │
│    [Drag & Drop area]                   │
│                                          │
│ Format: UTF-8, Latin-1                  │
│ Séparateur: , ; ou tab                  │
└─────────────────────────────────────────┘
```

#### Étape 1.2: Mapping colonnes
```
✅ Fichier lu: 245 lignes, 12 colonnes
📝 Encodage: UTF-8 | Séparateur: ;

┌─────────────────────────────────────────┐
│ 🔗 Mapping des colonnes                 │
├─────────────────────────────────────────┤
│ [Expander: Entreprise ▼]                │
│   🏢 Entreprise  → [Dropdown: Company]  │
│   🔢 SIREN       → [Dropdown: (ignorer)]│
│   🏭 Code APE    → [Dropdown: APE]      │
│                                          │
│ [Expander: Contact ▼]                   │
│   👤 Prénom      → [Dropdown: FirstName]│
│   👤 Nom         → [Dropdown: LastName] │
│   📧 Email       → [Dropdown: Email]    │
│   💼 Fonction    → [Dropdown: Title]    │
│   🔗 LinkedIn    → [Dropdown: LinkedIn] │
│                                          │
│ [Expander: Adresse]                     │
│ [Expander: Autre]                       │
└─────────────────────────────────────────┘
```

#### Étape 1.3: Prévisualisation
```
┌─────────────────────────────────────────┐
│ 👀 Prévisualisation (10 premières)      │
├─────────────────────────────────────────┤
│ [Dataframe table]                       │
├─────────────────────────────────────────┤
│ 📊 Statistiques                         │
│   Lignes: 245 | Colonnes mappées: 8    │
│   Non mappées: 4 | Prêt: ✅            │
└─────────────────────────────────────────┘
```

#### Étape 1.4: Options de validation
```
┌─────────────────────────────────────────┐
│ ⚙️ Options de validation                │
├─────────────────────────────────────────┤
│ ☑ Détecter doublons HubSpot             │
│ ☑ Détecter doublons base locale         │
│ ☑ Analyser et lier les entreprises      │
│                                          │
│ Source: [csv_import_dec2024___]         │
│ Campagne: [prospection_q4_2024___]      │
│                                          │
│ [🔄 Analyser et créer file validation]  │
└─────────────────────────────────────────┘
```

**Action:** Clic sur bouton → Parse CSV, détecte doublons, insère dans `csv_pending_imports`

---

### **Section 2: File de validation**

#### Stats globales
```
┌────────────────────────────────────────────────────────────┐
│ 📊 Batch: clients_pme_2024.csv (245 contacts)              │
├────────────────────────────────────────────────────────────┤
│ [⏳ En attente: 156] [✅ Validés: 78] [❌ Rejetés: 11]     │
│                                                             │
│ [⚠️ Avec doublons HubSpot: 24] [🗃️ Doublons locaux: 12]  │
└────────────────────────────────────────────────────────────┘
```

#### Filtres
```
┌─────────────────────────────────────────┐
│ Statut: [En attente ▼]                  │
│ Doublons: [Tous ▼]                      │
│ Afficher: [50 par page ▼]               │
└─────────────────────────────────────────┘
```

#### Liste des contacts à valider

**Pattern identique à GetSales:**

```
[Expander: ⏳ Jean Dupont - Acme Corp ⚠️ 2 doublon(s) ▼]

  ┌─────────────────────────────────────────────────────┐
  │ Informations CSV                  │ Métadonnées     │
  ├───────────────────────────────────┼─────────────────┤
  │ 👤 Jean Dupont                    │ 📄 Ligne: 42    │
  │ 📧 j.dupont@acme.fr              │ 📁 Fichier:     │
  │ 🏢 Acme Corp                      │    clients.csv  │
  │ 💼 Directeur Commercial           │ 📅 Upload:      │
  │ 🔗 [LinkedIn]                     │    21/12/2025   │
  │                                    │                 │
  │ [✏️ Modifier]                     │                 │
  └───────────────────────────────────┴─────────────────┘

  ┌─────────────────────────────────────────────────────┐
  │ 🗃️ Doublons Base de Leads (1)                       │
  ├─────────────────────────────────────────────────────┤
  │ 🔴 EXACT - email                                     │
  │ 👤 Jean Dupont | 🏢 Acme Corporation                │
  │ 📧 j.dupont@acme.fr | Source: hubspot               │
  │                                    [🔗 Lier contact] │
  └─────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────┐
  │ 🟠 Doublons HubSpot (1)                             │
  ├─────────────────────────────────────────────────────┤
  │ 🔴 EXACT - email                                     │
  │ 👤 Jean Dupont | 📧 j.dupont@acme.fr                │
  │ 🏢 Acme Corp | 📍 Paris                             │
  │                                          [Utiliser]  │
  └─────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────┐
  │ 🏢 Entreprise: Acme Corp                            │
  ├─────────────────────────────────────────────────────┤
  │ 🗃️ Entreprises Base de Leads (2)                    │
  │                                                      │
  │ 🟢 domain                                            │
  │ 🏢 Acme Corporation | SIREN: 123456789              │
  │ 🌐 acme.fr | 📍 Paris | 👥 5 contacts               │
  │                                          [Utiliser]  │
  │                                                      │
  │ 🟡 fuzzy_name (85%)                                 │
  │ 🏢 ACME Corp | SIREN: N/A                           │
  │ 🌐 N/A | 📍 Lyon | 👥 2 contacts                    │
  │                                          [Utiliser]  │
  │                                                      │
  │ [➕ Créer nouvelle entreprise locale]               │
  ├─────────────────────────────────────────────────────┤
  │ 🟠 Entreprises HubSpot (1)                          │
  │                                                      │
  │ 🟢 exact - domain                                   │
  │ 🏢 Acme Corp                                        │
  │ 🌐 acme.fr | 📍 Paris | 🏭 Software                 │
  │                                          [Utiliser]  │
  │                                                      │
  │ [➕ Créer nouvelle entreprise HubSpot]              │
  └─────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────┐
  │ Actions                                              │
  ├─────────────────────────────────────────────────────┤
  │ [✅ Créer nouveau] [🔀 Fusionner] [❌ Rejeter]      │
  └─────────────────────────────────────────────────────┘
```

---

### **Section 3: Historique**

```
┌──────────────────────────────────────────────────────────┐
│ 📊 Historique des imports CSV                            │
├──────────────────────────────────────────────────────────┤
│                                                           │
│ 📄 clients_pme_2024.csv - 21/12/2025 14:32              │
│    Lignes: 245 | ✅ 78 validés | ❌ 11 rejetés          │
│    ⏳ 156 en attente | 🔄 24 synced HubSpot             │
│    [📥 Voir détails] [🗑️ Supprimer]                     │
│                                                           │
│ 📄 leads_salon_nov.csv - 18/11/2025 09:15               │
│    Lignes: 89 | ✅ 89 validés | ❌ 0 rejetés             │
│    ⏳ 0 en attente | 🔄 89 synced HubSpot               │
│    [📥 Voir détails] [🗑️ Supprimer]                     │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

---

## ⚙️ Services Backend

### 1. `CSVPendingImportManager`

**Nouveau fichier:** `modules/lead_scraper/csv_pending_manager.py`

```python
class CSVPendingImportManager:
    """Gère la file de validation des imports CSV."""

    def __init__(self, db_path: str = "data/leads.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Crée les tables csv_pending_imports et csv_import_batches."""
        pass

    def create_batch(self, filename: str, total_rows: int,
                     mapping: dict, config: dict) -> str:
        """Crée un nouveau batch d'import.

        Returns:
            batch_id (str)
        """
        pass

    def add_pending_contact(self, batch_id: str, csv_data: dict,
                           row_number: int) -> str:
        """Ajoute un contact à la file de validation.

        Returns:
            pending_uuid (str)
        """
        pass

    def detect_duplicates(self, pending_uuid: str,
                         dedup_matcher, hubspot_client=None,
                         company_manager=None):
        """Détecte les doublons et met à jour les matches."""
        pass

    def get_pending_contacts(self, batch_id: str = None,
                            status: str = 'pending',
                            has_duplicates: bool = None,
                            limit: int = 50) -> List[dict]:
        """Récupère les contacts en attente de validation."""
        pass

    def get_batch_stats(self, batch_id: str) -> dict:
        """Stats d'un batch."""
        pass

    def get_all_batches(self, limit: int = 20) -> List[dict]:
        """Liste tous les batches."""
        pass

    def validate_contact(self, pending_uuid: str,
                        action: str,  # create_new, merge, reject, link
                        merge_data: dict = None) -> dict:
        """Valide un contact (similaire à GetSales)."""
        pass

    def update_contact_data(self, pending_uuid: str,
                           updated_data: dict):
        """Met à jour les données CSV d'un contact avant validation."""
        pass

    def delete_batch(self, batch_id: str):
        """Supprime un batch et tous ses contacts."""
        pass
```

---

### 2. `CSVValidationService`

**Nouveau fichier:** `modules/lead_scraper/csv_validation_service.py`

```python
class CSVValidationService:
    """Service de validation des imports CSV (similaire à GetSalesSyncService)."""

    def __init__(self, contact_manager, company_manager,
                 hubspot_client=None, pending_manager=None):
        self.contact_manager = contact_manager
        self.company_manager = company_manager
        self.hubspot_client = hubspot_client
        self.pending_manager = pending_manager or CSVPendingImportManager()

    def process_csv_file(self, file_content: bytes, filename: str,
                        mapping: dict, config: dict) -> dict:
        """
        Parse le CSV et crée la file de validation.

        Args:
            file_content: Contenu du fichier
            filename: Nom du fichier
            mapping: Mapping colonnes CSV → champs
            config: {
                'source_name': str,
                'campaign_id': str,
                'detect_hubspot_dupes': bool,
                'detect_local_dupes': bool,
                'analyze_companies': bool
            }

        Returns:
            {
                'batch_id': str,
                'total_rows': int,
                'pending_created': int,
                'errors': List[str]
            }
        """
        pass

    def validate_pending_contact(self, pending_uuid: str,
                                action: str,
                                merge_data: dict = None) -> dict:
        """
        Valide un contact de la file (create_new, merge, reject, link).

        Similaire à GetSalesSyncService.validate_lead()

        Returns:
            {
                'success': bool,
                'message': str,
                'contact_uuid': str,
                'hubspot_contact_id': str,
                'company_id': int,
                'hubspot_company_id': str
            }
        """
        pass

    def bulk_validate(self, pending_uuids: List[str],
                     action: str = 'create_new',
                     sync_to_hubspot: bool = False) -> dict:
        """Validation en masse."""
        pass
```

---

## 🔄 Workflow Détaillé

### Workflow 1: Upload et analyse

```
1. User upload CSV
   ↓
2. CSVImporter.parse()
   ↓
3. User configure mapping
   ↓
4. User configure options validation
   ↓
5. CSVValidationService.process_csv_file()
   ├─ Créer batch dans csv_import_batches
   ├─ Pour chaque ligne:
   │  ├─ Mapper les colonnes
   │  ├─ Insérer dans csv_pending_imports (status: pending)
   │  ├─ Si detect_local_dupes: find_matches() local
   │  ├─ Si detect_hubspot_dupes: search HubSpot API
   │  ├─ Si analyze_companies: find companies (local + HubSpot)
   │  └─ Sauvegarder matches dans JSON
   └─ Retourner batch_id
   ↓
6. Rediriger vers Tab "File de validation"
```

### Workflow 2: Validation manuelle

```
1. User ouvre pending contact
   ↓
2. Review données + doublons + entreprises
   ↓
3. [Option A] User clique "✏️ Modifier"
   ├─ Édite firstname, lastname, company, etc.
   ├─ CSVPendingImportManager.update_contact_data()
   └─ Rafraîchir
   ↓
4. [Option B] User sélectionne choix entreprise
   ├─ Entreprise locale existante
   ├─ OU entreprise HubSpot existante
   ├─ OU créer nouvelle (locale ou HubSpot)
   └─ Stocker dans session_state
   ↓
5. User clique action:
   ├─ [✅ Créer nouveau]
   │  ├─ CSVValidationService.validate_pending_contact(action='create_new')
   │  ├─ Créer/lier company selon choix
   │  ├─ Créer contact dans contacts table
   │  ├─ Si sync_to_hubspot: créer dans HubSpot
   │  └─ Update status = 'approved'
   │
   ├─ [🔀 Fusionner] (si doublons HubSpot)
   │  ├─ User choisit champs à garder (GetSales vs HubSpot)
   │  ├─ CSVValidationService.validate_pending_contact(action='merge')
   │  ├─ Update contact HubSpot
   │  ├─ Update contact local
   │  └─ Update status = 'approved'
   │
   ├─ [🔗 Lier] (si doublons locaux)
   │  ├─ CSVValidationService.validate_pending_contact(action='link')
   │  ├─ Update contact existant avec données CSV
   │  └─ Update status = 'approved'
   │
   └─ [❌ Rejeter]
      ├─ CSVPendingImportManager.validate_contact(action='reject')
      └─ Update status = 'rejected'
```

### Workflow 3: Validation en masse

```
1. User filtre contacts (ex: "Sans doublons")
   ↓
2. User clique "✅ Valider tous sans doublons (156)"
   ↓
3. CSVValidationService.bulk_validate(
      pending_uuids=[...],
      action='create_new',
      sync_to_hubspot=True
   )
   ├─ Progress bar
   ├─ Pour chaque contact:
   │  ├─ Créer company si besoin
   │  ├─ Créer contact
   │  ├─ Sync HubSpot si demandé
   │  └─ Update status
   └─ Retourner stats
   ↓
4. Afficher résultats:
   ✅ 156 contacts créés
   🔄 142 synchronisés HubSpot
   ❌ 14 erreurs
```

---

## 📊 Gestion des Entreprises

### Logic similaire à GetSales

Pour chaque contact CSV avec `company_name`:

1. **Rechercher entreprises locales:**
   - Par website/domain (si disponible dans CSV)
   - Par nom fuzzy (similarity > 0.8)
   - Stocker dans `local_company_matches` (JSON)

2. **Rechercher entreprises HubSpot:**
   - API search par domain
   - API search par nom
   - Stocker dans `company_matches` (JSON)

3. **UI - Choix utilisateur:**
   - Utiliser entreprise locale existante → `company_id`
   - OU utiliser entreprise HubSpot existante → `hubspot_company_id`
   - OU créer nouvelle locale + sync HubSpot
   - OU créer nouvelle HubSpot uniquement

4. **Lors de la validation:**
   ```python
   if merge_data.get('use_existing_local_company_id'):
       company_id = merge_data['use_existing_local_company_id']
   elif merge_data.get('create_new_local_company'):
       company_id = company_manager.add_company({...})

   if sync_to_hubspot and merge_data.get('use_existing_company_id'):
       hubspot_company_id = merge_data['use_existing_company_id']
   elif sync_to_hubspot and merge_data.get('create_new_company'):
       hubspot_company_id = hubspot_client.create_company({...})
   ```

---

## 🔄 Synchronisation HubSpot

### Options

1. **Pas de sync** (défaut)
   - Import uniquement dans base locale
   - `sync_status = 'not_synced'`

2. **Sync après validation manuelle**
   - Checkbox par contact
   - Sync lors du clic "✅ Créer nouveau"

3. **Sync en masse**
   - Bouton "🔄 Synchroniser tous les validés vers HubSpot"
   - Bulk operation avec progress bar

### Propriétés HubSpot

Mapper les champs CSV → propriétés HubSpot:

```python
hubspot_properties = {
    'firstname': csv_data.get('firstname'),
    'lastname': csv_data.get('lastname'),
    'email': csv_data.get('email'),
    'phone': csv_data.get('phone'),
    'jobtitle': csv_data.get('job_title'),
    'hs_linkedin_url': csv_data.get('linkedin_url'),

    # Source tracking
    'hs_analytics_source': 'OTHER_CAMPAIGNS',
    'hs_analytics_source_data_1': csv_data.get('source_name', 'csv_import'),
    'hs_analytics_source_data_2': csv_data.get('campaign_id'),
    'import_source': 'csv_import',
    'csv_batch_id': batch_id,
    'csv_filename': filename,
    'csv_row_number': row_number
}
```

---

## 🛡️ Validation et Qualité

### Validations avant mise en file

1. **Champs requis:**
   - Au moins `email` OU (`firstname` + `lastname` + `company_name`)
   - Sinon: skip avec message d'erreur

2. **Format email:**
   - Regex validation
   - Lowercase automatique

3. **Format téléphone:**
   - Nettoyer (garder +, chiffres, espaces)
   - Valider format FR si détecté

4. **Entreprise:**
   - Si `siren`: valider 9 chiffres
   - Si `website`: valider format URL

### Qualité des doublons

**Confidence levels:**
- `EXACT`: Email identique OU (LinkedIn identique)
- `HIGH`: Firstname + Lastname + Company similaires (>90%)
- `MEDIUM`: Email domain identique + nom similaire
- `LOW`: Nom similaire uniquement

**Actions selon confidence:**
- EXACT/HIGH → Afficher en priorité, suggérer fusion
- MEDIUM → Afficher mais permettre création
- LOW → Ne pas afficher (bruit)

---

## 📁 Structure Fichiers

### Nouveaux fichiers

```
modules/lead_scraper/
  ├── csv_pending_manager.py          # NEW - Gestion file validation
  └── csv_validation_service.py       # NEW - Service de validation

pages/
  └── 5_📤_Import_CSV.py               # NEW - Page dédiée

docs/
  └── pages/
      └── csv_import.md                # NEW - Documentation utilisateur
```

### Fichiers modifiés

```
modules/lead_scraper/
  ├── __init__.py                      # Ajouter exports
  └── csv_importer.py                  # Garder pour backward compat

pages/
  └── 3_📜_Base_de_Leads.py            # Retirer l'onglet CSV import
```

---

## 🔧 Migration

### Migration des données existantes

**Pas de migration nécessaire** - nouveau système parallèle.

**Ancien CSV import (dans Base de Leads):**
- Garder disponible pour imports rapides sans validation
- Ajouter warning: "⚠️ Import direct sans validation. Pour validation manuelle, utilisez la page Import CSV."

**Nouveau CSV import (page dédiée):**
- Workflow complet avec validation
- Recommandé pour imports importants

---

## 📈 Améliorations Futures

### Phase 2

1. **Validation automatique intelligente**
   - Auto-approve si aucun doublon et qualité données > seuil
   - Auto-reject si doublons EXACT

2. **Templates de mapping**
   - Sauvegarder mapping fréquents
   - "Mapping GetSales export", "Mapping LinkedIn Sales Navigator", etc.

3. **Enrichissement automatique**
   - Si SIREN dans CSV → enrichir avec Pappers
   - Si email → enrichir LinkedIn via API

4. **Webhooks**
   - Notifier quand import est prêt à valider
   - Notifier quand batch est complété

### Phase 3

1. **Scheduling d'imports**
   - Import récurrent (ex: tous les lundis)
   - SFTP/Google Drive sync

2. **Collaboration**
   - Assignation de batches à des utilisateurs
   - Commentaires sur contacts

3. **ML-powered matching**
   - Améliorer détection doublons avec ML
   - Prédire meilleure action (create vs merge)

---

## ✅ Checklist Implémentation

### Backend
- [ ] Créer table `csv_pending_imports`
- [ ] Créer table `csv_import_batches`
- [ ] Implémenter `CSVPendingImportManager`
- [ ] Implémenter `CSVValidationService`
- [ ] Tests unitaires services
- [ ] Migration base de données

### Frontend
- [ ] Créer page `5_📤_Import_CSV.py`
- [ ] Tab 1: Upload + Mapping
- [ ] Tab 2: File de validation
  - [ ] Stats batch
  - [ ] Liste contacts pending
  - [ ] Détection doublons (local + HubSpot)
  - [ ] Gestion entreprises
  - [ ] Actions (create/merge/reject/link)
  - [ ] Formulaire merge
  - [ ] Édition données
- [ ] Tab 3: Historique
- [ ] Tab 4: Documentation
- [ ] Validation en masse
- [ ] Progress bars

### Intégrations
- [ ] Intégration DeduplicationMatcher
- [ ] Intégration CompanyManager
- [ ] Intégration HubSpotClient
- [ ] Intégration ContactManager

### Documentation
- [ ] `docs/pages/csv_import.md`
- [ ] `docs/specs/SPEC_CSV_IMPORT_VALIDATION.md`
- [ ] README update

### Tests
- [ ] Tests end-to-end upload → validation → sync
- [ ] Tests détection doublons
- [ ] Tests gestion entreprises
- [ ] Tests validation en masse

---

## 🎯 Success Metrics

**Qualité des données:**
- ✅ 0% doublons créés dans HubSpot
- ✅ 100% des contacts ont une entreprise liée
- ✅ > 95% des données validées manuellement avant import massif

**Productivité:**
- ✅ Import CSV 245 contacts: < 30 min (vs 2h manuel)
- ✅ Détection doublons automatique: 100% (vs 60% manuel)

**Adoption:**
- ✅ > 80% des imports CSV passent par nouvelle page
- ✅ < 5% des contacts rejetés après validation

---

**Version:** 1.0
**Date:** 2025-12-21
**Statut:** READY - Prêt pour implémentation
