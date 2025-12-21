# Base de Leads

Hub central de tous vos leads provenant de multiples sources.

---

## Vue d'ensemble

La Base de Leads centralise tous vos leads en un seul endroit, quelle que soit leur origine :

| Source | Description |
|--------|-------------|
| **SIRENE** | Leads extraits via l'API SIRENE |
| **HubSpot** | Contacts importés depuis HubSpot |
| **GetSales** | Leads LinkedIn validés via GetSales |

---

## Fonctionnalités

### Onglet "Tous les leads"

#### Filtres disponibles
- **Source** : Filtrer par origine (SIRENE, HubSpot, GetSales)
- **Statut enrichissement** : Leads enrichis ou non
- **Recherche** : Par SIREN, nom d'entreprise ou email
- **Nombre de résultats** : 50, 100, 200 ou 500

#### Colonnes affichées
- Source (avec icône)
- SIREN
- Dénomination
- Email
- Ville
- Code APE
- Date d'extraction

#### Actions batch
Sélectionnez plusieurs leads pour :
- **Enrichir avec Pappers** : Compléter les informations manquantes
- **Sync vers HubSpot** : Pousser les leads enrichis vers votre CRM
- **Supprimer** : Retirer les leads sélectionnés

#### Export
- Téléchargez vos leads filtrés au format CSV

---

### Onglet "Import HubSpot"

Importez vos contacts ou entreprises depuis HubSpot vers la base locale.

#### Options d'import
- **Type** : Contacts ou Entreprises
- **Limite** : Nombre maximum à importer (10-1000)

#### Filtres avancés (optionnel)
- **ID de liste HubSpot** : Importer uniquement une liste spécifique
- **Période** : Importer uniquement les leads créés récemment

#### Métriques
- Nombre de leads importés depuis HubSpot
- Nombre de leads synchronisés vers HubSpot

---

### Onglet "Gestion"

#### Répartition par source
Tableau récapitulatif montrant :
- Nombre de leads par source
- Pourcentage de la base totale

#### Campagnes récentes
- Liste des dernières campagnes d'extraction
- Possibilité de supprimer une campagne entière

#### Nettoyage
- Supprimer les leads plus vieux qu'un certain nombre de jours
- Réinitialisation complète de la base

#### Informations système
- Chemin de la base de données
- Taille du fichier
- Nombre total de leads

---

## Sources des leads

### SIRENE (source="sirene")
- Origine : API SIRENE de l'INSEE
- Données : Informations légales (SIREN, NAF, adresse)
- Enrichissement : Possible via Pappers

### HubSpot (source="hubspot")
- Origine : Import depuis HubSpot CRM
- Données : Contacts ou entreprises existants
- Enrichissement : Possible pour compléter les infos

### GetSales (source="getsales")
- Origine : Validation manuelle de leads LinkedIn
- Données : Profils LinkedIn avec interactions
- Enrichissement : Recommandé pour données entreprise

---

## Flux de données

```
┌─────────────────┐
│   API SIRENE    │──┐
└─────────────────┘  │
                     │
┌─────────────────┐  │     ┌─────────────────┐
│  Import HubSpot │──┼────▶│   BASE LEADS    │────▶ Export/Sync
└─────────────────┘  │     │    (SQLite)     │
                     │     └─────────────────┘
┌─────────────────┐  │            │
│ GetSales Valid. │──┘            ▼
└─────────────────┘       ┌─────────────────┐
                          │  Enrichissement │
                          │    (Pappers)    │
                          └─────────────────┘
```

---

## Statuts des leads

| Indicateur | Signification |
|------------|---------------|
| Non enrichi | Données brutes, pas encore complétées |
| Enrichi | Informations complétées via Pappers |
| Synchronisé | Exporté vers HubSpot |

---

## Schéma des données (unified_contacts)

Les données sont stockées localement en SQLite dans la table `unified_contacts` :

```
data/
└── leads.db    # Base de données locale
```

### Champs principaux

| Champ | Type | Description |
|-------|------|-------------|
| `uuid` | TEXT | Identifiant unique interne (UUID4) |
| `source` | TEXT | Origine : sirene, hubspot, getsales, csv_import |
| `siren` | TEXT | Numéro SIREN (9 chiffres) |
| `siret` | TEXT | Numéro SIRET (14 chiffres) |
| `company_name` | TEXT | Nom de l'entreprise |
| `email` | TEXT | Adresse email |
| `phone` | TEXT | Téléphone fixe |
| `firstname` | TEXT | Prénom du contact |
| `lastname` | TEXT | Nom du contact |
| `job_title` | TEXT | Fonction/poste |
| `linkedin_url` | TEXT | URL profil LinkedIn |
| `website` | TEXT | Site web de l'entreprise |
| `address` | TEXT | Adresse postale |
| `postal_code` | TEXT | Code postal |
| `city` | TEXT | Ville |
| `region` | TEXT | Région |
| `country` | TEXT | Pays |
| `ape_code` | TEXT | Code APE/NAF (secteur d'activité) |
| `employee_range` | TEXT | Tranche d'effectif |
| `revenue_range` | TEXT | Tranche de chiffre d'affaires |

### Champs de suivi

| Champ | Type | Description |
|-------|------|-------------|
| `campaign_id` | TEXT | Identifiant de la campagne d'extraction |
| `created_at` | DATETIME | Date de création |
| `updated_at` | DATETIME | Dernière modification |
| `enriched_at` | DATETIME | Date d'enrichissement Pappers |
| `hubspot_contact_id` | TEXT | ID du contact HubSpot lié |
| `synced_to_hubspot` | BOOLEAN | Synchronisé vers HubSpot ? |
| `last_sync_hubspot` | DATETIME | Date de dernière sync |
| `getsales_uuid` | TEXT | ID GetSales lié |
| `notes` | TEXT | Remarques libres |

---

## Mapping HubSpot

Lors du push vers HubSpot, les champs sont automatiquement mappés :

### Propriétés standard HubSpot

Ces propriétés existent par défaut dans tout compte HubSpot :

| Champ local | Propriété HubSpot | Description |
|-------------|-------------------|-------------|
| `email` | `email` | Adresse email (obligatoire) |
| `firstname` | `firstname` | Prénom |
| `lastname` | `lastname` | Nom |
| `phone` | `phone` | Téléphone |
| `company_name` | `company` | Nom d'entreprise |
| `job_title` | `jobtitle` | Fonction |
| `website` | `website` | Site web |
| `address` | `address` | Adresse |
| `city` | `city` | Ville |
| `postal_code` | `zip` | Code postal |
| `country` | `country` | Pays |

### Propriétés personnalisées (custom)

Ces propriétés sont **créées automatiquement** dans votre compte HubSpot lors du premier push :

| Champ local | Propriété HubSpot | Label dans HubSpot | Description |
|-------------|-------------------|-------------------|-------------|
| `siren` | `siren` | SIREN | Numéro SIREN de l'entreprise |
| `siret` | `siret` | SIRET | Numéro SIRET de l'établissement |
| `ape_code` | `code_ape` | Code APE/NAF | Code secteur d'activité |
| `employee_range` | `effectif` | Effectif | Tranche d'effectif |
| `revenue_range` | `chiffre_affaires` | Chiffre d'affaires | Tranche de CA |
| `linkedin_url` | `linkedin_url` | LinkedIn URL | URL du profil LinkedIn |
| (auto) | `import_source` | Source d'import | SIRENE, CSV, GetSales... |
| `notes` | `import_notes` | Notes d'import | Remarques et commentaires |
| `getsales_uuid` | `getsales_uuid` | GetSales UUID | Lien vers GetSales |

> 💡 **Note** : Les propriétés custom sont créées dans le groupe "Contact information" de HubSpot.

---

## Import CSV

### Colonnes reconnues automatiquement

L'import CSV détecte automatiquement les colonnes suivantes :

| Nom dans CSV | Champ cible | Variantes reconnues |
|--------------|-------------|---------------------|
| Entreprise | `company_name` | Société, Company, Raison sociale |
| Prénom | `firstname` | First Name, Prenom |
| Nom | `lastname` | Last Name, Nom de famille |
| Email | `email` | Mail, Courriel, E-mail |
| Téléphone | `phone` | Phone, Tel, Mobile |
| Fonction | `job_title` | Poste, Position, Job Title |
| SIREN | `siren` | N° SIREN, Numéro SIREN |
| Ville | `city` | City, Localité |
| Code postal | `postal_code` | CP, Zip, ZIP Code |
| LinkedIn | `linkedin_url` | URL LinkedIn, Profil LinkedIn |
| Notes | `notes` | Commentaire, Remarques, Comments |

---

## Bonnes pratiques

1. **Vérifiez les doublons** avant d'importer de nouvelles données
2. **Enrichissez par lots** pour optimiser les appels API Pappers
3. **Synchronisez régulièrement** vers HubSpot pour maintenir votre CRM à jour
4. **Nettoyez périodiquement** les leads obsolètes
5. **Exportez une sauvegarde** CSV avant toute opération de masse
