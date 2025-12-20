"""
Page Analytics : Tableaux de bord et visualisation des performances.
Stats globales, graphiques, ROI, taux de conversion.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from collections import Counter

from core.hubspot_client import HubSpotClient
from config import HUBSPOT_API_KEY, PAPPERS_API_KEY

# Configuration de la page
st.set_page_config(
    page_title="Analytics - Lead Gen SIRENE",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Analytics & Performance")
st.markdown("Visualisez vos performances d'enrichissement et de prospection")
st.divider()

# Vérifier la configuration HubSpot
if not HUBSPOT_API_KEY or HUBSPOT_API_KEY == "your_hubspot_api_key_here":
    st.warning("⚠️ **Clé API HubSpot non configurée** - Certaines métriques ne seront pas disponibles")
    hubspot = None
else:
    try:
        hubspot = HubSpotClient(HUBSPOT_API_KEY)
    except:
        hubspot = None

# Charger les données HubSpot
if hubspot:
    mirror = hubspot.get_mirror()
    contacts = mirror.get("contacts", [])
    last_sync = mirror.get("last_sync")
else:
    contacts = []
    last_sync = None

# === SECTION 1: STATS GLOBALES ===
st.subheader("📊 Vue d'ensemble")

col1, col2, col3, col4 = st.columns(4)

with col1:
    total_contacts = len(contacts)
    st.metric(
        "Total Contacts HubSpot",
        f"{total_contacts:,}",
        delta=None
    )

with col2:
    contacts_with_siren = sum(1 for c in contacts if c.get('siren'))
    pct_siren = (contacts_with_siren / total_contacts * 100) if total_contacts > 0 else 0
    st.metric(
        "Avec SIREN",
        f"{contacts_with_siren:,}",
        delta=f"{pct_siren:.1f}%",
        delta_color="normal"
    )

with col3:
    contacts_with_email = sum(1 for c in contacts if c.get('email'))
    pct_email = (contacts_with_email / total_contacts * 100) if total_contacts > 0 else 0
    st.metric(
        "Avec Email",
        f"{contacts_with_email:,}",
        delta=f"{pct_email:.1f}%",
        delta_color="normal"
    )

with col4:
    contacts_with_phone = sum(1 for c in contacts if c.get('telephone'))
    pct_phone = (contacts_with_phone / total_contacts * 100) if total_contacts > 0 else 0
    st.metric(
        "Avec Téléphone",
        f"{contacts_with_phone:,}",
        delta=f"{pct_phone:.1f}%",
        delta_color="normal"
    )

st.divider()

# === SECTION 2: TAUX DE COMPLÉTUDE ===
st.subheader("✅ Taux de complétude des données")

if total_contacts > 0:
    completeness_data = {
        "SIREN": contacts_with_siren,
        "SIRET": sum(1 for c in contacts if c.get('siret')),
        "Email": contacts_with_email,
        "Téléphone": contacts_with_phone,
        "Code APE": sum(1 for c in contacts if c.get('code_ape')),
        "Libellé APE": sum(1 for c in contacts if c.get('libelle_ape')),
        "Secteur": sum(1 for c in contacts if c.get('secteur')),
        "Ville": sum(1 for c in contacts if c.get('ville')),
        "Effectif": sum(1 for c in contacts if c.get('effectif')),
        "Tranche Effectif": sum(1 for c in contacts if c.get('effectif_tranche')),
        "Dirigeants": sum(1 for c in contacts if c.get('dirigeants') and len(c.get('dirigeants', [])) > 0),
    }

    # Créer DataFrame pour affichage
    df_completeness = pd.DataFrame([
        {
            "Champ": key,
            "Remplis": value,
            "Vides": total_contacts - value,
            "Taux": f"{value/total_contacts*100:.1f}%"
        }
        for key, value in completeness_data.items()
    ])

    # Barre de progression visuelle
    for idx, row in df_completeness.iterrows():
        pct = float(row['Taux'].rstrip('%'))
        col1, col2 = st.columns([1, 3])
        with col1:
            st.text(row['Champ'])
        with col2:
            st.progress(pct / 100)
            st.caption(f"{row['Remplis']:,} / {total_contacts:,} ({row['Taux']})")

else:
    st.info("Aucune donnée disponible pour analyse")

st.divider()

# === SECTION 3: TOP SECTEURS ===
st.subheader("🏢 Top 10 Secteurs (APE)")

if contacts:
    # Compter les codes APE
    ape_codes = [c.get('code_ape') for c in contacts if c.get('code_ape')]
    ape_counter = Counter(ape_codes)
    top_ape = ape_counter.most_common(10)

    if top_ape:
        df_ape = pd.DataFrame(top_ape, columns=['Code APE', 'Nombre'])

        # Afficher en tableau
        col1, col2 = st.columns([2, 1])

        with col1:
            st.dataframe(
                df_ape,
                use_container_width=True,
                hide_index=True
            )

        with col2:
            # Graphique simple
            st.bar_chart(df_ape.set_index('Code APE'))
    else:
        st.info("Aucun code APE renseigné")
else:
    st.info("Aucune donnée disponible")

st.divider()

# === SECTION 4: TOP VILLES ===
st.subheader("🌍 Top 10 Villes")

if contacts:
    villes = [c.get('ville') for c in contacts if c.get('ville')]
    villes_counter = Counter(villes)
    top_villes = villes_counter.most_common(10)

    if top_villes:
        df_villes = pd.DataFrame(top_villes, columns=['Ville', 'Nombre'])

        col1, col2 = st.columns([2, 1])

        with col1:
            st.dataframe(
                df_villes,
                use_container_width=True,
                hide_index=True
            )

        with col2:
            st.bar_chart(df_villes.set_index('Ville'))
    else:
        st.info("Aucune ville renseignée")

st.divider()

# === SECTION 5: ENRICHISSEMENT ===
st.subheader("💎 Potentiel d'enrichissement")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 🔧 Enrichissement SIRENE (Gratuit)")
    contacts_without_siren = total_contacts - contacts_with_siren
    st.metric(
        "Contacts enrichissables",
        f"{contacts_without_siren:,}",
        delta=f"{contacts_without_siren/total_contacts*100:.1f}% de la base" if total_contacts > 0 else "0%"
    )
    if contacts_without_siren > 0:
        st.info(f"💡 Potentiel : {contacts_without_siren:,} contacts peuvent être enrichis gratuitement via SIRENE")

with col2:
    st.markdown("#### 💎 Enrichissement Pappers (Premium)")
    contacts_enrichable_pappers = sum(
        1 for c in contacts
        if c.get('siren') and (not c.get('dirigeant') or not c.get('telephone'))
    )
    st.metric(
        "Contacts enrichissables",
        f"{contacts_enrichable_pappers:,}",
        delta=f"{contacts_enrichable_pappers} crédits nécessaires"
    )
    if contacts_enrichable_pappers > 0:
        st.info(f"💰 Coût estimé : {contacts_enrichable_pappers} crédit(s) Pappers")

st.divider()

# === SECTION 6: QUALITÉ DES DONNÉES ===
st.subheader("⭐ Score de qualité")

if total_contacts > 0:
    # Calculer un score de qualité global
    quality_score = 0
    weights = {
        'siren': 20,
        'email': 20,
        'telephone': 15,
        'code_ape': 10,
        'secteur': 10,
        'ville': 10,
        'dirigeant': 10,
        'effectif': 5
    }

    for field, weight in weights.items():
        field_filled = sum(1 for c in contacts if c.get(field))
        quality_score += (field_filled / total_contacts) * weight

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.metric(
            "Score de qualité global",
            f"{quality_score:.1f}/100",
            delta="Basé sur complétude 8 champs clés"
        )

        # Jauge visuelle
        if quality_score >= 80:
            st.success("🎉 Excellente qualité de données !")
        elif quality_score >= 60:
            st.info("👍 Bonne qualité de données")
        elif quality_score >= 40:
            st.warning("⚠️ Qualité moyenne - Enrichissement recommandé")
        else:
            st.error("❌ Qualité faible - Enrichissement nécessaire")

st.divider()

# === FOOTER ===
if last_sync:
    try:
        sync_date = datetime.fromisoformat(last_sync)
        st.caption(f"📅 Dernière synchronisation : {sync_date.strftime('%d/%m/%Y à %H:%M')}")
    except:
        st.caption("📅 Dernière synchronisation : Inconnue")
else:
    st.caption("📅 Aucune synchronisation effectuée")

st.caption("💡 **Astuce** : Synchronisez régulièrement pour des analytics à jour")
