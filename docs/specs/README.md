# Spec: Architecture Companies/Contacts - Index

Cette spec décrit la refonte de l'architecture de données pour séparer proprement **Entreprises** et **Contacts**, actuellement fusionnés dans la table `unified_contacts`.

---

## 📚 Documents de la spec

### 1. **[SPEC_COMPANIES_CONTACTS_SEPARATION.md](./SPEC_COMPANIES_CONTACTS_SEPARATION.md)**
   **📖 Document principal - À lire en premier**

   Contient:
   - Objectif et contexte
   - Schéma de données détaillé (tables `companies` et `contacts`)
   - Relations et règles de gestion
   - Cas d'usage détaillés (recherche SIRENE, enrichissement, import GetSales, sync HubSpot)
   - Impact sur le code existant
   - Plan de migration complet (4 phases)
   - Critères d'acceptance
   - Timeline estimée
   - Questions ouvertes

### 2. **[EXAMPLES_DATA.md](./EXAMPLES_DATA.md)**
   **💡 Exemples concrets**

   Illustre avec des données réelles:
   - Entreprise française avec SIREN (ESCP Business School)
   - Entreprise étrangère sans SIREN (Stripe US)
   - Contact sans entreprise (freelance)
   - Scénario complet import GetSales
   - Établissements multiples (SIRET)
   - Sync HubSpot avec associations
   - Dédoublonnage entreprise
   - Requêtes SQL courantes
   - Vue de compatibilité legacy

### 3. **[DECISIONS_RATIONALE.md](./DECISIONS_RATIONALE.md)**
   **🎯 Justifications des choix techniques**

   Explique les 10 décisions clés:
   1. SIREN optionnel (nullable)
   2. SIRET multiples = liste CSV
   3. company_id optionnel sur contacts
   4. Pas de soft delete (status flags)
   5. Stats agrégées sur companies
   6. Matching hiérarchique GetSales
   7. Unicité email/LinkedIn
   8. raw_data JSON
   9. Pas de table history (v1)
   10. Migration avec vue compatibilité

   Pour chaque décision: alternatives considérées, pour/contre, implémentation.

### 4. **[diagrams/](./diagrams/)**
   **📊 Diagrammes visuels**

   - `companies_contacts_erd.mmd` - Schéma entité-relation (ERD) avec tous les champs
   - `workflow_import_sources.mmd` - Flows des différentes sources (SIRENE, GetSales, HubSpot, Manual)

---

## 🎯 Résumé exécutif (TL;DR)

### Problème actuel
- **535 contacts** pour ESCP → infos entreprise **dupliquées 535 fois**
- Impossible de gérer les entreprises comme entités propres
- Recherche et enrichissement inefficaces
- Pas de support entreprises étrangères (sans SIREN)

### Solution proposée
**Architecture normalisée :**
```
companies (1) ↔ (N) contacts
```

**Bénéfices :**
- ✅ **0 duplication** données entreprise
- ✅ Update entreprise = **1 UPDATE** au lieu de 535
- ✅ Vue consolidée entreprises
- ✅ Support international (SIREN nullable)
- ✅ Matching intelligent GetSales (évite doublons)
- ✅ Relation préservée dans HubSpot

**Timeline :** 7-10 jours de dev

---

## 🚀 Quick Start

### Pour reviewer la spec:

1. **Lire en priorité:**
   - [SPEC_COMPANIES_CONTACTS_SEPARATION.md](./SPEC_COMPANIES_CONTACTS_SEPARATION.md) - Sections "Objectif" et "Schéma de données"
   - [EXAMPLES_DATA.md](./EXAMPLES_DATA.md) - Exemples 1, 2, 4 (cas courants)

2. **Approfondir si questions:**
   - [DECISIONS_RATIONALE.md](./DECISIONS_RATIONALE.md) - Comprendre les choix
   - Diagrammes ERD et workflows

3. **Valider:**
   - Cas d'usage couvrent vos besoins ?
   - Décisions techniques font sens ?
   - Migration plan réaliste ?

### Pour implémenter:

**Phase 1:** Migration DB (pas de code)
```bash
# 1. Créer nouvelles tables
sqlite3 data/leads.db < migrations/001_create_companies.sql
sqlite3 data/leads.db < migrations/002_create_contacts.sql

# 2. Migrer données
python scripts/migrate_unified_to_companies_contacts.py

# 3. Vérifier intégrité
python scripts/verify_migration.py
```

**Phase 2-3:** Adapter code (voir SPEC section "Impact sur le code")

**Phase 4:** Cleanup

---

## 📋 Checklist validation spec

Avant d'approuver la spec, vérifier:

### Fonctionnel
- [ ] Cas d'usage SIRENE couvert
- [ ] Cas d'usage GetSales couvert
- [ ] Cas d'usage HubSpot sync couvert
- [ ] Support entreprises sans SIREN
- [ ] Support contacts sans entreprise
- [ ] Dédoublonnage entreprise possible

### Technique
- [ ] Schéma SQL valide (constraints, indexes)
- [ ] Migration sans perte de données
- [ ] Performance acceptable (indexes sur recherches)
- [ ] Code legacy peut coexister (vue compatibilité)

### Projet
- [ ] Timeline réaliste
- [ ] Risques identifiés
- [ ] Plan de rollback existe
- [ ] Critères d'acceptance clairs

---

## ❓ FAQ

### Q: Pourquoi séparer maintenant ?
**R:** Duplication data devient problème critique avec 535 contacts ESCP (et ça va croître). Migration plus facile maintenant que dans 6 mois avec 10x plus de données.

### Q: Risque de casser l'existant ?
**R:** Migration avec vue `unified_contacts_legacy` permet code existant de continuer à fonctionner pendant adaptation progressive.

### Q: Combien de temps migration DB ?
**R:** Migration pure DB = **~5 min downtime**. Mais préparation scripts + vérification = 2-3 jours de travail en amont.

### Q: Peut-on rollback ?
**R:** Oui, `unified_contacts_backup` gardée. Rollback = renommer tables + réactiver ancien code. Tester rollback avant migration prod.

### Q: Que faire des doublons entreprises existants ?
**R:** Phase 1: Migration crée doublons (basé sur SIREN unique). Phase 2: Fonction `merge_companies()` pour nettoyer manuellement. Phase 3: Matching intelligent évite nouveaux doublons.

---

## 📞 Contact

**Questions sur la spec ?** Ouvrir une discussion dans l'équipe.

**Bugs/suggestions ?** Éditer directement les fichiers de spec (Markdown) et proposer PR.

---

**Version:** 1.0
**Date:** 2025-12-21
**Statut:** DRAFT - En attente validation
**Prochaine étape:** Review équipe → Approbation → Implémentation Phase 1
