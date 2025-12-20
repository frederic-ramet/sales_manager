# 🎯 Portail Sales Ops - Genie Factory

## Spec-Driven Development avec spec-kit

Ce projet utilise [spec-kit](https://github.com/github/spec-kit) pour organiser le développement.

## Structure

```
.specify/
├── memory/
│   └── constitution.md      # Principes directeurs du projet
└── specs/
    └── 001-portail-sales-ops/
        ├── spec.md          # Spécifications fonctionnelles (User Stories)
        ├── plan.md          # Plan d'implémentation technique
        ├── tasks.md         # Découpage en tâches
        └── research.md      # Recherche technique (APIs, etc.)
```

## Workflow

### 1. Lire la constitution
Avant tout développement, lire `.specify/memory/constitution.md` pour comprendre les principes du projet.

### 2. Consulter la spec
Le fichier `spec.md` contient les User Stories et critères d'acceptation.

### 3. Suivre le plan
Le fichier `plan.md` décrit l'architecture et les composants à développer.

### 4. Exécuter les tâches
Le fichier `tasks.md` liste les tâches dans l'ordre, avec leurs dépendances.

## Commandes spec-kit (si installé)

```bash
# Voir la spec
/speckit.specify

# Voir le plan
/speckit.plan

# Voir les tâches
/speckit.tasks

# Implémenter
/speckit.implement
```

## Quick Start Dev

1. **Phase 0** : Restructurer le repo existant
2. **Phase 1** : Développer le module Pilotage (Asana)
3. **Phase 2** : Ajouter le connecteur Lead → Asana
4. **Phase 3** : Compléter l'Admin
5. **Phase 4** : Polish UX

Temps estimé : ~22h
