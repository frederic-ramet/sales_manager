"""
Page Recherche de Leads - Extraction et enrichissement B2B.
"""
import json
import logging
import os
from datetime import datetime, date
from typing import List, Dict, Any, Optional

import streamlit as st
import pandas as pd
from dotenv import load_dotenv

from modules.lead_scraper import (
    SireneClient,
    PappersClient,
    Enricher,
    Exporter,
    QueryParser,
    ContactManager,
    HubSpotClient
)

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
load_dotenv()

st.title("🎯 Recherche de Leads")
st.markdown("Extraction et enrichissement de leads B2B français")

# Onglets principal et documentation
tab_main, tab_doc = st.tabs(["🔧 Application", "📖 Documentation"])

# Charger la documentation
def load_documentation():
    doc_path = "docs/pages/recherche_leads.md"
    try:
        with open(doc_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "Documentation non disponible."

with tab_doc:
    st.markdown(load_documentation())

with tab_main:
    # Configuration depuis .env
    MAX_RESULTS = int(os.getenv('MAX_RESULTS', '500'))
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    HUBSPOT_API_KEY = os.getenv('HUBSPOT_API_KEY')
    PAPPERS_API_KEY = os.getenv('PAPPERS_API_KEY')
    GOOGLE_CREDENTIALS_PATH = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials/service-account.json')
    DEFAULT_SHEET_ID = os.getenv('DEFAULT_SHEET_ID', '')


    def load_referentiel(filepath: str) -> List[Dict[str, str]]:
        """Charge un fichier référentiel JSON."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erreur lors du chargement de {filepath}: {e}")
            return []


    def format_option(item: Dict[str, str]) -> str:
        """Formate une option pour les selectbox (code - label)."""
        return f"{item['code']} - {item['label']}"


    def init_session_state():
        """Initialise les variables de session Streamlit."""
        if 'results' not in st.session_state:
            st.session_state.results = None
        if 'extraction_status' not in st.session_state:
            st.session_state.extraction_status = 'idle'
        if 'logs' not in st.session_state:
            st.session_state.logs = []
        if 'export_files' not in st.session_state:
            st.session_state.export_files = {}
        if 'parsed_filters' not in st.session_state:
            st.session_state.parsed_filters = None
        if 'natural_query' not in st.session_state:
            st.session_state.natural_query = ""
        if 'enable_deduplication' not in st.session_state:
            st.session_state.enable_deduplication = True


    def add_log(message: str):
        """Ajoute un message aux logs de session."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        st.session_state.logs.append(f"[{timestamp}] {message}")
        logger.info(message)


    # Initialisation
    init_session_state()

    # Chargement des référentiels
    codes_ape = load_referentiel("data/codes_ape.json")
    departements = load_referentiel("data/departements.json")

    st.divider()

    # Recherche en langage naturel
    anthropic_available = ANTHROPIC_API_KEY and ANTHROPIC_API_KEY != "your_anthropic_api_key_here"

    if anthropic_available:
        with st.expander("🔍 Recherche en langage naturel", expanded=True):
            st.markdown("""
            Décrivez votre recherche en français. Exemples :
            - *"PME -50 dans la publicité à Paris"*
            - *"Agences web en Île-de-France"*
            - *"Restaurants Lyon +10 employés"*
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

                    st.success(f"✅ {filters.get('interpretation', 'Filtres extraits avec succès')}")

                    st.markdown("**Filtres détectés :**")
                    cols = st.columns(4)

                    with cols[0]:
                        if 'codes_ape' in filters and filters['codes_ape']:
                            st.metric("Secteurs", len(filters['codes_ape']))

                    with cols[1]:
                        if 'departements' in filters and filters['departements']:
                            st.metric("Départements", len(filters['departements']))

                    with cols[2]:
                        if 'effectif_min' in filters or 'effectif_max' in filters:
                            eff_min = filters.get('effectif_min', 0)
                            eff_max = filters.get('effectif_max', '∞')
                            st.metric("Effectifs", f"{eff_min}-{eff_max}")

                    with cols[3]:
                        if 'date_creation_min' in filters:
                            st.metric("Créée après", filters['date_creation_min'])

                except ValueError as e:
                    st.error(f"❌ Erreur: {str(e)}")
                except Exception as e:
                    st.error(f"❌ Erreur inattendue: {str(e)}")
    else:
        st.info("💡 **Recherche en langage naturel désactivée** - Configurez ANTHROPIC_API_KEY dans .env")

    st.divider()


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
        """Lance l'extraction et l'enrichissement des leads."""
        progress_bar = st.progress(0)
        status_text = st.empty()
        logs_container = st.expander("📋 Logs détaillés", expanded=True)

        st.session_state.extraction_status = 'running'
        st.session_state.logs = []
        st.session_state.results = None
        st.session_state.export_files = {}

        def update_log(message):
            add_log(message)
            with logs_container:
                st.text("\n".join(st.session_state.logs))

        try:
            # Étape 1: Recherche SIRENE
            progress_bar.progress(10)
            status_text.text("📡 Recherche SIRENE...")
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
                update_log("⚠️ Aucune entreprise trouvée")
                st.session_state.extraction_status = 'done'
                status_text.text("Aucun résultat")
                progress_bar.progress(100)
                return

            # Déduplication SQLite
            if enable_deduplication:
                progress_bar.progress(35)
                status_text.text("🔍 Filtrage des doublons...")
                update_log("🔍 Vérification des doublons SQLite...")

                contact_manager = ContactManager()
                companies, num_duplicates = contact_manager.filter_duplicates(companies)

                if num_duplicates > 0:
                    update_log(f"⚠️ {num_duplicates} doublons filtrés")

                if not companies:
                    update_log("⚠️ Toutes les entreprises déjà extraites")
                    st.session_state.extraction_status = 'done'
                    status_text.text("Aucun nouveau lead")
                    progress_bar.progress(100)
                    return

                update_log(f"✅ {len(companies)} nouveaux leads")

            # Déduplication HubSpot
            if enable_hubspot:
                progress_bar.progress(37)
                status_text.text("🔍 Filtrage HubSpot...")
                update_log("🔍 Vérification dans HubSpot...")

                try:
                    hubspot_client = HubSpotClient()
                    enricher_temp = Enricher(None, hubspot_client)
                    companies, num_dups = enricher_temp.deduplicate_against_hubspot(companies)

                    if num_dups > 0:
                        update_log(f"🟠 {num_dups} doublons HubSpot filtrés")

                    if not companies:
                        update_log("⚠️ Toutes les entreprises dans HubSpot")
                        st.session_state.extraction_status = 'done'
                        progress_bar.progress(100)
                        return

                except Exception as e:
                    update_log(f"⚠️ Erreur HubSpot: {e}")

            # Enrichissement Pappers
            if enable_pappers:
                progress_bar.progress(40)
                status_text.text("💎 Enrichissement Pappers...")
                update_log("💎 Enrichissement via Pappers...")

                try:
                    with PappersClient() as pappers_client:
                        enricher = Enricher(pappers_client)

                        def progress_callback(current, total):
                            percent = 40 + int((current / total) * 40)
                            progress_bar.progress(percent)

                        enriched_companies = enricher.enrich_batch(
                            companies,
                            progress_callback=progress_callback
                        )

                    progress_bar.progress(80)
                    update_log(f"✅ {len(enriched_companies)} entreprises enrichies")

                    stats = enricher.get_statistics(enriched_companies)
                    update_log(
                        f"📊 {stats['with_email']} emails, "
                        f"{stats['with_phone']} téléphones"
                    )

                except ValueError as e:
                    if "PAPPERS_API_KEY" in str(e):
                        update_log("⚠️ Clé Pappers non configurée")
                        enriched_companies = companies
                    else:
                        raise
            else:
                enriched_companies = companies
                progress_bar.progress(80)
                update_log("ℹ️ Enrichissement désactivé")

            # Export
            progress_bar.progress(85)
            status_text.text("💾 Export...")
            update_log("💾 Export des données...")

            csv_filename = f"leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            hubspot_client = None
            if enable_hubspot:
                hubspot_client = HubSpotClient()

            exporter = Exporter(
                credentials_path=GOOGLE_CREDENTIALS_PATH,
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
                update_log(f"✅ CSV: {export_results['csv_path']}")
            if 'sheet_url' in export_results:
                update_log(f"✅ Google Sheet OK")
            if 'hubspot_created' in export_results:
                update_log(f"✅ HubSpot: {export_results['hubspot_created']} contacts")

            # Enregistrement historique
            if enable_deduplication:
                progress_bar.progress(95)
                update_log("📝 Enregistrement historique...")

                try:
                    contact_manager = ContactManager()
                    campagne_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                    added, _ = contact_manager.import_from_sirene(enriched_companies, campaign_id=campagne_id)
                    update_log(f"✅ {added} leads ajoutés")
                except Exception as e:
                    update_log(f"⚠️ Erreur enregistrement: {e}")

            st.session_state.results = enriched_companies
            st.session_state.extraction_status = 'done'

            progress_bar.progress(100)
            status_text.text("✅ Extraction terminée!")
            update_log("🎉 Terminé!")

        except Exception as e:
            update_log(f"❌ Erreur: {str(e)}")
            logger.exception("Erreur extraction")
            st.session_state.extraction_status = 'error'
            status_text.text("❌ Erreur")
            progress_bar.progress(0)


    # Zone principale - Affichage des résultats
    if st.session_state.extraction_status == 'done' and st.session_state.results:
        results = st.session_state.results
        export_files = st.session_state.export_files

        st.subheader("📊 Résultats")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total leads", len(results))
        with col2:
            with_email = sum(1 for r in results if r.get('email'))
            st.metric("Avec email", with_email)
        with col3:
            with_phone = sum(1 for r in results if r.get('telephone'))
            st.metric("Avec téléphone", with_phone)
        with col4:
            with_dirigeant = sum(1 for r in results if r.get('dirigeant_nom'))
            st.metric("Avec dirigeant", with_dirigeant)

        st.divider()

        # Preview
        st.subheader("📋 Aperçu (10 premières)")
        df = pd.DataFrame(results)

        display_columns = [
            'siren', 'denomination', 'ville', 'code_ape',
            'dirigeant_nom', 'email', 'telephone'
        ]
        display_columns = [col for col in display_columns if col in df.columns]

        st.dataframe(df[display_columns].head(10), use_container_width=True)

        st.divider()

        # Téléchargements
        st.subheader("💾 Téléchargements")

        cols = st.columns(3)

        if 'csv_path' in export_files:
            csv_path = export_files['csv_path']
            if os.path.exists(csv_path):
                with cols[0]:
                    with open(csv_path, 'rb') as f:
                        st.download_button(
                            label="📥 Télécharger CSV",
                            data=f,
                            file_name=os.path.basename(csv_path),
                            mime="text/csv",
                            use_container_width=True
                        )

        if 'sheet_url' in export_files:
            with cols[1]:
                st.link_button(
                    label="📊 Google Sheet",
                    url=export_files['sheet_url'],
                    use_container_width=True
                )

        if 'hubspot_created' in export_files:
            with cols[2]:
                st.success(f"✅ {export_files['hubspot_created']} dans HubSpot")

    elif st.session_state.extraction_status == 'error':
        st.error("❌ Une erreur est survenue")

        with st.expander("📋 Logs d'erreur", expanded=True):
            for log in st.session_state.logs:
                st.text(log)

        if st.button("Réinitialiser"):
            st.session_state.extraction_status = 'idle'
            st.session_state.logs = []
            st.rerun()

    else:
        st.info("👈 Configurez vos filtres dans la barre latérale et lancez l'extraction")

# Sidebar - Filtres (en dehors des tabs)
with st.sidebar:
    st.header("Filtres de recherche")

    # Chargement des référentiels pour la sidebar
    codes_ape_sidebar = []
    departements_sidebar = []
    try:
        with open("data/codes_ape.json", 'r', encoding='utf-8') as f:
            codes_ape_sidebar = json.load(f)
        with open("data/departements.json", 'r', encoding='utf-8') as f:
            departements_sidebar = json.load(f)
    except:
        pass

    def format_option_sidebar(item):
        return f"{item['code']} - {item['label']}"

    # Utiliser les filtres parsés si disponibles
    parsed = st.session_state.get('parsed_filters') or {}

    # Pré-sélectionner les secteurs APE depuis le parsing
    default_ape = []
    if 'codes_ape' in parsed and parsed['codes_ape']:
        for code in parsed['codes_ape']:
            matching = [item for item in codes_ape_sidebar if item['code'] == code]
            if matching:
                default_ape.append(matching[0])

    selected_ape = st.multiselect(
        "Secteurs d'activité (APE)",
        options=codes_ape_sidebar,
        default=default_ape,
        format_func=format_option_sidebar,
        help="Sélectionnez un ou plusieurs codes APE"
    )

    # Pré-sélectionner les départements depuis le parsing
    default_dept = []
    if 'departements' in parsed and parsed['departements']:
        for code in parsed['departements']:
            matching = [item for item in departements_sidebar if item['code'] == code]
            if matching:
                default_dept.append(matching[0])

    selected_dept = st.multiselect(
        "Départements",
        options=departements_sidebar,
        default=default_dept,
        format_func=format_option_sidebar,
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
    default_date = None
    if 'date_creation_min' in parsed:
        try:
            default_date = datetime.strptime(parsed['date_creation_min'], "%Y-%m-%d").date()
        except:
            pass

    date_creation_min = st.date_input(
        "Créée après",
        value=default_date,
        min_value=date(1800, 1, 1),
        max_value=date.today(),
        help="Filtrer les entreprises créées après cette date"
    )

    # Nombre max de leads
    MAX_RESULTS = int(os.getenv('MAX_RESULTS', '500'))
    max_leads = st.number_input(
        "Nombre maximum de leads",
        min_value=1,
        max_value=MAX_RESULTS,
        value=1,
        step=1,
        help=f"Minimum 1, maximum {MAX_RESULTS}"
    )

    st.divider()

    # Options d'enrichissement
    st.subheader("Enrichissement")
    PAPPERS_API_KEY = os.getenv('PAPPERS_API_KEY')
    pappers_available = PAPPERS_API_KEY and PAPPERS_API_KEY != "your_pappers_api_key_here"
    enable_pappers = st.checkbox(
        "Enrichir avec Pappers",
        value=pappers_available,
        disabled=not pappers_available,
        help="Enrichissement avec dirigeants, email, téléphone, CA"
    )

    if not pappers_available:
        st.caption("⚠️ Configurez PAPPERS_API_KEY dans .env")

    st.divider()

    # Déduplication
    st.subheader("Déduplication")
    enable_deduplication = st.checkbox(
        "Éviter les doublons",
        value=st.session_state.get('enable_deduplication', True),
        help="Filtre les entreprises déjà extraites"
    )
    st.session_state.enable_deduplication = enable_deduplication

    if enable_deduplication:
        try:
            from modules.lead_scraper import ContactManager
            manager = ContactManager()
            stats = manager.get_stats()
            if stats['total_contacts'] > 0:
                st.caption(f"📊 {stats['total_contacts']} contacts en base")
        except Exception as e:
            pass

    st.divider()

    # Export
    st.subheader("Export")
    GOOGLE_CREDENTIALS_PATH = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials/service-account.json')
    DEFAULT_SHEET_ID = os.getenv('DEFAULT_SHEET_ID', '')

    enable_sheets = st.checkbox("Export Google Sheets", value=False)
    sheet_id = None
    if enable_sheets:
        sheet_id = st.text_input(
            "ID du Google Sheet",
            value=DEFAULT_SHEET_ID or "",
            help="ID du spreadsheet (dans l'URL)"
        )

    HUBSPOT_API_KEY = os.getenv('HUBSPOT_API_KEY')
    hubspot_available = HUBSPOT_API_KEY and HUBSPOT_API_KEY != "your_hubspot_api_key_here"
    enable_hubspot = st.checkbox(
        "Export HubSpot",
        value=False,
        disabled=not hubspot_available,
        help="Envoyer les leads vers HubSpot CRM" if hubspot_available else "Configurez HUBSPOT_API_KEY"
    )

    st.divider()

    # Bouton d'extraction
    extraction_disabled = (
        st.session_state.get('extraction_status') == 'running' or
        (not selected_ape and not selected_dept)
    )

    if st.button(
        "🚀 Lancer l'extraction",
        disabled=extraction_disabled,
        use_container_width=True,
        type="primary"
    ):
        # Import and run extraction in main tab
        with tab_main:
            from modules.lead_scraper import SireneClient, PappersClient, Enricher, Exporter, ContactManager, HubSpotClient

            def run_extraction_sidebar(
                codes_ape_list, dept_list, eff_min, eff_max,
                date_min, max_l, pappers, dedup, sheet, hubspot
            ):
                progress_bar = st.progress(0)
                status_text = st.empty()
                logs_container = st.expander("📋 Logs détaillés", expanded=True)

                st.session_state.extraction_status = 'running'
                st.session_state.logs = []
                st.session_state.results = None
                st.session_state.export_files = {}

                def update_log(message):
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    st.session_state.logs.append(f"[{timestamp}] {message}")
                    with logs_container:
                        st.text("\n".join(st.session_state.logs))

                try:
                    progress_bar.progress(10)
                    status_text.text("📡 Recherche SIRENE...")
                    update_log("📡 Recherche des entreprises via SIRENE...")

                    with SireneClient() as sirene_client:
                        companies = sirene_client.search_all(
                            codes_ape=codes_ape_list if codes_ape_list else None,
                            departements=dept_list if dept_list else None,
                            effectif_min=eff_min,
                            effectif_max=eff_max,
                            date_creation_min=date_min,
                            max_results=max_l
                        )

                    progress_bar.progress(30)
                    update_log(f"✅ {len(companies)} entreprises trouvées")

                    if not companies:
                        update_log("⚠️ Aucune entreprise trouvée")
                        st.session_state.extraction_status = 'done'
                        status_text.text("Aucun résultat")
                        progress_bar.progress(100)
                        return

                    if dedup:
                        progress_bar.progress(35)
                        status_text.text("🔍 Filtrage des doublons...")
                        contact_manager = ContactManager()
                        companies, num_duplicates = contact_manager.filter_duplicates(companies)
                        if num_duplicates > 0:
                            update_log(f"⚠️ {num_duplicates} doublons filtrés")
                        if not companies:
                            update_log("⚠️ Toutes les entreprises déjà extraites")
                            st.session_state.extraction_status = 'done'
                            progress_bar.progress(100)
                            return
                        update_log(f"✅ {len(companies)} nouveaux leads")

                    if pappers:
                        progress_bar.progress(40)
                        status_text.text("💎 Enrichissement Pappers...")
                        update_log("💎 Enrichissement via Pappers...")
                        try:
                            with PappersClient() as pappers_client:
                                enricher = Enricher(pappers_client)
                                companies = enricher.enrich_batch(companies)
                            progress_bar.progress(80)
                            update_log(f"✅ {len(companies)} entreprises enrichies")
                        except Exception as e:
                            update_log(f"⚠️ Erreur Pappers: {e}")
                    else:
                        progress_bar.progress(80)

                    progress_bar.progress(85)
                    status_text.text("💾 Export...")
                    csv_filename = f"leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    hubspot_client = HubSpotClient() if hubspot else None
                    exporter = Exporter(
                        credentials_path=os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials/service-account.json'),
                        hubspot_client=hubspot_client
                    )
                    export_results = exporter.export_all(
                        data=companies,
                        csv_filename=csv_filename,
                        sheet_id=sheet,
                        enable_hubspot=hubspot
                    )
                    st.session_state.export_files = export_results

                    if dedup:
                        contact_manager = ContactManager()
                        campagne_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                        contact_manager.import_from_sirene(companies, campaign_id=campagne_id)

                    st.session_state.results = companies
                    st.session_state.extraction_status = 'done'
                    progress_bar.progress(100)
                    status_text.text("✅ Extraction terminée!")
                    update_log("🎉 Terminé!")

                except Exception as e:
                    update_log(f"❌ Erreur: {str(e)}")
                    st.session_state.extraction_status = 'error'
                    status_text.text("❌ Erreur")
                    progress_bar.progress(0)

            run_extraction_sidebar(
                codes_ape_list=[item['code'] for item in selected_ape],
                dept_list=[item['code'] for item in selected_dept],
                eff_min=effectif_min if effectif_min > 0 else None,
                eff_max=effectif_max if effectif_max < 5000 else None,
                date_min=date_creation_min.strftime("%Y-%m-%d") if date_creation_min else None,
                max_l=max_leads,
                pappers=enable_pappers,
                dedup=enable_deduplication,
                sheet=sheet_id if enable_sheets else None,
                hubspot=enable_hubspot if hubspot_available else False
            )

    if not selected_ape and not selected_dept:
        st.warning("⚠️ Sélectionnez au moins un secteur ou département")
