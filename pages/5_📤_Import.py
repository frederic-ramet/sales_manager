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
# TAB: IMPORT GETSALES
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
        st.success("✅ GetSales configuré")

        # Lien vers la page de sync complète
        st.info("""
        **Pour la synchronisation GetSales complète**, utilisez la page dédiée:
        - Synchronisation automatique
        - File de validation
        - Gestion des doublons HubSpot

        Accédez à **🔄 GetSales Sync** dans le menu.
        """)

        # Import manuel rapide
        with st.expander("📥 Import manuel rapide"):
            st.markdown("""
            Collez ici les données d'un lead GetSales au format JSON pour un import rapide.
            """)

            json_input = st.text_area(
                "Données JSON du lead",
                height=150,
                placeholder='{"first_name": "Jean", "last_name": "Dupont", "company_name": "ACME Corp", "email": "jean@acme.fr"}'
            )

            if st.button("📥 Importer ce lead", disabled=not json_input):
                try:
                    import json
                    lead_data = json.loads(json_input)

                    # Trouver ou créer l'entreprise
                    company_id, created = company_manager.find_or_create_company({
                        'company_name': lead_data.get('company_name'),
                        'website': lead_data.get('website'),
                        'siren': lead_data.get('siren'),
                        'source': 'getsales'
                    })

                    # Créer le contact
                    contact_uuid = contact_manager.add_contact_with_company(
                        data={
                            'firstname': lead_data.get('first_name'),
                            'lastname': lead_data.get('last_name'),
                            'email': lead_data.get('email'),
                            'phone': lead_data.get('phone'),
                            'job_title': lead_data.get('position'),
                            'linkedin_url': lead_data.get('linkedin'),
                            'getsales_uuid': lead_data.get('uuid'),
                        },
                        source='getsales',
                        company_id=company_id
                    )

                    st.success(f"✅ Lead importé! Contact: {contact_uuid[:8]}...")
                except Exception as e:
                    st.error(f"❌ Erreur: {e}")


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
                                action = st.selectbox(
                                    "Action",
                                    ["Lier à l'existant", "Créer doublon", "Ignorer"],
                                    key=f"action_{row['row_index']}",
                                    label_visibility="collapsed"
                                )
                                # Mettre à jour l'action
                                action_map = {
                                    "Lier à l'existant": "link",
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
                errors = []

                for i, row in enumerate(selected_rows):
                    progress.progress((i + 1) / len(selected_rows))
                    row_data = row['row_data']

                    try:
                        if row['action'] == 'ignore':
                            continue

                        # Déterminer le company_id
                        if row['company_match'] and row['action'] == 'link':
                            # Lier à l'entreprise existante
                            company_id = row['company_match']['id']
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

                        # Créer le contact
                        contact_uuid = contact_manager.add_contact_with_company(
                            data={
                                'firstname': row_data.get('firstname'),
                                'lastname': row_data.get('lastname'),
                                'email': row_data.get('email'),
                                'phone': row_data.get('phone'),
                                'job_title': row_data.get('job_title'),
                                'linkedin_url': row_data.get('linkedin_url'),
                                'notes': row_data.get('notes'),
                            },
                            source=source_name,
                            company_id=company_id
                        )

                        imported += 1
                        status.text(f"Importé: {row_data.get('company_name', 'N/A')}")

                    except Exception as e:
                        errors.append(f"Ligne {row['row_index'] + 2}: {str(e)}")

                progress.progress(1.0)

                if imported > 0:
                    st.success(f"✅ {imported} contact(s) importé(s) avec succès!")

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
