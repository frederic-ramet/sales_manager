"""
Page Recherche de Leads - Extraction et enrichissement B2B.

SIREN v2: Classification ICP (A/B/C) + Segmentation + Presets campagne
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
    HubSpotClient,
    ProspectClassifier
)
from config.campaigns import CAMPAIGN_PRESETS, SEGMENTS, list_presets

# Import CompanyManager si nouveau schéma disponible
# Vérifie aussi que la table companies existe dans la base
COMPANY_SCHEMA_AVAILABLE = False
try:
    from modules.lead_scraper import CompanyManager
    import sqlite3
    from pathlib import Path
    db_path = Path(__file__).parent.parent / "data" / "leads.db"
    if db_path.exists():
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='companies'")
            if cursor.fetchone():
                COMPANY_SCHEMA_AVAILABLE = True
except ImportError:
    pass
from components import render_top_nav, hide_sidebar, render_footer

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
load_dotenv()

# Navigation
hide_sidebar()

st.title("🎯 Ajout Leads SIRENE")
st.markdown("Extraction et enrichissement de leads B2B français")

render_top_nav(current_page="pages/2_🎯_Recherche_Leads.py")

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
    # SIREN v2: Nouveaux états
    if 'selected_preset' not in st.session_state:
        st.session_state.selected_preset = None
    if 'classified_results' not in st.session_state:
        st.session_state.classified_results = None
    if 'existing_companies' not in st.session_state:
        st.session_state.existing_companies = []
    if 'new_companies' not in st.session_state:
        st.session_state.new_companies = []


def render_class_badge(prospect_class: str) -> str:
    """Retourne un badge coloré pour la classe de prospect."""
    badges = {
        'A': '🟢 A',
        'B': '🟡 B',
        'C': '⚪ C',
    }
    return badges.get(prospect_class, prospect_class or '-')


def apply_preset_filters(preset_id: str) -> Dict[str, Any]:
    """Applique les filtres d'un preset de campagne."""
    if not preset_id or preset_id not in CAMPAIGN_PRESETS:
        return {}

    preset = CAMPAIGN_PRESETS[preset_id]
    filters = preset.get('filters', {})

    return {
        'effectif_min': filters.get('effectif_min', 0),
        'effectif_max': filters.get('effectif_max', 5000),
        'ape_groups': filters.get('ape_groups', []),
        'geo': filters.get('geo', 'national'),
        'target_volume': preset.get('target_volume', 100),
        'segment': preset.get('segment', 'icp_principal'),
    }


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

# Onglets principal et documentation
tab_main, tab_doc = st.tabs(["🔧 Recherche", "📖 Documentation"])


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
    # === Section 0: Presets de campagne ===
    st.subheader("🚀 Campagnes prédéfinies")

    presets = list_presets()
    preset_options = ["⚙️ Custom (filtres manuels)"] + [
        f"{p['icon']} {p['name']}" for p in presets
    ]

    selected_preset_idx = st.selectbox(
        "Sélectionner une campagne",
        range(len(preset_options)),
        format_func=lambda x: preset_options[x],
        help="Choisissez un preset pour pré-remplir les filtres"
    )

    # Appliquer le preset sélectionné
    preset_filters = {}
    selected_segment = "ICP Principal"  # Défaut
    if selected_preset_idx > 0:
        preset_id = list(CAMPAIGN_PRESETS.keys())[selected_preset_idx - 1]
        preset = CAMPAIGN_PRESETS[preset_id]
        preset_filters = apply_preset_filters(preset_id)
        selected_segment = SEGMENTS.get(preset_filters.get('segment', 'icp_principal'), {}).get('label', 'ICP Principal')

        # Afficher les infos du preset
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Volume cible", preset.get('target_volume', 100))
        with col2:
            st.metric("Classe min", preset.get('min_class', 'B'))
        with col3:
            st.metric("Meetings attendus", f"~{preset.get('expected_meetings', 0)}")

    st.divider()

    # === Section 1: Recherche en langage naturel ===
    anthropic_available = ANTHROPIC_API_KEY and ANTHROPIC_API_KEY != "your_anthropic_api_key_here"

    if anthropic_available:
        with st.expander("🔍 Recherche en langage naturel", expanded=False):
            st.caption("Décrivez votre recherche : *\"PME dans la publicité à Paris\"*")

            col1, col2 = st.columns([5, 1])
            with col1:
                natural_query = st.text_input(
                    "Votre recherche",
                    value=st.session_state.natural_query,
                    placeholder="Ex: Agences web en Île-de-France",
                    label_visibility="collapsed"
                )
            with col2:
                parse_btn = st.button("🔍 Parser", use_container_width=True, type="primary")

            if parse_btn and natural_query:
                try:
                    with st.spinner("Analyse de votre requête..."):
                        parser = QueryParser(codes_ape=codes_ape, departements=departements)
                        filters = parser.parse(natural_query)
                        st.session_state.parsed_filters = filters
                        st.session_state.natural_query = natural_query

                    st.success(f"✅ {filters.get('interpretation', 'Filtres extraits avec succès')}")

                except Exception as e:
                    st.error(f"❌ Erreur: {str(e)}")

    # === Section 2: Filtres de recherche ===
    st.subheader("⚙️ Filtres de recherche")

    # Utiliser les filtres parsés si disponibles
    parsed = st.session_state.get('parsed_filters') or {}

    # Ligne 1: Secteurs et Départements
    col1, col2 = st.columns(2)

    with col1:
        # Pré-sélectionner les secteurs APE depuis le parsing
        default_ape = []
        if 'codes_ape' in parsed and parsed['codes_ape']:
            for code in parsed['codes_ape']:
                matching = [item for item in codes_ape if item['code'] == code]
                if matching:
                    default_ape.append(matching[0])

        selected_ape = st.multiselect(
            "Secteurs d'activité (APE)",
            options=codes_ape,
            default=default_ape,
            format_func=format_option,
            help="Sélectionnez un ou plusieurs codes APE"
        )

    with col2:
        # Pré-sélectionner les départements depuis le parsing
        default_dept = []
        if 'departements' in parsed and parsed['departements']:
            for code in parsed['departements']:
                matching = [item for item in departements if item['code'] == code]
                if matching:
                    default_dept.append(matching[0])

        selected_dept = st.multiselect(
            "Départements",
            options=departements,
            default=default_dept,
            format_func=format_option,
            help="Sélectionnez un ou plusieurs départements"
        )

    # Ligne 2: Effectifs, Date, Max leads
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        effectif_min = st.number_input(
            "Effectif min",
            min_value=0,
            max_value=5000,
            value=preset_filters.get('effectif_min', parsed.get('effectif_min', 50)),
            step=1
        )

    with col2:
        effectif_max = st.number_input(
            "Effectif max",
            min_value=0,
            max_value=5000,
            value=preset_filters.get('effectif_max', parsed.get('effectif_max', 1000)),
            step=1
        )

    with col3:
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
            help="Filtrer par date de création"
        )

    with col4:
        max_leads = st.number_input(
            "Max leads",
            min_value=1,
            max_value=MAX_RESULTS,
            value=preset_filters.get('target_volume', 50),
            step=10,
            help=f"Maximum {MAX_RESULTS}"
        )

    # Ligne 3: Segment à assigner
    col1, col2 = st.columns(2)
    with col1:
        segment_options = [s['label'] for s in SEGMENTS.values()]
        selected_segment = st.selectbox(
            "Segment à assigner",
            segment_options,
            index=segment_options.index(selected_segment) if selected_segment in segment_options else 0,
            help="Segment HubSpot pour les entreprises importées"
        )

    # === Section 3: Options (expander) ===
    with st.expander("⚙️ Options d'enrichissement et export", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**Enrichissement**")
            pappers_available = PAPPERS_API_KEY and PAPPERS_API_KEY != "your_pappers_api_key_here"
            enable_pappers = st.checkbox(
                "Enrichir avec Pappers",
                value=pappers_available,
                disabled=not pappers_available,
                help="Dirigeants, email, téléphone, CA"
            )
            if not pappers_available:
                st.caption("⚠️ PAPPERS_API_KEY non configurée")

        with col2:
            st.markdown("**Déduplication**")
            enable_deduplication = st.checkbox(
                "Éviter les doublons",
                value=st.session_state.get('enable_deduplication', True),
                help="Filtre les entreprises déjà extraites"
            )
            st.session_state.enable_deduplication = enable_deduplication

            if enable_deduplication:
                try:
                    manager = ContactManager()
                    stats = manager.get_stats()
                    if stats['total_contacts'] > 0:
                        st.caption(f"📊 {stats['total_contacts']} contacts en base")
                except:
                    pass

        with col3:
            st.markdown("**Export**")
            enable_sheets = st.checkbox("Google Sheets", value=False)
            sheet_id = None
            if enable_sheets:
                sheet_id = st.text_input(
                    "ID du Sheet",
                    value=DEFAULT_SHEET_ID or "",
                    label_visibility="collapsed"
                )

            hubspot_available = HUBSPOT_API_KEY and HUBSPOT_API_KEY != "your_hubspot_api_key_here"
            enable_hubspot = st.checkbox(
                "HubSpot",
                value=False,
                disabled=not hubspot_available,
                help="Envoyer vers HubSpot CRM"
            )

    # === Bouton d'extraction ===
    st.divider()

    extraction_disabled = (
        st.session_state.get('extraction_status') == 'running' or
        (not selected_ape and not selected_dept)
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        launch_btn = st.button(
            "🚀 Lancer l'extraction",
            disabled=extraction_disabled,
            use_container_width=True,
            type="primary"
        )

    if not selected_ape and not selected_dept:
        st.warning("⚠️ Sélectionnez au moins un secteur ou département")

    # === Exécution de l'extraction ===
    if launch_btn:
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

            codes_ape_list = [item['code'] for item in selected_ape]
            dept_list = [item['code'] for item in selected_dept]

            with SireneClient() as sirene_client:
                companies = sirene_client.search_all(
                    codes_ape=codes_ape_list if codes_ape_list else None,
                    departements=dept_list if dept_list else None,
                    effectif_min=effectif_min if effectif_min > 0 else None,
                    effectif_max=effectif_max if effectif_max < 5000 else None,
                    date_creation_min=date_creation_min.strftime("%Y-%m-%d") if date_creation_min else None,
                    max_results=max_leads
                )

            progress_bar.progress(25)
            update_log(f"✅ {len(companies)} entreprises trouvées")

            if not companies:
                update_log("⚠️ Aucune entreprise trouvée")
                st.session_state.extraction_status = 'done'
                status_text.text("Aucun résultat")
                progress_bar.progress(100)
            else:
                # Classification ICP (A/B/C)
                progress_bar.progress(30)
                status_text.text("📊 Classification ICP...")
                update_log("📊 Classification des prospects (A/B/C)...")

                classifier = ProspectClassifier()
                companies = classifier.classify_batch(companies)

                # Stats de classification
                stats = classifier.get_classification_stats(companies)
                update_log(f"   🟢 A: {stats['by_class']['A']} | 🟡 B: {stats['by_class']['B']} | ⚪ C: {stats['by_class']['C']}")
                update_log(f"   📈 Contacts attendus: ~{stats['expected_contacts']['total']}")

                # Déduplication SQLite - séparer nouvelles vs existantes
                if enable_deduplication and COMPANY_SCHEMA_AVAILABLE:
                    progress_bar.progress(35)
                    status_text.text("🔍 Comparaison avec la base...")
                    update_log("🔍 Comparaison avec la base existante...")

                    company_manager = CompanyManager()
                    new_companies = []
                    existing_companies = []

                    for company in companies:
                        siren = company.get('siren')
                        if siren:
                            existing = company_manager.find_by_siren(siren)
                            if existing:
                                # Ajouter les infos de l'entreprise existante
                                company['_existing'] = True
                                company['_existing_id'] = existing['id']
                                company['_existing_segment'] = existing.get('segment')
                                existing_companies.append(company)
                            else:
                                company['_existing'] = False
                                new_companies.append(company)
                        else:
                            company['_existing'] = False
                            new_companies.append(company)

                    st.session_state.new_companies = new_companies
                    st.session_state.existing_companies = existing_companies

                    update_log(f"   ✨ {len(new_companies)} nouvelles | 📋 {len(existing_companies)} déjà en base")

                    # Continuer avec les nouvelles uniquement pour l'enrichissement
                    companies = new_companies

                    if not companies and not existing_companies:
                        update_log("⚠️ Aucune entreprise trouvée")
                        st.session_state.extraction_status = 'done'
                        status_text.text("Aucun résultat")
                        progress_bar.progress(100)
                elif enable_deduplication:
                    # Ancien schéma
                    progress_bar.progress(35)
                    status_text.text("🔍 Filtrage des doublons...")
                    update_log("🔍 Vérification des doublons (ancien schéma)...")

                    contact_manager = ContactManager()
                    companies, num_duplicates = contact_manager.filter_duplicates(companies)
                    st.session_state.new_companies = companies
                    st.session_state.existing_companies = []

                    if num_duplicates > 0:
                        update_log(f"⚠️ {num_duplicates} doublons filtrés")

                    if not companies:
                        update_log("⚠️ Toutes les entreprises déjà extraites")
                        st.session_state.extraction_status = 'done'
                        status_text.text("Aucun nouveau lead")
                        progress_bar.progress(100)
                else:
                    # Pas de déduplication
                    st.session_state.new_companies = companies
                    st.session_state.existing_companies = []

                if companies:
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

                                companies = enricher.enrich_batch(companies, progress_callback=progress_callback)

                            progress_bar.progress(80)
                            update_log(f"✅ {len(companies)} entreprises enrichies")

                        except Exception as e:
                            update_log(f"⚠️ Erreur Pappers: {e}")
                            progress_bar.progress(80)
                    else:
                        progress_bar.progress(80)
                        update_log("ℹ️ Enrichissement désactivé")

                    # Export
                    progress_bar.progress(85)
                    status_text.text("💾 Export...")
                    update_log("💾 Export des données...")

                    csv_filename = f"leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

                    hubspot_client = None
                    if enable_hubspot and hubspot_available:
                        hubspot_client = HubSpotClient()

                    exporter = Exporter(
                        credentials_path=GOOGLE_CREDENTIALS_PATH,
                        hubspot_client=hubspot_client
                    )
                    export_results = exporter.export_all(
                        data=companies,
                        csv_filename=csv_filename,
                        sheet_id=sheet_id if enable_sheets else None,
                        enable_hubspot=enable_hubspot and hubspot_available
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

                            # Nouveau schéma: créer companies + contacts séparément
                            if COMPANY_SCHEMA_AVAILABLE:
                                company_manager = CompanyManager()
                                added_companies = 0
                                added_contacts = 0

                                for company_data in companies:
                                    # Créer ou trouver l'entreprise
                                    company_id, is_new = company_manager.find_or_create_company(company_data)
                                    if is_new:
                                        added_companies += 1

                                    # Créer le contact associé (si dirigeant présent)
                                    if company_data.get('dirigeant_nom') or company_data.get('email'):
                                        contact_data = {
                                            'firstname': company_data.get('dirigeant_prenom', ''),
                                            'lastname': company_data.get('dirigeant_nom', ''),
                                            'email': company_data.get('email', ''),
                                            'phone': company_data.get('telephone', ''),
                                            'job_title': company_data.get('dirigeant_fonction', ''),
                                            'campaign_id': campagne_id,
                                        }
                                        contact_manager.add_contact_with_company(
                                            data=contact_data,
                                            source='sirene',
                                            company_id=company_id
                                        )
                                        added_contacts += 1

                                update_log(f"✅ {added_companies} entreprises, {added_contacts} contacts ajoutés")
                            else:
                                # Ancien schéma: unified_contacts
                                added, _ = contact_manager.import_from_sirene(companies, campaign_id=campagne_id)
                                update_log(f"✅ {added} leads ajoutés")
                        except Exception as e:
                            update_log(f"⚠️ Erreur enregistrement: {e}")

                    st.session_state.results = companies
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

    # === Affichage des résultats ===
    if st.session_state.extraction_status == 'done' and (st.session_state.new_companies or st.session_state.existing_companies):
        new_companies = st.session_state.new_companies
        existing_companies = st.session_state.existing_companies
        export_files = st.session_state.export_files

        st.divider()
        st.subheader("📊 Résultats")

        # Métriques globales avec classification
        all_companies = new_companies + existing_companies
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total", len(all_companies))
        with col2:
            count_a = sum(1 for c in all_companies if c.get('prospect_class') == 'A')
            st.metric("🟢 Classe A", count_a)
        with col3:
            count_b = sum(1 for c in all_companies if c.get('prospect_class') == 'B')
            st.metric("🟡 Classe B", count_b)
        with col4:
            st.metric("✨ Nouvelles", len(new_companies))
        with col5:
            st.metric("📋 Déjà en base", len(existing_companies))

        # 2 Onglets: Nouvelles / Déjà en base
        tab_new, tab_existing = st.tabs([
            f"✨ Nouvelles ({len(new_companies)})",
            f"📋 Déjà en base ({len(existing_companies)})"
        ])

        with tab_new:
            if new_companies:
                st.caption(f"Entreprises à importer dans le segment: **{selected_segment}**")

                # Créer DataFrame avec colonnes appropriées
                df_new = pd.DataFrame(new_companies)

                # Ajouter colonne badge
                if 'prospect_class' in df_new.columns:
                    df_new['Classe'] = df_new['prospect_class'].apply(render_class_badge)

                display_cols = ['Classe', 'siren', 'denomination', 'ville', 'code_ape']
                if 'prospect_class_signals' in df_new.columns:
                    df_new['Signaux'] = df_new['prospect_class_signals'].apply(
                        lambda x: ', '.join(x) if isinstance(x, list) else str(x) if x else ''
                    )
                    display_cols.append('Signaux')

                display_cols = [c for c in display_cols if c in df_new.columns]

                st.dataframe(
                    df_new[display_cols],
                    use_container_width=True,
                    hide_index=True
                )

                # Bouton d'import
                if COMPANY_SCHEMA_AVAILABLE:
                    st.divider()
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.info(f"📥 Prêt à importer **{len(new_companies)}** entreprises dans le segment **{selected_segment}**")
                    with col2:
                        if st.button("✅ Importer tout", type="primary", use_container_width=True):
                            try:
                                company_manager = CompanyManager()
                                segment_id = [k for k, v in SEGMENTS.items() if v['label'] == selected_segment][0]
                                imported = 0
                                for company in new_companies:
                                    company_id = company_manager.create_company({
                                        **company,
                                        'segment': selected_segment,
                                        'source': 'sirene',
                                    })
                                    # Classifier
                                    company_manager.classify_company(company_id)
                                    imported += 1
                                st.success(f"✅ {imported} entreprises importées!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Erreur: {e}")
            else:
                st.info("Aucune nouvelle entreprise trouvée")

        with tab_existing:
            if existing_companies:
                st.caption("Ces entreprises sont déjà dans votre base")

                df_existing = pd.DataFrame(existing_companies)

                if 'prospect_class' in df_existing.columns:
                    df_existing['Classe'] = df_existing['prospect_class'].apply(render_class_badge)

                display_cols = ['Classe', 'siren', 'denomination', 'ville', '_existing_segment']
                df_existing = df_existing.rename(columns={'_existing_segment': 'Segment actuel'})
                display_cols = [c.replace('_existing_segment', 'Segment actuel') for c in display_cols]
                display_cols = [c for c in display_cols if c in df_existing.columns]

                st.dataframe(
                    df_existing[display_cols],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("Aucune entreprise existante correspondante")

        # Téléchargements
        st.divider()
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

# Footer
render_footer()
