# Tasks - Module UI Navigation

## Phase 1 : Restructuration Multi-Page

### T3.1.1 - Convertir app.py actuel en page
**Durée** : 1h
**Priorité** : 🔴 Bloquant

- [ ] Créer dossier `pages/`
- [ ] Copier `app.py` → `pages/1_📊_Pipeline_CFO.py`
- [ ] Adapter les imports si nécessaire
- [ ] Vérifier que la page fonctionne isolément

**Fichiers** : `pages/1_📊_Pipeline_CFO.py`
**Dépend de** : Rien

---

### T3.1.2 - Créer page d'accueil
**Durée** : 2h
**Priorité** : 🔴 Bloquant

- [ ] Créer nouveau `app.py` (page d'accueil)
- [ ] Titre "Sales Ops - Genie Factory"
- [ ] Carte statut Dashboard CFO :
  - Dernière sync
  - Nb deals synchro
  - Bouton raccourci
- [ ] Carte statut Lead Scraper :
  - Nb leads en base
  - Dernière extraction
  - Bouton raccourci
- [ ] Zone alertes (config manquante, erreurs)

**Fichiers** : `app.py`
**Dépend de** : T3.1.1

---

### T3.1.3 - Tester navigation
**Durée** : 30min
**Priorité** : 🟠 Haute

- [ ] Vérifier sidebar Streamlit
- [ ] Tester navigation entre pages
- [ ] Vérifier session state partagé
- [ ] Corriger les bugs éventuels

**Dépend de** : T3.1.2

---

## Phase 2 : Intégration Lead Scraper

### T3.2.1 - Migrer page recherche principale
**Durée** : 2h
**Priorité** : 🟠 Haute

- [ ] Copier `_to_migrate_leadscraper/app.py` → `pages/2_🎯_Recherche_Leads.py`
- [ ] Adapter imports vers `modules/lead_scraper/`
- [ ] Supprimer config sidebar (utiliser page Paramètres)
- [ ] Tester fonctionnement

**Fichiers sources** : `_to_migrate_leadscraper/app.py`
**Dépend de** : T3.1.3, Epic 002 (modules migrés)

---

### T3.2.2 - Migrer page Mes Leads
**Durée** : 1h
**Priorité** : 🟡 Moyenne

- [ ] Copier `pages/3_📋_Mes_Leads_HubSpot.py` → `pages/3_📋_Mes_Leads.py`
- [ ] Adapter imports
- [ ] Tester sync HubSpot

**Fichiers sources** : `_to_migrate_leadscraper/pages/3_📋_Mes_Leads_HubSpot.py`
**Dépend de** : T3.2.1

---

### T3.2.3 - Migrer page Lookalike
**Durée** : 1h
**Priorité** : 🟡 Moyenne

- [ ] Copier `pages/4_🔍_Lookalike.py` → `pages/4_🔍_Lookalike.py`
- [ ] Adapter imports
- [ ] Tester recherche lookalike

**Fichiers sources** : `_to_migrate_leadscraper/pages/4_🔍_Lookalike.py`
**Dépend de** : T3.2.1

---

### T3.2.4 - Migrer page Historique
**Durée** : 1h
**Priorité** : 🟢 Basse

- [ ] Copier `pages/2_📊_Historique.py` → `pages/5_📜_Historique_Leads.py`
- [ ] Adapter imports
- [ ] Tester affichage SQLite

**Fichiers sources** : `_to_migrate_leadscraper/pages/2_📊_Historique.py`
**Dépend de** : T3.2.1

---

## Phase 3 : Configuration Centralisée

### T3.3.1 - Page Paramètres unifiée
**Durée** : 2h
**Priorité** : 🟠 Haute

- [ ] Créer `pages/9_⚙️_Parametres.py`
- [ ] Section Asana :
  - Input PAT (masqué)
  - Input Project GID
  - Bouton "Tester connexion"
- [ ] Section Google Sheets :
  - Chemin credentials
  - URL Spreadsheet
  - Bouton "Tester connexion"
- [ ] Section Pappers :
  - Input API Key (masqué)
  - Affichage crédits restants
  - Bouton "Tester connexion"
- [ ] Section HubSpot :
  - Input Private App Token (masqué)
  - Bouton "Tester connexion"
- [ ] Section Anthropic (optionnel) :
  - Input API Key
  - Sélecteur modèle
  - Bouton "Tester connexion"

**Fichiers** : `pages/9_⚙️_Parametres.py`
**Dépend de** : T3.1.3

---

### T3.3.2 - Sauvegarde config
**Durée** : 1h
**Priorité** : 🟡 Moyenne

- [ ] Créer `config/app_config.json` pour paramètres modifiables
- [ ] Sauvegarder au changement dans UI
- [ ] Charger au démarrage app
- [ ] Garder secrets dans .env (non modifiables via UI)

**Fichiers** : `config/app_config.json`, `core/config_manager.py`
**Dépend de** : T3.3.1

---

## Phase 4 : Composants Communs

### T3.4.1 - Carte statut module
**Durée** : 1h
**Priorité** : 🟢 Basse

- [ ] Créer `components/status_card.py`
- [ ] Affichage : icône, titre, métrique, dernière action
- [ ] Couleur selon statut (vert/orange/rouge)
- [ ] Bouton action rapide

**Fichiers** : `components/status_card.py`
**Dépend de** : T3.1.2

---

### T3.4.2 - Testeur API générique
**Durée** : 1h
**Priorité** : 🟢 Basse

- [ ] Créer `components/api_tester.py`
- [ ] Input clé/config
- [ ] Bouton test
- [ ] Affichage résultat (succès/erreur)
- [ ] Réutilisable pour toutes les APIs

**Fichiers** : `components/api_tester.py`
**Dépend de** : T3.3.1

---

## Temps Total Estimé

| Phase | Tâches | Temps |
|-------|--------|-------|
| Phase 1 - Multi-page | T3.1.1 → T3.1.3 | 3.5h |
| Phase 2 - Lead Scraper | T3.2.1 → T3.2.4 | 5h |
| Phase 3 - Config | T3.3.1 → T3.3.2 | 3h |
| Phase 4 - Composants | T3.4.1 → T3.4.2 | 2h |
| **TOTAL** | | **13.5h** |

---

## Ordre d'exécution recommandé

1. **T3.1.1 → T3.1.3** : D'abord restructurer en multi-page
2. **T3.3.1** : Ensuite page Paramètres (base pour tests)
3. **Epic 002** : Migrer les modules lead_scraper
4. **T3.2.1 → T3.2.4** : Puis intégrer les pages Lead Scraper
5. **T3.3.2, T3.4.x** : Finitions

---

## Notes

1. **Phase 1 peut être faite indépendamment** - juste restructuration
2. **Phase 2 dépend d'Epic 002** - modules doivent être migrés d'abord
3. **Réutiliser le pattern leadscraper** - ne pas réinventer
4. **Session state** - partager données entre pages via `st.session_state`
