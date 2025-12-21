# Spec: Séparation Entreprises / Contacts

**Version:** 1.0
**Date:** 2025-12-21
**Auteur:** Équipe Sales Manager
**Statut:** DRAFT

---

## 🎯 Objectif

Séparer les données **Entreprises** et **Contacts** actuellement fusionnées dans `unified_contacts` pour :
- Éliminer la duplication des données entreprise
- Faciliter l'enrichissement et la mise à jour des entreprises
- Permettre une vue consolidée des entreprises
- Supporter les entreprises sans SIREN (internationales)
- Gérer les établissements multiples (plusieurs SIRET)

---

## 📊 Schéma de données cible

### Table `companies`

Stocke les **entreprises uniques** avec leurs données propres.

```sql
CREATE TABLE companies (
    -- === IDENTIFIANTS ===
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,  -- UUID v4 pour référence externe

    -- Identifiants officiels (optionnels)
    siren TEXT,  -- 9 chiffres (France), NULL si étranger/inconnu
    siret_list TEXT,  -- Liste SIRET séparés par virgule "12345678900001,12345678900002"

    -- Identifiants externes
    hubspot_company_id TEXT,

    -- === INFORMATIONS ENTREPRISE ===
    company_name TEXT NOT NULL,  -- Dénomination sociale
    legal_form TEXT,  -- SA, SAS, SARL, etc.

    -- Activité
    ape_code TEXT,  -- Code APE/NAF
    ape_label TEXT,  -- Libellé activité

    -- Siège social (adresse principale)
    address TEXT,
    postal_code TEXT,
    city TEXT,
    region TEXT,
    country TEXT DEFAULT 'FR',

    -- Taille & financier
    employee_range TEXT,  -- "1-10", "11-50", "51-200", etc.
    revenue_range TEXT,  -- Tranche CA

    -- Contact entreprise
    website TEXT,
    company_phone TEXT,
    company_email TEXT,

    -- === ENRICHISSEMENT ===
    enriched_at TIMESTAMP,
    enrichment_source TEXT,  -- "pappers", "hubspot", "manual"
    enrichment_quality TEXT,  -- "full", "partial", "minimal"

    -- === PROSPECTION (niveau entreprise) ===
    prospection_status TEXT DEFAULT 'new',  -- "new", "in_progress", "contacted", "qualified", "lost", "client"
    prospection_priority TEXT,  -- "high", "medium", "low"

    -- Stats agrégées des contacts
    total_contacts INTEGER DEFAULT 0,
    total_messages_sent INTEGER DEFAULT 0,
    total_messages_received INTEGER DEFAULT 0,
    last_contact_interaction_at TIMESTAMP,

    -- === SYNC HUBSPOT ===
    synced_to_hubspot INTEGER DEFAULT 0,
    last_sync_hubspot TIMESTAMP,

    -- === MÉTADONNÉES ===
    source TEXT NOT NULL,  -- "sirene", "getsales", "hubspot", "csv", "manual"
    campaign_id TEXT,  -- Campagne d'import

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Statut
    status TEXT DEFAULT 'active',  -- "active", "archived", "duplicate"

    -- Notes et données brutes
    notes TEXT,
    tags TEXT,  -- Tags séparés par virgule "tech,saas,paris"
    raw_data TEXT  -- JSON avec données brutes sources
);

-- Index
CREATE INDEX idx_companies_siren ON companies(siren);
CREATE INDEX idx_companies_name ON companies(company_name);
CREATE INDEX idx_companies_country ON companies(country);
CREATE INDEX idx_companies_campaign ON companies(campaign_id);
CREATE INDEX idx_companies_hubspot ON companies(hubspot_company_id);
CREATE INDEX idx_companies_status ON companies(status);
CREATE INDEX idx_companies_source ON companies(source);
CREATE INDEX idx_companies_created ON companies(created_at);

-- Contraintes
CREATE UNIQUE INDEX idx_companies_siren_unique ON companies(siren) WHERE siren IS NOT NULL;
CREATE UNIQUE INDEX idx_companies_hubspot_unique ON companies(hubspot_company_id) WHERE hubspot_company_id IS NOT NULL;
```

### Table `contacts` (ex unified_contacts)

Stocke les **contacts individuels** liés aux entreprises.

```sql
CREATE TABLE contacts (
    -- === IDENTIFIANTS ===
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,

    -- Lien entreprise (optionnel si contact sans entreprise connue)
    company_id INTEGER,  -- FK vers companies.id

    -- Identifiants externes
    getsales_uuid TEXT,
    hubspot_contact_id TEXT,

    -- === INFORMATIONS CONTACT ===
    -- Identité
    firstname TEXT,
    lastname TEXT,
    email TEXT,
    phone TEXT,
    mobile TEXT,

    -- Fonction
    job_title TEXT,
    department TEXT,  -- "Sales", "Marketing", "IT", etc.
    seniority TEXT,  -- "C-Level", "VP", "Director", "Manager", "Individual Contributor"

    -- LinkedIn
    linkedin_url TEXT,
    linkedin_headline TEXT,
    linkedin_bio TEXT,

    -- === PROSPECTION (niveau contact) ===
    prospection_status TEXT,  -- "new", "contacted", "replied", "interested", "not_interested"
    messages_sent INTEGER DEFAULT 0,
    messages_received INTEGER DEFAULT 0,
    last_interaction_at TIMESTAMP,

    -- GetSales specifique
    getsales_campaign_id TEXT,
    getsales_flow_id TEXT,

    -- === SYNC HUBSPOT ===
    synced_to_hubspot INTEGER DEFAULT 0,
    last_sync_hubspot TIMESTAMP,

    -- === MÉTADONNÉES ===
    source TEXT NOT NULL,  -- "sirene", "getsales", "hubspot", "csv", "manual"
    campaign_id TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Statut
    status TEXT DEFAULT 'active',  -- "active", "bounced", "unsubscribed", "archived"

    -- Notes
    notes TEXT,
    tags TEXT,
    raw_data TEXT,

    -- Contraintes
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL
);

-- Index
CREATE INDEX idx_contacts_company ON contacts(company_id);
CREATE INDEX idx_contacts_email ON contacts(email);
CREATE INDEX idx_contacts_linkedin ON contacts(linkedin_url);
CREATE INDEX idx_contacts_getsales ON contacts(getsales_uuid);
CREATE INDEX idx_contacts_hubspot ON contacts(hubspot_contact_id);
CREATE INDEX idx_contacts_campaign ON contacts(campaign_id);
CREATE INDEX idx_contacts_status ON contacts(status);
CREATE INDEX idx_contacts_source ON contacts(source);
CREATE INDEX idx_contacts_created ON contacts(created_at);

-- Contraintes
CREATE UNIQUE INDEX idx_contacts_email_unique ON contacts(email) WHERE email IS NOT NULL;
CREATE UNIQUE INDEX idx_contacts_linkedin_unique ON contacts(linkedin_url) WHERE linkedin_url IS NOT NULL;
CREATE UNIQUE INDEX idx_contacts_getsales_unique ON contacts(getsales_uuid) WHERE getsales_uuid IS NOT NULL;
CREATE UNIQUE INDEX idx_contacts_hubspot_unique ON contacts(hubspot_contact_id) WHERE hubspot_contact_id IS NOT NULL;
```

### Table `company_contacts_history`

**Optionnel** : Tracker les changements de poste (si un contact change d'entreprise).

```sql
CREATE TABLE company_contacts_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL,
    company_id INTEGER NOT NULL,
    job_title TEXT,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    is_current INTEGER DEFAULT 1,

    FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);
```

---

## 🔄 Relations et règles de gestion

### Relation Companies ↔ Contacts

- **Cardinalité**: 1 Company → N Contacts (1:N)
- **Optionalité**:
  - Un contact **peut** ne pas avoir d'entreprise (`company_id = NULL`)
  - Une entreprise **peut** ne pas avoir de contacts (juste données entreprise)

### Règles SIREN/SIRET

1. **SIREN optionnel**:
   - `siren = NULL` pour entreprises étrangères ou inconnues
   - Déduplication alors basée sur `company_name` + `website` + `country`

2. **Multiples SIRET**:
   - Format: `"12345678900001,12345678900002,12345678900003"`
   - Premier SIRET = siège principal
   - Utiliser pour établissements multiples (ex: chaînes de magasins)

3. **Contrainte unicité SIREN**:
   - Index unique sur SIREN (si non NULL)
   - Évite doublons d'entreprises françaises

### Règles de suppression

- **CASCADE**: Si suppression company → contacts.company_id = NULL (pas suppression contact)
- **Rationale**: Un contact peut exister sans entreprise, mais garde son historique

---

## 📋 Cas d'usage détaillés

### CU1: Recherche SIRENE → Ajout entreprises

**Flow:**
```
1. User recherche "cybersécurité Paris" dans page SIRENE
2. Pappers retourne 50 entreprises
3. Pour chaque entreprise:
   a. Vérifier si SIREN existe déjà
   b. Si existe: UPDATE données (enrichissement)
   c. Si nouveau: INSERT INTO companies
4. Afficher liste des 50 entreprises (pas de contacts)
5. User peut sélectionner entreprises à enrichir
```

**SQL:**
```sql
-- Vérification existence
SELECT id FROM companies WHERE siren = ?

-- Insert nouvelle entreprise
INSERT INTO companies (
    uuid, siren, company_name, ape_code, address, city,
    source, campaign_id
) VALUES (?, ?, ?, ?, ?, ?, 'sirene', ?)

-- Update si existe
UPDATE companies SET
    company_name = ?,
    ape_code = ?,
    address = ?,
    updated_at = CURRENT_TIMESTAMP,
    enrichment_source = 'sirene'
WHERE siren = ?
```

### CU2: Enrichissement entreprise (Pappers dirigeants)

**Flow:**
```
1. User clique "Enrichir dirigeants" sur une entreprise
2. API Pappers → Liste dirigeants + contacts
3. Pour chaque dirigeant:
   a. Vérifier si contact existe (email ou nom+prénom)
   b. Si nouveau: INSERT INTO contacts avec company_id
   c. Si existe: UPDATE infos contact
4. UPDATE companies SET enriched_at, total_contacts
5. Afficher entreprise avec ses contacts
```

**SQL:**
```sql
-- Vérification contact existant
SELECT id FROM contacts
WHERE email = ? OR (firstname = ? AND lastname = ? AND company_id = ?)

-- Insert nouveau contact
INSERT INTO contacts (
    uuid, company_id, firstname, lastname, email, job_title,
    source, campaign_id
) VALUES (?, ?, ?, ?, ?, ?, 'pappers', ?)

-- Update stats entreprise
UPDATE companies SET
    total_contacts = (SELECT COUNT(*) FROM contacts WHERE company_id = ?),
    enriched_at = CURRENT_TIMESTAMP,
    enrichment_quality = 'full'
WHERE id = ?
```

### CU3: Import GetSales → Matching entreprise

**Flow:**
```
1. GetSales retourne 10 leads
2. Pour chaque lead:
   a. Extraire company_name, domain, linkedin_company
   b. Chercher entreprise existante:
      - Par domain (website)
      - Par SIREN (si trouvé via API)
      - Par nom normalisé (fuzzy matching)
   c. Si trouvée: Lier contact à company_id existant
   d. Si nouvelle:
      - INSERT INTO companies (sans SIREN si pas français)
      - INSERT INTO contacts avec company_id
3. Éviter création entreprise doublon
```

**Logique matching:**
```python
def find_or_create_company(lead_data):
    """
    Matching hiérarchique pour éviter doublons
    """
    # 1. Match par domain
    if lead_data.get('domain'):
        company = find_by_website(lead_data['domain'])
        if company:
            return company

    # 2. Match par SIREN (si dispo via enrichissement)
    if lead_data.get('company_name'):
        siren = pappers_search_siren(lead_data['company_name'])
        if siren:
            company = find_by_siren(siren)
            if company:
                return company

    # 3. Match par nom normalisé (fuzzy)
    if lead_data.get('company_name'):
        company = find_by_fuzzy_name(
            normalize_company_name(lead_data['company_name'])
        )
        if company and similarity > 0.85:
            return company

    # 4. Créer nouvelle entreprise
    return create_company({
        'company_name': lead_data['company_name'],
        'website': lead_data.get('domain'),
        'siren': None,  # Pas de SIREN pour GetSales leads
        'source': 'getsales',
        'country': 'FR'  # Par défaut, à confirmer
    })
```

### CU4: Sync HubSpot bidirectionnelle

**Flow Sync Companies:**
```
1. Récupérer companies modifiées depuis last_sync
2. Pour chaque company:
   a. Si hubspot_company_id exists: UPDATE HubSpot company
   b. Si nouveau: CREATE HubSpot company
   c. Stocker hubspot_company_id
3. UPDATE last_sync_hubspot
```

**Flow Sync Contacts:**
```
1. Récupérer contacts modifiés depuis last_sync
2. Pour chaque contact:
   a. Vérifier si company_id existe
   b. Si company_id ET company.hubspot_company_id:
      - Lier contact HubSpot à company HubSpot
   c. CREATE ou UPDATE contact HubSpot
   d. Stocker hubspot_contact_id
3. UPDATE last_sync_hubspot
```

**Mapping HubSpot:**
```
Companies table → HubSpot Companies
├── company_name → name
├── website → website
├── employee_range → numberofemployees
├── revenue_range → annualrevenue
├── address → address
├── city → city
├── siren → custom: siren
└── siret_list → custom: siret_list

Contacts table → HubSpot Contacts
├── firstname → firstname
├── lastname → lastname
├── email → email
├── job_title → jobtitle
├── linkedin_url → hs_linkedin_url
├── company_id → associatedcompanyid (via hubspot_company_id)
└── getsales_uuid → custom: getsales_uuid
```

### CU5: Ajout contact manuel sans entreprise

**Flow:**
```
1. User clique "Ajouter contact manuel"
2. Formulaire:
   - Prénom, Nom, Email (requis)
   - Entreprise (optionnel, autocomplete sur companies.company_name)
   - Job title, LinkedIn
3. Si entreprise sélectionnée: company_id = selected
4. Si pas d'entreprise: company_id = NULL
5. INSERT INTO contacts
```

**Permet:**
- Contacts freelances
- Contacts dont on ne connaît pas l'entreprise
- Enrichissement ultérieur

---

## 🔧 Impact sur le code existant

### Modules à adapter

#### 1. `ContactManager` → Devient `CompanyManager` + `ContactManager`

**Nouveau: `CompanyManager`**
```python
class CompanyManager:
    def create_company(data: dict) -> int
    def get_company(company_id: int) -> Company
    def find_company_by_siren(siren: str) -> Company
    def find_company_by_website(website: str) -> Company
    def update_company(company_id: int, data: dict)
    def enrich_company_from_pappers(company_id: int)
    def get_companies_stats()
    def search_companies(filters: dict)
    def merge_companies(company_id_1: int, company_id_2: int)
```

**Modifié: `ContactManager`**
```python
class ContactManager:
    def create_contact(data: dict, company_id: int = None) -> int
    def get_contact(contact_id: int) -> Contact
    def get_contacts_by_company(company_id: int) -> List[Contact]
    def link_contact_to_company(contact_id: int, company_id: int)
    def unlink_contact_from_company(contact_id: int)
    def update_contact(contact_id: int, data: dict)
    def search_contacts(filters: dict)
```

#### 2. `HubSpotClient`

**Nouvelles méthodes:**
```python
def sync_companies() -> dict
    """Sync bidirectionnelle companies"""

def push_companies(companies: List[dict]) -> dict
    """Push companies vers HubSpot"""

def sync_contacts_with_company_association() -> dict
    """Sync contacts + lien company"""

def link_contact_to_company_hubspot(
    hubspot_contact_id: str,
    hubspot_company_id: str
)
```

#### 3. `PappersClient`

**Nouvelles méthodes:**
```python
def search_companies(query: str, filters: dict) -> List[dict]
    """Recherche entreprises (retourne données company)"""

def get_company_dirigeants(siren: str) -> List[dict]
    """Récupère dirigeants (retourne données contacts)"""

def enrich_company(siren: str) -> dict
    """Enrichissement complet entreprise"""
```

#### 4. `GetSalesClient` + `GetSalesSyncService`

**Nouvelles méthodes:**
```python
def extract_company_data(lead: dict) -> dict
    """Extrait données entreprise d'un lead GetSales"""

def match_or_create_company(lead: dict) -> int
    """Trouve ou crée entreprise, retourne company_id"""

def create_contact_with_company(lead: dict, company_id: int) -> int
    """Crée contact lié à entreprise"""
```

### Pages Streamlit à adapter

#### Page "Recherche Leads SIRENE"
**Avant:** Recherche → Insert unified_contacts
**Après:**
- Recherche → Insert companies
- Affichage table entreprises
- Bouton "Enrichir dirigeants" par entreprise
- Enrichissement → Insert contacts liés

#### Page "Base de Leads"
**Renommer:** "Base Contacts & Entreprises"
**Sections:**
- Onglet "Entreprises"
  - Table companies
  - Stats par entreprise (nb contacts, prospection status)
  - Actions: Enrichir, Sync HubSpot, Voir contacts
- Onglet "Contacts"
  - Table contacts avec colonne entreprise
  - Filtres: par entreprise, par statut, par source
  - Actions: Modifier, Sync HubSpot

#### Page "GetSales Sync"
**Workflow modifié:**
- Pour chaque pending lead:
  1. Extraire company_name, domain
  2. Proposer matching entreprise existante (ou créer)
  3. Créer contact lié à company_id
  4. Afficher "Contact créé pour [Entreprise X]"

---

## 📦 Plan de migration

### Phase 1: Préparation (pas de downtime)

1. **Créer tables nouvelles**
   ```sql
   CREATE TABLE companies (...);
   CREATE TABLE contacts_new (...);
   ```

2. **Extraire entreprises uniques**
   ```sql
   INSERT INTO companies (uuid, siren, company_name, ape_code, ...)
   SELECT
       lower(hex(randomblob(16))),
       siren,
       company_name,
       ape_code,
       ...
   FROM unified_contacts
   WHERE siren IS NOT NULL
   GROUP BY siren;

   -- Pour contacts sans SIREN (GetSales par ex)
   INSERT INTO companies (uuid, company_name, website, ...)
   SELECT ...
   FROM unified_contacts
   WHERE siren IS NULL AND getsales_uuid IS NOT NULL
   GROUP BY company_name, website;
   ```

3. **Migrer contacts vers contacts_new**
   ```sql
   INSERT INTO contacts_new (
       uuid, company_id, firstname, lastname, email, ...
   )
   SELECT
       uc.uuid,
       (SELECT id FROM companies WHERE companies.siren = uc.siren LIMIT 1),
       uc.firstname,
       uc.lastname,
       uc.email,
       ...
   FROM unified_contacts uc;
   ```

4. **Vérification intégrité**
   ```sql
   -- Vérifier tous les contacts ont bien un company_id ou NULL explicite
   SELECT COUNT(*) FROM contacts_new WHERE company_id IS NULL;

   -- Vérifier pas de SIREN dupliqués
   SELECT siren, COUNT(*) FROM companies
   WHERE siren IS NOT NULL
   GROUP BY siren
   HAVING COUNT(*) > 1;
   ```

### Phase 2: Bascule (downtime 5min)

1. **Renommer tables**
   ```sql
   ALTER TABLE unified_contacts RENAME TO unified_contacts_backup;
   ALTER TABLE contacts_new RENAME TO contacts;
   ```

2. **Créer vues compatibilité** (optionnel pour migration progressive)
   ```sql
   CREATE VIEW unified_contacts AS
   SELECT
       c.id,
       c.uuid,
       c.firstname,
       c.lastname,
       c.email,
       comp.siren,
       comp.company_name,
       comp.ape_code,
       ...
   FROM contacts c
   LEFT JOIN companies comp ON c.company_id = comp.id;
   ```

### Phase 3: Adaptation code

1. **Adapter modules** (ordre):
   - CompanyManager (nouveau)
   - ContactManager (modifié)
   - HubSpotClient
   - PappersClient
   - GetSalesSyncService

2. **Adapter pages Streamlit**
   - Recherche Leads (workflow entreprises)
   - Base de Leads → Base Contacts & Entreprises
   - GetSales Sync (matching entreprise)

3. **Tests**
   - Test création entreprise + contacts
   - Test sync HubSpot companies + contacts
   - Test import GetSales avec matching

### Phase 4: Nettoyage

1. **Supprimer vue compatibilité**
2. **Supprimer backup table** (après validation production)
3. **Documenter nouvelle architecture**

---

## ✅ Critères d'acceptance

### Fonctionnels

- [ ] Une entreprise peut avoir 0 à N contacts
- [ ] Un contact peut exister sans entreprise (company_id = NULL)
- [ ] Pas de duplication entreprise sur SIREN (si présent)
- [ ] Recherche SIRENE crée des entreprises (pas de contacts)
- [ ] Enrichissement Pappers crée des contacts liés à entreprise
- [ ] Import GetSales fait matching entreprise existante
- [ ] Sync HubSpot préserve lien contact ↔ company
- [ ] Interface permet de:
  - Voir liste entreprises avec nb contacts
  - Voir contacts d'une entreprise
  - Créer contact sans entreprise
  - Lier contact existant à entreprise

### Techniques

- [ ] FK constraint sur contacts.company_id
- [ ] Index sur tous les champs de recherche
- [ ] Unicité SIREN (si non NULL)
- [ ] Unicité email contacts (si non NULL)
- [ ] Migration 0 perte de données
- [ ] Performance: Requête "toutes entreprises avec stats contacts" < 100ms

### Non-régression

- [ ] Import SIRENE fonctionne
- [ ] Sync HubSpot fonctionne
- [ ] Import GetSales fonctionne
- [ ] Export CSV fonctionne
- [ ] Recherche contacts fonctionne

---

## 🚀 Timeline estimée

| Phase | Durée | Tâches |
|-------|-------|--------|
| **Phase 1: Préparation** | 2-3 jours | Créer tables, scripts migration, tests migration |
| **Phase 2: Bascule** | 5 min | Renommer tables, créer vues |
| **Phase 3: Adaptation code** | 3-5 jours | Modules, pages Streamlit, tests |
| **Phase 4: Nettoyage** | 1 jour | Suppression backup, docs |
| **TOTAL** | ~7-10 jours | |

---

## 📝 Questions ouvertes

### Q1: Gestion établissements multiples (SIRET)

**Contexte:** Une entreprise (1 SIREN) peut avoir plusieurs établissements (N SIRET).

**Options:**

**Option A (retenue): Liste SIRET dans companies**
```
companies.siret_list = "12345678900001,12345678900002"
```
✅ Simple
✅ Couvre 95% des cas
❌ Pas d'adresse par établissement

**Option B: Table establishments**
```sql
CREATE TABLE establishments (
    id INTEGER PRIMARY KEY,
    company_id INTEGER,
    siret TEXT,
    address TEXT,
    is_headquarters INTEGER
);
```
✅ Modélisation complète
❌ Complexité accrue
❌ Overkill pour notre usage

**Décision:** Option A pour MVP, évoluer vers B si besoin.

### Q2: Matching entreprises GetSales (sans SIREN)

**Stratégies:**

1. **Par domain** (ex: `company.com`)
   - Fiabilité: 90%
   - Problème: Domaines multiples, sous-domaines

2. **Par nom normalisé + fuzzy matching**
   ```python
   normalize("ESCP Business School") → "escp business school"
   similarity("escp business school", "escp bs") → 0.75
   ```
   - Fiabilité: 70%
   - Problème: Homonymes

3. **Enrichissement API (Pappers/Clearbit) pour trouver SIREN**
   - Fiabilité: 95%
   - Problème: Coût API, latence

**Décision:** Stratégie combinée (1 → 3 → 2).

### Q3: Contacts changeant d'entreprise

**Scénario:** Jean Dupont passe de Entreprise A à Entreprise B.

**Options:**

**Option A (retenue): Update company_id**
```sql
UPDATE contacts SET company_id = ? WHERE id = ?
```
✅ Simple
❌ Perte historique

**Option B: Table history + soft delete**
```sql
-- Garder ancien contact, créer nouveau
INSERT INTO contacts (...) VALUES (...);
UPDATE contacts SET status = 'archived' WHERE id = old_id;

-- OU table company_contacts_history
```
✅ Historique complet
❌ Complexité

**Décision:** Option A pour MVP, ajouter history si besoin tracking précis.

---

## 📚 Références

- [HubSpot Companies API](https://developers.hubspot.com/docs/api/crm/companies)
- [HubSpot Associations API](https://developers.hubspot.com/docs/api/crm/associations)
- [Pappers API Entreprises](https://www.pappers.fr/api/documentation)
- [SQLite Foreign Keys](https://www.sqlite.org/foreignkeys.html)

---

## ✍️ Changelog

| Date | Version | Changements |
|------|---------|-------------|
| 2025-12-21 | 1.0 | Spec initiale |
