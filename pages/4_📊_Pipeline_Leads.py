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
    st.subheader("Vue d'ensemble")

    # Métriques principales
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("🏢 Entreprises", company_stats.get('total', 0))

    with col2:
        st.metric("👤 Contacts", contact_stats.get('total', 0))

    with col3:
        st.metric("💬 Interactions", interaction_stats.get('total', 0))

    with col4:
        synced = company_stats.get('total', 0) - company_stats.get('to_sync', 0)
        st.metric("🔄 Synced HubSpot", synced)

    st.divider()

    # Stats par source
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**📁 Par Source**")
        by_source = company_stats.get('by_source', {})
        if by_source:
            for source, count in by_source.items():
                st.write(f"• {source}: {count}")
        else:
            st.write("Aucune donnée")

    with col2:
        st.markdown("**📈 Statut Pipeline**")
        st.write(f"• À nettoyer: {company_manager.find_duplicates(limit=1).__len__()} groupes")
        st.write(f"• À enrichir: {company_stats.get('to_enrich', 0)}")
        st.write(f"• À synchroniser: {company_stats.get('to_sync', 0)}")

    st.divider()

    # Recherche
    st.subheader("🔍 Recherche")

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        search_term = st.text_input("Rechercher", placeholder="Nom, SIREN, email...")

    with col2:
        search_type = st.selectbox("Type", ["Entreprises", "Contacts"])

    with col3:
        limit = st.selectbox("Limite", [50, 100, 200, 500], index=1)

    if st.button("🔍 Chercher", type="primary"):
        if search_type == "Entreprises":
            if search_term:
                # Recherche par SIREN
                result = company_manager.find_by_siren(search_term)
                if result:
                    st.success(f"Trouvé par SIREN: {result['name']}")
                    st.json(result)
                else:
                    # Recherche par nom
                    result = company_manager.find_by_name_fuzzy(search_term, threshold=0.5)
                    if result:
                        st.success(f"Trouvé par nom: {result['name']}")
                        st.json(result)
                    else:
                        st.warning("Aucun résultat")
            else:
                # Liste
                companies = company_manager.list_all(limit=limit)
                if companies:
                    df = st.dataframe(
                        [{
                            'Nom': c.get('name'),
                            'Domain': c.get('domain'),
                            'SIREN': c.get('siren'),
                            'Ville': c.get('hq_city'),
                            'Source': c.get('source')
                        } for c in companies],
                        use_container_width=True
                    )
                else:
                    st.info("Aucune entreprise")
        else:
            if search_term:
                result = contact_manager.find_by_email(search_term)
                if result:
                    st.success(f"Trouvé: {result.get('firstname')} {result.get('lastname')}")
                    st.json(result)
                else:
                    result = contact_manager.find_by_linkedin(search_term)
                    if result:
                        st.success(f"Trouvé: {result.get('firstname')} {result.get('lastname')}")
                        st.json(result)
                    else:
                        st.warning("Aucun résultat")
            else:
                contacts = contact_manager.list_all(limit=limit)
                if contacts:
                    st.dataframe(
                        [{
                            'Prénom': c.get('firstname'),
                            'Nom': c.get('lastname'),
                            'Email': c.get('email'),
                            'Fonction': c.get('job_title'),
                            'Source': c.get('source')
                        } for c in contacts],
                        use_container_width=True
                    )
                else:
                    st.info("Aucun contact")

# =============================================================================
# TAB 2: IMPORT
# =============================================================================
with tab_import:
    st.subheader("📥 Import de données")

    # Source d'import
    import_source = st.radio(
        "Source d'import",
        ["📄 CSV (FullEnrich, Salesbot, etc.)", "🟠 HubSpot", "🔍 SIRENE"],
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
        st.info("🟠 Import depuis HubSpot - À venir")
        st.write("Cette fonctionnalité permettra d'importer les contacts et entreprises depuis HubSpot.")

    else:
        st.info("🔍 Import depuis SIRENE - À venir")
        st.write("Cette fonctionnalité permettra de rechercher et importer des entreprises depuis la base SIRENE.")

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

        if duplicates:
            st.warning(f"⚠️ {len(duplicates)} groupes de doublons détectés")

            for i, group in enumerate(duplicates[:10]):
                with st.expander(f"Groupe {i+1} - Score: {group['score']}% - {group['reason']}"):
                    if "Entreprises" in dedup_type:
                        items = group['companies']
                        st.dataframe([{
                            'Nom': c.get('name'),
                            'SIREN': c.get('siren'),
                            'Domain': c.get('domain'),
                            'Contacts': c.get('contact_count', 0)
                        } for c in items])

                        # Sélection du master
                        master_options = [f"{c.get('name')} ({c.get('uuid')[:8]})" for c in items]
                        master_choice = st.selectbox(
                            "Master (à conserver)",
                            master_options,
                            key=f"master_company_{i}"
                        )

                        if st.button(f"🔀 Fusionner le groupe {i+1}", key=f"merge_company_{i}"):
                            master_idx = master_options.index(master_choice)
                            master_uuid = items[master_idx]['uuid']
                            dup_uuids = [c['uuid'] for c in items if c['uuid'] != master_uuid]

                            result = company_manager.merge(master_uuid, dup_uuids)
                            if result['success']:
                                st.success(f"✅ Fusion réussie! {result['contacts_moved']} contacts transférés")
                                st.rerun()
                            else:
                                st.error(f"❌ Erreur: {result['errors']}")
                    else:
                        items = group['contacts']
                        st.dataframe([{
                            'Nom': f"{c.get('firstname', '')} {c.get('lastname', '')}",
                            'Email': c.get('email'),
                            'LinkedIn': c.get('linkedin_url'),
                            'Entreprise': c.get('company_name')
                        } for c in items])

                        master_options = [
                            f"{c.get('firstname', '')} {c.get('lastname', '')} ({c.get('uuid')[:8]})"
                            for c in items
                        ]
                        master_choice = st.selectbox(
                            "Master",
                            master_options,
                            key=f"master_contact_{i}"
                        )

                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button(f"🔀 Fusionner", key=f"merge_contact_{i}"):
                                master_idx = master_options.index(master_choice)
                                master_uuid = items[master_idx]['uuid']
                                dup_uuids = [c['uuid'] for c in items if c['uuid'] != master_uuid]

                                result = contact_manager.merge(master_uuid, dup_uuids)
                                if result['success']:
                                    st.success("✅ Fusion réussie!")
                                    st.rerun()
                        with col2:
                            if st.button(f"👥 Homonymes", key=f"homonym_{i}"):
                                uuids = [c['uuid'] for c in items]
                                contact_manager.mark_as_homonyms(uuids)
                                st.success("✅ Marqués comme homonymes")
                                st.rerun()
        else:
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

    # Source d'enrichissement
    enrich_source = st.radio(
        "Source d'enrichissement",
        ["📊 Pappers (SIREN → dirigeants, CA, effectifs)", "🔍 SIRENE (SIREN → adresse, APE)"],
        horizontal=True
    )

    source = 'pappers' if 'Pappers' in enrich_source else 'sirene'

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
