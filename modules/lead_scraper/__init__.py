"""
Module Lead Scraper - Génération et enrichissement de leads B2B.

Fonctionnalités:
- Recherche SIRENE (API gouvernementale)
- Enrichissement Pappers (dirigeants, financier)
- Synchronisation HubSpot
- Déduplication triple (session, SQLite, HubSpot)
- Export multi-canal (CSV, Sheets, HubSpot)
- Gestion unifiée des contacts multi-sources
"""

from .sirene_client import SireneClient
from .pappers_client import PappersClient
from .contact_manager import ContactManager
from .enricher import Enricher
from .hubspot_client import HubSpotClient
from .query_parser import QueryParser
from .lookalike import LookalikeEngine
from .scoring import LeadScorer
from .exporter import Exporter

# Alias pour compatibilité avec code existant
LeadTracker = ContactManager

__all__ = [
    'SireneClient',
    'PappersClient',
    'ContactManager',
    'LeadTracker',  # Alias legacy
    'Enricher',
    'HubSpotClient',
    'QueryParser',
    'LookalikeEngine',
    'LeadScorer',
    'Exporter',
]
