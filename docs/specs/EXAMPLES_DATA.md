# Exemples de données - Architecture Companies/Contacts

Ce document illustre avec des exemples concrets comment les données sont structurées dans la nouvelle architecture.

---

## Exemple 1: Entreprise française avec SIREN

### Table `companies`

| id | uuid | siren | siret_list | company_name | ape_code | city | employee_range | source | total_contacts |
|----|------|-------|------------|--------------|----------|------|----------------|--------|----------------|
| 1 | abc-123 | 123456789 | 12345678900001,12345678900015 | ESCP Business School | 8542Z | Paris | 51-200 | sirene | 3 |

### Table `contacts`

| id | company_id | firstname | lastname | email | job_title | linkedin_url | source |
|----|------------|-----------|----------|-------|-----------|--------------|--------|
| 1 | 1 | Jean | Dupont | j.dupont@escp.eu | Directeur Marketing | linkedin.com/in/jdupont | pappers |
| 2 | 1 | Marie | Martin | m.martin@escp.eu | Responsable Communication | linkedin.com/in/mmartin | pappers |
| 3 | 1 | Pierre | Durand | p.durand@escp.eu | Professeur | linkedin.com/in/pdurand | getsales |

**Avantage:** Les infos ESCP (adresse, SIREN, APE) sont stockées **1 seule fois**, pas 3.

---

## Exemple 2: Entreprise étrangère (sans SIREN)

### Table `companies`

| id | uuid | siren | company_name | website | country | employee_range | source | total_contacts |
|----|------|-------|--------------|---------|---------|----------------|--------|----------------|
| 2 | def-456 | NULL | Stripe Inc | stripe.com | US | 1001-5000 | getsales | 2 |

### Table `contacts`

| id | company_id | firstname | lastname | email | job_title | source |
|----|------------|-----------|----------|-------|-----------|--------|
| 4 | 2 | John | Doe | john@stripe.com | Sales Manager | getsales |
| 5 | 2 | Jane | Smith | jane@stripe.com | Account Executive | getsales |

**Note:** `siren = NULL` car entreprise US, matching fait par `website = stripe.com`.

---

## Exemple 3: Contact sans entreprise connue

### Table `contacts`

| id | company_id | firstname | lastname | email | job_title | linkedin_url | source |
|----|------------|-----------|----------|-------|-----------|--------------|--------|
| 6 | NULL | Alice | Freelance | alice@freelance.com | Consultante Indépendante | linkedin.com/in/alice | manual |

**Cas d'usage:**
- Freelances
- Contacts dont on ne connaît pas l'entreprise
- Contacts en cours d'enrichissement

---

## Exemple 4: Scénario complet - Import GetSales

### Étape 1: GetSales retourne un lead

```json
{
  "uuid": "gs-789",
  "first_name": "Thomas",
  "last_name": "Bernard",
  "email": "t.bernard@leboncoin.fr",
  "company_name": "Leboncoin",
  "position": "VP Product",
  "domain": "leboncoin.fr",
  "linkedin": "linkedin.com/in/tbernard"
}
```

### Étape 2: Matching entreprise

**Recherche 1 - Par domain:**
```sql
SELECT id FROM companies WHERE website LIKE '%leboncoin.fr%';
-- Résultat: NULL (pas trouvé)
```

**Recherche 2 - Enrichissement Pappers via nom:**
```python
pappers.search("Leboncoin")
# Retourne: SIREN 521016632
```

**Recherche 3 - Par SIREN:**
```sql
SELECT id FROM companies WHERE siren = '521016632';
-- Résultat: 15 (trouvé!)
```

### Étape 3: Insertion contact

```sql
INSERT INTO contacts (
    uuid, company_id, firstname, lastname, email, job_title,
    linkedin_url, getsales_uuid, source
) VALUES (
    'contact-uuid-123',
    15,  -- company_id de Leboncoin
    'Thomas',
    'Bernard',
    't.bernard@leboncoin.fr',
    'VP Product',
    'linkedin.com/in/tbernard',
    'gs-789',
    'getsales'
);
```

### Résultat final

**Table `companies` (ligne existante enrichie):**

| id | siren | company_name | website | total_contacts |
|----|-------|--------------|---------|----------------|
| 15 | 521016632 | Leboncoin | leboncoin.fr | 8 → 9 |

**Table `contacts` (nouvelle ligne):**

| id | company_id | firstname | lastname | email | job_title | getsales_uuid |
|----|------------|-----------|----------|-------|-----------|---------------|
| 142 | 15 | Thomas | Bernard | t.bernard@leboncoin.fr | VP Product | gs-789 |

**Avantage:** Contact automatiquement lié à l'entreprise existante, pas de doublon Leboncoin.

---

## Exemple 5: Établissements multiples (SIRET)

### Table `companies`

| id | siren | siret_list | company_name | address | city |
|----|-------|------------|--------------|---------|------|
| 20 | 552032534 | 55203253400012,55203253400045,55203253400078 | McDonald's France | 1 Rue Gustave Eiffel | Guyancourt |

**Détail SIRET:**
- `55203253400012` - Siège social (Guyancourt)
- `55203253400045` - Restaurant Paris 15e
- `55203253400078` - Restaurant Lyon Part-Dieu

**Format:**
- Liste séparée par virgules
- Premier SIRET = établissement principal (siège)
- Adresse dans `companies.address` = adresse du siège

**Limitation actuelle:**
- Pas d'adresse individuelle par établissement
- Si besoin futur → créer table `establishments`

**Cas d'usage actuel:**
- Permet de stocker tous les SIRET pour vérification/enrichissement
- Recherche par n'importe quel SIRET de la liste:
  ```sql
  SELECT * FROM companies
  WHERE siret_list LIKE '%55203253400045%';
  ```

---

## Exemple 6: Sync HubSpot avec associations

### Avant sync

**Table `companies`:**

| id | siren | company_name | hubspot_company_id |
|----|-------|--------------|---------------------|
| 1 | 123456789 | ESCP Business School | NULL |

**Table `contacts`:**

| id | company_id | firstname | lastname | hubspot_contact_id |
|----|------------|-----------|----------|---------------------|
| 1 | 1 | Jean | Dupont | NULL |

### Après sync (1ère exécution)

**Table `companies`:**

| id | siren | company_name | hubspot_company_id | synced_to_hubspot | last_sync_hubspot |
|----|-------|--------------|---------------------|-------------------|-------------------|
| 1 | 123456789 | ESCP Business School | **8765432** | 1 | 2025-12-21 10:30 |

**Table `contacts`:**

| id | company_id | firstname | lastname | hubspot_contact_id | synced_to_hubspot | last_sync_hubspot |
|----|------------|-----------|----------|---------------------|-------------------|-------------------|
| 1 | 1 | Jean | Dupont | **1234567** | 1 | 2025-12-21 10:30 |

**Dans HubSpot:**
- Company créée avec ID `8765432`
- Contact créé avec ID `1234567`
- **Association** créée: Contact `1234567` → Company `8765432`

**Requête SQL pour sync:**
```sql
-- Récupérer contact avec info company
SELECT
    c.id,
    c.firstname,
    c.lastname,
    c.email,
    comp.hubspot_company_id
FROM contacts c
LEFT JOIN companies comp ON c.company_id = comp.id
WHERE c.synced_to_hubspot = 0;
```

---

## Exemple 7: Dédoublonnage entreprise

### Scénario: 2 imports créent la même entreprise

**Import 1 (GetSales):**
```sql
INSERT INTO companies (company_name, website, source)
VALUES ('ESCP BS', 'escp.eu', 'getsales');
-- id = 100
```

**Import 2 (SIRENE):**
```sql
INSERT INTO companies (siren, company_name, source)
VALUES ('123456789', 'ESCP Business School', 'sirene');
-- id = 101
```

**Détection doublon:**
```sql
SELECT
    c1.id as id1,
    c2.id as id2,
    c1.company_name,
    c2.company_name,
    c1.website,
    c2.siren
FROM companies c1
JOIN companies c2 ON (
    c1.id < c2.id
    AND (
        c1.website = c2.website
        OR c1.siren = c2.siren
        OR LOWER(c1.company_name) = LOWER(c2.company_name)
    )
);
```

**Résultat:**
| id1 | id2 | company_name (1) | company_name (2) | website | siren |
|-----|-----|------------------|------------------|---------|-------|
| 100 | 101 | ESCP BS | ESCP Business School | escp.eu | 123456789 |

**Fusion (fonction à implémenter):**
```sql
-- 1. Migrer tous les contacts vers company maître (101)
UPDATE contacts SET company_id = 101 WHERE company_id = 100;

-- 2. Enrichir company maître avec données manquantes
UPDATE companies SET
    website = 'escp.eu',  -- de company 100
    updated_at = CURRENT_TIMESTAMP
WHERE id = 101;

-- 3. Marquer company 100 comme dupliqué
UPDATE companies SET status = 'duplicate' WHERE id = 100;

-- 4. Mettre à jour stats
UPDATE companies SET
    total_contacts = (SELECT COUNT(*) FROM contacts WHERE company_id = 101)
WHERE id = 101;
```

---

## Exemple 8: Requêtes courantes

### Toutes les entreprises avec leurs contacts

```sql
SELECT
    comp.id,
    comp.company_name,
    comp.siren,
    comp.city,
    comp.total_contacts,
    COUNT(c.id) as contacts_count_real,
    GROUP_CONCAT(c.firstname || ' ' || c.lastname) as contacts
FROM companies comp
LEFT JOIN contacts c ON c.company_id = comp.id
GROUP BY comp.id
ORDER BY comp.total_contacts DESC;
```

### Contacts sans entreprise

```sql
SELECT
    id,
    firstname,
    lastname,
    email,
    job_title,
    source
FROM contacts
WHERE company_id IS NULL;
```

### Entreprises enrichies récemment

```sql
SELECT
    company_name,
    siren,
    enriched_at,
    enrichment_source,
    total_contacts
FROM companies
WHERE enriched_at > datetime('now', '-7 days')
ORDER BY enriched_at DESC;
```

### Top 10 entreprises par prospection

```sql
SELECT
    company_name,
    prospection_status,
    total_contacts,
    total_messages_sent,
    total_messages_received,
    last_contact_interaction_at
FROM companies
WHERE prospection_status IN ('in_progress', 'contacted')
ORDER BY total_messages_sent DESC
LIMIT 10;
```

### Contacts d'une entreprise spécifique

```sql
SELECT
    c.firstname,
    c.lastname,
    c.email,
    c.job_title,
    c.linkedin_url,
    c.prospection_status,
    c.last_interaction_at
FROM contacts c
JOIN companies comp ON c.company_id = comp.id
WHERE comp.siren = '123456789'
ORDER BY c.created_at DESC;
```

### Stats par source

```sql
SELECT
    source,
    COUNT(*) as total_companies,
    SUM(total_contacts) as total_contacts,
    AVG(total_contacts) as avg_contacts_per_company
FROM companies
WHERE status = 'active'
GROUP BY source
ORDER BY total_companies DESC;
```

---

## Exemple 9: Vue simplifiée (compatibilité legacy)

Pour faciliter la migration progressive du code, créer une vue qui reproduit l'ancienne structure:

```sql
CREATE VIEW unified_contacts_legacy AS
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
    c.source as contact_source,
    c.created_at,
    c.updated_at,
    c.status as contact_status,
    -- Champs entreprise (NULL si pas de company_id)
    comp.siren,
    comp.siret_list,
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
    comp.source as company_source
FROM contacts c
LEFT JOIN companies comp ON c.company_id = comp.id;
```

**Utilisation:**
```sql
-- Code legacy peut continuer à fonctionner temporairement
SELECT * FROM unified_contacts_legacy WHERE email = 'test@example.com';
```

**⚠️ À supprimer** une fois migration code complète.

---

## Résumé des patterns

| Pattern | Description | Exemple |
|---------|-------------|---------|
| **1 Company → N Contacts** | Relation principale | ESCP → 535 contacts |
| **Contact sans company** | `company_id = NULL` | Freelances, enrichissement en cours |
| **Entreprise sans SIREN** | `siren = NULL` | Entreprises étrangères (Stripe US) |
| **Multiples SIRET** | Liste CSV | McDonald's avec 50 restaurants |
| **Matching intelligent** | domain → SIREN → nom | Évite doublons GetSales |
| **Dédoublonnage** | Fusion companies + migration contacts | ESCP BS + ESCP Business School |
| **Sync HubSpot** | Association contact ↔ company | Préserve structure dans HubSpot |
