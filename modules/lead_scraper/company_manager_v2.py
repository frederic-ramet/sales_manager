"""
CompanyManager V2 - Gestionnaire des entreprises (Schema V2).

Pipeline: Import → Clean → Enrich → Sync

Usage:
    manager = CompanyManagerV2()

    # Import avec matching
    uuid = manager.find_or_create({
        'name': 'Airbus',
        'domain': 'airbus.com',
        'siren': '383474814'
    }, source='csv')

    # Déduplication
    duplicates = manager.find_duplicates()
    manager.merge(master_uuid, [dup1_uuid, dup2_uuid])
"""

import sqlite3
import logging
import json
import uuid as uuid_lib
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "leads.db"


class CompanyManagerV2:
    """
    Gestionnaire des entreprises - Schema V2.

    Clés de matching (priorité):
    1. SIREN (exact) - 100%
    2. Domain (exact) - 95%
    3. Name fuzzy + City - 85%
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(DEFAULT_DB_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _generate_uuid(self) -> str:
        return str(uuid_lib.uuid4())

    def _normalize_name(self, name: str) -> str:
        """Normalise un nom d'entreprise pour comparaison."""
        if not name:
            return ""
        normalized = name.lower().strip()
        # Retirer formes juridiques
        for suffix in [' sas', ' sarl', ' sa', ' eurl', ' sasu', ' sci', ' snc', ' inc', ' ltd', ' gmbh', ' s.a.s', ' s.a.r.l']:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)].strip()
        # Retirer caractères spéciaux
        normalized = ''.join(c for c in normalized if c.isalnum() or c == ' ')
        return ' '.join(normalized.split())

    def _normalize_domain(self, url: str) -> str:
        """Extrait et normalise le domaine."""
        if not url:
            return ""
        domain = url.lower().strip()
        for prefix in ['https://', 'http://', 'www.']:
            if domain.startswith(prefix):
                domain = domain[len(prefix):]
        return domain.split('/')[0]

    def _similarity(self, s1: str, s2: str) -> float:
        """Calcule la similarité (Levenshtein normalisé)."""
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
        return 1 - (previous_row[-1] / max(len1, len2))

    # =========================================================================
    # CRUD
    # =========================================================================

    def create(self, data: Dict[str, Any], source: str = 'manual') -> str:
        """
        Crée une nouvelle entreprise.

        Args:
            data: Données de l'entreprise
            source: Source de l'import ('csv', 'hubspot', 'getsales', 'sirene', 'pappers')

        Returns:
            UUID de l'entreprise créée
        """
        if not data.get('name'):
            raise ValueError("'name' est requis")

        company_uuid = self._generate_uuid()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO companies (
                    uuid, siren, siret, hubspot_company_id,
                    name, domain, legal_form,
                    hq_address, hq_city, hq_state, hq_postal_code, hq_country,
                    ape_code, ape_label, industry, description,
                    size, size_exact, revenue, revenue_range,
                    investment_stage, investment_amount, investment_date, lead_investor,
                    founded_date, technology_used,
                    source, source_file,
                    status
                ) VALUES (
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?,
                    ?, ?,
                    'active'
                )
            """, (
                company_uuid,
                data.get('siren'),
                data.get('siret'),
                data.get('hubspot_company_id'),
                data.get('name'),
                self._normalize_domain(data.get('domain') or data.get('website') or ''),
                data.get('legal_form'),
                data.get('hq_address') or data.get('address'),
                data.get('hq_city') or data.get('city'),
                data.get('hq_state') or data.get('state') or data.get('region'),
                data.get('hq_postal_code') or data.get('postal_code'),
                data.get('hq_country') or data.get('country') or 'France',
                data.get('ape_code'),
                data.get('ape_label'),
                data.get('industry'),
                data.get('description'),
                data.get('size'),
                data.get('size_exact'),
                data.get('revenue'),
                data.get('revenue_range'),
                data.get('investment_stage'),
                data.get('investment_amount'),
                data.get('investment_date'),
                data.get('lead_investor'),
                data.get('founded_date'),
                data.get('technology_used'),
                source,
                data.get('source_file'),
            ))
            conn.commit()
            logger.debug(f"Company créée: {data.get('name')} ({company_uuid})")
            return company_uuid

    def get(self, company_uuid: str) -> Optional[Dict[str, Any]]:
        """Récupère une entreprise par UUID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM companies WHERE uuid = ?", (company_uuid,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update(self, company_uuid: str, data: Dict[str, Any]) -> bool:
        """Met à jour une entreprise."""
        if not data:
            return False

        # Champs autorisés
        allowed_fields = {
            'siren', 'siret', 'hubspot_company_id', 'name', 'domain', 'legal_form',
            'hq_address', 'hq_city', 'hq_state', 'hq_postal_code', 'hq_country',
            'ape_code', 'ape_label', 'industry', 'description',
            'size', 'size_exact', 'revenue', 'revenue_range',
            'investment_stage', 'investment_amount', 'investment_date', 'lead_investor',
            'founded_date', 'technology_used',
            'enriched_at', 'enrichment_source',
            'synced_to_hubspot', 'last_sync_hubspot',
            'status', 'notes'
        }

        updates = {k: v for k, v in data.items() if k in allowed_fields}
        if not updates:
            return False

        updates['updated_at'] = datetime.now()

        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [company_uuid]

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE companies SET {set_clause} WHERE uuid = ?", values)
            conn.commit()
            return cursor.rowcount > 0

    def delete(self, company_uuid: str, soft: bool = True) -> bool:
        """Supprime une entreprise (soft delete par défaut)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if soft:
                cursor.execute(
                    "UPDATE companies SET status = 'deleted', updated_at = ? WHERE uuid = ?",
                    (datetime.now(), company_uuid)
                )
            else:
                cursor.execute("DELETE FROM companies WHERE uuid = ?", (company_uuid,))
            conn.commit()
            return cursor.rowcount > 0

    # =========================================================================
    # RECHERCHE / MATCHING
    # =========================================================================

    def find_by_siren(self, siren: str) -> Optional[Dict[str, Any]]:
        """Trouve une entreprise par SIREN."""
        if not siren or len(siren) < 9:
            return None
        siren_clean = ''.join(c for c in siren if c.isdigit())[:9]
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM companies WHERE siren = ? AND status = 'active'",
                (siren_clean,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_by_domain(self, domain: str) -> Optional[Dict[str, Any]]:
        """Trouve une entreprise par domaine."""
        domain_norm = self._normalize_domain(domain)
        if not domain_norm or len(domain_norm) < 4:
            return None
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM companies WHERE domain = ? AND status = 'active'",
                (domain_norm,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_by_hubspot_id(self, hubspot_id: str) -> Optional[Dict[str, Any]]:
        """Trouve une entreprise par HubSpot ID."""
        if not hubspot_id:
            return None
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM companies WHERE hubspot_company_id = ? AND status = 'active'",
                (str(hubspot_id),)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_by_name_fuzzy(self, name: str, city: str = None, threshold: float = 0.85) -> Optional[Dict[str, Any]]:
        """Trouve une entreprise par nom (fuzzy matching)."""
        if not name:
            return None
        name_norm = self._normalize_name(name)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if city:
                cursor.execute(
                    "SELECT * FROM companies WHERE status = 'active' AND LOWER(hq_city) = LOWER(?)",
                    (city,)
                )
            else:
                cursor.execute("SELECT * FROM companies WHERE status = 'active'")

            best_match = None
            best_score = 0
            for row in cursor.fetchall():
                db_name_norm = self._normalize_name(row['name'] or '')
                score = self._similarity(name_norm, db_name_norm)
                if score >= threshold and score > best_score:
                    best_score = score
                    best_match = dict(row)

            return best_match

    def find_existing(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Trouve une entreprise existante avec matching hiérarchique.

        Ordre de priorité:
        1. hubspot_company_id (exact)
        2. SIREN (exact)
        3. Domain (exact)
        4. Name fuzzy + City
        """
        # 1. Par HubSpot ID
        if data.get('hubspot_company_id'):
            existing = self.find_by_hubspot_id(data['hubspot_company_id'])
            if existing:
                return existing

        # 2. Par SIREN
        if data.get('siren'):
            existing = self.find_by_siren(data['siren'])
            if existing:
                return existing

        # 3. Par Domain
        domain = data.get('domain') or data.get('website')
        if domain:
            existing = self.find_by_domain(domain)
            if existing:
                return existing

        # 4. Par Name + City (fuzzy)
        if data.get('name'):
            city = data.get('hq_city') or data.get('city')
            existing = self.find_by_name_fuzzy(data['name'], city=city)
            if existing:
                return existing

        return None

    def find_or_create(self, data: Dict[str, Any], source: str = 'manual') -> Tuple[str, bool]:
        """
        Trouve ou crée une entreprise avec matching intelligent.

        Returns:
            Tuple (uuid, created) - created=True si nouvelle
        """
        existing = self.find_existing(data)
        if existing:
            # Mettre à jour avec nouvelles données (complète les champs vides)
            updates = {}
            for key, value in data.items():
                if value and not existing.get(key):
                    updates[key] = value
            if updates:
                self.update(existing['uuid'], updates)
            return existing['uuid'], False
        else:
            new_uuid = self.create(data, source=source)
            return new_uuid, True

    # =========================================================================
    # LISTING / STATS
    # =========================================================================

    def list_all(
        self,
        status: str = 'active',
        source: str = None,
        limit: int = 1000,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Liste les entreprises avec filtres."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            conditions = ["status = ?"]
            params = [status]

            if source:
                conditions.append("source = ?")
                params.append(source)

            where_clause = " AND ".join(conditions)
            params.extend([limit, offset])

            cursor.execute(f"""
                SELECT * FROM companies
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, params)

            return [dict(row) for row in cursor.fetchall()]

    def count(self, status: str = 'active') -> int:
        """Compte les entreprises."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM companies WHERE status = ?", (status,))
            return cursor.fetchone()[0]

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques des entreprises."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            stats = {}

            # Total
            cursor.execute("SELECT COUNT(*) FROM companies WHERE status = 'active'")
            stats['total'] = cursor.fetchone()[0]

            # Par source
            cursor.execute("""
                SELECT source, COUNT(*) as count
                FROM companies WHERE status = 'active'
                GROUP BY source
            """)
            stats['by_source'] = {row[0]: row[1] for row in cursor.fetchall()}

            # À enrichir
            cursor.execute("""
                SELECT COUNT(*) FROM companies
                WHERE status = 'active' AND enriched_at IS NULL
            """)
            stats['to_enrich'] = cursor.fetchone()[0]

            # À synchroniser
            cursor.execute("""
                SELECT COUNT(*) FROM companies
                WHERE status = 'active' AND synced_to_hubspot = 0
            """)
            stats['to_sync'] = cursor.fetchone()[0]

            # Merged
            cursor.execute("SELECT COUNT(*) FROM companies WHERE status = 'merged'")
            stats['merged'] = cursor.fetchone()[0]

            return stats

    # =========================================================================
    # DÉDUPLICATION
    # =========================================================================

    def find_duplicates(self, threshold: float = 0.85, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Détecte les groupes de doublons.

        Returns:
            Liste de groupes: [{
                'score': float,
                'reason': str,
                'companies': [company1, company2, ...]
            }]
        """
        groups = []
        processed_uuids = set()

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT c.*,
                    (SELECT COUNT(*) FROM contacts WHERE company_uuid = c.uuid) as contact_count
                FROM companies c
                WHERE c.status = 'active'
            """)
            companies = [dict(row) for row in cursor.fetchall()]

            # 1. Par SIREN
            siren_groups = {}
            for c in companies:
                siren = c.get('siren')
                if siren and len(siren) >= 9:
                    key = siren[:9]
                    if key not in siren_groups:
                        siren_groups[key] = []
                    siren_groups[key].append(c)

            for siren, group_companies in siren_groups.items():
                if len(group_companies) > 1:
                    uuids = tuple(sorted(c['uuid'] for c in group_companies))
                    if uuids not in processed_uuids:
                        processed_uuids.add(uuids)
                        groups.append({
                            'score': 100,
                            'reason': f'SIREN identique ({siren})',
                            'companies': group_companies
                        })

            # 2. Par Domain
            domain_groups = {}
            grouped_uuids = {c['uuid'] for g in groups for c in g['companies']}
            for c in companies:
                if c['uuid'] in grouped_uuids:
                    continue
                domain = c.get('domain')
                if domain and len(domain) > 3:
                    if domain not in domain_groups:
                        domain_groups[domain] = []
                    domain_groups[domain].append(c)

            for domain, group_companies in domain_groups.items():
                if len(group_companies) > 1:
                    uuids = tuple(sorted(c['uuid'] for c in group_companies))
                    if uuids not in processed_uuids:
                        processed_uuids.add(uuids)
                        groups.append({
                            'score': 95,
                            'reason': f'Domain identique ({domain})',
                            'companies': group_companies
                        })

            # 3. Par nom (fuzzy)
            grouped_uuids = {c['uuid'] for g in groups for c in g['companies']}
            remaining = [c for c in companies if c['uuid'] not in grouped_uuids]

            for i, ca in enumerate(remaining):
                if ca['uuid'] in grouped_uuids:
                    continue
                name_a = ca.get('name', '')
                if not name_a:
                    continue
                name_a_norm = self._normalize_name(name_a)
                potential = [ca]

                for cb in remaining[i+1:]:
                    if cb['uuid'] in grouped_uuids:
                        continue
                    name_b = cb.get('name', '')
                    if not name_b:
                        continue
                    similarity = self._similarity(name_a_norm, self._normalize_name(name_b))
                    if similarity >= threshold:
                        # Bonus si même ville
                        city_a = (ca.get('hq_city') or '').lower()
                        city_b = (cb.get('hq_city') or '').lower()
                        if city_a and city_b and city_a == city_b:
                            similarity = min(similarity + 0.1, 1.0)
                        if similarity >= threshold:
                            potential.append(cb)
                            grouped_uuids.add(cb['uuid'])

                if len(potential) > 1:
                    grouped_uuids.add(ca['uuid'])
                    groups.append({
                        'score': round(threshold * 100),
                        'reason': f'Nom similaire',
                        'companies': potential
                    })

        groups.sort(key=lambda x: x['score'], reverse=True)
        return groups[:limit]

    def merge(
        self,
        master_uuid: str,
        duplicate_uuids: List[str],
        sync_hubspot: bool = False
    ) -> Dict[str, Any]:
        """
        Fusionne des entreprises vers le master.

        1. Transfère les contacts
        2. Complète les données du master
        3. Renomme les doublons en '_todelete'
        """
        result = {
            'success': False,
            'contacts_moved': 0,
            'companies_merged': 0,
            'errors': []
        }

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Get master
                cursor.execute("SELECT * FROM companies WHERE uuid = ?", (master_uuid,))
                master_row = cursor.fetchone()
                if not master_row:
                    result['errors'].append(f"Master {master_uuid} non trouvé")
                    return result
                master = dict(master_row)

                for dup_uuid in duplicate_uuids:
                    if dup_uuid == master_uuid:
                        continue

                    cursor.execute("SELECT * FROM companies WHERE uuid = ?", (dup_uuid,))
                    dup_row = cursor.fetchone()
                    if not dup_row:
                        continue
                    dup = dict(dup_row)

                    # 1. Transférer contacts
                    cursor.execute("""
                        UPDATE contacts SET company_uuid = ?, updated_at = ?
                        WHERE company_uuid = ?
                    """, (master_uuid, datetime.now(), dup_uuid))
                    result['contacts_moved'] += cursor.rowcount

                    # 2. Compléter master
                    fields_to_merge = [
                        'siren', 'domain', 'hq_address', 'hq_city', 'hq_postal_code',
                        'ape_code', 'ape_label', 'industry', 'size', 'revenue'
                    ]
                    for field in fields_to_merge:
                        if not master.get(field) and dup.get(field):
                            cursor.execute(
                                f"UPDATE companies SET {field} = ? WHERE uuid = ?",
                                (dup[field], master_uuid)
                            )

                    # 3. Renommer doublon
                    new_name = f"{dup.get('name', 'Unknown')}_todelete"
                    cursor.execute("""
                        UPDATE companies SET
                            name = ?, status = 'merged',
                            merged_into = ?, merged_at = ?, updated_at = ?
                        WHERE uuid = ?
                    """, (new_name, master_uuid, datetime.now(), datetime.now(), dup_uuid))

                    result['companies_merged'] += 1

                conn.commit()
                result['success'] = True

        except Exception as e:
            result['errors'].append(str(e))
            logger.error(f"Erreur merge: {e}")

        return result

    def get_merged(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Récupère les entreprises fusionnées (_todelete)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.*, m.name as merged_into_name
                FROM companies c
                LEFT JOIN companies m ON c.merged_into = m.uuid
                WHERE c.status = 'merged'
                ORDER BY c.merged_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    # =========================================================================
    # IMPORT HELPERS
    # =========================================================================

    def import_from_csv_data(
        self,
        rows: List[Dict[str, Any]],
        source_file: str = None
    ) -> Dict[str, Any]:
        """
        Importe des données CSV avec matching intelligent.

        Args:
            rows: Liste de dicts avec données entreprise
            source_file: Nom du fichier source

        Returns:
            Rapport d'import
        """
        report = {
            'created': 0,
            'updated': 0,
            'matched': 0,
            'errors': []
        }

        for row in rows:
            try:
                # Mapper les champs CSV
                data = self._map_csv_fields(row)
                data['source_file'] = source_file

                uuid, created = self.find_or_create(data, source='csv')

                if created:
                    report['created'] += 1
                else:
                    report['matched'] += 1
                    report['updated'] += 1  # find_or_create met à jour les champs vides

            except Exception as e:
                report['errors'].append(f"Row error: {e}")

        return report

    def _map_csv_fields(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Mappe les champs CSV vers le schema."""
        mapping = {
            # Company name
            'name': ['Company', 'Company 1 Name', 'company_name', 'name', 'Name'],
            # Domain
            'domain': ['Domain', 'Company 1 Website', 'website', 'Website'],
            # Size
            'size': ['Size', 'Company 1 Size', 'size', 'employee_range'],
            # Revenue
            'revenue': ['Company 1 Revenue', 'revenue', 'Revenue'],
            # Location
            'hq_city': ['Company 1 HQ City', 'city', 'City', 'Geo - company'],
            'hq_state': ['Company 1 HQ State', 'state', 'State', 'region'],
            'hq_country': ['Company 1 HQ Country', 'country', 'Country'],
            # Industry
            'industry': ['Company 1 Industries', 'industry', 'Industry'],
            'description': ['Company 1 Description', 'description'],
            # Investment
            'investment_stage': ['Company 1 Investment Stage'],
            'investment_amount': ['Company 1 Investment Amount'],
            'investment_date': ['Company 1 Investment Date'],
            'lead_investor': ['Company 1 Lead Investor'],
            # Other
            'founded_date': ['Company 1 Founded Date'],
            'technology_used': ['Company 1 Technology Used'],
        }

        data = {}
        for target, sources in mapping.items():
            for src in sources:
                if src in row and row[src]:
                    data[target] = row[src]
                    break

        return data
