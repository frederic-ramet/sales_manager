# Spec: Page Import Unifiée (GetSales + CSV)

## Contexte

L'import CSV actuel est basique : il importe directement sans vérifier les doublons entreprise ni proposer de liaison avec les données existantes.

L'objectif est de créer une **page dédiée Import** avec 2 onglets :
- **Import GetSales** : import depuis l'API GetSales (existant à migrer)
- **Import CSV** : import fichiers CSV avec workflow amélioré

Les 2 onglets partagent le même workflow :
1. Détection des entreprises existantes
2. Choix : lier à l'existant ou créer nouveau
3. Sync HubSpot avec les propriétés (déjà configurées via GetSales)

---

## 1. Workflow cible (inspiré GetSales)

```
┌─────────────────────────────────────────────────────────────┐
│ 📤 Import CSV                                                │
├─────────────────────────────────────────────────────────────┤
│ ÉTAPE 1: Upload & Mapping                                    │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ [Glisser fichier CSV ici]                               │ │
│ │ ✅ fichier_alix.csv - 3 lignes, 9 colonnes              │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
│ Mapping automatique: 8/9 colonnes mappées                    │
│ 📋 Colonnes ignorées: Date envoi message                     │
│ ℹ️ (sera ajoutée aux notes automatiquement)                  │
├─────────────────────────────────────────────────────────────┤
│ ÉTAPE 2: Analyse & Détection doublons        [🔍 Analyser]  │
├─────────────────────────────────────────────────────────────┤
│ === RÉSULTATS ANALYSE ===                                    │
│                                                              │
│ [Tab: ✨ Nouvelles (2)]  [Tab: 📋 Déjà en base (1)]         │
│                                                              │
│ ── Onglet "Nouvelles" ──                                     │
│ ┌────┬──────────────────┬─────────────┬───────────────────┐ │
│ │ ☑  │ Entreprise       │ Contact     │ Action            │ │
│ ├────┼──────────────────┼─────────────┼───────────────────┤ │
│ │ ☑  │ Midnight Trains  │ Odile Fagot │ Créer entreprise  │ │
│ │ ☑  │ Sustainable...   │ F. Maurage  │ Créer entreprise  │ │
│ └────┴──────────────────┴─────────────┴───────────────────┘ │
│                                                              │
│ ── Onglet "Déjà en base" ──                                  │
│ ┌────┬──────────────────┬─────────────┬───────────────────┐ │
│ │ ☑  │ SNCF RESEAU      │ O. Rohr     │ [Lier ▼]          │ │
│ │    │ ↳ Match: SNCF... │ 2 contacts  │ • Lier existant   │ │
│ │    │   (score: 95%)   │             │ • Créer doublon   │ │
│ │    │                  │             │ • Ignorer         │ │
│ └────┴──────────────────┴─────────────┴───────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ ÉTAPE 3: Options import                                      │
│                                                              │
│ ☑ Sync automatique vers HubSpot après import                │
│ Segment: [ICP Principal ▼]                                   │
│ Source: [csv_import_alix ▼]                                  │
│                                                              │
│ [📥 Importer 3 contacts]                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Détection des doublons

### 2.1 Critères de matching entreprise

```python
def find_matching_company(csv_row: dict) -> Optional[Company]:
    """
    Cherche une entreprise existante correspondante.

    Critères (par ordre de priorité):
    1. SIREN exact (si disponible) → match 100%
    2. Nom entreprise exact (insensible casse) → match 95%
    3. Nom entreprise fuzzy (> 85% similarité) → match 80%
    4. Email domaine identique → match 70%
    """

    # 1. Match SIREN
    if csv_row.get('siren'):
        company = company_manager.get_by_siren(csv_row['siren'])
        if company:
            return company, 100, "SIREN exact"

    # 2. Match nom exact
    company_name = csv_row.get('company_name', '').lower().strip()
    if company_name:
        company = company_manager.search(query=company_name, limit=1)
        if company and company[0]['company_name'].lower() == company_name:
            return company[0], 95, "Nom exact"

    # 3. Match nom fuzzy
    if company_name:
        companies = company_manager.search(query=company_name, limit=5)
        for c in companies:
            ratio = fuzz.ratio(c['company_name'].lower(), company_name)
            if ratio > 85:
                return c, ratio, f"Nom similaire ({ratio}%)"

    # 4. Match domaine email
    email = csv_row.get('email', '')
    if email and '@' in email:
        domain = email.split('@')[1]
        company = company_manager.get_by_domain(domain)
        if company:
            return company, 70, f"Domaine {domain}"

    return None, 0, None
```

### 2.2 Critères de matching contact

```python
def find_matching_contact(csv_row: dict, company_id: int = None) -> Optional[Contact]:
    """
    Cherche un contact existant correspondant.

    Critères:
    1. Email exact → match 100%
    2. LinkedIn URL exact → match 100%
    3. Nom + Prénom + Entreprise → match 90%
    4. Téléphone exact → match 85%
    """

    # 1. Email exact
    if csv_row.get('email'):
        contact = contact_manager.get_by_email(csv_row['email'])
        if contact:
            return contact, 100, "Email exact"

    # 2. LinkedIn
    if csv_row.get('linkedin_url'):
        contact = contact_manager.get_by_linkedin(csv_row['linkedin_url'])
        if contact:
            return contact, 100, "LinkedIn exact"

    # 3. Nom + Prénom + Entreprise
    firstname = csv_row.get('firstname', '').lower()
    lastname = csv_row.get('lastname', '').lower()
    if firstname and lastname and company_id:
        contacts = contact_manager.get_contacts_by_company(company_id)
        for c in contacts:
            if c['firstname'].lower() == firstname and c['lastname'].lower() == lastname:
                return c, 90, "Nom/Prénom/Entreprise"

    # 4. Téléphone
    if csv_row.get('phone'):
        contact = contact_manager.get_by_phone(csv_row['phone'])
        if contact:
            return contact, 85, "Téléphone exact"

    return None, 0, None
```

---

## 3. Actions possibles par ligne

### 3.1 Pour les nouvelles entreprises

| Action | Description |
|--------|-------------|
| **Créer** | Crée entreprise + contact |
| **Ignorer** | Ne pas importer cette ligne |

### 3.2 Pour les entreprises existantes

| Action | Description |
|--------|-------------|
| **Lier** | Ajoute le contact à l'entreprise existante |
| **Créer doublon** | Crée une nouvelle entreprise (force) |
| **Mettre à jour** | Met à jour l'entreprise + ajoute/update contact |
| **Ignorer** | Ne pas importer cette ligne |

---

## 4. Sync HubSpot

### 4.1 Mapping propriétés HubSpot Contact

```python
HUBSPOT_CONTACT_MAPPING = {
    # Champs standard HubSpot
    'email': 'email',
    'firstname': 'firstname',
    'lastname': 'lastname',
    'phone': 'phone',
    'jobtitle': 'job_title',
    'company': 'company_name',

    # Champs custom (à créer dans HubSpot si nécessaire)
    'linkedin_url': 'linkedin_url',           # ou hs_linkedin_url si existe
    'source_import': 'source',                # custom: origine du lead
    'segment': 'segment',                     # custom: ICP Principal, etc.
    'prospect_class': 'prospect_class',       # custom: A/B/C
    'notes': 'notes',                         # custom ou hs_lead_status
    'siren': 'siren',                         # custom
}
```

### 4.2 Mapping propriétés HubSpot Company

```python
HUBSPOT_COMPANY_MAPPING = {
    # Champs standard HubSpot
    'name': 'company_name',
    'domain': 'website',  # extrait du website ou email
    'phone': 'phone',
    'city': 'city',
    'zip': 'postal_code',
    'address': 'address',
    'industry': 'ape_code',  # ou mapping APE → industrie HubSpot
    'numberofemployees': 'employee_range',  # conversion nécessaire
    'annualrevenue': 'revenue_range',       # conversion nécessaire

    # Champs custom
    'siren': 'siren',
    'segment': 'segment',
    'prospect_class': 'prospect_class',
}
```

### 4.3 Logique de sync

```python
def sync_to_hubspot(contacts: List[dict], options: dict) -> SyncResult:
    """
    Synchronise les contacts importés vers HubSpot.

    Workflow:
    1. Pour chaque contact, chercher/créer l'entreprise HubSpot
    2. Créer/mettre à jour le contact HubSpot
    3. Associer contact → entreprise
    """

    with HubSpotClient() as hubspot:
        for contact in contacts:
            # 1. Entreprise
            company_data = extract_company_data(contact)
            hs_company_id = hubspot.get_or_create_company(company_data)

            # 2. Contact
            contact_data = extract_contact_data(contact)
            contact_data['associatedcompanyid'] = hs_company_id
            hs_contact_id = hubspot.get_or_create_contact(contact_data)

            # 3. Marquer comme synchronisé
            contact_manager.mark_synced_hubspot(contact['uuid'], hs_contact_id)
            company_manager.mark_synced_hubspot(contact['company_id'], hs_company_id)
```

---

## 5. Interface utilisateur détaillée

### 5.1 Étape 1: Upload & Mapping

```
┌─────────────────────────────────────────────────────────────┐
│ 📤 Import CSV                                                │
├─────────────────────────────────────────────────────────────┤
│ [Zone drag & drop fichier CSV]                              │
│                                                              │
│ ✅ fichier_alix.csv chargé                                   │
│ • 3 lignes, 9 colonnes                                       │
│ • Encodage: UTF-8, Séparateur: ;                            │
├─────────────────────────────────────────────────────────────┤
│ 🔗 Mapping des colonnes                                      │
│                                                              │
│ ┌─────────────┬───────────────┬────────────────────────────┐│
│ │ Colonne CSV │ Champ cible   │ Aperçu                     ││
│ ├─────────────┼───────────────┼────────────────────────────┤│
│ │ company_nam │ 🏢 Entreprise │ Midnight Trains, SNCF...   ││
│ │ firstname   │ 👤 Prénom     │ Odile, François, Olivier   ││
│ │ lastname    │ 👤 Nom        │ Fagot, Maurage, Rohr       ││
│ │ email       │ 📧 Email      │ olivier.rohr@...           ││
│ │ phone       │ 📞 Téléphone  │ 01 71 32... (2 numéros)    ││
│ │ job_title   │ 💼 Fonction   │ Senior Advisor, Resp...    ││
│ │ notes       │ 📝 Notes      │ 20/01 : mess laissé        ││
│ │ source_file │ 📁 Source     │ Fichier alix               ││
│ │ Date envoi  │ ➡️ Notes      │ (auto-ajouté aux notes)    ││
│ └─────────────┴───────────────┴────────────────────────────┘│
│                                                              │
│ 📋 Colonnes ignorées: aucune                                 │
│ ⚠️ Téléphones multiples détectés → 1er gardé, autres en notes│
│                                                              │
│                                    [🔍 Analyser les doublons]│
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Étape 2: Analyse doublons

```
┌─────────────────────────────────────────────────────────────┐
│ 📊 Analyse terminée                                          │
│                                                              │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│ │ Total    │ │ Nouvelles│ │ Existants│ │ Doublons │        │
│ │    3     │ │    2     │ │    1     │ │    0     │        │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
├─────────────────────────────────────────────────────────────┤
│ [Tab: ✨ Nouvelles (2)]  [Tab: 📋 Déjà en base (1)]         │
│                                                              │
│ ══════════════════════════════════════════════════════════  │
│ ✨ NOUVELLES ENTREPRISES                                     │
│ ══════════════════════════════════════════════════════════  │
│                                                              │
│ ☑ Midnight Trains                                            │
│   └─ Contact: Odile Fagot (Senior Advisor)                  │
│   └─ Action: Créer entreprise + contact                     │
│                                                              │
│ ☑ The sustainable procurement pledge                         │
│   └─ Contact: François Maurage (Spp Ambassador)             │
│   └─ Action: Créer entreprise + contact                     │
│                                                              │
│ ══════════════════════════════════════════════════════════  │
│ 📋 ENTREPRISES EXISTANTES                                    │
│ ══════════════════════════════════════════════════════════  │
│                                                              │
│ ☑ SNCF RESEAU                                                │
│   └─ Match: "SNCF RESEAU" (score: 100% - nom exact)         │
│   └─ Entreprise existante: 2 contacts déjà en base          │
│   └─ Contact CSV: Olivier Rohr (olivier.rohr@reseau.sncf.fr)│
│   └─ Action: [Lier à l'existant ▼]                          │
│              ├─ Lier à l'existant (recommandé)              │
│              ├─ Créer comme doublon                          │
│              ├─ Mettre à jour entreprise + lier             │
│              └─ Ignorer cette ligne                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 5.3 Étape 3: Options & Import

```
┌─────────────────────────────────────────────────────────────┐
│ ⚙️ Options d'import                                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Segment:  [ICP Principal ▼]                                  │
│ Source:   [csv_import      ]  (pour traçabilité)            │
│                                                              │
│ ☑ Synchroniser vers HubSpot après import                    │
│   └─ ☑ Créer entreprises HubSpot                            │
│   └─ ☑ Créer contacts HubSpot                               │
│   └─ ☑ Associer contacts → entreprises                      │
│                                                              │
│ ☐ Envoyer notification email après import                   │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│ 📊 Résumé                                                    │
│                                                              │
│ • 2 nouvelles entreprises à créer                           │
│ • 1 contact à lier à entreprise existante                   │
│ • 3 contacts à créer au total                               │
│ • Sync HubSpot: 3 contacts + 2 entreprises                  │
│                                                              │
│              [📥 Importer 3 contacts]                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Fichiers à modifier/créer

| Fichier | Modifications |
|---------|---------------|
| `modules/lead_scraper/csv_importer.py` | Ajouter `analyze_duplicates()`, `preview_import()` |
| `modules/lead_scraper/company_manager.py` | Ajouter `get_by_siren()`, `get_by_domain()` |
| `modules/lead_scraper/contact_manager.py` | Ajouter `get_by_email()`, `get_by_phone()`, `get_by_linkedin()` |
| `modules/lead_scraper/hubspot_client.py` | Ajouter `create_contact_with_company()`, mapping propriétés |
| `pages/5_📤_Import_CSV.py` | **Nouvelle page** dédiée à l'import CSV |
| `config/hubspot_mappings.py` | **Nouveau fichier** mappings propriétés HubSpot |

---

## 7. Plan d'implémentation

### Phase 1: Backend détection doublons (0.5 jour)
- [ ] `csv_importer.analyze_duplicates()`
- [ ] `company_manager.get_by_siren()`, `get_by_domain()`
- [ ] `contact_manager.get_by_email()`, `get_by_phone()`

### Phase 2: UI Import CSV v2 (1 jour)
- [ ] Créer `pages/5_📤_Import_CSV.py`
- [ ] Étape 1: Upload & mapping (existant, à migrer)
- [ ] Étape 2: Analyse doublons avec 2 onglets
- [ ] Étape 3: Options & Import

### Phase 3: Sync HubSpot (1 jour)
- [ ] Créer `config/hubspot_mappings.py`
- [ ] `hubspot_client.create_contact_with_company()`
- [ ] Association contact → entreprise HubSpot
- [ ] Checkbox sync auto après import

### Phase 4: Tests & Polish (0.5 jour)
- [ ] Tests avec fichiers CSV variés
- [ ] Gestion erreurs (API HubSpot rate limit, etc.)
- [ ] Messages utilisateur clairs

---

## 8. Métriques de succès

| Métrique | Objectif |
|----------|----------|
| Détection doublons entreprise | > 95% précision |
| Temps analyse 100 lignes | < 5s |
| Sync HubSpot 100 contacts | < 60s |
| Taux erreur import | < 1% |

---

## 9. Questions ouvertes

1. **Propriétés custom HubSpot**: Doit-on les créer automatiquement si elles n'existent pas ?
2. **Rate limiting HubSpot**: Gérer les quotas API (100 req/10s pour free tier)
3. **Rollback**: Si sync HubSpot échoue, que faire des données locales déjà créées ?
