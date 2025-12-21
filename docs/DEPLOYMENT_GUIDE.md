# Guide de Déploiement - Sales Manager

Guide pratique pour déployer l'application Sales Manager avec Docker et Dockploy.

---

## 🚀 Quick Start

### 1. Test local avec Docker

```bash
# Cloner le repo
git clone https://github.com/your-org/sales_manager.git
cd sales_manager

# Copier .env.example vers .env et remplir les secrets
cp .env.example .env
nano .env  # Ajouter vos API keys

# Build et lancer avec Docker Compose
docker-compose up --build

# Accéder à l'app
open http://localhost:8501
```

### 2. Déploiement Dockploy

```bash
# 1. Créer compte Dockploy (https://dockploy.com)

# 2. Connecter votre repo GitHub
#    - Settings > Integrations > GitHub
#    - Autoriser accès au repo sales_manager

# 3. Créer nouveau projet
#    - New Project > sales-manager
#    - Type: Docker
#    - Repository: your-org/sales_manager
#    - Branch: main
#    - Config file: dockploy.json (auto-détecté)

# 4. Configurer secrets
#    Settings > Environment Variables > Add Secret
#    - HUBSPOT_API_KEY
#    - GETSALES_API_KEY
#    - PAPPERS_API_KEY

# 5. Configurer domaine
#    Settings > Domain
#    - Domain: sales.geniefactory.com
#    - SSL: Auto (Let's Encrypt)

# 6. Déployer!
#    Click "Deploy" → attendre build (3-5 min)
```

---

## 📋 Prérequis

### Pour développement local

- Docker Desktop installé
- Git
- Éditeur de code (VS Code recommandé)

### Pour déploiement Dockploy

- Compte Dockploy
- Serveur avec Docker (min 2GB RAM, 10GB disk)
- Domaine DNS configuré
- API keys:
  - HubSpot Private App Token
  - GetSales API Key
  - Pappers API Key

---

## 🐳 Build et test Docker local

### Build l'image

```bash
# Build simple
docker build -t sales-manager:latest .

# Build avec cache optimisé (BuildKit)
DOCKER_BUILDKIT=1 docker build -t sales-manager:latest .

# Build multi-plateforme
docker buildx build --platform linux/amd64,linux/arm64 -t sales-manager:latest .
```

### Lancer le container

```bash
# Avec docker-compose (recommandé)
docker-compose up

# Ou directement avec docker run
docker run -d \
  --name sales-manager \
  -p 8501:8501 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  sales-manager:latest

# Voir les logs
docker logs -f sales-manager

# Arrêter
docker-compose down
```

### Tester health check

```bash
# Vérifier que le container est healthy
docker ps

# Tester endpoint health
curl http://localhost:8501/_stcore/health

# Expected output:
# {"status":"ok"}
```

---

## 🔐 Configuration des secrets

### En développement local (.env)

```bash
# Copier template
cp .env.example .env

# Éditer avec vos vraies valeurs
nano .env
```

**.env:**
```bash
HUBSPOT_API_KEY=pat-na1-xxxxxxxx
GETSALES_API_KEY=gs_xxxxxxxx
PAPPERS_API_KEY=pap_xxxxxxxx

ENVIRONMENT=development
LOG_LEVEL=INFO
```

### En production (Dockploy)

**Via UI:**
1. Projet > Settings > Environment Variables
2. Click "+ Add Secret"
3. Name: `HUBSPOT_API_KEY`
4. Value: `pat-na1-xxxxxxxx`
5. Type: Secret ✓ (masqué)
6. Save

**Via API:**
```bash
curl -X POST https://api.dockploy.com/v1/apps/sales-manager/secrets \
  -H "Authorization: Bearer $DOCKPLOY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "HUBSPOT_API_KEY": "pat-na1-xxxxx",
    "GETSALES_API_KEY": "gs_xxxxx",
    "PAPPERS_API_KEY": "pap_xxxxx"
  }'
```

---

## 📦 Volumes et données persistantes

### Volumes configurés

| Volume | Path | Usage | Taille |
|--------|------|-------|--------|
| data | /app/data | Databases SQLite | 5GB |
| logs | /app/logs | Application logs | 1GB |

### Backup manuel

```bash
# Exporter données depuis container Dockploy
dockploy exec sales-manager -- tar czf /tmp/backup.tar.gz /app/data

# Télécharger
dockploy cp sales-manager:/tmp/backup.tar.gz ./backup-$(date +%Y%m%d).tar.gz

# Ou avec docker local
docker exec sales-manager tar czf /tmp/backup.tar.gz /app/data
docker cp sales-manager:/tmp/backup.tar.gz ./backup.tar.gz
```

### Restauration

```bash
# Upload backup
dockploy cp ./backup-20251221.tar.gz sales-manager:/tmp/

# Extraire
dockploy exec sales-manager -- tar xzf /tmp/backup-20251221.tar.gz -C /app/

# Redémarrer app
dockploy restart sales-manager
```

### Backup automatique (configuré dans dockploy.json)

```json
{
  "backup": {
    "enabled": true,
    "schedule": "0 2 * * *",  // Quotidien à 2h
    "retention": 7,           // Garder 7 jours
    "volumes": ["data"]
  }
}
```

---

## 🌍 Environnements multiples

### Development (local)

```bash
# docker-compose.yml
ENVIRONMENT=development
LOG_LEVEL=DEBUG
STREAMLIT_SERVER_FILE_WATCHER_TYPE=auto  # Hot reload

docker-compose up
```

### Staging

```bash
# Branch: staging
# URL: staging.sales.geniefactory.com

git push origin staging
# Auto-deploy via GitHub Actions
```

### Production

```bash
# Branch: main
# URL: sales.geniefactory.com

git push origin main
# Auto-deploy via GitHub Actions (avec approval manuel)
```

---

## 🔄 CI/CD avec GitHub Actions

### Configuration

Fichier `.github/workflows/deploy.yml` déjà configuré.

**Secrets GitHub à ajouter:**

Repository Settings > Secrets and variables > Actions:

```
DOCKPLOY_TOKEN: <votre_token_dockploy>
```

### Workflow

```
Push main → Run tests → Build Docker → Deploy production
Push staging → Run tests → Build Docker → Deploy staging
Pull Request → Run tests → Build Docker (sans deploy)
```

### Déclencher un déploiement

```bash
# Auto-deploy sur push
git commit -m "feat: nouvelle fonctionnalité"
git push origin main

# Voir progression
# GitHub > Actions > Build and Deploy

# Rollback si problème
git revert HEAD
git push origin main
```

---

## 🔧 Troubleshooting

### Container ne démarre pas

```bash
# Vérifier logs
docker logs sales-manager
# ou
dockploy logs sales-manager --tail 100

# Erreurs communes:
# - "No module named 'streamlit'" → requirements.txt mal installé
# - "Permission denied" → problème user/permissions dans Dockerfile
# - Port 8501 déjà utilisé → changer port dans docker-compose.yml
```

### Health check échoue

```bash
# Tester manuellement
docker exec sales-manager curl localhost:8501/_stcore/health

# Si timeout:
# - Augmenter start_period dans healthcheck (Dockerfile)
# - Vérifier que Streamlit démarre (voir logs)

# Si 404:
# - Streamlit pas sur bonne route
# - Vérifier CMD dans Dockerfile
```

### Données perdues après redéploiement

```bash
# Vérifier volumes persistants
dockploy volumes list

# Vérifier montage
dockploy exec sales-manager -- ls -la /app/data

# Si vide → restaurer backup
dockploy cp ./backup.tar.gz sales-manager:/tmp/
dockploy exec sales-manager -- tar xzf /tmp/backup.tar.gz -C /app/
```

### Lenteur / performance

```bash
# Vérifier ressources
docker stats sales-manager
# ou
dockploy stats sales-manager

# Si mémoire saturée:
# - Augmenter limit dans dockploy.json
# - Vérifier memory leaks (logs)

# Optimiser SQLite
docker exec sales-manager sqlite3 /app/data/leads.db "VACUUM; ANALYZE;"
```

---

## 📊 Monitoring

### Logs en temps réel

```bash
# Docker local
docker logs -f sales-manager

# Dockploy
dockploy logs sales-manager --follow

# Filtrer par niveau
dockploy logs sales-manager | grep ERROR
```

### Métriques (optionnel)

Si Prometheus configuré, accéder à:
```
https://sales.geniefactory.com/metrics
```

---

## ✅ Checklist post-déploiement

Après chaque déploiement production:

- [ ] Health check OK (`curl https://sales.geniefactory.com/_stcore/health`)
- [ ] Login fonctionne
- [ ] Navigation entre pages OK
- [ ] Sync HubSpot teste (1-2 contacts)
- [ ] Import GetSales teste
- [ ] Recherche SIRENE teste
- [ ] Logs sans erreur critique
- [ ] Données persistantes vérifiées
- [ ] Backup automatique configuré
- [ ] SSL certificat valide (Let's Encrypt)

---

## 🆘 Support

**Problème avec Docker:**
- [Docker Documentation](https://docs.docker.com/)
- [Streamlit Docker Guide](https://docs.streamlit.io/knowledge-base/tutorials/deploy/docker)

**Problème avec Dockploy:**
- [Dockploy Docs](https://docs.dockploy.com/)
- [Dockploy Discord](https://discord.gg/dockploy)

**Problème applicatif:**
- Vérifier logs: `dockploy logs sales-manager --tail 200`
- Ouvrir issue GitHub si bug

---

**Dernière mise à jour:** 2025-12-21
