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
    engagement_mod = load_module('engagement_manager', 'engagement_manager.py')
    csv_importer_mod = load_module('csv_importer_v2', 'csv_importer_v2.py')
    data_cleaner_mod = load_module('data_cleaner', 'data_cleaner.py')
    hubspot_sync_mod = load_module('hubspot_sync_v2', 'hubspot_sync_v2.py')
    enrichment_mod = load_module('enrichment_service', 'enrichment_service.py')

    CompanyManagerV2 = company_mod.CompanyManagerV2
    ContactManagerV2 = contact_mod.ContactManagerV2
    EngagementManager = engagement_mod.EngagementManager
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
    engagement_mgr = EngagementManager()
    return company_mgr, contact_mgr, engagement_mgr

company_manager, contact_manager, engagement_manager = get_managers()

# Stats globales
company_stats = company_manager.get_stats()
contact_stats = contact_manager.get_stats()
engagement_stats = engagement_manager.get_stats()

# Onglets principaux
tab_vue, tab_import, tab_clean, tab_enrich, tab_qualify, tab_sync = st.tabs([
    "📊 Vue",
    "📥 Import",
    "🧹 Clean",
    "🔍 Enrich",
    "🎯 Qualify",
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
        total_interactions = engagement_stats.get('total', 0)
        st.metric("💬 Engagements", total_interactions)

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

    # Filtres en ligne - Ligne 1
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

    # Filtres en ligne - Ligne 2 (Tier, Owner, Qualification)
    col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1])

    with col1:
        filter_tier = st.selectbox("Tier", ["Tous", "Tier 1", "Tier 2", "Tier 3", "Excluded", "Non classé"], key="vue_filter_tier")

    with col2:
        # Collecter les owners uniques
        all_owners = set()
        for c in company_manager.list_all(limit=1000):
            if c.get('owner'):
                all_owners.add(c['owner'])
        owner_options = ["Tous"] + sorted(list(all_owners))
        filter_owner = st.selectbox("Owner", owner_options, key="vue_filter_owner")

    with col3:
        filter_qualification = st.selectbox("Qualification", ["Tous", "Contact", "Lead", "Transaction"], key="vue_filter_qual")

    with col4:
        filter_size = st.selectbox("Taille", ["Toutes", "1-10", "11-50", "51-200", "201-500", "501+"], key="vue_filter_size")

    with col5:
        filter_city = st.text_input("Ville", placeholder="Paris...", key="vue_filter_city")

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
                    limit=limit * 2  # Fetch more to account for filtering
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

                # Appliquer filtre Tier
                if filter_tier != "Tous":
                    tier_map = {"Tier 1": "tier_1", "Tier 2": "tier_2", "Tier 3": "tier_3", "Excluded": "excluded", "Non classé": "unclassified"}
                    target_tier = tier_map.get(filter_tier, "unclassified")
                    companies = [c for c in companies if (c.get('tier') or 'unclassified') == target_tier]

                # Appliquer filtre Owner
                if filter_owner != "Tous":
                    companies = [c for c in companies if c.get('owner') == filter_owner]

                # Appliquer filtre Taille
                if filter_size != "Toutes":
                    companies = [c for c in companies if c.get('size') == filter_size]

                # Appliquer filtre Ville
                if filter_city:
                    city_lower = filter_city.lower()
                    companies = [c for c in companies if c.get('hq_city') and city_lower in c['hq_city'].lower()]

                # Limiter le résultat final
                companies = companies[:limit]

                # Helper pour afficher le badge tier
                def get_tier_badge(tier):
                    badges = {'tier_1': '🟢', 'tier_2': '🟡', 'tier_3': '🟠', 'excluded': '⚫', 'unclassified': '⚪'}
                    return badges.get(tier or 'unclassified', '⚪')

                if companies:
                    st.write(f"**{len(companies)}** entreprises affichées")
                    st.dataframe([{
                        'Tier': get_tier_badge(c.get('tier')),
                        'Nom': c.get('name'),
                        'Domain': c.get('domain'),
                        'SIREN': c.get('siren'),
                        'Ville': c.get('hq_city'),
                        'Taille': c.get('size'),
                        'Owner': c.get('owner', '-'),
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
                    limit=limit * 2  # Fetch more for filtering
                )

                # Appliquer filtre Qualification
                if filter_qualification != "Tous":
                    qual_map = {"Contact": "contact", "Lead": "lead", "Transaction": "transaction"}
                    target_qual = qual_map.get(filter_qualification, "contact")
                    contacts = [c for c in contacts if (c.get('qualification_status') or 'contact') == target_qual]

                # Limiter
                contacts = contacts[:limit]

                # Helper pour badge qualification
                def get_qual_badge(status):
                    badges = {'contact': '⚪', 'lead': '🟡', 'transaction': '🟢'}
                    return badges.get(status or 'contact', '⚪')

                if contacts:
                    st.write(f"**{len(contacts)}** contacts affichés")
                    st.dataframe([{
                        'Qual': get_qual_badge(c.get('qualification_status')),
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

    # =========================================================================
    # FICHE ENTREPRISE (Sprint 4.4)
    # =========================================================================
    st.divider()
    st.markdown("### 🏢 Fiche Entreprise")

    col1, col2 = st.columns([3, 1])
    with col1:
        company_detail_search = st.text_input(
            "Rechercher une entreprise",
            placeholder="Nom, SIREN, UUID...",
            key="company_detail_search"
        )
    with col2:
        if st.button("🔍 Afficher fiche", key="show_company_detail"):
            st.session_state['show_company_detail'] = True

    if st.session_state.get('show_company_detail') and company_detail_search:
        # Chercher l'entreprise
        found_company = None

        # Par SIREN
        found_company = company_manager.find_by_siren(company_detail_search)

        # Par nom
        if not found_company:
            found_company = company_manager.find_by_name_fuzzy(company_detail_search, threshold=0.8)

        # Par UUID (si format UUID)
        if not found_company and len(company_detail_search) == 36:
            try:
                found_company = company_manager.get_by_uuid(company_detail_search)
            except:
                pass

        if found_company:
            # Helper pour badge tier
            def get_tier_display(tier):
                badges = {
                    'tier_1': '🟢 Tier 1',
                    'tier_2': '🟡 Tier 2',
                    'tier_3': '🟠 Tier 3',
                    'excluded': '⚫ Excluded',
                    'unclassified': '⚪ Non classé'
                }
                return badges.get(tier or 'unclassified', '⚪ Non classé')

            # Header
            st.markdown(f"## 🏢 {found_company.get('name', 'N/A')}")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**Tier:** {get_tier_display(found_company.get('tier'))}")
            with col2:
                st.write(f"**Owner:** {found_company.get('owner', 'Non assigné')}")
            with col3:
                st.write(f"**Source:** {found_company.get('source', '-')}")

            # Sous-onglets
            fiche_tab1, fiche_tab2, fiche_tab3, fiche_tab4 = st.tabs([
                "📋 Infos",
                "👤 Contacts",
                "💬 Engagements",
                "⚙️ Actions"
            ])

            with fiche_tab1:
                st.markdown("#### Informations générales")
                col1, col2 = st.columns(2)

                with col1:
                    st.write(f"**SIREN:** {found_company.get('siren', '-')}")
                    st.write(f"**Domaine:** {found_company.get('domain', '-')}")
                    st.write(f"**Taille:** {found_company.get('size', '-')}")
                    st.write(f"**Secteur:** {found_company.get('industry', '-')}")
                    st.write(f"**CA:** {found_company.get('revenue', '-')}")

                with col2:
                    st.write(f"**Ville:** {found_company.get('hq_city', '-')}")
                    st.write(f"**Pays:** {found_company.get('hq_country', '-')}")
                    st.write(f"**Forme juridique:** {found_company.get('legal_form', '-')}")
                    st.write(f"**Code APE:** {found_company.get('ape_code', '-')}")
                    st.write(f"**Website:** {found_company.get('website', '-')}")

                st.markdown("#### Statuts")
                col1, col2, col3 = st.columns(3)
                with col1:
                    enriched = "✅" if found_company.get('enriched_at') else "❌"
                    st.write(f"**Enrichi:** {enriched}")
                with col2:
                    synced = "✅" if found_company.get('synced_to_hubspot') else "❌"
                    st.write(f"**Synced HubSpot:** {synced}")
                with col3:
                    st.write(f"**Source tag:** {found_company.get('source_tag', '-')}")

            with fiche_tab2:
                st.markdown("#### Contacts liés")
                # Récupérer les contacts de cette entreprise
                company_contacts = contact_manager.list_by_company(found_company['uuid'])

                if company_contacts:
                    for contact in company_contacts:
                        qual_badge = {'contact': '⚪', 'lead': '🟡', 'transaction': '🟢'}.get(
                            contact.get('qualification_status', 'contact'), '⚪'
                        )
                        name = f"{contact.get('firstname', '')} {contact.get('lastname', '')}".strip()
                        col1, col2, col3, col4 = st.columns([0.5, 3, 2, 2])
                        with col1:
                            st.write(qual_badge)
                        with col2:
                            st.write(f"**{name}**")
                        with col3:
                            st.write(contact.get('email', '-'))
                        with col4:
                            st.write(contact.get('job_title', '-'))
                else:
                    st.info("Aucun contact lié à cette entreprise")

            with fiche_tab3:
                st.markdown("#### Historique des engagements")
                # Récupérer les engagements
                company_engagements = engagement_manager.list_by_company(found_company['uuid'], limit=20)

                if company_engagements:
                    for eng in company_engagements:
                        eng_type = eng.get('type', 'note')
                        eng_date = eng.get('interaction_date', eng.get('created_at', ''))[:10] if eng.get('interaction_date') or eng.get('created_at') else '-'
                        eng_icon = {'email': '📧', 'call': '📞', 'meeting': '📅', 'linkedin_message_sent': '💼', 'linkedin_reply_received': '📥', 'note': '📝'}.get(eng_type, '📋')

                        col1, col2, col3 = st.columns([1, 1, 4])
                        with col1:
                            st.write(f"{eng_icon} {eng_date}")
                        with col2:
                            st.write(eng_type)
                        with col3:
                            content = eng.get('content', '')
                            st.write(content[:100] + '...' if len(content) > 100 else content if content else '-')
                else:
                    st.info("Aucun engagement enregistré")

            with fiche_tab4:
                st.markdown("#### Actions rapides")

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    new_tier = st.selectbox(
                        "Changer Tier",
                        ["-- Sélectionner --", "tier_1", "tier_2", "tier_3", "excluded"],
                        key="fiche_change_tier"
                    )
                    if st.button("Appliquer Tier", key="fiche_apply_tier"):
                        if new_tier != "-- Sélectionner --":
                            company_manager.update(found_company['uuid'], {'tier': new_tier})
                            st.success(f"✅ Tier changé en {new_tier}")
                            st.rerun()

                with col2:
                    new_owner = st.text_input("Assigner Owner", key="fiche_new_owner")
                    if st.button("Appliquer Owner", key="fiche_apply_owner"):
                        if new_owner:
                            company_manager.update(found_company['uuid'], {'owner': new_owner})
                            st.success(f"✅ Owner assigné: {new_owner}")
                            st.rerun()

                with col3:
                    if st.button("🔍 Enrichir", key="fiche_enrich"):
                        if found_company.get('siren'):
                            result = enricher.enrich_company(found_company['uuid'], source='pappers')
                            if result.get('success'):
                                st.success("✅ Entreprise enrichie!")
                            else:
                                st.error(f"❌ {result.get('error', 'Erreur')}")
                        else:
                            st.warning("⚠️ SIREN requis pour l'enrichissement")

                with col4:
                    if st.button("🔄 Sync HubSpot", key="fiche_sync"):
                        st.info("Sync individuelle non implémentée - utilisez l'onglet Sync")

        else:
            st.warning("❌ Aucune entreprise trouvée avec cette recherche")

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

            st.divider()

            # =====================================================
            # SOURCE TAG (Sprint 3.2)
            # =====================================================
            st.markdown("### 🏷️ Tag source business")
            col1, col2 = st.columns([3, 2])
            with col1:
                source_tag = st.text_input(
                    "Tag d'origine",
                    placeholder="Ex: Salon VivaTech 2024, LinkedIn Ads, Cold List...",
                    key="csv_source_tag",
                    help="Tag business pour identifier la provenance de ce fichier"
                )
            with col2:
                st.caption("Ce tag sera appliqué à toutes les entreprises et contacts importés")

            st.divider()

            # =====================================================
            # MAPPING MANUEL DES COLONNES (Sprint 3.1)
            # =====================================================
            st.markdown("### 📋 Mapping des colonnes")

            # Champs disponibles pour le mapping
            company_fields = [
                "-- Ignorer --",
                "companies.name", "companies.siren", "companies.domain",
                "companies.hq_address", "companies.hq_city", "companies.hq_postal_code",
                "companies.size", "companies.industry", "companies.phone",
                "companies.website", "companies.linkedin_url"
            ]
            contact_fields = [
                "contacts.firstname", "contacts.lastname", "contacts.email",
                "contacts.phone", "contacts.job_title", "contacts.linkedin_url",
                "contacts.seniority"
            ]
            engagement_fields = [
                "engagements.interaction_date", "engagements.content", "engagements.type"
            ]
            all_fields = company_fields + contact_fields + engagement_fields

            # Initialiser le mapping depuis la session ou la détection
            if 'csv_mapping' not in st.session_state or st.session_state.get('csv_file_name') != uploaded_file.name:
                st.session_state['csv_mapping'] = detection['suggested_mapping'].copy()
                st.session_state['csv_file_name'] = uploaded_file.name

            # Mode de mapping
            mapping_mode = st.radio(
                "Mode de mapping",
                ["🤖 Automatique (avec ajustements)", "✏️ Manuel complet"],
                horizontal=True,
                key="csv_mapping_mode"
            )

            if "Automatique" in mapping_mode:
                # Afficher le mapping auto avec possibilité de modifier
                st.markdown("**Mapping détecté** (modifiable)")

                # Colonnes mappées
                csv_columns = list(detection['suggested_mapping'].keys()) + detection['unmapped']

                # Afficher en 2 colonnes
                col1, col2 = st.columns(2)
                mapping_updates = {}

                for i, csv_col in enumerate(csv_columns[:20]):  # Limiter à 20 colonnes affichées
                    target_col = col1 if i % 2 == 0 else col2

                    with target_col:
                        current_mapping = st.session_state['csv_mapping'].get(csv_col, "-- Ignorer --")
                        # Trouver l'index du mapping actuel
                        try:
                            default_idx = all_fields.index(current_mapping)
                        except ValueError:
                            default_idx = 0

                        new_mapping = st.selectbox(
                            f"`{csv_col}`",
                            all_fields,
                            index=default_idx,
                            key=f"map_{i}_{csv_col[:20]}"
                        )

                        if new_mapping != "-- Ignorer --":
                            mapping_updates[csv_col] = new_mapping

                # Mettre à jour le mapping
                st.session_state['csv_mapping'] = mapping_updates

                if len(csv_columns) > 20:
                    st.caption(f"... et {len(csv_columns) - 20} autres colonnes (non affichées)")

            else:
                # Mode manuel complet - afficher toutes les colonnes
                st.markdown("**Mapping manuel**")
                st.warning("⚠️ Mode manuel: vérifiez chaque colonne avant d'importer")

                csv_columns = list(detection['all_columns']) if 'all_columns' in detection else list(detection['suggested_mapping'].keys()) + detection['unmapped']

                mapping_updates = {}
                for i, csv_col in enumerate(csv_columns):
                    col1, col2, col3 = st.columns([3, 3, 1])

                    with col1:
                        st.write(f"`{csv_col}`")

                    with col2:
                        current_mapping = st.session_state['csv_mapping'].get(csv_col, "-- Ignorer --")
                        try:
                            default_idx = all_fields.index(current_mapping)
                        except ValueError:
                            default_idx = 0

                        new_mapping = st.selectbox(
                            "→",
                            all_fields,
                            index=default_idx,
                            key=f"manual_map_{i}",
                            label_visibility="collapsed"
                        )

                        if new_mapping != "-- Ignorer --":
                            mapping_updates[csv_col] = new_mapping

                    with col3:
                        if new_mapping == "-- Ignorer --":
                            st.write("❌")
                        elif new_mapping.startswith("companies"):
                            st.write("🏢")
                        elif new_mapping.startswith("contacts"):
                            st.write("👤")
                        else:
                            st.write("💬")

                st.session_state['csv_mapping'] = mapping_updates

            st.divider()

            # Résumé du mapping
            mapping_summary = st.session_state.get('csv_mapping', {})
            company_mapped = sum(1 for v in mapping_summary.values() if v.startswith('companies'))
            contact_mapped = sum(1 for v in mapping_summary.values() if v.startswith('contacts'))
            engagement_mapped = sum(1 for v in mapping_summary.values() if v.startswith('engagements'))

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🏢 Champs entreprise", company_mapped)
            with col2:
                st.metric("👤 Champs contact", contact_mapped)
            with col3:
                st.metric("💬 Champs engagement", engagement_mapped)

            st.divider()

            # Options d'import
            st.markdown("### ⚙️ Options d'import")
            col1, col2, col3 = st.columns(3)

            with col1:
                smart_matching = st.checkbox("✅ Matching intelligent (éviter doublons)", value=True)

            with col2:
                create_companies = st.checkbox("✅ Créer les entreprises manquantes", value=True)

            with col3:
                preview_mode = st.checkbox("👁 Mode preview (sans import)", value=False)

            # Bouton d'import
            if st.button("📥 IMPORTER", type="primary", use_container_width=True):
                # Construire le mapping final
                final_mapping = st.session_state.get('csv_mapping', detection['suggested_mapping'])

                with st.spinner("Import en cours..."):
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    def update_progress(current, total):
                        progress_bar.progress(current / total if total > 0 else 0)
                        status_text.text(f"Traitement: {current}/{total}")

                    report = importer.import_file(
                        tmp_path,
                        mapping=final_mapping,
                        source_name=uploaded_file.name,
                        source_tag=source_tag if source_tag else None,
                        preview_only=preview_mode,
                        create_companies=create_companies,
                        smart_matching=smart_matching,
                        progress_callback=update_progress
                    )

                    progress_bar.progress(1.0)

                # Résultat
                if report['success']:
                    st.success("✅ Import terminé!")

                    col1, col2, col3 = st.columns(3)
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

                    with col3:
                        st.markdown("**Engagements**")
                        eng_created = report.get('engagements', {}).get('created', 0)
                        st.write(f"• Créés: {eng_created}")

                    if source_tag:
                        st.info(f"🏷️ Tag source appliqué: **{source_tag}**")

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
                hs_importer = HubSpotImportV2(company_manager, contact_manager, engagement_manager, api_key)

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
                                    st.markdown("**Engagements**")
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
                gs_importer = GetSalesImportV2(company_manager, contact_manager, engagement_manager, api_key)

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

                            if report.get('engagements', {}).get('created', 0) > 0:
                                st.info(f"💬 {report['engagements']['created']} interactions importées")

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
            # Reset checkbox states
            for key in list(st.session_state.keys()):
                if key.startswith('enrich_company_'):
                    del st.session_state[key]

        # Afficher les entreprises avec checkboxes
        if 'enrich_companies' in st.session_state and st.session_state['enrich_companies']:
            companies = st.session_state['enrich_companies']

            st.write(f"**{len(companies)}** entreprises affichées")

            # ÉTAPE 1: D'abord afficher les checkboxes pour capturer leur état
            st.divider()

            # Liste des entreprises avec checkboxes - AVANT les actions
            checkbox_states = {}
            for i, company in enumerate(companies):
                col1, col2, col3, col4, col5 = st.columns([0.5, 3, 2, 2, 1])

                with col1:
                    # Lire l'état précédent du checkbox depuis session_state
                    checkbox_key = f"enrich_company_{i}"
                    is_checked = st.checkbox("", key=checkbox_key)
                    checkbox_states[i] = is_checked

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

            # ÉTAPE 2: Calculer le compte APRÈS les checkboxes
            selected_indices = [i for i, checked in checkbox_states.items() if checked]
            selected_count = len(selected_indices)

            st.divider()

            # ÉTAPE 3: Afficher les actions avec le bon compte
            col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

            with col1:
                if st.button("☑️ Tout sélectionner", key="select_all_enrich_btn"):
                    # Sélectionner tous - mettre tous les checkboxes à True
                    for i in range(len(companies)):
                        st.session_state[f"enrich_company_{i}"] = True
                    st.rerun()

            with col2:
                st.write(f"**{selected_count}** sélectionnées")

            with col3:
                if st.button("🗑️ Effacer sélection"):
                    for i in range(len(companies)):
                        st.session_state[f"enrich_company_{i}"] = False
                    st.rerun()

            with col4:
                enrich_btn_disabled = selected_count == 0
                if st.button(f"🔍 ENRICHIR ({selected_count})", type="primary", disabled=enrich_btn_disabled):
                    if source == 'pappers' and not pappers_key:
                        st.error("❌ PAPPERS_API_KEY requise pour Pappers")
                    else:
                        # Récupérer les entreprises sélectionnées
                        selected_companies = [companies[i] for i in selected_indices]

                        with st.spinner(f"Enrichissement via {source.upper()} en cours..."):
                            progress_bar = st.progress(0)
                            status_text = st.empty()

                            enriched = 0
                            errors = []
                            contacts_added = 0

                            for idx, company in enumerate(selected_companies):
                                progress_bar.progress((idx + 1) / len(selected_companies))
                                status_text.text(f"Traitement: {company.get('name', 'N/A')} ({idx+1}/{len(selected_companies)})")

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
                        for key in list(st.session_state.keys()):
                            if key.startswith('enrich_company_'):
                                del st.session_state[key]
                        st.rerun()

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
            # Récupérer toutes les entreprises pour diagnostic
            all_companies = company_manager.list_all(status='active', limit=min(enrich_limit * 2, 200))

            # Filtrer par statut enrichissement
            if only_unenriched:
                filtered_companies = [c for c in all_companies if not c.get('enriched_at')]
            else:
                filtered_companies = all_companies

            # Compter celles avec SIREN
            with_siren = [c for c in filtered_companies if c.get('siren')]
            without_siren = len(filtered_companies) - len(with_siren)

            if with_siren:
                st.write(f"**{len(with_siren)}** entreprises avec SIREN (enrichissables)")
                if without_siren > 0:
                    st.caption(f"⚠️ {without_siren} entreprises sans SIREN (non enrichissables)")

                st.dataframe([{
                    'Nom': c.get('name'),
                    'SIREN': c.get('siren'),
                    'Taille': c.get('size'),
                    'Enrichi': '✅' if c.get('enriched_at') else '❌'
                } for c in with_siren[:20]], use_container_width=True)
            elif filtered_companies:
                st.warning(f"⚠️ {len(filtered_companies)} entreprises trouvées mais **aucune n'a de SIREN**")
                st.info("💡 Le mode batch nécessite un SIREN pour enrichir. Utilisez le mode manuel pour voir toutes les entreprises.")
            else:
                st.info("Aucune entreprise à enrichir (toutes déjà enrichies ou aucune importée)")

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
# TAB 5: QUALIFY (Tier & Qualification)
# =============================================================================
with tab_qualify:
    st.subheader("🎯 Classification & Qualification")

    # Sous-onglets pour Tier et Qualification
    qual_tab_tier, qual_tab_contacts = st.tabs(["🏢 Tier Entreprises", "👤 Qualification Contacts"])

    # -------------------------------------------------------------------------
    # TIER ENTREPRISES
    # -------------------------------------------------------------------------
    with qual_tab_tier:
        st.markdown("### 🎯 Classification Tier / ICP")

        # Stats par Tier
        all_companies_for_tier = company_manager.list_all(status='active', limit=5000)
        tier_counts = {'tier_1': 0, 'tier_2': 0, 'tier_3': 0, 'excluded': 0, 'unclassified': 0}
        for c in all_companies_for_tier:
            tier = c.get('tier', 'unclassified') or 'unclassified'
            if tier in tier_counts:
                tier_counts[tier] += 1
            else:
                tier_counts['unclassified'] += 1

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("🟢 Tier 1", tier_counts['tier_1'])
        with col2:
            st.metric("🟡 Tier 2", tier_counts['tier_2'])
        with col3:
            st.metric("🟠 Tier 3", tier_counts['tier_3'])
        with col4:
            st.metric("⚫ Excluded", tier_counts['excluded'])
        with col5:
            st.metric("⚪ Non classé", tier_counts['unclassified'])

        st.divider()

        # Filtres
        st.markdown("**Filtres de recherche**")
        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])

        with col1:
            tier_search = st.text_input("🔍 Recherche", placeholder="Nom, SIREN...", key="tier_search")

        with col2:
            tier_filter_current = st.selectbox(
                "Tier actuel",
                ["Tous", "Non classé", "Tier 1", "Tier 2", "Tier 3", "Excluded"],
                key="tier_filter_current"
            )

        with col3:
            tier_filter_size = st.selectbox(
                "Taille",
                ["Toutes", "1-10", "11-50", "51-200", "201-500", "501+"],
                key="tier_filter_size"
            )

        with col4:
            tier_filter_enriched = st.selectbox(
                "Enrichi",
                ["Tous", "Oui", "Non"],
                key="tier_filter_enriched"
            )

        with col5:
            tier_display_limit = st.selectbox("Limite", [25, 50, 100], key="tier_display_limit")

        # Bouton charger
        if st.button("🔍 CHARGER ENTREPRISES", key="load_tier_companies"):
            companies_tier = company_manager.list_all(status='active', limit=tier_display_limit * 2)

            # Appliquer filtres
            if tier_search:
                search_lower = tier_search.lower()
                companies_tier = [c for c in companies_tier if
                    (c.get('name') and search_lower in c['name'].lower()) or
                    (c.get('siren') and search_lower in c['siren'])
                ]

            if tier_filter_current != "Tous":
                tier_map = {"Non classé": "unclassified", "Tier 1": "tier_1", "Tier 2": "tier_2", "Tier 3": "tier_3", "Excluded": "excluded"}
                target_tier = tier_map.get(tier_filter_current, "unclassified")
                companies_tier = [c for c in companies_tier if (c.get('tier') or 'unclassified') == target_tier]

            if tier_filter_size != "Toutes":
                companies_tier = [c for c in companies_tier if c.get('size') == tier_filter_size]

            if tier_filter_enriched == "Oui":
                companies_tier = [c for c in companies_tier if c.get('enriched_at')]
            elif tier_filter_enriched == "Non":
                companies_tier = [c for c in companies_tier if not c.get('enriched_at')]

            companies_tier = companies_tier[:tier_display_limit]
            st.session_state['tier_companies'] = companies_tier

            # Reset checkbox states
            for key in list(st.session_state.keys()):
                if key.startswith('tier_company_'):
                    del st.session_state[key]

        # Afficher les entreprises
        if 'tier_companies' in st.session_state and st.session_state['tier_companies']:
            companies_tier = st.session_state['tier_companies']

            st.write(f"**{len(companies_tier)}** entreprises")
            st.divider()

            # Helper pour badge tier
            def tier_badge(tier):
                badges = {
                    'tier_1': '🟢 T1',
                    'tier_2': '🟡 T2',
                    'tier_3': '🟠 T3',
                    'excluded': '⚫ Excl',
                    'unclassified': '⚪ -'
                }
                return badges.get(tier or 'unclassified', '⚪ -')

            # Liste avec checkboxes
            tier_checkbox_states = {}
            for i, company in enumerate(companies_tier):
                col1, col2, col3, col4, col5, col6 = st.columns([0.5, 3, 1.5, 1.5, 1.5, 1])

                with col1:
                    is_checked = st.checkbox("", key=f"tier_company_{i}")
                    tier_checkbox_states[i] = is_checked

                with col2:
                    st.write(f"**{company.get('name', 'N/A')}**")

                with col3:
                    st.write(company.get('size', '-'))

                with col4:
                    st.write(company.get('hq_city', '-'))

                with col5:
                    st.write(company.get('industry', '-'))

                with col6:
                    st.write(tier_badge(company.get('tier')))

            # Actions de classification
            tier_selected_indices = [i for i, checked in tier_checkbox_states.items() if checked]
            tier_selected_count = len(tier_selected_indices)

            st.divider()

            col1, col2, col3, col4, col5, col6 = st.columns([2, 1.5, 1.5, 1.5, 1.5, 1.5])

            with col1:
                if st.button("☑️ Tout sélectionner", key="tier_select_all"):
                    for i in range(len(companies_tier)):
                        st.session_state[f"tier_company_{i}"] = True
                    st.rerun()

            with col2:
                st.write(f"**{tier_selected_count}** sélect.")

            # Boutons de classification
            with col3:
                if st.button("🟢 Tier 1", disabled=tier_selected_count == 0, key="set_tier1"):
                    for i in tier_selected_indices:
                        company_manager.update(companies_tier[i]['uuid'], {'tier': 'tier_1'})
                    st.success(f"✅ {tier_selected_count} entreprises → Tier 1")
                    del st.session_state['tier_companies']
                    st.rerun()

            with col4:
                if st.button("🟡 Tier 2", disabled=tier_selected_count == 0, key="set_tier2"):
                    for i in tier_selected_indices:
                        company_manager.update(companies_tier[i]['uuid'], {'tier': 'tier_2'})
                    st.success(f"✅ {tier_selected_count} entreprises → Tier 2")
                    del st.session_state['tier_companies']
                    st.rerun()

            with col5:
                if st.button("🟠 Tier 3", disabled=tier_selected_count == 0, key="set_tier3"):
                    for i in tier_selected_indices:
                        company_manager.update(companies_tier[i]['uuid'], {'tier': 'tier_3'})
                    st.success(f"✅ {tier_selected_count} entreprises → Tier 3")
                    del st.session_state['tier_companies']
                    st.rerun()

            with col6:
                if st.button("⚫ Exclure", disabled=tier_selected_count == 0, key="set_excluded"):
                    for i in tier_selected_indices:
                        company_manager.update(companies_tier[i]['uuid'], {'tier': 'excluded'})
                    st.success(f"✅ {tier_selected_count} entreprises exclues")
                    del st.session_state['tier_companies']
                    st.rerun()

            # =========================================================
            # OWNER ASSIGNMENT (Sprint 5.1)
            # =========================================================
            st.divider()
            st.markdown("**👤 Assignation Owner**")

            col1, col2, col3 = st.columns([2, 2, 1])

            with col1:
                # Liste des owners existants
                existing_owners = set()
                for c in companies_tier:
                    if c.get('owner'):
                        existing_owners.add(c['owner'])
                owner_suggestions = ["-- Sélectionner --"] + sorted(list(existing_owners))
                selected_owner = st.selectbox("Owner existant", owner_suggestions, key="tier_owner_select")

            with col2:
                new_owner_input = st.text_input("Ou nouvel owner", placeholder="email ou nom...", key="tier_new_owner")

            with col3:
                owner_to_assign = new_owner_input if new_owner_input else (selected_owner if selected_owner != "-- Sélectionner --" else None)
                if st.button("👤 Assigner", disabled=tier_selected_count == 0 or not owner_to_assign, key="tier_assign_owner"):
                    if owner_to_assign:
                        for i in tier_selected_indices:
                            company_manager.update(companies_tier[i]['uuid'], {'owner': owner_to_assign})
                        st.success(f"✅ {tier_selected_count} entreprises → Owner: {owner_to_assign}")
                        del st.session_state['tier_companies']
                        st.rerun()

        elif 'tier_companies' in st.session_state:
            st.info("Aucune entreprise ne correspond aux filtres")
        else:
            st.info("Cliquez sur 'CHARGER ENTREPRISES' pour afficher la liste")

    # -------------------------------------------------------------------------
    # QUALIFICATION CONTACTS
    # -------------------------------------------------------------------------
    with qual_tab_contacts:
        st.markdown("### 👤 Qualification Contact → Lead → Transaction")

        # Stats par statut
        all_contacts_for_qual = contact_manager.list_all(status='active', limit=5000)
        qual_counts = {'contact': 0, 'lead': 0, 'transaction': 0}
        for c in all_contacts_for_qual:
            status = c.get('qualification_status', 'contact') or 'contact'
            if status in qual_counts:
                qual_counts[status] += 1
            else:
                qual_counts['contact'] += 1

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("⚪ Contacts", qual_counts['contact'])
        with col2:
            st.metric("🟡 Leads", qual_counts['lead'])
        with col3:
            st.metric("🟢 Transactions", qual_counts['transaction'])

        st.divider()

        # Filtres
        st.markdown("**Filtres de recherche**")
        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])

        with col1:
            qual_search = st.text_input("🔍 Recherche", placeholder="Nom, email...", key="qual_search")

        with col2:
            qual_filter_status = st.selectbox(
                "Statut",
                ["Tous", "Contact", "Lead", "Transaction"],
                key="qual_filter_status"
            )

        with col3:
            qual_filter_has_email = st.selectbox(
                "Email",
                ["Tous", "Avec email", "Sans email"],
                key="qual_filter_email"
            )

        with col4:
            qual_display_limit = st.selectbox("Limite", [25, 50, 100], key="qual_display_limit")

        # Bouton charger
        if st.button("🔍 CHARGER CONTACTS", key="load_qual_contacts"):
            contacts_qual = contact_manager.list_all(status='active', limit=qual_display_limit * 2)

            # Appliquer filtres
            if qual_search:
                search_lower = qual_search.lower()
                contacts_qual = [c for c in contacts_qual if
                    (c.get('firstname') and search_lower in c['firstname'].lower()) or
                    (c.get('lastname') and search_lower in c['lastname'].lower()) or
                    (c.get('email') and search_lower in c['email'].lower())
                ]

            if qual_filter_status != "Tous":
                status_map = {"Contact": "contact", "Lead": "lead", "Transaction": "transaction"}
                target_status = status_map.get(qual_filter_status, "contact")
                contacts_qual = [c for c in contacts_qual if (c.get('qualification_status') or 'contact') == target_status]

            if qual_filter_has_email == "Avec email":
                contacts_qual = [c for c in contacts_qual if c.get('email')]
            elif qual_filter_has_email == "Sans email":
                contacts_qual = [c for c in contacts_qual if not c.get('email')]

            contacts_qual = contacts_qual[:qual_display_limit]
            st.session_state['qual_contacts'] = contacts_qual

            # Reset checkbox states
            for key in list(st.session_state.keys()):
                if key.startswith('qual_contact_'):
                    del st.session_state[key]

        # Afficher les contacts
        if 'qual_contacts' in st.session_state and st.session_state['qual_contacts']:
            contacts_qual = st.session_state['qual_contacts']

            st.write(f"**{len(contacts_qual)}** contacts")
            st.divider()

            # Helper pour badge qualification
            def qual_badge(status):
                badges = {
                    'contact': '⚪ Contact',
                    'lead': '🟡 Lead',
                    'transaction': '🟢 Transaction'
                }
                return badges.get(status or 'contact', '⚪ Contact')

            # Liste avec checkboxes
            qual_checkbox_states = {}
            for i, contact in enumerate(contacts_qual):
                col1, col2, col3, col4, col5 = st.columns([0.5, 3, 2, 2, 1.5])

                with col1:
                    is_checked = st.checkbox("", key=f"qual_contact_{i}")
                    qual_checkbox_states[i] = is_checked

                with col2:
                    name = f"{contact.get('firstname', '')} {contact.get('lastname', '')}".strip() or 'N/A'
                    st.write(f"**{name}**")

                with col3:
                    st.write(contact.get('email', '-'))

                with col4:
                    st.write(contact.get('job_title', '-'))

                with col5:
                    st.write(qual_badge(contact.get('qualification_status')))

            # Actions de qualification
            qual_selected_indices = [i for i, checked in qual_checkbox_states.items() if checked]
            qual_selected_count = len(qual_selected_indices)

            st.divider()

            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 2])

            with col1:
                if st.button("☑️ Tout sélectionner", key="qual_select_all"):
                    for i in range(len(contacts_qual)):
                        st.session_state[f"qual_contact_{i}"] = True
                    st.rerun()

            with col2:
                st.write(f"**{qual_selected_count}** sélect.")

            # Boutons de qualification
            with col3:
                if st.button("⚪ Contact", disabled=qual_selected_count == 0, key="set_contact"):
                    for i in qual_selected_indices:
                        contact_manager.update(contacts_qual[i]['uuid'], {'qualification_status': 'contact'})
                    st.success(f"✅ {qual_selected_count} → Contact")
                    del st.session_state['qual_contacts']
                    st.rerun()

            with col4:
                if st.button("🟡 Lead", disabled=qual_selected_count == 0, key="set_lead"):
                    for i in qual_selected_indices:
                        contact_manager.update(contacts_qual[i]['uuid'], {'qualification_status': 'lead'})
                    st.success(f"✅ {qual_selected_count} → Lead")
                    del st.session_state['qual_contacts']
                    st.rerun()

            with col5:
                if st.button("🟢 Transaction", disabled=qual_selected_count == 0, key="set_transaction"):
                    for i in qual_selected_indices:
                        contact_manager.update(contacts_qual[i]['uuid'], {'qualification_status': 'transaction'})
                    st.success(f"✅ {qual_selected_count} → Transaction")
                    del st.session_state['qual_contacts']
                    st.rerun()

        elif 'qual_contacts' in st.session_state:
            st.info("Aucun contact ne correspond aux filtres")
        else:
            st.info("Cliquez sur 'CHARGER CONTACTS' pour afficher la liste")

# =============================================================================
# TAB 6: SYNC
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

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        st.metric("🏢 À syncer", sync_stats['companies']['not_synced'])
    with col2:
        st.metric("🏢 Synced", sync_stats['companies']['synced'])
    with col3:
        st.metric("👤 À syncer", sync_stats['contacts']['not_synced'])
    with col4:
        st.metric("👤 Synced", sync_stats['contacts']['synced'])
    with col5:
        eng_total = engagement_stats.get('total', 0)
        st.metric("💬 Engagements", eng_total)
    with col6:
        eng_synced = engagement_stats.get('synced', 0)
        st.metric("💬 Synced", eng_synced)

    st.divider()

    # =========================================================================
    # QUALITY GATE (Sprint 4.1)
    # =========================================================================
    st.markdown("### 🔍 Quality Gate - Analyse avant sync")

    if st.button("🔍 ANALYSER QUALITÉ", type="secondary"):
        with st.spinner("Analyse qualité en cours..."):
            # Récupérer les données à analyser
            companies_to_check = company_manager.list_all(status='active', limit=1000)
            contacts_to_check = contact_manager.list_all(status='active', limit=1000)
            engagements_to_check = engagement_manager.list_all(limit=1000)

            # Warnings entreprises
            warnings_companies = {
                'no_siren': [],
                'unclassified_tier': [],
                'no_domain': [],
            }
            for c in companies_to_check:
                if not c.get('siren'):
                    warnings_companies['no_siren'].append(c.get('name', 'N/A'))
                if (c.get('tier') or 'unclassified') == 'unclassified':
                    warnings_companies['unclassified_tier'].append(c.get('name', 'N/A'))
                if not c.get('domain'):
                    warnings_companies['no_domain'].append(c.get('name', 'N/A'))

            # Warnings contacts
            warnings_contacts = {
                'no_email': [],
                'no_company': [],
                'contact_status': [],
            }
            for c in contacts_to_check:
                if not c.get('email') and not c.get('phone') and not c.get('linkedin_url'):
                    name = f"{c.get('firstname', '')} {c.get('lastname', '')}".strip() or 'N/A'
                    warnings_contacts['no_email'].append(name)
                if not c.get('company_uuid'):
                    name = f"{c.get('firstname', '')} {c.get('lastname', '')}".strip() or 'N/A'
                    warnings_contacts['no_company'].append(name)
                if (c.get('qualification_status') or 'contact') == 'contact':
                    name = f"{c.get('firstname', '')} {c.get('lastname', '')}".strip() or 'N/A'
                    warnings_contacts['contact_status'].append(name)

        # Afficher les résultats
        st.session_state['quality_gate_done'] = True

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**🏢 Entreprises**")
            total_companies = len(companies_to_check)
            st.write(f"Total: **{total_companies}**")

            if warnings_companies['no_siren']:
                st.warning(f"⚠️ {len(warnings_companies['no_siren'])} sans SIREN")
            if warnings_companies['unclassified_tier']:
                st.warning(f"⚠️ {len(warnings_companies['unclassified_tier'])} Tier non défini")
            if warnings_companies['no_domain']:
                st.caption(f"ℹ️ {len(warnings_companies['no_domain'])} sans domain")

            if not warnings_companies['no_siren'] and not warnings_companies['unclassified_tier']:
                st.success("✅ Qualité OK")

        with col2:
            st.markdown("**👤 Contacts**")
            total_contacts = len(contacts_to_check)
            st.write(f"Total: **{total_contacts}**")

            if warnings_contacts['no_email']:
                st.warning(f"⚠️ {len(warnings_contacts['no_email'])} sans coordonnées")
            if warnings_contacts['no_company']:
                st.warning(f"⚠️ {len(warnings_contacts['no_company'])} sans entreprise liée")
            if warnings_contacts['contact_status']:
                st.caption(f"ℹ️ {len(warnings_contacts['contact_status'])} non qualifiés (status=contact)")

            if not warnings_contacts['no_email'] and not warnings_contacts['no_company']:
                st.success("✅ Qualité OK")

        with col3:
            st.markdown("**💬 Engagements**")
            total_engagements = len(engagements_to_check)
            st.write(f"Total: **{total_engagements}**")
            st.success("✅ Prêts à synchroniser")

        # Détails des warnings
        with st.expander("📋 Voir détails des warnings"):
            if warnings_companies['no_siren']:
                st.markdown("**Entreprises sans SIREN:**")
                for name in warnings_companies['no_siren'][:10]:
                    st.write(f"• {name}")
                if len(warnings_companies['no_siren']) > 10:
                    st.caption(f"... et {len(warnings_companies['no_siren']) - 10} autres")

            if warnings_contacts['no_email']:
                st.markdown("**Contacts sans coordonnées:**")
                for name in warnings_contacts['no_email'][:10]:
                    st.write(f"• {name}")
                if len(warnings_contacts['no_email']) > 10:
                    st.caption(f"... et {len(warnings_contacts['no_email']) - 10} autres")

    st.divider()

    # =========================================================================
    # SYNC GRANULAIRE (Sprint 4.2)
    # =========================================================================
    st.markdown("### ⚙️ Options de synchronisation")

    # Options granulaires
    col1, col2, col3 = st.columns(3)

    with col1:
        sync_companies_opt = st.checkbox("🏢 Entreprises", value=True, key="sync_opt_companies")

    with col2:
        sync_contacts_opt = st.checkbox("👤 Contacts", value=True, key="sync_opt_contacts")

    with col3:
        sync_engagements_opt = st.checkbox("💬 Engagements", value=False, key="sync_opt_engagements",
                                           help="Sync des engagements vers HubSpot (notes, calls, etc.)")

    # Options avancées
    col1, col2 = st.columns(2)

    with col1:
        create_new = st.checkbox("✅ Créer les nouvelles entités", value=True)

    with col2:
        update_existing = st.checkbox("✅ Mettre à jour les existantes", value=True)

    st.divider()

    # Analyse / Preview
    if st.button("🔍 ANALYSER SYNC", type="secondary"):
        with st.spinner("Analyse en cours..."):
            analysis = sync.analyze(limit=100)

        col1, col2, col3 = st.columns(3)

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

        with col3:
            st.markdown("**Engagements**")
            eng_to_sync = engagement_stats.get('total', 0) - engagement_stats.get('synced', 0)
            st.write(f"• À synchroniser: {eng_to_sync}")
            st.write(f"• Déjà synced: {engagement_stats.get('synced', 0)}")

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

    # Bouton sync avec warning
    quality_done = st.session_state.get('quality_gate_done', False)

    if not quality_done:
        st.info("💡 Conseil: Exécutez l'analyse qualité avant de synchroniser")

    if st.button("🔄 SYNCHRONISER VERS HUBSPOT", type="primary", use_container_width=True):
        with st.spinner("Synchronisation en cours..."):
            progress_bar = st.progress(0)
            status_text = st.empty()

            def update_progress(current, total, entity_type):
                progress_bar.progress(current / total if total > 0 else 0)
                status_text.text(f"Sync {entity_type}: {current}/{total}")

            report = sync.sync_all(
                companies=sync_companies_opt,
                contacts=sync_contacts_opt,
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
