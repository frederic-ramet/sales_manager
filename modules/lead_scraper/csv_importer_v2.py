"""
CSV Importer V2 - Import CSV avec mapping intelligent (Schema V2).

Pipeline: Import → Clean → Enrich → Sync

Usage:
    importer = CSVImporterV2(company_manager, contact_manager)

    # Détecter les colonnes
    detection = importer.detect_columns(file_path)

    # Importer avec mapping personnalisé
    report = importer.import_file(
        file_path,
        mapping=detection['suggested_mapping'],
        source_name='fullenrich_export'
    )
"""

import csv
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import re

logger = logging.getLogger(__name__)

# Mapping automatique des colonnes CSV vers champs DB
DEFAULT_CSV_MAPPING = {
    # =========================================================================
    # COMPANY FIELDS
    # =========================================================================
    # Name
    'Company': 'companies.name',
    'Company 1 Name': 'companies.name',
    'company_name': 'companies.name',
    'Company Name': 'companies.name',
    'company': 'companies.name',
    'Entreprise': 'companies.name',
    'entreprise': 'companies.name',

    # Domain/Website
    'Domain': 'companies.domain',
    'Company 1 Website': 'companies.domain',
    'website': 'companies.domain',
    'Website': 'companies.domain',
    'Company Website': 'companies.domain',
    'Company Domain': 'companies.domain',
    'Site web': 'companies.domain',

    # SIREN/SIRET
    'SIREN': 'companies.siren',
    'siren': 'companies.siren',
    'SIRET': 'companies.siret',
    'siret': 'companies.siret',

    # Size
    'Size': 'companies.size',
    'Company 1 Size': 'companies.size',
    'size': 'companies.size',
    'Company Size': 'companies.size',
    'employee_range': 'companies.size',
    'Employees': 'companies.size',
    'Effectif': 'companies.size',

    # Revenue
    'Company 1 Revenue': 'companies.revenue',
    'revenue': 'companies.revenue',
    'Revenue': 'companies.revenue',
    'CA': 'companies.revenue',

    # Location HQ
    'Company 1 HQ City': 'companies.hq_city',
    'Company City': 'companies.hq_city',
    'company_city': 'companies.hq_city',
    'HQ City': 'companies.hq_city',
    'Ville': 'companies.hq_city',

    'Company 1 HQ State': 'companies.hq_state',
    'Company State': 'companies.hq_state',
    'HQ State': 'companies.hq_state',
    'Region': 'companies.hq_state',
    'Région': 'companies.hq_state',

    'Company 1 HQ Country': 'companies.hq_country',
    'Company Country': 'companies.hq_country',
    'company_country': 'companies.hq_country',
    'HQ Country': 'companies.hq_country',
    'Geo - company': 'companies.hq_country',
    'Pays': 'companies.hq_country',

    'Company 1 HQ Address': 'companies.hq_address',
    'Company Address': 'companies.hq_address',
    'Address': 'companies.hq_address',
    'Adresse': 'companies.hq_address',

    'Company 1 HQ Postal Code': 'companies.hq_postal_code',
    'Postal Code': 'companies.hq_postal_code',
    'ZIP': 'companies.hq_postal_code',
    'Code Postal': 'companies.hq_postal_code',

    # Industry
    'Company 1 Industries': 'companies.industry',
    'industry': 'companies.industry',
    'Industry': 'companies.industry',
    'Sector': 'companies.industry',
    'Secteur': 'companies.industry',

    # Description
    'Company 1 Description': 'companies.description',
    'description': 'companies.description',
    'Description': 'companies.description',

    # Legal
    'Legal Form': 'companies.legal_form',
    'legal_form': 'companies.legal_form',
    'Company Type': 'companies.legal_form',
    'Forme juridique': 'companies.legal_form',

    # APE
    'APE Code': 'companies.ape_code',
    'ape_code': 'companies.ape_code',
    'NAF': 'companies.ape_code',
    'Code APE': 'companies.ape_code',
    'APE Label': 'companies.ape_label',
    'ape_label': 'companies.ape_label',

    # Investment (startups)
    'Company 1 Investment Stage': 'companies.investment_stage',
    'Investment Stage': 'companies.investment_stage',
    'Funding Stage': 'companies.investment_stage',

    'Company 1 Investment Amount': 'companies.investment_amount',
    'Investment Amount': 'companies.investment_amount',
    'Total Funding': 'companies.investment_amount',

    'Company 1 Investment Date': 'companies.investment_date',
    'Investment Date': 'companies.investment_date',
    'Last Funding Date': 'companies.investment_date',

    'Company 1 Lead Investor': 'companies.lead_investor',
    'Lead Investor': 'companies.lead_investor',

    # Other company fields
    'Company 1 Founded Date': 'companies.founded_date',
    'Founded': 'companies.founded_date',
    'Founded Date': 'companies.founded_date',

    'Company 1 Technology Used': 'companies.technology_used',
    'Technology Used': 'companies.technology_used',
    'Tech Stack': 'companies.technology_used',

    # =========================================================================
    # CONTACT FIELDS
    # =========================================================================
    # Name
    'First Name': 'contacts.firstname',
    'firstname': 'contacts.firstname',
    'FirstName': 'contacts.firstname',
    'first_name': 'contacts.firstname',
    'Prénom': 'contacts.firstname',

    'Last Name': 'contacts.lastname',
    'lastname': 'contacts.lastname',
    'LastName': 'contacts.lastname',
    'last_name': 'contacts.lastname',
    'Nom': 'contacts.lastname',

    # Email
    'Email': 'contacts.email',
    'email': 'contacts.email',
    'Email Address': 'contacts.email',
    'Work Email': 'contacts.email',
    'Verified Professional Email 1': 'contacts.email',
    'Professional Email': 'contacts.email',

    'Unverified Professional Email 1': 'contacts.email_secondary',
    'Personal Email': 'contacts.email_secondary',
    'Secondary Email': 'contacts.email_secondary',

    # Phone
    'Phone': 'contacts.phone',
    'phone': 'contacts.phone',
    'Phone Number': 'contacts.phone',
    'Direct Dial': 'contacts.phone',
    'Work Phone': 'contacts.phone',
    'Téléphone': 'contacts.phone',
    'Numéro de téléphone': 'contacts.phone',

    'Mobile': 'contacts.mobile',
    'mobile': 'contacts.mobile',
    'Mobile Phone': 'contacts.mobile',
    'Cell': 'contacts.mobile',
    'Cell Phone': 'contacts.mobile',
    'Portable': 'contacts.mobile',

    # LinkedIn
    'LinkedIn': 'contacts.linkedin_url',
    'linkedin_url': 'contacts.linkedin_url',
    'LinkedIn URL': 'contacts.linkedin_url',
    'linkedin': 'contacts.linkedin_url',
    'Person Linkedin Url': 'contacts.linkedin_url',
    'LinkedIn URL 1': 'contacts.linkedin_url',

    # Job
    'Title': 'contacts.job_title',
    'Job Title': 'contacts.job_title',
    'job_title': 'contacts.job_title',
    'Position': 'contacts.job_title',
    'Company 1 Job Title': 'contacts.job_title',
    'Role': 'contacts.job_title',
    'Fonction': 'contacts.job_title',
    'Poste': 'contacts.job_title',

    'Seniority': 'contacts.seniority',
    'seniority': 'contacts.seniority',
    'Level': 'contacts.seniority',

    'Department': 'contacts.department',
    'department': 'contacts.department',
    'Function': 'contacts.department',

    # Location contact
    'City': 'contacts.city',
    'city': 'contacts.city',
    'Person City': 'contacts.city',
    'Contact City': 'contacts.city',
    'Location': 'contacts.city',

    'State': 'contacts.state',
    'state': 'contacts.state',
    'Person State': 'contacts.state',
    'Contact State': 'contacts.state',

    'Country': 'contacts.country',
    'country': 'contacts.country',
    'Person Country': 'contacts.country',
    'Contact Country': 'contacts.country',
    'Geo - lead': 'contacts.country',

    'Timezone': 'contacts.timezone',
    'Timezone - lead': 'contacts.timezone',

    # Social
    'Twitter': 'contacts.twitter_url',
    'Twitter URL': 'contacts.twitter_url',
    'twitter_url': 'contacts.twitter_url',

    'Github': 'contacts.github_url',
    'Github URL': 'contacts.github_url',
    'github_url': 'contacts.github_url',

    'Facebook': 'contacts.facebook_url',
    'Facebook URL': 'contacts.facebook_url',

    # GetSales specific
    'uuid': 'contacts.getsales_uuid',
    'UUID': 'contacts.getsales_uuid',
    'getsales_uuid': 'contacts.getsales_uuid',

    'campaign_id': 'contacts.campaign_id',
    'Campaign ID': 'contacts.campaign_id',
    'Campaign': 'contacts.campaign_id',

    'project': 'contacts.project_name',
    'Project': 'contacts.project_name',
    'project_name': 'contacts.project_name',
    'Project Name': 'contacts.project_name',

    'search': 'contacts.search_name',
    'Search': 'contacts.search_name',
    'search_name': 'contacts.search_name',
    'Search Name': 'contacts.search_name',
}

# Liste des champs DB disponibles
DB_FIELDS = {
    'companies': [
        'name', 'domain', 'siren', 'siret',
        'hq_address', 'hq_city', 'hq_state', 'hq_postal_code', 'hq_country',
        'legal_form', 'ape_code', 'ape_label', 'industry', 'description',
        'size', 'size_exact', 'revenue', 'revenue_range',
        'investment_stage', 'investment_amount', 'investment_date', 'lead_investor',
        'founded_date', 'technology_used'
    ],
    'contacts': [
        'firstname', 'lastname', 'linkedin_url',
        'email', 'email_secondary', 'phone', 'mobile',
        'job_title', 'seniority', 'department',
        'city', 'state', 'country', 'timezone',
        'twitter_url', 'github_url', 'facebook_url',
        'getsales_uuid', 'campaign_id', 'project_name', 'search_name'
    ]
}


class CSVImporterV2:
    """
    Importateur CSV avec mapping intelligent - Schema V2.

    Détecte automatiquement le format (FullEnrich, Salesbot, etc.)
    et mappe les colonnes vers le schema DB.
    """

    def __init__(self, company_manager=None, contact_manager=None):
        """
        Args:
            company_manager: Instance de CompanyManagerV2
            contact_manager: Instance de ContactManagerV2
        """
        self.company_manager = company_manager
        self.contact_manager = contact_manager

    def detect_columns(self, file_path: str) -> Dict[str, Any]:
        """
        Détecte les colonnes d'un fichier CSV et propose un mapping.

        Returns:
            {
                'columns': ['col1', 'col2', ...],
                'suggested_mapping': {'col1': 'companies.name', ...},
                'unmapped': ['col3', ...],
                'row_count': 1234,
                'sample_data': [{...}, {...}, ...],
                'encoding': 'utf-8',
                'delimiter': ','
            }
        """
        result = {
            'columns': [],
            'suggested_mapping': {},
            'unmapped': [],
            'row_count': 0,
            'sample_data': [],
            'encoding': 'utf-8',
            'delimiter': ','
        }

        try:
            # Détecter l'encodage et le délimiteur
            encoding = self._detect_encoding(file_path)
            delimiter = self._detect_delimiter(file_path, encoding)
            result['encoding'] = encoding
            result['delimiter'] = delimiter

            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                # Nettoyer BOM et espaces des noms de colonnes
                raw_columns = reader.fieldnames or []
                result['columns'] = [col.strip().lstrip('\ufeff') for col in raw_columns]

                # Lire quelques lignes pour l'aperçu
                for i, raw_row in enumerate(reader):
                    # Nettoyer BOM des clés dans les données
                    row = {k.strip().lstrip('\ufeff'): v for k, v in raw_row.items()}
                    if i < 5:
                        result['sample_data'].append(row)
                    result['row_count'] += 1

            # Proposer le mapping
            for col in result['columns']:
                if col in DEFAULT_CSV_MAPPING:
                    result['suggested_mapping'][col] = DEFAULT_CSV_MAPPING[col]
                else:
                    # Essayer des variations (case insensitive)
                    col_lower = col.lower().strip()
                    matched = False
                    for csv_col, db_field in DEFAULT_CSV_MAPPING.items():
                        if csv_col.lower() == col_lower:
                            result['suggested_mapping'][col] = db_field
                            matched = True
                            break
                    if not matched:
                        result['unmapped'].append(col)

        except Exception as e:
            logger.error(f"Erreur détection colonnes: {e}")
            raise

        return result

    def import_file(
        self,
        file_path: str,
        mapping: Dict[str, str] = None,
        source_name: str = None,
        preview_only: bool = False,
        create_companies: bool = True,
        smart_matching: bool = True,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Importe un fichier CSV.

        Args:
            file_path: Chemin du fichier CSV
            mapping: Mapping personnalisé {'CSV_col': 'table.field'}
            source_name: Nom de la source pour tracking
            preview_only: Si True, ne fait que l'aperçu sans import
            create_companies: Si True, crée les entreprises manquantes
            smart_matching: Si True, utilise le matching intelligent
            progress_callback: Callback(current, total) pour progression

        Returns:
            Rapport d'import
        """
        report = {
            'success': True,
            'file': Path(file_path).name,
            'source': source_name or Path(file_path).stem,
            'started_at': datetime.now().isoformat(),
            'companies': {'created': 0, 'updated': 0, 'matched': 0},
            'contacts': {'created': 0, 'updated': 0, 'matched': 0},
            'rows_processed': 0,
            'rows_skipped': 0,
            'errors': [],
            'preview_only': preview_only
        }

        if not self.company_manager or not self.contact_manager:
            report['success'] = False
            report['errors'].append("Managers non initialisés")
            return report

        # Utiliser mapping par défaut si non fourni
        if mapping is None:
            detection = self.detect_columns(file_path)
            mapping = detection['suggested_mapping']

        try:
            encoding = self._detect_encoding(file_path)
            delimiter = self._detect_delimiter(file_path, encoding)

            # Compter total pour progress
            total_rows = sum(1 for _ in open(file_path, 'r', encoding=encoding, errors='replace')) - 1

            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                reader = csv.DictReader(f, delimiter=delimiter)

                for row_num, raw_row in enumerate(reader, start=2):  # Start at 2 (header = 1)
                    # Nettoyer BOM et espaces des clés
                    row = {k.strip().lstrip('\ufeff'): v for k, v in raw_row.items()}
                    try:
                        if progress_callback:
                            progress_callback(row_num - 1, total_rows)

                        result = self._process_row(
                            row, mapping, report['source'],
                            create_companies, smart_matching, preview_only
                        )

                        # Agréger les résultats
                        for entity in ['companies', 'contacts']:
                            for action in ['created', 'updated', 'matched']:
                                report[entity][action] += result.get(entity, {}).get(action, 0)

                        report['rows_processed'] += 1

                    except Exception as e:
                        report['errors'].append(f"Ligne {row_num}: {str(e)}")
                        report['rows_skipped'] += 1

                        # Limiter le nombre d'erreurs stockées
                        if len(report['errors']) > 100:
                            report['errors'].append("... (erreurs tronquées)")
                            break

        except Exception as e:
            report['success'] = False
            report['errors'].append(f"Erreur lecture fichier: {str(e)}")
            logger.error(f"Erreur import CSV: {e}")

        report['finished_at'] = datetime.now().isoformat()
        return report

    def _process_row(
        self,
        row: Dict[str, str],
        mapping: Dict[str, str],
        source: str,
        create_companies: bool,
        smart_matching: bool,
        preview_only: bool
    ) -> Dict[str, Dict[str, int]]:
        """Traite une ligne CSV."""
        result = {
            'companies': {'created': 0, 'updated': 0, 'matched': 0},
            'contacts': {'created': 0, 'updated': 0, 'matched': 0}
        }

        # Extraire les données selon le mapping
        company_data = {}
        contact_data = {}

        for csv_col, db_field in mapping.items():
            value = row.get(csv_col, '').strip()
            if not value:
                continue

            if db_field.startswith('companies.'):
                field_name = db_field.replace('companies.', '')
                company_data[field_name] = self._clean_value(value, field_name)
            elif db_field.startswith('contacts.'):
                field_name = db_field.replace('contacts.', '')
                contact_data[field_name] = self._clean_value(value, field_name)

        if preview_only:
            # En mode preview, on simule juste
            if company_data.get('name'):
                result['companies']['created'] = 1
            if contact_data.get('email') or contact_data.get('linkedin_url') or contact_data.get('firstname'):
                result['contacts']['created'] = 1
            return result

        # Importer l'entreprise
        company_uuid = None
        if company_data.get('name') and create_companies:
            company_data['source_file'] = source

            if smart_matching:
                company_uuid, created = self.company_manager.find_or_create(
                    company_data, source='csv'
                )
                if created:
                    result['companies']['created'] = 1
                else:
                    result['companies']['matched'] = 1
                    result['companies']['updated'] = 1
            else:
                company_uuid = self.company_manager.create(company_data, source='csv')
                result['companies']['created'] = 1

        # Importer le contact
        if contact_data.get('email') or contact_data.get('linkedin_url') or \
           (contact_data.get('firstname') and contact_data.get('lastname')):
            contact_data['source_file'] = source

            if smart_matching:
                contact_uuid, created = self.contact_manager.find_or_create(
                    contact_data, company_uuid=company_uuid, source='csv'
                )
                if created:
                    result['contacts']['created'] = 1
                else:
                    result['contacts']['matched'] = 1
                    result['contacts']['updated'] = 1
            else:
                self.contact_manager.create(
                    contact_data, company_uuid=company_uuid, source='csv'
                )
                result['contacts']['created'] = 1

        return result

    def _clean_value(self, value: str, field_name: str) -> Any:
        """Nettoie une valeur selon le type de champ."""
        if not value:
            return None

        value = value.strip()

        # Champs numériques
        if field_name in ['revenue', 'investment_amount', 'size_exact']:
            # Extraire le nombre
            numbers = re.findall(r'[\d,.]+', value.replace(' ', ''))
            if numbers:
                try:
                    return float(numbers[0].replace(',', '.'))
                except ValueError:
                    return None
            return None

        # Champs date
        if field_name in ['founded_date', 'investment_date']:
            # Essayer différents formats
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y']:
                try:
                    return datetime.strptime(value, fmt).strftime('%Y-%m-%d')
                except ValueError:
                    continue
            return value  # Garder tel quel si pas de format reconnu

        # Champs email
        if 'email' in field_name:
            return value.lower().strip()

        # Champs URL
        if 'url' in field_name or field_name == 'domain':
            return self._normalize_url(value, field_name)

        # SIREN/SIRET
        if field_name in ['siren', 'siret']:
            return ''.join(c for c in value if c.isdigit())

        # Phone
        if field_name in ['phone', 'mobile']:
            return self._normalize_phone(value)

        return value

    def _normalize_url(self, url: str, field_name: str) -> str:
        """Normalise une URL."""
        if not url:
            return ''

        url = url.lower().strip()

        # Retirer protocole
        for prefix in ['https://', 'http://']:
            if url.startswith(prefix):
                url = url[len(prefix):]

        # Retirer www.
        if url.startswith('www.'):
            url = url[4:]

        # Retirer trailing slash
        url = url.rstrip('/')

        # Pour les domaines, garder juste le domaine
        if field_name == 'domain':
            url = url.split('/')[0]

        return url

    def _normalize_phone(self, phone: str) -> str:
        """Normalise un numéro de téléphone."""
        if not phone:
            return ''

        # Garder que les chiffres et +
        digits = ''.join(c for c in phone if c.isdigit())

        # Gestion +33 / 0
        if digits.startswith('33') and len(digits) >= 11:
            digits = '0' + digits[2:]

        return digits

    def _detect_encoding(self, file_path: str) -> str:
        """Détecte l'encodage du fichier."""
        encodings_to_try = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']

        for encoding in encodings_to_try:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    f.read(10000)
                return encoding
            except (UnicodeDecodeError, UnicodeError):
                continue

        return 'utf-8'  # Default

    def _detect_delimiter(self, file_path: str, encoding: str = 'utf-8') -> str:
        """Détecte le délimiteur CSV."""
        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            sample = f.read(5000)

        # Compter les occurrences de délimiteurs potentiels
        delimiters = {',': 0, ';': 0, '\t': 0, '|': 0}
        for d in delimiters:
            delimiters[d] = sample.count(d)

        # Retourner le plus fréquent
        return max(delimiters, key=delimiters.get)

    def get_available_db_fields(self) -> Dict[str, List[str]]:
        """Retourne la liste des champs DB disponibles pour le mapping."""
        return DB_FIELDS.copy()

    def validate_mapping(self, mapping: Dict[str, str]) -> List[str]:
        """
        Valide un mapping.

        Returns:
            Liste d'erreurs (vide si valide)
        """
        errors = []

        for csv_col, db_field in mapping.items():
            if '.' not in db_field:
                errors.append(f"'{db_field}' doit être au format 'table.field'")
                continue

            table, field = db_field.split('.', 1)
            if table not in DB_FIELDS:
                errors.append(f"Table '{table}' inconnue")
            elif field not in DB_FIELDS.get(table, []):
                errors.append(f"Champ '{field}' inconnu dans '{table}'")

        return errors

    def analyze_preview(
        self,
        file_path: str,
        mapping: Dict[str, str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Analyse un fichier CSV et prédit les résultats d'import.

        Returns:
            {
                'rows': [...],  # Données avec prédiction de matching
                'stats': {
                    'total': 100,
                    'new_companies': 45,
                    'existing_companies': 55,
                    'new_contacts': 60,
                    'existing_contacts': 40
                }
            }
        """
        if not self.company_manager or not self.contact_manager:
            return {'error': 'Managers non initialisés'}

        if mapping is None:
            detection = self.detect_columns(file_path)
            mapping = detection['suggested_mapping']

        encoding = self._detect_encoding(file_path)
        delimiter = self._detect_delimiter(file_path, encoding)

        rows = []
        stats = {
            'total': 0,
            'new_companies': 0,
            'existing_companies': 0,
            'new_contacts': 0,
            'existing_contacts': 0
        }

        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            reader = csv.DictReader(f, delimiter=delimiter)

            for i, row in enumerate(reader):
                if i >= limit:
                    break

                stats['total'] += 1

                # Extraire données
                company_data = {}
                contact_data = {}

                for csv_col, db_field in mapping.items():
                    value = row.get(csv_col, '').strip()
                    if not value:
                        continue

                    if db_field.startswith('companies.'):
                        field_name = db_field.replace('companies.', '')
                        company_data[field_name] = self._clean_value(value, field_name)
                    elif db_field.startswith('contacts.'):
                        field_name = db_field.replace('contacts.', '')
                        contact_data[field_name] = self._clean_value(value, field_name)

                # Chercher matching
                row_result = {
                    'row_num': i + 2,
                    'company_data': company_data,
                    'contact_data': contact_data,
                    'company_match': None,
                    'contact_match': None,
                    'action': 'create'
                }

                if company_data.get('name'):
                    existing = self.company_manager.find_existing(company_data)
                    if existing:
                        row_result['company_match'] = {
                            'uuid': existing['uuid'],
                            'name': existing['name']
                        }
                        stats['existing_companies'] += 1
                    else:
                        stats['new_companies'] += 1

                if contact_data.get('email') or contact_data.get('linkedin_url'):
                    existing = self.contact_manager.find_existing(contact_data)
                    if existing:
                        row_result['contact_match'] = {
                            'uuid': existing['uuid'],
                            'name': f"{existing.get('firstname', '')} {existing.get('lastname', '')}".strip()
                        }
                        stats['existing_contacts'] += 1
                        row_result['action'] = 'update'
                    else:
                        stats['new_contacts'] += 1

                rows.append(row_result)

        return {'rows': rows, 'stats': stats}
