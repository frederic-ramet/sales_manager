# GetSales Sync

Synchronisation des leads LinkedIn prospectés via GetSales.io vers HubSpot CRM.

---

## Fonctionnalités

### Import depuis GetSales
- Récupération des leads des campagnes LinkedIn
- Import des messages et interactions
- Stockage local avant validation

### Détection des doublons
- Matching par URL LinkedIn
- Matching par email
- Affichage des correspondances HubSpot

### Validation manuelle
- File d'attente des leads à valider
- 3 actions possibles : créer, fusionner, rejeter
- Formulaire de merge champ par champ

### Suivi des interactions
- Historique des messages LinkedIn
- Conversion en notes HubSpot (optionnel)

---

## Comment utiliser

### 1. Configurer l'API GetSales
Dans `.env`, ajoutez votre clé API :
```bash
GETSALES_API_KEY=xxx
```

### 2. Lancer une synchronisation
1. Cliquez sur **"Synchroniser GetSales"**
2. Les leads sont importés et analysés
3. Les doublons potentiels sont détectés

### 3. Valider les leads

Pour chaque lead dans la file :

**Créer nouveau** (vert)
- Aucun doublon détecté
- Crée un nouveau contact HubSpot

**Fusionner** (orange)
- Doublon potentiel trouvé
- Ouvrez le formulaire de merge
- Choisissez champ par champ quelle valeur garder

**Rejeter** (rouge)
- Lead non pertinent
- Marque comme rejeté (ne sera plus proposé)

### 4. Consulter les interactions
- Développez un lead pour voir ses messages
- Les échanges LinkedIn sont affichés chronologiquement

---

## File de validation

### Filtres disponibles

| Filtre | Options |
|--------|---------|
| Statut | En attente, Validé, Rejeté |
| Doublons | Tous, Avec doublons, Sans doublons |
| Campagne | Filtrer par campagne GetSales |

### Informations affichées

Pour chaque lead :
- Nom complet et titre
- Entreprise et poste
- URL LinkedIn
- Email (si disponible)
- Nombre de messages échangés
- Statut de doublon

---

## Formulaire de merge

Quand un doublon est détecté, le formulaire affiche :

| Champ | Valeur GetSales | Valeur HubSpot |
|-------|-----------------|----------------|
| Prénom | Jean | Jean-Pierre |
| Nom | Dupont | Dupont |
| Email | jean@acme.com | jp@acme.com |
| ... | ... | ... |

Pour chaque champ, choisissez :
- **GetSales** : utiliser la nouvelle valeur
- **HubSpot** : garder la valeur existante
- **Manuel** : saisir une valeur personnalisée

---

## Workflow recommandé

```
1. Sync quotidienne
   └── Récupérer les nouveaux leads GetSales

2. Validation par lot
   └── Traiter 10-20 leads à la fois

3. Merge des doublons
   └── Enrichir les contacts existants

4. Suivi
   └── Vérifier dans HubSpot
```

---

## Configuration requise

```bash
# Dans .env
GETSALES_API_KEY=xxx    # Clé API GetSales.io
HUBSPOT_API_KEY=xxx     # Pour déduplication et export
```

### Obtenir la clé GetSales
1. Connectez-vous sur https://app.getsales.io
2. Allez dans Settings → API
3. Générez une clé API
4. Copiez dans `.env`

---

## Statuts des leads

| Statut | Description |
|--------|-------------|
| pending | En attente de validation |
| approved | Validé et exporté vers HubSpot |
| rejected | Rejeté (ne sera plus proposé) |
| merged | Fusionné avec un contact existant |

---

## Bonnes pratiques

1. **Synchronisez régulièrement** : une fois par jour minimum
2. **Traitez les doublons** : ils enrichissent vos données existantes
3. **Vérifiez les emails** : souvent plus fiables que les noms
4. **Consultez les messages** : le contexte aide à la qualification
