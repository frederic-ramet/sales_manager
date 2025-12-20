# Spec - Module UI Navigation

## Vision

Interface unifiée pour naviguer entre les modules du portail Sales Ops, basée sur le pattern multi-page Streamlit existant dans leadscraper.

## Contexte

### Pattern existant (leadscraper)
L'app à migrer utilise déjà Streamlit multi-page :
```
app.py                              # Page principale
pages/
  1_⚙️_Admin.py                    # Configuration APIs
  2_📊_Historique.py               # Extractions passées
  3_📋_Mes_Leads_HubSpot.py        # Contacts CRM
  4_🔍_Lookalike.py                # Recherche similaires
  ...
```

### Objectif
Réutiliser ce pattern pour unifier Dashboard CFO + Lead Scraper dans une navigation cohérente.

---

## Architecture Cible

```
app.py                              # Page d'accueil / Dashboard global
pages/
  # Module 1 : Dashboard CFO
  1_📊_Pipeline_CFO.py             # Sync Asana → Sheets (app.py actuel)

  # Module 2 : Lead Scraper
  2_🎯_Recherche_Leads.py          # Recherche SIRENE + enrichissement
  3_📋_Mes_Leads.py                # Contacts HubSpot
  4_🔍_Lookalike.py                # Recherche similaires
  5_📜_Historique_Leads.py         # Extractions passées

  # Admin / Config
  9_⚙️_Parametres.py              # Configuration globale APIs
```

---

## User Stories

### US-3.1 : Page d'accueil
**En tant qu'** utilisateur
**Je veux** voir un dashboard récapitulatif
**Afin de** avoir une vue d'ensemble rapide

**Critères d'acceptation :**
- [ ] Statut Dashboard CFO (dernière sync, nb deals)
- [ ] Statut Lead Scraper (nb leads, dernière extraction)
- [ ] Raccourcis vers actions principales
- [ ] Alertes si erreur de config

---

### US-3.2 : Navigation intégrée
**En tant qu'** utilisateur
**Je veux** naviguer entre les modules facilement
**Afin de** passer d'un outil à l'autre sans friction

**Critères d'acceptation :**
- [ ] Sidebar Streamlit native (pages/)
- [ ] Icônes distinctives par module
- [ ] Regroupement logique (CFO / Leads / Admin)
- [ ] Indication visuelle du module actif

---

### US-3.3 : Configuration centralisée
**En tant qu'** admin
**Je veux** configurer toutes les APIs au même endroit
**Afin de** simplifier la maintenance

**Critères d'acceptation :**
- [ ] Page Paramètres unique regroupant :
  - Asana (PAT, Project GID)
  - Google Sheets (Service Account)
  - Pappers (API Key)
  - HubSpot (Private App Token)
  - Anthropic (API Key) - optionnel
- [ ] Test de connexion pour chaque API
- [ ] Sauvegarde dans .env ou config.json

---

## Stratégie de Migration

### Étape 1 : Restructurer app.py actuel
1. Renommer `app.py` → `pages/1_📊_Pipeline_CFO.py`
2. Créer nouveau `app.py` (page d'accueil)
3. Vérifier que la navigation fonctionne

### Étape 2 : Intégrer pages leadscraper
1. Migrer les pages depuis `_to_migrate_leadscraper/pages/`
2. Renommer avec numérotation cohérente
3. Adapter les imports

### Étape 3 : Page Admin unifiée
1. Fusionner config CFO + config Leadscraper
2. Créer `pages/9_⚙️_Parametres.py`

---

## Composants Réutilisables

### Depuis leadscraper (à conserver)
- Pattern de numérotation pages (`1_emoji_Nom.py`)
- Session state pour partage données entre pages
- Structure config.py centralisée

### À créer
- `components/status_card.py` - Carte statut module
- `components/api_tester.py` - Test connexion API générique

---

## Dépendances

- Streamlit >= 1.28 (multi-page natif)
- Aucune dépendance externe supplémentaire

---

## Hors Scope (v1)

- Thème personnalisé / mode sombre
- Responsive mobile
- Authentification utilisateur
- Breadcrumbs / fil d'Ariane
