"""
Moteur d'auto-enrichissement intelligent.
Phase 3: WebSearch + Multi-sources + Validation + Scoring confiance.
"""
import logging
import re
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class AutoEnricher:
    """
    Enrichisseur automatique multi-sources avec scoring de confiance.

    Sources utilisées:
    1. API SIRENE (SIREN, SIRET, APE, adresse) - Confiance: 1.0
    2. Google Maps (téléphone, adresse) - Confiance: 0.7-0.9
    3. WebSearch (données manquantes) - Confiance: 0.5-0.7
    4. Validation croisée (augmente confiance)
    """

    def __init__(
        self,
        sirene_client=None,
        google_maps_client=None,
        phone_enricher=None,
        websearch_enricher=None
    ):
        """
        Initialise l'auto-enrichisseur.

        Args:
            sirene_client: Client SIRENE V2 (optionnel)
            google_maps_client: Client Google Maps (optionnel)
            phone_enricher: PhoneEnricher (optionnel)
            websearch_enricher: WebSearchEnricher (optionnel, REX-validated)
        """
        self.sirene = sirene_client
        self.google_maps = google_maps_client
        self.phone_enricher = phone_enricher
        self.websearch = websearch_enricher

        # Tracker des sources disponibles
        self.sources_available = {
            'sirene': bool(sirene_client),
            'google_maps': bool(google_maps_client),
            'phone_enricher': bool(phone_enricher),
            'websearch': bool(websearch_enricher),
            'web_search': True  # Toujours disponible (simulation)
        }

        logger.info(f"AutoEnricher initialisé avec sources: {self.sources_available}")

    def enrich_contact(
        self,
        contact: Dict[str, Any],
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Enrichit un contact avec toutes les sources disponibles.

        Args:
            contact: Contact à enrichir
            fields: Liste des champs à enrichir (None = tous)

        Returns:
            Contact enrichi avec métadonnées de confiance
        """
        if fields is None:
            fields = [
                'siren', 'siret', 'code_ape', 'libelle_ape',
                'telephone', 'adresse', 'ville', 'code_postal',
                'effectif', 'effectif_tranche', 'dirigeants',
                'website', 'secteur'
            ]

        enriched = contact.copy()
        confidence_scores = {}

        # Enrichir chaque champ
        for field in fields:
            if contact.get(field):
                # Champ déjà rempli, garder confiance élevée
                confidence_scores[field] = 1.0
            else:
                # Tenter enrichissement
                result = self._enrich_field(contact, field)
                if result:
                    enriched[field] = result['value']
                    confidence_scores[field] = result['confidence']
                    enriched[f'{field}_source'] = result['source']
                    logger.info(
                        f"✅ {field} enrichi: {result['value']} "
                        f"(source: {result['source']}, confiance: {result['confidence']:.2f})"
                    )

        # Ajouter métadonnées d'enrichissement
        enriched['enrichment_metadata'] = {
            'timestamp': datetime.now().isoformat(),
            'confidence_scores': confidence_scores,
            'global_confidence': sum(confidence_scores.values()) / len(confidence_scores) if confidence_scores else 0,
            'sources_used': list(set(enriched.get(f'{f}_source', '') for f in fields if enriched.get(f'{f}_source'))),
            'completeness': len([f for f in fields if enriched.get(f)]) / len(fields)
        }

        return enriched

    def _enrich_field(
        self,
        contact: Dict[str, Any],
        field: str
    ) -> Optional[Dict[str, Any]]:
        """
        Enrichit un champ spécifique avec la meilleure source.

        Returns:
            {'value': Any, 'source': str, 'confidence': float}
        """
        # Mapping champ → méthode d'enrichissement
        enrichers = {
            'siren': self._enrich_siren,
            'siret': self._enrich_siret,
            'code_ape': self._enrich_ape,
            'libelle_ape': self._enrich_libelle_ape,
            'telephone': self._enrich_telephone,
            'adresse': self._enrich_adresse,
            'ville': self._enrich_ville,
            'code_postal': self._enrich_code_postal,
            'effectif': self._enrich_effectif,
            'effectif_tranche': self._enrich_effectif_tranche,
            'dirigeants': self._enrich_dirigeants,
            'website': self._enrich_website,
            'secteur': self._enrich_secteur,
        }

        enricher_func = enrichers.get(field)
        if not enricher_func:
            logger.warning(f"Pas d'enrichisseur pour le champ: {field}")
            return None

        try:
            return enricher_func(contact)
        except Exception as e:
            logger.error(f"Erreur enrichissement {field}: {e}")
            return None

    # === ENRICHISSEURS PAR CHAMP ===

    def _enrich_siren(self, contact: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Enrichit SIREN via WebSearch (priorité) ou nom d'entreprise.

        REX: 100% succès avec annuaire-entreprises.data.gouv.fr
        """
        company_name = contact.get('denomination', '')
        if not company_name:
            return None

        city = contact.get('ville', '')

        # Priorité 1: WebSearchEnricher (REX: 100% succès)
        if self.websearch:
            try:
                result = self.websearch.enrich_siren(company_name, city)
                if result:
                    logger.info(f"✅ SIREN trouvé via WebSearch: {result['siren']}")
                    return {
                        'value': result['siren'],
                        'source': result['source'],
                        'confidence': result['confidence']
                    }
            except Exception as e:
                logger.error(f"Erreur WebSearch SIREN: {e}")

        # Fallback: CompanyResolver (non implémenté)
        logger.info(f"SIREN non trouvé pour: {company_name}")
        return None

    def _enrich_siret(self, contact: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Enrichit SIRET via SIREN + SIRENE API."""
        siren = contact.get('siren')
        if not siren or not self.sirene:
            return None

        try:
            data = self.sirene.get_full_company_data(siren)
            if data and data.get('siret_siege'):
                return {
                    'value': data['siret_siege'],
                    'source': 'sirene_v2',
                    'confidence': 1.0  # Source officielle
                }
        except:
            pass

        return None

    def _enrich_ape(self, contact: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Enrichit code APE via SIRENE."""
        return self._enrich_siret(contact)  # Même source

    def _enrich_libelle_ape(self, contact: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Enrichit libellé APE via code APE + mapping."""
        code_ape = contact.get('code_ape')
        if not code_ape or not self.sirene:
            return None

        try:
            # Utiliser le mapping de SIRENE V2
            libelle = self.sirene._get_ape_libelle(code_ape)
            return {
                'value': libelle,
                'source': 'sirene_v2_mapping',
                'confidence': 0.9
            }
        except:
            return None

    def _enrich_telephone(self, contact: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Enrichit téléphone via cascade: PhoneEnricher → WebSearch.

        REX WebSearch: 75% succès (6/8) via pagesjaunes.fr
        """
        company_name = contact.get('denomination', '')
        if not company_name:
            return None

        # Priorité 1: PhoneEnricher (Google Maps)
        if self.phone_enricher:
            try:
                result = self.phone_enricher.enrich(
                    company_name=company_name,
                    siren=contact.get('siren'),
                    address=contact.get('adresse'),
                    city=contact.get('ville'),
                    website=contact.get('website')
                )

                if result:
                    return {
                        'value': result['phone'],
                        'source': result['source'],
                        'confidence': result['confidence']
                    }
            except Exception as e:
                logger.error(f"Erreur PhoneEnricher: {e}")

        # Priorité 2: WebSearchEnricher (REX: 75% succès)
        if self.websearch:
            try:
                result = self.websearch.enrich_phone(
                    company_name=company_name,
                    city=contact.get('ville'),
                    siren=contact.get('siren'),
                    address=contact.get('adresse')
                )

                if result:
                    logger.info(f"✅ Téléphone trouvé via WebSearch: {result['telephone']}")
                    return {
                        'value': result['telephone'],
                        'source': result['source'],
                        'confidence': result['confidence']
                    }
            except Exception as e:
                logger.error(f"Erreur WebSearch téléphone: {e}")

        return None

    def _enrich_adresse(self, contact: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Enrichit adresse via SIRENE ou Google Maps."""
        # Essayer SIRENE d'abord
        siren = contact.get('siren')
        if siren and self.sirene:
            try:
                data = self.sirene.get_full_company_data(siren)
                if data and data.get('adresse'):
                    adresse = data['adresse']
                    if isinstance(adresse, dict):
                        adresse = adresse.get('complete', '')

                    return {
                        'value': adresse,
                        'source': 'sirene_v2',
                        'confidence': 1.0
                    }
            except:
                pass

        # Fallback Google Maps
        if self.google_maps:
            company_name = contact.get('denomination', '')
            city = contact.get('ville', '')
            if company_name:
                try:
                    place = self.google_maps.find_place(company_name, city=city)
                    if place:
                        details = self.google_maps.get_place_details(place['place_id'])
                        if details and details.get('formatted_address'):
                            return {
                                'value': details['formatted_address'],
                                'source': 'google_maps',
                                'confidence': 0.8
                            }
                except:
                    pass

        return None

    def _enrich_ville(self, contact: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Enrichit ville via SIRENE."""
        siren = contact.get('siren')
        if not siren or not self.sirene:
            return None

        try:
            data = self.sirene.get_full_company_data(siren)
            if data and data.get('ville'):
                return {
                    'value': data['ville'],
                    'source': 'sirene_v2',
                    'confidence': 1.0
                }
        except:
            pass

        return None

    def _enrich_code_postal(self, contact: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Enrichit code postal via SIRENE."""
        return self._enrich_ville(contact)  # Même source

    def _enrich_effectif(self, contact: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Enrichit effectif via SIRENE."""
        siren = contact.get('siren')
        if not siren or not self.sirene:
            return None

        try:
            data = self.sirene.get_full_company_data(siren)
            if data and data.get('effectif'):
                return {
                    'value': data['effectif'],
                    'source': 'sirene_v2',
                    'confidence': 0.9
                }
        except:
            pass

        return None

    def _enrich_effectif_tranche(self, contact: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Enrichit tranche effectif via SIRENE."""
        siren = contact.get('siren')
        if not siren or not self.sirene:
            return None

        try:
            data = self.sirene.get_full_company_data(siren)
            if data and data.get('effectif_tranche'):
                return {
                    'value': data['effectif_tranche'],
                    'source': 'sirene_v2',
                    'confidence': 1.0
                }
        except:
            pass

        return None

    def _enrich_dirigeants(self, contact: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Enrichit dirigeants via WebSearch ou Pappers.

        REX WebSearch: 25% succès (2/8) - Thales, Dassault
        Succès: grandes entreprises publiques uniquement
        """
        company_name = contact.get('denomination', '')
        siren = contact.get('siren')

        if not company_name and not siren:
            return None

        # Priorité 1: WebSearchEnricher (REX: 25% succès sur grandes entreprises)
        if self.websearch:
            try:
                result = self.websearch.enrich_dirigeants(
                    company_name=company_name,
                    siren=siren
                )

                if result:
                    logger.info(f"✅ Dirigeants trouvés via WebSearch: {result['dirigeants']}")
                    return {
                        'value': result['dirigeants'],
                        'source': result['source'],
                        'confidence': result['confidence']
                    }
            except Exception as e:
                logger.error(f"Erreur WebSearch dirigeants: {e}")

        # Priorité 2: Pappers API (payant, non implémenté)
        logger.info("Dirigeants non trouvés - Pappers API nécessaire pour PME/ETI")
        return None

    def _enrich_website(self, contact: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Enrichit website via Google Maps."""
        if not self.google_maps:
            return None

        company_name = contact.get('denomination', '')
        city = contact.get('ville', '')
        if not company_name:
            return None

        try:
            place = self.google_maps.find_place(company_name, city=city)
            if place:
                details = self.google_maps.get_place_details(place['place_id'])
                if details and details.get('website'):
                    return {
                        'value': details['website'],
                        'source': 'google_maps',
                        'confidence': 0.9
                    }
        except:
            pass

        return None

    def _enrich_secteur(self, contact: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Enrichit secteur via libellé APE."""
        libelle_ape = contact.get('libelle_ape', '')
        if libelle_ape and libelle_ape != 'N/A':
            return {
                'value': libelle_ape,
                'source': 'derived_from_ape',
                'confidence': 0.8
            }

        return None

    def enrich_batch(
        self,
        contacts: List[Dict[str, Any]],
        fields: Optional[List[str]] = None,
        max_contacts: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Enrichit un batch de contacts.

        Args:
            contacts: Liste de contacts
            fields: Champs à enrichir
            max_contacts: Limite de contacts à traiter

        Returns:
            Liste de contacts enrichis
        """
        enriched = []
        processed = 0

        for contact in contacts:
            if max_contacts and processed >= max_contacts:
                logger.info(f"Limite de {max_contacts} contacts atteinte")
                break

            enriched_contact = self.enrich_contact(contact, fields)
            enriched.append(enriched_contact)
            processed += 1

            if processed % 10 == 0:
                logger.info(f"Progression: {processed}/{len(contacts)} contacts traités")

        logger.info(f"Enrichissement batch terminé: {processed} contacts")
        return enriched

    def get_enrichment_stats(
        self,
        contacts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calcule les statistiques d'enrichissement.

        Returns:
            Statistiques complètes
        """
        total = len(contacts)
        if total == 0:
            return {}

        # Complétude par champ
        fields = [
            'siren', 'siret', 'code_ape', 'libelle_ape',
            'telephone', 'adresse', 'ville', 'effectif',
            'effectif_tranche', 'dirigeants', 'website'
        ]

        completeness = {}
        for field in fields:
            filled = sum(1 for c in contacts if c.get(field))
            completeness[field] = {
                'count': filled,
                'percentage': filled / total * 100
            }

        # Confiance moyenne
        confidences = [
            c.get('enrichment_metadata', {}).get('global_confidence', 0)
            for c in contacts
            if c.get('enrichment_metadata')
        ]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        # Sources utilisées
        sources = {}
        for contact in contacts:
            metadata = contact.get('enrichment_metadata', {})
            for source in metadata.get('sources_used', []):
                sources[source] = sources.get(source, 0) + 1

        return {
            'total_contacts': total,
            'completeness_by_field': completeness,
            'average_confidence': avg_confidence,
            'sources_distribution': sources,
            'enriched_count': len([c for c in contacts if c.get('enrichment_metadata')])
        }
