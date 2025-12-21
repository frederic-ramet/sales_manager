"""
Client API GetSales.io pour récupération des leads et interactions LinkedIn.
"""
import os
import logging
import time
from typing import List, Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)


class GetSalesClient:
    """
    Client API GetSales.io.

    Fonctionnalités:
    - Récupération des leads
    - Récupération des messages LinkedIn
    - Récupération des flows/campagnes

    Usage:
        with GetSalesClient() as client:
            leads = client.fetch_leads()
            messages = client.fetch_lead_messages(lead_uuid)
    """

    BASE_URL = "https://amazing.getsales.io"
    RATE_LIMIT_DELAY = 0.5  # Délai entre requêtes (secondes)
    MAX_RETRIES = 3
    RETRY_DELAYS = [2, 4, 8]  # Backoff exponentiel

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialise le client GetSales.

        Args:
            api_key: Clé API GetSales (utilise GETSALES_API_KEY si None)
        """
        self.api_key = api_key or os.getenv('GETSALES_API_KEY')
        if not self.api_key:
            raise ValueError(
                "GETSALES_API_KEY non définie. "
                "Ajoutez-la dans .env ou passez-la au constructeur."
            )

        self.client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            timeout=30.0
        )

        self._last_request_time = 0
        self._request_count = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Ferme le client HTTP."""
        self.client.close()

    def _handle_rate_limit(self):
        """Gère le rate limiting entre requêtes."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()
        self._request_count += 1

    def _request_with_retry(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> httpx.Response:
        """
        Effectue une requête avec retry et backoff exponentiel.

        Args:
            method: GET, POST, etc.
            endpoint: Endpoint API
            **kwargs: Arguments pour httpx

        Returns:
            Response HTTP

        Raises:
            httpx.HTTPError: Si toutes les tentatives échouent
        """
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                self._handle_rate_limit()

                if method.upper() == "GET":
                    response = self.client.get(endpoint, **kwargs)
                elif method.upper() == "POST":
                    response = self.client.post(endpoint, **kwargs)
                else:
                    raise ValueError(f"Méthode non supportée: {method}")

                response.raise_for_status()
                return response

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429:  # Rate limited
                    delay = self.RETRY_DELAYS[min(attempt, len(self.RETRY_DELAYS) - 1)]
                    logger.warning(f"Rate limit atteint, pause {delay}s...")
                    time.sleep(delay)
                elif e.response.status_code >= 500:  # Server error
                    delay = self.RETRY_DELAYS[min(attempt, len(self.RETRY_DELAYS) - 1)]
                    logger.warning(f"Erreur serveur {e.response.status_code}, retry dans {delay}s...")
                    time.sleep(delay)
                else:
                    raise

            except httpx.RequestError as e:
                last_error = e
                delay = self.RETRY_DELAYS[min(attempt, len(self.RETRY_DELAYS) - 1)]
                logger.warning(f"Erreur réseau: {e}, retry dans {delay}s...")
                time.sleep(delay)

        raise last_error

    def test_connection(self) -> tuple[bool, str]:
        """
        Teste la connexion à l'API GetSales.

        Returns:
            (success, message)
        """
        try:
            response = self._request_with_retry("GET", "/flows/api/flows", params={"limit": 1})
            return True, "Connexion GetSales réussie"
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return False, "Clé API invalide"
            elif e.response.status_code == 403:
                return False, "Accès refusé"
            else:
                return False, f"Erreur HTTP {e.response.status_code}"
        except Exception as e:
            return False, f"Erreur: {str(e)}"

    def fetch_flows(self) -> List[Dict[str, Any]]:
        """
        Récupère la liste des flows/campagnes.

        Returns:
            Liste des flows avec uuid, name, status, etc.
        """
        logger.info("Récupération des flows GetSales...")

        try:
            response = self._request_with_retry("GET", "/flows/api/flows")
            data = response.json()

            # L'API peut retourner {data: [...]} ou directement [...]
            flows = data.get("data", data) if isinstance(data, dict) else data

            logger.info(f"{len(flows)} flows récupérés")
            return flows

        except Exception as e:
            logger.error(f"Erreur fetch flows: {e}")
            raise

    def fetch_leads(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Récupère les leads depuis GetSales.

        Args:
            filters: Filtres optionnels (list_uuid, flow_uuid, etc.)
            limit: Nombre max de leads à récupérer

        Returns:
            Liste des leads avec uuid, first_name, last_name, email, etc.
        """
        logger.info(f"Récupération des leads GetSales (limit={limit})...")

        payload = filters.copy() if filters else {}
        payload["limit"] = limit

        try:
            response = self._request_with_retry(
                "POST",
                "/leads/api/leads/search",
                json=payload
            )
            data = response.json()

            # L'API peut retourner {data: [...]} ou directement [...]
            leads = data.get("data", data) if isinstance(data, dict) else data

            # Extraire les données du lead de la structure imbriquée
            # L'API retourne {lead: {...}, markers: [], flows: [], custom_fields: {}}
            # On extrait 'lead' et on ajoute 'flows' pour garder les infos de campagne
            extracted_leads = []
            for item in leads:
                if isinstance(item, dict) and 'lead' in item:
                    lead_data = item['lead']
                    # Ajouter les flows (campagnes) au lead
                    if item.get('flows'):
                        lead_data['flows'] = item['flows']
                    if item.get('markers'):
                        lead_data['markers'] = item['markers']
                    extracted_leads.append(lead_data)
                else:
                    extracted_leads.append(item)

            logger.info(f"{len(extracted_leads)} leads récupérés")
            return extracted_leads

        except Exception as e:
            logger.error(f"Erreur fetch leads: {e}")
            raise

    def fetch_leads_paginated(
        self,
        filters: Optional[Dict[str, Any]] = None,
        max_results: int = 500,
        page_size: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Récupère les leads avec pagination.

        Args:
            filters: Filtres optionnels
            max_results: Nombre max total de leads
            page_size: Taille de chaque page

        Returns:
            Liste complète des leads
        """
        all_leads = []
        page = 1

        while len(all_leads) < max_results:
            payload = filters.copy() if filters else {}
            payload["limit"] = min(page_size, max_results - len(all_leads))
            payload["page"] = page

            try:
                response = self._request_with_retry(
                    "POST",
                    "/leads/api/leads/search",
                    json=payload
                )
                data = response.json()
                leads = data.get("data", data) if isinstance(data, dict) else data

                if not leads:
                    break

                # Extraire les données du lead de la structure imbriquée
                # Ajouter aussi les 'flows' pour garder les infos de campagne
                extracted_leads = []
                for item in leads:
                    if isinstance(item, dict) and 'lead' in item:
                        lead_data = item['lead']
                        if item.get('flows'):
                            lead_data['flows'] = item['flows']
                        if item.get('markers'):
                            lead_data['markers'] = item['markers']
                        extracted_leads.append(lead_data)
                    else:
                        extracted_leads.append(item)

                all_leads.extend(extracted_leads)
                logger.info(f"Page {page}: {len(extracted_leads)} leads (total: {len(all_leads)})")

                if len(extracted_leads) < page_size:
                    break

                page += 1

            except Exception as e:
                logger.error(f"Erreur pagination page {page}: {e}")
                break

        return all_leads[:max_results]

    def fetch_lead_messages(self, lead_uuid: str) -> List[Dict[str, Any]]:
        """
        Récupère les messages LinkedIn pour un lead.

        Args:
            lead_uuid: UUID du lead GetSales

        Returns:
            Liste des messages avec type, status, text, sent_at, etc.
        """
        logger.debug(f"Récupération messages pour lead {lead_uuid}...")

        try:
            response = self._request_with_retry(
                "GET",
                "/flows/api/linkedin-messages",
                params={"filter[lead_uuid]": lead_uuid}
            )
            data = response.json()

            messages = data.get("data", data) if isinstance(data, dict) else data

            logger.debug(f"{len(messages)} messages récupérés pour {lead_uuid}")
            return messages

        except Exception as e:
            logger.warning(f"Erreur fetch messages pour {lead_uuid}: {e}")
            return []

    def fetch_lead_with_messages(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrichit un lead avec ses messages.

        Args:
            lead: Lead brut depuis fetch_leads

        Returns:
            Lead avec clé '_messages' ajoutée
        """
        lead_uuid = lead.get("uuid")
        if not lead_uuid:
            lead["_messages"] = []
            return lead

        messages = self.fetch_lead_messages(lead_uuid)
        lead["_messages"] = messages
        return lead

    def fetch_leads_with_messages(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Récupère les leads avec leurs messages.

        Args:
            filters: Filtres optionnels
            limit: Nombre max de leads

        Returns:
            Liste des leads enrichis avec '_messages'
        """
        leads = self.fetch_leads(filters=filters, limit=limit)

        enriched_leads = []
        for i, lead in enumerate(leads):
            enriched = self.fetch_lead_with_messages(lead)
            enriched_leads.append(enriched)

            if (i + 1) % 10 == 0:
                logger.info(f"Messages récupérés: {i + 1}/{len(leads)}")

        return enriched_leads

    def get_request_count(self) -> int:
        """Retourne le nombre de requêtes effectuées."""
        return self._request_count
