"""
Application Streamlit pour la génération de leads B2B français.
Interface utilisateur pour piloter les campagnes d'extraction et d'enrichissement.
"""
import json
import logging
import os
from datetime import datetime, date
from typing import List, Dict, Any, Optional

import streamlit as st
import pandas as pd

from core.sirene_client import SireneClient
from core.pappers_client import PappersClient
from core.enricher import Enricher
from core.exporter import Exporter
from core.query_parser import QueryParser
from core.lead_tracker import LeadTracker
from core.hubspot_client import HubSpotClient
from config import (
    GOOGLE_SHEETS_CREDENTIALS_PATH,
    DEFAULT_SHEET_ID,
    MAX_RESULTS,
    ANTHROPIC_API_KEY,
    HUBSPOT_API_KEY
)

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration Streamlit
st.set_page_config(
    page_title="Lead Gen SIRENE",
    page_icon="🎯",
    layout="wide"
)


def load_referentiel(filepath: str) -> List[Dict[str, str]]:
    """
    Charge un fichier référentiel JSON.

    Args:
        filepath: Chemin vers le fichier JSON

    Returns:
        Liste de dict avec 'code' et 'label'
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erreur lors du chargement de {filepath}: {e}")
        return []


def format_option(item: Dict[str, str]) -> str:
    """
    Formate une option pour les selectbox (code - label).

    Args:
        item: Dict avec 'code' et 'label'

    Returns:
        String formatée
    """
    return f"{item['code']} - {item['label']}"


def init_session_state():
    """Initialise les variables de session Streamlit."""
    if 'results' not in st.session_state:
        st.session_state.results = None

    if 'extraction_status' not in st.session_state:
        st.session_state.extraction_status = 'idle'  # idle, running, done, error

    if 'logs' not in st.session_state:
        st.session_state.logs = []

    if 'export_files' not in st.session_state:
        st.session_state.export_files = {}

    # Recherche en langage naturel
    if 'parsed_filters' not in st.session_state:
        st.session_state.parsed_filters = None

    if 'natural_query' not in st.session_state:
        st.session_state.natural_query = ""

    # Déduplication
    if 'enable_deduplication' not in st.session_state:
        st.session_state.enable_deduplication = True


def add_log(message: str):
    """
    Ajoute un message aux logs de session.

    Args:
        message: Message à logger
    """
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.append(f"[{timestamp}] {message}")
    logger.info(message)


def main():
    """Point d'entrée principal de l'application."""
    init_session_state()

    # En-tête
    st.title("🎯 Lead Gen SIRENE")
    st.markdown("Générateur de leads B2B français - SIRENE + Pappers")
    st.divider()

    # Chargement des référentiels
    codes_ape = load_referentiel("data/codes_ape.json")
    departements = load_referentiel("data/departements.json")

    # Recherche en langage naturel
    anthropic_available = ANTHROPIC_API_KEY and ANTHROPIC_API_KEY != "your_anthropic_api_key_here"

    if anthropic_available:
        with st.expander("🔍 Recherche en langage naturel", expanded=True):
            st.markdown("""
            Décrivez votre recherche en français. Exemples :
            - *"PME -50 dans la publicité à Paris"*
            - *"Agences web en Île-de-France"*
            - *"Restaurants Lyon +10 employés"*
            - *"Startups tech Bordeaux créées après 2020"*
            """)

            col1, col2 = st.columns([4, 1])
            with col1:
                natural_query = st.text_input(
                    "Votre recherche",
                    value=st.session_state.natural_query,
                    placeholder="Ex: PME dans la publicité à Paris",
                    label_visibility="collapsed"
                )
            with col2:
                parse_btn = st.button("🔍 Parser", use_container_width=True, type="primary")

            if parse_btn and natural_query:
                try:
                    with st.spinner("Analyse de votre requête..."):
                        parser = QueryParser(
                            codes_ape=codes_ape,
                            departements=departements
                        )
                        filters = parser.parse(natural_query)
                        st.session_state.parsed_filters = filters
                        st.session_state.natural_query = natural_query

                    # Afficher l'interprétation
                    st.success(f"✅ {filters.get('interpretation', 'Filtres extraits avec succès')}")

                    # Afficher les filtres détectés
                    st.markdown("**Filtres détectés :**")
                    cols = st.columns(4)

                    with cols[0]:
                        if 'codes_ape' in filters and filters['codes_ape']:
                            st.metric("Secteurs", len(filters['codes_ape']))
                            st.caption(", ".join(filters['codes_ape'][:3]) + ("..." if len(filters['codes_ape']) > 3 else ""))

                    with cols[1]:
                        if 'departements' in filters and filters['departements']:
                            st.metric("Départements", len(filters['departements']))
                            st.caption(", ".join(filters['departements'][:5]) + ("..." if len(filters['departements']) > 5 else ""))

                    with cols[2]:
                        if 'effectif_min' in filters or 'effectif_max' in filters:
                            eff_min = filters.get('effectif_min', 0)
                            eff_max = filters.get('effectif_max', '∞')
                            st.metric("Effectifs", f"{eff_min}-{eff_max}")

                    with cols[3]:
                        if 'date_creation_min' in filters:
                            st.metric("Créée après", filters['date_creation_min'])

                    st.info("👇 Les filtres sont appliqués ci-dessous. Vous pouvez les ajuster manuellement avant de lancer l'extraction.")

                except ValueError as e:
                    st.error(f"❌ Erreur: {str(e)}")
                    st.info("💡 Essayez de reformuler votre recherche ou configurez l'API Anthropic dans la page Admin")
                except Exception as e:
                    st.error(f"❌ Erreur inattendue: {str(e)}")
                    logger.exception("Erreur lors du parsing de la requête")
    else:
        st.info("💡 **Recherche en langage naturel désactivée** - Configurez l'API Anthropic dans la page ⚙️ Admin pour activer cette fonctionnalité")

    st.divider()

    # Sidebar - Filtres
    with st.sidebar:
        # État de la configuration
        with st.expander("⚙️ Configuration", expanded=False):
            import config as cfg

            # Clé Pappers
            if cfg.PAPPERS_API_KEY and cfg.PAPPERS_API_KEY != "your_api_key_here":
                st.success("✓ Clé API Pappers configurée")
            else:
                st.error("✗ Clé API Pappers manquante")
                st.caption("Configurez-la dans le fichier .env")

            # Credentials Google
            if cfg.GOOGLE_SHEETS_CREDENTIALS_PATH and os.path.exists(cfg.GOOGLE_SHEETS_CREDENTIALS_PATH):
                st.success("✓ Credentials Google Cloud OK")
                # Afficher l'email du service account
                try:
                    import json
                    with open(cfg.GOOGLE_SHEETS_CREDENTIALS_PATH, 'r') as f:
                        creds_data = json.load(f)
                        if 'client_email' in creds_data:
                            st.caption(f"Service account: `{creds_data['client_email']}`")
                            st.caption("⚠️ Donnez accès à ce compte dans votre Google Sheet")
                except:
                    pass
            else:
                st.warning("⚠ Credentials Google Cloud non trouvées")
                st.caption("Export Google Sheets indisponible")

            # HubSpot
            if cfg.HUBSPOT_API_KEY and cfg.HUBSPOT_API_KEY != "your_hubspot_api_key_here":
                st.success("✓ HubSpot API configurée")
                st.caption("Déduplication et export HubSpot activés")
            else:
                st.info("ℹ️ HubSpot optionnel (déduplication + export)")

            st.caption("Utilisez la page ⚙️ Admin pour configurer")

        st.header("Filtres de recherche")

        # Utiliser les filtres parsés si disponibles
        parsed = st.session_state.parsed_filters or {}

        # Pré-sélectionner les secteurs APE depuis le parsing
        default_ape = []
        if 'codes_ape' in parsed and parsed['codes_ape']:
            # Trouver les objets correspondant aux codes parsés
            for code in parsed['codes_ape']:
                matching = [item for item in codes_ape if item['code'] == code]
                if matching:
                    default_ape.append(matching[0])

        # Secteurs (APE)
        selected_ape = st.multiselect(
            "Secteurs d'activité (APE)",
            options=codes_ape,
            default=default_ape,
            format_func=format_option,
            help="Sélectionnez un ou plusieurs codes APE"
        )

        # Pré-sélectionner les départements depuis le parsing
        default_dept = []
        if 'departements' in parsed and parsed['departements']:
            for code in parsed['departements']:
                matching = [item for item in departements if item['code'] == code]
                if matching:
                    default_dept.append(matching[0])

        # Départements
        selected_dept = st.multiselect(
            "Départements",
            options=departements,
            default=default_dept,
            format_func=format_option,
            help="Sélectionnez un ou plusieurs départements"
        )

        # Effectifs
        st.subheader("Effectifs")
        col1, col2 = st.columns(2)
        with col1:
            effectif_min = st.number_input(
                "Minimum",
                min_value=0,
                max_value=5000,
                value=parsed.get('effectif_min', 0),
                step=1
            )
        with col2:
            effectif_max = st.number_input(
                "Maximum",
                min_value=0,
                max_value=5000,
                value=parsed.get('effectif_max', 5000),
                step=1
            )

        # Date de création
        from datetime import date
        default_date = None
        if 'date_creation_min' in parsed:
            try:
                default_date = datetime.strptime(parsed['date_creation_min'], "%Y-%m-%d").date()
            except:
                pass

        date_creation_min = st.date_input(
            "Créée après",
            value=default_date,
            min_value=date(1800, 1, 1),  # Permettre les entreprises historiques (ex: Barrière 1914)
            max_value=date.today(),
            help="Filtrer les entreprises créées après cette date"
        )

        # Nombre max de leads
        max_leads = st.number_input(
            "Nombre maximum de leads",
            min_value=1,  # Permettre 1 seul lead pour les tests
            max_value=MAX_RESULTS,
            value=10,
            step=1,
            help=f"Minimum 1, maximum {MAX_RESULTS}"
        )

        st.divider()

        # Options d'enrichissement
        st.subheader("Enrichissement")
        enable_pappers = st.checkbox(
            "Enrichir avec Pappers",
            value=True,
            help="Enrichissement avec dirigeants, email, téléphone, CA (consomme des crédits Pappers)"
        )

        if not enable_pappers:
            st.caption("⚠️ Sans enrichissement, seules les données SIRENE seront disponibles")

        st.divider()

        # Déduplication
        st.subheader("Déduplication")
        enable_deduplication = st.checkbox(
            "Éviter les doublons",
            value=st.session_state.enable_deduplication,
            help="Filtre automatiquement les entreprises déjà extraites précédemment"
        )
        st.session_state.enable_deduplication = enable_deduplication

        if enable_deduplication:
            # Afficher les stats de l'historique
            try:
                tracker = LeadTracker()
                stats = tracker.get_stats()
                if stats['total_leads'] > 0:
                    st.caption(f"📊 {stats['total_leads']} leads déjà extraits ({stats['num_campagnes']} campagnes)")
                else:
                    st.caption("ℹ️ Aucun historique - première extraction")
            except Exception as e:
                logger.error(f"Erreur lors du chargement des stats: {e}")

        st.divider()

        # Export
        st.subheader("Export")

        # Google Sheets
        enable_sheets = st.checkbox(
            "Export Google Sheets",
            value=False
        )

        sheet_id = None
        if enable_sheets:
            sheet_id = st.text_input(
                "ID du Google Sheet",
                value=DEFAULT_SHEET_ID or "",
                help="ID du spreadsheet (dans l'URL)"
            )

        # HubSpot
        hubspot_available = HUBSPOT_API_KEY and HUBSPOT_API_KEY != "your_hubspot_api_key_here"
        enable_hubspot = st.checkbox(
            "Export HubSpot",
            value=False,
            disabled=not hubspot_available,
            help="Envoyer automatiquement les leads vers HubSpot CRM" if hubspot_available else "Configurez l'API HubSpot dans Admin"
        )

        if not hubspot_available and enable_hubspot:
            st.caption("⚠️ Configurez HubSpot dans la page ⚙️ Admin")

        st.divider()

        # Bouton d'extraction
        extraction_disabled = (
            st.session_state.extraction_status == 'running' or
            (not selected_ape and not selected_dept)
        )

        if st.button(
            "🚀 Lancer l'extraction",
            disabled=extraction_disabled,
            use_container_width=True,
            type="primary"
        ):
            run_extraction(
                codes_ape=[item['code'] for item in selected_ape],
                departements=[item['code'] for item in selected_dept],
                effectif_min=effectif_min if effectif_min > 0 else None,
                effectif_max=effectif_max if effectif_max < 5000 else None,
                date_creation_min=date_creation_min.strftime("%Y-%m-%d") if date_creation_min else None,
                max_leads=max_leads,
                enable_pappers=enable_pappers,
                enable_deduplication=enable_deduplication,
                sheet_id=sheet_id if enable_sheets else None,
                enable_hubspot=enable_hubspot if hubspot_available else False
            )

        if not selected_ape and not selected_dept:
            st.warning("⚠️ Sélectionnez au moins un secteur ou département")

    # Zone principale
    if st.session_state.extraction_status == 'running':
        show_extraction_progress()
    elif st.session_state.extraction_status == 'done':
        show_results()
    elif st.session_state.extraction_status == 'error':
        show_error()
    else:
        show_welcome()


def show_welcome():
    """Affiche l'écran d'accueil."""
    st.info("👈 Configurez vos filtres dans la barre latérale et lancez l'extraction")

    # Afficher les stats si on a des résultats précédents
    if st.session_state.results:
        st.subheader("Dernière extraction")
        show_results()


def show_extraction_progress():
    """Affiche un message pendant l'extraction (l'extraction se fait dans run_extraction)."""
    st.info("⏳ Extraction en cours... Veuillez patienter.")


def show_results():
    """Affiche les résultats de l'extraction."""
    results = st.session_state.results
    export_files = st.session_state.export_files

    if not results:
        st.warning("Aucun résultat à afficher")
        return

    # Statistiques
    st.subheader("📊 Résultats")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total leads", len(results))
    with col2:
        with_email = sum(1 for r in results if r.get('email'))
        st.metric("Avec email", with_email, f"{with_email/len(results)*100:.0f}%")
    with col3:
        with_phone = sum(1 for r in results if r.get('telephone'))
        st.metric("Avec téléphone", with_phone, f"{with_phone/len(results)*100:.0f}%")
    with col4:
        with_dirigeant = sum(1 for r in results if r.get('dirigeant_nom'))
        st.metric("Avec dirigeant", with_dirigeant, f"{with_dirigeant/len(results)*100:.0f}%")

    st.divider()

    # Preview des données
    st.subheader("📋 Aperçu des données (10 premières lignes)")

    # Convertir en DataFrame pour affichage
    df = pd.DataFrame(results)

    # Sélectionner les colonnes à afficher
    display_columns = [
        'siren', 'denomination', 'ville', 'code_ape',
        'dirigeant_nom', 'dirigeant_prenom', 'email', 'telephone'
    ]
    display_columns = [col for col in display_columns if col in df.columns]

    st.dataframe(
        df[display_columns].head(10),
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    # Boutons d'export
    st.subheader("💾 Téléchargements")

    # Déterminer le nombre de colonnes en fonction des exports disponibles
    num_exports = sum([
        'csv_path' in export_files,
        'sheet_url' in export_files,
        'hubspot_created' in export_files
    ])

    if num_exports == 0:
        st.warning("Aucun export disponible")
    else:
        cols = st.columns(min(num_exports, 3))
        col_idx = 0

        if 'csv_path' in export_files:
            with cols[col_idx]:
                csv_path = export_files['csv_path']
                if os.path.exists(csv_path):
                    with open(csv_path, 'rb') as f:
                        st.download_button(
                            label="📥 Télécharger CSV",
                            data=f,
                            file_name=os.path.basename(csv_path),
                            mime="text/csv",
                            use_container_width=True
                        )
            col_idx += 1

        if 'sheet_url' in export_files:
            with cols[col_idx]:
                st.link_button(
                    label="📊 Ouvrir Google Sheet",
                    url=export_files['sheet_url'],
                    use_container_width=True
                )
            col_idx += 1

        if 'hubspot_created' in export_files:
            with cols[col_idx]:
                st.success(f"✅ {export_files['hubspot_created']} contacts créés dans HubSpot")
                st.caption("Consultez votre CRM HubSpot")

    # Logs
    with st.expander("📋 Logs de l'extraction"):
        for log in st.session_state.logs:
            st.text(log)


def show_error():
    """Affiche l'écran d'erreur."""
    st.error("❌ Une erreur est survenue lors de l'extraction")

    with st.expander("📋 Logs d'erreur", expanded=True):
        for log in st.session_state.logs:
            st.text(log)

    if st.button("Réinitialiser"):
        st.session_state.extraction_status = 'idle'
        st.session_state.logs = []
        st.rerun()


def run_extraction(
    codes_ape: List[str],
    departements: List[str],
    effectif_min: Optional[int],
    effectif_max: Optional[int],
    date_creation_min: Optional[str],
    max_leads: int,
    enable_pappers: bool,
    enable_deduplication: bool,
    sheet_id: Optional[str],
    enable_hubspot: bool = False
):
    """
    Lance l'extraction et l'enrichissement des leads.

    Args:
        codes_ape: Codes APE sélectionnés
        departements: Départements sélectionnés
        effectif_min: Effectif minimum
        effectif_max: Effectif maximum
        date_creation_min: Date de création minimum
        max_leads: Nombre max de leads
        enable_pappers: Activer l'enrichissement Pappers
        enable_deduplication: Filtrer les doublons SQLite
        sheet_id: ID du Google Sheet (optionnel)
        enable_hubspot: Activer déduplication et export HubSpot
    """
    # Créer des placeholders pour la mise à jour en temps réel
    progress_bar = st.progress(0)
    status_text = st.empty()
    logs_container = st.expander("📋 Logs détaillés", expanded=True)

    st.session_state.extraction_status = 'running'
    st.session_state.logs = []
    st.session_state.results = None
    st.session_state.export_files = {}

    def update_log(message):
        """Ajoute un log et met à jour l'affichage."""
        add_log(message)
        with logs_container:
            st.text("\n".join(st.session_state.logs))

    try:
        # Étape 1: Recherche SIRENE
        progress_bar.progress(10)
        status_text.text("📡 Recherche SIRENE en cours...")
        update_log("📡 Recherche des entreprises via SIRENE...")

        with SireneClient() as sirene_client:
            companies = sirene_client.search_all(
                codes_ape=codes_ape if codes_ape else None,
                departements=departements if departements else None,
                effectif_min=effectif_min,
                effectif_max=effectif_max,
                date_creation_min=date_creation_min,
                max_results=max_leads
            )

        progress_bar.progress(30)
        update_log(f"✅ {len(companies)} entreprises trouvées")

        if not companies:
            update_log("⚠️ Aucune entreprise trouvée avec ces critères")
            st.session_state.extraction_status = 'done'
            status_text.text("Aucun résultat")
            progress_bar.progress(100)
            return

        # Étape 1.5: Filtrage des doublons SQLite (optionnel)
        if enable_deduplication:
            progress_bar.progress(35)
            status_text.text("🔍 Filtrage des doublons SQLite...")
            update_log("🔍 Vérification des doublons dans l'historique SQLite...")

            tracker = LeadTracker()
            companies, num_duplicates = tracker.filter_duplicates(companies)

            if num_duplicates > 0:
                update_log(f"⚠️ {num_duplicates} doublons SQLite filtrés")

            if not companies:
                update_log("⚠️ Toutes les entreprises ont déjà été extraites précédemment")
                st.session_state.extraction_status = 'done'
                status_text.text("Aucun nouveau lead")
                progress_bar.progress(100)
                return

            update_log(f"✅ {len(companies)} nouveaux leads après SQLite")

        # Étape 1.6: Filtrage des doublons HubSpot (optionnel)
        if enable_hubspot:
            progress_bar.progress(37)
            status_text.text("🔍 Filtrage des doublons HubSpot...")
            update_log("🔍 Vérification des doublons dans HubSpot...")

            try:
                hubspot_client = HubSpotClient(HUBSPOT_API_KEY)
                enricher_temp = Enricher(None, hubspot_client)
                companies, num_dups_hubspot = enricher_temp.deduplicate_against_hubspot(companies)

                if num_dups_hubspot > 0:
                    update_log(f"🟠 {num_dups_hubspot} doublons HubSpot filtrés")

                if not companies:
                    update_log("⚠️ Toutes les entreprises sont déjà dans HubSpot")
                    st.session_state.extraction_status = 'done'
                    status_text.text("Aucun nouveau lead")
                    progress_bar.progress(100)
                    return

                update_log(f"✅ {len(companies)} nouveaux leads après HubSpot")

            except Exception as e:
                logger.error(f"Erreur lors de la déduplication HubSpot: {e}")
                update_log(f"⚠️ Erreur déduplication HubSpot: {e}")
                # Continuer sans dédup HubSpot

        # Étape 2: Enrichissement Pappers (optionnel)
        if enable_pappers:
            progress_bar.progress(40)
            status_text.text("💎 Enrichissement Pappers en cours...")
            update_log("💎 Enrichissement via Pappers...")

            try:
                with PappersClient() as pappers_client:
                    enricher = Enricher(pappers_client)

                    def progress_callback(current, total):
                        """Callback pour la progression de l'enrichissement."""
                        percent = 40 + int((current / total) * 40)  # 40% à 80%
                        progress_bar.progress(percent)
                        if current % 5 == 0 or current == total:  # Log tous les 5
                            update_log(f"  → Enrichissement: {current}/{total}")

                    enriched_companies = enricher.enrich_batch(
                        companies,
                        progress_callback=progress_callback
                    )

                progress_bar.progress(80)
                update_log(f"✅ {len(enriched_companies)} entreprises enrichies")

                # Statistiques
                stats = enricher.get_statistics(enriched_companies)
                update_log(
                    f"📊 Stats: {stats['with_email']} emails, "
                    f"{stats['with_phone']} téléphones, "
                    f"{stats['with_dirigeant']} dirigeants"
                )

            except ValueError as e:
                if "PAPPERS_API_KEY" in str(e):
                    update_log("⚠️ Clé API Pappers non configurée - enrichissement ignoré")
                    enriched_companies = companies
                else:
                    raise
        else:
            # Pas d'enrichissement Pappers
            enriched_companies = companies
            progress_bar.progress(80)
            update_log("ℹ️ Enrichissement Pappers désactivé - données SIRENE uniquement")

        # Étape 3: Export
        progress_bar.progress(85)
        status_text.text("💾 Export en cours...")
        update_log("💾 Export des données...")

        csv_filename = f"leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Préparer le client HubSpot si nécessaire
        hubspot_client = None
        if enable_hubspot:
            hubspot_client = HubSpotClient(HUBSPOT_API_KEY)

        exporter = Exporter(
            credentials_path=GOOGLE_SHEETS_CREDENTIALS_PATH,
            hubspot_client=hubspot_client
        )
        export_results = exporter.export_all(
            data=enriched_companies,
            csv_filename=csv_filename,
            sheet_id=sheet_id,
            enable_hubspot=enable_hubspot
        )

        st.session_state.export_files = export_results

        if 'csv_path' in export_results:
            update_log(f"✅ CSV exporté: {export_results['csv_path']}")

        if 'csv_error' in export_results:
            update_log(f"❌ Erreur export CSV: {export_results['csv_error']}")

        if 'sheet_url' in export_results:
            update_log(f"✅ Google Sheet: {export_results['sheet_url']}")

        if 'sheet_error' in export_results:
            update_log(f"❌ Erreur export Google Sheet: {export_results['sheet_error']}")
            update_log("   Vérifiez:")
            update_log("   • Le service account a accès au Sheet")
            update_log("   • L'ID du Sheet est correct")
            update_log("   • Les credentials sont valides")

        if 'hubspot_created' in export_results:
            update_log(f"✅ HubSpot: {export_results['hubspot_created']} contacts créés")

        if 'hubspot_error' in export_results:
            update_log(f"❌ Erreur export HubSpot: {export_results['hubspot_error']}")

        # Étape 4: Enregistrement dans l'historique (si déduplication activée)
        if enable_deduplication:
            progress_bar.progress(95)
            update_log("📝 Enregistrement dans l'historique...")

            try:
                tracker = LeadTracker()
                campagne_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                added = tracker.add_leads(enriched_companies, campagne_id=campagne_id)
                update_log(f"✅ {added} leads ajoutés à l'historique")
            except Exception as e:
                logger.error(f"Erreur lors de l'enregistrement dans l'historique: {e}")
                update_log(f"⚠️ Erreur lors de l'enregistrement: {e}")

        # Sauvegarder les résultats
        st.session_state.results = enriched_companies
        st.session_state.extraction_status = 'done'

        progress_bar.progress(100)
        status_text.text("✅ Extraction terminée!")
        update_log("🎉 Extraction terminée avec succès!")

        # Attendre un peu avant de rerun pour que l'utilisateur voie le message
        import time
        time.sleep(1)

    except Exception as e:
        update_log(f"❌ Erreur: {str(e)}")
        logger.exception("Erreur lors de l'extraction")
        st.session_state.extraction_status = 'error'
        status_text.text("❌ Erreur lors de l'extraction")
        progress_bar.progress(0)


if __name__ == "__main__":
    main()
