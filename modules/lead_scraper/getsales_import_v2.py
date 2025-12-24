"""
Import GetSales vers Schema V2.

Adapte l'import GetSales pour utiliser:
- CompanyManagerV2 (companies)
- ContactManagerV2 (contacts)
- EngagementManager (interactions)
"""
import os
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable

logger = logging.getLogger(__name__)


class GetSalesImportV2:
    """
    Service d'import GetSales vers Schema V2.

    Importe les leads GetSales avec leurs messages LinkedIn
    dans la base V2 (companies, contacts, interactions).

    Usage:
        from modules.getsales import GetSalesClient

        getsales = GetSalesClient()
        importer = GetSalesImportV2(company_mgr, contact_mgr, interaction_mgr)

        report = importer.import_leads(getsales, limit=100)
    """

    def __init__(
        self,
        company_manager,
        contact_manager,
        engagement_manager,
        api_key: Optional[str] = None
    ):
        """
        Initialise l'importeur.

        Args:
            company_manager: CompanyManagerV2
            contact_manager: ContactManagerV2
            engagement_manager: EngagementManager
            api_key: Clé API GetSales (ou GETSALES_API_KEY)
        """
        self.company_manager = company_manager
        self.contact_manager = contact_manager
        self.engagement_manager = engagement_manager
        self.api_key = api_key or os.environ.get('GETSALES_API_KEY')
        self._getsales_client = None

    def _get_client(self):
        """Lazy loading du client GetSales."""
        if self._getsales_client is None:
            try:
                from modules.getsales.getsales_client import GetSalesClient
                self._getsales_client = GetSalesClient(self.api_key)
            except Exception as e:
                logger.error(f"Erreur initialisation GetSalesClient: {e}")
                raise
        return self._getsales_client

    def is_connected(self) -> bool:
        """Vérifie la connexion à l'API GetSales."""
        if not self.api_key:
            return False
        try:
            client = self._get_client()
            success, _ = client.test_connection()
            return success
        except Exception:
            return False

    def get_import_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques d'import.

        Returns:
            Dict avec stats locales et GetSales
        """
        stats = {
            'local_from_getsales': 0,
            'getsales_leads': '?',
            'getsales_flows': '?',
        }

        # Stats locales
        try:
            contacts = self.contact_manager.list_all(source='getsales', limit=10000)
            stats['local_from_getsales'] = len(contacts)
        except Exception:
            pass

        # Stats GetSales
        if self.is_connected():
            try:
                client = self._get_client()
                flows = client.fetch_flows()
                stats['getsales_flows'] = len(flows)
            except Exception:
                pass

        return stats

    def fetch_flows(self) -> List[Dict[str, Any]]:
        """
        Récupère la liste des campagnes/flows GetSales.

        Returns:
            Liste des flows avec uuid, name, status
        """
        client = self._get_client()
        return client.fetch_flows()

    def import_all(
        self,
        limit: int = 100,
        flow_uuid: Optional[str] = None,
        fetch_messages: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Import complet depuis GetSales.

        Args:
            limit: Nombre max de leads à importer
            flow_uuid: Filtrer par campagne/flow
            fetch_messages: Récupérer les messages LinkedIn
            progress_callback: Callback(current, total, entity_type)

        Returns:
            Rapport d'import
        """
        report = {
            'success': True,
            'leads_fetched': 0,
            'companies': {'created': 0, 'matched': 0},
            'contacts': {'created': 0, 'updated': 0, 'matched': 0},
            'interactions': {'created': 0},
            'errors': []
        }

        try:
            client = self._get_client()

            # 1. Fetch leads depuis GetSales
            filters = {}
            if flow_uuid:
                filters['flow_uuid'] = flow_uuid

            if progress_callback:
                progress_callback(0, limit, 'leads')

            if fetch_messages:
                leads = client.fetch_leads_with_messages(filters=filters, limit=limit)
            else:
                leads = client.fetch_leads(filters=filters, limit=limit)

            report['leads_fetched'] = len(leads)
            logger.info(f"GetSales: {len(leads)} leads récupérés")

            # 2. Importer chaque lead
            for i, lead in enumerate(leads):
                if progress_callback:
                    progress_callback(i + 1, len(leads), 'importing')

                try:
                    result = self._import_lead(lead, fetch_messages)

                    # Agréger les stats
                    if result.get('company_created'):
                        report['companies']['created'] += 1
                    elif result.get('company_matched'):
                        report['companies']['matched'] += 1

                    if result.get('contact_created'):
                        report['contacts']['created'] += 1
                    elif result.get('contact_updated'):
                        report['contacts']['updated'] += 1
                    elif result.get('contact_matched'):
                        report['contacts']['matched'] += 1

                    report['interactions']['created'] += result.get('interactions_created', 0)

                except Exception as e:
                    error_msg = f"Lead {lead.get('uuid', '?')}: {str(e)}"
                    report['errors'].append(error_msg)
                    logger.error(error_msg)

            if progress_callback:
                progress_callback(len(leads), len(leads), 'done')

        except Exception as e:
            report['success'] = False
            report['errors'].append(str(e))
            logger.error(f"Erreur import GetSales: {e}")

        return report

    def _import_lead(self, lead: Dict[str, Any], fetch_messages: bool = True) -> Dict[str, Any]:
        """
        Importe un lead GetSales en base V2.

        Args:
            lead: Données du lead GetSales
            fetch_messages: Si True, importe aussi les messages

        Returns:
            Résultat de l'import
        """
        result = {
            'company_created': False,
            'company_matched': False,
            'contact_created': False,
            'contact_updated': False,
            'contact_matched': False,
            'interactions_created': 0,
        }

        getsales_uuid = lead.get('uuid')
        if not getsales_uuid:
            raise ValueError("Lead sans UUID")

        # 1. Vérifier si contact déjà importé (par getsales_uuid)
        existing_contact = self._find_existing_contact(lead)

        # 2. Trouver ou créer l'entreprise
        company_uuid = None
        company_name = lead.get('company_name')

        if company_name:
            company_uuid, created = self._find_or_create_company(lead)
            if created:
                result['company_created'] = True
            else:
                result['company_matched'] = True

        # 3. Créer ou mettre à jour le contact
        contact_data = self._build_contact_data(lead, company_uuid)

        if existing_contact:
            # Mise à jour
            contact_uuid = existing_contact['uuid']
            self.contact_manager.update(contact_uuid, contact_data)
            result['contact_updated'] = True
        else:
            # Vérifier par email/linkedin
            matched = self._find_matching_contact(lead)
            if matched:
                contact_uuid = matched['uuid']
                self.contact_manager.update(contact_uuid, contact_data)
                result['contact_matched'] = True
            else:
                # Création
                contact_uuid = self.contact_manager.create(contact_data, source='getsales')
                result['contact_created'] = True

        # 4. Importer les messages/interactions
        if fetch_messages:
            messages = lead.get('_messages', [])
            for msg in messages:
                try:
                    self._import_interaction(contact_uuid, company_uuid, lead, msg)
                    result['interactions_created'] += 1
                except Exception as e:
                    logger.warning(f"Erreur import message: {e}")

        return result

    def _find_existing_contact(self, lead: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Cherche un contact existant par getsales_uuid."""
        getsales_uuid = lead.get('uuid')

        # Recherche par getsales_uuid dans les tags ou metadata
        contacts = self.contact_manager.list_all(source='getsales', limit=5000)

        for contact in contacts:
            # Vérifier si getsales_uuid stocké quelque part
            if contact.get('getsales_uuid') == getsales_uuid:
                return contact

            # Fallback: chercher dans tags ou notes
            tags = contact.get('tags', [])
            if isinstance(tags, list) and f"getsales:{getsales_uuid}" in tags:
                return contact

        return None

    def _find_matching_contact(self, lead: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Cherche un contact existant par email ou LinkedIn."""
        # Par email
        email = lead.get('email')
        if email:
            contact = self.contact_manager.find_by_email(email)
            if contact:
                return contact

        # Par LinkedIn
        linkedin = lead.get('linkedin')
        if linkedin:
            # Normaliser l'URL
            if not linkedin.startswith('http'):
                linkedin = f"https://linkedin.com/in/{linkedin}"
            contact = self.contact_manager.find_by_linkedin(linkedin)
            if contact:
                return contact

        return None

    def _find_or_create_company(self, lead: Dict[str, Any]) -> tuple:
        """
        Trouve ou crée l'entreprise correspondante.

        Returns:
            (company_uuid, created)
        """
        company_name = lead.get('company_name')
        domain = lead.get('domain')

        # Chercher par domain
        if domain:
            existing = self.company_manager.find_by_domain(domain)
            if existing:
                return existing['uuid'], False

        # Chercher par nom fuzzy
        if company_name:
            existing = self.company_manager.find_by_name_fuzzy(company_name, threshold=0.85)
            if existing:
                return existing['uuid'], False

        # Créer nouvelle entreprise
        company_data = {
            'name': company_name,
            'domain': domain,
            'hq_city': lead.get('company_city'),
            'industry': lead.get('company_industry'),
        }

        company_uuid = self.company_manager.create(company_data, source='getsales')
        return company_uuid, True

    def _build_contact_data(self, lead: Dict[str, Any], company_uuid: Optional[str]) -> Dict[str, Any]:
        """Construit les données contact pour le schema V2."""
        # Extraire les stats de campagne
        campaign_stats = self._extract_campaign_stats(lead)

        # Normaliser LinkedIn URL
        linkedin = lead.get('linkedin')
        if linkedin and not linkedin.startswith('http'):
            linkedin = f"https://linkedin.com/in/{linkedin}"

        return {
            'firstname': lead.get('first_name'),
            'lastname': lead.get('last_name'),
            'email': lead.get('email'),
            'phone': lead.get('phone'),
            'job_title': lead.get('position'),
            'linkedin_url': linkedin,
            'company_uuid': company_uuid,
            'source': 'getsales',
            'getsales_uuid': lead.get('uuid'),
            'tags': [f"getsales:{lead.get('uuid')}", campaign_stats.get('flow_name', '')],
            'notes': self._build_notes(lead, campaign_stats),
        }

    def _extract_campaign_stats(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Extrait les statistiques de campagne depuis les messages."""
        messages = lead.get('_messages', [])

        stats = {
            'flow_name': None,
            'flow_uuid': None,
            'first_contact_date': None,
            'last_interaction_date': None,
            'interaction_count': len(messages),
            'has_replied': False
        }

        # Chercher flow_name dans les données du lead
        if lead.get('flow_name'):
            stats['flow_name'] = lead['flow_name']
        if lead.get('flow_uuid'):
            stats['flow_uuid'] = lead['flow_uuid']

        # Chercher dans 'flows' si présent
        flows = lead.get('flows', [])
        if flows and isinstance(flows, list) and len(flows) > 0:
            first_flow = flows[0]
            if isinstance(first_flow, dict):
                flow_uuid = first_flow.get('flow_uuid') or first_flow.get('uuid')
                flow_name = first_flow.get('name') or first_flow.get('flow_name')

                if not stats['flow_uuid'] and flow_uuid:
                    stats['flow_uuid'] = flow_uuid
                if not stats['flow_name'] and flow_name:
                    stats['flow_name'] = flow_name

                if first_flow.get('created_at'):
                    stats['first_contact_date'] = first_flow['created_at'][:10]

        # Traiter les messages
        if messages:
            sorted_msgs = sorted(
                messages,
                key=lambda m: m.get('sent_at', '') or m.get('created_at', '') or ''
            )

            # Premier message sortant
            for msg in sorted_msgs:
                msg_type = msg.get('type') or msg.get('direction', '')
                sent_at = msg.get('sent_at') or msg.get('created_at', '')
                if msg_type in ('outbox', 'out', 'sent') and sent_at:
                    stats['first_contact_date'] = sent_at[:10]
                    break

            # Dernier message
            for msg in reversed(sorted_msgs):
                sent_at = msg.get('sent_at') or msg.get('created_at', '')
                if sent_at:
                    stats['last_interaction_date'] = sent_at[:10]
                    break

            # A répondu?
            stats['has_replied'] = any(
                m.get('type') in ('inbox', 'in', 'received') or m.get('direction') == 'in'
                for m in messages
            )

        return stats

    def _build_notes(self, lead: Dict[str, Any], stats: Dict[str, Any]) -> str:
        """Construit une note récapitulative pour le contact."""
        lines = [
            f"Import GetSales {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        ]

        if stats.get('flow_name'):
            lines.append(f"Campagne: {stats['flow_name']}")
        if stats.get('first_contact_date'):
            lines.append(f"Premier contact: {stats['first_contact_date']}")
        if stats.get('interaction_count'):
            lines.append(f"Messages: {stats['interaction_count']}")
        if stats.get('has_replied'):
            lines.append("A répondu: Oui")

        if lead.get('headline'):
            lines.append(f"Headline: {lead['headline']}")

        return '\n'.join(lines)

    def _import_interaction(
        self,
        contact_uuid: str,
        company_uuid: Optional[str],
        lead: Dict[str, Any],
        message: Dict[str, Any]
    ):
        """Importe un message LinkedIn comme interaction."""
        msg_type = message.get('type', '')

        # Déterminer le type d'interaction
        if msg_type in ('outbox', 'out', 'sent'):
            interaction_type = 'linkedin_message_sent'
            direction = 'outbound'
        elif msg_type in ('inbox', 'in', 'received'):
            interaction_type = 'linkedin_reply_received'
            direction = 'inbound'
        else:
            interaction_type = 'linkedin_message'
            direction = 'unknown'

        # Date
        interaction_date = message.get('sent_at') or message.get('created_at')

        # Contenu
        content = message.get('text', '')[:2000] if message.get('text') else None

        # Métadonnées
        metadata = {
            'getsales_uuid': lead.get('uuid'),
            'flow_name': message.get('flow_name') or lead.get('flow_name'),
            'flow_uuid': message.get('flow_uuid') or lead.get('flow_uuid'),
            'message_status': message.get('status'),
        }

        # Créer l'engagement
        engagement_data = {
            'contact_uuid': contact_uuid,
            'company_uuid': company_uuid,
            'type': interaction_type,
            'direction': direction,
            'channel': 'linkedin',
            'content': content,
            'interaction_date': interaction_date,
            'metadata': metadata,
        }

        self.engagement_manager.create(engagement_data, source='getsales')
