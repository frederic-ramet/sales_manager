# Epic 006 : Unification du Data Model

**Version**: 1.0
**Date**: 20/12/2025
**Statut**: Approuvé
**Approche**: Option B - Refonte complète

---

## Contexte

L'application gère des leads de 3 sources différentes stockés dans des structures séparées :
- `leads_history` dans `data/leads.db` (SIRENE)
- `pending_leads` dans `data/getsales.db` (GetSales)
- Pas de stockage local pour HubSpot

Cette architecture crée des silos de données incompatibles avec une vue unifiée.

**Décision** : Refonte complète (Option B) car aucune donnée en production.

---

## Objectifs

1. **Table unique** `unified_contacts` comme source de vérité
2. **Suppression** de `leads_history` (remplacée)
3. **Intégration** des leads GetSales validés dans la table unifiée
4. **Support natif** HubSpot (import/export)
5. **Traçabilité** enrichissement Pappers
6. **Déduplication** cross-sources (email, SIREN, LinkedIn)

---

## Schéma de la table `unified_contacts`

```sql
CREATE TABLE unified_contacts (
    -- Identifiants
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,

    -- Liens sources externes
    siren TEXT,
    siret TEXT,
    getsales_uuid TEXT,
    hubspot_contact_id TEXT,
    hubspot_company_id TEXT,

    -- Métadonnées
    source TEXT NOT NULL,  -- 'sirene', 'hubspot', 'getsales'
    campaign_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- === ENTREPRISE ===
    company_name TEXT,
    ape_code TEXT,
    ape_label TEXT,
    legal_form TEXT,

    -- Adresse
    address TEXT,
    postal_code TEXT,
    city TEXT,
    region TEXT,
    country TEXT DEFAULT 'FR',

    -- Infos entreprise
    employee_range TEXT,
    revenue_range TEXT,
    website TEXT,

    -- === CONTACT ===
    firstname TEXT,
    lastname TEXT,
    email TEXT,
    phone TEXT,
    mobile TEXT,
    job_title TEXT,

    -- LinkedIn
    linkedin_url TEXT,
    linkedin_headline TEXT,

    -- === ENRICHISSEMENT ===
    enriched_at TIMESTAMP,
    enrichment_source TEXT,  -- 'pappers', 'manual', etc.

    -- === SYNC HUBSPOT ===
    synced_to_hubspot INTEGER DEFAULT 0,
    last_sync_hubspot TIMESTAMP,

    -- === PROSPECTION (GetSales) ===
    prospection_status TEXT,
    messages_sent INTEGER DEFAULT 0,
    messages_received INTEGER DEFAULT 0,
    last_interaction_at TIMESTAMP,

    -- === STATUT ===
    status TEXT DEFAULT 'active',  -- active, archived, deleted
    notes TEXT,

    -- JSON pour données brutes complètes
    raw_data TEXT,

    -- Contraintes unicité conditionnelles
    UNIQUE(siren),
    UNIQUE(getsales_uuid),
    UNIQUE(hubspot_contact_id)
);

-- Indexes
CREATE INDEX idx_uc_source ON unified_contacts(source);
CREATE INDEX idx_uc_email ON unified_contacts(email);
CREATE INDEX idx_uc_siren ON unified_contacts(siren);
CREATE INDEX idx_uc_campaign ON unified_contacts(campaign_id);
CREATE INDEX idx_uc_hubspot ON unified_contacts(hubspot_contact_id);
CREATE INDEX idx_uc_linkedin ON unified_contacts(linkedin_url);
CREATE INDEX idx_uc_status ON unified_contacts(status);
CREATE INDEX idx_uc_created ON unified_contacts(created_at);
```

---

## Modifications du code

### 1. Remplacer `LeadTracker` par `ContactManager`

**Fichier** : `modules/lead_scraper/contact_manager.py` (nouveau)

```python
class ContactManager:
    """Gestionnaire unifié des contacts multi-sources."""

    def __init__(self, db_path: str = "data/leads.db"):
        self.db_path = db_path
        self._init_db()

    # === CRUD ===
    def add_contact(self, data: Dict, source: str) -> str:
        """Ajoute un contact, retourne UUID."""

    def update_contact(self, uuid: str, data: Dict) -> bool:
        """Met à jour un contact existant."""

    def get_contact(self, uuid: str) -> Optional[Dict]:
        """Récupère un contact par UUID."""

    def delete_contact(self, uuid: str) -> bool:
        """Supprime un contact (soft delete)."""

    # === RECHERCHE ===
    def search(self,
               query: str = None,
               source: str = None,
               enriched: bool = None,
               synced: bool = None,
               limit: int = 100) -> List[Dict]:
        """Recherche avec filtres."""

    def get_stats(self) -> Dict:
        """Stats globales et par source."""

    # === DÉDUPLICATION ===
    def find_duplicate(self,
                       email: str = None,
                       siren: str = None,
                       linkedin_url: str = None) -> Optional[Dict]:
        """Trouve un doublon potentiel."""

    def merge_contacts(self, uuid_keep: str, uuid_merge: str) -> bool:
        """Fusionne deux contacts."""

    # === ENRICHISSEMENT ===
    def mark_enriched(self, uuid: str, source: str = 'pappers') -> bool:
        """Marque un contact comme enrichi."""

    def get_contacts_to_enrich(self, limit: int = 50) -> List[Dict]:
        """Liste des contacts non enrichis."""

    # === HUBSPOT ===
    def mark_synced_hubspot(self, uuid: str, hubspot_id: str) -> bool:
        """Marque un contact comme synchronisé."""

    def get_contacts_to_sync(self, limit: int = 50) -> List[Dict]:
        """Liste des contacts à pousser vers HubSpot."""

    # === IMPORT SOURCES ===
    def import_from_sirene(self, leads: List[Dict], campaign_id: str) -> int:
        """Import batch depuis extraction SIRENE."""

    def import_from_getsales(self, lead_data: Dict) -> str:
        """Import d'un lead GetSales validé."""

    def import_from_hubspot(self, contacts: List[Dict]) -> int:
        """Import batch depuis HubSpot."""

    # === EXPORT ===
    def export_csv(self, filters: Dict = None) -> bytes:
        """Export filtré en CSV."""

    def export_for_hubspot(self, uuids: List[str]) -> List[Dict]:
        """Prépare les données pour push HubSpot."""
```

### 2. Supprimer `lead_tracker.py`

L'ancien fichier sera supprimé et remplacé par `contact_manager.py`.

### 3. Adapter `getsales_sync.py`

Modifier la validation pour insérer dans `unified_contacts` :

```python
# Avant (Epic 005)
# Leads validés restent dans getsales.db

# Après (Epic 006)
def on_lead_approved(pending_lead):
    contact_manager = ContactManager()

    # Vérifier doublon
    duplicate = contact_manager.find_duplicate(
        email=pending_lead['email'],
        linkedin_url=pending_lead['linkedin_url']
    )

    if duplicate:
        # Enrichir contact existant
        contact_manager.update_contact(duplicate['uuid'], {
            'getsales_uuid': pending_lead['getsales_uuid'],
            'prospection_status': pending_lead['status'],
            # ... merge données
        })
    else:
        # Créer nouveau contact
        contact_manager.import_from_getsales(pending_lead)
```

### 4. Adapter les pages Streamlit

| Page | Modification |
|------|--------------|
| `2_Recherche_Leads.py` | `LeadTracker` → `ContactManager.import_from_sirene()` |
| `3_Base_de_Leads.py` | `LeadTracker` → `ContactManager.search()` |
| `4_GetSales_Sync.py` | Validation → `ContactManager.import_from_getsales()` |

---

## Plan d'implémentation

### Phase 1 : Nouveau modèle (T6.1)

| Tâche | Description | Temps |
|-------|-------------|-------|
| T6.1.1 | Créer `contact_manager.py` avec table `unified_contacts` | 2h |
| T6.1.2 | Implémenter méthodes CRUD de base | 1h |
| T6.1.3 | Implémenter recherche avec filtres | 1h |
| T6.1.4 | Implémenter stats par source | 30min |
| T6.1.5 | Tests unitaires ContactManager | 1h |

### Phase 2 : Migration pages (T6.2)

| Tâche | Description | Temps |
|-------|-------------|-------|
| T6.2.1 | Adapter `Recherche_Leads.py` → `import_from_sirene()` | 1h |
| T6.2.2 | Adapter `Base_de_Leads.py` → `ContactManager` | 1h |
| T6.2.3 | Supprimer `lead_tracker.py` | 15min |
| T6.2.4 | Mettre à jour imports dans `__init__.py` | 15min |

### Phase 3 : Intégration GetSales (T6.3)

| Tâche | Description | Temps |
|-------|-------------|-------|
| T6.3.1 | Modifier validation GetSales → `unified_contacts` | 1h |
| T6.3.2 | Ajouter déduplication cross-source | 1h |
| T6.3.3 | Afficher leads GetSales dans Base de Leads | 30min |

### Phase 4 : HubSpot (T6.4)

| Tâche | Description | Temps |
|-------|-------------|-------|
| T6.4.1 | Implémenter `import_from_hubspot()` | 1h |
| T6.4.2 | Implémenter `export_for_hubspot()` | 1h |
| T6.4.3 | Connecter UI Import HubSpot | 1h |
| T6.4.4 | Connecter UI Sync vers HubSpot | 1h |

### Phase 5 : Enrichissement (T6.5)

| Tâche | Description | Temps |
|-------|-------------|-------|
| T6.5.1 | UI sélection contacts à enrichir | 1h |
| T6.5.2 | Appel API Pappers batch | 1h |
| T6.5.3 | Mise à jour `enriched_at` + données | 1h |

**Total estimé** : ~16h

---

## Ordre d'implémentation recommandé

### Epic 006 AVANT Epic 005 (restant)

**Raison** : Epic 006 crée le modèle de données correct. Implémenter les features Epic 005 sur l'ancien modèle serait du travail à refaire.

```
Ordre optimal :
1. Epic 006 Phase 1-2 : Nouveau modèle + migration pages
2. Epic 006 Phase 3   : Intégration GetSales
3. Epic 006 Phase 4   : HubSpot import/export
4. Epic 005 restant   : UI enrichissement (sur nouveau modèle)
5. Epic 006 Phase 5   : Backend enrichissement Pappers
```

---

## Fichiers impactés

### À créer
- `modules/lead_scraper/contact_manager.py`

### À modifier
- `modules/lead_scraper/__init__.py`
- `pages/2_🎯_Recherche_Leads.py`
- `pages/3_📜_Base_de_Leads.py`
- `pages/4_🔄_GetSales_Sync.py`

### À supprimer
- `modules/lead_scraper/lead_tracker.py`

### Base de données
- `data/leads.db` : Nouvelle table `unified_contacts`, suppression `leads_history`
- `data/getsales.db` : Inchangé (file d'attente validation)

---

## Critères de succès

- [ ] Table `unified_contacts` créée avec tous les indexes
- [ ] `ContactManager` fonctionnel avec tests
- [ ] Extraction SIRENE insère dans `unified_contacts`
- [ ] Validation GetSales insère dans `unified_contacts`
- [ ] Page Base de Leads affiche toutes les sources
- [ ] Déduplication fonctionne (email, SIREN, LinkedIn)
- [ ] Import HubSpot fonctionnel
- [ ] Export/Sync vers HubSpot fonctionnel
- [ ] Enrichissement Pappers tracé

---

## Risques et mitigations

| Risque | Mitigation |
|--------|------------|
| Perte de données si BDD existante | Backup avant, mais pas de données prod |
| Régression features existantes | Tests manuels complets |
| Performance sur gros volumes | Indexes sur tous les champs de recherche |

---

## Documentation à mettre à jour

- [ ] `docs/pages/base_leads.md` - Refléter nouveau modèle
- [ ] `README.md` - Architecture données
- [ ] `.specify/README.md` - Ajouter Epic 006
