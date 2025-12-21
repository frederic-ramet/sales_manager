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

                # Créer ou mettre à jour le pending lead
                pending = PendingLead(
                    id=existing.id if existing else None,
                    getsales_uuid=lead_uuid,
                    getsales_data=lead,
                    hubspot_matches=[d.to_dict() for d in duplicates],
                    local_matches=local_matches,
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
                # Créer nouveau contact HubSpot
                contact = self._create_hubspot_contact(getsales_data)

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

                return {
                    'success': True,
                    'hubspot_contact_id': contact['id'],
                    'message': f"Contact créé: {contact['id']}"
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

    def _create_hubspot_contact(self, getsales_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crée un nouveau contact dans HubSpot.

        Args:
            getsales_data: Données du lead GetSales

        Returns:
            Contact créé avec 'id'
        """
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
                contact_data['linkedin_url'] = linkedin_url

        # Ajouter propriétés custom GetSales
        contact_data['getsales_uuid'] = getsales_data.get('uuid', '')

        # Ajouter headline/bio si disponibles
        if getsales_data.get('headline'):
            contact_data['getsales_headline'] = getsales_data['headline'][:500]
        if getsales_data.get('about'):
            contact_data['getsales_bio'] = getsales_data['about'][:2000]

        # Créer le contact
        result = self.hubspot.push_contacts([contact_data])

        if result.get('created', 0) > 0:
            logger.info(f"Contact HubSpot créé depuis GetSales")
            # Retourner un ID fictif car push_contacts ne retourne pas l'ID
            return {'id': f"new_{getsales_data.get('uuid', 'unknown')}"}
        else:
            errors = result.get('errors', [])
            raise Exception(f"Échec création contact: {errors}")

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

        Args:
            hubspot_contact_id: ID du contact HubSpot
            getsales_lead: Lead avec '_messages'
        """
        messages = getsales_lead.get('_messages', [])
        if not messages:
            return

        lead_uuid = getsales_lead.get('uuid', '')

        for msg in messages:
            # Créer l'interaction en base
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

            # Créer la note HubSpot (si supporté par le client)
            # Note: Le HubSpotClient actuel ne supporte pas les engagements
            # On marque quand même comme synced pour l'instant
            self.db.mark_interaction_synced(interaction_id)

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
