"""
CompanyManager - Gestionnaire des entreprises.

Nouveau module pour gérer les entreprises séparément des contacts.
Fournit le matching intelligent, la fusion, et les stats agrégées.

Usage:
    manager = CompanyManager()

    # Créer une entreprise
    company_id = manager.create_company({
        'company_name': 'ESCP Business School',
        'siren': '123456789',
        'city': 'Paris'
    })

    # Matching intelligent (GetSales)
    company_id = manager.find_or_create_company({
        'company_name': 'Leboncoin',
        'domain': 'leboncoin.fr'
    })

    # Fusion de doublons
    manager.merge_companies(company_id_keep=1, company_id_merge=2)
"""

import sqlite3
import logging
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Chemin par défaut de la base de données
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "leads.db"


class CompanyManager:
    """
    Gestionnaire des entreprises.

    Responsabilités:
    - CRUD entreprises
    - Recherche par SIREN, website, nom
    - Matching intelligent pour éviter doublons
    - Fusion d'entreprises doublons
    - Stats agrégées (total contacts, messages, etc.)
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialise le gestionnaire.

        Args:
            db_path: Chemin vers la base de données SQLite (optionnel)
        """
        self.db_path = db_path or str(DEFAULT_DB_PATH)
        self._ensure_schema_updated()

    def _ensure_schema_updated(self):
        """Ajoute les colonnes manquantes si nécessaire."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Vérifier si la table companies existe
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='companies'")
                if not cursor.fetchone():
                    return  # Table n'existe pas encore

                # Colonnes à ajouter pour la classification
                columns_to_add = [
                    ('prospect_class', 'TEXT'),
                    ('prospect_class_points', 'INTEGER'),
                    ('prospect_class_signals', 'TEXT'),
                    ('segment', 'TEXT'),
                ]

                # Récupérer les colonnes existantes
                cursor.execute("PRAGMA table_info(companies)")
                existing_columns = {row[1] for row in cursor.fetchall()}

                # Ajouter les colonnes manquantes
                for col_name, col_type in columns_to_add:
                    if col_name not in existing_columns:
                        try:
                            cursor.execute(f"ALTER TABLE companies ADD COLUMN {col_name} {col_type}")
                            logger.info(f"Colonne {col_name} ajoutée à companies")
                        except sqlite3.OperationalError:
                            pass  # Colonne existe déjà

                conn.commit()
        except Exception as e:
            logger.warning(f"Erreur migration schema companies: {e}")

        # Créer le dossier si nécessaire
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _generate_uuid(self) -> str:
        """Génère un UUID unique."""
        return str(uuid.uuid4())

    # =========================================================================
    # CRUD
    # =========================================================================

    def create_company(self, data: Dict[str, Any]) -> int:
        """
        Crée une nouvelle entreprise.

        Args:
            data: Données de l'entreprise

        Returns:
            ID de l'entreprise créée

        Raises:
            ValueError: Si company_name manquant ou SIREN dupliqué
        """
        if not data.get('company_name'):
            raise ValueError("company_name est requis")

        company_uuid = self._generate_uuid()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            try:
                cursor.execute("""
                    INSERT INTO companies (
                        uuid, siren, siret_list, hubspot_company_id,
                        company_name, legal_form,
                        ape_code, ape_label,
                        address, postal_code, city, region, country,
                        employee_range, revenue_range,
                        website, company_phone, company_email,
                        enriched_at, enrichment_source, enrichment_quality,
                        prospection_status, prospection_priority,
                        total_contacts, total_messages_sent, total_messages_received,
                        synced_to_hubspot, last_sync_hubspot,
                        source, campaign_id,
                        status, notes, tags, raw_data
                    ) VALUES (
                        ?, ?, ?, ?,
                        ?, ?,
                        ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?,
                        0, 0, 0,
                        0, NULL,
                        ?, ?,
                        'active', ?, ?, ?
                    )
                """, (
                    company_uuid,
                    data.get('siren'),
                    data.get('siret_list') or data.get('siret'),
                    data.get('hubspot_company_id'),
                    data.get('company_name'),
                    data.get('legal_form'),
                    data.get('ape_code') or data.get('code_ape'),
                    data.get('ape_label'),
                    data.get('address'),
                    data.get('postal_code'),
                    data.get('city') or data.get('ville'),
                    data.get('region'),
                    data.get('country', 'FR'),
                    data.get('employee_range'),
                    data.get('revenue_range'),
                    data.get('website'),
                    data.get('company_phone') or data.get('phone'),
                    data.get('company_email'),
                    data.get('enriched_at'),
                    data.get('enrichment_source'),
                    data.get('enrichment_quality'),
                    data.get('prospection_status', 'new'),
                    data.get('prospection_priority'),
                    data.get('source', 'manual'),
                    data.get('campaign_id'),
                    data.get('notes'),
                    data.get('tags'),
                    json.dumps(data, ensure_ascii=False, default=str) if data else None
                ))

                company_id = cursor.lastrowid
                conn.commit()

                logger.info(f"Entreprise créée: {company_uuid} (ID: {company_id})")
                return company_id

            except sqlite3.IntegrityError as e:
                if 'UNIQUE constraint failed' in str(e) and 'siren' in str(e):
                    raise ValueError(f"SIREN {data.get('siren')} existe déjà")
                raise

    def get_company(self, company_id: int) -> Optional[Dict[str, Any]]:
        """
        Récupère une entreprise par ID.

        Args:
            company_id: ID de l'entreprise

        Returns:
            Dict de l'entreprise ou None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM companies WHERE id = ?", (company_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_company_by_uuid(self, company_uuid: str) -> Optional[Dict[str, Any]]:
        """Récupère une entreprise par UUID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM companies WHERE uuid = ?", (company_uuid,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_company(self, company_id: int, data: Dict[str, Any]) -> bool:
        """
        Met à jour une entreprise.

        Args:
            company_id: ID de l'entreprise
            data: Données à mettre à jour

        Returns:
            True si mis à jour
        """
        field_mapping = {
            'siren': 'siren',
            'siret_list': 'siret_list',
            'hubspot_company_id': 'hubspot_company_id',
            'company_name': 'company_name',
            'legal_form': 'legal_form',
            'ape_code': 'ape_code',
            'code_ape': 'ape_code',
            'ape_label': 'ape_label',
            'address': 'address',
            'postal_code': 'postal_code',
            'city': 'city',
            'ville': 'city',
            'region': 'region',
            'country': 'country',
            'employee_range': 'employee_range',
            'revenue_range': 'revenue_range',
            'website': 'website',
            'company_phone': 'company_phone',
            'company_email': 'company_email',
            'enriched_at': 'enriched_at',
            'enrichment_source': 'enrichment_source',
            'enrichment_quality': 'enrichment_quality',
            'prospection_status': 'prospection_status',
            'prospection_priority': 'prospection_priority',
            'synced_to_hubspot': 'synced_to_hubspot',
            'last_sync_hubspot': 'last_sync_hubspot',
            'status': 'status',
            'notes': 'notes',
            'tags': 'tags',
            # Champs classification SIREN v2
            'segment': 'segment',
            'prospect_class': 'prospect_class',
            'prospect_class_points': 'prospect_class_points',
            'prospect_class_signals': 'prospect_class_signals',
        }

        fields_to_update = []
        values = []

        for key, col in field_mapping.items():
            if key in data and data[key] is not None:
                fields_to_update.append(f"{col} = ?")
                values.append(data[key])

        if not fields_to_update:
            return False

        fields_to_update.append("updated_at = ?")
        values.append(datetime.now())
        values.append(company_id)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            query = f"UPDATE companies SET {', '.join(fields_to_update)} WHERE id = ?"
            cursor.execute(query, values)
            conn.commit()
            return cursor.rowcount > 0

    def delete_company(self, company_id: int, hard_delete: bool = False) -> bool:
        """
        Supprime une entreprise (soft delete par défaut).

        Args:
            company_id: ID de l'entreprise
            hard_delete: Si True, suppression définitive

        Returns:
            True si supprimé
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if hard_delete:
                # D'abord délier les contacts
                cursor.execute(
                    "UPDATE contacts SET company_id = NULL WHERE company_id = ?",
                    (company_id,)
                )
                cursor.execute("DELETE FROM companies WHERE id = ?", (company_id,))
            else:
                cursor.execute(
                    "UPDATE companies SET status = 'archived', updated_at = ? WHERE id = ?",
                    (datetime.now(), company_id)
                )

            conn.commit()
            return cursor.rowcount > 0

    # =========================================================================
    # RECHERCHE
    # =========================================================================

    def find_by_siren(self, siren: str) -> Optional[Dict[str, Any]]:
        """Trouve une entreprise par SIREN."""
        if not siren:
            return None

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM companies WHERE siren = ? AND status = 'active'",
                (siren,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_by_website(self, website: str) -> Optional[Dict[str, Any]]:
        """Trouve une entreprise par website/domain."""
        if not website:
            return None

        # Normaliser le domaine
        domain = self._normalize_domain(website)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Recherche exacte sur le domaine normalisé
            cursor.execute("""
                SELECT * FROM companies
                WHERE website LIKE ? AND status = 'active'
                LIMIT 1
            """, (f"%{domain}%",))

            row = cursor.fetchone()
            return dict(row) if row else None

    def get_by_domain(self, email_or_domain: str) -> Optional[Dict[str, Any]]:
        """
        Trouve une entreprise par domaine email.

        Args:
            email_or_domain: Email (extrait domaine) ou domaine direct

        Returns:
            Entreprise ou None
        """
        if not email_or_domain:
            return None

        # Extraire le domaine si c'est un email
        if '@' in email_or_domain:
            domain = email_or_domain.split('@')[1].lower().strip()
        else:
            domain = self._normalize_domain(email_or_domain)

        if not domain or domain in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'orange.fr', 'free.fr', 'sfr.fr']:
            return None  # Ignorer les domaines génériques

        # Chercher par website ou company_email
        return self.find_by_website(domain)

    def find_by_hubspot_id(self, hubspot_company_id: str) -> Optional[Dict[str, Any]]:
        """Trouve une entreprise par ID HubSpot."""
        if not hubspot_company_id:
            return None

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM companies WHERE hubspot_company_id = ? AND status = 'active'",
                (str(hubspot_company_id),)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_by_name_exact(self, company_name: str) -> Optional[Dict[str, Any]]:
        """Trouve une entreprise par nom exact (case insensitive)."""
        if not company_name:
            return None

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM companies WHERE LOWER(company_name) = LOWER(?) AND status = 'active'",
                (company_name.strip(),)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_by_name_fuzzy(
        self,
        company_name: str,
        threshold: float = 0.85,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Trouve des entreprises par nom avec fuzzy matching.

        Args:
            company_name: Nom à chercher
            threshold: Seuil de similarité (0-1)
            limit: Nombre max de résultats

        Returns:
            Liste de dicts avec 'company' et 'similarity_score'
        """
        if not company_name:
            return []

        name_norm = self._normalize_company_name(company_name)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Récupérer toutes les entreprises actives
            cursor.execute("""
                SELECT * FROM companies
                WHERE status = 'active'
                AND company_name IS NOT NULL
            """)

            results = []
            for row in cursor.fetchall():
                db_name_norm = self._normalize_company_name(row['company_name'])
                similarity = self._similarity(name_norm, db_name_norm)

                if similarity >= threshold:
                    results.append({
                        'company': dict(row),
                        'similarity_score': similarity
                    })

            # Trier par similarité décroissante
            results.sort(key=lambda x: x['similarity_score'], reverse=True)
            return results[:limit]

    def search(
        self,
        query: str = None,
        source: str = None,
        status: str = 'active',
        has_contacts: bool = None,
        synced_hubspot: bool = None,
        city: str = None,
        ape_codes: List[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Recherche d'entreprises avec filtres.

        Args:
            query: Recherche texte (siren, nom, website)
            source: Filtrer par source
            status: Statut (active, archived)
            has_contacts: Filtrer par présence de contacts
            synced_hubspot: Filtrer par statut sync HubSpot
            city: Filtrer par ville
            ape_codes: Liste de codes APE
            limit: Nombre max de résultats
            offset: Offset pour pagination

        Returns:
            Liste d'entreprises
        """
        conditions = []
        params = []

        if status:
            conditions.append("status = ?")
            params.append(status)

        if source:
            conditions.append("source = ?")
            params.append(source.lower())

        if query:
            conditions.append("""
                (siren LIKE ? OR company_name LIKE ? OR website LIKE ?)
            """)
            search_term = f"%{query}%"
            params.extend([search_term, search_term, search_term])

        if city:
            conditions.append("city LIKE ?")
            params.append(f"%{city}%")

        if ape_codes:
            placeholders = ','.join(['?' for _ in ape_codes])
            conditions.append(f"ape_code IN ({placeholders})")
            params.extend(ape_codes)

        if has_contacts is not None:
            if has_contacts:
                conditions.append("total_contacts > 0")
            else:
                conditions.append("total_contacts = 0")

        if synced_hubspot is not None:
            if synced_hubspot:
                conditions.append("synced_to_hubspot = 1")
            else:
                conditions.append("synced_to_hubspot = 0")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            sql = f"""
                SELECT * FROM companies
                {where_clause}
                ORDER BY total_contacts DESC, created_at DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])

            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_companies_with_contacts_count(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Récupère les entreprises avec leur nombre de contacts.

        Returns:
            Liste d'entreprises avec total_contacts
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT c.*,
                       (SELECT COUNT(*) FROM contacts WHERE company_id = c.id) as contacts_count
                FROM companies c
                WHERE c.status = 'active'
                ORDER BY contacts_count DESC, c.company_name
                LIMIT ?
            """, (limit,))

            return [dict(row) for row in cursor.fetchall()]

    # =========================================================================
    # MATCHING INTELLIGENT
    # =========================================================================

    def find_or_create_company(
        self,
        lead_data: Dict[str, Any],
        pappers_client=None
    ) -> Tuple[int, bool]:
        """
        Matching hiérarchique pour éviter doublons.

        Ordre de recherche:
        1. Par SIREN (si fourni)
        2. Par website/domain
        3. Par enrichissement Pappers (si client fourni)
        4. Par nom fuzzy
        5. Création si non trouvé

        Args:
            lead_data: Données du lead avec company_name, domain, siren
            pappers_client: Client Pappers pour enrichissement (optionnel)

        Returns:
            Tuple (company_id, created) - created=True si nouvelle entreprise
        """
        company_name = lead_data.get('company_name')
        if not company_name:
            raise ValueError("company_name requis pour matching")

        # 1. Match par SIREN si fourni
        siren = lead_data.get('siren')
        if siren:
            company = self.find_by_siren(siren)
            if company:
                logger.debug(f"Match SIREN: {company['company_name']}")
                return company['id'], False

        # 2. Match par website/domain
        domain = lead_data.get('domain') or lead_data.get('website')
        if domain:
            company = self.find_by_website(domain)
            if company:
                logger.debug(f"Match website: {company['company_name']}")
                return company['id'], False

        # 3. Enrichissement Pappers pour trouver SIREN
        if pappers_client and not siren:
            try:
                siren = pappers_client.search_siren(company_name)
                if siren:
                    company = self.find_by_siren(siren)
                    if company:
                        logger.debug(f"Match SIREN via Pappers: {company['company_name']}")
                        return company['id'], False
                    # Ajouter le SIREN pour la création
                    lead_data['siren'] = siren
            except Exception as e:
                logger.warning(f"Enrichissement Pappers échoué: {e}")

        # 4. Match par nom fuzzy
        fuzzy_matches = self.find_by_name_fuzzy(company_name, threshold=0.90)
        if fuzzy_matches:
            best_match = fuzzy_matches[0]
            logger.debug(
                f"Match fuzzy ({best_match['similarity_score']:.2f}): "
                f"{best_match['company']['company_name']}"
            )
            return best_match['company']['id'], False

        # 5. Création nouvelle entreprise
        new_company_data = {
            'company_name': company_name,
            'siren': lead_data.get('siren'),
            'website': domain,
            'city': lead_data.get('city') or lead_data.get('company_city'),
            'country': lead_data.get('country', 'FR'),
            'source': lead_data.get('source', 'getsales'),
            'campaign_id': lead_data.get('campaign_id'),
        }

        company_id = self.create_company(new_company_data)
        logger.info(f"Nouvelle entreprise créée: {company_name} (ID: {company_id})")
        return company_id, True

    # =========================================================================
    # FUSION
    # =========================================================================

    def merge_companies(self, company_id_keep: int, company_id_merge: int) -> bool:
        """
        Fusionne deux entreprises en une seule.

        - Migre tous les contacts de company_merge vers company_keep
        - Enrichit company_keep avec données manquantes
        - Marque company_merge comme 'duplicate'

        Args:
            company_id_keep: ID de l'entreprise à conserver
            company_id_merge: ID de l'entreprise à fusionner

        Returns:
            True si fusion réussie
        """
        if company_id_keep == company_id_merge:
            raise ValueError("Impossible de fusionner une entreprise avec elle-même")

        company_keep = self.get_company(company_id_keep)
        company_merge = self.get_company(company_id_merge)

        if not company_keep or not company_merge:
            raise ValueError("Une des entreprises n'existe pas")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 1. Migrer tous les contacts
            cursor.execute("""
                UPDATE contacts SET company_id = ? WHERE company_id = ?
            """, (company_id_keep, company_id_merge))
            migrated_contacts = cursor.rowcount

            # 2. Enrichir company_keep avec données manquantes
            fields_to_merge = [
                'siren', 'siret_list', 'website', 'ape_code', 'ape_label',
                'legal_form', 'address', 'postal_code', 'city', 'region',
                'employee_range', 'revenue_range', 'company_phone', 'company_email',
                'hubspot_company_id'
            ]

            updates = []
            values = []

            for field in fields_to_merge:
                if not company_keep.get(field) and company_merge.get(field):
                    updates.append(f"{field} = ?")
                    values.append(company_merge[field])

            if updates:
                updates.append("updated_at = ?")
                values.append(datetime.now())
                values.append(company_id_keep)

                cursor.execute(
                    f"UPDATE companies SET {', '.join(updates)} WHERE id = ?",
                    values
                )

            # 3. Marquer company_merge comme duplicate
            cursor.execute("""
                UPDATE companies SET status = 'duplicate', updated_at = ?
                WHERE id = ?
            """, (datetime.now(), company_id_merge))

            # 4. Mettre à jour les stats
            self._update_company_stats_single(cursor, company_id_keep)

            conn.commit()

            logger.info(
                f"Fusion réussie: {company_merge['company_name']} → {company_keep['company_name']} "
                f"({migrated_contacts} contacts migrés)"
            )
            return True

    # =========================================================================
    # STATS
    # =========================================================================

    def update_company_stats(self, company_id: int):
        """Recalcule les stats agrégées d'une entreprise."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            self._update_company_stats_single(cursor, company_id)
            conn.commit()

    def _update_company_stats_single(self, cursor: sqlite3.Cursor, company_id: int):
        """Helper pour mise à jour stats (sans commit)."""
        cursor.execute("""
            UPDATE companies SET
                total_contacts = (
                    SELECT COUNT(*) FROM contacts WHERE company_id = ?
                ),
                total_messages_sent = (
                    SELECT COALESCE(SUM(messages_sent), 0) FROM contacts WHERE company_id = ?
                ),
                total_messages_received = (
                    SELECT COALESCE(SUM(messages_received), 0) FROM contacts WHERE company_id = ?
                ),
                last_contact_interaction_at = (
                    SELECT MAX(last_interaction_at) FROM contacts WHERE company_id = ?
                ),
                updated_at = ?
            WHERE id = ?
        """, (company_id, company_id, company_id, company_id, datetime.now(), company_id))

    def update_all_company_stats(self):
        """Met à jour les stats de toutes les entreprises."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT id FROM companies WHERE status = 'active'")
            company_ids = [row[0] for row in cursor.fetchall()]

            for company_id in company_ids:
                self._update_company_stats_single(cursor, company_id)

            conn.commit()
            logger.info(f"Stats mises à jour pour {len(company_ids)} entreprises")

    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques globales des entreprises."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Total actives
            cursor.execute("SELECT COUNT(*) FROM companies WHERE status = 'active'")
            total = cursor.fetchone()[0]

            # Avec SIREN
            cursor.execute("""
                SELECT COUNT(*) FROM companies
                WHERE status = 'active' AND siren IS NOT NULL AND siren != ''
            """)
            with_siren = cursor.fetchone()[0]

            # Avec contacts
            cursor.execute("""
                SELECT COUNT(*) FROM companies
                WHERE status = 'active' AND total_contacts > 0
            """)
            with_contacts = cursor.fetchone()[0]

            # Par source
            cursor.execute("""
                SELECT source, COUNT(*) as count
                FROM companies
                WHERE status = 'active'
                GROUP BY source
            """)
            by_source = {row[0]: row[1] for row in cursor.fetchall()}

            # Par prospection_status
            cursor.execute("""
                SELECT prospection_status, COUNT(*) as count
                FROM companies
                WHERE status = 'active'
                GROUP BY prospection_status
            """)
            by_status = {row[0] or 'new': row[1] for row in cursor.fetchall()}

            # Top villes
            cursor.execute("""
                SELECT city, COUNT(*) as count
                FROM companies
                WHERE status = 'active' AND city IS NOT NULL AND city != ''
                GROUP BY city
                ORDER BY count DESC
                LIMIT 10
            """)
            top_cities = [{'city': row[0], 'count': row[1]} for row in cursor.fetchall()]

            return {
                'total_companies': total,
                'with_siren': with_siren,
                'with_contacts': with_contacts,
                'by_source': by_source,
                'by_prospection_status': by_status,
                'top_cities': top_cities,
            }

    # =========================================================================
    # UTILITAIRES
    # =========================================================================

    def _normalize_company_name(self, name: str) -> str:
        """Normalise un nom d'entreprise pour la comparaison."""
        if not name:
            return ""

        normalized = name.lower().strip()

        # Supprimer formes juridiques courantes
        for suffix in [' sas', ' sarl', ' sa', ' eurl', ' sasu', ' sci', ' snc', ' inc', ' ltd', ' gmbh']:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)].strip()

        # Supprimer caractères spéciaux
        normalized = ''.join(c for c in normalized if c.isalnum() or c == ' ')

        # Supprimer espaces multiples
        normalized = ' '.join(normalized.split())

        return normalized

    def _normalize_domain(self, url: str) -> str:
        """Extrait et normalise le domaine d'une URL."""
        if not url:
            return ""

        domain = url.lower().strip()

        # Supprimer protocole
        for prefix in ['https://', 'http://', 'www.']:
            if domain.startswith(prefix):
                domain = domain[len(prefix):]

        # Supprimer path
        domain = domain.split('/')[0]

        return domain

    def _similarity(self, s1: str, s2: str) -> float:
        """Calcule la similarité entre deux chaînes (Levenshtein normalisé)."""
        if not s1 or not s2:
            return 0.0
        if s1 == s2:
            return 1.0

        len1, len2 = len(s1), len(s2)
        if len1 < len2:
            s1, s2 = s2, s1
            len1, len2 = len2, len1

        if len1 - len2 > max(len1, len2) * 0.3:
            return 0.0

        previous_row = range(len2 + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        distance = previous_row[-1]
        max_len = max(len1, len2)
        return 1.0 - (distance / max_len)

    # =========================================================================
    # HUBSPOT
    # =========================================================================

    def mark_synced_hubspot(self, company_id: int, hubspot_company_id: str) -> bool:
        """Marque une entreprise comme synchronisée vers HubSpot."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE companies SET
                    hubspot_company_id = ?,
                    synced_to_hubspot = 1,
                    last_sync_hubspot = ?,
                    updated_at = ?
                WHERE id = ?
            """, (hubspot_company_id, datetime.now(), datetime.now(), company_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_companies_to_sync(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Récupère les entreprises non synchronisées vers HubSpot."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM companies
                WHERE status = 'active'
                  AND synced_to_hubspot = 0
                  AND total_contacts > 0
                ORDER BY total_contacts DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def import_from_hubspot(self, companies: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Importe des entreprises depuis HubSpot.

        Matching hiérarchique:
        1. hubspot_company_id (exact)
        2. siren (exact)
        3. website/domain (exact)
        4. company_name (fuzzy, >90%)

        Args:
            companies: Liste de dicts HubSpot company

        Returns:
            Tuple (added, updated)
        """
        added = 0
        updated = 0

        # Mapping HubSpot → local
        field_mapping = {
            'name': 'company_name',
            'company_name': 'company_name',
            'domain': 'website',
            'website': 'website',
            'city': 'city',
            'address': 'address',
            'zip': 'postal_code',
            'postal_code': 'postal_code',
            'country': 'country',
            'siren': 'siren',
            'numberofemployees': 'employee_range',
            'employee_range': 'employee_range',
            'annualrevenue': 'revenue_range',
            'revenue_range': 'revenue_range',
            'industry': 'ape_label',
            'hubspot_company_id': 'hubspot_company_id',
            'id': 'hubspot_company_id',
        }

        for hs_company in companies:
            # Normaliser les données
            company_data = {}
            for hs_key, local_key in field_mapping.items():
                if hs_key in hs_company and hs_company[hs_key]:
                    company_data[local_key] = hs_company[hs_key]

            if not company_data.get('company_name'):
                logger.warning(f"Company HubSpot sans nom, ignorée: {hs_company}")
                continue

            # Chercher entreprise existante
            existing = None
            hubspot_id = company_data.get('hubspot_company_id')
            siren = company_data.get('siren')
            website = company_data.get('website')
            company_name = company_data.get('company_name')

            # 1. Par hubspot_company_id
            if hubspot_id:
                existing = self.find_by_hubspot_id(hubspot_id)

            # 2. Par SIREN
            if not existing and siren:
                existing = self.find_by_siren(siren)

            # 3. Par website
            if not existing and website:
                existing = self.find_by_website(website)

            # 4. Par nom fuzzy
            if not existing and company_name:
                fuzzy_matches = self.find_by_name_fuzzy(company_name, threshold=0.90, limit=1)
                if fuzzy_matches:
                    existing = fuzzy_matches[0]['company']

            if existing:
                # Mettre à jour l'entreprise existante
                update_data = {}
                for key, value in company_data.items():
                    if value and key != 'hubspot_company_id':
                        # Ne pas écraser si valeur existante
                        if not existing.get(key) or existing.get(key) != value:
                            update_data[key] = value

                # Toujours mettre à jour le hubspot_company_id
                if hubspot_id and existing.get('hubspot_company_id') != hubspot_id:
                    update_data['hubspot_company_id'] = hubspot_id

                if update_data:
                    self.update_company(existing['id'], update_data)
                    updated += 1
                    logger.debug(f"Company mise à jour: {company_name}")
            else:
                # Créer une nouvelle entreprise
                try:
                    company_data['source'] = 'hubspot'
                    self.create_company(company_data)
                    added += 1
                    logger.debug(f"Company créée: {company_name}")
                except Exception as e:
                    logger.warning(f"Erreur création company {company_name}: {e}")

        logger.info(f"Import HubSpot companies: {added} ajoutées, {updated} mises à jour")
        return added, updated

    # =========================================================================
    # CLASSIFICATION & SEGMENTATION (SIREN v2)
    # =========================================================================

    def set_segment(self, company_id: int, segment: str) -> bool:
        """
        Définit le segment d'une entreprise.

        Args:
            company_id: ID de l'entreprise
            segment: Segment à assigner ('ICP Principal', 'ICP Opportuniste', etc.)

        Returns:
            True si mis à jour
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE companies SET segment = ?, updated_at = ?
                WHERE id = ?
            """, (segment, datetime.now(), company_id))
            conn.commit()
            return cursor.rowcount > 0

    def set_segment_batch(self, company_ids: List[int], segment: str) -> int:
        """
        Définit le segment pour plusieurs entreprises.

        Args:
            company_ids: Liste des IDs
            segment: Segment à assigner

        Returns:
            Nombre d'entreprises mises à jour
        """
        if not company_ids:
            return 0

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            placeholders = ','.join(['?' for _ in company_ids])
            cursor.execute(f"""
                UPDATE companies SET segment = ?, updated_at = ?
                WHERE id IN ({placeholders})
            """, [segment, datetime.now()] + list(company_ids))
            conn.commit()
            return cursor.rowcount

    def classify_company(self, company_id: int) -> Dict[str, Any]:
        """
        Classifie une entreprise avec ProspectClassifier.

        Args:
            company_id: ID de l'entreprise

        Returns:
            Dict avec résultat de classification
        """
        from .scoring import ProspectClassifier

        company = self.get_company(company_id)
        if not company:
            raise ValueError(f"Entreprise {company_id} non trouvée")

        classifier = ProspectClassifier()
        result = classifier.classify(company)

        # Sauvegarder la classification
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE companies SET
                    prospect_class = ?,
                    prospect_class_points = ?,
                    prospect_class_signals = ?,
                    updated_at = ?
                WHERE id = ?
            """, (
                result['prospect_class'],
                result['points'],
                json.dumps(result['signals'], ensure_ascii=False),
                datetime.now(),
                company_id
            ))
            conn.commit()

        return result

    def classify_batch(self, company_ids: List[int] = None) -> Dict[str, Any]:
        """
        Classifie plusieurs entreprises.

        Args:
            company_ids: Liste des IDs (si None, classifie toutes les non-classifiées)

        Returns:
            Dict avec statistiques de classification
        """
        from .scoring import ProspectClassifier

        classifier = ProspectClassifier()
        stats = {'total': 0, 'A': 0, 'B': 0, 'C': 0}

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if company_ids:
                placeholders = ','.join(['?' for _ in company_ids])
                cursor.execute(f"""
                    SELECT * FROM companies WHERE id IN ({placeholders})
                """, company_ids)
            else:
                # Classifie les entreprises sans classification
                cursor.execute("""
                    SELECT * FROM companies
                    WHERE prospect_class IS NULL AND status = 'active'
                """)

            companies = [dict(row) for row in cursor.fetchall()]

            for company in companies:
                result = classifier.classify(company)
                cursor.execute("""
                    UPDATE companies SET
                        prospect_class = ?,
                        prospect_class_points = ?,
                        prospect_class_signals = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    result['prospect_class'],
                    result['points'],
                    json.dumps(result['signals'], ensure_ascii=False),
                    datetime.now(),
                    company['id']
                ))
                stats['total'] += 1
                stats[result['prospect_class']] += 1

            conn.commit()

        return stats

    def get_companies_by_class(
        self,
        prospect_class: str,
        segment: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Récupère les entreprises par classe de prospect.

        Args:
            prospect_class: 'A', 'B', ou 'C'
            segment: Filtrer par segment (optionnel)
            limit: Nombre max de résultats

        Returns:
            Liste d'entreprises
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if segment:
                cursor.execute("""
                    SELECT * FROM companies
                    WHERE prospect_class = ? AND segment = ? AND status = 'active'
                    ORDER BY prospect_class_points DESC
                    LIMIT ?
                """, (prospect_class, segment, limit))
            else:
                cursor.execute("""
                    SELECT * FROM companies
                    WHERE prospect_class = ? AND status = 'active'
                    ORDER BY prospect_class_points DESC
                    LIMIT ?
                """, (prospect_class, limit))

            return [dict(row) for row in cursor.fetchall()]

    def get_classification_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques de classification.

        Returns:
            Dict avec stats par classe et segment
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Par classe
            cursor.execute("""
                SELECT prospect_class, COUNT(*) as count
                FROM companies
                WHERE status = 'active' AND prospect_class IS NOT NULL
                GROUP BY prospect_class
            """)
            by_class = {row[0]: row[1] for row in cursor.fetchall()}

            # Par segment
            cursor.execute("""
                SELECT segment, COUNT(*) as count
                FROM companies
                WHERE status = 'active' AND segment IS NOT NULL
                GROUP BY segment
            """)
            by_segment = {row[0]: row[1] for row in cursor.fetchall()}

            # Non classifiées
            cursor.execute("""
                SELECT COUNT(*) FROM companies
                WHERE status = 'active' AND prospect_class IS NULL
            """)
            unclassified = cursor.fetchone()[0]

            return {
                'by_class': by_class,
                'by_segment': by_segment,
                'unclassified': unclassified,
                'total_classified': sum(by_class.values())
            }

    def add_tag(self, company_id: int, tag: str) -> bool:
        """
        Ajoute un tag à une entreprise.

        Args:
            company_id: ID de l'entreprise
            tag: Tag à ajouter

        Returns:
            True si ajouté
        """
        company = self.get_company(company_id)
        if not company:
            return False

        # Parser les tags existants
        existing_tags = []
        if company.get('tags'):
            try:
                existing_tags = json.loads(company['tags'])
            except (json.JSONDecodeError, TypeError):
                existing_tags = []

        # Ajouter le nouveau tag s'il n'existe pas
        if tag not in existing_tags:
            existing_tags.append(tag)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE companies SET tags = ?, updated_at = ?
                WHERE id = ?
            """, (json.dumps(existing_tags, ensure_ascii=False), datetime.now(), company_id))
            conn.commit()
            return cursor.rowcount > 0

    def remove_tag(self, company_id: int, tag: str) -> bool:
        """
        Supprime un tag d'une entreprise.

        Args:
            company_id: ID de l'entreprise
            tag: Tag à supprimer

        Returns:
            True si supprimé
        """
        company = self.get_company(company_id)
        if not company:
            return False

        existing_tags = []
        if company.get('tags'):
            try:
                existing_tags = json.loads(company['tags'])
            except (json.JSONDecodeError, TypeError):
                existing_tags = []

        if tag in existing_tags:
            existing_tags.remove(tag)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE companies SET tags = ?, updated_at = ?
                WHERE id = ?
            """, (json.dumps(existing_tags, ensure_ascii=False), datetime.now(), company_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_companies_by_tag(self, tag: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Récupère les entreprises par tag.

        Args:
            tag: Tag à rechercher
            limit: Nombre max de résultats

        Returns:
            Liste d'entreprises
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Recherche JSON (SQLite LIKE pour simplifier)
            cursor.execute("""
                SELECT * FROM companies
                WHERE status = 'active' AND tags LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (f'%"{tag}"%', limit))
            return [dict(row) for row in cursor.fetchall()]

    # =========================================================================
    # ENRICHISSEMENT PAPPERS (SIREN v2 - Phase 4)
    # =========================================================================

    def enrich_with_pappers(self, company_id: int, pappers_client=None) -> Dict[str, Any]:
        """
        Enrichit une entreprise avec les données Pappers.

        Cette méthode:
        1. Récupère les données Pappers (dirigeants, CA, téléphone, email)
        2. Met à jour l'entreprise avec les nouvelles données
        3. Crée des contacts pour chaque dirigeant trouvé
        4. Re-classifie l'entreprise avec les nouvelles données

        Args:
            company_id: ID de l'entreprise à enrichir
            pappers_client: Instance PappersClient (optionnel, créé si non fourni)

        Returns:
            Dict avec résultats:
            - success: bool
            - company_updated: bool
            - contacts_created: int
            - new_classification: str (A/B/C)
            - data: dict des données Pappers récupérées
        """
        from .pappers_client import PappersClient
        from .contact_manager import ContactManager

        result = {
            'success': False,
            'company_updated': False,
            'contacts_created': 0,
            'new_classification': None,
            'data': {},
            'error': None
        }

        # Récupérer l'entreprise
        company = self.get_company(company_id)
        if not company:
            result['error'] = f"Entreprise {company_id} non trouvée"
            return result

        siren = company.get('siren')
        if not siren:
            result['error'] = "Entreprise sans SIREN, impossible d'enrichir"
            return result

        # Appeler Pappers
        close_client = False
        if pappers_client is None:
            pappers_client = PappersClient()
            close_client = True

        try:
            pappers_data = pappers_client.get_company(siren)
            if not pappers_data:
                result['error'] = f"Aucune donnée Pappers pour SIREN {siren}"
                return result

            # Extraire les informations de contact
            contact_info = pappers_client.extract_contact_info(pappers_data)
            result['data'] = contact_info

            # Mettre à jour l'entreprise
            update_data = {}

            # Email et téléphone
            if contact_info.get('email') and not company.get('email'):
                update_data['email'] = contact_info['email']
            if contact_info.get('telephone') and not company.get('phone'):
                update_data['phone'] = contact_info['telephone']
            if contact_info.get('site_web') and not company.get('website'):
                update_data['website'] = contact_info['site_web']

            # Chiffre d'affaires
            if contact_info.get('chiffre_affaires'):
                try:
                    ca = float(contact_info['chiffre_affaires'])
                    update_data['revenue_range'] = f"{ca:,.0f}€"
                except (ValueError, TypeError):
                    pass

            # Effectif précis depuis Pappers
            effectif = pappers_data.get('effectif')
            if effectif and not company.get('employee_range'):
                update_data['employee_range'] = str(effectif)

            # Marquer comme enrichi
            update_data['enriched'] = True
            update_data['enriched_at'] = datetime.now()
            update_data['enrichment_source'] = 'pappers'
            update_data['enrichment_quality'] = 'high' if contact_info.get('email') else 'medium'

            if update_data:
                self.update_company(company_id, update_data)
                result['company_updated'] = True

            # Créer des contacts pour les dirigeants
            representants = pappers_data.get('representants', [])
            contact_manager = ContactManager()

            for rep in representants:
                # Ignorer les personnes morales
                if rep.get('personne_morale', True):
                    continue

                nom = rep.get('nom', '')
                prenom = rep.get('prenom', '')
                fonction = rep.get('qualite', '')

                if not nom:
                    continue

                # Vérifier si le contact existe déjà pour cette entreprise
                existing_contacts = contact_manager.get_contacts_by_company(company_id, limit=100)
                contact_exists = any(
                    c.get('lastname', '').lower() == nom.lower() and
                    c.get('firstname', '').lower() == prenom.lower()
                    for c in existing_contacts
                )

                if not contact_exists:
                    contact_data = {
                        'firstname': prenom,
                        'lastname': nom,
                        'job_title': fonction,
                        'email': contact_info.get('email') if result['contacts_created'] == 0 else None,
                        'phone': contact_info.get('telephone') if result['contacts_created'] == 0 else None,
                    }
                    # Filtrer les None
                    contact_data = {k: v for k, v in contact_data.items() if v}

                    if contact_data:
                        contact_manager.add_contact_with_company(
                            data=contact_data,
                            source='pappers',
                            company_id=company_id
                        )
                        result['contacts_created'] += 1

            # Re-classifier l'entreprise avec les nouvelles données
            classification_result = self.classify_company(company_id)
            result['new_classification'] = classification_result.get('prospect_class')

            result['success'] = True

        except Exception as e:
            result['error'] = str(e)
        finally:
            if close_client:
                pappers_client.close()

        return result

    def enrich_batch(
        self,
        company_ids: List[int],
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Enrichit plusieurs entreprises avec Pappers.

        Args:
            company_ids: Liste des IDs d'entreprises
            progress_callback: Fonction callback(current, total)

        Returns:
            Dict avec statistiques d'enrichissement
        """
        from .pappers_client import PappersClient

        stats = {
            'total': len(company_ids),
            'enriched': 0,
            'contacts_created': 0,
            'errors': [],
            'by_class': {'A': 0, 'B': 0, 'C': 0}
        }

        if not company_ids:
            return stats

        with PappersClient() as pappers:
            for i, company_id in enumerate(company_ids):
                if progress_callback:
                    progress_callback(i + 1, len(company_ids))

                result = self.enrich_with_pappers(company_id, pappers_client=pappers)

                if result['success']:
                    stats['enriched'] += 1
                    stats['contacts_created'] += result['contacts_created']
                    if result['new_classification']:
                        stats['by_class'][result['new_classification']] += 1
                else:
                    stats['errors'].append({
                        'company_id': company_id,
                        'error': result.get('error')
                    })

        return stats

    def get_companies_to_enrich(
        self,
        segment: str = None,
        prospect_class: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Récupère les entreprises candidates à l'enrichissement.

        Priorité:
        1. Entreprises non enrichies avec SIREN
        2. Triées par classe (A > B > C)
        3. Triées par segment si spécifié

        Args:
            segment: Filtrer par segment
            prospect_class: Filtrer par classe
            limit: Nombre max

        Returns:
            Liste d'entreprises
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            conditions = [
                "status = 'active'",
                "siren IS NOT NULL",
                "(enriched = 0 OR enriched IS NULL)"
            ]
            params = []

            if segment:
                conditions.append("segment = ?")
                params.append(segment)

            if prospect_class:
                conditions.append("prospect_class = ?")
                params.append(prospect_class)

            where_clause = " AND ".join(conditions)
            params.append(limit)

            cursor.execute(f"""
                SELECT * FROM companies
                WHERE {where_clause}
                ORDER BY
                    CASE prospect_class
                        WHEN 'A' THEN 1
                        WHEN 'B' THEN 2
                        WHEN 'C' THEN 3
                        ELSE 4
                    END,
                    created_at DESC
                LIMIT ?
            """, params)

            return [dict(row) for row in cursor.fetchall()]
