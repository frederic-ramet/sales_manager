"""
Page Base de Leads - Hub central de tous les leads multi-sources.
"""
import json
import os
import streamlit as st
import pandas as pd
from datetime import datetime, date

from modules.lead_scraper import ContactManager, HubSpotClient, PappersClient, CSVImporter
from modules.deduplication import DeduplicationMatcher
from components import render_top_nav, hide_sidebar, render_footer


def load_referentiel(filepath: str):
    """Charge un fichier référentiel JSON."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def format_option(item):
    """Formate une option pour les selectbox (code - label)."""
    return f"{item['code']} - {item['label']}"

# Navigation
hide_sidebar()

st.title("📜 Base de Leads")
st.markdown("Hub central de tous vos leads (SIRENE, HubSpot, GetSales)")

render_top_nav(current_page="pages/3_📜_Base_de_Leads.py")

# Charger la documentation
def load_documentation():
    doc_path = "docs/pages/base_leads.md"
    try:
        with open(doc_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "Documentation non disponible."


# Charger les référentiels
codes_ape = load_referentiel("data/codes_ape.json")
departements = load_referentiel("data/departements.json")

# Initialiser le gestionnaire de contacts
contact_manager = ContactManager()
stats = contact_manager.get_stats()
filter_options = contact_manager.get_filter_options()

# Stats globales avec sources
st.subheader("📈 Vue d'ensemble")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("Total leads", stats['total_leads'])

with col2:
    sirene_count = stats.get('by_source', {}).get('sirene', 0)
    st.metric("🔍 SIRENE", sirene_count)

with col3:
    hubspot_count = stats.get('by_source', {}).get('hubspot', 0)
    st.metric("🟠 HubSpot", hubspot_count)

with col4:
    getsales_count = stats.get('by_source', {}).get('getsales', 0)
    st.metric("💼 GetSales", getsales_count)

with col5:
    enriched_count = stats.get('enriched_count', 0)
    st.metric("✨ Enrichis", enriched_count)

st.divider()

# Onglets principaux
tab1, tab2, tab3, tab4, tab_doc = st.tabs([
    "📋 Tous les leads",
    "⬇️ Import HubSpot",
    "📤 Import CSV",
    "🧹 Gestion",
    "📖 Documentation"
])

# --- TAB 1: Tous les leads ---
with tab1:
    if stats['total_leads'] == 0:
        st.info("ℹ️ Aucun lead dans la base. Lancez votre première extraction !")
    else:
        # === FILTRES PRINCIPAUX ===
        col1, col2, col3, col4 = st.columns(4)

        # Construire la liste des sources disponibles
        available_sources = ["Toutes"] + filter_options.get('sources', [])

        with col1:
            filter_source = st.selectbox(
                "Source",
                options=available_sources,
                index=0
            )

        with col2:
            filter_enriched = st.selectbox(
                "Statut enrichissement",
                options=["Tous", "Enrichis", "Non enrichis"],
                index=0
            )

        with col3:
            search_term = st.text_input(
                "🔍 Rechercher",
                placeholder="SIREN, nom, email..."
            )

        with col4:
            limit = st.selectbox(
                "Résultats",
                options=[50, 100, 200, 500],
                index=1
            )

        # === FILTRES AVANCÉS (expander) ===
        with st.expander("⚙️ Filtres avancés", expanded=False):
            # Ligne 1: Secteurs et Localisation
            col1, col2, col3 = st.columns(3)

            with col1:
                # Filtrer les codes APE disponibles dans la base
                available_ape_codes = filter_options.get('ape_codes', [])
                # Créer liste avec labels si le référentiel est chargé
                ape_options = []
                for code in available_ape_codes:
                    matching = [item for item in codes_ape if item['code'] == code]
                    if matching:
                        ape_options.append(matching[0])
                    else:
                        ape_options.append({'code': code, 'label': code})

                selected_ape = st.multiselect(
                    "🏭 Secteurs APE",
                    options=ape_options,
                    format_func=format_option,
                    help="Filtrer par code APE"
                )

            with col2:
                # Départements disponibles
                available_depts = filter_options.get('departements', [])
                dept_options = []
                for code in available_depts:
                    matching = [item for item in departements if item['code'] == code]
                    if matching:
                        dept_options.append(matching[0])
                    else:
                        dept_options.append({'code': code, 'label': f"Département {code}"})

                selected_dept = st.multiselect(
                    "📍 Départements",
                    options=dept_options,
                    format_func=format_option,
                    help="Filtrer par département"
                )

            with col3:
                filter_city = st.text_input(
                    "🏙️ Ville",
                    placeholder="Paris, Lyon..."
                )

            # Ligne 2: Filtres contacts
            st.markdown("**Filtrer par données disponibles**")
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                filter_has_email = st.checkbox("📧 Avec email", value=False)

            with col2:
                filter_has_phone = st.checkbox("📞 Avec téléphone", value=False)

            with col3:
                filter_has_linkedin = st.checkbox("🔗 Avec LinkedIn", value=False)

            with col4:
                # Campagnes disponibles
                available_campaigns = ["Toutes"] + filter_options.get('campaigns', [])
                filter_campaign = st.selectbox(
                    "📁 Campagne",
                    options=available_campaigns,
                    index=0
                )

            # Ligne 3: Dates
            col1, col2 = st.columns(2)

            with col1:
                filter_date_after = st.date_input(
                    "Créé après",
                    value=None,
                    min_value=date(2020, 1, 1),
                    max_value=date.today(),
                    help="Date de création minimum"
                )

            with col2:
                filter_date_before = st.date_input(
                    "Créé avant",
                    value=None,
                    min_value=date(2020, 1, 1),
                    max_value=date.today(),
                    help="Date de création maximum"
                )

        # === CONSTRUIRE LES FILTRES ===
        source_filter = None if filter_source == "Toutes" else filter_source
        search_filter = search_term if search_term else None

        # Filtre enriched
        enriched_filter = None
        if filter_enriched == "Enrichis":
            enriched_filter = True
        elif filter_enriched == "Non enrichis":
            enriched_filter = False

        # Filtres avancés
        ape_codes_filter = [item['code'] for item in selected_ape] if selected_ape else None
        dept_filter = [item['code'] for item in selected_dept] if selected_dept else None
        city_filter = filter_city if filter_city else None
        campaign_filter = None if filter_campaign == "Toutes" else filter_campaign
        date_after_str = filter_date_after.strftime("%Y-%m-%d") if filter_date_after else None
        date_before_str = filter_date_before.strftime("%Y-%m-%d") if filter_date_before else None

        # Filtres has_*
        has_email_filter = True if filter_has_email else None
        has_phone_filter = True if filter_has_phone else None
        has_linkedin_filter = True if filter_has_linkedin else None

        # === RECHERCHE ===
        contacts = contact_manager.search(
            query=search_filter,
            source=source_filter,
            enriched=enriched_filter,
            campaign_id=campaign_filter,
            ape_codes=ape_codes_filter,
            departements=dept_filter,
            city=city_filter,
            has_email=has_email_filter,
            has_phone=has_phone_filter,
            has_linkedin=has_linkedin_filter,
            created_after=date_after_str,
            created_before=date_before_str,
            limit=limit
        )

        if contacts:
            df = pd.DataFrame(contacts)

            # Colonnes à afficher avec source (nouveau schéma)
            display_cols = ['source', 'siren', 'company_name', 'email', 'city', 'ape_code', 'created_at']
            display_cols = [col for col in display_cols if col in df.columns]

            # Formater la date
            if 'created_at' in df.columns:
                df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M')

            # Ajouter emoji source
            if 'source' in df.columns:
                source_emoji = {'sirene': '🔍', 'hubspot': '🟠', 'getsales': '💼'}
                df['source'] = df['source'].apply(lambda x: f"{source_emoji.get(x, '📄')} {x}" if x else "📄 sirene")

            # Sélection multiple
            st.markdown(f"**{len(contacts)} contacts trouvés**")

            # Afficher le tableau avec sélection
            selected_indices = []

            # Utiliser data_editor pour la sélection
            df_display = df[display_cols].copy()
            df_display.insert(0, 'Sélectionner', False)

            edited_df = st.data_editor(
                df_display,
                use_container_width=True,
                hide_index=True,
                height=400,
                column_config={
                    "Sélectionner": st.column_config.CheckboxColumn(
                        "✓",
                        help="Sélectionner pour actions batch",
                        default=False,
                        width="small"
                    ),
                    "source": st.column_config.TextColumn("Source", width="small"),
                    "siren": st.column_config.TextColumn("SIREN", width="medium"),
                    "company_name": st.column_config.TextColumn("Entreprise", width="large"),
                    "email": st.column_config.TextColumn("Email", width="medium"),
                    "city": st.column_config.TextColumn("Ville", width="medium"),
                    "ape_code": st.column_config.TextColumn("APE", width="small"),
                    "created_at": st.column_config.TextColumn("Date", width="medium"),
                },
                disabled=display_cols  # Désactiver l'édition des colonnes data
            )

            # Compter les sélectionnés
            selected_count = edited_df['Sélectionner'].sum()

            if selected_count > 0:
                st.info(f"**{selected_count}** lead(s) sélectionné(s)")

                # Récupérer les UUIDs des contacts sélectionnés
                selected_mask = edited_df['Sélectionner']
                selected_uuids = df.loc[selected_mask, 'uuid'].tolist() if 'uuid' in df.columns else []

                col1, col2, col3 = st.columns(3)

                with col1:
                    pappers_key = os.getenv('PAPPERS_API_KEY')
                    if st.button("✨ Enrichir avec Pappers", use_container_width=True, disabled=not pappers_key):
                        if not pappers_key:
                            st.error("❌ PAPPERS_API_KEY non configurée")
                        elif selected_uuids:
                            with st.spinner("Enrichissement en cours..."):
                                enriched_count = 0
                                try:
                                    with PappersClient() as pappers:
                                        for uuid in selected_uuids:
                                            contact = contact_manager.get_contact(uuid)
                                            if contact and contact.get('siren'):
                                                # Enrichir via Pappers
                                                enriched_data = pappers.get_company(contact['siren'])
                                                if enriched_data:
                                                    # Mettre à jour le contact
                                                    update_data = {
                                                        'email': enriched_data.get('email'),
                                                        'phone': enriched_data.get('telephone'),
                                                        'firstname': enriched_data.get('dirigeant_prenom'),
                                                        'lastname': enriched_data.get('dirigeant_nom'),
                                                        'job_title': enriched_data.get('dirigeant_fonction'),
                                                        'employee_range': enriched_data.get('effectif'),
                                                        'revenue_range': enriched_data.get('chiffre_affaires'),
                                                    }
                                                    # Filtrer les valeurs None
                                                    update_data = {k: v for k, v in update_data.items() if v}
                                                    if update_data:
                                                        contact_manager.update_contact(uuid, update_data)
                                                        contact_manager.mark_enriched(uuid, source='pappers')
                                                        enriched_count += 1
                                    st.success(f"✅ {enriched_count} contact(s) enrichi(s)")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Erreur: {e}")

                with col2:
                    hubspot_key = os.getenv('HUBSPOT_API_KEY')
                    if st.button("⬆️ Sync vers HubSpot", use_container_width=True, disabled=not hubspot_key):
                        if not hubspot_key:
                            st.error("❌ HUBSPOT_API_KEY non configurée")
                        elif selected_uuids:
                            with st.spinner("Synchronisation vers HubSpot..."):
                                try:
                                    # Préparer les contacts pour HubSpot
                                    contacts_to_push = contact_manager.export_for_hubspot(selected_uuids)

                                    with HubSpotClient() as hubspot:
                                        # Extraire les properties pour push
                                        push_data = [c['properties'] for c in contacts_to_push]
                                        result = hubspot.push_contacts(push_data)

                                        # Marquer comme synchronisés
                                        for contact in contacts_to_push:
                                            contact_manager.update_contact(contact['_uuid'], {
                                                'synced_to_hubspot': True,
                                                'last_sync_hubspot': datetime.now()
                                            })

                                    st.success(f"✅ {result['created']} contact(s) envoyé(s) vers HubSpot")
                                    if result.get('errors'):
                                        st.warning(f"⚠️ {len(result['errors'])} erreur(s)")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Erreur: {e}")

                with col3:
                    if st.button("🗑️ Supprimer", use_container_width=True):
                        if selected_uuids:
                            if st.session_state.get('confirm_delete_batch'):
                                deleted = 0
                                for uuid in selected_uuids:
                                    if contact_manager.delete_contact(uuid, hard_delete=True):
                                        deleted += 1
                                st.success(f"✅ {deleted} contact(s) supprimé(s)")
                                del st.session_state.confirm_delete_batch
                                st.rerun()
                            else:
                                st.session_state.confirm_delete_batch = True
                                st.warning("⚠️ Cliquez à nouveau pour confirmer la suppression")

            st.divider()

            # Export
            col1, col2 = st.columns([1, 3])
            with col1:
                csv = df.to_csv(index=False, sep=';').encode('utf-8')
                st.download_button(
                    "📥 Exporter CSV",
                    data=csv,
                    file_name=f"leads_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        else:
            st.warning("Aucun contact trouvé avec ces filtres")


# --- TAB 2: Import HubSpot ---
with tab2:
    st.subheader("⬇️ Import depuis HubSpot")
    st.markdown("Importez vos contacts ou entreprises HubSpot dans la base locale.")

    # Vérifier config HubSpot
    HUBSPOT_API_KEY = os.getenv('HUBSPOT_API_KEY')

    if not HUBSPOT_API_KEY:
        st.error("❌ HUBSPOT_API_KEY non configurée dans .env")
        st.markdown("""
        Pour activer l'import HubSpot :
        1. Créez une clé API dans HubSpot > Settings > Integrations > API Key
        2. Ajoutez `HUBSPOT_API_KEY=votre_clé` dans le fichier `.env`
        3. Redémarrez l'application
        """)
    else:
        st.success("✅ HubSpot configuré")

        # Options d'import
        col1, col2 = st.columns(2)

        with col1:
            import_type = st.radio(
                "Type d'import",
                options=["Contacts", "Entreprises"],
                horizontal=True
            )

        with col2:
            import_limit = st.number_input(
                "Nombre max à importer",
                min_value=10,
                max_value=1000,
                value=100,
                step=10
            )

        # Filtres optionnels
        with st.expander("⚙️ Filtres avancés (optionnel)"):
            col1, col2 = st.columns(2)
            with col1:
                filter_list = st.text_input(
                    "ID de liste HubSpot",
                    placeholder="Laisser vide pour tous"
                )
            with col2:
                filter_days = st.number_input(
                    "Créés dans les X derniers jours",
                    min_value=0,
                    max_value=365,
                    value=0,
                    help="0 = pas de filtre"
                )

        st.divider()

        # Bouton import
        if st.button("🔄 Lancer l'import", type="primary", use_container_width=True):
            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                status_text.text("🔄 Connexion à HubSpot...")
                progress_bar.progress(10)

                with HubSpotClient() as hubspot:
                    # Tester la connexion
                    success, msg = hubspot.test_connection()
                    if not success:
                        st.error(f"❌ {msg}")
                    else:
                        status_text.text("📥 Récupération des contacts HubSpot...")
                        progress_bar.progress(20)

                        # Synchroniser depuis HubSpot
                        def progress_callback(current, phase):
                            progress_bar.progress(min(20 + int(current / 10), 80))
                            status_text.text(f"📥 {current} contacts récupérés...")

                        sync_result = hubspot.sync_contacts(progress_callback=progress_callback)

                        if sync_result['success']:
                            status_text.text("💾 Import dans la base locale...")
                            progress_bar.progress(85)

                            # Récupérer les contacts du miroir
                            mirror = hubspot.get_mirror()
                            hubspot_contacts = mirror.get('contacts', [])

                            # Limiter si demandé
                            if import_limit and import_limit < len(hubspot_contacts):
                                hubspot_contacts = hubspot_contacts[:import_limit]

                            # Convertir au format unified_contacts
                            contacts_to_import = []
                            for hc in hubspot_contacts:
                                contacts_to_import.append({
                                    'hubspot_contact_id': hc.get('hubspot_id'),
                                    'company_name': hc.get('denomination'),
                                    'email': hc.get('email'),
                                    'phone': hc.get('telephone'),
                                    'firstname': hc.get('dirigeant', '').split(' ')[0] if hc.get('dirigeant') else None,
                                    'lastname': ' '.join(hc.get('dirigeant', '').split(' ')[1:]) if hc.get('dirigeant') else None,
                                    'job_title': hc.get('fonction'),
                                    'siren': hc.get('siren'),
                                    'ape_code': hc.get('code_ape'),
                                    'city': hc.get('ville'),
                                    'address': hc.get('adresse'),
                                    'postal_code': hc.get('code_postal'),
                                    'synced_to_hubspot': True,
                                    'last_sync_hubspot': datetime.now(),
                                })

                            # Importer dans unified_contacts
                            added, updated = contact_manager.import_from_hubspot(contacts_to_import)

                            progress_bar.progress(100)
                            status_text.text("✅ Import terminé!")

                            st.success(f"""
                            ✅ Import HubSpot terminé !
                            - **{sync_result['total_contacts']}** contacts dans HubSpot
                            - **{added}** nouveaux contacts importés
                            - **{updated}** contacts mis à jour
                            """)
                            st.rerun()
                        else:
                            st.error("❌ Erreur lors de la synchronisation HubSpot")

            except Exception as e:
                st.error(f"❌ Erreur: {e}")
                progress_bar.progress(0)

        st.divider()

        # Stats HubSpot
        st.markdown("**📊 Leads HubSpot dans la base**")
        hubspot_in_base = stats.get('by_source', {}).get('hubspot', 0)
        hubspot_synced = stats.get('hubspot_synced', 0)

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Importés depuis HubSpot", hubspot_in_base)
        with col2:
            st.metric("Synchronisés vers HubSpot", hubspot_synced)


# --- TAB 3: Import CSV ---
with tab3:
    st.subheader("📤 Import de fichiers CSV")
    st.markdown("Importez des contacts depuis un fichier CSV (listes achetées, exports, etc.)")

    # File uploader
    uploaded_file = st.file_uploader(
        "Glissez votre fichier CSV ici",
        type=['csv'],
        help="Format: UTF-8 ou Latin-1, séparateur virgule ou point-virgule"
    )

    if uploaded_file:
        # Initialiser l'importeur
        importer = CSVImporter(uploaded_file.getvalue(), uploaded_file.name)

        # Parser le fichier
        try:
            df = importer.parse()
            stats_csv = importer.get_stats()

            st.success(f"✅ Fichier lu: **{stats_csv['rows']} lignes**, {stats_csv['columns']} colonnes")
            st.caption(f"Encodage: {stats_csv['encoding']} | Séparateur: {stats_csv['separator']}")

            # Mapping automatique
            auto_mapping = importer.auto_map_columns()

            st.divider()
            st.subheader("🔗 Mapping des colonnes")
            st.caption("Associez les colonnes du CSV aux champs de la base")

            # Interface de mapping en 3 colonnes
            csv_columns = ['(ignorer)'] + list(df.columns)
            mapping = {}

            # Grouper les champs par catégorie
            field_groups = {
                'Entreprise': ['company_name', 'siren', 'ape_code', 'employee_range', 'revenue_range'],
                'Contact': ['firstname', 'lastname', 'email', 'phone', 'job_title', 'linkedin_url'],
                'Adresse': ['address', 'postal_code', 'city', 'region', 'country', 'website'],
                'Autre': ['notes', 'source_file']
            }

            for group_name, fields in field_groups.items():
                with st.expander(f"**{group_name}**", expanded=(group_name in ['Entreprise', 'Contact'])):
                    cols = st.columns(3)
                    for i, target in enumerate(fields):
                        if target in CSVImporter.TARGET_COLUMNS:
                            with cols[i % 3]:
                                # Trouver l'index par défaut
                                default_idx = 0
                                if target in auto_mapping:
                                    try:
                                        default_idx = csv_columns.index(auto_mapping[target])
                                    except ValueError:
                                        pass

                                # Labels plus lisibles
                                labels = {
                                    'company_name': '🏢 Entreprise',
                                    'siren': '🔢 SIREN',
                                    'email': '📧 Email',
                                    'phone': '📞 Téléphone',
                                    'firstname': '👤 Prénom',
                                    'lastname': '👤 Nom',
                                    'job_title': '💼 Fonction',
                                    'linkedin_url': '🔗 LinkedIn',
                                    'website': '🌐 Site web',
                                    'city': '🏙️ Ville',
                                    'postal_code': '📮 Code postal',
                                    'address': '📍 Adresse',
                                    'region': '🗺️ Région',
                                    'country': '🌍 Pays',
                                    'ape_code': '🏭 Code APE',
                                    'employee_range': '👥 Effectif',
                                    'revenue_range': '💰 CA',
                                    'notes': '📝 Notes',
                                    'source_file': '📁 Source fichier'
                                }

                                selected = st.selectbox(
                                    labels.get(target, target),
                                    options=csv_columns,
                                    index=default_idx,
                                    key=f"map_{target}"
                                )

                                if selected != '(ignorer)':
                                    mapping[target] = selected

            # Stocker le mapping
            importer.mapping = mapping

            st.divider()

            # Prévisualisation
            st.subheader("👀 Prévisualisation")

            if mapping:
                preview = importer.get_preview(10)
                st.dataframe(preview, use_container_width=True, hide_index=True)

                # Stats
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Lignes totales", stats_csv['rows'])
                with col2:
                    st.metric("Colonnes mappées", len(mapping))
                with col3:
                    unmapped = importer.get_unmapped_columns()
                    st.metric("Non mappées", len(unmapped))
                with col4:
                    required = ['company_name', 'email']
                    has_required = any(r in mapping for r in required)
                    st.metric("Prêt", "✅ Oui" if has_required else "❌ Non")

                # Colonnes non mappées
                if unmapped:
                    with st.expander(f"Colonnes ignorées ({len(unmapped)})"):
                        st.write(", ".join(unmapped))
            else:
                st.warning("⚠️ Aucune colonne mappée. Configurez le mapping ci-dessus.")

            st.divider()

            # Validation et import
            errors = importer.validate()

            if errors:
                for err in errors:
                    st.error(f"❌ {err}")
            else:
                # Options d'import
                col1, col2 = st.columns(2)
                with col1:
                    skip_dupes = st.checkbox("Ignorer les doublons", value=True)
                with col2:
                    source_name = st.text_input("Nom de source", value="csv_import")

                st.divider()

                # Bouton import
                if st.button("📥 Importer les contacts", type="primary", use_container_width=True):
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    def update_progress(current, total):
                        progress_bar.progress(int(current / total * 100))
                        status_text.text(f"Import en cours... {current}/{total}")

                    try:
                        # Initialiser le matcher pour déduplication
                        dedup_matcher = DeduplicationMatcher()

                        # Lancer l'import
                        result = importer.import_to_contacts(
                            contact_manager=contact_manager,
                            dedup_matcher=dedup_matcher,
                            source_name=source_name,
                            skip_duplicates=skip_dupes,
                            progress_callback=update_progress
                        )

                        progress_bar.progress(100)
                        status_text.empty()

                        # Afficher les résultats
                        st.success(f"""
                        ✅ **Import terminé !**
                        - **{result.imported}** contacts ajoutés
                        - **{result.duplicates}** doublons détectés
                        - **{result.skipped}** lignes ignorées (données manquantes)
                        """)

                        if result.errors:
                            with st.expander(f"⚠️ {len(result.errors)} erreurs"):
                                for err in result.errors[:20]:
                                    st.text(err)

                        if result.duplicate_details:
                            with st.expander(f"📋 Doublons détectés ({result.duplicates})"):
                                for dup in result.duplicate_details[:10]:
                                    input_name = f"{dup['input_data'].get('firstname', '')} {dup['input_data'].get('lastname', '')}".strip()
                                    match_name = f"{dup['match'].get('firstname', '')} {dup['match'].get('lastname', '')}".strip()
                                    st.markdown(f"""
                                    **Ligne {dup['row']}**: {input_name or dup['input_data'].get('company_name', 'N/A')}
                                    → Match: {match_name or dup['match'].get('company_name', 'N/A')} ({dup['confidence']})
                                    """)

                        st.balloons()
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ Erreur lors de l'import: {e}")
                        progress_bar.empty()

        except Exception as e:
            st.error(f"❌ Erreur lors de la lecture du fichier: {e}")

    else:
        # Instructions
        st.info("""
        **Formats supportés:**
        - Encodage: UTF-8, Latin-1, Windows-1252
        - Séparateurs: virgule (,), point-virgule (;), tabulation

        **Colonnes reconnues automatiquement:**
        - Entreprise, Société, Company → `company_name`
        - Prénom, First Name → `firstname`
        - Nom, Last Name → `lastname`
        - Email, Mail, Courriel → `email`
        - Téléphone, Phone → `phone`
        - Fonction, Poste → `job_title`
        - Et bien d'autres...
        """)


# --- TAB 4: Gestion ---
with tab4:
    st.subheader("🧹 Gestion de la base")
    st.warning("⚠️ **Attention** : Ces actions sont irréversibles !")

    # Stats par source
    st.markdown("**📊 Répartition par source**")
    by_source = stats.get('by_source', {})

    if by_source:
        source_data = []
        for source, count in by_source.items():
            source_data.append({
                'Source': source,
                'Nombre': count,
                'Pourcentage': f"{count / stats['total_leads'] * 100:.1f}%" if stats['total_leads'] > 0 else "0%"
            })

        if source_data:
            st.dataframe(
                pd.DataFrame(source_data),
                use_container_width=True,
                hide_index=True
            )

    st.divider()

    # Campagnes récentes
    st.markdown("**📁 Campagnes récentes**")

    campaigns = stats.get('campaigns_recent', [])
    if campaigns:
        for campaign in campaigns[:5]:
            campaign_id = campaign.get('campaign_id', 'N/A')
            with st.expander(
                f"📁 {campaign_id} - {campaign['count']} contacts",
                expanded=False
            ):
                try:
                    date_camp = datetime.fromisoformat(campaign['date'])
                    st.caption(f"Date: {date_camp.strftime('%Y-%m-%d %H:%M:%S')}")
                except:
                    st.caption(f"Date: {campaign['date']}")

                col1, col2 = st.columns([3, 1])

                with col1:
                    st.metric("Nombre de contacts", campaign['count'])

                with col2:
                    if st.button("🗑️ Supprimer", key=f"del_{campaign_id}"):
                        if st.session_state.get(f'confirm_{campaign_id}'):
                            deleted = contact_manager.delete_campaign(campaign_id)
                            st.success(f"✅ {deleted} contacts supprimés")
                            st.rerun()
                        else:
                            st.session_state[f'confirm_{campaign_id}'] = True
                            st.warning("⚠️ Cliquez à nouveau pour confirmer")
    else:
        st.info("ℹ️ Aucune campagne enregistrée")

    st.divider()

    # Archiver les anciens contacts
    st.markdown("**🗑️ Archivage**")

    col1, col2 = st.columns(2)
    with col1:
        days = st.number_input(
            "Archiver les contacts plus vieux que (jours)",
            min_value=1,
            max_value=365,
            value=90
        )

    with col2:
        st.write("")
        st.write("")
        if st.button("🗑️ Archiver", use_container_width=True):
            if st.session_state.get('confirm_clean'):
                archived = contact_manager.archive_old_contacts(older_than_days=days)
                st.success(f"✅ {archived} contacts archivés")
                del st.session_state.confirm_clean
                st.rerun()
            else:
                st.session_state.confirm_clean = True
                st.warning(f"⚠️ Cliquez à nouveau pour confirmer")

    st.divider()

    # Réinitialisation complète
    st.markdown("**🔥 Réinitialisation complète**")
    st.markdown("Supprime **TOUS** les contacts.")

    if st.button("🔥 RÉINITIALISER", type="primary"):
        if st.session_state.get('confirm_reset'):
            deleted = contact_manager.clear_all(confirm=True)
            st.success(f"✅ {deleted} contacts supprimés")
            del st.session_state.confirm_reset
            st.rerun()
        else:
            st.session_state.confirm_reset = True
            st.error("⚠️ Cliquez à nouveau pour CONFIRMER")

    st.divider()

    # Infos système
    st.markdown("**ℹ️ Informations système**")
    db_path = "data/leads.db"
    if os.path.exists(db_path):
        st.code(f"Base: {db_path}\nTaille: {os.path.getsize(db_path) / 1024:.2f} KB\nContacts: {stats['total_contacts']}")
    else:
        st.info("Base de données non initialisée")


# --- TAB 4: Documentation ---
with tab_doc:
    st.markdown(load_documentation())


# Rafraîchir
st.divider()
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    if st.button("🔄 Rafraîchir", use_container_width=True):
        st.rerun()

# Footer
render_footer()
