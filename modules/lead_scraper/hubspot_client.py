"""
Client API HubSpot pour synchronisation bidirectionnelle des contacts.
Gère le miroir local, la déduplication et l'export vers HubSpot.
"""
import json
import os
import re
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Chemin par défaut du miroir
DEFAULT_MIRROR_PATH = Path(__file__).parent.parent.parent / "data" / "hubspot_mirror.json"


class HubSpotClient:
    """
    Client API HubSpot v3 pour gestion des contacts.

    Fonctionnalités :
    - Synchronisation contacts HubSpot → miroir local JSON
    - Déduplication via SIREN
    - Export contacts vers HubSpot (batch)
    - Génération URLs fiches contacts

    Usage:
        with HubSpotClient() as client:
            client.sync_contacts()
            client.push_contacts(new_leads)
    """

    HUBSPOT_BASE_URL = "https://api.hubapi.com"
    RATE_LIMIT = 100  # req/10sec
    BATCH_SIZE = 100  # contacts par batch

    # Mapping propriétés Lead Gen → HubSpot
    PROPERTY_MAPPING = {
        "denomination": "company",
        "email": "email",
        "telephone": "phone",
        "dirigeant_nom": "lastname",
        "dirigeant_prenom": "firstname",
        "dirigeant_fonction": "jobtitle",
        "siren": "siren",
        "code_ape": "code_ape",
        "effectif": "effectif",
        "chiffre_affaires": "chiffre_affaires",
        "ville": "city",
        "adresse": "address",
        "code_postal": "zip"
    }

    # Propriétés standard HubSpot (toujours disponibles)
    STANDARD_PROPERTIES = [
        "firstname", "lastname", "email", "phone", "company",
        "jobtitle", "city", "address", "zip", "hs_object_id", "createdate"
    ]

    # Propriétés personnalisées (peuvent ne pas exister)
    CUSTOM_PROPERTIES = [
        "siren", "code_ape", "effectif", "chiffre_affaires"
    ]

    # Toutes les propriétés (pour compatibilité)
    SYNC_PROPERTIES = STANDARD_PROPERTIES + CUSTOM_PROPERTIES

    def __init__(self, api_key: Optional[str] = None, mirror_path: Optional[str] = None):
        """
        Initialise le client HubSpot.

        Args:
            api_key: Clé API HubSpot (Private App token), utilise HUBSPOT_API_KEY si None
            mirror_path: Chemin du fichier miroir local (optionnel)
        """
        self.api_key = api_key or os.getenv('HUBSPOT_API_KEY')
        if not self.api_key:
            raise ValueError(
                "HUBSPOT_API_KEY non définie. "
                "Ajoutez-la dans .env ou passez-la au constructeur."
            )

        self.mirror_path = mirror_path or str(DEFAULT_MIRROR_PATH)

        self.client = httpx.Client(
            base_url=self.HUBSPOT_BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )

        # Créer le dossier data si nécessaire
        Path(self.mirror_path).parent.mkdir(parents=True, exist_ok=True)

        # Compteur pour rate limiting
        self.request_count = 0
        self.window_start = time.time()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()

    def close(self):
        """Ferme le client HTTP."""
        self.client.close()

    def _handle_rate_limit(self):
        """Gère le rate limiting (100 req/10sec)."""
        self.request_count += 1

        # Reset tous les 10 secondes
        if time.time() - self.window_start >= 10:
            self.request_count = 0
            self.window_start = time.time()

        # Si on approche la limite, on attend
        if self.request_count >= self.RATE_LIMIT:
            wait_time = 10 - (time.time() - self.window_start)
            if wait_time > 0:
                logger.info(f"Rate limit HubSpot approché - pause {wait_time:.1f}s")
                time.sleep(wait_time)
                self.request_count = 0
                self.window_start = time.time()

    def test_connection(self) -> tuple[bool, str]:
        """
        Teste la connexion à l'API HubSpot.

        Returns:
            (success, message)
        """
        try:
            self._handle_rate_limit()
            response = self.client.get("/crm/v3/objects/contacts", params={"limit": 1})
            response.raise_for_status()
            return True, "Connexion HubSpot réussie"
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return False, "Clé API invalide"
            elif e.response.status_code == 403:
                return False, "Permissions insuffisantes"
            else:
                return False, f"Erreur HTTP {e.response.status_code}"
        except Exception as e:
            return False, f"Erreur: {str(e)}"

    def _is_uuid(self, value: str) -> bool:
        """
        Vérifie si une valeur est un UUID.

        Args:
            value: Valeur à vérifier

        Returns:
            True si c'est un UUID
        """
        if not value or not isinstance(value, str):
            return False
        # Format UUID: 8-4-4-4-12 caractères hexadécimaux
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        return bool(re.match(uuid_pattern, value.lower()))

    def get_company_details(self, company_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les détails d'une company HubSpot par son ID.

        Args:
            company_id: ID de la company (UUID)

        Returns:
            Dict avec les détails de la company ou None
        """
        try:
            self._handle_rate_limit()
            response = self.client.get(
                f"/crm/v3/objects/companies/{company_id}",
                params={
                    "properties": "name,domain,industry,city,state,country,numberofemployees,annualrevenue,hs_object_id"
                }
            )
            response.raise_for_status()
            data = response.json()
            props = data.get("properties", {})

            return {
                "name": props.get("name", ""),
                "domain": props.get("domain", ""),
                "industry": props.get("industry", ""),
                "city": props.get("city", ""),
                "state": props.get("state", ""),
                "country": props.get("country", ""),
                "employees": props.get("numberofemployees", ""),
                "revenue": props.get("annualrevenue", ""),
                "hubspot_company_id": data.get("id", "")
            }

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Company {company_id} non trouvée")
            elif e.response.status_code == 403:
                logger.warning(
                    f"Permissions insuffisantes pour lire les companies - "
                    f"ajoutez 'crm.objects.companies.read'"
                )
            else:
                logger.error(f"Erreur récupération company {company_id}: HTTP {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Erreur récupération company {company_id}: {e}")
            return None

    def sync_contacts(self, progress_callback=None) -> Dict[str, Any]:
        """
        Synchronise tous les contacts HubSpot vers le miroir local.

        Args:
            progress_callback: Fonction callback(current, total) optionnelle

        Returns:
            Dict avec résultats de la sync
        """
        logger.info("Début de la synchronisation HubSpot...")

        contacts = []
        after = None
        page = 0
        properties_to_use = None
        custom_properties_available = True

        try:
            # Déterminer quelles propriétés utiliser
            try:
                self._handle_rate_limit()
                test_response = self.client.get(
                    "/crm/v3/objects/contacts",
                    params={
                        "limit": 1,
                        "properties": ",".join(self.SYNC_PROPERTIES)
                    }
                )
                test_response.raise_for_status()
                properties_to_use = self.SYNC_PROPERTIES
                logger.info("Propriétés personnalisées détectées et disponibles")

            except httpx.HTTPStatusError as e:
                if e.response.status_code in [400, 401]:
                    logger.warning(
                        "Propriétés personnalisées non disponibles - "
                        "utilisation des propriétés standard uniquement"
                    )

                    self._handle_rate_limit()
                    test_response = self.client.get(
                        "/crm/v3/objects/contacts",
                        params={
                            "limit": 1,
                            "properties": ",".join(self.STANDARD_PROPERTIES)
                        }
                    )
                    test_response.raise_for_status()
                    properties_to_use = self.STANDARD_PROPERTIES
                    custom_properties_available = False
                else:
                    raise

            # Synchronisation principale
            while True:
                self._handle_rate_limit()

                params = {
                    "limit": 100,
                    "properties": ",".join(properties_to_use),
                    "associations": "companies"
                }
                if after:
                    params["after"] = after

                response = self.client.get("/crm/v3/objects/contacts", params=params)
                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                for result in results:
                    contact = self._parse_contact(result)
                    if contact:
                        contacts.append(contact)

                page += 1
                if progress_callback:
                    progress_callback(len(contacts), "sync")

                logger.info(f"Page {page}: {len(results)} contacts récupérés (total: {len(contacts)})")

                paging = data.get("paging", {})
                if "next" in paging:
                    after = paging["next"]["after"]
                else:
                    break

            # Sauvegarder le miroir
            mirror_data = {
                "last_sync": datetime.now().isoformat(),
                "total_contacts": len(contacts),
                "contacts": contacts,
                "custom_properties_available": custom_properties_available
            }

            with open(self.mirror_path, 'w', encoding='utf-8') as f:
                json.dump(mirror_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Synchronisation terminée: {len(contacts)} contacts")

            return {
                "success": True,
                "total_contacts": len(contacts),
                "last_sync": mirror_data["last_sync"],
                "custom_properties_available": custom_properties_available
            }

        except Exception as e:
            logger.error(f"Erreur lors de la synchronisation: {e}")
            raise

    def sync_recent_contacts(self, since_days: int = 1, progress_callback=None) -> Dict[str, Any]:
        """
        Synchronise uniquement les contacts modifiés récemment.

        Args:
            since_days: Nombre de jours en arrière (default: 1)
            progress_callback: Fonction callback(current, total) optionnelle

        Returns:
            Dict avec résultats de la sync incrémentale
        """
        from datetime import datetime, timedelta

        logger.info(f"Début de la synchronisation incrémentale HubSpot (depuis {since_days} jours)...")

        # Calculer timestamp (millisecondes depuis epoch)
        since_date = datetime.now() - timedelta(days=since_days)
        since_timestamp = int(since_date.timestamp() * 1000)

        contacts = []
        properties_to_use = None
        custom_properties_available = True

        try:
            # Déterminer quelles propriétés utiliser
            try:
                self._handle_rate_limit()
                test_response = self.client.get(
                    "/crm/v3/objects/contacts",
                    params={
                        "limit": 1,
                        "properties": ",".join(self.SYNC_PROPERTIES)
                    }
                )
                test_response.raise_for_status()
                properties_to_use = self.SYNC_PROPERTIES
                logger.info("Propriétés personnalisées détectées et disponibles")

            except httpx.HTTPStatusError as e:
                if e.response.status_code in [400, 401]:
                    logger.warning(
                        "Propriétés personnalisées non disponibles - "
                        "utilisation des propriétés standard uniquement"
                    )
                    properties_to_use = self.STANDARD_PROPERTIES
                    custom_properties_available = False
                else:
                    raise

            # Recherche avec filtre lastmodifieddate
            self._handle_rate_limit()

            search_payload = {
                "filterGroups": [
                    {
                        "filters": [
                            {
                                "propertyName": "lastmodifieddate",
                                "operator": "GTE",
                                "value": str(since_timestamp)
                            }
                        ]
                    }
                ],
                "properties": properties_to_use,
                "limit": 100
            }

            after = 0
            page = 0

            while True:
                search_payload["after"] = after

                self._handle_rate_limit()
                response = self.client.post(
                    "/crm/v3/objects/contacts/search",
                    json=search_payload
                )
                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                for result in results:
                    contact = self._parse_contact(result)
                    if contact:
                        contacts.append(contact)

                page += 1
                if progress_callback:
                    progress_callback(len(contacts), "sync_incremental")

                logger.info(f"Page {page}: {len(results)} contacts récupérés (total: {len(contacts)})")

                # Pagination
                paging = data.get("paging", {})
                if "next" in paging:
                    after = paging["next"]["after"]
                else:
                    break

            logger.info(f"Synchronisation incrémentale terminée: {len(contacts)} contacts modifiés")

            return {
                "success": True,
                "total_contacts": len(contacts),
                "since_date": since_date.isoformat(),
                "contacts": contacts,
                "custom_properties_available": custom_properties_available
            }

        except Exception as e:
            logger.error(f"Erreur lors de la synchronisation incrémentale: {e}")
            raise

    def _parse_contact(self, raw_contact: Dict) -> Optional[Dict[str, Any]]:
        """
        Parse un contact brut de l'API HubSpot.

        Args:
            raw_contact: Contact brut depuis l'API

        Returns:
            Contact formaté ou None si invalide
        """
        try:
            props = raw_contact.get("properties", {})

            # Construire le dirigeant complet
            dirigeant_parts = []
            if props.get("firstname"):
                dirigeant_parts.append(props["firstname"])
            if props.get("lastname"):
                dirigeant_parts.append(props["lastname"])
            dirigeant = " ".join(dirigeant_parts) if dirigeant_parts else ""

            # Initialiser les champs company
            company_name = ""
            company_industry = ""
            company_city = props.get("city", "")
            company_employees = props.get("effectif")

            # PRIORITÉ 1 : Utiliser les associations company
            associations = raw_contact.get("associations", {})
            company_associations = associations.get("companies", {}).get("results", [])

            if company_associations:
                first_company_id = company_associations[0].get("id")
                if first_company_id:
                    logger.debug(f"Association company trouvée: {first_company_id}")
                    company_details = self.get_company_details(first_company_id)

                    if company_details:
                        company_name = company_details.get("name", "")
                        company_industry = company_details.get("industry", "")
                        if company_details.get("city"):
                            company_city = company_details["city"]
                        if company_details.get("employees"):
                            company_employees = company_details["employees"]

            # PRIORITÉ 2 : Fallback sur le champ company
            if not company_name:
                company_field = props.get("company", "")

                if company_field and self._is_uuid(company_field):
                    company_details = self.get_company_details(company_field)
                    if company_details:
                        company_name = company_details.get("name", "")
                        company_industry = company_details.get("industry", "")
                        if company_details.get("city"):
                            company_city = company_details["city"]
                        if company_details.get("employees"):
                            company_employees = company_details["employees"]
                elif company_field and not self._is_uuid(company_field):
                    company_name = company_field

            contact = {
                "hubspot_id": raw_contact.get("id"),
                "siren": props.get("siren", ""),
                "denomination": company_name,
                "email": props.get("email", ""),
                "telephone": props.get("phone", ""),
                "dirigeant": dirigeant,
                "fonction": props.get("jobtitle", ""),
                "code_ape": props.get("code_ape", ""),
                "secteur": company_industry,
                "ville": company_city,
                "adresse": props.get("address", ""),
                "code_postal": props.get("zip", ""),
                "effectif": company_employees,
                "chiffre_affaires": props.get("chiffre_affaires"),
                "created_at": props.get("createdate", "")
            }

            return contact

        except Exception as e:
            logger.warning(f"Erreur parsing contact {raw_contact.get('id')}: {e}")
            return None

    def get_mirror(self) -> Dict[str, Any]:
        """
        Charge et retourne le miroir local.

        Returns:
            Dict avec last_sync, total_contacts, contacts
        """
        if not Path(self.mirror_path).exists():
            return {
                "last_sync": None,
                "total_contacts": 0,
                "contacts": []
            }

        try:
            with open(self.mirror_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erreur lecture miroir: {e}")
            return {
                "last_sync": None,
                "total_contacts": 0,
                "contacts": []
            }

    def get_siren_set(self) -> Set[str]:
        """
        Retourne l'ensemble des SIREN présents dans HubSpot.

        Returns:
            Set de SIREN (strings)
        """
        mirror = self.get_mirror()
        sirens = {
            contact.get("siren")
            for contact in mirror.get("contacts", [])
            if contact.get("siren") and contact.get("siren").strip()
        }
        return sirens

    def update_contacts(self, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Met à jour des contacts existants dans HubSpot (batch).

        Args:
            updates: Liste de dict avec format:
                {"hubspot_id": "123", "properties": {"siren": "...", ...}}

        Returns:
            Dict avec résultats (updated, errors)
        """
        if not updates:
            return {"updated": 0, "errors": []}

        logger.info(f"Mise à jour de {len(updates)} contacts dans HubSpot...")

        updated = 0
        errors = []

        for i in range(0, len(updates), self.BATCH_SIZE):
            batch = updates[i:i + self.BATCH_SIZE]

            try:
                inputs = []
                for update in batch:
                    hubspot_id = update.get("hubspot_id")
                    properties = update.get("properties", {})

                    if not hubspot_id:
                        logger.warning("Update sans hubspot_id, ignoré")
                        continue

                    properties_str = {
                        k: str(v) if v is not None else ""
                        for k, v in properties.items()
                    }

                    inputs.append({
                        "id": hubspot_id,
                        "properties": properties_str
                    })

                if not inputs:
                    continue

                self._handle_rate_limit()
                response = self.client.post(
                    "/crm/v3/objects/contacts/batch/update",
                    json={"inputs": inputs}
                )
                response.raise_for_status()
                data = response.json()

                batch_updated = len(data.get("results", []))
                updated += batch_updated
                logger.info(f"Batch {i//self.BATCH_SIZE + 1}: {batch_updated} contacts mis à jour")

            except httpx.HTTPStatusError as e:
                error_msg = f"Erreur HTTP {e.response.status_code}: {e.response.text}"
                logger.error(error_msg)
                errors.append(error_msg)
            except Exception as e:
                error_msg = f"Erreur batch {i//self.BATCH_SIZE + 1}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        logger.info(f"Mise à jour terminée: {updated} mis à jour, {len(errors)} erreurs")

        return {"updated": updated, "errors": errors}

    def push_contacts(self, contacts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Envoie des contacts vers HubSpot (création batch).

        Args:
            contacts: Liste de contacts à créer

        Returns:
            Dict avec résultats (created, errors)
        """
        if not contacts:
            return {"created": 0, "errors": []}

        logger.info(f"Push de {len(contacts)} contacts vers HubSpot...")

        created = 0
        errors = []

        for i in range(0, len(contacts), self.BATCH_SIZE):
            batch = contacts[i:i + self.BATCH_SIZE]

            try:
                inputs = []
                for contact in batch:
                    properties = self._map_properties(contact)
                    inputs.append({"properties": properties})

                self._handle_rate_limit()
                response = self.client.post(
                    "/crm/v3/objects/contacts/batch/create",
                    json={"inputs": inputs}
                )
                response.raise_for_status()
                data = response.json()

                created += len(data.get("results", []))
                logger.info(f"Batch {i//self.BATCH_SIZE + 1}: {len(data.get('results', []))} contacts créés")

            except httpx.HTTPStatusError as e:
                error_msg = f"Erreur HTTP {e.response.status_code}: {e.response.text}"
                logger.error(error_msg)
                errors.append(error_msg)
            except Exception as e:
                error_msg = f"Erreur batch {i//self.BATCH_SIZE + 1}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        logger.info(f"Push terminé: {created} créés, {len(errors)} erreurs")

        return {"created": created, "errors": errors}

    def _map_properties(self, contact: Dict[str, Any]) -> Dict[str, str]:
        """
        Mappe les propriétés du contact vers les propriétés HubSpot.

        Accepte:
        - Noms internes legacy (denomination, telephone, dirigeant_nom...)
        - Noms HubSpot directs (company, phone, firstname...)
        - Noms unified_contacts (company_name, job_title...)

        Args:
            contact: Contact avec propriétés

        Returns:
            Dict de propriétés HubSpot
        """
        properties = {}

        # Mapping étendu: plusieurs noms possibles pour chaque propriété HubSpot
        EXTENDED_MAPPING = {
            'email': ['email'],
            'firstname': ['firstname', 'dirigeant_prenom', 'first_name'],
            'lastname': ['lastname', 'dirigeant_nom', 'last_name'],
            'phone': ['phone', 'telephone', 'tel'],
            'mobilephone': ['mobilephone', 'mobile'],
            'company': ['company', 'denomination', 'company_name'],
            'jobtitle': ['jobtitle', 'dirigeant_fonction', 'job_title', 'fonction'],
            'website': ['website', 'site_web'],
            'address': ['address', 'adresse'],
            'city': ['city', 'ville'],
            'zip': ['zip', 'code_postal', 'postal_code'],
            'country': ['country', 'pays'],
            'siren': ['siren'],
            'siret': ['siret'],
            'code_ape': ['code_ape', 'ape_code'],
            'effectif': ['effectif', 'employee_range'],
            'chiffre_affaires': ['chiffre_affaires', 'revenue_range'],
            'linkedin_url': ['linkedin_url', 'linkedin'],
        }

        for hubspot_prop, possible_names in EXTENDED_MAPPING.items():
            for name in possible_names:
                value = contact.get(name)
                if value is not None and str(value).strip():
                    properties[hubspot_prop] = str(value)
                    break  # Prendre la première valeur trouvée

        return properties

    def contact_url(self, hubspot_id: str, portal_id: Optional[str] = None) -> str:
        """
        Génère l'URL de la fiche contact HubSpot.

        Args:
            hubspot_id: ID du contact
            portal_id: ID du portail (optionnel)

        Returns:
            URL de la fiche contact
        """
        if not portal_id:
            portal_id = os.getenv('HUBSPOT_PORTAL_ID', 'PORTAL_ID')

        return f"https://app.hubspot.com/contacts/{portal_id}/contact/{hubspot_id}"

    def update_mirror_with_pushed(self, pushed_contacts: List[Dict[str, Any]]):
        """
        Met à jour le miroir local avec les contacts qui viennent d'être pushés.

        Args:
            pushed_contacts: Contacts qui ont été envoyés à HubSpot
        """
        try:
            mirror = self.get_mirror()

            for contact in pushed_contacts:
                mirror_entry = {
                    "hubspot_id": None,
                    "siren": contact.get("siren", ""),
                    "denomination": contact.get("denomination", ""),
                    "email": contact.get("email", ""),
                    "telephone": contact.get("telephone", ""),
                    "dirigeant": f"{contact.get('dirigeant_prenom', '')} {contact.get('dirigeant_nom', '')}".strip(),
                    "fonction": contact.get("dirigeant_fonction", ""),
                    "code_ape": contact.get("code_ape", ""),
                    "ville": contact.get("ville", ""),
                    "created_at": datetime.now().isoformat()
                }
                mirror["contacts"].append(mirror_entry)

            mirror["total_contacts"] = len(mirror["contacts"])
            mirror["last_update"] = datetime.now().isoformat()

            with open(self.mirror_path, 'w', encoding='utf-8') as f:
                json.dump(mirror, f, ensure_ascii=False, indent=2)

            logger.info(f"Miroir mis à jour avec {len(pushed_contacts)} nouveaux contacts")

        except Exception as e:
            logger.error(f"Erreur mise à jour miroir: {e}")
