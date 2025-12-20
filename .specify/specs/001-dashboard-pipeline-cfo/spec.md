# Spec - Portail Sales Ops Genie Factory

## Vision

Créer un **portail modulaire** pour l'équipe Sales & Finance de Genie Factory. Chaque module est un outil indépendant qui résout un problème spécifique.

## Contexte

### Situation actuelle
- Le sales manager gère son pipeline dans **Asana** (board Kanban "Sales pipeline")
- Le CFO a besoin d'un **dashboard financier** dans Google Sheets pour :
  - Suivre le deal flow
  - Calculer les prévisions de trésorerie (scénarios conservateur/probable)
  - Avoir une vue consolidée client/projet/budget/marge

### Problème
Pas de synchronisation automatique Asana → Google Sheets, tout est manuel.

### Objectif Phase 1
Créer le **Module 1 : Dashboard Pipeline CFO** qui :
1. Récupère les deals depuis Asana
2. Calcule les métriques financières (revenue pondéré, scénarios)
3. Synchronise vers Google Sheets automatiquement

---

## User Stories - Module 1 : Dashboard Pipeline CFO

### US-1.1 : Extraction des deals Asana
**En tant que** CFO  
**Je veux** que le système récupère automatiquement les deals d'Asana  
**Afin de** ne pas avoir à maintenir manuellement un fichier

**Critères d'acceptation :**
- [ ] Connexion à l'API Asana avec PAT
- [ ] Récupération de toutes les tasks du projet "Sales pipeline"
- [ ] Extraction des custom fields : Client, Projet, Budget, Marge, Mois facturation, Confidence Score
- [ ] Cache local pour éviter trop d'appels API

---

### US-1.2 : Calculs financiers
**En tant que** CFO  
**Je veux** voir le revenue pondéré et les scénarios de trésorerie  
**Afin de** faire mes prévisions financières

**Critères d'acceptation :**
- [ ] Calcul probabilité basé sur Confidence Score (1-5)
- [ ] Calcul revenue pondéré = Budget × Probabilité
- [ ] Calcul marge %
- [ ] Flag scénario conservateur (confidence ≥ 4)
- [ ] Flag scénario probable (confidence ≥ 3)
- [ ] Dimensions temporelles : Année, Trimestre, Mois (depuis mois facturation)

---

### US-1.3 : Synchronisation Google Sheets
**En tant que** CFO  
**Je veux** que mes données soient automatiquement dans Google Sheets  
**Afin de** les analyser avec mes outils habituels (tableaux croisés dynamiques, etc.)

**Critères d'acceptation :**
- [ ] Onglet "Pipeline complet" avec toutes les données
- [ ] Onglet "Scénario conservateur" (filtre confidence ≥ 4)
- [ ] Onglet "Scénario probable" (filtre confidence ≥ 3)
- [ ] Onglet "Config" avec metadata de sync
- [ ] Sync incrémenta ou replace (à définir)
- [ ] Timestamp de dernière sync

---

### US-1.4 : Interface d'administration
**En tant qu'** admin technique
**Je veux** configurer les connexions et déclencher les syncs
**Afin de** maintenir le système

**Critères d'acceptation :**
- [x] Page Streamlit simple avec :
  - Configuration Asana (PAT, Project GID)
  - Configuration Google Sheets (Service Account, Sheet URL)
  - Test de connexion pour chaque API
  - Bouton "Sync maintenant"
  - Affichage dernière sync et statut

---

### US-1.5 : Synchronisation automatique
**En tant que** CFO
**Je veux** que la sync se fasse automatiquement (quotidienne ou hebdomadaire)
**Afin de** avoir des données toujours à jour sans intervention manuelle

**Critères d'acceptation :**
- [ ] Scheduler configurable (quotidien / hebdomadaire)
- [ ] Activation/désactivation depuis l'UI
- [ ] Choix de la fréquence depuis l'UI
- [ ] Indicateur du prochain sync prévu
- [ ] Log des syncs automatiques (succès/échec)
- [ ] Persistance de la configuration (fichier ou DB)

**Implémentation technique :**
- APScheduler pour le scheduling en background
- Stockage config dans fichier JSON ou SQLite
- Thread séparé pour ne pas bloquer l'UI Streamlit

---

## Modules Futurs (Hors Scope Phase 1)

### Module 2 : Prospection & Enrichissement
- Enrichissement leads SIRENE/Pappers
- Scoring automatique
- Push vers Asana

### Module 3 : Sync HubSpot
- Rapprochement Asana ↔ HubSpot
- Détection doublons
- Sync bidirectionnelle

---

## Dépendances Externes (Phase 1)

| Service | Usage | Clé requise | Coût |
|---------|-------|-------------|------|
| Asana | Source des deals | Oui (PAT) | Gratuit |
| Google Sheets | Destination dashboard | Oui (Service Account) | Gratuit |

---

## Custom Fields Asana Requis

Ces champs doivent être créés manuellement dans le projet Asana avant de lancer le dev :

| Field | Type | Description |
|-------|------|-------------|
| Client | Text | Nom du client/prospect |
| Projet | Text | Nom du projet |
| Budget (€) | Number | Existe déjà ("Estimated value") |
| Marge (€) | Number | Bénéfice attendu |
| Mois facturation | Date | Mois où facturation est prévue |
| Confidence Score | Number | 1-5 (déjà existant dans ton screenshot) |

---

## Hors Scope (v1)

- Authentification multi-utilisateurs
- Notifications email/Slack
- Dashboard analytics interactif (Streamlit uniquement pour admin)
- Sync temps réel (webhooks)
