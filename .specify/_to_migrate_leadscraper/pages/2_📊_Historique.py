"""
Page d'historique des leads extraits.
Permet de visualiser, filtrer et gérer l'historique de déduplication.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from core.lead_tracker import LeadTracker

# Configuration de la page
st.set_page_config(
    page_title="Historique - Lead Gen SIRENE",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Historique des leads")
st.markdown("Visualisation et gestion des entreprises déjà extraites")
st.divider()

# Initialiser le tracker
tracker = LeadTracker()

# Récupérer les stats
stats = tracker.get_stats()

# Afficher les stats globales
st.subheader("📈 Statistiques globales")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total leads", stats['total_leads'])

with col2:
    st.metric("Campagnes", stats['num_campagnes'])

with col3:
    if stats['dernier_lead']:
        try:
            dernier = datetime.fromisoformat(stats['dernier_lead'])
            delta_days = (datetime.now() - dernier).days
            st.metric("Dernier lead", f"Il y a {delta_days}j")
        except:
            st.metric("Dernier lead", "N/A")
    else:
        st.metric("Dernier lead", "Aucun")

with col4:
    # Base de données size
    import os
    db_path = "data/leads_history.db"
    if os.path.exists(db_path):
        size_mb = os.path.getsize(db_path) / (1024 * 1024)
        st.metric("Taille BDD", f"{size_mb:.2f} MB")
    else:
        st.metric("Taille BDD", "0 MB")

st.divider()

# Onglets
tab1, tab2, tab3 = st.tabs(["📋 Historique détaillé", "📊 Par campagne", "🗑️ Gestion"])

# --- TAB 1: Historique détaillé ---
with tab1:
    st.subheader("Historique des leads")

    if stats['total_leads'] == 0:
        st.info("ℹ️ Aucun lead dans l'historique. Lancez votre première extraction !")
    else:
        # Filtres
        col1, col2 = st.columns(2)
        with col1:
            search_siren = st.text_input(
                "Rechercher un SIREN",
                placeholder="123456789"
            )

        with col2:
            limit = st.selectbox(
                "Nombre de résultats",
                options=[50, 100, 200, 500, 1000],
                index=1
            )

        # Récupérer l'historique
        history = tracker.get_history(limit=limit)

        if search_siren:
            # Filtrer par SIREN
            history = [h for h in history if search_siren in h['siren']]

        if history:
            # Convertir en DataFrame
            df = pd.DataFrame(history)

            # Formater les colonnes
            display_cols = ['siren', 'denomination', 'ville', 'code_ape', 'date_extraction', 'campagne_id']
            display_cols = [col for col in display_cols if col in df.columns]

            # Formater la date
            if 'date_extraction' in df.columns:
                df['date_extraction'] = pd.to_datetime(df['date_extraction']).dt.strftime('%Y-%m-%d %H:%M')

            st.dataframe(
                df[display_cols],
                use_container_width=True,
                hide_index=True,
                height=500
            )

            # Bouton d'export
            csv = df.to_csv(index=False, sep=';').encode('utf-8')
            st.download_button(
                "📥 Télécharger l'historique (CSV)",
                data=csv,
                file_name=f"leads_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        else:
            st.warning("Aucun résultat trouvé")

# --- TAB 2: Par campagne ---
with tab2:
    st.subheader("Leads par campagne")

    if stats['campagnes_recentes']:
        for campagne in stats['campagnes_recentes']:
            with st.expander(
                f"📁 Campagne {campagne['campagne_id']} - {campagne['count']} leads",
                expanded=False
            ):
                # Date de la campagne
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

                # Afficher les leads de cette campagne
                campagne_leads = tracker.get_history(limit=1000, campagne_id=campagne['campagne_id'])
                if campagne_leads:
                    df_camp = pd.DataFrame(campagne_leads)
                    display_cols = ['siren', 'denomination', 'ville', 'code_ape']
                    display_cols = [col for col in display_cols if col in df_camp.columns]

                    st.dataframe(
                        df_camp[display_cols].head(20),
                        use_container_width=True,
                        hide_index=True
                    )

                    if len(df_camp) > 20:
                        st.caption(f"... et {len(df_camp) - 20} autres leads")
    else:
        st.info("ℹ️ Aucune campagne enregistrée")

# --- TAB 3: Gestion ---
with tab3:
    st.subheader("Gestion de l'historique")

    st.warning("⚠️ **Attention** : Ces actions sont irréversibles !")

    st.markdown("---")

    # Supprimer les anciens leads
    st.subheader("Nettoyer les leads anciens")
    st.markdown("Supprime les leads plus vieux qu'une certaine période.")

    col1, col2 = st.columns(2)
    with col1:
        days = st.number_input(
            "Supprimer les leads plus vieux que (jours)",
            min_value=1,
            max_value=365,
            value=90
        )

    with col2:
        st.write("")  # Spacing
        st.write("")  # Spacing
        if st.button("🗑️ Nettoyer", use_container_width=True):
            if 'confirm_clean' in st.session_state and st.session_state.confirm_clean:
                deleted = tracker.clear_history(older_than_days=days)
                st.success(f"✅ {deleted} leads supprimés (> {days} jours)")
                del st.session_state.confirm_clean
                st.rerun()
            else:
                st.session_state.confirm_clean = True
                st.warning(f"⚠️ Cliquez à nouveau pour confirmer la suppression des leads > {days} jours")

    st.markdown("---")

    # Réinitialiser complètement
    st.subheader("Réinitialisation complète")
    st.markdown("Supprime **TOUT** l'historique. Cette action est irréversible !")

    if st.button("🔥 RÉINITIALISER TOUT L'HISTORIQUE", type="primary"):
        if 'confirm_reset' in st.session_state and st.session_state.confirm_reset:
            deleted = tracker.clear_history()
            st.success(f"✅ Historique réinitialisé - {deleted} leads supprimés")
            del st.session_state.confirm_reset
            st.rerun()
        else:
            st.session_state.confirm_reset = True
            st.error("⚠️ **ATTENTION** : Cliquez à nouveau pour CONFIRMER la suppression de TOUT l'historique")

    st.markdown("---")

    # Informations système
    st.subheader("Informations système")

    db_path = "data/leads_history.db"
    if os.path.exists(db_path):
        st.code(f"""
Base de données: {db_path}
Taille: {os.path.getsize(db_path) / 1024:.2f} KB
Total leads: {stats['total_leads']}
        """)
    else:
        st.info("Base de données non initialisée")

# Bouton de rafraîchissement
st.divider()
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    if st.button("🔄 Rafraîchir", use_container_width=True):
        st.rerun()
