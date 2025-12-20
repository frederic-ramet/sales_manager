"""
Résout un nom d'entreprise ou un domaine email vers un SIREN via l'API SIRENE.
Utilisé pour enrichir les contacts HubSpot qui n'ont pas de SIREN.
"""
import logging
import re
from typing import Optional, List, Dict
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class CompanyResolver:
    """
    Résout company name ou email domain → SIREN via SIRENE (gratuit).

    Stratégies de résolution :
    1. Recherche par nom d'entreprise direct
    2. Recherche par domaine email (extraction + nettoyage)
    3. Sélection du meilleur match par similarité
    """

    def __init__(self, sirene_client):
        """
        Initialise le resolver.

        Args:
            sirene_client: Instance de SireneClient pour les recherches
        """
        self.sirene = sirene_client

        # Extensions à supprimer des domaines
        self.domain_extensions = [
            '.fr', '.com', '.eu', '.net', '.org', '.io', '.co', '.biz'
        ]

        # Suffixes d'entreprise à supprimer
        self.company_suffixes = [
            '-group', '-groupe', '-pro', '-company', '-tech',
            '-digital', '-consulting', '-conseil', '-services'
        ]

    def resolve(
        self,
        company_name: Optional[str] = None,
        email: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Tente de trouver le SIREN d'une entreprise.

        Stratégie :
        1. Si company_name fourni → recherche par nom
        2. Sinon si email fourni → extrait domaine → recherche par nom de domaine
        3. Retourne le meilleur match ou None

        Args:
            company_name: Nom de l'entreprise
            email: Email (pour extraction du domaine)

        Returns:
            Dict avec siren, denomination, adresse, code_ape, effectif
            ou None si non trouvé
        """
        search_term = None

        # Stratégie 1 : Nom d'entreprise
        if company_name and company_name.strip():
            search_term = company_name.strip()
            logger.debug(f"Recherche par nom d'entreprise: {search_term}")

        # Stratégie 2 : Domaine email
        elif email and email.strip():
            domain = self.extract_domain(email)
            if domain:
                search_term = self.domain_to_company_name(domain)
                logger.debug(f"Recherche par domaine email: {email} → {search_term}")

        if not search_term:
            logger.warning("Aucun terme de recherche disponible")
            return None

        # Recherche SIRENE
        try:
            candidates = self.search_by_name(search_term)

            if not candidates:
                logger.debug(f"Aucun résultat pour: {search_term}")
                return None

            # Sélectionner le meilleur match
            best = self.best_match(candidates, search_term)

            if best:
                logger.info(f"✅ SIREN trouvé: {best['siren']} - {best['denomination']}")

            return best

        except Exception as e:
            logger.error(f"Erreur lors de la résolution: {e}")
            return None

    def extract_domain(self, email: str) -> Optional[str]:
        """
        Extrait le domaine d'un email.

        Args:
            email: Email à parser

        Returns:
            Domaine (ex: "ddb.fr") ou None

        Examples:
            >>> extract_domain("fabien@ddb.fr")
            "ddb.fr"
            >>> extract_domain("contact@agence-digitale.com")
            "agence-digitale.com"
        """
        if not email or '@' not in email:
            return None

        try:
            domain = email.split('@')[1].strip().lower()

            # Filtrer les domaines génériques
            generic_domains = [
                'gmail.com', 'yahoo.fr', 'yahoo.com', 'hotmail.com',
                'outlook.com', 'orange.fr', 'free.fr', 'wanadoo.fr',
                'laposte.net', 'sfr.fr', 'live.fr', 'live.com'
            ]

            if domain in generic_domains:
                logger.debug(f"Domaine générique ignoré: {domain}")
                return None

            return domain

        except Exception as e:
            logger.warning(f"Erreur extraction domaine de {email}: {e}")
            return None

    def domain_to_company_name(self, domain: str) -> str:
        """
        Nettoie le domaine pour recherche : ddb.fr → ddb

        Supprime :
        - Extensions (.fr, .com, etc.)
        - Suffixes courants (-pro, -group, etc.)
        - Caractères spéciaux

        Args:
            domain: Domaine à nettoyer

        Returns:
            Nom nettoyé pour recherche

        Examples:
            >>> domain_to_company_name("ddb.fr")
            "ddb"
            >>> domain_to_company_name("agence-digital-pro.com")
            "agence digital"
        """
        name = domain.lower()

        # Supprimer les extensions
        for ext in self.domain_extensions:
            if name.endswith(ext):
                name = name[:-len(ext)]
                break

        # Supprimer les suffixes
        for suffix in self.company_suffixes:
            if name.endswith(suffix):
                name = name[:-len(suffix)]

        # Remplacer tirets et underscores par espaces
        name = name.replace('-', ' ').replace('_', ' ')

        # Nettoyer espaces multiples
        name = ' '.join(name.split())

        return name.strip()

    def search_by_name(self, name: str, max_results: int = 10) -> List[Dict]:
        """
        Recherche SIRENE par nom.

        Args:
            name: Nom à rechercher
            max_results: Nombre max de résultats

        Returns:
            Liste de candidats trouvés
        """
        try:
            # Utiliser la recherche textuelle de SIRENE
            results = self.sirene.search_companies(
                q=name,
                max_results=max_results
            )

            logger.debug(f"Recherche '{name}': {len(results)} résultats")
            return results

        except Exception as e:
            logger.error(f"Erreur recherche SIRENE pour '{name}': {e}")
            return []

    def best_match(
        self,
        candidates: List[Dict],
        reference: str
    ) -> Optional[Dict]:
        """
        Sélectionne le meilleur match parmi les candidats.

        Utilise la similarité de chaînes (SequenceMatcher) pour comparer
        le nom de référence avec les dénominations des candidats.

        Args:
            candidates: Liste de résultats SIRENE
            reference: Nom de référence pour comparaison

        Returns:
            Meilleur candidat ou None
        """
        if not candidates:
            return None

        reference_clean = self._normalize_for_comparison(reference)

        best_candidate = None
        best_score = 0.0

        for candidate in candidates:
            denomination = candidate.get('denomination', '')
            denomination_clean = self._normalize_for_comparison(denomination)

            # Calculer similarité
            score = SequenceMatcher(
                None,
                reference_clean,
                denomination_clean
            ).ratio()

            logger.debug(f"Similarité: {score:.2f} - {denomination}")

            if score > best_score:
                best_score = score
                best_candidate = candidate

        # Seuil de confiance : 0.6 (60% de similarité minimum)
        if best_score >= 0.6:
            logger.info(f"Meilleur match (score: {best_score:.2f}): {best_candidate.get('denomination')}")
            return best_candidate
        else:
            logger.warning(f"Aucun match confiant (meilleur score: {best_score:.2f})")
            return None

    def _normalize_for_comparison(self, text: str) -> str:
        """
        Normalise un texte pour comparaison.

        - Minuscules
        - Supprime ponctuation
        - Supprime mots courants (SA, SAS, SARL, etc.)

        Args:
            text: Texte à normaliser

        Returns:
            Texte normalisé
        """
        if not text:
            return ""

        text = text.lower()

        # Supprimer formes juridiques
        legal_forms = [
            ' sa ', ' sas ', ' sarl ', ' sasu ', ' eurl ',
            ' sci ', ' scop ', ' association ', ' asso '
        ]
        for form in legal_forms:
            text = text.replace(form, ' ')

        # Supprimer ponctuation
        text = re.sub(r'[^\w\s]', ' ', text)

        # Nettoyer espaces multiples
        text = ' '.join(text.split())

        return text.strip()
