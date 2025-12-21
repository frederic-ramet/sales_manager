-- Migration 001: Create companies table
-- Date: 2025-12-21
-- Description: Table des entreprises (séparée des contacts)

CREATE TABLE IF NOT EXISTS companies (
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

-- === INDEX ===
CREATE INDEX IF NOT EXISTS idx_companies_siren ON companies(siren);
CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(company_name);
CREATE INDEX IF NOT EXISTS idx_companies_country ON companies(country);
CREATE INDEX IF NOT EXISTS idx_companies_campaign ON companies(campaign_id);
CREATE INDEX IF NOT EXISTS idx_companies_hubspot ON companies(hubspot_company_id);
CREATE INDEX IF NOT EXISTS idx_companies_status ON companies(status);
CREATE INDEX IF NOT EXISTS idx_companies_source ON companies(source);
CREATE INDEX IF NOT EXISTS idx_companies_created ON companies(created_at);
CREATE INDEX IF NOT EXISTS idx_companies_website ON companies(website);
CREATE INDEX IF NOT EXISTS idx_companies_city ON companies(city);
CREATE INDEX IF NOT EXISTS idx_companies_postal_code ON companies(postal_code);

-- === CONTRAINTES UNICITÉ ===
-- SIREN unique si non NULL (évite doublons entreprises françaises)
CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_siren_unique
ON companies(siren) WHERE siren IS NOT NULL;

-- HubSpot company ID unique si non NULL
CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_hubspot_unique
ON companies(hubspot_company_id) WHERE hubspot_company_id IS NOT NULL;
