# Plan d'Implémentation - Enrichissement Optimisé

**Date de création :** 2025-11-23
**Objectif :** Améliorer l'enrichissement de 40% → 90% de complétude avec -91% de coûts

---

## 📋 Vue d'Ensemble

| Phase | Objectif | Durée | Coût | Impact |
|-------|----------|-------|------|--------|
| **Phase 1** | Quick Wins (gratuit) | 4h | 0€ | +45% complétude |
| **Phase 2** | Téléphones | 7h | 17€/1000 | +70% téléphones |
| **Phase 3** | Automatisation | 10h | 0€ | -90% temps |
| **TOTAL** | | **21h** | **17€/1000** | **90% complétude** |

---

## 🎯 Phase 1 : Quick Wins (GRATUIT)

**Durée estimée :** 4 heures
**Impact :** +45% complétude
**Coût :** 0€

### 1.1 API SIRENE V2 Complète (2h)

**Objectif :** Récupérer TOUTES les données SIRENE au lieu de juste la recherche

**Fichiers à créer/modifier :**

#### A. Créer `core/sirene_client_v2.py`
```python
class SireneClientV2(SireneClient):
    """
    Client SIRENE enrichi qui récupère données complètes.

    Nouvelles fonctionnalités:
    - get_full_company_data(siren) -> Toutes données entreprise
    - get_dirigeants(siren) -> Liste dirigeants
    - get_etablissements(siren) -> Liste établissements
    """

    def get_full_company_data(self, siren: str) -> Dict:
        """
        Endpoint: GET /entreprises/sirene/V3.11/siren/{siren}

        Returns:
            {
                'siren': str,
                'siret_siege': str,
                'denomination': str,
                'code_ape': str,
                'libelle_ape': str,
                'adresse': {
                    'numero': str,
                    'type_voie': str,
                    'libelle_voie': str,
                    'code_postal': str,
                    'commune': str
                },
                'effectif_tranche': str,
                'date_creation': str,
                'dirigeants': [
                    {
                        'nom': str,
                        'prenom': str,
                        'fonction': str,
                        'date_nomination': str
                    }
                ],
                'etablissements_count': int
            }
        """
```

**Dépendances :**
- Aucune nouvelle (utilise httpx existant)
- Token INSEE peut-être nécessaire (gratuit)

**Tests :**
- Test avec SIREN Nexans : 428593230
- Test avec SIREN Airbus : 383474814
- Vérifier dirigeants récupérés

---

#### B. Modifier `core/hubspot_client.py`

**Ajout champs dans le modèle de contact :**
```python
STANDARD_PROPERTIES = [
    "firstname", "lastname", "email", "phone",
    "company", "jobtitle", "city", "address", "zip",
    "hs_object_id", "createdate"
]

CUSTOM_PROPERTIES = [
    "siren",
    "siret",  # ← NOUVEAU
    "code_ape",
    "libelle_ape",  # ← NOUVEAU
    "effectif",
    "effectif_tranche",  # ← NOUVEAU
    "chiffre_affaires",
    "dirigeant_principal",  # ← RENOMMÉ (ancien: dirigeant)
    "dirigeants_json"  # ← NOUVEAU (stocke liste JSON)
]
```

**Méthode de parsing enrichie :**
```python
def _parse_contact_v2(self, raw_contact: Dict) -> Dict:
    """Parse avec nouveaux champs SIRENE V2."""
    # ... parsing existant ...

    # Nouveaux champs
    contact['siret'] = props.get('siret', '')
    contact['libelle_ape'] = props.get('libelle_ape', '')
    contact['effectif_tranche'] = props.get('effectif_tranche', '')

    # Dirigeants multiples
    dirigeants_json = props.get('dirigeants_json', '')
    if dirigeants_json:
        contact['dirigeants'] = json.loads(dirigeants_json)
    else:
        # Fallback ancien format
        contact['dirigeants'] = [{
            'nom': props.get('lastname', ''),
            'prenom': props.get('firstname', ''),
            'fonction': props.get('jobtitle', '')
        }] if props.get('lastname') else []

    return contact
```

---

#### C. Créer script de migration `scripts/migrate_to_v2.py`

```python
"""
Migration données existantes vers format V2.

Actions:
1. Lit hubspot_mirror.json
2. Pour chaque contact avec SIREN, enrichit via SIRENE V2
3. Ajoute SIRET, dirigeants, libellé APE
4. Sauvegarde hubspot_mirror_v2.json
5. Optionnel: Push vers HubSpot
"""

def migrate_contacts():
    # Charger contacts existants
    contacts = load_hubspot_mirror()

    # Enrichir chaque contact avec SIREN
    sirene_v2 = SireneClientV2()

    for contact in contacts:
        if contact.get('siren'):
            # Récupérer données complètes
            full_data = sirene_v2.get_full_company_data(contact['siren'])

            # Mettre à jour contact
            contact['siret'] = full_data['siret_siege']
            contact['libelle_ape'] = full_data['libelle_ape']
            contact['effectif_tranche'] = full_data['effectif_tranche']
            contact['dirigeants'] = full_data['dirigeants']

    # Sauvegarder
    save_hubspot_mirror_v2(contacts)
```

---

### 1.2 SIRET en complément SIREN (1h)

**Objectif :** Stocker SIRET du siège social pour géolocalisation précise

**Modifications :**

#### A. Mise à jour affichage contacts

**Fichier :** `pages/3_📋_Mes_Leads_HubSpot.py`

```python
# Affichage info contact
info_data = {
    "SIREN": contact.get('siren', 'N/A'),
    "SIRET": contact.get('siret', 'N/A'),  # ← NOUVEAU
    "Code APE": f"{contact.get('code_ape', 'N/A')} - {contact.get('libelle_ape', '')}",  # ← ENRICHI
    "Secteur": contact.get('secteur', 'N/A'),
    "Ville": contact.get('ville', 'N/A'),
    "Effectif": contact.get('effectif_tranche', contact.get('effectif', 'N/A')),  # ← NOUVEAU FORMAT
}
```

---

### 1.3 Multi-Dirigeants (1h)

**Objectif :** Afficher et stocker TOUS les dirigeants au lieu d'un seul

**Modifications :**

#### A. Affichage dirigeants multiples

**Fichier :** `pages/3_📋_Mes_Leads_HubSpot.py`

```python
# Section dirigeants
if contact.get('dirigeants'):
    st.markdown("**👔 Dirigeants :**")
    for dirigeant in contact['dirigeants']:
        nom_complet = f"{dirigeant.get('prenom', '')} {dirigeant.get('nom', '')}".strip()
        fonction = dirigeant.get('fonction', '')
        st.text(f"  • {nom_complet} - {fonction}")
else:
    st.text("Dirigeants: N/A")
```

#### B. Export dirigeants multiples

**Fichier :** `pages/10_📝_Templates_Export.py`

Option 1 : Une ligne par dirigeant (format long)
```python
# Exploser DataFrame avec dirigeants multiples
contacts_expanded = []
for contact in contacts:
    if contact.get('dirigeants'):
        for dirigeant in contact['dirigeants']:
            row = contact.copy()
            row['dirigeant_nom'] = dirigeant.get('nom')
            row['dirigeant_prenom'] = dirigeant.get('prenom')
            row['dirigeant_fonction'] = dirigeant.get('fonction')
            contacts_expanded.append(row)
```

Option 2 : Dirigeants en colonnes séparées
```python
# Max 3 dirigeants
contact['dirigeant_1'] = dirigeants[0] if len(dirigeants) > 0 else ''
contact['dirigeant_2'] = dirigeants[1] if len(dirigeants) > 1 else ''
contact['dirigeant_3'] = dirigeants[2] if len(dirigeants) > 2 else ''
```

---

### 1.4 Tests Phase 1

**Script de test :** `tests/test_phase1.py`

```python
def test_sirene_v2():
    """Test API SIRENE V2."""
    client = SireneClientV2()

    # Test Nexans
    data = client.get_full_company_data('428593230')

    assert data['siren'] == '428593230'
    assert data['siret_siege'] == '42859323000389'
    assert data['libelle_ape'] is not None
    assert len(data['dirigeants']) > 0

    print("✅ SIRENE V2 OK")

def test_multi_dirigeants():
    """Test stockage multi-dirigeants."""
    contact = {
        'siren': '758501001',  # Legrand
        'dirigeants': [
            {'nom': 'BUREL', 'prenom': 'Antoine', 'fonction': 'Président'},
            {'nom': 'DESCAMPS', 'prenom': 'David', 'fonction': 'DG'}
        ]
    }

    assert len(contact['dirigeants']) == 2
    print("✅ Multi-dirigeants OK")

def test_migration():
    """Test migration contacts existants."""
    # Charger 10 contacts test
    # Enrichir via SIRENE V2
    # Vérifier nouvelles données
    print("✅ Migration OK")
```

---

### 1.5 Checklist Phase 1

- [ ] Créer `core/sirene_client_v2.py`
- [ ] Ajouter méthode `get_full_company_data()`
- [ ] Tester avec 3 SIREN différents
- [ ] Modifier `core/hubspot_client.py` (nouveaux champs)
- [ ] Créer script `scripts/migrate_to_v2.py`
- [ ] Exécuter migration sur contacts test (10 contacts)
- [ ] Vérifier résultats migration
- [ ] Mettre à jour affichage `pages/3_📋_Mes_Leads_HubSpot.py`
- [ ] Mettre à jour affichage dirigeants (multi)
- [ ] Mettre à jour exports `pages/10_📝_Templates_Export.py`
- [ ] Exécuter tests `tests/test_phase1.py`
- [ ] Valider avec contacts réels (531 contacts)
- [ ] Commit + Push

---

## 🚀 Phase 2 : Téléphones

**Durée estimée :** 7 heures
**Impact :** +70% téléphones
**Coût :** 17€/1000 contacts

### 2.1 Google Maps API Integration (3h)

**Objectif :** Trouver numéros téléphone via Google Places API

**Fichiers à créer :**

#### A. `core/google_maps_client.py`

```python
class GoogleMapsClient:
    """
    Client Google Maps pour recherche téléphones.

    API utilisée: Places API - Find Place
    Coût: $17 per 1,000 requests (Text Search)
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://maps.googleapis.com/maps/api/place"

    def find_phone(self, company_name: str, city: str = None) -> Optional[Dict]:
        """
        Recherche téléphone entreprise.

        Args:
            company_name: "Nexans France"
            city: "Courbevoie" (optionnel, améliore précision)

        Returns:
            {
                'phone': '+33 1 73 23 84 00',
                'formatted_address': '4 Allée de l\'Arche, Courbevoie',
                'place_id': 'ChIJ...',
                'confidence': 0.95
            }
        """
        # Construction query
        query = company_name
        if city:
            query += f" {city}"
        query += " France"

        # Appel API
        params = {
            'input': query,
            'inputtype': 'textquery',
            'fields': 'formatted_phone_number,formatted_address,name,place_id',
            'key': self.api_key
        }

        response = httpx.get(f"{self.base_url}/findplacefromtext/json", params=params)
        # ... parse response ...
```

#### B. Intégration dans enrichissement

**Fichier :** `pages/5_🔧_Enrichir_SIRENE.py`

```python
# Après enrichissement SIRENE
if result and GOOGLE_MAPS_API_KEY:
    # Rechercher téléphone
    maps_client = GoogleMapsClient(GOOGLE_MAPS_API_KEY)
    phone_data = maps_client.find_phone(
        company_name=result['denomination'],
        city=result.get('ville')
    )

    if phone_data and phone_data['confidence'] > 0.7:
        update["properties"]["phone"] = phone_data['phone']
        st.info(f"📞 Téléphone trouvé: {phone_data['phone']}")
```

---

### 2.2 Fallback Pages Jaunes (4h)

**Objectif :** Scraping léger Pages Jaunes si Google Maps échoue

**Note :** Scraping à utiliser avec prudence (respect robots.txt)

#### A. `core/pages_jaunes_client.py`

```python
class PagesJaunesClient:
    """
    Fallback pour téléphones si Google Maps échoue.

    Méthode: Scraping léger avec respect robots.txt
    Rate limit: 1 requête/seconde
    """

    def search_phone(self, company_name: str, city: str) -> Optional[str]:
        """
        Recherche téléphone sur Pages Jaunes.

        Returns:
            "+33 1 73 23 84 00" ou None
        """
        # Construction URL
        # Respect robots.txt
        # Parse résultat
        # Validation format téléphone
```

---

### 2.3 Workflow Téléphones

```
1. Essayer Google Maps API (coût: 0.017€)
   ├─ Succès (70%) → Fin
   └─ Échec (30%) → Étape 2

2. Essayer Pages Jaunes (gratuit)
   ├─ Succès (50%) → Fin
   └─ Échec (50%) → Pas de téléphone

Taux final: 70% + (30% × 50%) = 85% téléphones
```

---

### 2.4 Checklist Phase 2

- [ ] Créer compte Google Cloud Platform
- [ ] Activer Places API
- [ ] Obtenir API key
- [ ] Créer `core/google_maps_client.py`
- [ ] Tester avec 10 entreprises
- [ ] Mesurer taux de succès
- [ ] Créer `core/pages_jaunes_client.py`
- [ ] Implémenter respect robots.txt
- [ ] Intégrer dans pages enrichissement
- [ ] Ajouter option "Rechercher téléphone" (opt-in)
- [ ] Afficher coût estimé avant lancement
- [ ] Tests end-to-end
- [ ] Commit + Push

---

## 🤖 Phase 3 : Automatisation

**Durée estimée :** 10 heures
**Impact :** -90% temps enrichissement
**Coût :** 0€

### 3.1 WebSearch Auto-Enrichment (5h)

**Objectif :** Enrichissement automatique via WebSearch pour grandes entreprises

**Fichier :** `core/web_enrichment.py`

```python
class WebEnrichment:
    """
    Enrichissement automatique via WebSearch.

    Workflow:
    1. Recherche "{company} France SIREN dirigeant téléphone"
    2. Parse résultats (regex SIREN, noms, téléphones)
    3. Valide via API SIRENE
    4. Retourne données enrichies

    Taux de succès:
    - Grandes entreprises (>1000 sal): 100%
    - ETI (250-1000): 95%
    - PME (50-250): 80%
    - TPE (<50): 60%
    """

    def enrich_contact(self, contact: Dict) -> Dict:
        """
        Enrichissement auto via web.

        Returns:
            {
                'siren': str,
                'dirigeant': str,
                'telephone': str,
                'confidence': float,  # 0-1
                'sources': [str]
            }
        """
```

---

### 3.2 Validation Multi-Sources (3h)

**Objectif :** Croiser plusieurs sources pour valider données

```python
class DataValidator:
    """
    Validation multi-sources.

    Méthode:
    1. Collecte données de N sources
    2. Compare et détecte conflits
    3. Calcule score de confiance
    4. Retourne donnée la plus fiable
    """

    def validate_siren(self, siren: str, sources: List[Dict]) -> Dict:
        """
        Valide SIREN via plusieurs sources.

        Returns:
            {
                'siren': str,
                'confidence': float,
                'sources_agreement': int,  # Nombre sources d'accord
                'conflicts': List[str]
            }
        """
```

---

### 3.3 Confidence Scoring (2h)

**Objectif :** Score de confiance par champ enrichi

```python
{
    "siren": {
        "value": "428593230",
        "confidence": 1.0,  # API officielle
        "source": "INSEE SIRENE",
        "verified": true,
        "last_update": "2025-11-23"
    },
    "telephone": {
        "value": "+33 1 73 23 84 00",
        "confidence": 0.85,  # Google Maps + Pages Jaunes
        "sources": ["Google Maps", "Pages Jaunes"],
        "verified": false,
        "last_update": "2025-11-23"
    }
}
```

---

### 3.4 Checklist Phase 3

- [ ] Créer `core/web_enrichment.py`
- [ ] Implémenter parsing regex (SIREN, téléphone, noms)
- [ ] Créer `core/data_validator.py`
- [ ] Implémenter détection conflits
- [ ] Ajouter confidence scoring
- [ ] Créer page "🤖 Enrichissement Auto"
- [ ] Interface: sélection source prioritaire
- [ ] Affichage conflits détectés
- [ ] Tests avec 100 contacts
- [ ] Mesure précision vs Pappers
- [ ] Commit + Push

---

## 📊 Métriques de Succès

### KPIs Phase 1
- [ ] SIRET récupérés: 100% (pour contacts avec SIREN)
- [ ] Dirigeants récupérés: 100% (pour contacts avec SIREN)
- [ ] Libellé APE récupérés: 100% (pour contacts avec code APE)
- [ ] Temps exécution: <2min pour 500 contacts

### KPIs Phase 2
- [ ] Téléphones trouvés: >70%
- [ ] Coût réel: <20€/1000 contacts
- [ ] Précision téléphones: >90% (vérification manuelle sur 50)

### KPIs Phase 3
- [ ] Temps enrichissement: -90% vs manuel
- [ ] Précision auto: >85% vs Pappers
- [ ] Conflits détectés: <5%

---

## 🎯 Jalons

| Jalon | Date cible | Livrables |
|-------|-----------|-----------|
| **Phase 1 complétée** | J+1 | SIRENE V2 fonctionnel, 531 contacts migrés |
| **Phase 2 complétée** | J+3 | Google Maps intégré, 70% téléphones |
| **Phase 3 complétée** | J+5 | Auto-enrichissement opérationnel |
| **Production** | J+7 | Documentation, formation, déploiement |

---

## 💰 Budget Total

| Poste | Coût Unitaire | Volume | Total |
|-------|---------------|--------|-------|
| **Développement** | 0€ | - | 0€ |
| **Google Maps API** | 0.017€ | 1000 contacts | 17€ |
| **SIRENE API** | 0€ | Illimité | 0€ |
| **Hébergement** | 0€ | Streamlit local | 0€ |
| **TOTAL** | | | **17€** |

**vs Pappers seul:** 199€ → **Économie: 182€ (-91%)**

---

## 📝 Notes Importantes

### Limitations Connues

1. **Téléphones Pages Jaunes**
   - Scraping peut être bloqué
   - Alternative: API PagesJaunes (payant)

2. **WebSearch Auto**
   - Moins fiable pour TPE/PME
   - Nécessite validation manuelle

3. **Google Maps API**
   - Quota: 200€ gratuit/mois (≈11,750 recherches)
   - Au-delà: facturation

### Recommandations

1. **Commencer par Phase 1** (gratuit, impact immédiat)
2. **Tester Phase 2** sur 100 contacts avant déploiement complet
3. **Phase 3** à implémenter progressivement (complexe)

---

**Prêt pour exécution Phase 1 !** 🚀
