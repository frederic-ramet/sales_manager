# EPIC: Lead Management v2 - Pipeline Unifié

**Version:** 1.0
**Date:** 2025-12-22
**Statut:** Draft
**Auteur:** Claude + Frédéric

---

## 1. Vision

### 1.1 Objectif

Construire une application de gestion de leads avec un pipeline clair :

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   IMPORT    │ →  │    CLEAN    │ →  │   ENRICH    │ →  │    SYNC     │
│             │    │             │    │             │    │             │
│ CSV/GetSales│    │ Dédup       │    │ Pappers     │    │ → HubSpot   │
│ HubSpot     │    │ Normalise   │    │ SIRENE      │    │ (one-way)   │
│ SIRENE      │    │ Valide      │    │ LinkedIn    │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### 1.2 Principe clé

**La base locale est la source de vérité.**

- On importe, nettoie, enrichit en LOCAL
- On pousse vers HubSpot uniquement quand les données sont propres
- Pas de doublons créés dans HubSpot

### 1.3 Changements par rapport à v1

| Aspect | v1 (actuel) | v2 (cible) |
|--------|-------------|------------|
| Pipeline | Flou, features éparpillées | 4 étapes claires |
| Import | Crée des doublons | Matching intelligent |
| Data model | Contacts + Companies basiques | + Interactions + champs enrichis |
| Sync | Bidirectionnel complexe | One-way Local → HubSpot |
| UI | Tabs multiples confus | 4 onglets = 4 étapes |

---

## 2. Data Model

### 2.1 Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA MODEL v2                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────┐         ┌────────────────┐         ┌────────────────┐   │
│  │   COMPANIES    │         │    CONTACTS    │         │  INTERACTIONS  │   │
│  ├────────────────┤         ├────────────────┤         ├────────────────┤   │
│  │ uuid (PK)      │◄────────│ company_uuid   │    ┌────│ contact_uuid   │   │
│  │ name           │         │ uuid (PK)      │◄───┘    │ uuid (PK)      │   │
│  │ domain         │         │ linkedin_url ──┼─────┐   │ type           │   │
│  │ siren          │         │ firstname      │     │   │ direction      │   │
│  │ ...            │         │ lastname       │     │   │ channel        │   │
│  └────────────────┘         │ email          │     │   │ date           │   │
│                             │ job_title      │     │   │ content        │   │
│                             │ ...            │     │   │ ...            │   │
│                             └────────────────┘     │   └────────────────┘   │
│                                                    │                         │
│                             linkedin_url = clé pour lier                     │
│                             la même personne dans plusieurs sociétés         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Table COMPANIES

```sql
CREATE TABLE companies (
    -- Identifiants
    uuid TEXT PRIMARY KEY,
    siren TEXT,                          -- Clé de matching #1
    siret TEXT,

    -- Identifiants externes
    hubspot_company_id TEXT,

    -- Informations entreprise
    name TEXT NOT NULL,
    domain TEXT,                         -- Clé de matching #2
    legal_form TEXT,                     -- SAS, SARL, SA...

    -- Localisation siège
    hq_address TEXT,
    hq_city TEXT,
    hq_state TEXT,                       -- Région
    hq_postal_code TEXT,
    hq_country TEXT DEFAULT 'France',

    -- Activité
    ape_code TEXT,
    ape_label TEXT,
    industry TEXT,                       -- Secteur (depuis CSV)
    description TEXT,

    -- Taille & Finance
    size TEXT,                           -- "1-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000", "5001-10000", "10001+"
    size_exact INTEGER,                  -- Nombre exact si connu
    revenue REAL,                        -- CA en euros
    revenue_range TEXT,                  -- "< 1M", "1-10M", "10-50M", "50-100M", "> 100M"

    -- Investissement (si startup)
    investment_stage TEXT,               -- Seed, Series A, B, C...
    investment_amount REAL,
    investment_date DATE,
    lead_investor TEXT,

    -- Tech
    founded_date DATE,
    technology_used TEXT,                -- JSON array ou texte libre

    -- Métadonnées
    source TEXT NOT NULL,                -- 'csv', 'getsales', 'hubspot', 'sirene', 'pappers'
    source_file TEXT,                    -- Nom du fichier CSV d'origine
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Statut
    status TEXT DEFAULT 'active',        -- 'active', 'merged', 'deleted'
    merged_into TEXT,                    -- UUID du master si fusionné
    merged_at TIMESTAMP,

    -- Enrichissement
    enriched_at TIMESTAMP,
    enrichment_source TEXT,              -- 'pappers', 'sirene'

    -- Sync
    synced_to_hubspot INTEGER DEFAULT 0,
    last_sync_hubspot TIMESTAMP
);

-- Index
CREATE INDEX idx_companies_siren ON companies(siren);
CREATE INDEX idx_companies_domain ON companies(domain);
CREATE INDEX idx_companies_name ON companies(name);
CREATE INDEX idx_companies_hubspot ON companies(hubspot_company_id);
CREATE INDEX idx_companies_status ON companies(status);
```

### 2.3 Table CONTACTS

**Principe : 1 contact = 1 personne + 1 entreprise + 1 rôle**

```sql
CREATE TABLE contacts (
    -- Identifiants
    uuid TEXT PRIMARY KEY,
    company_uuid TEXT,                   -- FK vers companies

    -- Identifiants externes
    hubspot_contact_id TEXT,
    getsales_uuid TEXT,

    -- Identité
    firstname TEXT,
    lastname TEXT,
    linkedin_url TEXT,                   -- Clé pour identifier même personne

    -- Coordonnées
    email TEXT,                          -- Email principal (verified si possible)
    email_verified INTEGER DEFAULT 0,    -- 1 = verified, 0 = unverified
    email_secondary TEXT,                -- Email secondaire
    phone TEXT,
    mobile TEXT,

    -- Poste
    job_title TEXT,
    seniority TEXT,                      -- 'C-Level', 'VP', 'Director', 'Manager', 'Individual'
    department TEXT,                     -- 'Tech', 'Sales', 'Marketing', 'HR', 'Finance'

    -- Localisation contact
    city TEXT,
    state TEXT,
    country TEXT DEFAULT 'France',
    timezone TEXT,

    -- Social
    twitter_url TEXT,
    github_url TEXT,

    -- Métadonnées
    source TEXT NOT NULL,                -- 'csv', 'getsales', 'hubspot', 'sirene', 'pappers'
    source_file TEXT,
    campaign_id TEXT,                    -- Campagne GetSales
    project_name TEXT,                   -- Projet d'origine
    search_name TEXT,                    -- Nom de la recherche
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Statut
    status TEXT DEFAULT 'active',        -- 'active', 'merged', 'deleted'
    merged_into TEXT,
    merged_at TIMESTAMP,
    homonym_group_id INTEGER,            -- Groupe d'homonymes confirmés

    -- Enrichissement
    enriched_at TIMESTAMP,
    enrichment_source TEXT,

    -- Sync
    synced_to_hubspot INTEGER DEFAULT 0,
    last_sync_hubspot TIMESTAMP,

    -- Foreign key
    FOREIGN KEY (company_uuid) REFERENCES companies(uuid)
);

-- Index
CREATE INDEX idx_contacts_linkedin ON contacts(linkedin_url);
CREATE INDEX idx_contacts_email ON contacts(email);
CREATE INDEX idx_contacts_company ON contacts(company_uuid);
CREATE INDEX idx_contacts_hubspot ON contacts(hubspot_contact_id);
CREATE INDEX idx_contacts_status ON contacts(status);
```

### 2.4 Table INTERACTIONS

```sql
CREATE TABLE interactions (
    -- Identifiants
    uuid TEXT PRIMARY KEY,
    contact_uuid TEXT NOT NULL,          -- FK vers contacts

    -- Identifiants externes
    hubspot_engagement_id TEXT,
    getsales_message_id TEXT,

    -- Type d'interaction
    type TEXT NOT NULL,                  -- 'message', 'email', 'call', 'meeting', 'note'
    direction TEXT,                      -- 'inbound', 'outbound'
    channel TEXT,                        -- 'linkedin', 'email', 'phone', 'in_person'

    -- Contenu
    subject TEXT,
    content TEXT,

    -- Timing
    interaction_date TIMESTAMP NOT NULL,
    duration_minutes INTEGER,            -- Pour calls/meetings

    -- Campagne
    campaign_id TEXT,
    sequence_step INTEGER,               -- Étape dans la séquence

    -- Résultat
    outcome TEXT,                        -- 'replied', 'no_reply', 'bounced', 'interested', 'not_interested'

    -- Métadonnées
    source TEXT NOT NULL,                -- 'getsales', 'hubspot', 'manual'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (contact_uuid) REFERENCES contacts(uuid)
);

-- Index
CREATE INDEX idx_interactions_contact ON interactions(contact_uuid);
CREATE INDEX idx_interactions_date ON interactions(interaction_date);
CREATE INDEX idx_interactions_type ON interactions(type);
CREATE INDEX idx_interactions_campaign ON interactions(campaign_id);
```

### 2.5 Clés de matching (déduplication)

| Entité | Priorité | Clé | Score |
|--------|----------|-----|-------|
| **Company** | 1 | SIREN exact | 100% |
| | 2 | Domain exact | 95% |
| | 3 | Name fuzzy (>85%) + même ville | 85% |
| **Contact** | 1 | Email exact | 100% |
| | 2 | LinkedIn URL exact | 100% |
| | 3 | Phone exact | 95% |
| | 4 | Name fuzzy (>90%) + même company | 85% |

---

## 3. Pipeline - Flux de données

### 3.1 Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PIPELINE LEAD MANAGEMENT                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ ÉTAPE 1: IMPORT                                                       │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │                                                                        │   │
│  │  Sources:          Mapping:              Résultat:                    │   │
│  │  • CSV             CSV headers →         • Companies créées/matchées  │   │
│  │  • GetSales        → champs DB           • Contacts créés/matchés     │   │
│  │  • HubSpot                               • Rapport d'import           │   │
│  │  • SIRENE                                                             │   │
│  │                                                                        │   │
│  │  Matching à l'import:                                                 │   │
│  │  Company: SIREN → Domain → Name+City                                  │   │
│  │  Contact: Email → LinkedIn → Name+Company                             │   │
│  │                                                                        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ ÉTAPE 2: CLEAN                                                        │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │                                                                        │   │
│  │  Déduplication:    Normalisation:        Validation:                  │   │
│  │  • Détection       • Noms entreprises    • Emails valides?           │   │
│  │  • Preview         • Téléphones          • LinkedIn URLs?            │   │
│  │  • Fusion/Ignore   • Adresses            • SIREN format?             │   │
│  │                    • Formes juridiques                                │   │
│  │                                                                        │   │
│  │  Actions:                                                             │   │
│  │  • Merge companies → transfert contacts                               │   │
│  │  • Merge contacts → complète données                                  │   │
│  │  • Mark homonymes → pas de fusion                                     │   │
│  │                                                                        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ ÉTAPE 3: ENRICH                                                       │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │                                                                        │   │
│  │  Sources:          Données ajoutées:     Priorisation:               │   │
│  │  • Pappers API     • Dirigeants          • Entreprises avec SIREN    │   │
│  │  • SIRENE API      • CA / Effectifs      • Sans données financières  │   │
│  │  • (LinkedIn)      • Forme juridique     • Triées par taille         │   │
│  │                    • Code APE                                         │   │
│  │                    • Adresse complète                                 │   │
│  │                                                                        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ ÉTAPE 4: SYNC                                                         │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │                                                                        │   │
│  │  Direction:        Matching HubSpot:     Résultat:                    │   │
│  │  Local → HubSpot   • Par hubspot_id      • Companies créées/màj      │   │
│  │  (one-way)         • Par SIREN           • Contacts créés/màj        │   │
│  │                    • Par domain          • Associations créées       │   │
│  │                    • Par email           • Pas de doublons           │   │
│  │                                                                        │   │
│  │  Ordre: Companies d'abord, puis Contacts (pour associations)          │   │
│  │                                                                        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Étape 1: IMPORT - Détails

#### Sources supportées

| Source | Format | Champs principaux |
|--------|--------|-------------------|
| **CSV FullEnrich** | CSV | Company, Domain, Size, First/Last Name, Job Title, LinkedIn, Email |
| **CSV Salesbot** | CSV | Idem + Investment info, Tech used, Description |
| **GetSales** | API/JSON | Contact LinkedIn, Messages, Company basique |
| **HubSpot** | API | Companies, Contacts, Engagements |
| **SIRENE** | API | SIREN, Denomination, APE, Adresse |

#### Mapping CSV → DB

```python
CSV_MAPPING = {
    # Company fields
    'Company': 'companies.name',
    'Company 1 Name': 'companies.name',
    'Domain': 'companies.domain',
    'Company 1 Website': 'companies.domain',
    'Size': 'companies.size',
    'Company 1 Size': 'companies.size',
    'Company 1 Revenue': 'companies.revenue',
    'Company 1 HQ City': 'companies.hq_city',
    'Company 1 HQ State': 'companies.hq_state',
    'Company 1 HQ Country': 'companies.hq_country',
    'Company 1 Industries': 'companies.industry',
    'Company 1 Description': 'companies.description',
    'Company 1 Founded Date': 'companies.founded_date',
    'Company 1 Investment Stage': 'companies.investment_stage',
    'Company 1 Investment Amount': 'companies.investment_amount',
    'Company 1 Investment Date': 'companies.investment_date',
    'Company 1 Lead Investor': 'companies.lead_investor',
    'Company 1 Technology Used': 'companies.technology_used',
    'Geo - company': 'companies.hq_country',

    # Contact fields
    'First Name': 'contacts.firstname',
    'Last Name': 'contacts.lastname',
    'Email': 'contacts.email',
    'Verified Professional Email 1': 'contacts.email',
    'Unverified Professional Email 1': 'contacts.email_secondary',
    'LinkedIn': 'contacts.linkedin_url',
    'LinkedIn URL 1': 'contacts.linkedin_url',
    'Job Title': 'contacts.job_title',
    'Company 1 Job Title': 'contacts.job_title',
    'Contact City': 'contacts.city',
    'Contact State': 'contacts.state',
    'Contact Country': 'contacts.country',
    'Timezone - lead': 'contacts.timezone',
    'Geo - lead': 'contacts.country',
    'Twitter URL': 'contacts.twitter_url',
    'Github URL': 'contacts.github_url',
    'Project Name': 'contacts.project_name',
    'Search Name': 'contacts.search_name',
}
```

#### Logique d'import

```python
def import_csv(file_path, source_name):
    """
    Import CSV avec matching intelligent.

    1. Parse CSV
    2. Pour chaque ligne:
       a. Extraire données company
       b. Chercher company existante (SIREN → Domain → Name+City)
       c. Créer ou mettre à jour company
       d. Extraire données contact
       e. Chercher contact existant (Email → LinkedIn → Name+Company)
       f. Créer ou mettre à jour contact
    3. Retourner rapport
    """
    report = {
        'companies': {'created': 0, 'updated': 0, 'matched': 0},
        'contacts': {'created': 0, 'updated': 0, 'matched': 0},
        'errors': []
    }
    # ...
```

### 3.3 Étape 2: CLEAN - Détails

#### Déduplication

Voir `SPEC_DEDUPLICATION_TOOL.md` pour les détails complets.

**Résumé:**
- Détection par score (100% SIREN, 95% Domain, 85% Name fuzzy)
- Preview avant fusion
- Choix du master
- Transfert contacts (pour companies)
- Renommage `_todelete` pour suppression manuelle
- Sync vers HubSpot

#### Normalisation

| Champ | Règle |
|-------|-------|
| **company.name** | Trim, capitalize, retirer formes juridiques en double |
| **company.domain** | Lowercase, retirer http(s)://, www., trailing slash |
| **company.siren** | Garder uniquement chiffres, valider longueur 9 |
| **contact.phone** | Format E.164 (+33612345678) |
| **contact.email** | Lowercase, trim |
| **contact.linkedin_url** | Normaliser format linkedin.com/in/xxx |

#### Validation

| Champ | Validation |
|-------|------------|
| **email** | Regex + MX check optionnel |
| **phone** | Regex format international |
| **siren** | 9 chiffres + clé Luhn |
| **linkedin_url** | Format valide |

### 3.4 Étape 3: ENRICH - Détails

#### Sources d'enrichissement

| Source | Condition | Données ajoutées |
|--------|-----------|------------------|
| **Pappers** | SIREN présent | Dirigeants, CA, Effectifs, Forme juridique |
| **SIRENE** | SIREN présent | Adresse complète, Code APE |

#### Priorisation

```python
def get_companies_to_enrich(limit=100):
    """
    Priorité:
    1. SIREN présent mais non enrichi
    2. Grandes entreprises d'abord (size)
    3. Créées récemment
    """
    return query("""
        SELECT * FROM companies
        WHERE siren IS NOT NULL
          AND enriched_at IS NULL
          AND status = 'active'
        ORDER BY
            CASE size
                WHEN '10001+' THEN 1
                WHEN '5001-10000' THEN 2
                WHEN '1001-5000' THEN 3
                ...
            END,
            created_at DESC
        LIMIT ?
    """, limit)
```

### 3.5 Étape 4: SYNC - Détails

#### Direction

```
LOCAL (SQLite) ──────────────────────────────► HUBSPOT
               Companies puis Contacts
               Matching pour éviter doublons
```

#### Matching HubSpot

| Local | HubSpot | Priorité |
|-------|---------|----------|
| `hubspot_company_id` | `id` | 1 (exact) |
| `siren` | custom property `siren` | 2 |
| `domain` | `domain` | 3 |
| `email` | `email` | 1 (contacts) |
| `hubspot_contact_id` | `id` | 1 (contacts) |

#### Workflow sync

```python
def sync_to_hubspot(companies=True, contacts=True):
    """
    1. Sync companies
       - Pour chaque company non synced ou modifiée
       - Chercher dans HubSpot (hubspot_id → SIREN → domain)
       - Créer ou update
       - Sauvegarder hubspot_company_id

    2. Sync contacts
       - Pour chaque contact non synced ou modifié
       - Chercher dans HubSpot (hubspot_id → email)
       - Créer ou update
       - Associer à company
       - Sauvegarder hubspot_contact_id

    3. Retourner rapport
    """
```

---

## 4. Interface Utilisateur

### 4.1 Structure des onglets

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BASE DE LEADS                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ 📊 Vue   │  │ 📥 Import│  │ 🧹 Clean │  │ 🔍 Enrich│  │ 🔄 Sync  │      │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Onglet 1: Vue (Dashboard)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 📊 VUE D'ENSEMBLE                                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │    1,234    │  │    3,456    │  │     567     │  │    2,890    │        │
│  │ Entreprises │  │  Contacts   │  │Interactions │  │ Synced HS   │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                                              │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐          │
│  │ PAR SOURCE                  │  │ STATUT PIPELINE             │          │
│  │ ● CSV: 800                  │  │ ○ À nettoyer: 45            │          │
│  │ ● GetSales: 234             │  │ ○ À enrichir: 123           │          │
│  │ ● HubSpot: 200              │  │ ○ À synchroniser: 67        │          │
│  └─────────────────────────────┘  └─────────────────────────────┘          │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │ RECHERCHE                                                    │           │
│  │ [_______________________________________________] [Chercher]  │           │
│  │                                                               │           │
│  │ Filtres: [Source ▼] [Statut ▼] [Enrichi ▼] [Synced ▼]       │           │
│  └─────────────────────────────────────────────────────────────┘           │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │ RÉSULTATS                                                    │           │
│  │ ┌──────────────────────────────────────────────────────────┐│           │
│  │ │ Nom         │ Email      │ Entreprise │ Source │ Statut  ││           │
│  │ │─────────────│────────────│────────────│────────│─────────││           │
│  │ │ Jean Dupont │ j@acme.fr  │ ACME SAS   │ csv    │ active  ││           │
│  │ │ ...         │ ...        │ ...        │ ...    │ ...     ││           │
│  │ └──────────────────────────────────────────────────────────┘│           │
│  └─────────────────────────────────────────────────────────────┘           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Onglet 2: Import

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 📥 IMPORT                                                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Source d'import:                                                            │
│  ○ CSV (FullEnrich, Salesbot, etc.)                                         │
│  ○ GetSales (synchronisation)                                               │
│  ○ HubSpot (import initial)                                                 │
│  ○ SIRENE (recherche par critères)                                          │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  [SI CSV SÉLECTIONNÉ]                                                        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │                    📁 Glisser un fichier CSV                 │           │
│  │                         ou cliquer pour sélectionner         │           │
│  └─────────────────────────────────────────────────────────────┘           │
│                                                                              │
│  Nom du fichier: export_10525.csv                                           │
│  Lignes détectées: 1,234                                                    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │ MAPPING DES COLONNES                                         │           │
│  │                                                               │           │
│  │ Company        → [companies.name          ▼]                 │           │
│  │ Domain         → [companies.domain        ▼]                 │           │
│  │ First Name     → [contacts.firstname      ▼]                 │           │
│  │ Last Name      → [contacts.lastname       ▼]                 │           │
│  │ Email          → [contacts.email          ▼]                 │           │
│  │ LinkedIn       → [contacts.linkedin_url   ▼]                 │           │
│  │ Job Title      → [contacts.job_title      ▼]                 │           │
│  │ ...                                                           │           │
│  └─────────────────────────────────────────────────────────────┘           │
│                                                                              │
│  Options:                                                                    │
│  ☑ Matching intelligent (éviter doublons)                                   │
│  ☑ Créer les entreprises manquantes                                         │
│  ☐ Mode test (preview sans import)                                          │
│                                                                              │
│  [📥 IMPORTER]                                                              │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  RÉSULTAT IMPORT:                                                            │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │ ✅ Import terminé                                            │           │
│  │                                                               │           │
│  │ Entreprises: 45 créées, 12 mises à jour, 8 matchées          │           │
│  │ Contacts: 123 créés, 34 mis à jour, 15 matchés               │           │
│  │ Erreurs: 2 lignes ignorées                                   │           │
│  └─────────────────────────────────────────────────────────────┘           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.4 Onglet 3: Clean

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🧹 CLEAN                                                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ DÉDUPLICATION                                                          │  │
│  │                                                                         │  │
│  │ Type: ○ 🏢 Entreprises  ○ 👤 Contacts  ○ 🔄 Les deux                   │  │
│  │                                                                         │  │
│  │ Seuil similarité: [====●=====] 85%     ☑ Sync HubSpot                  │  │
│  │                                                                         │  │
│  │ [🔍 DÉTECTER LES DOUBLONS]                                             │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ NORMALISATION                                                          │  │
│  │                                                                         │  │
│  │ ☑ Normaliser noms entreprises (trim, capitalize)                       │  │
│  │ ☑ Normaliser téléphones (format E.164)                                 │  │
│  │ ☑ Normaliser emails (lowercase)                                        │  │
│  │ ☑ Normaliser URLs LinkedIn                                             │  │
│  │                                                                         │  │
│  │ [🔧 NORMALISER]                                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ VALIDATION                                                             │  │
│  │                                                                         │  │
│  │ Données invalides détectées:                                           │  │
│  │ • 12 emails invalides                                                  │  │
│  │ • 5 SIREN incorrects                                                   │  │
│  │ • 3 URLs LinkedIn mal formées                                          │  │
│  │                                                                         │  │
│  │ [👁 VOIR DÉTAILS] [🗑 CORRIGER/SUPPRIMER]                              │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.5 Onglet 4: Enrich

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🔍 ENRICH                                                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Stats enrichissement:                                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                         │
│  │     234     │  │     567     │  │     123     │                         │
│  │ À enrichir  │  │  Enrichies  │  │ Sans SIREN  │                         │
│  └─────────────┘  └─────────────┘  └─────────────┘                         │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  Source d'enrichissement:                                                    │
│  ○ Pappers (SIREN → dirigeants, CA, effectifs)                              │
│  ○ SIRENE (SIREN → adresse, APE)                                            │
│                                                                              │
│  Filtres:                                                                    │
│  [Taille ▼]  [Secteur ▼]  [Non enrichies uniquement ☑]                     │
│                                                                              │
│  Limite: [___100___] entreprises                                            │
│                                                                              │
│  [🔍 ENRICHIR]                                                              │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  Progression: [████████░░░░░░░░░░░░] 45/100                                 │
│                                                                              │
│  Résultat:                                                                   │
│  • 45 entreprises enrichies                                                  │
│  • 12 dirigeants ajoutés                                                     │
│  • 3 erreurs (SIREN invalide)                                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.6 Onglet 5: Sync

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🔄 SYNC HUBSPOT                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Statut connexion: ✅ Connecté                                               │
│                                                                              │
│  Stats sync:                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │     890     │  │     567     │  │     123     │  │     200     │        │
│  │ À syncer    │  │  Synced     │  │  Modifiés   │  │ Depuis HS   │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  Mode:                                                                       │
│  ○ 🔄 Sync complète (entreprises + contacts)                                │
│  ○ 🏢 Entreprises uniquement                                                │
│  ○ 👤 Contacts uniquement                                                   │
│                                                                              │
│  Options:                                                                    │
│  ☑ Preview avant sync                                                       │
│  ☑ Créer les nouvelles entités                                              │
│  ☑ Mettre à jour les existantes                                             │
│                                                                              │
│  [🔍 ANALYSER] [🔄 SYNCHRONISER]                                            │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  PREVIEW:                                                                    │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ Entreprises: 45 à créer, 23 à màj, 12 inchangées                      │  │
│  │ Contacts: 123 à créer, 56 à màj, 34 inchangés                         │  │
│  │                                                                         │  │
│  │ [▼ Voir détails entreprises]                                           │  │
│  │ [▼ Voir détails contacts]                                              │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  [✅ CONFIRMER LA SYNC]                                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Fichiers à modifier / créer

### 5.1 Backend

| Fichier | Action | Description |
|---------|--------|-------------|
| `database/schema_v2.sql` | **Créer** | Nouveau schema avec tables companies, contacts, interactions |
| `modules/lead_scraper/company_manager.py` | **Modifier** | Adapter au nouveau schema |
| `modules/lead_scraper/contact_manager.py` | **Modifier** | Adapter au nouveau schema |
| `modules/lead_scraper/interaction_manager.py` | **Créer** | Gestionnaire des interactions |
| `modules/lead_scraper/csv_importer.py` | **Créer** | Import CSV avec mapping intelligent |
| `modules/lead_scraper/data_cleaner.py` | **Créer** | Normalisation et validation |
| `modules/lead_scraper/hubspot_sync.py` | **Modifier** | Simplifier pour one-way sync |

### 5.2 Frontend

| Fichier | Action | Description |
|---------|--------|-------------|
| `pages/3_📜_Base_de_Leads.py` | **Refactorer** | 5 onglets clairs (Vue, Import, Clean, Enrich, Sync) |

### 5.3 Migration

| Fichier | Action | Description |
|---------|--------|-------------|
| `scripts/migrate_to_v2.py` | **Créer** | Script de migration des données existantes |

---

## 6. Plan d'implémentation

### Phase 1: Data Model (1-2 jours)
- [ ] Créer schema_v2.sql
- [ ] Script de migration
- [ ] Tests migration

### Phase 2: Import (2-3 jours)
- [ ] CSV importer avec mapping
- [ ] Matching intelligent à l'import
- [ ] UI onglet Import

### Phase 3: Clean (1-2 jours)
- [ ] Adapter déduplication existante au nouveau schema
- [ ] Ajouter normalisation
- [ ] Ajouter validation
- [ ] UI onglet Clean

### Phase 4: Enrich (1 jour)
- [ ] Adapter enrichissement existant
- [ ] UI onglet Enrich

### Phase 5: Sync (1-2 jours)
- [ ] Simplifier sync one-way
- [ ] UI onglet Sync

### Phase 6: Dashboard (1 jour)
- [ ] UI onglet Vue
- [ ] Recherche et filtres

---

## 7. Questions ouvertes

| Question | Options | Décision |
|----------|---------|----------|
| Migration données existantes ? | Oui / Non | À discuter |
| Garder l'ancien schema en parallèle ? | Oui / Non | À discuter |
| Interactions GetSales - import auto ? | Oui / Manuel | À discuter |

---

*Document créé le 2025-12-22*
