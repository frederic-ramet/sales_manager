"""
Page d'administration pour la configuration des clés API.
"""
import os
import streamlit as st
from pathlib import Path
import json

# Configuration de la page
st.set_page_config(
    page_title="Admin - Lead Gen SIRENE",
    page_icon="⚙️",
    layout="wide"
)

st.title("⚙️ Administration")
st.markdown("Configuration des clés API et paramètres de l'application")
st.divider()


def load_env_file() -> dict:
    """Charge le fichier .env et retourne un dict des variables."""
    env_path = Path(".env")
    env_vars = {}

    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()

    return env_vars


def save_env_file(env_vars: dict) -> None:
    """Sauvegarde les variables d'environnement dans .env."""
    env_path = Path(".env")

    with open(env_path, 'w') as f:
        f.write("# Configuration Lead Gen SIRENE\n")
        f.write("# Généré automatiquement via l'interface Admin\n\n")

        # API Pappers
        f.write("# API Pappers (enrichissement)\n")
        f.write(f"PAPPERS_API_KEY={env_vars.get('PAPPERS_API_KEY', 'your_api_key_here')}\n\n")

        # Google Sheets
        f.write("# Google Sheets\n")
        f.write(f"GOOGLE_SHEETS_CREDENTIALS_PATH={env_vars.get('GOOGLE_SHEETS_CREDENTIALS_PATH', 'credentials/gcp_service_account.json')}\n")
        f.write(f"DEFAULT_SHEET_ID={env_vars.get('DEFAULT_SHEET_ID', 'your_sheet_id_here')}\n\n")

        # Anthropic API
        f.write("# Anthropic API (recherche en langage naturel)\n")
        f.write(f"ANTHROPIC_API_KEY={env_vars.get('ANTHROPIC_API_KEY', 'your_anthropic_api_key_here')}\n")
        f.write(f"ANTHROPIC_MODEL={env_vars.get('ANTHROPIC_MODEL', 'claude-3-5-haiku-20241022')}\n\n")

        # HubSpot API
        f.write("# HubSpot API (CRM et synchronisation)\n")
        f.write(f"HUBSPOT_API_KEY={env_vars.get('HUBSPOT_API_KEY', 'your_hubspot_api_key_here')}\n")


def test_anthropic_api(api_key: str, model: str) -> tuple[bool, str]:
    """
    Teste la connexion à l'API Anthropic.

    Returns:
        (success, message)
    """
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)

        # Test simple avec un message court
        message = client.messages.create(
            model=model,
            max_tokens=10,
            messages=[
                {
                    "role": "user",
                    "content": "Réponds juste 'OK'"
                }
            ]
        )

        return True, f"✅ Connexion réussie ! Modèle: {model}"

    except Exception as e:
        return False, f"❌ Erreur: {str(e)}"


def test_pappers_api(api_key: str) -> tuple[bool, str]:
    """
    Teste la connexion à l'API Pappers.

    Returns:
        (success, message)
    """
    try:
        import httpx

        response = httpx.get(
            "https://api.pappers.fr/v2/entreprise",
            params={
                "api_token": api_key,
                "siren": "443061841"  # SIREN de test (Google France)
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            return True, f"✅ Connexion réussie ! Entreprise test: {data.get('nom_entreprise', 'OK')}"
        else:
            return False, f"❌ Erreur {response.status_code}: {response.text}"

    except Exception as e:
        return False, f"❌ Erreur: {str(e)}"


def test_hubspot_api(api_key: str) -> tuple[bool, str, dict]:
    """
    Teste la connexion à l'API HubSpot.

    Returns:
        (success, message, stats_dict)
    """
    try:
        from core.hubspot_client import HubSpotClient
        import httpx

        # Test direct pour plus de détails en cas d'erreur
        try:
            response = httpx.get(
                "https://api.hubapi.com/crm/v3/objects/contacts",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                params={"limit": 1},
                timeout=30.0
            )

            if response.status_code == 401:
                # Analyser la réponse pour donner plus de détails
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', '')
                    error_category = error_data.get('category', '')

                    detailed_msg = f"❌ Clé API invalide (401)\n\n"
                    detailed_msg += f"**Erreur HubSpot:** {error_msg}\n"
                    detailed_msg += f"**Catégorie:** {error_category}\n\n"

                    # Vérifier si c'est une Personal Access Key ou Developer Key
                    if "personal access" in error_msg.lower() or len(api_key) > 150:
                        detailed_msg += "⚠️ **Détection:** Vous utilisez probablement une Personal Access Key ou Developer API Key.\n\n"
                        detailed_msg += "Ces clés NE SONT PAS supportées pour les API CRM.\n\n"
                        detailed_msg += "**Solution:** Créez une **Private App** (voir instructions ci-dessous)"
                    else:
                        detailed_msg += "Vérifiez que vous avez copié la clé complète."

                    return False, detailed_msg, {}
                except:
                    return False, f"❌ Clé API invalide (401)\n\nRéponse: {response.text[:300]}", {}

            elif response.status_code == 403:
                return False, "❌ Permissions insuffisantes - Ajoutez 'crm.objects.contacts.read'", {}
            elif response.status_code != 200:
                return False, f"❌ Erreur HTTP {response.status_code}\n\nRéponse: {response.text[:300]}", {}

        except Exception as e:
            return False, f"❌ Erreur connexion: {str(e)}", {}

        # Si le test direct fonctionne, utiliser le client complet
        with HubSpotClient(api_key) as hubspot:
            success, message = hubspot.test_connection()

            if success:
                # Récupérer les stats du miroir
                mirror = hubspot.get_mirror()
                stats = {
                    "total_contacts": mirror.get("total_contacts", 0),
                    "last_sync": mirror.get("last_sync"),
                    "with_siren": sum(1 for c in mirror.get("contacts", []) if c.get("siren")),
                    "custom_properties_available": mirror.get("custom_properties_available", True)
                }
                return True, message, stats
            else:
                return False, message, {}

    except Exception as e:
        return False, f"❌ Erreur: {str(e)}", {}


# Charger la config actuelle
env_vars = load_env_file()

# Tabs pour organiser
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🤖 Anthropic API",
    "💎 Pappers API",
    "🟠 HubSpot CRM",
    "📊 Google Sheets",
    "ℹ️ Informations"
])

# --- TAB 1: Anthropic API ---
with tab1:
    st.header("Configuration Anthropic API")
    st.markdown("""
    L'API Anthropic (Claude) est utilisée pour la **recherche en langage naturel**.
    Elle permet de transformer des requêtes comme "PME dans la publicité à Paris" en filtres structurés.

    📚 **Obtenir une clé API:**
    1. Créez un compte sur [console.anthropic.com](https://console.anthropic.com)
    2. Générez une clé API dans la section "API Keys"
    3. Copiez-collez la clé ci-dessous
    """)

    # Formulaire Anthropic
    with st.form("anthropic_form"):
        anthropic_key = st.text_input(
            "Clé API Anthropic",
            value=env_vars.get('ANTHROPIC_API_KEY', ''),
            type="password",
            help="Commence par 'sk-ant-...'"
        )

        anthropic_model = st.selectbox(
            "Modèle Claude",
            options=[
                "claude-3-5-haiku-20241022",
                "claude-3-5-sonnet-20241022",
                "claude-3-opus-20240229"
            ],
            index=0,
            help="Haiku: rapide et économique | Sonnet: équilibré | Opus: le plus puissant"
        )

        col1, col2 = st.columns(2)
        with col1:
            test_btn = st.form_submit_button("🧪 Tester la connexion", use_container_width=True)
        with col2:
            save_btn = st.form_submit_button("💾 Sauvegarder", use_container_width=True, type="primary")

        if test_btn:
            if anthropic_key and anthropic_key != "your_anthropic_api_key_here":
                with st.spinner("Test en cours..."):
                    success, message = test_anthropic_api(anthropic_key, anthropic_model)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
            else:
                st.warning("⚠️ Veuillez entrer une clé API valide")

        if save_btn:
            env_vars['ANTHROPIC_API_KEY'] = anthropic_key
            env_vars['ANTHROPIC_MODEL'] = anthropic_model
            save_env_file(env_vars)
            st.success("✅ Configuration sauvegardée ! Redémarrez l'application pour appliquer les changements.")
            st.info("💡 Commande: `streamlit run app.py`")

# --- TAB 2: Pappers API ---
with tab2:
    st.header("Configuration Pappers API")
    st.markdown("""
    L'API Pappers est utilisée pour **enrichir** les données des entreprises :
    - Dirigeants (nom, prénom, fonction)
    - Contacts (email, téléphone)
    - Finances (chiffre d'affaires, effectif)

    📚 **Obtenir une clé API:**
    1. Créez un compte sur [pappers.fr](https://www.pappers.fr)
    2. Accédez à votre [tableau de bord API](https://www.pappers.fr/api)
    3. Copiez votre clé API

    ⚠️ **Plan gratuit:** 100 crédits (100 entreprises enrichies)
    """)

    with st.form("pappers_form"):
        pappers_key = st.text_input(
            "Clé API Pappers",
            value=env_vars.get('PAPPERS_API_KEY', ''),
            type="password"
        )

        col1, col2 = st.columns(2)
        with col1:
            test_btn_pappers = st.form_submit_button("🧪 Tester la connexion", use_container_width=True)
        with col2:
            save_btn_pappers = st.form_submit_button("💾 Sauvegarder", use_container_width=True, type="primary")

        if test_btn_pappers:
            if pappers_key and pappers_key != "your_api_key_here":
                with st.spinner("Test en cours..."):
                    success, message = test_pappers_api(pappers_key)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
            else:
                st.warning("⚠️ Veuillez entrer une clé API valide")

        if save_btn_pappers:
            env_vars['PAPPERS_API_KEY'] = pappers_key
            save_env_file(env_vars)
            st.success("✅ Configuration sauvegardée !")

# --- TAB 3: HubSpot CRM ---
with tab3:
    st.header("Configuration HubSpot CRM")

    st.warning("""
    ⚠️ **IMPORTANT:** Utilisez une **Private App** (pas Personal Access Key ou Developer API Key)
    """)

    st.markdown("""
    HubSpot permet de **synchroniser bidirectionnellement** vos contacts :
    - **Sync HubSpot → App** : Récupérer vos contacts existants pour analyse lookalike
    - **Sync App → HubSpot** : Envoyer automatiquement les nouveaux leads
    - **Déduplication automatique** : Éviter les doublons via SIREN

    ## 📚 Configuration (Private App - REQUIS)

    **⚠️ NE PAS UTILISER:**
    - ❌ Personal Access Key (Settings → Security) - **Ne fonctionne pas avec l'API CRM**
    - ❌ Developer API Key (Settings → Developer) - **Ne fonctionne pas avec l'API CRM**

    **✅ UTILISER: Private App (Legacy)**

    1. Accédez à [HubSpot Settings](https://app.hubspot.com/settings) → **Integrations** → **Private Apps**
       - Si vous ne voyez pas "Private Apps", cliquez sur "Connected Apps" puis l'onglet "Private Apps"

    2. Cliquez **"Create a private app"**

    3. **Basic Info:**
       - Nom: "Lead Gen SIRENE" (ou autre nom)
       - Description: "Synchronisation contacts SIRENE"

    4. **Scopes** (onglet "Scopes"):
       - Cherchez "crm" et cochez:
         - ✅ `crm.objects.contacts.read` (lecture contacts - **REQUIS**)
         - ✅ `crm.objects.contacts.write` (création contacts - **REQUIS pour export**)
         - ✅ `crm.objects.companies.read` (lecture entreprises - **REQUIS pour secteur/effectif**)

    5. **Créer l'app** → Un token sera généré (format: `pat-na1-...` ou `pat-eu1-...`)

    6. **Copiez le token complet** et collez-le ci-dessous

    📖 **Documentation HubSpot:**
    - [Private Apps Guide](https://developers.hubspot.com/docs/api/private-apps)
    - Les Private Apps legacy sont toujours **fully supported** par HubSpot

    ⚠️ **Longueur du token:** ~40-50 caractères (si beaucoup plus long = mauvaise clé)
    """)

    with st.form("hubspot_form"):
        hubspot_key = st.text_input(
            "Token Private App HubSpot",
            value=env_vars.get('HUBSPOT_API_KEY', ''),
            type="password",
            help="Token de votre Private App (commence par 'pat-', ~40-50 caractères)"
        )

        if hubspot_key and len(hubspot_key) > 10:
            # Détection du type de clé
            if len(hubspot_key) > 100:
                key_type = "⚠️ Personal Access Key ou Developer Key (NON SUPPORTÉ)"
                st.error(f"{key_type} - {len(hubspot_key)} caractères")
                st.caption("Cette clé ne fonctionnera pas. Créez une Private App (voir instructions ci-dessus)")
            elif hubspot_key.startswith("pat-"):
                key_type = "✅ Private App Token (CORRECT)"
                st.success(f"{key_type} - {len(hubspot_key)} caractères")
            else:
                key_type = "⚠️ Format inconnu"
                st.warning(f"{key_type} - {len(hubspot_key)} caractères")

        col1, col2 = st.columns(2)
        with col1:
            test_btn_hubspot = st.form_submit_button("🧪 Tester la connexion", use_container_width=True)
        with col2:
            save_btn_hubspot = st.form_submit_button("💾 Sauvegarder", use_container_width=True, type="primary")

        if test_btn_hubspot:
            if hubspot_key and hubspot_key != "your_hubspot_api_key_here":
                with st.spinner("Test en cours..."):
                    success, message, stats = test_hubspot_api(hubspot_key)
                    if success:
                        st.success(message)

                        # Afficher les stats du miroir si disponible
                        if stats.get("total_contacts", 0) > 0:
                            st.divider()
                            st.subheader("📊 Miroir local")

                            col_a, col_b, col_c = st.columns(3)
                            with col_a:
                                st.metric("Total contacts", stats["total_contacts"])
                            with col_b:
                                st.metric("Avec SIREN", stats["with_siren"])
                            with col_c:
                                if stats["last_sync"]:
                                    from datetime import datetime
                                    last_sync = datetime.fromisoformat(stats["last_sync"])
                                    st.metric("Dernière sync", last_sync.strftime("%d/%m/%Y %H:%M"))
                                else:
                                    st.metric("Dernière sync", "Jamais")

                            # Afficher le statut des propriétés personnalisées
                            if not stats.get("custom_properties_available", True):
                                st.warning("""
                                ⚠️ **Propriétés personnalisées non disponibles**

                                Les champs SIREN, Code APE, Effectif et Chiffre d'affaires ne sont pas synchronisés car ils n'existent pas dans votre HubSpot.

                                **Pour activer ces champs:**
                                1. Accédez à [HubSpot Settings](https://app.hubspot.com/settings) → **Properties** → **Contact Properties**
                                2. Créez les propriétés personnalisées suivantes (type: Single-line text):
                                   - `siren` (SIREN de l'entreprise)
                                   - `code_ape` (Code APE / NAF)
                                   - `effectif` (Nombre d'employés)
                                   - `chiffre_affaires` (Chiffre d'affaires)
                                3. Re-synchronisez vos contacts
                                """)

                            st.caption("💡 Utilisez la page **📋 Mes Leads HubSpot** pour synchroniser")
                        else:
                            st.info("ℹ️ Aucun contact dans le miroir local. Utilisez la page **📋 Mes Leads HubSpot** pour synchroniser.")
                    else:
                        st.error(message)
            else:
                st.warning("⚠️ Veuillez entrer une clé API valide")

        if save_btn_hubspot:
            env_vars['HUBSPOT_API_KEY'] = hubspot_key
            save_env_file(env_vars)
            st.success("✅ Configuration sauvegardée ! Redémarrez l'application pour appliquer les changements.")
            st.info("💡 Commande: `streamlit run app.py`")

# --- TAB 4: Google Sheets ---
with tab4:
    st.header("Configuration Google Sheets")
    st.markdown("""
    Google Sheets permet d'**exporter automatiquement** vos leads dans un tableur partagé.

    📚 **Configuration:**
    1. Créez un projet sur [Google Cloud Console](https://console.cloud.google.com)
    2. Activez l'API Google Sheets
    3. Créez un Service Account et téléchargez le fichier JSON
    4. Placez le fichier dans `credentials/gcp_service_account.json`
    5. Partagez votre Google Sheet avec l'email du service account
    """)

    with st.form("gsheets_form"):
        creds_path = st.text_input(
            "Chemin des credentials",
            value=env_vars.get('GOOGLE_SHEETS_CREDENTIALS_PATH', 'credentials/gcp_service_account.json')
        )

        sheet_id = st.text_input(
            "ID du Google Sheet par défaut (optionnel)",
            value=env_vars.get('DEFAULT_SHEET_ID', ''),
            help="ID trouvé dans l'URL: https://docs.google.com/spreadsheets/d/[ID]/..."
        )

        # Afficher l'email du service account si le fichier existe
        if os.path.exists(creds_path):
            try:
                with open(creds_path, 'r') as f:
                    creds_data = json.load(f)
                    if 'client_email' in creds_data:
                        st.info(f"📧 Service account: `{creds_data['client_email']}`")
                        st.caption("⚠️ Donnez accès 'Éditeur' à cet email dans votre Google Sheet")
            except:
                st.warning("⚠️ Fichier credentials invalide ou mal formaté")
        else:
            st.warning(f"⚠️ Fichier credentials non trouvé: {creds_path}")

        save_btn_gsheets = st.form_submit_button("💾 Sauvegarder", use_container_width=True, type="primary")

        if save_btn_gsheets:
            env_vars['GOOGLE_SHEETS_CREDENTIALS_PATH'] = creds_path
            env_vars['DEFAULT_SHEET_ID'] = sheet_id
            save_env_file(env_vars)
            st.success("✅ Configuration sauvegardée !")

# --- TAB 5: Informations ---
with tab5:
    st.header("Informations système")

    # Afficher l'état de toutes les configurations
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 État des APIs")

        # Anthropic
        anthropic_configured = (
            env_vars.get('ANTHROPIC_API_KEY', '') and
            env_vars.get('ANTHROPIC_API_KEY') != 'your_anthropic_api_key_here'
        )
        if anthropic_configured:
            st.success("✅ Anthropic API configurée")
        else:
            st.error("❌ Anthropic API non configurée")

        # Pappers
        pappers_configured = (
            env_vars.get('PAPPERS_API_KEY', '') and
            env_vars.get('PAPPERS_API_KEY') != 'your_api_key_here'
        )
        if pappers_configured:
            st.success("✅ Pappers API configurée")
        else:
            st.error("❌ Pappers API non configurée")

        # HubSpot
        hubspot_configured = (
            env_vars.get('HUBSPOT_API_KEY', '') and
            env_vars.get('HUBSPOT_API_KEY') != 'your_hubspot_api_key_here'
        )
        if hubspot_configured:
            st.success("✅ HubSpot API configurée")
        else:
            st.warning("⚠️ HubSpot API non configurée (optionnel)")

        # Google Sheets
        gsheets_path = env_vars.get('GOOGLE_SHEETS_CREDENTIALS_PATH', '')
        if gsheets_path and os.path.exists(gsheets_path):
            st.success("✅ Google Sheets credentials trouvées")
        else:
            st.warning("⚠️ Google Sheets credentials non trouvées")

    with col2:
        st.subheader("🔧 Fichiers de configuration")

        # .env
        if os.path.exists('.env'):
            st.success("✅ Fichier .env présent")
        else:
            st.warning("⚠️ Fichier .env manquant")

        # credentials directory
        if os.path.exists('credentials'):
            st.success("✅ Dossier credentials présent")
        else:
            st.warning("⚠️ Dossier credentials manquant")

        # data directory
        if os.path.exists('data'):
            st.success("✅ Dossier data présent")
        else:
            st.warning("⚠️ Dossier data manquant")

    st.divider()

    st.subheader("📝 Variables d'environnement actuelles")
    st.code(f"""
ANTHROPIC_API_KEY: {'✓ configurée' if anthropic_configured else '✗ non configurée'}
ANTHROPIC_MODEL: {env_vars.get('ANTHROPIC_MODEL', 'claude-3-5-haiku-20241022')}

PAPPERS_API_KEY: {'✓ configurée' if pappers_configured else '✗ non configurée'}

HUBSPOT_API_KEY: {'✓ configurée' if hubspot_configured else '✗ non configurée'}

GOOGLE_SHEETS_CREDENTIALS_PATH: {env_vars.get('GOOGLE_SHEETS_CREDENTIALS_PATH', 'non défini')}
DEFAULT_SHEET_ID: {env_vars.get('DEFAULT_SHEET_ID', 'non défini')}
    """)

    if st.button("🔄 Recharger la configuration"):
        st.rerun()
