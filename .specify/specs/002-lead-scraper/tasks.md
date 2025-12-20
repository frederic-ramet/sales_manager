# Tasks - Module Lead Scraper

## Phase 1 : Migration & Setup

### T2.1.1 - Analyse code existant
**Durée** : 2h
**Priorité** : 🔴 Bloquant

- [ ] Lire le code dans `.specify/_to_migrate/`
- [ ] Documenter les fonctionnalités existantes
- [ ] Identifier les dépendances
- [ ] Lister ce qui peut être réutilisé
- [ ] Planifier les adaptations nécessaires

**Fichiers** : Notes dans ce fichier
**Dépend de** : Code à migrer disponible

---

### T2.1.2 - Setup module
**Durée** : 1h
**Priorité** : 🔴 Bloquant

- [ ] Créer structure `modules/lead_scraper/`
- [ ] Créer `__init__.py`
- [ ] Ajouter dépendances dans `requirements.txt`
- [ ] Créer page Streamlit dédiée

**Fichiers** : `modules/lead_scraper/`, `requirements.txt`
**Dépend de** : T2.1.1

---

## Phase 2 : Récupération des leads

### T2.2.1 - Scraper core
**Durée** : 4h
**Priorité** : 🟠 Haute

- [ ] Créer `modules/lead_scraper/scraper.py`
- [ ] Implémenter import CSV
- [ ] Implémenter scraping (selon sources identifiées)
- [ ] Parser et normaliser les données
- [ ] Tests unitaires

**Fichiers** : `modules/lead_scraper/scraper.py`
**Dépend de** : T2.1.2

---

### T2.2.2 - Stockage local
**Durée** : 2h
**Priorité** : 🟠 Haute

- [ ] Créer `modules/lead_scraper/storage.py`
- [ ] Schema SQLite pour les leads
- [ ] CRUD basique (create, read, update, delete)
- [ ] Déduplication par SIREN/email
- [ ] Tests unitaires

**Fichiers** : `modules/lead_scraper/storage.py`, `data/leads.db`
**Dépend de** : T2.2.1

---

## Phase 3 : Enrichissement

### T2.3.1 - Enrichissement SIRENE
**Durée** : 3h
**Priorité** : 🟠 Haute

- [ ] Créer `modules/lead_scraper/enricher.py`
- [ ] Client API SIRENE (api.insee.fr)
- [ ] Récupération : raison sociale, adresse, NAF, effectif
- [ ] Gestion rate limits
- [ ] Cache des résultats

**Fichiers** : `modules/lead_scraper/enricher.py`
**Dépend de** : T2.2.2

---

### T2.3.2 - Enrichissement Pappers (optionnel)
**Durée** : 2h
**Priorité** : 🟡 Moyenne

- [ ] Intégration API Pappers
- [ ] Récupération : CA, résultat, dirigeants
- [ ] Gestion clé API et quotas

**Fichiers** : `modules/lead_scraper/enricher.py`
**Dépend de** : T2.3.1

---

### T2.3.3 - Scoring leads
**Durée** : 2h
**Priorité** : 🟡 Moyenne

- [ ] Algorithme de scoring configurable
- [ ] Critères : taille entreprise, secteur, localisation
- [ ] Score 1-5 compatible avec Confidence Score Asana

**Fichiers** : `modules/lead_scraper/enricher.py`
**Dépend de** : T2.3.1

---

## Phase 4 : Intégration

### T2.4.1 - Push Asana
**Durée** : 3h
**Priorité** : 🟠 Haute

- [ ] Créer `modules/lead_scraper/asana_push.py`
- [ ] Création task depuis lead
- [ ] Mapping champs → custom fields
- [ ] Vérification doublons avant création
- [ ] Feedback UI

**Fichiers** : `modules/lead_scraper/asana_push.py`
**Dépend de** : T2.3.1

---

### T2.4.2 - UI Lead Scraper
**Durée** : 3h
**Priorité** : 🟠 Haute

- [ ] Page Streamlit `pages/lead_scraper.py`
- [ ] Import CSV avec preview
- [ ] Tableau des leads avec filtres
- [ ] Bouton enrichir sélection
- [ ] Bouton push vers Asana
- [ ] Export CSV/JSON

**Fichiers** : `pages/lead_scraper.py`
**Dépend de** : T2.4.1

---

## Temps Total Estimé

| Task | Durée |
|------|-------|
| T2.1.1 - Analyse | 2h |
| T2.1.2 - Setup | 1h |
| T2.2.1 - Scraper | 4h |
| T2.2.2 - Stockage | 2h |
| T2.3.1 - SIRENE | 3h |
| T2.3.2 - Pappers | 2h |
| T2.3.3 - Scoring | 2h |
| T2.4.1 - Push Asana | 3h |
| T2.4.2 - UI | 3h |
| **TOTAL** | **22h** |

---

## Notes

1. **Attendre le code à migrer** avant de commencer T2.1.1
2. **SIRENE est prioritaire** sur Pappers (gratuit vs payant)
3. **Réutiliser `core/asana_client.py`** existant pour le push
