"""
Configuration centrale de l'application Lead Gen SIRENE.
Charge les variables d'environnement et définit les constantes.
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Chargement des variables d'environnement
load_dotenv()

# Variables d'environnement
PAPPERS_API_KEY: Optional[str] = os.getenv("PAPPERS_API_KEY")
GOOGLE_SHEETS_CREDENTIALS_PATH: str = os.getenv(
    "GOOGLE_SHEETS_CREDENTIALS_PATH",
    "credentials/gcp_service_account.json"
)
DEFAULT_SHEET_ID: Optional[str] = os.getenv("DEFAULT_SHEET_ID")

# Anthropic API (pour recherche en langage naturel)
ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")

# HubSpot API (CRM et synchronisation)
HUBSPOT_API_KEY: Optional[str] = os.getenv("HUBSPOT_API_KEY")

# Google Maps API (enrichissement téléphones - Phase 2)
GOOGLE_MAPS_API_KEY: Optional[str] = os.getenv("GOOGLE_MAPS_API_KEY")

# URLs API
SIRENE_BASE_URL: str = "https://recherche-entreprises.api.gouv.fr"
PAPPERS_BASE_URL: str = "https://api.pappers.fr/v2"
HUBSPOT_BASE_URL: str = "https://api.hubapi.com"

# Limites et quotas
SIRENE_RATE_LIMIT: int = 400  # Requêtes par minute
MAX_RESULTS: int = 500  # Maximum de résultats par campagne
BATCH_SIZE: int = 25  # Taille des batchs pour enrichissement

# Paramètres de pagination SIRENE
DEFAULT_PER_PAGE: int = 25
MAX_PER_PAGE: int = 25  # Limite imposée par l'API SIRENE

# Timeouts et retries
REQUEST_TIMEOUT: int = 30  # Secondes
MAX_RETRIES: int = 3

# Chemins
DATA_DIR: str = "data"
EXPORTS_DIR: str = "data/exports"
CREDENTIALS_DIR: str = "credentials"

# Formats de date
DATE_FORMAT: str = "%Y-%m-%d"
DATETIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"
