# Spec - Pipeline V2.1

**Version**: 2.1
**Date**: 2024-12-24
**Statut**: Draft
**Basé sur**: Feedback session test Pipeline V2

---

## Contexte

Suite aux tests du Pipeline V2, plusieurs bugs critiques et améliorations ont été identifiés. Cette spec définit les corrections et évolutions pour la version 2.1.

### Décisions clés

| Question | Décision |
|----------|----------|
| Priorité | Features critiques d'abord, puis bugs |
| V1 vs V2 | Garder V1 temporairement, clean ultérieur |
| Navigation | Potentiel double header (1 page/étape) - à évaluer |
| Tier/ICP | Classification manuelle uniquement (auto = nice to have) |
| Multi-owners | 20 apporteurs, tag simple, pas de restriction accès |
| Quality Gate | Avertissements uniquement, pas de blocage |

---

## Phase 1 : Modèle de données (Critique)

### 1.1 Nouveaux champs - Table `companies`

```sql
ALTER TABLE companies ADD COLUMN tier TEXT DEFAULT 'unclassified';
-- Valeurs: 'tier_1', 'tier_2', 'tier_3', 'excluded', 'unclassified'

ALTER TABLE companies ADD COLUMN owner TEXT;
-- Email ou nom de l'apporteur d'affaires

ALTER TABLE companies ADD COLUMN source_tag TEXT;
-- Tag business de provenance (ex: "Salon VivaTech 2024")
```

### 1.2 Nouveaux champs - Table `contacts`

```sql
ALTER TABLE contacts ADD COLUMN qualification_status TEXT DEFAULT 'contact';
-- Valeurs: 'contact', 'lead', 'transaction'

ALTER TABLE contacts ADD COLUMN source_tag TEXT;
-- Tag business de provenance
```

### 1.3 Renommage table

```sql
ALTER TABLE interactions RENAME TO engagements;
-- Aligner sur terminologie HubSpot
```

### 1.4 Index

```sql
CREATE INDEX idx_companies_tier ON companies(tier);
CREATE INDEX idx_companies_owner ON companies(owner);
CREATE INDEX idx_contacts_qualification ON contacts(qualification_status);
```

---

## Phase 2 : Corrections bugs critiques

### 2.1 Bug source "manual" (Priorité: Critique)

**Problème**: Import HubSpot et GetSales affichent source "manual" au lieu de "hubspot"/"getsales"

**Fichiers à corriger**:
- `modules/lead_scraper/hubspot_import_v2.py`
- `modules/lead_scraper/getsales_import_v2.py`

**Action**: Vérifier que le paramètre `source` est bien passé lors de l'appel aux managers.

### 2.2 Bugs Enrichissement (Priorité: Critique)

| Bug | Description | Fichier |
|-----|-------------|---------|
| Compteur -1 | Sélection affiche 1 de moins | `pages/4_📊_Pipeline_Leads.py` |
| Bouton inactif | 1er clic = rien, 2ème = reload | `pages/4_📊_Pipeline_Leads.py` |
| Batch vide | Mode batch ne trouve pas les entreprises | `pages/4_📊_Pipeline_Leads.py` |

**Action**: Debug de la logique de sélection et du callback du bouton enrichir.

---

## Phase 3 : Import CSV amélioré

### 3.1 Mapping manuel des colonnes (Critique)

**Problème**: V2 n'a que le mapping automatique, V1 permettait le mapping manuel.

**UI à implémenter**:
```
┌─────────────────────────────────────────────────────────┐
│ Mapping des colonnes                                    │
├─────────────────────────────────────────────────────────┤
│ Colonne CSV          │  Champ DB           │  Action   │
│ ─────────────────────┼─────────────────────┼───────────│
│ First Name           │  contacts.firstname │  ✅ Auto  │
│ Work Direct Phone    │  [Sélectionner ▼]   │  ⚠️ Manuel│
│ # Employees          │  [Sélectionner ▼]   │  ⚠️ Manuel│
│ Technologies         │  [Sélectionner ▼]   │  ⚠️ Manuel│
│ Keywords             │  [Ignorer]          │  ❌ Skip  │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Tag source à l'import

**UI**:
```
┌─────────────────────────────────────────────────────────┐
│ Source de l'import                                      │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Salon VivaTech 2024                                 │ │
│ └─────────────────────────────────────────────────────┘ │
│ Ex: "LinkedIn Ads", "Referral Partner X", "Cold List"   │
└─────────────────────────────────────────────────────────┘
```

### 3.3 Import des engagements depuis CSV

**Colonnes à mapper**:
- `Date envoi message` → `engagements.interaction_date`
- `Commentaire` → `engagements.content`
- Type par défaut: `note`

---

## Phase 4 : Tier / ICP

### 4.1 UI Classification manuelle

**Workflow**:
1. Recherche par critères (taille, secteur, localisation, etc.)
2. Affichage liste résultats
3. Sélection multiple
4. Action "Classifier en Tier X"

**UI**:
```
┌─────────────────────────────────────────────────────────┐
│ 🎯 Classification Tier                                  │
├─────────────────────────────────────────────────────────┤
│ Filtres:                                                │
│ Taille: [11-50 ▼]  Secteur: [Tech ▼]  Ville: [Paris ▼] │
│                                                         │
│ [🔍 Rechercher]                                         │
├─────────────────────────────────────────────────────────┤
│ 45 entreprises trouvées          [☑️ Tout sélectionner] │
│                                                         │
│ ☑️ Acme Corp      | 25 emp | Tech    | Paris           │
│ ☑️ Beta SA        | 50 emp | SaaS    | Lyon            │
│ ☐ Gamma SARL     | 12 emp | Conseil | Paris           │
├─────────────────────────────────────────────────────────┤
│ 2 sélectionnées                                         │
│ [Tier 1] [Tier 2] [Tier 3] [Exclure]                   │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Affichage Tier dans les vues

- Colonne Tier dans toutes les listes entreprises
- Badge coloré: 🟢 Tier 1 | 🟡 Tier 2 | 🟠 Tier 3 | ⚫ Excluded | ⚪ Non classé
- Filtre par Tier

---

## Phase 5 : Qualification Contact

### 5.1 Workflow Contact → Lead → Transaction

| Statut | Déclencheur | Actions disponibles |
|--------|-------------|---------------------|
| `contact` | Import initial | Promouvoir en Lead |
| `lead` | Premier échange réel | Promouvoir en Transaction, Rétrograder |
| `transaction` | Besoin qualifié | Sync HubSpot Deal, Rétrograder |

### 5.2 UI

- Badge statut sur chaque contact
- Bouton "Promouvoir" avec confirmation
- Historique des changements de statut

---

## Phase 6 : Attribution / Owner

### 6.1 Champ Owner

- Texte libre (email ou nom)
- 20 apporteurs prévus
- Pas de restriction de visibilité (tous voient tout)
- Permet d'identifier les recouvrements

### 6.2 UI

- Colonne Owner dans liste entreprises
- Filtre par Owner
- Bulk assign: sélection multiple → assigner owner

---

## Phase 7 : Quality Gate Sync

### 7.1 Règles d'avertissement (non bloquantes)

| Règle | Condition warning |
|-------|-------------------|
| SIREN manquant | `companies.siren IS NULL` |
| Contact sans coordonnées | `email IS NULL AND phone IS NULL AND linkedin_url IS NULL` |
| Tier non défini | `companies.tier = 'unclassified'` |

### 7.2 UI Analyse Sync

```
┌─────────────────────────────────────────────────────────┐
│ 🔍 Analyse avant sync                                   │
├─────────────────────────────────────────────────────────┤
│ Entreprises: 45 à sync                                  │
│   ⚠️ 12 sans SIREN                                      │
│   ⚠️ 8 Tier non défini                                  │
│                                                         │
│ Contacts: 120 à sync                                    │
│   ⚠️ 5 sans coordonnées (email/tel/linkedin)            │
│                                                         │
│ Engagements: 230 à sync                                 │
│   ✅ Tous valides                                       │
├─────────────────────────────────────────────────────────┤
│ [Voir détails warnings]                                 │
│                                                         │
│ [🔄 SYNCHRONISER QUAND MÊME]                            │
└─────────────────────────────────────────────────────────┘
```

### 7.3 Sync granulaire

Options de sync séparées:
- ☑️ Entreprises
- ☑️ Contacts
- ☑️ Engagements

---

## Phase 8 : Vue Fiche Entreprise

### 8.1 Structure

```
┌─────────────────────────────────────────────────────────┐
│ 🏢 Acme Corp                          [Tier 1 🟢]       │
│ Owner: jean.dupont@genie.fr                             │
├─────────────────────────────────────────────────────────┤
│ [Infos] [Contacts (5)] [Engagements (23)] [Actions]     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ INFORMATIONS ENTREPRISE                                 │
│ ───────────────────────                                 │
│ SIREN: 123456789        Secteur: Technology             │
│ Taille: 51-200          CA: 5M€                         │
│ Adresse: 123 rue...     Ville: Paris                    │
│ Website: acme.com       LinkedIn: linkedin.com/...      │
│ APE: 6201Z              Forme: SAS                      │
│ ...                                                     │
│                                                         │
│ CONTACTS (5)                                            │
│ ───────────────────────                                 │
│ 👤 Marie Martin | CEO | marie@acme.com | Lead 🟡        │
│ 👤 Paul Durand | CTO | paul@acme.com | Contact ⚪       │
│ ...                                                     │
│                                                         │
│ ENGAGEMENTS RÉCENTS                                     │
│ ───────────────────────                                 │
│ 📧 2024-12-20 | Email envoyé à Marie Martin             │
│ 📞 2024-12-18 | Call avec Paul Durand (15min)           │
│ ...                                                     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Phase 9 : Filtres avancés

### 9.1 Nouveaux filtres recherche

| Filtre | Type |
|--------|------|
| Tier | Multi-select |
| Owner | Multi-select |
| Taille | Range |
| Secteur | Multi-select |
| Ville | Text + suggestions |
| Enrichi | Oui/Non |
| Qualification (contacts) | Multi-select |
| Source tag | Multi-select |

---

## Nice to Have (V2.2+)

| Feature | Description |
|---------|-------------|
| Classification auto recommandée | ML/règles pour suggérer Tier |
| Double header navigation | 1 page par étape pipeline |
| Suppression code V1 | Clean des pages obsolètes |
| Dashboard analytics | Stats par Tier, Owner, conversion |

---

## Plan d'implémentation

### Sprint 1 : Fondations (Critique)

| # | Tâche | Estimation |
|---|-------|------------|
| 1.1 | Migration DB (nouveaux champs) | 1h |
| 1.2 | Fix bug source "manual" | 1h |
| 1.3 | Fix bugs enrichissement | 2h |

### Sprint 2 : Tier & Qualification

| # | Tâche | Estimation |
|---|-------|------------|
| 2.1 | UI classification Tier | 3h |
| 2.2 | UI qualification contacts | 2h |
| 2.3 | Filtres par Tier/Qualification | 2h |

### Sprint 3 : Import amélioré

| # | Tâche | Estimation |
|---|-------|------------|
| 3.1 | Mapping manuel colonnes CSV | 3h |
| 3.2 | Tag source à l'import | 1h |
| 3.3 | Import engagements CSV | 2h |

### Sprint 4 : Sync & Vues

| # | Tâche | Estimation |
|---|-------|------------|
| 4.1 | Quality gate avec warnings | 2h |
| 4.2 | Sync granulaire (entités séparées) | 2h |
| 4.3 | Engagements dans analyse sync | 1h |
| 4.4 | Vue Fiche Entreprise | 3h |

### Sprint 5 : Owner & Polish

| # | Tâche | Estimation |
|---|-------|------------|
| 5.1 | Champ Owner + UI | 2h |
| 5.2 | Filtres avancés | 2h |
| 5.3 | Tests & corrections | 2h |

**Total estimé**: ~30h

---

## Critères d'acceptation

- [x] Tier classifiable manuellement sur entreprises
- [x] Qualification Contact/Lead/Transaction fonctionnelle
- [x] Import CSV avec mapping manuel restauré
- [x] Tag source sur tous les imports
- [x] Bugs enrichissement corrigés
- [x] Bug source "manual" corrigé
- [x] Quality gate avec warnings avant sync
- [x] Sync granulaire (entreprises/contacts/engagements séparés)
- [x] Vue Fiche Entreprise complète
- [x] Filtres avancés opérationnels
- [x] Owner assignable sur entreprises

**Implémenté le**: 2024-12-24
