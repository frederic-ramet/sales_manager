"""
Sales Ops Portal - Genie Factory
Page d'accueil avec statut des modules.
"""

import streamlit as st
import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Configuration de la page (uniquement dans app.py principal)
st.set_page_config(
    page_title="Sales Ops - Genie Factory",
    page_icon="🏭",
    layout="wide"
)

st.title("🏭 Sales Ops Portal")
st.markdown("**Genie Factory** - Outils de gestion commerciale")

st.divider()

# === Statut des modules ===
col1, col2 = st.columns(2)

# --- Module 1: Dashboard CFO ---
with col1:
    st.subheader("📊 Dashboard Pipeline CFO")
    st.markdown("Synchronisation Asana → Google Sheets")

    # Vérifier la config
    asana_ok = bool(os.getenv('ASANA_ACCESS_TOKEN')) and bool(os.getenv('ASANA_PROJECT_GID'))
    sheets_ok = bool(os.getenv('GOOGLE_SPREADSHEET_URL')) and os.path.exists(
        os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials/service-account.json')
    )

    if asana_ok and sheets_ok:
        st.success("✅ Configuré")
    elif asana_ok:
        st.warning("⚠️ Google Sheets non configuré")
    elif sheets_ok:
        st.warning("⚠️ Asana non configuré")
    else:
        st.error("❌ Non configuré")

    # Dernière sync
    if 'last_sync' in st.session_state and st.session_state.last_sync:
        st.caption(f"Dernière sync: {st.session_state.last_sync}")

    st.page_link("pages/1_📊_Pipeline_CFO.py", label="Ouvrir le Dashboard CFO", icon="📊")

# --- Module 2: Lead Scraper ---
with col2:
    st.subheader("🎯 Lead Scraper")
    st.markdown("Recherche et enrichissement de leads B2B")

    # Vérifier la config
    pappers_ok = bool(os.getenv('PAPPERS_API_KEY'))
    hubspot_ok = bool(os.getenv('HUBSPOT_API_KEY'))

    st.info("🚧 Module en cours de migration")

    if pappers_ok:
        st.caption("✅ Pappers configuré")
    if hubspot_ok:
        st.caption("✅ HubSpot configuré")

st.divider()

# === Liens rapides ===
st.subheader("🔗 Liens rapides")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**Documentation**")
    st.markdown("- [Asana API](https://developers.asana.com)")
    st.markdown("- [Google Sheets API](https://developers.google.com/sheets)")

with col2:
    st.markdown("**Configuration**")
    st.markdown("- Éditer `.env` pour les credentials")
    st.markdown("- Dossier `credentials/` pour les fichiers JSON")

with col3:
    st.markdown("**Support**")
    st.markdown("- Voir `.specify/` pour les specs")
    st.markdown("- README.md pour le guide")

st.divider()
st.caption("Sales Ops Portal - Genie Factory")
