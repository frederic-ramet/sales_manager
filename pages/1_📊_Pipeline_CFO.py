"""
Page Pipeline CFO - Synchronisation Asana → Google Sheets.
"""

import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
import logging

from core.asana_client import AsanaClient, AsanaClientError
from core.sheets_sync import GoogleSheetsSync, SheetsSyncError

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
load_dotenv()

st.title("📊 Dashboard Pipeline CFO")
st.markdown("Synchronisation Asana → Google Sheets pour le pilotage financier")

# Initialiser le state
if 'last_sync' not in st.session_state:
    st.session_state.last_sync = None
if 'raw_tasks' not in st.session_state:
    st.session_state.raw_tasks = None

# Charger config depuis .env
asana_token = os.getenv('ASANA_ACCESS_TOKEN', '')
asana_project_gid = os.getenv('ASANA_PROJECT_GID', '')
gsheet_url = os.getenv('GOOGLE_SPREADSHEET_URL', '')
google_creds_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials/service-account.json')


def get_custom_field(task, field_name):
    """Extrait la valeur d'un custom field par son nom."""
    for cf in task.get('custom_fields', []):
        if cf.get('name') == field_name:
            # Selon le type, récupérer la bonne valeur
            cf_type = cf.get('type')
            if cf_type == 'number':
                return cf.get('number_value')
            elif cf_type == 'enum':
                enum_val = cf.get('enum_value')
                return enum_val.get('name') if enum_val else None
            elif cf_type == 'text':
                return cf.get('text_value')
            else:
                return cf.get('display_value')
    return None


def parse_tasks_to_dataframe(tasks):
    """Convertit les tasks Asana en DataFrame avec le mapping défini."""
    rows = []
    for task in tasks:
        row = {
            'Id': task.get('gid'),
            'Name': task.get('name'),
            'Budget': get_custom_field(task, 'Estimated value'),
            'Status': get_custom_field(task, 'Lead status'),
            'Source': get_custom_field(task, 'Source'),
            'DocSuivi': get_custom_field(task, 'Link Sheets'),
            'Proba': get_custom_field(task, 'Confidence Score'),
            'Modified': task.get('modified_at'),
        }
        rows.append(row)

    return pd.DataFrame(rows)


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
                    st.session_state.raw_tasks = tasks
                    st.success(f"**{len(tasks)} tasks** récupérées depuis Asana")

            except AsanaClientError as e:
                st.error(f"**Erreur Asana:** {e}")

    # Afficher les données si disponibles
    if st.session_state.raw_tasks:
        tasks = st.session_state.raw_tasks

        # Créer le DataFrame
        df = parse_tasks_to_dataframe(tasks)

        st.subheader(f"📋 {len(df)} tasks")

        # Afficher le tableau
        st.dataframe(df, use_container_width=True)

        # Données brutes (debug)
        with st.expander("🔍 Voir les données JSON brutes"):
            for i, task in enumerate(tasks):
                with st.expander(f"Task {i+1}: {task.get('name', 'Sans nom')}"):
                    st.json(task)

st.divider()

# === Synchronisation ===
st.header("3. Synchronisation vers Google Sheets")

config_ok = all([asana_token, asana_project_gid, gsheet_url, google_creds_path])
creds_exist = os.path.exists(google_creds_path) if google_creds_path else False

if not config_ok:
    st.warning("⚠️ Configuration incomplète.")
elif not creds_exist:
    st.warning(f"⚠️ Fichier credentials introuvable: `{google_creds_path}`")
elif not st.session_state.raw_tasks:
    st.info("👆 Récupérez d'abord les données Asana (section 2)")
else:
    if st.button("🔄 Synchroniser vers Google Sheets", type="primary"):
        with st.spinner("Synchronisation en cours..."):
            try:
                df = parse_tasks_to_dataframe(st.session_state.raw_tasks)

                syncer = GoogleSheetsSync(google_creds_path, gsheet_url)
                result = syncer.sync_with_logging(df, 'Pipeline')

                if result.success:
                    st.session_state.last_sync = result.timestamp
                    if 'Log' in result.sheets_updated:
                        st.success(f"**{len(df)} lignes** synchronisées (changements loggés)")
                    else:
                        st.success(f"**{len(df)} lignes** synchronisées (aucun changement)")
                else:
                    st.error(f"Erreur: {result.error}")

            except SheetsSyncError as e:
                st.error(f"**Erreur Google Sheets:** {e}")

    if st.session_state.last_sync:
        st.caption(f"Dernière sync: {st.session_state.last_sync}")
