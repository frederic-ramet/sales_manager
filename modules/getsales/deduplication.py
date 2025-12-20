"""
Service de détection et gestion des doublons GetSales ↔ HubSpot.
"""
import logging
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DuplicateMatch:
    """Résultat d'un match de doublon."""
    hubspot_contact_id: str
    confidence: str  # 'high', 'medium', 'low'
    match_type: str  # 'linkedin_url', 'email'
    contact_data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour stockage JSON."""
        return {
            'hubspot_contact_id': self.hubspot_contact_id,
            'confidence': self.confidence,
            'match_type': self.match_type,
            'contact_data': self.contact_data
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DuplicateMatch':
        """Crée depuis un dictionnaire."""
        return cls(
            hubspot_contact_id=data['hubspot_contact_id'],
            confidence=data['confidence'],
            match_type=data['match_type'],
            contact_data=data['contact_data']
        )


class DeduplicationService:
    """
    Service de détection des doublons entre GetSales et HubSpot.

    Stratégie de matching:
    1. LinkedIn URL (prioritaire, confiance HIGH)
    2. Email (confiance HIGH)

    Usage:
        from modules.lead_scraper import HubSpotClient

        hubspot = HubSpotClient()
        dedup = DeduplicationService(hubspot)

        matches = dedup.find_duplicates(getsales_lead)
    """

    # Patterns pour normalisation LinkedIn
    LINKEDIN_PATTERNS = [
        r'linkedin\.com/in/([^/?]+)',
        r'linkedin\.com/sales/lead/([^/?]+)',
        r'linkedin\.com/sales/people/([^/?]+)',
    ]

    def __init__(self, hubspot_client):
        """
        Initialise le service.

        Args:
            hubspot_client: Instance de HubSpotClient
        """
        self.hubspot = hubspot_client
        self._hubspot_cache = {}  # Cache des contacts HubSpot

    def find_duplicates(self, getsales_lead: Dict[str, Any]) -> List[DuplicateMatch]:
        """
        Recherche les doublons potentiels dans HubSpot.

        Args:
            getsales_lead: Lead depuis GetSales avec champs:
                - linkedin: ID ou URL LinkedIn
                - email: Email
                - first_name, last_name, company_name

        Returns:
            Liste des DuplicateMatch trouvés (peut être vide)
        """
        matches = []

        # 1. Chercher par LinkedIn URL
        linkedin_url = self._format_linkedin_url(getsales_lead.get('linkedin'))
        if linkedin_url:
            linkedin_match = self._search_by_linkedin(linkedin_url)
            if linkedin_match:
                matches.append(DuplicateMatch(
                    hubspot_contact_id=linkedin_match['id'],
                    confidence='high',
                    match_type='linkedin_url',
                    contact_data=linkedin_match
                ))
                logger.info(f"Match LinkedIn trouvé: {linkedin_match.get('id')}")

        # 2. Chercher par email (si pas de match LinkedIn)
        if not matches:
            email = getsales_lead.get('email')
            if email and self._is_valid_email(email):
                email_match = self._search_by_email(email)
                if email_match:
                    matches.append(DuplicateMatch(
                        hubspot_contact_id=email_match['id'],
                        confidence='high',
                        match_type='email',
                        contact_data=email_match
                    ))
                    logger.info(f"Match email trouvé: {email_match.get('id')}")

        return matches

    def _format_linkedin_url(self, linkedin_id: Optional[str]) -> Optional[str]:
        """
        Formate l'ID LinkedIn en URL complète normalisée.

        Args:
            linkedin_id: ID ou URL LinkedIn (divers formats)

        Returns:
            URL normalisée ou None
        """
        if not linkedin_id:
            return None

        linkedin_id = str(linkedin_id).strip()

        # Si c'est déjà une URL complète, extraire l'ID
        if 'linkedin.com' in linkedin_id:
            for pattern in self.LINKEDIN_PATTERNS:
                match = re.search(pattern, linkedin_id)
                if match:
                    linkedin_id = match.group(1)
                    break

        # Nettoyer l'ID
        linkedin_id = linkedin_id.strip('/')

        if not linkedin_id:
            return None

        return f"https://www.linkedin.com/in/{linkedin_id}"

    def _is_valid_email(self, email: str) -> bool:
        """Vérifie si l'email est valide."""
        if not email:
            return False
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def _search_by_linkedin(self, linkedin_url: str) -> Optional[Dict[str, Any]]:
        """
        Recherche un contact HubSpot par LinkedIn URL.

        Args:
            linkedin_url: URL LinkedIn normalisée

        Returns:
            Contact HubSpot ou None
        """
        try:
            # Utiliser la recherche HubSpot par propriété
            # Note: nécessite que linkedin_url soit une propriété dans HubSpot
            mirror = self.hubspot.get_mirror()
            contacts = mirror.get('contacts', [])

            for contact in contacts:
                contact_linkedin = contact.get('linkedin_url', '')
                if contact_linkedin:
                    # Normaliser les deux URLs pour comparaison
                    normalized_contact = self._normalize_linkedin_for_compare(contact_linkedin)
                    normalized_search = self._normalize_linkedin_for_compare(linkedin_url)

                    if normalized_contact and normalized_search:
                        if normalized_contact == normalized_search:
                            return {
                                'id': contact.get('hubspot_id'),
                                'firstname': contact.get('dirigeant', '').split()[0] if contact.get('dirigeant') else '',
                                'lastname': contact.get('dirigeant', '').split()[-1] if contact.get('dirigeant') else '',
                                'email': contact.get('email'),
                                'company': contact.get('denomination'),
                                'jobtitle': contact.get('fonction'),
                                'linkedin_url': contact_linkedin
                            }

            return None

        except Exception as e:
            logger.error(f"Erreur recherche LinkedIn: {e}")
            return None

    def _search_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Recherche un contact HubSpot par email.

        Args:
            email: Adresse email

        Returns:
            Contact HubSpot ou None
        """
        try:
            mirror = self.hubspot.get_mirror()
            contacts = mirror.get('contacts', [])

            email_lower = email.lower().strip()

            for contact in contacts:
                contact_email = contact.get('email', '').lower().strip()
                if contact_email and contact_email == email_lower:
                    return {
                        'id': contact.get('hubspot_id'),
                        'firstname': contact.get('dirigeant', '').split()[0] if contact.get('dirigeant') else '',
                        'lastname': contact.get('dirigeant', '').split()[-1] if contact.get('dirigeant') else '',
                        'email': contact.get('email'),
                        'company': contact.get('denomination'),
                        'jobtitle': contact.get('fonction'),
                        'linkedin_url': contact.get('linkedin_url', '')
                    }

            return None

        except Exception as e:
            logger.error(f"Erreur recherche email: {e}")
            return None

    def _normalize_linkedin_for_compare(self, url: str) -> Optional[str]:
        """Normalise une URL LinkedIn pour comparaison."""
        if not url:
            return None

        url = url.lower().strip()

        for pattern in self.LINKEDIN_PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1).strip('/')

        # Si c'est juste un ID
        if '/' not in url and 'linkedin' not in url:
            return url.strip('/')

        return None

    def suggest_merge_strategy(
        self,
        getsales_lead: Dict[str, Any],
        hubspot_contact: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Suggère une stratégie de merge pour le formulaire.

        Logique: prendre GetSales si non vide, sinon HubSpot.

        Args:
            getsales_lead: Lead GetSales
            hubspot_contact: Contact HubSpot existant

        Returns:
            Dict avec suggestion par champ:
            {'firstname': 'getsales', 'email': 'hubspot', ...}
        """
        strategy = {}

        fields_mapping = {
            'first_name': 'firstname',
            'last_name': 'lastname',
            'email': 'email',
            'company_name': 'company',
            'position': 'jobtitle'
        }

        for gs_field, hs_field in fields_mapping.items():
            gs_value = str(getsales_lead.get(gs_field, '')).strip()
            hs_value = str(hubspot_contact.get(hs_field, '')).strip()

            # Logique: prendre GetSales si non vide, sinon HubSpot
            if gs_value:
                strategy[hs_field] = 'getsales'
            elif hs_value:
                strategy[hs_field] = 'hubspot'
            else:
                strategy[hs_field] = 'getsales'  # par défaut

        return strategy

    def get_duplicate_status(self, matches: List[DuplicateMatch]) -> str:
        """
        Détermine le statut de duplication.

        Args:
            matches: Liste des matches trouvés

        Returns:
            'none', 'potential' ou 'confirmed'
        """
        if not matches:
            return 'none'

        # Si au moins un match high confidence
        for match in matches:
            if match.confidence == 'high':
                return 'confirmed'

        return 'potential'
