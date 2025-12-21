"""
Service de déduplication avec fuzzy matching.

Utilisable par:
- GetSales sync
- Recherche SIRENE/Pappers
- Import CSV/fichiers

Architecture:
    matcher = DeduplicationMatcher(contact_manager)
    results = matcher.find_matches(
        firstname="Steven",
        lastname="FERREIRA",
        company_name="D-GROUPE",
        email="steven@dgroupe.fr",
        linkedin_url="https://linkedin.com/in/sferreira"
    )

    for match in results:
        print(f"{match.confidence}: {match.contact['company_name']} - {match.match_type}")

Supporte les deux schémas:
- Ancien: unified_contacts (tout dans une table)
- Nouveau: contacts + companies (tables séparées)
"""
import logging
import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class MatchConfidence(Enum):
    """Niveaux de confiance pour les matches."""
    EXACT = "exact"      # UUID, email, linkedin exact
    HIGH = "high"        # Prénom + Nom + Entreprise
    MEDIUM = "medium"    # Prénom + Nom OU Entreprise seule
    LOW = "low"          # Fuzzy matching


@dataclass
class MatchResult:
    """Résultat d'un match de déduplication (contact)."""
    contact: Dict[str, Any]          # Contact trouvé dans contacts/unified_contacts
    match_type: str                   # Type de match (email, linkedin, fullname_company, etc.)
    confidence: MatchConfidence       # Niveau de confiance
    similarity_score: float = 1.0     # Score de similarité (1.0 = exact)
    matched_fields: List[str] = field(default_factory=list)  # Champs qui ont matché

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dict pour stockage JSON."""
        return {
            'uuid': self.contact.get('uuid'),
            'company_name': self.contact.get('company_name'),
            'firstname': self.contact.get('firstname'),
            'lastname': self.contact.get('lastname'),
            'email': self.contact.get('email'),
            'linkedin_url': self.contact.get('linkedin_url'),
            'source': self.contact.get('source'),
            'match_type': self.match_type,
            'confidence': self.confidence.value,
            'similarity_score': self.similarity_score,
            'matched_fields': self.matched_fields
        }


@dataclass
class CompanyMatchResult:
    """Résultat d'un match de déduplication (entreprise) - nouveau schéma."""
    company: Dict[str, Any]          # Entreprise trouvée dans companies
    match_type: str                   # Type de match (siren, domain, name_fuzzy, etc.)
    confidence: MatchConfidence       # Niveau de confiance
    similarity_score: float = 1.0     # Score de similarité (1.0 = exact)
    matched_fields: List[str] = field(default_factory=list)  # Champs qui ont matché

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dict pour stockage JSON."""
        return {
            'id': self.company.get('id'),
            'uuid': self.company.get('uuid'),
            'company_name': self.company.get('company_name'),
            'siren': self.company.get('siren'),
            'website': self.company.get('website'),
            'city': self.company.get('city'),
            'total_contacts': self.company.get('total_contacts', 0),
            'match_type': self.match_type,
            'confidence': self.confidence.value,
            'similarity_score': self.similarity_score,
            'matched_fields': self.matched_fields
        }


class DeduplicationMatcher:
    """
    Service de déduplication avec fuzzy matching.

    Niveaux de recherche:
    1. EXACT: email, linkedin_url, siren, getsales_uuid, hubspot_id
    2. HIGH: (prénom + nom + entreprise) exact ou fuzzy > 90%
    3. MEDIUM: (prénom + nom) seul OU entreprise seule
    4. LOW: fuzzy matching < 90%
    """

    # Seuils de similarité
    FUZZY_THRESHOLD_HIGH = 0.90    # > 90% = HIGH confidence
    FUZZY_THRESHOLD_MEDIUM = 0.80  # > 80% = MEDIUM confidence
    FUZZY_THRESHOLD_LOW = 0.70     # > 70% = LOW confidence

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialise le matcher.

        Args:
            db_path: Chemin vers la base SQLite.
                     Si None, utilise le chemin par défaut.
        """
        if db_path is None:
            from pathlib import Path
            db_path = Path(__file__).parent.parent.parent / "data" / "leads.db"
        self.db_path = str(db_path)

        # Détecter le schéma (nouveau vs ancien)
        self._new_schema = self._detect_schema()
        self._contacts_table = 'contacts' if self._new_schema else 'unified_contacts'

    def _detect_schema(self) -> bool:
        """Détecte si le nouveau schéma (contacts + companies) est disponible."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='companies'
                """)
                return cursor.fetchone() is not None
        except Exception:
            return False

    @property
    def has_new_schema(self) -> bool:
        """Retourne True si le nouveau schéma est disponible."""
        return self._new_schema

    def find_matches(
        self,
        firstname: str = None,
        lastname: str = None,
        company_name: str = None,
        email: str = None,
        linkedin_url: str = None,
        siren: str = None,
        getsales_uuid: str = None,
        hubspot_contact_id: str = None,
        include_low_confidence: bool = True
    ) -> List[MatchResult]:
        """
        Trouve tous les doublons potentiels.

        Args:
            firstname: Prénom du contact
            lastname: Nom du contact
            company_name: Nom de l'entreprise
            email: Email
            linkedin_url: URL LinkedIn
            siren: Numéro SIREN
            getsales_uuid: UUID GetSales
            hubspot_contact_id: ID HubSpot
            include_low_confidence: Inclure les matches à faible confiance

        Returns:
            Liste de MatchResult triés par confiance décroissante
        """
        matches: List[MatchResult] = []
        seen_uuids: Set[str] = set()

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # 1. Matches EXACT par identifiants uniques
                exact_matches = self._find_exact_matches(
                    cursor, email, linkedin_url, siren, getsales_uuid, hubspot_contact_id
                )
                for contact, match_type in exact_matches:
                    if contact['uuid'] not in seen_uuids:
                        seen_uuids.add(contact['uuid'])
                        matches.append(MatchResult(
                            contact=contact,
                            match_type=match_type,
                            confidence=MatchConfidence.EXACT,
                            similarity_score=1.0,
                            matched_fields=[match_type]
                        ))

                # 2. Matches HIGH par (prénom + nom + entreprise)
                if firstname and lastname and company_name:
                    high_matches = self._find_fullname_company_matches(
                        cursor, firstname, lastname, company_name, seen_uuids
                    )
                    for result in high_matches:
                        if result.contact['uuid'] not in seen_uuids:
                            seen_uuids.add(result.contact['uuid'])
                            matches.append(result)

                # 3. Matches MEDIUM par (prénom + nom) seul
                if firstname and lastname:
                    medium_matches = self._find_fullname_matches(
                        cursor, firstname, lastname, seen_uuids
                    )
                    for result in medium_matches:
                        if result.contact['uuid'] not in seen_uuids:
                            seen_uuids.add(result.contact['uuid'])
                            matches.append(result)

                # 4. Matches MEDIUM par entreprise seule
                if company_name:
                    company_matches = self._find_company_matches(
                        cursor, company_name, seen_uuids, include_low_confidence
                    )
                    for result in company_matches:
                        if result.contact['uuid'] not in seen_uuids:
                            seen_uuids.add(result.contact['uuid'])
                            matches.append(result)

        except Exception as e:
            logger.error(f"Erreur lors de la recherche de doublons: {e}")

        # Trier par confiance (EXACT > HIGH > MEDIUM > LOW) puis par score
        confidence_order = {
            MatchConfidence.EXACT: 0,
            MatchConfidence.HIGH: 1,
            MatchConfidence.MEDIUM: 2,
            MatchConfidence.LOW: 3
        }
        matches.sort(key=lambda m: (confidence_order[m.confidence], -m.similarity_score))

        return matches

    def _find_exact_matches(
        self,
        cursor: sqlite3.Cursor,
        email: str = None,
        linkedin_url: str = None,
        siren: str = None,
        getsales_uuid: str = None,
        hubspot_contact_id: str = None
    ) -> List[tuple]:
        """Trouve les matches exacts par identifiants uniques."""
        results = []

        table = self._contacts_table

        # Par HubSpot ID
        if hubspot_contact_id:
            cursor.execute(
                f"SELECT * FROM {table} WHERE hubspot_contact_id = ? AND status = 'active'",
                (hubspot_contact_id,)
            )
            for row in cursor.fetchall():
                results.append((dict(row), 'hubspot_id'))

        # Par GetSales UUID
        if getsales_uuid:
            cursor.execute(
                f"SELECT * FROM {table} WHERE getsales_uuid = ? AND status = 'active'",
                (getsales_uuid,)
            )
            for row in cursor.fetchall():
                results.append((dict(row), 'getsales_uuid'))

        # Par LinkedIn URL
        if linkedin_url:
            normalized = self._normalize_linkedin_url(linkedin_url)
            cursor.execute(
                f"SELECT * FROM {table} WHERE linkedin_url = ? AND status = 'active'",
                (normalized,)
            )
            for row in cursor.fetchall():
                results.append((dict(row), 'linkedin'))

        # Par Email
        if email:
            email_lower = email.lower().strip()
            cursor.execute(
                f"SELECT * FROM {table} WHERE LOWER(email) = ? AND status = 'active'",
                (email_lower,)
            )
            for row in cursor.fetchall():
                results.append((dict(row), 'email'))

        # Par SIREN (ancien schéma seulement - dans nouveau schéma, SIREN est dans companies)
        if siren and not self._new_schema:
            cursor.execute(
                f"SELECT * FROM {table} WHERE siren = ? AND status = 'active'",
                (siren,)
            )
            for row in cursor.fetchall():
                results.append((dict(row), 'siren'))

        return results

    def _find_fullname_company_matches(
        self,
        cursor: sqlite3.Cursor,
        firstname: str,
        lastname: str,
        company_name: str,
        exclude_uuids: Set[str]
    ) -> List[MatchResult]:
        """Trouve les matches par prénom + nom + entreprise (exact et fuzzy)."""
        results = []
        table = self._contacts_table

        # Normaliser les inputs
        fn_norm = self._normalize_name(firstname)
        ln_norm = self._normalize_name(lastname)
        company_norm = self._normalize_company(company_name)

        # Chercher tous les contacts avec un nom similaire
        # Pour nouveau schéma, company_name peut être dans la table companies via JOIN
        if self._new_schema:
            cursor.execute(f"""
                SELECT c.*, comp.company_name, comp.siren, comp.website
                FROM {table} c
                LEFT JOIN companies comp ON c.company_id = comp.id
                WHERE c.status = 'active'
                AND (
                    (LOWER(c.firstname) = ? AND LOWER(c.lastname) = ? AND LOWER(comp.company_name) = ?)
                    OR (LOWER(c.firstname) = ? AND LOWER(c.lastname) = ?)
                    OR LOWER(comp.company_name) = ?
                )
                LIMIT 50
            """, (fn_norm, ln_norm, company_norm, fn_norm, ln_norm, company_norm))
        else:
            cursor.execute(f"""
                SELECT * FROM {table}
                WHERE status = 'active'
                AND (
                    (LOWER(firstname) = ? AND LOWER(lastname) = ? AND LOWER(company_name) = ?)
                    OR (LOWER(firstname) = ? AND LOWER(lastname) = ?)
                    OR LOWER(company_name) = ?
                )
                LIMIT 50
            """, (fn_norm, ln_norm, company_norm, fn_norm, ln_norm, company_norm))

        for row in cursor.fetchall():
            contact = dict(row)
            if contact['uuid'] in exclude_uuids:
                continue

            # Calculer le score de similarité
            db_fn = self._normalize_name(contact.get('firstname') or '')
            db_ln = self._normalize_name(contact.get('lastname') or '')
            db_company = self._normalize_company(contact.get('company_name') or '')

            # Score pour chaque composant
            fn_score = self._similarity(fn_norm, db_fn) if fn_norm and db_fn else 0
            ln_score = self._similarity(ln_norm, db_ln) if ln_norm and db_ln else 0
            company_score = self._similarity(company_norm, db_company) if company_norm and db_company else 0

            # Match prénom + nom + entreprise
            if fn_score > 0.8 and ln_score > 0.8 and company_score > 0.8:
                avg_score = (fn_score + ln_score + company_score) / 3
                confidence = MatchConfidence.HIGH if avg_score >= self.FUZZY_THRESHOLD_HIGH else MatchConfidence.MEDIUM

                results.append(MatchResult(
                    contact=contact,
                    match_type='fullname_company',
                    confidence=confidence,
                    similarity_score=avg_score,
                    matched_fields=['firstname', 'lastname', 'company_name']
                ))

        return results

    def _find_fullname_matches(
        self,
        cursor: sqlite3.Cursor,
        firstname: str,
        lastname: str,
        exclude_uuids: Set[str]
    ) -> List[MatchResult]:
        """Trouve les matches par prénom + nom seul."""
        results = []
        table = self._contacts_table

        fn_norm = self._normalize_name(firstname)
        ln_norm = self._normalize_name(lastname)

        cursor.execute(f"""
            SELECT * FROM {table}
            WHERE LOWER(firstname) = ? AND LOWER(lastname) = ?
            AND status = 'active'
            LIMIT 20
        """, (fn_norm, ln_norm))

        for row in cursor.fetchall():
            contact = dict(row)
            if contact['uuid'] in exclude_uuids:
                continue

            results.append(MatchResult(
                contact=contact,
                match_type='fullname',
                confidence=MatchConfidence.MEDIUM,
                similarity_score=1.0,
                matched_fields=['firstname', 'lastname']
            ))

        return results

    def _find_company_matches(
        self,
        cursor: sqlite3.Cursor,
        company_name: str,
        exclude_uuids: Set[str],
        include_low_confidence: bool
    ) -> List[MatchResult]:
        """Trouve les matches par entreprise (exact et fuzzy)."""
        results = []
        table = self._contacts_table
        company_norm = self._normalize_company(company_name)

        # Match exact sur entreprise
        if self._new_schema:
            cursor.execute(f"""
                SELECT c.*, comp.company_name, comp.siren, comp.website
                FROM {table} c
                LEFT JOIN companies comp ON c.company_id = comp.id
                WHERE LOWER(comp.company_name) = ?
                AND c.status = 'active'
                LIMIT 30
            """, (company_norm,))
        else:
            cursor.execute(f"""
                SELECT * FROM {table}
                WHERE LOWER(company_name) = ?
                AND status = 'active'
                LIMIT 30
            """, (company_norm,))

        for row in cursor.fetchall():
            contact = dict(row)
            if contact['uuid'] in exclude_uuids:
                continue

            results.append(MatchResult(
                contact=contact,
                match_type='company_exact',
                confidence=MatchConfidence.MEDIUM,
                similarity_score=1.0,
                matched_fields=['company_name']
            ))

        # Fuzzy match sur entreprise si demandé
        if include_low_confidence and len(results) < 10:
            if self._new_schema:
                cursor.execute(f"""
                    SELECT c.*, comp.company_name, comp.siren, comp.website
                    FROM {table} c
                    LEFT JOIN companies comp ON c.company_id = comp.id
                    WHERE comp.company_name IS NOT NULL
                    AND c.status = 'active'
                    LIMIT 500
                """)
            else:
                cursor.execute(f"""
                    SELECT * FROM {table}
                    WHERE company_name IS NOT NULL
                    AND status = 'active'
                    LIMIT 500
                """)

            for row in cursor.fetchall():
                contact = dict(row)
                if contact['uuid'] in exclude_uuids:
                    continue

                db_company = self._normalize_company(contact.get('company_name') or '')
                if not db_company:
                    continue

                score = self._similarity(company_norm, db_company)
                if score >= self.FUZZY_THRESHOLD_LOW and score < 1.0:
                    confidence = MatchConfidence.MEDIUM if score >= self.FUZZY_THRESHOLD_MEDIUM else MatchConfidence.LOW

                    results.append(MatchResult(
                        contact=contact,
                        match_type='company_fuzzy',
                        confidence=confidence,
                        similarity_score=score,
                        matched_fields=['company_name']
                    ))

        return results

    # =========================================================================
    # UTILITAIRES
    # =========================================================================

    def _normalize_name(self, name: str) -> str:
        """Normalise un nom (lowercase, trim, accents)."""
        if not name:
            return ''
        return name.lower().strip()

    def _normalize_company(self, company: str) -> str:
        """Normalise un nom d'entreprise."""
        if not company:
            return ''
        # Lowercase, trim, supprimer formes juridiques courantes
        normalized = company.lower().strip()
        # Supprimer suffixes courants
        for suffix in [' sas', ' sarl', ' sa', ' eurl', ' sasu', ' sci']:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)].strip()
        # Supprimer caractères spéciaux
        normalized = ''.join(c for c in normalized if c.isalnum() or c == ' ')
        # Supprimer espaces multiples
        normalized = ' '.join(normalized.split())
        return normalized

    def _normalize_linkedin_url(self, url: str) -> str:
        """Normalise une URL LinkedIn."""
        if not url:
            return url
        url = url.split('?')[0].rstrip('/')
        if url.startswith('http://'):
            url = url.replace('http://', 'https://')
        if not url.startswith('https://'):
            url = f"https://linkedin.com/in/{url}"
        return url

    def _similarity(self, s1: str, s2: str) -> float:
        """
        Calcule la similarité entre deux chaînes (Levenshtein normalisé).

        Returns:
            Score entre 0.0 et 1.0
        """
        if not s1 or not s2:
            return 0.0
        if s1 == s2:
            return 1.0

        # Levenshtein distance
        len1, len2 = len(s1), len(s2)
        if len1 < len2:
            s1, s2 = s2, s1
            len1, len2 = len2, len1

        # Optimisation: si différence de longueur trop grande, skip
        if len1 - len2 > max(len1, len2) * 0.3:
            return 0.0

        # Calcul distance de Levenshtein
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
    # RECHERCHE MANUELLE (pour l'UI)
    # =========================================================================

    def search_contacts(
        self,
        query: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Recherche manuelle de contacts pour l'UI.

        Args:
            query: Texte de recherche (nom, entreprise, email)
            limit: Nombre max de résultats

        Returns:
            Liste de contacts matchant la recherche
        """
        results = []
        query_norm = query.lower().strip()
        table = self._contacts_table

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                if self._new_schema:
                    cursor.execute(f"""
                        SELECT c.*, comp.company_name, comp.siren, comp.website
                        FROM {table} c
                        LEFT JOIN companies comp ON c.company_id = comp.id
                        WHERE c.status = 'active'
                        AND (
                            LOWER(c.firstname) LIKE ?
                            OR LOWER(c.lastname) LIKE ?
                            OR LOWER(comp.company_name) LIKE ?
                            OR LOWER(c.email) LIKE ?
                        )
                        ORDER BY comp.company_name, c.lastname
                        LIMIT ?
                    """, (f"%{query_norm}%", f"%{query_norm}%", f"%{query_norm}%", f"%{query_norm}%", limit))
                else:
                    cursor.execute(f"""
                        SELECT * FROM {table}
                        WHERE status = 'active'
                        AND (
                            LOWER(firstname) LIKE ?
                            OR LOWER(lastname) LIKE ?
                            OR LOWER(company_name) LIKE ?
                            OR LOWER(email) LIKE ?
                        )
                        ORDER BY company_name, lastname
                        LIMIT ?
                    """, (f"%{query_norm}%", f"%{query_norm}%", f"%{query_norm}%", f"%{query_norm}%", limit))

                for row in cursor.fetchall():
                    results.append(dict(row))

        except Exception as e:
            logger.error(f"Erreur recherche contacts: {e}")

        return results

    # =========================================================================
    # MÉTHODES ENTREPRISES (nouveau schéma uniquement)
    # =========================================================================

    def find_company_matches(
        self,
        company_name: str = None,
        siren: str = None,
        website: str = None,
        include_low_confidence: bool = True
    ) -> List[CompanyMatchResult]:
        """
        Trouve les entreprises correspondantes (nouveau schéma uniquement).

        Args:
            company_name: Nom de l'entreprise
            siren: Numéro SIREN
            website: Site web / domaine
            include_low_confidence: Inclure les matches fuzzy

        Returns:
            Liste de CompanyMatchResult triés par confiance décroissante
        """
        if not self._new_schema:
            logger.warning("find_company_matches() appelé sans nouveau schéma disponible")
            return []

        matches: List[CompanyMatchResult] = []
        seen_ids: Set[int] = set()

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # 1. Match exact par SIREN
                if siren:
                    cursor.execute("""
                        SELECT * FROM companies WHERE siren = ?
                    """, (siren,))
                    for row in cursor.fetchall():
                        company = dict(row)
                        if company['id'] not in seen_ids:
                            seen_ids.add(company['id'])
                            matches.append(CompanyMatchResult(
                                company=company,
                                match_type='siren',
                                confidence=MatchConfidence.EXACT,
                                similarity_score=1.0,
                                matched_fields=['siren']
                            ))

                # 2. Match par domaine/website
                if website:
                    domain = self._extract_domain(website)
                    if domain:
                        cursor.execute("""
                            SELECT * FROM companies WHERE website LIKE ?
                        """, (f"%{domain}%",))
                        for row in cursor.fetchall():
                            company = dict(row)
                            if company['id'] not in seen_ids:
                                seen_ids.add(company['id'])
                                matches.append(CompanyMatchResult(
                                    company=company,
                                    match_type='domain',
                                    confidence=MatchConfidence.HIGH,
                                    similarity_score=1.0,
                                    matched_fields=['website']
                                ))

                # 3. Match exact par nom
                if company_name:
                    company_norm = self._normalize_company(company_name)
                    cursor.execute("""
                        SELECT * FROM companies WHERE LOWER(company_name) = ?
                    """, (company_norm,))
                    for row in cursor.fetchall():
                        company = dict(row)
                        if company['id'] not in seen_ids:
                            seen_ids.add(company['id'])
                            matches.append(CompanyMatchResult(
                                company=company,
                                match_type='name_exact',
                                confidence=MatchConfidence.HIGH,
                                similarity_score=1.0,
                                matched_fields=['company_name']
                            ))

                # 4. Match fuzzy par nom
                if company_name and include_low_confidence and len(matches) < 10:
                    company_norm = self._normalize_company(company_name)
                    cursor.execute("""
                        SELECT * FROM companies WHERE company_name IS NOT NULL LIMIT 500
                    """)
                    for row in cursor.fetchall():
                        company = dict(row)
                        if company['id'] in seen_ids:
                            continue

                        db_name_norm = self._normalize_company(company.get('company_name') or '')
                        if not db_name_norm:
                            continue

                        score = self._similarity(company_norm, db_name_norm)
                        if score >= self.FUZZY_THRESHOLD_LOW and score < 1.0:
                            confidence = (
                                MatchConfidence.HIGH if score >= self.FUZZY_THRESHOLD_HIGH
                                else MatchConfidence.MEDIUM if score >= self.FUZZY_THRESHOLD_MEDIUM
                                else MatchConfidence.LOW
                            )
                            seen_ids.add(company['id'])
                            matches.append(CompanyMatchResult(
                                company=company,
                                match_type='name_fuzzy',
                                confidence=confidence,
                                similarity_score=score,
                                matched_fields=['company_name']
                            ))

        except Exception as e:
            logger.error(f"Erreur recherche entreprises: {e}")

        # Trier par confiance
        confidence_order = {
            MatchConfidence.EXACT: 0,
            MatchConfidence.HIGH: 1,
            MatchConfidence.MEDIUM: 2,
            MatchConfidence.LOW: 3
        }
        matches.sort(key=lambda m: (confidence_order[m.confidence], -m.similarity_score))

        return matches

    def _extract_domain(self, url: str) -> Optional[str]:
        """Extrait le domaine d'une URL."""
        if not url:
            return None

        url = url.lower().strip()
        # Supprimer le protocole
        for prefix in ['https://', 'http://', 'www.']:
            if url.startswith(prefix):
                url = url[len(prefix):]
        # Prendre le premier segment
        domain = url.split('/')[0]
        return domain if domain else None
