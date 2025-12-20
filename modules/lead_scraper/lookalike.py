"""
Moteur de recherche lookalike pour trouver des leads similaires.
Analyse un ensemble de leads et génère un profil type pour rechercher des entreprises similaires.
"""
import logging
from typing import List, Dict, Any, Optional
from collections import Counter

logger = logging.getLogger(__name__)


# Mapping régions → départements
REGIONS = {
    "Île-de-France": ["75", "77", "78", "91", "92", "93", "94", "95"],
    "Auvergne-Rhône-Alpes": ["01", "03", "07", "15", "26", "38", "42", "43", "63", "69", "73", "74"],
    "Provence-Alpes-Côte d'Azur": ["04", "05", "06", "13", "83", "84"],
    "Occitanie": ["09", "11", "12", "30", "31", "32", "34", "46", "48", "65", "66", "81", "82"],
    "Nouvelle-Aquitaine": ["16", "17", "19", "23", "24", "33", "40", "47", "64", "79", "86", "87"],
    "Hauts-de-France": ["02", "59", "60", "62", "80"],
    "Normandie": ["14", "27", "50", "61", "76"],
    "Grand Est": ["08", "10", "51", "52", "54", "55", "57", "67", "68", "88"],
    "Pays de la Loire": ["44", "49", "53", "72", "85"],
    "Bretagne": ["22", "29", "35", "56"],
    "Centre-Val de Loire": ["18", "28", "36", "37", "41", "45"],
    "Bourgogne-Franche-Comté": ["21", "25", "39", "58", "70", "71", "89", "90"],
    "Corse": ["2A", "2B"]
}

# Mapping inverse : département → région
DEPT_TO_REGION = {}
for region, depts in REGIONS.items():
    for dept in depts:
        DEPT_TO_REGION[dept] = region


class LookalikeEngine:
    """
    Moteur de génération de profils lookalike.

    Analyse un ensemble de leads et génère un profil type
    permettant de rechercher des entreprises similaires.

    Usage:
        engine = LookalikeEngine()
        profile = engine.build_profile(my_contacts)
        search_params = engine.to_search_params(profile)
    """

    def __init__(self, codes_ape_data: Optional[List[Dict]] = None):
        """
        Initialise le moteur.

        Args:
            codes_ape_data: Liste des codes APE disponibles (pour expansion)
        """
        self.codes_ape_data = codes_ape_data or []

    def build_profile(self, contacts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Construit un profil type à partir d'un ensemble de contacts.

        Args:
            contacts: Liste de contacts à analyser

        Returns:
            Profil type avec critères de recherche
        """
        if not contacts:
            raise ValueError("Liste de contacts vide")

        logger.info(f"Construction du profil lookalike basé sur {len(contacts)} contacts...")

        # Analyser les codes APE
        codes_ape = [c.get("code_ape") for c in contacts if c.get("code_ape")]
        ape_counter = Counter(codes_ape)
        top_ape_codes = [code for code, count in ape_counter.most_common(5)]

        # Analyser les départements/villes
        departements = []
        villes = []
        for contact in contacts:
            ville = contact.get("ville", "")
            code_postal = contact.get("code_postal", "")

            # Extraire département du code postal
            if code_postal:
                dept = code_postal[:2]
                if dept not in departements:
                    departements.append(dept)

            if ville and ville not in villes:
                villes.append(ville)

        # Analyser les effectifs
        effectifs = [
            int(c.get("effectif", 0))
            for c in contacts
            if c.get("effectif") and str(c.get("effectif")).isdigit()
        ]

        if effectifs:
            effectif_min = min(effectifs)
            effectif_max = max(effectifs)
            effectif_median = sorted(effectifs)[len(effectifs) // 2]

            # Ajouter une marge de ±50%
            effectif_min = max(0, int(effectif_min * 0.5))
            effectif_max = int(effectif_max * 1.5)
        else:
            effectif_min = None
            effectif_max = None
            effectif_median = None

        # Construire le profil
        profile = {
            "codes_ape": top_ape_codes,
            "codes_ape_extended": self._expand_ape_codes(top_ape_codes),
            "departements": departements,
            "region_extended": self._expand_regions(departements),
            "villes": villes[:10],  # Top 10 villes
            "effectif_min": effectif_min,
            "effectif_max": effectif_max,
            "effectif_median": effectif_median,
            "num_contacts_analyzed": len(contacts),
            "interpretation": self._build_interpretation(
                top_ape_codes, departements, effectif_min, effectif_max
            )
        }

        logger.info(f"Profil généré: {profile['interpretation']}")

        return profile

    def _expand_ape_codes(self, codes: List[str]) -> List[str]:
        """
        Élargit les codes APE aux codes de la même division.

        Args:
            codes: Liste de codes APE de base

        Returns:
            Liste élargie avec codes voisins
        """
        if not codes:
            return []

        expanded = set(codes)

        # Pour chaque code, ajouter les codes de la même division (2 premiers chars)
        for code in codes:
            if len(code) >= 2:
                division = code[:2]

                # Chercher dans les données de référence
                for ape in self.codes_ape_data:
                    ape_code = ape.get("code", "")
                    if ape_code.startswith(division) and ape_code not in expanded:
                        expanded.add(ape_code)

        return list(expanded)

    def _expand_regions(self, departements: List[str]) -> List[str]:
        """
        Élargit les départements à toute la région.

        Args:
            departements: Liste de départements

        Returns:
            Liste de tous les départements des régions concernées
        """
        if not departements:
            return []

        regions_found = set()

        # Trouver les régions
        for dept in departements:
            region = DEPT_TO_REGION.get(dept)
            if region:
                regions_found.add(region)

        # Récupérer tous les départements de ces régions
        expanded = set()
        for region in regions_found:
            depts = REGIONS.get(region, [])
            expanded.update(depts)

        return list(expanded)

    def _build_interpretation(
        self,
        codes_ape: List[str],
        departements: List[str],
        effectif_min: Optional[int],
        effectif_max: Optional[int]
    ) -> str:
        """
        Génère une interprétation textuelle du profil.

        Args:
            codes_ape: Codes APE principaux
            departements: Départements principaux
            effectif_min: Effectif minimum
            effectif_max: Effectif maximum

        Returns:
            Description textuelle du profil
        """
        parts = []

        # Effectif
        if effectif_min is not None and effectif_max is not None:
            if effectif_max <= 10:
                parts.append("TPE")
            elif effectif_max <= 50:
                parts.append("Petites entreprises")
            elif effectif_max <= 250:
                parts.append("PME")
            else:
                parts.append("Entreprises")

            parts.append(f"({effectif_min}-{effectif_max} employés)")

        # Secteurs
        if codes_ape:
            secteurs_str = ", ".join(codes_ape[:3])
            if len(codes_ape) > 3:
                secteurs_str += "..."
            parts.append(f"secteurs {secteurs_str}")

        # Zones
        if departements:
            # Trouver les régions
            regions = set()
            for dept in departements:
                region = DEPT_TO_REGION.get(dept)
                if region:
                    regions.add(region)

            if regions:
                regions_str = ", ".join(list(regions)[:2])
                if len(regions) > 2:
                    regions_str += "..."
                parts.append(f"en {regions_str}")
            else:
                depts_str = ", ".join(departements[:3])
                if len(departements) > 3:
                    depts_str += "..."
                parts.append(f"depts {depts_str}")

        return " ".join(parts) if parts else "Profil générique"

    def to_search_params(
        self,
        profile: Dict[str, Any],
        options: Optional[Dict[str, bool]] = None
    ) -> Dict[str, Any]:
        """
        Convertit un profil en paramètres de recherche SIRENE.

        Args:
            profile: Profil lookalike
            options: Options d'élargissement
                - extend_ape: utiliser codes APE élargis
                - extend_region: utiliser régions complètes
                - france_entiere: ignorer zone géographique

        Returns:
            Dict de paramètres pour SireneClient.search()
        """
        options = options or {}

        params = {}

        # Codes APE
        if options.get("extend_ape"):
            params["codes_ape"] = profile.get("codes_ape_extended", [])
        else:
            params["codes_ape"] = profile.get("codes_ape", [])

        # Départements
        if options.get("france_entiere"):
            params["departements"] = None
        elif options.get("extend_region"):
            params["departements"] = profile.get("region_extended", [])
        else:
            params["departements"] = profile.get("departements", [])

        # Effectifs (avec marge)
        params["effectif_min"] = profile.get("effectif_min")
        params["effectif_max"] = profile.get("effectif_max")

        # Date de création (optionnel - non utilisé pour lookalike)
        params["date_creation_min"] = None

        return params

    def get_profile_summary(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Génère un résumé du profil pour affichage UI.

        Args:
            profile: Profil lookalike

        Returns:
            Dict avec résumé formaté
        """
        return {
            "interpretation": profile.get("interpretation", ""),
            "secteurs": {
                "base": profile.get("codes_ape", []),
                "elargi": profile.get("codes_ape_extended", []),
                "count_base": len(profile.get("codes_ape", [])),
                "count_elargi": len(profile.get("codes_ape_extended", []))
            },
            "zones": {
                "departements": profile.get("departements", []),
                "region_complete": profile.get("region_extended", []),
                "count_dept": len(profile.get("departements", [])),
                "count_region": len(profile.get("region_extended", []))
            },
            "effectifs": {
                "min": profile.get("effectif_min"),
                "max": profile.get("effectif_max"),
                "median": profile.get("effectif_median")
            },
            "base_contacts": profile.get("num_contacts_analyzed", 0)
        }
