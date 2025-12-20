# Research - Portail Sales Ops

## API Asana

### Authentification
- **Personal Access Token (PAT)** : recommandé pour usage interne
- Génération : Settings → Apps → Developer Apps → Personal Access Tokens
- Format : `Bearer {token}` dans header Authorization

### Endpoints clés

```
GET /workspaces                     # Liste des workspaces
GET /projects?workspace={id}        # Projets d'un workspace
GET /projects/{id}/tasks            # Tâches d'un projet
GET /tasks/{id}                     # Détail d'une tâche
POST /tasks                         # Créer une tâche
GET /projects/{id}/custom_fields    # Custom fields d'un projet
```

### Rate Limits
- 1500 requests/minute par utilisateur
- Pagination : 100 items max par page
- Retry avec backoff exponentiel recommandé

### SDK Python
```bash
pip install asana
```
```python
import asana
client = asana.Client.access_token('PAT')
```

---

## Custom Fields Asana

### Création
1. Ouvrir le projet Asana
2. Clic droit sur header → "Add column" (vue List) ou "Customize" (vue Board)
3. Types supportés : Text, Number, Dropdown, Date, People

### Accès API
```python
# Récupérer les custom fields d'un projet
custom_fields = client.custom_fields.get_custom_fields_for_project(project_gid)

# Créer une tâche avec custom fields
task = client.tasks.create_task({
    'name': 'Opportunité XYZ',
    'projects': [project_gid],
    'custom_fields': {
        'montant_gid': 50000,
        'etape_gid': 'option_gid_qualification'
    }
})
```

---

## Sync Google Sheets (rappel)

### Méthode existante
Le repo actuel utilise déjà `gspread` avec Service Account.

### Sync incrémentale
```python
# Trouver la dernière ligne
last_row = len(worksheet.get_all_values())

# Ajouter uniquement les nouvelles lignes
new_data = [row for row in data if row['updated_at'] > last_sync]
worksheet.append_rows(new_data)
```

---

## Mapping Lead → Opportunité Asana

| Champ Lead | Champ Asana | Notes |
|------------|-------------|-------|
| denomination | name | Titre de la tâche |
| email, telephone, dirigeant | notes | Description formatée |
| siren | custom_field:siren | Custom field texte |
| score | custom_field:score_lead | Custom field number |
| - | custom_field:montant | À remplir manuellement |
| - | custom_field:etape | "Qualification" par défaut |
| - | assignee | Commercial connecté ou à choisir |

### Format description suggéré
```
**Contact:** Jean Dupont (CEO)
**Email:** j.dupont@example.com
**Téléphone:** +33 1 23 45 67 89
**SIREN:** 123456789
**Score Lead:** 85/100 (Hot)

---
Source: Lead enrichi le 20/12/2025
```

---

## Alternatives considérées

### Pourquoi pas Notion au lieu d'Asana ?
- Asana déjà utilisé chez Genie Factory
- API Asana plus mature pour les custom fields
- Notion API limitée pour les databases relationnelles

### Pourquoi pas un CRM dédié (Pipedrive, etc.) ?
- Coût supplémentaire
- Duplication avec HubSpot existant
- Asana suffit pour le pipeline simple

---

## Prochaines recherches à faire

- [ ] Vérifier la structure exacte du projet Asana "Sales Pipeline" existant
- [ ] Identifier les custom fields déjà créés vs à créer
- [ ] Tester les permissions du PAT sur les opérations write
