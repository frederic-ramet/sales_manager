# Epic Review - Lead Management V2

## Statut Global: 85% Complete

Date: 2024-12-23

---

## Pipeline Implémenté

```
Import → Clean → Enrich → Sync (one-way)
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

---

## Tâches Restantes

### Import HubSpot (HubSpot → Local) ❌ PRIORITAIRE
**Description:** Importer les données existantes depuis HubSpot vers la base locale
- Récupérer Companies via API HubSpot
- Récupérer Contacts via API HubSpot
- Récupérer Engagements → Interactions
- Matching intelligent (éviter doublons si données déjà présentes)
- Conserver hubspot_company_id / hubspot_contact_id pour sync bidirectionnel

**Fichier à créer:** `modules/lead_scraper/hubspot_import_v2.py`

**UI:** Mettre à jour onglet Import dans Pipeline_Leads.py

---

### Import GetSales ❌
**Description:** Intégrer l'import GetSales existant avec Schema V2
- Module existant : `modules/getsales/` (getsales_client.py, sync_service.py)
- Adapter pour utiliser CompanyManagerV2 / ContactManagerV2
- Importer messages → table `interactions`
- Conserver getsales_uuid pour tracking

**Fichiers à adapter:** `modules/getsales/sync_service.py`

---

### Bulk Deduplication UI ❌
**Description:** Améliorer l'UI de déduplication pour traitement rapide
- Checkbox pour sélectionner plusieurs groupes (ou "Tout sélectionner")
- Actions groupées : "Fusionner sélection", "Marquer homonymes"
- Auto-merge : garde automatiquement le record avec le plus de données remplies

**Fichier:** `pages/4_📊_Pipeline_Leads.py` (onglet Clean)

---

### Enrichment UI - Sélection manuelle ❌
**Description:** Permettre sélection manuelle des entreprises à enrichir
- Recherche/filtre pour trouver les entreprises
- Checkbox pour sélection multiple (ou "Tout sélectionner")
- Choix de la source : SIRENE (défaut, gratuit), Pappers (payant, plus complet)
- Enrichissement sur sélection uniquement

**Fichier:** `pages/4_📊_Pipeline_Leads.py` (onglet Enrich)

---

### Import SIRENE (Recherche) ❌
**Description:** Rechercher et importer de nouvelles entreprises cibles depuis SIRENE

**Critères de recherche :**
- Nom / mot-clé
- Code APE / secteur d'activité
- Localisation (ville, département, région)
- Tranche d'effectif
- Forme juridique (SAS, SARL, SA...)

**Flow UI :**
1. Formulaire de recherche multi-critères
2. Affichage résultats paginés avec preview
3. Checkbox sélection (bulk)
4. [IMPORTER SÉLECTION] → crée dans companies avec source='sirene'

**API :** https://recherche-entreprises.api.gouv.fr (gratuite, pas de clé)

**Fichier à créer :** `modules/lead_scraper/sirene_search.py`
**UI :** Onglet Import → source "SIRENE"

---

### Enrichissement LinkedIn ❌
**Description:** Enrichir les contacts via LinkedIn (scraping ou API)
- Récupérer infos profil LinkedIn (headline, experience, skills)
- Mettre à jour job_title, seniority, department
- Attention: respect des ToS LinkedIn

**Note:** Complexe légalement, à évaluer priorité

---

### Validation Email MX Check ❌
**Description:** Vérification avancée des emails
- Check MX record du domaine
- Détecter emails invalides avant sync HubSpot
- Optionnel car plus lent

**Fichier:** `modules/lead_scraper/data_cleaner.py` (ajouter option)

---

### Sync Bidirectionnel ❌
**Description:** Détecter les modifications dans HubSpot et les rapatrier
- Comparaison timestamps updated_at
- Gestion des conflits

---

## Parcours Utilisateur Cible

```
1. [Import HubSpot] → Récupère base existante (companies, contacts, engagements)
2. [Import CSV]     → Ajoute nouveaux leads (FullEnrich, Salesbot)
3. [Clean]          → Déduplique, normalise, valide
4. [Enrich]         → Enrichit via Pappers/SIRENE
5. [Sync]           → Pousse vers HubSpot
```

---

## Fichiers Créés

```
database/
  schema_v2.sql
  init_db_v2.py

modules/lead_scraper/
  company_manager_v2.py
  contact_manager_v2.py
  interaction_manager.py
  csv_importer_v2.py
  data_cleaner.py
  hubspot_sync_v2.py
  enrichment_service.py

pages/
  4_📊_Pipeline_Leads.py

scripts/
  migrate_to_v2.py
```

---

## Prochaine Action

**Implémenter Import HubSpot** pour permettre le parcours utilisateur complet.
