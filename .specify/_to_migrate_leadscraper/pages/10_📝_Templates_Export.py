"""
Page Templates d'Export : Exporter les leads avec des formats personnalisables.
Supporte CSV, Excel, JSON avec colonnes sélectionnables et filtres avancés.
"""
import streamlit as st
import pandas as pd
import json
import io
from datetime import datetime

from core.hubspot_client import HubSpotClient
from core.scoring import LeadScorer
from config import HUBSPOT_API_KEY

# Configuration de la page
st.set_page_config(
    page_title="Templates Export - Lead Gen SIRENE",
    page_icon="📝",
    layout="wide"
)

st.title("📝 Templates d'Export")
st.markdown("Exportez vos leads avec des templates personnalisables (CSV, Excel, JSON)")
st.divider()

# Vérifier la configuration HubSpot
if not HUBSPOT_API_KEY or HUBSPOT_API_KEY == "your_hubspot_api_key_here":
    st.error("❌ **Clé API HubSpot non configurée**")
    st.info("Configurez votre clé API HubSpot dans la page ⚙️ Admin")
    st.stop()

# Initialiser le client HubSpot
try:
    hubspot = HubSpotClient(HUBSPOT_API_KEY)
except Exception as e:
    st.error(f"❌ Erreur d'initialisation: {e}")
    st.stop()

# Charger les contacts HubSpot
mirror = hubspot.get_mirror()
all_contacts = mirror.get("contacts", [])

if not all_contacts:
    st.warning("⚠️ **Aucun contact dans le miroir local**")
    st.info("Synchronisez d'abord vos contacts HubSpot depuis la page **📋 Mes Leads HubSpot**")
    st.stop()

# Calculer les scores
scorer = LeadScorer()
scored_contacts = scorer.score_batch(all_contacts)
df = pd.DataFrame(scored_contacts)

# === SECTION 1: TEMPLATES PRÉDÉFINIS ===
st.subheader("📋 Templates prédéfinis")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**🎯 Template Commercial**")
    st.caption("Nom, Email, Téléphone, Score")
    template_commercial = st.button("Utiliser", key="template_commercial", use_container_width=True)

with col2:
    st.markdown("**📊 Template Analyse V2**")
    st.caption("SIREN, SIRET, APE + Libellé, Effectif + Tranche, CA, Ville")
    template_analyse = st.button("Utiliser", key="template_analyse", use_container_width=True)

with col3:
    st.markdown("**💎 Template Complet**")
    st.caption("Toutes les colonnes disponibles")
    template_complet = st.button("Utiliser", key="template_complet", use_container_width=True)

# Appliquer les templates
selected_columns = []

if template_commercial:
    selected_columns = ['denomination', 'email', 'telephone', 'score', 'score_category']
    st.session_state.selected_columns = selected_columns

elif template_analyse:
    selected_columns = ['denomination', 'siren', 'siret', 'code_ape', 'libelle_ape', 'secteur', 'effectif', 'effectif_tranche', 'chiffre_affaires', 'ville']
    st.session_state.selected_columns = selected_columns

elif template_complet:
    selected_columns = list(df.columns)
    # Exclure les colonnes internes
    selected_columns = [c for c in selected_columns if c not in ['hubspot_id', 'score_breakdown', 'score_color']]
    st.session_state.selected_columns = selected_columns

# Récupérer les colonnes sélectionnées
if 'selected_columns' not in st.session_state:
    st.session_state.selected_columns = ['denomination', 'email', 'telephone', 'score', 'score_category']

st.divider()

# === SECTION 2: PERSONNALISATION ===
st.subheader("⚙️ Personnalisation de l'export")

# Toutes les colonnes disponibles
all_available_columns = [c for c in df.columns if c not in ['hubspot_id', 'score_breakdown', 'score_color']]

# Sélection des colonnes
st.markdown("**Colonnes à exporter :**")
selected_columns = st.multiselect(
    "Sélectionnez les colonnes",
    options=all_available_columns,
    default=st.session_state.selected_columns,
    help="Choisissez les colonnes à inclure dans l'export"
)

st.session_state.selected_columns = selected_columns

if not selected_columns:
    st.warning("⚠️ Sélectionnez au moins une colonne à exporter")
    st.stop()

st.divider()

# === SECTION 3: FILTRES ===
st.subheader("🔍 Filtres avancés")

col1, col2, col3 = st.columns(3)

with col1:
    # Filtre par score
    score_range = st.select_slider(
        "Score minimum",
        options=[0, 30, 50, 70, 100],
        value=0,
        help="Exporter uniquement les contacts avec un score ≥ ce seuil"
    )

with col2:
    # Filtre par catégorie
    categories_filter = st.multiselect(
        "Catégories",
        options=["🔥 Hot", "🌡️ Warm", "❄️ Cold", "🧊 Frozen"],
        default=["🔥 Hot", "🌡️ Warm", "❄️ Cold", "🧊 Frozen"],
        help="Filtrer par catégorie de score"
    )

with col3:
    # Filtre SIREN
    siren_filter = st.selectbox(
        "SIREN",
        options=["Tous", "Avec SIREN uniquement", "Sans SIREN uniquement"],
        index=0
    )

# Appliquer les filtres
filtered_df = df.copy()

# Filtre score
if score_range > 0:
    filtered_df = filtered_df[filtered_df['score'] >= score_range]

# Filtre catégories
if categories_filter:
    category_mask = pd.Series([False] * len(filtered_df), index=filtered_df.index)
    for cat in categories_filter:
        if cat == "🔥 Hot":
            category_mask |= (filtered_df['score'] >= 70)
        elif cat == "🌡️ Warm":
            category_mask |= ((filtered_df['score'] >= 50) & (filtered_df['score'] < 70))
        elif cat == "❄️ Cold":
            category_mask |= ((filtered_df['score'] >= 30) & (filtered_df['score'] < 50))
        elif cat == "🧊 Frozen":
            category_mask |= (filtered_df['score'] < 30)
    filtered_df = filtered_df[category_mask]

# Filtre SIREN
if siren_filter == "Avec SIREN uniquement":
    filtered_df = filtered_df[filtered_df['siren'].notna() & (filtered_df['siren'] != '')]
elif siren_filter == "Sans SIREN uniquement":
    filtered_df = filtered_df[~(filtered_df['siren'].notna() & (filtered_df['siren'] != ''))]

st.caption(f"**{len(filtered_df)}** contacts après filtrage (sur {len(df)} total)")

st.divider()

# === SECTION 4: PRÉVISUALISATION ===
st.subheader("👁️ Prévisualisation")

# Préparer l'export avec les colonnes sélectionnées
export_df = filtered_df[selected_columns].copy()

# Renommer les colonnes pour un meilleur affichage
column_renames = {
    'denomination': 'Société',
    'email': 'Email',
    'telephone': 'Téléphone',
    'score': 'Score',
    'score_category': 'Qualité',
    'siren': 'SIREN',
    'code_ape': 'Code APE',
    'secteur': 'Secteur',
    'ville': 'Ville',
    'effectif': 'Effectif',
    'chiffre_affaires': 'CA',
    'dirigeant': 'Dirigeant'
}

display_df = export_df.rename(columns={k: v for k, v in column_renames.items() if k in export_df.columns})

st.dataframe(
    display_df.head(10),
    use_container_width=True,
    hide_index=True
)

if len(filtered_df) > 10:
    st.caption(f"Affichage des 10 premières lignes sur {len(filtered_df)}")

st.divider()

# === SECTION 5: EXPORT ===
st.subheader("💾 Export")

col1, col2, col3 = st.columns(3)

# Timestamp pour les noms de fichiers
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

with col1:
    # Export CSV
    csv_buffer = io.StringIO()
    export_df.to_csv(csv_buffer, index=False)
    csv_data = csv_buffer.getvalue()

    st.download_button(
        label="📥 Télécharger CSV",
        data=csv_data,
        file_name=f"export_leads_{timestamp}.csv",
        mime="text/csv",
        use_container_width=True,
        help=f"Exporter {len(filtered_df)} contacts au format CSV"
    )

with col2:
    # Export Excel
    try:
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            export_df.to_excel(writer, index=False, sheet_name='Leads')
        excel_data = excel_buffer.getvalue()

        st.download_button(
            label="📊 Télécharger Excel",
            data=excel_data,
            file_name=f"export_leads_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            help=f"Exporter {len(filtered_df)} contacts au format Excel"
        )
    except ImportError:
        st.button(
            "📊 Excel (openpyxl requis)",
            disabled=True,
            use_container_width=True,
            help="Installez openpyxl : pip install openpyxl"
        )

with col3:
    # Export JSON
    json_data = export_df.to_json(orient='records', force_ascii=False, indent=2)

    st.download_button(
        label="🗂️ Télécharger JSON",
        data=json_data,
        file_name=f"export_leads_{timestamp}.json",
        mime="application/json",
        use_container_width=True,
        help=f"Exporter {len(filtered_df)} contacts au format JSON"
    )

# === SECTION 6: STATISTIQUES D'EXPORT ===
st.divider()
st.subheader("📊 Statistiques de l'export")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Contacts exportés", len(filtered_df))

with col2:
    avg_score = filtered_df['score'].mean() if 'score' in filtered_df.columns else 0
    st.metric("Score moyen", f"{avg_score:.0f}/100")

with col3:
    with_siren = len(filtered_df[filtered_df['siren'].notna() & (filtered_df['siren'] != '')])
    st.metric("Avec SIREN", f"{with_siren} ({with_siren/len(filtered_df)*100:.0f}%)")

with col4:
    with_email = len(filtered_df[filtered_df['email'].notna() & (filtered_df['email'] != '')])
    st.metric("Avec Email", f"{with_email} ({with_email/len(filtered_df)*100:.0f}%)")

# Distribution des scores
if len(filtered_df) > 0 and 'score' in filtered_df.columns:
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        hot = len(filtered_df[filtered_df['score'] >= 70])
        st.metric("🔥 Hot", f"{hot} ({hot/len(filtered_df)*100:.0f}%)")

    with col2:
        warm = len(filtered_df[(filtered_df['score'] >= 50) & (filtered_df['score'] < 70)])
        st.metric("🌡️ Warm", f"{warm} ({warm/len(filtered_df)*100:.0f}%)")

    with col3:
        cold = len(filtered_df[(filtered_df['score'] >= 30) & (filtered_df['score'] < 50)])
        st.metric("❄️ Cold", f"{cold} ({cold/len(filtered_df)*100:.0f}%)")

    with col4:
        frozen = len(filtered_df[filtered_df['score'] < 30])
        st.metric("🧊 Frozen", f"{frozen} ({frozen/len(filtered_df)*100:.0f}%)")

# Footer
st.divider()
st.caption("💡 **Astuce** : Utilisez les templates prédéfinis pour des exports rapides, ou personnalisez vos colonnes pour des besoins spécifiques")
