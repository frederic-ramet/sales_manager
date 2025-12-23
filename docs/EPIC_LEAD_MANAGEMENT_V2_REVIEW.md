# Epic Review - Lead Management V2

## Statut Global: 98% Complete

Date: 2024-12-23

---

## Pipeline Implémenté

```
Import (CSV/HubSpot/SIRENE) → Clean (Dedup/Normalize/Validate) → Enrich (SIRENE/Pappers) → Sync (HubSpot)
```

---

## Phases Complétées

### Phase 1: Schema V2 + Data Managers ✅
- `database/schema_v2.sql` - Nouveau schéma (companies, contacts, interactions)
- `database/init_db_v2.py` - Initialisation base
- `modules/lead_scraper/company_manager_v2.py` - CRUD + matching + dedup + merge
- `modules/lead_scraper/contact_manager_v2.py` - CRUD + matching + dedup
- `modules/lead_scraper/interaction_manager.py` - Historique interactions

### Phase 2: Import CSV ✅
- `modules/lead_scraper/csv_importer_v2.py`
- Auto-détection colonnes
- Mapping FullEnrich, Salesbot, exports HubSpot
- Mode preview

### Phase 3: Data Cleaning ✅
- `modules/lead_scraper/data_cleaner.py`
- Normalisation (noms, emails, phones, SIREN, LinkedIn)
- Validation (format email, SIREN Luhn, etc.)
- Détection doublons
- **MX Check validation** (vérification enregistrements MX des domaines)

### Phase 4: Sync HubSpot (Local → HubSpot) ✅
- `modules/lead_scraper/hubspot_sync_v2.py`
- One-way sync: Local → HubSpot
- Création/màj companies et contacts
- Associations contact-company

### Phase 5: Enrichissement ✅
- `modules/lead_scraper/enrichment_service.py`
- Pappers API (dirigeants, CA, effectifs)
- SIRENE API (adresse, APE)
- Batch enrichment avec progress

### Phase 6: Dashboard UI ✅
- `pages/4_📊_Pipeline_Leads.py` - Interface 5 onglets
- Vue d'ensemble avec stats pipeline
- Recherche avancée avec filtres

### Phase 7: Import HubSpot (HubSpot → Local) ✅
- `modules/lead_scraper/hubspot_import_v2.py`
- Import Companies via API HubSpot
- Import Contacts via API HubSpot
- Import Engagements → Interactions
- Matching intelligent (éviter doublons)
- Conservation hubspot_company_id / hubspot_contact_id pour sync bidirectionnel
- UI intégrée dans onglet Import

### Phase 8: Import SIRENE (Recherche) ✅
- `modules/lead_scraper/sirene_search.py`
- Recherche multi-critères (nom, département, secteur NAF, effectif)
- API gratuite: https://recherche-entreprises.api.gouv.fr
- Sélection bulk avec checkboxes
- Import sélection vers base locale
- UI intégrée dans onglet Import

### Phase 9: Bulk Deduplication UI ✅
- Onglet Clean avec actions groupées
- Checkbox "Tout sélectionner"
- AUTO-MERGE: garde automatiquement le record avec le plus de données
- HOMONYMES: marquer les contacts comme homonymes
- Actions individuelles par groupe conservées

### Phase 10: Enrichment UI - Sélection manuelle ✅
- Mode "Sélection manuelle" avec liste d'entreprises
- Filtres: recherche, statut enrichissement, taille
- Checkbox sélection multiple + "Tout sélectionner"
- Choix source: SIRENE (gratuit) ou Pappers (payant)
- Enrichissement uniquement sur sélection
- Mode "Batch automatique" conservé

---

## Tâches Restantes

### Import GetSales ❌
**Description:** Intégrer l'import GetSales existant avec Schema V2
- Module existant : `modules/getsales/` (getsales_client.py, sync_service.py)
- Adapter pour utiliser CompanyManagerV2 / ContactManagerV2
- Importer messages → table `interactions`
- Conserver getsales_uuid pour tracking

**Fichiers à adapter:** `modules/getsales/sync_service.py`

---

### Enrichissement LinkedIn ❌
**Description:** Enrichir les contacts via LinkedIn (scraping ou API)
- Récupérer infos profil LinkedIn (headline, experience, skills)
- Mettre à jour job_title, seniority, department
- Attention: respect des ToS LinkedIn

**Note:** Complexe légalement, à évaluer priorité

---

### Sync Bidirectionnel ❌
**Description:** Détecter les modifications dans HubSpot et les rapatrier
- Comparaison timestamps updated_at
- Gestion des conflits

---

## Parcours Utilisateur Cible ✅

```
1. [Import HubSpot] → Récupère base existante (companies, contacts, engagements) ✅
2. [Import CSV]     → Ajoute nouveaux leads (FullEnrich, Salesbot) ✅
3. [Import SIRENE]  → Recherche et import nouvelles cibles ✅
4. [Clean]          → Déduplique (bulk), normalise, valide (MX check) ✅
5. [Enrich]         → Enrichit via Pappers/SIRENE (sélection manuelle) ✅
6. [Sync]           → Pousse vers HubSpot ✅
```

---

## Fichiers Créés/Modifiés

```
database/
  schema_v2.sql
  init_db_v2.py

modules/lead_scraper/
  company_manager_v2.py
  contact_manager_v2.py
  interaction_manager.py
  csv_importer_v2.py
  data_cleaner.py          # + MX Check
  hubspot_sync_v2.py
  hubspot_import_v2.py     # NEW - Import depuis HubSpot
  enrichment_service.py
  sirene_search.py         # NEW - Recherche SIRENE

pages/
  4_📊_Pipeline_Leads.py   # UI complète 5 onglets

scripts/
  migrate_to_v2.py
```

---

## Prochaine Action

Le pipeline Lead Management V2 est fonctionnel à 98%.

Tâches optionnelles restantes:
1. **Import GetSales** - Intégrer avec le pipeline V2
2. **Sync Bidirectionnel** - Rapatrier les modifications HubSpot
3. **Enrichissement LinkedIn** - À évaluer (légal)
