# Spec - Module UI Navigation

## Vision

Créer une interface unifiée et intuitive pour naviguer entre les différents modules du portail Sales Ops.

## Contexte

### Situation actuelle
- Module 1 (Dashboard CFO) : `app.py` standalone
- Module 2 (Lead Scraper) : à intégrer
- Pas de navigation entre modules

### Objectif
Restructurer l'UI pour avoir :
- Une page d'accueil avec vue d'ensemble
- Navigation claire entre les modules
- Cohérence visuelle

---

## User Stories

### US-3.1 : Navigation principale
**En tant qu'** utilisateur
**Je veux** naviguer facilement entre les modules
**Afin de** accéder rapidement aux outils dont j'ai besoin

**Critères d'acceptation :**
- [ ] Sidebar avec menu des modules
- [ ] Icônes distinctives par module
- [ ] Indication du module actif
- [ ] Navigation fluide (pas de rechargement complet)

---

### US-3.2 : Page d'accueil
**En tant qu'** utilisateur
**Je veux** voir un dashboard d'accueil avec les infos clés
**Afin de** avoir une vue d'ensemble rapide

**Critères d'acceptation :**
- [ ] Statut de chaque module (dernière sync, nb leads, etc.)
- [ ] Raccourcis vers actions fréquentes
- [ ] Notifications/alertes si problème

---

### US-3.3 : Cohérence visuelle
**En tant qu'** utilisateur
**Je veux** une interface cohérente entre les modules
**Afin de** avoir une expérience utilisateur fluide

**Critères d'acceptation :**
- [ ] Header commun avec logo/titre
- [ ] Palette de couleurs cohérente
- [ ] Composants UI réutilisables
- [ ] Messages d'erreur/succès standardisés

---

## Architecture Streamlit

```
app.py                    # Point d'entrée + routing
pages/
  __init__.py
  home.py                 # Page d'accueil / dashboard
  pipeline_cfo.py         # Module 1 : Dashboard CFO
  lead_scraper.py         # Module 2 : Lead Scraper
components/
  __init__.py
  sidebar.py              # Navigation sidebar
  header.py               # Header commun
  notifications.py        # Système de notifications
```

### Option : Streamlit Multi-page Apps

Utiliser la fonctionnalité native de Streamlit :
```
pages/
  1_Dashboard_CFO.py
  2_Lead_Scraper.py
  3_Settings.py
```

Avantage : navigation automatique dans la sidebar.

---

## Maquettes

### Sidebar
```
┌─────────────────────┐
│  🏭 Sales Ops       │
│  Genie Factory      │
├─────────────────────┤
│  📊 Dashboard CFO   │  <- Module 1
│  🎯 Lead Scraper    │  <- Module 2
│  ⚙️  Paramètres     │
├─────────────────────┤
│  Dernière sync:     │
│  2024-01-15 14:30   │
└─────────────────────┘
```

### Page d'accueil
```
┌─────────────────────────────────────┐
│  Bienvenue sur Sales Ops            │
├─────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐           │
│  │ CFO     │  │ Leads   │           │
│  │ 45 deals│  │ 120     │           │
│  │ ✅ Sync │  │ 15 new  │           │
│  └─────────┘  └─────────┘           │
├─────────────────────────────────────┤
│  Actions rapides:                   │
│  [Sync maintenant] [Import leads]   │
└─────────────────────────────────────┘
```

---

## Dépendances

- Streamlit >= 1.28 (pour multi-page apps natif)
- Pas de dépendance externe supplémentaire

---

## Hors Scope (v1)

- Authentification utilisateur
- Personnalisation du thème
- Mode sombre
- Responsive mobile (desktop first)
