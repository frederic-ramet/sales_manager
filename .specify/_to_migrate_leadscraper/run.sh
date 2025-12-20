#!/bin/bash

# ============================================================================
# Script de lancement - Lead Gen SIRENE
# ============================================================================

# Couleurs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}       🎯 Lead Gen SIRENE - Lancement          ${CYAN}║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════╝${NC}"
echo ""

# Vérifier qu'on est dans le bon dossier
if [ ! -f "app.py" ]; then
    echo -e "${RED}✗ Erreur:${NC} Fichier app.py non trouvé"
    echo "  Ce script doit être exécuté depuis le dossier racine du projet"
    exit 1
fi

# Vérifier que le venv existe
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠ Environnement virtuel non trouvé${NC}"
    echo ""
    echo "Voulez-vous lancer le script de configuration ?"
    echo "  ./setup.sh"
    echo ""
    read -p "$(echo -e ${CYAN}Lancer setup.sh maintenant ? [Y/n]: ${NC})" response
    response=${response:-y}

    if [[ "$response" =~ ^[Yy]$ ]]; then
        ./setup.sh
        exit 0
    else
        echo ""
        echo -e "${RED}✗ Annulé${NC}"
        echo "  Exécutez d'abord: ./setup.sh"
        exit 1
    fi
fi

# Vérifier que .env existe
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠ Fichier .env non trouvé${NC}"
    echo ""
    echo "Configuration rapide:"

    # Créer .env depuis .env.example
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}✓${NC} Fichier .env créé depuis .env.example"
    else
        echo -e "${RED}✗ Fichier .env.example manquant${NC}"
        exit 1
    fi

    echo ""
    echo "Pour configurer vos clés API:"
    echo "  ./update_keys.sh"
    echo ""
    read -p "$(echo -e ${CYAN}Continuer le lancement ? [Y/n]: ${NC})" response
    response=${response:-y}

    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}→ Annulé${NC}"
        exit 0
    fi
fi

# Vérifier les dépendances
echo -e "${CYAN}→${NC} Vérification des dépendances..."

if [ ! -f "venv/bin/streamlit" ]; then
    echo -e "${YELLOW}⚠ Streamlit non installé dans le venv${NC}"
    echo ""
    read -p "$(echo -e ${CYAN}Installer les dépendances ? [Y/n]: ${NC})" response
    response=${response:-y}

    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo -e "${CYAN}→${NC} Installation des dépendances..."
        source venv/bin/activate
        pip install -q -r requirements.txt
        echo -e "${GREEN}✓${NC} Dépendances installées"
    else
        echo -e "${RED}✗ Annulé${NC}"
        exit 1
    fi
fi

# Afficher l'état de la configuration
echo ""
echo -e "${CYAN}═══ État de la configuration ═══${NC}"
echo ""

source .env 2>/dev/null || true

# Clé Pappers
if [ -n "$PAPPERS_API_KEY" ] && [ "$PAPPERS_API_KEY" != "your_api_key_here" ]; then
    echo -e "${GREEN}✓${NC} Clé API Pappers configurée"
else
    echo -e "${YELLOW}⚠${NC} Clé API Pappers non configurée"
    echo "  L'enrichissement des données sera limité"
fi

# Credentials Google
if [ -n "$GOOGLE_SHEETS_CREDENTIALS_PATH" ] && [ -f "$GOOGLE_SHEETS_CREDENTIALS_PATH" ]; then
    echo -e "${GREEN}✓${NC} Credentials Google Cloud trouvées"
else
    echo -e "${YELLOW}⚠${NC} Credentials Google Cloud non trouvées"
    echo "  L'export Google Sheets sera indisponible"
fi

# Référentiels
if [ -f "data/codes_ape.json" ] && [ -f "data/departements.json" ]; then
    echo -e "${GREEN}✓${NC} Référentiels chargés"
else
    echo -e "${RED}✗${NC} Référentiels manquants"
fi

echo ""

# Proposer de configurer si nécessaire
if [ -z "$PAPPERS_API_KEY" ] || [ "$PAPPERS_API_KEY" = "your_api_key_here" ]; then
    read -p "$(echo -e ${CYAN}Configurer les clés API maintenant ? [y/N]: ${NC})" response

    if [[ "$response" =~ ^[Yy]$ ]]; then
        ./update_keys.sh
        echo ""
    fi
fi

# Lancement de Streamlit
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🚀 Lancement de l'application...${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "📍 L'application sera accessible sur:"
echo -e "   ${CYAN}http://localhost:8501${NC}"
echo ""
echo -e "💡 Conseils:"
echo "   • Utilisez Ctrl+C pour arrêter l'application"
echo "   • Ouvrez http://localhost:8501 dans votre navigateur"
echo "   • Consultez la section 'Configuration' dans la sidebar"
echo ""
echo -e "${YELLOW}⏳ Démarrage en cours...${NC}"
echo ""

# Activer le venv et lancer Streamlit
source venv/bin/activate
streamlit run app.py

# Message après arrêt
echo ""
echo -e "${CYAN}👋 Application arrêtée${NC}"
echo ""
