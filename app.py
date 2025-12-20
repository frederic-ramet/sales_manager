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
if 'last_result' not in st.session_state:
    st.session_state.last_result = None


# === SIDEBAR - Configuration ===
with st.sidebar:
    st.header("⚙️ Configuration")

    st.subheader("Asana")
    asana_token = st.text_input(
        "Personal Access Token",
        value=os.getenv('ASANA_ACCESS_TOKEN', ''),
        type="password",
        help="Créez un PAT sur https://app.asana.com/0/my-apps"
    )
    asana_project_gid = st.text_input(
        "Project GID",
        value=os.getenv('ASANA_PROJECT_GID', ''),
        help="GID du projet Sales Pipeline (visible dans l'URL)"
    )

    st.subheader("Google Sheets")
    gsheet_url = st.text_input(
        "URL du Spreadsheet",
        value=os.getenv('GOOGLE_SPREADSHEET_URL', ''),
        help="URL complète du Google Sheet de destination"
    )
    google_creds_path = st.text_input(
        "Chemin credentials JSON",
        value=os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json'),
        help="Chemin vers le fichier Service Account JSON"
    )

    st.divider()

    # Test connexions
    st.subheader("Tests de connexion")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔗 Test Asana", use_container_width=True):
            if not asana_token:
                st.error("Token requis")
            else:
                try:
                    client = AsanaClient(asana_token)
                    user = client.test_connection()
                    st.success(f"✅ Connecté: {user['name']}")
                except AsanaClientError as e:
                    st.error(f"❌ {e}")

    with col2:
        if st.button("📊 Test Sheets", use_container_width=True):
            if not gsheet_url or not google_creds_path:
                st.error("Config requise")
            elif not os.path.exists(google_creds_path):
                st.error(f"Fichier introuvable: {google_creds_path}")
            else:
                try:
                    syncer = GoogleSheetsSync(google_creds_path, gsheet_url)
                    info = syncer.test_connection()
                    st.success(f"✅ {info['title']}")
                except SheetsSyncError as e:
                    st.error(f"❌ {e}")


# === MAIN - Synchronisation ===
st.header("Synchronisation")

# Vérification config
config_ok = all([asana_token, asana_project_gid, gsheet_url, google_creds_path])

if not config_ok:
    st.warning("⚠️ Configurez tous les paramètres dans la sidebar avant de synchroniser.")
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
            # Étape 1: Récupération Asana
            progress.progress(10, text="Connexion à Asana...")
            asana_client = AsanaClient(asana_token)

            progress.progress(20, text="Récupération des deals...")
            tasks = asana_client.get_project_tasks(asana_project_gid)

            if not tasks:
                st.warning("Aucun deal trouvé dans le projet Asana.")
                progress.empty()
            else:
                # Étape 2: Calculs
                progress.progress(40, text=f"Traitement de {len(tasks)} deals...")
                calculator = PipelineCalculator(tasks)
                df = calculator.parse_tasks_to_dataframe()
                df = calculator.calculate_metrics()

                # Préparer les données pour Sheets
                progress.progress(60, text="Préparation des données...")
                sheets_data = calculator.prepare_sheets_data()
                summary = calculator.get_summary_metrics()

                # Étape 3: Sync Google Sheets
                progress.progress(80, text="Synchronisation vers Google Sheets...")
                syncer = GoogleSheetsSync(google_creds_path, gsheet_url)
                result = syncer.sync_pipeline(sheets_data)

                progress.progress(100, text="Terminé!")

                if result.success:
                    st.session_state.last_sync = result.timestamp
                    st.session_state.last_result = result

                    st.success(f"✅ Synchronisation réussie! {result.total_rows} lignes mises à jour.")

                    # Afficher les métriques
                    st.subheader("📈 Résumé du Pipeline")

                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Deals", summary.get('total_deals', 0))
                    m2.metric("Budget Total", f"{summary.get('total_budget', 0):,.0f} €")
                    m3.metric("Revenue Pondéré", f"{summary.get('total_revenue_pondere', 0):,.0f} €")
                    m4.metric("Marge Totale", f"{summary.get('total_marge', 0):,.0f} €")

                    m5, m6, m7, m8 = st.columns(4)
                    m5.metric("Scénario Conservateur", f"{summary.get('deals_conservateur', 0)} deals")
                    m6.metric("Budget Conservateur", f"{summary.get('revenue_conservateur', 0):,.0f} €")
                    m7.metric("Scénario Probable", f"{summary.get('deals_probable', 0)} deals")
                    m8.metric("Budget Probable", f"{summary.get('revenue_probable', 0):,.0f} €")

                    # Preview des données
                    st.subheader("📋 Aperçu des données")
                    with st.expander("Voir le pipeline complet", expanded=False):
                        st.dataframe(
                            df[[
                                'titre', 'client', 'projet', 'budget', 'marge',
                                'confidence_score', 'revenue_pondere', 'section'
                            ]],
                            use_container_width=True
                        )

                else:
                    st.error(f"❌ Erreur lors de la sync: {result.error}")

                progress.empty()

        except AsanaClientError as e:
            progress.empty()
            st.error(f"❌ Erreur Asana: {e}")
            logger.error(f"Erreur Asana: {e}")

        except SheetsSyncError as e:
            progress.empty()
            st.error(f"❌ Erreur Google Sheets: {e}")
            logger.error(f"Erreur Sheets: {e}")

        except Exception as e:
            progress.empty()
            st.error(f"❌ Erreur inattendue: {e}")
            logger.exception("Erreur inattendue")


# === Footer ===
st.divider()
st.caption("Dashboard Pipeline CFO - Genie Factory")
