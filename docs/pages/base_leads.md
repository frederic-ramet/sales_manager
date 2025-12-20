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

## Stockage

Les données sont stockées localement en SQLite :

```
data/
└── leads.db    # Base de données locale
```

### Colonnes principales
- `siren` : Identifiant unique
- `source` : Origine du lead
- `denomination` : Nom de l'entreprise
- `email` / `telephone` : Coordonnées
- `hubspot_id` : Lien vers contact HubSpot
- `enriched_at` : Date d'enrichissement
- `full_data` : JSON complet des données

---

## Bonnes pratiques

1. **Vérifiez les doublons** avant d'importer de nouvelles données
2. **Enrichissez par lots** pour optimiser les appels API Pappers
3. **Synchronisez régulièrement** vers HubSpot pour maintenir votre CRM à jour
4. **Nettoyez périodiquement** les leads obsolètes
5. **Exportez une sauvegarde** CSV avant toute opération de masse
