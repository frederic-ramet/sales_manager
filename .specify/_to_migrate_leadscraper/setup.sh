#!/bin/bash

# ============================================================================
# Script de configuration pour Lead Gen SIRENE
# ============================================================================

set -e  # Arrêt en cas d'erreur

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Symboles
CHECK="${GREEN}✓${NC}"
CROSS="${RED}✗${NC}"
ARROW="${CYAN}→${NC}"
STAR="${YELLOW}★${NC}"

# ============================================================================
# Fonctions utilitaires
# ============================================================================

print_header() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}  ${BOLD}Lead Gen SIRENE - Configuration & Setup${NC}                      ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_section() {
    echo ""
    echo -e "${BOLD}${CYAN}═══ $1 ═══${NC}"
    echo ""
}

print_success() {
    echo -e "${CHECK} $1"
}

print_error() {
    echo -e "${CROSS} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC}  $1"
}

print_info() {
    echo -e "${ARROW} $1"
}

ask_yes_no() {
    local prompt="$1"
    local default="${2:-n}"

    if [ "$default" = "y" ]; then
        prompt="$prompt [Y/n]: "
    else
        prompt="$prompt [y/N]: "
    fi

    read -p "$(echo -e ${CYAN}${prompt}${NC})" response
    response=${response:-$default}

    if [[ "$response" =~ ^[Yy]$ ]]; then
        return 0
    else
        return 1
    fi
}

ask_input() {
    local prompt="$1"
    local default="$2"

    if [ -n "$default" ]; then
        read -p "$(echo -e ${CYAN}${prompt} [${default}]: ${NC})" response
        echo "${response:-$default}"
    else
        read -p "$(echo -e ${CYAN}${prompt}: ${NC})" response
        echo "$response"
    fi
}

ask_secret() {
    local prompt="$1"
    read -s -p "$(echo -e ${CYAN}${prompt}: ${NC})" response
    echo ""
    echo "$response"
}

# ============================================================================
# Vérifications initiales
# ============================================================================

check_requirements() {
    print_section "Vérification des prérequis"

    local all_ok=true

    # Python 3
    if command -v python3 &> /dev/null; then
        local python_version=$(python3 --version | cut -d' ' -f2)
        print_success "Python 3 installé (version $python_version)"
    else
        print_error "Python 3 non trouvé"
        all_ok=false
    fi

    # pip
    if command -v pip3 &> /dev/null || python3 -m pip --version &> /dev/null; then
        print_success "pip installé"
    else
        print_error "pip non trouvé"
        all_ok=false
    fi

    # git
    if command -v git &> /dev/null; then
        print_success "git installé"
    else
        print_warning "git non trouvé (non critique)"
    fi

    if [ "$all_ok" = false ]; then
        echo ""
        print_error "Certains prérequis sont manquants. Installez-les avant de continuer."
        exit 1
    fi
}

# ============================================================================
# Environnement virtuel
# ============================================================================

setup_virtualenv() {
    print_section "Configuration de l'environnement virtuel"

    if [ -d "venv" ]; then
        print_info "Environnement virtuel détecté"

        if ask_yes_no "Recréer l'environnement virtuel ?" "n"; then
            print_info "Suppression de l'ancien venv..."
            rm -rf venv
            print_info "Création du nouvel environnement virtuel..."
            python3 -m venv venv
            print_success "Environnement virtuel créé"
        else
            print_success "Environnement virtuel existant conservé"
        fi
    else
        print_info "Création de l'environnement virtuel..."
        python3 -m venv venv
        print_success "Environnement virtuel créé"
    fi

    # Installation des dépendances
    if ask_yes_no "Installer/mettre à jour les dépendances ?" "y"; then
        print_info "Installation des dépendances..."

        # Activer le venv et installer
        source venv/bin/activate
        pip install --upgrade pip -q
        pip install -r requirements.txt -q

        print_success "Dépendances installées"

        # Afficher les versions
        echo ""
        print_info "Versions installées:"
        echo "  - streamlit: $(pip show streamlit | grep Version | cut -d' ' -f2)"
        echo "  - httpx: $(pip show httpx | grep Version | cut -d' ' -f2)"
        echo "  - gspread: $(pip show gspread | grep Version | cut -d' ' -f2)"
        echo "  - pandas: $(pip show pandas | grep Version | cut -d' ' -f2)"
    fi
}

# ============================================================================
# Configuration .env
# ============================================================================

setup_env_file() {
    print_section "Configuration du fichier .env"

    local env_file=".env"
    local env_example=".env.example"

    # Créer .env depuis .env.example si nécessaire
    if [ ! -f "$env_file" ]; then
        if [ -f "$env_example" ]; then
            print_info "Création du fichier .env depuis .env.example..."
            cp "$env_example" "$env_file"
            print_success "Fichier .env créé"
        else
            print_error ".env.example non trouvé"
            return 1
        fi
    else
        print_info "Fichier .env existant détecté"
    fi

    # Lire les valeurs actuelles
    source "$env_file" 2>/dev/null || true

    echo ""
    print_info "Configuration des variables d'environnement"
    echo ""

    # PAPPERS_API_KEY
    if [ -z "$PAPPERS_API_KEY" ] || [ "$PAPPERS_API_KEY" = "your_api_key_here" ]; then
        print_warning "Clé API Pappers non configurée"
        echo ""
        echo -e "${CYAN}Pour obtenir une clé API Pappers gratuite:${NC}"
        echo "  1. Aller sur https://www.pappers.fr/api"
        echo "  2. Créer un compte gratuit (100 requêtes/mois)"
        echo "  3. Copier votre clé API"
        echo ""

        if ask_yes_no "Configurer la clé API Pappers maintenant ?" "y"; then
            local pappers_key=$(ask_input "Entrez votre clé API Pappers" "")

            if [ -n "$pappers_key" ]; then
                # Mise à jour du .env
                if grep -q "PAPPERS_API_KEY=" "$env_file"; then
                    sed -i.bak "s|PAPPERS_API_KEY=.*|PAPPERS_API_KEY=$pappers_key|" "$env_file"
                else
                    echo "PAPPERS_API_KEY=$pappers_key" >> "$env_file"
                fi
                print_success "Clé API Pappers configurée"
            else
                print_warning "Clé API Pappers non configurée (vous pourrez la configurer plus tard)"
            fi
        fi
    else
        print_success "Clé API Pappers configurée (${PAPPERS_API_KEY:0:10}...)"
    fi

    echo ""

    # GOOGLE_SHEETS_CREDENTIALS_PATH
    local current_creds_path="${GOOGLE_SHEETS_CREDENTIALS_PATH:-credentials/gcp_service_account.json}"

    print_info "Chemin credentials Google Cloud: $current_creds_path"

    if [ ! -f "$current_creds_path" ]; then
        print_warning "Fichier credentials Google Cloud non trouvé"
        echo ""
        echo -e "${CYAN}Pour configurer Google Sheets:${NC}"
        echo "  1. Créer un projet sur https://console.cloud.google.com"
        echo "  2. Activer Google Sheets API + Drive API"
        echo "  3. Créer un compte de service"
        echo "  4. Télécharger le JSON des credentials"
        echo "  5. Placer le fichier dans credentials/"
        echo ""

        if ask_yes_no "Configurer le chemin des credentials maintenant ?" "n"; then
            local creds_path=$(ask_input "Chemin vers le fichier JSON" "$current_creds_path")

            if [ -n "$creds_path" ]; then
                if grep -q "GOOGLE_SHEETS_CREDENTIALS_PATH=" "$env_file"; then
                    sed -i.bak "s|GOOGLE_SHEETS_CREDENTIALS_PATH=.*|GOOGLE_SHEETS_CREDENTIALS_PATH=$creds_path|" "$env_file"
                else
                    echo "GOOGLE_SHEETS_CREDENTIALS_PATH=$creds_path" >> "$env_file"
                fi

                if [ -f "$creds_path" ]; then
                    print_success "Credentials Google Cloud configurées"
                else
                    print_warning "Fichier non trouvé. Assurez-vous de le placer au bon endroit."
                fi
            fi
        fi
    else
        print_success "Credentials Google Cloud trouvées"
    fi

    echo ""

    # DEFAULT_SHEET_ID
    if [ -z "$DEFAULT_SHEET_ID" ] || [ "$DEFAULT_SHEET_ID" = "your_sheet_id_here" ]; then
        if ask_yes_no "Configurer un ID de Google Sheet par défaut ?" "n"; then
            echo ""
            echo -e "${CYAN}L'ID se trouve dans l'URL du Sheet:${NC}"
            echo "  https://docs.google.com/spreadsheets/d/[ID_ICI]/edit"
            echo ""

            local sheet_id=$(ask_input "Entrez l'ID du Google Sheet" "")

            if [ -n "$sheet_id" ]; then
                if grep -q "DEFAULT_SHEET_ID=" "$env_file"; then
                    sed -i.bak "s|DEFAULT_SHEET_ID=.*|DEFAULT_SHEET_ID=$sheet_id|" "$env_file"
                else
                    echo "DEFAULT_SHEET_ID=$sheet_id" >> "$env_file"
                fi
                print_success "ID Google Sheet configuré"
            fi
        fi
    else
        print_success "ID Google Sheet configuré"
    fi

    # Nettoyage des fichiers backup
    rm -f "$env_file.bak"
}

# ============================================================================
# Validation de la configuration
# ============================================================================

validate_config() {
    print_section "Validation de la configuration"

    source .env 2>/dev/null || true

    local warnings=0
    local errors=0

    # Vérifier PAPPERS_API_KEY
    if [ -z "$PAPPERS_API_KEY" ] || [ "$PAPPERS_API_KEY" = "your_api_key_here" ]; then
        print_warning "Clé API Pappers non configurée"
        echo "           L'enrichissement des données ne fonctionnera pas"
        ((warnings++))
    else
        print_success "Clé API Pappers configurée"
    fi

    # Vérifier credentials Google
    if [ -n "$GOOGLE_SHEETS_CREDENTIALS_PATH" ] && [ -f "$GOOGLE_SHEETS_CREDENTIALS_PATH" ]; then
        print_success "Credentials Google Cloud trouvées"

        # Vérifier que c'est un JSON valide
        if python3 -c "import json; json.load(open('$GOOGLE_SHEETS_CREDENTIALS_PATH'))" 2>/dev/null; then
            print_success "Fichier credentials JSON valide"
        else
            print_error "Fichier credentials JSON invalide"
            ((errors++))
        fi
    else
        print_warning "Credentials Google Cloud non configurées"
        echo "           L'export Google Sheets ne fonctionnera pas"
        ((warnings++))
    fi

    # Vérifier les référentiels
    if [ -f "data/codes_ape.json" ]; then
        local ape_count=$(python3 -c "import json; print(len(json.load(open('data/codes_ape.json'))))")
        print_success "Référentiel codes APE ($ape_count codes)"
    else
        print_error "Référentiel codes APE manquant"
        ((errors++))
    fi

    if [ -f "data/departements.json" ]; then
        local dept_count=$(python3 -c "import json; print(len(json.load(open('data/departements.json'))))")
        print_success "Référentiel départements ($dept_count départements)"
    else
        print_error "Référentiel départements manquant"
        ((errors++))
    fi

    # Vérifier les dossiers
    if [ -d "data/exports" ]; then
        print_success "Dossier exports créé"
    else
        print_warning "Dossier exports manquant, création..."
        mkdir -p data/exports
        print_success "Dossier exports créé"
    fi

    if [ -d "credentials" ]; then
        print_success "Dossier credentials créé"
    else
        print_warning "Dossier credentials manquant, création..."
        mkdir -p credentials
        print_success "Dossier credentials créé"
    fi

    echo ""
    echo -e "${BOLD}Résumé:${NC}"
    if [ $errors -eq 0 ] && [ $warnings -eq 0 ]; then
        print_success "Configuration complète et valide !"
    elif [ $errors -eq 0 ]; then
        echo -e "${YELLOW}Configuration valide avec $warnings avertissement(s)${NC}"
        echo "  L'application peut fonctionner avec des fonctionnalités limitées"
    else
        echo -e "${RED}Configuration incomplète : $errors erreur(s), $warnings avertissement(s)${NC}"
        echo "  Certaines fonctionnalités ne seront pas disponibles"
    fi
}

# ============================================================================
# Test rapide
# ============================================================================

run_quick_test() {
    print_section "Test rapide de l'application"

    if ask_yes_no "Exécuter un test rapide des imports ?" "y"; then
        print_info "Exécution du test..."
        echo ""

        source venv/bin/activate

        python3 << 'PYTEST'
import sys
try:
    print("  → Test config.py...", end=" ")
    import config
    print("✓")

    print("  → Test core.sirene_client...", end=" ")
    from core.sirene_client import SireneClient
    print("✓")

    print("  → Test core.pappers_client...", end=" ")
    from core.pappers_client import PappersClient
    print("✓")

    print("  → Test core.enricher...", end=" ")
    from core.enricher import Enricher
    print("✓")

    print("  → Test core.exporter...", end=" ")
    from core.exporter import Exporter
    print("✓")

    print("  → Test app.py...", end=" ")
    import py_compile
    py_compile.compile('app.py', doraise=True)
    print("✓")

    print()
    print("✅ Tous les tests passent !")
    sys.exit(0)

except Exception as e:
    print(f"✗\n\n❌ Erreur: {e}")
    sys.exit(1)
PYTEST

        if [ $? -eq 0 ]; then
            echo ""
            print_success "Application prête à être lancée"
        else
            echo ""
            print_error "Des erreurs ont été détectées"
        fi
    fi
}

# ============================================================================
# Lancement de l'application
# ============================================================================

launch_app() {
    print_section "Lancement de l'application"

    if ask_yes_no "Lancer l'application Streamlit maintenant ?" "y"; then
        echo ""
        print_info "Lancement de Streamlit..."
        print_info "L'application sera accessible sur http://localhost:8501"
        echo ""
        print_warning "Appuyez sur Ctrl+C pour arrêter l'application"
        echo ""

        sleep 2

        source venv/bin/activate
        streamlit run app.py
    else
        echo ""
        print_info "Pour lancer l'application plus tard, exécutez:"
        echo ""
        echo "  source venv/bin/activate"
        echo "  streamlit run app.py"
        echo ""
    fi
}

# ============================================================================
# Affichage de l'aide
# ============================================================================

show_help() {
    print_section "Aide rapide"

    echo -e "${BOLD}Fichiers de configuration:${NC}"
    echo "  .env                     Variables d'environnement"
    echo "  credentials/             Credentials Google Cloud (JSON)"
    echo "  data/codes_ape.json      Référentiel codes APE"
    echo "  data/departements.json   Référentiel départements"
    echo ""

    echo -e "${BOLD}Commandes utiles:${NC}"
    echo "  ./setup.sh               Relancer ce script de configuration"
    echo "  source venv/bin/activate Activer l'environnement virtuel"
    echo "  streamlit run app.py     Lancer l'application"
    echo "  deactivate               Désactiver le venv"
    echo ""

    echo -e "${BOLD}Documentation:${NC}"
    echo "  README.md                Documentation complète"
    echo "  https://pappers.fr/api   API Pappers (gratuit)"
    echo "  https://console.cloud.google.com  Google Cloud Console"
    echo ""
}

# ============================================================================
# Main
# ============================================================================

main() {
    print_header

    # Vérifier qu'on est dans le bon dossier
    if [ ! -f "app.py" ] || [ ! -f "config.py" ]; then
        print_error "Ce script doit être exécuté depuis le dossier racine du projet"
        exit 1
    fi

    # Exécution des étapes
    check_requirements
    setup_virtualenv
    setup_env_file
    validate_config
    run_quick_test
    show_help
    launch_app

    echo ""
    print_success "Configuration terminée !"
    echo ""
}

# Lancer le script
main
