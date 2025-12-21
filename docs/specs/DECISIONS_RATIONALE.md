# Décisions d'architecture - Séparation Companies/Contacts

Ce document explique les décisions clés prises dans la spec et leur rationale.

---

## 🎯 Décision 1: SIREN optionnel (nullable)

### Décision
```sql
companies.siren TEXT,  -- NULL autorisé
```

### Rationale

**Pourquoi:**
- Support entreprises **étrangères** (US, UK, etc.) sans équivalent SIREN
- Support contacts sans info entreprise confirmée (enrichissement progressif)
- Flexibilité pour imports GetSales (souvent pas de SIREN)

**Alternative rejetée:**
- `siren TEXT NOT NULL` + table séparée `foreign_companies`
  - ❌ Complexifie inutilement (2 tables à interroger)
  - ❌ Logique métier fragmentée

**Contrainte mise en place:**
```sql
CREATE UNIQUE INDEX idx_companies_siren_unique
ON companies(siren) WHERE siren IS NOT NULL;
```
→ Garantit unicité SIREN quand présent, permet NULL

---

## 🎯 Décision 2: SIRET multiples = liste CSV

### Décision
```sql
companies.siret_list TEXT,  -- "12345678900001,12345678900002"
```

### Rationale

**Pour (retenu):**
- ✅ Simple à implémenter
- ✅ Couvre 95% des cas d'usage (traçabilité, recherche)
- ✅ Pas de complexité relationnelle
- ✅ Facile à parser en Python: `siret_list.split(',')`

**Contre:**
- ❌ Pas d'adresse individuelle par établissement
- ❌ Pas de recherche SQL optimale (LIKE au lieu de =)

**Alternative considérée:**
Table `establishments`:
```sql
CREATE TABLE establishments (
    id INTEGER PRIMARY KEY,
    company_id INTEGER,
    siret TEXT UNIQUE,
    address TEXT,
    is_headquarters INTEGER
);
```

**Pourquoi rejetée (pour l'instant):**
- Overkill pour MVP
- Ajoute complexité jointures
- Cas d'usage réels limités (on prospecte rarement par établissement spécifique)

**Évolution future:**
Si besoin de gérer finement les établissements (ex: prospection magasins individuels), migrer vers table séparée.

---

## 🎯 Décision 3: company_id optionnel sur contacts

### Décision
```sql
contacts.company_id INTEGER,  -- NULL autorisé
FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL
```

### Rationale

**Cas d'usage NULL:**
1. **Freelances** (pas d'entreprise)
2. **Enrichissement progressif** (contact importé avant identification entreprise)
3. **Contacts personnels** (networking hors prospection)

**Alternative rejetée:**
- `company_id NOT NULL` + entreprise "Unknown" par défaut
  - ❌ Pollue table companies avec fausses données
  - ❌ Complique stats entreprises

**ON DELETE SET NULL vs CASCADE:**
- `SET NULL`: Contact garde son historique si entreprise supprimée
- Évite perte data si suppression accidentelle company

---

## 🎯 Décision 4: Pas de soft delete (pour l'instant)

### Décision
```sql
companies.status TEXT DEFAULT 'active',  -- 'active', 'archived', 'duplicate'
contacts.status TEXT DEFAULT 'active',   -- 'active', 'bounced', 'unsubscribed', 'archived'
```

Simple flag status, pas de `deleted_at` timestamp.

### Rationale

**Pour flag status:**
- ✅ Simple à comprendre et requêter
- ✅ Plusieurs états possibles (pas juste deleted/not deleted)
- ✅ Suffisant pour MVP

**Contre soft delete complet:**
```sql
deleted_at TIMESTAMP,
deleted_by INTEGER
```
- Ajoute complexité (toutes les requêtes doivent filtrer `WHERE deleted_at IS NULL`)
- Cas d'usage limités pour historique exact de suppression

**Évolution future:**
Si audit trail nécessaire, ajouter table `audit_log`:
```sql
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY,
    entity_type TEXT,  -- 'company', 'contact'
    entity_id INTEGER,
    action TEXT,  -- 'created', 'updated', 'deleted'
    user_id INTEGER,
    changes TEXT,  -- JSON
    created_at TIMESTAMP
);
```

---

## 🎯 Décision 5: Stats agrégées sur companies

### Décision
```sql
companies.total_contacts INTEGER DEFAULT 0,
companies.total_messages_sent INTEGER DEFAULT 0,
companies.total_messages_received INTEGER DEFAULT 0,
companies.last_contact_interaction_at TIMESTAMP
```

Redondance de données (dénormalisation).

### Rationale

**Pour dénormalisation:**
- ✅ Performance: Pas de COUNT(*) à chaque affichage liste entreprises
- ✅ Requêtes simples: `SELECT * FROM companies ORDER BY total_contacts DESC`
- ✅ UX fluide: Tri/filtre instantané

**Contre (risque désynchronisation):**
- ❌ Faut maintenir à jour (triggers ou logique app)

**Mitigation:**
```python
def update_company_stats(company_id):
    """Recalculer stats après modification contacts"""
    stats = db.execute("""
        SELECT
            COUNT(*) as total,
            SUM(messages_sent) as sent,
            SUM(messages_received) as received,
            MAX(last_interaction_at) as last_interaction
        FROM contacts
        WHERE company_id = ?
    """, [company_id])

    db.execute("""
        UPDATE companies SET
            total_contacts = ?,
            total_messages_sent = ?,
            total_messages_received = ?,
            last_contact_interaction_at = ?
        WHERE id = ?
    """, [stats.total, stats.sent, stats.received, stats.last_interaction, company_id])
```

**Alternative rejetée:**
Vue matérialisée (pas supportée par SQLite nativement).

---

## 🎯 Décision 6: Matching hiérarchique pour GetSales

### Décision

Ordre de matching pour éviter doublons:
1. **Domain** (website)
2. **SIREN** (via enrichissement API)
3. **Nom normalisé** (fuzzy matching)

### Rationale

**1. Domain = meilleur signal:**
- Fiabilité ~90%
- Rapide (index SQL)
- Peu de faux positifs

**2. SIREN = gold standard (si dispo):**
- Fiabilité 100%
- Nécessite appel API Pappers (latence + coût)
- Fallback si domain manque

**3. Fuzzy matching = last resort:**
- Fiabilité ~70%
- Homonymes possibles
- Validation manuelle recommandée

**Implémentation:**
```python
def find_or_create_company(getsales_lead):
    domain = extract_domain(getsales_lead.get('linkedin_company_url'))

    # 1. Match domain
    if domain:
        company = db.get_company_by_website(domain)
        if company:
            return company.id

    # 2. Enrichissement SIREN
    if getsales_lead.get('company_name'):
        siren = pappers_api.search_siren(getsales_lead['company_name'])
        if siren:
            company = db.get_company_by_siren(siren)
            if company:
                return company.id

    # 3. Fuzzy matching
    normalized = normalize_company_name(getsales_lead['company_name'])
    candidates = db.search_companies_fuzzy(normalized, threshold=0.85)

    if candidates:
        # Proposer à user de valider match ou créer nouvelle
        return ask_user_confirm_match(candidates, getsales_lead)

    # 4. Créer nouvelle entreprise
    return db.create_company({
        'company_name': getsales_lead['company_name'],
        'website': domain,
        'source': 'getsales'
    })
```

---

## 🎯 Décision 7: Unicité email/linkedin sur contacts

### Décision
```sql
CREATE UNIQUE INDEX idx_contacts_email_unique
ON contacts(email) WHERE email IS NOT NULL;

CREATE UNIQUE INDEX idx_contacts_linkedin_unique
ON contacts(linkedin_url) WHERE linkedin_url IS NOT NULL;
```

### Rationale

**Pour unicité stricte:**
- ✅ Évite doublons contacts (même personne importée 2 fois)
- ✅ Simplifie matching import
- ✅ Garantit qualité data

**Gestion cas particuliers:**

**Cas 1: Contact change entreprise**
```sql
-- Ne pas créer nouveau contact, UPDATE company_id
UPDATE contacts SET company_id = ? WHERE email = ?
```

**Cas 2: Email partagé (info@, contact@)**
→ Ne pas mettre dans contacts.email, utiliser company.company_email

**Cas 3: Contact avec 2 emails**
→ Choisir email principal dans contacts.email
→ Stocker secondaire dans raw_data JSON

**Alternative rejetée:**
Permettre doublons emails:
- ❌ Complique matching
- ❌ Risque spam (envoyer 2x au même contact)
- ❌ Incohérence stats

---

## 🎯 Décision 8: raw_data JSON pour flexibilité

### Décision
```sql
companies.raw_data TEXT,  -- JSON brut sources
contacts.raw_data TEXT
```

### Rationale

**Pour stockage JSON:**
- ✅ Conserve données originales complètes (audit)
- ✅ Permet enrichissements futurs sans migration schema
- ✅ Facilite debug (voir payload API original)

**Exemple:**
```json
// companies.raw_data
{
  "pappers": {
    "capital": 500000,
    "date_creation": "2010-01-15",
    "tva_number": "FR12345678900",
    "dirigeants": [...]
  },
  "hubspot": {
    "industry": "Education",
    "hs_createdate": "2024-01-01",
    "custom_fields": {...}
  }
}

// contacts.raw_data
{
  "getsales": {
    "messages": [...],
    "flows": [...],
    "profile_picture": "https://...",
    "skills": ["Sales", "Marketing"]
  }
}
```

**Requêtage JSON (SQLite 3.38+):**
```sql
-- Extraire champ JSON
SELECT
    company_name,
    json_extract(raw_data, '$.pappers.capital') as capital
FROM companies
WHERE json_extract(raw_data, '$.pappers.capital') > 100000;
```

**Alternative rejetée:**
Créer colonne pour chaque champ possible:
- ❌ Schema rigide
- ❌ Migrations fréquentes
- ❌ Beaucoup de NULL

---

## 🎯 Décision 9: Pas de table history (pour MVP)

### Décision

Pas de table `company_contacts_history` dans v1.

### Rationale

**Cas d'usage history:**
- Tracker changements de poste d'un contact
- "Jean Dupont était VP Sales chez Stripe, maintenant CEO chez StartupX"

**Pourquoi différé:**
- Complexité ajoutée (logique update, queries)
- Cas d'usage rare en prospection B2B (on suit contacts actuels, pas historiques postes)
- Peut être implémenté plus tard sans casser existant

**Implémentation future si besoin:**
```sql
CREATE TABLE company_contacts_history (
    id INTEGER PRIMARY KEY,
    contact_id INTEGER NOT NULL,
    company_id INTEGER NOT NULL,
    job_title TEXT,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    is_current INTEGER DEFAULT 0,
    FOREIGN KEY (contact_id) REFERENCES contacts(id),
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- Trigger sur UPDATE contacts.company_id
CREATE TRIGGER archive_old_company
AFTER UPDATE OF company_id ON contacts
WHEN OLD.company_id IS NOT NULL AND NEW.company_id != OLD.company_id
BEGIN
    INSERT INTO company_contacts_history (
        contact_id, company_id, job_title,
        started_at, ended_at, is_current
    ) VALUES (
        OLD.id, OLD.company_id, OLD.job_title,
        NULL, CURRENT_TIMESTAMP, 0
    );
END;
```

---

## 🎯 Décision 10: Migration avec vue de compatibilité

### Décision

Créer vue `unified_contacts_legacy` reproduisant ancienne structure.

### Rationale

**Pour migration progressive:**
- ✅ Code legacy continue de fonctionner pendant migration
- ✅ Tests peuvent tourner sur ancienne et nouvelle structure
- ✅ Rollback facile si problème

**Exemple:**
```python
# Ancien code (continue de fonctionner)
contacts = db.execute("SELECT * FROM unified_contacts WHERE email = ?", [email])

# Nouveau code
contact = db.get_contact_by_email(email)
company = db.get_company(contact.company_id) if contact.company_id else None
```

**Timeline:**
1. **Semaine 1-2:** Migration DB + création vue
2. **Semaine 3-4:** Adapter modules (ContactManager, HubSpotClient)
3. **Semaine 5:** Adapter pages Streamlit
4. **Semaine 6:** Tests E2E, validation
5. **Semaine 7:** Suppression vue legacy

**Risque:**
Si vue garde trop longtemps → technique debt

**Mitigation:**
- Ajouter `TODO: Remove legacy view by 2025-02-28` dans code
- Monitoring: Log warning si vue utilisée en production

---

## 📊 Tableau récapitulatif décisions

| # | Décision | Rationale | Alternative rejetée |
|---|----------|-----------|---------------------|
| 1 | SIREN nullable | Support international | Table foreign_companies séparée |
| 2 | SIRET liste CSV | Simplicité MVP | Table establishments |
| 3 | company_id nullable | Freelances, enrichissement progressif | Entreprise "Unknown" par défaut |
| 4 | Status flags | Simple, plusieurs états | Soft delete (deleted_at) |
| 5 | Stats agrégées | Performance affichage | Calcul à la volée (COUNT) |
| 6 | Matching hiérarchique | Éviter doublons GetSales | Match nom uniquement |
| 7 | Unicité email/LinkedIn | Qualité data | Autoriser doublons |
| 8 | raw_data JSON | Flexibilité, audit | Colonnes pour chaque champ |
| 9 | Pas de history (v1) | YAGNI, simplifier MVP | Table history immédiate |
| 10 | Vue compatibilité | Migration progressive | Big bang migration |

---

## 🔮 Évolutions futures envisagées

### Court terme (3-6 mois)
- [ ] Fonction merge companies (dédoublonnage semi-auto)
- [ ] Enrichissement automatique SIREN via domain (API)
- [ ] Dashboard analytics par entreprise

### Moyen terme (6-12 mois)
- [ ] Table `establishments` si besoin multi-sites
- [ ] Table `company_contacts_history` si besoin tracking carrière
- [ ] Audit log complet (qui a modifié quoi quand)

### Long terme (12+ mois)
- [ ] Machine learning matching entreprises (réduire doublons)
- [ ] Scoring qualité data (complétude, fraîcheur)
- [ ] Graph de relations (contacts qui ont travaillé ensemble)

---

**Dernière mise à jour:** 2025-12-21
**Prochaine revue:** Après implémentation Phase 1 (migration DB)
