# Recherche de Leads

Recherche et enrichissement de leads B2B via les bases SIRENE et Pappers.

---

## Fonctionnalités

### Recherche d'entreprises
- **Recherche classique** : par secteur, localisation, taille
- **Recherche en langage naturel** : décrivez votre cible, Claude AI génère les filtres

### Enrichissement automatique
- Données légales (SIREN, forme juridique, capital)
- Données financières (chiffre d'affaires, effectifs)
- Contacts dirigeants (si disponibles via Pappers)

### Export vers HubSpot
- Création automatique de contacts/entreprises
- Déduplication intelligente
- Historique des exports

---

## Comment utiliser

### 1. Choisir le mode de recherche

**Mode classique :**
- Sélectionnez les critères dans les filtres
- Code NAF, département, tranche d'effectifs, etc.

**Mode langage naturel :**
- Tapez votre recherche en français
- Exemple : "ESN de plus de 50 salariés en Île-de-France"
- Claude AI convertit en filtres techniques

### 2. Lancer la recherche
Cliquez sur **"Rechercher"** pour interroger la base SIRENE.

### 3. Enrichir les résultats (optionnel)
Si Pappers est configuré :
- Sélectionnez les entreprises à enrichir
- Cliquez sur "Enrichir" pour obtenir plus de données

### 4. Exporter vers HubSpot
- Sélectionnez les leads à exporter
- Cliquez sur "Exporter vers HubSpot"
- Les doublons sont automatiquement détectés

---

## Filtres disponibles

| Filtre | Description | Exemple |
|--------|-------------|---------|
| Code NAF | Secteur d'activité | 6201Z (programmation) |
| Département | Localisation | 75, 92, 69... |
| Effectifs | Tranche de salariés | 10-49, 50-99... |
| Forme juridique | Type de société | SAS, SARL, SA... |
| Date création | Ancienneté | Depuis 2020 |

---

## Sources de données

### SIRENE (gratuit)
- Base officielle INSEE
- Toutes les entreprises françaises
- Données de base : SIREN, adresse, NAF, effectifs

### Pappers (enrichissement)
- Données financières détaillées
- Dirigeants et contacts
- Documents légaux
- **Requiert une clé API payante**

---

## Configuration requise

```bash
# Dans .env

# Obligatoire pour l'enrichissement
PAPPERS_API_KEY=xxx

# Optionnel - Export HubSpot
HUBSPOT_API_KEY=xxx

# Optionnel - Recherche langage naturel
ANTHROPIC_API_KEY=xxx
```

---

## Bonnes pratiques

1. **Affinez vos critères** : des recherches trop larges retournent trop de résultats
2. **Enrichissez par lot** : sélectionnez 10-20 leads à la fois
3. **Vérifiez avant export** : contrôlez les données avant envoi vers HubSpot
4. **Utilisez l'historique** : consultez vos recherches précédentes pour éviter les doublons
