# Constitution - Portail Sales Ops Genie Factory

## Principes Fondamentaux

### 1. Simplicité avant tout
- Pas d'usine à gaz : chaque module reste autonome et maintenable
- Une fonctionnalité = un besoin métier clair
- Code lisible > code clever

### 2. Architecture modulaire
- Les modules communiquent via des interfaces simples (fichiers JSON, API REST)
- Chaque module peut évoluer indépendamment
- Pas de couplage fort entre modules

### 3. Données comme source de vérité
- Un lead enrichi = une seule source (pas de duplication)
- Sync bidirectionnelle avec les outils externes (Asana, HubSpot)
- Traçabilité des modifications

### 4. UX Sales-first
- L'interface doit être utilisable par un commercial sans formation
- Actions en 1-2 clics maximum
- Feedback visuel immédiat (scores, statuts)

### 5. Philosophie du portail
- Un portail = plusieurs outils indépendants
- Chaque outil résout UN problème métier
- Les outils peuvent communiquer entre eux (optionnel)
- On développe un outil à la fois, pas tout d'un coup

## Standards Techniques

### Stack
- **Frontend** : Streamlit (Python) - simple et rapide
- **Backend** : Python 3.11+
- **Data** : SQLite local + JSON pour le cache
- **APIs** : REST pour les intégrations externes

### Qualité
- Tests unitaires pour la logique métier critique (scoring, enrichissement)
- Logs structurés pour le debugging
- Gestion d'erreurs explicite (pas de fail silencieux)

### Sécurité
- Clés API dans `.env` uniquement
- Pas de secrets dans le code
- Validation des inputs utilisateur

## Contraintes Projet

### Ce qu'on fait
- Portail unifié pour l'équipe sales
- Modules indépendants et évolutifs
- Premier module : Dashboard Pipeline CFO (sync Asana → Google Sheets)

### Ce qu'on ne fait PAS (pour l'instant)
- Module prospection/enrichissement (viendra plus tard)
- Authentification utilisateur (hors scope v1)
- Multi-tenant (un seul tenant Genie Factory)
- App mobile
