# Feedback - Pipeline V2

**Date**: 2024-12-24
**Testeur**: Frederic Ramet
**Version**: Post-commit 7e946bf

---

## Retours de test

### Import CSV

| # | Remarque | Priorité | Statut |
|---|----------|----------|--------|
| 1 | Import crée entreprises + contacts mais PAS les interactions/événements | Moyenne | Open |
| 2 | Permettre de tagger l'origine/source lors de l'import | Haute | Open |

**Détail remarque #2 :**
- À l'import, pouvoir spécifier un tag d'origine (ex: "Salon VivaTech 2024", "LinkedIn Ads", "Referral Partner X")
- Différent du champ `source` technique (csv, hubspot, getsales)
- Permet de tracker la provenance business des données
- **Action technique** : Ajouter champ `source_tag` ou `origin` dans companies/contacts + input dans UI import

**Détail remarque #1 :**
- Les entreprises sont créées ✅
- Les contacts sont créés ✅
- Les interactions ne sont pas créées ❌
- **Cause probable** : Le CSV contient des colonnes comme "Date envoi message", "Commentaire" qui ne sont pas mappées vers la table `interactions`
- **Action suggérée** : Ajouter mapping CSV → interactions (type, date, contenu)

### Vue Dashboard

| # | Remarque | Priorité | Statut |
|---|----------|----------|--------|
| 1 | Ajouter plus de champs de recherche/filtres | Moyenne | Open |
| 2 | Créer une vue Fiche Entreprise (infos entreprise + contacts liés) | Haute | Open |

**Détail remarque #1 :**
- Actuellement : recherche par nom, SIREN, email, domain
- Manque : filtres par taille, ville, secteur, tier, enrichi/non enrichi, etc.

**Détail remarque #2 : Vue Fiche Entreprise**
- Clic sur une entreprise → ouvre une fiche détaillée
- Section 1 : Toutes les infos entreprise (~30 champs)
- Section 2 : Liste des contacts liés à cette entreprise
- Section 3 : Historique des engagements (tous contacts confondus)
- Actions : Modifier, Enrichir, Changer Tier, Sync HubSpot

### Clean (Déduplication)

| # | Remarque | Priorité | Statut |
|---|----------|----------|--------|
| 1 | | | |

### Enrich

| # | Remarque | Priorité | Statut |
|---|----------|----------|--------|
| 1 | | | |

### Sync HubSpot

| # | Remarque | Priorité | Statut |
|---|----------|----------|--------|
| 1 | | | |

### Navigation / UX

| # | Remarque | Priorité | Statut |
|---|----------|----------|--------|
| 1 | Confusion V1/V2 : nav header (pages V1) + tabs Pipeline (V2) coexistent | Haute | Open |

**Détail remarque #1 :**
- Navigation header contient les anciennes pages V1
- Pipeline V2 a ses propres tabs (Import, Clean, Enrich, Sync)
- Questions soulevées :
  - Quelles différences entre features V1 et V2 ?
  - Pourquoi conserver les deux dans la navigation ?
  - Cela implique du code mort (UI + controllers V1)
- **Action suggérée** : Nettoyer les pages V1 obsolètes, unifier la navigation autour du Pipeline V2

---

## Bugs critiques

| # | Description | Repro | Statut |
|---|-------------|-------|--------|
| 1 | | | |

---

## Suggestions d'amélioration

| # | Suggestion | Impact |
|---|------------|--------|
| 1 | Ajouter statut Contact → Lead → Transaction | Haute |
| 2 | Renommer `interactions` → `engagements` (aligner sur HubSpot) | Moyenne |
| 3 | Ajouter Tier/ICP sur entreprises (driver de l'enrichissement) | **Critique** |

**Détail suggestion #3 : Classification Tier / ICP**

### Concept clé
Le **Tier** est le driver principal de toute la stratégie :
- On enrichit pour **mieux cibler**
- On enrichit pour **mieux qualifier**
- On enrichit pour **mieux investir** dans les opérations de contact

### Hiérarchie

```
ICP (Ideal Customer Profile)     ← Définition des critères cibles
       ↓
   Tier / Classe                 ← Classification priorité entreprise
       ↓
    Segment                      ← Regroupement pour campagnes
       ↓
    Contact                      ← Personnes à contacter
```

### Valeurs proposées

| Tier | Description | Action enrichissement |
|------|-------------|----------------------|
| `tier_1` | Cible idéale, priorité max | Enrichissement complet + manuel |
| `tier_2` | Bonne cible, priorité moyenne | Enrichissement automatique |
| `tier_3` | Opportuniste | Enrichissement minimal |
| `excluded` | Hors cible (concurrent, trop petit...) | Aucun enrichissement |

### Impact sur le pipeline

| Étape | Utilisation du Tier |
|-------|---------------------|
| **Import** | Pré-classification si critères disponibles |
| **Enrich** | Priorisation : Tier 1 d'abord, profondeur selon tier |
| **Clean** | Dédup prioritaire sur Tier 1 |
| **Sync** | Push HubSpot : Tier 1-2 uniquement |

**Action technique** :
- Ajouter champ `tier` dans table `companies` : `tier_1`, `tier_2`, `tier_3`, `excluded`, `unclassified`
- UI de classification manuelle + règles auto (taille, secteur, localisation)

**Détail suggestion #2 : Terminologie HubSpot**
- Renommer table `interactions` → `engagements`
- Aligner le vocabulaire sur HubSpot pour cohérence
- Types d'engagement : `email`, `call`, `meeting`, `note`, `task`, `message`

**Détail suggestion #1 : Workflow de qualification**

### Niveau 1 – Contact
- Quelqu'un identifié avec info de contact valide
- **Aucune interaction commerciale active**
- Pas de qualification, pas de scoring
- **Statut** : `contact`

### Niveau 2 – Lead
Créé après un **premier contact réel** :
- Réponse à un message
- Échange LinkedIn / email
- Call rapide
- Intérêt exprimé (même léger)

**Objectif** : Comprendre besoin, vérifier timing, vérifier capacité à avancer
- **Statut** : `lead`

### Niveau 3 – Transaction (Deal)
Créé quand :
- Besoin clair
- Scope minimum défini
- Probabilité de vente existe

**Règles** :
- Toute transaction créée dans HubSpot (pipeline) ET Asana (actions)
- Objectif : amener à une vente (call → proposition → décision)
- **Statut** : `transaction`

### Règles de passage

| Transition | Question à se poser |
|------------|---------------------|
| Contact → Lead | Est-ce qu'on a eu un vrai échange ? |
| Lead → Transaction | Est-ce qu'il y a un besoin réel + une chance de vendre ? |

⚠️ Si réponse = NON → on ne passe pas l'étape

**Action technique** : Ajouter champ `qualification_status` dans table `contacts` avec valeurs : `contact`, `lead`, `transaction`

