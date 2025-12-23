"""
Data Cleaner - Normalisation et validation des données (Schema V2).

Pipeline: Import → Clean → Enrich → Sync

Usage:
    cleaner = DataCleaner(company_manager, contact_manager)

    # Normaliser toutes les données
    report = cleaner.normalize_all()

    # Valider les données
    validation = cleaner.validate_all()

    # Corriger les problèmes
    cleaner.fix_invalid_emails()
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class DataCleaner:
    """
    Nettoyeur de données - Schema V2.

    Fonctionnalités:
    - Normalisation (noms, téléphones, emails, URLs)
    - Validation (formats, cohérence)
    - Correction automatique
    """

    def __init__(self, company_manager=None, contact_manager=None):
        """
        Args:
            company_manager: Instance de CompanyManagerV2
            contact_manager: Instance de ContactManagerV2
        """
        self.company_manager = company_manager
        self.contact_manager = contact_manager

        # Patterns de validation
        self.email_pattern = re.compile(
            r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        )
        self.phone_pattern = re.compile(r'^\+?[0-9]{8,15}$')
        self.siren_pattern = re.compile(r'^[0-9]{9}$')
        self.siret_pattern = re.compile(r'^[0-9]{14}$')
        self.linkedin_pattern = re.compile(
            r'^(https?://)?(www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+/?$'
        )

        # Formes juridiques françaises
        self.legal_forms = [
            'SAS', 'SASU', 'SARL', 'EURL', 'SA', 'SCI', 'SNC',
            'EIRL', 'EI', 'SELAS', 'SELARL', 'GIE', 'SCOP', 'SCA'
        ]

    # =========================================================================
    # NORMALISATION
    # =========================================================================

    def normalize_all(self, progress_callback=None) -> Dict[str, Any]:
        """
        Normalise toutes les données.

        Returns:
            Rapport de normalisation
        """
        report = {
            'companies': {'processed': 0, 'normalized': 0, 'errors': []},
            'contacts': {'processed': 0, 'normalized': 0, 'errors': []},
            'started_at': datetime.now().isoformat()
        }

        # Normaliser les entreprises
        if self.company_manager:
            companies = self.company_manager.list_all(limit=10000)
            total = len(companies)

            for i, company in enumerate(companies):
                if progress_callback:
                    progress_callback(i + 1, total, 'companies')

                report['companies']['processed'] += 1
                try:
                    updates = self._normalize_company(company)
                    if updates:
                        self.company_manager.update(company['uuid'], updates)
                        report['companies']['normalized'] += 1
                except Exception as e:
                    report['companies']['errors'].append(
                        f"{company.get('name', 'Unknown')}: {str(e)}"
                    )

        # Normaliser les contacts
        if self.contact_manager:
            contacts = self.contact_manager.list_all(limit=10000)
            total = len(contacts)

            for i, contact in enumerate(contacts):
                if progress_callback:
                    progress_callback(i + 1, total, 'contacts')

                report['contacts']['processed'] += 1
                try:
                    updates = self._normalize_contact(contact)
                    if updates:
                        self.contact_manager.update(contact['uuid'], updates)
                        report['contacts']['normalized'] += 1
                except Exception as e:
                    name = f"{contact.get('firstname', '')} {contact.get('lastname', '')}".strip()
                    report['contacts']['errors'].append(f"{name}: {str(e)}")

        report['finished_at'] = datetime.now().isoformat()
        return report

    def _normalize_company(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """Normalise une entreprise."""
        updates = {}

        # Nom
        if company.get('name'):
            normalized_name = self.normalize_company_name(company['name'])
            if normalized_name != company['name']:
                updates['name'] = normalized_name

        # Domain
        if company.get('domain'):
            normalized_domain = self.normalize_domain(company['domain'])
            if normalized_domain != company['domain']:
                updates['domain'] = normalized_domain

        # SIREN
        if company.get('siren'):
            normalized_siren = self.normalize_siren(company['siren'])
            if normalized_siren != company['siren']:
                updates['siren'] = normalized_siren

        # Ville
        if company.get('hq_city'):
            normalized_city = self.normalize_city(company['hq_city'])
            if normalized_city != company['hq_city']:
                updates['hq_city'] = normalized_city

        # Pays
        if company.get('hq_country'):
            normalized_country = self.normalize_country(company['hq_country'])
            if normalized_country != company['hq_country']:
                updates['hq_country'] = normalized_country

        return updates

    def _normalize_contact(self, contact: Dict[str, Any]) -> Dict[str, Any]:
        """Normalise un contact."""
        updates = {}

        # Prénom/Nom
        if contact.get('firstname'):
            normalized = self.normalize_name(contact['firstname'])
            if normalized != contact['firstname']:
                updates['firstname'] = normalized

        if contact.get('lastname'):
            normalized = self.normalize_name(contact['lastname'])
            if normalized != contact['lastname']:
                updates['lastname'] = normalized

        # Email
        if contact.get('email'):
            normalized = self.normalize_email(contact['email'])
            if normalized != contact['email']:
                updates['email'] = normalized

        # Téléphone
        if contact.get('phone'):
            normalized = self.normalize_phone(contact['phone'])
            if normalized != contact['phone']:
                updates['phone'] = normalized

        if contact.get('mobile'):
            normalized = self.normalize_phone(contact['mobile'])
            if normalized != contact['mobile']:
                updates['mobile'] = normalized

        # LinkedIn
        if contact.get('linkedin_url'):
            normalized = self.normalize_linkedin_url(contact['linkedin_url'])
            if normalized != contact['linkedin_url']:
                updates['linkedin_url'] = normalized

        # Ville
        if contact.get('city'):
            normalized = self.normalize_city(contact['city'])
            if normalized != contact['city']:
                updates['city'] = normalized

        return updates

    # =========================================================================
    # FONCTIONS DE NORMALISATION
    # =========================================================================

    def normalize_company_name(self, name: str) -> str:
        """
        Normalise un nom d'entreprise.

        - Trim et capitalize
        - Retire les formes juridiques en double
        - Uniformise les formes juridiques
        """
        if not name:
            return ''

        name = name.strip()

        # Retirer formes juridiques en double ou mal placées
        for form in self.legal_forms:
            # Patterns: "SAS ACME SAS" -> "ACME SAS"
            pattern = rf'\b{form}\b\s+(.+)\s+\b{form}\b'
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                name = f"{match.group(1)} {form}"

        # Capitalize proprement (sauf acronymes)
        words = name.split()
        result = []
        for word in words:
            if word.upper() in self.legal_forms:
                result.append(word.upper())
            elif word.isupper() and len(word) <= 4:
                result.append(word)  # Garder les acronymes
            else:
                result.append(word.capitalize())

        return ' '.join(result)

    def normalize_domain(self, domain: str) -> str:
        """
        Normalise un domaine.

        - Lowercase
        - Retire http(s)://, www., trailing slash
        """
        if not domain:
            return ''

        domain = domain.lower().strip()

        for prefix in ['https://', 'http://']:
            if domain.startswith(prefix):
                domain = domain[len(prefix):]

        if domain.startswith('www.'):
            domain = domain[4:]

        domain = domain.rstrip('/')
        domain = domain.split('/')[0]  # Garder que le domaine

        return domain

    def normalize_siren(self, siren: str) -> str:
        """
        Normalise un SIREN.

        - Garde uniquement les chiffres
        - Valide longueur 9
        """
        if not siren:
            return ''

        digits = ''.join(c for c in str(siren) if c.isdigit())
        return digits[:9] if len(digits) >= 9 else digits

    def normalize_name(self, name: str) -> str:
        """
        Normalise un prénom/nom.

        - Trim
        - Capitalize proprement
        - Gère les noms composés
        """
        if not name:
            return ''

        name = name.strip()

        # Gérer les noms composés (Jean-Pierre, Van der Berg)
        parts = re.split(r'([-\s])', name)
        result = []
        for part in parts:
            if part in ['-', ' ']:
                result.append(part)
            elif part.lower() in ['de', 'du', 'des', 'le', 'la', 'les', 'van', 'von', 'der']:
                result.append(part.lower())
            else:
                result.append(part.capitalize())

        return ''.join(result)

    def normalize_email(self, email: str) -> str:
        """
        Normalise un email.

        - Lowercase
        - Trim
        """
        if not email:
            return ''
        return email.lower().strip()

    def normalize_phone(self, phone: str) -> str:
        """
        Normalise un numéro de téléphone.

        - Garde chiffres et +
        - Convertit +33 en 0
        - Format: 0612345678
        """
        if not phone:
            return ''

        # Garder que les chiffres
        digits = ''.join(c for c in str(phone) if c.isdigit())

        # Gestion +33 / 0033
        if digits.startswith('33') and len(digits) >= 11:
            digits = '0' + digits[2:]
        elif digits.startswith('0033') and len(digits) >= 13:
            digits = '0' + digits[4:]

        return digits

    def normalize_linkedin_url(self, url: str) -> str:
        """
        Normalise une URL LinkedIn.

        - Format: linkedin.com/in/username
        """
        if not url:
            return ''

        url = url.lower().strip()

        for prefix in ['https://', 'http://']:
            if url.startswith(prefix):
                url = url[len(prefix):]

        if url.startswith('www.'):
            url = url[4:]

        url = url.rstrip('/')

        return url

    def normalize_city(self, city: str) -> str:
        """
        Normalise une ville.

        - Capitalize
        - Gère les noms composés
        """
        if not city:
            return ''

        city = city.strip()

        # Capitalize chaque mot sauf prépositions
        parts = city.split()
        result = []
        for part in parts:
            if part.lower() in ['sur', 'sous', 'les', 'la', 'le', 'en', 'de', 'du']:
                result.append(part.lower())
            else:
                result.append(part.capitalize())

        return ' '.join(result)

    def normalize_country(self, country: str) -> str:
        """
        Normalise un pays.

        - Standardise les variantes
        """
        if not country:
            return ''

        country = country.strip()

        # Mapping des variantes
        mapping = {
            'fr': 'France',
            'france': 'France',
            'french': 'France',
            'us': 'United States',
            'usa': 'United States',
            'united states': 'United States',
            'uk': 'United Kingdom',
            'gb': 'United Kingdom',
            'great britain': 'United Kingdom',
            'de': 'Germany',
            'germany': 'Germany',
            'deutschland': 'Germany',
            'es': 'Spain',
            'spain': 'Spain',
            'it': 'Italy',
            'italy': 'Italy',
        }

        return mapping.get(country.lower(), country.capitalize())

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def validate_all(self) -> Dict[str, Any]:
        """
        Valide toutes les données.

        Returns:
            Rapport de validation avec problèmes détectés
        """
        report = {
            'companies': {
                'total': 0,
                'valid': 0,
                'issues': []
            },
            'contacts': {
                'total': 0,
                'valid': 0,
                'issues': []
            },
            'summary': {
                'invalid_emails': 0,
                'invalid_phones': 0,
                'invalid_sirens': 0,
                'invalid_linkedin': 0,
                'missing_required': 0
            }
        }

        # Valider les entreprises
        if self.company_manager:
            companies = self.company_manager.list_all(limit=10000)
            report['companies']['total'] = len(companies)

            for company in companies:
                issues = self._validate_company(company)
                if issues:
                    report['companies']['issues'].append({
                        'uuid': company['uuid'],
                        'name': company.get('name', 'Unknown'),
                        'issues': issues
                    })
                    for issue in issues:
                        if 'siren' in issue.lower():
                            report['summary']['invalid_sirens'] += 1
                else:
                    report['companies']['valid'] += 1

        # Valider les contacts
        if self.contact_manager:
            contacts = self.contact_manager.list_all(limit=10000)
            report['contacts']['total'] = len(contacts)

            for contact in contacts:
                issues = self._validate_contact(contact)
                if issues:
                    name = f"{contact.get('firstname', '')} {contact.get('lastname', '')}".strip()
                    report['contacts']['issues'].append({
                        'uuid': contact['uuid'],
                        'name': name or contact.get('email', 'Unknown'),
                        'issues': issues
                    })
                    for issue in issues:
                        if 'email' in issue.lower():
                            report['summary']['invalid_emails'] += 1
                        elif 'phone' in issue.lower() or 'téléphone' in issue.lower():
                            report['summary']['invalid_phones'] += 1
                        elif 'linkedin' in issue.lower():
                            report['summary']['invalid_linkedin'] += 1
                else:
                    report['contacts']['valid'] += 1

        return report

    def _validate_company(self, company: Dict[str, Any]) -> List[str]:
        """Valide une entreprise."""
        issues = []

        # Nom requis
        if not company.get('name'):
            issues.append("Nom manquant")

        # SIREN format
        if company.get('siren'):
            if not self.validate_siren(company['siren']):
                issues.append(f"SIREN invalide: {company['siren']}")

        # Domain format
        if company.get('domain'):
            if not self.validate_domain(company['domain']):
                issues.append(f"Domain invalide: {company['domain']}")

        return issues

    def _validate_contact(self, contact: Dict[str, Any]) -> List[str]:
        """Valide un contact."""
        issues = []

        # Au moins un identifiant
        has_identifier = any([
            contact.get('email'),
            contact.get('linkedin_url'),
            contact.get('phone')
        ])
        if not has_identifier:
            issues.append("Aucun identifiant (email, LinkedIn, téléphone)")

        # Email format
        if contact.get('email'):
            if not self.validate_email(contact['email']):
                issues.append(f"Email invalide: {contact['email']}")

        # Phone format
        if contact.get('phone'):
            if not self.validate_phone(contact['phone']):
                issues.append(f"Téléphone invalide: {contact['phone']}")

        if contact.get('mobile'):
            if not self.validate_phone(contact['mobile']):
                issues.append(f"Mobile invalide: {contact['mobile']}")

        # LinkedIn format
        if contact.get('linkedin_url'):
            if not self.validate_linkedin_url(contact['linkedin_url']):
                issues.append(f"LinkedIn invalide: {contact['linkedin_url']}")

        return issues

    # =========================================================================
    # FONCTIONS DE VALIDATION
    # =========================================================================

    def validate_email(self, email: str, check_mx: bool = False) -> bool:
        """
        Valide un email.

        Args:
            email: Adresse email à valider
            check_mx: Si True, vérifie aussi les records MX du domaine

        Returns:
            True si valide
        """
        if not email:
            return False

        email = email.lower().strip()

        # Validation format
        if not self.email_pattern.match(email):
            return False

        # Validation MX optionnelle
        if check_mx:
            domain = email.split('@')[1]
            if not self.check_mx_record(domain):
                return False

        return True

    def check_mx_record(self, domain: str) -> bool:
        """
        Vérifie les records MX d'un domaine.

        Args:
            domain: Domaine à vérifier

        Returns:
            True si le domaine a des records MX valides
        """
        try:
            import dns.resolver
            DNS_AVAILABLE = True
        except ImportError:
            DNS_AVAILABLE = False

        if not DNS_AVAILABLE:
            logger.debug("dnspython non installé, MX check ignoré")
            return True  # Skip si pas de dns module

        try:
            mx_records = dns.resolver.resolve(domain, 'MX')
            return len(mx_records) > 0
        except dns.resolver.NXDOMAIN:
            logger.debug(f"Domaine inexistant: {domain}")
            return False
        except dns.resolver.NoAnswer:
            logger.debug(f"Pas de MX record: {domain}")
            return False
        except dns.resolver.Timeout:
            logger.debug(f"Timeout MX check: {domain}")
            return True  # Timeout = on ne bloque pas
        except Exception as e:
            logger.debug(f"Erreur MX check {domain}: {e}")
            return True  # Erreur = on ne bloque pas

    def validate_emails_with_mx(
        self,
        limit: int = 100,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Valide les emails des contacts avec vérification MX.

        Args:
            limit: Nombre max de contacts à vérifier
            progress_callback: Callback(current, total)

        Returns:
            Rapport de validation
        """
        report = {
            'checked': 0,
            'valid': 0,
            'invalid': [],
            'domains_checked': {},
            'errors': []
        }

        if not self.contact_manager:
            report['errors'].append('ContactManager non initialisé')
            return report

        contacts = self.contact_manager.list_all(limit=limit)

        # Cache des domaines déjà vérifiés
        domain_cache = {}

        for i, contact in enumerate(contacts):
            if progress_callback:
                progress_callback(i + 1, len(contacts))

            email = contact.get('email')
            if not email:
                continue

            report['checked'] += 1

            # Valider format d'abord
            if not self.email_pattern.match(email.lower().strip()):
                report['invalid'].append({
                    'uuid': contact['uuid'],
                    'email': email,
                    'reason': 'format_invalid'
                })
                continue

            # Vérifier MX (avec cache)
            domain = email.split('@')[1].lower()

            if domain not in domain_cache:
                domain_cache[domain] = self.check_mx_record(domain)
                report['domains_checked'][domain] = domain_cache[domain]

            if not domain_cache[domain]:
                report['invalid'].append({
                    'uuid': contact['uuid'],
                    'email': email,
                    'reason': 'mx_invalid',
                    'domain': domain
                })
            else:
                report['valid'] += 1

        return report

    def validate_phone(self, phone: str) -> bool:
        """Valide un numéro de téléphone."""
        if not phone:
            return False
        digits = ''.join(c for c in str(phone) if c.isdigit())
        return 8 <= len(digits) <= 15

    def validate_siren(self, siren: str) -> bool:
        """
        Valide un SIREN (9 chiffres + clé Luhn).
        """
        if not siren:
            return False

        digits = ''.join(c for c in str(siren) if c.isdigit())
        if len(digits) != 9:
            return False

        # Vérification Luhn
        total = 0
        for i, digit in enumerate(digits):
            n = int(digit)
            if i % 2 == 1:  # Position paire (0-indexed impair)
                n *= 2
                if n > 9:
                    n -= 9
            total += n

        return total % 10 == 0

    def validate_siret(self, siret: str) -> bool:
        """Valide un SIRET (14 chiffres, commence par SIREN valide)."""
        if not siret:
            return False

        digits = ''.join(c for c in str(siret) if c.isdigit())
        if len(digits) != 14:
            return False

        # Les 9 premiers chiffres doivent être un SIREN valide
        return self.validate_siren(digits[:9])

    def validate_domain(self, domain: str) -> bool:
        """Valide un domaine."""
        if not domain:
            return False

        domain = domain.lower().strip()
        # Pattern basique pour domaine
        pattern = r'^[a-zA-Z0-9][a-zA-Z0-9-]*\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, domain))

    def validate_linkedin_url(self, url: str) -> bool:
        """Valide une URL LinkedIn."""
        if not url:
            return False

        url = url.lower().strip()
        # Accepter avec ou sans protocole
        return 'linkedin.com/in/' in url

    # =========================================================================
    # CORRECTIONS
    # =========================================================================

    def fix_invalid_emails(self, delete: bool = False) -> Dict[str, Any]:
        """
        Corrige ou supprime les emails invalides.

        Args:
            delete: Si True, supprime le champ. Sinon, tente de corriger.

        Returns:
            Rapport
        """
        report = {'fixed': 0, 'deleted': 0, 'errors': []}

        if not self.contact_manager:
            return report

        contacts = self.contact_manager.list_all(limit=10000)

        for contact in contacts:
            email = contact.get('email')
            if email and not self.validate_email(email):
                try:
                    if delete:
                        self.contact_manager.update(contact['uuid'], {'email': None})
                        report['deleted'] += 1
                    else:
                        # Tenter de corriger
                        fixed = self._try_fix_email(email)
                        if fixed and self.validate_email(fixed):
                            self.contact_manager.update(contact['uuid'], {'email': fixed})
                            report['fixed'] += 1
                        elif delete:
                            self.contact_manager.update(contact['uuid'], {'email': None})
                            report['deleted'] += 1
                except Exception as e:
                    report['errors'].append(f"{contact['uuid']}: {str(e)}")

        return report

    def _try_fix_email(self, email: str) -> Optional[str]:
        """Tente de corriger un email."""
        if not email:
            return None

        email = email.lower().strip()

        # Retirer espaces
        email = email.replace(' ', '')

        # Corriger erreurs courantes
        corrections = {
            ',com': '.com',
            '.con': '.com',
            '@gmail,com': '@gmail.com',
            'gmial.com': 'gmail.com',
            'gmai.com': 'gmail.com',
            'hotmai.com': 'hotmail.com',
            'yahooo.com': 'yahoo.com',
        }

        for wrong, correct in corrections.items():
            email = email.replace(wrong, correct)

        return email if self.validate_email(email) else None

    def fix_invalid_phones(self) -> Dict[str, Any]:
        """
        Normalise tous les téléphones invalides.

        Returns:
            Rapport
        """
        report = {'fixed': 0, 'errors': []}

        if not self.contact_manager:
            return report

        contacts = self.contact_manager.list_all(limit=10000)

        for contact in contacts:
            updates = {}

            for field in ['phone', 'mobile']:
                phone = contact.get(field)
                if phone:
                    normalized = self.normalize_phone(phone)
                    if normalized != phone and self.validate_phone(normalized):
                        updates[field] = normalized

            if updates:
                try:
                    self.contact_manager.update(contact['uuid'], updates)
                    report['fixed'] += 1
                except Exception as e:
                    report['errors'].append(f"{contact['uuid']}: {str(e)}")

        return report

    def fix_invalid_sirens(self) -> Dict[str, Any]:
        """
        Normalise ou supprime les SIREN invalides.

        Returns:
            Rapport
        """
        report = {'fixed': 0, 'cleared': 0, 'errors': []}

        if not self.company_manager:
            return report

        companies = self.company_manager.list_all(limit=10000)

        for company in companies:
            siren = company.get('siren')
            if siren:
                normalized = self.normalize_siren(siren)
                if self.validate_siren(normalized):
                    if normalized != siren:
                        try:
                            self.company_manager.update(company['uuid'], {'siren': normalized})
                            report['fixed'] += 1
                        except Exception as e:
                            report['errors'].append(f"{company['uuid']}: {str(e)}")
                else:
                    # SIREN invalide, le supprimer
                    try:
                        self.company_manager.update(company['uuid'], {'siren': None})
                        report['cleared'] += 1
                    except Exception as e:
                        report['errors'].append(f"{company['uuid']}: {str(e)}")

        return report

    # =========================================================================
    # STATS
    # =========================================================================

    def get_data_quality_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques de qualité des données.
        """
        stats = {
            'companies': {
                'total': 0,
                'with_siren': 0,
                'with_domain': 0,
                'with_address': 0,
                'valid_siren_rate': 0
            },
            'contacts': {
                'total': 0,
                'with_email': 0,
                'with_phone': 0,
                'with_linkedin': 0,
                'valid_email_rate': 0
            }
        }

        if self.company_manager:
            companies = self.company_manager.list_all(limit=10000)
            stats['companies']['total'] = len(companies)

            valid_sirens = 0
            for c in companies:
                if c.get('siren'):
                    stats['companies']['with_siren'] += 1
                    if self.validate_siren(c['siren']):
                        valid_sirens += 1
                if c.get('domain'):
                    stats['companies']['with_domain'] += 1
                if c.get('hq_address') or c.get('hq_city'):
                    stats['companies']['with_address'] += 1

            if stats['companies']['with_siren'] > 0:
                stats['companies']['valid_siren_rate'] = round(
                    valid_sirens / stats['companies']['with_siren'] * 100, 1
                )

        if self.contact_manager:
            contacts = self.contact_manager.list_all(limit=10000)
            stats['contacts']['total'] = len(contacts)

            valid_emails = 0
            for c in contacts:
                if c.get('email'):
                    stats['contacts']['with_email'] += 1
                    if self.validate_email(c['email']):
                        valid_emails += 1
                if c.get('phone') or c.get('mobile'):
                    stats['contacts']['with_phone'] += 1
                if c.get('linkedin_url'):
                    stats['contacts']['with_linkedin'] += 1

            if stats['contacts']['with_email'] > 0:
                stats['contacts']['valid_email_rate'] = round(
                    valid_emails / stats['contacts']['with_email'] * 100, 1
                )

        return stats
