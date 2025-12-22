"""
HubSpot Sync V2 - Synchronisation one-way Local → HubSpot (Schema V2).

Pipeline: Import → Clean → Enrich → Sync

Usage:
    sync = HubSpotSyncV2(company_manager, contact_manager)

    # Analyser avant sync
    preview = sync.analyze()

    # Synchroniser
    report = sync.sync_all()
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None

logger = logging.getLogger(__name__)


class HubSpotSyncV2:
    """
    Synchronisation one-way Local → HubSpot - Schema V2.

    Direction: Local (SQLite) → HubSpot
    - Matching pour éviter doublons
    - Companies d'abord, puis Contacts
    - Associations Contact → Company
    """

    HUBSPOT_BASE_URL = "https://api.hubapi.com"
    BATCH_SIZE = 100

    # Mapping Local → HubSpot (Companies)
    COMPANY_MAPPING = {
        'name': 'name',
        'domain': 'domain',
        'siren': 'siren',
        'siret': 'siret',
        'hq_address': 'address',
        'hq_city': 'city',
        'hq_postal_code': 'zip',
        'hq_country': 'country',
        'hq_state': 'state',
        'industry': 'industry',
        'description': 'description',
        'size': 'numberofemployees',
        'revenue': 'annualrevenue',
        'ape_code': 'code_ape',
        'founded_date': 'founded_year',
        'technology_used': 'hs_tech_stack',
    }

    # Mapping Local → HubSpot (Contacts)
    CONTACT_MAPPING = {
        'firstname': 'firstname',
        'lastname': 'lastname',
        'email': 'email',
        'phone': 'phone',
        'mobile': 'mobilephone',
        'job_title': 'jobtitle',
        'linkedin_url': 'hs_linkedinid',
        'city': 'city',
        'country': 'country',
        'twitter_url': 'twitterhandle',
        'getsales_uuid': 'getsales_uuid',
    }

    def __init__(
        self,
        company_manager=None,
        contact_manager=None,
        api_key: str = None
    ):
        """
        Args:
            company_manager: Instance de CompanyManagerV2
            contact_manager: Instance de ContactManagerV2
            api_key: Clé API HubSpot (ou depuis HUBSPOT_API_KEY)
        """
        self.company_manager = company_manager
        self.contact_manager = contact_manager
        self.api_key = api_key or os.environ.get('HUBSPOT_API_KEY')
        self._client = None

    def _get_headers(self) -> Dict[str, str]:
        """Retourne les headers pour l'API HubSpot."""
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def _get_client(self):
        """Retourne un client HTTP."""
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx non installé. Installez avec: pip install httpx")
        if not self._client:
            self._client = httpx.Client(timeout=30.0)
        return self._client

    def is_connected(self) -> bool:
        """Vérifie la connexion à HubSpot."""
        if not self.api_key:
            return False

        try:
            response = self._get_client().get(
                f"{self.HUBSPOT_BASE_URL}/crm/v3/objects/contacts",
                headers=self._get_headers(),
                params={'limit': 1}
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Erreur connexion HubSpot: {e}")
            return False

    # =========================================================================
    # ANALYSE
    # =========================================================================

    def analyze(self, limit: int = 1000) -> Dict[str, Any]:
        """
        Analyse les données à synchroniser.

        Returns:
            {
                'companies': {
                    'to_create': 45,
                    'to_update': 23,
                    'up_to_date': 12
                },
                'contacts': {
                    'to_create': 123,
                    'to_update': 56,
                    'up_to_date': 34
                }
            }
        """
        result = {
            'companies': {'to_create': 0, 'to_update': 0, 'up_to_date': 0, 'details': []},
            'contacts': {'to_create': 0, 'to_update': 0, 'up_to_date': 0, 'details': []}
        }

        if not self.api_key:
            result['error'] = 'API key non configurée'
            return result

        # Analyser les entreprises
        if self.company_manager:
            companies = self.company_manager.list_all(status='active', limit=limit)
            for company in companies:
                action, hs_id = self._analyze_company(company)
                result['companies'][action] += 1
                if action != 'up_to_date':
                    result['companies']['details'].append({
                        'uuid': company['uuid'],
                        'name': company.get('name'),
                        'action': action,
                        'hubspot_id': hs_id
                    })

        # Analyser les contacts
        if self.contact_manager:
            contacts = self.contact_manager.list_all(status='active', limit=limit)
            for contact in contacts:
                action, hs_id = self._analyze_contact(contact)
                result['contacts'][action] += 1
                if action != 'up_to_date':
                    name = f"{contact.get('firstname', '')} {contact.get('lastname', '')}".strip()
                    result['contacts']['details'].append({
                        'uuid': contact['uuid'],
                        'name': name or contact.get('email'),
                        'action': action,
                        'hubspot_id': hs_id
                    })

        return result

    def _analyze_company(self, company: Dict[str, Any]) -> tuple:
        """
        Analyse une entreprise.

        Returns:
            (action, hubspot_id) - action: 'to_create', 'to_update', 'up_to_date'
        """
        # Déjà synced et pas modifié
        if company.get('synced_to_hubspot') and company.get('hubspot_company_id'):
            # Vérifier si modifié depuis dernier sync
            last_sync = company.get('last_sync_hubspot')
            updated_at = company.get('updated_at')
            if last_sync and updated_at:
                if str(updated_at) <= str(last_sync):
                    return ('up_to_date', company.get('hubspot_company_id'))

        # Chercher dans HubSpot
        hs_company = self._find_hubspot_company(company)

        if hs_company:
            return ('to_update', hs_company.get('id'))
        else:
            return ('to_create', None)

    def _analyze_contact(self, contact: Dict[str, Any]) -> tuple:
        """Analyse un contact."""
        if contact.get('synced_to_hubspot') and contact.get('hubspot_contact_id'):
            last_sync = contact.get('last_sync_hubspot')
            updated_at = contact.get('updated_at')
            if last_sync and updated_at:
                if str(updated_at) <= str(last_sync):
                    return ('up_to_date', contact.get('hubspot_contact_id'))

        hs_contact = self._find_hubspot_contact(contact)

        if hs_contact:
            return ('to_update', hs_contact.get('id'))
        else:
            return ('to_create', None)

    # =========================================================================
    # RECHERCHE HUBSPOT
    # =========================================================================

    def _find_hubspot_company(self, company: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Recherche une entreprise dans HubSpot.

        Ordre de matching:
        1. hubspot_company_id
        2. domain
        3. name (si unique)
        """
        # 1. Par ID
        if company.get('hubspot_company_id'):
            hs = self._get_company_by_id(company['hubspot_company_id'])
            if hs:
                return hs

        # 2. Par domain
        if company.get('domain'):
            hs = self._search_company_by_domain(company['domain'])
            if hs:
                return hs

        # 3. Par name
        if company.get('name'):
            hs = self._search_company_by_name(company['name'])
            if hs:
                return hs

        return None

    def _find_hubspot_contact(self, contact: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Recherche un contact dans HubSpot.

        Ordre de matching:
        1. hubspot_contact_id
        2. email
        """
        # 1. Par ID
        if contact.get('hubspot_contact_id'):
            hs = self._get_contact_by_id(contact['hubspot_contact_id'])
            if hs:
                return hs

        # 2. Par email
        if contact.get('email'):
            hs = self._search_contact_by_email(contact['email'])
            if hs:
                return hs

        return None

    def _get_company_by_id(self, company_id: str) -> Optional[Dict[str, Any]]:
        """Récupère une entreprise par ID HubSpot."""
        try:
            response = self._get_client().get(
                f"{self.HUBSPOT_BASE_URL}/crm/v3/objects/companies/{company_id}",
                headers=self._get_headers()
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Erreur get company {company_id}: {e}")
        return None

    def _get_contact_by_id(self, contact_id: str) -> Optional[Dict[str, Any]]:
        """Récupère un contact par ID HubSpot."""
        try:
            response = self._get_client().get(
                f"{self.HUBSPOT_BASE_URL}/crm/v3/objects/contacts/{contact_id}",
                headers=self._get_headers()
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Erreur get contact {contact_id}: {e}")
        return None

    def _search_company_by_domain(self, domain: str) -> Optional[Dict[str, Any]]:
        """Recherche une entreprise par domain."""
        try:
            response = self._get_client().post(
                f"{self.HUBSPOT_BASE_URL}/crm/v3/objects/companies/search",
                headers=self._get_headers(),
                json={
                    'filterGroups': [{
                        'filters': [{
                            'propertyName': 'domain',
                            'operator': 'EQ',
                            'value': domain
                        }]
                    }],
                    'limit': 1
                }
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('results'):
                    return data['results'][0]
        except Exception as e:
            logger.error(f"Erreur search company by domain: {e}")
        return None

    def _search_company_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Recherche une entreprise par nom."""
        try:
            response = self._get_client().post(
                f"{self.HUBSPOT_BASE_URL}/crm/v3/objects/companies/search",
                headers=self._get_headers(),
                json={
                    'filterGroups': [{
                        'filters': [{
                            'propertyName': 'name',
                            'operator': 'EQ',
                            'value': name
                        }]
                    }],
                    'limit': 1
                }
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('results'):
                    return data['results'][0]
        except Exception as e:
            logger.error(f"Erreur search company by name: {e}")
        return None

    def _search_contact_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Recherche un contact par email."""
        try:
            response = self._get_client().post(
                f"{self.HUBSPOT_BASE_URL}/crm/v3/objects/contacts/search",
                headers=self._get_headers(),
                json={
                    'filterGroups': [{
                        'filters': [{
                            'propertyName': 'email',
                            'operator': 'EQ',
                            'value': email
                        }]
                    }],
                    'limit': 1
                }
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('results'):
                    return data['results'][0]
        except Exception as e:
            logger.error(f"Erreur search contact by email: {e}")
        return None

    # =========================================================================
    # SYNCHRONISATION
    # =========================================================================

    def sync_all(
        self,
        companies: bool = True,
        contacts: bool = True,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Synchronise toutes les données vers HubSpot.

        Args:
            companies: Synchroniser les entreprises
            contacts: Synchroniser les contacts
            progress_callback: Callback(current, total, entity_type)

        Returns:
            Rapport de synchronisation
        """
        report = {
            'success': True,
            'started_at': datetime.now().isoformat(),
            'companies': {'created': 0, 'updated': 0, 'errors': []},
            'contacts': {'created': 0, 'updated': 0, 'errors': []},
            'associations': {'created': 0, 'errors': []}
        }

        if not self.api_key:
            report['success'] = False
            report['error'] = 'API key non configurée'
            return report

        # 1. Sync companies
        if companies and self.company_manager:
            company_list = self.company_manager.list_all(status='active', limit=10000)
            total = len(company_list)

            for i, company in enumerate(company_list):
                if progress_callback:
                    progress_callback(i + 1, total, 'companies')

                try:
                    result = self._sync_company(company)
                    if result.get('created'):
                        report['companies']['created'] += 1
                    elif result.get('updated'):
                        report['companies']['updated'] += 1
                except Exception as e:
                    report['companies']['errors'].append(
                        f"{company.get('name', 'Unknown')}: {str(e)}"
                    )

        # 2. Sync contacts
        if contacts and self.contact_manager:
            contact_list = self.contact_manager.list_all(status='active', limit=10000)
            total = len(contact_list)

            for i, contact in enumerate(contact_list):
                if progress_callback:
                    progress_callback(i + 1, total, 'contacts')

                try:
                    result = self._sync_contact(contact)
                    if result.get('created'):
                        report['contacts']['created'] += 1
                    elif result.get('updated'):
                        report['contacts']['updated'] += 1

                    # Association
                    if result.get('hubspot_id') and contact.get('company_uuid'):
                        assoc_result = self._create_association(
                            contact['company_uuid'],
                            result['hubspot_id']
                        )
                        if assoc_result:
                            report['associations']['created'] += 1
                except Exception as e:
                    name = f"{contact.get('firstname', '')} {contact.get('lastname', '')}".strip()
                    report['contacts']['errors'].append(f"{name}: {str(e)}")

        report['finished_at'] = datetime.now().isoformat()
        return report

    def _sync_company(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronise une entreprise."""
        result = {'created': False, 'updated': False, 'hubspot_id': None}

        # Préparer les propriétés
        properties = self._map_company_properties(company)

        # Chercher existant
        hs_company = self._find_hubspot_company(company)

        if hs_company:
            # Update
            hs_id = hs_company['id']
            response = self._get_client().patch(
                f"{self.HUBSPOT_BASE_URL}/crm/v3/objects/companies/{hs_id}",
                headers=self._get_headers(),
                json={'properties': properties}
            )
            if response.status_code == 200:
                result['updated'] = True
                result['hubspot_id'] = hs_id
        else:
            # Create
            response = self._get_client().post(
                f"{self.HUBSPOT_BASE_URL}/crm/v3/objects/companies",
                headers=self._get_headers(),
                json={'properties': properties}
            )
            if response.status_code == 201:
                data = response.json()
                result['created'] = True
                result['hubspot_id'] = data.get('id')

        # Mettre à jour local
        if result['hubspot_id']:
            self.company_manager.update(company['uuid'], {
                'hubspot_company_id': result['hubspot_id'],
                'synced_to_hubspot': 1,
                'last_sync_hubspot': datetime.now()
            })

        return result

    def _sync_contact(self, contact: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronise un contact."""
        result = {'created': False, 'updated': False, 'hubspot_id': None}

        properties = self._map_contact_properties(contact)

        hs_contact = self._find_hubspot_contact(contact)

        if hs_contact:
            hs_id = hs_contact['id']
            response = self._get_client().patch(
                f"{self.HUBSPOT_BASE_URL}/crm/v3/objects/contacts/{hs_id}",
                headers=self._get_headers(),
                json={'properties': properties}
            )
            if response.status_code == 200:
                result['updated'] = True
                result['hubspot_id'] = hs_id
        else:
            response = self._get_client().post(
                f"{self.HUBSPOT_BASE_URL}/crm/v3/objects/contacts",
                headers=self._get_headers(),
                json={'properties': properties}
            )
            if response.status_code == 201:
                data = response.json()
                result['created'] = True
                result['hubspot_id'] = data.get('id')

        if result['hubspot_id']:
            self.contact_manager.update(contact['uuid'], {
                'hubspot_contact_id': result['hubspot_id'],
                'synced_to_hubspot': 1,
                'last_sync_hubspot': datetime.now()
            })

        return result

    def _create_association(self, company_uuid: str, contact_hubspot_id: str) -> bool:
        """Crée une association Contact → Company dans HubSpot."""
        # Récupérer le hubspot_company_id
        company = self.company_manager.get(company_uuid)
        if not company or not company.get('hubspot_company_id'):
            return False

        company_hs_id = company['hubspot_company_id']

        try:
            response = self._get_client().put(
                f"{self.HUBSPOT_BASE_URL}/crm/v3/objects/contacts/{contact_hubspot_id}/associations/companies/{company_hs_id}/contact_to_company",
                headers=self._get_headers()
            )
            return response.status_code in [200, 201]
        except Exception as e:
            logger.error(f"Erreur association: {e}")
            return False

    def _map_company_properties(self, company: Dict[str, Any]) -> Dict[str, str]:
        """Mappe les propriétés locales vers HubSpot."""
        properties = {}

        for local_field, hs_field in self.COMPANY_MAPPING.items():
            value = company.get(local_field)
            if value:
                properties[hs_field] = str(value)

        return properties

    def _map_contact_properties(self, contact: Dict[str, Any]) -> Dict[str, str]:
        """Mappe les propriétés locales vers HubSpot."""
        properties = {}

        for local_field, hs_field in self.CONTACT_MAPPING.items():
            value = contact.get(local_field)
            if value:
                properties[hs_field] = str(value)

        return properties

    # =========================================================================
    # UTILITAIRES
    # =========================================================================

    def get_sync_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de synchronisation."""
        stats = {
            'companies': {
                'total': 0,
                'synced': 0,
                'not_synced': 0
            },
            'contacts': {
                'total': 0,
                'synced': 0,
                'not_synced': 0
            }
        }

        if self.company_manager:
            companies = self.company_manager.list_all(limit=10000)
            stats['companies']['total'] = len(companies)
            stats['companies']['synced'] = sum(
                1 for c in companies if c.get('synced_to_hubspot')
            )
            stats['companies']['not_synced'] = (
                stats['companies']['total'] - stats['companies']['synced']
            )

        if self.contact_manager:
            contacts = self.contact_manager.list_all(limit=10000)
            stats['contacts']['total'] = len(contacts)
            stats['contacts']['synced'] = sum(
                1 for c in contacts if c.get('synced_to_hubspot')
            )
            stats['contacts']['not_synced'] = (
                stats['contacts']['total'] - stats['contacts']['synced']
            )

        return stats

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            self._client.close()
