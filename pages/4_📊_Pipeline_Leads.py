"""
Page Pipeline Leads V2 - Interface 5 onglets pour le pipeline unifié.

Pipeline: Import → Clean → Enrich → Sync
"""
import os
import sys
import tempfile
import streamlit as st
from pathlib import Path
from datetime import datetime

# Ajouter le répertoire racine au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from components import render_top_nav, hide_sidebar

# Import des managers V2
try:
    import importlib.util

    base_path = Path(__file__).parent.parent / "modules" / "lead_scraper"

    # Charger les modules V2
    def load_module(name, filename):
        spec = importlib.util.spec_from_file_location(name, base_path / filename)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    company_mod = load_module('company_manager_v2', 'company_manager_v2.py')
    contact_mod = load_module('contact_manager_v2', 'contact_manager_v2.py')
    interaction_mod = load_module('interaction_manager', 'interaction_manager.py')
    csv_importer_mod = load_module('csv_importer_v2', 'csv_importer_v2.py')
    data_cleaner_mod = load_module('data_cleaner', 'data_cleaner.py')
    hubspot_sync_mod = load_module('hubspot_sync_v2', 'hubspot_sync_v2.py')
    enrichment_mod = load_module('enrichment_service', 'enrichment_service.py')

    CompanyManagerV2 = company_mod.CompanyManagerV2
    ContactManagerV2 = contact_mod.ContactManagerV2
    InteractionManager = interaction_mod.InteractionManager
    CSVImporterV2 = csv_importer_mod.CSVImporterV2
    DataCleaner = data_cleaner_mod.DataCleaner
    HubSpotSyncV2 = hubspot_sync_mod.HubSpotSyncV2
    EnrichmentService = enrichment_mod.EnrichmentService

    MODULES_AVAILABLE = True
except Exception as e:
    MODULES_AVAILABLE = False
    MODULE_ERROR = str(e)

# Navigation
hide_sidebar()

st.title("📊 Pipeline Leads")
st.markdown("Import → Clean → Enrich → Sync")

render_top_nav(current_page="pages/4_📊_Pipeline_Leads.py")

if not MODULES_AVAILABLE:
    st.error(f"❌ Modules V2 non disponibles: {MODULE_ERROR}")
    st.stop()

# Initialiser les managers
@st.cache_resource
def get_managers():
    company_mgr = CompanyManagerV2()
    contact_mgr = ContactManagerV2()
    interaction_mgr = InteractionManager()
    return company_mgr, contact_mgr, interaction_mgr

company_manager, contact_manager, interaction_manager = get_managers()

# Stats globales
company_stats = company_manager.get_stats()
contact_stats = contact_manager.get_stats()
interaction_stats = interaction_manager.get_stats()

# Onglets principaux
tab_vue, tab_import, tab_clean, tab_enrich, tab_sync = st.tabs([
    "📊 Vue",
    "📥 Import",
    "🧹 Clean",
    "🔍 Enrich",
    "🔄 Sync"
])

# =============================================================================
# TAB 1: VUE (Dashboard)
# =============================================================================
with tab_vue:
    st.subheader("📊 Vue d'ensemble")

    # Métriques principales avec delta
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_companies = company_stats.get('total', 0)
        st.metric("🏢 Entreprises", total_companies)

    with col2:
        total_contacts = contact_stats.get('total', 0)
        st.metric("👤 Contacts", total_contacts)

    with col3:
        total_interactions = interaction_stats.get('total', 0)
        st.metric("💬 Interactions", total_interactions)

    with col4:
        synced = total_companies - company_stats.get('to_sync', 0)
        sync_pct = round(synced / total_companies * 100) if total_companies > 0 else 0
        st.metric("🔄 Synced", f"{synced} ({sync_pct}%)")

    st.divider()

    # Pipeline Status - visuel
    st.markdown("### 📈 Statut Pipeline")

    col1, col2, col3, col4 = st.columns(4)

    # Calculer les stats pipeline
    to_clean = len(company_manager.find_duplicates(limit=100))
    to_enrich = company_stats.get('to_enrich', 0)
    to_sync = company_stats.get('to_sync', 0)
    enriched = total_companies - to_enrich if total_companies > 0 else 0

    with col1:
        st.markdown("**📥 Importés**")
        st.markdown(f"### {total_companies}")
        st.caption("Entreprises")

    with col2:
        clean_color = "🟢" if to_clean == 0 else "🟡" if to_clean < 10 else "🔴"
        st.markdown(f"**🧹 À nettoyer** {clean_color}")
        st.markdown(f"### {to_clean}")
        st.caption("Groupes doublons")

    with col3:
        enrich_pct = round(enriched / total_companies * 100) if total_companies > 0 else 0
        st.markdown("**🔍 Enrichis**")
        st.markdown(f"### {enriched}")
        st.caption(f"{enrich_pct}% du total")

    with col4:
        st.markdown("**🔄 À synchroniser**")
        st.markdown(f"### {to_sync}")
        st.caption("Vers HubSpot")

    st.divider()

    # Stats détaillées en 2 colonnes
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📁 Par Source")
        by_source = company_stats.get('by_source', {})
        if by_source:
            # Afficher sous forme de tableau
            source_data = [{'Source': k, 'Count': v} for k, v in sorted(by_source.items(), key=lambda x: -x[1])]
            st.dataframe(source_data, use_container_width=True, hide_index=True)
        else:
            st.info("Aucune donnée importée")

    with col2:
        st.markdown("### 👤 Contacts")
        contact_with_email = contact_stats.get('email_verified', 0)
        contact_without_company = contact_stats.get('without_company', 0)

        st.write(f"• Total: **{total_contacts}**")
        st.write(f"• Avec email vérifié: **{contact_with_email}**")
        st.write(f"• Sans entreprise: **{contact_without_company}**")
        st.write(f"• À synchroniser: **{contact_stats.get('to_sync', 0)}**")

    st.divider()

    # Recherche avancée
    st.markdown("### 🔍 Recherche & Exploration")

    # Filtres en ligne
    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])

    with col1:
        search_term = st.text_input("🔍 Recherche", placeholder="Nom, SIREN, email, domain...")

    with col2:
        search_type = st.selectbox("Type", ["Entreprises", "Contacts"])

    with col3:
        by_source_options = ["Toutes"] + list(company_stats.get('by_source', {}).keys())
        filter_source = st.selectbox("Source", by_source_options)

    with col4:
        filter_status = st.selectbox("Statut", ["Tous", "Enrichis", "Non enrichis", "Synced", "Non synced"])

    with col5:
        limit = st.selectbox("Limite", [25, 50, 100, 200, 500], index=1)

    # Bouton de recherche
    search_clicked = st.button("🔍 Rechercher", type="primary", use_container_width=True)

    if search_clicked or search_term:
        if search_type == "Entreprises":
            # Recherche entreprises
            if search_term:
                # Recherche par SIREN
                result = company_manager.find_by_siren(search_term)
                if result:
                    st.success(f"✅ Trouvé par SIREN: **{result['name']}**")
                    with st.expander("📋 Détails", expanded=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Nom:** {result.get('name')}")
                            st.write(f"**SIREN:** {result.get('siren')}")
                            st.write(f"**Domain:** {result.get('domain')}")
                            st.write(f"**Ville:** {result.get('hq_city')}")
                        with col2:
                            st.write(f"**Taille:** {result.get('size')}")
                            st.write(f"**Secteur:** {result.get('industry')}")
                            st.write(f"**Source:** {result.get('source')}")
                            st.write(f"**Enrichi:** {'✅' if result.get('enriched_at') else '❌'}")

                        # Contacts de cette entreprise
                        contacts = contact_manager.list_all(limit=100)
                        company_contacts = [c for c in contacts if c.get('company_uuid') == result['uuid']]
                        if company_contacts:
                            st.markdown("**👤 Contacts:**")
                            st.dataframe([{
                                'Nom': f"{c.get('firstname', '')} {c.get('lastname', '')}",
                                'Email': c.get('email'),
                                'Fonction': c.get('job_title')
                            } for c in company_contacts], use_container_width=True, hide_index=True)
                else:
                    # Recherche par domain
                    result = company_manager.find_by_domain(search_term)
                    if result:
                        st.success(f"✅ Trouvé par domain: **{result['name']}**")
                        st.json(result)
                    else:
                        # Recherche fuzzy par nom
                        result = company_manager.find_by_name_fuzzy(search_term, threshold=0.5)
                        if result:
                            st.success(f"✅ Trouvé par nom: **{result['name']}**")
                            st.json(result)
                        else:
                            st.warning("Aucun résultat trouvé")
            else:
                # Liste avec filtres
                companies = company_manager.list_all(
                    status='active',
                    source=filter_source if filter_source != "Toutes" else None,
                    limit=limit
                )

                # Appliquer filtre status
                if filter_status == "Enrichis":
                    companies = [c for c in companies if c.get('enriched_at')]
                elif filter_status == "Non enrichis":
                    companies = [c for c in companies if not c.get('enriched_at')]
                elif filter_status == "Synced":
                    companies = [c for c in companies if c.get('synced_to_hubspot')]
                elif filter_status == "Non synced":
                    companies = [c for c in companies if not c.get('synced_to_hubspot')]

                if companies:
                    st.write(f"**{len(companies)}** entreprises affichées")
                    st.dataframe([{
                        'Nom': c.get('name'),
                        'Domain': c.get('domain'),
                        'SIREN': c.get('siren'),
                        'Ville': c.get('hq_city'),
                        'Taille': c.get('size'),
                        'Source': c.get('source'),
                        'Enrichi': '✅' if c.get('enriched_at') else '❌',
                        'Synced': '✅' if c.get('synced_to_hubspot') else '❌'
                    } for c in companies], use_container_width=True, hide_index=True)
                else:
                    st.info("Aucune entreprise trouvée avec ces filtres")

        else:
            # Recherche contacts
            if search_term:
                # Par email
                result = contact_manager.find_by_email(search_term)
                if result:
                    st.success(f"✅ Trouvé par email: **{result.get('firstname')} {result.get('lastname')}**")
                    st.json(result)
                else:
                    # Par LinkedIn
                    result = contact_manager.find_by_linkedin(search_term)
                    if result:
                        st.success(f"✅ Trouvé par LinkedIn: **{result.get('firstname')} {result.get('lastname')}**")
                        st.json(result)
                    else:
                        st.warning("Aucun résultat trouvé")
            else:
                # Liste contacts
                contacts = contact_manager.list_all(
                    status='active',
                    source=filter_source if filter_source != "Toutes" else None,
                    limit=limit
                )

                if contacts:
                    st.write(f"**{len(contacts)}** contacts affichés")
                    st.dataframe([{
                        'Prénom': c.get('firstname'),
                        'Nom': c.get('lastname'),
                        'Email': c.get('email'),
                        'Fonction': c.get('job_title'),
                        'Entreprise': c.get('company_uuid', '')[:8] if c.get('company_uuid') else '-',
                        'Source': c.get('source'),
                        'Synced': '✅' if c.get('synced_to_hubspot') else '❌'
                    } for c in contacts], use_container_width=True, hide_index=True)
                else:
                    st.info("Aucun contact trouvé")

# =============================================================================
# TAB 2: IMPORT
# =============================================================================
with tab_import:
    st.subheader("📥 Import de données")

    # Source d'import
    import_source = st.radio(
        "Source d'import",
        ["📄 CSV (FullEnrich, Salesbot, etc.)", "🟠 HubSpot", "🔍 SIRENE", "💼 GetSales"],
        horizontal=True
    )

    st.divider()

    if "CSV" in import_source:
        # Upload CSV
        uploaded_file = st.file_uploader(
            "Glisser un fichier CSV",
            type=['csv'],
            help="Formats supportés: FullEnrich, Salesbot, export HubSpot"
        )

        if uploaded_file:
            # Sauvegarder temporairement
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name

            # Détecter les colonnes
            importer = CSVImporterV2(company_manager, contact_manager)
            detection = importer.detect_columns(tmp_path)

            st.success(f"✅ Fichier chargé: {uploaded_file.name}")
            st.write(f"**{detection['row_count']}** lignes détectées")

            # Aperçu des données
            with st.expander("👁 Aperçu des données", expanded=False):
                if detection['sample_data']:
                    st.dataframe(detection['sample_data'][:5])

            # Mapping des colonnes
            st.markdown("### Mapping des colonnes")

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Colonnes mappées automatiquement**")
                for csv_col, db_field in detection['suggested_mapping'].items():
                    st.write(f"• `{csv_col}` → `{db_field}`")

            with col2:
                st.markdown("**Colonnes non mappées**")
                if detection['unmapped']:
                    for col in detection['unmapped'][:10]:
                        st.write(f"• `{col}`")
                    if len(detection['unmapped']) > 10:
                        st.write(f"... et {len(detection['unmapped']) - 10} autres")
                else:
                    st.success("Toutes les colonnes sont mappées!")

            st.divider()

            # Options d'import
            col1, col2 = st.columns(2)

            with col1:
                smart_matching = st.checkbox("✅ Matching intelligent (éviter doublons)", value=True)
                create_companies = st.checkbox("✅ Créer les entreprises manquantes", value=True)

            with col2:
                preview_mode = st.checkbox("👁 Mode preview (sans import)", value=False)

            # Bouton d'import
            if st.button("📥 IMPORTER", type="primary", use_container_width=True):
                with st.spinner("Import en cours..."):
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    def update_progress(current, total):
                        progress_bar.progress(current / total if total > 0 else 0)
                        status_text.text(f"Traitement: {current}/{total}")

                    report = importer.import_file(
                        tmp_path,
                        mapping=detection['suggested_mapping'],
                        source_name=uploaded_file.name,
                        preview_only=preview_mode,
                        create_companies=create_companies,
                        smart_matching=smart_matching,
                        progress_callback=update_progress
                    )

                    progress_bar.progress(1.0)

                # Résultat
                if report['success']:
                    st.success("✅ Import terminé!")

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Entreprises**")
                        st.write(f"• Créées: {report['companies']['created']}")
                        st.write(f"• Mises à jour: {report['companies']['updated']}")
                        st.write(f"• Matchées: {report['companies']['matched']}")

                    with col2:
                        st.markdown("**Contacts**")
                        st.write(f"• Créés: {report['contacts']['created']}")
                        st.write(f"• Mis à jour: {report['contacts']['updated']}")
                        st.write(f"• Matchés: {report['contacts']['matched']}")

                    if report['errors']:
                        with st.expander(f"⚠️ {len(report['errors'])} erreurs"):
                            for err in report['errors'][:20]:
                                st.write(f"• {err}")
                else:
                    st.error("❌ Erreur d'import")
                    for err in report.get('errors', []):
                        st.write(f"• {err}")

            # Cleanup
            try:
                os.unlink(tmp_path)
            except:
                pass

    elif "HubSpot" in import_source:
        # Import HubSpot
        api_key = os.environ.get('HUBSPOT_API_KEY')

        if not api_key:
            st.warning("⚠️ HUBSPOT_API_KEY non configurée")
            st.info("Configurez la variable d'environnement HUBSPOT_API_KEY")
        else:
            # Charger le module d'import
            try:
                hubspot_import_mod = load_module('hubspot_import_v2', 'hubspot_import_v2.py')
                HubSpotImportV2 = hubspot_import_mod.HubSpotImportV2
                hs_importer = HubSpotImportV2(company_manager, contact_manager, interaction_manager, api_key)

                if hs_importer.is_connected():
                    st.success("✅ Connecté à HubSpot")

                    # Stats
                    stats = hs_importer.get_import_stats()
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Companies HubSpot", stats.get('hubspot_companies', '?'))
                    with col2:
                        st.metric("Contacts HubSpot", stats.get('hubspot_contacts', '?'))
                    with col3:
                        st.metric("Déjà importées", stats.get('local_from_hubspot', 0))

                    st.divider()

                    # Options
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        import_companies = st.checkbox("🏢 Entreprises", value=True)
                    with col2:
                        import_contacts = st.checkbox("👤 Contacts", value=True)
                    with col3:
                        import_engagements = st.checkbox("💬 Engagements", value=True)

                    hs_limit = st.number_input("Limite par type", 10, 1000, 100)

                    if st.button("📥 IMPORTER DEPUIS HUBSPOT", type="primary", use_container_width=True):
                        with st.spinner("Import HubSpot en cours..."):
                            progress_bar = st.progress(0)
                            status_text = st.empty()

                            def update_hs_progress(current, total, entity_type):
                                progress_bar.progress(current / total if total > 0 else 0)
                                status_text.text(f"Import {entity_type}: {current}/{total}")

                            report = hs_importer.import_all(
                                companies=import_companies,
                                contacts=import_contacts,
                                engagements=import_engagements,
                                limit=hs_limit,
                                progress_callback=update_hs_progress
                            )
                            progress_bar.progress(1.0)

                        if report['success']:
                            st.success("✅ Import HubSpot terminé!")

                            col1, col2, col3 = st.columns(3)
                            if report.get('companies'):
                                with col1:
                                    st.markdown("**Entreprises**")
                                    st.write(f"• Créées: {report['companies']['created']}")
                                    st.write(f"• Matchées: {report['companies']['matched']}")
                            if report.get('contacts'):
                                with col2:
                                    st.markdown("**Contacts**")
                                    st.write(f"• Créés: {report['contacts']['created']}")
                                    st.write(f"• Matchés: {report['contacts']['matched']}")
                            if report.get('engagements'):
                                with col3:
                                    st.markdown("**Interactions**")
                                    st.write(f"• Créées: {report['engagements']['created']}")
                        else:
                            st.error("❌ Erreur import HubSpot")
                else:
                    st.error("❌ Erreur connexion HubSpot - vérifiez la clé API")
            except Exception as e:
                st.error(f"❌ Erreur: {e}")

    elif "SIRENE" in import_source:
        # Import SIRENE - Recherche
        try:
            sirene_mod = load_module('sirene_search', 'sirene_search.py')
            SireneSearch = sirene_mod.SireneSearch
            sirene = SireneSearch(company_manager)

            st.markdown("### Recherche d'entreprises SIRENE")

            # Formulaire de recherche
            col1, col2 = st.columns(2)

            with col1:
                sirene_query = st.text_input("🔍 Recherche", placeholder="Nom, SIREN, mot-clé...")
                sirene_dept = st.text_input("📍 Département", placeholder="69, 75...")

            with col2:
                # Sections NAF
                naf_sections = sirene.get_naf_sections()
                naf_options = ["Tous"] + [f"{k} - {v}" for k, v in naf_sections.items()]
                sirene_naf = st.selectbox("🏭 Secteur NAF", naf_options)

                # Tranches effectif
                effectif_tranches = sirene.get_effectif_tranches()
                eff_options = ["Toutes"] + [f"{k} - {v}" for k, v in effectif_tranches.items()]
                sirene_effectif = st.selectbox("👥 Effectif", eff_options)

            if st.button("🔍 RECHERCHER", type="primary"):
                with st.spinner("Recherche SIRENE en cours..."):
                    # Préparer les paramètres
                    search_params = {'per_page': 25}
                    if sirene_query:
                        search_params['query'] = sirene_query
                    if sirene_dept:
                        search_params['departement'] = sirene_dept
                    if sirene_naf != "Tous":
                        search_params['section_naf'] = sirene_naf.split(" - ")[0]
                    if sirene_effectif != "Toutes":
                        search_params['tranche_effectif'] = sirene_effectif.split(" - ")[0]

                    results = sirene.search(**search_params)

                if results.get('error'):
                    st.error(f"Erreur: {results['error']}")
                elif results['total'] == 0:
                    st.info("Aucun résultat trouvé")
                else:
                    st.success(f"✅ {results['total']} résultats trouvés")

                    # Stocker les résultats dans session state
                    st.session_state['sirene_results'] = results['results']

                    # Afficher les résultats avec checkboxes
                    st.markdown("### Résultats")

                    selected = []
                    for i, company in enumerate(results['results']):
                        col1, col2, col3, col4 = st.columns([0.5, 3, 2, 2])
                        with col1:
                            if st.checkbox("", key=f"sirene_{i}"):
                                selected.append(i)
                        with col2:
                            st.write(f"**{company.get('name', 'N/A')}**")
                        with col3:
                            st.write(company.get('hq_city', ''))
                        with col4:
                            st.write(company.get('size_label', ''))

                    st.session_state['sirene_selected'] = selected

            # Bouton import si résultats
            if 'sirene_results' in st.session_state and st.session_state.get('sirene_selected'):
                selected_count = len(st.session_state['sirene_selected'])
                if st.button(f"📥 IMPORTER {selected_count} ENTREPRISE(S)", type="primary"):
                    selected_companies = [
                        st.session_state['sirene_results'][i]
                        for i in st.session_state['sirene_selected']
                    ]

                    with st.spinner("Import en cours..."):
                        report = sirene.import_companies(selected_companies)

                    if report.get('errors'):
                        st.warning(f"Import partiel: {report['created']} créées, {len(report['errors'])} erreurs")
                    else:
                        st.success(f"✅ {report['created']} entreprises importées!")

                    # Nettoyer session
                    del st.session_state['sirene_results']
                    del st.session_state['sirene_selected']

        except Exception as e:
            st.error(f"❌ Erreur SIRENE: {e}")

    else:
        # Import GetSales
        api_key = os.environ.get('GETSALES_API_KEY')

        if not api_key:
            st.warning("⚠️ GETSALES_API_KEY non configurée")
            st.info("Configurez la variable d'environnement GETSALES_API_KEY")
        else:
            try:
                getsales_import_mod = load_module('getsales_import_v2', 'getsales_import_v2.py')
                GetSalesImportV2 = getsales_import_mod.GetSalesImportV2
                gs_importer = GetSalesImportV2(company_manager, contact_manager, interaction_manager, api_key)

                if gs_importer.is_connected():
                    st.success("✅ Connecté à GetSales")

                    # Stats
                    stats = gs_importer.get_import_stats()
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Flows GetSales", stats.get('getsales_flows', '?'))
                    with col2:
                        st.metric("Déjà importés", stats.get('local_from_getsales', 0))
                    with col3:
                        st.metric("Source", "LinkedIn")

                    st.divider()

                    # Options
                    col1, col2 = st.columns(2)
                    with col1:
                        gs_limit = st.number_input("Limite leads", 10, 500, 100, key="gs_limit")
                    with col2:
                        fetch_messages = st.checkbox("📨 Récupérer messages LinkedIn", value=True)

                    # Sélection de flow/campagne
                    try:
                        flows = gs_importer.fetch_flows()
                        if flows:
                            flow_options = ["Toutes les campagnes"] + [
                                f"{f.get('name', f.get('uuid', 'Unknown'))} ({f.get('uuid', '')[:8]})"
                                for f in flows
                            ]
                            selected_flow = st.selectbox("🎯 Campagne", flow_options)

                            flow_uuid = None
                            if selected_flow != "Toutes les campagnes":
                                idx = flow_options.index(selected_flow) - 1
                                flow_uuid = flows[idx].get('uuid')
                    except Exception:
                        flow_uuid = None
                        st.info("Impossible de charger les campagnes")

                    if st.button("📥 IMPORTER DEPUIS GETSALES", type="primary", use_container_width=True):
                        with st.spinner("Import GetSales en cours..."):
                            progress_bar = st.progress(0)
                            status_text = st.empty()

                            def update_gs_progress(current, total, entity_type):
                                progress_bar.progress(current / total if total > 0 else 0)
                                status_text.text(f"Import {entity_type}: {current}/{total}")

                            report = gs_importer.import_all(
                                limit=gs_limit,
                                flow_uuid=flow_uuid if 'flow_uuid' in dir() else None,
                                fetch_messages=fetch_messages,
                                progress_callback=update_gs_progress
                            )
                            progress_bar.progress(1.0)

                        if report['success']:
                            st.success("✅ Import GetSales terminé!")

                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.markdown("**Leads**")
                                st.write(f"• Récupérés: {report['leads_fetched']}")
                            if report.get('companies'):
                                with col2:
                                    st.markdown("**Entreprises**")
                                    st.write(f"• Créées: {report['companies']['created']}")
                                    st.write(f"• Matchées: {report['companies']['matched']}")
                            if report.get('contacts'):
                                with col3:
                                    st.markdown("**Contacts**")
                                    st.write(f"• Créés: {report['contacts']['created']}")
                                    st.write(f"• Mis à jour: {report['contacts']['updated']}")

                            if report.get('interactions', {}).get('created', 0) > 0:
                                st.info(f"💬 {report['interactions']['created']} interactions importées")

                            if report.get('errors'):
                                with st.expander(f"⚠️ {len(report['errors'])} erreurs"):
                                    for err in report['errors'][:20]:
                                        st.write(f"• {err}")
                        else:
                            st.error("❌ Erreur import GetSales")
                            for err in report.get('errors', []):
                                st.write(f"• {err}")
                else:
                    st.error("❌ Erreur connexion GetSales - vérifiez la clé API")
            except Exception as e:
                st.error(f"❌ Erreur: {e}")

# =============================================================================
# TAB 3: CLEAN
# =============================================================================
with tab_clean:
    st.subheader("🧹 Nettoyage des données")

    cleaner = DataCleaner(company_manager, contact_manager)

    # Section Déduplication
    st.markdown("### 🔍 Déduplication")

    col1, col2, col3 = st.columns(3)

    with col1:
        dedup_type = st.radio("Type", ["🏢 Entreprises", "👤 Contacts"], horizontal=True)

    with col2:
        threshold = st.slider("Seuil similarité", 70, 100, 85, 5)

    with col3:
        dedup_limit = st.number_input("Limite groupes", 10, 100, 50)

    if st.button("🔍 DÉTECTER LES DOUBLONS", type="primary"):
        with st.spinner("Analyse en cours..."):
            if "Entreprises" in dedup_type:
                duplicates = company_manager.find_duplicates(
                    threshold=threshold/100,
                    limit=dedup_limit
                )
            else:
                duplicates = contact_manager.find_duplicates(
                    threshold=threshold/100,
                    limit=dedup_limit
                )

            st.session_state['duplicates'] = duplicates
            st.session_state['dedup_type'] = dedup_type

    # Afficher les résultats si disponibles
    if 'duplicates' in st.session_state and st.session_state['duplicates']:
        duplicates = st.session_state['duplicates']
        dedup_type = st.session_state.get('dedup_type', 'Entreprises')

        st.warning(f"⚠️ {len(duplicates)} groupes de doublons détectés")

        # Bulk actions
        st.markdown("**Actions groupées**")
        col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

        with col1:
            select_all = st.checkbox("☑️ Tout sélectionner", key="select_all_dedup")

        with col2:
            if st.button("🔀 AUTO-MERGE SÉLECTION", type="secondary"):
                selected_groups = [i for i in range(len(duplicates)) if st.session_state.get(f"dedup_select_{i}", select_all)]
                if selected_groups:
                    merged = 0
                    for idx in selected_groups:
                        group = duplicates[idx]
                        items = group.get('companies', group.get('contacts', []))
                        if len(items) < 2:
                            continue

                        # Auto-select master: celui avec le plus de données remplies
                        def count_filled(item):
                            return sum(1 for v in item.values() if v)

                        items_sorted = sorted(items, key=count_filled, reverse=True)
                        master = items_sorted[0]
                        dups = items_sorted[1:]

                        try:
                            if "Entreprises" in dedup_type:
                                company_manager.merge(master['uuid'], [d['uuid'] for d in dups])
                            else:
                                contact_manager.merge(master['uuid'], [d['uuid'] for d in dups])
                            merged += 1
                        except:
                            pass

                    st.success(f"✅ {merged} groupes fusionnés automatiquement!")
                    del st.session_state['duplicates']
                    st.rerun()
                else:
                    st.warning("Sélectionnez au moins un groupe")

        with col3:
            if st.button("👥 HOMONYMES SÉLECTION", type="secondary"):
                if "Contacts" in dedup_type:
                    selected_groups = [i for i in range(len(duplicates)) if st.session_state.get(f"dedup_select_{i}", select_all)]
                    if selected_groups:
                        marked = 0
                        for idx in selected_groups:
                            group = duplicates[idx]
                            items = group.get('contacts', [])
                            uuids = [c['uuid'] for c in items]
                            try:
                                contact_manager.mark_as_homonyms(uuids)
                                marked += 1
                            except:
                                pass
                        st.success(f"✅ {marked} groupes marqués homonymes!")
                        del st.session_state['duplicates']
                        st.rerun()
                else:
                    st.info("Homonymes uniquement pour contacts")

        with col4:
            if st.button("🗑️ EFFACER RÉSULTATS"):
                del st.session_state['duplicates']
                st.rerun()

        st.divider()

        # Afficher les groupes avec checkboxes
        for i, group in enumerate(duplicates[:20]):
            col1, col2 = st.columns([0.5, 9.5])

            with col1:
                st.checkbox("", key=f"dedup_select_{i}", value=select_all)

            with col2:
                with st.expander(f"Groupe {i+1} - Score: {group['score']}% - {group['reason']}"):
                    if "Entreprises" in dedup_type:
                        items = group['companies']
                        st.dataframe([{
                            'Nom': c.get('name'),
                            'SIREN': c.get('siren'),
                            'Domain': c.get('domain'),
                            'Contacts': c.get('contact_count', 0)
                        } for c in items], hide_index=True)

                        master_options = [f"{c.get('name')} ({c.get('uuid')[:8]})" for c in items]
                        master_choice = st.selectbox("Master", master_options, key=f"master_company_{i}")

                        if st.button(f"🔀 Fusionner", key=f"merge_company_{i}"):
                            master_idx = master_options.index(master_choice)
                            master_uuid = items[master_idx]['uuid']
                            dup_uuids = [c['uuid'] for c in items if c['uuid'] != master_uuid]
                            result = company_manager.merge(master_uuid, dup_uuids)
                            if result['success']:
                                st.success(f"✅ Fusion réussie!")
                                st.rerun()
                    else:
                        items = group['contacts']
                        st.dataframe([{
                            'Nom': f"{c.get('firstname', '')} {c.get('lastname', '')}",
                            'Email': c.get('email'),
                            'LinkedIn': c.get('linkedin_url'),
                            'Entreprise': c.get('company_name')
                        } for c in items], hide_index=True)

                        master_options = [f"{c.get('firstname', '')} {c.get('lastname', '')} ({c.get('uuid')[:8]})" for c in items]
                        master_choice = st.selectbox("Master", master_options, key=f"master_contact_{i}")

                        bcol1, bcol2 = st.columns(2)
                        with bcol1:
                            if st.button(f"🔀 Fusionner", key=f"merge_contact_{i}"):
                                master_idx = master_options.index(master_choice)
                                master_uuid = items[master_idx]['uuid']
                                dup_uuids = [c['uuid'] for c in items if c['uuid'] != master_uuid]
                                result = contact_manager.merge(master_uuid, dup_uuids)
                                if result['success']:
                                    st.success("✅ Fusion réussie!")
                                    st.rerun()
                        with bcol2:
                            if st.button(f"👥 Homonymes", key=f"homonym_{i}"):
                                uuids = [c['uuid'] for c in items]
                                contact_manager.mark_as_homonyms(uuids)
                                st.success("✅ Homonymes!")
                                st.rerun()

    elif 'duplicates' in st.session_state:
        st.success("✅ Aucun doublon détecté!")

    st.divider()

    # Section Normalisation
    st.markdown("### 🔧 Normalisation")

    col1, col2 = st.columns(2)

    with col1:
        norm_names = st.checkbox("Normaliser noms entreprises", value=True)
        norm_phones = st.checkbox("Normaliser téléphones", value=True)

    with col2:
        norm_emails = st.checkbox("Normaliser emails", value=True)
        norm_linkedin = st.checkbox("Normaliser URLs LinkedIn", value=True)

    if st.button("🔧 NORMALISER", type="primary"):
        with st.spinner("Normalisation en cours..."):
            report = cleaner.normalize_all()

        st.success("✅ Normalisation terminée!")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Entreprises**: {report['companies']['normalized']} normalisées")
        with col2:
            st.write(f"**Contacts**: {report['contacts']['normalized']} normalisés")

    st.divider()

    # Section Validation
    st.markdown("### ✅ Validation")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ VALIDER LES DONNÉES"):
            with st.spinner("Validation en cours..."):
                validation = cleaner.validate_all()

            st.markdown("**Résumé**")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Emails invalides", validation['summary']['invalid_emails'])
            with col2:
                st.metric("Téléphones invalides", validation['summary']['invalid_phones'])
            with col3:
                st.metric("SIREN invalides", validation['summary']['invalid_sirens'])
            with col4:
                st.metric("LinkedIn invalides", validation['summary']['invalid_linkedin'])

            if validation['companies']['issues']:
                with st.expander(f"⚠️ {len(validation['companies']['issues'])} entreprises avec problèmes"):
                    for issue in validation['companies']['issues'][:20]:
                        st.write(f"• **{issue['name']}**: {', '.join(issue['issues'])}")

            if validation['contacts']['issues']:
                with st.expander(f"⚠️ {len(validation['contacts']['issues'])} contacts avec problèmes"):
                    for issue in validation['contacts']['issues'][:20]:
                        st.write(f"• **{issue['name']}**: {', '.join(issue['issues'])}")

    with col2:
        st.markdown("**MX Check (emails)**")
        mx_limit = st.number_input("Limite contacts", 10, 500, 100, key="mx_limit")
        if st.button("📧 VÉRIFIER MX"):
            with st.spinner("Vérification MX en cours..."):
                progress_bar = st.progress(0)

                def mx_progress(current, total):
                    progress_bar.progress(current / total if total > 0 else 0)

                mx_report = cleaner.validate_emails_with_mx(
                    limit=mx_limit,
                    progress_callback=mx_progress
                )
                progress_bar.progress(1.0)

            st.write(f"**Vérifiés:** {mx_report['checked']}")
            st.write(f"**Valides:** {mx_report['valid']}")

            if mx_report['invalid']:
                with st.expander(f"⚠️ {len(mx_report['invalid'])} emails invalides"):
                    for inv in mx_report['invalid'][:20]:
                        reason = "Format" if inv['reason'] == 'format_invalid' else f"MX ({inv.get('domain', '')})"
                        st.write(f"• {inv['email']} - {reason}")

            if mx_report.get('domains_checked'):
                invalid_domains = [d for d, valid in mx_report['domains_checked'].items() if not valid]
                if invalid_domains:
                    st.warning(f"Domaines sans MX: {', '.join(invalid_domains[:10])}")

# =============================================================================
# TAB 4: ENRICH
# =============================================================================
with tab_enrich:
    st.subheader("🔍 Enrichissement des données")

    # Initialiser le service d'enrichissement
    enricher = EnrichmentService(company_manager, contact_manager)
    enrich_stats = enricher.get_enrichment_stats()

    # Stats
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("À enrichir", enrich_stats.get('to_enrich', 0))

    with col2:
        st.metric("Enrichies", enrich_stats.get('enriched', 0))

    with col3:
        no_siren = enrich_stats.get('total_companies', 0) - enrich_stats.get('with_siren', 0)
        st.metric("Sans SIREN", no_siren)

    # Stats par source
    if enrich_stats.get('by_source'):
        st.caption(f"Par source: {enrich_stats['by_source']}")

    st.divider()

    # Vérifier les clés API
    pappers_key = os.environ.get('PAPPERS_API_KEY')

    col1, col2 = st.columns(2)
    with col1:
        if pappers_key:
            st.success("✅ Pappers API configurée")
        else:
            st.warning("⚠️ PAPPERS_API_KEY non configurée")

    with col2:
        st.success("✅ SIRENE API (gratuite)")

    st.divider()

    # Mode d'enrichissement
    enrich_mode = st.radio(
        "Mode",
        ["📋 Sélection manuelle", "🔄 Batch automatique"],
        horizontal=True
    )

    # Source d'enrichissement
    enrich_source = st.radio(
        "Source d'enrichissement",
        ["🔍 SIRENE (gratuit - adresse, APE)", "📊 Pappers (payant - dirigeants, CA, effectifs)"],
        horizontal=True
    )

    source = 'pappers' if 'Pappers' in enrich_source else 'sirene'

    st.divider()

    if "Sélection manuelle" in enrich_mode:
        # Mode sélection manuelle avec checkboxes
        st.markdown("### 📋 Sélection des entreprises à enrichir")

        # Filtres de recherche
        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])

        with col1:
            enrich_search = st.text_input("🔍 Recherche", placeholder="Nom, SIREN...", key="enrich_search")

        with col2:
            enrich_filter_status = st.selectbox(
                "Statut",
                ["Non enrichies", "Toutes", "Enrichies"],
                key="enrich_status"
            )

        with col3:
            enrich_size_filter = st.selectbox(
                "Taille",
                ["Toutes", "1-10", "11-50", "51-200", "201-500", "501+"],
                key="enrich_size"
            )

        with col4:
            enrich_display_limit = st.selectbox("Afficher", [25, 50, 100], key="enrich_display")

        # Charger les entreprises avec filtres
        if st.button("🔍 CHARGER", key="load_enrich_companies"):
            # Récupérer les entreprises
            only_unenriched = enrich_filter_status == "Non enrichies"
            only_enriched = enrich_filter_status == "Enrichies"

            companies = company_manager.list_all(status='active', limit=enrich_display_limit * 2)

            # Filtrer par statut enrichissement
            if only_unenriched:
                companies = [c for c in companies if not c.get('enriched_at')]
            elif only_enriched:
                companies = [c for c in companies if c.get('enriched_at')]

            # Filtrer par recherche
            if enrich_search:
                search_lower = enrich_search.lower()
                companies = [c for c in companies if
                    (c.get('name') and search_lower in c['name'].lower()) or
                    (c.get('siren') and search_lower in c['siren'])
                ]

            # Filtrer par taille
            if enrich_size_filter != "Toutes":
                companies = [c for c in companies if c.get('size') == enrich_size_filter]

            # Limiter
            companies = companies[:enrich_display_limit]

            st.session_state['enrich_companies'] = companies
            st.session_state['enrich_selected'] = set()

        # Afficher les entreprises avec checkboxes
        if 'enrich_companies' in st.session_state and st.session_state['enrich_companies']:
            companies = st.session_state['enrich_companies']

            st.write(f"**{len(companies)}** entreprises affichées")

            # Actions groupées
            col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

            with col1:
                select_all_enrich = st.checkbox("☑️ Tout sélectionner", key="select_all_enrich")
                if select_all_enrich:
                    st.session_state['enrich_selected'] = set(range(len(companies)))

            with col2:
                selected_count = len(st.session_state.get('enrich_selected', set()))
                st.write(f"**{selected_count}** sélectionnées")

            with col3:
                if st.button("🗑️ Effacer sélection"):
                    st.session_state['enrich_selected'] = set()
                    st.rerun()

            with col4:
                if st.button(f"🔍 ENRICHIR SÉLECTION ({selected_count})", type="primary", disabled=selected_count == 0):
                    if source == 'pappers' and not pappers_key:
                        st.error("❌ PAPPERS_API_KEY requise pour Pappers")
                    else:
                        # Récupérer les entreprises sélectionnées
                        selected_companies = [companies[i] for i in st.session_state['enrich_selected']]

                        with st.spinner(f"Enrichissement via {source.upper()} en cours..."):
                            progress_bar = st.progress(0)
                            status_text = st.empty()

                            enriched = 0
                            errors = []
                            contacts_added = 0

                            for i, company in enumerate(selected_companies):
                                progress_bar.progress((i + 1) / len(selected_companies))
                                status_text.text(f"Traitement: {company.get('name', 'N/A')} ({i+1}/{len(selected_companies)})")

                                siren = company.get('siren')
                                if not siren:
                                    errors.append(f"{company.get('name', 'N/A')}: pas de SIREN")
                                    continue

                                try:
                                    result = enricher.enrich_company(company['uuid'], source=source)
                                    if result.get('success'):
                                        enriched += 1
                                        contacts_added += result.get('contacts_added', 0)
                                    else:
                                        errors.append(f"{company.get('name', 'N/A')}: {result.get('error', 'erreur')}")
                                except Exception as e:
                                    errors.append(f"{company.get('name', 'N/A')}: {str(e)}")

                            progress_bar.progress(1.0)

                        st.success(f"✅ Enrichissement terminé! {enriched}/{len(selected_companies)} entreprises enrichies")

                        if contacts_added > 0:
                            st.info(f"👤 {contacts_added} contacts ajoutés")

                        if errors:
                            with st.expander(f"⚠️ {len(errors)} erreurs"):
                                for err in errors[:20]:
                                    st.write(f"• {err}")

                        # Nettoyer la session
                        del st.session_state['enrich_companies']
                        del st.session_state['enrich_selected']
                        st.rerun()

            st.divider()

            # Liste des entreprises avec checkboxes
            for i, company in enumerate(companies):
                col1, col2, col3, col4, col5 = st.columns([0.5, 3, 2, 2, 1])

                with col1:
                    checked = i in st.session_state.get('enrich_selected', set())
                    if st.checkbox("", key=f"enrich_company_{i}", value=checked or select_all_enrich):
                        if 'enrich_selected' not in st.session_state:
                            st.session_state['enrich_selected'] = set()
                        st.session_state['enrich_selected'].add(i)
                    elif i in st.session_state.get('enrich_selected', set()):
                        st.session_state['enrich_selected'].discard(i)

                with col2:
                    st.write(f"**{company.get('name', 'N/A')}**")

                with col3:
                    siren = company.get('siren', '-')
                    st.write(f"SIREN: {siren}" if siren else "⚠️ Pas de SIREN")

                with col4:
                    st.write(company.get('size', '-'))

                with col5:
                    if company.get('enriched_at'):
                        st.write("✅")
                    else:
                        st.write("❌")

        elif 'enrich_companies' in st.session_state:
            st.info("Aucune entreprise ne correspond aux filtres")
        else:
            st.info("Cliquez sur 'CHARGER' pour afficher les entreprises")

    else:
        # Mode batch automatique (ancien mode)
        st.markdown("### 🔄 Enrichissement batch")

        # Filtres
        col1, col2, col3 = st.columns(3)

        with col1:
            only_unenriched = st.checkbox("Non enrichies uniquement", value=True)

        with col2:
            size_filter = st.selectbox("Taille", ["Toutes", "1-10", "11-50", "51-200", "201-500", "501+"])

        with col3:
            enrich_limit = st.number_input("Limite", 10, 500, 100)

        # Aperçu des entreprises à enrichir
        with st.expander("👁 Aperçu des entreprises à enrichir"):
            preview_companies = enricher._get_companies_to_enrich(min(enrich_limit, 20), only_unenriched)
            if preview_companies:
                st.dataframe([{
                    'Nom': c.get('name'),
                    'SIREN': c.get('siren'),
                    'Taille': c.get('size'),
                    'Enrichi': '✅' if c.get('enriched_at') else '❌'
                } for c in preview_companies], use_container_width=True)
            else:
                st.info("Aucune entreprise à enrichir (vérifiez les filtres)")

        # Bouton enrichissement
        if st.button("🔍 ENRICHIR", type="primary", use_container_width=True):
            if source == 'pappers' and not pappers_key:
                st.error("❌ PAPPERS_API_KEY requise pour Pappers")
            else:
                with st.spinner(f"Enrichissement via {source.upper()} en cours..."):
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    def update_progress(current, total):
                        progress_bar.progress(current / total if total > 0 else 0)
                        status_text.text(f"Traitement: {current}/{total}")

                    report = enricher.enrich_batch(
                        source=source,
                        limit=enrich_limit,
                        only_unenriched=only_unenriched,
                        progress_callback=update_progress
                    )

                    progress_bar.progress(1.0)

                # Résultats
                if report['success']:
                    st.success("✅ Enrichissement terminé!")

                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.metric("Traitées", report['total_processed'])

                    with col2:
                        st.metric("Enrichies", report['enriched'])

                    with col3:
                        st.metric("Contacts ajoutés", report['contacts_added'])

                    if report['skipped'] > 0:
                        st.info(f"ℹ️ {report['skipped']} entreprises ignorées (sans SIREN)")

                    if report['errors']:
                        with st.expander(f"⚠️ {len(report['errors'])} erreurs"):
                            for err in report['errors'][:20]:
                                st.write(f"• {err}")
                else:
                    st.error("❌ Erreur d'enrichissement")
                    for err in report.get('errors', []):
                        st.write(f"• {err}")

# =============================================================================
# TAB 5: SYNC
# =============================================================================
with tab_sync:
    st.subheader("🔄 Synchronisation HubSpot")

    # Vérifier connexion
    api_key = os.environ.get('HUBSPOT_API_KEY')

    if api_key:
        sync = HubSpotSyncV2(company_manager, contact_manager, api_key)
        if sync.is_connected():
            st.success("✅ Connecté à HubSpot")
        else:
            st.error("❌ Erreur de connexion HubSpot")
            st.stop()
    else:
        st.warning("⚠️ HUBSPOT_API_KEY non configurée")
        st.info("Configurez la variable d'environnement HUBSPOT_API_KEY pour activer la synchronisation.")
        st.stop()

    # Stats sync
    sync_stats = sync.get_sync_stats()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("🏢 À syncer", sync_stats['companies']['not_synced'])

    with col2:
        st.metric("🏢 Synced", sync_stats['companies']['synced'])

    with col3:
        st.metric("👤 À syncer", sync_stats['contacts']['not_synced'])

    with col4:
        st.metric("👤 Synced", sync_stats['contacts']['synced'])

    st.divider()

    # Mode sync
    sync_mode = st.radio(
        "Mode",
        ["🔄 Sync complète", "🏢 Entreprises uniquement", "👤 Contacts uniquement"],
        horizontal=True
    )

    # Options
    col1, col2 = st.columns(2)

    with col1:
        preview_sync = st.checkbox("👁 Preview avant sync", value=True)
        create_new = st.checkbox("✅ Créer les nouvelles entités", value=True)

    with col2:
        update_existing = st.checkbox("✅ Mettre à jour les existantes", value=True)

    # Analyse / Preview
    if st.button("🔍 ANALYSER", type="secondary"):
        with st.spinner("Analyse en cours..."):
            analysis = sync.analyze(limit=100)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Entreprises**")
            st.write(f"• À créer: {analysis['companies']['to_create']}")
            st.write(f"• À mettre à jour: {analysis['companies']['to_update']}")
            st.write(f"• À jour: {analysis['companies']['up_to_date']}")

        with col2:
            st.markdown("**Contacts**")
            st.write(f"• À créer: {analysis['contacts']['to_create']}")
            st.write(f"• À mettre à jour: {analysis['contacts']['to_update']}")
            st.write(f"• À jour: {analysis['contacts']['up_to_date']}")

        if analysis['companies']['details']:
            with st.expander("Détails entreprises"):
                st.dataframe([{
                    'Nom': d['name'],
                    'Action': d['action'],
                    'HubSpot ID': d.get('hubspot_id')
                } for d in analysis['companies']['details'][:20]])

        if analysis['contacts']['details']:
            with st.expander("Détails contacts"):
                st.dataframe([{
                    'Nom': d['name'],
                    'Action': d['action'],
                    'HubSpot ID': d.get('hubspot_id')
                } for d in analysis['contacts']['details'][:20]])

    st.divider()

    # Bouton sync
    if st.button("🔄 SYNCHRONISER", type="primary", use_container_width=True):
        sync_companies = "Entreprises" in sync_mode or "complète" in sync_mode
        sync_contacts = "Contacts" in sync_mode or "complète" in sync_mode

        with st.spinner("Synchronisation en cours..."):
            progress_bar = st.progress(0)
            status_text = st.empty()

            def update_progress(current, total, entity_type):
                progress_bar.progress(current / total if total > 0 else 0)
                status_text.text(f"Sync {entity_type}: {current}/{total}")

            report = sync.sync_all(
                companies=sync_companies,
                contacts=sync_contacts,
                progress_callback=update_progress
            )

            progress_bar.progress(1.0)

        if report['success']:
            st.success("✅ Synchronisation terminée!")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown("**Entreprises**")
                st.write(f"• Créées: {report['companies']['created']}")
                st.write(f"• Mises à jour: {report['companies']['updated']}")

            with col2:
                st.markdown("**Contacts**")
                st.write(f"• Créés: {report['contacts']['created']}")
                st.write(f"• Mis à jour: {report['contacts']['updated']}")

            with col3:
                st.markdown("**Associations**")
                st.write(f"• Créées: {report['associations']['created']}")

            if report['companies']['errors'] or report['contacts']['errors']:
                with st.expander("⚠️ Erreurs"):
                    for err in report['companies']['errors'][:10]:
                        st.write(f"• 🏢 {err}")
                    for err in report['contacts']['errors'][:10]:
                        st.write(f"• 👤 {err}")
        else:
            st.error(f"❌ Erreur: {report.get('error', 'Unknown')}")
