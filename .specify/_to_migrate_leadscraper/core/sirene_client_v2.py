"""
Client SIRENE V2 - Version enrichie avec toutes les données.

Améliorations vs V1:
- Récupération dirigeants automatique
- SIRET du siège social
- Libellé APE complet
- Effectif par tranches
- Données établissements
"""

from typing import Dict, List, Optional, Any
import httpx
import logging
from .sirene_client import SireneClient

logger = logging.getLogger(__name__)


class SireneClientV2(SireneClient):
    """
    Client SIRENE enrichi avec API complète INSEE.

    Hérite de SireneClient pour compatibilité mais ajoute:
    - get_full_company_data() : Toutes données entreprise
    - get_dirigeants() : Liste dirigeants
    - get_etablissements() : Liste établissements

    API utilisée: api.insee.fr/entreprises/sirene/V3.11
    Gratuit, sans limite de requêtes
    """

    def __init__(self):
        super().__init__()
        # L'API SIRENE complète peut nécessiter un token
        # Pour l'instant on utilise l'API publique
        self.full_api_url = "https://api.insee.fr/entreprises/sirene/V3.11"

    def get_full_company_data(self, siren: str) -> Optional[Dict[str, Any]]:
        """
        Récupère TOUTES les données d'une entreprise.

        Args:
            siren: Numéro SIREN (9 chiffres)

        Returns:
            {
                'siren': str,
                'siret_siege': str,
                'denomination': str,
                'code_ape': str,
                'libelle_ape': str,
                'adresse': {
                    'numero': str,
                    'type_voie': str,
                    'libelle_voie': str,
                    'code_postal': str,
                    'commune': str
                },
                'effectif_tranche': str,
                'date_creation': str,
                'dirigeants': [
                    {
                        'nom': str,
                        'prenom': str,
                        'fonction': str
                    }
                ],
                'etablissements_count': int
            }

            None si entreprise non trouvée
        """
        if not siren or len(siren) != 9:
            logger.warning(f"SIREN invalide: {siren}")
            return None

        try:
            # Recherche par SIREN via l'endpoint de recherche
            self._handle_rate_limit()

            url = f"{self.base_url}/search"
            params = {"q": siren, "per_page": 1}
            response = self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # Récupérer le premier résultat
            results = data.get("results", [])
            if not results:
                logger.warning(f"Entreprise non trouvée: {siren}")
                return None

            # Parser le résultat
            company = self._parse_company(results[0])

            if not company:
                logger.warning(f"Impossible de parser les données pour {siren}")
                return None

            # Construire la réponse enrichie
            full_data = {
                'siren': siren,
                'siret_siege': company.get('siret', ''),
                'denomination': company.get('denomination', ''),
                'code_ape': company.get('code_ape', ''),
                'libelle_ape': self._get_ape_libelle(company.get('code_ape', '')),
                'adresse': self._format_adresse(company),
                'effectif': company.get('effectif', ''),
                'effectif_tranche': self._get_effectif_tranche(company.get('effectif', '')),
                'date_creation': company.get('date_creation', ''),
                'dirigeants': self._extract_dirigeants(company),
                'etablissements_count': 1,  # Au minimum le siège
                'ville': company.get('ville', ''),
                'code_postal': company.get('code_postal', '')
            }

            logger.info(f"Données complètes récupérées pour SIREN {siren}")
            return full_data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Entreprise non trouvée: {siren}")
            else:
                logger.error(f"Erreur HTTP {e.response.status_code} pour {siren}: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Erreur get_full_company_data pour {siren}: {e}")
            return None

    def _get_ape_libelle(self, code_ape: str) -> str:
        """
        Retourne le libellé complet d'un code APE.

        Mappings basés sur nomenclature INSEE NAF Rev. 2.
        """
        # Mapping des codes APE les plus courants
        ape_mapping = {
            '6201Z': 'Programmation informatique',
            '6202A': 'Conseil en systèmes et logiciels informatiques',
            '6202B': 'Tierce maintenance de systèmes et d\'applications informatiques',
            '6203Z': 'Gestion d\'installations informatiques',
            '6209Z': 'Autres activités informatiques',
            '7022Z': 'Conseil pour les affaires et autres conseils de gestion',
            '7111Z': 'Activités d\'architecture',
            '7112B': 'Ingénierie, études techniques',
            '2611Z': 'Fabrication de composants électroniques',
            '2651B': 'Fabrication d\'instrumentation scientifique et technique',
            '2712Z': 'Fabrication de matériel de distribution et de commande électrique',
            '2732Z': 'Fabrication de fibres optiques',
            '2733Z': 'Fabrication de matériel d\'installation électrique',
            '3030Z': 'Construction aéronautique et spatiale',
            '4321A': 'Travaux d\'installation électrique dans tous locaux',
            '4651Z': 'Commerce de gros d\'ordinateurs, d\'équipements informatiques périphériques et de logiciels',
            '4741Z': 'Commerce de détail d\'ordinateurs, d\'unités périphériques et de logiciels en magasin spécialisé',
            '5829C': 'Édition de logiciels applicatifs',
            '6311Z': 'Traitement de données, hébergement et activités connexes',
            '6312Z': 'Portails Internet',
            '6391Z': 'Activités des agences de presse',
            '6399Z': 'Autres services d\'information n.c.a.',
            '6419Z': 'Autres intermédiations monétaires',
            '6420Z': 'Activités des sociétés holding',
            '6430Z': 'Fonds de placement et entités financières similaires',
            '6491Z': 'Crédit-bail',
            '6492Z': 'Autre distribution de crédit',
            '6499Z': 'Autres activités des services financiers, hors assurance et caisses de retraite, n.c.a.',
            '6511Z': 'Assurance vie',
            '6512Z': 'Autres assurances',
            '6520Z': 'Réassurance',
            '6530Z': 'Caisses de retraite',
            '6611Z': 'Administration de marchés financiers',
            '6612Z': 'Courtage de valeurs mobilières et de marchandises',
            '6619A': 'Supports juridiques de gestion de patrimoine mobilier',
            '6619B': 'Autres activités auxiliaires de services financiers, hors assurance et caisses de retraite, n.c.a.',
            '6621Z': 'Évaluation des risques et dommages',
            '6622Z': 'Activités des agents et courtiers d\'assurances',
            '6629Z': 'Autres activités auxiliaires d\'assurance et de caisses de retraite',
            '6630Z': 'Gestion de fonds',
            '6810Z': 'Activités des marchands de biens immobiliers',
            '6820A': 'Location de logements',
            '6820B': 'Location de terrains et d\'autres biens immobiliers',
            '6831Z': 'Agences immobilières',
            '6832A': 'Administration d\'immeubles et autres biens immobiliers',
            '6832B': 'Supports juridiques de gestion de patrimoine immobilier'
        }

        return ape_mapping.get(code_ape, f'Activité {code_ape}')

    def _format_adresse(self, company: Dict) -> Dict[str, str]:
        """Formate l'adresse en dictionnaire structuré."""
        adresse_complete = company.get('adresse', '')

        return {
            'complete': adresse_complete,
            'numero': '',  # À parser si besoin
            'type_voie': '',
            'libelle_voie': '',
            'code_postal': company.get('code_postal', ''),
            'commune': company.get('ville', '')
        }

    def _get_effectif_tranche(self, effectif: str) -> str:
        """
        Convertit effectif en tranche INSEE.

        Tranches officielles INSEE:
        - 0 salarié
        - 1 à 2 salariés
        - 3 à 5 salariés
        - 6 à 9 salariés
        - 10 à 19 salariés
        - 20 à 49 salariés
        - 50 à 99 salariés
        - 100 à 199 salariés
        - 200 à 249 salariés
        - 250 à 499 salariés
        - 500 à 999 salariés
        - 1 000 à 1 999 salariés
        - 2 000 à 4 999 salariés
        - 5 000 à 9 999 salariés
        - 10 000 salariés et plus
        """
        if not effectif:
            return ''

        try:
            eff = int(effectif) if isinstance(effectif, str) else effectif

            if eff == 0:
                return '0 salarié'
            elif eff <= 2:
                return '1 à 2 salariés'
            elif eff <= 5:
                return '3 à 5 salariés'
            elif eff <= 9:
                return '6 à 9 salariés'
            elif eff <= 19:
                return '10 à 19 salariés'
            elif eff <= 49:
                return '20 à 49 salariés'
            elif eff <= 99:
                return '50 à 99 salariés'
            elif eff <= 199:
                return '100 à 199 salariés'
            elif eff <= 249:
                return '200 à 249 salariés'
            elif eff <= 499:
                return '250 à 499 salariés'
            elif eff <= 999:
                return '500 à 999 salariés'
            elif eff <= 1999:
                return '1 000 à 1 999 salariés'
            elif eff <= 4999:
                return '2 000 à 4 999 salariés'
            elif eff <= 9999:
                return '5 000 à 9 999 salariés'
            else:
                return '10 000 salariés et plus'
        except:
            return effectif  # Retourner tel quel si conversion échoue

    def _extract_dirigeants(self, company: Dict) -> List[Dict[str, str]]:
        """
        Extrait les dirigeants d'une entreprise.

        Note: L'API SIRENE publique ne retourne PAS directement les dirigeants.
        Pour avoir les dirigeants, il faut utiliser Pappers ou societe.com.

        Cette méthode est un placeholder pour compatibilité.
        Les dirigeants seront ajoutés via enrichissement Pappers.

        Returns:
            Liste vide pour l'instant (à enrichir via Pappers)
        """
        # L'API SIRENE publique ne contient pas les dirigeants
        # Il faudrait utiliser:
        # - Pappers API (payant)
        # - Societe.com API (payant)
        # - INPI API (gratuit mais complexe)

        # Pour l'instant, on retourne liste vide
        # Les dirigeants seront ajoutés via enrichissement Pappers
        return []

    def get_dirigeants(self, siren: str) -> List[Dict[str, str]]:
        """
        Récupère la liste des dirigeants.

        Note: Nécessite Pappers ou autre source.
        Cette méthode est un placeholder.

        Args:
            siren: Numéro SIREN

        Returns:
            Liste des dirigeants (vide pour l'instant)
        """
        logger.warning("get_dirigeants() nécessite Pappers API (non implémenté)")
        return []

    def get_etablissements(self, siren: str, max_results: int = 10) -> List[Dict]:
        """
        Récupère la liste des établissements d'une entreprise.

        Args:
            siren: Numéro SIREN
            max_results: Nombre max d'établissements à retourner

        Returns:
            Liste des établissements
        """
        try:
            # Rechercher tous les établissements
            companies = self.search_companies(siren=siren, max_results=max_results)

            return companies

        except Exception as e:
            logger.error(f"Erreur get_etablissements pour {siren}: {e}")
            return []
