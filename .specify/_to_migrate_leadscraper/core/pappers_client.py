"""
Client pour l'API Pappers.
Enrichit les données entreprises avec dirigeants, contacts, finances.
"""
import logging
from typing import Dict, Optional, Any

import httpx

from config import PAPPERS_BASE_URL, PAPPERS_API_KEY, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


class PappersClient:
    """
    Client pour interagir avec l'API Pappers.
    Permet d'enrichir les données entreprises.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialise le client Pappers.

        Args:
            api_key: Clé API Pappers (utilise config.PAPPERS_API_KEY si None)
        """
        self.api_key = api_key or PAPPERS_API_KEY
        if not self.api_key:
            raise ValueError(
                "PAPPERS_API_KEY non définie. "
                "Ajoutez-la dans .env ou passez-la au constructeur."
            )

        self.base_url = PAPPERS_BASE_URL
        self.client = httpx.Client(timeout=REQUEST_TIMEOUT)
        self.request_count = 0

    def get_company(self, siren: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les informations complètes d'une entreprise via son SIREN.

        Args:
            siren: Numéro SIREN (9 chiffres)

        Returns:
            Dict avec les données de l'entreprise ou None si erreur
        """
        if not siren or len(siren) != 9:
            logger.warning(f"SIREN invalide: {siren}")
            return None

        url = f"{self.base_url}/entreprise"
        params = {
            "siren": siren,
            "api_token": self.api_key
        }

        try:
            response = self.client.get(url, params=params)
            self.request_count += 1

            if response.status_code == 404:
                logger.debug(f"Entreprise non trouvée sur Pappers: {siren}")
                return None

            if response.status_code == 429:
                logger.error("Quota API Pappers dépassé.")
                return None

            response.raise_for_status()
            data = response.json()

            logger.debug(f"Données Pappers récupérées pour {siren}")
            return data

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Erreur HTTP {e.response.status_code} pour {siren}: "
                f"{e.response.text}"
            )
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la requête Pappers pour {siren}: {e}")
            return None

    def extract_contact_info(self, data: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """
        Extrait les informations de contact depuis les données Pappers.

        Args:
            data: Données brutes de l'API Pappers

        Returns:
            Dict avec dirigeant_nom, dirigeant_prenom, dirigeant_fonction,
            email, telephone, site_web, chiffre_affaires
        """
        contact_info = {
            "dirigeant_nom": None,
            "dirigeant_prenom": None,
            "dirigeant_fonction": None,
            "email": None,
            "telephone": None,
            "site_web": None,
            "chiffre_affaires": None
        }

        if not data:
            return contact_info

        try:
            # Extraction du dirigeant principal
            representants = data.get("representants", [])
            if representants:
                dirigeant = representants[0]  # Premier représentant

                # Nom et prénom
                if dirigeant.get("personne_morale") is False:
                    contact_info["dirigeant_nom"] = dirigeant.get("nom", "")
                    contact_info["dirigeant_prenom"] = dirigeant.get("prenom", "")
                else:
                    # Si c'est une personne morale
                    contact_info["dirigeant_nom"] = dirigeant.get(
                        "denomination",
                        dirigeant.get("nom", "")
                    )

                # Fonction
                contact_info["dirigeant_fonction"] = dirigeant.get("qualite", "")

            # Email
            email = data.get("email")
            if email:
                contact_info["email"] = email

            # Téléphone
            telephone = data.get("telephone")
            if telephone:
                contact_info["telephone"] = telephone

            # Site web
            site_web = data.get("site_internet")
            if site_web:
                contact_info["site_web"] = site_web

            # Chiffre d'affaires (dernier connu)
            finances = data.get("finances", [])
            if finances:
                # Trier par année décroissante
                finances_sorted = sorted(
                    finances,
                    key=lambda x: x.get("annee", 0),
                    reverse=True
                )
                if finances_sorted:
                    ca = finances_sorted[0].get("chiffre_affaires")
                    if ca:
                        contact_info["chiffre_affaires"] = str(ca)

        except Exception as e:
            logger.warning(f"Erreur lors de l'extraction des contacts: {e}")

        return contact_info

    def enrich_company(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrichit une entreprise avec les données Pappers.

        Args:
            company: Dict avec au minimum 'siren'

        Returns:
            Dict entreprise enrichie (merge des données SIRENE + Pappers)
        """
        siren = company.get("siren")
        if not siren:
            logger.warning("Entreprise sans SIREN, impossible d'enrichir.")
            return company

        # Récupération des données Pappers
        pappers_data = self.get_company(siren)
        if not pappers_data:
            logger.debug(f"Pas de données Pappers pour {siren}")
            return company

        # Extraction des contacts
        contact_info = self.extract_contact_info(pappers_data)

        # Merge avec les données existantes
        enriched = {**company, **contact_info}

        return enriched

    def get_request_count(self) -> int:
        """
        Retourne le nombre de requêtes effectuées depuis l'instanciation.

        Returns:
            Nombre de requêtes
        """
        return self.request_count

    def close(self) -> None:
        """Ferme le client HTTP."""
        self.client.close()

    def __enter__(self):
        """Support du context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ferme le client à la sortie du context manager."""
        self.close()
