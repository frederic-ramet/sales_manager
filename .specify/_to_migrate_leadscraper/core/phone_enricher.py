"""
Enrichisseur de téléphones multi-sources.
Combine Google Maps, web scraping et validation.
"""
import logging
import re
from typing import Optional, Dict, Any, List
import httpx

from core.google_maps_client import GoogleMapsClient

logger = logging.getLogger(__name__)


class PhoneEnricher:
    """
    Enrichisseur de téléphones avec plusieurs sources.
    1. Google Maps Places API (prioritaire)
    2. WebSearch + extraction
    3. Validation et scoring de confiance
    """

    def __init__(self, google_maps_api_key: Optional[str] = None):
        """
        Initialise l'enrichisseur.

        Args:
            google_maps_api_key: Clé API Google Maps (optionnel)
        """
        self.google_maps_api_key = google_maps_api_key
        self.google_maps_enabled = bool(google_maps_api_key)

        if self.google_maps_enabled:
            self.google_maps = GoogleMapsClient(google_maps_api_key)
            logger.info("PhoneEnricher initialisé avec Google Maps")
        else:
            self.google_maps = None
            logger.warning("PhoneEnricher initialisé SANS Google Maps (clé manquante)")

    def enrich(
        self,
        company_name: str,
        siren: Optional[str] = None,
        address: Optional[str] = None,
        city: Optional[str] = None,
        website: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Enrichit le téléphone d'une entreprise (multi-sources).

        Args:
            company_name: Nom entreprise
            siren: SIREN (pour validation)
            address: Adresse
            city: Ville
            website: Site web (pour extraction)

        Returns:
            {
                'phone': str,
                'phone_international': str,
                'source': str,  # 'google_maps', 'website', 'web_search'
                'confidence': float,  # 0.0-1.0
                'verified': bool,
                'metadata': dict
            }
        """
        results = []

        # Source 1: Google Maps (prioritaire si disponible)
        if self.google_maps_enabled:
            gm_result = self._enrich_google_maps(company_name, address, city, siren)
            if gm_result:
                results.append(gm_result)

        # Source 2: Website (si fourni)
        if website:
            web_result = self._enrich_website(website, company_name)
            if web_result:
                results.append(web_result)

        # Source 3: Web Search (fallback)
        if not results:
            ws_result = self._enrich_web_search(company_name, city)
            if ws_result:
                results.append(ws_result)

        # Sélectionner le meilleur résultat (confiance max)
        if not results:
            logger.warning(f"Aucun téléphone trouvé pour: {company_name}")
            return None

        best_result = max(results, key=lambda r: r.get('confidence', 0))
        logger.info(
            f"Téléphone trouvé pour {company_name}: {best_result['phone']} "
            f"(source: {best_result['source']}, confiance: {best_result['confidence']:.2f})"
        )

        return best_result

    def _enrich_google_maps(
        self,
        company_name: str,
        address: Optional[str],
        city: Optional[str],
        siren: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Enrichissement via Google Maps."""
        try:
            if not self.google_maps:
                return None

            result = self.google_maps.get_phone(company_name, address, city, siren)
            if not result:
                return None

            return {
                'phone': result['phone'],
                'phone_international': result['phone_international'],
                'source': 'google_maps',
                'confidence': result['confidence'],
                'verified': result['confidence'] >= 0.8,
                'metadata': {
                    'website': result.get('website', ''),
                    'rating': result.get('rating', 0.0),
                    'reviews_count': result.get('reviews_count', 0),
                    'address': result.get('address', '')
                }
            }

        except Exception as e:
            logger.error(f"Erreur Google Maps pour {company_name}: {e}")
            return None

    def _enrich_website(
        self,
        website: str,
        company_name: str
    ) -> Optional[Dict[str, Any]]:
        """Extraction téléphone depuis site web."""
        try:
            # Normaliser URL
            if not website.startswith(('http://', 'https://')):
                website = f"https://{website}"

            # Fetch page
            response = httpx.get(website, timeout=10, follow_redirects=True)
            response.raise_for_status()
            html = response.text

            # Extraction téléphones (regex)
            phones = self._extract_phones_from_html(html)

            if not phones:
                logger.info(f"Aucun téléphone trouvé sur: {website}")
                return None

            # Prendre le premier téléphone français trouvé
            phone = phones[0]

            return {
                'phone': phone,
                'phone_international': phone,
                'source': 'website',
                'confidence': 0.7,  # Confiance moyenne (non vérifié par tiers)
                'verified': False,
                'metadata': {
                    'website': website,
                    'extraction_method': 'regex'
                }
            }

        except Exception as e:
            logger.error(f"Erreur extraction website {website}: {e}")
            return None

    def _enrich_web_search(
        self,
        company_name: str,
        city: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Recherche téléphone via recherche web.
        (Simplifié - pas d'accès à des APIs de recherche ici)
        """
        # Note: Nécessiterait une API de recherche (Google Search API, Bing, etc.)
        # Pour l'instant, retourne None (implémentation future)
        logger.info(f"WebSearch non implémenté pour: {company_name}")
        return None

    def _extract_phones_from_html(self, html: str) -> List[str]:
        """
        Extrait les numéros de téléphone français d'une page HTML.

        Returns:
            Liste de téléphones formatés
        """
        # Patterns téléphone français
        patterns = [
            r'(?:(?:\+|00)33|0)\s*[1-9](?:[\s.-]*\d{2}){4}',  # Format FR standard
            r'\b0[1-9][\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}\b',  # 01 23 45 67 89
            r'\+33\s*[1-9](?:[\s.-]*\d{2}){4}',  # +33 1 23 45 67 89
        ]

        phones = []
        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            phones.extend(matches)

        # Nettoyer et formater
        cleaned = []
        for phone in phones:
            # Supprimer espaces/tirets/points
            clean = re.sub(r'[\s.-]', '', phone)

            # Normaliser format
            if clean.startswith('0033'):
                clean = '+33' + clean[4:]
            elif clean.startswith('33') and not clean.startswith('+'):
                clean = '+33' + clean[2:]
            elif clean.startswith('0'):
                clean = '+33' + clean[1:]

            # Formater pour affichage
            if clean.startswith('+33') and len(clean) == 12:
                formatted = f"+33 {clean[3]} {clean[4:6]} {clean[6:8]} {clean[8:10]} {clean[10:12]}"
                cleaned.append(formatted)
            else:
                cleaned.append(clean)

        # Dédupliquer
        return list(set(cleaned))

    def enrich_batch(
        self,
        contacts: List[Dict[str, Any]],
        max_contacts: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Enrichit une liste de contacts.

        Args:
            contacts: Liste de contacts à enrichir
            max_contacts: Nombre max de contacts à traiter (pour tests)

        Returns:
            Liste de contacts enrichis
        """
        enriched = []
        processed = 0

        for contact in contacts:
            if max_contacts and processed >= max_contacts:
                logger.info(f"Limite de {max_contacts} contacts atteinte")
                break

            # Skip si téléphone déjà présent
            if contact.get('telephone'):
                enriched.append(contact)
                continue

            # Enrichir
            company_name = contact.get('denomination', '')
            if not company_name:
                enriched.append(contact)
                continue

            result = self.enrich(
                company_name=company_name,
                siren=contact.get('siren'),
                address=contact.get('adresse'),
                city=contact.get('ville'),
                website=contact.get('website')
            )

            if result:
                contact['telephone'] = result['phone']
                contact['telephone_international'] = result.get('phone_international', '')
                contact['telephone_source'] = result['source']
                contact['telephone_confidence'] = result['confidence']
                contact['telephone_verified'] = result['verified']
                logger.info(f"✅ Téléphone enrichi pour: {company_name}")
            else:
                logger.info(f"❌ Aucun téléphone trouvé pour: {company_name}")

            enriched.append(contact)
            processed += 1

        logger.info(f"Enrichissement terminé: {processed} contacts traités")
        return enriched

    def close(self):
        """Ferme les connexions."""
        if self.google_maps:
            self.google_maps.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
