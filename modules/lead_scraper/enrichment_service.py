"""
Enrichment Module V2 - Enrichissement des données via Pappers/SIRENE.

Pipeline: Import → Clean → Enrich → Sync

Usage:
    enricher = EnrichmentService(company_manager, contact_manager)

    # Enrichir une entreprise
    result = enricher.enrich_company(company_uuid)

    # Enrichir en batch
    report = enricher.enrich_batch(limit=100)
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Import optionnel des clients
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


class PappersClientV2:
    """
    Client Pappers simplifié pour enrichissement V2.
    """

    BASE_URL = "https://api.pappers.fr/v2"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get('PAPPERS_API_KEY')
        self._client = None

    def _get_client(self):
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx non installé")
        if not self._client:
            import httpx
            self._client = httpx.Client(timeout=30.0)
        return self._client

    def get_company(self, siren: str) -> Optional[Dict[str, Any]]:
        """Récupère les données d'une entreprise par SIREN."""
        if not self.api_key:
            return None

        if not siren or len(siren) < 9:
            return None

        siren = siren[:9]

        try:
            response = self._get_client().get(
                f"{self.BASE_URL}/entreprise",
                params={'siren': siren, 'api_token': self.api_key}
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.debug(f"Entreprise non trouvée: {siren}")
            elif response.status_code == 429:
                logger.warning("Quota Pappers dépassé")
            else:
                logger.error(f"Erreur Pappers {response.status_code}")

        except Exception as e:
            logger.error(f"Erreur Pappers: {e}")

        return None

    def close(self):
        if self._client:
            self._client.close()


class SireneClientV2:
    """
    Client SIRENE simplifié pour enrichissement V2.
    """

    BASE_URL = "https://recherche-entreprises.api.gouv.fr"

    def __init__(self):
        self._client = None

    def _get_client(self):
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx non installé")
        if not self._client:
            import httpx
            self._client = httpx.Client(timeout=30.0)
        return self._client

    def get_company(self, siren: str) -> Optional[Dict[str, Any]]:
        """Récupère les données d'une entreprise par SIREN."""
        if not siren or len(siren) < 9:
            return None

        siren = siren[:9]

        try:
            response = self._get_client().get(
                f"{self.BASE_URL}/search",
                params={'q': siren, 'page': 1, 'per_page': 1}
            )

            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                if results:
                    return results[0]

        except Exception as e:
            logger.error(f"Erreur SIRENE: {e}")

        return None

    def close(self):
        if self._client:
            self._client.close()


class EnrichmentService:
    """
    Service d'enrichissement des données - Schema V2.

    Sources:
    - Pappers: Dirigeants, CA, effectifs, forme juridique
    - SIRENE: Adresse complète, code APE
    """

    def __init__(self, company_manager=None, contact_manager=None):
        """
        Args:
            company_manager: Instance de CompanyManagerV2
            contact_manager: Instance de ContactManagerV2
        """
        self.company_manager = company_manager
        self.contact_manager = contact_manager
        self._pappers = None
        self._sirene = None

    def _get_pappers(self) -> PappersClientV2:
        if not self._pappers:
            self._pappers = PappersClientV2()
        return self._pappers

    def _get_sirene(self) -> SireneClientV2:
        if not self._sirene:
            self._sirene = SireneClientV2()
        return self._sirene

    def enrich_company(
        self,
        company_uuid: str,
        source: str = 'pappers'
    ) -> Dict[str, Any]:
        """
        Enrichit une entreprise avec données Pappers ou SIRENE.

        Args:
            company_uuid: UUID de l'entreprise
            source: 'pappers' ou 'sirene'

        Returns:
            {
                'success': bool,
                'updated_fields': [...],
                'contacts_added': int,
                'error': str (si erreur)
            }
        """
        result = {
            'success': False,
            'updated_fields': [],
            'contacts_added': 0,
            'error': None
        }

        if not self.company_manager:
            result['error'] = 'CompanyManager non initialisé'
            return result

        # Récupérer l'entreprise
        company = self.company_manager.get(company_uuid)
        if not company:
            result['error'] = 'Entreprise non trouvée'
            return result

        siren = company.get('siren')
        if not siren:
            result['error'] = 'SIREN manquant'
            return result

        # Enrichir selon la source
        if source == 'pappers':
            enriched_data = self._enrich_from_pappers(siren)
        else:
            enriched_data = self._enrich_from_sirene(siren)

        if not enriched_data:
            result['error'] = f'Aucune donnée trouvée ({source})'
            return result

        # Appliquer les mises à jour
        updates = {}
        contacts_to_add = []

        for field, value in enriched_data.items():
            if field == 'contacts':
                contacts_to_add = value
            elif value and not company.get(field):
                updates[field] = value
                result['updated_fields'].append(field)

        # Mettre à jour l'entreprise
        if updates:
            updates['enriched_at'] = datetime.now()
            updates['enrichment_source'] = source
            self.company_manager.update(company_uuid, updates)

        # Ajouter les contacts (dirigeants)
        if contacts_to_add and self.contact_manager:
            for contact_data in contacts_to_add:
                try:
                    _, created = self.contact_manager.find_or_create(
                        contact_data,
                        company_uuid=company_uuid,
                        source=source
                    )
                    if created:
                        result['contacts_added'] += 1
                except Exception as e:
                    logger.error(f"Erreur ajout contact: {e}")

        result['success'] = True
        return result

    def _enrich_from_pappers(self, siren: str) -> Optional[Dict[str, Any]]:
        """Récupère et mappe les données Pappers."""
        try:
            pappers = self._get_pappers()
            data = pappers.get_company(siren)

            if not data:
                return None

            result = {}

            # Données entreprise
            if data.get('denomination'):
                result['name'] = data['denomination']

            if data.get('forme_juridique'):
                result['legal_form'] = data['forme_juridique']

            if data.get('code_naf'):
                result['ape_code'] = data['code_naf']

            if data.get('libelle_code_naf'):
                result['ape_label'] = data['libelle_code_naf']

            # Adresse siège
            siege = data.get('siege', {})
            if siege.get('adresse_ligne_1'):
                result['hq_address'] = siege['adresse_ligne_1']
            if siege.get('ville'):
                result['hq_city'] = siege['ville']
            if siege.get('code_postal'):
                result['hq_postal_code'] = siege['code_postal']

            # Effectif
            if data.get('effectif'):
                result['size'] = data['effectif']
            if data.get('tranche_effectif'):
                result['size'] = data['tranche_effectif']

            # Finances (dernier exercice)
            finances = data.get('finances', [])
            if finances:
                dernier = finances[0]
                if dernier.get('chiffre_affaires'):
                    result['revenue'] = dernier['chiffre_affaires']

            # Date création
            if data.get('date_creation'):
                result['founded_date'] = data['date_creation']

            # Dirigeants → Contacts
            dirigeants = data.get('representants', [])
            contacts = []
            for dir in dirigeants[:5]:  # Max 5 dirigeants
                if dir.get('nom') or dir.get('prenom'):
                    contacts.append({
                        'firstname': dir.get('prenom', ''),
                        'lastname': dir.get('nom', ''),
                        'job_title': dir.get('qualite', 'Dirigeant'),
                        'seniority': 'C-Level'
                    })

            if contacts:
                result['contacts'] = contacts

            return result

        except Exception as e:
            logger.error(f"Erreur enrichissement Pappers: {e}")
            return None

    def _enrich_from_sirene(self, siren: str) -> Optional[Dict[str, Any]]:
        """Récupère et mappe les données SIRENE."""
        try:
            sirene = self._get_sirene()
            data = sirene.get_company(siren)

            if not data:
                return None

            result = {}

            # Nom
            if data.get('nom_complet'):
                result['name'] = data['nom_complet']
            elif data.get('nom_raison_sociale'):
                result['name'] = data['nom_raison_sociale']

            # Nature juridique
            if data.get('nature_juridique'):
                result['legal_form'] = data['nature_juridique']

            # Activité
            if data.get('activite_principale'):
                result['ape_code'] = data['activite_principale']

            if data.get('libelle_activite_principale'):
                result['ape_label'] = data['libelle_activite_principale']

            # Siège
            siege = data.get('siege', {})
            if siege:
                if siege.get('adresse'):
                    result['hq_address'] = siege['adresse']
                if siege.get('commune'):
                    result['hq_city'] = siege['commune']
                if siege.get('code_postal'):
                    result['hq_postal_code'] = siege['code_postal']
                if siege.get('departement'):
                    result['hq_state'] = siege['departement']

            # Effectif
            if data.get('tranche_effectif_salarie'):
                result['size'] = data['tranche_effectif_salarie']

            # Date création
            if data.get('date_creation'):
                result['founded_date'] = data['date_creation']

            return result

        except Exception as e:
            logger.error(f"Erreur enrichissement SIRENE: {e}")
            return None

    def enrich_batch(
        self,
        source: str = 'pappers',
        limit: int = 100,
        only_unenriched: bool = True,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Enrichit un lot d'entreprises.

        Args:
            source: 'pappers' ou 'sirene'
            limit: Nombre max d'entreprises
            only_unenriched: Uniquement celles non enrichies
            progress_callback: Callback(current, total)

        Returns:
            Rapport d'enrichissement
        """
        report = {
            'success': True,
            'total_processed': 0,
            'enriched': 0,
            'contacts_added': 0,
            'skipped': 0,
            'errors': [],
            'started_at': datetime.now().isoformat()
        }

        if not self.company_manager:
            report['success'] = False
            report['errors'].append('CompanyManager non initialisé')
            return report

        # Récupérer les entreprises à enrichir
        companies = self._get_companies_to_enrich(limit, only_unenriched)

        if not companies:
            report['errors'].append('Aucune entreprise à enrichir')
            return report

        total = len(companies)

        for i, company in enumerate(companies):
            if progress_callback:
                progress_callback(i + 1, total)

            report['total_processed'] += 1

            if not company.get('siren'):
                report['skipped'] += 1
                continue

            try:
                result = self.enrich_company(company['uuid'], source=source)

                if result['success']:
                    if result['updated_fields']:
                        report['enriched'] += 1
                    report['contacts_added'] += result['contacts_added']
                else:
                    if result.get('error'):
                        report['errors'].append(
                            f"{company.get('name', 'Unknown')}: {result['error']}"
                        )

            except Exception as e:
                report['errors'].append(
                    f"{company.get('name', 'Unknown')}: {str(e)}"
                )

        report['finished_at'] = datetime.now().isoformat()
        return report

    def _get_companies_to_enrich(
        self,
        limit: int,
        only_unenriched: bool
    ) -> List[Dict[str, Any]]:
        """Récupère les entreprises prioritaires pour enrichissement."""
        if not self.company_manager:
            return []

        companies = self.company_manager.list_all(status='active', limit=limit * 2)

        # Filtrer
        result = []
        for c in companies:
            # Doit avoir un SIREN
            if not c.get('siren'):
                continue

            # Si only_unenriched, exclure les déjà enrichies
            if only_unenriched and c.get('enriched_at'):
                continue

            result.append(c)

            if len(result) >= limit:
                break

        # Trier par taille (grandes entreprises en premier)
        size_order = {
            '10001+': 1, '5001-10000': 2, '1001-5000': 3,
            '501-1000': 4, '201-500': 5, '51-200': 6,
            '11-50': 7, '1-10': 8
        }

        result.sort(key=lambda x: size_order.get(x.get('size', ''), 99))

        return result

    def get_enrichment_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques d'enrichissement."""
        stats = {
            'total_companies': 0,
            'with_siren': 0,
            'enriched': 0,
            'to_enrich': 0,
            'by_source': {}
        }

        if not self.company_manager:
            return stats

        companies = self.company_manager.list_all(limit=10000)
        stats['total_companies'] = len(companies)

        for c in companies:
            if c.get('siren'):
                stats['with_siren'] += 1

            if c.get('enriched_at'):
                stats['enriched'] += 1
                source = c.get('enrichment_source', 'unknown')
                stats['by_source'][source] = stats['by_source'].get(source, 0) + 1
            elif c.get('siren'):
                stats['to_enrich'] += 1

        return stats

    def close(self):
        """Ferme les clients."""
        if self._pappers:
            self._pappers.close()
        if self._sirene:
            self._sirene.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
