"""
Service de déduplication réutilisable.
Utilisé par: GetSales sync, Recherche SIRENE, Import CSV

Supporte les deux schémas:
- Ancien: unified_contacts (tout dans une table)
- Nouveau: contacts + companies (tables séparées)
"""
from .matcher import (
    DeduplicationMatcher,
    MatchResult,
    MatchConfidence,
    CompanyMatchResult
)

__all__ = [
    'DeduplicationMatcher',
    'MatchResult',
    'MatchConfidence',
    'CompanyMatchResult'
]
