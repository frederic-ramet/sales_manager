"""
Page de recherche lookalike basée sur un profil de contacts existants.
"""
import streamlit as st
import json
from datetime import datetime

from core.sirene_client import SireneClient
from core.pappers_client import PappersClient
from core.enricher import Enricher
from core.exporter import Exporter
from core.lookalike import LookalikeEngine
from core.lead_tracker import LeadTracker
from core.hubspot_client import HubSpotClient
from config import (
    GOOGLE_SHEETS_CREDENTIALS_PATH,
    DEFAULT_SHEET_ID,
    MAX_RESULTS,
    PAPPERS_API_KEY,
    HUBSPOT_API_KEY
)

# Configuration de la page
st.set_page_config(
    page_title="Lookalike - Lead Gen SIRENE",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 Recherche Lookalike")
st.markdown("Trouvez des entreprises similaires à vos contacts existants")
st.divider()


def init_session_state():
    """Initialise les variables de session."""
    if 'lookalike_profile' not in st.session_state:
        st.session_state.lookalike_profile = None
    if 'lookalike_results' not in st.session_state:
        st.session_state.lookalike_results = None
    if 'lookalike_status' not in st.session_state:
        st.session_state.lookalike_status = 'idle'


init_session_state()

# Vérifier qu'un profil a été généré
if not st.session_state.lookalike_profile:
    st.warning("⚠️ **Aucun profil lookalike disponible**")
    st.markdown("""
    ### Comment générer un profil ?

    1. Allez sur la page **📋 Mes Leads HubSpot**
    2. Synchronisez vos contacts HubSpot
    3. Filtrez les contacts qui vous intéressent
    4. Cliquez sur **"🔍 Trouver des similaires"**
    5. Revenez sur cette page

    Le profil sera généré automatiquement basé sur vos contacts sélectionnés.
    """)
    st.stop()

# Récupérer le profil
profile = st.session_state.lookalike_profile
engine = LookalikeEngine()
summary = engine.get_profile_summary(profile)

# Afficher le profil détecté
st.subheader("📊 Profil détecté")

col1, col2 = st.columns([2, 1])

with col1:
    st.info(f"**{summary['interpretation']}**")
    st.caption(f"Basé sur {summary['base_contacts']} contacts")

with col2:
    if st.button("🔄 Nouveau profil", use_container_width=True):
        st.session_state.lookalike_profile = None
        st.session_state.lookalike_results = None
        st.rerun()

# Détails du profil
with st.expander("📋 Détails du profil", expanded=False):
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Secteurs**")
        st.markdown(f"Base: {summary['secteurs']['count_base']} codes")
        for code in summary['secteurs']['base'][:5]:
            st.caption(f"• {code}")
        if summary['secteurs']['count_elargi'] > summary['secteurs']['count_base']:
            st.caption(f"+ {summary['secteurs']['count_elargi'] - summary['secteurs']['count_base']} codes élargis")

    with col2:
        st.markdown("**Zones géographiques**")
        st.markdown(f"Départements: {summary['zones']['count_dept']}")
        for dept in summary['zones']['departements'][:5]:
            st.caption(f"• {dept}")
        if summary['zones']['count_region'] > summary['zones']['count_dept']:
            st.caption(f"+ {summary['zones']['count_region'] - summary['zones']['count_dept']} depts (région)")

    with col3:
        st.markdown("**Effectifs**")
        if summary['effectifs']['min'] is not None:
            st.metric("Min", summary['effectifs']['min'])
            st.metric("Max", summary['effectifs']['max'])
            if summary['effectifs']['median']:
                st.caption(f"Médiane: {summary['effectifs']['median']}")

st.divider()

# Options d'élargissement
st.subheader("⚙️ Options de recherche")

col1, col2, col3 = st.columns(3)

with col1:
    extend_ape = st.checkbox(
        "Élargir aux secteurs proches",
        value=True,
        help=f"Utiliser {summary['secteurs']['count_elargi']} codes APE au lieu de {summary['secteurs']['count_base']}"
    )

with col2:
    extend_region = st.checkbox(
        "Élargir à toute la région",
        value=False,
        help=f"Utiliser {summary['zones']['count_region']} départements au lieu de {summary['zones']['count_dept']}"
    )

with col3:
    france_entiere = st.checkbox(
        "France entière",
        value=False,
        help="Ignorer la zone géographique"
    )

# Paramètres de recherche
col1, col2 = st.columns(2)

with col1:
    max_leads = st.number_input(
        "Nombre maximum de leads",
        min_value=1,
        max_value=MAX_RESULTS,
        value=50,
        step=10,
        help=f"Maximum {MAX_RESULTS}"
    )

with col2:
    enable_pappers = st.checkbox(
        "Enrichir avec Pappers",
        value=True,
        help="Ajouter dirigeants, email, téléphone via Pappers"
    )

st.divider()

# Bouton de lancement
if st.button("🚀 Lancer la recherche", use_container_width=True, type="primary", disabled=st.session_state.lookalike_status == 'running'):
    # Convertir le profil en paramètres de recherche
    search_params = engine.to_search_params(profile, {
        'extend_ape': extend_ape,
        'extend_region': extend_region,
        'france_entiere': france_entiere
    })

    # Lancer la recherche
    st.session_state.lookalike_status = 'running'

    progress_bar = st.progress(0)
    status_text = st.empty()
    logs = []

    def add_log(msg):
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    try:
        # Recherche SIRENE
        progress_bar.progress(10)
        status_text.text("📡 Recherche SIRENE en cours...")
        add_log("📡 Recherche des entreprises similaires via SIRENE...")

        with SireneClient() as sirene:
            companies = sirene.search_all(
                codes_ape=search_params.get('codes_ape'),
                departements=search_params.get('departements'),
                effectif_min=search_params.get('effectif_min'),
                effectif_max=search_params.get('effectif_max'),
                date_creation_min=search_params.get('date_creation_min'),
                max_results=max_leads
            )

        progress_bar.progress(30)
        add_log(f"✅ {len(companies)} entreprises trouvées")

        if not companies:
            add_log("⚠️ Aucune entreprise trouvée avec ces critères")
            st.warning("Aucune entreprise similaire trouvée. Essayez d'élargir les options.")
            st.session_state.lookalike_status = 'done'
            st.stop()

        # Déduplication
        progress_bar.progress(35)
        status_text.text("🔍 Déduplication...")

        # Déduplication SQLite
        tracker = LeadTracker()
        companies, num_dups_sqlite = tracker.filter_duplicates(companies)
        if num_dups_sqlite > 0:
            add_log(f"⚠️ {num_dups_sqlite} doublons SQLite filtrés")

        # Déduplication HubSpot
        if HUBSPOT_API_KEY and HUBSPOT_API_KEY != "your_hubspot_api_key_here":
            hubspot = HubSpotClient(HUBSPOT_API_KEY)
            enricher_temp = Enricher(None, hubspot)
            companies, num_dups_hubspot = enricher_temp.deduplicate_against_hubspot(companies)
            if num_dups_hubspot > 0:
                add_log(f"🟠 {num_dups_hubspot} doublons HubSpot filtrés")

        if not companies:
            add_log("⚠️ Toutes les entreprises ont déjà été extraites")
            st.info("Toutes les entreprises similaires ont déjà été extraites précédemment.")
            st.session_state.lookalike_status = 'done'
            st.stop()

        add_log(f"✅ {len(companies)} nouveaux leads à traiter")

        # Enrichissement
        if enable_pappers:
            progress_bar.progress(40)
            status_text.text("💎 Enrichissement Pappers...")
            add_log("💎 Enrichissement via Pappers...")

            if PAPPERS_API_KEY and PAPPERS_API_KEY != "your_api_key_here":
                with PappersClient() as pappers:
                    enricher = Enricher(pappers)
                    companies = enricher.enrich_batch(companies)
                add_log(f"✅ {len(companies)} entreprises enrichies")
            else:
                add_log("⚠️ Clé Pappers non configurée - enrichissement ignoré")

        progress_bar.progress(80)

        # Sauvegarder les résultats
        st.session_state.lookalike_results = companies
        st.session_state.lookalike_status = 'done'

        # Enregistrer dans l'historique
        campagne_id = f"lookalike_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        tracker.add_leads(companies, campagne_id=campagne_id, source="LOOKALIKE")

        progress_bar.progress(100)
        status_text.text("✅ Recherche terminée!")
        add_log("🎉 Recherche lookalike terminée avec succès!")

        # Afficher les logs
        with st.expander("📋 Logs détaillés"):
            st.text("\n".join(logs))

        st.success(f"✅ {len(companies)} entreprises similaires trouvées !")
        st.rerun()

    except Exception as e:
        st.error(f"❌ Erreur: {e}")
        st.session_state.lookalike_status = 'error'
        import logging
        logging.exception("Erreur recherche lookalike")

# Afficher les résultats
if st.session_state.lookalike_results:
    st.divider()
    st.subheader("📊 Résultats")

    results = st.session_state.lookalike_results

    # Stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total leads", len(results))
    with col2:
        with_email = sum(1 for r in results if r.get('email'))
        st.metric("Avec email", with_email, f"{with_email/len(results)*100:.0f}%")
    with col3:
        with_phone = sum(1 for r in results if r.get('telephone'))
        st.metric("Avec téléphone", with_phone, f"{with_phone/len(results)*100:.0f}%")
    with col4:
        with_dirigeant = sum(1 for r in results if r.get('dirigeant_nom'))
        st.metric("Avec dirigeant", with_dirigeant, f"{with_dirigeant/len(results)*100:.0f}%")

    st.divider()

    # Preview
    st.subheader("📋 Aperçu (10 premiers)")
    import pandas as pd
    df = pd.DataFrame(results)
    display_cols = ['siren', 'denomination', 'ville', 'code_ape', 'dirigeant_nom', 'email', 'telephone']
    display_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(df[display_cols].head(10), use_container_width=True, hide_index=True)

    st.divider()

    # Export
    st.subheader("💾 Export")

    col1, col2, col3 = st.columns(3)

    with col1:
        # CSV
        csv_data = df.to_csv(index=False, sep=';').encode('utf-8')
        st.download_button(
            "📥 Télécharger CSV",
            data=csv_data,
            file_name=f"lookalike_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col2:
        # Google Sheets
        enable_sheets = st.checkbox("Google Sheets", value=False)
        if enable_sheets:
            sheet_id = st.text_input("ID du Sheet", value=DEFAULT_SHEET_ID or "")
            if st.button("📊 Exporter vers Sheets", use_container_width=True):
                if sheet_id:
                    try:
                        exporter = Exporter(GOOGLE_SHEETS_CREDENTIALS_PATH)
                        url = exporter.to_google_sheet(results, sheet_id)
                        st.success(f"✅ Exporté: {url}")
                    except Exception as e:
                        st.error(f"❌ Erreur: {e}")
                else:
                    st.warning("ID du Sheet requis")

    with col3:
        # HubSpot
        enable_hubspot = st.checkbox("HubSpot", value=False)
        if enable_hubspot:
            if st.button("🟠 Push vers HubSpot", use_container_width=True):
                if HUBSPOT_API_KEY and HUBSPOT_API_KEY != "your_hubspot_api_key_here":
                    try:
                        hubspot = HubSpotClient(HUBSPOT_API_KEY)
                        exporter = Exporter(hubspot_client=hubspot)
                        result = exporter.to_hubspot(results)
                        st.success(f"✅ {result['created']} contacts créés dans HubSpot")
                        if result.get('errors'):
                            st.warning(f"⚠️ {len(result['errors'])} erreurs")
                    except Exception as e:
                        st.error(f"❌ Erreur: {e}")
                else:
                    st.warning("Clé HubSpot non configurée")

st.caption("💡 **Astuce** : Ajustez les options d'élargissement pour obtenir plus ou moins de résultats")
