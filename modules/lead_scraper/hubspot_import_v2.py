"""
HubSpot Import V2 - Import depuis HubSpot vers base locale.

Pipeline: HubSpot → Local (companies, contacts, interactions)

Usage:
    importer = HubSpotImportV2(company_manager, contact_manager, engagement_manager, api_key)

    # Import complet
    report = importer.import_all()

    # Import partiel
    report = importer.import_companies(limit=100)
    report = importer.import_contacts(limit=100)
    report = importer.import_engagements(limit=100)
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None

logger = logging.getLogger(__name__)


class HubSpotImportV2:
    """
    Import HubSpot → Local - Schema V2.

    Importe:
    - Companies → table companies
    - Contacts → table contacts
    - Engagements → table interactions

    Conserve les IDs HubSpot pour sync bidirectionnel.
    """

    BASE_URL = "https://api.hubapi.com"

    def __init__(
        self,
        company_manager=None,
        contact_manager=None,
        engagement_manager=None,
        api_key: str = None
    ):
        self.company_manager = company_manager
        self.contact_manager = contact_manager
        self.engagement_manager = engagement_manager
        self.api_key = api_key or os.environ.get('HUBSPOT_API_KEY')
        self._client = None

    def _get_client(self):
        """Retourne un client HTTP."""
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx non installé. Installez avec: pip install httpx")
        if not self._client:
            self._client = httpx.Client(timeout=30.0)
        return self._client

    def _get_headers(self) -> Dict[str, str]:
        """Headers pour l'API HubSpot."""
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def is_connected(self) -> bool:
        """Vérifie la connexion à HubSpot."""
        if not self.api_key:
            return False
        try:
            response = self._get_client().get(
                f"{self.BASE_URL}/crm/v3/objects/contacts",
                headers=self._get_headers(),
                params={'limit': 1}
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Erreur connexion HubSpot: {e}")
            return False

    # =========================================================================
    # IMPORT COMPANIES
    # =========================================================================

    def import_companies(
        self,
        limit: int = None,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Importe les companies depuis HubSpot.

        Args:
            limit: Nombre max de companies (None = toutes)
            progress_callback: Callback(current, total)

        Returns:
            Rapport d'import
        """
        report = {
            'success': True,
            'created': 0,
            'updated': 0,
            'matched': 0,
            'errors': [],
            'total_fetched': 0
        }

        if not self.company_manager:
            report['success'] = False
            report['errors'].append('CompanyManager non initialisé')
            return report

        try:
            # Récupérer les companies depuis HubSpot
            companies = self._fetch_all_companies(limit)
            report['total_fetched'] = len(companies)

            for i, hs_company in enumerate(companies):
                if progress_callback:
                    progress_callback(i + 1, len(companies))

                try:
                    result = self._import_company(hs_company)
                    if result == 'created':
                        report['created'] += 1
                    elif result == 'updated':
                        report['updated'] += 1
                    else:
                        report['matched'] += 1
                except Exception as e:
                    report['errors'].append(f"Company {hs_company.get('id')}: {e}")

        except Exception as e:
            report['success'] = False
            report['errors'].append(str(e))

        return report

    def _fetch_all_companies(self, limit: int = None) -> List[Dict]:
        """Récupère toutes les companies depuis HubSpot avec pagination."""
        companies = []
        after = None
        page_size = min(100, limit) if limit else 100

        properties = [
            'name', 'domain', 'phone', 'industry', 'numberofemployees',
            'annualrevenue', 'city', 'state', 'country', 'zip',
            'address', 'description', 'founded_year', 'hs_object_id'
        ]

        while True:
            params = {
                'limit': page_size,
                'properties': ','.join(properties)
            }
            if after:
                params['after'] = after

            response = self._get_client().get(
                f"{self.BASE_URL}/crm/v3/objects/companies",
                headers=self._get_headers(),
                params=params
            )

            if response.status_code != 200:
                logger.error(f"Erreur API HubSpot: {response.status_code}")
                break

            data = response.json()
            results = data.get('results', [])
            companies.extend(results)

            if limit and len(companies) >= limit:
                companies = companies[:limit]
                break

            paging = data.get('paging', {})
            next_page = paging.get('next', {})
            after = next_page.get('after')

            if not after:
                break

        return companies

    def _import_company(self, hs_company: Dict) -> str:
        """
        Importe une company HubSpot.

        Returns:
            'created', 'updated', ou 'matched'
        """
        hs_id = str(hs_company.get('id'))
        props = hs_company.get('properties', {})

        # Mapper les données
        company_data = {
            'hubspot_company_id': hs_id,
            'name': props.get('name'),
            'domain': props.get('domain'),
            'industry': props.get('industry'),
            'description': props.get('description'),
            'hq_address': props.get('address'),
            'hq_city': props.get('city'),
            'hq_state': props.get('state'),
            'hq_postal_code': props.get('zip'),
            'hq_country': props.get('country') or 'France',
        }

        # Taille
        employees = props.get('numberofemployees')
        if employees:
            company_data['size'] = self._map_employee_count(employees)

        # Revenue
        revenue = props.get('annualrevenue')
        if revenue:
            try:
                company_data['revenue'] = float(revenue)
            except:
                pass

        # Chercher existant par hubspot_id
        existing = self.company_manager.find_by_hubspot_id(hs_id)

        if existing:
            # Mettre à jour uniquement les champs vides
            updates = {}
            for key, value in company_data.items():
                if value and not existing.get(key):
                    updates[key] = value

            if updates:
                self.company_manager.update(existing['uuid'], updates)
                return 'updated'
            return 'matched'

        # Chercher par domain ou SIREN
        if company_data.get('domain'):
            existing = self.company_manager.find_by_domain(company_data['domain'])
            if existing:
                # Lier et mettre à jour
                self.company_manager.update(existing['uuid'], {
                    'hubspot_company_id': hs_id,
                    'synced_to_hubspot': 1,
                    'last_sync_hubspot': datetime.now()
                })
                return 'matched'

        # Créer nouvelle company
        company_data['synced_to_hubspot'] = 1
        company_data['last_sync_hubspot'] = datetime.now()

        self.company_manager.create(company_data, source='hubspot')
        return 'created'

    def _map_employee_count(self, count: str) -> str:
        """Mappe le nombre d'employés vers les tranches."""
        try:
            n = int(count)
            if n <= 10:
                return '1-10'
            elif n <= 50:
                return '11-50'
            elif n <= 200:
                return '51-200'
            elif n <= 500:
                return '201-500'
            elif n <= 1000:
                return '501-1000'
            elif n <= 5000:
                return '1001-5000'
            elif n <= 10000:
                return '5001-10000'
            else:
                return '10001+'
        except:
            return count

    # =========================================================================
    # IMPORT CONTACTS
    # =========================================================================

    def import_contacts(
        self,
        limit: int = None,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Importe les contacts depuis HubSpot.
        """
        report = {
            'success': True,
            'created': 0,
            'updated': 0,
            'matched': 0,
            'errors': [],
            'total_fetched': 0
        }

        if not self.contact_manager:
            report['success'] = False
            report['errors'].append('ContactManager non initialisé')
            return report

        try:
            contacts = self._fetch_all_contacts(limit)
            report['total_fetched'] = len(contacts)

            for i, hs_contact in enumerate(contacts):
                if progress_callback:
                    progress_callback(i + 1, len(contacts))

                try:
                    result = self._import_contact(hs_contact)
                    if result == 'created':
                        report['created'] += 1
                    elif result == 'updated':
                        report['updated'] += 1
                    else:
                        report['matched'] += 1
                except Exception as e:
                    report['errors'].append(f"Contact {hs_contact.get('id')}: {e}")

        except Exception as e:
            report['success'] = False
            report['errors'].append(str(e))

        return report

    def _fetch_all_contacts(self, limit: int = None) -> List[Dict]:
        """Récupère tous les contacts depuis HubSpot avec pagination."""
        contacts = []
        after = None
        page_size = min(100, limit) if limit else 100

        properties = [
            'firstname', 'lastname', 'email', 'phone', 'mobilephone',
            'jobtitle', 'linkedin_url', 'hs_linkedin_url',
            'city', 'state', 'country', 'associatedcompanyid'
        ]

        while True:
            params = {
                'limit': page_size,
                'properties': ','.join(properties)
            }
            if after:
                params['after'] = after

            response = self._get_client().get(
                f"{self.BASE_URL}/crm/v3/objects/contacts",
                headers=self._get_headers(),
                params=params
            )

            if response.status_code != 200:
                logger.error(f"Erreur API HubSpot: {response.status_code}")
                break

            data = response.json()
            results = data.get('results', [])
            contacts.extend(results)

            if limit and len(contacts) >= limit:
                contacts = contacts[:limit]
                break

            paging = data.get('paging', {})
            next_page = paging.get('next', {})
            after = next_page.get('after')

            if not after:
                break

        return contacts

    def _import_contact(self, hs_contact: Dict) -> str:
        """Importe un contact HubSpot."""
        hs_id = str(hs_contact.get('id'))
        props = hs_contact.get('properties', {})

        # Mapper les données
        contact_data = {
            'hubspot_contact_id': hs_id,
            'firstname': props.get('firstname'),
            'lastname': props.get('lastname'),
            'email': props.get('email'),
            'phone': props.get('phone'),
            'mobile': props.get('mobilephone'),
            'job_title': props.get('jobtitle'),
            'linkedin_url': props.get('linkedin_url') or props.get('hs_linkedin_url'),
            'city': props.get('city'),
            'state': props.get('state'),
            'country': props.get('country') or 'France',
        }

        # Trouver la company associée
        hs_company_id = props.get('associatedcompanyid')
        company_uuid = None
        if hs_company_id and self.company_manager:
            company = self.company_manager.find_by_hubspot_id(str(hs_company_id))
            if company:
                company_uuid = company['uuid']

        # Chercher existant par hubspot_id
        existing = self.contact_manager.find_by_hubspot_id(hs_id)

        if existing:
            updates = {}
            for key, value in contact_data.items():
                if value and not existing.get(key):
                    updates[key] = value
            if company_uuid and not existing.get('company_uuid'):
                updates['company_uuid'] = company_uuid

            if updates:
                self.contact_manager.update(existing['uuid'], updates)
                return 'updated'
            return 'matched'

        # Chercher par email
        if contact_data.get('email'):
            existing = self.contact_manager.find_by_email(contact_data['email'])
            if existing:
                self.contact_manager.update(existing['uuid'], {
                    'hubspot_contact_id': hs_id,
                    'synced_to_hubspot': 1,
                    'last_sync_hubspot': datetime.now()
                })
                return 'matched'

        # Créer nouveau contact
        contact_data['company_uuid'] = company_uuid
        contact_data['synced_to_hubspot'] = 1
        contact_data['last_sync_hubspot'] = datetime.now()

        self.contact_manager.create(contact_data, source='hubspot')
        return 'created'

    # =========================================================================
    # IMPORT ENGAGEMENTS → INTERACTIONS
    # =========================================================================

    def import_engagements(
        self,
        limit: int = None,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Importe les engagements HubSpot → interactions.

        Types: emails, calls, meetings, notes
        """
        report = {
            'success': True,
            'created': 0,
            'skipped': 0,
            'errors': [],
            'total_fetched': 0,
            'by_type': {}
        }

        if not self.engagement_manager:
            report['success'] = False
            report['errors'].append('EngagementManager non initialisé')
            return report

        engagement_types = ['emails', 'calls', 'meetings', 'notes']

        for eng_type in engagement_types:
            try:
                engagements = self._fetch_engagements(eng_type, limit)
                report['total_fetched'] += len(engagements)
                report['by_type'][eng_type] = 0

                for i, engagement in enumerate(engagements):
                    if progress_callback:
                        progress_callback(i + 1, len(engagements))

                    try:
                        created = self._import_engagement(engagement, eng_type)
                        if created:
                            report['created'] += 1
                            report['by_type'][eng_type] += 1
                        else:
                            report['skipped'] += 1
                    except Exception as e:
                        report['errors'].append(f"{eng_type} {engagement.get('id')}: {e}")

            except Exception as e:
                report['errors'].append(f"Erreur {eng_type}: {e}")

        return report

    def _fetch_engagements(self, eng_type: str, limit: int = None) -> List[Dict]:
        """Récupère les engagements d'un type."""
        engagements = []
        after = None
        page_size = min(100, limit) if limit else 100

        while True:
            params = {'limit': page_size}
            if after:
                params['after'] = after

            response = self._get_client().get(
                f"{self.BASE_URL}/crm/v3/objects/{eng_type}",
                headers=self._get_headers(),
                params=params
            )

            if response.status_code != 200:
                break

            data = response.json()
            results = data.get('results', [])
            engagements.extend(results)

            if limit and len(engagements) >= limit:
                engagements = engagements[:limit]
                break

            paging = data.get('paging', {})
            after = paging.get('next', {}).get('after')

            if not after:
                break

        return engagements

    def _import_engagement(self, engagement: Dict, eng_type: str) -> bool:
        """
        Importe un engagement → interaction.

        Returns:
            True si créé, False si skipped
        """
        hs_id = str(engagement.get('id'))
        props = engagement.get('properties', {})

        # Vérifier si déjà importé
        existing = self.engagement_manager.find_by_hubspot_id(hs_id)
        if existing:
            return False

        # Trouver le contact associé
        # Note: nécessite une requête supplémentaire pour les associations
        contact_uuid = self._find_contact_for_engagement(hs_id, eng_type)

        if not contact_uuid:
            return False  # Skip si pas de contact associé

        # Mapper le type
        type_mapping = {
            'emails': 'email',
            'calls': 'call',
            'meetings': 'meeting',
            'notes': 'note'
        }

        interaction_data = {
            'contact_uuid': contact_uuid,
            'hubspot_engagement_id': hs_id,
            'type': type_mapping.get(eng_type, eng_type),
            'source': 'hubspot',
            'interaction_date': props.get('hs_timestamp') or props.get('hs_createdate'),
        }

        # Contenu selon le type
        if eng_type == 'emails':
            interaction_data['subject'] = props.get('hs_email_subject')
            interaction_data['content'] = props.get('hs_email_text') or props.get('hs_email_html')
            interaction_data['direction'] = 'outbound' if props.get('hs_email_direction') == 'SENT' else 'inbound'
            interaction_data['channel'] = 'email'
        elif eng_type == 'calls':
            interaction_data['content'] = props.get('hs_call_body')
            interaction_data['duration_minutes'] = props.get('hs_call_duration')
            interaction_data['direction'] = props.get('hs_call_direction', 'outbound').lower()
            interaction_data['channel'] = 'phone'
        elif eng_type == 'meetings':
            interaction_data['subject'] = props.get('hs_meeting_title')
            interaction_data['content'] = props.get('hs_meeting_body')
            interaction_data['channel'] = 'in_person'
        elif eng_type == 'notes':
            interaction_data['content'] = props.get('hs_note_body')

        self.engagement_manager.create(interaction_data, source='hubspot')
        return True

    def _find_contact_for_engagement(self, engagement_id: str, eng_type: str) -> Optional[str]:
        """Trouve le contact associé à un engagement."""
        try:
            response = self._get_client().get(
                f"{self.BASE_URL}/crm/v4/objects/{eng_type}/{engagement_id}/associations/contacts",
                headers=self._get_headers()
            )

            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                if results:
                    hs_contact_id = str(results[0].get('toObjectId'))
                    contact = self.contact_manager.find_by_hubspot_id(hs_contact_id)
                    if contact:
                        return contact['uuid']
        except Exception as e:
            logger.debug(f"Erreur association engagement: {e}")

        return None

    # =========================================================================
    # IMPORT COMPLET
    # =========================================================================

    def import_all(
        self,
        companies: bool = True,
        contacts: bool = True,
        engagements: bool = True,
        limit: int = None,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Import complet depuis HubSpot.

        Args:
            companies: Importer les companies
            contacts: Importer les contacts
            engagements: Importer les engagements
            limit: Limite par type d'objet
            progress_callback: Callback(current, total, entity_type)
        """
        report = {
            'success': True,
            'companies': None,
            'contacts': None,
            'engagements': None,
            'started_at': datetime.now().isoformat()
        }

        def make_callback(entity_type):
            def cb(current, total):
                if progress_callback:
                    progress_callback(current, total, entity_type)
            return cb

        # 1. Companies d'abord (pour les associations)
        if companies:
            logger.info("Import companies...")
            report['companies'] = self.import_companies(
                limit=limit,
                progress_callback=make_callback('companies')
            )

        # 2. Contacts ensuite
        if contacts:
            logger.info("Import contacts...")
            report['contacts'] = self.import_contacts(
                limit=limit,
                progress_callback=make_callback('contacts')
            )

        # 3. Engagements en dernier
        if engagements:
            logger.info("Import engagements...")
            report['engagements'] = self.import_engagements(
                limit=limit,
                progress_callback=make_callback('engagements')
            )

        report['finished_at'] = datetime.now().isoformat()

        # Vérifier succès global
        for key in ['companies', 'contacts', 'engagements']:
            if report[key] and not report[key].get('success', True):
                report['success'] = False
                break

        return report

    def get_import_stats(self) -> Dict[str, Any]:
        """Retourne les stats d'import potentiel."""
        stats = {
            'hubspot_companies': 0,
            'hubspot_contacts': 0,
            'local_from_hubspot': 0,
            'to_import': 0
        }

        try:
            # Compter dans HubSpot
            response = self._get_client().get(
                f"{self.BASE_URL}/crm/v3/objects/companies",
                headers=self._get_headers(),
                params={'limit': 1}
            )
            if response.status_code == 200:
                data = response.json()
                stats['hubspot_companies'] = data.get('total', 0)

            response = self._get_client().get(
                f"{self.BASE_URL}/crm/v3/objects/contacts",
                headers=self._get_headers(),
                params={'limit': 1}
            )
            if response.status_code == 200:
                data = response.json()
                stats['hubspot_contacts'] = data.get('total', 0)

            # Compter local avec source hubspot
            if self.company_manager:
                companies = self.company_manager.list_all(source='hubspot', limit=10000)
                stats['local_from_hubspot'] = len(companies)

            stats['to_import'] = max(0, stats['hubspot_companies'] - stats['local_from_hubspot'])

        except Exception as e:
            logger.error(f"Erreur stats: {e}")

        return stats

    def close(self):
        """Ferme le client HTTP."""
        if self._client:
            self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
