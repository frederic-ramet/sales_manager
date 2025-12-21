"""
Service orchestrateur de synchronisation GetSales → HubSpot.
"""
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from .getsales_client import GetSalesClient
from .models import GetSalesDB, PendingLead, LeadInteraction
from .deduplication import DeduplicationService

# Import DeduplicationMatcher pour déduplication locale
try:
    from modules.deduplication import DeduplicationMatcher
    DEDUP_MATCHER_AVAILABLE = True
except ImportError:
    DEDUP_MATCHER_AVAILABLE = False

logger = logging.getLogger(__name__)


class GetSalesSyncService:
    """
    Service principal de synchronisation GetSales → HubSpot.

    Workflow:
    1. Fetch leads depuis GetSales API
    2. Fetch messages pour chaque lead
    3. Détection doublons HubSpot
    4. Stockage en pending_leads (attente validation)
    5. Validation manuelle (UI)
    6. Push vers HubSpot + sync interactions

    Usage:
        from modules.lead_scraper import HubSpotClient

        getsales = GetSalesClient()
        hubspot = HubSpotClient()
        db = GetSalesDB()

        sync = GetSalesSyncService(getsales, hubspot, db)
        result = sync.sync_leads()
    """

    # Mapping GetSales → HubSpot
    FIELD_MAPPING = {
        'first_name': 'firstname',
        'last_name': 'lastname',
        'email': 'email',
        'company_name': 'company',
        'position': 'jobtitle',
        'domain': 'website',
    }

    def __init__(
        self,
        getsales_client: GetSalesClient,
        hubspot_client,  # HubSpotClient from lead_scraper
        db: GetSalesDB
    ):
        """
        Initialise le service de sync.

        Args:
            getsales_client: Client API GetSales
            hubspot_client: Client API HubSpot
            db: Gestionnaire base SQLite
        """
        self.getsales = getsales_client
        self.hubspot = hubspot_client
        self.db = db
        self.dedup = DeduplicationService(hubspot_client)

        # DeduplicationMatcher pour déduplication locale (unified_contacts)
        self.local_matcher = DeduplicationMatcher() if DEDUP_MATCHER_AVAILABLE else None

    def sync_leads(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        fetch_messages: bool = True
    ) -> Dict[str, Any]:
        """
        Synchronisation principale: fetch leads et stockage pending.

        Args:
            filters: Filtres GetSales (flow_uuid, etc.)
            limit: Nombre max de leads
            fetch_messages: Récupérer les messages LinkedIn

        Returns:
            {
                'leads_fetched': int,
                'leads_new': int,
                'leads_updated': int,
                'sync_id': int
            }
        """
        # Créer le log de sync
        sync_id = self.db.create_sync_log(status='running')

        try:
            logger.info(f"Début sync GetSales (limit={limit})...")

            # 1. Fetch leads
            if fetch_messages:
                leads = self.getsales.fetch_leads_with_messages(
                    filters=filters,
                    limit=limit
                )
            else:
                leads = self.getsales.fetch_leads(
                    filters=filters,
                    limit=limit
                )

            logger.info(f"{len(leads)} leads récupérés depuis GetSales")

            # 2. Traiter chaque lead
            new_count = 0
            updated_count = 0

            for lead in leads:
                lead_uuid = lead.get('uuid')
                if not lead_uuid:
                    continue

                # Vérifier si déjà en base
                existing = self.db.get_pending_lead_by_uuid(lead_uuid)

                # Détecter doublons HubSpot
                duplicates = self.dedup.find_duplicates(lead)
                duplicate_status = self.dedup.get_duplicate_status(duplicates)

                # Détecter doublons locaux (unified_contacts)
                local_matches = []
                if self.local_matcher:
                    local_matches = self._find_local_duplicates(lead)
                    # Si pas de doublons HubSpot mais doublons locaux, marquer comme potential
                    if local_matches and duplicate_status == 'none':
                        duplicate_status = 'potential'

                # Chercher les companies HubSpot correspondantes
                company_matches = self._find_company_matches(lead)

                # Créer ou mettre à jour le pending lead
                pending = PendingLead(
                    id=existing.id if existing else None,
                    getsales_uuid=lead_uuid,
                    getsales_data=lead,
                    hubspot_matches=[d.to_dict() for d in duplicates],
                    local_matches=local_matches,
                    company_matches=company_matches,
                    duplicate_status=duplicate_status,
                    validation_status=existing.validation_status if existing else 'pending'
                )

                self.db.save_pending_lead(pending)

                if existing:
                    updated_count += 1
                else:
                    new_count += 1

            # Mettre à jour le log
            self.db.update_sync_log(
                log_id=sync_id,
                status='completed',
                leads_fetched=len(leads),
                leads_created=new_count,
                leads_updated=updated_count
            )

            logger.info(f"Sync terminée: {new_count} nouveaux, {updated_count} mis à jour")

            return {
                'leads_fetched': len(leads),
                'leads_new': new_count,
                'leads_updated': updated_count,
                'sync_id': sync_id
            }

        except Exception as e:
            logger.error(f"Erreur sync: {e}")
            self.db.update_sync_log(
                log_id=sync_id,
                status='failed',
                error_message=str(e)
            )
            raise

    def validate_lead(
        self,
        pending_lead_id: int,
        action: str,
        merge_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Valide un lead et effectue l'action appropriée.

        Args:
            pending_lead_id: ID du pending lead
            action: 'create_new', 'merge', ou 'reject'
            merge_data: Si merge, dict avec choix par champ:
                {
                    'hubspot_contact_id': '123',
                    'fields': {'firstname': 'getsales', 'email': 'hubspot', ...}
                }

        Returns:
            {'success': bool, 'hubspot_contact_id': str, 'message': str}
        """
        pending = self.db.get_pending_lead(pending_lead_id)
        if not pending:
            raise ValueError(f"Lead {pending_lead_id} non trouvé")

        getsales_data = pending.getsales_data

        try:
            if action == 'reject':
                # Marquer comme rejeté
                self.db.update_lead_status(
                    lead_id=pending_lead_id,
                    status='rejected',
                    rejection_reason=merge_data.get('reason') if merge_data else None
                )
                return {
                    'success': True,
                    'hubspot_contact_id': None,
                    'message': 'Lead rejeté'
                }

            elif action == 'create_new':
                # Extraire le choix de company depuis merge_data
                company_choice = None
                if merge_data:
                    if merge_data.get('use_existing_company_id'):
                        company_choice = {'type': 'existing', 'id': merge_data['use_existing_company_id']}
                    elif merge_data.get('create_new_company'):
                        company_choice = {'type': 'create_new'}

                # Récupérer les messages LinkedIn pour ce lead
                lead_uuid = getsales_data.get('uuid')
                logger.info(f"Validation lead {lead_uuid} - données existantes: flow_name={getsales_data.get('flow_name')}, flows={getsales_data.get('flows')}")

                if lead_uuid and self.getsales:
                    try:
                        messages = self.getsales.fetch_lead_messages(lead_uuid)
                        getsales_data['_messages'] = messages
                        logger.info(f"Messages récupérés pour lead {lead_uuid}: {len(messages)}")
                        if messages:
                            logger.info(f"Structure premier message: {list(messages[0].keys()) if isinstance(messages[0], dict) else type(messages[0])}")
                    except Exception as e:
                        logger.warning(f"Impossible de récupérer les messages: {e}")
                        getsales_data['_messages'] = []

                # Créer nouveau contact HubSpot
                contact = self._create_hubspot_contact(getsales_data, company_choice=company_choice)

                # Sync interactions
                self._sync_interactions(
                    hubspot_contact_id=contact['id'],
                    getsales_lead=getsales_data
                )

                # Marquer comme validé
                self.db.update_lead_status(
                    lead_id=pending_lead_id,
                    status='approved'
                )

                # Message avec info company
                company_msg = ""
                if contact.get('company_id'):
                    company_msg = f" + Company {contact['company_id']}"

                return {
                    'success': True,
                    'hubspot_contact_id': contact['id'],
                    'message': f"Contact créé: {contact['id']}{company_msg}"
                }

            elif action == 'merge':
                if not merge_data:
                    raise ValueError("merge_data requis pour action 'merge'")

                # Merger avec contact existant
                contact = self._merge_hubspot_contact(
                    getsales_data=getsales_data,
                    merge_data=merge_data
                )

                # Sync interactions
                self._sync_interactions(
                    hubspot_contact_id=merge_data['hubspot_contact_id'],
                    getsales_lead=getsales_data
                )

                # Marquer comme validé
                self.db.update_lead_status(
                    lead_id=pending_lead_id,
                    status='approved',
                    merge_decision=merge_data
                )

                return {
                    'success': True,
                    'hubspot_contact_id': merge_data['hubspot_contact_id'],
                    'message': 'Contact fusionné'
                }

            else:
                raise ValueError(f"Action inconnue: {action}")

        except Exception as e:
            logger.error(f"Erreur validation lead {pending_lead_id}: {e}")
            raise

    def _extract_campaign_stats(self, getsales_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrait les statistiques de campagne depuis les messages GetSales.

        Args:
            getsales_data: Données du lead GetSales avec '_messages'

        Returns:
            Dict avec flow_name, flow_uuid, first_contact_date, last_interaction_date,
            interaction_count, has_replied
        """
        messages = getsales_data.get('_messages', [])

        logger.info(f"Extraction stats campagne - {len(messages)} messages trouvés")
        if messages:
            logger.debug(f"Premier message: {messages[0]}")

        stats = {
            'flow_name': None,
            'flow_uuid': None,
            'first_contact_date': None,
            'last_interaction_date': None,
            'interaction_count': len(messages),
            'has_replied': False
        }

        # Chercher flow_name dans les données du lead directement (fallback)
        # GetSales peut stocker le flow_name au niveau du lead, pas des messages
        if getsales_data.get('flow_name'):
            stats['flow_name'] = getsales_data['flow_name']
        if getsales_data.get('flow_uuid'):
            stats['flow_uuid'] = getsales_data['flow_uuid']

        # Chercher aussi dans 'flows' si présent (structure GetSales)
        flows = getsales_data.get('flows', [])
        logger.info(f"Flows trouvés: {flows}")
        if flows and isinstance(flows, list) and len(flows) > 0:
            first_flow = flows[0]
            logger.info(f"Premier flow: {first_flow}")
            if isinstance(first_flow, dict):
                # Structure GetSales: flow_uuid est l'UUID de la campagne, uuid est l'ID de l'association
                # Priorité: flow_uuid > uuid
                flow_uuid = first_flow.get('flow_uuid') or first_flow.get('uuid') or first_flow.get('id')
                flow_name = first_flow.get('name') or first_flow.get('flow_name') or first_flow.get('title')

                if not stats['flow_uuid'] and flow_uuid:
                    stats['flow_uuid'] = flow_uuid
                if not stats['flow_name'] and flow_name:
                    stats['flow_name'] = flow_name

                # Utiliser created_at du flow comme date de premier contact si pas de messages
                if not stats['first_contact_date'] and first_flow.get('created_at'):
                    created_at = first_flow['created_at']
                    # Format: 2025-11-17T17:02:55.000000Z
                    stats['first_contact_date'] = created_at[:10]
                    logger.info(f"Date premier contact depuis flow: {stats['first_contact_date']}")

        # Traiter les messages si présents
        if messages:
            # Trier les messages par date
            sorted_messages = sorted(
                messages,
                key=lambda m: m.get('sent_at', '') or m.get('created_at', '') or ''
            )

            # Extraire le flow_name du premier message sortant (si pas déjà trouvé)
            for msg in sorted_messages:
                if msg.get('flow_name') and not stats['flow_name']:
                    stats['flow_name'] = msg['flow_name']
                if msg.get('flow_uuid') and not stats['flow_uuid']:
                    stats['flow_uuid'] = msg['flow_uuid']
                if stats['flow_name'] and stats['flow_uuid']:
                    break

            # Premier contact = premier message sortant (écrase la date du flow si messages présents)
            for msg in sorted_messages:
                msg_type = msg.get('type') or msg.get('direction', '')
                sent_at = msg.get('sent_at') or msg.get('created_at', '')
                if msg_type in ('outbox', 'out', 'sent') and sent_at:
                    stats['first_contact_date'] = sent_at[:10]  # YYYY-MM-DD
                    break

            # Dernière interaction = dernier message (tous types)
            for msg in reversed(sorted_messages):
                sent_at = msg.get('sent_at') or msg.get('created_at', '')
                if sent_at:
                    stats['last_interaction_date'] = sent_at[:10]  # YYYY-MM-DD
                    break

            # A répondu = au moins un message inbox
            stats['has_replied'] = any(
                m.get('type') in ('inbox', 'in', 'received') or m.get('direction') == 'in'
                for m in messages
            )

        # Si on a un flow_uuid mais pas de flow_name, récupérer le nom via l'API
        if stats['flow_uuid'] and not stats['flow_name'] and self.getsales:
            logger.info(f"Récupération nom flow pour UUID: {stats['flow_uuid']}")
            flow_name = self.getsales.get_flow_name(stats['flow_uuid'])
            if flow_name:
                stats['flow_name'] = flow_name
                logger.info(f"Nom flow récupéré: {flow_name}")

        logger.info(f"Stats campagne extraites: flow={stats['flow_name']}, first_contact={stats['first_contact_date']}, messages={stats['interaction_count']}")

        return stats

    def _build_campaign_note(self, getsales_data: Dict[str, Any], stats: Dict[str, Any]) -> str:
        """
        Construit le contenu de la note récapitulative de la campagne.

        Args:
            getsales_data: Données du lead GetSales
            stats: Stats extraites via _extract_campaign_stats

        Returns:
            Contenu de la note (texte formaté)
        """
        from datetime import datetime
        messages = getsales_data.get('_messages', [])

        lines = [
            "📧 <b>Prospection LinkedIn via GetSales</b>",
            f"<i>Sync: {datetime.now().strftime('%Y-%m-%d %H:%M')}</i>",
            "",
        ]

        # Info campagne
        if stats['flow_name']:
            lines.append(f"🎯 <b>Campagne:</b> {stats['flow_name']}")
        if stats['flow_uuid'] and not stats['flow_name']:
            lines.append(f"🎯 <b>Flow UUID:</b> {stats['flow_uuid']}")
        if stats['first_contact_date']:
            lines.append(f"📅 <b>Premier contact:</b> {stats['first_contact_date']}")
        if stats['last_interaction_date']:
            lines.append(f"📅 <b>Dernière interaction:</b> {stats['last_interaction_date']}")
        lines.append(f"💬 <b>Messages échangés:</b> {stats['interaction_count']}")
        lines.append(f"✉️ <b>A répondu:</b> {'Oui ✅' if stats['has_replied'] else 'Non'}")

        # Historique des messages
        if messages:
            lines.append("")
            lines.append("─" * 40)
            lines.append("<b>Historique des messages:</b>")
            lines.append("")

            sorted_messages = sorted(
                messages,
                key=lambda m: m.get('sent_at', '') or ''
            )

            for msg in sorted_messages:
                msg_type = msg.get('type', '')
                sent_at = msg.get('sent_at', '')[:16].replace('T', ' ') if msg.get('sent_at') else 'N/A'
                text = msg.get('text', '')[:200] if msg.get('text') else ''
                status = msg.get('status', '')

                if msg_type == 'outbox':
                    icon = "➡️"
                    label = "Envoyé"
                    if status == 'read':
                        label += " (lu ✓)"
                elif msg_type == 'inbox':
                    icon = "⬅️"
                    label = "Réponse reçue"
                else:
                    icon = "•"
                    label = msg_type

                lines.append(f"<b>[{sent_at}]</b> {icon} {label}")
                if text:
                    # Tronquer et échapper le texte
                    text_preview = text.replace('<', '&lt;').replace('>', '&gt;')
                    lines.append(f"<i>\"{text_preview}{'...' if len(msg.get('text', '')) > 200 else ''}\"</i>")
                lines.append("")

        return "<br>".join(lines)

    def _create_hubspot_contact(
        self,
        getsales_data: Dict[str, Any],
        company_choice: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Crée un nouveau contact dans HubSpot avec association à une company.

        Args:
            getsales_data: Données du lead GetSales
            company_choice: Choix de company fait par l'utilisateur:
                - None: auto-detect (chercher ou créer)
                - {'type': 'existing', 'id': '123'}: utiliser company existante
                - {'type': 'create_new'}: forcer création nouvelle company

        Returns:
            Contact créé avec 'id' et 'company_id' (si associé)
        """
        # Extraire les stats de campagne
        campaign_stats = self._extract_campaign_stats(getsales_data)

        # Mapper les champs
        contact_data = {}

        for gs_field, hs_field in self.FIELD_MAPPING.items():
            value = getsales_data.get(gs_field)
            if value:
                contact_data[hs_field] = str(value)

        # Ajouter LinkedIn URL
        linkedin = getsales_data.get('linkedin')
        if linkedin:
            linkedin_url = self.dedup._format_linkedin_url(linkedin)
            if linkedin_url:
                contact_data['hs_linkedin_url'] = linkedin_url

        # Ajouter propriétés custom GetSales
        contact_data['getsales_uuid'] = getsales_data.get('uuid', '')
        contact_data['import_source'] = 'GetSales_interne'

        # Attribution HubSpot - prospection LinkedIn
        contact_data['hs_analytics_source'] = 'OTHER_CAMPAIGNS'
        contact_data['hs_analytics_source_data_1'] = 'GetSales_interne'
        contact_data['hs_analytics_source_data_2'] = 'LinkedIn'

        # Ajouter headline/bio si disponibles
        if getsales_data.get('headline'):
            contact_data['getsales_headline'] = getsales_data['headline'][:500]
        if getsales_data.get('about'):
            contact_data['getsales_bio'] = getsales_data['about'][:2000]

        # Ajouter propriétés de campagne
        if campaign_stats['flow_name']:
            contact_data['getsales_flow_name'] = campaign_stats['flow_name']
        if campaign_stats['flow_uuid']:
            contact_data['getsales_flow_uuid'] = campaign_stats['flow_uuid']
        if campaign_stats['first_contact_date']:
            contact_data['getsales_first_contact_date'] = campaign_stats['first_contact_date']
        if campaign_stats['last_interaction_date']:
            contact_data['getsales_last_interaction_date'] = campaign_stats['last_interaction_date']
        if campaign_stats['interaction_count']:
            contact_data['getsales_interaction_count'] = str(campaign_stats['interaction_count'])
        contact_data['getsales_has_replied'] = 'true' if campaign_stats['has_replied'] else 'false'

        # 1. Créer le contact (utiliser create_contact pour avoir l'ID)
        contact_result = self.hubspot.create_contact(contact_data)

        if not contact_result:
            raise Exception("Échec création contact HubSpot")

        contact_id = contact_result['id']
        logger.info(f"Contact HubSpot créé: ID {contact_id}")

        result = {'id': contact_id, 'company_id': None}

        # 2. Gérer la company (si nom d'entreprise fourni)
        company_name = getsales_data.get('company_name')
        if company_name:
            try:
                company_id = None

                # Cas 1: Utiliser une company existante (choisie par l'utilisateur)
                if company_choice and company_choice.get('type') == 'existing':
                    company_id = company_choice['id']
                    logger.info(f"Utilisation company existante choisie: ID {company_id}")

                # Cas 2: Forcer la création d'une nouvelle company
                elif company_choice and company_choice.get('type') == 'create_new':
                    domain = getsales_data.get('domain')
                    new_company = self.hubspot.create_company({
                        'name': company_name,
                        'domain': domain,
                        'city': getsales_data.get('company_city'),
                        'industry': getsales_data.get('company_industry'),
                    })
                    if new_company:
                        company_id = new_company['id']
                        logger.info(f"Nouvelle company créée (forcé): {company_name} (ID: {company_id})")

                # Cas 3: Auto-detect (comportement par défaut)
                else:
                    domain = getsales_data.get('domain')
                    company_result = self.hubspot.get_or_create_company(
                        name=company_name,
                        domain=domain,
                        additional_properties={
                            'city': getsales_data.get('company_city'),
                            'industry': getsales_data.get('company_industry'),
                        }
                    )
                    if company_result:
                        company_id = company_result['id']
                        action = "trouvée" if not company_result.get('created') else "créée"
                        logger.info(f"Company {action} (auto): {company_name} (ID: {company_id})")

                # 3. Associer le contact à la company
                if company_id:
                    if self.hubspot.associate_contact_company(contact_id, company_id):
                        result['company_id'] = company_id
                        logger.info(f"Contact {contact_id} associé à company {company_id}")
                    else:
                        logger.warning(f"Échec association contact-company")
                else:
                    logger.warning(f"Aucune company à associer pour: {company_name}")

            except Exception as e:
                logger.error(f"Erreur gestion company: {e}")
                # Le contact est créé, on continue sans company

        return result

    def _merge_hubspot_contact(
        self,
        getsales_data: Dict[str, Any],
        merge_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Fusionne les données avec un contact HubSpot existant.

        Args:
            getsales_data: Données du lead GetSales
            merge_data: Décisions de merge:
                {
                    'hubspot_contact_id': '123',
                    'fields': {'firstname': 'getsales', ...}
                }

        Returns:
            Contact mis à jour
        """
        hubspot_contact_id = merge_data['hubspot_contact_id']
        field_decisions = merge_data.get('fields', {})

        # Construire les données à updater
        update_data = {}

        for hs_field, source in field_decisions.items():
            if source == 'getsales':
                # Trouver le champ GetSales correspondant
                gs_field = self._reverse_map_field(hs_field)
                value = getsales_data.get(gs_field)
                if value:
                    update_data[hs_field] = str(value)

        # Toujours ajouter getsales_uuid
        update_data['getsales_uuid'] = getsales_data.get('uuid', '')

        # LinkedIn URL si pas dans HubSpot
        linkedin = getsales_data.get('linkedin')
        if linkedin:
            linkedin_url = self.dedup._format_linkedin_url(linkedin)
            if linkedin_url:
                update_data['linkedin_url'] = linkedin_url

        # Mettre à jour le contact
        if update_data:
            result = self.hubspot.update_contacts([{
                'hubspot_id': hubspot_contact_id,
                'properties': update_data
            }])

            if result.get('updated', 0) > 0:
                logger.info(f"Contact {hubspot_contact_id} mis à jour")
            else:
                errors = result.get('errors', [])
                logger.warning(f"Erreurs mise à jour: {errors}")

        return {'id': hubspot_contact_id}

    def _reverse_map_field(self, hs_field: str) -> str:
        """Trouve le champ GetSales pour un champ HubSpot."""
        for gs, hs in self.FIELD_MAPPING.items():
            if hs == hs_field:
                return gs
        return hs_field

    def _sync_interactions(
        self,
        hubspot_contact_id: str,
        getsales_lead: Dict[str, Any]
    ):
        """
        Synchronise les interactions LinkedIn vers HubSpot.

        Crée une note récapitulative avec l'historique des messages.

        Args:
            hubspot_contact_id: ID du contact HubSpot
            getsales_lead: Lead avec '_messages'
        """
        messages = getsales_lead.get('_messages', [])
        lead_uuid = getsales_lead.get('uuid', '')

        # Stocker les interactions en base locale
        for msg in messages:
            interaction = LeadInteraction(
                getsales_lead_uuid=lead_uuid,
                hubspot_contact_id=hubspot_contact_id,
                interaction_type=self._get_interaction_type(msg),
                interaction_date=msg.get('sent_at'),
                message_text=msg.get('text', '')[:500] if msg.get('text') else None,
                flow_name=msg.get('flow_name'),
                synced_to_hubspot=False
            )
            interaction_id = self.db.save_interaction(interaction)
            self.db.mark_interaction_synced(interaction_id)

        # Créer une note récapitulative dans HubSpot
        campaign_stats = self._extract_campaign_stats(getsales_lead)
        note_body = self._build_campaign_note(getsales_lead, campaign_stats)

        # Utiliser la date du premier contact comme timestamp de la note
        first_contact_date = campaign_stats.get('first_contact_date')

        note_result = self.hubspot.create_note(
            contact_id=hubspot_contact_id,
            body=note_body,
            timestamp=first_contact_date
        )

        if note_result:
            logger.info(f"Note campagne créée pour contact {hubspot_contact_id}")
        else:
            logger.warning(f"Échec création note pour contact {hubspot_contact_id}")

        if messages:
            logger.info(f"{len(messages)} interactions synchronisées pour {hubspot_contact_id}")

    def _get_interaction_type(self, message: Dict[str, Any]) -> str:
        """Détermine le type d'interaction."""
        msg_type = message.get('type', '')
        status = message.get('status', '')

        if msg_type == 'outbox':
            if status == 'read':
                return 'message_read'
            return 'message_sent'
        elif msg_type == 'inbox':
            return 'reply_received'

        return 'unknown'

    def _find_local_duplicates(self, lead: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Trouve les doublons dans la base locale unified_contacts.

        Utilise DeduplicationMatcher avec fuzzy matching.

        Args:
            lead: Données du lead GetSales

        Returns:
            Liste de matches avec 'contact', 'match_type', 'confidence', 'similarity_score'
        """
        if not self.local_matcher:
            return []

        # Extraire les champs pour la recherche
        email = lead.get('email')
        linkedin_url = lead.get('linkedin')
        if linkedin_url and not linkedin_url.startswith('http'):
            linkedin_url = f"https://linkedin.com/in/{linkedin_url}"

        company_name = lead.get('company_name')
        first_name = lead.get('first_name')
        last_name = lead.get('last_name')
        getsales_uuid = lead.get('uuid')

        # Appeler DeduplicationMatcher.find_matches()
        matches = self.local_matcher.find_matches(
            email=email,
            linkedin_url=linkedin_url,
            company_name=company_name,
            firstname=first_name,
            lastname=last_name,
            getsales_uuid=getsales_uuid,
            include_low_confidence=True
        )

        # Convertir MatchResult en dict pour stockage JSON
        return [match.to_dict() for match in matches]

    def _find_company_matches(self, lead: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Trouve les companies HubSpot correspondant au lead.

        Recherche par nom d'entreprise et domaine.

        Args:
            lead: Données du lead GetSales

        Returns:
            Liste de companies avec 'id', 'name', 'domain', 'match_type'
        """
        company_name = lead.get('company_name')
        if not company_name:
            return []

        matches = []
        domain = lead.get('domain')

        try:
            # Recherche par nom exact
            result = self.hubspot.search_company(name=company_name, domain=domain)

            if result:
                props = result.get('properties', {})
                matches.append({
                    'id': result['id'],
                    'name': props.get('name', company_name),
                    'domain': props.get('domain', ''),
                    'city': props.get('city', ''),
                    'industry': props.get('industry', ''),
                    'employees': props.get('numberofemployees', ''),
                    'match_type': 'exact' if props.get('name', '').lower() == company_name.lower() else 'fuzzy'
                })
                logger.debug(f"Company HubSpot trouvée: {props.get('name')}")
            else:
                logger.debug(f"Aucune company HubSpot trouvée pour: {company_name}")

        except Exception as e:
            logger.error(f"Erreur recherche company HubSpot: {e}")

        return matches

    def get_sync_status(self) -> Dict[str, Any]:
        """
        Retourne le statut actuel de la sync.

        Returns:
            {
                'last_sync': SyncLog or None,
                'pending_stats': Dict avec counts
            }
        """
        return {
            'last_sync': self.db.get_last_sync(),
            'pending_stats': self.db.get_pending_stats()
        }
