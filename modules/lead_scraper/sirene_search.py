"""
SIRENE Search V2 - Recherche et import d'entreprises depuis SIRENE.

API: https://recherche-entreprises.api.gouv.fr (gratuite, sans clé)

Usage:
    searcher = SireneSearch(company_manager)

    # Recherche
    results = searcher.search(
        query="ESN",
        code_postal="69000",
        effectif="50-99"
    )

    # Import sélection
    report = searcher.import_companies(results[:10])
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None

logger = logging.getLogger(__name__)


class SireneSearch:
    """
    Recherche et import depuis l'API SIRENE.

    API gratuite du gouvernement français.
    Documentation: https://api.gouv.fr/documentation/api-recherche-entreprises
    """

    BASE_URL = "https://recherche-entreprises.api.gouv.fr"

    # Mapping tranches effectif SIRENE → format V2
    EFFECTIF_MAPPING = {
        '00': '0',           # 0 salarié
        '01': '1-10',        # 1 ou 2
        '02': '1-10',        # 3 à 5
        '03': '1-10',        # 6 à 9
        '11': '11-50',       # 10 à 19
        '12': '11-50',       # 20 à 49
        '21': '51-200',      # 50 à 99
        '22': '51-200',      # 100 à 199
        '31': '201-500',     # 200 à 249
        '32': '201-500',     # 250 à 499
        '41': '501-1000',    # 500 à 999
        '42': '1001-5000',   # 1000 à 1999
        '51': '1001-5000',   # 2000 à 4999
        '52': '5001-10000',  # 5000 à 9999
        '53': '10001+',      # 10000 et plus
    }

    def __init__(self, company_manager=None):
        self.company_manager = company_manager
        self._client = None

    def _get_client(self):
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx non installé")
        if not self._client:
            self._client = httpx.Client(timeout=30.0)
        return self._client

    def search(
        self,
        query: str = None,
        code_postal: str = None,
        departement: str = None,
        region: str = None,
        code_naf: str = None,
        section_naf: str = None,
        tranche_effectif: str = None,
        nature_juridique: str = None,
        est_entrepreneur_individuel: bool = None,
        page: int = 1,
        per_page: int = 25
    ) -> Dict[str, Any]:
        """
        Recherche des entreprises dans SIRENE.

        Args:
            query: Texte libre (nom, SIREN, SIRET)
            code_postal: Code postal (ex: "75001", "69*" pour tout le Rhône)
            departement: Code département (ex: "69", "75")
            region: Code région INSEE
            code_naf: Code NAF/APE (ex: "6201Z")
            section_naf: Section NAF (ex: "J" pour Information/Communication)
            tranche_effectif: Tranche effectif (ex: "22" pour 100-199)
            nature_juridique: Code juridique (ex: "5710" pour SAS)
            est_entrepreneur_individuel: True/False
            page: Numéro de page (1-based)
            per_page: Résultats par page (max 25)

        Returns:
            {
                'total': int,
                'page': int,
                'per_page': int,
                'results': [...]
            }
        """
        params = {
            'page': page,
            'per_page': min(per_page, 25)  # API limite à 25
        }

        if query:
            params['q'] = query
        if code_postal:
            params['code_postal'] = code_postal
        if departement:
            params['departement'] = departement
        if region:
            params['region'] = region
        if code_naf:
            params['activite_principale'] = code_naf
        if section_naf:
            params['section_activite_principale'] = section_naf
        if tranche_effectif:
            params['tranche_effectif_salarie'] = tranche_effectif
        if nature_juridique:
            params['nature_juridique'] = nature_juridique
        if est_entrepreneur_individuel is not None:
            params['est_entrepreneur_individuel'] = str(est_entrepreneur_individuel).lower()

        try:
            response = self._get_client().get(
                f"{self.BASE_URL}/search",
                params=params
            )

            if response.status_code == 200:
                data = response.json()

                # Mapper les résultats
                results = []
                for item in data.get('results', []):
                    results.append(self._map_result(item))

                return {
                    'total': data.get('total_results', 0),
                    'page': data.get('page', page),
                    'per_page': data.get('per_page', per_page),
                    'results': results
                }
            else:
                logger.error(f"Erreur API SIRENE: {response.status_code}")
                return {'total': 0, 'page': 1, 'per_page': per_page, 'results': [], 'error': response.text}

        except Exception as e:
            logger.error(f"Erreur recherche SIRENE: {e}")
            return {'total': 0, 'page': 1, 'per_page': per_page, 'results': [], 'error': str(e)}

    def _map_result(self, item: Dict) -> Dict[str, Any]:
        """Mappe un résultat SIRENE vers notre format."""
        siege = item.get('siege', {}) or {}

        # Extraire le nom
        name = item.get('nom_complet') or item.get('nom_raison_sociale') or ''

        # Taille
        tranche = item.get('tranche_effectif_salarie') or ''
        size = self.EFFECTIF_MAPPING.get(tranche, tranche)

        return {
            'siren': item.get('siren'),
            'siret': siege.get('siret'),
            'name': name,
            'legal_form': item.get('nature_juridique'),
            'ape_code': item.get('activite_principale'),
            'ape_label': item.get('libelle_activite_principale'),
            'size': size,
            'size_label': item.get('tranche_effectif_salarie_intitule'),
            'hq_address': siege.get('adresse'),
            'hq_city': siege.get('commune'),
            'hq_postal_code': siege.get('code_postal'),
            'hq_state': siege.get('departement'),
            'hq_country': 'France',
            'founded_date': item.get('date_creation'),
            'is_active': item.get('etat_administratif') == 'A',
            # Données brutes pour debug
            '_raw': item
        }

    def search_by_siren(self, siren: str) -> Optional[Dict]:
        """Recherche une entreprise par SIREN."""
        results = self.search(query=siren, per_page=1)
        if results.get('results'):
            return results['results'][0]
        return None

    def search_by_name(
        self,
        name: str,
        city: str = None,
        limit: int = 10
    ) -> List[Dict]:
        """Recherche par nom d'entreprise."""
        query = name
        code_postal = None

        if city:
            # Essayer de déduire le code postal
            # TODO: améliorer avec une API de géocodage
            pass

        results = self.search(query=query, code_postal=code_postal, per_page=min(limit, 25))
        return results.get('results', [])

    def import_companies(
        self,
        companies: List[Dict],
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Importe une liste d'entreprises SIRENE dans la base locale.

        Args:
            companies: Liste de résultats de recherche SIRENE
            progress_callback: Callback(current, total)

        Returns:
            Rapport d'import
        """
        report = {
            'success': True,
            'created': 0,
            'matched': 0,
            'skipped': 0,
            'errors': []
        }

        if not self.company_manager:
            report['success'] = False
            report['errors'].append('CompanyManager non initialisé')
            return report

        for i, company in enumerate(companies):
            if progress_callback:
                progress_callback(i + 1, len(companies))

            try:
                # Vérifier si actif
                if not company.get('is_active', True):
                    report['skipped'] += 1
                    continue

                siren = company.get('siren')
                if not siren:
                    report['skipped'] += 1
                    continue

                # Chercher existant par SIREN
                existing = self.company_manager.find_by_siren(siren)

                if existing:
                    report['matched'] += 1
                    continue

                # Créer l'entreprise
                company_data = {
                    'siren': siren,
                    'siret': company.get('siret'),
                    'name': company.get('name'),
                    'legal_form': company.get('legal_form'),
                    'ape_code': company.get('ape_code'),
                    'ape_label': company.get('ape_label'),
                    'size': company.get('size'),
                    'hq_address': company.get('hq_address'),
                    'hq_city': company.get('hq_city'),
                    'hq_postal_code': company.get('hq_postal_code'),
                    'hq_state': company.get('hq_state'),
                    'hq_country': 'France',
                    'founded_date': company.get('founded_date'),
                    'source': 'sirene',
                    'enriched_at': datetime.now(),
                    'enrichment_source': 'sirene'
                }

                self.company_manager.create(company_data)
                report['created'] += 1

            except Exception as e:
                report['errors'].append(f"{company.get('name', 'Unknown')}: {e}")

        return report

    def get_naf_sections(self) -> Dict[str, str]:
        """Retourne les sections NAF pour les filtres."""
        return {
            'A': 'Agriculture, sylviculture et pêche',
            'B': 'Industries extractives',
            'C': 'Industrie manufacturière',
            'D': 'Production et distribution d\'électricité, de gaz, de vapeur et d\'air conditionné',
            'E': 'Production et distribution d\'eau; assainissement, gestion des déchets et dépollution',
            'F': 'Construction',
            'G': 'Commerce; réparation d\'automobiles et de motocycles',
            'H': 'Transports et entreposage',
            'I': 'Hébergement et restauration',
            'J': 'Information et communication',
            'K': 'Activités financières et d\'assurance',
            'L': 'Activités immobilières',
            'M': 'Activités spécialisées, scientifiques et techniques',
            'N': 'Activités de services administratifs et de soutien',
            'O': 'Administration publique',
            'P': 'Enseignement',
            'Q': 'Santé humaine et action sociale',
            'R': 'Arts, spectacles et activités récréatives',
            'S': 'Autres activités de services',
            'T': 'Activités des ménages',
            'U': 'Activités extra-territoriales',
        }

    def get_effectif_tranches(self) -> Dict[str, str]:
        """Retourne les tranches d'effectif pour les filtres."""
        return {
            '00': '0 salarié',
            '01': '1 à 2 salariés',
            '02': '3 à 5 salariés',
            '03': '6 à 9 salariés',
            '11': '10 à 19 salariés',
            '12': '20 à 49 salariés',
            '21': '50 à 99 salariés',
            '22': '100 à 199 salariés',
            '31': '200 à 249 salariés',
            '32': '250 à 499 salariés',
            '41': '500 à 999 salariés',
            '42': '1 000 à 1 999 salariés',
            '51': '2 000 à 4 999 salariés',
            '52': '5 000 à 9 999 salariés',
            '53': '10 000 salariés et plus',
        }

    def close(self):
        if self._client:
            self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
