"""
Modèles SQLite pour le module GetSales.
"""
import json
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

# Chemin par défaut de la base
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "getsales.db"


@dataclass
class PendingLead:
    """Lead en attente de validation."""
    id: Optional[int] = None
    getsales_uuid: str = ""
    getsales_data: Dict[str, Any] = field(default_factory=dict)
    hubspot_matches: List[Dict[str, Any]] = field(default_factory=list)
    local_matches: List[Dict[str, Any]] = field(default_factory=list)  # Doublons dans unified_contacts
    company_matches: List[Dict[str, Any]] = field(default_factory=list)  # Companies HubSpot potentielles
    duplicate_status: str = "none"  # none, potential, confirmed
    validation_status: str = "pending"  # pending, approved, rejected
    merge_decision: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    validated_at: Optional[str] = None
    rejection_reason: Optional[str] = None


@dataclass
class SyncLog:
    """Log de synchronisation."""
    id: Optional[int] = None
    sync_date: Optional[str] = None
    leads_fetched: int = 0
    leads_validated: int = 0
    leads_rejected: int = 0
    leads_created: int = 0
    leads_updated: int = 0
    status: str = "running"  # running, completed, failed
    error_message: Optional[str] = None


@dataclass
class LeadInteraction:
    """Interaction LinkedIn."""
    id: Optional[int] = None
    getsales_lead_uuid: str = ""
    hubspot_contact_id: Optional[str] = None
    interaction_type: str = ""  # message_sent, message_read, reply_received
    interaction_date: Optional[str] = None
    message_text: Optional[str] = None
    flow_name: Optional[str] = None
    synced_to_hubspot: bool = False
    created_at: Optional[str] = None


class GetSalesDB:
    """
    Gestionnaire de base de données SQLite pour GetSales.

    Usage:
        db = GetSalesDB()
        db.save_pending_lead(lead)
        pending = db.get_pending_leads(status='pending')
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialise la connexion à la base de données.

        Args:
            db_path: Chemin vers le fichier SQLite (optionnel)
        """
        self.db_path = db_path or str(DEFAULT_DB_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Crée une connexion SQLite."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialise les tables si elles n'existent pas."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Table pending_leads
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pending_leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    getsales_uuid TEXT UNIQUE NOT NULL,
                    getsales_data TEXT NOT NULL,
                    hubspot_matches TEXT DEFAULT '[]',
                    local_matches TEXT DEFAULT '[]',
                    duplicate_status TEXT DEFAULT 'none',
                    validation_status TEXT DEFAULT 'pending',
                    merge_decision TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    validated_at TEXT,
                    rejection_reason TEXT
                )
            """)

            # Migration: ajouter colonnes si elles n'existent pas
            cursor.execute("PRAGMA table_info(pending_leads)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'local_matches' not in columns:
                cursor.execute("ALTER TABLE pending_leads ADD COLUMN local_matches TEXT DEFAULT '[]'")
            if 'company_matches' not in columns:
                cursor.execute("ALTER TABLE pending_leads ADD COLUMN company_matches TEXT DEFAULT '[]'")

            # Index sur getsales_uuid et validation_status
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pending_uuid
                ON pending_leads(getsales_uuid)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pending_status
                ON pending_leads(validation_status)
            """)

            # Table sync_logs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sync_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    leads_fetched INTEGER DEFAULT 0,
                    leads_validated INTEGER DEFAULT 0,
                    leads_rejected INTEGER DEFAULT 0,
                    leads_created INTEGER DEFAULT 0,
                    leads_updated INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running',
                    error_message TEXT
                )
            """)

            # Table lead_interactions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lead_interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    getsales_lead_uuid TEXT NOT NULL,
                    hubspot_contact_id TEXT,
                    interaction_type TEXT,
                    interaction_date TEXT,
                    message_text TEXT,
                    flow_name TEXT,
                    synced_to_hubspot INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_interactions_lead
                ON lead_interactions(getsales_lead_uuid)
            """)

            conn.commit()
            logger.info(f"Base GetSales initialisée: {self.db_path}")

    # ========== PendingLead CRUD ==========

    def save_pending_lead(self, lead: PendingLead) -> int:
        """
        Sauvegarde un lead en attente (insert ou update).

        Args:
            lead: PendingLead à sauvegarder

        Returns:
            ID du lead
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            getsales_data_json = json.dumps(lead.getsales_data, ensure_ascii=False)
            hubspot_matches_json = json.dumps(lead.hubspot_matches, ensure_ascii=False)
            local_matches_json = json.dumps(lead.local_matches, ensure_ascii=False)
            company_matches_json = json.dumps(lead.company_matches, ensure_ascii=False)
            merge_decision_json = json.dumps(lead.merge_decision) if lead.merge_decision else None

            if lead.id:
                # Update
                cursor.execute("""
                    UPDATE pending_leads SET
                        getsales_data = ?,
                        hubspot_matches = ?,
                        local_matches = ?,
                        company_matches = ?,
                        duplicate_status = ?,
                        validation_status = ?,
                        merge_decision = ?,
                        validated_at = ?,
                        rejection_reason = ?
                    WHERE id = ?
                """, (
                    getsales_data_json,
                    hubspot_matches_json,
                    local_matches_json,
                    company_matches_json,
                    lead.duplicate_status,
                    lead.validation_status,
                    merge_decision_json,
                    lead.validated_at,
                    lead.rejection_reason,
                    lead.id
                ))
                conn.commit()
                return lead.id
            else:
                # Insert
                try:
                    cursor.execute("""
                        INSERT INTO pending_leads
                        (getsales_uuid, getsales_data, hubspot_matches, local_matches, company_matches, duplicate_status, validation_status)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        lead.getsales_uuid,
                        getsales_data_json,
                        hubspot_matches_json,
                        local_matches_json,
                        company_matches_json,
                        lead.duplicate_status,
                        lead.validation_status
                    ))
                    conn.commit()
                    return cursor.lastrowid
                except sqlite3.IntegrityError:
                    # UUID déjà existe, update
                    cursor.execute("""
                        UPDATE pending_leads SET
                            getsales_data = ?,
                            hubspot_matches = ?,
                            local_matches = ?,
                            company_matches = ?,
                            duplicate_status = ?
                        WHERE getsales_uuid = ?
                    """, (
                        getsales_data_json,
                        hubspot_matches_json,
                        local_matches_json,
                        company_matches_json,
                        lead.duplicate_status,
                        lead.getsales_uuid
                    ))
                    conn.commit()

                    cursor.execute(
                        "SELECT id FROM pending_leads WHERE getsales_uuid = ?",
                        (lead.getsales_uuid,)
                    )
                    row = cursor.fetchone()
                    return row['id'] if row else 0

    def get_pending_lead(self, lead_id: int) -> Optional[PendingLead]:
        """Récupère un lead par son ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pending_leads WHERE id = ?", (lead_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_pending_lead(row)

    def get_pending_lead_by_uuid(self, getsales_uuid: str) -> Optional[PendingLead]:
        """Récupère un lead par son UUID GetSales."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM pending_leads WHERE getsales_uuid = ?",
                (getsales_uuid,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_pending_lead(row)

    def get_pending_leads(
        self,
        status: Optional[str] = None,
        duplicate_status: Optional[str] = None,
        limit: int = 100
    ) -> List[PendingLead]:
        """
        Récupère les leads en attente.

        Args:
            status: Filtrer par validation_status
            duplicate_status: Filtrer par duplicate_status
            limit: Nombre max de résultats

        Returns:
            Liste de PendingLead
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM pending_leads WHERE 1=1"
            params = []

            if status:
                query += " AND validation_status = ?"
                params.append(status)

            if duplicate_status:
                if duplicate_status == "with_duplicates":
                    query += " AND duplicate_status != 'none'"
                elif duplicate_status == "no_duplicates":
                    query += " AND duplicate_status = 'none'"
                else:
                    query += " AND duplicate_status = ?"
                    params.append(duplicate_status)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [self._row_to_pending_lead(row) for row in rows]

    def _row_to_pending_lead(self, row: sqlite3.Row) -> PendingLead:
        """Convertit une row SQLite en PendingLead."""
        # Gérer les colonnes avec fallback pour anciennes entrées
        columns = row.keys()
        local_matches_raw = row['local_matches'] if 'local_matches' in columns else '[]'
        company_matches_raw = row['company_matches'] if 'company_matches' in columns else '[]'
        return PendingLead(
            id=row['id'],
            getsales_uuid=row['getsales_uuid'],
            getsales_data=json.loads(row['getsales_data']),
            hubspot_matches=json.loads(row['hubspot_matches']),
            local_matches=json.loads(local_matches_raw) if local_matches_raw else [],
            company_matches=json.loads(company_matches_raw) if company_matches_raw else [],
            duplicate_status=row['duplicate_status'],
            validation_status=row['validation_status'],
            merge_decision=json.loads(row['merge_decision']) if row['merge_decision'] else None,
            created_at=row['created_at'],
            validated_at=row['validated_at'],
            rejection_reason=row['rejection_reason']
        )

    def update_lead_status(
        self,
        lead_id: int,
        status: str,
        merge_decision: Optional[Dict] = None,
        rejection_reason: Optional[str] = None
    ):
        """Met à jour le statut d'un lead."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            merge_json = json.dumps(merge_decision) if merge_decision else None
            validated_at = datetime.now().isoformat() if status in ('approved', 'rejected') else None

            cursor.execute("""
                UPDATE pending_leads SET
                    validation_status = ?,
                    merge_decision = ?,
                    validated_at = ?,
                    rejection_reason = ?
                WHERE id = ?
            """, (status, merge_json, validated_at, rejection_reason, lead_id))

            conn.commit()

    def get_pending_stats(self) -> Dict[str, int]:
        """Retourne les statistiques des leads en attente."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN validation_status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN validation_status = 'approved' THEN 1 ELSE 0 END) as approved,
                    SUM(CASE WHEN validation_status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                    SUM(CASE WHEN duplicate_status != 'none' THEN 1 ELSE 0 END) as with_duplicates
                FROM pending_leads
            """)

            row = cursor.fetchone()
            return {
                'total': row['total'] or 0,
                'pending': row['pending'] or 0,
                'approved': row['approved'] or 0,
                'rejected': row['rejected'] or 0,
                'with_duplicates': row['with_duplicates'] or 0
            }

    # ========== SyncLog CRUD ==========

    def create_sync_log(self, leads_fetched: int = 0, status: str = "running") -> int:
        """Crée un nouveau log de sync."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sync_logs (leads_fetched, status)
                VALUES (?, ?)
            """, (leads_fetched, status))
            conn.commit()
            return cursor.lastrowid

    def update_sync_log(
        self,
        log_id: int,
        status: str,
        leads_fetched: Optional[int] = None,
        leads_created: Optional[int] = None,
        leads_updated: Optional[int] = None,
        error_message: Optional[str] = None
    ):
        """Met à jour un log de sync."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            updates = ["status = ?"]
            params = [status]

            if leads_fetched is not None:
                updates.append("leads_fetched = ?")
                params.append(leads_fetched)

            if leads_created is not None:
                updates.append("leads_created = ?")
                params.append(leads_created)

            if leads_updated is not None:
                updates.append("leads_updated = ?")
                params.append(leads_updated)

            if error_message is not None:
                updates.append("error_message = ?")
                params.append(error_message)

            params.append(log_id)

            cursor.execute(f"""
                UPDATE sync_logs SET {', '.join(updates)}
                WHERE id = ?
            """, params)

            conn.commit()

    def get_last_sync(self) -> Optional[SyncLog]:
        """Récupère le dernier log de sync."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM sync_logs
                ORDER BY sync_date DESC
                LIMIT 1
            """)
            row = cursor.fetchone()

            if not row:
                return None

            return SyncLog(
                id=row['id'],
                sync_date=row['sync_date'],
                leads_fetched=row['leads_fetched'],
                leads_validated=row['leads_validated'],
                leads_rejected=row['leads_rejected'],
                leads_created=row['leads_created'],
                leads_updated=row['leads_updated'],
                status=row['status'],
                error_message=row['error_message']
            )

    # ========== LeadInteraction CRUD ==========

    def save_interaction(self, interaction: LeadInteraction) -> int:
        """Sauvegarde une interaction."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO lead_interactions
                (getsales_lead_uuid, hubspot_contact_id, interaction_type,
                 interaction_date, message_text, flow_name, synced_to_hubspot)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                interaction.getsales_lead_uuid,
                interaction.hubspot_contact_id,
                interaction.interaction_type,
                interaction.interaction_date,
                interaction.message_text,
                interaction.flow_name,
                1 if interaction.synced_to_hubspot else 0
            ))
            conn.commit()
            return cursor.lastrowid

    def get_unsynced_interactions(self, lead_uuid: str) -> List[LeadInteraction]:
        """Récupère les interactions non encore sync vers HubSpot."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM lead_interactions
                WHERE getsales_lead_uuid = ? AND synced_to_hubspot = 0
            """, (lead_uuid,))

            rows = cursor.fetchall()
            return [
                LeadInteraction(
                    id=row['id'],
                    getsales_lead_uuid=row['getsales_lead_uuid'],
                    hubspot_contact_id=row['hubspot_contact_id'],
                    interaction_type=row['interaction_type'],
                    interaction_date=row['interaction_date'],
                    message_text=row['message_text'],
                    flow_name=row['flow_name'],
                    synced_to_hubspot=bool(row['synced_to_hubspot']),
                    created_at=row['created_at']
                )
                for row in rows
            ]

    def mark_interaction_synced(self, interaction_id: int):
        """Marque une interaction comme synchronisée."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE lead_interactions
                SET synced_to_hubspot = 1
                WHERE id = ?
            """, (interaction_id,))
            conn.commit()
