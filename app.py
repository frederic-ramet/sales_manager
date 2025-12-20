"""
Interface Streamlit - Dashboard Pipeline CFO.
"""

import streamlit as st
import os
from dotenv import load_dotenv
import logging

from core.asana_client import AsanaClient, AsanaClientError
from core.pipeline import PipelineCalculator
from core.sheets_sync import GoogleSheetsSync, SheetsSyncError

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
load_dotenv()

# Configuration de la page
st.set_page_config(
    page_title="Dashboard Pipeline CFO",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Dashboard Pipeline CFO")
st.markdown("Synchronisation Asana → Google Sheets pour le pilotage financier")

# Initialiser le state
if 'last_sync' not in st.session_state:
    st.session_state.last_sync = None
if 'preview_df' not in st.session_state:
    st.session_state.preview_df = None
if 'preview_summary' not in st.session_state:
    st.session_state.preview_summary = None

# Charger config depuis .env
asana_token = os.getenv('ASANA_ACCESS_TOKEN', '')
asana_project_gid = os.getenv('ASANA_PROJECT_GID', '')
gsheet_url = os.getenv('GOOGLE_SPREADSHEET_URL', '')
google_creds_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials/service-account.json')


# === Tests de connexion ===
st.header("1. Vérification des connexions")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Asana")
    if st.button("🔗 Tester Asana", use_container_width=True):
        if not asana_token:
            st.error("**ASANA_ACCESS_TOKEN** non défini dans `.env`")
        elif not asana_project_gid:
            st.error("**ASANA_PROJECT_GID** non défini dans `.env`")
        else:
            try:
                client = AsanaClient(asana_token)
                user = client.test_connection()
                st.success(f"Connecté en tant que **{user['name']}** ({user['email']})")
            except AsanaClientError as e:
                st.error(f"**Erreur Asana:** {e}")
                st.info("Vérifiez que votre PAT est valide sur https://app.asana.com/0/my-apps")

with col2:
    st.subheader("Google Sheets")
    if st.button("📊 Tester Google Sheets", use_container_width=True):
        if not gsheet_url:
            st.error("**GOOGLE_SPREADSHEET_URL** non défini dans `.env`")
        elif not google_creds_path:
            st.error("**GOOGLE_CREDENTIALS_PATH** non défini dans `.env`")
        elif not os.path.exists(google_creds_path):
            st.error(f"**Fichier credentials introuvable:** `{google_creds_path}`")
            st.info("Placez votre fichier `service-account.json` dans le dossier `credentials/`")
        else:
            try:
                syncer = GoogleSheetsSync(google_creds_path, gsheet_url)
                info = syncer.test_connection()
                st.success(f"Connecté au sheet **{info['title']}**")
                st.caption(f"Onglets existants: {', '.join(info['sheets'])}")
            except SheetsSyncError as e:
                error_msg = str(e)
                st.error(f"**Erreur Google Sheets:** {error_msg}")

                # Lire l'email du service account pour l'afficher
                try:
                    import json
                    with open(google_creds_path) as f:
                        sa_email = json.load(f).get('client_email', 'N/A')
                    st.warning(f"📧 **Email à partager:** `{sa_email}`")
                    st.info("Ouvrez votre Google Sheet → Partager → Collez cet email → Éditeur → Partager")
                except:
                    st.info("Partagez le Google Sheet avec l'email du Service Account (en éditeur)")

st.divider()

# === Aperçu des données ===
st.header("2. Aperçu des données Asana")

asana_config_ok = all([asana_token, asana_project_gid])

if not asana_config_ok:
    st.warning("⚠️ Configuration Asana incomplète.")
else:
    if st.button("📥 Récupérer les données Asana", use_container_width=False):
        with st.spinner("Récupération en cours..."):
            try:
                asana_client = AsanaClient(asana_token)
                tasks = asana_client.get_project_tasks(asana_project_gid)

                if not tasks:
                    st.warning("Aucun deal trouvé dans le projet Asana.")
                else:
                    calculator = PipelineCalculator(tasks)
                    df = calculator.parse_tasks_to_dataframe()
                    df = calculator.calculate_metrics()
                    summary = calculator.get_summary_metrics()

                    # Sauvegarder dans session state
                    st.session_state.preview_df = df
                    st.session_state.preview_summary = summary

                    st.success(f"**{len(df)} deals** récupérés depuis Asana")

            except AsanaClientError as e:
                st.error(f"**Erreur Asana:** {e}")

    # Afficher les données si disponibles
    if st.session_state.preview_df is not None:
        df = st.session_state.preview_df
        summary = st.session_state.preview_summary

        # Métriques
        st.subheader("📈 Résumé")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Deals", summary.get('total_deals', 0))
        m2.metric("Budget Total", f"{summary.get('total_budget', 0):,.0f} €")
        m3.metric("Revenue Pondéré", f"{summary.get('total_revenue_pondere', 0):,.0f} €")
        m4.metric("Marge Totale", f"{summary.get('total_marge', 0):,.0f} €")

        # Tableau des données
        st.subheader("📋 Détail des deals")

        # Sélectionner les colonnes à afficher
        display_cols = ['titre', 'client', 'projet', 'budget', 'marge', 'confidence_score',
                       'probabilite_pct', 'revenue_pondere', 'section', 'mois']
        available_cols = [c for c in display_cols if c in df.columns]

        st.dataframe(df[available_cols], use_container_width=True)

        # Données brutes (debug)
        with st.expander("🔍 Voir toutes les colonnes (debug)"):
            st.dataframe(df, use_container_width=True)

st.divider()

# === Synchronisation ===
st.header("3. Synchronisation vers Google Sheets")

# Vérification config
config_ok = all([asana_token, asana_project_gid, gsheet_url, google_creds_path])
creds_exist = os.path.exists(google_creds_path) if google_creds_path else False

if not config_ok:
    st.warning("⚠️ Configuration incomplète. Éditez le fichier `.env` avec vos identifiants.")
elif not creds_exist:
    st.warning(f"⚠️ Fichier credentials introuvable: `{google_creds_path}`")
elif st.session_state.preview_df is None:
    st.info("👆 Récupérez d'abord les données Asana (section 2)")
else:
    col1, col2 = st.columns([1, 3])

    with col1:
        sync_button = st.button(
            "🔄 Synchroniser maintenant",
            type="primary",
            use_container_width=True
        )

    with col2:
        if st.session_state.last_sync:
            st.info(f"Dernière sync: {st.session_state.last_sync}")

    if sync_button:
        progress = st.progress(0, text="Initialisation...")

        try:
            df = st.session_state.preview_df

            # Préparer les données pour Sheets
            progress.progress(30, text="Préparation des données...")
            calculator = PipelineCalculator([])  # Dummy init
            calculator.df = df
            sheets_data = calculator.prepare_sheets_data()

            # Sync Google Sheets
            progress.progress(60, text="Synchronisation vers Google Sheets...")
            syncer = GoogleSheetsSync(google_creds_path, gsheet_url)
            result = syncer.sync_pipeline(sheets_data)

            progress.progress(100, text="Terminé!")

            if result.success:
                st.session_state.last_sync = result.timestamp
                st.success(f"Synchronisation réussie! **{result.total_rows} lignes** envoyées vers Google Sheets.")
                st.caption(f"Onglets mis à jour: {', '.join(result.sheets_updated)}")
            else:
                st.error(f"Erreur lors de la sync: {result.error}")

            progress.empty()

        except SheetsSyncError as e:
            progress.empty()
            st.error(f"**Erreur Google Sheets:** {e}")
            logger.error(f"Erreur Sheets: {e}")

        except Exception as e:
            progress.empty()
            st.error(f"**Erreur inattendue:** {e}")
            logger.exception("Erreur inattendue")


# === Footer ===
st.divider()
st.caption("Dashboard Pipeline CFO - Genie Factory")
