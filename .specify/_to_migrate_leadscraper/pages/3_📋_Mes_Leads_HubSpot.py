"""
Page de visualisation et gestion des leads HubSpot.
Permet de synchroniser, filtrer, sélectionner et lancer des recherches lookalike.
"""
import streamlit as st
import pandas as pd
from datetime import datetime

from core.hubspot_client import HubSpotClient
from core.lookalike import LookalikeEngine
from core.scoring import LeadScorer
from core.sirene_client import SireneClient
from core.company_resolver import CompanyResolver
from config import HUBSPOT_API_KEY

# Configuration de la page
st.set_page_config(
    page_title="Mes Leads HubSpot - Lead Gen SIRENE",
    page_icon="📋",
    layout="wide"
)

st.title("📋 Mes Leads HubSpot")
st.markdown("Visualisez, filtrez et sélectionnez vos contacts pour des recherches lookalike")
st.divider()


def init_session_state():
    """Initialise les variables de session."""
    if 'selected_contacts' not in st.session_state:
        st.session_state.selected_contacts = []
    if 'lookalike_profile' not in st.session_state:
        st.session_state.lookalike_profile = None


init_session_state()

# Vérifier la configuration HubSpot
if not HUBSPOT_API_KEY or HUBSPOT_API_KEY == "your_hubspot_api_key_here":
    st.error("❌ **Clé API HubSpot non configurée**")
    st.info("Configurez votre clé API HubSpot dans la page ⚙️ Admin")
    st.stop()

# Initialiser le client HubSpot
try:
    hubspot = HubSpotClient(HUBSPOT_API_KEY)
except Exception as e:
    st.error(f"❌ Erreur d'initialisation HubSpot: {e}")
    st.stop()

# Bouton sync en haut à droite
col1, col2 = st.columns([5, 1])

with col2:
    # Afficher date dernière sync
    mirror = hubspot.get_mirror()
    last_sync = mirror.get("last_sync")
    if last_sync:
        try:
            sync_date = datetime.fromisoformat(last_sync)
            st.caption(f"Sync: {sync_date.strftime('%d/%m %Hh%M')}")
        except:
            st.caption("Sync: N/A")

    if st.button("🔄 Synchroniser", use_container_width=True, type="primary"):
        with st.spinner("Synchronisation en cours..."):
            try:
                result = hubspot.sync_contacts()
                st.success(f"✅ {result['total_contacts']} contacts synchronisés")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erreur: {e}")

# Charger les contacts depuis le miroir
mirror = hubspot.get_mirror()
contacts = mirror.get("contacts", [])

if not contacts:
    st.info("ℹ️ **Aucun contact dans HubSpot**")
    st.markdown("""
    Cliquez sur **🔄 Synchroniser** pour récupérer vos contacts depuis HubSpot.

    Si vous n'avez aucun contact dans HubSpot, commencez par faire une extraction
    depuis la page **📍 Lead Gen SIRENE** et exportez vers HubSpot.
    """)
    st.stop()

# Convertir en DataFrame
df = pd.DataFrame(contacts)

# Calculer le score pour chaque contact
scorer = LeadScorer()
scored_contacts = scorer.score_batch(contacts)
df = pd.DataFrame(scored_contacts)

# Stats globales
st.subheader("📊 Statistiques")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total contacts", len(df))

with col2:
    with_siren = df[df['siren'].notna() & (df['siren'] != '')].shape[0]
    st.metric("Avec SIREN", with_siren, f"{with_siren/len(df)*100:.0f}%")

with col3:
    with_email = df[df['email'].notna() & (df['email'] != '')].shape[0]
    st.metric("Avec email", with_email, f"{with_email/len(df)*100:.0f}%")

with col4:
    avg_score = df['score'].mean()
    st.metric("Score moyen", f"{avg_score:.0f}/100")

# Stats par catégorie de score
col1, col2, col3, col4 = st.columns(4)

with col1:
    hot_count = len(df[df['score'] >= 70])
    st.metric("🔥 Hot (≥70)", hot_count, f"{hot_count/len(df)*100:.0f}%")

with col2:
    warm_count = len(df[(df['score'] >= 50) & (df['score'] < 70)])
    st.metric("🌡️ Warm (50-69)", warm_count, f"{warm_count/len(df)*100:.0f}%")

with col3:
    cold_count = len(df[(df['score'] >= 30) & (df['score'] < 50)])
    st.metric("❄️ Cold (30-49)", cold_count, f"{cold_count/len(df)*100:.0f}%")

with col4:
    frozen_count = len(df[df['score'] < 30])
    st.metric("🧊 Frozen (<30)", frozen_count, f"{frozen_count/len(df)*100:.0f}%")

st.divider()

# Filtres
st.subheader("🔍 Filtres")

col1, col2, col3, col4 = st.columns(4)

with col1:
    search_text = st.text_input(
        "Recherche (dénomination, email, SIREN)",
        placeholder="Tapez pour filtrer..."
    )

with col2:
    # Filtre score
    score_filter = st.multiselect(
        "Catégorie de score",
        options=["🔥 Hot", "🌡️ Warm", "❄️ Cold", "🧊 Frozen"],
        default=[]
    )

with col3:
    # Filtre secteur
    secteurs_disponibles = df[df['code_ape'].notna() & (df['code_ape'] != '')]['code_ape'].unique().tolist()
    secteur_filter = st.multiselect(
        "Secteur (APE)",
        options=sorted(secteurs_disponibles),
        default=[]
    )

with col4:
    # Filtre ville
    villes_disponibles = df[df['ville'].notna() & (df['ville'] != '')]['ville'].unique().tolist()
    ville_filter = st.multiselect(
        "Ville",
        options=sorted(villes_disponibles),
        default=[]
    )

# Appliquer les filtres
filtered_df = df.copy()

if search_text:
    mask = (
        filtered_df['denomination'].str.contains(search_text, case=False, na=False) |
        filtered_df['email'].str.contains(search_text, case=False, na=False) |
        filtered_df['siren'].str.contains(search_text, case=False, na=False)
    )
    filtered_df = filtered_df[mask]

if score_filter:
    score_mask = pd.Series([False] * len(filtered_df), index=filtered_df.index)
    if "🔥 Hot" in score_filter:
        score_mask |= (filtered_df['score'] >= 70)
    if "🌡️ Warm" in score_filter:
        score_mask |= ((filtered_df['score'] >= 50) & (filtered_df['score'] < 70))
    if "❄️ Cold" in score_filter:
        score_mask |= ((filtered_df['score'] >= 30) & (filtered_df['score'] < 50))
    if "🧊 Frozen" in score_filter:
        score_mask |= (filtered_df['score'] < 30)
    filtered_df = filtered_df[score_mask]

if secteur_filter:
    filtered_df = filtered_df[filtered_df['code_ape'].isin(secteur_filter)]

if ville_filter:
    filtered_df = filtered_df[filtered_df['ville'].isin(ville_filter)]

st.caption(f"{len(filtered_df)} contacts affichés (sur {len(df)} total)")

st.divider()

# Tableau de sélection
st.subheader("📋 Contacts")

if len(filtered_df) == 0:
    st.warning("Aucun contact ne correspond aux filtres")
else:
    # Ajouter une colonne de sélection
    filtered_df_indexed = filtered_df.reset_index(drop=True)

    # Colonnes à afficher (ajout du score)
    display_columns = ['denomination', 'score', 'score_category', 'secteur', 'code_ape', 'ville', 'email', 'telephone', 'effectif']
    display_columns = [col for col in display_columns if col in filtered_df_indexed.columns]

    # Préparer le dataframe pour l'affichage avec checkbox
    display_df = filtered_df_indexed[display_columns].copy()
    display_df.insert(0, 'Sélectionner', False)  # Colonne checkbox au début

    # Renommer pour l'affichage
    column_names = {
        'denomination': 'Société',
        'score': 'Score',
        'score_category': 'Qualité',
        'secteur': 'Industrie',
        'code_ape': 'Code APE',
        'ville': 'Ville',
        'email': 'Email',
        'telephone': 'Téléphone',
        'effectif': 'Effectif'
    }
    display_df = display_df.rename(columns=column_names)

    # Afficher avec sélection
    st.info("💡 **Sélectionnez les contacts** avec les checkboxes, puis cliquez sur \"Trouver des similaires\" ou \"Enrichir sélection\"")

    # Data editor avec checkboxes
    edited_df = st.data_editor(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=400,
        column_config={
            "Sélectionner": st.column_config.CheckboxColumn(
                "Sélectionner",
                help="Cochez pour sélectionner ce contact",
                default=False
            ),
            "Score": st.column_config.ProgressColumn(
                "Score",
                help="Score de qualité (0-100)",
                min_value=0,
                max_value=100,
                format="%d"
            ),
            "Qualité": st.column_config.TextColumn(
                "Qualité",
                help="Catégorie de score"
            )
        },
        disabled=[col for col in display_df.columns if col != 'Sélectionner'],  # Seule la colonne checkbox est éditable
        key="contacts_editor"
    )

    # Compter les sélections
    selected_mask = edited_df['Sélectionner']
    num_selected = selected_mask.sum()

    # Récupérer les indices des contacts sélectionnés
    selected_indices = filtered_df_indexed.index[selected_mask].tolist()
    selected_contacts_df = filtered_df_indexed.loc[selected_indices]

    # Boutons d'action
    st.divider()

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        st.markdown(f"**{num_selected} contact(s) sélectionné(s)** sur {len(filtered_df)} affichés")

    with col2:
        if st.button(
            "🔍 Trouver des similaires",
            use_container_width=True,
            type="primary",
            disabled=num_selected == 0
        ):
            # Convertir la sélection en liste de dicts
            selected_contacts = selected_contacts_df.to_dict('records')

            # Créer le profil lookalike
            try:
                from core.lookalike import LookalikeEngine
                import json

                # Charger les codes APE pour l'expansion
                try:
                    with open("data/codes_ape.json", 'r') as f:
                        codes_ape_data = json.load(f)
                except:
                    codes_ape_data = []

                engine = LookalikeEngine(codes_ape_data)
                profile = engine.build_profile(selected_contacts)

                # Sauvegarder dans session state
                st.session_state.lookalike_profile = profile
                st.session_state.selected_contacts = selected_contacts

                # Rediriger vers la page Lookalike
                st.success(f"✅ Profil généré depuis {len(selected_contacts)} contacts !")
                st.info("👉 Rendez-vous sur la page **🔍 Lookalike** pour lancer la recherche")

            except Exception as e:
                st.error(f"❌ Erreur lors de la génération du profil: {e}")
                import logging
                logging.exception("Erreur profil lookalike")

    with col3:
        if st.button(
            "💎 Enrichir sélection",
            use_container_width=True,
            disabled=num_selected == 0
        ):
            st.session_state.show_enrichment = True
            st.session_state.contacts_to_enrich = selected_contacts_df.to_dict('records')
            st.rerun()

# Section enrichissement
if st.session_state.get('show_enrichment', False):
    st.divider()
    st.subheader("💎 Enrichissement des contacts sélectionnés")

    contacts_to_enrich = st.session_state.get('contacts_to_enrich', [])

    if st.button("❌ Fermer"):
        st.session_state.show_enrichment = False
        st.rerun()

    # Afficher chaque contact avec option d'enrichissement
    for idx, contact in enumerate(contacts_to_enrich):
        with st.expander(f"📋 {contact.get('denomination', 'N/A')} - {contact.get('ville', 'N/A')}", expanded=(idx == 0)):
            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown("**Informations actuelles:**")
                # Informations de base
                info_data = {
                    "SIREN": contact.get('siren', 'N/A'),
                    "SIRET": contact.get('siret', 'N/A'),
                    "Code APE": contact.get('code_ape', 'N/A'),
                    "Secteur": f"{contact.get('libelle_ape', contact.get('secteur', 'N/A'))}",
                    "Ville": contact.get('ville', 'N/A'),
                    "Effectif": contact.get('effectif', 'N/A'),
                    "Tranche": contact.get('effectif_tranche', 'N/A'),
                    "CA": contact.get('chiffre_affaires', 'N/A'),
                    "Email": contact.get('email', 'N/A'),
                    "Téléphone": contact.get('telephone', 'N/A'),
                }
                for key, value in info_data.items():
                    st.text(f"{key}: {value}")

                # Afficher les dirigeants si disponibles
                dirigeants = contact.get('dirigeants', [])
                if dirigeants:
                    st.markdown("**Dirigeants:**")
                    for dir in dirigeants:
                        nom_complet = f"{dir.get('prenom', '')} {dir.get('nom', '')}".strip()
                        fonction = dir.get('fonction', '')
                        st.text(f"• {nom_complet} - {fonction}")

            with col2:
                siren = contact.get('siren', '').strip()

                if siren:
                    st.info("✅ SIREN disponible")

                    if st.button(f"🔍 Enrichir via SIRENE V2", key=f"sirene_{idx}"):
                        with st.spinner("Enrichissement SIRENE V2..."):
                            try:
                                from core.sirene_client_v2 import SireneClientV2
                                sirene_v2 = SireneClientV2()
                                # Récupérer données complètes
                                data = sirene_v2.get_full_company_data(siren)
                                if data:
                                    st.success("✅ Données SIRENE V2:")

                                    # Affichage formaté
                                    st.markdown(f"""
                                    **Entreprise:** {data.get('denomination', 'N/A')}
                                    **SIRET:** {data.get('siret_siege', 'N/A')}
                                    **APE:** {data.get('code_ape', 'N/A')} - {data.get('libelle_ape', 'N/A')}
                                    **Effectif:** {data.get('effectif', 'N/A')} ({data.get('effectif_tranche', 'N/A')})
                                    **Adresse:** {data.get('adresse', {}).get('complete', 'N/A')}
                                    **Ville:** {data.get('ville', 'N/A')} ({data.get('code_postal', 'N/A')})
                                    """)

                                    # Bouton pour sauvegarder dans HubSpot
                                    if st.button(f"💾 Mettre à jour HubSpot", key=f"update_hs_{idx}"):
                                        hubspot_id = contact.get('hubspot_id')
                                        if hubspot_id:
                                            update = {
                                                "hubspot_id": hubspot_id,
                                                "properties": {
                                                    "siret": data.get('siret_siege', ''),
                                                    "libelle_ape": data.get('libelle_ape', ''),
                                                    "effectif_tranche": data.get('effectif_tranche', '')
                                                }
                                            }
                                            try:
                                                result = hubspot.update_contacts([update])
                                                if result.get("updated", 0) > 0:
                                                    st.success("✅ Contact mis à jour dans HubSpot!")
                                                else:
                                                    st.warning("⚠️ Aucune mise à jour effectuée")
                                            except Exception as e:
                                                st.error(f"❌ Erreur mise à jour: {e}")
                                else:
                                    st.warning("Aucune donnée trouvée")
                            except Exception as e:
                                st.error(f"Erreur: {e}")

                    # Pappers si configuré
                    from config import PAPPERS_API_KEY
                    if PAPPERS_API_KEY and PAPPERS_API_KEY != "your_api_key_here":
                        if st.button(f"💎 Enrichir via Pappers", key=f"pappers_{idx}"):
                            with st.spinner("Enrichissement Pappers..."):
                                try:
                                    from core.pappers_client import PappersClient
                                    pappers = PappersClient(PAPPERS_API_KEY)
                                    data = pappers.get_company_data(siren)
                                    if data:
                                        st.success("✅ Données Pappers:")
                                        st.json(data)
                                    else:
                                        st.warning("Aucune donnée trouvée")
                                except Exception as e:
                                    st.error(f"Erreur: {e}")
                    else:
                        st.caption("⚠️ Pappers non configuré")

                    # Enrichissement téléphone (Phase 2)
                    if not contact.get('telephone'):
                        from config import GOOGLE_MAPS_API_KEY
                        if GOOGLE_MAPS_API_KEY and GOOGLE_MAPS_API_KEY != "your_google_maps_api_key_here":
                            if st.button(f"📞 Rechercher téléphone", key=f"phone_{idx}"):
                                with st.spinner("Recherche téléphone via Google Maps..."):
                                    try:
                                        from core.phone_enricher import PhoneEnricher
                                        enricher = PhoneEnricher(GOOGLE_MAPS_API_KEY)

                                        result = enricher.enrich(
                                            company_name=contact.get('denomination', ''),
                                            siren=siren,
                                            address=contact.get('adresse'),
                                            city=contact.get('ville'),
                                            website=contact.get('website')
                                        )

                                        if result:
                                            st.success(f"✅ **Téléphone trouvé : {result['phone']}**")
                                            st.markdown(f"""
                                            **Source :** {result['source']}
                                            **Confiance :** {result['confidence']:.0%}
                                            **Vérifié :** {'Oui' if result['verified'] else 'Non'}
                                            """)

                                            # Bouton pour sauvegarder
                                            if st.button(f"💾 Enregistrer téléphone", key=f"save_phone_{idx}"):
                                                hubspot_id = contact.get('hubspot_id')
                                                if hubspot_id:
                                                    update = {
                                                        "hubspot_id": hubspot_id,
                                                        "properties": {
                                                            "phone": result['phone']
                                                        }
                                                    }
                                                    try:
                                                        hubspot_result = hubspot.update_contacts([update])
                                                        if hubspot_result.get("updated", 0) > 0:
                                                            st.success("✅ Téléphone enregistré dans HubSpot!")
                                                        else:
                                                            st.warning("⚠️ Aucune mise à jour")
                                                    except Exception as e:
                                                        st.error(f"❌ Erreur: {e}")
                                        else:
                                            st.warning("⚠️ Aucun téléphone trouvé")
                                    except Exception as e:
                                        st.error(f"Erreur: {e}")
                        else:
                            st.caption("⚠️ Google Maps non configuré (Phase 2)")
                else:
                    # Pas de SIREN → Essayer de le trouver via CompanyResolver
                    st.warning("⚠️ SIREN manquant")

                    company_name = contact.get('denomination', '').strip()
                    email = contact.get('email', '').strip()

                    if company_name or email:
                        if st.button(f"🔍 Rechercher SIREN", key=f"resolve_{idx}"):
                            with st.spinner("Recherche SIREN via nom/email..."):
                                try:
                                    sirene_client = SireneClient()
                                    resolver = CompanyResolver(sirene_client)

                                    # Tenter la résolution
                                    result = resolver.resolve(
                                        company_name=company_name if company_name else None,
                                        email=email if email else None
                                    )

                                    if result:
                                        st.success(f"✅ **SIREN trouvé : {result.get('siren')}**")
                                        st.markdown(f"""
                                        **Entreprise :** {result.get('denomination', 'N/A')}
                                        **Code APE :** {result.get('code_ape', 'N/A')}
                                        **Ville :** {result.get('ville', 'N/A')}
                                        **Effectif :** {result.get('effectif', 'N/A')}
                                        """)

                                        # Bouton pour mettre à jour HubSpot avec ce SIREN
                                        if st.button(f"💾 Enregistrer ce SIREN dans HubSpot", key=f"save_siren_{idx}"):
                                            hubspot_id = contact.get('hubspot_id')
                                            if hubspot_id:
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

                                                try:
                                                    hubspot_result = hubspot.update_contacts([update])
                                                    if hubspot_result.get("updated", 0) > 0:
                                                        st.success("✅ SIREN enregistré dans HubSpot ! Re-synchronisez pour voir les changements.")
                                                    else:
                                                        st.error("❌ Erreur lors de l'enregistrement")
                                                except Exception as e:
                                                    st.error(f"❌ Erreur: {e}")
                                    else:
                                        st.warning(f"⚠️ Aucun SIREN trouvé pour '{company_name or email}'")
                                        st.info("💡 **Suggestions :**\n- Vérifiez l'orthographe du nom\n- Essayez avec un email professionnel\n- L'entreprise n'est peut-être pas dans SIRENE")

                                except Exception as e:
                                    st.error(f"❌ Erreur: {e}")
                    else:
                        st.caption("💡 Besoin d'un nom d'entreprise ou email pour rechercher le SIREN")

# Footer
st.divider()
st.caption("💡 **Astuce** : Synchronisez régulièrement pour garder vos données à jour")
