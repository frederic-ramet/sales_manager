"""
Module GetSales - Synchronisation leads LinkedIn vers HubSpot.

Fonctionnalités:
- Récupération leads et interactions depuis GetSales.io
- Détection doublons (LinkedIn URL, email)
- Validation manuelle avec merge
- Sync interactions vers HubSpot Notes
"""

from .getsales_client import GetSalesClient
from .models import PendingLead, SyncLog, LeadInteraction, GetSalesDB
from .deduplication import DeduplicationService
from .sync_service import GetSalesSyncService

__all__ = [
    'GetSalesClient',
    'PendingLead',
    'SyncLog',
    'LeadInteraction',
    'GetSalesDB',
    'DeduplicationService',
    'GetSalesSyncService',
]
