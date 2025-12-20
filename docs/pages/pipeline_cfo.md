# Pipeline CFO

Synchronisation automatique des deals Asana vers Google Sheets pour le pilotage financier.

---

## Fonctionnalités

### Synchronisation Asana → Sheets
- Extraction automatique des deals depuis le projet Asana "Sales Pipeline"
- Calcul des revenus pondérés selon le niveau de confiance
- Export vers 4 onglets Google Sheets

### Scénarios financiers
Le système génère automatiquement 3 vues :
- **Pipeline complet** : tous les deals
- **Scénario conservateur** : deals avec confiance >= 4 (70%+)
- **Scénario probable** : deals avec confiance >= 3 (50%+)

### Planification automatique
- Sync automatique configurable (toutes les X heures)
- Historique des synchronisations

---

## Comment utiliser

### 1. Vérifier la configuration
Dans la sidebar, vérifiez que :
- Asana est connecté (token valide)
- Google Sheets est configuré (service account + URL)

### 2. Tester les connexions
Cliquez sur "Tester Asana" et "Tester Google Sheets" pour valider.

### 3. Lancer une synchronisation
Cliquez sur **"Synchroniser maintenant"** pour :
1. Récupérer les deals depuis Asana
2. Calculer les métriques financières
3. Mettre à jour le Google Sheet

### 4. Consulter les résultats
Ouvrez le Google Sheet pour voir :
- La liste des deals avec revenus pondérés
- Les scénarios conservateur et probable
- La date de dernière sync

---

## Données synchronisées

| Champ Asana | Description |
|-------------|-------------|
| Client | Nom du client |
| Projet | Nom du deal/projet |
| Estimated value | Budget estimé en € |
| Marge/Bénéfice | Marge prévue en € |
| Mois de facturation | Date de facturation prévue |
| Confidence Score | Niveau de confiance (1-5) |

### Calcul des probabilités

| Confidence | Probabilité | Interprétation |
|------------|-------------|----------------|
| 5 | 90% | Quasi-certain |
| 4 | 70% | Très probable |
| 3 | 50% | Probable |
| 2 | 25% | Incertain |
| 1 | 10% | Exploratoire |

### Métriques calculées

- **Revenue pondéré** = Budget × Probabilité
- **Marge %** = Marge / Budget × 100
- **Marge pondérée** = Marge × Probabilité

---

## Configuration requise

```bash
# Dans .env
ASANA_ACCESS_TOKEN=xxx      # Personal Access Token Asana
ASANA_PROJECT_GID=xxx       # ID du projet (visible dans l'URL)
GOOGLE_CREDENTIALS_PATH=credentials/service-account.json
GOOGLE_SPREADSHEET_URL=xxx  # URL complète du Sheet
```

### Obtenir les credentials

**Asana :**
1. Aller sur https://app.asana.com/0/my-apps
2. Créer un Personal Access Token
3. Copier dans `.env`

**Google Sheets :**
1. Créer un Service Account sur Google Cloud Console
2. Activer l'API Google Sheets
3. Télécharger le JSON et le placer dans `credentials/`
4. Partager le Sheet avec l'email du Service Account
