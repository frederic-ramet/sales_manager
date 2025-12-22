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

            # Indexes pour performance - seulement si c'est une table (pas une vue)
            # Après migration, unified_contacts devient une vue et on ne peut pas l'indexer
            cursor.execute("SELECT type FROM sqlite_master WHERE name='unified_contacts'")
            result = cursor.fetchone()
            is_table = result and result[0] == 'table'

            if is_table:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_uc_source ON unified_contacts(source)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_uc_email ON unified_contacts(email)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_uc_siren ON unified_contacts(siren)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_uc_campaign ON unified_contacts(campaign_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_uc_hubspot ON unified_contacts(hubspot_contact_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_uc_linkedin ON unified_contacts(linkedin_url)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_uc_status ON unified_contacts(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_uc_created ON unified_contacts(created_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_uc_getsales ON unified_contacts(getsales_uuid)")

            # Table de métadonnées de synchronisation
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sync_type TEXT NOT NULL,
                    last_sync_date TIMESTAMP NOT NULL,
                    contacts_synced INTEGER DEFAULT 0,
                    notes TEXT,
                    UNIQUE(sync_type)
                )
            """)

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
        table = self._get_table_name()

        # Champs contact (disponibles dans la table contacts)
        contact_fields = {
            'getsales_uuid': 'getsales_uuid',
            'hubspot_contact_id': 'hubspot_contact_id',
            'firstname': 'firstname',
            'lastname': 'lastname',
            'email': 'email',
            'phone': 'phone',
            'telephone': 'phone',
            'mobile': 'mobile',
            'job_title': 'job_title',
            'linkedin_url': 'linkedin_url',
            'linkedin_headline': 'linkedin_headline',
            'synced_to_hubspot': 'synced_to_hubspot',
            'last_sync_hubspot': 'last_sync_hubspot',
            'prospection_status': 'prospection_status',
            'messages_sent': 'messages_sent',
            'messages_received': 'messages_received',
            'last_interaction_at': 'last_interaction_at',
            'status': 'status',
            'notes': 'notes',
        }

        # Champs entreprise (seulement si table unified_contacts ou pour mise à jour company)
        company_fields = {
            'siren': 'siren',
            'siret': 'siret',
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
            'enriched_at': 'enriched_at',
            'enrichment_source': 'enrichment_source',
        }

        # Choisir les champs selon la table
        if table == 'contacts':
            # Nouveau schéma: seulement les champs contact
            field_mapping = contact_fields
        else:
            # Ancien schéma: tous les champs
            field_mapping = {**contact_fields, **company_fields}

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
            query = f"UPDATE {table} SET {', '.join(fields_to_update)} WHERE uuid = ?"
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
        table = self._get_table_name()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if hard_delete:
                cursor.execute(f"DELETE FROM {table} WHERE uuid = ?", (contact_uuid,))
            else:
                cursor.execute(
                    f"UPDATE {table} SET status = 'deleted', updated_at = ? WHERE uuid = ?",
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
        # Nouveaux filtres avancés
        ape_codes: List[str] = None,
        departements: List[str] = None,
        city: str = None,
        has_email: bool = None,
        has_phone: bool = None,
        has_linkedin: bool = None,
        created_after: str = None,
        created_before: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Recherche des contacts avec filtres.

        Args:
            query: Recherche texte (siren, nom, email, entreprise)
            source: Filtrer par source (sirene, hubspot, getsales, csv_import)
            enriched: Filtrer par statut enrichissement
            synced: Filtrer par statut sync HubSpot
            status: Statut (active, archived, deleted)
            campaign_id: Filtrer par campagne
            ape_codes: Liste de codes APE
            departements: Liste de départements (2 premiers chiffres du code postal)
            city: Filtrer par ville (recherche partielle)
            has_email: Filtrer contacts avec email
            has_phone: Filtrer contacts avec téléphone
            has_linkedin: Filtrer contacts avec LinkedIn
            created_after: Date min de création (format YYYY-MM-DD)
            created_before: Date max de création (format YYYY-MM-DD)
            limit: Nombre max de résultats
            offset: Offset pour pagination

        Returns:
            Liste de contacts
        """
        conditions = []
        params = []

        if status:
            conditions.append("contact_status = ?")
            params.append(status)

        if source:
            conditions.append("contact_source = ?")
            params.append(source.lower())

        if campaign_id:
            conditions.append("campaign_id = ?")
            params.append(campaign_id)

        # DISABLED: enriched_at is now a company-level field, not contact-level
        # if enriched is not None:
        #     if enriched:
        #         conditions.append("enriched_at IS NOT NULL")
        #     else:
        #         conditions.append("enriched_at IS NULL")

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

        # Filtres avancés
        if ape_codes:
            placeholders = ','.join(['?' for _ in ape_codes])
            conditions.append(f"ape_code IN ({placeholders})")
            params.extend(ape_codes)

        if departements:
            # Filtrer par les 2 premiers chiffres du code postal
            dept_conditions = []
            for dept in departements:
                dept_conditions.append("postal_code LIKE ?")
                params.append(f"{dept}%")
            conditions.append(f"({' OR '.join(dept_conditions)})")

        if city:
            conditions.append("city LIKE ?")
            params.append(f"%{city}%")

        if has_email is not None:
            if has_email:
                conditions.append("email IS NOT NULL AND email != ''")
            else:
                conditions.append("(email IS NULL OR email = '')")

        if has_phone is not None:
            if has_phone:
                conditions.append("(phone IS NOT NULL AND phone != '') OR (mobile IS NOT NULL AND mobile != '')")
            else:
                conditions.append("(phone IS NULL OR phone = '') AND (mobile IS NULL OR mobile = '')")

        if has_linkedin is not None:
            if has_linkedin:
                conditions.append("linkedin_url IS NOT NULL AND linkedin_url != ''")
            else:
                conditions.append("(linkedin_url IS NULL OR linkedin_url = '')")

        if created_after:
            conditions.append("created_at >= ?")
            params.append(created_after)

        if created_before:
            conditions.append("created_at <= ?")
            params.append(created_before + " 23:59:59")

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
            cursor.execute("SELECT COUNT(*) FROM unified_contacts WHERE contact_status = 'active'")
            total = cursor.fetchone()[0]

            # Par source
            cursor.execute("""
                SELECT contact_source, COUNT(*) as count
                FROM unified_contacts
                WHERE contact_status = 'active'
                GROUP BY contact_source
            """)
            by_source = {row[0]: row[1] for row in cursor.fetchall()}

            # Synced HubSpot
            cursor.execute("""
                SELECT COUNT(*) FROM unified_contacts
                WHERE contact_status = 'active' AND synced_to_hubspot = 1
            """)
            hubspot_synced = cursor.fetchone()[0]

            # Nombre de campagnes
            cursor.execute("SELECT COUNT(DISTINCT campaign_id) FROM unified_contacts WHERE campaign_id IS NOT NULL")
            num_campaigns = cursor.fetchone()[0]

            # Dernier contact
            cursor.execute("""
                SELECT created_at FROM unified_contacts
                WHERE contact_status = 'active'
                ORDER BY created_at DESC LIMIT 1
            """)
            row = cursor.fetchone()
            last_contact = row[0] if row else None

            # Campagnes récentes
            cursor.execute("""
                SELECT campaign_id, COUNT(*) as count, MAX(created_at) as date
                FROM unified_contacts
                WHERE campaign_id IS NOT NULL AND contact_status = 'active'
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
                'hubspot_synced': hubspot_synced,
                'num_campaigns': num_campaigns,
                'last_contact': last_contact,
                'campaigns_recent': campaigns,
                # Alias pour compatibilité
                'total_leads': total,
                'dernier_lead': last_contact,
                'campagnes_recentes': campaigns,
            }

    def get_filter_options(self) -> Dict[str, List[str]]:
        """
        Récupère les valeurs distinctes pour les filtres de recherche.

        Returns:
            Dict avec listes de valeurs pour APE, villes, campagnes, etc.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Codes APE distincts (non vides)
            cursor.execute("""
                SELECT DISTINCT ape_code FROM unified_contacts
                WHERE contact_status = 'active' AND ape_code IS NOT NULL AND ape_code != ''
                ORDER BY ape_code
            """)
            ape_codes = [row[0] for row in cursor.fetchall()]

            # Départements distincts (2 premiers chiffres du code postal)
            cursor.execute("""
                SELECT DISTINCT SUBSTR(postal_code, 1, 2) as dept FROM unified_contacts
                WHERE contact_status = 'active' AND postal_code IS NOT NULL AND LENGTH(postal_code) >= 2
                ORDER BY dept
            """)
            departements = [row[0] for row in cursor.fetchall()]

            # Villes distinctes
            cursor.execute("""
                SELECT DISTINCT city FROM unified_contacts
                WHERE contact_status = 'active' AND city IS NOT NULL AND city != ''
                ORDER BY city
                LIMIT 500
            """)
            cities = [row[0] for row in cursor.fetchall()]

            # Campagnes
            cursor.execute("""
                SELECT DISTINCT campaign_id FROM unified_contacts
                WHERE contact_status = 'active' AND campaign_id IS NOT NULL
                ORDER BY campaign_id DESC
            """)
            campaigns = [row[0] for row in cursor.fetchall()]

            # Sources
            cursor.execute("""
                SELECT DISTINCT contact_source FROM unified_contacts
                WHERE contact_status = 'active' AND contact_source IS NOT NULL
                ORDER BY contact_source
            """)
            sources = [row[0] for row in cursor.fetchall()]

            return {
                'ape_codes': ape_codes,
                'departements': departements,
                'cities': cities,
                'campaigns': campaigns,
                'sources': sources,
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
                    "SELECT * FROM unified_contacts WHERE hubspot_contact_id = ? AND contact_status = 'active'",
                    (hubspot_contact_id,)
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)

            # 2. Par GetSales UUID
            if getsales_uuid:
                cursor.execute(
                    "SELECT * FROM unified_contacts WHERE getsales_uuid = ? AND contact_status = 'active'",
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
                    "SELECT * FROM unified_contacts WHERE linkedin_url = ? AND contact_status = 'active'",
                    (normalized,)
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)

            # 4. Par Email
            if email:
                email_lower = email.lower().strip()
                cursor.execute(
                    "SELECT * FROM unified_contacts WHERE LOWER(email) = ? AND contact_status = 'active'",
                    (email_lower,)
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)

            # 5. Par SIREN
            if siren:
                cursor.execute(
                    "SELECT * FROM unified_contacts WHERE siren = ? AND contact_status = 'active'",
                    (siren,)
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)

            return None

    def find_all_duplicates(
        self,
        email: str = None,
        siren: str = None,
        linkedin_url: str = None,
        hubspot_contact_id: str = None,
        getsales_uuid: str = None,
        company_name: str = None,
        firstname: str = None,
        lastname: str = None
    ) -> List[Dict[str, Any]]:
        """
        Trouve TOUS les doublons potentiels avec leur type de match.

        Retourne une liste de matches avec:
        - contact: les données du contact
        - match_type: 'hubspot_id', 'getsales_uuid', 'linkedin', 'email', 'siren', 'company_name', 'fullname'
        - confidence: 'high' (ID exact), 'medium' (email/linkedin), 'low' (nom entreprise)

        Args:
            email: Email à chercher
            siren: SIREN à chercher
            linkedin_url: URL LinkedIn
            hubspot_contact_id: ID HubSpot
            getsales_uuid: UUID GetSales
            company_name: Nom de l'entreprise
            firstname: Prénom du contact
            lastname: Nom du contact

        Returns:
            Liste de dicts avec 'contact', 'match_type', 'confidence'
        """
        matches = []
        seen_uuids = set()

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 1. Par HubSpot ID (high confidence)
            if hubspot_contact_id:
                cursor.execute(
                    "SELECT * FROM unified_contacts WHERE hubspot_contact_id = ? AND contact_status = 'active'",
                    (hubspot_contact_id,)
                )
                for row in cursor.fetchall():
                    contact = dict(row)
                    if contact['uuid'] not in seen_uuids:
                        seen_uuids.add(contact['uuid'])
                        matches.append({
                            'contact': contact,
                            'match_type': 'hubspot_id',
                            'confidence': 'high'
                        })

            # 2. Par GetSales UUID (high confidence)
            if getsales_uuid:
                cursor.execute(
                    "SELECT * FROM unified_contacts WHERE getsales_uuid = ? AND contact_status = 'active'",
                    (getsales_uuid,)
                )
                for row in cursor.fetchall():
                    contact = dict(row)
                    if contact['uuid'] not in seen_uuids:
                        seen_uuids.add(contact['uuid'])
                        matches.append({
                            'contact': contact,
                            'match_type': 'getsales_uuid',
                            'confidence': 'high'
                        })

            # 3. Par LinkedIn URL (high confidence)
            if linkedin_url:
                normalized = self._normalize_linkedin_url(linkedin_url)
                cursor.execute(
                    "SELECT * FROM unified_contacts WHERE linkedin_url = ? AND contact_status = 'active'",
                    (normalized,)
                )
                for row in cursor.fetchall():
                    contact = dict(row)
                    if contact['uuid'] not in seen_uuids:
                        seen_uuids.add(contact['uuid'])
                        matches.append({
                            'contact': contact,
                            'match_type': 'linkedin',
                            'confidence': 'high'
                        })

            # 4. Par Email (medium confidence)
            if email:
                email_lower = email.lower().strip()
                cursor.execute(
                    "SELECT * FROM unified_contacts WHERE LOWER(email) = ? AND contact_status = 'active'",
                    (email_lower,)
                )
                for row in cursor.fetchall():
                    contact = dict(row)
                    if contact['uuid'] not in seen_uuids:
                        seen_uuids.add(contact['uuid'])
                        matches.append({
                            'contact': contact,
                            'match_type': 'email',
                            'confidence': 'medium'
                        })

            # 5. Par SIREN (medium confidence)
            if siren:
                cursor.execute(
                    "SELECT * FROM unified_contacts WHERE siren = ? AND contact_status = 'active'",
                    (siren,)
                )
                for row in cursor.fetchall():
                    contact = dict(row)
                    if contact['uuid'] not in seen_uuids:
                        seen_uuids.add(contact['uuid'])
                        matches.append({
                            'contact': contact,
                            'match_type': 'siren',
                            'confidence': 'medium'
                        })

            # 6. Par nom d'entreprise (low confidence) - exact match insensible à la casse
            if company_name:
                company_normalized = company_name.lower().strip()
                cursor.execute(
                    "SELECT * FROM unified_contacts WHERE LOWER(company_name) = ? AND contact_status = 'active'",
                    (company_normalized,)
                )
                for row in cursor.fetchall():
                    contact = dict(row)
                    if contact['uuid'] not in seen_uuids:
                        seen_uuids.add(contact['uuid'])
                        matches.append({
                            'contact': contact,
                            'match_type': 'company_name',
                            'confidence': 'low'
                        })

            # 7. Par nom complet (prénom + nom) dans la même entreprise (low confidence)
            if firstname and lastname and company_name:
                fn_lower = firstname.lower().strip()
                ln_lower = lastname.lower().strip()
                company_normalized = company_name.lower().strip()
                cursor.execute("""
                    SELECT * FROM unified_contacts
                    WHERE LOWER(firstname) = ?
                    AND LOWER(lastname) = ?
                    AND LOWER(company_name) = ?
                    AND contact_status = 'active'
                """, (fn_lower, ln_lower, company_normalized))
                for row in cursor.fetchall():
                    contact = dict(row)
                    if contact['uuid'] not in seen_uuids:
                        seen_uuids.add(contact['uuid'])
                        matches.append({
                            'contact': contact,
                            'match_type': 'fullname_company',
                            'confidence': 'medium'
                        })

        return matches

    def search_by_company(self, company_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Recherche les contacts d'une entreprise par nom.

        Args:
            company_name: Nom de l'entreprise (recherche partielle)
            limit: Nombre max de résultats

        Returns:
            Liste des contacts trouvés
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Recherche LIKE pour matching partiel
            pattern = f"%{company_name}%"
            cursor.execute("""
                SELECT * FROM unified_contacts
                WHERE company_name LIKE ? AND contact_status = 'active'
                ORDER BY company_name, lastname
                LIMIT ?
            """, (pattern, limit))

            return [dict(row) for row in cursor.fetchall()]

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

    # =========================================================================
    # DEDUPLICATION HELPERS (pour Import CSV v2)
    # =========================================================================

    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Trouve un contact par email exact.

        Args:
            email: Email à chercher

        Returns:
            Contact ou None
        """
        if not email:
            return None

        email_lower = email.lower().strip()

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            table = self._get_table_name()
            cursor.execute(
                f"SELECT * FROM {table} WHERE LOWER(email) = ? AND status = 'active' LIMIT 1",
                (email_lower,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """
        Trouve un contact par téléphone.

        Args:
            phone: Téléphone à chercher (sera normalisé)

        Returns:
            Contact ou None
        """
        if not phone:
            return None

        # Normaliser: garder seulement les chiffres
        digits = ''.join(c for c in phone if c.isdigit())
        if len(digits) < 9:
            return None

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            table = self._get_table_name()
            # Rechercher par les derniers 9 chiffres (ignore préfixe international)
            cursor.execute(f"""
                SELECT * FROM {table}
                WHERE status = 'active'
                AND (
                    REPLACE(REPLACE(REPLACE(phone, ' ', ''), '-', ''), '.', '') LIKE ?
                    OR REPLACE(REPLACE(REPLACE(mobile, ' ', ''), '-', ''), '.', '') LIKE ?
                )
                LIMIT 1
            """, (f"%{digits[-9:]}", f"%{digits[-9:]}"))

            row = cursor.fetchone()
            return dict(row) if row else None

    def get_by_linkedin(self, linkedin_url: str) -> Optional[Dict[str, Any]]:
        """
        Trouve un contact par URL LinkedIn.

        Args:
            linkedin_url: URL LinkedIn

        Returns:
            Contact ou None
        """
        if not linkedin_url:
            return None

        normalized = self._normalize_linkedin_url(linkedin_url)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            table = self._get_table_name()
            cursor.execute(
                f"SELECT * FROM {table} WHERE linkedin_url = ? AND status = 'active' LIMIT 1",
                (normalized,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

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
                f"SELECT siren FROM unified_contacts WHERE siren IN ({placeholders}) AND contact_status = 'active'",
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
        Note: Enrichment is now a company-level property.

        Args:
            contact_uuid: UUID du contact
            source: Source d'enrichissement (pappers, manual, etc.)

        Returns:
            True si mis à jour
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Get the contact's company_id
            cursor.execute("SELECT company_id FROM contacts WHERE uuid = ?", (contact_uuid,))
            row = cursor.fetchone()

            if not row or not row[0]:
                # No company associated, can't mark as enriched
                return False

            company_id = row[0]

            # Update the company record
            cursor.execute("""
                UPDATE companies
                SET enriched_at = ?, enrichment_source = ?, updated_at = ?
                WHERE id = ?
            """, (datetime.now(), source, datetime.now(), company_id))
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
        table = self._get_table_name()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE {table}
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
                WHERE contact_status = 'active'
                  AND synced_to_hubspot = 0
                ORDER BY created_at DESC
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

        table = self._get_table_name()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {table}")
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
        table = self._get_table_name()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"DELETE FROM {table} WHERE campaign_id = ?",
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
        table = self._get_table_name()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE {table}
                SET status = 'archived', updated_at = ?
                WHERE status = 'active'
                  AND created_at < datetime('now', '-' || ? || ' days')
            """, (datetime.now(), older_than_days))
            archived = cursor.rowcount
            conn.commit()

        logger.info(f"Archivé {archived} contacts plus vieux que {older_than_days} jours")
        return archived

    # =========================================================================
    # MÉTADONNÉES DE SYNCHRONISATION
    # =========================================================================

    def update_sync_metadata(self, sync_type: str, contacts_synced: int, notes: str = None):
        """
        Met à jour les métadonnées de synchronisation.

        Args:
            sync_type: Type de sync ('hubspot_full', 'hubspot_incremental', etc.)
            contacts_synced: Nombre de contacts synchronisés
            notes: Notes optionnelles
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sync_metadata (sync_type, last_sync_date, contacts_synced, notes)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(sync_type) DO UPDATE SET
                    last_sync_date = excluded.last_sync_date,
                    contacts_synced = excluded.contacts_synced,
                    notes = excluded.notes
            """, (sync_type, datetime.now(), contacts_synced, notes))
            conn.commit()

        logger.info(f"Métadonnées de sync mises à jour: {sync_type}")

    def get_sync_metadata(self, sync_type: str = None) -> Optional[Dict[str, Any]]:
        """
        Récupère les métadonnées de synchronisation.

        Args:
            sync_type: Type de sync (None = tous)

        Returns:
            Dict avec métadonnées ou None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if sync_type:
                cursor.execute(
                    "SELECT * FROM sync_metadata WHERE sync_type = ?",
                    (sync_type,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
            else:
                cursor.execute("SELECT * FROM sync_metadata ORDER BY last_sync_date DESC")
                rows = cursor.fetchall()
                return [dict(row) for row in rows]

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

    # =========================================================================
    # COMPANY SUPPORT (Phase 3 - Companies/Contacts separation)
    # =========================================================================

    def _has_company_id_column(self) -> bool:
        """Vérifie si la colonne company_id existe (nouveau schéma)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(contacts)")
                columns = [row[1] for row in cursor.fetchall()]
                return 'company_id' in columns
        except Exception:
            return False

    def _get_table_name(self) -> str:
        """Retourne le nom de la table à utiliser (contacts ou unified_contacts)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='contacts'
            """)
            if cursor.fetchone():
                return 'contacts'
            return 'unified_contacts'

    def get_contacts_by_company(
        self,
        company_id: int,
        status: str = 'active',
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Récupère tous les contacts d'une entreprise.

        Args:
            company_id: ID de l'entreprise
            status: Statut des contacts (active, archived, etc.)
            limit: Nombre max de résultats

        Returns:
            Liste des contacts de l'entreprise
        """
        table = self._get_table_name()

        # Vérifier si le nouveau schéma est disponible
        if table != 'contacts':
            logger.warning("get_contacts_by_company: nouveau schéma non disponible")
            return []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(f"""
                SELECT * FROM {table}
                WHERE company_id = ?
                  AND status = ?
                ORDER BY lastname, firstname
                LIMIT ?
            """, (company_id, status, limit))

            return [dict(row) for row in cursor.fetchall()]

    def link_contact_to_company(self, contact_uuid: str, company_id: int) -> bool:
        """
        Lie un contact à une entreprise.

        Args:
            contact_uuid: UUID du contact
            company_id: ID de l'entreprise

        Returns:
            True si lié avec succès
        """
        table = self._get_table_name()

        if table != 'contacts':
            logger.warning("link_contact_to_company: nouveau schéma non disponible")
            return False

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(f"""
                UPDATE {table}
                SET company_id = ?, updated_at = ?
                WHERE uuid = ?
            """, (company_id, datetime.now(), contact_uuid))

            conn.commit()
            return cursor.rowcount > 0

    def unlink_contact_from_company(self, contact_uuid: str) -> bool:
        """
        Délie un contact de son entreprise.

        Args:
            contact_uuid: UUID du contact

        Returns:
            True si délié avec succès
        """
        table = self._get_table_name()

        if table != 'contacts':
            logger.warning("unlink_contact_from_company: nouveau schéma non disponible")
            return False

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(f"""
                UPDATE {table}
                SET company_id = NULL, updated_at = ?
                WHERE uuid = ?
            """, (datetime.now(), contact_uuid))

            conn.commit()
            return cursor.rowcount > 0

    def add_contact_with_company(
        self,
        data: Dict[str, Any],
        source: str,
        company_id: Optional[int] = None
    ) -> str:
        """
        Ajoute un contact avec lien vers une entreprise (nouveau schéma).

        Args:
            data: Données du contact
            source: Source (sirene, hubspot, getsales, pappers)
            company_id: ID de l'entreprise (optionnel)

        Returns:
            UUID du contact créé
        """
        table = self._get_table_name()

        if table != 'contacts':
            # Fallback vers ancien schéma
            return self.add_contact(data, source)

        contact_uuid = self._generate_uuid()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO contacts (
                    uuid, company_id,
                    getsales_uuid, hubspot_contact_id,
                    firstname, lastname, email, phone, mobile,
                    job_title, department, seniority,
                    linkedin_url, linkedin_headline, linkedin_bio,
                    prospection_status, messages_sent, messages_received, last_interaction_at,
                    getsales_campaign_id, getsales_flow_uuid,
                    synced_to_hubspot, last_sync_hubspot,
                    source, campaign_id,
                    status, notes, tags, raw_data
                ) VALUES (
                    ?, ?,
                    ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?,
                    'active', ?, ?, ?
                )
            """, (
                contact_uuid,
                company_id,
                data.get('getsales_uuid'),
                data.get('hubspot_contact_id'),
                data.get('firstname'),
                data.get('lastname'),
                data.get('email'),
                data.get('phone') or data.get('telephone'),
                data.get('mobile'),
                data.get('job_title'),
                data.get('department'),
                data.get('seniority'),
                data.get('linkedin_url'),
                data.get('linkedin_headline'),
                data.get('linkedin_bio'),
                data.get('prospection_status'),
                data.get('messages_sent', 0),
                data.get('messages_received', 0),
                data.get('last_interaction_at'),
                data.get('getsales_campaign_id'),
                data.get('getsales_flow_uuid'),
                1 if data.get('synced_to_hubspot') else 0,
                data.get('last_sync_hubspot'),
                source.lower(),
                data.get('campaign_id'),
                data.get('notes'),
                data.get('tags'),
                json.dumps(data, ensure_ascii=False, default=str) if data else None
            ))

            conn.commit()

        logger.info(f"Contact ajouté (nouveau schéma): {contact_uuid} (company_id: {company_id})")
        return contact_uuid

    def search_with_company(
        self,
        query: str = None,
        company_id: int = None,
        source: str = None,
        status: str = 'active',
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Recherche des contacts avec support du filtre company_id.

        Args:
            query: Recherche texte
            company_id: Filtrer par entreprise
            source: Filtrer par source
            status: Statut des contacts
            limit: Nombre max de résultats
            offset: Offset pour pagination

        Returns:
            Liste de contacts avec infos entreprise
        """
        table = self._get_table_name()

        conditions = []
        params = []

        # Column names differ between contacts table and unified_contacts view
        status_col = "c.status" if table == 'contacts' else "c.contact_status"
        source_col = "c.source" if table == 'contacts' else "c.contact_source"

        if status:
            conditions.append(f"{status_col} = ?")
            params.append(status)

        if company_id is not None:
            if table == 'contacts':
                conditions.append("c.company_id = ?")
                params.append(company_id)
            else:
                # Ancien schéma: pas de support company_id
                pass

        if source:
            conditions.append(f"{source_col} = ?")
            params.append(source.lower())

        if query:
            conditions.append("""
                (c.firstname LIKE ? OR c.lastname LIKE ? OR c.email LIKE ?)
            """)
            search_term = f"%{query}%"
            params.extend([search_term, search_term, search_term])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if table == 'contacts':
                # Nouveau schéma: JOIN avec companies
                sql = f"""
                    SELECT c.*,
                           comp.company_name,
                           comp.siren,
                           comp.city as company_city,
                           comp.website
                    FROM contacts c
                    LEFT JOIN companies comp ON c.company_id = comp.id
                    {where_clause}
                    ORDER BY c.created_at DESC
                    LIMIT ? OFFSET ?
                """
            else:
                # Ancien schéma
                sql = f"""
                    SELECT * FROM unified_contacts c
                    {where_clause}
                    ORDER BY c.created_at DESC
                    LIMIT ? OFFSET ?
                """

            params.extend([limit, offset])
            cursor.execute(sql, params)

            return [dict(row) for row in cursor.fetchall()]

    def get_contact_with_company(self, contact_uuid: str) -> Optional[Dict[str, Any]]:
        """
        Récupère un contact avec les infos de son entreprise.

        Args:
            contact_uuid: UUID du contact

        Returns:
            Dict du contact avec infos entreprise ou None
        """
        table = self._get_table_name()

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if table == 'contacts':
                cursor.execute("""
                    SELECT c.*,
                           comp.id as company_id,
                           comp.company_name,
                           comp.siren,
                           comp.siret_list,
                           comp.ape_code,
                           comp.city as company_city,
                           comp.website,
                           comp.hubspot_company_id
                    FROM contacts c
                    LEFT JOIN companies comp ON c.company_id = comp.id
                    WHERE c.uuid = ?
                """, (contact_uuid,))
            else:
                cursor.execute(
                    "SELECT * FROM unified_contacts WHERE uuid = ?",
                    (contact_uuid,)
                )

            row = cursor.fetchone()
            return dict(row) if row else None

    def count_contacts_by_company(self, company_id: int) -> int:
        """
        Compte le nombre de contacts d'une entreprise.

        Args:
            company_id: ID de l'entreprise

        Returns:
            Nombre de contacts
        """
        table = self._get_table_name()

        if table != 'contacts':
            return 0

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM contacts
                WHERE company_id = ? AND status = 'active'
            """, (company_id,))
            return cursor.fetchone()[0]

    def get_orphan_contacts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Récupère les contacts sans entreprise associée.

        Args:
            limit: Nombre max de résultats

        Returns:
            Liste de contacts orphelins
        """
        table = self._get_table_name()

        if table != 'contacts':
            return []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM contacts
                WHERE company_id IS NULL AND status = 'active'
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

            return [dict(row) for row in cursor.fetchall()]
