"""
Module Lead Scraper - Génération et enrichissement de leads B2B.

Fonctionnalités:
- Recherche SIRENE (API gouvernementale)
- Enrichissement Pappers (dirigeants, financier)
- Synchronisation HubSpot
- Déduplication triple (session, SQLite, HubSpot)
- Export multi-canal (CSV, Sheets, HubSpot)
"""

from .sirene_client import SireneClient
from .pappers_client import PappersClient
from .lead_tracker import LeadTracker
from .enricher import Enricher
from .hubspot_client import HubSpotClient
from .query_parser import QueryParser
from .lookalike import LookalikeEngine
from .scoring import LeadScorer
from .exporter import Exporter

__all__ = [
    'SireneClient',
    'PappersClient',
    'LeadTracker',
    'Enricher',
    'HubSpotClient',
    'QueryParser',
    'LookalikeEngine',
    'LeadScorer',
    'Exporter',
]
