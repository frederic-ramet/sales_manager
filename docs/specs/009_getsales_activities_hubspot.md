# Epic 009 - GetSales Activities & Campaign Tracking in HubSpot

## Contexte

Actuellement, quand un contact GetSales est créé dans HubSpot :
- ✅ Le contact est créé avec ses données (nom, entreprise, fonction)
- ✅ L'entreprise est associée
- ❌ Aucune activité n'est tracée (messages LinkedIn)
- ❌ Le segment/campagne GetSales n'est pas visible

## Objectif

Tracer dans HubSpot :
1. **La campagne/flow GetSales** d'origine (segment de ciblage)
2. **Les interactions LinkedIn** (messages envoyés, réponses reçues)
3. **Une note récapitulative** de la prospection

---

## Données GetSales disponibles

### 1. Lead data
```json
{
  "uuid": "abc-123",
  "first_name": "Steven",
  "last_name": "FERREIRA",
  "email": "steven@d-groupe.com",
  "company_name": "D-GROUPE",
  "position": "DSI",
  "linkedin": "stevenferreira",
  "headline": "DSI chez D-GROUPE | Transformation digitale",
  "about": "Passionné par l'innovation..."
}
```

### 2. Messages LinkedIn (`_messages`)
```json
[
  {
    "type": "outbox",
    "status": "read",
    "text": "Bonjour Steven, je me permets de vous contacter...",
    "sent_at": "2025-12-15T10:30:00Z",
    "flow_name": "Campagne DSI Île-de-France"
  },
  {
    "type": "inbox",
    "text": "Bonjour, merci pour votre message...",
    "sent_at": "2025-12-16T14:22:00Z"
  }
]
```

### 3. Flows (campagnes)
```json
{
  "uuid": "flow-456",
  "name": "Campagne DSI Île-de-France",
  "status": "active"
}
```

---

## Solution proposée

### 1. Nouvelles propriétés custom HubSpot (Contact)

| Propriété | Type | Description |
|-----------|------|-------------|
| `getsales_flow_name` | text | Nom de la campagne GetSales |
| `getsales_flow_uuid` | text | UUID du flow GetSales |
| `getsales_first_contact_date` | date | Date du premier message envoyé |
| `getsales_last_interaction_date` | date | Date de la dernière interaction |
| `getsales_interaction_count` | number | Nombre d'interactions |
| `getsales_has_replied` | boolean | A répondu (inbox message) |

### 2. Création d'une Note HubSpot

Lors de la création du contact, créer une **Note** (engagement) avec le récapitulatif :

```
📧 Prospection LinkedIn via GetSales

🎯 Campagne: Campagne DSI Île-de-France
📅 Premier contact: 15/12/2025
💬 Messages échangés: 3

--- Historique des messages ---

[15/12/2025 10:30] ➡️ Message envoyé (lu ✓)
"Bonjour Steven, je me permets de vous contacter..."

[16/12/2025 14:22] ⬅️ Réponse reçue
"Bonjour, merci pour votre message..."

[17/12/2025 09:00] ➡️ Message envoyé (lu ✓)
"Merci pour votre retour..."
```

### 3. API HubSpot pour les Notes

Endpoint: `POST /crm/v3/objects/notes`

```json
{
  "properties": {
    "hs_timestamp": "2025-12-15T10:30:00Z",
    "hs_note_body": "📧 Prospection LinkedIn via GetSales\n\n🎯 Campagne: ..."
  },
  "associations": [
    {
      "to": { "id": "contact_id" },
      "types": [{ "associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202 }]
    }
  ]
}
```

---

## Implémentation

### Fichiers à modifier

1. **`modules/lead_scraper/hubspot_client.py`**
   - Ajouter propriétés custom (`getsales_flow_name`, etc.)
   - Ajouter méthode `create_note(contact_id, body, timestamp)`

2. **`modules/getsales/sync_service.py`**
   - Modifier `_create_hubspot_contact()` pour :
     - Remplir les propriétés de campagne
     - Créer la note récapitulative
   - Modifier `_sync_interactions()` pour créer la note dans HubSpot

3. **`modules/getsales/getsales_client.py`**
   - Enrichir `fetch_leads()` pour inclure le `flow_uuid` et `flow_name`
   - Ou ajouter méthode pour récupérer le flow d'un lead

---

## Comportement attendu

### Avant (actuel)
```
Contact HubSpot:
  - Steven FERREIRA
  - DSI chez D-GROUPE
  - Entreprises: D-GROUPE
  - Activités: (vide)
```

### Après
```
Contact HubSpot:
  - Steven FERREIRA
  - DSI chez D-GROUPE
  - Entreprises: D-GROUPE
  - Propriétés custom:
    - GetSales Flow: "Campagne DSI Île-de-France"
    - Premier contact: 15/12/2025
    - A répondu: Oui
    - Nb interactions: 3
  - Activités:
    - Note "📧 Prospection LinkedIn via GetSales" (15/12/2025)
```

---

## Questions ouvertes

1. **Récupération du flow** - L'API GetSales retourne-t-elle le `flow_uuid` dans les données du lead, ou faut-il faire une requête séparée ?

2. **Mise à jour des notes** - Si de nouvelles interactions arrivent après la création du contact, faut-il :
   - Mettre à jour la note existante ?
   - Créer une nouvelle note ?

3. **Timeline HubSpot** - Faut-il créer un **custom timeline event** plutôt qu'une simple note ?

---

## Estimation

- Propriétés custom : 30 min
- Méthode create_note : 1h
- Enrichissement sync_service : 2h
- Tests : 1h

**Total : ~4h30**
