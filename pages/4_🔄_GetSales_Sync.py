"""
Page GetSales Sync - REDIRECTION vers Import.
Cette fonctionnalité a été intégrée dans la page Import unifiée.
"""
import streamlit as st

st.set_page_config(page_title="GetSales Sync", page_icon="🔄")

st.info("🔄 La synchronisation GetSales a été intégrée dans la page **Import**.")
st.markdown("Vous allez être redirigé...")

# Redirection automatique
st.switch_page("pages/5_📤_Import.py")
