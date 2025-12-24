"""
EngagementManager - Gestionnaire des engagements (Schema V2).

Gère l'historique des engagements avec les contacts:
- Messages GetSales (LinkedIn)
- Emails HubSpot
- Appels téléphoniques
- Réunions
- Notes manuelles

Usage:
    manager = EngagementManager()

    # Créer une interaction
    uuid = manager.create({
        'contact_uuid': 'xxx',
        'type': 'message',
        'direction': 'outbound',
        'channel': 'linkedin',
        'content': 'Bonjour...',
        'interaction_date': datetime.now()
    }, source='getsales')

    # Lister engagements d'un contact
    engagements = manager.list_by_contact('xxx')
"""

import sqlite3
import logging
import uuid as uuid_lib
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "leads.db"


class EngagementManager:
    """
    Gestionnaire des engagements - Schema V2.

    Types d'engagements:
    - message: Messages LinkedIn (GetSales)
    - email: Emails
    - call: Appels téléphoniques
    - meeting: Réunions
    - note: Notes manuelles

    Directions:
    - inbound: Reçu du contact
    - outbound: Envoyé au contact

    Channels:
    - linkedin: Messages LinkedIn
    - email: Emails
    - phone: Appels téléphoniques
    - in_person: En personne
    - video: Vidéoconférence
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(DEFAULT_DB_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _generate_uuid(self) -> str:
        return str(uuid_lib.uuid4())

    # =========================================================================
    # CRUD
    # =========================================================================

    def create(self, data: Dict[str, Any], source: str = 'manual') -> str:
        """
        Crée une nouvelle interaction.

        Args:
            data: Données de l'interaction
            source: Source de l'import ('getsales', 'hubspot', 'manual')

        Returns:
            UUID de l'interaction créée
        """
        if not data.get('contact_uuid'):
            raise ValueError("'contact_uuid' est requis")
        if not data.get('type'):
            raise ValueError("'type' est requis")
        if not data.get('interaction_date'):
            data['interaction_date'] = datetime.now()

        interaction_uuid = self._generate_uuid()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO engagements (
                    uuid, contact_uuid,
                    hubspot_engagement_id, getsales_message_id,
                    type, direction, channel,
                    subject, content, content_html,
                    interaction_date, duration_minutes,
                    campaign_id, sequence_name, sequence_step,
                    outcome,
                    source
                ) VALUES (
                    ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?,
                    ?
                )
            """, (
                interaction_uuid,
                data.get('contact_uuid'),
                data.get('hubspot_engagement_id'),
                data.get('getsales_message_id'),
                data.get('type'),
                data.get('direction'),
                data.get('channel'),
                data.get('subject'),
                data.get('content'),
                data.get('content_html'),
                data.get('interaction_date'),
                data.get('duration_minutes'),
                data.get('campaign_id'),
                data.get('sequence_name'),
                data.get('sequence_step'),
                data.get('outcome'),
                source,
            ))
            conn.commit()

            # Mettre à jour le compteur du contact
            cursor.execute("""
                UPDATE contacts SET
                    total_engagements = total_engagements + 1,
                    last_interaction_at = ?
                WHERE uuid = ?
            """, (data.get('interaction_date'), data.get('contact_uuid')))
            conn.commit()

            logger.debug(f"Engagement créée: {data.get('type')} ({interaction_uuid})")
            return interaction_uuid

    def get(self, interaction_uuid: str) -> Optional[Dict[str, Any]]:
        """Récupère une interaction par UUID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM engagements WHERE uuid = ?", (interaction_uuid,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update(self, interaction_uuid: str, data: Dict[str, Any]) -> bool:
        """Met à jour une interaction."""
        if not data:
            return False

        # Champs autorisés
        allowed_fields = {
            'type', 'direction', 'channel',
            'subject', 'content', 'content_html',
            'interaction_date', 'duration_minutes',
            'campaign_id', 'sequence_name', 'sequence_step',
            'outcome'
        }

        updates = {k: v for k, v in data.items() if k in allowed_fields}
        if not updates:
            return False

        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [interaction_uuid]

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE engagements SET {set_clause} WHERE uuid = ?", values)
            conn.commit()
            return cursor.rowcount > 0

    def delete(self, interaction_uuid: str) -> bool:
        """Supprime une interaction."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # D'abord récupérer le contact_uuid pour décrémenter le compteur
            cursor.execute(
                "SELECT contact_uuid FROM engagements WHERE uuid = ?",
                (interaction_uuid,)
            )
            row = cursor.fetchone()
            contact_uuid = row[0] if row else None

            # Supprimer l'interaction
            cursor.execute("DELETE FROM engagements WHERE uuid = ?", (interaction_uuid,))
            deleted = cursor.rowcount > 0

            # Mettre à jour le compteur du contact
            if deleted and contact_uuid:
                cursor.execute("""
                    UPDATE contacts SET total_engagements = total_engagements - 1
                    WHERE uuid = ? AND total_engagements > 0
                """, (contact_uuid,))

            conn.commit()
            return deleted

    # =========================================================================
    # RECHERCHE
    # =========================================================================

    def find_by_hubspot_id(self, hubspot_engagement_id: str) -> Optional[Dict[str, Any]]:
        """Trouve une interaction par HubSpot engagement ID."""
        if not hubspot_engagement_id:
            return None
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM engagements WHERE hubspot_engagement_id = ?",
                (str(hubspot_engagement_id),)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_by_getsales_id(self, getsales_message_id: str) -> Optional[Dict[str, Any]]:
        """Trouve une interaction par GetSales message ID."""
        if not getsales_message_id:
            return None
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM engagements WHERE getsales_message_id = ?",
                (getsales_message_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_or_create(self, data: Dict[str, Any], source: str = 'manual') -> Tuple[str, bool]:
        """
        Trouve ou crée une interaction.

        Returns:
            Tuple (uuid, created) - created=True si nouvelle
        """
        # Vérifier par ID externe
        if data.get('hubspot_engagement_id'):
            existing = self.find_by_hubspot_id(data['hubspot_engagement_id'])
            if existing:
                return existing['uuid'], False

        if data.get('getsales_message_id'):
            existing = self.find_by_getsales_id(data['getsales_message_id'])
            if existing:
                return existing['uuid'], False

        # Créer nouvelle interaction
        new_uuid = self.create(data, source=source)
        return new_uuid, True

    # =========================================================================
    # LISTING
    # =========================================================================

    def list_by_contact(
        self,
        contact_uuid: str,
        interaction_type: str = None,
        channel: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Liste les engagements d'un contact."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            conditions = ["contact_uuid = ?"]
            params = [contact_uuid]

            if interaction_type:
                conditions.append("type = ?")
                params.append(interaction_type)

            if channel:
                conditions.append("channel = ?")
                params.append(channel)

            where_clause = " AND ".join(conditions)
            params.append(limit)

            cursor.execute(f"""
                SELECT * FROM engagements
                WHERE {where_clause}
                ORDER BY interaction_date DESC
                LIMIT ?
            """, params)

            return [dict(row) for row in cursor.fetchall()]

    def list_by_company(
        self,
        company_uuid: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Liste les engagements de tous les contacts d'une entreprise."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.*, c.firstname, c.lastname, c.email
                FROM engagements e
                JOIN contacts c ON e.contact_uuid = c.uuid
                WHERE c.company_uuid = ?
                ORDER BY e.interaction_date DESC
                LIMIT ?
            """, (company_uuid, limit))
            return [dict(row) for row in cursor.fetchall()]

    def list_by_campaign(
        self,
        campaign_id: str,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Liste les engagements d'une campagne."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT i.*, c.firstname, c.lastname, c.email, c.linkedin_url
                FROM engagements i
                LEFT JOIN contacts c ON i.contact_uuid = c.uuid
                WHERE i.campaign_id = ?
                ORDER BY i.interaction_date DESC
                LIMIT ?
            """, (campaign_id, limit))
            return [dict(row) for row in cursor.fetchall()]

    def list_recent(
        self,
        days: int = 7,
        interaction_type: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Liste les engagements récentes."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            conditions = ["interaction_date >= datetime('now', ?)"]
            params = [f'-{days} days']

            if interaction_type:
                conditions.append("type = ?")
                params.append(interaction_type)

            where_clause = " AND ".join(conditions)
            params.append(limit)

            cursor.execute(f"""
                SELECT i.*, c.firstname, c.lastname, c.email, co.name as company_name
                FROM engagements i
                LEFT JOIN contacts c ON i.contact_uuid = c.uuid
                LEFT JOIN companies co ON c.company_uuid = co.uuid
                WHERE {where_clause}
                ORDER BY i.interaction_date DESC
                LIMIT ?
            """, params)

            return [dict(row) for row in cursor.fetchall()]

    def count(self, contact_uuid: str = None, campaign_id: str = None) -> int:
        """Compte les engagements."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if contact_uuid:
                cursor.execute(
                    "SELECT COUNT(*) FROM engagements WHERE contact_uuid = ?",
                    (contact_uuid,)
                )
            elif campaign_id:
                cursor.execute(
                    "SELECT COUNT(*) FROM engagements WHERE campaign_id = ?",
                    (campaign_id,)
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM engagements")

            return cursor.fetchone()[0]

    # =========================================================================
    # STATS
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques des engagements."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            stats = {}

            # Total
            cursor.execute("SELECT COUNT(*) FROM engagements")
            stats['total'] = cursor.fetchone()[0]

            # Par type
            cursor.execute("""
                SELECT type, COUNT(*) as count
                FROM engagements
                GROUP BY type
            """)
            stats['by_type'] = {row[0]: row[1] for row in cursor.fetchall()}

            # Par source
            cursor.execute("""
                SELECT source, COUNT(*) as count
                FROM engagements
                GROUP BY source
            """)
            stats['by_source'] = {row[0]: row[1] for row in cursor.fetchall()}

            # Par direction
            cursor.execute("""
                SELECT direction, COUNT(*) as count
                FROM engagements
                WHERE direction IS NOT NULL
                GROUP BY direction
            """)
            stats['by_direction'] = {row[0]: row[1] for row in cursor.fetchall()}

            # Par outcome
            cursor.execute("""
                SELECT outcome, COUNT(*) as count
                FROM engagements
                WHERE outcome IS NOT NULL
                GROUP BY outcome
            """)
            stats['by_outcome'] = {row[0]: row[1] for row in cursor.fetchall()}

            # Cette semaine
            cursor.execute("""
                SELECT COUNT(*) FROM engagements
                WHERE interaction_date >= datetime('now', '-7 days')
            """)
            stats['this_week'] = cursor.fetchone()[0]

            # Campagnes actives
            cursor.execute("""
                SELECT COUNT(DISTINCT campaign_id) FROM engagements
                WHERE campaign_id IS NOT NULL
            """)
            stats['campaigns'] = cursor.fetchone()[0]

            return stats

    def get_campaign_stats(self, campaign_id: str) -> Dict[str, Any]:
        """Retourne les statistiques d'une campagne."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            stats = {'campaign_id': campaign_id}

            # Total engagements
            cursor.execute(
                "SELECT COUNT(*) FROM engagements WHERE campaign_id = ?",
                (campaign_id,)
            )
            stats['total_engagements'] = cursor.fetchone()[0]

            # Contacts uniques
            cursor.execute(
                "SELECT COUNT(DISTINCT contact_uuid) FROM engagements WHERE campaign_id = ?",
                (campaign_id,)
            )
            stats['unique_contacts'] = cursor.fetchone()[0]

            # Par outcome
            cursor.execute("""
                SELECT outcome, COUNT(*) as count
                FROM engagements
                WHERE campaign_id = ? AND outcome IS NOT NULL
                GROUP BY outcome
            """, (campaign_id,))
            stats['by_outcome'] = {row[0]: row[1] for row in cursor.fetchall()}

            # Par étape de séquence
            cursor.execute("""
                SELECT sequence_step, COUNT(*) as count
                FROM engagements
                WHERE campaign_id = ? AND sequence_step IS NOT NULL
                GROUP BY sequence_step
                ORDER BY sequence_step
            """, (campaign_id,))
            stats['by_step'] = {row[0]: row[1] for row in cursor.fetchall()}

            # Taux de réponse
            replied = stats['by_outcome'].get('replied', 0)
            if stats['unique_contacts'] > 0:
                stats['reply_rate'] = round(replied / stats['unique_contacts'] * 100, 1)
            else:
                stats['reply_rate'] = 0

            return stats

    # =========================================================================
    # IMPORT HELPERS
    # =========================================================================

    def import_from_getsales(
        self,
        messages: List[Dict[str, Any]],
        contact_manager
    ) -> Dict[str, Any]:
        """
        Importe des messages GetSales.

        Args:
            messages: Liste de messages GetSales
            contact_manager: Instance de ContactManagerV2

        Returns:
            Rapport d'import
        """
        report = {
            'created': 0,
            'skipped': 0,
            'errors': []
        }

        for msg in messages:
            try:
                # Mapper les champs GetSales
                data = {
                    'getsales_message_id': msg.get('id') or msg.get('message_id'),
                    'type': 'message',
                    'direction': msg.get('direction', 'outbound'),
                    'channel': 'linkedin',
                    'subject': msg.get('subject'),
                    'content': msg.get('text') or msg.get('content'),
                    'interaction_date': msg.get('date') or msg.get('sent_at'),
                    'campaign_id': msg.get('campaign_id'),
                    'sequence_name': msg.get('sequence_name'),
                    'sequence_step': msg.get('step') or msg.get('sequence_step'),
                    'outcome': self._map_getsales_outcome(msg.get('status')),
                }

                # Trouver le contact
                contact_uuid = None
                if msg.get('contact_uuid'):
                    contact_uuid = msg.get('contact_uuid')
                elif msg.get('uuid'):
                    # GetSales UUID du contact
                    contact = contact_manager.find_by_getsales_id(msg.get('uuid'))
                    if contact:
                        contact_uuid = contact['uuid']
                elif msg.get('linkedin_url'):
                    contact = contact_manager.find_by_linkedin(msg.get('linkedin_url'))
                    if contact:
                        contact_uuid = contact['uuid']

                if not contact_uuid:
                    report['errors'].append(f"Contact non trouvé pour message {data.get('getsales_message_id')}")
                    continue

                data['contact_uuid'] = contact_uuid

                # Créer ou ignorer si déjà existant
                uuid, created = self.find_or_create(data, source='getsales')

                if created:
                    report['created'] += 1
                else:
                    report['skipped'] += 1

            except Exception as e:
                report['errors'].append(f"Message error: {e}")

        return report

    def _map_getsales_outcome(self, status: str) -> Optional[str]:
        """Mappe le statut GetSales vers un outcome."""
        if not status:
            return None

        status_lower = status.lower()
        mapping = {
            'replied': 'replied',
            'response': 'replied',
            'interested': 'interested',
            'meeting': 'meeting_booked',
            'meeting_booked': 'meeting_booked',
            'not_interested': 'not_interested',
            'bounce': 'bounced',
            'bounced': 'bounced',
        }

        for key, value in mapping.items():
            if key in status_lower:
                return value

        return None
