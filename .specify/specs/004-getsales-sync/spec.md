# Epic 004 - GetSales Sync

**Version**: 1.0
**Date**: 20/12/2025
**Status**: Draft

---

## Objectif

Ajouter un module de synchronisation GetSales → HubSpot dans l'application Streamlit existante, avec validation manuelle des leads et gestion des doublons.

## Positionnement

| Source | Rôle |
|--------|------|
| SIRENE | Enrichissement données entreprises (existant) |
| GetSales | Leads + interactions prospection LinkedIn (nouveau) |
| HubSpot | CRM centralisé (existant) |

## Flux utilisateur

```
1. User clique "Synchroniser GetSales" (bouton manuel)
2. App récupère les leads depuis GetSales API
3. App détecte les doublons potentiels dans HubSpot
4. User valide lead par lead (interface dédiée)
5. Si doublon: User merge manuellement via formulaire
6. App push vers HubSpot + crée les engagements
```

---

## User Stories

### US-4.1: Synchronisation GetSales
**En tant que** commercial
**Je veux** récupérer mes leads GetSales
**Afin de** les centraliser dans HubSpot

**Critères d'acceptation:**
- Bouton "Synchroniser" déclenche le fetch API
- Leads stockés en base SQLite (pending_leads)
- Affichage du nombre de leads récupérés
- Log de synchronisation créé

### US-4.2: Détection de doublons
**En tant que** commercial
**Je veux** voir les doublons potentiels
**Afin de** éviter les duplications dans HubSpot

**Critères d'acceptation:**
- Match sur LinkedIn URL (prioritaire, confiance high)
- Match sur email (confiance high)
- Affichage visuel des matches trouvés
- Badge indiquant le niveau de confiance

### US-4.3: Validation manuelle
**En tant que** commercial
**Je veux** valider chaque lead avant import
**Afin de** contrôler la qualité des données

**Critères d'acceptation:**
- Liste des leads en attente de validation
- Actions: Créer nouveau / Merger / Rejeter
- Filtres par statut et présence de doublons
- Historique des validations

### US-4.4: Formulaire de merge
**En tant que** commercial
**Je veux** choisir les données à conserver
**Afin de** fusionner intelligemment les profils

**Critères d'acceptation:**
- Comparaison côte à côte GetSales vs HubSpot
- Sélection champ par champ (radio buttons)
- Prévisualisation avant confirmation
- Annulation possible

### US-4.5: Sync des interactions
**En tant que** commercial
**Je veux** voir l'historique LinkedIn dans HubSpot
**Afin de** avoir le contexte des échanges

**Critères d'acceptation:**
- Messages LinkedIn → Notes HubSpot
- Horodatage préservé
- Type d'interaction (envoyé/lu/réponse)
- Nom de la campagne GetSales

---

## Architecture technique

### Nouveaux fichiers

```
modules/getsales/
├── __init__.py
├── getsales_client.py      # Client API GetSales
├── deduplication.py        # Service détection doublons
├── sync_service.py         # Orchestrateur sync
└── models.py               # Modèles SQLite

pages/
└── 4_🔄_GetSales_Sync.py   # Interface Streamlit

scripts/
└── init_hubspot_properties.py  # Setup propriétés custom
```

### Modèles de données (SQLite)

**Table: pending_leads**
| Colonne | Type | Description |
|---------|------|-------------|
| id | INTEGER PK | Auto-increment |
| getsales_uuid | TEXT UNIQUE | UUID GetSales |
| getsales_data | JSON | Données complètes du lead |
| hubspot_matches | JSON | Doublons détectés |
| duplicate_status | TEXT | none/potential/confirmed |
| validation_status | TEXT | pending/approved/rejected |
| merge_decision | JSON | Choix du formulaire |
| created_at | DATETIME | Date création |
| validated_at | DATETIME | Date validation |

**Table: getsales_sync_logs**
| Colonne | Type | Description |
|---------|------|-------------|
| id | INTEGER PK | Auto-increment |
| sync_date | DATETIME | Date sync |
| leads_fetched | INTEGER | Nb leads récupérés |
| status | TEXT | running/completed/failed |
| error_message | TEXT | Message erreur |

**Table: lead_interactions**
| Colonne | Type | Description |
|---------|------|-------------|
| id | INTEGER PK | Auto-increment |
| getsales_lead_uuid | TEXT | UUID lead |
| hubspot_contact_id | TEXT | ID contact HubSpot |
| interaction_type | TEXT | message_sent/read/reply |
| interaction_date | DATETIME | Date interaction |
| message_text | TEXT | Contenu message |
| flow_name | TEXT | Nom campagne |
| synced_to_hubspot | BOOLEAN | Déjà sync? |

### API GetSales

**Base URL**: `https://amazing.getsales.io`

**Endpoints utilisés:**
- `POST /leads/api/leads/search` - Récupérer leads
- `GET /flows/api/linkedin-messages?filter[lead_uuid]=xxx` - Messages
- `GET /flows/api/flows` - Liste campagnes

**Authentification**: Bearer token (API key)

### Propriétés custom HubSpot

À créer une fois via script:
- `getsales_uuid` (text) - UUID GetSales
- `getsales_source` (boolean) - Provient de GetSales
- `getsales_linkedin_id` (text) - ID LinkedIn
- `getsales_headline` (text) - Titre LinkedIn
- `getsales_bio` (textarea) - Bio LinkedIn
- `getsales_last_interaction` (date) - Dernière interaction
- `getsales_campaign` (text) - Nom campagne

---

## Configuration

**.env (ajouter)**
```
GETSALES_API_KEY=your_getsales_api_key_here
```

**requirements.txt (déjà présent)**
```
httpx>=0.25.0  # Déjà ajouté pour lead_scraper
```

---

## Interface UI

### Page 4_🔄_GetSales_Sync.py

**Section 1: Contrôle sync**
- Dernière sync (date, statut, nb leads)
- Bouton "Synchroniser maintenant"
- Spinner pendant sync

**Section 2: File de validation**
- Filtres: statut validation, présence doublon
- Metric: nb leads en attente
- Liste expandable des leads
  - Infos GetSales (nom, email, entreprise, LinkedIn)
  - Interactions (nb messages, dernière date)
  - Doublons détectés (badge warning)
  - Boutons actions (Créer/Merger/Rejeter)

**Section 3: Formulaire merge (conditionnel)**
- Comparaison côte à côte par champ
- Radio buttons GetSales/HubSpot
- Boutons Confirmer/Annuler

---

## Stratégie de déduplication

1. **Match LinkedIn URL** (priorité 1, confiance HIGH)
   - Format: `https://www.linkedin.com/in/{id}`
   - Recherche dans propriété `linkedin_url` HubSpot

2. **Match Email** (priorité 2, confiance HIGH)
   - Recherche exacte dans HubSpot
   - Seulement si pas de match LinkedIn

3. **Pas de fuzzy matching** (complexité évitée en v1)

---

## Gestion des erreurs

- **Rate limit GetSales**: Retry avec backoff exponentiel (2s, 4s, 8s)
- **Timeout**: 30s par requête
- **API down**: Message utilisateur + log erreur
- **Validation échouée**: Rollback + message explicite

---

## Phases d'implémentation

### Phase 1: Setup & Test API (2 jours)
- T4.1.1: Créer `modules/getsales/getsales_client.py`
- T4.1.2: Script test API `scripts/test_getsales_api.py`
- T4.1.3: Analyser structure données réelles

### Phase 2: Modèles & Déduplication (2 jours)
- T4.2.1: Créer `modules/getsales/models.py` (SQLite)
- T4.2.2: Créer `modules/getsales/deduplication.py`
- T4.2.3: Script init propriétés HubSpot

### Phase 3: Service sync (2 jours)
- T4.3.1: Créer `modules/getsales/sync_service.py`
- T4.3.2: Implémenter fetch + stockage pending
- T4.3.3: Implémenter validation + push HubSpot
- T4.3.4: Implémenter sync interactions

### Phase 4: Interface Streamlit (2 jours)
- T4.4.1: Créer page `pages/4_🔄_GetSales_Sync.py`
- T4.4.2: Section contrôle sync
- T4.4.3: Section file validation
- T4.4.4: Formulaire merge

### Phase 5: Tests & Polish (1 jour)
- T4.5.1: Tests end-to-end
- T4.5.2: Gestion erreurs
- T4.5.3: Logging
- T4.5.4: Mise à jour home page

**Durée totale**: ~9 jours

---

## Évolutions futures (v2)

- Dashboard analytics (taux conversion, ROI)
- Sync automatique (scheduler)
- Bidirectionnel HubSpot → GetSales
- Auto-enrichissement contacts existants
- Webhooks temps réel

---

## Références

- API GetSales: https://api.getsales.io
- HubSpot API: https://developers.hubspot.com
- Spec 002 Lead Scraper: Pattern similaire pour HubSpot client
