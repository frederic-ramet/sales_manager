-- ============================================================================
-- SCHEMA V2 - Lead Management Pipeline
-- ============================================================================
-- Version: 2.0
-- Date: 2025-12-22
-- Description: Nouveau schema pour pipeline Import → Clean → Enrich → Sync
-- ============================================================================

-- ============================================================================
-- TABLE: COMPANIES
-- ============================================================================
-- Entreprises avec données enrichies
-- Clés de matching: SIREN (priorité 1), Domain (priorité 2), Name+City (priorité 3)

CREATE TABLE IF NOT EXISTS companies (
    -- Identifiants
    uuid TEXT PRIMARY KEY,
    siren TEXT,                          -- Clé de matching #1 (9 chiffres)
    siret TEXT,                          -- SIRET complet (14 chiffres)

    -- Identifiants externes
    hubspot_company_id TEXT,

    -- Informations entreprise
    name TEXT NOT NULL,
    domain TEXT,                         -- Clé de matching #2 (ex: acme.fr)
    legal_form TEXT,                     -- SAS, SARL, SA, EURL...

    -- Localisation siège
    hq_address TEXT,
    hq_city TEXT,
    hq_state TEXT,                       -- Région
    hq_postal_code TEXT,
    hq_country TEXT DEFAULT 'France',

    -- Activité
    ape_code TEXT,                       -- Code NAF/APE (ex: 6201Z)
    ape_label TEXT,                      -- Libellé APE
    industry TEXT,                       -- Secteur (depuis CSV, plus générique)
    description TEXT,

    -- Taille & Finance
    size TEXT,                           -- "1-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000", "5001-10000", "10001+"
    size_exact INTEGER,                  -- Nombre exact si connu
    revenue REAL,                        -- CA en euros
    revenue_range TEXT,                  -- "< 1M", "1-10M", "10-50M", "50-100M", "> 100M"

    -- Investissement (si startup)
    investment_stage TEXT,               -- Seed, Series A, B, C, Venture Round...
    investment_amount REAL,
    investment_date DATE,
    lead_investor TEXT,

    -- Tech & Fondation
    founded_date DATE,
    technology_used TEXT,                -- Technologies utilisées (texte libre ou JSON)

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

    -- Sync HubSpot
    synced_to_hubspot INTEGER DEFAULT 0,
    last_sync_hubspot TIMESTAMP,

    -- V2.1: Classification & Attribution
    tier TEXT DEFAULT 'unclassified',    -- 'tier_1', 'tier_2', 'tier_3', 'excluded', 'unclassified'
    owner TEXT,                          -- Email/nom de l'apporteur d'affaires
    source_tag TEXT,                     -- Tag business provenance (ex: "Salon VivaTech 2024")

    -- Statistiques (calculées)
    total_contacts INTEGER DEFAULT 0,
    total_engagements INTEGER DEFAULT 0
);

-- Index companies
CREATE INDEX IF NOT EXISTS idx_companies_siren ON companies(siren);
CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain);
CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name);
CREATE INDEX IF NOT EXISTS idx_companies_hubspot ON companies(hubspot_company_id);
CREATE INDEX IF NOT EXISTS idx_companies_status ON companies(status);
CREATE INDEX IF NOT EXISTS idx_companies_source ON companies(source);
CREATE INDEX IF NOT EXISTS idx_companies_created ON companies(created_at);
CREATE INDEX IF NOT EXISTS idx_companies_tier ON companies(tier);
CREATE INDEX IF NOT EXISTS idx_companies_owner ON companies(owner);


-- ============================================================================
-- TABLE: CONTACTS
-- ============================================================================
-- 1 contact = 1 personne + 1 entreprise + 1 rôle
-- linkedin_url = clé pour identifier la même personne dans plusieurs sociétés
-- Clés de matching: Email (priorité 1), LinkedIn (priorité 2), Phone (priorité 3)

CREATE TABLE IF NOT EXISTS contacts (
    -- Identifiants
    uuid TEXT PRIMARY KEY,
    company_uuid TEXT,                   -- FK vers companies

    -- Identifiants externes
    hubspot_contact_id TEXT,
    getsales_uuid TEXT,

    -- Identité
    firstname TEXT,
    lastname TEXT,
    linkedin_url TEXT,                   -- Clé pour identifier même personne multi-sociétés

    -- Coordonnées
    email TEXT,                          -- Email principal (verified si possible)
    email_verified INTEGER DEFAULT 0,    -- 1 = verified, 0 = unverified
    email_secondary TEXT,                -- Email secondaire
    phone TEXT,
    mobile TEXT,

    -- Poste
    job_title TEXT,
    seniority TEXT,                      -- 'C-Level', 'VP', 'Director', 'Manager', 'Individual'
    department TEXT,                     -- 'Tech', 'Sales', 'Marketing', 'HR', 'Finance', 'Operations'

    -- Localisation contact
    city TEXT,
    state TEXT,
    country TEXT DEFAULT 'France',
    timezone TEXT,

    -- Social
    twitter_url TEXT,
    github_url TEXT,
    facebook_url TEXT,
    other_social_urls TEXT,              -- JSON pour autres réseaux

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
    merged_into TEXT,                    -- UUID du master si fusionné
    merged_at TIMESTAMP,
    homonym_group_id INTEGER,            -- Groupe d'homonymes confirmés

    -- Enrichissement
    enriched_at TIMESTAMP,
    enrichment_source TEXT,

    -- Sync HubSpot
    synced_to_hubspot INTEGER DEFAULT 0,
    last_sync_hubspot TIMESTAMP,

    -- V2.1: Qualification & Attribution
    qualification_status TEXT DEFAULT 'contact',  -- 'contact', 'lead', 'transaction'
    source_tag TEXT,                              -- Tag business provenance

    -- Statistiques (calculées)
    total_engagements INTEGER DEFAULT 0,
    last_engagement_at TIMESTAMP,

    -- Notes
    notes TEXT,

    -- Foreign key
    FOREIGN KEY (company_uuid) REFERENCES companies(uuid) ON DELETE SET NULL
);

-- Index contacts
CREATE INDEX IF NOT EXISTS idx_contacts_linkedin ON contacts(linkedin_url);
CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email);
CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(phone);
CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(company_uuid);
CREATE INDEX IF NOT EXISTS idx_contacts_hubspot ON contacts(hubspot_contact_id);
CREATE INDEX IF NOT EXISTS idx_contacts_getsales ON contacts(getsales_uuid);
CREATE INDEX IF NOT EXISTS idx_contacts_status ON contacts(status);
CREATE INDEX IF NOT EXISTS idx_contacts_source ON contacts(source);
CREATE INDEX IF NOT EXISTS idx_contacts_created ON contacts(created_at);
CREATE INDEX IF NOT EXISTS idx_contacts_qualification ON contacts(qualification_status);


-- ============================================================================
-- TABLE: ENGAGEMENTS
-- ============================================================================
-- Historique des engagements avec les contacts (GetSales, HubSpot, manuel)

CREATE TABLE IF NOT EXISTS engagements (
    -- Identifiants
    uuid TEXT PRIMARY KEY,
    contact_uuid TEXT NOT NULL,          -- FK vers contacts

    -- Identifiants externes
    hubspot_engagement_id TEXT,
    getsales_message_id TEXT,

    -- Type d'interaction
    type TEXT NOT NULL,                  -- 'message', 'email', 'call', 'meeting', 'note'
    direction TEXT,                      -- 'inbound', 'outbound'
    channel TEXT,                        -- 'linkedin', 'email', 'phone', 'in_person', 'video'

    -- Contenu
    subject TEXT,
    content TEXT,
    content_html TEXT,                   -- Contenu HTML si disponible

    -- Timing
    interaction_date TIMESTAMP NOT NULL,
    duration_minutes INTEGER,            -- Pour calls/meetings

    -- Campagne
    campaign_id TEXT,
    sequence_name TEXT,
    sequence_step INTEGER,               -- Étape dans la séquence

    -- Résultat
    outcome TEXT,                        -- 'replied', 'no_reply', 'bounced', 'interested', 'not_interested', 'meeting_booked'

    -- Métadonnées
    source TEXT NOT NULL,                -- 'getsales', 'hubspot', 'manual'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (contact_uuid) REFERENCES contacts(uuid) ON DELETE CASCADE
);

-- Index engagements
CREATE INDEX IF NOT EXISTS idx_engagements_contact ON engagements(contact_uuid);
CREATE INDEX IF NOT EXISTS idx_engagements_date ON engagements(interaction_date);
CREATE INDEX IF NOT EXISTS idx_engagements_type ON engagements(type);
CREATE INDEX IF NOT EXISTS idx_engagements_campaign ON engagements(campaign_id);
CREATE INDEX IF NOT EXISTS idx_engagements_hubspot ON engagements(hubspot_engagement_id);
CREATE INDEX IF NOT EXISTS idx_engagements_getsales ON engagements(getsales_message_id);


-- ============================================================================
-- TABLE: HOMONYM_GROUPS
-- ============================================================================
-- Groupes d'homonymes confirmés (pour éviter re-détection)

CREATE TABLE IF NOT EXISTS homonym_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,           -- 'contact' ou 'company'
    entity_uuids TEXT NOT NULL,          -- JSON array d'UUIDs
    confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_by TEXT DEFAULT 'user'     -- 'user' ou 'system'
);


-- ============================================================================
-- TABLE: SYNC_METADATA
-- ============================================================================
-- Métadonnées de synchronisation

CREATE TABLE IF NOT EXISTS sync_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_type TEXT NOT NULL,             -- 'hubspot_full', 'hubspot_incremental', 'getsales', etc.
    last_sync_date TIMESTAMP NOT NULL,
    entities_synced INTEGER DEFAULT 0,
    notes TEXT,
    UNIQUE(sync_type)
);


-- ============================================================================
-- TABLE: IMPORT_HISTORY
-- ============================================================================
-- Historique des imports

CREATE TABLE IF NOT EXISTS import_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,                -- 'csv', 'getsales', 'hubspot', 'sirene'
    source_file TEXT,                    -- Nom du fichier si CSV
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    companies_created INTEGER DEFAULT 0,
    companies_updated INTEGER DEFAULT 0,
    companies_matched INTEGER DEFAULT 0,
    contacts_created INTEGER DEFAULT 0,
    contacts_updated INTEGER DEFAULT 0,
    contacts_matched INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    errors_details TEXT,                 -- JSON des erreurs
    notes TEXT
);


-- ============================================================================
-- VUE: CONTACTS_WITH_COMPANY
-- ============================================================================
-- Vue jointe pour faciliter les requêtes

CREATE VIEW IF NOT EXISTS contacts_with_company AS
SELECT
    c.*,
    co.name as company_name,
    co.domain as company_domain,
    co.siren as company_siren,
    co.size as company_size,
    co.hq_city as company_city,
    co.industry as company_industry,
    co.hubspot_company_id
FROM contacts c
LEFT JOIN companies co ON c.company_uuid = co.uuid
WHERE c.status = 'active';


-- ============================================================================
-- VUE: PIPELINE_STATS
-- ============================================================================
-- Vue pour dashboard avec stats du pipeline

CREATE VIEW IF NOT EXISTS pipeline_stats AS
SELECT
    -- Totaux
    (SELECT COUNT(*) FROM companies WHERE status = 'active') as total_companies,
    (SELECT COUNT(*) FROM contacts WHERE status = 'active') as total_contacts,
    (SELECT COUNT(*) FROM engagements) as total_engagements,

    -- Par source
    (SELECT COUNT(*) FROM companies WHERE source = 'csv' AND status = 'active') as companies_from_csv,
    (SELECT COUNT(*) FROM companies WHERE source = 'hubspot' AND status = 'active') as companies_from_hubspot,
    (SELECT COUNT(*) FROM companies WHERE source = 'getsales' AND status = 'active') as companies_from_getsales,

    (SELECT COUNT(*) FROM contacts WHERE source = 'csv' AND status = 'active') as contacts_from_csv,
    (SELECT COUNT(*) FROM contacts WHERE source = 'hubspot' AND status = 'active') as contacts_from_hubspot,
    (SELECT COUNT(*) FROM contacts WHERE source = 'getsales' AND status = 'active') as contacts_from_getsales,

    -- Pipeline status
    (SELECT COUNT(*) FROM companies WHERE enriched_at IS NULL AND status = 'active') as companies_to_enrich,
    (SELECT COUNT(*) FROM companies WHERE synced_to_hubspot = 0 AND status = 'active') as companies_to_sync,
    (SELECT COUNT(*) FROM contacts WHERE synced_to_hubspot = 0 AND status = 'active') as contacts_to_sync,

    -- Merged/Deleted
    (SELECT COUNT(*) FROM companies WHERE status = 'merged') as companies_merged,
    (SELECT COUNT(*) FROM contacts WHERE status = 'merged') as contacts_merged;
