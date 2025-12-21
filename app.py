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
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Navigation top bar
from components import render_top_nav, hide_sidebar, render_footer
hide_sidebar()

st.title("🏭 Sales Ops Portal")
st.markdown("**Genie Factory** - Outils de gestion commerciale")

render_top_nav(current_page="app.py")

st.divider()

# === Statut des modules ===
col1, col2 = st.columns(2)

# --- Module 1: Lead Scraper ---
with col1:
    st.subheader("🎯 Lead Scraper")
    st.markdown("Recherche et enrichissement de leads B2B")

    # Vérifier la config
    pappers_ok = bool(os.getenv('PAPPERS_API_KEY'))
    hubspot_ok = bool(os.getenv('HUBSPOT_API_KEY'))
    anthropic_ok = bool(os.getenv('ANTHROPIC_API_KEY'))

    if pappers_ok:
        st.success("✅ Pappers configuré")
    else:
        st.warning("⚠️ Pappers non configuré (enrichissement désactivé)")

    if hubspot_ok:
        st.caption("✅ HubSpot configuré")
    if anthropic_ok:
        st.caption("✅ Claude AI configuré (recherche NL)")

    st.page_link("pages/2_🎯_Recherche_Leads.py", label="Ouvrir Lead Scraper", icon="🎯")

# --- Module 2: GetSales Sync ---
with col2:
    st.subheader("🔄 GetSales Sync")
    st.markdown("Synchronisation leads LinkedIn → HubSpot")

    # Vérifier la config
    getsales_ok = bool(os.getenv('GETSALES_API_KEY'))
    hubspot_sync_ok = bool(os.getenv('HUBSPOT_API_KEY'))

    if getsales_ok and hubspot_sync_ok:
        st.success("✅ Configuré")
    elif getsales_ok:
        st.warning("⚠️ HubSpot non configuré (déduplication désactivée)")
    elif hubspot_sync_ok:
        st.warning("⚠️ GetSales non configuré")
    else:
        st.error("❌ Non configuré")

    st.page_link("pages/4_🔄_GetSales_Sync.py", label="Ouvrir GetSales Sync", icon="🔄")

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

render_footer()
