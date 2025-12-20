"""
Orchestrateur d'enrichissement des données entreprises.
Gère la déduplication et l'enrichissement par batch.
"""
import logging
from typing import List, Dict, Any, Optional, Callable, Set, TYPE_CHECKING

from core.pappers_client import PappersClient
from config import BATCH_SIZE

if TYPE_CHECKING:
    from core.hubspot_client import HubSpotClient

logger = logging.getLogger(__name__)


class Enricher:
    """
    Orchestrateur d'enrichissement des données entreprises.
    Coordonne la déduplication et l'enrichissement via Pappers.
    Supporte déduplication contre HubSpot en plus de la déduplication interne.
    """

    def __init__(
        self,
        pappers_client: Optional[PappersClient] = None,
        hubspot_client: Optional["HubSpotClient"] = None
    ):
        """
        Initialise l'enricher.

        Args:
            pappers_client: Instance du client Pappers (optionnel si seulement dédup HubSpot)
            hubspot_client: Instance du client HubSpot (optionnel, pour déduplication)
        """
        self.pappers_client = pappers_client
        self.hubspot_client = hubspot_client

    def deduplicate(self, companies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Supprime les doublons basés sur le SIREN.
        Conserve la première occurrence de chaque SIREN.

        Args:
            companies: Liste d'entreprises

        Returns:
            Liste d'entreprises dédupliquées
        """
        if not companies:
            return []

        seen_sirens = set()
        deduplicated = []

        for company in companies:
            siren = company.get("siren")
            if not siren:
                logger.warning("Entreprise sans SIREN, ignorée pour déduplication")
                continue

            if siren not in seen_sirens:
                seen_sirens.add(siren)
                deduplicated.append(company)

        duplicates_count = len(companies) - len(deduplicated)
        if duplicates_count > 0:
            logger.info(f"{duplicates_count} doublons supprimés")

        return deduplicated

    def deduplicate_against_hubspot(
        self,
        companies: List[Dict[str, Any]],
        hubspot_siren_set: Optional[Set[str]] = None
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        Filtre les entreprises déjà présentes dans HubSpot.

        Args:
            companies: Liste d'entreprises
            hubspot_siren_set: Set de SIREN HubSpot (optionnel, auto-chargé si None)

        Returns:
            Tuple (entreprises filtrées, nombre de doublons HubSpot)
        """
        if not companies:
            return [], 0

        # Charger les SIREN HubSpot si nécessaire
        if hubspot_siren_set is None:
            if self.hubspot_client:
                hubspot_siren_set = self.hubspot_client.get_siren_set()
            else:
                logger.warning("Pas de client HubSpot configuré - déduplication HubSpot ignorée")
                return companies, 0

        if not hubspot_siren_set:
            logger.info("Aucun SIREN dans HubSpot - tous les leads sont nouveaux")
            return companies, 0

        # Filtrer
        filtered = []
        for company in companies:
            siren = company.get("siren")
            if siren and siren not in hubspot_siren_set:
                filtered.append(company)

        num_duplicates = len(companies) - len(filtered)

        if num_duplicates > 0:
            logger.info(f"🟠 {num_duplicates} leads déjà dans HubSpot (exclus)")

        return filtered, num_duplicates

    def enrich_batch(
        self,
        companies: List[Dict[str, Any]],
        progress_callback: Optional[Callable[[int, int], None]] = None,
        batch_size: int = BATCH_SIZE
    ) -> List[Dict[str, Any]]:
        """
        Enrichit une liste d'entreprises par batch.

        Args:
            companies: Liste d'entreprises à enrichir
            progress_callback: Fonction appelée avec (current, total) pour la progression
            batch_size: Taille des batchs pour enrichissement

        Returns:
            Liste d'entreprises enrichies
        """
        # Déduplication préalable
        companies = self.deduplicate(companies)

        if not companies:
            logger.warning("Aucune entreprise à enrichir après déduplication")
            return []

        # Si pas de client Pappers, retourner les entreprises sans enrichissement
        if not self.pappers_client:
            logger.warning("Pas de client Pappers configuré - enrichissement ignoré")
            return companies

        total = len(companies)
        enriched_companies = []

        logger.info(f"Début de l'enrichissement de {total} entreprises...")

        for i in range(0, total, batch_size):
            batch = companies[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total + batch_size - 1) // batch_size

            logger.info(
                f"Traitement du batch {batch_num}/{total_batches} "
                f"({len(batch)} entreprises)..."
            )

            for idx, company in enumerate(batch):
                current = i + idx + 1

                try:
                    # Enrichissement via Pappers
                    enriched = self.pappers_client.enrich_company(company)
                    enriched_companies.append(enriched)

                    # Callback de progression
                    if progress_callback:
                        progress_callback(current, total)

                except Exception as e:
                    logger.warning(
                        f"Échec de l'enrichissement pour {company.get('siren', 'N/A')}: {e}"
                    )
                    # On garde l'entreprise même si l'enrichissement échoue
                    enriched_companies.append(company)

                    # Callback même en cas d'erreur
                    if progress_callback:
                        progress_callback(current, total)

            logger.info(
                f"Batch {batch_num}/{total_batches} terminé. "
                f"Total enrichi: {len(enriched_companies)}/{total}"
            )

        credits_info = f"Crédits Pappers utilisés: {self.pappers_client.get_request_count()}" if self.pappers_client else ""
        logger.info(
            f"Enrichissement terminé: {len(enriched_companies)} entreprises enrichies. {credits_info}"
        )

        return enriched_companies

    def get_statistics(self, companies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calcule des statistiques sur les entreprises enrichies.

        Args:
            companies: Liste d'entreprises enrichies

        Returns:
            Dict avec statistiques
        """
        if not companies:
            return {
                "total": 0,
                "with_email": 0,
                "with_phone": 0,
                "with_website": 0,
                "with_dirigeant": 0,
                "with_ca": 0
            }

        stats = {
            "total": len(companies),
            "with_email": sum(1 for c in companies if c.get("email")),
            "with_phone": sum(1 for c in companies if c.get("telephone")),
            "with_website": sum(1 for c in companies if c.get("site_web")),
            "with_dirigeant": sum(1 for c in companies if c.get("dirigeant_nom")),
            "with_ca": sum(1 for c in companies if c.get("chiffre_affaires"))
        }

        # Calcul des pourcentages
        total = stats["total"]
        stats["email_percent"] = (stats["with_email"] / total * 100) if total > 0 else 0
        stats["phone_percent"] = (stats["with_phone"] / total * 100) if total > 0 else 0
        stats["website_percent"] = (stats["with_website"] / total * 100) if total > 0 else 0
        stats["dirigeant_percent"] = (stats["with_dirigeant"] / total * 100) if total > 0 else 0
        stats["ca_percent"] = (stats["with_ca"] / total * 100) if total > 0 else 0

        return stats
