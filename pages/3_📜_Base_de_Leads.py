"""
Page Base de Leads - Hub central de tous les leads multi-sources.
"""
import os
import streamlit as st
import pandas as pd
from datetime import datetime

from modules.lead_scraper import LeadTracker

st.title("📜 Base de Leads")
st.markdown("Hub central de tous vos leads (SIRENE, HubSpot, GetSales)")

# Charger la documentation
def load_documentation():
    doc_path = "docs/pages/base_leads.md"
    try:
        with open(doc_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "Documentation non disponible."


# Initialiser le tracker
tracker = LeadTracker()
stats = tracker.get_stats()

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
tab1, tab2, tab3, tab_doc = st.tabs([
    "📋 Tous les leads",
    "⬇️ Import HubSpot",
    "🧹 Gestion",
    "📖 Documentation"
])

# --- TAB 1: Tous les leads ---
with tab1:
    if stats['total_leads'] == 0:
        st.info("ℹ️ Aucun lead dans la base. Lancez votre première extraction !")
    else:
        # Filtres
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            filter_source = st.selectbox(
                "Source",
                options=["Toutes", "sirene", "hubspot", "getsales"],
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
                "Rechercher",
                placeholder="SIREN, nom, email..."
            )

        with col4:
            limit = st.selectbox(
                "Résultats",
                options=[50, 100, 200, 500],
                index=1
            )

        # Construire les filtres
        source_filter = None if filter_source == "Toutes" else filter_source
        search_filter = search_term if search_term else None

        # Récupérer les leads
        history = tracker.get_history(
            limit=limit,
            source=source_filter,
            search=search_filter
        )

        # Filtre enrichissement (côté client)
        if filter_enriched == "Enrichis":
            history = [h for h in history if h.get('enriched_at')]
        elif filter_enriched == "Non enrichis":
            history = [h for h in history if not h.get('enriched_at')]

        if history:
            df = pd.DataFrame(history)

            # Colonnes à afficher avec source
            display_cols = ['source', 'siren', 'denomination', 'email', 'ville', 'code_ape', 'date_extraction']
            display_cols = [col for col in display_cols if col in df.columns]

            # Formater la date
            if 'date_extraction' in df.columns:
                df['date_extraction'] = pd.to_datetime(df['date_extraction']).dt.strftime('%Y-%m-%d %H:%M')

            # Ajouter emoji source
            if 'source' in df.columns:
                source_emoji = {'sirene': '🔍', 'hubspot': '🟠', 'getsales': '💼'}
                df['source'] = df['source'].apply(lambda x: f"{source_emoji.get(x, '📄')} {x}" if x else "📄 sirene")

            # Sélection multiple
            st.markdown(f"**{len(history)} leads trouvés**")

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
                    "denomination": st.column_config.TextColumn("Entreprise", width="large"),
                    "email": st.column_config.TextColumn("Email", width="medium"),
                    "ville": st.column_config.TextColumn("Ville", width="medium"),
                    "code_ape": st.column_config.TextColumn("APE", width="small"),
                    "date_extraction": st.column_config.TextColumn("Date", width="medium"),
                },
                disabled=display_cols  # Désactiver l'édition des colonnes data
            )

            # Compter les sélectionnés
            selected_count = edited_df['Sélectionner'].sum()

            if selected_count > 0:
                st.info(f"**{selected_count}** lead(s) sélectionné(s)")

                col1, col2, col3 = st.columns(3)

                with col1:
                    if st.button("✨ Enrichir avec Pappers", use_container_width=True):
                        st.warning("🚧 Fonctionnalité à venir - Enrichissement Pappers")

                with col2:
                    if st.button("⬆️ Sync vers HubSpot", use_container_width=True):
                        st.warning("🚧 Fonctionnalité à venir - Push HubSpot")

                with col3:
                    if st.button("🗑️ Supprimer", use_container_width=True):
                        st.warning("🚧 Suppression batch à implémenter")

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
            st.warning("Aucun lead trouvé avec ces filtres")


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
            st.warning("🚧 Fonctionnalité en cours de développement")
            st.info(f"""
            Import prévu :
            - Type : {import_type}
            - Limite : {import_limit}
            - Liste : {filter_list or 'Toutes'}
            - Période : {f'{filter_days} derniers jours' if filter_days > 0 else 'Toutes dates'}
            """)

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


# --- TAB 3: Gestion ---
with tab3:
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

    if stats['campagnes_recentes']:
        for campagne in stats['campagnes_recentes'][:5]:
            with st.expander(
                f"📁 {campagne['campagne_id']} - {campagne['count']} leads",
                expanded=False
            ):
                try:
                    date_camp = datetime.fromisoformat(campagne['date'])
                    st.caption(f"Date: {date_camp.strftime('%Y-%m-%d %H:%M:%S')}")
                except:
                    st.caption(f"Date: {campagne['date']}")

                col1, col2 = st.columns([3, 1])

                with col1:
                    st.metric("Nombre de leads", campagne['count'])

                with col2:
                    if st.button("🗑️ Supprimer", key=f"del_{campagne['campagne_id']}"):
                        if st.session_state.get(f'confirm_{campagne["campagne_id"]}'):
                            deleted = tracker.delete_campagne(campagne['campagne_id'])
                            st.success(f"✅ {deleted} leads supprimés")
                            st.rerun()
                        else:
                            st.session_state[f'confirm_{campagne["campagne_id"]}'] = True
                            st.warning("⚠️ Cliquez à nouveau pour confirmer")
    else:
        st.info("ℹ️ Aucune campagne enregistrée")

    st.divider()

    # Nettoyer les anciens leads
    st.markdown("**🗑️ Nettoyage**")

    col1, col2 = st.columns(2)
    with col1:
        days = st.number_input(
            "Supprimer les leads plus vieux que (jours)",
            min_value=1,
            max_value=365,
            value=90
        )

    with col2:
        st.write("")
        st.write("")
        if st.button("🗑️ Nettoyer", use_container_width=True):
            if st.session_state.get('confirm_clean'):
                deleted = tracker.clear_history(older_than_days=days)
                st.success(f"✅ {deleted} leads supprimés")
                del st.session_state.confirm_clean
                st.rerun()
            else:
                st.session_state.confirm_clean = True
                st.warning(f"⚠️ Cliquez à nouveau pour confirmer")

    st.divider()

    # Réinitialisation complète
    st.markdown("**🔥 Réinitialisation complète**")
    st.markdown("Supprime **TOUT** l'historique.")

    if st.button("🔥 RÉINITIALISER", type="primary"):
        if st.session_state.get('confirm_reset'):
            deleted = tracker.clear_history()
            st.success(f"✅ {deleted} leads supprimés")
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
        st.code(f"Base: {db_path}\nTaille: {os.path.getsize(db_path) / 1024:.2f} KB\nLeads: {stats['total_leads']}")
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
