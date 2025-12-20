"""
Module de parsing de requêtes en langage naturel via Claude API.
Transforme des requêtes comme "PME -50 dans la publicité à Paris"
en filtres structurés (codes APE, effectifs, départements).
"""
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

import anthropic

from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL

logger = logging.getLogger(__name__)


class QueryParser:
    """
    Parser de requêtes en langage naturel pour extraction de leads.
    Utilise Claude API pour interpréter les intentions et extraire les filtres.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        codes_ape: Optional[List[Dict[str, str]]] = None,
        departements: Optional[List[Dict[str, str]]] = None
    ):
        """
        Initialise le parser.

        Args:
            api_key: Clé API Anthropic (optionnel, utilise config par défaut)
            model: Modèle à utiliser (optionnel, utilise config par défaut)
            codes_ape: Liste des codes APE disponibles
            departements: Liste des départements disponibles
        """
        self.api_key = api_key or ANTHROPIC_API_KEY
        self.model = model or ANTHROPIC_MODEL
        self.codes_ape = codes_ape or []
        self.departements = departements or []

        if not self.api_key or self.api_key == "your_anthropic_api_key_here":
            raise ValueError(
                "Clé API Anthropic non configurée. "
                "Configurez ANTHROPIC_API_KEY dans .env ou passez api_key au constructeur."
            )

        self.client = anthropic.Anthropic(api_key=self.api_key)

    def _build_prompt(self, query: str) -> str:
        """
        Construit le prompt pour Claude avec le contexte des référentiels.

        Args:
            query: Requête de l'utilisateur en langage naturel

        Returns:
            Prompt formaté
        """
        # Formater les codes APE pour le contexte
        ape_context = "\n".join([
            f"- {item['code']}: {item['label']}"
            for item in self.codes_ape[:30]  # Limiter pour ne pas surcharger
        ])

        # Zones géographiques communes
        zones = {
            "Île-de-France": "75,77,78,91,92,93,94,95",
            "PACA": "04,05,06,13,83,84",
            "Auvergne-Rhône-Alpes": "01,03,07,15,26,38,42,43,63,69,73,74",
            "Occitanie": "09,11,12,30,31,32,34,46,48,65,66,81,82",
            "Nouvelle-Aquitaine": "16,17,19,23,24,33,40,47,64,79,86,87"
        }

        zones_context = "\n".join([
            f"- {region}: départements {depts}"
            for region, depts in zones.items()
        ])

        return f"""Tu es un assistant spécialisé dans l'extraction de critères de recherche d'entreprises françaises.

L'utilisateur va formuler une requête en langage naturel. Tu dois extraire les filtres suivants :

**Codes APE disponibles (secteurs d'activité) :**
{ape_context}

**Zones géographiques courantes :**
{zones_context}

**Départements français :**
- Paris: 75, Lyon: 69, Marseille: 13, Bordeaux: 33, Toulouse: 31, etc.
- Départements d'outre-mer: 971 (Guadeloupe), 972 (Martinique), 973 (Guyane), 974 (Réunion), 976 (Mayotte)

**Tailles d'entreprise (effectifs) :**
- TPE: 0-9 employés
- PME: 10-249 employés
- ETI: 250-4999 employés
- GE: 5000+ employés

**Requête de l'utilisateur :**
"{query}"

**Instructions :**
1. Identifie le secteur d'activité et trouve les codes APE correspondants
2. Identifie la zone géographique (départements ou régions)
3. Identifie la taille d'entreprise (effectif min/max)
4. Identifie la date de création si mentionnée

Réponds UNIQUEMENT avec un JSON valide suivant ce format :

{{
  "codes_ape": ["62.01Z", "62.02A"],
  "departements": ["75", "92"],
  "effectif_min": 10,
  "effectif_max": 50,
  "date_creation_min": "2020-01-01",
  "interpretation": "PME (10-50 employés) dans le développement informatique à Paris et Hauts-de-Seine"
}}

Si tu n'es pas sûr d'un champ, omets-le (ne mets pas null).
Si plusieurs codes APE correspondent au secteur, inclus-les tous.

Réponds UNIQUEMENT avec le JSON, sans markdown ni texte additionnel."""

    def parse(self, query: str) -> Dict[str, Any]:
        """
        Parse une requête en langage naturel et extrait les filtres.

        Args:
            query: Requête de l'utilisateur (ex: "PME -50 dans la publicité à Paris")

        Returns:
            Dict avec les filtres extraits:
            {
                "codes_ape": ["73.11Z", "73.12Z"],
                "departements": ["75"],
                "effectif_min": 1,
                "effectif_max": 50,
                "date_creation_min": "2020-01-01",
                "interpretation": "Description lisible des filtres"
            }

        Raises:
            ValueError: Si la requête ne peut pas être parsée
            anthropic.APIError: Si l'appel API échoue
        """
        if not query or not query.strip():
            raise ValueError("La requête ne peut pas être vide")

        logger.info(f"Parsing de la requête: '{query}'")

        try:
            # Construire le prompt
            prompt = self._build_prompt(query)

            # Appeler Claude API
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Extraire le texte de la réponse
            response_text = message.content[0].text.strip()
            logger.debug(f"Réponse Claude: {response_text}")

            # Parser le JSON
            # Nettoyer les éventuels backticks markdown
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            filters = json.loads(response_text)

            # Valider la structure
            self._validate_filters(filters)

            logger.info(f"Filtres extraits: {filters.get('interpretation', filters)}")

            return filters

        except json.JSONDecodeError as e:
            logger.error(f"Erreur de parsing JSON: {e}")
            raise ValueError(f"Impossible de parser la réponse de Claude: {e}")

        except anthropic.APIError as e:
            logger.error(f"Erreur API Anthropic: {e}")
            raise

        except Exception as e:
            logger.error(f"Erreur inattendue lors du parsing: {e}")
            raise ValueError(f"Erreur lors du parsing de la requête: {e}")

    def _validate_filters(self, filters: Dict[str, Any]) -> None:
        """
        Valide la structure des filtres extraits.

        Args:
            filters: Dictionnaire de filtres à valider

        Raises:
            ValueError: Si les filtres sont invalides
        """
        # Vérifier que c'est bien un dict
        if not isinstance(filters, dict):
            raise ValueError("Les filtres doivent être un dictionnaire")

        # Valider codes_ape
        if "codes_ape" in filters:
            if not isinstance(filters["codes_ape"], list):
                raise ValueError("codes_ape doit être une liste")
            # Vérifier le format (XX.XXX)
            for code in filters["codes_ape"]:
                if not isinstance(code, str) or not code:
                    raise ValueError(f"Code APE invalide: {code}")

        # Valider departements
        if "departements" in filters:
            if not isinstance(filters["departements"], list):
                raise ValueError("departements doit être une liste")
            for dept in filters["departements"]:
                if not isinstance(dept, str) or not dept:
                    raise ValueError(f"Département invalide: {dept}")

        # Valider effectifs
        if "effectif_min" in filters:
            if not isinstance(filters["effectif_min"], int) or filters["effectif_min"] < 0:
                raise ValueError("effectif_min doit être un entier >= 0")

        if "effectif_max" in filters:
            if not isinstance(filters["effectif_max"], int) or filters["effectif_max"] < 0:
                raise ValueError("effectif_max doit être un entier >= 0")

        # Valider date
        if "date_creation_min" in filters:
            try:
                datetime.strptime(filters["date_creation_min"], "%Y-%m-%d")
            except ValueError:
                raise ValueError("date_creation_min doit être au format YYYY-MM-DD")

        logger.debug("Filtres validés avec succès")
