# SPEC: Outil de Déduplication Entreprises & Contacts

**Version:** 1.0
**Date:** 2025-12-22
**Statut:** Draft
**Auteur:** Claude

---

## 1. Contexte et Problème

### 1.1 Situation actuelle

Après un import CSV, des doublons peuvent être créés :
- **Entreprises** : Même entreprise avec des noms légèrement différents
- **Contacts** : Homonymes ou même personne avec variations

### 1.2 Problèmes identifiés

1. **Doublons d'entreprises**
   - Import CSV sans matching → création de doublons
   - Variations de noms : "ACME SAS" vs "Acme" vs "ACME S.A.S."
   - Contacts dispersés sur plusieurs fiches entreprise

2. **Doublons de contacts**
   - Même personne avec emails différents
   - Homonymes (personnes différentes avec même nom)
   - Variations : "Jean-Pierre" vs "Jean Pierre" vs "JP"

### 1.3 Impact

- Stats faussées (nombre d'entreprises/contacts gonflé)
- Difficultés de suivi commercial
- Sync HubSpot créant des doublons côté CRM

---

## 2. Solution Proposée

### 2.1 Architecture

```
+------------------------------------------------------------------+
|                    OUTIL DE DÉDUPLICATION                         |
+------------------------------------------------------------------+
|                                                                    |
|  +-------------------------+    +-------------------------+       |
|  | Détection Entreprises   |    | Détection Contacts      |       |
|  |                         |    |                         |       |
|  | - Fuzzy name matching   |    | - Fuzzy name matching   |       |
|  | - SIREN identique       |    | - Email similaire       |       |
|  | - Website identique     |    | - Téléphone identique   |       |
|  | - Adresse similaire     |    | - Même entreprise       |       |
|  +-------------------------+    +-------------------------+       |
|              |                              |                      |
|              v                              v                      |
|  +-------------------------+    +-------------------------+       |
|  | Preview des groupes     |    | Preview des groupes     |       |
|  | de doublons             |    | de doublons             |       |
|  +-------------------------+    +-------------------------+       |
|              |                              |                      |
|              v                              v                      |
|  +-------------------------+    +-------------------------+       |
|  | Fusion manuelle         |    | Fusion manuelle         |       |
|  | (choix du master)       |    | ou marquage homonyme    |       |
|  +-------------------------+    +-------------------------+       |
|                                                                    |
+------------------------------------------------------------------+
```

### 2.2 Flux Utilisateur

```
┌─────────────────┐
│  1. ANALYSE     │  Bouton "🔍 Détecter les doublons"
└────────┬────────┘
         │
         v
┌─────────────────┐
│  2. PREVIEW     │  Liste des groupes de doublons potentiels
│                 │  avec score de similarité
└────────┬────────┘
         │
         v
┌─────────────────┐
│  3. DÉCISION    │  Pour chaque groupe :
│                 │  - Fusionner → choisir le master
│                 │  - Ignorer → pas des doublons
│                 │  - Marquer homonyme (contacts)
└────────┬────────┘
         │
         v
┌─────────────────┐
│  4. EXÉCUTION   │  Fusion des données
│                 │  Transfert des contacts
│                 │  Suppression des doublons
└─────────────────┘
```

---

## 3. Détection des Doublons

### 3.1 Entreprises - Critères de matching

| Critère | Poids | Seuil |
|---------|-------|-------|
| SIREN identique | 100% | Match exact → doublon certain |
| Website identique | 90% | Match exact → très probable |
| Nom fuzzy match | Variable | >85% similarité |
| Ville identique | +10% | Bonus si même ville |
| Adresse similaire | +15% | Bonus si adresse proche |

**Algorithme de scoring :**
```python
score = 0

# Critères absolus (doublon certain)
if siren_a == siren_b and siren_a:
    score = 100

elif website_a == website_b and website_a:
    score = 95

else:
    # Fuzzy matching sur le nom
    name_similarity = fuzzy_match(name_a, name_b)
    score = name_similarity * 100

    # Bonus géographique
    if city_a == city_b:
        score += 10
    if address_similarity > 0.8:
        score += 15

# Seuil de détection
if score >= 80:
    return "doublon_potentiel"
```

### 3.2 Contacts - Critères de matching

| Critère | Poids | Seuil |
|---------|-------|-------|
| Email identique | 100% | Match exact → doublon certain |
| Téléphone identique | 95% | Match exact → très probable |
| Nom + Prénom fuzzy | Variable | >90% similarité |
| Même entreprise | +20% | Bonus si même company_id |
| Job title similaire | +10% | Bonus si même fonction |

**Distinction Homonyme vs Doublon :**
```python
if email_a == email_b or phone_a == phone_b:
    return "doublon_certain"

name_score = fuzzy_match(fullname_a, fullname_b)

if name_score > 90:
    if company_a == company_b:
        return "doublon_probable"  # Même nom, même entreprise
    else:
        return "homonyme_possible"  # Même nom, entreprises différentes
```

---

## 4. Interface Utilisateur

### 4.1 Section dans l'onglet Sync HubSpot

Ajout d'une section dans l'onglet "🔄 Sync HubSpot" (après la sync bidirectionnelle) :

```
┌──────────────────────────────────────────────────────────────┐
│  🔄 Déduplication                                             │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ○ 🏢 Entreprises    ○ 👤 Contacts    ○ 🔄 Les deux          │
│                                                               │
│  Seuil de similarité : [====●=====] 85%                      │
│                                                               │
│  [🔍 Détecter les doublons]                                  │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 Preview des doublons entreprises

```
┌──────────────────────────────────────────────────────────────┐
│  📋 12 groupes de doublons potentiels détectés               │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ▼ Groupe 1 - Score: 95% (SIREN identique)                   │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ ○ ACME SAS          | 12345678901234 | Paris | 5 contacts│
│  │ ○ Acme              | 12345678901234 | Paris | 2 contacts│
│  │ ○ ACME S.A.S.       | 12345678901234 | Paris | 0 contacts│
│  └────────────────────────────────────────────────────────┘  │
│  [Fusionner ▼] [Ignorer]                                     │
│                                                               │
│  ▼ Groupe 2 - Score: 87% (Nom similaire + même ville)        │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ ○ Tech Solutions    |              | Lyon   | 3 contacts │
│  │ ○ TechSolutions SAS |              | Lyon   | 1 contact  │
│  └────────────────────────────────────────────────────────┘  │
│  [Fusionner ▼] [Ignorer]                                     │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### 4.3 Preview des doublons contacts

```
┌──────────────────────────────────────────────────────────────┐
│  📋 8 groupes de doublons/homonymes détectés                 │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ▼ Groupe 1 - DOUBLON CERTAIN (même email)                   │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ ○ Jean Dupont | jean@acme.fr | ACME SAS    | Directeur │  │
│  │ ○ J. Dupont   | jean@acme.fr | Acme        | DG        │  │
│  └────────────────────────────────────────────────────────┘  │
│  [Fusionner ▼] [Ignorer]                                     │
│                                                               │
│  ▼ Groupe 2 - HOMONYME POSSIBLE (entreprises différentes)   │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ ○ Marie Martin | marie@alpha.fr | Alpha Corp | RH      │  │
│  │ ○ Marie Martin | m.martin@beta.fr| Beta Inc  | Compta  │  │
│  └────────────────────────────────────────────────────────┘  │
│  [Ce sont des homonymes] [Fusionner ▼] [Ignorer]             │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### 4.4 Modal de fusion

```
┌──────────────────────────────────────────────────────────────┐
│  🔄 Fusion d'entreprises                                      │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Choisir l'entreprise MASTER (qui sera conservée) :          │
│                                                               │
│  ● ACME SAS (12345678901234) - 5 contacts                    │
│    → Website: acme.fr | Ville: Paris                         │
│                                                               │
│  ○ Acme (12345678901234) - 2 contacts                        │
│    → Website: (vide) | Ville: Paris                          │
│                                                               │
│  ○ ACME S.A.S. (12345678901234) - 0 contacts                 │
│    → Website: (vide) | Ville: (vide)                         │
│                                                               │
│  ─────────────────────────────────────────────────────────── │
│  Résultat de la fusion :                                      │
│  • 7 contacts seront rattachés à ACME SAS                    │
│  • 2 entreprises seront supprimées                           │
│  • Les données manquantes seront complétées si possible      │
│                                                               │
│  [Annuler]                    [✅ Confirmer la fusion]        │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 5. Implémentation Technique

### 5.1 CompanyManager - Nouvelles méthodes

```python
def find_duplicates(
    self,
    threshold: float = 0.85,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Détecte les groupes de doublons potentiels.

    Returns:
        Liste de groupes: [{
            'score': float,
            'reason': str,
            'companies': [company1, company2, ...]
        }]
    """

def merge_companies(
    self,
    master_id: int,
    duplicate_ids: List[int]
) -> Dict[str, Any]:
    """
    Fusionne des entreprises vers le master.

    1. Transfère tous les contacts vers master
    2. Complète les données manquantes du master
    3. Supprime (soft delete) les doublons

    Returns:
        {'contacts_moved': int, 'companies_deleted': int}
    """
```

### 5.2 ContactManager - Nouvelles méthodes

```python
def find_duplicates(
    self,
    threshold: float = 0.90,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Détecte les doublons et homonymes.

    Returns:
        Liste de groupes: [{
            'score': float,
            'type': 'doublon_certain' | 'doublon_probable' | 'homonyme',
            'reason': str,
            'contacts': [contact1, contact2, ...]
        }]
    """

def merge_contacts(
    self,
    master_id: int,
    duplicate_ids: List[int]
) -> Dict[str, Any]:
    """
    Fusionne des contacts vers le master.

    1. Complète les données du master
    2. Supprime (soft delete) les doublons

    Returns:
        {'merged': int}
    """

def mark_as_homonyms(
    self,
    contact_ids: List[int]
) -> bool:
    """
    Marque des contacts comme homonymes confirmés
    pour éviter de les re-détecter.
    """
```

### 5.3 Schéma BDD - Nouvelles tables/colonnes

```sql
-- Table pour tracker les homonymes confirmés
CREATE TABLE IF NOT EXISTS homonym_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,  -- 'contact' ou 'company'
    entity_ids TEXT NOT NULL,   -- JSON array d'IDs
    confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_by TEXT           -- 'user' ou 'system'
);

-- Ajout colonne pour ignorer dans la détection
ALTER TABLE contacts ADD COLUMN homonym_group_id INTEGER;
ALTER TABLE companies ADD COLUMN duplicate_checked_at TIMESTAMP;
```

---

## 6. Stratégie de Fusion

### 6.0 Stratégie de suppression : Renommage "_todelete"

**Principe** : Les doublons ne sont pas supprimés directement mais **renommés** avec le suffixe `_todelete` pour permettre :
- Une vérification manuelle avant suppression définitive
- Un nettoyage facile dans HubSpot (recherche "_todelete")
- Une traçabilité des fusions

**Convention de nommage :**
```
Entreprise : "Acme"           → "Acme_todelete"
Contact    : "Jean Dupont"    → "Jean Dupont_todelete"
```

**Champs modifiés lors du marquage :**
- `company_name` / `firstname` + `lastname` : Ajout du suffixe `_todelete`
- `status` : `'merged'`
- `merged_into` : ID du master
- `merged_at` : Timestamp

### 6.1 Fusion Entreprises

```
Master                    Doublon 1           Doublon 2
─────────────────────────────────────────────────────────
company_name: "ACME SAS"  "Acme"              "ACME S.A.S."
siren: 123456789          123456789           123456789
website: "acme.fr"        (vide)              (vide)
city: "Paris"             "Paris"             (vide)
contacts: [A, B, C]       [D, E]              []
─────────────────────────────────────────────────────────

Résultat après fusion :
─────────────────────────────────────────────────────────
company_name: "ACME SAS"  ← Garde le master
siren: 123456789          ← Déjà présent
website: "acme.fr"        ← Déjà présent
city: "Paris"             ← Déjà présent
contacts: [A, B, C, D, E] ← Tous transférés
─────────────────────────────────────────────────────────
Doublon 1 → company_name = "Acme_todelete", status = 'merged'
Doublon 2 → company_name = "ACME S.A.S._todelete", status = 'merged'
```

### 6.2 Fusion Contacts

```
Master                    Doublon
─────────────────────────────────────────────────────────
firstname: "Jean"         "J."
lastname: "Dupont"        "Dupont"
email: "jean@acme.fr"     "jean@acme.fr"
phone: "+33612345678"     (vide)
job_title: "Directeur"    "DG"
company_id: 42            43 (doublon entreprise)
─────────────────────────────────────────────────────────

Résultat après fusion :
─────────────────────────────────────────────────────────
firstname: "Jean"         ← Préfère le plus complet
lastname: "Dupont"
email: "jean@acme.fr"
phone: "+33612345678"     ← Garde la valeur existante
job_title: "Directeur"    ← Garde le master
company_id: 42            ← Garde le master
─────────────────────────────────────────────────────────
Doublon → lastname = "Dupont_todelete", status = 'merged'
```

### 6.3 Synchronisation HubSpot après fusion

**Flux de synchronisation :**

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Fusion locale  │ ──► │  Sync HubSpot   │ ──► │  Clean HubSpot  │
│  (Base SQLite)  │     │  (API update)   │     │  (manuel)       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

**Actions automatiques après fusion :**

1. **Mise à jour du master dans HubSpot** (si hubspot_id existe)
   - Transfert des associations contacts → master company
   - Mise à jour des données enrichies

2. **Renommage des doublons dans HubSpot**
   - `name` → `"Acme_todelete"`
   - Permet filtrage facile : rechercher `_todelete` dans HubSpot
   - Suppression manuelle par l'utilisateur

**Exemple d'appel API HubSpot :**
```python
# Renommer le doublon dans HubSpot
hubspot.update_company(
    hubspot_company_id=doublon.hubspot_company_id,
    properties={"name": f"{doublon.company_name}_todelete"}
)

# Transférer les contacts vers le master
for contact in doublon.contacts:
    hubspot.update_contact_company(
        contact.hubspot_contact_id,
        master.hubspot_company_id
    )
```

---

## 7. Cas d'Usage

### 7.1 Après import CSV

1. Utilisateur importe un CSV avec des entreprises
2. Certaines existent déjà (variations de nom)
3. → Lance "Détecter les doublons"
4. → Preview montre les groupes
5. → Fusionne en choisissant le master

### 7.2 Nettoyage périodique

1. Tous les mois, lancer la détection
2. Traiter les nouveaux doublons créés
3. Confirmer les homonymes

### 7.3 Avant sync HubSpot

1. Nettoyer les doublons locaux
2. Lancer la sync → évite de créer des doublons dans HubSpot

---

## 8. Tests

### 8.1 Scénarios de test

| Test | Entrée | Résultat attendu |
|------|--------|------------------|
| SIREN identique | 2 entreprises même SIREN | Doublon détecté (100%) |
| Nom similaire | "ACME" vs "Acme SAS" | Doublon potentiel (>85%) |
| Email identique | 2 contacts même email | Doublon certain |
| Homonyme | Même nom, entreprises différentes | Marqué homonyme |
| Fusion entreprise | Master + 2 doublons | Contacts transférés, doublons supprimés |
| Fusion contact | Master + doublon | Données complétées, doublon supprimé |

---

## 9. Fichiers à modifier

| Fichier | Modifications |
|---------|---------------|
| `modules/lead_scraper/company_manager.py` | +find_duplicates(), +merge_companies() |
| `modules/lead_scraper/contact_manager.py` | +find_duplicates(), +merge_contacts(), +mark_as_homonyms() |
| `modules/lead_scraper/hubspot_client.py` | +update_company_name(), +reassign_contacts_to_company() |
| `pages/3_📜_Base_de_Leads.py` | Section déduplication dans onglet **Sync HubSpot** |
| `database/schema.sql` | Colonnes merged_into, merged_at |

---

## 10. Décisions Prises

| Question | Décision |
|----------|----------|
| Soft delete ou hard delete ? | **Soft delete avec renommage `_todelete`** pour permettre hard delete manuel |
| Sync vers HubSpot ? | **Oui** - Renommer les doublons en `_todelete` dans HubSpot pour nettoyage manuel |
| Emplacement UI ? | **Onglet Sync HubSpot** (après la section sync bidirectionnelle) |
| Historique des fusions ? | Colonnes `merged_into` et `merged_at` suffisantes pour traçabilité |

---

## 11. Workflow Complet

```
┌──────────────────────────────────────────────────────────────────────┐
│                    WORKFLOW DÉDUPLICATION                             │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  1. DÉTECTION                                                         │
│     └─► Bouton "🔍 Détecter les doublons"                            │
│         └─► Analyse locale (SQLite)                                   │
│                                                                       │
│  2. PREVIEW                                                           │
│     └─► Affichage des groupes de doublons                            │
│         └─► Score + raison (SIREN, website, nom fuzzy...)            │
│                                                                       │
│  3. FUSION (par groupe)                                               │
│     └─► Choix du master                                               │
│     └─► Confirmation                                                  │
│         │                                                             │
│         ├─► LOCAL : Transfert contacts, renommage "_todelete"        │
│         │                                                             │
│         └─► HUBSPOT : Renommage "_todelete", transfert associations  │
│                                                                       │
│  4. NETTOYAGE (manuel dans HubSpot)                                   │
│     └─► Rechercher "_todelete"                                       │
│     └─► Supprimer définitivement                                      │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

---

*Document créé le 2025-12-22 - Mis à jour avec décisions validées*
