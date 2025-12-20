"""
Page d'enrichissement Pappers (payant) pour contacts HubSpot avec SIREN.
Ajoute dirigeants, email/téléphone directs, CA, etc.
"""
import streamlit as st
import pandas as pd
from datetime import datetime

from core.hubspot_client import HubSpotClient
from core.pappers_client import PappersClient
from core.scoring import LeadScorer
from config import HUBSPOT_API_KEY, PAPPERS_API_KEY

# Configuration de la page
st.set_page_config(
    page_title="Enrichir Pappers - Lead Gen SIRENE",
    page_icon="💎",
    layout="wide"
)

st.title("💎 Enrichir via Pappers (Premium)")
st.markdown("Obtenez les contacts directs : dirigeants, emails, téléphones, CA, etc.")
st.divider()

# Vérifier la configuration
if not HUBSPOT_API_KEY or HUBSPOT_API_KEY == "your_hubspot_api_key_here":
    st.error("❌ **Clé API HubSpot non configurée**")
    st.info("Configurez votre clé API HubSpot dans la page ⚙️ Admin")
    st.stop()

if not PAPPERS_API_KEY or PAPPERS_API_KEY == "your_api_key_here":
    st.error("❌ **Clé API Pappers non configurée**")
    st.info("Configurez votre clé API Pappers dans la page ⚙️ Admin")
    st.stop()

# Initialiser les clients
try:
    hubspot = HubSpotClient(HUBSPOT_API_KEY)
    pappers = PappersClient(PAPPERS_API_KEY)
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

# Filtrer les contacts avec SIREN mais sans enrichissement Pappers
# (on considère qu'un contact est enrichi s'il a un dirigeant ou un téléphone direct)
contacts_with_siren = [
    c for c in all_contacts
    if c.get('siren') and str(c.get('siren')).strip()
]

contacts_enrichable = [
    c for c in contacts_with_siren
    if not c.get('dirigeant') or not c.get('telephone')
]

# Stats
st.subheader("📊 Statistiques")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total contacts", len(all_contacts))

with col2:
    st.metric("Avec SIREN", len(contacts_with_siren))

with col3:
    already_enriched = len(contacts_with_siren) - len(contacts_enrichable)
    st.metric("Déjà enrichis", already_enriched)

with col4:
    st.metric(
        "Enrichissables Pappers",
        len(contacts_enrichable),
        delta=None if len(contacts_enrichable) == 0 else f"-{len(contacts_enrichable)} crédits"
    )

st.divider()

# Info sur Pappers
st.info("""
💎 **Enrichissement Pappers Premium**

Chaque requête Pappers consomme **1 crédit** et ajoute :
- 👤 Dirigeant (nom, prénom, fonction)
- 📧 Email direct du dirigeant
- 📞 Téléphone direct
- 💰 Chiffre d'affaires
- 📊 Effectif exact
- 🌐 Site web

**Plan gratuit :** 100 crédits/mois | **Plans payants :** À partir de 49€/mois
""")

# Si pas de contacts sans SIREN
if not contacts_with_siren:
    st.warning("⚠️ **Aucun contact avec SIREN**")
    st.info("💡 Enrichissez d'abord vos contacts via **🔧 Enrichir SIRENE** pour obtenir leurs SIREN")
    st.stop()

# Si tous déjà enrichis
if not contacts_enrichable:
    st.success("✅ **Tous vos contacts avec SIREN sont déjà enrichis !**")
    st.balloons()
    st.stop()

# Afficher les contacts enrichissables
st.subheader(f"📋 Contacts à enrichir ({len(contacts_enrichable)})")

df = pd.DataFrame(contacts_enrichable)

# Ajouter une colonne de sélection
df_indexed = df.reset_index(drop=True)
display_columns = ['denomination', 'siren', 'email', 'ville', 'code_ape']
display_columns = [col for col in display_columns if col in df_indexed.columns]

display_df = df_indexed[display_columns].copy()
display_df.insert(0, 'Sélectionner', False)

display_df = display_df.rename(columns={
    'denomination': 'Société',
    'siren': 'SIREN',
    'email': 'Email',
    'ville': 'Ville',
    'code_ape': 'Code APE'
})

# Data editor avec checkboxes
st.info("💡 **Sélectionnez les contacts** à enrichir via Pappers (coût : 1 crédit/contact)")

edited_df = st.data_editor(
    display_df,
    use_container_width=True,
    hide_index=True,
    height=300,
    column_config={
        "Sélectionner": st.column_config.CheckboxColumn(
            "Sélectionner",
            help="Cochez pour enrichir ce contact",
            default=False
        )
    },
    disabled=[col for col in display_df.columns if col != 'Sélectionner'],
    key="pappers_contacts_editor"
)

# Compter les sélections
selected_mask = edited_df['Sélectionner']
num_selected = selected_mask.sum()

st.divider()

# Bouton enrichissement
col1, col2 = st.columns([3, 1])

with col1:
    st.markdown(f"**{num_selected} contact(s) sélectionné(s)** → Coût : **{num_selected} crédit(s) Pappers**")

with col2:
    start_enrichment = st.button(
        f"💎 Enrichir ({num_selected} crédits)",
        use_container_width=True,
        type="primary",
        disabled=num_selected == 0
    )

# Lancer l'enrichissement
if start_enrichment:
    selected_indices = df_indexed.index[selected_mask].tolist()
    selected_contacts = df_indexed.loc[selected_indices].to_dict('records')

    st.divider()
    st.subheader("⚙️ Enrichissement Pappers en cours...")

    progress_bar = st.progress(0)
    status_text = st.empty()
    results_container = st.container()

    enriched_count = 0
    failed_count = 0
    updates_for_hubspot = []

    # Scoring
    scorer = LeadScorer()
    score_improvements = []

    total = len(selected_contacts)

    for idx, contact in enumerate(selected_contacts):
        progress = (idx + 1) / total
        progress_bar.progress(progress)

        siren = contact.get('siren', '').strip()
        denomination = contact.get('denomination', 'N/A')
        hubspot_id = contact.get('hubspot_id')

        status_text.text(f"💎 {idx + 1}/{total} - {denomination} (SIREN: {siren})...")

        # Enrichissement Pappers
        try:
            company_data = pappers.get_company_data(siren)

            if company_data:
                enriched_count += 1

                # Extraire les infos de contact
                contact_info = pappers.extract_contact_info(company_data)

                # Calculer le score avant/après
                score_before = scorer.score_lead(contact)
                contact_enriched = contact.copy()

                # Créer un dirigeant formaté pour le scoring
                dirigeant_full = f"{contact_info.get('dirigeant_prenom', '')} {contact_info.get('dirigeant_nom', '')}".strip()

                contact_enriched.update({
                    'dirigeant': dirigeant_full if dirigeant_full else contact.get('dirigeant', ''),
                    'email': contact_info.get('email', contact.get('email', '')),
                    'telephone': contact_info.get('telephone', contact.get('telephone', '')),
                    'chiffre_affaires': contact_info.get('chiffre_affaires', contact.get('chiffre_affaires', '')),
                })
                score_after = scorer.score_lead(contact_enriched)

                score_diff = score_after['score'] - score_before['score']
                if score_diff > 0:
                    score_improvements.append({
                        'contact': denomination,
                        'before': score_before['score'],
                        'after': score_after['score'],
                        'improvement': score_diff
                    })

                # Préparer la mise à jour HubSpot
                update = {
                    "hubspot_id": hubspot_id,
                    "properties": {}
                }

                # Ajouter les données disponibles
                if contact_info.get('dirigeant_nom'):
                    update["properties"]["lastname"] = contact_info['dirigeant_nom']
                if contact_info.get('dirigeant_prenom'):
                    update["properties"]["firstname"] = contact_info['dirigeant_prenom']
                if contact_info.get('dirigeant_fonction'):
                    update["properties"]["jobtitle"] = contact_info['dirigeant_fonction']
                if contact_info.get('email'):
                    update["properties"]["email"] = contact_info['email']
                if contact_info.get('telephone'):
                    update["properties"]["phone"] = contact_info['telephone']
                if contact_info.get('chiffre_affaires'):
                    update["properties"]["chiffre_affaires"] = str(contact_info['chiffre_affaires'])

                updates_for_hubspot.append(update)

                with results_container:
                    improvement_text = f" (+{score_diff} pts)" if score_diff > 0 else ""
                    st.success(f"""
                    ✅ **{denomination}**{improvement_text}
                    - Dirigeant: {contact_info.get('dirigeant_prenom', '')} {contact_info.get('dirigeant_nom', 'N/A')}
                    - Email: {contact_info.get('email', 'N/A')}
                    - Téléphone: {contact_info.get('telephone', 'N/A')}
                    """)

            else:
                failed_count += 1
                with results_container:
                    st.warning(f"⚠️ **{denomination}** → Aucune donnée Pappers trouvée")

        except Exception as e:
            failed_count += 1
            with results_container:
                st.error(f"❌ **{denomination}** → Erreur: {str(e)[:100]}")

    progress_bar.progress(1.0)
    status_text.text("✅ Enrichissement terminé !")

    # Résultats finaux
    st.divider()
    st.subheader("📊 Résultats")

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("✅ Enrichis", enriched_count)
    with col2:
        st.metric("⚠️ Échecs", failed_count)
    with col3:
        st.metric("💰 Crédits utilisés", enriched_count + failed_count)
    with col4:
        success_rate = (enriched_count / total * 100) if total > 0 else 0
        st.metric("Taux de succès", f"{success_rate:.0f}%")
    with col5:
        if score_improvements:
            avg_improvement = sum(s['improvement'] for s in score_improvements) / len(score_improvements)
            st.metric("📈 Score moyen", f"+{avg_improvement:.1f} pts")

    # Afficher les améliorations de score
    if score_improvements:
        st.divider()
        st.subheader("📈 Améliorations de score")

        # Trier par amélioration décroissante
        score_improvements.sort(key=lambda x: x['improvement'], reverse=True)

        # Afficher top 10
        st.markdown("**Top 10 des améliorations :**")
        top_improvements = score_improvements[:10]

        for imp in top_improvements:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.text(f"📊 {imp['contact']}")
            with col2:
                st.text(f"{imp['before']} → {imp['after']} (+{imp['improvement']} pts)")

        if len(score_improvements) > 10:
            with st.expander(f"Voir tous les {len(score_improvements)} contacts améliorés"):
                for imp in score_improvements:
                    st.text(f"{imp['contact']}: {imp['before']} → {imp['after']} (+{imp['improvement']} pts)")

    # Bouton mise à jour HubSpot
    if updates_for_hubspot:
        st.divider()
        st.subheader("🔄 Mise à jour HubSpot")

        st.info(f"""
        **{len(updates_for_hubspot)} contacts** peuvent être mis à jour dans HubSpot avec :
        - Dirigeant (nom, prénom, fonction)
        - Email direct
        - Téléphone direct
        - Chiffre d'affaires
        """)

        if st.button("💾 Mettre à jour HubSpot", type="primary"):
            with st.spinner("Mise à jour en cours..."):
                try:
                    result = hubspot.update_contacts(updates_for_hubspot)
                    updated = result.get("updated", 0)
                    errors = result.get("errors", [])

                    if updated > 0:
                        st.success(f"✅ {updated} contacts mis à jour dans HubSpot !")
                        st.info("💡 Re-synchronisez vos contacts pour voir les changements")

                    if errors:
                        st.error(f"⚠️ {len(errors)} erreurs détectées")
                        with st.expander("Voir les erreurs"):
                            for error in errors:
                                st.text(error)

                except Exception as e:
                    st.error(f"❌ Erreur lors de la mise à jour: {e}")

# Footer
st.divider()
st.caption("💡 **Note** : Les crédits Pappers sont consommés même en cas d'échec de requête. Vérifiez vos sélections avant de lancer l'enrichissement.")
