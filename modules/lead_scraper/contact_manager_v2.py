"""
ContactManager V2 - Gestionnaire des contacts (Schema V2).

Pipeline: Import → Clean → Enrich → Sync

Usage:
    manager = ContactManagerV2()

    # Import avec matching
    uuid = manager.find_or_create({
        'firstname': 'Jean',
        'lastname': 'Dupont',
        'email': 'jean.dupont@acme.fr',
        'linkedin_url': 'https://linkedin.com/in/jeandupont'
    }, company_uuid='xxx', source='csv')

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


class ContactManagerV2:
    """
    Gestionnaire des contacts - Schema V2.

    Clés de matching (priorité):
    1. Email (exact) - 100%
    2. LinkedIn URL (exact) - 95%
    3. Phone (exact) - 90%
    4. Firstname + Lastname + Company (fuzzy) - 80%
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
        """Normalise un nom pour comparaison."""
        if not name:
            return ""
        normalized = name.lower().strip()
        # Retirer accents basiques
        accents = {'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
                   'à': 'a', 'â': 'a', 'ä': 'a',
                   'ù': 'u', 'û': 'u', 'ü': 'u',
                   'î': 'i', 'ï': 'i',
                   'ô': 'o', 'ö': 'o',
                   'ç': 'c'}
        for acc, rep in accents.items():
            normalized = normalized.replace(acc, rep)
        return normalized

    def _normalize_email(self, email: str) -> str:
        """Normalise un email."""
        if not email:
            return ""
        return email.lower().strip()

    def _normalize_phone(self, phone: str) -> str:
        """Normalise un numéro de téléphone."""
        if not phone:
            return ""
        # Garder que les chiffres
        digits = ''.join(c for c in phone if c.isdigit())
        # Gestion +33 / 0
        if digits.startswith('33') and len(digits) >= 11:
            digits = '0' + digits[2:]
        return digits

    def _normalize_linkedin(self, url: str) -> str:
        """Normalise une URL LinkedIn."""
        if not url:
            return ""
        url = url.lower().strip()
        # Extraire l'identifiant
        for prefix in ['https://', 'http://', 'www.']:
            if url.startswith(prefix):
                url = url[len(prefix):]
        # Retirer trailing slash
        url = url.rstrip('/')
        return url

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

    def create(self, data: Dict[str, Any], company_uuid: str = None, source: str = 'manual') -> str:
        """
        Crée un nouveau contact.

        Args:
            data: Données du contact
            company_uuid: UUID de l'entreprise associée
            source: Source de l'import ('csv', 'hubspot', 'getsales', 'sirene')

        Returns:
            UUID du contact créé
        """
        contact_uuid = self._generate_uuid()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO contacts (
                    uuid, company_uuid, hubspot_contact_id, getsales_uuid,
                    firstname, lastname, linkedin_url,
                    email, email_verified, email_secondary, phone, mobile,
                    job_title, seniority, department,
                    city, state, country, timezone,
                    twitter_url, github_url, facebook_url, other_social_urls,
                    source, source_file, campaign_id, project_name, search_name,
                    status, notes
                ) VALUES (
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    'active', ?
                )
            """, (
                contact_uuid,
                company_uuid,
                data.get('hubspot_contact_id'),
                data.get('getsales_uuid'),
                data.get('firstname'),
                data.get('lastname'),
                self._normalize_linkedin(data.get('linkedin_url') or ''),
                self._normalize_email(data.get('email') or ''),
                1 if data.get('email_verified') else 0,
                self._normalize_email(data.get('email_secondary') or ''),
                self._normalize_phone(data.get('phone') or ''),
                self._normalize_phone(data.get('mobile') or ''),
                data.get('job_title'),
                data.get('seniority'),
                data.get('department'),
                data.get('city'),
                data.get('state'),
                data.get('country') or 'France',
                data.get('timezone'),
                data.get('twitter_url'),
                data.get('github_url'),
                data.get('facebook_url'),
                json.dumps(data.get('other_social_urls')) if data.get('other_social_urls') else None,
                source,
                data.get('source_file'),
                data.get('campaign_id'),
                data.get('project_name'),
                data.get('search_name'),
                data.get('notes'),
            ))
            conn.commit()
            logger.debug(f"Contact créé: {data.get('firstname')} {data.get('lastname')} ({contact_uuid})")
            return contact_uuid

    def get(self, contact_uuid: str) -> Optional[Dict[str, Any]]:
        """Récupère un contact par UUID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM contacts WHERE uuid = ?", (contact_uuid,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update(self, contact_uuid: str, data: Dict[str, Any]) -> bool:
        """Met à jour un contact."""
        if not data:
            return False

        # Champs autorisés
        allowed_fields = {
            'company_uuid', 'hubspot_contact_id', 'getsales_uuid',
            'firstname', 'lastname', 'linkedin_url',
            'email', 'email_verified', 'email_secondary', 'phone', 'mobile',
            'job_title', 'seniority', 'department',
            'city', 'state', 'country', 'timezone',
            'twitter_url', 'github_url', 'facebook_url', 'other_social_urls',
            'enriched_at', 'enrichment_source',
            'synced_to_hubspot', 'last_sync_hubspot',
            'status', 'notes'
        }

        updates = {k: v for k, v in data.items() if k in allowed_fields}
        if not updates:
            return False

        updates['updated_at'] = datetime.now()

        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [contact_uuid]

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE contacts SET {set_clause} WHERE uuid = ?", values)
            conn.commit()
            return cursor.rowcount > 0

    def delete(self, contact_uuid: str, soft: bool = True) -> bool:
        """Supprime un contact (soft delete par défaut)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if soft:
                cursor.execute(
                    "UPDATE contacts SET status = 'deleted', updated_at = ? WHERE uuid = ?",
                    (datetime.now(), contact_uuid)
                )
            else:
                cursor.execute("DELETE FROM contacts WHERE uuid = ?", (contact_uuid,))
            conn.commit()
            return cursor.rowcount > 0

    # =========================================================================
    # RECHERCHE / MATCHING
    # =========================================================================

    def find_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Trouve un contact par email."""
        email_norm = self._normalize_email(email)
        if not email_norm:
            return None
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM contacts
                WHERE (email = ? OR email_secondary = ?) AND status = 'active'
            """, (email_norm, email_norm))
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_by_linkedin(self, linkedin_url: str) -> Optional[Dict[str, Any]]:
        """Trouve un contact par LinkedIn URL."""
        linkedin_norm = self._normalize_linkedin(linkedin_url)
        if not linkedin_norm or len(linkedin_norm) < 10:
            return None
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM contacts WHERE linkedin_url = ? AND status = 'active'",
                (linkedin_norm,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Trouve un contact par téléphone."""
        phone_norm = self._normalize_phone(phone)
        if not phone_norm or len(phone_norm) < 8:
            return None
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM contacts
                WHERE (phone = ? OR mobile = ?) AND status = 'active'
            """, (phone_norm, phone_norm))
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_by_hubspot_id(self, hubspot_id: str) -> Optional[Dict[str, Any]]:
        """Trouve un contact par HubSpot ID."""
        if not hubspot_id:
            return None
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM contacts WHERE hubspot_contact_id = ? AND status = 'active'",
                (str(hubspot_id),)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_by_getsales_id(self, getsales_uuid: str) -> Optional[Dict[str, Any]]:
        """Trouve un contact par GetSales UUID."""
        if not getsales_uuid:
            return None
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM contacts WHERE getsales_uuid = ? AND status = 'active'",
                (getsales_uuid,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_by_name_fuzzy(
        self,
        firstname: str,
        lastname: str,
        company_uuid: str = None,
        threshold: float = 0.80
    ) -> Optional[Dict[str, Any]]:
        """Trouve un contact par nom (fuzzy matching)."""
        if not firstname and not lastname:
            return None

        firstname_norm = self._normalize_name(firstname or '')
        lastname_norm = self._normalize_name(lastname or '')
        fullname_norm = f"{firstname_norm} {lastname_norm}".strip()

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if company_uuid:
                cursor.execute(
                    "SELECT * FROM contacts WHERE status = 'active' AND company_uuid = ?",
                    (company_uuid,)
                )
            else:
                cursor.execute("SELECT * FROM contacts WHERE status = 'active'")

            best_match = None
            best_score = 0
            for row in cursor.fetchall():
                db_first = self._normalize_name(row['firstname'] or '')
                db_last = self._normalize_name(row['lastname'] or '')
                db_fullname = f"{db_first} {db_last}".strip()

                score = self._similarity(fullname_norm, db_fullname)
                if score >= threshold and score > best_score:
                    best_score = score
                    best_match = dict(row)

            return best_match

    def find_existing(self, data: Dict[str, Any], company_uuid: str = None) -> Optional[Dict[str, Any]]:
        """
        Trouve un contact existant avec matching hiérarchique.

        Ordre de priorité:
        1. hubspot_contact_id (exact)
        2. getsales_uuid (exact)
        3. Email (exact)
        4. LinkedIn URL (exact)
        5. Phone (exact)
        6. Firstname + Lastname + Company (fuzzy)
        """
        # 1. Par HubSpot ID
        if data.get('hubspot_contact_id'):
            existing = self.find_by_hubspot_id(data['hubspot_contact_id'])
            if existing:
                return existing

        # 2. Par GetSales UUID
        if data.get('getsales_uuid'):
            existing = self.find_by_getsales_id(data['getsales_uuid'])
            if existing:
                return existing

        # 3. Par Email
        if data.get('email'):
            existing = self.find_by_email(data['email'])
            if existing:
                return existing

        # 4. Par LinkedIn
        if data.get('linkedin_url'):
            existing = self.find_by_linkedin(data['linkedin_url'])
            if existing:
                return existing

        # 5. Par Phone
        phone = data.get('phone') or data.get('mobile')
        if phone:
            existing = self.find_by_phone(phone)
            if existing:
                return existing

        # 6. Par Name + Company (fuzzy)
        if data.get('firstname') or data.get('lastname'):
            existing = self.find_by_name_fuzzy(
                data.get('firstname'),
                data.get('lastname'),
                company_uuid=company_uuid
            )
            if existing:
                return existing

        return None

    def find_or_create(
        self,
        data: Dict[str, Any],
        company_uuid: str = None,
        source: str = 'manual'
    ) -> Tuple[str, bool]:
        """
        Trouve ou crée un contact avec matching intelligent.

        Returns:
            Tuple (uuid, created) - created=True si nouveau
        """
        existing = self.find_existing(data, company_uuid=company_uuid)
        if existing:
            # Mettre à jour avec nouvelles données (complète les champs vides)
            updates = {}
            for key, value in data.items():
                if value and not existing.get(key):
                    updates[key] = value
            # Mettre à jour company_uuid si fourni et non défini
            if company_uuid and not existing.get('company_uuid'):
                updates['company_uuid'] = company_uuid
            if updates:
                self.update(existing['uuid'], updates)
            return existing['uuid'], False
        else:
            new_uuid = self.create(data, company_uuid=company_uuid, source=source)
            return new_uuid, True

    # =========================================================================
    # LISTING / STATS
    # =========================================================================

    def list_all(
        self,
        status: str = 'active',
        company_uuid: str = None,
        source: str = None,
        limit: int = 1000,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Liste les contacts avec filtres."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            conditions = ["status = ?"]
            params = [status]

            if company_uuid:
                conditions.append("company_uuid = ?")
                params.append(company_uuid)

            if source:
                conditions.append("source = ?")
                params.append(source)

            where_clause = " AND ".join(conditions)
            params.extend([limit, offset])

            cursor.execute(f"""
                SELECT * FROM contacts
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, params)

            return [dict(row) for row in cursor.fetchall()]

    def list_with_company(
        self,
        status: str = 'active',
        limit: int = 1000,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Liste les contacts avec données entreprise."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM contacts_with_company
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (status, limit, offset))
            return [dict(row) for row in cursor.fetchall()]

    def count(self, status: str = 'active', company_uuid: str = None) -> int:
        """Compte les contacts."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if company_uuid:
                cursor.execute(
                    "SELECT COUNT(*) FROM contacts WHERE status = ? AND company_uuid = ?",
                    (status, company_uuid)
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM contacts WHERE status = ?", (status,))
            return cursor.fetchone()[0]

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques des contacts."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            stats = {}

            # Total
            cursor.execute("SELECT COUNT(*) FROM contacts WHERE status = 'active'")
            stats['total'] = cursor.fetchone()[0]

            # Par source
            cursor.execute("""
                SELECT source, COUNT(*) as count
                FROM contacts WHERE status = 'active'
                GROUP BY source
            """)
            stats['by_source'] = {row[0]: row[1] for row in cursor.fetchall()}

            # Avec email verified
            cursor.execute("""
                SELECT COUNT(*) FROM contacts
                WHERE status = 'active' AND email_verified = 1
            """)
            stats['email_verified'] = cursor.fetchone()[0]

            # Sans entreprise
            cursor.execute("""
                SELECT COUNT(*) FROM contacts
                WHERE status = 'active' AND company_uuid IS NULL
            """)
            stats['without_company'] = cursor.fetchone()[0]

            # À synchroniser
            cursor.execute("""
                SELECT COUNT(*) FROM contacts
                WHERE status = 'active' AND synced_to_hubspot = 0
            """)
            stats['to_sync'] = cursor.fetchone()[0]

            # Merged
            cursor.execute("SELECT COUNT(*) FROM contacts WHERE status = 'merged'")
            stats['merged'] = cursor.fetchone()[0]

            return stats

    # =========================================================================
    # DÉDUPLICATION
    # =========================================================================

    def find_duplicates(self, threshold: float = 0.80, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Détecte les groupes de doublons.

        Returns:
            Liste de groupes: [{
                'score': float,
                'reason': str,
                'contacts': [contact1, contact2, ...]
            }]
        """
        groups = []
        processed_uuids = set()

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT c.*, co.name as company_name
                FROM contacts c
                LEFT JOIN companies co ON c.company_uuid = co.uuid
                WHERE c.status = 'active'
            """)
            contacts = [dict(row) for row in cursor.fetchall()]

            # 1. Par Email
            email_groups = {}
            for c in contacts:
                email = c.get('email')
                if email and len(email) > 3:
                    if email not in email_groups:
                        email_groups[email] = []
                    email_groups[email].append(c)

            for email, group_contacts in email_groups.items():
                if len(group_contacts) > 1:
                    uuids = tuple(sorted(c['uuid'] for c in group_contacts))
                    if uuids not in processed_uuids:
                        processed_uuids.add(uuids)
                        groups.append({
                            'score': 100,
                            'reason': f'Email identique ({email})',
                            'contacts': group_contacts
                        })

            # 2. Par LinkedIn
            linkedin_groups = {}
            grouped_uuids = {c['uuid'] for g in groups for c in g['contacts']}
            for c in contacts:
                if c['uuid'] in grouped_uuids:
                    continue
                linkedin = c.get('linkedin_url')
                if linkedin and len(linkedin) > 10:
                    if linkedin not in linkedin_groups:
                        linkedin_groups[linkedin] = []
                    linkedin_groups[linkedin].append(c)

            for linkedin, group_contacts in linkedin_groups.items():
                if len(group_contacts) > 1:
                    uuids = tuple(sorted(c['uuid'] for c in group_contacts))
                    if uuids not in processed_uuids:
                        processed_uuids.add(uuids)
                        groups.append({
                            'score': 95,
                            'reason': f'LinkedIn identique',
                            'contacts': group_contacts
                        })

            # 3. Par Phone
            phone_groups = {}
            grouped_uuids = {c['uuid'] for g in groups for c in g['contacts']}
            for c in contacts:
                if c['uuid'] in grouped_uuids:
                    continue
                phone = c.get('phone') or c.get('mobile')
                if phone and len(phone) >= 8:
                    if phone not in phone_groups:
                        phone_groups[phone] = []
                    phone_groups[phone].append(c)

            for phone, group_contacts in phone_groups.items():
                if len(group_contacts) > 1:
                    uuids = tuple(sorted(c['uuid'] for c in group_contacts))
                    if uuids not in processed_uuids:
                        processed_uuids.add(uuids)
                        groups.append({
                            'score': 90,
                            'reason': f'Téléphone identique',
                            'contacts': group_contacts
                        })

            # 4. Par nom (fuzzy) dans même entreprise
            grouped_uuids = {c['uuid'] for g in groups for c in g['contacts']}
            remaining = [c for c in contacts if c['uuid'] not in grouped_uuids]

            for i, ca in enumerate(remaining):
                if ca['uuid'] in grouped_uuids:
                    continue
                first_a = self._normalize_name(ca.get('firstname') or '')
                last_a = self._normalize_name(ca.get('lastname') or '')
                if not first_a and not last_a:
                    continue
                fullname_a = f"{first_a} {last_a}".strip()
                potential = [ca]

                for cb in remaining[i+1:]:
                    if cb['uuid'] in grouped_uuids:
                        continue
                    first_b = self._normalize_name(cb.get('firstname') or '')
                    last_b = self._normalize_name(cb.get('lastname') or '')
                    if not first_b and not last_b:
                        continue
                    fullname_b = f"{first_b} {last_b}".strip()

                    similarity = self._similarity(fullname_a, fullname_b)
                    if similarity >= threshold:
                        # Bonus si même entreprise
                        if ca.get('company_uuid') and ca.get('company_uuid') == cb.get('company_uuid'):
                            similarity = min(similarity + 0.15, 1.0)
                        if similarity >= threshold:
                            potential.append(cb)
                            grouped_uuids.add(cb['uuid'])

                if len(potential) > 1:
                    grouped_uuids.add(ca['uuid'])
                    groups.append({
                        'score': round(threshold * 100),
                        'reason': f'Nom similaire',
                        'contacts': potential
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
        Fusionne des contacts vers le master.

        1. Transfère les interactions
        2. Complète les données du master
        3. Renomme les doublons en '_todelete'
        """
        result = {
            'success': False,
            'interactions_moved': 0,
            'contacts_merged': 0,
            'errors': []
        }

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Get master
                cursor.execute("SELECT * FROM contacts WHERE uuid = ?", (master_uuid,))
                master_row = cursor.fetchone()
                if not master_row:
                    result['errors'].append(f"Master {master_uuid} non trouvé")
                    return result
                master = dict(master_row)

                for dup_uuid in duplicate_uuids:
                    if dup_uuid == master_uuid:
                        continue

                    cursor.execute("SELECT * FROM contacts WHERE uuid = ?", (dup_uuid,))
                    dup_row = cursor.fetchone()
                    if not dup_row:
                        continue
                    dup = dict(dup_row)

                    # 1. Transférer interactions
                    cursor.execute("""
                        UPDATE interactions SET contact_uuid = ?
                        WHERE contact_uuid = ?
                    """, (master_uuid, dup_uuid))
                    result['interactions_moved'] += cursor.rowcount

                    # 2. Compléter master
                    fields_to_merge = [
                        'email', 'linkedin_url', 'phone', 'mobile',
                        'job_title', 'seniority', 'department',
                        'city', 'company_uuid'
                    ]
                    for field in fields_to_merge:
                        if not master.get(field) and dup.get(field):
                            cursor.execute(
                                f"UPDATE contacts SET {field} = ? WHERE uuid = ?",
                                (dup[field], master_uuid)
                            )

                    # 3. Renommer doublon
                    dup_name = f"{dup.get('firstname', '')} {dup.get('lastname', '')}".strip()
                    new_lastname = f"{dup.get('lastname', 'Unknown')}_todelete"
                    cursor.execute("""
                        UPDATE contacts SET
                            lastname = ?, status = 'merged',
                            merged_into = ?, merged_at = ?, updated_at = ?
                        WHERE uuid = ?
                    """, (new_lastname, master_uuid, datetime.now(), datetime.now(), dup_uuid))

                    result['contacts_merged'] += 1

                conn.commit()
                result['success'] = True

        except Exception as e:
            result['errors'].append(str(e))
            logger.error(f"Erreur merge: {e}")

        return result

    def mark_as_homonyms(self, contact_uuids: List[str]) -> int:
        """
        Marque un groupe de contacts comme homonymes confirmés.

        Returns:
            ID du groupe créé
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Créer le groupe
            cursor.execute("""
                INSERT INTO homonym_groups (entity_type, entity_uuids, confirmed_by)
                VALUES ('contact', ?, 'user')
            """, (json.dumps(contact_uuids),))
            group_id = cursor.lastrowid

            # Mettre à jour les contacts
            for contact_uuid in contact_uuids:
                cursor.execute(
                    "UPDATE contacts SET homonym_group_id = ? WHERE uuid = ?",
                    (group_id, contact_uuid)
                )

            conn.commit()
            return group_id

    def get_merged(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Récupère les contacts fusionnés (_todelete)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.*, m.firstname as merged_into_firstname, m.lastname as merged_into_lastname
                FROM contacts c
                LEFT JOIN contacts m ON c.merged_into = m.uuid
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
        company_manager,
        source_file: str = None
    ) -> Dict[str, Any]:
        """
        Importe des données CSV avec matching intelligent.

        Args:
            rows: Liste de dicts avec données contact
            company_manager: Instance de CompanyManagerV2
            source_file: Nom du fichier source

        Returns:
            Rapport d'import
        """
        report = {
            'contacts_created': 0,
            'contacts_updated': 0,
            'contacts_matched': 0,
            'companies_created': 0,
            'companies_matched': 0,
            'errors': []
        }

        for row in rows:
            try:
                # Mapper les champs CSV
                contact_data = self._map_csv_fields_contact(row)
                company_data = self._map_csv_fields_company(row)

                contact_data['source_file'] = source_file

                # Trouver ou créer l'entreprise
                company_uuid = None
                if company_data.get('name'):
                    company_uuid, company_created = company_manager.find_or_create(
                        company_data, source='csv'
                    )
                    if company_created:
                        report['companies_created'] += 1
                    else:
                        report['companies_matched'] += 1

                # Trouver ou créer le contact
                contact_uuid, contact_created = self.find_or_create(
                    contact_data,
                    company_uuid=company_uuid,
                    source='csv'
                )

                if contact_created:
                    report['contacts_created'] += 1
                else:
                    report['contacts_matched'] += 1
                    report['contacts_updated'] += 1

            except Exception as e:
                report['errors'].append(f"Row error: {e}")

        return report

    def _map_csv_fields_contact(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Mappe les champs CSV vers le schema contact."""
        mapping = {
            # Name
            'firstname': ['First Name', 'firstname', 'FirstName', 'first_name', 'Prénom'],
            'lastname': ['Last Name', 'lastname', 'LastName', 'last_name', 'Nom'],
            # Contact
            'email': ['Email', 'email', 'Email Address', 'email_address', 'Work Email'],
            'email_verified': ['Email Verified', 'verified'],
            'phone': ['Phone', 'phone', 'Phone Number', 'Direct Dial'],
            'mobile': ['Mobile', 'mobile', 'Mobile Phone', 'Cell'],
            # LinkedIn
            'linkedin_url': ['LinkedIn', 'linkedin_url', 'LinkedIn URL', 'linkedin', 'Person Linkedin Url'],
            # Job
            'job_title': ['Title', 'Job Title', 'job_title', 'Position'],
            'seniority': ['Seniority', 'seniority', 'Level'],
            'department': ['Department', 'department', 'Function'],
            # Location
            'city': ['City', 'city', 'Person City', 'Location'],
            'state': ['State', 'state', 'Person State', 'Region'],
            'country': ['Country', 'country', 'Person Country'],
            # Social
            'twitter_url': ['Twitter', 'twitter_url', 'Twitter URL'],
            'github_url': ['Github', 'github_url', 'Github URL'],
            # GetSales specific
            'getsales_uuid': ['uuid', 'UUID', 'getsales_uuid'],
            'campaign_id': ['campaign_id', 'Campaign ID'],
            'project_name': ['project', 'Project', 'project_name'],
            'search_name': ['search', 'Search', 'search_name'],
        }

        data = {}
        for target, sources in mapping.items():
            for src in sources:
                if src in row and row[src]:
                    data[target] = row[src]
                    break

        return data

    def _map_csv_fields_company(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Mappe les champs CSV vers le schema company."""
        mapping = {
            'name': ['Company', 'Company 1 Name', 'company_name', 'name', 'Company Name'],
            'domain': ['Domain', 'Company 1 Website', 'website', 'Website', 'Company Website'],
            'size': ['Size', 'Company 1 Size', 'size', 'Company Size'],
            'industry': ['Company 1 Industries', 'industry', 'Industry'],
            'hq_city': ['Company 1 HQ City', 'city', 'Company City', 'Geo - company'],
            'hq_state': ['Company 1 HQ State', 'Company State'],
            'hq_country': ['Company 1 HQ Country', 'Company Country'],
        }

        data = {}
        for target, sources in mapping.items():
            for src in sources:
                if src in row and row[src]:
                    data[target] = row[src]
                    break

        return data
