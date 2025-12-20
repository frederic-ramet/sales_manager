"""
Import CSV pour enrichissement :
Upload CSV → Mapping colonnes → Enrichissement SIRENE/Pappers → Export
"""
import streamlit as st
import pandas as pd
import io
from datetime import datetime

from core.sirene_client import SireneClient
from core.pappers_client import PappersClient
from core.company_resolver import CompanyResolver
from core.hubspot_client import HubSpotClient
from config import PAPPERS_API_KEY, HUBSPOT_API_KEY

# Configuration de la page
st.set_page_config(
    page_title="Import CSV - Lead Gen SIRENE",
    page_icon="📥",
    layout="wide"
)

st.title("📥 Import & Enrichissement CSV")
st.markdown("Importez vos listes existantes (clients, prospects, événements) et enrichissez-les automatiquement")
st.divider()

# Initialiser les clients
try:
    sirene = SireneClient()
    resolver = CompanyResolver(sirene)

    pappers_configured = PAPPERS_API_KEY and PAPPERS_API_KEY != "your_api_key_here"
    pappers = PappersClient(PAPPERS_API_KEY) if pappers_configured else None

    hubspot_configured = HUBSPOT_API_KEY and HUBSPOT_API_KEY != "your_hubspot_api_key_here"
    hubspot = HubSpotClient(HUBSPOT_API_KEY) if hubspot_configured else None

except Exception as e:
    st.error(f"❌ Erreur d'initialisation: {e}")
    st.stop()

# === SECTION 1: UPLOAD CSV ===
st.subheader("1️⃣ Upload du fichier CSV")

uploaded_file = st.file_uploader(
    "Choisissez un fichier CSV",
    type=['csv'],
    help="Le fichier doit contenir au minimum un nom d'entreprise OU un email"
)

if uploaded_file is None:
    st.info("""
    📋 **Format attendu :**

    Votre CSV doit contenir au moins une de ces colonnes :
    - `nom` ou `entreprise` ou `societe` (nom de l'entreprise)
    - `email` (pour extraction du domaine)

    Colonnes optionnelles :
    - `ville`, `telephone`, `prenom`, `nom_dirigeant`, etc.

    **Exemple :**
    ```
    entreprise,email,ville
    Nexans,contact@nexans.com,Paris
    DDB,info@ddb.fr,Paris
    ```
    """)
    st.stop()

# Lire le CSV
try:
    df = pd.read_csv(uploaded_file)
    st.success(f"✅ Fichier chargé : **{len(df)} lignes** × **{len(df.columns)} colonnes**")
except Exception as e:
    st.error(f"❌ Erreur de lecture du CSV : {e}")
    st.stop()

# Preview
with st.expander("👁️ Aperçu des données (5 premières lignes)"):
    st.dataframe(df.head(), use_container_width=True)

st.divider()

# === SECTION 2: MAPPING DES COLONNES ===
st.subheader("2️⃣ Mapping des colonnes")

st.info("💡 Associez les colonnes de votre CSV aux champs standards")

col1, col2 = st.columns(2)

with col1:
    company_col = st.selectbox(
        "Nom de l'entreprise",
        options=["(Non mappé)"] + list(df.columns),
        help="Colonne contenant le nom de l'entreprise"
    )

    email_col = st.selectbox(
        "Email",
        options=["(Non mappé)"] + list(df.columns),
        help="Colonne contenant l'email (professionnel)"
    )

    ville_col = st.selectbox(
        "Ville",
        options=["(Non mappé)"] + list(df.columns),
        help="Optionnel : ville de l'entreprise"
    )

with col2:
    prenom_col = st.selectbox(
        "Prénom du contact",
        options=["(Non mappé)"] + list(df.columns),
        help="Optionnel : prénom"
    )

    nom_col = st.selectbox(
        "Nom du contact",
        options=["(Non mappé)"] + list(df.columns),
        help="Optionnel : nom"
    )

    tel_col = st.selectbox(
        "Téléphone",
        options=["(Non mappé)"] + list(df.columns),
        help="Optionnel : téléphone"
    )

# Validation
if company_col == "(Non mappé)" and email_col == "(Non mappé)":
    st.error("❌ Vous devez mapper au moins **Nom de l'entreprise** OU **Email**")
    st.stop()

st.divider()

# === SECTION 3: OPTIONS D'ENRICHISSEMENT ===
st.subheader("3️⃣ Options d'enrichissement")

col1, col2, col3 = st.columns(3)

with col1:
    enrich_sirene = st.checkbox(
        "🔧 SIRENE (gratuit)",
        value=True,
        help="Récupère SIREN, Code APE, adresse"
    )

with col2:
    enrich_pappers = st.checkbox(
        "💎 Pappers (payant)",
        value=False,
        disabled=not pappers_configured,
        help="Récupère dirigeants, contacts directs (1 crédit/ligne)"
    )

with col3:
    push_hubspot = st.checkbox(
        "📤 Push vers HubSpot",
        value=False,
        disabled=not hubspot_configured,
        help="Crée les contacts dans HubSpot après enrichissement"
    )

st.divider()

# === SECTION 4: ESTIMATION ===
st.subheader("4️⃣ Estimation")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Lignes à traiter", len(df))

with col2:
    if enrich_pappers:
        st.metric("💎 Crédits Pappers", len(df), delta="1 crédit/ligne")
    else:
        st.metric("💎 Crédits Pappers", "Désactivé")

with col3:
    if push_hubspot:
        st.metric("📤 Push HubSpot", "Activé")
    else:
        st.metric("📤 Push HubSpot", "Désactivé")

st.divider()

# === SECTION 5: LANCEMENT ===
st.subheader("5️⃣ Lancement")

col1, col2 = st.columns([3, 1])

with col1:
    st.markdown(f"**Prêt à enrichir {len(df)} lignes**")

with col2:
    start_enrichment = st.button(
        "▶️ Lancer l'enrichissement",
        use_container_width=True,
        type="primary"
    )

# Enrichissement
if start_enrichment:
    st.divider()
    st.subheader("⚙️ Enrichissement en cours...")

    progress_bar = st.progress(0)
    status_text = st.empty()
    results_container = st.container()

    enriched_data = []
    enriched_sirene_count = 0
    enriched_pappers_count = 0

    for idx, row in df.iterrows():
        progress = (idx + 1) / len(df)
        progress_bar.progress(progress)

        # Récupérer les valeurs mappées
        company_name = row[company_col] if company_col != "(Non mappé)" else ""
        email = row[email_col] if email_col != "(Non mappé)" else ""

        status_text.text(f"🔍 {idx + 1}/{len(df)} - {company_name or email or 'Contact'}...")

        # Créer l'entrée enrichie
        enriched_row = row.to_dict()

        # SIRENE enrichment
        if enrich_sirene:
            try:
                result = resolver.resolve(
                    company_name=company_name if company_name else None,
                    email=email if email else None
                )

                if result:
                    enriched_sirene_count += 1
                    enriched_row['siren'] = result.get('siren', '')
                    enriched_row['code_ape'] = result.get('code_ape', '')
                    enriched_row['adresse_sirene'] = result.get('adresse', '')
                    enriched_row['ville_sirene'] = result.get('ville', '')
                    enriched_row['effectif_sirene'] = result.get('effectif', '')
            except:
                pass

        # Pappers enrichment
        if enrich_pappers and pappers and enriched_row.get('siren'):
            try:
                company_data = pappers.get_company_data(enriched_row['siren'])
                if company_data:
                    contact_info = pappers.extract_contact_info(company_data)
                    enriched_pappers_count += 1

                    enriched_row['dirigeant_prenom'] = contact_info.get('dirigeant_prenom', '')
                    enriched_row['dirigeant_nom'] = contact_info.get('dirigeant_nom', '')
                    enriched_row['dirigeant_fonction'] = contact_info.get('dirigeant_fonction', '')
                    enriched_row['email_dirigeant'] = contact_info.get('email', '')
                    enriched_row['telephone_dirigeant'] = contact_info.get('telephone', '')
                    enriched_row['chiffre_affaires'] = contact_info.get('chiffre_affaires', '')
            except:
                pass

        enriched_data.append(enriched_row)

    progress_bar.progress(1.0)
    status_text.text("✅ Enrichissement terminé !")

    # Créer DataFrame enrichi
    df_enriched = pd.DataFrame(enriched_data)

    # RÉSULTATS
    st.divider()
    st.subheader("📊 Résultats")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("✅ Lignes traitées", len(df_enriched))
    with col2:
        st.metric("🔧 Enrichis SIRENE", enriched_sirene_count)
    with col3:
        st.metric("💎 Enrichis Pappers", enriched_pappers_count)

    # Preview des résultats
    with st.expander("👁️ Aperçu des données enrichies (5 premières lignes)"):
        st.dataframe(df_enriched.head(), use_container_width=True)

    # EXPORT
    st.divider()
    st.subheader("💾 Export")

    col1, col2 = st.columns(2)

    with col1:
        # Download CSV
        csv_buffer = io.StringIO()
        df_enriched.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue()

        st.download_button(
            label="📥 Télécharger CSV enrichi",
            data=csv_data,
            file_name=f"enrichi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col2:
        # Push to HubSpot
        if push_hubspot and hubspot:
            if st.button("📤 Push vers HubSpot", use_container_width=True, type="primary"):
                with st.spinner("Push en cours..."):
                    try:
                        # Convertir en format HubSpot
                        contacts_to_push = []
                        for _, row in df_enriched.iterrows():
                            contacts_to_push.append({
                                "email": row.get('email', ''),
                                "siren": row.get('siren', ''),
                                "denomination": row.get(company_col, '') if company_col != "(Non mappé)" else '',
                                "ville": row.get('ville_sirene', ''),
                                "code_ape": row.get('code_ape', '')
                            })

                        result = hubspot.push_contacts(contacts_to_push)
                        created = result.get("created", 0)

                        st.success(f"✅ {created} contacts créés dans HubSpot !")
                    except Exception as e:
                        st.error(f"❌ Erreur push HubSpot : {e}")

    st.success("🎉 **Enrichissement terminé !**")

# Footer
st.divider()
st.caption("💡 **Astuce** : Vous pouvez réutiliser cette fonctionnalité pour enrichir régulièrement de nouvelles listes")
