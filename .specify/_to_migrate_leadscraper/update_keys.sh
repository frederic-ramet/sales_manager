#!/bin/bash

# ============================================================================
# Script de mise à jour des clés API - Lead Gen SIRENE
# ============================================================================

# Couleurs
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "${CYAN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}  Mise à jour des clés API - Lead Gen SIRENE  ${CYAN}║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════╝${NC}"
echo ""

ENV_FILE=".env"

# Vérifier que .env existe
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}⚠ Fichier .env non trouvé${NC}"
    if [ -f ".env.example" ]; then
        echo "→ Création du fichier .env depuis .env.example..."
        cp .env.example "$ENV_FILE"
        echo -e "${GREEN}✓${NC} Fichier .env créé"
    else
        echo "✗ .env.example non trouvé"
        exit 1
    fi
fi

# Charger les valeurs actuelles
source "$ENV_FILE" 2>/dev/null || true

echo "Quelles clés souhaitez-vous mettre à jour ?"
echo ""
echo "  1) Clé API Pappers"
echo "  2) Clé API Anthropic (recherche naturelle)"
echo "  3) Chemin credentials Google Cloud"
echo "  4) ID Google Sheet par défaut"
echo "  5) Tout afficher"
echo "  6) Quitter"
echo ""

read -p "Votre choix [1-6]: " choice

case $choice in
    1)
        echo ""
        echo -e "${CYAN}Clé API Pappers actuelle:${NC} ${PAPPERS_API_KEY:-<non configurée>}"
        echo ""
        read -p "Nouvelle clé API Pappers (Entrée pour conserver): " new_key

        if [ -n "$new_key" ]; then
            if grep -q "PAPPERS_API_KEY=" "$ENV_FILE"; then
                sed -i.bak "s|PAPPERS_API_KEY=.*|PAPPERS_API_KEY=$new_key|" "$ENV_FILE"
            else
                echo "PAPPERS_API_KEY=$new_key" >> "$ENV_FILE"
            fi
            echo -e "${GREEN}✓${NC} Clé API Pappers mise à jour"
        else
            echo "→ Clé conservée"
        fi
        ;;

    2)
        echo ""
        echo -e "${CYAN}Clé API Anthropic actuelle:${NC} ${ANTHROPIC_API_KEY:-<non configurée>}"
        echo ""
        echo "La clé Anthropic permet la recherche en langage naturel."
        echo "Obtenez une clé sur: https://console.anthropic.com"
        echo ""
        read -p "Nouvelle clé API Anthropic (Entrée pour conserver): " new_key

        if [ -n "$new_key" ]; then
            if grep -q "ANTHROPIC_API_KEY=" "$ENV_FILE"; then
                sed -i.bak "s|ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$new_key|" "$ENV_FILE"
            else
                echo "ANTHROPIC_API_KEY=$new_key" >> "$ENV_FILE"
            fi
            echo -e "${GREEN}✓${NC} Clé API Anthropic mise à jour"
        else
            echo "→ Clé conservée"
        fi
        ;;

    3)
        echo ""
        echo -e "${CYAN}Chemin actuel:${NC} ${GOOGLE_SHEETS_CREDENTIALS_PATH:-<non configuré>}"
        echo ""
        read -p "Nouveau chemin credentials (Entrée pour conserver): " new_path

        if [ -n "$new_path" ]; then
            if grep -q "GOOGLE_SHEETS_CREDENTIALS_PATH=" "$ENV_FILE"; then
                sed -i.bak "s|GOOGLE_SHEETS_CREDENTIALS_PATH=.*|GOOGLE_SHEETS_CREDENTIALS_PATH=$new_path|" "$ENV_FILE"
            else
                echo "GOOGLE_SHEETS_CREDENTIALS_PATH=$new_path" >> "$ENV_FILE"
            fi

            if [ -f "$new_path" ]; then
                echo -e "${GREEN}✓${NC} Chemin mis à jour (fichier trouvé)"
            else
                echo -e "${YELLOW}⚠${NC} Chemin mis à jour (fichier non trouvé)"
            fi
        else
            echo "→ Chemin conservé"
        fi
        ;;

    4)
        echo ""
        echo -e "${CYAN}ID actuel:${NC} ${DEFAULT_SHEET_ID:-<non configuré>}"
        echo ""
        echo "L'ID se trouve dans l'URL: https://docs.google.com/spreadsheets/d/[ID_ICI]/edit"
        echo ""
        read -p "Nouvel ID Google Sheet (Entrée pour conserver): " new_id

        if [ -n "$new_id" ]; then
            if grep -q "DEFAULT_SHEET_ID=" "$ENV_FILE"; then
                sed -i.bak "s|DEFAULT_SHEET_ID=.*|DEFAULT_SHEET_ID=$new_id|" "$ENV_FILE"
            else
                echo "DEFAULT_SHEET_ID=$new_id" >> "$ENV_FILE"
            fi
            echo -e "${GREEN}✓${NC} ID Google Sheet mis à jour"
        else
            echo "→ ID conservé"
        fi
        ;;

    5)
        echo ""
        echo -e "${CYAN}═══ Configuration actuelle (.env) ═══${NC}"
        echo ""
        source "$ENV_FILE" 2>/dev/null || true
        echo "PAPPERS_API_KEY=${PAPPERS_API_KEY:-<non configurée>}"
        echo "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-<non configurée>}"
        echo "ANTHROPIC_MODEL=${ANTHROPIC_MODEL:-claude-3-5-haiku-20241022}"
        echo "GOOGLE_SHEETS_CREDENTIALS_PATH=${GOOGLE_SHEETS_CREDENTIALS_PATH:-<non configuré>}"
        echo "DEFAULT_SHEET_ID=${DEFAULT_SHEET_ID:-<non configuré>}"
        echo ""

        # Vérifications
        if [ -n "$PAPPERS_API_KEY" ] && [ "$PAPPERS_API_KEY" != "your_api_key_here" ]; then
            echo -e "${GREEN}✓${NC} Clé API Pappers configurée"
        else
            echo -e "${YELLOW}⚠${NC} Clé API Pappers non configurée"
        fi

        if [ -n "$ANTHROPIC_API_KEY" ] && [ "$ANTHROPIC_API_KEY" != "your_anthropic_api_key_here" ]; then
            echo -e "${GREEN}✓${NC} Clé API Anthropic configurée"
        else
            echo -e "${YELLOW}⚠${NC} Clé API Anthropic non configurée (recherche naturelle désactivée)"
        fi

        if [ -n "$GOOGLE_SHEETS_CREDENTIALS_PATH" ] && [ -f "$GOOGLE_SHEETS_CREDENTIALS_PATH" ]; then
            echo -e "${GREEN}✓${NC} Credentials Google Cloud trouvées"
        else
            echo -e "${YELLOW}⚠${NC} Credentials Google Cloud non trouvées"
        fi

        if [ -n "$DEFAULT_SHEET_ID" ] && [ "$DEFAULT_SHEET_ID" != "your_sheet_id_here" ]; then
            echo -e "${GREEN}✓${NC} ID Google Sheet configuré"
        else
            echo -e "${YELLOW}⚠${NC} ID Google Sheet non configuré"
        fi
        ;;

    6)
        echo "→ Annulé"
        exit 0
        ;;

    *)
        echo "✗ Choix invalide"
        exit 1
        ;;
esac

# Nettoyer les backups
rm -f "$ENV_FILE.bak"

echo ""
echo -e "${GREEN}✓${NC} Terminé !"
echo ""
