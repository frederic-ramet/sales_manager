"""
Page Synchronisation GetSales → HubSpot.
Import des leads LinkedIn avec validation manuelle et gestion des doublons.
"""
import os
import logging
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.title("🔄 GetSales Sync")
st.markdown("Synchronisation des leads LinkedIn vers HubSpot")

# Vérifier la configuration
GETSALES_API_KEY = os.getenv('GETSALES_API_KEY')
HUBSPOT_API_KEY = os.getenv('HUBSPOT_API_KEY')

if not GETSALES_API_KEY:
    st.error("❌ GETSALES_API_KEY non configurée dans .env")
    st.stop()

if not HUBSPOT_API_KEY:
    st.warning("⚠️ HUBSPOT_API_KEY non configurée - déduplication désactivée")

st.divider()

# Imports après vérification config
from modules.getsales import (
    GetSalesClient,
    GetSalesDB,
    GetSalesSyncService,
    DeduplicationService
)

# Import HubSpot si disponible
hubspot_client = None
if HUBSPOT_API_KEY:
    try:
        from modules.lead_scraper import HubSpotClient
        hubspot_client = HubSpotClient()
    except Exception as e:
        st.warning(f"⚠️ Erreur init HubSpot: {e}")


# Initialisation des services
@st.cache_resource
def get_db():
    return GetSalesDB()


@st.cache_resource
def get_getsales_client():
    return GetSalesClient()


db = get_db()
getsales_client = get_getsales_client()

# Service de sync (si HubSpot disponible)
sync_service = None
if hubspot_client:
    sync_service = GetSalesSyncService(getsales_client, hubspot_client, db)


# ============ Section 1: Contrôle Sync ============
st.header("1. Synchronisation")

col1, col2 = st.columns([2, 1])

with col1:
    # Dernière sync
    last_sync = db.get_last_sync()

    if last_sync:
        status_emoji = "✅" if last_sync.status == 'completed' else "❌" if last_sync.status == 'failed' else "⏳"
        sync_date = last_sync.sync_date or "N/A"

        st.info(f"""
        **Dernière synchronisation**: {sync_date}
        **Statut**: {status_emoji} {last_sync.status}
        **Leads récupérés**: {last_sync.leads_fetched}
        """)
    else:
        st.warning("Aucune synchronisation effectuée")

with col2:
    # Options de sync
    with st.expander("⚙️ Options", expanded=False):
        sync_limit = st.number_input("Limite de leads", min_value=10, max_value=500, value=100)
        fetch_messages = st.checkbox("Récupérer les messages", value=True)

    # Bouton sync
    sync_disabled = sync_service is None
    if st.button(
        "🔄 Synchroniser maintenant",
        type="primary",
        use_container_width=True,
        disabled=sync_disabled
    ):
        with st.spinner("Synchronisation en cours..."):
            try:
                result = sync_service.sync_leads(
                    limit=sync_limit,
                    fetch_messages=fetch_messages
                )
                st.success(f"""
                ✅ Synchronisation terminée!
                - **{result['leads_fetched']}** leads récupérés
                - **{result['leads_new']}** nouveaux
                - **{result['leads_updated']}** mis à jour
                """)
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erreur: {str(e)}")
                logger.exception("Erreur sync")

    if sync_disabled:
        st.caption("⚠️ Configurez HubSpot pour activer")

# Test connexion API
with st.expander("🔌 Test connexion API"):
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Tester GetSales"):
            success, message = getsales_client.test_connection()
            if success:
                st.success(f"✅ {message}")
            else:
                st.error(f"❌ {message}")

    with col2:
        if hubspot_client:
            if st.button("Tester HubSpot"):
                success, message = hubspot_client.test_connection()
                if success:
                    st.success(f"✅ {message}")
                else:
                    st.error(f"❌ {message}")

st.divider()

# ============ Section 2: File de validation ============
st.header("2. File de validation")

# Stats
stats = db.get_pending_stats()
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("En attente", stats['pending'])
with col2:
    st.metric("Validés", stats['approved'])
with col3:
    st.metric("Rejetés", stats['rejected'])
with col4:
    st.metric("Avec doublons", stats['with_duplicates'])

# Filtres
col1, col2 = st.columns(2)
with col1:
    filter_status = st.selectbox(
        "Statut",
        ["Tous", "En attente", "Validés", "Rejetés"],
        index=1  # Par défaut "En attente"
    )

with col2:
    filter_duplicates = st.selectbox(
        "Doublons",
        ["Tous", "Avec doublons", "Sans doublons"]
    )

# Mapper les filtres
status_map = {
    "Tous": None,
    "En attente": "pending",
    "Validés": "approved",
    "Rejetés": "rejected"
}

dup_map = {
    "Tous": None,
    "Avec doublons": "with_duplicates",
    "Sans doublons": "no_duplicates"
}

# Récupérer les leads
pending_leads = db.get_pending_leads(
    status=status_map[filter_status],
    duplicate_status=dup_map[filter_duplicates],
    limit=50
)

if not pending_leads:
    st.info("Aucun lead correspondant aux filtres")
else:
    st.markdown(f"**{len(pending_leads)} leads**")

    for lead in pending_leads:
        lead_data = lead.getsales_data
        name = f"{lead_data.get('first_name', '')} {lead_data.get('last_name', '')}".strip()
        company = lead_data.get('company_name', 'N/A')

        # Badge status
        if lead.validation_status == 'approved':
            status_badge = "✅"
        elif lead.validation_status == 'rejected':
            status_badge = "❌"
        else:
            status_badge = "⏳"

        # Badge doublon
        dup_badge = "⚠️ Doublon" if lead.duplicate_status != 'none' else ""

        with st.expander(
            f"{status_badge} {name} - {company} {dup_badge}",
            expanded=(lead.validation_status == 'pending')
        ):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Informations GetSales**")
                st.write(f"📧 Email: {lead_data.get('email', 'N/A')}")
                st.write(f"🏢 Entreprise: {company}")
                st.write(f"💼 Poste: {lead_data.get('position', 'N/A')}")

                linkedin = lead_data.get('linkedin', '')
                if linkedin:
                    if not linkedin.startswith('http'):
                        linkedin = f"https://linkedin.com/in/{linkedin}"
                    st.write(f"🔗 [LinkedIn]({linkedin})")

            with col2:
                st.markdown("**Interactions**")
                messages = lead_data.get('_messages', [])
                if messages:
                    outbox = len([m for m in messages if m.get('type') == 'outbox'])
                    inbox = len([m for m in messages if m.get('type') == 'inbox'])
                    st.write(f"📨 Messages envoyés: {outbox}")
                    st.write(f"📥 Réponses: {inbox}")

                    # Dernière interaction
                    if messages:
                        dates = [m.get('sent_at', '') for m in messages if m.get('sent_at')]
                        if dates:
                            last_date = max(dates)
                            st.write(f"🕐 Dernière: {last_date[:10]}")
                else:
                    st.write("Aucune interaction")

            # Doublons détectés
            if lead.hubspot_matches:
                st.warning(f"⚠️ {len(lead.hubspot_matches)} doublon(s) potentiel(s)")

                for match in lead.hubspot_matches:
                    contact = match.get('contact_data', {})
                    st.markdown(f"""
                    **Match {match.get('match_type')}** (confiance: {match.get('confidence')})
                    - Nom: {contact.get('firstname', '')} {contact.get('lastname', '')}
                    - Email: {contact.get('email', 'N/A')}
                    - Entreprise: {contact.get('company', 'N/A')}
                    """)
            else:
                st.success("✅ Aucun doublon détecté")

            # Actions (si pending)
            if lead.validation_status == 'pending' and sync_service:
                st.divider()
                col1, col2, col3 = st.columns(3)

                with col1:
                    if st.button("✅ Créer nouveau", key=f"create_{lead.id}", use_container_width=True):
                        try:
                            result = sync_service.validate_lead(
                                pending_lead_id=lead.id,
                                action='create_new'
                            )
                            st.success(result['message'])
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur: {e}")

                with col2:
                    if lead.hubspot_matches:
                        if st.button("🔀 Merger", key=f"merge_{lead.id}", use_container_width=True):
                            st.session_state[f'merging_{lead.id}'] = True
                            st.rerun()

                with col3:
                    if st.button("❌ Rejeter", key=f"reject_{lead.id}", use_container_width=True):
                        try:
                            result = sync_service.validate_lead(
                                pending_lead_id=lead.id,
                                action='reject'
                            )
                            st.success(result['message'])
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur: {e}")

            # Formulaire de merge (si activé)
            if st.session_state.get(f'merging_{lead.id}') and lead.hubspot_matches:
                st.divider()
                st.subheader("🔀 Fusion de contact")

                hs_match = lead.hubspot_matches[0]
                hs_contact = hs_match.get('contact_data', {})

                st.info(f"Fusion avec le contact HubSpot: {hs_contact.get('firstname', '')} {hs_contact.get('lastname', '')}")

                merge_fields = {}

                # Comparaison champ par champ
                fields = [
                    ('first_name', 'firstname', 'Prénom'),
                    ('last_name', 'lastname', 'Nom'),
                    ('email', 'email', 'Email'),
                    ('company_name', 'company', 'Entreprise'),
                    ('position', 'jobtitle', 'Poste')
                ]

                for gs_field, hs_field, label in fields:
                    gs_value = lead_data.get(gs_field, '') or ''
                    hs_value = hs_contact.get(hs_field, '') or ''

                    col1, col2, col3 = st.columns([1, 2, 2])

                    with col1:
                        st.write(f"**{label}**")

                    with col2:
                        st.text_input(
                            "GetSales",
                            value=gs_value,
                            disabled=True,
                            key=f"gs_{lead.id}_{gs_field}",
                            label_visibility="collapsed"
                        )

                    with col3:
                        st.text_input(
                            "HubSpot",
                            value=hs_value,
                            disabled=True,
                            key=f"hs_{lead.id}_{hs_field}",
                            label_visibility="collapsed"
                        )

                    # Choix
                    default_idx = 0 if gs_value else 1
                    choice = st.radio(
                        f"Choisir pour {label}",
                        ["GetSales", "HubSpot"],
                        horizontal=True,
                        index=default_idx,
                        key=f"choice_{lead.id}_{hs_field}",
                        label_visibility="collapsed"
                    )

                    merge_fields[hs_field] = 'getsales' if choice == 'GetSales' else 'hubspot'

                # Boutons confirmer/annuler
                col1, col2 = st.columns(2)

                with col1:
                    if st.button("✅ Confirmer fusion", key=f"confirm_merge_{lead.id}", type="primary", use_container_width=True):
                        try:
                            merge_data = {
                                'hubspot_contact_id': hs_match['hubspot_contact_id'],
                                'fields': merge_fields
                            }
                            result = sync_service.validate_lead(
                                pending_lead_id=lead.id,
                                action='merge',
                                merge_data=merge_data
                            )
                            del st.session_state[f'merging_{lead.id}']
                            st.success(result['message'])
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur: {e}")

                with col2:
                    if st.button("❌ Annuler", key=f"cancel_merge_{lead.id}", use_container_width=True):
                        del st.session_state[f'merging_{lead.id}']
                        st.rerun()

            # Info si déjà traité
            if lead.validation_status != 'pending':
                st.caption(f"Traité le {lead.validated_at or 'N/A'}")

st.divider()

# ============ Rafraîchir ============
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    if st.button("🔄 Rafraîchir", use_container_width=True):
        st.rerun()
