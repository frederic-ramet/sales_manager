# Tasks - Epic 004 GetSales Sync

## Phase 1: Setup & Test API

### T4.1.1 - Client GetSales
- [ ] Créer `modules/getsales/__init__.py`
- [ ] Créer `modules/getsales/getsales_client.py`
- [ ] Implémenter `fetch_leads(filters)`
- [ ] Implémenter `fetch_lead_messages(lead_uuid)`
- [ ] Implémenter `fetch_flows()`
- [ ] Gestion rate limit + retry

### T4.1.2 - Script test API
- [ ] Créer `scripts/test_getsales_api.py`
- [ ] Tester connexion API
- [ ] Sauvegarder samples JSON dans data/

### T4.1.3 - Analyse données
- [ ] Documenter structure leads GetSales
- [ ] Documenter structure messages
- [ ] Mapper champs GetSales → HubSpot

---

## Phase 2: Modèles & Déduplication

### T4.2.1 - Modèles SQLite
- [ ] Créer `modules/getsales/models.py`
- [ ] Table `pending_leads`
- [ ] Table `getsales_sync_logs`
- [ ] Table `lead_interactions`
- [ ] Méthodes CRUD

### T4.2.2 - Service déduplication
- [ ] Créer `modules/getsales/deduplication.py`
- [ ] Implémenter `find_duplicates(lead)`
- [ ] Match LinkedIn URL
- [ ] Match Email
- [ ] Implémenter `suggest_merge_strategy()`

### T4.2.3 - Propriétés HubSpot
- [ ] Créer `scripts/init_hubspot_properties.py`
- [ ] Définir 7 propriétés custom
- [ ] Tester création via API

---

## Phase 3: Service Sync

### T4.3.1 - Structure service
- [ ] Créer `modules/getsales/sync_service.py`
- [ ] Classe `GetSalesSyncService`
- [ ] Injection dépendances (clients, db)

### T4.3.2 - Fetch & stockage
- [ ] Implémenter `sync_leads(filters)`
- [ ] Fetch leads + messages
- [ ] Détection doublons
- [ ] Stockage pending_leads
- [ ] Création sync_log

### T4.3.3 - Validation & push
- [ ] Implémenter `validate_lead(id, action, merge_data)`
- [ ] Action `create_new` → nouveau contact HubSpot
- [ ] Action `merge` → update contact existant
- [ ] Action `reject` → marquer rejeté
- [ ] Mise à jour statut pending_lead

### T4.3.4 - Sync interactions
- [ ] Implémenter `_sync_interactions(contact_id, messages)`
- [ ] Créer engagements/notes HubSpot
- [ ] Formater message selon type (envoyé/lu/réponse)
- [ ] Préserver horodatage

---

## Phase 4: Interface Streamlit

### T4.4.1 - Page base
- [ ] Créer `pages/4_🔄_GetSales_Sync.py`
- [ ] Config page
- [ ] Initialisation services
- [ ] Layout header

### T4.4.2 - Section sync
- [ ] Afficher dernière sync (date, statut, nb leads)
- [ ] Bouton "Synchroniser maintenant"
- [ ] Spinner + feedback résultat
- [ ] Gestion erreurs

### T4.4.3 - File validation
- [ ] Filtres (statut, doublons)
- [ ] Metric leads en attente
- [ ] Liste expandable leads
- [ ] Affichage infos GetSales
- [ ] Affichage interactions
- [ ] Badge doublons
- [ ] Boutons actions

### T4.4.4 - Formulaire merge
- [ ] Modal/section conditionnelle
- [ ] Comparaison côte à côte
- [ ] Radio buttons par champ
- [ ] Boutons confirmer/annuler
- [ ] Feedback succès/erreur

---

## Phase 5: Tests & Polish

### T4.5.1 - Tests end-to-end
- [ ] Test sync complet (5 leads)
- [ ] Test validation create_new
- [ ] Test validation merge
- [ ] Test validation reject

### T4.5.2 - Gestion erreurs
- [ ] Try/catch sur toutes les actions
- [ ] Messages utilisateur clairs
- [ ] Rollback si échec

### T4.5.3 - Logging
- [ ] Logger toutes les actions sync
- [ ] Logger validations
- [ ] Logger erreurs API

### T4.5.4 - Intégration home
- [ ] Ajouter module GetSales sur app.py
- [ ] Afficher statut config (API key)
- [ ] Lien vers page sync

---

## Dépendances

- `httpx>=0.25.0` ✅ (déjà dans requirements.txt)
- HubSpotClient existant (`modules/lead_scraper/hubspot_client.py`)

## Variables environnement

- `GETSALES_API_KEY` (à ajouter dans .env)
- `HUBSPOT_API_KEY` ✅ (existant)
