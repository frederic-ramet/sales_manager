# Guide d'Utilisation - spec-kit pour Portail Sales

## C'est quoi spec-kit ?

spec-kit est un framework de documentation créé par GitHub pour organiser les specs de projet de manière structurée. Il aide à :
- Garder les specs à jour pendant le dev
- Éviter de perdre le contexte du projet
- Faciliter l'onboarding de nouveaux devs
- Structurer la pensée avant de coder

## Structure de notre projet

```
.specify/
├── memory/
│   └── constitution.md          # Principes directeurs (ne change jamais)
└── specs/
    └── 001-dashboard-pipeline-cfo/
        ├── spec.md              # Quoi construire (User Stories)
        ├── plan.md              # Comment construire (Architecture)
        ├── tasks.md             # Découpage en tâches
        └── research.md          # Notes de recherche technique
```

## Utilisation pendant le dev

### 1. Avant de coder
```bash
# Lire la constitution
cat .specify/memory/constitution.md

# Lire la spec
cat .specify/specs/001-dashboard-pipeline-cfo/spec.md

# Lire le plan technique
cat .specify/specs/001-dashboard-pipeline-cfo/plan.md

# Voir les tâches
cat .specify/specs/001-dashboard-pipeline-cfo/tasks.md
```

### 2. Pendant le dev
- **Cocher les tâches** dans `tasks.md` au fur et à mesure
- **Mettre à jour `research.md`** si tu découvres des infos importantes sur les APIs
- **Mettre à jour `plan.md`** si l'architecture change

### 3. Si tu bloques
- Relire la `constitution.md` pour te rappeler les principes
- Vérifier que tu n'as pas dévié de la `spec.md`
- Regarder les notes de `research.md`

## Workflow recommandé

### Option 1 : Édition manuelle
```bash
# Éditer avec ton éditeur préféré
vim .specify/specs/001-dashboard-pipeline-cfo/tasks.md

# Committer régulièrement
git add .specify/
git commit -m "Update tasks: completed T1.2"
```

### Option 2 : Avec Claude (dans le chat)
```
"Peux-tu mettre à jour tasks.md pour marquer T1.2 comme complété ?"
```

Claude peut lire et modifier les fichiers .specify/ directement.

## Bonnes pratiques

### ✅ À FAIRE
- Lire constitution.md AVANT de commencer
- Cocher les tâches au fur et à mesure
- Ajouter des notes dans research.md quand tu trouves quelque chose d'important
- Mettre à jour plan.md si l'archi change
- Committer les .specify/ régulièrement

### ❌ À ÉVITER
- Modifier constitution.md (c'est la référence stable)
- Coder sans avoir lu spec.md
- Laisser tasks.md désynchronisé avec le code réel
- Ignorer les principes de la constitution

## Exemple de workflow quotidien

```bash
# 1. Matin - Check where you are
cat .specify/specs/001-dashboard-pipeline-cfo/tasks.md | grep "^\- \[ \]" | head -3

# 2. Dev de la journée
# ... coder ...

# 3. Soir - Update progress
vim .specify/specs/001-dashboard-pipeline-cfo/tasks.md
# Cocher T1.2 et T1.3

# 4. Commit
git add .specify/ core/asana_client.py
git commit -m "Implement Asana client (T1.2) and pipeline calculator (T1.3)"
```

## Commandes utiles

### Voir toutes les tâches restantes
```bash
grep "^\- \[ \]" .specify/specs/001-dashboard-pipeline-cfo/tasks.md
```

### Voir les tâches complétées
```bash
grep "^\- \[x\]" .specify/specs/001-dashboard-pipeline-cfo/tasks.md
```

### Compter les tâches
```bash
echo "Total: $(grep -c "^\- \[" .specify/specs/001-dashboard-pipeline-cfo/tasks.md)"
echo "Done: $(grep -c "^\- \[x\]" .specify/specs/001-dashboard-pipeline-cfo/tasks.md)"
echo "Todo: $(grep -c "^\- \[ \]" .specify/specs/001-dashboard-pipeline-cfo/tasks.md)"
```

## Tips pour travailler avec Claude

Tu peux demander à Claude :

```
"Lis la spec et dis-moi ce que je dois coder maintenant"

"Vérifie si mon code respecte la constitution"

"Mets à jour tasks.md : T1.2 est fait, T1.3 en cours"

"Ajoute une note dans research.md : l'API Asana a un rate limit de 1500/min"

"Crée une nouvelle spec pour le module 2"
```

## Organisation multi-modules

Quand tu auras plusieurs modules :

```
.specify/
├── memory/
│   └── constitution.md
└── specs/
    ├── 001-dashboard-pipeline-cfo/
    │   ├── spec.md
    │   ├── plan.md
    │   ├── tasks.md
    │   └── research.md
    ├── 002-module-prospection/
    │   ├── spec.md
    │   ├── plan.md
    │   ├── tasks.md
    │   └── research.md
    └── 003-module-hubspot-sync/
        ├── spec.md
        ├── plan.md
        ├── tasks.md
        └── research.md
```

Chaque module est indépendant mais partage la même `constitution.md`.

## Ressources

- [spec-kit sur GitHub](https://github.com/github/spec-kit)
- [Documentation spec-kit](https://github.com/github/spec-kit#readme)

## Questions fréquentes

**Q: Dois-je vraiment lire constitution.md à chaque fois ?**
R: Au début oui, après ça devient naturel. C'est comme les tests : ça prend 2min mais ça t'évite des heures de refactoring.

**Q: Que faire si je veux changer l'architecture ?**
R: 1) Vérifier que ça respecte la constitution 2) Mettre à jour plan.md 3) Adapter tasks.md si besoin

**Q: spec-kit impose-t-il une façon de coder ?**
R: Non, c'est juste de la doc structurée. Tu codes comme tu veux tant que tu respectes la spec.

**Q: Puis-je utiliser spec-kit avec d'autres outils (Notion, Linear, etc.) ?**
R: Oui ! Les fichiers .specify/ sont complémentaires. Tu peux avoir tes issues GitHub EN PLUS de spec-kit.
