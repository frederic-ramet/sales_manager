# 🛠️ Scripts utilitaires

Ce document décrit les scripts fournis pour faciliter la configuration et l'utilisation de Lead Gen SIRENE.

## 📋 Liste des scripts

### `run.sh` - Lancement rapide de l'application

Script simple pour lancer l'application avec vérifications préalables.

**Usage :**
```bash
./run.sh
```

**Fonctionnalités :**
- ✅ Vérification du venv (propose setup.sh si absent)
- ✅ Vérification du fichier .env (crée depuis .env.example si absent)
- ✅ Vérification des dépendances (propose installation si manquantes)
- ✅ Affichage de l'état de la configuration
  - Clé API Pappers ✓/⚠
  - Credentials Google Cloud ✓/⚠
  - Référentiels ✓/✗
- ✅ Proposition de configurer les clés si nécessaire
- ✅ Lancement automatique de Streamlit
- ✅ Messages d'aide et conseils

**Workflow typique :**
```bash
$ ./run.sh

╔════════════════════════════════════════════════╗
║       🎯 Lead Gen SIRENE - Lancement          ║
╚════════════════════════════════════════════════╝

→ Vérification des dépendances...

═══ État de la configuration ═══

✓ Clé API Pappers configurée
⚠ Credentials Google Cloud non trouvées
  L'export Google Sheets sera indisponible
✓ Référentiels chargés

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 Lancement de l'application...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📍 L'application sera accessible sur:
   http://localhost:8501

💡 Conseils:
   • Utilisez Ctrl+C pour arrêter l'application
   • Ouvrez http://localhost:8501 dans votre navigateur
   • Consultez la section 'Configuration' dans la sidebar
```

**Actions automatiques :**
- Si venv manquant → propose ./setup.sh
- Si .env manquant → crée depuis .env.example
- Si dépendances manquantes → propose installation
- Si clés API non configurées → propose ./update_keys.sh

---

### `setup.sh` - Configuration complète

Script interactif pour configurer l'environnement de A à Z.

**Usage :**
```bash
./setup.sh
```

**Fonctionnalités :**
- ✅ Vérification des prérequis (Python, pip, git)
- ✅ Création de l'environnement virtuel
- ✅ Installation des dépendances Python
- ✅ Configuration interactive du fichier `.env`
- ✅ Validation de la configuration
- ✅ Tests rapides de l'application
- ✅ Lancement optionnel de Streamlit

**Étapes détaillées :**

1. **Vérification des prérequis**
   - Détecte Python 3, pip, git
   - Affiche les versions installées

2. **Environnement virtuel**
   - Crée `venv/` si absent
   - Propose de recréer si existant
   - Installe/met à jour les dépendances

3. **Configuration .env**
   - Crée `.env` depuis `.env.example` si nécessaire
   - Demande interactivement :
     - Clé API Pappers
     - Chemin credentials Google Cloud
     - ID Google Sheet par défaut
   - Affiche des instructions pour obtenir les clés

4. **Validation**
   - Vérifie que les fichiers de config existent
   - Valide le JSON des credentials Google
   - Compte les référentiels (codes APE, départements)
   - Affiche un résumé avec erreurs/warnings

5. **Tests rapides**
   - Teste l'import de tous les modules
   - Vérifie que l'application compile
   - Affiche le résultat ✓/✗

6. **Lancement**
   - Propose de lancer Streamlit
   - Affiche l'URL d'accès

---

### `update_keys.sh` - Mise à jour rapide des clés

Script simple pour modifier les clés API sans relancer la configuration complète.

**Usage :**
```bash
./update_keys.sh
```

**Menu interactif :**
```
1) Clé API Pappers
2) Chemin credentials Google Cloud
3) ID Google Sheet par défaut
4) Tout afficher
5) Quitter
```

**Exemples d'utilisation :**

**Mettre à jour la clé Pappers :**
```bash
./update_keys.sh
# Choisir option 1
# Entrer la nouvelle clé
```

**Afficher la config actuelle :**
```bash
./update_keys.sh
# Choisir option 4
```

**Fonctionnalités :**
- ✅ Mise à jour sélective des variables
- ✅ Affichage de la valeur actuelle
- ✅ Validation (fichier existe, JSON valide)
- ✅ Sauvegarde automatique du `.env`

---

## 🎨 Codes couleur

Les scripts utilisent des codes couleur pour faciliter la lecture :

- 🟢 **Vert (✓)** : Succès, validation OK
- 🔴 **Rouge (✗)** : Erreur critique
- 🟡 **Jaune (⚠)** : Avertissement, non critique
- 🔵 **Cyan (→)** : Information, action en cours

---

## 🔧 Personnalisation

### Modifier les scripts

Les scripts sont commentés et structurés en sections :

```bash
# ============================================================================
# Section
# ============================================================================

fonction() {
    # Description
}
```

**Variables principales :**

**setup.sh :**
- `RED`, `GREEN`, `YELLOW`, `BLUE`, `CYAN` : Couleurs
- `CHECK`, `CROSS`, `ARROW`, `STAR` : Symboles

**update_keys.sh :**
- `ENV_FILE` : Chemin vers `.env`

### Ajouter une nouvelle variable d'environnement

1. Ajouter dans `.env.example` :
   ```bash
   MA_NOUVELLE_VAR=valeur_par_defaut
   ```

2. Modifier `setup.sh` dans la fonction `setup_env_file()` :
   ```bash
   # MA_NOUVELLE_VAR
   if [ -z "$MA_NOUVELLE_VAR" ]; then
       if ask_yes_no "Configurer MA_NOUVELLE_VAR ?" "y"; then
           local nouvelle_var=$(ask_input "Entrez la valeur" "")

           if [ -n "$nouvelle_var" ]; then
               echo "MA_NOUVELLE_VAR=$nouvelle_var" >> "$env_file"
               print_success "MA_NOUVELLE_VAR configurée"
           fi
       fi
   fi
   ```

3. Ajouter dans `update_keys.sh` menu :
   ```bash
   echo "  4) Ma nouvelle variable"
   # ...
   case $choice in
       4)
           # Code de mise à jour
           ;;
   esac
   ```

---

## 🐛 Dépannage

### Le script ne s'exécute pas

```bash
# Vérifier qu'il est exécutable
chmod +x setup.sh
chmod +x update_keys.sh

# Vérifier la syntaxe
bash -n setup.sh
```

### Erreur "command not found"

Le script doit être lancé avec `./` depuis le dossier du projet :

```bash
# ✗ Incorrect
setup.sh

# ✓ Correct
./setup.sh
```

### Le script ne trouve pas Python

Le script cherche `python3`. Vérifiez votre installation :

```bash
python3 --version
which python3
```

Si vous utilisez `python` au lieu de `python3`, créez un alias ou modifiez le script.

### Les couleurs ne s'affichent pas

Certains terminaux ne supportent pas les codes ANSI. Vous pouvez :

1. Utiliser un terminal compatible (bash, zsh)
2. Désactiver les couleurs dans le script :
   ```bash
   # Commenter les définitions de couleurs
   # RED='\033[0;31m'
   # ...
   RED=''
   GREEN=''
   # etc.
   ```

### Le .env n'est pas mis à jour

Vérifiez les permissions :

```bash
ls -la .env
chmod 644 .env
```

### Erreur lors de l'installation des dépendances

```bash
# Mettre à jour pip
venv/bin/pip install --upgrade pip

# Réinstaller les dépendances
venv/bin/pip install -r requirements.txt --force-reinstall
```

---

## 📚 Ressources

**Documentation Bash :**
- [Advanced Bash-Scripting Guide](https://tldp.org/LDP/abs/html/)
- [ShellCheck](https://www.shellcheck.net/) - Validateur de scripts bash

**Variables d'environnement :**
- [python-dotenv](https://pypi.org/project/python-dotenv/)

**Scripts similaires :**
- [Oh My Zsh installer](https://github.com/ohmyzsh/ohmyzsh/blob/master/tools/install.sh)
- [Node Version Manager](https://github.com/nvm-sh/nvm/blob/master/install.sh)

---

## 💡 Bonnes pratiques

1. **Toujours tester** les scripts après modification :
   ```bash
   bash -n script.sh  # Vérifier syntaxe
   ```

2. **Sauvegarder** `.env` avant modifications :
   ```bash
   cp .env .env.backup
   ```

3. **Documenter** les changements dans les commentaires

4. **Utiliser** des fonctions pour la réutilisabilité

5. **Gérer** les erreurs avec `set -e` et des try/catch appropriés

---

**Dernière mise à jour :** 2025-11-22
