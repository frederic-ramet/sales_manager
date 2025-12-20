"""
Module de scoring et qualification automatique des leads.
Calcule un score de qualité basé sur la complétude et la pertinence des données.
"""
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


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
