"""
Page d'enrichissement SIRENE (gratuit) pour contacts HubSpot sans SIREN.
Résout nom d'entreprise ou domaine email → SIREN + données entreprise.
"""
import streamlit as st
import pandas as pd
from datetime import datetime

from core.hubspot_client import HubSpotClient
from core.sirene_client import SireneClient
from core.company_resolver import CompanyResolver
from core.scoring import LeadScorer
from config import HUBSPOT_API_KEY

# Configuration de la page
st.set_page_config(
    page_title="Enrichir SIRENE - Lead Gen SIRENE",
    page_icon="🔧",
    layout="wide"
)

st.title("🔧 Enrichir via SIRENE (Gratuit)")
st.markdown("Récupérez automatiquement le SIREN, Code APE, effectif et adresse de vos contacts HubSpot")
st.divider()

# Vérifier la configuration HubSpot
if not HUBSPOT_API_KEY or HUBSPOT_API_KEY == "your_hubspot_api_key_here":
    st.error("❌ **Clé API HubSpot non configurée**")
    st.info("Configurez votre clé API HubSpot dans la page ⚙️ Admin")
    st.stop()

# Initialiser les clients
try:
    hubspot = HubSpotClient(HUBSPOT_API_KEY)
    sirene = SireneClient()
    resolver = CompanyResolver(sirene)
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

# Filtrer les contacts sans SIREN
contacts_without_siren = [
    c for c in all_contacts
    if not c.get('siren') or not str(c.get('siren')).strip()
]

# Stats
st.subheader("📊 Statistiques")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total contacts", len(all_contacts))

with col2:
    with_siren = len(all_contacts) - len(contacts_without_siren)
    st.metric("Avec SIREN", with_siren, f"{with_siren/len(all_contacts)*100:.0f}%")

with col3:
    st.metric(
        "Sans SIREN (enrichissables)",
        len(contacts_without_siren),
        f"{len(contacts_without_siren)/len(all_contacts)*100:.0f}%"
    )

st.divider()

# Vérifier si beaucoup de contacts ont des UUIDs (companies non résolues)
import re
uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
uuid_count = sum(
    1 for c in contacts_without_siren
    if c.get('denomination') and re.match(uuid_pattern, str(c.get('denomination')).lower())
)

if uuid_count > 0:
    st.warning(f"""
    ⚠️ **{uuid_count} contacts ont des UUIDs au lieu de noms d'entreprise**

    Cela signifie que vos contacts HubSpot sont liés à des objets Company mais les noms
    ne sont pas récupérés.

    **Solution :**
    1. Ajoutez le scope `crm.objects.companies.read` à votre Private App HubSpot
    2. Re-synchronisez vos contacts (page **📋 Mes Leads HubSpot**)
    3. Les UUIDs seront automatiquement résolus en vrais noms d'entreprise

    **Ou** : L'enrichissement SIRENE utilisera les domaines email à la place.
    """)

# Si pas de contacts à enrichir
if not contacts_without_siren:
    st.success("✅ **Tous vos contacts ont déjà un SIREN !**")
    st.info("💡 Rendez-vous sur **💎 Enrichir Pappers** pour ajouter dirigeants, emails et téléphones directs")
    st.stop()

# Afficher les contacts sans SIREN
st.subheader("📋 Contacts sans SIREN")

df = pd.DataFrame(contacts_without_siren)

# Colonnes à afficher
display_columns = ['denomination', 'email', 'ville', 'code_ape', 'telephone']
display_columns = [col for col in display_columns if col in df.columns]

display_df = df[display_columns].copy()
display_df = display_df.rename(columns={
    'denomination': 'Société',
    'email': 'Email',
    'ville': 'Ville',
    'code_ape': 'Code APE',
    'telephone': 'Téléphone'
})

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    height=300
)

st.divider()

# Section enrichissement
st.subheader("🔧 Enrichissement automatique")

st.info("""
**Comment ça marche ?**

Pour chaque contact sans SIREN :
1. 🔍 Recherche via le **nom d'entreprise** (si disponible)
2. 📧 Sinon, recherche via le **domaine email** (ex: contact@ddb.fr → "ddb")
3. 🎯 Sélection du meilleur match (similarité > 60%)
4. ✅ Récupération : SIREN, Code APE, effectif, adresse complète

**100% gratuit** via l'API SIRENE officielle
""")

col1, col2 = st.columns([3, 1])

with col1:
    st.markdown(f"**{len(contacts_without_siren)} contacts** seront enrichis")

with col2:
    start_enrichment = st.button(
        "🚀 Lancer l'enrichissement",
        use_container_width=True,
        type="primary"
    )

# Lancer l'enrichissement
if start_enrichment:
    st.divider()
    st.subheader("⚙️ Enrichissement en cours...")

    progress_bar = st.progress(0)
    status_text = st.empty()
    results_container = st.container()

    enriched_count = 0
    failed_count = 0
    updates_for_hubspot = []

    # Scoring
    scorer = LeadScorer()
    score_improvements = []

    total = len(contacts_without_siren)

    for idx, contact in enumerate(contacts_without_siren):
        progress = (idx + 1) / total
        progress_bar.progress(progress)

        company_name = (contact.get('denomination') or '').strip()
        email = (contact.get('email') or '').strip()
        hubspot_id = contact.get('hubspot_id')

        # Détecter et ignorer les UUIDs (company non résolues)
        import re
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        if company_name and re.match(uuid_pattern, company_name.lower()):
            failed_count += 1
            with results_container:
                st.warning(f"⚠️ **{email or 'Contact sans email'}** → UUID non résolu (ajoutez scope 'companies.read')")
            continue

        status_text.text(f"🔍 {idx + 1}/{total} - {company_name or email or 'Contact sans info'}...")

        # Tenter la résolution
        try:
            result = resolver.resolve(
                company_name=company_name if company_name else None,
                email=email if email else None
            )

            if result:
                # Succès !
                enriched_count += 1

                # Calculer le score avant/après
                score_before = scorer.score_lead(contact)
                contact_enriched = contact.copy()
                contact_enriched.update({
                    'siren': result.get('siren', ''),
                    'code_ape': result.get('code_ape', ''),
                    'ville': result.get('ville', contact.get('ville', '')),
                    'effectif': result.get('effectif', contact.get('effectif', '')),
                })
                score_after = scorer.score_lead(contact_enriched)

                score_diff = score_after['score'] - score_before['score']
                if score_diff > 0:
                    score_improvements.append({
                        'contact': company_name or email,
                        'before': score_before['score'],
                        'after': score_after['score'],
                        'improvement': score_diff
                    })

                # Préparer la mise à jour HubSpot
                update = {
                    "hubspot_id": hubspot_id,
                    "properties": {
                        "siren": result.get('siren', ''),
                        "code_ape": result.get('code_ape', ''),
                    }
                }

                # Ajouter adresse si disponible
                if result.get('adresse'):
                    update["properties"]["address"] = result['adresse']
                if result.get('ville'):
                    update["properties"]["city"] = result['ville']
                if result.get('code_postal'):
                    update["properties"]["zip"] = result['code_postal']

                updates_for_hubspot.append(update)

                with results_container:
                    improvement_text = f" (+{score_diff} pts)" if score_diff > 0 else ""
                    st.success(f"✅ **{company_name or email}** → SIREN: {result['siren']}{improvement_text}")

            else:
                failed_count += 1
                with results_container:
                    st.warning(f"⚠️ **{company_name or email}** → Aucun match trouvé")

        except Exception as e:
            failed_count += 1
            with results_container:
                st.error(f"❌ **{company_name or email}** → Erreur: {str(e)[:100]}")

    progress_bar.progress(1.0)
    status_text.text("✅ Enrichissement terminé !")

    # Résultats finaux
    st.divider()
    st.subheader("📊 Résultats")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("✅ Enrichis", enriched_count)
    with col2:
        st.metric("⚠️ Non trouvés", failed_count)
    with col3:
        success_rate = (enriched_count / total * 100) if total > 0 else 0
        st.metric("Taux de succès", f"{success_rate:.0f}%")
    with col4:
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
        - SIREN
        - Code APE
        - Adresse complète (si trouvée)
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
st.caption("💡 **Astuce** : Après l'enrichissement SIRENE, utilisez **💎 Enrichir Pappers** pour obtenir les contacts directs (email/téléphone dirigeants)")
