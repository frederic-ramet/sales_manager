"""
Workflow d'enrichissement automatisé complet :
Sélection → SIRENE (gratuit) → Pappers (payant) → Mise à jour HubSpot
Tout en UN SEUL CLIC !
"""
import streamlit as st
import pandas as pd
from datetime import datetime

from core.hubspot_client import HubSpotClient
from core.sirene_client import SireneClient
from core.pappers_client import PappersClient
from core.company_resolver import CompanyResolver
from config import HUBSPOT_API_KEY, PAPPERS_API_KEY

# Configuration de la page
st.set_page_config(
    page_title="Workflow Auto - Lead Gen SIRENE",
    page_icon="🚀",
    layout="wide"
)

st.title("🚀 Workflow d'enrichissement automatisé")
st.markdown("Enrichissez vos contacts en **un seul clic** : SIRENE → Pappers → HubSpot")
st.divider()

# Vérifier la configuration
if not HUBSPOT_API_KEY or HUBSPOT_API_KEY == "your_hubspot_api_key_here":
    st.error("❌ **Clé API HubSpot non configurée**")
    st.stop()

# Initialiser les clients
try:
    hubspot = HubSpotClient(HUBSPOT_API_KEY)
    sirene = SireneClient()
    resolver = CompanyResolver(sirene)

    pappers_configured = PAPPERS_API_KEY and PAPPERS_API_KEY != "your_api_key_here"
    if pappers_configured:
        pappers = PappersClient(PAPPERS_API_KEY)
    else:
        pappers = None

except Exception as e:
    st.error(f"❌ Erreur d'initialisation: {e}")
    st.stop()

# Charger les contacts HubSpot
mirror = hubspot.get_mirror()
all_contacts = mirror.get("contacts", [])

if not all_contacts:
    st.warning("⚠️ **Aucun contact dans le miroir local**")
    st.info("Synchronisez vos contacts depuis **📋 Mes Leads HubSpot**")
    st.stop()

# === SECTION 1: CONFIGURATION DU WORKFLOW ===
st.subheader("⚙️ Configuration du workflow")

col1, col2 = st.columns(2)

with col1:
    enable_sirene = st.checkbox(
        "🔧 Enrichissement SIRENE (gratuit)",
        value=True,
        help="Récupère SIREN, Code APE, adresse si manquants"
    )

with col2:
    enable_pappers = st.checkbox(
        "💎 Enrichissement Pappers (payant)",
        value=pappers_configured,
        disabled=not pappers_configured,
        help="Récupère dirigeants, email/téléphone directs (1 crédit/contact)"
    )
    if not pappers_configured:
        st.caption("⚠️ Pappers non configuré")

st.divider()

# === SECTION 2: SÉLECTION DES CONTACTS ===
st.subheader("👥 Sélection des contacts")

# Filtrer par critères
filter_option = st.selectbox(
    "Filtrer les contacts à enrichir",
    [
        "Tous les contacts",
        "Sans SIREN uniquement",
        "Avec SIREN mais sans dirigeant",
        "Sans email",
        "Sans téléphone"
    ]
)

# Appliquer les filtres
if filter_option == "Sans SIREN uniquement":
    filtered_contacts = [c for c in all_contacts if not c.get('siren')]
elif filter_option == "Avec SIREN mais sans dirigeant":
    filtered_contacts = [
        c for c in all_contacts
        if c.get('siren') and not c.get('dirigeant')
    ]
elif filter_option == "Sans email":
    filtered_contacts = [c for c in all_contacts if not c.get('email')]
elif filter_option == "Sans téléphone":
    filtered_contacts = [c for c in all_contacts if not c.get('telephone')]
else:
    filtered_contacts = all_contacts

st.info(f"📊 **{len(filtered_contacts)}** contacts sélectionnés sur {len(all_contacts)} total")

# Preview des contacts
if filtered_contacts:
    with st.expander(f"👁️ Aperçu des {min(5, len(filtered_contacts))} premiers contacts"):
        df_preview = pd.DataFrame(filtered_contacts[:5])
        preview_cols = ['denomination', 'email', 'siren', 'ville']
        preview_cols = [c for c in preview_cols if c in df_preview.columns]
        st.dataframe(df_preview[preview_cols], use_container_width=True, hide_index=True)

st.divider()

# === SECTION 3: ESTIMATION ===
st.subheader("💰 Estimation")

# Estimer les coûts
contacts_need_sirene = sum(1 for c in filtered_contacts if not c.get('siren'))
contacts_need_pappers = sum(
    1 for c in filtered_contacts
    if c.get('siren') and (not c.get('dirigeant') or not c.get('telephone'))
)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("🔧 SIRENE (gratuit)", f"{contacts_need_sirene} contacts")

with col2:
    if enable_pappers:
        st.metric("💎 Pappers", f"{contacts_need_pappers} crédits")
    else:
        st.metric("💎 Pappers", "Désactivé")

with col3:
    st.metric("📊 Total à enrichir", f"{len(filtered_contacts)} contacts")

st.divider()

# === SECTION 4: LANCEMENT DU WORKFLOW ===
st.subheader("🚀 Lancement")

col1, col2 = st.columns([3, 1])

with col1:
    st.markdown(f"**Prêt à enrichir {len(filtered_contacts)} contacts**")

with col2:
    start_workflow = st.button(
        "▶️ Lancer le workflow",
        use_container_width=True,
        type="primary",
        disabled=len(filtered_contacts) == 0
    )

# Workflow execution
if start_workflow:
    st.divider()
    st.subheader("⚙️ Exécution du workflow")

    # Conteneurs pour les résultats
    progress_container = st.container()
    results_container = st.container()

    with progress_container:
        overall_progress = st.progress(0)
        status_text = st.empty()

    enriched_sirene = 0
    enriched_pappers = 0
    errors = 0
    updates_for_hubspot = []

    total_contacts = len(filtered_contacts)

    # ÉTAPE 1 : Enrichissement SIRENE
    if enable_sirene and contacts_need_sirene > 0:
        status_text.text("🔧 Étape 1/3 : Enrichissement SIRENE...")

        for idx, contact in enumerate([c for c in filtered_contacts if not c.get('siren')]):
            progress = (idx + 1) / total_contacts * 0.4  # 40% du progrès
            overall_progress.progress(progress)

            company_name = (contact.get('denomination') or '').strip()
            email = (contact.get('email') or '').strip()
            hubspot_id = contact.get('hubspot_id')

            try:
                result = resolver.resolve(
                    company_name=company_name if company_name else None,
                    email=email if email else None
                )

                if result:
                    enriched_sirene += 1
                    updates_for_hubspot.append({
                        "hubspot_id": hubspot_id,
                        "properties": {
                            "siren": result.get('siren', ''),
                            "code_ape": result.get('code_ape', ''),
                            "address": result.get('adresse', ''),
                            "city": result.get('ville', ''),
                            "zip": result.get('code_postal', '')
                        }
                    })
            except:
                errors += 1

        with results_container:
            st.success(f"✅ SIRENE : {enriched_sirene} contacts enrichis")

    # ÉTAPE 2 : Enrichissement Pappers
    if enable_pappers and pappers and contacts_need_pappers > 0:
        status_text.text("💎 Étape 2/3 : Enrichissement Pappers...")

        for idx, contact in enumerate([c for c in filtered_contacts if c.get('siren')]):
            progress = 0.4 + (idx + 1) / total_contacts * 0.4  # 40-80%
            overall_progress.progress(progress)

            siren = contact.get('siren', '').strip()
            hubspot_id = contact.get('hubspot_id')

            if not siren:
                continue

            try:
                company_data = pappers.get_company_data(siren)
                if company_data:
                    contact_info = pappers.extract_contact_info(company_data)
                    enriched_pappers += 1

                    update = {
                        "hubspot_id": hubspot_id,
                        "properties": {}
                    }

                    if contact_info.get('dirigeant_nom'):
                        update["properties"]["lastname"] = contact_info['dirigeant_nom']
                    if contact_info.get('dirigeant_prenom'):
                        update["properties"]["firstname"] = contact_info['dirigeant_prenom']
                    if contact_info.get('email'):
                        update["properties"]["email"] = contact_info['email']
                    if contact_info.get('telephone'):
                        update["properties"]["phone"] = contact_info['telephone']

                    updates_for_hubspot.append(update)
            except:
                errors += 1

        with results_container:
            st.success(f"✅ Pappers : {enriched_pappers} contacts enrichis")

    # ÉTAPE 3 : Mise à jour HubSpot
    if updates_for_hubspot:
        status_text.text("🔄 Étape 3/3 : Mise à jour HubSpot...")

        try:
            result = hubspot.update_contacts(updates_for_hubspot)
            updated = result.get("updated", 0)

            overall_progress.progress(1.0)
            status_text.text("✅ Workflow terminé !")

            with results_container:
                st.success(f"✅ HubSpot : {updated} contacts mis à jour")

        except Exception as e:
            with results_container:
                st.error(f"❌ Erreur mise à jour HubSpot : {e}")

    # RÉSUMÉ FINAL
    st.divider()
    st.subheader("📊 Résumé du workflow")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("🔧 Enrichis SIRENE", enriched_sirene)
    with col2:
        st.metric("💎 Enrichis Pappers", enriched_pappers)
    with col3:
        st.metric("✅ Mis à jour HubSpot", updated if 'updated' in locals() else 0)
    with col4:
        st.metric("⚠️ Erreurs", errors)

    st.success("🎉 **Workflow terminé avec succès !**")
    st.info("💡 Re-synchronisez vos contacts pour voir les changements")

# Footer
st.divider()
st.caption("💡 **Astuce** : Lancez ce workflow régulièrement pour maintenir vos données à jour")
