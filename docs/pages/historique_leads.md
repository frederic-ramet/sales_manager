# Historique des Leads

Consultation et gestion des leads précédemment recherchés et exportés.

---

## Fonctionnalités

### Historique des recherches
- Liste de toutes les recherches effectuées
- Critères utilisés pour chaque recherche
- Nombre de résultats obtenus

### Base locale des leads
- Tous les leads enrichis sont stockés localement
- Consultation sans refaire d'appels API
- Données disponibles hors-ligne

### Suivi des exports
- Historique des exports vers HubSpot
- Statut de chaque lead (exporté, en attente, erreur)
- Lien vers le contact HubSpot

---

## Comment utiliser

### 1. Consulter les recherches passées
- Parcourez la liste des recherches
- Cliquez sur une recherche pour voir les résultats

### 2. Filtrer les leads
Utilisez les filtres pour trouver des leads spécifiques :
- Par statut d'export
- Par date de recherche
- Par critères (NAF, localisation...)

### 3. Ré-exporter des leads
- Sélectionnez des leads non encore exportés
- Cliquez sur "Exporter vers HubSpot"

### 4. Nettoyer l'historique
- Supprimez les anciennes recherches
- Purgez les leads obsolètes

---

## Statuts des leads

| Statut | Description |
|--------|-------------|
| Nouveau | Lead jamais exporté |
| Exporté | Envoyé vers HubSpot avec succès |
| Doublon | Existe déjà dans HubSpot |
| Erreur | Échec de l'export |

---

## Données stockées

### Pour chaque lead
- SIREN / SIRET
- Raison sociale
- Adresse complète
- Code NAF et libellé
- Effectifs et CA (si enrichi)
- Dirigeants (si enrichi)
- Date de recherche
- Statut d'export

### Pour chaque recherche
- Date et heure
- Critères utilisés
- Nombre de résultats
- Utilisateur (si multi-user)

---

## Stockage

Les données sont stockées localement en SQLite :

```
data/
└── leads.db    # Base de données locale
```

Cette base permet :
- Consultation rapide sans appels API
- Travail hors-ligne
- Historique complet des recherches

---

## Bonnes pratiques

1. **Consultez l'historique** avant de lancer une nouvelle recherche
2. **Évitez les doublons** : vérifiez si le lead existe déjà
3. **Nettoyez régulièrement** : supprimez les recherches obsolètes
4. **Exportez par lots** : groupez les exports pour optimiser les appels API
