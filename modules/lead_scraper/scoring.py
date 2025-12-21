"""
Module de scoring et qualification automatique des leads.

Contient 2 systèmes de scoring distincts:

1. ProspectClassifier (A/B/C) - Classification ICP
   - Utilisé AVANT contact pour prioriser les entreprises à prospecter
   - Basé sur critères métier: effectif, CA, secteur, géographie

2. LeadScorer (Hot/Warm/Cold) - Qualification leads
   - Utilisé APRÈS contact pour qualifier les leads
   - Basé sur complétude et engagement: email, téléphone, dirigeant
"""
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Chemin vers les fichiers de config
CONFIG_PATH = Path(__file__).parent.parent.parent / "data"


class LeadScorer:
    """
    Calcule un score de qualité pour chaque lead.

    Score sur 100 points basé sur :
    - Complétude des données (présence des champs clés)
    - Qualité des données (email direct > email générique, etc.)
    - Pertinence business (CA, effectif, secteur prioritaire)

    Usage:
        scorer = LeadScorer()
        scored_leads = scorer.score_batch(leads)
        segments = scorer.segment_leads(scored_leads)
    """

    # Pondération des critères (total = 100 points)
    WEIGHTS = {
        # Données de contact (40 points)
        'email_direct': 15,  # Email direct (non gmail/yahoo)
        'telephone_direct': 15,  # Téléphone direct
        'dirigeant': 10,  # Nom du dirigeant

        # Données entreprise (35 points)
        'siren': 10,  # SIREN présent
        'code_ape': 5,  # Code APE
        'ville': 5,  # Localisation
        'effectif': 10,  # Effectif renseigné
        'chiffre_affaires': 5,  # CA renseigné

        # Bonus pertinence (25 points)
        'effectif_cible': 10,  # Effectif dans plage cible (10-50)
        'ca_significatif': 10,  # CA > 1M€
        'secteur_prioritaire': 5,  # Secteur B2B prioritaire
    }

    # Domaines email génériques (score réduit)
    GENERIC_DOMAINS = [
        'gmail.com', 'yahoo.fr', 'yahoo.com', 'hotmail.com',
        'outlook.com', 'orange.fr', 'free.fr', 'wanadoo.fr',
        'laposte.net', 'sfr.fr', 'live.fr', 'live.com'
    ]

    # Codes APE B2B prioritaires
    PRIORITY_APE_CODES = [
        '6201Z', '6202A', '6202B', '6203Z', '6209Z',  # Info/Dev
        '7021Z', '7022Z',  # Conseil
        '7311Z', '7312Z', '7320Z',  # Publicité
        '6920Z', '6910Z',  # Juridique/Compta
        '7111Z', '7112B',  # Architecture/Ing
    ]

    def score_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calcule le score d'un lead.

        Args:
            lead: Dict avec les données du lead

        Returns:
            Dict avec score, category, breakdown
        """
        score = 0
        breakdown = {}

        # 1. Email direct
        email = lead.get('email', '')
        if email:
            domain = email.split('@')[1] if '@' in email else ''
            if domain and domain not in self.GENERIC_DOMAINS:
                score += self.WEIGHTS['email_direct']
                breakdown['email_direct'] = self.WEIGHTS['email_direct']
            else:
                # Email générique = demi-points
                score += self.WEIGHTS['email_direct'] // 2
                breakdown['email_direct'] = self.WEIGHTS['email_direct'] // 2

        # 2. Téléphone direct
        if lead.get('telephone'):
            score += self.WEIGHTS['telephone_direct']
            breakdown['telephone_direct'] = self.WEIGHTS['telephone_direct']

        # 3. Dirigeant
        if lead.get('dirigeant'):
            score += self.WEIGHTS['dirigeant']
            breakdown['dirigeant'] = self.WEIGHTS['dirigeant']

        # 4. SIREN
        if lead.get('siren'):
            score += self.WEIGHTS['siren']
            breakdown['siren'] = self.WEIGHTS['siren']

        # 5. Code APE
        if lead.get('code_ape'):
            score += self.WEIGHTS['code_ape']
            breakdown['code_ape'] = self.WEIGHTS['code_ape']

        # 6. Ville
        if lead.get('ville'):
            score += self.WEIGHTS['ville']
            breakdown['ville'] = self.WEIGHTS['ville']

        # 7. Effectif
        if lead.get('effectif'):
            score += self.WEIGHTS['effectif']
            breakdown['effectif'] = self.WEIGHTS['effectif']

        # 8. Chiffre d'affaires
        if lead.get('chiffre_affaires'):
            score += self.WEIGHTS['chiffre_affaires']
            breakdown['chiffre_affaires'] = self.WEIGHTS['chiffre_affaires']

        # BONUS 9. Effectif cible (10-50 employés)
        effectif = lead.get('effectif')
        if effectif:
            try:
                effectif_num = int(str(effectif).replace('+', '').replace(' ', ''))
                if 10 <= effectif_num <= 50:
                    score += self.WEIGHTS['effectif_cible']
                    breakdown['effectif_cible'] = self.WEIGHTS['effectif_cible']
            except (ValueError, TypeError):
                pass

        # BONUS 10. CA significatif (> 1M€)
        ca = lead.get('chiffre_affaires')
        if ca:
            try:
                ca_num = float(str(ca).replace(' ', '').replace('€', '').replace(',', '.'))
                if ca_num > 1000000:
                    score += self.WEIGHTS['ca_significatif']
                    breakdown['ca_significatif'] = self.WEIGHTS['ca_significatif']
            except (ValueError, TypeError):
                pass

        # BONUS 11. Secteur prioritaire
        code_ape = lead.get('code_ape', '')
        if code_ape in self.PRIORITY_APE_CODES:
            score += self.WEIGHTS['secteur_prioritaire']
            breakdown['secteur_prioritaire'] = self.WEIGHTS['secteur_prioritaire']

        # Catégorisation
        if score >= 70:
            category = "Hot"
            color = "red"
        elif score >= 50:
            category = "Warm"
            color = "orange"
        elif score >= 30:
            category = "Cold"
            color = "blue"
        else:
            category = "Frozen"
            color = "gray"

        return {
            "score": score,
            "category": category,
            "color": color,
            "breakdown": breakdown
        }

    def score_batch(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Score un batch de leads.

        Args:
            leads: Liste de leads

        Returns:
            Liste de leads avec scores ajoutés
        """
        scored_leads = []

        for lead in leads:
            score_result = self.score_lead(lead)

            # Ajouter le score au lead
            enriched_lead = lead.copy()
            enriched_lead['score'] = score_result['score']
            enriched_lead['score_category'] = score_result['category']
            enriched_lead['score_color'] = score_result['color']
            enriched_lead['score_breakdown'] = score_result['breakdown']

            scored_leads.append(enriched_lead)

        return scored_leads

    def segment_leads(
        self,
        leads: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Segmente les leads par catégorie de score.

        Args:
            leads: Liste de leads scorés

        Returns:
            Dict avec segments : hot, warm, cold, frozen
        """
        segments = {
            "hot": [],
            "warm": [],
            "cold": [],
            "frozen": []
        }

        for lead in leads:
            score = lead.get('score', 0)

            if score >= 70:
                segments["hot"].append(lead)
            elif score >= 50:
                segments["warm"].append(lead)
            elif score >= 30:
                segments["cold"].append(lead)
            else:
                segments["frozen"].append(lead)

        return segments

    def get_score_stats(self, leads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calcule des statistiques sur les scores.

        Args:
            leads: Liste de leads scorés

        Returns:
            Dict avec stats (moyenne, médiane, distribution)
        """
        if not leads:
            return {
                "count": 0,
                "average": 0,
                "median": 0,
                "min": 0,
                "max": 0,
                "hot_count": 0,
                "warm_count": 0,
                "cold_count": 0,
                "frozen_count": 0
            }

        scores = [lead.get('score', 0) for lead in leads]
        scores.sort()

        return {
            "count": len(scores),
            "average": sum(scores) / len(scores),
            "median": scores[len(scores) // 2],
            "min": min(scores),
            "max": max(scores),
            "hot_count": sum(1 for s in scores if s >= 70),
            "warm_count": sum(1 for s in scores if 50 <= s < 70),
            "cold_count": sum(1 for s in scores if 30 <= s < 50),
            "frozen_count": sum(1 for s in scores if s < 30)
        }


class ProspectClassifier:
    """
    Classifie les prospects selon critères ICP (Ideal Customer Profile).

    Utilisé AVANT contact pour prioriser les entreprises à prospecter.
    - A = ultra-qualifié (40% taux contact attendu)
    - B = volume (5% taux contact attendu)
    - C = opportuniste (2% taux contact attendu)

    Critères de scoring:
    - Effectif dans range ICP (50-1000)
    - CA > 10M€
    - Secteur prioritaire (codes APE)
    - Géographie (IDF prioritaire)
    - Croissance effectif > 20% (si data disponible)

    Usage:
        classifier = ProspectClassifier()
        result = classifier.classify(company_data)
        # {'prospect_class': 'A', 'points': 75, 'signals': [...], 'expected_contact_rate': 0.40}

        # Batch
        classified = classifier.classify_batch(companies)
    """

    # Départements IDF (prioritaires)
    IDF_CODES = ["75", "92", "93", "94", "95", "77", "78", "91"]

    # Codes APE prioritaires par groupe
    # Chargés depuis data/ape_groups.json si disponible, sinon valeurs par défaut
    DEFAULT_APE_GROUPS = {
        "Industrie Manufacturing": [
            "27.32Z",  # Câbles/composants électroniques
            "28.11Z", "28.12Z", "28.13Z", "28.14Z", "28.15Z",  # Machines
            "28.21Z", "28.22Z", "28.23Z", "28.24Z", "28.25Z",
            "28.29A", "28.29B", "28.30Z", "28.41Z", "28.49Z",
            "28.91Z", "28.92Z", "28.93Z", "28.94Z", "28.95Z", "28.96Z", "28.99A", "28.99B",
            "25.11Z", "25.12Z", "25.21Z", "25.29Z", "25.30Z",  # Produits métalliques
            "25.40Z", "25.50A", "25.50B", "25.61Z", "25.62A", "25.62B",
            "25.71Z", "25.72Z", "25.73A", "25.73B", "25.91Z", "25.92Z", "25.93Z", "25.94Z", "25.99A", "25.99B",
        ],
        "Services Professionnels": [
            "70.22Z",  # Conseil en gestion
            "69.20Z",  # Conseil comptable/audit
            "71.12B",  # Ingénierie/études techniques
            "71.20B",  # Analyses techniques
            "62.01Z", "62.02A", "62.02B", "62.03Z", "62.09Z",  # Informatique
            "63.11Z", "63.12Z",  # Traitement données
        ],
        "Santé Privée": [
            "86.10Z",  # Activités hospitalières
            "86.21Z",  # Médecine générale
            "86.22A", "86.22B", "86.22C",  # Spécialistes
            "86.90A", "86.90B", "86.90C", "86.90D", "86.90E", "86.90F",  # Autres santé
        ],
        "PME Croissance": [
            "10.92Z",  # Aliments animaux
            "46.21Z",  # Commerce gros céréales
            "46.31Z", "46.32A", "46.32B", "46.33Z", "46.34Z",  # Commerce gros alimentaire
        ],
    }

    # Pondération des critères (total max = 100 points)
    WEIGHTS = {
        'effectif_icp': 20,      # Effectif dans range 50-1000
        'ca_significatif': 20,   # CA > 10M€
        'secteur_prioritaire': 15,  # Code APE prioritaire
        'geo_idf': 15,           # Île-de-France
        'croissance': 30,        # Croissance effectif > 20% (bonus)
    }

    # Seuils de classification
    THRESHOLDS = {
        'A': 70,  # >= 70 points = classe A
        'B': 40,  # >= 40 points = classe B
        # < 40 = classe C
    }

    # Taux de contact attendus par classe
    EXPECTED_CONTACT_RATES = {
        'A': 0.40,  # 40%
        'B': 0.05,  # 5%
        'C': 0.02,  # 2%
    }

    def __init__(self, ape_groups: Optional[Dict[str, List[str]]] = None):
        """
        Initialise le classificateur.

        Args:
            ape_groups: Dict des groupes APE prioritaires (optionnel)
                        Si non fourni, charge depuis data/ape_groups.json ou utilise défauts
        """
        self.ape_groups = ape_groups or self._load_ape_groups()
        self._build_priority_ape_set()

    def _load_ape_groups(self) -> Dict[str, List[str]]:
        """Charge les groupes APE depuis le fichier JSON."""
        ape_file = CONFIG_PATH / "ape_groups.json"
        if ape_file.exists():
            try:
                with open(ape_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Erreur chargement ape_groups.json: {e}")
        return self.DEFAULT_APE_GROUPS

    def _build_priority_ape_set(self):
        """Construit le set des codes APE prioritaires."""
        self._priority_ape_codes = set()
        for codes in self.ape_groups.values():
            self._priority_ape_codes.update(codes)

    def classify(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classifie une entreprise selon les critères ICP.

        Args:
            company: Dict avec les données entreprise (employee_range, revenue_range,
                    ape_code, postal_code, etc.)

        Returns:
            Dict avec:
            - prospect_class: 'A', 'B', ou 'C'
            - points: score numérique (0-100)
            - signals: liste des signaux positifs détectés
            - expected_contact_rate: taux de contact attendu
        """
        points = 0
        signals = []

        # 1. Effectif dans range ICP (50-1000)
        effectif = self._parse_effectif(company.get('employee_range'))
        if effectif is not None:
            if 50 <= effectif <= 1000:
                points += self.WEIGHTS['effectif_icp']
                signals.append(f"Effectif {effectif} (ICP 50-1000)")
            elif 20 <= effectif < 50:
                # Demi-points pour PME proche du seuil
                points += self.WEIGHTS['effectif_icp'] // 2
                signals.append(f"Effectif {effectif} (proche ICP)")

        # 2. CA > 10M€
        ca = self._parse_ca(company.get('revenue_range') or company.get('chiffre_affaires'))
        if ca is not None and ca >= 10_000_000:
            points += self.WEIGHTS['ca_significatif']
            signals.append(f"CA {ca/1_000_000:.1f}M€")
        elif ca is not None and ca >= 5_000_000:
            # Demi-points pour CA 5-10M€
            points += self.WEIGHTS['ca_significatif'] // 2
            signals.append(f"CA {ca/1_000_000:.1f}M€ (proche seuil)")

        # 3. Secteur prioritaire
        ape_code = company.get('ape_code') or company.get('code_ape')
        if ape_code and self._is_priority_ape(ape_code):
            points += self.WEIGHTS['secteur_prioritaire']
            group = self._get_ape_group(ape_code)
            signals.append(f"Secteur: {group}")

        # 4. Géographie IDF
        postal_code = company.get('postal_code') or company.get('code_postal', '')
        dept = str(postal_code)[:2] if postal_code else ''
        if dept in self.IDF_CODES:
            points += self.WEIGHTS['geo_idf']
            signals.append("Île-de-France")

        # 5. Croissance effectif > 20% (si data disponible)
        growth = company.get('effectif_growth') or company.get('employee_growth')
        if growth is not None:
            try:
                growth_pct = float(growth)
                if growth_pct >= 20:
                    points += self.WEIGHTS['croissance']
                    signals.append(f"Croissance +{growth_pct:.0f}%")
                elif growth_pct >= 10:
                    points += self.WEIGHTS['croissance'] // 2
                    signals.append(f"Croissance +{growth_pct:.0f}%")
            except (ValueError, TypeError):
                pass

        # Classification finale
        if points >= self.THRESHOLDS['A']:
            prospect_class = 'A'
        elif points >= self.THRESHOLDS['B']:
            prospect_class = 'B'
        else:
            prospect_class = 'C'

        return {
            'prospect_class': prospect_class,
            'points': points,
            'signals': signals,
            'expected_contact_rate': self.EXPECTED_CONTACT_RATES[prospect_class]
        }

    def classify_batch(self, companies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Classifie un batch d'entreprises.

        Args:
            companies: Liste d'entreprises

        Returns:
            Liste d'entreprises avec classification ajoutée
        """
        classified = []
        for company in companies:
            result = self.classify(company)
            enriched = company.copy()
            enriched['prospect_class'] = result['prospect_class']
            enriched['prospect_class_points'] = result['points']
            enriched['prospect_class_signals'] = result['signals']
            enriched['expected_contact_rate'] = result['expected_contact_rate']
            classified.append(enriched)
        return classified

    def get_classification_stats(self, companies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calcule les statistiques de classification.

        Args:
            companies: Liste d'entreprises classifiées

        Returns:
            Dict avec stats par classe et projections
        """
        if not companies:
            return {
                'total': 0,
                'by_class': {'A': 0, 'B': 0, 'C': 0},
                'expected_contacts': {'A': 0, 'B': 0, 'C': 0, 'total': 0}
            }

        by_class = {'A': 0, 'B': 0, 'C': 0}
        for c in companies:
            cls = c.get('prospect_class', 'C')
            by_class[cls] = by_class.get(cls, 0) + 1

        expected_contacts = {
            'A': int(by_class['A'] * self.EXPECTED_CONTACT_RATES['A']),
            'B': int(by_class['B'] * self.EXPECTED_CONTACT_RATES['B']),
            'C': int(by_class['C'] * self.EXPECTED_CONTACT_RATES['C']),
        }
        expected_contacts['total'] = sum(expected_contacts.values())

        return {
            'total': len(companies),
            'by_class': by_class,
            'expected_contacts': expected_contacts
        }

    def _parse_effectif(self, value: Any) -> Optional[int]:
        """Parse une valeur d'effectif en entier."""
        if value is None:
            return None

        if isinstance(value, int):
            return value

        try:
            # Format "50-100" → prendre la moyenne
            s = str(value).strip()
            if '-' in s:
                parts = s.split('-')
                low = int(re.sub(r'[^\d]', '', parts[0]))
                high = int(re.sub(r'[^\d]', '', parts[1]))
                return (low + high) // 2
            # Format "100+" → prendre la valeur
            s = re.sub(r'[^\d]', '', s)
            return int(s) if s else None
        except (ValueError, TypeError, IndexError):
            return None

    def _parse_ca(self, value: Any) -> Optional[float]:
        """Parse une valeur de CA en float."""
        if value is None:
            return None

        if isinstance(value, (int, float)):
            return float(value)

        try:
            s = str(value).strip().lower()
            # Supprimer symboles
            s = s.replace('€', '').replace(' ', '').replace(',', '.')

            # Gérer les suffixes (k, m, M)
            multiplier = 1
            if s.endswith('k'):
                multiplier = 1_000
                s = s[:-1]
            elif s.endswith('m'):
                multiplier = 1_000_000
                s = s[:-1]

            return float(s) * multiplier
        except (ValueError, TypeError):
            return None

    def _is_priority_ape(self, ape_code: str) -> bool:
        """Vérifie si un code APE est prioritaire."""
        if not ape_code:
            return False
        return ape_code in self._priority_ape_codes

    def _get_ape_group(self, ape_code: str) -> str:
        """Retourne le groupe d'un code APE."""
        for group, codes in self.ape_groups.items():
            if ape_code in codes:
                return group
        return "Autre"
