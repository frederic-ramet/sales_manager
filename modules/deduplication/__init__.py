"""
Service de déduplication réutilisable.
Utilisé par: GetSales sync, Recherche SIRENE, Import CSV
"""
from .matcher import DeduplicationMatcher, MatchResult, MatchConfidence

__all__ = ['DeduplicationMatcher', 'MatchResult', 'MatchConfidence']
