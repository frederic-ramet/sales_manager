# SPEC: Synchronisation Bidirectionnelle HubSpot

**Version:** 1.0
**Date:** 2025-12-22
**Statut:** Implemented
**Auteur:** Claude

---

## 1. Contexte et Probleme

### 1.1 Architecture actuelle

L'application utilise un schema separe :
- Table `contacts` : donnees personnelles (firstname, lastname, email, phone, job_title)
- Table `companies` : donnees entreprise (company_name, siren, city, address, etc.)
- Relation : `contacts.company_id` -> `companies.id`

### 1.2 Problemes identifies

1. **Sync HubSpot ne met pas a jour les entreprises**
   - `import_from_hubspot()` appelle `update_contact()`
   - `update_contact()` filtre les champs entreprise (company_name, city, etc.)
   - Resultat : les changements d'entreprise dans HubSpot ne sont jamais appliques

2. **Sync incrementale ne detecte pas les changements d'entreprise**
   - Filtre sur `lastmodifieddate` des **contacts** uniquement
   - Si une entreprise est renommee dans HubSpot, le contact n'est pas "modifie"
   - Les changements d'entreprise passent inapercus

3. **Preview trompeuse**
   - La preview montre `company_name: OldName -> NewName`
   - Mais le changement n'est jamais applique car `company_name` est filtre

---

## 2. Solution Implementee

### 2.1 Architecture de Sync

```
+----------------------------------------------------------------+
|                    SYNC HUBSPOT                                  |
+----------------------------------------------------------------+
|                                                                  |
|  +------------------+    +------------------+                   |
|  | Sync Entreprises |    |  Sync Contacts   |                   |
|  |                  |    |                  |                   |
|  | HubSpot Companies|    | HubSpot Contacts |                   |
|  |       |          |    |       |          |                   |
|  | Table: companies |    | Table: contacts  |                   |
|  +------------------+    +------------------+                   |
|           |                       |                              |
|           +-----------+-----------+                              |
|                       |                                          |
|              +----------------+                                  |
|              | Sync Complete  |                                  |
|              | (Entreprises   |                                  |
|              |  puis Contacts)|                                  |
|              +----------------+                                  |
|                                                                  |
+----------------------------------------------------------------+
```

### 2.2 Modes de Synchronisation

| Mode | Description | Cas d'usage |
|------|-------------|-------------|
| **Sync Entreprises** | Pull companies depuis HubSpot | Mise a jour noms, adresses |
| **Sync Contacts** | Pull contacts depuis HubSpot | Mise a jour emails, telephones |
| **Sync Complete** | Entreprises + Contacts (sequentiel) | Sync hebdomadaire, recommande |

### 2.3 Sens de Synchronisation

**Phase 1 (implementee) : Pull uniquement (HubSpot -> Local)**
- HubSpot est la source de verite
- Aucune modification de HubSpot depuis l'app

---

## 3. Implementation

### 3.1 CompanyManager - Nouvelles methodes

```python
def find_by_hubspot_id(self, hubspot_company_id: str) -> Optional[Dict[str, Any]]
    """Trouve une entreprise par ID HubSpot."""

def import_from_hubspot(self, companies: List[Dict[str, Any]]) -> Tuple[int, int]
    """
    Importe des entreprises depuis HubSpot.

    Matching hierarchique:
    1. hubspot_company_id (exact)
    2. siren (exact)
    3. website/domain (exact)
    4. company_name (fuzzy, >90%)

    Returns: Tuple (added, updated)
    """
```

### 3.2 HubSpotClient - Nouvelles methodes

```python
def get_all_companies(self, limit: int = 1000, progress_callback=None) -> List[Dict]
    """Recupere toutes les companies depuis HubSpot."""

def sync_companies(self, limit: int = 1000, progress_callback=None) -> Dict
    """
    Synchronise les companies depuis HubSpot.

    Returns:
        Dict avec: success, total_companies, companies
    """

def _parse_company(self, raw_company: Dict) -> Optional[Dict[str, Any]]
    """Parse une company brute de l'API HubSpot."""
```

### 3.3 Interface Utilisateur

L'onglet "Sync HubSpot" (anciennement "Import HubSpot") offre maintenant:
- Radio buttons pour choisir le mode de sync
- Limites configurables pour entreprises et contacts
- Preview separee pour Entreprises et Contacts
- Import sequentiel (entreprises d'abord)

---

## 4. Tests

### 4.1 Scenarios couverts

1. **Sync entreprise - Nouveau** : Company HubSpot non existante localement -> creation
2. **Sync entreprise - Mise a jour** : Nom modifie dans HubSpot -> update local
3. **Sync contact** : Champs contact uniquement mis a jour
4. **Sync complete** : Entreprises puis contacts dans l'ordre

---

## 5. Fichiers modifies

| Fichier | Modifications |
|---------|---------------|
| `modules/lead_scraper/company_manager.py` | +find_by_hubspot_id(), +import_from_hubspot() |
| `modules/lead_scraper/hubspot_client.py` | +get_all_companies(), +sync_companies(), +_parse_company() |
| `pages/3_Base_de_Leads.py` | Refonte complete onglet Sync HubSpot |

---

*Document cree le 2025-12-22*
