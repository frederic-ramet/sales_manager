"""
Service d'import CSV pour unified_contacts.

Gère:
- Détection encodage (UTF-8, Latin-1, Windows-1252)
- Détection séparateur (, ; \t)
- Mapping automatique des colonnes
- Déduplication avec DeduplicationMatcher
- Import dans unified_contacts
"""
import io
import csv
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ImportResult:
    """Résultat d'un import CSV."""
    total_rows: int = 0
    imported: int = 0
    duplicates: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)
    duplicate_details: List[Dict[str, Any]] = field(default_factory=list)


class CSVImporter:
    """
    Service d'import de fichiers CSV vers unified_contacts.

    Usage:
        importer = CSVImporter(file_content, filename)
        df = importer.parse()
        mapping = importer.auto_map_columns()
        # ... ajuster le mapping si nécessaire
        result = importer.import_to_contacts(contact_manager)
    """

    # Mapping colonnes CSV → champs unified_contacts
    # Clé = champ cible, valeurs = alias possibles (lowercase)
    TARGET_COLUMNS = {
        'company_name': [
            'entreprise', 'company', 'société', 'societe', 'nom',
            'raison sociale', 'denomination', 'company_name', 'nom entreprise'
        ],
        'siren': ['siren', 'siret', 'n° siren', 'numero siren'],
        'email': ['email', 'mail', 'e-mail', 'courriel', 'adresse email'],
        'phone': [
            'numéro de téléphone', 'numero de telephone', 'phone', 'téléphone',
            'telephone', 'tel', 'mobile', 'portable', 'tel fixe', 'tel mobile'
        ],
        'firstname': ['prénom', 'prenom', 'first_name', 'firstname', 'first name'],
        'lastname': ['nom', 'last_name', 'lastname', 'last name', 'nom de famille'],
        'job_title': [
            'fonction', 'poste', 'job', 'title', 'job_title', 'titre',
            'fonction/poste', 'position', 'role'
        ],
        'linkedin_url': [
            'linkedin', 'linkedin_url', 'profil linkedin', 'url linkedin',
            'lien linkedin'
        ],
        'website': ['site', 'website', 'site web', 'url', 'site internet'],
        'city': ['ville', 'city', 'commune', 'localité', 'localite'],
        'postal_code': ['code postal', 'cp', 'postal_code', 'zip', 'code_postal'],
        'address': ['adresse', 'address', 'rue', 'adresse postale'],
        'country': ['pays', 'country'],
        'region': ['région', 'region', 'département', 'departement'],
        'ape_code': ['ape', 'naf', 'code ape', 'code naf', 'code_ape'],
        'employee_range': [
            'effectif', 'employees', 'nb employés', 'taille', 'nombre employés',
            'tranche effectif', 'employee_range'
        ],
        'revenue_range': [
            'ca', 'chiffre affaires', 'revenue', 'chiffre_affaires',
            'chiffre d\'affaires', 'revenue_range'
        ],
        'notes': [
            'notes', 'commentaire', 'commentaires', 'description', 'remarques',
            'observations', 'note'
        ],
        'source_file': ['source', 'origine', 'fichier source', 'provenance'],
    }

    # Colonnes qui ne seront pas importées mais conservées comme métadonnées
    METADATA_COLUMNS = [
        'date envoi message', 'date_envoi', 'date contact', 'date',
        'statut', 'status', 'étape', 'stage'
    ]

    def __init__(self, file_content: bytes, filename: str):
        """
        Initialise l'importeur CSV.

        Args:
            file_content: Contenu brut du fichier
            filename: Nom du fichier (pour logging)
        """
        self.file_content = file_content
        self.filename = filename
        self.df: Optional[pd.DataFrame] = None
        self.mapping: Dict[str, str] = {}
        self.encoding: str = 'utf-8'
        self.separator: str = ','

    def detect_encoding(self) -> str:
        """
        Détecte l'encodage du fichier.

        Returns:
            Encodage détecté (utf-8, latin-1, etc.)
        """
        try:
            import chardet
            result = chardet.detect(self.file_content)
            encoding = result.get('encoding', 'utf-8')
            confidence = result.get('confidence', 0)

            logger.info(f"Encodage détecté: {encoding} (confiance: {confidence:.0%})")

            # Fallback si confiance faible
            if confidence < 0.7:
                # Essayer UTF-8 d'abord
                try:
                    self.file_content.decode('utf-8')
                    return 'utf-8'
                except UnicodeDecodeError:
                    return 'latin-1'

            return encoding or 'utf-8'

        except ImportError:
            logger.warning("chardet non installé, fallback vers utf-8")
            return 'utf-8'

    def detect_separator(self, sample: str) -> str:
        """
        Détecte le séparateur CSV.

        Args:
            sample: Échantillon du contenu (premières lignes)

        Returns:
            Séparateur détecté (, ; ou \t)
        """
        try:
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample, delimiters=',;\t')
            separator = dialect.delimiter
            logger.info(f"Séparateur détecté: '{separator}'")
            return separator
        except csv.Error:
            # Fallback: compter les occurrences
            counts = {
                ',': sample.count(','),
                ';': sample.count(';'),
                '\t': sample.count('\t')
            }
            separator = max(counts, key=counts.get)
            logger.info(f"Séparateur par comptage: '{separator}'")
            return separator

    def parse(
        self,
        encoding: Optional[str] = None,
        separator: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Parse le fichier CSV.

        Args:
            encoding: Forcer l'encodage (optionnel)
            separator: Forcer le séparateur (optionnel)

        Returns:
            DataFrame avec les données
        """
        # Détecter encodage si non spécifié
        self.encoding = encoding or self.detect_encoding()

        # Décoder le contenu
        try:
            content = self.file_content.decode(self.encoding)
        except UnicodeDecodeError:
            # Fallback latin-1
            logger.warning(f"Erreur décodage {self.encoding}, fallback latin-1")
            self.encoding = 'latin-1'
            content = self.file_content.decode(self.encoding)

        # Détecter séparateur si non spécifié
        self.separator = separator or self.detect_separator(content[:2000])

        # Parser avec pandas
        self.df = pd.read_csv(
            io.StringIO(content),
            sep=self.separator,
            dtype=str,
            keep_default_na=False  # Garder les chaînes vides comme ''
        )

        # Nettoyer les noms de colonnes
        self.df.columns = [c.strip() for c in self.df.columns]

        logger.info(f"CSV parsé: {len(self.df)} lignes, {len(self.df.columns)} colonnes")
        return self.df

    def auto_map_columns(self) -> Dict[str, str]:
        """
        Mapping automatique des colonnes CSV vers les champs cibles.

        Returns:
            Dict {champ_cible: colonne_csv}
        """
        if self.df is None:
            raise ValueError("Appelez parse() d'abord")

        mapping = {}
        csv_columns_lower = {c.lower().strip(): c for c in self.df.columns}

        for target, aliases in self.TARGET_COLUMNS.items():
            for alias in aliases:
                alias_lower = alias.lower()
                if alias_lower in csv_columns_lower:
                    mapping[target] = csv_columns_lower[alias_lower]
                    break

        self.mapping = mapping
        logger.info(f"Mapping automatique: {len(mapping)} colonnes mappées")
        return mapping

    def get_preview(self, n: int = 10) -> pd.DataFrame:
        """
        Retourne un aperçu des données avec le mapping appliqué.

        Args:
            n: Nombre de lignes

        Returns:
            DataFrame avec colonnes renommées
        """
        if self.df is None:
            raise ValueError("Appelez parse() d'abord")

        if not self.mapping:
            self.auto_map_columns()

        # Créer le preview avec les colonnes mappées
        preview_data = {}
        for target, source in self.mapping.items():
            if source in self.df.columns:
                preview_data[target] = self.df[source].head(n)

        return pd.DataFrame(preview_data)

    def validate(self) -> List[str]:
        """
        Valide les données avant import.

        Returns:
            Liste des erreurs (vide si OK)
        """
        errors = []

        if self.df is None:
            errors.append("Fichier non parsé")
            return errors

        if not self.mapping:
            errors.append("Aucune colonne mappée")
            return errors

        # Vérifier qu'au moins company_name ou email est mappé
        required = ['company_name', 'email']
        has_required = any(r in self.mapping for r in required)
        if not has_required:
            errors.append("Mappez au moins 'company_name' ou 'email'")

        # Compter lignes vides
        empty_rows = 0
        for _, row in self.df.iterrows():
            has_data = False
            for source in self.mapping.values():
                if source in row and row[source] and str(row[source]).strip():
                    has_data = True
                    break
            if not has_data:
                empty_rows += 1

        if empty_rows > 0:
            errors.append(f"{empty_rows} lignes sans données mappées")

        return errors

    def import_to_contacts(
        self,
        contact_manager,
        dedup_matcher=None,
        campaign_id: Optional[str] = None,
        source_name: str = 'csv_import',
        skip_duplicates: bool = True,
        progress_callback=None
    ) -> ImportResult:
        """
        Importe les données dans unified_contacts.

        Args:
            contact_manager: Instance de ContactManager
            dedup_matcher: Instance de DeduplicationMatcher (optionnel)
            campaign_id: ID de campagne pour traçabilité
            source_name: Nom de la source
            skip_duplicates: Ignorer les doublons (sinon les lister)
            progress_callback: Callback(current, total) pour progression

        Returns:
            ImportResult avec statistiques
        """
        if self.df is None or not self.mapping:
            raise ValueError("Appelez parse() et configurez le mapping d'abord")

        result = ImportResult(total_rows=len(self.df))

        # Générer campaign_id si non fourni
        if not campaign_id:
            campaign_id = f"csv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        for idx, row in self.df.iterrows():
            if progress_callback:
                progress_callback(idx + 1, len(self.df))

            # Extraire les données selon le mapping
            contact_data = {}
            for target, source in self.mapping.items():
                value = row.get(source, '')
                if value and str(value).strip():
                    contact_data[target] = str(value).strip()

            # Extraire les colonnes métadonnées non mappées (date envoi, commentaire, etc.)
            # et les ajouter aux notes
            metadata_parts = []
            for col in self.df.columns:
                col_lower = col.lower().strip()
                # Colonnes métadonnées à inclure dans notes
                if any(meta in col_lower for meta in ['date envoi', 'date_envoi', 'date contact', 'commentaire', 'statut', 'étape']):
                    if col not in self.mapping.values():  # Pas déjà mappée
                        value = row.get(col, '')
                        if value and str(value).strip():
                            metadata_parts.append(f"{col}: {str(value).strip()}")

            if metadata_parts:
                existing_notes = contact_data.get('notes', '') or ''
                metadata_str = ' | '.join(metadata_parts)
                contact_data['notes'] = f"{existing_notes}\n{metadata_str}".strip() if existing_notes else metadata_str

            # Skip si pas de données essentielles
            if not contact_data.get('company_name') and not contact_data.get('email'):
                result.skipped += 1
                continue

            # Nettoyer l'email (lowercase)
            if contact_data.get('email'):
                contact_data['email'] = contact_data['email'].lower().strip()

            # Nettoyer le téléphone
            # Gère: séparateur ; OU numéros FR collés (10 chiffres chacun)
            if contact_data.get('phone'):
                phone = str(contact_data['phone'])
                phones = []

                # Cas 1: séparateur ;
                if ';' in phone:
                    phones = [p.strip() for p in phone.split(';') if p.strip()]
                else:
                    # Cas 2: détecter numéros FR collés (10 chiffres = 1 numéro)
                    # Ex: "01 71 32 30 32 06 11 74 94 86" = 20 chiffres = 2 numéros
                    digits_only = ''.join(c for c in phone if c.isdigit())
                    if len(digits_only) > 10 and len(digits_only) % 10 == 0:
                        # Plusieurs numéros FR de 10 chiffres collés
                        num_phones = len(digits_only) // 10
                        for i in range(num_phones):
                            num = digits_only[i*10:(i+1)*10]
                            # Formater en XX XX XX XX XX
                            formatted = ' '.join([num[j:j+2] for j in range(0, 10, 2)])
                            phones.append(formatted)
                    else:
                        phones = [phone]

                if phones:
                    # Prendre le premier, nettoyer
                    main_phone = phones[0]
                    main_phone = ''.join(c for c in main_phone if c.isdigit() or c == '+' or c == ' ')
                    contact_data['phone'] = main_phone.strip()

                    # Stocker les numéros supplémentaires dans notes
                    if len(phones) > 1:
                        extra_phones = '; '.join(phones[1:])
                        notes = contact_data.get('notes', '') or ''
                        contact_data['notes'] = f"{notes}\nTél. supplémentaires: {extra_phones}".strip()

            # Vérifier doublons
            is_duplicate = False
            duplicate_info = None

            if dedup_matcher:
                matches = dedup_matcher.find_matches(
                    email=contact_data.get('email'),
                    linkedin_url=contact_data.get('linkedin_url'),
                    company_name=contact_data.get('company_name'),
                    firstname=contact_data.get('firstname'),
                    lastname=contact_data.get('lastname'),
                    include_low_confidence=False  # Seulement HIGH/EXACT
                )

                if matches:
                    is_duplicate = True
                    best_match = matches[0]
                    duplicate_info = {
                        'row': idx + 2,  # +2 car header + index 0
                        'input_data': contact_data,
                        'match': best_match.to_dict(),
                        'confidence': best_match.confidence.value
                    }

            if is_duplicate:
                result.duplicates += 1
                if duplicate_info:
                    result.duplicate_details.append(duplicate_info)

                if skip_duplicates:
                    continue

            # Ajouter métadonnées
            contact_data['source'] = source_name
            contact_data['campaign_id'] = campaign_id

            # Récupérer source_file du CSV si mappé
            if 'source_file' in contact_data:
                contact_data['import_source_file'] = contact_data.pop('source_file')

            # Import
            try:
                contact_manager.add_contact(contact_data, source=source_name)
                result.imported += 1
            except Exception as e:
                result.errors.append(f"Ligne {idx + 2}: {str(e)}")

        logger.info(
            f"Import terminé: {result.imported} ajoutés, "
            f"{result.duplicates} doublons, {result.skipped} ignorés"
        )

        return result

    def get_unmapped_columns(self) -> List[str]:
        """Retourne les colonnes CSV non mappées."""
        if self.df is None:
            return []

        mapped_sources = set(self.mapping.values())
        return [c for c in self.df.columns if c not in mapped_sources]

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du fichier."""
        if self.df is None:
            return {}

        return {
            'rows': len(self.df),
            'columns': len(self.df.columns),
            'encoding': self.encoding,
            'separator': repr(self.separator),
            'mapped_columns': len(self.mapping),
            'unmapped_columns': len(self.get_unmapped_columns())
        }

    def analyze_duplicates(
        self,
        company_manager,
        contact_manager
    ) -> Dict[str, Any]:
        """
        Analyse les doublons entreprise/contact pour chaque ligne du CSV.

        Retourne pour chaque ligne:
        - company_match: entreprise existante trouvée (ou None)
        - company_match_type: type de match ('siren', 'name_exact', 'name_fuzzy', 'domain')
        - company_match_score: score de confiance (0-100)
        - contact_match: contact existant trouvé (ou None)
        - contact_match_type: type de match ('email', 'linkedin', 'phone', 'name')
        - action: action suggérée ('create', 'link', 'update', 'ignore')

        Args:
            company_manager: Instance de CompanyManager
            contact_manager: Instance de ContactManager

        Returns:
            Dict avec:
            - rows: liste de dicts avec infos de matching par ligne
            - stats: statistiques globales
        """
        if self.df is None or not self.mapping:
            raise ValueError("Appelez parse() et configurez le mapping d'abord")

        rows_analysis = []
        stats = {
            'total': len(self.df),
            'new_companies': 0,
            'existing_companies': 0,
            'new_contacts': 0,
            'existing_contacts': 0,
        }

        for idx, row in self.df.iterrows():
            # Extraire les données selon le mapping
            row_data = {}
            for target, source in self.mapping.items():
                value = row.get(source, '')
                if value and str(value).strip():
                    row_data[target] = str(value).strip()

            analysis = {
                'row_index': idx,
                'row_data': row_data,
                'company_match': None,
                'company_match_type': None,
                'company_match_score': 0,
                'contact_match': None,
                'contact_match_type': None,
                'contact_match_score': 0,
                'action': 'create',  # Par défaut
                'selected': True,  # Sélectionné par défaut
            }

            # =============================
            # 1. MATCHING ENTREPRISE
            # =============================

            company_name = row_data.get('company_name', '')
            siren = row_data.get('siren', '')
            email = row_data.get('email', '')

            # 1a. Par SIREN (100%)
            if siren:
                company = company_manager.find_by_siren(siren)
                if company:
                    analysis['company_match'] = company
                    analysis['company_match_type'] = 'siren'
                    analysis['company_match_score'] = 100

            # 1b. Par nom exact (95%)
            if not analysis['company_match'] and company_name:
                company = company_manager.find_by_name_exact(company_name)
                if company:
                    analysis['company_match'] = company
                    analysis['company_match_type'] = 'name_exact'
                    analysis['company_match_score'] = 95

            # 1c. Par nom fuzzy (>85%)
            if not analysis['company_match'] and company_name:
                fuzzy_matches = company_manager.find_by_name_fuzzy(company_name, threshold=0.85, limit=1)
                if fuzzy_matches:
                    best = fuzzy_matches[0]
                    analysis['company_match'] = best['company']
                    analysis['company_match_type'] = 'name_fuzzy'
                    analysis['company_match_score'] = int(best['similarity_score'] * 100)

            # 1d. Par domaine email (70%)
            if not analysis['company_match'] and email and '@' in email:
                company = company_manager.get_by_domain(email)
                if company:
                    analysis['company_match'] = company
                    analysis['company_match_type'] = 'domain'
                    analysis['company_match_score'] = 70

            # =============================
            # 2. MATCHING CONTACT
            # =============================

            linkedin_url = row_data.get('linkedin_url', '')
            phone = row_data.get('phone', '')
            firstname = row_data.get('firstname', '')
            lastname = row_data.get('lastname', '')

            # 2a. Par email (100%)
            if email:
                contact = contact_manager.get_by_email(email)
                if contact:
                    analysis['contact_match'] = contact
                    analysis['contact_match_type'] = 'email'
                    analysis['contact_match_score'] = 100

            # 2b. Par LinkedIn (100%)
            if not analysis['contact_match'] and linkedin_url:
                contact = contact_manager.get_by_linkedin(linkedin_url)
                if contact:
                    analysis['contact_match'] = contact
                    analysis['contact_match_type'] = 'linkedin'
                    analysis['contact_match_score'] = 100

            # 2c. Par téléphone (85%)
            if not analysis['contact_match'] and phone:
                contact = contact_manager.get_by_phone(phone)
                if contact:
                    analysis['contact_match'] = contact
                    analysis['contact_match_type'] = 'phone'
                    analysis['contact_match_score'] = 85

            # 2d. Par nom + prénom + entreprise (90%)
            if not analysis['contact_match'] and firstname and lastname and analysis['company_match']:
                company_id = analysis['company_match'].get('id')
                if company_id:
                    contacts = contact_manager.get_contacts_by_company(company_id, limit=100)
                    for c in contacts:
                        if (c.get('firstname', '').lower() == firstname.lower() and
                                c.get('lastname', '').lower() == lastname.lower()):
                            analysis['contact_match'] = c
                            analysis['contact_match_type'] = 'name_company'
                            analysis['contact_match_score'] = 90
                            break

            # =============================
            # 3. DÉTERMINER L'ACTION
            # =============================

            if analysis['company_match']:
                stats['existing_companies'] += 1
                if analysis['contact_match']:
                    stats['existing_contacts'] += 1
                    analysis['action'] = 'update'  # Mise à jour
                else:
                    stats['new_contacts'] += 1
                    analysis['action'] = 'link'  # Lier à entreprise existante
            else:
                stats['new_companies'] += 1
                stats['new_contacts'] += 1
                analysis['action'] = 'create'  # Créer tout

            rows_analysis.append(analysis)

        return {
            'rows': rows_analysis,
            'stats': stats
        }
