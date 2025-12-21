"""
Composant de navigation horizontale en haut de page.
Remplace la sidebar Streamlit par défaut.
"""
import streamlit as st
from pathlib import Path


# Pages disponibles
PAGES = [
    {"icon": "🏭", "name": "Accueil", "path": "app.py"},
    {"icon": "📊", "name": "Pipeline CFO", "path": "pages/1_📊_Pipeline_CFO.py"},
    {"icon": "🎯", "name": "Recherche", "path": "pages/2_🎯_Recherche_Leads.py"},
    {"icon": "📜", "name": "Base Leads", "path": "pages/3_📜_Base_de_Leads.py"},
    {"icon": "🔄", "name": "GetSales", "path": "pages/4_🔄_GetSales_Sync.py"},
]


def hide_sidebar():
    """Cache complètement la sidebar Streamlit."""
    st.markdown("""
    <style>
        /* Cacher la sidebar */
        [data-testid="stSidebar"] {
            display: none;
        }
        [data-testid="stSidebarNav"] {
            display: none;
        }
        /* Cacher le bouton hamburger */
        button[kind="header"] {
            display: none;
        }
        /* Ajuster le contenu principal */
        .stMainBlockContainer {
            padding-top: 1rem;
        }
        /* Style navigation */
        .top-nav-container {
            display: flex;
            gap: 0.5rem;
            padding: 0.5rem 0;
            margin-bottom: 1rem;
            border-bottom: 1px solid #e0e0e0;
        }
        .nav-button {
            padding: 0.5rem 1rem;
            border-radius: 0.5rem;
            text-decoration: none;
            transition: background-color 0.2s;
        }
        .nav-button:hover {
            background-color: #f0f0f0;
        }
        .nav-button.active {
            background-color: #ff4b4b;
            color: white;
        }
    </style>
    """, unsafe_allow_html=True)


def get_current_page() -> str:
    """Détecte la page courante."""
    # Streamlit stocke le chemin dans query_params ou on peut déduire du contexte
    # En pratique, on passe le nom de la page en paramètre
    return st.session_state.get('current_page', 'app.py')


def render_top_nav(current_page: str = None):
    """
    Affiche la barre de navigation horizontale.

    Args:
        current_page: Chemin de la page courante (ex: "pages/2_🎯_Recherche_Leads.py")
    """
    # Créer les colonnes pour les boutons de navigation
    cols = st.columns(len(PAGES))

    for i, page in enumerate(PAGES):
        with cols[i]:
            # Déterminer si c'est la page active
            is_active = current_page and page['path'] in current_page

            # Style du bouton selon état actif
            button_type = "primary" if is_active else "secondary"

            # Pour la page d'accueil, utiliser un chemin différent
            if page['path'] == "app.py":
                if st.button(
                    f"{page['icon']} {page['name']}",
                    key=f"nav_{i}",
                    use_container_width=True,
                    type=button_type,
                    disabled=is_active
                ):
                    st.switch_page("app.py")
            else:
                if st.button(
                    f"{page['icon']} {page['name']}",
                    key=f"nav_{i}",
                    use_container_width=True,
                    type=button_type,
                    disabled=is_active
                ):
                    st.switch_page(page['path'])

    # Ligne de séparation
    st.markdown("---")
