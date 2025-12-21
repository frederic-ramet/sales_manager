-- Migration 002: Create contacts table (new structure)
-- Date: 2025-12-21
-- Description: Table des contacts liés aux entreprises

CREATE TABLE IF NOT EXISTS contacts (
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
    getsales_flow_uuid TEXT,  -- UUID de la campagne/flow GetSales

    -- === SYNC HUBSPOT ===
    synced_to_hubspot INTEGER DEFAULT 0,
    last_sync_hubspot TIMESTAMP,

    -- === MÉTADONNÉES ===
    source TEXT NOT NULL,  -- "sirene", "getsales", "hubspot", "csv", "manual", "pappers"
    campaign_id TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Statut
    status TEXT DEFAULT 'active',  -- "active", "bounced", "unsubscribed", "archived"

    -- Notes
    notes TEXT,
    tags TEXT,
    raw_data TEXT,

    -- === CONTRAINTES ===
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL
);

-- === INDEX ===
CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(company_id);
CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email);
CREATE INDEX IF NOT EXISTS idx_contacts_linkedin ON contacts(linkedin_url);
CREATE INDEX IF NOT EXISTS idx_contacts_getsales ON contacts(getsales_uuid);
CREATE INDEX IF NOT EXISTS idx_contacts_hubspot ON contacts(hubspot_contact_id);
CREATE INDEX IF NOT EXISTS idx_contacts_campaign ON contacts(campaign_id);
CREATE INDEX IF NOT EXISTS idx_contacts_status ON contacts(status);
CREATE INDEX IF NOT EXISTS idx_contacts_source ON contacts(source);
CREATE INDEX IF NOT EXISTS idx_contacts_created ON contacts(created_at);
CREATE INDEX IF NOT EXISTS idx_contacts_firstname ON contacts(firstname);
CREATE INDEX IF NOT EXISTS idx_contacts_lastname ON contacts(lastname);

-- === CONTRAINTES UNICITÉ ===
-- Email unique si non NULL
CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_email_unique
ON contacts(email) WHERE email IS NOT NULL;

-- LinkedIn URL unique si non NULL
CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_linkedin_unique
ON contacts(linkedin_url) WHERE linkedin_url IS NOT NULL;

-- GetSales UUID unique si non NULL
CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_getsales_unique
ON contacts(getsales_uuid) WHERE getsales_uuid IS NOT NULL;

-- HubSpot contact ID unique si non NULL
CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_hubspot_unique
ON contacts(hubspot_contact_id) WHERE hubspot_contact_id IS NOT NULL;

-- === VUE DE COMPATIBILITÉ LEGACY ===
-- Permet au code legacy de continuer à fonctionner pendant la migration
CREATE VIEW IF NOT EXISTS unified_contacts_legacy AS
SELECT
    c.id,
    c.uuid,
    c.firstname,
    c.lastname,
    c.email,
    c.phone,
    c.mobile,
    c.job_title,
    c.linkedin_url,
    c.linkedin_headline,
    c.source AS contact_source,
    c.created_at,
    c.updated_at,
    c.status AS contact_status,
    c.getsales_uuid,
    c.hubspot_contact_id,
    c.synced_to_hubspot,
    c.last_sync_hubspot,
    c.prospection_status,
    c.messages_sent,
    c.messages_received,
    c.last_interaction_at,
    c.campaign_id,
    c.notes,
    c.raw_data,
    -- Champs entreprise (NULL si pas de company_id)
    comp.id AS company_id,
    comp.siren,
    comp.siret_list AS siret,
    comp.company_name,
    comp.ape_code,
    comp.ape_label,
    comp.legal_form,
    comp.address,
    comp.postal_code,
    comp.city,
    comp.region,
    comp.country,
    comp.employee_range,
    comp.revenue_range,
    comp.website,
    comp.hubspot_company_id,
    comp.source AS company_source
FROM contacts c
LEFT JOIN companies comp ON c.company_id = comp.id;
