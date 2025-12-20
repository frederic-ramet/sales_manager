"""
ContactManager - Gestionnaire unifié des contacts multi-sources.

Remplace LeadTracker avec une table unifiée `unified_contacts`
supportant les sources : sirene, hubspot, getsales.
"""

import sqlite3
import logging
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Set, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Chemin par défaut de la base de données
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "leads.db"


class ContactManager:
    """
    Gestionnaire unifié des contacts multi-sources.

    Supporte 3 sources :
    - sirene : Extraction API SIRENE/INSEE
    - hubspot : Import depuis HubSpot CRM
    - getsales : Leads LinkedIn validés via GetSales

    Usage:
        manager = ContactManager()
        manager.add_contact({...}, source='sirene')
        contacts = manager.search(source='hubspot', enriched=False)
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialise le gestionnaire.

        Args:
            db_path: Chemin vers la base de données SQLite (optionnel)
        """
        self.db_path = db_path or str(DEFAULT_DB_PATH)

        # Créer le dossier si nécessaire
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialiser la base de données
        self._init_db()

    def _init_db(self):
        """Crée la table unified_contacts si elle n'existe pas."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Table unifiée des contacts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS unified_contacts (
                    -- Identifiants
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid TEXT UNIQUE NOT NULL,

                    -- Liens sources externes
                    siren TEXT,
                    siret TEXT,
                    getsales_uuid TEXT,
                    hubspot_contact_id TEXT,
                    hubspot_company_id TEXT,

                    -- Métadonnées
                    source TEXT NOT NULL,
                    campaign_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    -- === ENTREPRISE ===
                    company_name TEXT,
                    ape_code TEXT,
                    ape_label TEXT,
                    legal_form TEXT,

                    -- Adresse
                    address TEXT,
                    postal_code TEXT,
                    city TEXT,
                    region TEXT,
                    country TEXT DEFAULT 'FR',

                    -- Infos entreprise
                    employee_range TEXT,
                    revenue_range TEXT,
                    website TEXT,

                    -- === CONTACT ===
                    firstname TEXT,
                    lastname TEXT,
                    email TEXT,
                    phone TEXT,
                    mobile TEXT,
                    job_title TEXT,

                    -- LinkedIn
                    linkedin_url TEXT,
                    linkedin_headline TEXT,

                    -- === ENRICHISSEMENT ===
                    enriched_at TIMESTAMP,
                    enrichment_source TEXT,

                    -- === SYNC HUBSPOT ===
                    synced_to_hubspot INTEGER DEFAULT 0,
                    last_sync_hubspot TIMESTAMP,

                    -- === PROSPECTION (GetSales) ===
                    prospection_status TEXT,
                    messages_sent INTEGER DEFAULT 0,
                    messages_received INTEGER DEFAULT 0,
                    last_interaction_at TIMESTAMP,

                    -- === STATUT ===
                    status TEXT DEFAULT 'active',
                    notes TEXT,

                    -- JSON pour données brutes complètes
                    raw_data TEXT
                )
            """)

            # Indexes pour performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_uc_source ON unified_contacts(source)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_uc_email ON unified_contacts(email)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_uc_siren ON unified_contacts(siren)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_uc_campaign ON unified_contacts(campaign_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_uc_hubspot ON unified_contacts(hubspot_contact_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_uc_linkedin ON unified_contacts(linkedin_url)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_uc_status ON unified_contacts(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_uc_created ON unified_contacts(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_uc_getsales ON unified_contacts(getsales_uuid)")

            conn.commit()

        logger.info(f"Base de données initialisée: {self.db_path}")

    def _generate_uuid(self) -> str:
        """Génère un UUID unique."""
        return str(uuid.uuid4())

    # =========================================================================
    # CRUD
    # =========================================================================

    def add_contact(self, data: Dict[str, Any], source: str) -> str:
        """
        Ajoute un nouveau contact.

        Args:
            data: Données du contact
            source: Source (sirene, hubspot, getsales)

        Returns:
            UUID du contact créé
        """
        contact_uuid = self._generate_uuid()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO unified_contacts (
                    uuid, source, campaign_id,
                    siren, siret, getsales_uuid, hubspot_contact_id, hubspot_company_id,
                    company_name, ape_code, ape_label, legal_form,
                    address, postal_code, city, region, country,
                    employee_range, revenue_range, website,
                    firstname, lastname, email, phone, mobile, job_title,
                    linkedin_url, linkedin_headline,
                    enriched_at, enrichment_source,
                    synced_to_hubspot, last_sync_hubspot,
                    prospection_status, messages_sent, messages_received, last_interaction_at,
                    status, notes, raw_data
                ) VALUES (
                    ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?
                )
            """, (
                contact_uuid,
                source.lower(),
                data.get('campaign_id'),
                data.get('siren'),
                data.get('siret'),
                data.get('getsales_uuid'),
                data.get('hubspot_contact_id'),
                data.get('hubspot_company_id'),
                data.get('company_name') or data.get('denomination'),
                data.get('ape_code') or data.get('code_ape'),
                data.get('ape_label'),
                data.get('legal_form'),
                data.get('address'),
                data.get('postal_code'),
                data.get('city') or data.get('ville'),
                data.get('region'),
                data.get('country', 'FR'),
                data.get('employee_range'),
                data.get('revenue_range'),
                data.get('website'),
                data.get('firstname'),
                data.get('lastname'),
                data.get('email'),
                data.get('phone') or data.get('telephone'),
                data.get('mobile'),
                data.get('job_title'),
                data.get('linkedin_url'),
                data.get('linkedin_headline'),
                data.get('enriched_at'),
                data.get('enrichment_source'),
                1 if data.get('synced_to_hubspot') else 0,
                data.get('last_sync_hubspot'),
                data.get('prospection_status'),
                data.get('messages_sent', 0),
                data.get('messages_received', 0),
                data.get('last_interaction_at'),
                data.get('status', 'active'),
                data.get('notes'),
                json.dumps(data, ensure_ascii=False, default=str)
            ))

            conn.commit()

        logger.info(f"Contact ajouté: {contact_uuid} (source: {source})")
        return contact_uuid

    def update_contact(self, contact_uuid: str, data: Dict[str, Any]) -> bool:
        """
        Met à jour un contact existant.

        Args:
            contact_uuid: UUID du contact
            data: Données à mettre à jour

        Returns:
            True si mis à jour, False sinon
        """
        # Mapping des clés vers les colonnes
        field_mapping = {
            'siren': 'siren',
            'siret': 'siret',
            'getsales_uuid': 'getsales_uuid',
            'hubspot_contact_id': 'hubspot_contact_id',
            'hubspot_company_id': 'hubspot_company_id',
            'company_name': 'company_name',
            'denomination': 'company_name',
            'ape_code': 'ape_code',
            'code_ape': 'ape_code',
            'ape_label': 'ape_label',
            'legal_form': 'legal_form',
            'address': 'address',
            'postal_code': 'postal_code',
            'city': 'city',
            'ville': 'city',
            'region': 'region',
            'country': 'country',
            'employee_range': 'employee_range',
            'revenue_range': 'revenue_range',
            'website': 'website',
            'firstname': 'firstname',
            'lastname': 'lastname',
            'email': 'email',
            'phone': 'phone',
            'telephone': 'phone',
            'mobile': 'mobile',
            'job_title': 'job_title',
            'linkedin_url': 'linkedin_url',
            'linkedin_headline': 'linkedin_headline',
            'enriched_at': 'enriched_at',
            'enrichment_source': 'enrichment_source',
            'synced_to_hubspot': 'synced_to_hubspot',
            'last_sync_hubspot': 'last_sync_hubspot',
            'prospection_status': 'prospection_status',
            'messages_sent': 'messages_sent',
            'messages_received': 'messages_received',
            'last_interaction_at': 'last_interaction_at',
            'status': 'status',
            'notes': 'notes',
        }

        fields_to_update = []
        values = []

        for key, col in field_mapping.items():
            if key in data and data[key] is not None:
                fields_to_update.append(f"{col} = ?")
                values.append(data[key])

        # Toujours mettre à jour updated_at
        fields_to_update.append("updated_at = ?")
        values.append(datetime.now())

        if not fields_to_update:
            return False

        values.append(contact_uuid)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            query = f"UPDATE unified_contacts SET {', '.join(fields_to_update)} WHERE uuid = ?"
            cursor.execute(query, values)
            conn.commit()
            return cursor.rowcount > 0

    def get_contact(self, contact_uuid: str) -> Optional[Dict[str, Any]]:
        """
        Récupère un contact par UUID.

        Args:
            contact_uuid: UUID du contact

        Returns:
            Dict du contact ou None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM unified_contacts WHERE uuid = ?", (contact_uuid,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def delete_contact(self, contact_uuid: str, hard_delete: bool = False) -> bool:
        """
        Supprime un contact (soft delete par défaut).

        Args:
            contact_uuid: UUID du contact
            hard_delete: Si True, suppression définitive

        Returns:
            True si supprimé
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if hard_delete:
                cursor.execute("DELETE FROM unified_contacts WHERE uuid = ?", (contact_uuid,))
            else:
                cursor.execute(
                    "UPDATE unified_contacts SET status = 'deleted', updated_at = ? WHERE uuid = ?",
                    (datetime.now(), contact_uuid)
                )

            conn.commit()
            return cursor.rowcount > 0

    # =========================================================================
    # RECHERCHE
    # =========================================================================

    def search(
        self,
        query: str = None,
        source: str = None,
        enriched: bool = None,
        synced: bool = None,
        status: str = 'active',
        campaign_id: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Recherche des contacts avec filtres.

        Args:
            query: Recherche texte (siren, nom, email, entreprise)
            source: Filtrer par source (sirene, hubspot, getsales)
            enriched: Filtrer par statut enrichissement
            synced: Filtrer par statut sync HubSpot
            status: Statut (active, archived, deleted)
            campaign_id: Filtrer par campagne
            limit: Nombre max de résultats
            offset: Offset pour pagination

        Returns:
            Liste de contacts
        """
        conditions = []
        params = []

        if status:
            conditions.append("status = ?")
            params.append(status)

        if source:
            conditions.append("source = ?")
            params.append(source.lower())

        if campaign_id:
            conditions.append("campaign_id = ?")
            params.append(campaign_id)

        if enriched is not None:
            if enriched:
                conditions.append("enriched_at IS NOT NULL")
            else:
                conditions.append("enriched_at IS NULL")

        if synced is not None:
            if synced:
                conditions.append("synced_to_hubspot = 1")
            else:
                conditions.append("synced_to_hubspot = 0")

        if query:
            conditions.append("""
                (siren LIKE ? OR company_name LIKE ? OR email LIKE ?
                 OR firstname LIKE ? OR lastname LIKE ? OR linkedin_url LIKE ?)
            """)
            search_term = f"%{query}%"
            params.extend([search_term] * 6)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            sql = f"""
                SELECT * FROM unified_contacts
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])

            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère des statistiques globales.

        Returns:
            Dict avec stats (total, par source, enrichis, etc.)
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Total actifs
            cursor.execute("SELECT COUNT(*) FROM unified_contacts WHERE status = 'active'")
            total = cursor.fetchone()[0]

            # Par source
            cursor.execute("""
                SELECT source, COUNT(*) as count
                FROM unified_contacts
                WHERE status = 'active'
                GROUP BY source
            """)
            by_source = {row[0]: row[1] for row in cursor.fetchall()}

            # Enrichis
            cursor.execute("""
                SELECT COUNT(*) FROM unified_contacts
                WHERE status = 'active' AND enriched_at IS NOT NULL
            """)
            enriched_count = cursor.fetchone()[0]

            # Synced HubSpot
            cursor.execute("""
                SELECT COUNT(*) FROM unified_contacts
                WHERE status = 'active' AND synced_to_hubspot = 1
            """)
            hubspot_synced = cursor.fetchone()[0]

            # Nombre de campagnes
            cursor.execute("SELECT COUNT(DISTINCT campaign_id) FROM unified_contacts WHERE campaign_id IS NOT NULL")
            num_campaigns = cursor.fetchone()[0]

            # Dernier contact
            cursor.execute("""
                SELECT created_at FROM unified_contacts
                WHERE status = 'active'
                ORDER BY created_at DESC LIMIT 1
            """)
            row = cursor.fetchone()
            last_contact = row[0] if row else None

            # Campagnes récentes
            cursor.execute("""
                SELECT campaign_id, COUNT(*) as count, MAX(created_at) as date
                FROM unified_contacts
                WHERE campaign_id IS NOT NULL AND status = 'active'
                GROUP BY campaign_id
                ORDER BY date DESC
                LIMIT 10
            """)
            campaigns = [
                {'campaign_id': row[0], 'count': row[1], 'date': row[2]}
                for row in cursor.fetchall()
            ]

            return {
                'total_contacts': total,
                'by_source': by_source,
                'enriched_count': enriched_count,
                'hubspot_synced': hubspot_synced,
                'num_campaigns': num_campaigns,
                'last_contact': last_contact,
                'campaigns_recent': campaigns,
                # Alias pour compatibilité
                'total_leads': total,
                'dernier_lead': last_contact,
                'campagnes_recentes': campaigns,
            }

    # =========================================================================
    # DÉDUPLICATION
    # =========================================================================

    def find_duplicate(
        self,
        email: str = None,
        siren: str = None,
        linkedin_url: str = None,
        hubspot_contact_id: str = None,
        getsales_uuid: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Trouve un doublon potentiel par clés uniques.

        Ordre de priorité :
        1. hubspot_contact_id
        2. getsales_uuid
        3. linkedin_url
        4. email
        5. siren

        Returns:
            Contact existant ou None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 1. Par HubSpot ID
            if hubspot_contact_id:
                cursor.execute(
                    "SELECT * FROM unified_contacts WHERE hubspot_contact_id = ? AND status = 'active'",
                    (hubspot_contact_id,)
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)

            # 2. Par GetSales UUID
            if getsales_uuid:
                cursor.execute(
                    "SELECT * FROM unified_contacts WHERE getsales_uuid = ? AND status = 'active'",
                    (getsales_uuid,)
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)

            # 3. Par LinkedIn URL
            if linkedin_url:
                # Normaliser l'URL LinkedIn
                normalized = self._normalize_linkedin_url(linkedin_url)
                cursor.execute(
                    "SELECT * FROM unified_contacts WHERE linkedin_url = ? AND status = 'active'",
                    (normalized,)
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)

            # 4. Par Email
            if email:
                email_lower = email.lower().strip()
                cursor.execute(
                    "SELECT * FROM unified_contacts WHERE LOWER(email) = ? AND status = 'active'",
                    (email_lower,)
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)

            # 5. Par SIREN
            if siren:
                cursor.execute(
                    "SELECT * FROM unified_contacts WHERE siren = ? AND status = 'active'",
                    (siren,)
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)

            return None

    def _normalize_linkedin_url(self, url: str) -> str:
        """Normalise une URL LinkedIn."""
        if not url:
            return url
        # Enlever trailing slash et paramètres
        url = url.split('?')[0].rstrip('/')
        # S'assurer du format https
        if url.startswith('http://'):
            url = url.replace('http://', 'https://')
        return url

    def get_duplicates_batch(self, sirens: List[str]) -> Set[str]:
        """
        Trouve tous les SIREN déjà présents.

        Args:
            sirens: Liste de SIREN à vérifier

        Returns:
            Set des SIREN déjà en base
        """
        if not sirens:
            return set()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(sirens))
            cursor.execute(
                f"SELECT siren FROM unified_contacts WHERE siren IN ({placeholders}) AND status = 'active'",
                sirens
            )
            return {row[0] for row in cursor.fetchall()}

    def filter_duplicates(self, companies: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
        """
        Filtre les entreprises déjà présentes (par SIREN).

        Args:
            companies: Liste d'entreprises

        Returns:
            Tuple (entreprises filtrées, nombre de doublons)
        """
        if not companies:
            return [], 0

        sirens = [c.get('siren') for c in companies if c.get('siren')]
        duplicates = self.get_duplicates_batch(sirens)

        filtered = [c for c in companies if c.get('siren') not in duplicates]
        num_dups = len(companies) - len(filtered)

        if num_dups > 0:
            logger.info(f"Filtré {num_dups} doublons sur {len(companies)} entreprises")

        return filtered, num_dups

    # =========================================================================
    # ENRICHISSEMENT
    # =========================================================================

    def mark_enriched(self, contact_uuid: str, source: str = 'pappers') -> bool:
        """
        Marque un contact comme enrichi.

        Args:
            contact_uuid: UUID du contact
            source: Source d'enrichissement (pappers, manual, etc.)

        Returns:
            True si mis à jour
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE unified_contacts
                SET enriched_at = ?, enrichment_source = ?, updated_at = ?
                WHERE uuid = ?
            """, (datetime.now(), source, datetime.now(), contact_uuid))
            conn.commit()
            return cursor.rowcount > 0

    def get_contacts_to_enrich(self, limit: int = 50, source: str = None) -> List[Dict[str, Any]]:
        """
        Récupère les contacts non enrichis.

        Args:
            limit: Nombre max
            source: Filtrer par source

        Returns:
            Liste de contacts à enrichir
        """
        return self.search(
            enriched=False,
            source=source,
            limit=limit
        )

    # =========================================================================
    # HUBSPOT
    # =========================================================================

    def mark_synced_hubspot(self, contact_uuid: str, hubspot_id: str) -> bool:
        """
        Marque un contact comme synchronisé vers HubSpot.

        Args:
            contact_uuid: UUID du contact
            hubspot_id: ID HubSpot du contact

        Returns:
            True si mis à jour
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE unified_contacts
                SET hubspot_contact_id = ?, synced_to_hubspot = 1, last_sync_hubspot = ?, updated_at = ?
                WHERE uuid = ?
            """, (hubspot_id, datetime.now(), datetime.now(), contact_uuid))
            conn.commit()
            return cursor.rowcount > 0

    def get_contacts_to_sync(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Récupère les contacts enrichis non encore synchronisés.

        Returns:
            Liste de contacts à pousser vers HubSpot
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM unified_contacts
                WHERE status = 'active'
                  AND enriched_at IS NOT NULL
                  AND synced_to_hubspot = 0
                ORDER BY enriched_at DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    # =========================================================================
    # IMPORT SOURCES
    # =========================================================================

    def import_from_sirene(
        self,
        leads: List[Dict[str, Any]],
        campaign_id: str = None
    ) -> Tuple[int, int]:
        """
        Import batch depuis extraction SIRENE.

        Args:
            leads: Liste de leads SIRENE
            campaign_id: ID de campagne (auto-généré si None)

        Returns:
            Tuple (ajoutés, doublons)
        """
        if not campaign_id:
            campaign_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Filtrer les doublons
        filtered, num_dups = self.filter_duplicates(leads)

        added = 0
        for lead in filtered:
            lead['campaign_id'] = campaign_id
            try:
                self.add_contact(lead, source='sirene')
                added += 1
            except Exception as e:
                logger.error(f"Erreur ajout lead SIRENE {lead.get('siren')}: {e}")

        logger.info(f"Import SIRENE: {added} ajoutés, {num_dups} doublons (campagne: {campaign_id})")
        return added, num_dups

    def import_from_getsales(self, lead_data: Dict[str, Any]) -> str:
        """
        Import d'un lead GetSales validé.

        Args:
            lead_data: Données du lead GetSales

        Returns:
            UUID du contact créé ou existant
        """
        # Vérifier doublon
        duplicate = self.find_duplicate(
            email=lead_data.get('email'),
            linkedin_url=lead_data.get('linkedin_url'),
            getsales_uuid=lead_data.get('getsales_uuid')
        )

        if duplicate:
            # Enrichir le contact existant
            self.update_contact(duplicate['uuid'], {
                'getsales_uuid': lead_data.get('getsales_uuid'),
                'linkedin_url': lead_data.get('linkedin_url'),
                'linkedin_headline': lead_data.get('linkedin_headline'),
                'prospection_status': lead_data.get('prospection_status'),
                'messages_sent': lead_data.get('messages_sent', 0),
                'messages_received': lead_data.get('messages_received', 0),
                'last_interaction_at': lead_data.get('last_interaction_at'),
            })
            logger.info(f"Lead GetSales fusionné avec contact existant: {duplicate['uuid']}")
            return duplicate['uuid']
        else:
            # Créer nouveau contact
            contact_uuid = self.add_contact(lead_data, source='getsales')
            logger.info(f"Lead GetSales importé: {contact_uuid}")
            return contact_uuid

    def import_from_hubspot(self, contacts: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Import batch depuis HubSpot.

        Args:
            contacts: Liste de contacts HubSpot

        Returns:
            Tuple (ajoutés, mis à jour)
        """
        added = 0
        updated = 0

        for contact in contacts:
            # Vérifier doublon
            duplicate = self.find_duplicate(
                hubspot_contact_id=contact.get('hubspot_contact_id') or contact.get('id'),
                email=contact.get('email')
            )

            if duplicate:
                # Mettre à jour
                self.update_contact(duplicate['uuid'], {
                    'hubspot_contact_id': contact.get('hubspot_contact_id') or contact.get('id'),
                    'synced_to_hubspot': True,
                    'last_sync_hubspot': datetime.now(),
                    **{k: v for k, v in contact.items() if k not in ['id', 'hubspot_contact_id']}
                })
                updated += 1
            else:
                # Créer
                contact['hubspot_contact_id'] = contact.get('hubspot_contact_id') or contact.get('id')
                contact['synced_to_hubspot'] = True
                contact['last_sync_hubspot'] = datetime.now()
                self.add_contact(contact, source='hubspot')
                added += 1

        logger.info(f"Import HubSpot: {added} ajoutés, {updated} mis à jour")
        return added, updated

    # =========================================================================
    # EXPORT
    # =========================================================================

    def export_for_hubspot(self, contact_uuids: List[str]) -> List[Dict[str, Any]]:
        """
        Prépare les données pour push vers HubSpot.

        Args:
            contact_uuids: Liste d'UUIDs à exporter

        Returns:
            Liste de dicts formatés pour l'API HubSpot
        """
        contacts = []

        for uuid in contact_uuids:
            contact = self.get_contact(uuid)
            if not contact:
                continue

            # Mapper vers format HubSpot
            hubspot_data = {
                'properties': {
                    'email': contact.get('email'),
                    'firstname': contact.get('firstname'),
                    'lastname': contact.get('lastname'),
                    'phone': contact.get('phone'),
                    'mobilephone': contact.get('mobile'),
                    'jobtitle': contact.get('job_title'),
                    'company': contact.get('company_name'),
                    'website': contact.get('website'),
                    'address': contact.get('address'),
                    'city': contact.get('city'),
                    'zip': contact.get('postal_code'),
                    'country': contact.get('country'),
                    # Custom properties
                    'siren': contact.get('siren'),
                    'siret': contact.get('siret'),
                    'linkedin_url': contact.get('linkedin_url'),
                    'code_ape': contact.get('ape_code'),
                }
            }

            # Filtrer les valeurs None
            hubspot_data['properties'] = {
                k: v for k, v in hubspot_data['properties'].items() if v
            }

            hubspot_data['_uuid'] = uuid
            contacts.append(hubspot_data)

        return contacts

    # =========================================================================
    # GESTION
    # =========================================================================

    def clear_all(self, confirm: bool = False) -> int:
        """
        Supprime tous les contacts (hard delete).

        Args:
            confirm: Doit être True pour confirmer

        Returns:
            Nombre de contacts supprimés
        """
        if not confirm:
            raise ValueError("Confirmation requise: clear_all(confirm=True)")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM unified_contacts")
            deleted = cursor.rowcount
            conn.commit()

        logger.warning(f"Supprimé {deleted} contacts (hard delete)")
        return deleted

    def delete_campaign(self, campaign_id: str) -> int:
        """
        Supprime tous les contacts d'une campagne.

        Args:
            campaign_id: ID de la campagne

        Returns:
            Nombre de contacts supprimés
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM unified_contacts WHERE campaign_id = ?",
                (campaign_id,)
            )
            deleted = cursor.rowcount
            conn.commit()

        logger.info(f"Supprimé {deleted} contacts de la campagne {campaign_id}")
        return deleted

    def archive_old_contacts(self, older_than_days: int = 90) -> int:
        """
        Archive les contacts plus vieux que N jours.

        Args:
            older_than_days: Nombre de jours

        Returns:
            Nombre de contacts archivés
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE unified_contacts
                SET status = 'archived', updated_at = ?
                WHERE status = 'active'
                  AND created_at < datetime('now', '-' || ? || ' days')
            """, (datetime.now(), older_than_days))
            archived = cursor.rowcount
            conn.commit()

        logger.info(f"Archivé {archived} contacts plus vieux que {older_than_days} jours")
        return archived

    # =========================================================================
    # COMPATIBILITÉ LEGACY (pour transition)
    # =========================================================================

    def add_leads(
        self,
        companies: List[Dict[str, Any]],
        campagne_id: str = None,
        source: str = "sirene"
    ) -> int:
        """
        Méthode legacy pour compatibilité avec LeadTracker.
        Utilise import_from_sirene en interne.
        """
        added, _ = self.import_from_sirene(companies, campaign_id=campagne_id)
        return added

    def get_history(
        self,
        limit: int = 100,
        offset: int = 0,
        campagne_id: str = None,
        source: str = None,
        search: str = None
    ) -> List[Dict[str, Any]]:
        """
        Méthode legacy pour compatibilité avec LeadTracker.
        """
        results = self.search(
            query=search,
            source=source,
            campaign_id=campagne_id,
            limit=limit,
            offset=offset
        )

        # Mapper les champs pour compatibilité
        for r in results:
            r['denomination'] = r.get('company_name')
            r['code_ape'] = r.get('ape_code')
            r['ville'] = r.get('city')
            r['date_extraction'] = r.get('created_at')
            r['campagne_id'] = r.get('campaign_id')

        return results

    def get_total_count(self) -> int:
        """Méthode legacy."""
        stats = self.get_stats()
        return stats['total_contacts']

    def is_duplicate(self, siren: str) -> bool:
        """Méthode legacy."""
        return self.find_duplicate(siren=siren) is not None

    def clear_history(self, older_than_days: int = None) -> int:
        """Méthode legacy."""
        if older_than_days:
            return self.archive_old_contacts(older_than_days)
        else:
            return self.clear_all(confirm=True)

    def delete_campagne(self, campagne_id: str) -> int:
        """Méthode legacy."""
        return self.delete_campaign(campagne_id)
