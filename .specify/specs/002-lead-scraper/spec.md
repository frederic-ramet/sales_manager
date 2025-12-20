# Spec - Module Lead Scraper

## Vision

Module de récupération et d'enrichissement des leads pour alimenter le pipeline commercial.

## Contexte

### Situation actuelle
- Une ancienne application existe (à migrer depuis `.specify/_to_migrate/`)
- Besoin de récupérer des leads depuis différentes sources
- Besoin d'enrichir les leads avec des données entreprise (SIRENE, Pappers, etc.)

### Objectif
Migrer et moderniser l'application existante en un module intégré au portail Sales Ops.

---

## User Stories

### US-2.1 : Récupération des leads
**En tant que** Sales Manager
**Je veux** récupérer des leads depuis différentes sources
**Afin de** alimenter mon pipeline commercial

**Critères d'acceptation :**
- [ ] Import depuis fichier CSV
- [ ] Scraping de sources web (à définir selon l'ancienne app)
- [ ] Déduplication des leads
- [ ] Stockage local (SQLite ou JSON)
- [ ] Interface de visualisation des leads récupérés

---

### US-2.2 : Enrichissement des leads
**En tant que** Sales Manager
**Je veux** enrichir automatiquement les leads avec des données entreprise
**Afin de** mieux qualifier mes prospects

**Critères d'acceptation :**
- [ ] Enrichissement via API SIRENE (données légales)
- [ ] Enrichissement via Pappers (données financières)
- [ ] Scoring automatique basé sur critères configurables
- [ ] Indicateur de qualité du lead
- [ ] Export enrichi (CSV, JSON)

---

### US-2.3 : Push vers Asana
**En tant que** Sales Manager
**Je veux** envoyer les leads qualifiés vers Asana
**Afin de** les intégrer directement dans mon pipeline

**Critères d'acceptation :**
- [ ] Création de task Asana depuis un lead
- [ ] Mapping des champs lead → custom fields Asana
- [ ] Éviter les doublons (vérification SIREN/nom)
- [ ] Feedback de confirmation dans l'UI

---

## Architecture

```
modules/
  lead_scraper/
    __init__.py
    scraper.py        # Récupération des leads
    enricher.py       # Enrichissement (SIRENE, Pappers)
    storage.py        # Stockage local
    asana_push.py     # Push vers Asana
```

---

## Dépendances Externes

| Service | Usage | Clé requise | Coût |
|---------|-------|-------------|------|
| SIRENE API | Données légales entreprise | Non (gratuit) | Gratuit |
| Pappers API | Données financières | Oui | Freemium |
| Asana | Destination leads | Oui (PAT) | Gratuit |

---

## Notes de Migration

> **TODO** : Analyser le code dans `.specify/_to_migrate/` pour :
> - Identifier les sources de scraping utilisées
> - Comprendre la logique d'enrichissement
> - Récupérer les patterns utiles
> - Adapter à l'architecture actuelle

---

## Hors Scope (v1)

- Scraping en temps réel (webhooks)
- Multi-utilisateurs avec quotas
- Intégration CRM autres que Asana
