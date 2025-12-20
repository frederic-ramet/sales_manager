"""
Client pour l'API SIRENE (recherche-entreprises.api.gouv.fr).
Permet de rechercher des entreprises avec filtres avancés.
"""
import logging
import time
from typing import List, Dict, Optional, Any
from datetime import datetime

import httpx

from config import (
    SIRENE_BASE_URL,
    SIRENE_RATE_LIMIT,
    MAX_RESULTS,
    DEFAULT_PER_PAGE,
    MAX_PER_PAGE,
    REQUEST_TIMEOUT
)

logger = logging.getLogger(__name__)


class SireneClient:
    """
    Client pour interagir avec l'API SIRENE.
    Gère le rate limiting et la pagination automatiquement.
    """

    def __init__(self):
        """Initialise le client SIRENE."""
        self.base_url = SIRENE_BASE_URL
        self.rate_limit = SIRENE_RATE_LIMIT  # Requêtes par minute
        self.request_times: List[float] = []
        self.client = httpx.Client(
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent": "LeadGenSIRENE/1.0 (Python/httpx)",
                "Accept": "application/json"
            }
        )

    def _handle_rate_limit(self) -> None:
        """
        Gère le rate limiting de l'API SIRENE (400 req/min).
        Ajoute un sleep si nécessaire pour respecter la limite.
        """
        now = time.time()
        # Nettoyer les requêtes de plus d'une minute
        self.request_times = [t for t in self.request_times if now - t < 60]

        if len(self.request_times) >= self.rate_limit:
            # Attendre jusqu'à ce que la plus ancienne requête ait plus d'une minute
            sleep_time = 60 - (now - self.request_times[0]) + 0.1
            if sleep_time > 0:
                logger.info(f"Rate limit atteint. Attente de {sleep_time:.1f}s...")
                time.sleep(sleep_time)
                # Nettoyer après le sleep
                now = time.time()
                self.request_times = [t for t in self.request_times if now - t < 60]

        self.request_times.append(now)

    def search(
        self,
        codes_ape: Optional[List[str]] = None,
        departements: Optional[List[str]] = None,
        effectif_min: Optional[int] = None,
        effectif_max: Optional[int] = None,
        date_creation_min: Optional[str] = None,
        forme_juridique: Optional[List[str]] = None,
        page: int = 1,
        per_page: int = DEFAULT_PER_PAGE
    ) -> Dict[str, Any]:
        """
        Recherche des entreprises avec filtres.

        Args:
            codes_ape: Liste de codes APE (ex: ["6201Z", "6202A"])
            departements: Liste de codes département (ex: ["75", "92"])
            effectif_min: Effectif minimum
            effectif_max: Effectif maximum
            date_creation_min: Date de création minimale (format YYYY-MM-DD)
            forme_juridique: Liste de formes juridiques
            page: Numéro de page (commence à 1)
            per_page: Nombre de résultats par page (max 25)

        Returns:
            Dict avec 'results' (liste d'entreprises) et 'total_results' (nombre total)
        """
        self._handle_rate_limit()

        # Construction des paramètres
        params: Dict[str, Any] = {
            "page": page,
            "per_page": min(per_page, MAX_PER_PAGE)
        }

        # Filtres
        if codes_ape:
            params["activite_principale"] = ",".join(codes_ape)

        if departements:
            params["departement"] = ",".join(departements)

        if effectif_min is not None or effectif_max is not None:
            # L'API SIRENE utilise des tranches d'effectifs
            # On construit une query pour filtrer
            if effectif_min is not None:
                params["minimal_effectif"] = effectif_min
            if effectif_max is not None:
                params["maximal_effectif"] = effectif_max

        if date_creation_min:
            params["date_creation_minimum"] = date_creation_min

        if forme_juridique:
            params["nature_juridique"] = ",".join(forme_juridique)

        # Requête
        url = f"{self.base_url}/search"
        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # Extraction des résultats
            results = []
            for result in data.get("results", []):
                company = self._parse_company(result)
                if company:
                    results.append(company)

            return {
                "results": results,
                "total_results": data.get("total_results", 0),
                "page": page,
                "per_page": per_page
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"Erreur HTTP {e.response.status_code}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Erreur lors de la recherche SIRENE: {e}")
            raise

    def search_all(
        self,
        codes_ape: Optional[List[str]] = None,
        departements: Optional[List[str]] = None,
        effectif_min: Optional[int] = None,
        effectif_max: Optional[int] = None,
        date_creation_min: Optional[str] = None,
        forme_juridique: Optional[List[str]] = None,
        max_results: int = MAX_RESULTS
    ) -> List[Dict[str, Any]]:
        """
        Recherche toutes les entreprises correspondant aux critères.
        Pagine automatiquement jusqu'à atteindre max_results.

        Args:
            codes_ape: Liste de codes APE
            departements: Liste de codes département
            effectif_min: Effectif minimum
            effectif_max: Effectif maximum
            date_creation_min: Date de création minimale
            forme_juridique: Liste de formes juridiques
            max_results: Nombre maximum de résultats à retourner

        Returns:
            Liste d'entreprises
        """
        all_results = []
        page = 1
        per_page = MAX_PER_PAGE

        logger.info(f"Début de la recherche SIRENE (max {max_results} résultats)...")

        while len(all_results) < max_results:
            try:
                response = self.search(
                    codes_ape=codes_ape,
                    departements=departements,
                    effectif_min=effectif_min,
                    effectif_max=effectif_max,
                    date_creation_min=date_creation_min,
                    forme_juridique=forme_juridique,
                    page=page,
                    per_page=per_page
                )

                results = response["results"]
                if not results:
                    logger.info("Plus de résultats disponibles.")
                    break

                all_results.extend(results)
                logger.info(
                    f"Page {page}: {len(results)} entreprises récupérées "
                    f"(total: {len(all_results)}/{response['total_results']})"
                )

                # Vérifier si on a atteint la fin
                if len(all_results) >= response["total_results"]:
                    break

                page += 1

            except Exception as e:
                logger.error(f"Erreur à la page {page}: {e}")
                break

        # Limiter au nombre maximum demandé
        final_results = all_results[:max_results]
        logger.info(f"Recherche terminée: {len(final_results)} entreprises trouvées.")

        return final_results

    def _parse_company(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse un résultat de l'API SIRENE et extrait les informations pertinentes.

        Args:
            result: Résultat brut de l'API

        Returns:
            Dict avec les informations de l'entreprise ou None si parsing échoue
        """
        try:
            # Extraction de l'adresse
            siege = result.get("siege", {})
            adresse_parts = []

            if siege.get("numero_voie"):
                adresse_parts.append(str(siege["numero_voie"]))
            if siege.get("type_voie"):
                adresse_parts.append(siege["type_voie"])
            if siege.get("libelle_voie"):
                adresse_parts.append(siege["libelle_voie"])
            if siege.get("complement_adresse"):
                adresse_parts.append(siege["complement_adresse"])

            adresse = " ".join(adresse_parts) if adresse_parts else ""

            return {
                "siren": result.get("siren", ""),
                "siret": siege.get("siret", ""),
                "denomination": result.get("nom_complet", result.get("nom_raison_sociale", "")),
                "adresse": adresse,
                "code_postal": siege.get("code_postal", ""),
                "ville": siege.get("libelle_commune", ""),
                "code_ape": result.get("activite_principale", ""),
                "libelle_ape": result.get("libelle_activite_principale", ""),
                "effectif": result.get("tranche_effectif_salarie", ""),
                "date_creation": result.get("date_creation", ""),
                "forme_juridique": result.get("nature_juridique", "")
            }

        except Exception as e:
            logger.warning(f"Erreur lors du parsing d'un résultat: {e}")
            return None

    def close(self) -> None:
        """Ferme le client HTTP."""
        self.client.close()

    def __enter__(self):
        """Support du context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ferme le client à la sortie du context manager."""
        self.close()
