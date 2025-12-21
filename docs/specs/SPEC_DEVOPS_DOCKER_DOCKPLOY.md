# Spec: DevOps - Dockerisation et Déploiement Dockploy

**Version:** 1.0
**Date:** 2025-12-21
**Auteur:** Équipe Sales Manager
**Statut:** DRAFT

---

## 🎯 Objectif

Containeriser l'application Sales Manager avec Docker et la rendre déployable facilement via **Dockploy** pour permettre:
- Déploiement reproductible (dev, staging, production)
- Isolation de l'environnement
- Scalabilité future
- Sauvegarde et restauration simplifiées
- CI/CD automatisé

---

## 📋 Architecture cible

### Stack technique

```
┌─────────────────────────────────────────┐
│          Dockploy (Orchestration)       │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│     Docker Container (sales-manager)    │
├─────────────────────────────────────────┤
│  - Python 3.11                          │
│  - Streamlit App                        │
│  - SQLite databases                     │
│  - Cron jobs (optional)                 │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│         Docker Volumes (Persistence)    │
├─────────────────────────────────────────┤
│  - /app/data (databases)                │
│  - /app/logs (application logs)         │
│  - /app/.env (secrets - mounted)        │
└─────────────────────────────────────────┘
```

### Composants

| Composant | Description | Technologie |
|-----------|-------------|-------------|
| **Application** | Streamlit multi-page app | Python 3.11 + Streamlit |
| **Databases** | SQLite files (leads.db, getsales.db) | SQLite 3 |
| **Secrets** | API keys (HubSpot, GetSales, Pappers) | Environment variables |
| **Logs** | Application logs | Fichiers texte |
| **Orchestration** | Déploiement et gestion | Dockploy |

---

## 🐳 Dockerisation

### Dockerfile

```dockerfile
# ============================================
# Multi-stage build pour optimiser taille image
# ============================================

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /build

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# ============================================
# Stage 2: Runtime
# ============================================

FROM python:3.11-slim

# Metadata
LABEL maintainer="sales-ops@geniefactory.com"
LABEL description="Sales Manager - CRM & Lead Management Platform"
LABEL version="1.0"

# Create app user (non-root for security)
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app /app/data /app/logs && \
    chown -R appuser:appuser /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser . .

# Set PATH for user-installed packages
ENV PATH=/home/appuser/.local/bin:$PATH

# Switch to non-root user
USER appuser

# Expose Streamlit default port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Default command
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.fileWatcherType=none", \
     "--browser.gatherUsageStats=false"]
```

### .dockerignore

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/
.venv

# IDEs
.vscode/
.idea/
*.swp
*.swo

# Data (sera en volume)
data/
*.db
*.db-journal

# Logs
logs/
*.log

# Secrets
.env
.env.*
!.env.example

# Git
.git/
.gitignore

# Docs
docs/
*.md
!README.md

# Tests
tests/
.pytest_cache/

# OS
.DS_Store
Thumbs.db

# Docker
Dockerfile
docker-compose.yml
.dockerignore
```

### docker-compose.yml (pour dev local)

```yaml
version: '3.8'

services:
  sales-manager:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: sales-manager
    restart: unless-stopped

    ports:
      - "8501:8501"

    environment:
      # Streamlit config
      - STREAMLIT_SERVER_PORT=8501
      - STREAMLIT_SERVER_ADDRESS=0.0.0.0
      - STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

      # Application config
      - ENVIRONMENT=development
      - LOG_LEVEL=INFO
      - TZ=Europe/Paris

    env_file:
      - .env

    volumes:
      # Persistent data
      - ./data:/app/data
      - ./logs:/app/logs

      # Hot reload for development
      - ./app.py:/app/app.py
      - ./pages:/app/pages
      - ./modules:/app/modules
      - ./components:/app/components

    networks:
      - sales-network

    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501/_stcore/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

networks:
  sales-network:
    driver: bridge

volumes:
  data:
    driver: local
  logs:
    driver: local
```

---

## 🚀 Configuration Dockploy

### dockploy.json

Configuration pour Dockploy (fichier à la racine du repo).

```json
{
  "name": "sales-manager",
  "description": "Sales Manager - CRM & Lead Management Platform",
  "type": "docker",
  "docker": {
    "dockerfile": "Dockerfile",
    "buildArgs": {},
    "ports": [
      {
        "containerPort": 8501,
        "protocol": "http"
      }
    ],
    "volumes": [
      {
        "name": "data",
        "mountPath": "/app/data"
      },
      {
        "name": "logs",
        "mountPath": "/app/logs"
      }
    ],
    "environment": {
      "ENVIRONMENT": "production",
      "LOG_LEVEL": "WARNING",
      "TZ": "Europe/Paris",
      "STREAMLIT_SERVER_PORT": "8501",
      "STREAMLIT_SERVER_ADDRESS": "0.0.0.0",
      "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false"
    },
    "secrets": [
      "HUBSPOT_API_KEY",
      "GETSALES_API_KEY",
      "PAPPERS_API_KEY"
    ],
    "healthcheck": {
      "path": "/_stcore/health",
      "interval": 30,
      "timeout": 10,
      "retries": 3
    }
  },
  "deployment": {
    "strategy": "recreate",
    "resources": {
      "limits": {
        "memory": "1Gi",
        "cpu": "1000m"
      },
      "requests": {
        "memory": "512Mi",
        "cpu": "500m"
      }
    }
  },
  "domain": {
    "enabled": true,
    "hostname": "sales.geniefactory.com"
  },
  "ssl": {
    "enabled": true,
    "provider": "letsencrypt"
  },
  "backup": {
    "enabled": true,
    "schedule": "0 2 * * *",
    "retention": 7,
    "volumes": ["data"]
  }
}
```

### Procédure déploiement Dockploy

#### 1. Prérequis

- Compte Dockploy configuré
- Serveur avec Docker installé (min 2GB RAM, 10GB disk)
- Domaine pointé vers serveur
- Secrets API configurés dans Dockploy

#### 2. Configuration initiale

**Dans l'interface Dockploy:**

```bash
# 1. Créer nouveau projet
Name: sales-manager
Type: Docker
Repository: github.com/your-org/sales_manager
Branch: main

# 2. Configurer secrets (Settings > Secrets)
HUBSPOT_API_KEY=pat-na1-xxxxx
GETSALES_API_KEY=gs_xxxxx
PAPPERS_API_KEY=pap_xxxxx

# 3. Configurer volumes persistants
- data → /app/data
- logs → /app/logs

# 4. Configurer domaine
Domain: sales.geniefactory.com
SSL: Auto (Let's Encrypt)

# 5. Ressources
Memory: 512MB-1GB
CPU: 0.5-1 core
```

#### 3. Premier déploiement

```bash
# Option A: Via Dockploy UI
1. Cliquer "Deploy"
2. Attendre build (3-5 min)
3. Vérifier logs
4. Accéder https://sales.geniefactory.com

# Option B: Via CLI Dockploy
dockploy deploy sales-manager --wait

# Option C: Via Git push (si webhook configuré)
git push origin main
# Auto-deploy déclenché
```

#### 4. Vérification post-déploiement

```bash
# Check santé container
curl https://sales.geniefactory.com/_stcore/health

# Vérifier logs
dockploy logs sales-manager --tail 100

# Tester accès
open https://sales.geniefactory.com

# Vérifier volumes
dockploy exec sales-manager -- ls -la /app/data
```

---

## 🔐 Gestion des secrets

### Stratégie

**JAMAIS commiter secrets dans le code!**

```
✅ Secrets dans Dockploy (variables d'environnement)
✅ .env.example dans le repo (template)
❌ .env dans le repo
❌ API keys en dur dans code
```

### .env.example

```bash
# API Keys (remplacer par vraies valeurs)
HUBSPOT_API_KEY=your_hubspot_key_here
GETSALES_API_KEY=your_getsales_key_here
PAPPERS_API_KEY=your_pappers_key_here

# Application Config
ENVIRONMENT=production
LOG_LEVEL=INFO
TZ=Europe/Paris

# Streamlit Config
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0
STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
```

### Configuration secrets dans Dockploy

**Via UI:**
```
Settings > Environment Variables > Add Secret
- Name: HUBSPOT_API_KEY
- Value: pat-na1-xxxxx
- Type: Secret (masked)
```

**Via API:**
```bash
curl -X POST https://dockploy.io/api/v1/apps/sales-manager/secrets \
  -H "Authorization: Bearer $DOCKPLOY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "HUBSPOT_API_KEY": "pat-na1-xxxxx",
    "GETSALES_API_KEY": "gs_xxxxx",
    "PAPPERS_API_KEY": "pap_xxxxx"
  }'
```

---

## 💾 Persistence et volumes

### Volumes Docker

| Volume | Path | Usage | Backup |
|--------|------|-------|--------|
| **data** | /app/data | Databases SQLite (leads.db, getsales.db) | Quotidien |
| **logs** | /app/logs | Application logs | Hebdomadaire |

### Configuration volumes Dockploy

```json
{
  "volumes": [
    {
      "name": "data",
      "mountPath": "/app/data",
      "type": "persistent",
      "size": "5Gi",
      "backup": true
    },
    {
      "name": "logs",
      "mountPath": "/app/logs",
      "type": "persistent",
      "size": "1Gi",
      "backup": false
    }
  ]
}
```

### Stratégie backup

#### Backup automatique (Dockploy)

```json
{
  "backup": {
    "enabled": true,
    "schedule": "0 2 * * *",  // 2h du matin chaque jour
    "retention": 7,  // Garder 7 jours
    "volumes": ["data"],
    "destination": "s3://geniefactory-backups/sales-manager/"
  }
}
```

#### Backup manuel

```bash
# Exporter données
dockploy exec sales-manager -- tar czf /tmp/backup.tar.gz /app/data

# Télécharger backup
dockploy cp sales-manager:/tmp/backup.tar.gz ./backup-$(date +%Y%m%d).tar.gz

# Restaurer backup
dockploy cp ./backup-20251221.tar.gz sales-manager:/tmp/
dockploy exec sales-manager -- tar xzf /tmp/backup-20251221.tar.gz -C /app/
```

#### Script backup SQLite (à ajouter dans l'app)

```python
# scripts/backup_databases.py
import os
import shutil
from datetime import datetime
from pathlib import Path

def backup_databases():
    """Backup SQLite databases avec timestamp"""
    data_dir = Path("data")
    backup_dir = Path("data/backups")
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for db_file in data_dir.glob("*.db"):
        backup_path = backup_dir / f"{db_file.stem}_{timestamp}.db"
        shutil.copy2(db_file, backup_path)
        print(f"✅ Backup: {backup_path}")

    # Cleanup old backups (garder 30 derniers)
    backups = sorted(backup_dir.glob("*.db"), key=os.path.getmtime, reverse=True)
    for old_backup in backups[30:]:
        old_backup.unlink()
        print(f"🗑️  Supprimé: {old_backup}")

if __name__ == "__main__":
    backup_databases()
```

**Cron dans Docker (optionnel):**

```dockerfile
# Ajouter dans Dockerfile
RUN apt-get install -y cron

# Créer crontab
RUN echo "0 2 * * * cd /app && python scripts/backup_databases.py" | crontab -

# Modifier CMD pour lancer cron + streamlit
CMD cron && streamlit run app.py ...
```

---

## 📊 Monitoring et Logs

### Logs application

**Configuration Streamlit logging:**

```python
# config/logging_config.py
import logging
from pathlib import Path

def setup_logging():
    """Configure logging pour production"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "app.log"),
            logging.StreamHandler()  # Pour Dockploy logs
        ]
    )
```

### Accès logs Dockploy

```bash
# Logs temps réel
dockploy logs sales-manager --follow

# Dernières 100 lignes
dockploy logs sales-manager --tail 100

# Filtrer par niveau
dockploy logs sales-manager | grep ERROR

# Export logs
dockploy logs sales-manager --since 24h > logs-export.txt
```

### Métriques (optionnel - Prometheus)

```python
# modules/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge
import time

# Métriques
sync_hubspot_count = Counter('hubspot_sync_total', 'Total HubSpot syncs')
sync_hubspot_duration = Histogram('hubspot_sync_duration_seconds', 'HubSpot sync duration')
contacts_total = Gauge('contacts_total', 'Total contacts in database')

def track_sync():
    """Decorator pour tracker sync"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start = time.time()
            sync_hubspot_count.inc()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                sync_hubspot_duration.observe(time.time() - start)
        return wrapper
    return decorator
```

**Endpoint metrics:**

```python
# app.py - ajouter route /metrics
from prometheus_client import make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware

# Exposer metrics sur /metrics
app = DispatcherMiddleware(streamlit_app, {
    '/metrics': make_wsgi_app()
})
```

---

## 🔄 CI/CD avec GitHub Actions

### .github/workflows/deploy.yml

```yaml
name: Build and Deploy

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run tests
        run: pytest tests/ --cov=modules --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3

  build:
    needs: test
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v3

      - name: Log in to Container Registry
        uses: docker/login-action@v2
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v4
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}

      - name: Build and push Docker image
        uses: docker/build-push-action@v4
        with:
          context: .
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'

    steps:
      - name: Deploy to Dockploy
        uses: dockploy/deploy-action@v1
        with:
          token: ${{ secrets.DOCKPLOY_TOKEN }}
          app: sales-manager
          wait: true
```

### Secrets GitHub à configurer

```
Settings > Secrets and variables > Actions > New repository secret

- DOCKPLOY_TOKEN: Token API Dockploy
- HUBSPOT_API_KEY: (pour tests e2e si besoin)
```

---

## 🏗️ Build optimization

### Multi-stage build expliqué

```dockerfile
# Stage 1: Builder (image lourde avec outils compilation)
FROM python:3.11 as builder
# Compile dependencies avec gcc/g++
# Résultat: wheels compilés

# Stage 2: Runtime (image légère)
FROM python:3.11-slim
# Copie seulement packages compilés depuis builder
# Pas d'outils compilation → image 50% plus petite
```

**Tailles comparées:**
- Sans multi-stage: ~1.2GB
- Avec multi-stage: ~600MB

### Cache layers Docker

```dockerfile
# ✅ BIEN: Dependencies en premier (changent rarement)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Code app après (change souvent)
COPY . .

# ❌ MAL: Invalide cache à chaque changement code
COPY . .
RUN pip install -r requirements.txt
```

### Build local optimisé

```bash
# Build avec cache
docker build -t sales-manager:latest .

# Build sans cache (clean)
docker build --no-cache -t sales-manager:latest .

# Build avec BuildKit (parallèle, plus rapide)
DOCKER_BUILDKIT=1 docker build -t sales-manager:latest .
```

---

## 🚦 Environnements

### Stratégie multi-environnements

| Environnement | Branche | URL | Auto-deploy | Backup |
|---------------|---------|-----|-------------|--------|
| **Development** | develop | dev.sales.local | Non | Non |
| **Staging** | staging | staging.sales.geniefactory.com | Oui | Quotidien |
| **Production** | main | sales.geniefactory.com | Oui (avec approval) | Quotidien |

### Configuration par environnement

```bash
# .env.development
ENVIRONMENT=development
LOG_LEVEL=DEBUG
STREAMLIT_SERVER_FILE_WATCHER_TYPE=auto

# .env.staging
ENVIRONMENT=staging
LOG_LEVEL=INFO
STREAMLIT_SERVER_FILE_WATCHER_TYPE=none

# .env.production
ENVIRONMENT=production
LOG_LEVEL=WARNING
STREAMLIT_SERVER_FILE_WATCHER_TYPE=none
```

### Promotion entre environnements

```bash
# Deploy staging
git push origin staging
# Auto-deploy vers staging.sales.geniefactory.com

# Tests OK → Merge vers main
git checkout main
git merge staging
git push origin main
# Auto-deploy vers sales.geniefactory.com (avec approval)
```

---

## 📋 Checklist déploiement production

### Avant premier déploiement

- [ ] Dockerfile testé localement (`docker build && docker run`)
- [ ] docker-compose.yml fonctionne en dev
- [ ] Tests passent (pytest)
- [ ] Variables d'environnement configurées dans Dockploy
- [ ] Secrets API ajoutés dans Dockploy (HubSpot, GetSales, Pappers)
- [ ] Volumes persistants configurés
- [ ] Domaine DNS pointé vers serveur Dockploy
- [ ] SSL Let's Encrypt activé
- [ ] Backup automatique configuré
- [ ] Monitoring/logs configurés
- [ ] Plan de rollback testé

### Post-déploiement

- [ ] Health check OK (`/_stcore/health`)
- [ ] Accès app fonctionnel (login, navigation)
- [ ] Sync HubSpot teste (quelques contacts)
- [ ] Import GetSales teste
- [ ] Recherche SIRENE teste
- [ ] Logs sans erreur critique
- [ ] Métriques remontées (si Prometheus)
- [ ] Backup manuel testé
- [ ] Restauration backup testée (important!)
- [ ] Documentation déploiement à jour

---

## 🔧 Troubleshooting

### Problèmes courants

#### 1. Container ne démarre pas

```bash
# Vérifier logs
dockploy logs sales-manager --tail 50

# Erreur commune: Secrets manquants
# → Vérifier variables d'environnement dans Dockploy

# Erreur commune: Port déjà utilisé
# → Changer port dans dockploy.json
```

#### 2. Health check échoue

```bash
# Tester manuellement
dockploy exec sales-manager -- curl localhost:8501/_stcore/health

# Si timeout → augmenter start_period dans healthcheck
# Si 404 → vérifier Streamlit démarre correctement
```

#### 3. Volumes vides après redéploiement

```bash
# Vérifier volumes persistants
dockploy volumes list

# Vérifier montage
dockploy exec sales-manager -- ls -la /app/data

# Si vide → restaurer backup
dockploy cp ./backup.tar.gz sales-manager:/tmp/
dockploy exec sales-manager -- tar xzf /tmp/backup.tar.gz -C /app/
```

#### 4. Lenteur performance

```bash
# Vérifier ressources
dockploy stats sales-manager

# Si mémoire saturée → augmenter limit dans dockploy.json
# Si CPU saturée → vérifier logs pour boucles infinies

# Optimiser SQLite
dockploy exec sales-manager -- sqlite3 /app/data/leads.db "VACUUM; ANALYZE;"
```

---

## 📚 Références

- [Dockploy Documentation](https://docs.dockploy.com/)
- [Docker Multi-stage Builds](https://docs.docker.com/build/building/multi-stage/)
- [Streamlit Docker Deployment](https://docs.streamlit.io/knowledge-base/tutorials/deploy/docker)
- [SQLite Docker Best Practices](https://www.sqlite.org/docker.html)
- [GitHub Actions Docker](https://docs.github.com/en/actions/publishing-packages/publishing-docker-images)

---

## ✅ Critères d'acceptance

### Fonctionnels
- [ ] Application accessible via HTTPS avec domaine custom
- [ ] Secrets chargés depuis Dockploy (pas dans code)
- [ ] Données persistantes après redéploiement
- [ ] Logs accessibles via Dockploy UI/CLI
- [ ] Backup automatique fonctionne
- [ ] Restauration backup testée et fonctionnelle

### Techniques
- [ ] Build Docker < 5 min
- [ ] Image Docker < 800 MB
- [ ] Démarrage container < 30 sec
- [ ] Health check passe après démarrage
- [ ] Pas de processus root dans container
- [ ] Volumes correctement montés

### DevOps
- [ ] CI/CD GitHub Actions fonctionnel
- [ ] Auto-deploy sur push main
- [ ] Tests passent avant build
- [ ] Rollback en < 2 min possible
- [ ] Monitoring configuré

---

## 🚀 Timeline estimée

| Phase | Durée | Tâches |
|-------|-------|--------|
| **Phase 1: Dockerisation** | 1 jour | Dockerfile, docker-compose, tests locaux |
| **Phase 2: Configuration Dockploy** | 0.5 jour | Compte, secrets, domaine SSL |
| **Phase 3: CI/CD** | 0.5 jour | GitHub Actions, auto-deploy |
| **Phase 4: Tests & Documentation** | 0.5 jour | Tests production, docs |
| **TOTAL** | ~2.5 jours | |

---

**Dernière mise à jour:** 2025-12-21
**Prochaine revue:** Après premier déploiement production
