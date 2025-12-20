"""
Client pour Google Maps Places API.
Permet de rechercher des téléphones d'entreprises via Google Maps.
"""
import logging
import time
from typing import Optional, Dict, Any, List
import httpx

from config import REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


class GoogleMapsClient:
    """
    Client pour interagir avec Google Maps Places API.
    Recherche de téléphones et informations d'entreprises.
    """

    def __init__(self, api_key: str):
        """
        Initialise le client Google Maps.

        Args:
            api_key: Clé API Google Maps
        """
        self.api_key = api_key
        self.base_url = "https://maps.googleapis.com/maps/api"
        self.client = httpx.Client(
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent": "LeadGenSIRENE/1.0 (Python/httpx)",
                "Accept": "application/json"
            }
        )
        self.rate_limit_delay = 0.1  # 100ms entre requêtes (respecte quota gratuit)

    def find_place(
        self,
        company_name: str,
        address: Optional[str] = None,
        city: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Recherche une entreprise sur Google Maps.

        Args:
            company_name: Nom de l'entreprise
            address: Adresse (optionnel, améliore précision)
            city: Ville (optionnel, améliore précision)

        Returns:
            Dict avec place_id si trouvé, None sinon
        """
        try:
            # Construire la query
            query_parts = [company_name]
            if address:
                query_parts.append(address)
            if city:
                query_parts.append(city)

            query = ", ".join(query_parts)

            # Find Place API
            url = f"{self.base_url}/place/findplacefromtext/json"
            params = {
                "input": query,
                "inputtype": "textquery",
                "fields": "place_id,name,formatted_address",
                "key": self.api_key
            }

            time.sleep(self.rate_limit_delay)
            response = self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "OK" and data.get("candidates"):
                candidate = data["candidates"][0]
                logger.info(f"Place trouvée: {candidate.get('name')}")
                return candidate
            else:
                logger.warning(f"Aucun résultat pour: {query}")
                return None

        except httpx.HTTPStatusError as e:
            logger.error(f"Erreur HTTP Google Maps: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Erreur find_place: {e}")
            return None

    def get_place_details(
        self,
        place_id: str,
        fields: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Récupère les détails complets d'un lieu.

        Args:
            place_id: ID du lieu Google Maps
            fields: Liste des champs à récupérer (défaut: phone, website, address)

        Returns:
            Dict avec les détails du lieu
        """
        try:
            if fields is None:
                fields = [
                    "name",
                    "formatted_phone_number",
                    "international_phone_number",
                    "formatted_address",
                    "website",
                    "rating",
                    "user_ratings_total"
                ]

            url = f"{self.base_url}/place/details/json"
            params = {
                "place_id": place_id,
                "fields": ",".join(fields),
                "key": self.api_key
            }

            time.sleep(self.rate_limit_delay)
            response = self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "OK":
                result = data.get("result", {})
                logger.info(f"Détails récupérés pour: {result.get('name')}")
                return result
            else:
                logger.warning(f"Détails non trouvés pour place_id: {place_id}")
                return None

        except httpx.HTTPStatusError as e:
            logger.error(f"Erreur HTTP Google Maps: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Erreur get_place_details: {e}")
            return None

    def get_phone(
        self,
        company_name: str,
        address: Optional[str] = None,
        city: Optional[str] = None,
        siren: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Recherche le téléphone d'une entreprise (méthode tout-en-un).

        Args:
            company_name: Nom de l'entreprise
            address: Adresse
            city: Ville
            siren: SIREN (pour validation)

        Returns:
            {
                'phone': str,  # Numéro formaté FR
                'phone_international': str,  # Format international
                'website': str,
                'address': str,
                'rating': float,
                'reviews_count': int,
                'confidence': float  # 0.0-1.0
            }
        """
        try:
            # 1. Trouver le lieu
            place = self.find_place(company_name, address, city)
            if not place:
                return None

            place_id = place.get("place_id")
            if not place_id:
                return None

            # 2. Récupérer les détails
            details = self.get_place_details(place_id)
            if not details:
                return None

            # 3. Extraire le téléphone
            phone = details.get("formatted_phone_number")
            phone_intl = details.get("international_phone_number")

            if not phone and not phone_intl:
                logger.warning(f"Aucun téléphone pour: {company_name}")
                return None

            # 4. Calculer confiance (0.0-1.0)
            confidence = 0.6  # Base
            if details.get("rating"):
                confidence += 0.2  # +0.2 si avis
            if details.get("user_ratings_total", 0) > 10:
                confidence += 0.1  # +0.1 si >10 avis
            if details.get("website"):
                confidence += 0.1  # +0.1 si site web

            confidence = min(confidence, 1.0)

            result = {
                'phone': phone or phone_intl,
                'phone_international': phone_intl or phone,
                'website': details.get("website", ""),
                'address': details.get("formatted_address", ""),
                'rating': details.get("rating", 0.0),
                'reviews_count': details.get("user_ratings_total", 0),
                'confidence': confidence,
                'source': 'google_maps'
            }

            logger.info(f"Téléphone trouvé pour {company_name}: {phone} (confiance: {confidence:.2f})")
            return result

        except Exception as e:
            logger.error(f"Erreur get_phone pour {company_name}: {e}")
            return None

    def search_text(
        self,
        query: str,
        location: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Recherche textuelle sur Google Maps.

        Args:
            query: Texte de recherche
            location: Localisation (ex: "Paris, France")

        Returns:
            Liste de résultats
        """
        try:
            url = f"{self.base_url}/place/textsearch/json"
            params = {
                "query": query,
                "key": self.api_key
            }

            if location:
                params["query"] = f"{query} {location}"

            time.sleep(self.rate_limit_delay)
            response = self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "OK":
                results = data.get("results", [])
                logger.info(f"{len(results)} résultats pour: {query}")
                return results
            else:
                logger.warning(f"Aucun résultat pour: {query}")
                return []

        except Exception as e:
            logger.error(f"Erreur search_text: {e}")
            return []

    def close(self) -> None:
        """Ferme le client HTTP."""
        self.client.close()

    def __enter__(self):
        """Support du context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ferme le client à la sortie."""
        self.close()


# Fonction helper pour vérification rapide
def quick_phone_lookup(
    company_name: str,
    api_key: str,
    city: Optional[str] = None
) -> Optional[str]:
    """
    Recherche rapide de téléphone (fonction helper).

    Args:
        company_name: Nom entreprise
        api_key: Clé Google Maps
        city: Ville

    Returns:
        Téléphone ou None
    """
    try:
        with GoogleMapsClient(api_key) as client:
            result = client.get_phone(company_name, city=city)
            return result.get("phone") if result else None
    except:
        return None
