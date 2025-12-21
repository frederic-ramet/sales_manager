# Epic 008 - Import Manuel CSV

## Contexte

Actuellement, les contacts peuvent être ajoutés via :
- Recherche SIRENE (automatique)
- Import HubSpot (automatique)
- Validation GetSales (semi-automatique)

Il manque la possibilité d'importer manuellement des fichiers CSV provenant de diverses sources (listes achetées, exports d'autres outils, etc.).

## Objectifs

1. **Upload de fichiers CSV**
2. **Détection et mapping des colonnes**
3. **Prévisualisation avant import**
4. **Import dans la table `unified_contacts`**

---

## Spécifications Techniques

### T8.1 - Interface upload CSV (~2h)

**Fichier:** `pages/3_📜_Base_de_Leads.py` (nouvel onglet)

Ajouter un onglet "Import CSV" avec :

```python
tab1, tab2, tab3 = st.tabs(["📋 Contacts", "☁️ HubSpot", "📤 Import CSV"])

with tab3:
    st.subheader("📤 Import CSV")

    uploaded_file = st.file_uploader(
        "Glissez votre fichier CSV ici",
        type=['csv'],
        help="Format: UTF-8 ou Latin-1, séparateur virgule ou point-virgule"
    )
```

**Gestion encodage/séparateur :**
- Détection automatique de l'encodage (chardet)
- Détection automatique du séparateur (csv.Sniffer)
- Option manuelle si détection échoue

### T8.2 - Mapping des colonnes (~3h)

**Fichier:** `modules/lead_scraper/csv_importer.py`

Créer une classe `CSVImporter` :

```python
class CSVImporter:
    # Colonnes cibles dans unified_contacts
    TARGET_COLUMNS = {
        'company_name': ['company', 'société', 'entreprise', 'nom', 'raison sociale', 'denomination'],
        'siren': ['siren', 'siret', 'n° siren'],
        'email': ['email', 'mail', 'e-mail', 'courriel'],
        'phone': ['phone', 'téléphone', 'tel', 'telephone', 'mobile'],
        'first_name': ['prénom', 'prenom', 'first_name', 'firstname'],
        'last_name': ['nom', 'last_name', 'lastname', 'nom de famille'],
        'job_title': ['poste', 'fonction', 'job', 'title', 'job_title'],
        'linkedin_url': ['linkedin', 'linkedin_url', 'profil linkedin'],
        'website': ['site', 'website', 'site web', 'url'],
        'city': ['ville', 'city', 'commune'],
        'postal_code': ['code postal', 'cp', 'postal_code', 'zip'],
        'address': ['adresse', 'address', 'rue'],
        'country': ['pays', 'country'],
        'ape_code': ['ape', 'naf', 'code ape', 'code naf'],
        'employee_count': ['effectif', 'employees', 'nb employés', 'taille'],
        'revenue': ['ca', 'chiffre affaires', 'revenue', 'chiffre_affaires'],
        'notes': ['notes', 'commentaires', 'description', 'remarques'],
    }

    def __init__(self, file_content: bytes, filename: str):
        self.file_content = file_content
        self.filename = filename
        self.df = None
        self.mapping = {}

    def detect_encoding(self) -> str:
        """Détecte l'encodage du fichier."""
        import chardet
        result = chardet.detect(self.file_content)
        return result['encoding'] or 'utf-8'

    def detect_separator(self, sample: str) -> str:
        """Détecte le séparateur CSV."""
        import csv
        sniffer = csv.Sniffer()
        try:
            dialect = sniffer.sniff(sample)
            return dialect.delimiter
        except:
            return ','

    def parse(self) -> pd.DataFrame:
        """Parse le fichier CSV."""
        encoding = self.detect_encoding()
        content = self.file_content.decode(encoding)
        separator = self.detect_separator(content[:2000])

        self.df = pd.read_csv(
            io.StringIO(content),
            sep=separator,
            dtype=str
        )
        return self.df

    def auto_map_columns(self) -> Dict[str, str]:
        """Mapping automatique des colonnes."""
        mapping = {}
        csv_columns = [c.lower().strip() for c in self.df.columns]

        for target, aliases in self.TARGET_COLUMNS.items():
            for alias in aliases:
                if alias.lower() in csv_columns:
                    idx = csv_columns.index(alias.lower())
                    mapping[target] = self.df.columns[idx]
                    break

        self.mapping = mapping
        return mapping

    def get_preview(self, n: int = 5) -> pd.DataFrame:
        """Retourne un aperçu des données mappées."""
        if not self.mapping:
            self.auto_map_columns()

        preview_data = {}
        for target, source in self.mapping.items():
            preview_data[target] = self.df[source].head(n)

        return pd.DataFrame(preview_data)

    def import_to_contacts(self, contact_manager, campaign_id: str = None) -> Tuple[int, int]:
        """Importe les données dans unified_contacts."""
        added = 0
        duplicates = 0

        for _, row in self.df.iterrows():
            contact_data = {}
            for target, source in self.mapping.items():
                if pd.notna(row.get(source)):
                    contact_data[target] = str(row[source]).strip()

            if not contact_data.get('company_name') and not contact_data.get('email'):
                continue  # Skip lignes sans données clés

            # Vérifier doublon
            existing = contact_manager.find_duplicate(
                email=contact_data.get('email'),
                siren=contact_data.get('siren'),
                linkedin_url=contact_data.get('linkedin_url')
            )

            if existing:
                duplicates += 1
                continue

            contact_data['source'] = 'csv_import'
            if campaign_id:
                contact_data['campaign_id'] = campaign_id

            contact_manager.add_contact(contact_data, source='csv_import')
            added += 1

        return added, duplicates
```

### T8.3 - Interface de mapping interactif (~2h)

**Dans `pages/3_📜_Base_de_Leads.py`:**

```python
with tab3:
    if uploaded_file:
        importer = CSVImporter(uploaded_file.getvalue(), uploaded_file.name)
        df = importer.parse()

        st.success(f"✅ {len(df)} lignes détectées")

        # Mapping automatique
        auto_mapping = importer.auto_map_columns()

        st.subheader("🔗 Mapping des colonnes")
        st.caption("Associez les colonnes du CSV aux champs de la base")

        # Interface de mapping
        mapping = {}
        csv_columns = ['(ignorer)'] + list(df.columns)

        cols = st.columns(3)
        for i, (target, aliases) in enumerate(CSVImporter.TARGET_COLUMNS.items()):
            with cols[i % 3]:
                default_idx = 0
                if target in auto_mapping:
                    try:
                        default_idx = csv_columns.index(auto_mapping[target])
                    except:
                        pass

                selected = st.selectbox(
                    target,
                    options=csv_columns,
                    index=default_idx,
                    key=f"map_{target}"
                )
                if selected != '(ignorer)':
                    mapping[target] = selected

        importer.mapping = mapping

        # Prévisualisation
        st.subheader("👀 Prévisualisation")
        preview = importer.get_preview(10)
        st.dataframe(preview, use_container_width=True)

        # Stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Lignes totales", len(df))
        with col2:
            st.metric("Colonnes mappées", len(mapping))
        with col3:
            required = ['company_name', 'email']
            has_required = any(r in mapping for r in required)
            st.metric("Prêt à importer", "✅" if has_required else "❌")

        # Import
        if st.button("📥 Importer", type="primary", disabled=not has_required):
            with st.spinner("Import en cours..."):
                contact_manager = ContactManager()
                campaign_id = f"csv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                added, duplicates = importer.import_to_contacts(contact_manager, campaign_id)

            st.success(f"✅ Import terminé: {added} contacts ajoutés, {duplicates} doublons ignorés")
            st.balloons()
```

### T8.4 - Gestion des erreurs et validation (~1h)

**Validations à ajouter :**

1. **Format fichier**
   - Taille max: 10 MB
   - Extension: .csv uniquement
   - Encodage supporté: UTF-8, Latin-1, Windows-1252

2. **Contenu**
   - Au moins une colonne mappée vers `company_name` ou `email`
   - Détection lignes vides ou invalides
   - Nettoyage automatique (trim, lowercase emails)

3. **Feedback utilisateur**
   - Barre de progression pour gros fichiers
   - Rapport d'import détaillé (succès, doublons, erreurs)
   - Option télécharger rapport CSV

```python
def validate_import(self) -> List[str]:
    """Valide les données avant import."""
    errors = []

    if not self.mapping:
        errors.append("Aucune colonne mappée")
        return errors

    if 'company_name' not in self.mapping and 'email' not in self.mapping:
        errors.append("Mappez au moins 'company_name' ou 'email'")

    # Vérifier données
    empty_rows = self.df.isna().all(axis=1).sum()
    if empty_rows > 0:
        errors.append(f"{empty_rows} lignes vides détectées")

    return errors
```

---

## Formats CSV supportés

L'import doit gérer les formats courants :

| Source | Particularités |
|--------|----------------|
| Excel export | UTF-8 ou Windows-1252, séparateur ; |
| HubSpot export | UTF-8, séparateur , |
| LinkedIn export | UTF-8, colonnes spécifiques |
| Fichiers achetés | Variable, souvent Latin-1 |

---

## Critères d'acceptation

1. [ ] Upload de fichiers CSV jusqu'à 10 MB
2. [ ] Détection automatique encodage et séparateur
3. [ ] Mapping automatique des colonnes courantes
4. [ ] Interface pour ajuster le mapping manuellement
5. [ ] Prévisualisation des 10 premières lignes mappées
6. [ ] Validation avant import (colonnes requises)
7. [ ] Déduplication pendant l'import (email, SIREN, LinkedIn)
8. [ ] Rapport d'import (ajoutés, doublons, erreurs)
9. [ ] Source = 'csv_import' pour traçabilité

---

## Estimation

| Tâche | Temps |
|-------|-------|
| T8.1 - Interface upload | 2h |
| T8.2 - Classe CSVImporter | 3h |
| T8.3 - Interface mapping | 2h |
| T8.4 - Validation/erreurs | 1h |
| **Total** | **~8h** |

---

## Notes

- L'utilisateur fournira des exemples de fichiers CSV pour tester
- Prévoir support futur: Excel (.xlsx), vCard (.vcf)
