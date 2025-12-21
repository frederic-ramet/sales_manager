# Epic 007 - Navigation Top Bar

## Contexte

Actuellement, l'application utilise la sidebar Streamlit pour :
1. La navigation entre pages
2. Les options de recherche (filtres) dans la page Recherche Leads

Cette architecture pose des problèmes d'UX :
- La sidebar prend de la place horizontale
- Les filtres de recherche sont séparés du contenu principal
- Sur mobile, la sidebar est peu pratique

## Objectifs

1. **Remplacer la navigation sidebar par une navigation en haut de page**
2. **Masquer la sidebar Streamlit par défaut**
3. **Déplacer les filtres de Recherche Leads dans la page principale**

---

## Spécifications Techniques

### T7.1 - Masquer la sidebar globalement (~1h)

**Fichier:** `app.py` ou `.streamlit/config.toml`

- Ajouter la configuration pour masquer la sidebar :
```python
st.set_page_config(
    page_title="Sales Ops Portal",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)
```
- Ajouter du CSS pour cacher complètement la sidebar :
```python
st.markdown("""
<style>
    [data-testid="stSidebar"] {
        display: none;
    }
    [data-testid="stSidebarNav"] {
        display: none;
    }
</style>
""", unsafe_allow_html=True)
```

### T7.2 - Créer composant navigation top bar (~2h)

**Fichier:** `components/top_nav.py`

Créer un composant réutilisable pour la navigation horizontale :

```python
def render_top_nav():
    """Affiche la barre de navigation horizontale."""
    pages = [
        {"icon": "📊", "name": "Pipeline CFO", "path": "pages/1_📊_Pipeline_CFO.py"},
        {"icon": "🎯", "name": "Recherche Leads", "path": "pages/2_🎯_Recherche_Leads.py"},
        {"icon": "📜", "name": "Base de Leads", "path": "pages/3_📜_Base_de_Leads.py"},
        {"icon": "🔄", "name": "GetSales Sync", "path": "pages/4_🔄_GetSales_Sync.py"},
    ]

    cols = st.columns(len(pages))
    for i, page in enumerate(pages):
        with cols[i]:
            if st.button(f"{page['icon']} {page['name']}", use_container_width=True):
                st.switch_page(page['path'])
```

**Design:**
- Boutons horizontaux avec icônes
- Indication visuelle de la page active
- Responsive (s'adapte à la largeur)

### T7.3 - Intégrer la navigation dans toutes les pages (~1h)

**Fichiers:** Toutes les pages dans `pages/`

Pour chaque page :
1. Importer le composant `render_top_nav`
2. Appeler `render_top_nav()` en haut de page, après le titre
3. Supprimer tout code utilisant `st.sidebar` pour la navigation

### T7.4 - Migrer les filtres de Recherche Leads (~2h)

**Fichier:** `pages/2_🎯_Recherche_Leads.py`

Déplacer tous les filtres de la sidebar vers la page principale :

**Structure proposée :**
```
┌─────────────────────────────────────────────────┐
│  🎯 Recherche de Leads                          │
├─────────────────────────────────────────────────┤
│  [Navigation: Pipeline | Recherche | Base | ...] │
├─────────────────────────────────────────────────┤
│  🔍 Recherche en langage naturel               │
│  [___________________________________________]   │
├─────────────────────────────────────────────────┤
│  ⚙️ Filtres avancés (expander)                  │
│  ┌─────────────────────────────────────────────┐│
│  │ Secteurs APE  │ Départements │ Effectifs   ││
│  │ [multiselect] │ [multiselect]│ [min] [max] ││
│  │ Date création │ Max leads    │             ││
│  │ [date_input]  │ [number]     │             ││
│  └─────────────────────────────────────────────┘│
├─────────────────────────────────────────────────┤
│  ⚙️ Options export (expander)                   │
│  ┌─────────────────────────────────────────────┐│
│  │ ☑ Pappers │ ☑ Dédup │ ☑ Sheets │ ☑ HubSpot ││
│  └─────────────────────────────────────────────┘│
├─────────────────────────────────────────────────┤
│  [🚀 Lancer l'extraction]                       │
├─────────────────────────────────────────────────┤
│  📊 Résultats                                   │
└─────────────────────────────────────────────────┘
```

**Actions :**
1. Supprimer tout le bloc `with st.sidebar:` (lignes ~451-751)
2. Créer des expanders dans la page principale pour les filtres
3. Réorganiser le layout avec colonnes pour optimiser l'espace
4. Conserver la logique de pré-remplissage depuis `parsed_filters`

### T7.5 - Nettoyer les autres pages (~1h)

Vérifier et nettoyer les autres pages :
- `pages/1_📊_Pipeline_CFO.py` - Supprimer usage sidebar si présent
- `pages/3_📜_Base_de_Leads.py` - Supprimer usage sidebar si présent
- `pages/4_🔄_GetSales_Sync.py` - Supprimer usage sidebar si présent

---

## Critères d'acceptation

1. [ ] La sidebar Streamlit n'est plus visible
2. [ ] Navigation horizontale en haut de chaque page
3. [ ] Indication visuelle de la page courante
4. [ ] Filtres de Recherche Leads accessibles dans la page principale
5. [ ] Expanders pour garder l'interface épurée
6. [ ] Bouton d'extraction visible sans scroller
7. [ ] Pas de régression fonctionnelle

---

## Estimation

| Tâche | Temps |
|-------|-------|
| T7.1 - Masquer sidebar | 1h |
| T7.2 - Composant top nav | 2h |
| T7.3 - Intégrer navigation | 1h |
| T7.4 - Migrer filtres Recherche | 2h |
| T7.5 - Nettoyer autres pages | 1h |
| **Total** | **~7h** |
