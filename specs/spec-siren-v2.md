# Spec: SIREN v2 - Recherche Entreprises & Segmentation

## Contexte

La page "Ajout Leads SIRENE" actuelle mélange la logique entreprise/contact.
SIREN fournit des **informations entreprise** (pas contacts) - les contacts viendront de Pappers ou LinkedIn.

Cette mise à jour clarifie les 2 cas d'usage principaux et ajoute un système de scoring/segmentation métier.

---

## 1. Cas d'usage

### Cas 1: Recherche et ajout d'entreprises SIREN

**Workflow:**
1. L'utilisateur configure ses filtres (APE, département, effectif, etc.)
2. Clic "Rechercher" → Affiche résultats en 2 groupes:
   - **Nouvelles entreprises** (pas encore en BDD)
   - **Entreprises existantes** (déjà en BDD, matching par SIREN)
3. L'utilisateur sélectionne les entreprises à importer
4. Il assigne un **segment** (ICP Principal, ICP Opportuniste, etc.)
5. Clic "Importer" → Crée les entreprises dans `companies`

**Points clés:**
- SIREN = données entreprise uniquement
- Pas de création de contacts à cette étape
- Scoring automatique basé sur critères ICP

### Cas 2: Enrichissement d'une entreprise existante

**Workflow:**
1. Depuis "Base de Leads", l'utilisateur sélectionne une entreprise
2. Clic "Enrichir avec Pappers"
3. Pappers retourne: dirigeants, CA, effectif précis, téléphone
4. Mise à jour de l'entreprise + création contacts (dirigeants)

---

## 2. Architecture technique

### 2.1 Nouveau champ `segment` sur `companies`

```sql
ALTER TABLE companies ADD COLUMN segment TEXT;
-- Valeurs: 'icp_principal', 'icp_opportuniste', 'test', 'custom'
```

### 2.2 Système de scoring double

**Fichier:** `modules/lead_scraper/scoring.py`

#### A. ProspectClassifier (A/B/C) - Classification ICP

```python
class ProspectClassifier:
    """
    Classifie les prospects selon critères ICP métier.

    Utilisé AVANT contact pour prioriser les entreprises à prospecter.
    A = ultra-qualifié, B = volume, C = opportuniste
    """

    # Codes APE prioritaires par groupe
    APE_GROUPS = {
        "Industrie Manufacturing": [
            "27.32Z",  # Câbles/composants électroniques
            "28.*",    # Machines/équipements (wildcard)
            "25.*",    # Produits métalliques (wildcard)
        ],
        "Services Professionnels": [
            "70.22Z",  # Conseil gestion
            "69.20Z",  # Conseil comptable/audit
            "71.12B",  # Ingénierie/études techniques
        ],
        "Santé Privée": [
            "86.10Z",  # Activités hospitalières
            "86.90*",  # Laboratoires/cliniques
        ],
    }

    # Départements IDF
    IDF_CODES = ["75", "92", "93", "94", "95", "77", "78", "91"]

    def classify(self, company: dict) -> dict:
        """
        Retourne: {
            'prospect_class': 'A' | 'B' | 'C',
            'points': int (0-100),
            'signals': list[str],
            'expected_contact_rate': float
        }
        """
        points = 0
        signals = []

        # 1. Effectif dans range ICP (20 pts)
        effectif = self._parse_effectif(company.get('employee_range'))
        if effectif and 50 <= effectif <= 1000:
            points += 20
            signals.append(f"Effectif {effectif} (ICP)")

        # 2. CA > 10M€ (20 pts)
        if self._ca_above(company.get('revenue_range'), 10_000_000):
            points += 20
            signals.append("CA > 10M€")

        # 3. Secteur prioritaire (15 pts)
        if self._is_priority_ape(company.get('ape_code')):
            points += 15
            signals.append("Secteur prioritaire")

        # 4. IDF (15 pts)
        if company.get('postal_code', '')[:2] in self.IDF_CODES:
            points += 15
            signals.append("IDF")

        # 5. Croissance effectif > 20% (30 pts) - TODO avec Pappers

        # Classification
        if points >= 70:
            return {'prospect_class': 'A', 'points': points, 'signals': signals, 'expected_contact_rate': 0.40}
        elif points >= 40:
            return {'prospect_class': 'B', 'points': points, 'signals': signals, 'expected_contact_rate': 0.05}
        else:
            return {'prospect_class': 'C', 'points': points, 'signals': signals, 'expected_contact_rate': 0.02}
```

#### B. LeadScorer (Hot/Warm/Cold) - Déjà existant

```python
class LeadScorer:
    """
    Score les leads selon complétude et engagement.

    Utilisé APRÈS contact pour qualifier les leads.
    Hot = prêt à closer, Warm = à nurture, Cold = à réactiver

    Critères: email direct, téléphone, dirigeant, interactions, etc.
    """
    # ... (existant dans scoring.py)
```

#### Workflow complet:

```
SIRENE → ProspectClassifier (A/B/C) → Import entreprises
                                           ↓
                                    Enrichissement Pappers
                                           ↓
                                    Prospection (GetSales/LinkedIn)
                                           ↓
                              LeadScorer (Hot/Warm/Cold) → HubSpot
```

### 2.3 Presets de campagne

**Nouveau fichier:** `config/campaigns.py`

```python
CAMPAIGN_PRESETS = {
    "audit_ia_bpi": {
        "name": "Audit IA BPI (13K€ subventionné)",
        "target_volume": 500,
        "min_score": "B",
        "segment": "icp_principal",
        "filters": {
            "ape_groups": ["Industrie Manufacturing", "Services Professionnels"],
            "effectif_min": 50,
            "effectif_max": 1000,
            "geo": "national",
        },
    },
    "digital_factory": {
        "name": "Digital Factory (plateforme)",
        "target_volume": 50,
        "min_score": "A+",
        "segment": "icp_principal",
        "filters": {
            "ape_groups": ["Industrie Manufacturing"],
            "effectif_min": 100,
            "effectif_max": 1000,
            "geo": "idf",
        },
    },
    "test_opportuniste": {
        "name": "Test PME Croissance",
        "target_volume": 100,
        "min_score": "B",
        "segment": "icp_opportuniste",
        "filters": {
            "ape_codes": ["10.92Z", "46.21Z"],
            "effectif_min": 50,
            "effectif_max": 300,
        },
    },
}
```

---

## 3. Modifications UI

### 3.1 Page "Ajout Leads SIRENE" (`pages/2_🎯_Recherche_Leads.py`)

**Nouvelle structure:**

```
┌─────────────────────────────────────────────────────────────┐
│ 🎯 Recherche Entreprises SIRENE                             │
├─────────────────────────────────────────────────────────────┤
│ [Onglet: Presets] [Onglet: Recherche avancée]              │
│                                                             │
│ === PRESETS CAMPAGNE ===                                    │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ 🎯 Audit IA BPI (500 leads B+)                          ││
│ │ 🏭 Digital Factory (50 leads A+)                        ││
│ │ 🧪 Test PME Croissance (100 leads)                      ││
│ │ ⚙️ Custom                                                ││
│ └─────────────────────────────────────────────────────────┘│
│                                                             │
│ === FILTRES (pré-remplis si preset) ===                    │
│ [Secteurs: multiselect groupé]  [Géo: IDF/National/Custom] │
│ [Effectif min: 50] [Effectif max: 1000] [Max results: 100] │
│                                                             │
│ [📊 Estimer] [🔍 Rechercher]                                │
├─────────────────────────────────────────────────────────────┤
│ === ESTIMATION (avant recherche) ===                        │
│ ~200 entreprises attendues                                  │
│ ~40 A+ (contact attendu: 16) | ~120 B (contact: 6) | 40 C  │
│ Temps: ~2 min | Coût Pappers: ~0€ (SIREN gratuit)          │
├─────────────────────────────────────────────────────────────┤
│ === RÉSULTATS ===                                           │
│ [Tab: Nouvelles (187)] [Tab: Déjà en base (13)]            │
│                                                             │
│ Nouvelles entreprises:                                      │
│ ┌────┬────────────────┬────────┬──────┬───────┬──────────┐│
│ │ ☐  │ Nom            │ SIREN  │ APE  │ Ville │ Score    ││
│ ├────┼────────────────┼────────┼──────┼───────┼──────────┤│
│ │ ☑  │ ACME Corp      │ 123... │ 28.1 │ Paris │ 🟢 A+    ││
│ │ ☑  │ Tech Solutions │ 456... │ 71.1 │ Lyon  │ 🟡 B     ││
│ └────┴────────────────┴────────┴──────┴───────┴──────────┘│
│                                                             │
│ [Segment: ICP Principal ▼]  [✅ Importer 45 sélectionnés]  │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Affichage score avec badge

```python
def render_score_badge(score: str) -> str:
    """Badge coloré pour le score ICP"""
    badges = {
        'A+': '🟢 A+',
        'B': '🟡 B',
        'C': '⚪ C',
    }
    return badges.get(score, score)
```

### 3.3 Page "Base de Leads" - Enrichissement

**Ajout d'un bouton "Enrichir" sur chaque entreprise:**

```
┌───────────────────────────────────────────────────────────┐
│ ACME Corp (SIREN: 123456789)                              │
│ Paris | 28.14Z - Fab. machines | 50-100 emp               │
│ Score: 🟢 A+ | Segment: ICP Principal                     │
│ Contacts: 0                                               │
│                                                           │
│ [💎 Enrichir Pappers] [📧 Voir contacts] [✏️ Modifier]    │
└───────────────────────────────────────────────────────────┘
```

---

## 4. Modifications base de données

### 4.1 Migration `companies`

```sql
-- Segment principal (compatible HubSpot)
ALTER TABLE companies ADD COLUMN segment TEXT;
-- Valeurs: 'ICP Principal', 'ICP Opportuniste', 'Test', 'Custom'

-- Classification prospect (A/B/C) - avant contact
ALTER TABLE companies ADD COLUMN prospect_class TEXT;  -- 'A', 'B', 'C'
ALTER TABLE companies ADD COLUMN prospect_class_points INTEGER;
ALTER TABLE companies ADD COLUMN prospect_class_signals TEXT;  -- JSON array

-- Tags est déjà présent dans le schéma existant

-- Index pour filtrage
CREATE INDEX idx_companies_segment ON companies(segment);
CREATE INDEX idx_companies_prospect_class ON companies(prospect_class);
```

### 4.2 Le champ `tags` existant

Le champ `tags` (TEXT, stocké en JSON) permet d'ajouter des tags personnalisés:
- "campagne_q1_2025"
- "audit_bpi"
- "priorité_haute"
- etc.

---

## 5. Fichiers à modifier

| Fichier | Modifications |
|---------|---------------|
| `modules/lead_scraper/scoring.py` | Ajouter `ICPScorer` class |
| `modules/lead_scraper/company_manager.py` | Ajouter `segment`, méthodes enrichissement |
| `pages/2_🎯_Recherche_Leads.py` | Refonte UI, presets, 2 onglets résultats |
| `pages/3_📜_Base_de_Leads.py` | Bouton enrichir, affichage score/segment |
| `config/campaigns.py` | Nouveau fichier presets |
| `data/ape_groups.json` | Nouveau fichier groupes APE |

---

## 6. Décisions validées

1. **Segment + Tags**: Les deux
   - `segment` = champ principal (compatible HubSpot): "ICP Principal", "ICP Opportuniste", etc.
   - `tags` = tags additionnels pour retrouver/filtrer

2. **Scoring: 2 systèmes distincts**
   - `prospect_class` (A/B/C) = classification ICP basée sur critères métier (effectif, CA, secteur, géo)
   - `lead_score` (Hot/Warm/Cold) = scoring engagement/complétude (email, tel, dirigeant)
   - **Workflow**: On trouve des prospects A/B/C → on les qualifie en leads Hot/Warm/Cold

3. **Vue résultats**: 2 onglets
   - Onglet "Nouvelles entreprises"
   - Onglet "Déjà en base"

4. **Enrichissement**: Depuis page Base de Leads
   - Sélection entreprise → bouton "Enrichir Pappers"

---

## 7. Plan d'implémentation

### Phase 1: Scoring ICP (1 jour)
- [ ] Créer `ICPScorer` dans `scoring.py`
- [ ] Migration DB (segment, icp_score)
- [ ] Tests unitaires scoring

### Phase 2: Presets campagne (0.5 jour)
- [ ] Créer `config/campaigns.py`
- [ ] Créer `data/ape_groups.json`

### Phase 3: UI Recherche (1.5 jours)
- [ ] Refonte page SIREN avec presets
- [ ] Onglets résultats Nouvelles/Existantes
- [ ] Sélection + import avec segment
- [ ] Estimation avant recherche

### Phase 4: Enrichissement (1 jour)
- [ ] Bouton enrichir sur Base de Leads
- [ ] Création contacts depuis Pappers (dirigeants)
- [ ] Mise à jour score après enrichissement

---

## 8. Métriques de succès

| Métrique | Objectif |
|----------|----------|
| Temps import 100 entreprises | < 30s |
| Taux A+ sur ICP Principal | > 30% |
| Coût API Pappers par enrichissement | < 0.10€ |
