"""
Page Import Unifiée - Import GetSales et CSV avec déduplication.

Permet l'import de contacts depuis:
- GetSales (leads LinkedIn validés)
- Fichiers CSV (avec détection doublons et workflow GetSales-like)
"""
import os
import logging
from datetime import datetime

import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from components import render_top_nav, hide_sidebar, render_footer
from modules.lead_scraper.hubspot_client import HubSpotClient
from modules.lead_scraper.scoring import ProspectClassifier

# Charger les variables d'environnement
load_dotenv()

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Navigation
hide_sidebar()

st.title("📤 Import")
st.markdown("Import de contacts depuis GetSales ou fichiers CSV")

render_top_nav(current_page="pages/5_📤_Import.py")

# Initialisation des managers
from modules.lead_scraper import CompanyManager, ContactManager, CSVImporter

company_manager = CompanyManager()
contact_manager = ContactManager()

# Onglets principaux
tab_getsales, tab_csv = st.tabs(["🔗 Import GetSales", "📄 Import CSV"])


# =============================================================================
# TAB: IMPORT GETSALES (avec sync complète)
# =============================================================================

with tab_getsales:
    st.header("Import depuis GetSales")

    GETSALES_API_KEY = os.getenv('GETSALES_API_KEY')
    HUBSPOT_API_KEY = os.getenv('HUBSPOT_API_KEY')

    if not GETSALES_API_KEY:
        st.error("❌ GETSALES_API_KEY non configurée dans .env")
        st.info("""
        Pour configurer GetSales:
        1. Créez un fichier `.env` à la racine du projet
        2. Ajoutez: `GETSALES_API_KEY=votre_clé_api`
        """)
    else:
        # Imports GetSales
        from modules.getsales import (
            GetSalesClient,
            GetSalesDB,
            GetSalesSyncService,
        )

        # Init HubSpot si dispo
        hubspot_client = None
        if HUBSPOT_API_KEY:
            try:
                hubspot_client = HubSpotClient()
            except Exception as e:
                st.warning(f"⚠️ Erreur init HubSpot: {e}")

        # Services
        @st.cache_resource
        def get_getsales_db():
            return GetSalesDB()

        @st.cache_resource
        def get_getsales_client():
            return GetSalesClient()

        gs_db = get_getsales_db()
        gs_client = get_getsales_client()

        sync_service = None
        if hubspot_client:
            sync_service = GetSalesSyncService(gs_client, hubspot_client, gs_db)

        # Sous-onglets GetSales
        gs_tab_sync, gs_tab_queue = st.tabs(["🔄 Synchronisation", "📋 File de validation"])

        # ========== SOUS-TAB: SYNCHRONISATION ==========
        with gs_tab_sync:
            col1, col2 = st.columns([2, 1])

            with col1:
                last_sync = gs_db.get_last_sync()
                if last_sync:
                    status_emoji = "✅" if last_sync.status == 'completed' else "❌" if last_sync.status == 'failed' else "⏳"
                    st.info(f"""
                    **Dernière sync**: {last_sync.sync_date or "N/A"}
                    **Statut**: {status_emoji} {last_sync.status}
                    **Leads récupérés**: {last_sync.leads_fetched}
                    """)
                else:
                    st.warning("Aucune synchronisation effectuée")

            with col2:
                with st.expander("⚙️ Options"):
                    sync_limit = st.number_input("Limite de leads", min_value=10, max_value=500, value=100, key="gs_sync_limit")
                    fetch_messages = st.checkbox("Récupérer messages", value=True, key="gs_fetch_msgs")

                sync_disabled = sync_service is None
                if st.button("🔄 Sync maintenant", type="primary", use_container_width=True, disabled=sync_disabled):
                    with st.spinner("Synchronisation..."):
                        try:
                            result = sync_service.sync_leads(limit=sync_limit, fetch_messages=fetch_messages)
                            st.success(f"✅ {result['leads_fetched']} leads | {result['leads_new']} nouveaux")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ {e}")

                if sync_disabled:
                    st.caption("⚠️ Configurez HubSpot pour activer")

            # Test connexion
            with st.expander("🔌 Test API"):
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Tester GetSales", key="test_gs"):
                        success, msg = gs_client.test_connection()
                        st.success(f"✅ {msg}") if success else st.error(f"❌ {msg}")
                with col2:
                    if hubspot_client and st.button("Tester HubSpot", key="test_hs_gs"):
                        success, msg = hubspot_client.test_connection()
                        st.success(f"✅ {msg}") if success else st.error(f"❌ {msg}")

        # ========== SOUS-TAB: FILE DE VALIDATION ==========
        with gs_tab_queue:
            # Stats
            stats = gs_db.get_pending_stats()
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("En attente", stats['pending'])
            with col2:
                st.metric("Validés", stats['approved'])
            with col3:
                st.metric("Rejetés", stats['rejected'])
            with col4:
                st.metric("Doublons", stats['with_duplicates'])

            # Filtres
            col1, col2 = st.columns(2)
            with col1:
                filter_status = st.selectbox("Statut", ["En attente", "Validés", "Rejetés", "Tous"], key="gs_filter_status")
            with col2:
                filter_dup = st.selectbox("Doublons", ["Tous", "Avec doublons", "Sans doublons"], key="gs_filter_dup")

            status_map = {"Tous": None, "En attente": "pending", "Validés": "approved", "Rejetés": "rejected"}
            dup_map = {"Tous": None, "Avec doublons": "with_duplicates", "Sans doublons": "no_duplicates"}

            pending_leads = gs_db.get_pending_leads(
                status=status_map[filter_status],
                duplicate_status=dup_map[filter_dup],
                limit=50
            )

            def confidence_badge(conf: str) -> str:
                badges = {'exact': '🔴 EXACT', 'high': '🟠 HIGH', 'medium': '🟡 MEDIUM', 'low': '⚪ LOW'}
                return badges.get(conf, conf)

            if not pending_leads:
                st.info("Aucun lead correspondant aux filtres")
            else:
                st.markdown(f"**{len(pending_leads)} leads**")

                for lead in pending_leads:
                    lead_data = lead.getsales_data
                    name = f"{lead_data.get('first_name', '')} {lead_data.get('last_name', '')}".strip()
                    company = lead_data.get('company_name', 'N/A')

                    status_badge = "✅" if lead.validation_status == 'approved' else "❌" if lead.validation_status == 'rejected' else "⏳"
                    total_matches = len(lead.hubspot_matches or []) + len(lead.local_matches or [])
                    dup_badge = f"⚠️ {total_matches}" if total_matches > 0 else ""

                    with st.expander(f"{status_badge} {name} - {company} {dup_badge}", expanded=(lead.validation_status == 'pending')):
                        col1, col2 = st.columns(2)

                        with col1:
                            st.markdown("**Informations GetSales**")
                            st.write(f"👤 {lead_data.get('first_name', '')} {lead_data.get('last_name', '')}")
                            st.write(f"📧 {lead_data.get('email', 'N/A')}")
                            st.write(f"🏢 {company}")
                            st.write(f"💼 {lead_data.get('position', 'N/A')}")
                            linkedin = lead_data.get('linkedin', '')
                            if linkedin:
                                url = linkedin if linkedin.startswith('http') else f"https://linkedin.com/in/{linkedin}"
                                st.write(f"🔗 [LinkedIn]({url})")

                        with col2:
                            st.markdown("**Interactions**")
                            messages = lead_data.get('_messages', [])
                            if messages:
                                outbox = len([m for m in messages if m.get('type') == 'outbox'])
                                inbox = len([m for m in messages if m.get('type') == 'inbox'])
                                st.write(f"📨 Envoyés: {outbox} | 📥 Réponses: {inbox}")

                        # Doublons locaux
                        if lead.local_matches:
                            st.divider()
                            st.markdown(f"**🗃️ Doublons Base** ({len(lead.local_matches)})")
                            for match in lead.local_matches:
                                match_name = f"{match.get('firstname', '')} {match.get('lastname', '')}".strip() or "N/A"
                                st.write(f"{confidence_badge(match.get('confidence', 'low'))} {match_name} | {match.get('company_name', 'N/A')}")

                        # Doublons HubSpot
                        if lead.hubspot_matches:
                            st.divider()
                            st.markdown(f"**🟠 Doublons HubSpot** ({len(lead.hubspot_matches)})")
                            for match in lead.hubspot_matches:
                                contact = match.get('contact_data', {})
                                st.write(f"{confidence_badge(match.get('confidence', 'medium'))} {contact.get('firstname', '')} {contact.get('lastname', '')} | {contact.get('email', 'N/A')}")

                        # Actions (si pending)
                        if lead.validation_status == 'pending' and sync_service:
                            st.divider()
                            col1, col2, col3 = st.columns(3)

                            with col1:
                                if st.button("✅ Créer", key=f"gs_create_{lead.id}", use_container_width=True):
                                    try:
                                        result = sync_service.validate_lead(pending_lead_id=lead.id, action='create_new')
                                        st.success(result['message'])
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erreur: {e}")

                            with col2:
                                if lead.hubspot_matches:
                                    if st.button("🔀 Merger", key=f"gs_merge_{lead.id}", use_container_width=True):
                                        hs_match = lead.hubspot_matches[0]
                                        merge_data = {'hubspot_contact_id': hs_match['hubspot_contact_id'], 'fields': {}}
                                        try:
                                            result = sync_service.validate_lead(pending_lead_id=lead.id, action='merge', merge_data=merge_data)
                                            st.success(result['message'])
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Erreur: {e}")

                            with col3:
                                if st.button("❌ Rejeter", key=f"gs_reject_{lead.id}", use_container_width=True):
                                    try:
                                        result = sync_service.validate_lead(pending_lead_id=lead.id, action='reject')
                                        st.success(result['message'])
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erreur: {e}")

                        elif lead.validation_status != 'pending':
                            st.caption(f"{'✅ Validé' if lead.validation_status == 'approved' else '❌ Rejeté'} le {lead.validated_at or 'N/A'}")

            st.divider()
            if st.button("🔄 Rafraîchir", key="gs_refresh", use_container_width=True):
                st.rerun()


# =============================================================================
# TAB: IMPORT CSV
# =============================================================================

with tab_csv:
    st.header("Import depuis fichier CSV")

    # Initialiser les états de session
    if 'csv_importer' not in st.session_state:
        st.session_state.csv_importer = None
    if 'csv_analysis' not in st.session_state:
        st.session_state.csv_analysis = None
    if 'csv_step' not in st.session_state:
        st.session_state.csv_step = 1

    # =========================================================================
    # ÉTAPE 1: UPLOAD & MAPPING
    # =========================================================================

    st.subheader("Étape 1: Upload & Mapping")

    uploaded_file = st.file_uploader(
        "Glissez votre fichier CSV ici",
        type=['csv'],
        help="Fichiers CSV avec séparateur , ; ou tabulation"
    )

    if uploaded_file:
        # Parser le fichier
        if st.session_state.csv_importer is None or st.session_state.get('csv_filename') != uploaded_file.name:
            content = uploaded_file.read()
            importer = CSVImporter(content, uploaded_file.name)
            importer.parse()
            importer.auto_map_columns()
            st.session_state.csv_importer = importer
            st.session_state.csv_filename = uploaded_file.name
            st.session_state.csv_analysis = None
            st.session_state.csv_step = 1

        importer = st.session_state.csv_importer
        stats = importer.get_stats()

        # Afficher les stats du fichier
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Lignes", stats['rows'])
        with col2:
            st.metric("Colonnes mappées", f"{stats['mapped_columns']}/{stats['columns']}")
        with col3:
            st.metric("Encodage", stats['encoding'])

        # Afficher le mapping
        with st.expander("🔗 Mapping des colonnes", expanded=True):
            mapping = importer.mapping.copy()

            # Créer 2 colonnes pour afficher le mapping
            col1, col2 = st.columns(2)

            target_fields = list(CSVImporter.TARGET_COLUMNS.keys())
            csv_columns = ['(non mappé)'] + list(importer.df.columns)

            for i, field in enumerate(target_fields):
                with col1 if i % 2 == 0 else col2:
                    current_value = mapping.get(field, None)
                    current_index = csv_columns.index(current_value) if current_value in csv_columns else 0

                    selected = st.selectbox(
                        field,
                        csv_columns,
                        index=current_index,
                        key=f"map_{field}"
                    )

                    if selected != '(non mappé)':
                        mapping[field] = selected
                    elif field in mapping:
                        del mapping[field]

            importer.mapping = mapping

        # Colonnes non mappées
        unmapped = importer.get_unmapped_columns()
        if unmapped:
            st.info(f"📋 Colonnes ignorées: {', '.join(unmapped)}")
            st.caption("Ces colonnes seront automatiquement ajoutées aux notes si elles contiennent des métadonnées (date envoi, commentaire, etc.)")

        # Aperçu des données
        with st.expander("👁️ Aperçu des données"):
            preview = importer.get_preview(5)
            st.dataframe(preview, use_container_width=True)

        # Validation
        errors = importer.validate()
        if errors:
            for err in errors:
                st.warning(f"⚠️ {err}")

        st.divider()

        # =========================================================================
        # ÉTAPE 2: ANALYSE DOUBLONS
        # =========================================================================

        st.subheader("Étape 2: Analyse des doublons")

        if st.button("🔍 Analyser les doublons", type="primary", use_container_width=True):
            with st.spinner("Analyse en cours..."):
                analysis = importer.analyze_duplicates(company_manager, contact_manager)
                st.session_state.csv_analysis = analysis
                st.session_state.csv_step = 2

        if st.session_state.csv_analysis:
            analysis = st.session_state.csv_analysis
            analysis_stats = analysis['stats']

            # Stats
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total", analysis_stats['total'])
            with col2:
                st.metric("Nouvelles", analysis_stats['new_companies'], help="Entreprises à créer")
            with col3:
                st.metric("Existantes", analysis_stats['existing_companies'], help="Entreprises déjà en base")
            with col4:
                st.metric("Contacts existants", analysis_stats['existing_contacts'])

            # Onglets Nouvelles / Existantes
            tab_new, tab_existing = st.tabs([
                f"✨ Nouvelles ({analysis_stats['new_companies']})",
                f"📋 Déjà en base ({analysis_stats['existing_companies']})"
            ])

            with tab_new:
                new_rows = [r for r in analysis['rows'] if r['company_match'] is None]

                if not new_rows:
                    st.info("Aucune nouvelle entreprise à importer")
                else:
                    for row in new_rows:
                        row_data = row['row_data']
                        company_name = row_data.get('company_name', 'N/A')
                        contact_name = f"{row_data.get('firstname', '')} {row_data.get('lastname', '')}".strip() or 'N/A'
                        email = row_data.get('email', '')

                        with st.container():
                            col1, col2, col3 = st.columns([0.5, 3, 2])

                            with col1:
                                selected = st.checkbox(
                                    "Sélectionner",
                                    value=row.get('selected', True),
                                    key=f"select_new_{row['row_index']}",
                                    label_visibility="collapsed"
                                )
                                # Mettre à jour la sélection
                                for r in analysis['rows']:
                                    if r['row_index'] == row['row_index']:
                                        r['selected'] = selected

                            with col2:
                                st.markdown(f"**🏢 {company_name}**")
                                st.caption(f"👤 {contact_name} | 📧 {email}")

                            with col3:
                                st.markdown("✅ Créer entreprise + contact")

                            st.divider()

            with tab_existing:
                existing_rows = [r for r in analysis['rows'] if r['company_match'] is not None]

                if not existing_rows:
                    st.info("Aucune entreprise existante trouvée")
                else:
                    for row in existing_rows:
                        row_data = row['row_data']
                        company_name = row_data.get('company_name', 'N/A')
                        contact_name = f"{row_data.get('firstname', '')} {row_data.get('lastname', '')}".strip() or 'N/A'
                        email = row_data.get('email', '')

                        match_company = row['company_match']
                        match_type = row['company_match_type']
                        match_score = row['company_match_score']

                        # Badge de confiance
                        if match_score >= 95:
                            badge = "🟢"
                        elif match_score >= 80:
                            badge = "🟡"
                        else:
                            badge = "🟠"

                        with st.container():
                            col1, col2, col3 = st.columns([0.5, 3, 2])

                            with col1:
                                selected = st.checkbox(
                                    "Sélectionner",
                                    value=row.get('selected', True),
                                    key=f"select_existing_{row['row_index']}",
                                    label_visibility="collapsed"
                                )
                                for r in analysis['rows']:
                                    if r['row_index'] == row['row_index']:
                                        r['selected'] = selected

                            with col2:
                                st.markdown(f"**🏢 {company_name}**")
                                st.caption(f"👤 {contact_name} | 📧 {email}")
                                st.caption(f"{badge} Match: **{match_company.get('company_name')}** ({match_type}, {match_score}%)")

                                # Afficher contacts existants
                                existing_contacts = contact_manager.get_contacts_by_company(
                                    match_company.get('id'), limit=5
                                )
                                if existing_contacts:
                                    st.caption(f"📋 {len(existing_contacts)} contact(s) existant(s)")

                            with col3:
                                # Proposer "Mettre à jour" si contact existant trouvé
                                has_contact_match = row.get('contact_match') is not None
                                if has_contact_match:
                                    contact_match = row['contact_match']
                                    st.caption(f"👤 Contact existant: {contact_match.get('firstname', '')} {contact_match.get('lastname', '')}")
                                    options = ["Mettre à jour", "Créer doublon", "Ignorer"]
                                    default_idx = 0  # Default to "Mettre à jour"
                                else:
                                    options = ["Lier à l'existant", "Créer doublon", "Ignorer"]
                                    default_idx = 0  # Default to "Lier à l'existant"

                                action = st.selectbox(
                                    "Action",
                                    options,
                                    index=default_idx,
                                    key=f"action_{row['row_index']}",
                                    label_visibility="collapsed"
                                )
                                # Mettre à jour l'action
                                action_map = {
                                    "Lier à l'existant": "link",
                                    "Mettre à jour": "update",
                                    "Créer doublon": "create",
                                    "Ignorer": "ignore"
                                }
                                for r in analysis['rows']:
                                    if r['row_index'] == row['row_index']:
                                        r['action'] = action_map[action]

                            st.divider()

            st.session_state.csv_analysis = analysis

            st.divider()

            # =========================================================================
            # ÉTAPE 3: OPTIONS & IMPORT
            # =========================================================================

            st.subheader("Étape 3: Options & Import")

            col1, col2 = st.columns(2)

            with col1:
                segment = st.selectbox(
                    "Segment",
                    ["ICP Principal", "ICP Opportuniste", "Test", "Custom"],
                    index=0
                )

            with col2:
                source_name = st.text_input(
                    "Source (traçabilité)",
                    value=f"csv_import_{datetime.now().strftime('%Y%m%d')}"
                )

            sync_hubspot = st.checkbox(
                "☁️ Synchroniser vers HubSpot après import",
                value=False,
                disabled=not os.getenv('HUBSPOT_API_KEY')
            )

            if not os.getenv('HUBSPOT_API_KEY'):
                st.caption("⚠️ HubSpot non configuré")

            # Résumé
            selected_rows = [r for r in analysis['rows'] if r.get('selected', True) and r.get('action') != 'ignore']
            new_selected = len([r for r in selected_rows if r['company_match'] is None])
            link_selected = len([r for r in selected_rows if r['company_match'] is not None and r['action'] == 'link'])
            create_dupe = len([r for r in selected_rows if r['company_match'] is not None and r['action'] == 'create'])

            st.info(f"""
            **Résumé de l'import:**
            - {new_selected} nouvelles entreprises à créer
            - {link_selected} contacts à lier à entreprises existantes
            - {create_dupe} doublons à créer volontairement
            - **{len(selected_rows)} contacts au total**
            """)

            # Bouton import
            if st.button("📥 Importer les contacts", type="primary", use_container_width=True, disabled=len(selected_rows) == 0):
                progress = st.progress(0)
                status = st.empty()

                imported = 0
                hubspot_synced = 0
                companies_classified = 0
                errors = []

                # Initialiser HubSpot client si sync demandé
                hubspot_client = None
                if sync_hubspot and os.getenv('HUBSPOT_API_KEY'):
                    hubspot_client = HubSpotClient()

                # Classificateur pour les nouvelles entreprises
                classifier = ProspectClassifier()

                for i, row in enumerate(selected_rows):
                    progress.progress((i + 1) / len(selected_rows))
                    row_data = row['row_data']

                    try:
                        if row['action'] == 'ignore':
                            continue

                        # Déterminer le company_id local
                        if row['action'] == 'update' and row.get('contact_match'):
                            # Mise à jour d'un contact existant - utiliser son entreprise
                            existing_contact = row['contact_match']
                            company_id = existing_contact.get('company_id')
                            company_data = row.get('company_match') or {}
                        elif row['company_match'] and row['action'] in ('link', 'update'):
                            # Lier à l'entreprise existante
                            company_id = row['company_match']['id']
                            company_data = row['company_match']
                        else:
                            # Créer nouvelle entreprise
                            company_id = company_manager.create_company({
                                'company_name': row_data.get('company_name'),
                                'siren': row_data.get('siren'),
                                'website': row_data.get('website'),
                                'city': row_data.get('city'),
                                'postal_code': row_data.get('postal_code'),
                                'ape_code': row_data.get('ape_code'),
                                'segment': segment,
                                'source': source_name,
                            })
                            company_data = {
                                'company_name': row_data.get('company_name'),
                                'siren': row_data.get('siren'),
                                'website': row_data.get('website'),
                                'city': row_data.get('city'),
                            }

                            # Classifier la nouvelle entreprise (A/B/C)
                            try:
                                classification = classifier.classify({
                                    'ape_code': row_data.get('ape_code'),
                                    'postal_code': row_data.get('postal_code'),
                                    'employee_range': row_data.get('employee_range'),
                                    'revenue_range': row_data.get('revenue_range'),
                                })
                                company_manager.update_company(company_id, {
                                    'prospect_class': classification['prospect_class'],
                                    'prospect_class_points': classification['points'],
                                    'prospect_class_signals': ', '.join(classification['signals']) if classification['signals'] else None,
                                })
                                companies_classified += 1
                            except Exception as class_error:
                                logger.warning(f"Erreur classification {company_data.get('company_name')}: {class_error}")

                        # Créer OU mettre à jour le contact
                        if row['action'] == 'update' and row.get('contact_match'):
                            # Mettre à jour le contact existant
                            existing_contact = row['contact_match']
                            contact_uuid = existing_contact.get('uuid') or existing_contact.get('id')

                            update_data = {}
                            # Ne mettre à jour que les champs avec des valeurs
                            if row_data.get('phone') and not existing_contact.get('phone'):
                                update_data['phone'] = row_data.get('phone')
                            if row_data.get('job_title') and not existing_contact.get('job_title'):
                                update_data['job_title'] = row_data.get('job_title')
                            if row_data.get('linkedin_url') and not existing_contact.get('linkedin_url'):
                                update_data['linkedin_url'] = row_data.get('linkedin_url')
                            if row_data.get('notes'):
                                # Ajouter aux notes existantes
                                existing_notes = existing_contact.get('notes', '') or ''
                                new_notes = row_data.get('notes', '')
                                update_data['notes'] = f"{existing_notes}\n[Import {source_name}] {new_notes}".strip()

                            if update_data:
                                contact_manager.update_contact(contact_uuid, update_data)

                            imported += 1
                            status.text(f"Mis à jour: {row_data.get('company_name', 'N/A')}")

                        else:
                            # Créer nouveau contact
                            contact_uuid = contact_manager.add_contact_with_company(
                                data={
                                    'firstname': row_data.get('firstname'),
                                    'lastname': row_data.get('lastname'),
                                    'email': row_data.get('email'),
                                    'phone': row_data.get('phone'),
                                    'job_title': row_data.get('job_title'),
                                    'linkedin_url': row_data.get('linkedin_url'),
                                    'notes': row_data.get('notes'),
                                    'last_interaction_at': row_data.get('contact_date'),
                                },
                                source=source_name,
                                company_id=company_id
                            )

                            imported += 1
                            status.text(f"Importé: {row_data.get('company_name', 'N/A')}")

                        # ====================================================
                        # SYNC HUBSPOT (comme GetSales)
                        # ====================================================
                        if hubspot_client:
                            try:
                                # 1. Créer ou récupérer l'entreprise HubSpot
                                domain = None
                                email = row_data.get('email')
                                if email and '@' in email:
                                    domain = email.split('@')[1]

                                hs_company = hubspot_client.get_or_create_company(
                                    name=company_data.get('company_name') or row_data.get('company_name'),
                                    domain=domain,
                                    siren=row_data.get('siren'),
                                    additional_properties={
                                        'city': row_data.get('city'),
                                        'zip': row_data.get('postal_code'),
                                    }
                                )

                                hs_company_id = None
                                if hs_company:
                                    hs_company_id = hs_company.get('id')
                                    # Mettre à jour l'entreprise locale avec l'ID HubSpot
                                    if company_id:
                                        try:
                                            company_manager.update_company(company_id, {
                                                'hubspot_company_id': hs_company_id
                                            })
                                        except Exception as update_err:
                                            # hubspot_company_id peut déjà exister sur une autre entreprise
                                            logger.warning(f"Impossible de lier hubspot_company_id {hs_company_id}: {update_err}")

                                # 2. Gérer le contact HubSpot (créer ou ignorer si existe)
                                existing_hs_contact_id = None
                                if row['action'] == 'update' and row.get('contact_match'):
                                    # Si on met à jour un contact qui a déjà un hubspot_contact_id, ne pas recréer
                                    existing_hs_contact_id = row['contact_match'].get('hubspot_contact_id')

                                if existing_hs_contact_id:
                                    # Contact existe déjà dans HubSpot - juste ajouter une note
                                    hs_contact_id = existing_hs_contact_id
                                    note_body = f"Mis à jour depuis CSV ({source_name})"
                                    if row_data.get('contact_date'):
                                        note_body += f"\n📅 Date de contact: {row_data.get('contact_date')}"
                                    if row_data.get('notes'):
                                        note_body += f"\n\nNotes: {row_data.get('notes')}"
                                    hubspot_client.create_note(hs_contact_id, note_body)
                                    hubspot_synced += 1
                                    status.text(f"Note HubSpot: {row_data.get('company_name', 'N/A')}")
                                else:
                                    # Créer nouveau contact HubSpot
                                    contact_props = {
                                        'firstname': row_data.get('firstname'),
                                        'lastname': row_data.get('lastname'),
                                        'email': row_data.get('email'),
                                        'phone': row_data.get('phone'),
                                        'jobtitle': row_data.get('job_title'),
                                    }
                                    # Nettoyer les None
                                    contact_props = {k: v for k, v in contact_props.items() if v}

                                    hs_contact = hubspot_client.create_contact(contact_props)

                                    if hs_contact:
                                        hs_contact_id = hs_contact.get('id')

                                        # 3. Associer contact à l'entreprise HubSpot
                                        if hs_company_id:
                                            hubspot_client.associate_contact_company(hs_contact_id, hs_company_id)

                                        # 4. Créer une note dans HubSpot
                                        note_body = f"Importé depuis CSV ({source_name})"
                                        if row_data.get('contact_date'):
                                            note_body += f"\n📅 Date de contact: {row_data.get('contact_date')}"
                                        if row_data.get('notes'):
                                            note_body += f"\n\nNotes: {row_data.get('notes')}"
                                        hubspot_client.create_note(hs_contact_id, note_body)

                                        # 5. Mettre à jour le contact local
                                        contact_manager.update_contact(contact_uuid, {
                                            'hubspot_contact_id': hs_contact_id
                                        })

                                        hubspot_synced += 1
                                        status.text(f"Synced HubSpot: {row_data.get('company_name', 'N/A')}")

                            except Exception as hs_error:
                                logger.warning(f"Erreur sync HubSpot pour {row_data.get('email')}: {hs_error}")
                                # On ne bloque pas l'import pour une erreur HubSpot

                    except Exception as e:
                        errors.append(f"Ligne {row['row_index'] + 2}: {str(e)}")

                progress.progress(1.0)

                if imported > 0:
                    msg = f"✅ {imported} contact(s) importé(s) avec succès!"
                    if companies_classified > 0:
                        msg += f" | 🏷️ {companies_classified} entreprise(s) classifiée(s)"
                    if hubspot_synced > 0:
                        msg += f" | ☁️ {hubspot_synced} synchronisé(s) vers HubSpot"
                    st.success(msg)

                if hubspot_client and hubspot_synced < imported:
                    st.warning(f"⚠️ {imported - hubspot_synced} contact(s) non synchronisé(s) vers HubSpot (voir logs)")

                if errors:
                    with st.expander(f"⚠️ {len(errors)} erreur(s)"):
                        for err in errors:
                            st.error(err)

                # Réinitialiser
                st.session_state.csv_importer = None
                st.session_state.csv_analysis = None
                st.session_state.csv_step = 1

    else:
        st.info("👆 Uploadez un fichier CSV pour commencer")

        # Exemple de format
        with st.expander("📋 Format CSV attendu"):
            st.markdown("""
            Le fichier CSV doit contenir au minimum:
            - **Entreprise** (company_name, entreprise, société...)
            - **Email** ou **Prénom + Nom**

            Colonnes supportées:
            - `company_name`, `entreprise`, `société`
            - `firstname`, `prénom`
            - `lastname`, `nom`
            - `email`, `mail`
            - `phone`, `téléphone`
            - `job_title`, `fonction`, `poste`
            - `linkedin_url`, `linkedin`
            - `siren`, `siret`
            - `city`, `ville`
            - `postal_code`, `code postal`

            **Exemple:**
            ```csv
            entreprise;prénom;nom;email;fonction
            ACME Corp;Jean;Dupont;jean@acme.fr;Directeur
            TechCo;Marie;Martin;marie@techco.io;CTO
            ```
            """)

# Footer
render_footer()
