# Tasks - Module UI Navigation

## Phase 1 : Restructuration

### T3.1.1 - Passage multi-page Streamlit
**Durée** : 2h
**Priorité** : 🔴 Bloquant

- [ ] Créer dossier `pages/`
- [ ] Migrer `app.py` → `pages/1_Dashboard_CFO.py`
- [ ] Créer `app.py` minimal (point d'entrée)
- [ ] Vérifier que la navigation fonctionne
- [ ] Renommer proprement les pages

**Fichiers** : `app.py`, `pages/`
**Dépend de** : Rien

---

### T3.1.2 - Page d'accueil
**Durée** : 2h
**Priorité** : 🟠 Haute

- [ ] Créer `pages/0_Accueil.py`
- [ ] Afficher statut des modules :
  - Dashboard CFO : dernière sync, nb lignes
  - Lead Scraper : nb leads, dernière récup
- [ ] Boutons raccourcis vers actions principales
- [ ] Zone notifications/alertes

**Fichiers** : `pages/0_Accueil.py`
**Dépend de** : T3.1.1

---

## Phase 2 : Composants communs

### T3.2.1 - Header commun
**Durée** : 1h
**Priorité** : 🟡 Moyenne

- [ ] Créer `components/header.py`
- [ ] Logo + titre "Sales Ops - Genie Factory"
- [ ] Intégrer dans chaque page
- [ ] Style cohérent

**Fichiers** : `components/header.py`
**Dépend de** : T3.1.1

---

### T3.2.2 - Système de notifications
**Durée** : 2h
**Priorité** : 🟡 Moyenne

- [ ] Créer `components/notifications.py`
- [ ] Stocker notifications en session state
- [ ] Types : success, warning, error, info
- [ ] Affichage dans sidebar ou header
- [ ] Auto-dismiss après X secondes

**Fichiers** : `components/notifications.py`
**Dépend de** : T3.2.1

---

### T3.2.3 - Sidebar enrichie
**Durée** : 1h
**Priorité** : 🟡 Moyenne

- [ ] Créer `components/sidebar.py`
- [ ] Ajouter infos contextuelles :
  - Dernière sync
  - Statut connexions
- [ ] Lien vers documentation/aide

**Fichiers** : `components/sidebar.py`
**Dépend de** : T3.1.1

---

## Phase 3 : Intégration

### T3.3.1 - Intégrer Lead Scraper
**Durée** : 1h
**Priorité** : 🟠 Haute

- [ ] Créer `pages/2_Lead_Scraper.py`
- [ ] Intégrer les composants du module
- [ ] Appliquer le style commun
- [ ] Vérifier navigation

**Fichiers** : `pages/2_Lead_Scraper.py`
**Dépend de** : T3.1.1, Module 002

---

### T3.3.2 - Page Paramètres
**Durée** : 2h
**Priorité** : 🟢 Basse

- [ ] Créer `pages/9_Parametres.py`
- [ ] Configuration globale (.env viewer)
- [ ] Test connexions (Asana, Google)
- [ ] Configuration scheduler
- [ ] À propos / version

**Fichiers** : `pages/9_Parametres.py`
**Dépend de** : T3.1.1

---

## Temps Total Estimé

| Task | Durée |
|------|-------|
| T3.1.1 - Multi-page | 2h |
| T3.1.2 - Accueil | 2h |
| T3.2.1 - Header | 1h |
| T3.2.2 - Notifications | 2h |
| T3.2.3 - Sidebar | 1h |
| T3.3.1 - Lead Scraper | 1h |
| T3.3.2 - Paramètres | 2h |
| **TOTAL** | **11h** |

---

## Notes

1. **T3.1.1 est critique** - à faire en premier pour établir la structure
2. **Streamlit multi-page** simplifie beaucoup la navigation
3. **Components réutilisables** = gain de temps sur les futurs modules
4. **T3.3.1 dépend du Module 002** - peut être fait en parallèle
