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
                    # Sauvegarder les données brutes
                    st.session_state.raw_tasks = tasks
                    st.success(f"**{len(tasks)} tasks** récupérées depuis Asana")

            except AsanaClientError as e:
                st.error(f"**Erreur Asana:** {e}")

    # Afficher les données brutes si disponibles
    if 'raw_tasks' in st.session_state and st.session_state.raw_tasks:
        tasks = st.session_state.raw_tasks

        st.subheader(f"📋 {len(tasks)} tasks récupérées")

        # Afficher chaque task en JSON
        for i, task in enumerate(tasks):
            with st.expander(f"Task {i+1}: {task.get('name', 'Sans nom')}"):
                st.json(task)

st.divider()

# === Synchronisation ===
st.header("3. Synchronisation vers Google Sheets")

st.info("🚧 Section à finaliser après validation du mapping des données Asana")


# === Footer ===
st.divider()
st.caption("Dashboard Pipeline CFO - Genie Factory")
