# Epic 005 - Leads Hub : Refonte de la gestion des leads

## Contexte

L'application actuelle a 4 modules fonctionnels mais cloisonnés. Cette refonte vise à :
1. Centraliser tous les leads dans une base unique multi-sources
2. Permettre l'enrichissement bidirectionnel (base ↔ HubSpot)
3. Rendre les flux plus cohérents

---

## Nouvelle structure des pages

### 1. 📜 Base de Leads (ex-Historique)
**Rôle** : Hub central de tous les leads

### 2. 🎯 Recherche et Enrichissement (ex-Recherche Leads)
**Rôle** : Extraction SIRENE + Enrichissement multi-source

### 3. 🔄 GetSales Sync
**Rôle** : Import LinkedIn → validation → Base de Leads

### 4. 📊 Dashboard CFO
**Rôle** : Inchangé (Analytics pipeline Asana)

---

## User Stories

### US-5.1 : Base de leads multi-sources
**En tant qu'** utilisateur
**Je veux** voir tous mes leads dans une vue unifiée
**Afin de** gérer mon pipeline depuis un seul endroit

**Critères d'acceptation :**
- [ ] Colonne "source" (sirene, hubspot, getsales)
- [ ] Filtres : source, campagne, statut, date
- [ ] Recherche par SIREN, nom, email
- [ ] Tri par colonnes
- [ ] Pagination ou scroll infini

### US-5.2 : Import depuis HubSpot
**En tant qu'** utilisateur
**Je veux** importer mes contacts/entreprises HubSpot dans la base locale
**Afin de** les enrichir et les centraliser

**Critères d'acceptation :**
- [ ] Bouton "Import HubSpot"
- [ ] Choix : contacts ou entreprises
- [ ] Filtres HubSpot (liste, propriété, date)
- [ ] Prévisualisation avant import
- [ ] Import avec source = "hubspot"
- [ ] Détection doublons (éviter re-import)

### US-5.3 : Enrichissement de leads existants
**En tant qu'** utilisateur
**Je veux** enrichir des leads déjà dans ma base
**Afin de** compléter les informations manquantes

**Critères d'acceptation :**
- [ ] Sélection multiple de leads dans la base
- [ ] Bouton "Enrichir avec Pappers"
- [ ] Mise à jour des champs enrichis
- [ ] Log des enrichissements

### US-5.4 : Push enrichissement vers HubSpot
**En tant qu'** utilisateur
**Je veux** renvoyer les leads enrichis vers HubSpot
**Afin de** mettre à jour mon CRM

**Critères d'acceptation :**
- [ ] Sélection de leads enrichis
- [ ] Bouton "Sync vers HubSpot"
- [ ] Update des contacts existants (par ID HubSpot)
- [ ] Création si nouveau
- [ ] Rapport de sync (créés/mis à jour/erreurs)

### US-5.5 : Réduire le minimum de leads à 1
**En tant qu'** utilisateur
**Je veux** pouvoir extraire 1 seul lead
**Afin de** tester rapidement

**Critères d'acceptation :**
- [ ] Champ "Nombre max de leads" : min=1
- [ ] Fonctionnel pour SIRENE et enrichissement

### US-5.6 : Leads GetSales → Base centrale
**En tant qu'** utilisateur
**Je veux** que les leads validés GetSales aillent dans la Base de Leads
**Afin d'** avoir une vue unifiée

**Critères d'acceptation :**
- [ ] Après validation "créer nouveau" → insert dans leads avec source="getsales"
- [ ] Après validation "merger" → update lead existant

---

## Modifications techniques

### Base de données

```sql
-- Table leads existante : ajouter colonnes
ALTER TABLE leads ADD COLUMN source VARCHAR(50) DEFAULT 'sirene';
ALTER TABLE leads ADD COLUMN hubspot_id VARCHAR(50);
ALTER TABLE leads ADD COLUMN enriched_at DATETIME;
ALTER TABLE leads ADD COLUMN last_sync_hubspot DATETIME;

-- Index pour performance
CREATE INDEX idx_leads_source ON leads(source);
CREATE INDEX idx_leads_hubspot_id ON leads(hubspot_id);
```

### Mapping des sources

| Source | Description |
|--------|-------------|
| sirene | Extraction API SIRENE |
| hubspot | Import depuis HubSpot |
| getsales | Validation GetSales Sync |
| manual | Saisie manuelle (futur) |

### Schéma des flux

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   SIRENE API    │────▶│                 │────▶│    HubSpot      │
└─────────────────┘     │                 │     └─────────────────┘
                        │   BASE LEADS    │            ▲
┌─────────────────┐     │   (SQLite)      │            │
│  HubSpot Import │────▶│                 │────────────┘
└─────────────────┘     │  source: xxx    │     (sync enrichis)
                        │  hubspot_id: x  │
┌─────────────────┐     │                 │
│ GetSales Valid. │────▶│                 │
└─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │  Enrichissement │
                        │    Pappers      │
                        └─────────────────┘
```

---

## Pages modifiées

### Page 1 : Base de Leads

```python
st.title("📜 Base de Leads")

tab1, tab2, tab3, tab_doc = st.tabs([
    "📋 Tous les leads",
    "⬇️ Import HubSpot",
    "🧹 Gestion",
    "📖 Documentation"
])

with tab1:
    # Filtres : source, campagne, date
    # Tableau avec colonnes : source, siren, nom, email, ville, enriched
    # Actions : sélection multiple → enrichir / exporter / supprimer

with tab2:
    # Import HubSpot
    # - Sélection : contacts ou companies
    # - Filtres HubSpot (optionnel)
    # - Prévisualisation
    # - Bouton Import

with tab3:
    # Gestion existante (nettoyage, suppression, stats)
```

### Page 2 : Recherche et Enrichissement

```python
st.title("🎯 Recherche et Enrichissement")

tab1, tab2, tab3, tab_doc = st.tabs([
    "🔍 Nouvelle recherche",
    "🔄 Enrichir existants",
    "⬆️ Sync HubSpot",
    "📖 Documentation"
])

with tab1:
    # Interface actuelle de recherche SIRENE
    # MODIF : min_leads = 1

with tab2:
    # Sélectionner leads de la base (non enrichis)
    # Enrichir avec Pappers
    # Voir résultat

with tab3:
    # Sélectionner leads enrichis
    # Push vers HubSpot
    # Rapport de sync
```

---

## Tâches de développement

### Phase 1 : Base de données (~2h)
- [ ] T5.1.1 - Migration : ajouter colonnes source, hubspot_id, enriched_at
- [ ] T5.1.2 - Mettre à jour le modèle LeadTracker
- [ ] T5.1.3 - Marquer leads existants avec source='sirene'

### Phase 2 : Page Base de Leads (~4h)
- [ ] T5.2.1 - Renommer page + restructurer en tabs
- [ ] T5.2.2 - Vue unifiée avec colonne source
- [ ] T5.2.3 - Filtres avancés (source, date, campagne)
- [ ] T5.2.4 - Sélection multiple + actions batch
- [ ] T5.2.5 - Tab Import HubSpot

### Phase 3 : Page Recherche et Enrichissement (~4h)
- [ ] T5.3.1 - Restructurer en tabs
- [ ] T5.3.2 - Changer min leads de 10 à 1
- [ ] T5.3.3 - Tab "Enrichir existants"
- [ ] T5.3.4 - Tab "Sync HubSpot" (push enrichis)

### Phase 4 : Intégration GetSales (~2h)
- [ ] T5.4.1 - Après validation → insert dans leads avec source='getsales'
- [ ] T5.4.2 - Mapper les champs GetSales → leads

### Phase 5 : Tests et polish (~2h)
- [ ] T5.5.1 - Tests avec 1 lead
- [ ] T5.5.2 - Tests flux complet : SIRENE → enrich → HubSpot
- [ ] T5.5.3 - Tests flux : HubSpot import → enrich → push back
- [ ] T5.5.4 - Mise à jour documentation

---

## Estimation

| Phase | Durée estimée |
|-------|---------------|
| Phase 1 - BDD | ~2h |
| Phase 2 - Base de Leads | ~4h |
| Phase 3 - Recherche/Enrichissement | ~4h |
| Phase 4 - Intégration GetSales | ~2h |
| Phase 5 - Tests | ~2h |
| **Total** | **~14h** |

---

## Questions ouvertes

1. **Import HubSpot** : importer tous les contacts ou seulement ceux sans SIREN ?
2. **Doublons cross-source** : un lead HubSpot peut-il être lié à un lead SIRENE existant ?
3. **Champs à synchroniser** : quels champs enrichis renvoyer vers HubSpot ?

---

## Prochaines étapes

1. Valider cette spec
2. Développer Phase 1 (BDD)
3. Itérer sur les pages
